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

from app.core.database import get_auth_db, get_char_db, get_world_db
from app.core.security import get_current_user
from app.models.schemas import SqlQueryRequest, SqlQueryResponse, TableListResponse

router = APIRouter(prefix="/database", tags=["Database Management"])

# Safety: block destructive single-table drops without WHERE
_BLOCKED_PATTERNS = ["DROP DATABASE", "SHUTDOWN", "RESET MASTER", "RESET SLAVE"]


def _safety_check(query: str) -> None:
    upper = query.upper().strip()
    for pat in _BLOCKED_PATTERNS:
        if pat in upper:
            raise HTTPException(status_code=403, detail=f"Query blocked for safety: contains '{pat}'")


@router.get("/tables/{database}", response_model=TableListResponse)
async def list_tables(
    database: str,
    _: dict = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_auth_db),
    char_db: AsyncSession = Depends(get_char_db),
    world_db: AsyncSession = Depends(get_world_db),
):
    """List all tables in the specified AzerothCore database."""
    db_sessions = {"auth": auth_db, "characters": char_db, "world": world_db}
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
):
    """
    Execute a SQL query against an AzerothCore database.
    SELECT queries return rows; others return affected row count.
    """
    _safety_check(req.query)
    db_sessions = {"auth": auth_db, "characters": char_db, "world": world_db}
    db: AsyncSession = db_sessions.get(req.database)
    if db is None:
        raise HTTPException(status_code=400, detail="Unknown database")

    is_select = req.query.strip().upper().startswith("SELECT")
    start = time.monotonic()
    try:
        result = await db.execute(text(req.query))
        if not is_select:
            await db.commit()
        elapsed = (time.monotonic() - start) * 1000

        if is_select:
            columns = list(result.keys())
            rows: list[list[Any]] = [list(r) for r in result.fetchmany(req.max_rows)]
        else:
            columns = ["affected_rows"]
            rows = [[result.rowcount]]

        return SqlQueryResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=round(elapsed, 2),
            is_select=is_select,
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
):
    """Browse a table with pagination."""
    db_sessions = {"auth": auth_db, "characters": char_db, "world": world_db}
    db = db_sessions.get(database)
    if db is None:
        raise HTTPException(status_code=400, detail="Unknown database")
    offset = (page - 1) * page_size
    try:
        result = await db.execute(
            text(f"SELECT * FROM `{table_name}` LIMIT :lim OFFSET :off"),
            {"lim": page_size, "off": offset},
        )
        columns = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
        count_result = await db.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
        total = count_result.scalar()
        return {"columns": columns, "rows": rows, "total": total, "page": page, "page_size": page_size}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/backup")
async def backup_database(
    database: str,
    _: dict = Depends(get_current_user),
):
    """Trigger a mysqldump backup of the specified database."""
    if database not in ("auth", "characters", "world", "all"):
        raise HTTPException(status_code=400, detail="database must be auth|characters|world|all")

    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()

    db_names = {
        "auth": s["AC_AUTH_DB_NAME"],
        "characters": s["AC_CHAR_DB_NAME"],
        "world": s["AC_WORLD_DB_NAME"],
    }

    backup_dir = Path("/tmp/azerothpanel_backups")
    backup_dir.mkdir(exist_ok=True)
    results = []

    targets = list(db_names.keys()) if database == "all" else [database]
    for target in targets:
        db_name = db_names[target]
        out_file = backup_dir / f"{db_name}_{int(time.time())}.sql"
        cmd = [
            "mysqldump",
            f"-h{s['AC_AUTH_DB_HOST']}",
            f"-u{s['AC_AUTH_DB_USER']}",
            f"-p{s['AC_AUTH_DB_PASSWORD']}",
            db_name,
        ]
        try:
            with open(out_file, "w") as f:
                subprocess.run(cmd, stdout=f, check=True, timeout=300)
            results.append({"database": target, "path": str(out_file), "size_bytes": out_file.stat().st_size, "success": True})
        except Exception as exc:
            results.append({"database": target, "success": False, "error": str(exc)})

    return {"backups": results}

