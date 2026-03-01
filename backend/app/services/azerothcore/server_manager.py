"""
Server process manager – start/stop/restart worldserver and authserver.

Architecture
------------
AzerothCore processes must live in the HOST's cgroup, not inside the Docker
container cgroup.  If they ran as subprocesses of the container they would be
killed whenever Docker restarts the panel – even with start_new_session=True.

The fix: a tiny Unix-socket daemon (`ac_host_daemon.py`) runs on the HOST and
truly owns the game-server processes.  This module communicates with that
daemon via JSON-over-Unix-socket.

Fallback
--------
If the daemon socket is not reachable (e.g. during local development outside
Docker) the old direct-subprocess code path is used automatically so the panel
still works without the daemon.
"""
from __future__ import annotations

import asyncio
import json
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
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------
# Daemon TCP address (set AC_DAEMON_HOST / AC_DAEMON_PORT env vars to override)
# ---------------------------------------------------------------------------
_DAEMON_HOST: str = os.environ.get("AC_DAEMON_HOST", "127.0.0.1")
_DAEMON_PORT: int = int(os.environ.get("AC_DAEMON_PORT", "7879"))

# ---------------------------------------------------------------------------
# Fallback: in-process tracking (used when daemon is not available)
# ---------------------------------------------------------------------------
_PID_DIR = Path("/tmp")

_processes: dict[str, Optional[asyncio.subprocess.Process]] = {
    "worldserver": None,
    "authserver": None,
}
_start_times: dict[str, Optional[float]] = {
    "worldserver": None,
    "authserver": None,
}
_stdin_writers: dict[str, Optional[asyncio.StreamWriter]] = {
    "worldserver": None,
    "authserver": None,
}


# ---------------------------------------------------------------------------
# Daemon client helpers
# ---------------------------------------------------------------------------

async def _daemon_send(request: dict, timeout: float = 35.0) -> Optional[dict]:
    """
    Send a single JSON request to the host daemon and return the parsed response.
    Returns None if the daemon is unreachable or an error occurs.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(_DAEMON_HOST, _DAEMON_PORT), timeout=5.0
        )
        try:
            line = json.dumps(request).encode() + b"\n"
            writer.write(line)
            await writer.drain()
            raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
            return json.loads(raw.decode())
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    except FileNotFoundError:
        return None
    except (ConnectionRefusedError, asyncio.TimeoutError, OSError) as exc:
        logger.debug(f"Daemon unavailable: {exc}")
        return None
    except Exception as exc:
        logger.warning(f"Daemon communication error: {exc}")
        return None


async def _daemon_available() -> bool:
    """Return True if the host daemon is reachable and healthy."""
    resp = await _daemon_send({"cmd": "ping"}, timeout=3.0)
    return resp is not None and resp.get("success") is True


# ---------------------------------------------------------------------------
# psutil helpers (fallback path)
# ---------------------------------------------------------------------------

def _find_pid(name: str) -> Optional[int]:
    """Find PID of a running process by name using psutil."""
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if proc.info["name"] == name or (
                proc.info["exe"] and proc.info["exe"].endswith(name)
            ):
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


# ---------------------------------------------------------------------------
# Public API: get_process_status
# ---------------------------------------------------------------------------

def get_process_status(name: str) -> ProcessStatus:
    """
    Return a ProcessStatus for `name`.
    Uses psutil for synchronous callers.  Async callers should prefer
    get_process_status_async() which can query the daemon for accurate state.
    """
    pid = _find_pid(name)
    if pid is None:
        return ProcessStatus(name=name, running=False)
    try:
        proc = psutil.Process(pid)
        create_time = proc.create_time()
        uptime = time.time() - create_time
        cpu = proc.cpu_percent(interval=0.1)
        mem = proc.memory_info().rss / (1024 * 1024)
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


async def get_process_status_async(name: str) -> ProcessStatus:
    """
    Async variant: prefers daemon query, falls back to psutil if daemon absent.
    """
    resp = await _daemon_send({"cmd": "status", "name": name}, timeout=5.0)
    if resp is not None and resp.get("success"):
        if resp.get("running"):
            return ProcessStatus(
                name=name,
                running=True,
                pid=resp.get("pid"),
                uptime_seconds=resp.get("uptime_seconds", 0.0),
                cpu_percent=resp.get("cpu_percent", 0.0),
                memory_mb=resp.get("memory_mb", 0.0),
            )
        return ProcessStatus(name=name, running=False)
    # Daemon not available – fall back to psutil
    return get_process_status(name)


# ---------------------------------------------------------------------------
# Validation (used by fallback path)
# ---------------------------------------------------------------------------

async def _validate_startup(name: str, binary_path: str) -> tuple[bool, str]:
    """Check that the binary and config file exist before trying to launch."""
    binary = Path(binary_path) / name
    if not binary.exists():
        return False, f"Binary not found: {binary}"
    if not os.access(binary, os.X_OK):
        return False, f"Binary is not executable: {binary}"

    config_path = Path(binary_path).parent / "etc" / f"{name}.conf"
    if not config_path.exists():
        return False, f"Config file not found: {config_path}"

    data_path = Path(binary_path).parent / "data"
    if not data_path.exists():
        logger.warning(f"Data directory not found: {data_path} – server may fail")

    return True, ""


# ---------------------------------------------------------------------------
# Launch / stop via daemon
# ---------------------------------------------------------------------------

async def _launch_via_daemon(name: str) -> tuple[bool, str]:
    """Ask the host daemon to start `name`."""
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    binary_path = s["AC_BINARY_PATH"]
    binary = str(Path(binary_path) / name)

    logger.info(f"[daemon] Starting {name} via host daemon")
    resp = await _daemon_send(
        {"cmd": "start", "name": name, "binary": binary, "cwd": binary_path},
        timeout=15.0,
    )
    if resp is None:
        return False, "Host daemon is not reachable"
    if resp.get("success"):
        logger.info(f"[daemon] {name} started (PID {resp.get('pid')})")
        return True, resp.get("message", f"{name} started")
    msg = resp.get("message", f"Daemon could not start {name}")
    logger.error(f"[daemon] {msg}")
    return False, msg


async def _stop_via_daemon(name: str) -> tuple[bool, str]:
    """Ask the host daemon to stop `name`."""
    logger.info(f"[daemon] Stopping {name} via host daemon")
    resp = await _daemon_send({"cmd": "stop", "name": name}, timeout=40.0)
    if resp is None:
        return False, "Host daemon is not reachable"
    success = resp.get("success", False)
    msg = resp.get("message", "")
    if success:
        logger.info(f"[daemon] {name} stopped")
    else:
        logger.error(f"[daemon] Could not stop {name}: {msg}")
    return success, msg


# ---------------------------------------------------------------------------
# Launch / stop direct (no daemon – fallback)
# ---------------------------------------------------------------------------

async def _launch_direct(name: str) -> tuple[bool, str]:
    """
    Fallback: spawn the server directly as a subprocess.
    WARNING: the process WILL be killed when the Docker container restarts.
    Use the host daemon (`make daemon-start`) for persistent server management.
    """
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    binary_path = s["AC_BINARY_PATH"]
    binary = str(Path(binary_path) / name)

    logger.warning(
        f"[direct] Host daemon not available – starting {name} directly. "
        "Process will NOT survive a container restart. "
        "Run `make daemon-start` on the host to enable persistent management."
    )

    valid, error = await _validate_startup(name, binary_path)
    if not valid:
        return False, error

    pid = _find_pid(name)
    if pid:
        return False, f"{name} is already running (PID {pid})"

    stderr_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".stderr", delete=False)
    stderr_path = stderr_file.name
    env = os.environ.copy()

    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            cwd=binary_path,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=stderr_file,
            start_new_session=True,
        )
        _processes[name] = proc
        _stdin_writers[name] = proc.stdin
        _start_times[name] = time.time()
        stderr_file.close()

        await asyncio.sleep(3.0)

        if _find_pid(name):
            try:
                os.unlink(stderr_path)
            except Exception:
                pass
            return True, f"{name} started (PID {proc.pid})"

        error_msg = f"{name} failed to start or exited immediately"
        try:
            with open(stderr_path) as fh:
                content = fh.read().strip()
                if content:
                    lines = content.split("\n")[-10:]
                    error_msg = f"{name} failed: " + "\n".join(lines)
                    logger.error(f"{name} stderr: {content}")
        except Exception as exc:
            logger.error(f"Could not read stderr file: {exc}")
        finally:
            try:
                os.unlink(stderr_path)
            except Exception:
                pass
        return False, error_msg

    except Exception as exc:
        logger.exception(f"Exception starting {name}: {exc}")
        try:
            os.unlink(stderr_path)
        except Exception:
            pass
        return False, f"Failed to start {name}: {str(exc)}"


async def _stop_direct(name: str) -> tuple[bool, str]:
    """Fallback stop via direct SIGTERM/SIGKILL."""
    logger.info(f"[direct] Stopping {name}")
    writer = _stdin_writers.get(name)
    if writer and not writer.is_closing():
        try:
            writer.close()
        except Exception:
            pass
    _stdin_writers[name] = None

    pid = _find_pid(name)
    if pid is None:
        return False, f"{name} is not running"
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            await asyncio.sleep(0.5)
            if _find_pid(name) is None:
                return True, f"{name} stopped"
        logger.warning(f"{name} did not stop gracefully – sending SIGKILL")
        os.kill(pid, signal.SIGKILL)
        return True, f"{name} force-killed"
    except ProcessLookupError:
        return True, f"{name} already stopped"
    except PermissionError:
        return False, f"Permission denied when stopping {name}"
    except Exception as exc:
        return False, f"Failed to stop {name}: {str(exc)}"


# ---------------------------------------------------------------------------
# Unified launch / stop (auto-selects daemon vs direct)
# ---------------------------------------------------------------------------

async def _launch(name: str) -> tuple[bool, str]:
    if await _daemon_available():
        return await _launch_via_daemon(name)
    return await _launch_direct(name)


async def _stop(name: str) -> tuple[bool, str]:
    if await _daemon_available():
        return await _stop_via_daemon(name)
    return await _stop_direct(name)


# ---------------------------------------------------------------------------
# Console commands
# ---------------------------------------------------------------------------

async def send_console_command(name: str, command: str) -> tuple[bool, str]:
    """
    Send a command to the server's stdin console.
    Routes through the host daemon when available; falls back to the in-process
    pipe for servers started without the daemon.
    """
    if await _daemon_available():
        resp = await _daemon_send(
            {"cmd": "console", "name": name, "command": command}, timeout=5.0
        )
        if resp is None:
            return False, "Host daemon is not reachable"
        return resp.get("success", False), resp.get("message", "")

    # Fallback: in-process pipe (only works if server was started this session)
    writer = _stdin_writers.get(name)
    if writer is None or writer.is_closing():
        return False, (
            f"{name} console is not available. "
            "Start the server from the panel so its stdin pipe is attached, "
            "or ensure the host daemon is running (`make daemon-start`)."
        )
    try:
        line = command.strip() + "\n"
        writer.write(line.encode())
        await writer.drain()
        logger.info(f"Console command sent to {name}: {command!r}")
        return True, f"Command sent to {name} console: {command}"
    except Exception as exc:
        logger.error(f"Failed to write to {name} stdin: {exc}")
        _stdin_writers[name] = None
        return False, f"Failed to send command: {exc}"


# ---------------------------------------------------------------------------
# Public start / stop / restart API
# ---------------------------------------------------------------------------

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
