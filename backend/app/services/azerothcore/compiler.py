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
        # CMAKE_INSTALL_PREFIX should be the build path, not the bin path
        # CMake will install binaries to {CMAKE_INSTALL_PREFIX}/bin
        install_prefix = str(build_path)

        _build_state.update(
            running=True, progress=0.0, step="cmake", start_time=time.time(), error=None
        )
        build_path.mkdir(parents=True, exist_ok=True)

        queue: asyncio.Queue[str | None] = asyncio.Queue()

        # ------------------------------------------------------------------
        # Phase 1: cmake configure
        # ------------------------------------------------------------------
        # Wipe stale CMake cache files before configuring.  A leftover
        # CMakeCache.txt from a previous build that had libmariadb.so will
        # cause the linker to look for that library even though the current
        # environment ships libmysqlclient.so (Oracle MySQL).
        for stale in ["CMakeCache.txt", "CMakeFiles"]:
            stale_path = build_path / stale
            if stale_path.exists():
                import shutil
                if stale_path.is_dir():
                    shutil.rmtree(stale_path)
                else:
                    stale_path.unlink()
                yield f"[cmake] Removed stale {stale}"

        # Detect the real libmysqlclient path so we can pin it explicitly.
        # This prevents cmake from accidentally resolving to libmariadb.so
        # when both MySQL and MariaDB connector packages are installed.
        import subprocess as _sp
        try:
            _mc_libs = _sp.check_output(
                ["mysql_config", "--libs"], text=True
            ).strip()
            # Extract -L path; fallback to the standard location.
            _lib_dir = "/usr/lib/x86_64-linux-gnu"
            for _token in _mc_libs.split():
                if _token.startswith("-L"):
                    _lib_dir = _token[2:]
                    break
            _mysql_lib = f"{_lib_dir}/libmysqlclient.so"
            _mysql_inc = _sp.check_output(
                ["mysql_config", "--include"], text=True
            ).strip().lstrip("-I").split()[0]
        except Exception:
            _mysql_lib = "/usr/lib/x86_64-linux-gnu/libmysqlclient.so"
            _mysql_inc = "/usr/include/mysql"

        extra = cmake_extra.strip()
        cmake_cmd = (
            f"cmake {ac_path} "
            f"-DCMAKE_INSTALL_PREFIX={install_prefix} "
            f"-DCMAKE_BUILD_TYPE={build_type} "
            f"-DTOOLS_BUILD=all "
            f"-DMYSQL_LIBRARY={_mysql_lib} "
            f"-DMYSQL_INCLUDE_DIR={_mysql_inc} "
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

        # ------------------------------------------------------------------
        # Phase 4: deploy module config files
        # ------------------------------------------------------------------
        # For every module that ships a conf/*.conf.dist, ensure the dest
        # modules/ directory has both the .conf.dist template and a live
        # .conf (copied from the template only when no .conf exists yet, so
        # existing edits are never overwritten).
        conf_dir = Path(s["AC_CONF_PATH"])
        modules_src = ac_path / "modules"
        dest_modules = conf_dir / "modules"
        dest_modules.mkdir(parents=True, exist_ok=True)

        deployed: list[str] = []
        skipped: list[str] = []

        import shutil as _shutil
        for dist_src in sorted(modules_src.glob("*/conf/*.conf.dist")):
            stem = dist_src.stem  # e.g. "playerbots.conf"  (removes .dist)
            dest_dist = dest_modules / dist_src.name   # keep the .conf.dist too
            dest_conf  = dest_modules / stem            # the live .conf

            # Always refresh the .conf.dist template
            _shutil.copy2(dist_src, dest_dist)

            if dest_conf.exists():
                skipped.append(stem)
            else:
                _shutil.copy2(dist_src, dest_conf)
                deployed.append(stem)

        if deployed:
            yield f"[config] Deployed new module configs: {', '.join(deployed)}"
        if skipped:
            yield f"[config] Kept existing module configs: {', '.join(skipped)}"
        if not deployed and not skipped:
            yield "[config] No module config files found to deploy."

        _build_state.update(running=False, progress=100.0, step="done", error=None)
        yield "[done] Build completed successfully!"

