"""
Server process manager – start/stop/restart worldserver and authserver.
Works with direct subprocess management and optionally systemd units.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import tempfile
import time
from pathlib import Path
from typing import Optional

import psutil

from app.models.schemas import ProcessStatus

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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


async def _validate_startup(name: str, binary_path: str) -> tuple[bool, str]:
    """
    Validate that all prerequisites for starting the server are met.
    Returns (success, error_message).
    """
    binary = Path(binary_path) / name
    
    # Check binary exists
    if not binary.exists():
        return False, f"Binary not found: {binary}"
    
    # Check binary is executable
    if not os.access(binary, os.X_OK):
        return False, f"Binary is not executable: {binary}"
    
    # Check config file exists
    config_path = Path(binary_path).parent / "etc" / f"{name}.conf"
    if not config_path.exists():
        return False, f"Config file not found: {config_path}"
    
    # Check data directory exists
    data_path = Path(binary_path).parent / "data"
    if not data_path.exists():
        logger.warning(f"Data directory not found: {data_path} - server may fail to start")
    
    return True, ""


async def _launch(name: str) -> tuple[bool, str]:
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    binary_path = s["AC_BINARY_PATH"]
    binary = str(Path(binary_path) / name)

    logger.info(f"Attempting to start {name} from {binary_path}")

    # Validate prerequisites
    valid, error = await _validate_startup(name, binary_path)
    if not valid:
        logger.error(f"Validation failed for {name}: {error}")
        return False, error

    pid = _find_pid(name)
    if pid:
        logger.warning(f"{name} is already running (PID {pid})")
        return False, f"{name} is already running (PID {pid})"

    # Create a temporary file to capture stderr
    stderr_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.stderr', delete=False)
    stderr_path = stderr_file.name
    
    env = os.environ.copy()
    
    # Set working directory to the binary path
    # AzerothCore servers need to run from their bin directory
    cwd = binary_path
    
    logger.debug(f"Starting {name} with cwd={cwd}")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=stderr_file,
            start_new_session=True,   # detach from panel's session
        )
        _processes[name] = proc
        _start_times[name] = time.time()
        
        # Close the file handle but keep the file for reading later
        stderr_file.close()
        
        logger.info(f"Started {name} with PID {proc.pid}, waiting for startup...")
        
        # Wait longer for startup - AzerothCore can take several seconds
        await asyncio.sleep(3.0)
        
        # Check if process is still running
        if _find_pid(name):
            logger.info(f"{name} started successfully (PID {proc.pid})")
            # Clean up the stderr file on success
            try:
                os.unlink(stderr_path)
            except:
                pass
            return True, f"{name} started (PID {proc.pid})"
        
        # Process exited - read stderr for error message
        logger.error(f"{name} failed to start or exited immediately")
        
        error_msg = f"{name} failed to start or exited immediately"
        try:
            with open(stderr_path, 'r') as f:
                stderr_content = f.read().strip()
                if stderr_content:
                    # Get last few lines of error output
                    lines = stderr_content.split('\n')[-10:]
                    error_msg = f"{name} failed: " + '\n'.join(lines)
                    logger.error(f"{name} stderr: {stderr_content}")
        except Exception as e:
            logger.error(f"Could not read stderr file: {e}")
        finally:
            # Clean up stderr file
            try:
                os.unlink(stderr_path)
            except:
                pass
        
        return False, error_msg
        
    except Exception as e:
        logger.exception(f"Exception starting {name}: {e}")
        try:
            os.unlink(stderr_path)
        except:
            pass
        return False, f"Failed to start {name}: {str(e)}"


async def _stop(name: str) -> tuple[bool, str]:
    logger.info(f"Attempting to stop {name}")
    
    pid = _find_pid(name)
    if pid is None:
        logger.info(f"{name} is not running")
        return False, f"{name} is not running"
    try:
        logger.debug(f"Sending SIGTERM to {name} (PID {pid})")
        os.kill(pid, signal.SIGTERM)
        for i in range(30):
            await asyncio.sleep(0.5)
            if _find_pid(name) is None:
                logger.info(f"{name} stopped gracefully")
                return True, f"{name} stopped"
        logger.warning(f"{name} did not stop gracefully, sending SIGKILL")
        os.kill(pid, signal.SIGKILL)
        return True, f"{name} force-killed"
    except ProcessLookupError:
        logger.info(f"{name} already stopped")
        return True, f"{name} already stopped"
    except PermissionError as e:
        logger.error(f"Permission denied stopping {name}: {e}")
        return False, f"Permission denied when stopping {name}"
    except Exception as e:
        logger.exception(f"Exception stopping {name}: {e}")
        return False, f"Failed to stop {name}: {str(e)}"


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

