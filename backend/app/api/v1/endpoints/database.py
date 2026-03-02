"""
Database management endpoints – query execution, table browser, backup/restore.

Per-instance character DB support
----------------------------------
Any endpoint that accesses the ``characters`` database accepts an optional
``instance_id`` query parameter (or ``instance_id`` field in the JSON body for
POST endpoints).  When supplied the panel looks up the corresponding
``WorldServerInstance`` and uses its ``char_db_*`` credential overrides
instead of the global ``AC_CHAR_DB_*`` settings.  All other database targets
(auth, world, playerbots) always use the global settings.
"""
import logging
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import (
    get_auth_db, get_char_db_for_instance,
    get_playerbots_db, get_world_db,
)
from app.core.security import get_current_user
from app.models.schemas import SqlQueryRequest, SqlQueryResponse, TableListResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/database", tags=["Database Management"])


async def _is_playerbots_available() -> bool:
    """Return True if the mod-playerbots module directory exists in the AC modules path."""
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    ac_path = Path(s.get("AC_PATH", "/opt/azerothcore"))
    return (ac_path / "modules" / "mod-playerbots").is_dir()


@asynccontextmanager
async def _db_session(database: str, instance_id: int | None = None):
    """
    Async context manager that yields the correct AsyncSession for *database*.

    For the ``characters`` database, ``instance_id`` selects per-instance
    credentials when set; otherwise the global settings are used.
    """
    if database == "characters":
        async for session in get_char_db_for_instance(instance_id):
            yield session
            return
    elif database == "auth":
        async for session in get_auth_db():
            yield session
            return
    elif database == "world":
        async for session in get_world_db():
            yield session
            return
    elif database == "playerbots":
        async for session in get_playerbots_db():
            yield session
            return
    else:
        raise HTTPException(status_code=400, detail=f"Unknown database '{database}'")


@router.get("/available")
async def get_available_databases(_: dict = Depends(get_current_user)):
    """
    Return the list of database targets that can be queried.
    Includes 'playerbots' only when the mod-playerbots module directory is present.
    """
    databases = ["auth", "characters", "world"]
    if await _is_playerbots_available():
        databases.append("playerbots")
    return {"databases": databases}


# Safety: block destructive operations
_BLOCKED_PATTERNS = [
    "DROP DATABASE", "DROP TABLE", "DROP USER",
    "SHUTDOWN", "RESET MASTER", "RESET SLAVE", "TRUNCATE",
]

_WRITE_PATTERNS = [
    "INSERT INTO", "UPDATE ", "UPDATE\n", "DELETE FROM", "DELETE\n",
    "ALTER TABLE", "ALTER USER", "CREATE TABLE", "CREATE DATABASE",
    "CREATE USER", "GRANT ", "REVOKE ",
]


def _safety_check(query: str) -> None:
    upper = query.upper().strip()
    for pat in _BLOCKED_PATTERNS:
        if pat in upper:
            raise HTTPException(
                status_code=403,
                detail=f"Query blocked for safety: contains '{pat}'"
            )
    first_word = upper.split()[0] if upper.split() else ""
    allowed_first_words = {"SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "WITH"}
    if first_word not in allowed_first_words:
        for pat in _WRITE_PATTERNS:
            if upper.startswith(pat.strip()):
                raise HTTPException(
                    status_code=403,
                    detail=f"Write operations are not allowed. Query starts with '{first_word}'"
                )


@router.get("/tables/{database}", response_model=TableListResponse)
async def list_tables(
    database: str,
    instance_id: Optional[int] = Query(None, description="Worldserver instance ID (scopes characters DB)"),
    _: dict = Depends(get_current_user),
):
    """List all tables in the specified AzerothCore database."""
    if database == "playerbots" and not await _is_playerbots_available():
        raise HTTPException(status_code=404, detail="Playerbots database is not available")
    async with _db_session(database, instance_id) as db:
        rows = await db.execute(text("SHOW TABLES"))
        tables = [r[0] for r in rows]
    return TableListResponse(database=database, tables=tables)


@router.post("/query", response_model=SqlQueryResponse)
async def execute_query(
    req: SqlQueryRequest,
    _: dict = Depends(get_current_user),
):
    """
    Execute a SQL query against an AzerothCore database.
    Only SELECT, SHOW, DESCRIBE, and EXPLAIN are allowed.

    Pass ``instance_id`` in the request body to scope ``characters`` queries
    to a specific worldserver instance's character database.
    """
    _safety_check(req.query)
    if req.database == "playerbots" and not await _is_playerbots_available():
        raise HTTPException(status_code=404, detail="Playerbots database is not available")

    start = time.monotonic()
    try:
        async with _db_session(req.database, req.instance_id) as db:
            result = await db.execute(text(req.query))
            elapsed = (time.monotonic() - start) * 1000
            columns = list(result.keys())
            rows: list[list[Any]] = [list(r) for r in result.fetchmany(req.max_rows)]
        logger.debug(
            "Query on %s returned %d rows in %.1fms",
            req.database, len(rows), elapsed,
        )
        return SqlQueryResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=round(elapsed, 2),
            is_select=True,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Query error on %s: %s", req.database, exc)
        raise HTTPException(status_code=400, detail=f"Query error: {exc}")


@router.get("/table/{database}/{table_name}")
async def browse_table(
    database: str,
    table_name: str,
    page: int = 1,
    page_size: int = 50,
    instance_id: Optional[int] = Query(None, description="Worldserver instance ID (scopes characters DB)"),
    _: dict = Depends(get_current_user),
):
    """Browse a table with pagination."""
    if database == "playerbots" and not await _is_playerbots_available():
        raise HTTPException(status_code=404, detail="Playerbots database is not available")
    offset = (page - 1) * page_size
    start = time.monotonic()
    try:
        async with _db_session(database, instance_id) as db:
            result = await db.execute(
                text(f"SELECT * FROM `{table_name}` LIMIT :lim OFFSET :off"),
                {"lim": page_size, "off": offset},
            )
            columns = list(result.keys())
            rows = [list(r) for r in result.fetchall()]
            count_result = await db.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
            total = count_result.scalar()
        elapsed = (time.monotonic() - start) * 1000
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": round(elapsed, 2),
            "is_select": True,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/backup")
async def backup_database(
    database: str,
    instance_id: Optional[int] = Query(None, description="Worldserver instance ID for per-instance characters DB backup"),
    _: dict = Depends(get_current_user),
):
    """Trigger a mysqldump backup of the specified database."""
    from app.services.panel_settings import get_settings_dict
    from app.core.database import PanelSessionLocal
    from app.models.panel_models import WorldServerInstance
    from sqlalchemy import select as sa_select

    s = await get_settings_dict()

    playerbots_available = await _is_playerbots_available()
    valid = {"auth", "characters", "world", "all"}
    if playerbots_available:
        valid.add("playerbots")
    if database not in valid:
        allowed = "auth|characters|world" + ("|playerbots" if playerbots_available else "") + "|all"
        raise HTTPException(status_code=400, detail=f"database must be {allowed}")

    # Resolve per-instance characters DB credentials if needed
    char_host = s["AC_CHAR_DB_HOST"]
    char_user = s["AC_CHAR_DB_USER"]
    char_password = s["AC_CHAR_DB_PASSWORD"]
    char_name = s["AC_CHAR_DB_NAME"]

    if instance_id is not None:
        async with PanelSessionLocal() as psess:
            result = await psess.execute(
                sa_select(WorldServerInstance).where(WorldServerInstance.id == instance_id)
            )
            inst = result.scalar_one_or_none()
        if inst is not None:
            if inst.char_db_host:
                char_host = inst.char_db_host
            if inst.char_db_user:
                char_user = inst.char_db_user
            if inst.char_db_password:
                char_password = inst.char_db_password
            if inst.char_db_name:
                char_name = inst.char_db_name

    db_info = {
        "auth":       {"name": s["AC_AUTH_DB_NAME"],  "host": s["AC_AUTH_DB_HOST"],  "user": s["AC_AUTH_DB_USER"],  "password": s["AC_AUTH_DB_PASSWORD"]},
        "characters": {"name": char_name,              "host": char_host,             "user": char_user,             "password": char_password},
        "world":      {"name": s["AC_WORLD_DB_NAME"], "host": s["AC_WORLD_DB_HOST"], "user": s["AC_WORLD_DB_USER"], "password": s["AC_WORLD_DB_PASSWORD"]},
    }
    if playerbots_available:
        db_info["playerbots"] = {
            "name":     s["AC_PLAYERBOTS_DB_NAME"],
            "host":     s["AC_PLAYERBOTS_DB_HOST"],
            "user":     s["AC_PLAYERBOTS_DB_USER"],
            "password": s["AC_PLAYERBOTS_DB_PASSWORD"],
        }

    backup_dir = Path("/tmp/azerothpanel_backups")
    backup_dir.mkdir(exist_ok=True)
    results = []

    targets = list(db_info.keys()) if database == "all" else [database]
    for target in targets:
        info = db_info[target]
        out_file = backup_dir / f"{info['name']}_{int(time.time())}.sql"
        cmd = [
            "mysqldump",
            f"-h{info['host']}",
            f"-u{info['user']}",
            f"-p{info['password']}",
            info["name"],
        ]
        try:
            with open(out_file, "w") as f:
                subprocess.run(cmd, stdout=f, check=True, timeout=300)
            logger.info("Backup of '%s' written to %s (%d bytes)", target, out_file, out_file.stat().st_size)
            results.append({"database": target, "path": str(out_file), "size_bytes": out_file.stat().st_size, "success": True})
        except Exception as exc:
            logger.error("Backup of '%s' failed: %s", target, exc)
            results.append({"database": target, "success": False, "error": str(exc)})

    return {"backups": results}
