import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from typing import Optional

from app.core.security import get_current_user
from app.services.logs import (
    list_available_sources,
    read_tail,
    search_logs,
    get_log_file_size,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/logs", tags=["Log Management"])


@router.get("/sources")
async def list_sources(
    instance_id: Optional[int] = Query(default=None),
    _: dict = Depends(get_current_user),
):
    """List log sources that currently have accessible log files."""
    return {"sources": await list_available_sources(instance_id)}


@router.get("/{source}")
async def get_logs(
    source: str,
    lines: int = Query(default=500, ge=1, le=5000),
    level: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    instance_id: Optional[int] = Query(default=None),
    _: dict = Depends(get_current_user),
):
    """
    Fetch log entries from a log source.
    - `source`: worldserver | authserver | gm | db_errors | arena | char
    - `lines`: number of tail lines (when no search)
    - `level`: filter by log level (ERROR, WARN, INFO, DEBUG)
    - `search`: full-text search pattern (regex supported)
    - `instance_id`: scope to a specific worldserver instance's log directory
    """
    if search or level:
        entries = await search_logs(source, search or "", level=level, instance_id=instance_id)
    else:
        entries = await read_tail(source, lines=lines, instance_id=instance_id)
    return {"source": source, "count": len(entries), "entries": entries}


@router.get("/{source}/size")
async def get_log_size(
    source: str,
    instance_id: Optional[int] = Query(default=None),
    _: dict = Depends(get_current_user),
):
    """Return the size in bytes of a log file."""
    size = await get_log_file_size(source, instance_id)
    return {"source": source, "size_bytes": size}


@router.get("/{source}/download")
async def download_log(
    source: str,
    instance_id: Optional[int] = Query(default=None),
    _: dict = Depends(get_current_user),
):
    """Download the raw log file."""
    log_files = {
        "worldserver": "Server.log",
        "authserver": "Auth.log",
        "gm": "GMCommands.log",
        "db_errors": "Errors.log",
        "arena": "ArenaTeam.log",
        "char": "Char.log",
    }
    filename = log_files.get(source)
    if not filename:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown log source: {source}")
    from app.services.logs.log_manager import _get_log_path
    path = await _get_log_path(source, instance_id)
    if not path or not path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Log file not found")
    return FileResponse(
        path=str(path),
        media_type="text/plain",
        filename=filename,
    )

