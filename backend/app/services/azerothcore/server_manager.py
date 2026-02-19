"""
Server process manager – start/stop/restart worldserver and authserver.
Works with direct subprocess management and optionally systemd units.
"""
from __future__ import annotations

import asyncio
import os
import signal
import time
from pathlib import Path
from typing import Optional

import psutil

from app.models.schemas import ProcessStatus

# ---------------------------------------------------------------------------
# PID file paths (fallback when not using systemd)
# ---------------------------------------------------------------------------
_PID_DIR = Path("/tmp")
_WORLD_PID = _PID_DIR / "worldserver.pid"
_AUTH_PID = _PID_DIR / "authserver.pid"

# Running subprocess handles (in-process tracking)
_processes: dict[str, Optional[asyncio.subprocess.Process]] = {
    "worldserver": None,
    "authserver": None,
}
_start_times: dict[str, Optional[float]] = {
    "worldserver": None,
    "authserver": None,
}


def _find_pid(name: str) -> Optional[int]:
    """Find PID of a running process by name (cross-check with psutil)."""
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if proc.info["name"] == name or (
                proc.info["exe"] and proc.info["exe"].endswith(name)
            ):
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def get_process_status(name: str) -> ProcessStatus:
    pid = _find_pid(name)
    if pid is None:
        return ProcessStatus(name=name, running=False)
    try:
        proc = psutil.Process(pid)
        create_time = proc.create_time()
        uptime = time.time() - create_time
        cpu = proc.cpu_percent(interval=0.1)
        mem = proc.memory_info().rss / (1024 * 1024)  # MB
        return ProcessStatus(
            name=name,
            running=True,
            pid=pid,
            uptime_seconds=round(uptime, 1),
            cpu_percent=round(cpu, 2),
            memory_mb=round(mem, 2),
        )
    except psutil.NoSuchProcess:
        return ProcessStatus(name=name, running=False)


async def _launch(name: str) -> tuple[bool, str]:
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    binary_path = s["AC_BINARY_PATH"]
    binary = str(Path(binary_path) / name)

    if not Path(binary).exists():
        return False, f"Binary not found: {binary}"

    pid = _find_pid(name)
    if pid:
        return False, f"{name} is already running (PID {pid})"

    env = os.environ.copy()
    proc = await asyncio.create_subprocess_exec(
        binary,
        cwd=binary_path,
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,   # detach from panel's session
    )
    _processes[name] = proc
    _start_times[name] = time.time()
    await asyncio.sleep(1.5)  # give it a moment to start
    if _find_pid(name):
        return True, f"{name} started (PID {proc.pid})"
    return False, f"{name} failed to start or exited immediately"


async def _stop(name: str) -> tuple[bool, str]:
    pid = _find_pid(name)
    if pid is None:
        return False, f"{name} is not running"
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            await asyncio.sleep(0.5)
            if _find_pid(name) is None:
                return True, f"{name} stopped"
        os.kill(pid, signal.SIGKILL)
        return True, f"{name} force-killed"
    except ProcessLookupError:
        return True, f"{name} already stopped"
    except PermissionError:
        return False, f"Permission denied when stopping {name}"


async def start_worldserver() -> tuple[bool, str]:
    return await _launch("worldserver")


async def stop_worldserver() -> tuple[bool, str]:
    return await _stop("worldserver")


async def restart_worldserver() -> tuple[bool, str]:
    ok, msg = await _stop("worldserver")
    if not ok and "not running" not in msg:
        return False, msg
    await asyncio.sleep(1)
    return await _launch("worldserver")


async def start_authserver() -> tuple[bool, str]:
    return await _launch("authserver")


async def stop_authserver() -> tuple[bool, str]:
    return await _stop("authserver")


async def restart_authserver() -> tuple[bool, str]:
    ok, msg = await _stop("authserver")
    if not ok and "not running" not in msg:
        return False, msg
    await asyncio.sleep(1)
    return await _launch("authserver")

