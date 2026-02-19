from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Optional

from app.core.security import get_current_user
from app.services.logs import log_manager as lm

router = APIRouter(prefix="/logs", tags=["Log Management"])


@router.get("/sources")
async def list_sources(_: dict = Depends(get_current_user)):
    """List log sources that currently have accessible log files."""
    return {"sources": await lm.list_available_sources()}


@router.get("/{source}")
async def get_logs(
    source: str,
    lines: int = Query(default=500, ge=1, le=5000),
    level: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    _: dict = Depends(get_current_user),
):
    """
    Fetch log entries from a log source.
    - `source`: worldserver | authserver | gm | db_errors | arena | char
    - `lines`: number of tail lines (when no search)
    - `level`: filter by log level (ERROR, WARN, INFO, DEBUG)
    - `search`: full-text search pattern (regex supported)
    """
    if search or level:
        entries = await lm.search_logs(source, search or "", level=level)
    else:
        entries = await lm.read_tail(source, lines=lines)
    return {"source": source, "count": len(entries), "entries": entries}


@router.get("/{source}/size")
async def get_log_size(source: str, _: dict = Depends(get_current_user)):
    """Return the size in bytes of a log file."""
    size = await lm.get_log_file_size(source)
    return {"source": source, "size_bytes": size}


@router.get("/{source}/download")
async def download_log(source: str, _: dict = Depends(get_current_user)):
    """Download the raw log file."""
    log_files = {
        "worldserver": "Server.log",
        "authserver": "Auth.log",
        "gm": "GMCommands.log",
        "db_errors": "DBErrors.log",
        "arena": "ArenaTeam.log",
        "char": "Char.log",
    }
    filename = log_files.get(source)
    if not filename:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown log source: {source}")
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    path = Path(s["AC_LOG_PATH"]) / filename
    if not path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Log file not found: {path}")
    return FileResponse(
        path=str(path),
        media_type="text/plain",
        filename=filename,
    )

