#!/usr/bin/env python3
"""
AzerothPanel – Host-side process daemon
========================================
Run this script ON THE HOST MACHINE (outside Docker) so that worldserver /
authserver processes belong to the HOST cgroup rather than the panel container
cgroup.  When Docker restarts the panel containers the game servers keep running;
the daemon re-exposes them to the next container instance via a TCP socket on
localhost.

WHY TCP AND NOT A UNIX SOCKET
------------------------------
The backend container uses `network_mode: host`, meaning it shares the host's
network namespace.  127.0.0.1 inside the container resolves to the same loopback
as on the host — no bind-mount, no path-sharing needed.  Unix sockets under
/var/run are hidden by the container's own tmpfs overlay mount and cannot be
reached reliably, so TCP is the correct IPC mechanism here.

Usage
-----
    python3 ac_host_daemon.py [--host 127.0.0.1] [--port 7879]

Environment variables:
    AC_DAEMON_HOST   bind address  (default: 127.0.0.1)
    AC_DAEMON_PORT   listen port   (default: 7879)
    AC_DAEMON_PID_DIR  directory for the JSON state file
                       (default: /var/run/azerothpanel or /tmp/azerothpanel)

Protocol
--------
Each client connection sends exactly ONE newline-terminated JSON request and
receives exactly ONE newline-terminated JSON response.

Request shapes:
    {"cmd": "ping"}
    {"cmd": "start",   "name": "worldserver", "binary": "/opt/azerothcore/bin/worldserver", "cwd": "/opt/azerothcore/bin"}
    {"cmd": "stop",    "name": "worldserver",  "force": false}
    {"cmd": "status",  "name": "worldserver"}
    {"cmd": "list"}
    {"cmd": "console", "name": "worldserver",  "command": "server info"}
    {"cmd": "version", "project_dir": "/root/azerothpanel"}
    {"cmd": "update",  "project_dir": "/root/azerothpanel"}

All responses include at minimum: {"success": bool, "message": str}
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import psutil
import signal
import sys
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_HOST = os.environ.get("AC_DAEMON_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("AC_DAEMON_PORT", "7879"))

# State/PID file directory — try /var/run first, fall back to /tmp
_default_pid_dir = "/var/run/azerothpanel"
try:
    Path(_default_pid_dir).mkdir(parents=True, exist_ok=True)
except PermissionError:
    _default_pid_dir = "/tmp/azerothpanel"

DEFAULT_PID_DIR = os.environ.get("AC_DAEMON_PID_DIR", _default_pid_dir)

# Auto-detect the panel project root: ac_host_daemon.py lives in backend/,
# so the project root is one level up.
_DAEMON_SCRIPT_DIR = Path(__file__).resolve().parent   # .../azerothpanel/backend/
_PROJECT_DIR = _DAEMON_SCRIPT_DIR.parent               # .../azerothpanel/

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [daemon] %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ac_daemon")

# ---------------------------------------------------------------------------
# In-memory process registry
# ---------------------------------------------------------------------------
_registry: dict[str, dict] = {}
_state_path: Optional[Path] = None


# ---------------------------------------------------------------------------
# State file helpers
# ---------------------------------------------------------------------------

def _save_state() -> None:
    if _state_path is None:
        return
    snapshot = {}
    for name, info in _registry.items():
        if info.get("pid"):
            snapshot[name] = {
                "pid": info["pid"],
                "binary": info.get("binary", ""),
                "cwd": info.get("cwd", ""),
                "start_time": info.get("start_time", 0.0),
            }
    try:
        _state_path.write_text(json.dumps(snapshot, indent=2))
    except Exception as exc:
        logger.warning(f"Could not save state: {exc}")


def _load_state() -> None:
    if _state_path is None or not _state_path.exists():
        return
    try:
        snapshot = json.loads(_state_path.read_text())
    except Exception as exc:
        logger.warning(f"Could not read state file: {exc}")
        return

    for name, info in snapshot.items():
        pid = info.get("pid")
        if pid is None:
            continue
        if psutil.pid_exists(pid):
            try:
                proc_info = psutil.Process(pid)
                expected_name = Path(info.get("binary", "")).name
                if expected_name and proc_info.name() != expected_name and \
                        not (proc_info.exe() or "").endswith(expected_name):
                    logger.warning(f"PID {pid} name mismatch – skipping {name}")
                    continue
                logger.info(f"Re-attached to existing {name} process (PID {pid})")
                _registry[name] = {
                    "proc": None,
                    "stdin_writer": None,
                    "pid": pid,
                    "binary": info.get("binary", ""),
                    "cwd": info.get("cwd", ""),
                    "start_time": info.get("start_time", 0.0),
                }
            except psutil.NoSuchProcess:
                logger.info(f"{name} (PID {pid}) is no longer running")
        else:
            logger.info(f"{name} (PID {pid}) is no longer running")


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------

def _find_pid_by_name(name: str) -> Optional[int]:
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if proc.info["name"] == name or (
                proc.info["exe"] and proc.info["exe"].endswith(name)
            ):
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def _process_running(name: str) -> Optional[int]:
    info = _registry.get(name)
    if info:
        pid = info.get("pid")
        if pid and psutil.pid_exists(pid):
            return pid
        if pid:
            _registry.pop(name, None)
            _save_state()
    return _find_pid_by_name(name)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def _do_ping() -> dict:
    return {"success": True, "message": "pong"}


async def _do_start(name: str, binary: str, cwd: str) -> dict:
    if not binary:
        return {"success": False, "message": "binary path is required"}
    binary_path = Path(binary)
    if not binary_path.exists():
        return {"success": False, "message": f"Binary not found: {binary}"}
    if not os.access(binary, os.X_OK):
        return {"success": False, "message": f"Binary not executable: {binary}"}

    existing_pid = _process_running(name)
    if existing_pid:
        return {
            "success": False,
            "message": f"{name} is already running (PID {existing_pid})",
            "pid": existing_pid,
        }

    effective_cwd = cwd or str(binary_path.parent)
    env = os.environ.copy()

    logger.info(f"Starting {name}: binary={binary!r}  cwd={effective_cwd!r}")
    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            cwd=effective_cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as exc:
        logger.error(f"Failed to start {name}: {exc}")
        return {"success": False, "message": f"Failed to start {name}: {exc}"}

    pid = proc.pid
    start_time = time.time()
    _registry[name] = {
        "proc": proc,
        "stdin_writer": proc.stdin,
        "pid": pid,
        "binary": binary,
        "cwd": effective_cwd,
        "start_time": start_time,
    }
    _save_state()

    await asyncio.sleep(2.5)

    if not psutil.pid_exists(pid):
        _registry.pop(name, None)
        _save_state()
        logger.error(f"{name} (PID {pid}) exited immediately")
        return {"success": False, "message": f"{name} exited immediately after start"}

    logger.info(f"{name} started successfully (PID {pid})")
    return {"success": True, "message": f"{name} started (PID {pid})", "pid": pid}


async def _do_stop(name: str, force: bool = False) -> dict:
    info = _registry.get(name)
    pid = _process_running(name)

    if pid is None:
        return {"success": False, "message": f"{name} is not running"}

    writer: Optional[asyncio.StreamWriter] = (info or {}).get("stdin_writer")
    if writer and not writer.is_closing():
        try:
            writer.close()
        except Exception:
            pass

    sig = signal.SIGKILL if force else signal.SIGTERM
    logger.info(f"Sending {'SIGKILL' if force else 'SIGTERM'} to {name} (PID {pid})")
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        _registry.pop(name, None)
        _save_state()
        return {"success": True, "message": f"{name} already stopped"}
    except PermissionError as exc:
        return {"success": False, "message": f"Permission denied stopping {name}: {exc}"}

    for _ in range(60):
        await asyncio.sleep(0.5)
        if not psutil.pid_exists(pid):
            break
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    _registry.pop(name, None)
    _save_state()
    logger.info(f"{name} stopped")
    return {"success": True, "message": f"{name} stopped"}


def _do_status(name: str) -> dict:
    pid = _process_running(name)
    if pid is None:
        return {"success": True, "running": False, "name": name}
    try:
        proc = psutil.Process(pid)
        uptime = time.time() - proc.create_time()
        cpu = proc.cpu_percent(interval=0.1)
        mem = proc.memory_info().rss / (1024 * 1024)
        return {
            "success": True,
            "running": True,
            "name": name,
            "pid": pid,
            "uptime_seconds": round(uptime, 1),
            "cpu_percent": round(cpu, 2),
            "memory_mb": round(mem, 2),
        }
    except psutil.NoSuchProcess:
        _registry.pop(name, None)
        _save_state()
        return {"success": True, "running": False, "name": name}


def _do_list() -> dict:
    names = {*_registry.keys(), "worldserver", "authserver"}
    services = [_do_status(n) for n in sorted(names)]
    return {"success": True, "services": services}


async def _run_cmd(args: list[str], cwd: str) -> tuple[int, str]:
    """Run a shell command, return (returncode, combined stdout+stderr output)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
    return proc.returncode, stdout.decode(errors="replace")


async def _do_version(project_dir: str = "") -> dict:
    """Return the current git commit hash, branch, and latest tag for the panel repo."""
    if not project_dir:
        project_dir = str(_PROJECT_DIR)
    if not Path(project_dir).is_dir():
        return {"success": False, "message": f"project_dir not found: {project_dir!r}"}

    results: dict = {"success": True}

    rc, out = await _run_cmd(["git", "rev-parse", "--short", "HEAD"], project_dir)
    results["commit"] = out.strip() if rc == 0 else "unknown"

    rc, out = await _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], project_dir)
    results["branch"] = out.strip() if rc == 0 else "unknown"

    rc, out = await _run_cmd(["git", "describe", "--tags", "--always"], project_dir)
    results["version"] = out.strip() if rc == 0 else results["commit"]

    # Check how many commits behind origin we are (best-effort, no network call)
    await _run_cmd(["git", "fetch", "--quiet", "--tags"], project_dir)
    rc, out = await _run_cmd(
        ["git", "rev-list", "--count", "HEAD..origin/HEAD"], project_dir
    )
    try:
        results["commits_behind"] = int(out.strip()) if rc == 0 else None
    except ValueError:
        results["commits_behind"] = None

    results["message"] = (
        f"Version {results['version']} on branch {results['branch']} "
        f"({results['commits_behind'] or 0} commit(s) behind origin)"
    )
    return results


async def _do_update(project_dir: str = "") -> dict:
    """
    Pull the latest code from origin and rebuild/restart the Docker containers.
    This runs entirely on the HOST so that git pull affects the real source tree.
    """
    if not project_dir:
        project_dir = str(_PROJECT_DIR)
    if not Path(project_dir).is_dir():
        return {"success": False, "message": f"project_dir not found: {project_dir!r}"}

    output_lines: list[str] = []

    # 1. git pull
    logger.info(f"[update] git pull in {project_dir!r}")
    rc, out = await _run_cmd(["git", "pull", "--rebase"], project_dir)
    output_lines.append("=== git pull ===")
    output_lines.append(out.strip())
    if rc != 0:
        return {
            "success": False,
            "message": "git pull failed",
            "output": "\n".join(output_lines),
        }

    # 2. docker compose up --build -d
    logger.info(f"[update] docker compose up --build -d in {project_dir!r}")
    rc, out = await _run_cmd(
        ["docker", "compose", "up", "--build", "-d"], project_dir
    )
    output_lines.append("\n=== docker compose up --build -d ===")
    output_lines.append(out.strip())
    if rc != 0:
        return {
            "success": False,
            "message": "docker compose rebuild failed",
            "output": "\n".join(output_lines),
        }

    logger.info("[update] Panel updated and containers restarted successfully")
    return {
        "success": True,
        "message": "Panel updated and containers restarted successfully",
        "output": "\n".join(output_lines),
    }


async def _do_console(name: str, command: str) -> dict:
    info = _registry.get(name)
    if info is None:
        return {
            "success": False,
            "message": (
                f"{name} was not started by this daemon session. "
                "Console stdin is unavailable until the server is restarted from the panel."
            ),
        }
    writer: Optional[asyncio.StreamWriter] = info.get("stdin_writer")
    if writer is None or writer.is_closing():
        return {
            "success": False,
            "message": f"{name} stdin pipe is closed. Restart the server to restore console access.",
        }
    try:
        line = command.strip() + "\n"
        writer.write(line.encode())
        await writer.drain()
        return {"success": True, "message": f"Command sent to {name}: {command!r}"}
    except Exception as exc:
        info["stdin_writer"] = None
        return {"success": False, "message": f"Failed to send command: {exc}"}


# ---------------------------------------------------------------------------
# Client handler
# ---------------------------------------------------------------------------

async def _handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    peer = writer.get_extra_info("peername", "<unknown>")
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=10.0)
        if not raw:
            return
        try:
            request = json.loads(raw.decode())
        except json.JSONDecodeError:
            writer.write(json.dumps({"success": False, "message": "Invalid JSON"}).encode() + b"\n")
            await writer.drain()
            return

        cmd = request.get("cmd", "")
        name = request.get("name", "")
        logger.debug(f"[{peer}] cmd={cmd!r} name={name!r}")

        if cmd == "ping":
            response = await _do_ping()
        elif cmd == "start":
            response = await _do_start(name, request.get("binary", ""), request.get("cwd", ""))
        elif cmd == "stop":
            response = await _do_stop(name, bool(request.get("force", False)))
        elif cmd == "status":
            response = _do_status(name)
        elif cmd == "list":
            response = _do_list()
        elif cmd == "console":
            response = await _do_console(name, request.get("command", ""))
        elif cmd == "version":
            response = await _do_version(request.get("project_dir", ""))
        elif cmd == "update":
            response = await _do_update(request.get("project_dir", ""))
        else:
            response = {"success": False, "message": f"Unknown command: {cmd!r}"}

        writer.write(json.dumps(response).encode() + b"\n")
        await writer.drain()

    except asyncio.TimeoutError:
        logger.warning(f"[{peer}] Request timed out")
    except Exception as exc:
        logger.error(f"[{peer}] Unhandled error: {exc}", exc_info=True)
        try:
            err = {"success": False, "message": f"Internal daemon error: {exc}"}
            writer.write(json.dumps(err).encode() + b"\n")
            await writer.drain()
        except Exception:
            pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _main(host: str, port: int, pid_dir: str) -> None:
    global _state_path
    pid_dir_path = Path(pid_dir)
    pid_dir_path.mkdir(parents=True, exist_ok=True)
    _state_path = pid_dir_path / "ac-daemon-state.json"

    _load_state()

    server = await asyncio.start_server(_handle_client, host, port)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    logger.info(f"AC Host Daemon listening on {addrs} (TCP)")
    logger.info(f"State file: {_state_path}")

    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AzerothPanel host daemon – manages worldserver/authserver outside Docker"
    )
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"Bind address (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Listen port (default: {DEFAULT_PORT})")
    parser.add_argument("--pid-dir", default=DEFAULT_PID_DIR,
                        help=f"Directory for state/PID files (default: {DEFAULT_PID_DIR})")
    parser.add_argument("--debug", action="store_true",
                        help="Enable verbose debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        asyncio.run(_main(args.host, args.port, args.pid_dir))
    except KeyboardInterrupt:
        logger.info("Daemon stopped (KeyboardInterrupt)")


if __name__ == "__main__":
    main()
