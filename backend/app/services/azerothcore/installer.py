"""
AzerothCore automated installer.

Runs installation steps sequentially and yields progress lines.
Follows the official Debian 12/13 guide:
  https://www.azerothcore.org/wiki/linux-requirements
  https://www.azerothcore.org/wiki/linux-core-installation
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import AsyncIterator

# ── Package lists ──────────────────────────────────────────────────────────────

# Needed before adding the MySQL APT repo
_APT_BOOTSTRAP = "wget gnupg ca-certificates lsb-release"

# Build tools (no MySQL — installed separately from the MySQL APT repo)
_APT_BUILD_DEPS = (
    "git cmake make gcc g++ clang "
    "libssl-dev libbz2-dev libreadline-dev libncurses-dev libboost-all-dev"
)

# From the MySQL 8 APT repo
_APT_MYSQL_DEPS = "mysql-client libmysqlclient-dev"

# MySQL APT config package (https://dev.mysql.com/downloads/repo/apt/)
_MYSQL_APT_CONFIG_VERSION = "0.8.36-1"
_MYSQL_APT_CONFIG_DEB = f"mysql-apt-config_{_MYSQL_APT_CONFIG_VERSION}_all.deb"
_MYSQL_APT_CONFIG_URL = f"https://dev.mysql.com/get/{_MYSQL_APT_CONFIG_DEB}"


# ── Low-level subprocess helper ────────────────────────────────────────────────

async def _run(
    cmd: str,
    cwd: str | None = None,
    extra_env: dict | None = None,
    rc_out: list[int] | None = None,
) -> AsyncIterator[str]:
    """
    Stream a shell command's combined stdout+stderr line-by-line.

    - stdbuf -oL -eL  forces line-buffered output from the subprocess so long-
      running tools (apt, git, cmake, make) surface each line immediately.
    - extra_env is merged into os.environ — use this instead of prepending shell
      variable assignments so stdbuf still sees the real binary as argv[0].
    - rc_out receives [returncode] after the process finishes.
    """
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    proc = await asyncio.create_subprocess_shell(
        f"stdbuf -oL -eL {cmd}",
        cwd=cwd,
        env=env,
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
        # Handle \r\n, bare \r (git/apt progress), and \n
        lines = buf.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        buf = lines.pop()
        for line in lines:
            s = line.rstrip()
            if s:
                yield s
        await asyncio.sleep(0)   # yield event-loop so uvicorn flushes SSE

    if buf.strip():
        yield buf.strip()

    await proc.wait()
    if rc_out is not None:
        rc_out.append(proc.returncode)
    if proc.returncode != 0:
        yield f"[exit {proc.returncode}]"


# ── Main installer ─────────────────────────────────────────────────────────────

async def run_installation(config: dict) -> AsyncIterator[str]:
    """
    Yield log lines for each installation operation.
    Aborts immediately when a critical step exits non-zero.

    config keys (all optional):
        ac_path         – clone & install root  (default /opt/azerothcore)
        clone_branch    – git branch            (default master)
        repository_url  – git remote URL
        db_host         – MySQL host            (default 127.0.0.1)
        db_user         – MySQL app user        (default acore)
        db_password     – MySQL root password   (default acore)
    """
    from app.models.schemas import REPO_STANDARD, REPO_PLAYERBOT

    ac_path     = Path(config.get("ac_path",      "/opt/azerothcore"))
    build_dir   = ac_path / "build"
    install_dir = ac_path / "build"   # cmake prefix → binaries at install_dir/bin
    repo_url    = config.get("repository_url", REPO_STANDARD)
    # Playerbot fork must be cloned from its dedicated branch
    default_branch = "Playerbot" if repo_url == REPO_PLAYERBOT else "master"
    branch      = config.get("clone_branch",   default_branch)
    db_host      = config.get("db_host",         "127.0.0.1")
    db_root_pass = config.get("db_root_password", "")
    db_user      = config.get("db_user",          "acore")
    db_pass      = config.get("db_password",      "acore")

    # Build the mysql root auth flags once — no -p flag at all when root has no password
    root_auth = f"-h {db_host} -u root" + (f" -p'{db_root_pass}'" if db_root_pass else "")

    NI = {"DEBIAN_FRONTEND": "noninteractive"}

    # ── Step 1: System dependencies ──────────────────────────────────────────
    yield "[step:dependencies] Installing system dependencies..."

    # 1a – refresh the base package index first so any apt-get install can succeed
    yield "[dependencies] Updating package index..."
    rc: list[int] = []
    async for line in _run("apt-get update", rc_out=rc):
        yield f"[dependencies] {line}"
    if rc and rc[0] != 0:
        yield "[error] apt-get update failed — aborting."; return

    # 1b – bootstrap tools needed to fetch the MySQL APT config package
    yield "[dependencies] Installing bootstrap tools (wget, gnupg)..."
    rc = []
    async for line in _run(f"apt-get install -y {_APT_BOOTSTRAP}", extra_env=NI, rc_out=rc):
        yield f"[dependencies] {line}"
    if rc and rc[0] != 0:
        yield "[error] Bootstrap install failed — aborting."; return

    # 1c – register the MySQL 8 official APT repository for Debian
    yield "[dependencies] Adding MySQL 8 APT repository..."
    rc = []
    mysql_repo_cmd = (
        f"bash -c '"
        f"cd /tmp && "
        f"wget -q -O {_MYSQL_APT_CONFIG_DEB} {_MYSQL_APT_CONFIG_URL} && "
        f"DEBIAN_FRONTEND=noninteractive dpkg -i {_MYSQL_APT_CONFIG_DEB} && "
        f"rm -f {_MYSQL_APT_CONFIG_DEB}"
        f"'"
    )
    async for line in _run(mysql_repo_cmd, rc_out=rc):
        yield f"[dependencies] {line}"
    if rc and rc[0] != 0:
        yield "[error] Failed to add MySQL 8 APT repository — aborting."; return

    # 1d – refresh index again (now includes MySQL 8)
    yield "[dependencies] Updating package index (with MySQL 8 repo)..."
    rc = []
    async for line in _run("apt-get update", rc_out=rc):
        yield f"[dependencies] {line}"
    if rc and rc[0] != 0:
        yield "[error] apt-get update (post-MySQL repo) failed — aborting."; return

    # 1e – MySQL packages
    yield "[dependencies] Installing MySQL packages..."
    rc = []
    async for line in _run(f"apt-get install -y {_APT_MYSQL_DEPS}", extra_env=NI, rc_out=rc):
        yield f"[dependencies] {line}"
    if rc and rc[0] != 0:
        yield "[error] MySQL package install failed — aborting."; return

    # 1f – compiler, cmake, and remaining build tools
    yield "[dependencies] Installing build tools..."
    rc = []
    async for line in _run(f"apt-get install -y {_APT_BUILD_DEPS}", extra_env=NI, rc_out=rc):
        yield f"[dependencies] {line}"
    if rc and rc[0] != 0:
        yield "[error] Build tool install failed — aborting."; return

    yield "[dependencies] All dependencies installed."

    # ── Step 2: Clone / pull repository ──────────────────────────────────────
    if (ac_path / ".git").exists():
        # Valid git repo already present — just update it
        yield f"[step:clone] Repository already present at {ac_path} — pulling latest..."
        rc = []
        async for line in _run("git pull --progress", cwd=str(ac_path), rc_out=rc):
            yield f"[clone] {line}"
        if rc and rc[0] != 0:
            yield "[error] git pull failed — aborting."; return
    else:
        # Directory may exist but is not a git repo — clear its contents so git
        # can clone into it.  We empty it rather than removing it because the
        # path may be a Docker volume mountpoint which cannot be deleted.
        if ac_path.exists():
            yield f"[step:clone] {ac_path} exists but is not a git repo — clearing contents..."
            rc = []
            async for line in _run(f"bash -c 'find {ac_path} -mindepth 1 -delete'", rc_out=rc):
                yield f"[clone] {line}"
            if rc and rc[0] != 0:
                yield "[error] Failed to clear directory contents — aborting."; return

        yield f"[step:clone] Cloning {repo_url} → {ac_path}..."
        ac_path.parent.mkdir(parents=True, exist_ok=True)
        rc = []
        async for line in _run(
            f"git clone --branch {branch} --depth=1 --progress {repo_url} {ac_path}",
            cwd=str(ac_path.parent), rc_out=rc,
        ):
            yield f"[clone] {line}"
        if rc and rc[0] != 0:
            yield "[error] git clone failed — aborting."; return

    # ── Step 2b: Clone mod-playerbots module (playerbot fork only) ─────────────
    if repo_url == REPO_PLAYERBOT:
        modules_dir = ac_path / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)
        playerbot_mod_dir = modules_dir / "mod-playerbots"
        playerbot_mod_url = "https://github.com/mod-playerbots/mod-playerbots.git"

        if (playerbot_mod_dir / ".git").exists():
            yield f"[step:module] mod-playerbots module already present — pulling latest..."
            rc = []
            async for line in _run("git pull --progress", cwd=str(playerbot_mod_dir), rc_out=rc):
                yield f"[module] {line}"
            if rc and rc[0] != 0:
                yield "[error] git pull (mod-playerbots) failed — aborting."; return
        else:
            yield f"[step:module] Cloning mod-playerbots module into {playerbot_mod_dir}..."
            rc = []
            async for line in _run(
                f"git clone --branch master --depth=1 --progress {playerbot_mod_url} {playerbot_mod_dir}",
                cwd=str(modules_dir), rc_out=rc,
            ):
                yield f"[module] {line}"
            if rc and rc[0] != 0:
                yield "[error] git clone (mod-playerbots) failed — aborting."; return
        yield "[module] mod-playerbots module ready."

    # ── Step 3: cmake configure ───────────────────────────────────────────────
    build_dir.mkdir(parents=True, exist_ok=True)
    yield "[step:cmake] Configuring with cmake..."
    cmake_cmd = (
        f"cmake {ac_path}"
        f" -DCMAKE_INSTALL_PREFIX={install_dir}"
        f" -DCMAKE_C_COMPILER=/usr/bin/clang"
        f" -DCMAKE_CXX_COMPILER=/usr/bin/clang++"
        f" -DCMAKE_BUILD_TYPE=RelWithDebInfo"
        f" -DWITH_WARNINGS=1"
        f" -DTOOLS_BUILD=all"
        f" -DSCRIPTS=static"
        f" -DMODULES=static"
    )
    rc = []
    async for line in _run(cmake_cmd, cwd=str(build_dir), rc_out=rc):
        yield f"[cmake] {line}"
    if rc and rc[0] != 0:
        yield "[error] cmake configuration failed — aborting."; return

    # ── Step 4: Compile ───────────────────────────────────────────────────────
    yield "[step:compile] Compiling (this may take 30–90 minutes)..."
    rc = []
    # Use nproc-1 cores per the official guide
    async for line in _run(
        "bash -c 'make -j$(( $(nproc) > 1 ? $(nproc) - 1 : 1 ))'",
        cwd=str(build_dir), rc_out=rc,
    ):
        yield f"[compile] {line}"
    if rc and rc[0] != 0:
        yield "[error] Compilation failed — aborting."; return

    # ── Step 5: Install binaries ──────────────────────────────────────────────
    yield "[step:install] Running make install..."
    rc = []
    async for line in _run("make install", cwd=str(build_dir), rc_out=rc):
        yield f"[install] {line}"
    if rc and rc[0] != 0:
        yield "[error] make install failed — aborting."; return

    # ── Step 6: Create databases ──────────────────────────────────────────────
    yield "[step:db_create] Creating AzerothCore databases..."
    # Always use inline SQL so the configured db_user/db_password are applied
    # correctly regardless of what is in the repo's create_mysql.sql.
    rc = []
    yield "[db_create] Creating databases and user via SQL..."
    inline = (
        f"CREATE DATABASE IF NOT EXISTS acore_auth CHARACTER SET utf8mb4; "
        f"CREATE DATABASE IF NOT EXISTS acore_characters CHARACTER SET utf8mb4; "
        f"CREATE DATABASE IF NOT EXISTS acore_world CHARACTER SET utf8mb4; "
        f"CREATE USER IF NOT EXISTS '{db_user}'@'%' IDENTIFIED BY '{db_pass}'; "
        f"GRANT ALL ON acore_auth.* TO '{db_user}'@'%'; "
        f"GRANT ALL ON acore_characters.* TO '{db_user}'@'%'; "
        f"GRANT ALL ON acore_world.* TO '{db_user}'@'%'; "
        f"FLUSH PRIVILEGES;"
    )
    async for line in _run(
        f"mysql {root_auth} -e \"{inline}\"",
        rc_out=rc,
    ):
        yield f"[db_create] {line}"
    if rc and rc[0] != 0:
        yield "[error] Database creation failed — aborting."; return

    # ── Step 7: Import SQL data ───────────────────────────────────────────────
    # authserver/worldserver auto-apply SQL on first start; db_assembler does a
    # full offline import if it exists.
    yield "[step:db_import] Importing database data..."
    assembler = ac_path / "apps" / "db_assembler" / "db_assembler.sh"
    if assembler.exists():
        yield f"[db_import] Running db_assembler.sh import-all..."
        rc = []
        async for line in _run(f"bash {assembler} import-all", cwd=str(ac_path), rc_out=rc):
            yield f"[db_import] {line}"
        if rc and rc[0] != 0:
            yield "[db_import] Warning: db_assembler returned non-zero — check logs."
    else:
        yield (
            "[db_import] db_assembler.sh not found. "
            "Servers will auto-populate databases on first start."
        )

    # ── Step 8: Generate config files ────────────────────────────────────────
    yield "[step:conf_generate] Generating configuration files..."
    etc_path = install_dir / "etc"
    etc_path.mkdir(parents=True, exist_ok=True)
    for dist_file in sorted(etc_path.glob("*.conf.dist")):
        target = dist_file.with_suffix("")
        if not target.exists():
            target.write_bytes(dist_file.read_bytes())
            yield f"[conf_generate] Created {target.name}"
        else:
            yield f"[conf_generate] {target.name} already exists — skipping."

    yield "[done] AzerothCore installation complete!"
