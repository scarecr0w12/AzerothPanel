"""
AzerothCore log file manager.

Provides functions for reading, searching, and tailing log files from the
AzerothCore server installation. Supports both historical log access and
real-time streaming via async generators.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import AsyncIterator, Optional

import aiofiles

# Log file mapping: source name -> filename
LOG_FILES = {
    "worldserver": "Server.log",
    "authserver": "Auth.log",
    "gm": "GMCommands.log",      # only present if Logger.commands.gm is enabled in worldserver.conf
    "db_errors": "Errors.log",   # worldserver Errors appender (DBErrors.log is not the default name)
    "arena": "ArenaTeam.log",
    "char": "Char.log",
}

# Log level patterns for filtering
LOG_LEVEL_PATTERN = re.compile(
    r"\b(ERROR|WARN|WARNING|INFO|DEBUG|TRACE|FATAL)\b",
    re.IGNORECASE
)


async def _get_log_path(source: str) -> Optional[Path]:
    """
    Resolve the full path for a log source.
    Returns None if the source is unknown or the log directory is not configured.
    """
    from app.services.panel_settings import get_settings_dict
    
    if source not in LOG_FILES:
        return None
    
    settings = await get_settings_dict()
    log_dir = Path(settings["AC_LOG_PATH"])
    return log_dir / LOG_FILES[source]


async def list_available_sources() -> list[str]:
    """
    List log sources that currently have accessible log files.
    Returns a list of source names that exist on disk.
    """
    available = []
    
    for source in LOG_FILES:
        path = await _get_log_path(source)
        if path and path.exists():
            available.append(source)
    
    return available


async def read_tail(source: str, lines: int = 500) -> list[dict]:
    """
    Read the last N lines from a log file.
    
    Args:
        source: Log source name (worldserver, authserver, etc.)
        lines: Number of lines to read from the end of the file
    
    Returns:
        List of log entry dicts with 'message' and optional 'level' keys
    """
    path = await _get_log_path(source)
    if not path or not path.exists():
        return []
    
    entries = []
    
    try:
        async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
            # Read all lines (for simplicity; could be optimized for very large files)
            content = await f.read()
            all_lines = content.strip().split("\n")
            
            # Get last N lines
            tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
            for line in tail_lines:
                if not line.strip():
                    continue
                
                entry = {"message": line, "source": source}
                
                # Extract log level if present
                match = LOG_LEVEL_PATTERN.search(line)
                if match:
                    entry["level"] = match.group(1).upper()
                
                entries.append(entry)
    
    except Exception:
        # Return empty list on error (file may be locked, permissions, etc.)
        pass
    
    return entries


async def search_logs(
    source: str,
    search: str = "",
    level: Optional[str] = None,
    max_lines: int = 1000,
) -> list[dict]:
    """
    Search within a log file for matching entries.
    
    Args:
        source: Log source name
        search: Search pattern (regex supported)
        level: Filter by log level (ERROR, WARN, INFO, DEBUG, etc.)
        max_lines: Maximum number of lines to scan from the end
    
    Returns:
        List of matching log entry dicts
    """
    path = await _get_log_path(source)
    if not path or not path.exists():
        return []
    
    entries = []
    search_lower = search.lower() if search else None
    level_upper = level.upper() if level else None
    
    try:
        # Compile search pattern as regex if provided
        search_regex = None
        if search:
            try:
                search_regex = re.compile(search, re.IGNORECASE)
            except re.error:
                # If not a valid regex, fall back to substring search
                pass
        
        async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
            content = await f.read()
            all_lines = content.strip().split("\n")
            
            # Scan from the end, up to max_lines
            scan_lines = all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines
            
            for line in scan_lines:
                if not line.strip():
                    continue
                
                # Level filter
                if level_upper:
                    match = LOG_LEVEL_PATTERN.search(line)
                    if not match or match.group(1).upper() != level_upper:
                        continue
                
                # Search filter
                if search:
                    if search_regex:
                        if not search_regex.search(line):
                            continue
                    else:
                        if search_lower not in line.lower():
                            continue
                
                entry = {"message": line, "source": source}
                if level_upper:
                    entry["level"] = level_upper
                entries.append(entry)
    
    except Exception:
        pass
    
    return entries


async def get_log_file_size(source: str) -> int:
    """
    Get the size of a log file in bytes.
    
    Args:
        source: Log source name
    
    Returns:
        File size in bytes, or 0 if file doesn't exist
    """
    path = await _get_log_path(source)
    if not path or not path.exists():
        return 0
    
    try:
        return path.stat().st_size
    except Exception:
        return 0


async def tail_follow(source: str) -> AsyncIterator[str]:
    """
    Follow a log file in real-time, yielding new lines as they're appended.
    
    This is an async generator that yields raw log lines. It handles:
    - File not existing yet (waits for it to appear)
    - File rotation (reopens if file shrinks)
    - Backpressure (won't block if consumer is slow)
    
    Args:
        source: Log source name
    
    Yields:
        Raw log lines (without newline characters)
    """
    path = await _get_log_path(source)
    if not path:
        return
    
    last_size = 0
    last_pos = 0
    
    while True:
        try:
            # Check if file exists
            if not path.exists():
                await asyncio.sleep(1)
                continue
            
            current_size = path.stat().st_size
            
            # File was rotated or truncated - start from beginning
            if current_size < last_size:
                last_pos = 0
                last_size = current_size
            
            # If file has grown, read new content
            if current_size > last_pos:
                async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
                    await f.seek(last_pos)
                    new_content = await f.read()
                    last_pos = await f.tell()
                    last_size = current_size
                    
                    # Yield each new line
                    for line in new_content.split("\n"):
                        if line.strip():
                            yield line
            
            # Small delay before next check
            await asyncio.sleep(0.2)
        
        except asyncio.CancelledError:
            # Generator was cancelled - clean exit
            break
        except Exception:
            # On error, wait and retry
            await asyncio.sleep(1)
