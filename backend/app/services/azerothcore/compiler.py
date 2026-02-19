"""
AzerothCore build manager.

Streams cmake + make output via an asyncio.Queue so the WebSocket endpoint
can push each line to the browser in real time.
"""
from __future__ import annotations

import asyncio
import re
import shlex
import time
from pathlib import Path
from typing import AsyncIterator

_build_lock = asyncio.Lock()
_build_state: dict = {
    "running": False,
    "progress": 0.0,
    "step": "",
    "start_time": None,
    "error": None,
}

# Regex to parse make progress lines like "[  5%] Building CXX object ..."
_PROGRESS_RE = re.compile(r"\[\s*(\d+)%\]")


def get_build_status() -> dict:
    s = _build_state.copy()
    if s["start_time"]:
        s["elapsed_seconds"] = round(time.time() - s["start_time"], 1)
    else:
        s["elapsed_seconds"] = None
    s.pop("start_time", None)
    return s


async def _stream_command(
    cmd: str, cwd: str, queue: asyncio.Queue
) -> int:
    """Run a shell command and push each stdout/stderr line to queue.
    Uses stdbuf to force line-buffered output from the subprocess."""
    proc = await asyncio.create_subprocess_shell(
        f"stdbuf -oL -eL {cmd}",
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert proc.stdout
    buf = ""
    while True:
        chunk = await proc.stdout.read(512)
        if not chunk:
            break
        buf += chunk.decode("utf-8", errors="replace")
        lines = buf.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        buf = lines.pop()
        for line in lines:
            stripped = line.rstrip()
            if stripped:
                await queue.put(stripped)
        await asyncio.sleep(0)
    if buf.strip():
        await queue.put(buf.strip())
    rc = await proc.wait()
    return rc


async def run_build(
    build_type: str = "RelWithDebInfo",
    jobs: int = 4,
    cmake_extra: str = "",
) -> AsyncIterator[str]:
    """
    Generator that yields log lines while building AzerothCore.
    Must only be called once at a time (enforced by _build_lock).
    """
    if _build_lock.locked():
        yield "[error] A build is already in progress."
        return

    async with _build_lock:
        from app.services.panel_settings import get_settings_dict
        s = await get_settings_dict()
        ac_path = Path(s["AC_PATH"])
        build_path = Path(s["AC_BUILD_PATH"])
        binary_path = s["AC_BINARY_PATH"]

        _build_state.update(
            running=True, progress=0.0, step="cmake", start_time=time.time(), error=None
        )
        build_path.mkdir(parents=True, exist_ok=True)

        queue: asyncio.Queue[str | None] = asyncio.Queue()

        # ------------------------------------------------------------------
        # Phase 1: cmake configure
        # ------------------------------------------------------------------
        extra = cmake_extra.strip()
        cmake_cmd = (
            f"cmake {ac_path} "
            f"-DCMAKE_INSTALL_PREFIX={binary_path} "
            f"-DCMAKE_BUILD_TYPE={build_type} "
            f"-DTOOLS_BUILD=all "
            f"{extra}"
        )
        yield f"[cmake] {cmake_cmd}"
        _build_state["step"] = "Configuring with cmake..."

        task = asyncio.create_task(_stream_command(cmake_cmd, str(build_path), queue))
        while not task.done() or not queue.empty():
            try:
                line = await asyncio.wait_for(queue.get(), timeout=0.2)
                yield f"[cmake] {line}"
            except asyncio.TimeoutError:
                pass
        rc = task.result()
        if rc != 0:
            _build_state.update(running=False, error=f"cmake failed (exit {rc})")
            yield f"[error] cmake exited with code {rc}"
            return

        # ------------------------------------------------------------------
        # Phase 2: make / compile
        # ------------------------------------------------------------------
        make_cmd = f"make -j{jobs}"
        yield f"[make] {make_cmd}"
        _build_state["step"] = "Compiling..."

        task2 = asyncio.create_task(_stream_command(make_cmd, str(build_path), queue))
        while not task2.done() or not queue.empty():
            try:
                line = await asyncio.wait_for(queue.get(), timeout=0.2)
                m = _PROGRESS_RE.search(line)
                if m:
                    _build_state["progress"] = float(m.group(1))
                yield f"[make] {line}"
            except asyncio.TimeoutError:
                pass
        rc2 = task2.result()
        if rc2 != 0:
            _build_state.update(running=False, error=f"make failed (exit {rc2})")
            yield f"[error] make exited with code {rc2}"
            return

        # ------------------------------------------------------------------
        # Phase 3: make install
        # ------------------------------------------------------------------
        yield "[install] Installing binaries..."
        _build_state["step"] = "Installing..."
        task3 = asyncio.create_task(
            _stream_command("make install", str(build_path), queue)
        )
        while not task3.done() or not queue.empty():
            try:
                line = await asyncio.wait_for(queue.get(), timeout=0.2)
                yield f"[install] {line}"
            except asyncio.TimeoutError:
                pass

        _build_state.update(running=False, progress=100.0, step="done", error=None)
        yield "[done] Build completed successfully!"

