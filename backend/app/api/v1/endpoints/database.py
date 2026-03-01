"""
Database management endpoints – query execution, table browser, backup/restore.
"""
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_auth_db, get_char_db, get_playerbots_db, get_world_db
from app.core.security import get_current_user
from app.models.schemas import SqlQueryRequest, SqlQueryResponse, TableListResponse

router = APIRouter(prefix="/database", tags=["Database Management"])


async def _is_playerbots_available() -> bool:
    """Return True if the mod-playerbots module directory exists in the AC modules path."""
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    ac_path = Path(s.get("AC_PATH", "/opt/azerothcore"))
    return (ac_path / "modules" / "mod-playerbots").is_dir()


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
# These patterns are blocked to prevent accidental data loss or modification
_BLOCKED_PATTERNS = [
    "DROP DATABASE",
    "DROP TABLE",
    "DROP USER",
    "SHUTDOWN",
    "RESET MASTER",
    "RESET SLAVE",
    "TRUNCATE",
]

# Patterns that indicate write operations (blocked in read-only mode)
_WRITE_PATTERNS = [
    "INSERT INTO",
    "UPDATE ",
    "UPDATE\n",
    "DELETE FROM",
    "DELETE\n",
    "ALTER TABLE",
    "ALTER USER",
    "CREATE TABLE",
    "CREATE DATABASE",
    "CREATE USER",
    "GRANT ",
    "REVOKE ",
]


def _safety_check(query: str) -> None:
    """
    Check if a query contains blocked patterns.
    Raises HTTPException if the query is blocked.
    """
    upper = query.upper().strip()
    
    # Check for absolutely blocked patterns
    for pat in _BLOCKED_PATTERNS:
        if pat in upper:
            raise HTTPException(
                status_code=403,
                detail=f"Query blocked for safety: contains '{pat}'"
            )
    
    # Check for write operations - only allow SELECT, SHOW, DESCRIBE, EXPLAIN
    first_word = upper.split()[0] if upper.split() else ""
    allowed_first_words = {"SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "WITH"}
    
    if first_word not in allowed_first_words:
        # Check if it matches any write pattern
        for pat in _WRITE_PATTERNS:
            if upper.startswith(pat.strip()):
                raise HTTPException(
                    status_code=403,
                    detail=f"Write operations are not allowed. Query starts with '{first_word}'"
                )


@router.get("/tables/{database}", response_model=TableListResponse)
async def list_tables(
    database: str,
    _: dict = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_auth_db),
    char_db: AsyncSession = Depends(get_char_db),
    world_db: AsyncSession = Depends(get_world_db),
    playerbots_db: AsyncSession = Depends(get_playerbots_db),
):
    """List all tables in the specified AzerothCore database."""
    db_sessions = {"auth": auth_db, "characters": char_db, "world": world_db, "playerbots": playerbots_db}
    if database == "playerbots" and not await _is_playerbots_available():
        raise HTTPException(status_code=404, detail="Playerbots database is not available")
    db = db_sessions.get(database)
    if db is None:
        raise HTTPException(status_code=400, detail="Unknown database")
    rows = await db.execute(text("SHOW TABLES"))
    tables = [r[0] for r in rows]
    return TableListResponse(database=database, tables=tables)


@router.post("/query", response_model=SqlQueryResponse)
async def execute_query(
    req: SqlQueryRequest,
    _: dict = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_auth_db),
    char_db: AsyncSession = Depends(get_char_db),
    world_db: AsyncSession = Depends(get_world_db),
    playerbots_db: AsyncSession = Depends(get_playerbots_db),
):
    """
    Execute a SQL query against an AzerothCore database.
    Only SELECT, SHOW, DESCRIBE, and EXPLAIN queries are allowed.
    Write operations (INSERT, UPDATE, DELETE, etc.) are blocked for safety.
    """
    _safety_check(req.query)
    db_sessions = {"auth": auth_db, "characters": char_db, "world": world_db, "playerbots": playerbots_db}
    if req.database == "playerbots" and not await _is_playerbots_available():
        raise HTTPException(status_code=404, detail="Playerbots database is not available")
    db: AsyncSession = db_sessions.get(req.database)
    if db is None:
        raise HTTPException(status_code=400, detail="Unknown database")

    start = time.monotonic()
    try:
        result = await db.execute(text(req.query))
        elapsed = (time.monotonic() - start) * 1000

        columns = list(result.keys())
        rows: list[list[Any]] = [list(r) for r in result.fetchmany(req.max_rows)]

        return SqlQueryResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=round(elapsed, 2),
            is_select=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Query error: {exc}")


@router.get("/table/{database}/{table_name}")
async def browse_table(
    database: str,
    table_name: str,
    page: int = 1,
    page_size: int = 50,
    _: dict = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_auth_db),
    char_db: AsyncSession = Depends(get_char_db),
    world_db: AsyncSession = Depends(get_world_db),
    playerbots_db: AsyncSession = Depends(get_playerbots_db),
):
    """Browse a table with pagination."""
    db_sessions = {"auth": auth_db, "characters": char_db, "world": world_db, "playerbots": playerbots_db}
    if database == "playerbots" and not await _is_playerbots_available():
        raise HTTPException(status_code=404, detail="Playerbots database is not available")
    db = db_sessions.get(database)
    if db is None:
        raise HTTPException(status_code=400, detail="Unknown database")
    offset = (page - 1) * page_size
    start = time.monotonic()
    try:
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
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/backup")
async def backup_database(
    database: str,
    _: dict = Depends(get_current_user),
):
    """Trigger a mysqldump backup of the specified database."""
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()

    playerbots_available = await _is_playerbots_available()
    valid = {"auth", "characters", "world", "all"}
    if playerbots_available:
        valid.add("playerbots")
    if database not in valid:
        allowed = "auth|characters|world" + ("|playerbots" if playerbots_available else "") + "|all"
        raise HTTPException(status_code=400, detail=f"database must be {allowed}")

    # Build the map of db logical name → actual db name and credentials
    db_info = {
        "auth":       {"name": s["AC_AUTH_DB_NAME"],        "host": s["AC_AUTH_DB_HOST"],        "user": s["AC_AUTH_DB_USER"],        "password": s["AC_AUTH_DB_PASSWORD"]},
        "characters": {"name": s["AC_CHAR_DB_NAME"],        "host": s["AC_AUTH_DB_HOST"],        "user": s["AC_AUTH_DB_USER"],        "password": s["AC_AUTH_DB_PASSWORD"]},
        "world":      {"name": s["AC_WORLD_DB_NAME"],       "host": s["AC_AUTH_DB_HOST"],        "user": s["AC_AUTH_DB_USER"],        "password": s["AC_AUTH_DB_PASSWORD"]},
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
            results.append({"database": target, "path": str(out_file), "size_bytes": out_file.stat().st_size, "success": True})
        except Exception as exc:
            results.append({"database": target, "success": False, "error": str(exc)})

    return {"backups": results}

