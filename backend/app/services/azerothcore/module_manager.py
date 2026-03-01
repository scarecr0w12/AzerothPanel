"""
AzerothCore Module Manager

Handles fetching the online catalogue from the AzerothCore GitHub organisation
(via the GitHub Search API) and cloning / removing modules from the modules
directory inside the AzerothCore source tree.
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import AsyncIterator

import httpx

# ── GitHub topic constants ─────────────────────────────────────────────────────

CATALOGUE_CATEGORIES: dict[str, list[str]] = {
    "modules":  ["azerothcore-module"],
    "premium":  ["azerothcore-module+ac-premium"],
    "tools":    ["azerothcore-tools"],
    "lua":      ["azerothcore-lua"],
    "sql":      ["azerothcore-sql"],
}

GH_SEARCH_URL  = "https://api.github.com/search/repositories"
GH_RATE_URL    = "https://api.github.com/rate_limit"
GH_BASE_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "AzerothPanel/1.0",
}


def _gh_headers(github_token: str | None = None) -> dict:
    """Build GitHub request headers, optionally injecting a personal access token."""
    h = dict(GH_BASE_HEADERS)
    if github_token:
        h["Authorization"] = f"Bearer {github_token}"
    return h


# ── Low-level subprocess helper (mirrors installer.py) ─────────────────────────

async def _run(
    cmd: str,
    cwd: str | None = None,
    rc_out: list[int] | None = None,
) -> AsyncIterator[str]:
    """Stream a shell command's combined stdout+stderr line-by-line."""
    env = os.environ.copy()
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
        lines = buf.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        buf = lines.pop()
        for line in lines:
            s = line.rstrip()
            if s:
                yield s
        await asyncio.sleep(0)

    if buf.strip():
        yield buf.strip()

    await proc.wait()
    if rc_out is not None:
        rc_out.append(proc.returncode)
    if proc.returncode != 0:
        yield f"[exit {proc.returncode}]"


# ── Catalogue fetching ─────────────────────────────────────────────────────────

async def fetch_rate_limit(github_token: str | None = None) -> dict:
    """
    Return the current GitHub rate-limit status for the search endpoint.
    { "limit": int, "remaining": int, "reset_epoch": int, "authenticated": bool }
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GH_RATE_URL, headers=_gh_headers(github_token))
        resp.raise_for_status()
        data = resp.json()
    search = data.get("resources", {}).get("search", {})
    return {
        "limit":        search.get("limit", 0),
        "remaining":    search.get("remaining", 0),
        "reset_epoch":  search.get("reset", 0),
        "authenticated": bool(github_token),
    }


async def fetch_catalogue(
    category: str = "modules",
    page: int = 1,
    per_page: int = 30,
    github_token: str | None = None,
) -> dict:
    """
    Query the GitHub Search API for repositories tagged with the AzerothCore
    catalogue topic(s) for the requested category.

    Returns the raw GitHub search result dict:
      { "total_count": int, "items": [ { repo fields ... }, ... ] }
    """
    topics = CATALOGUE_CATEGORIES.get(category, CATALOGUE_CATEGORIES["modules"])
    # GitHub search: space-separated topic: qualifiers (parentheses break the API)
    query = " ".join(f"topic:{t}" for t in topics)

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": page,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(GH_SEARCH_URL, params=params, headers=_gh_headers(github_token))
        if resp.status_code == 403:
            remaining = resp.headers.get("x-ratelimit-remaining", "0")
            if remaining == "0":
                raise RuntimeError(
                    "GitHub API rate limit exceeded. "
                    "Add a GitHub Personal Access Token in Settings to increase the limit."
                )
        resp.raise_for_status()
        data = resp.json()

    # Reshape items to a leaner format
    items = [
        {
            "id": r["id"],
            "name": r["name"],
            "full_name": r["full_name"],
            "description": r.get("description") or "",
            "html_url": r["html_url"],
            "clone_url": r["clone_url"],
            "ssh_url": r.get("ssh_url", ""),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "open_issues": r.get("open_issues_count", 0),
            "default_branch": r.get("default_branch", "master"),
            "updated_at": r.get("updated_at", ""),
            "pushed_at": r.get("pushed_at", ""),
            "archived": r.get("archived", False),
            "topics": r.get("topics", []),
            "owner_avatar": r["owner"]["avatar_url"],
            "owner_login": r["owner"]["login"],
        }
        for r in data.get("items", [])
    ]

    return {
        "total_count": data.get("total_count", 0),
        "page": page,
        "per_page": per_page,
        "items": items,
    }


# ── Installed module discovery ─────────────────────────────────────────────────

def list_installed_modules(modules_path: str) -> list[dict]:
    """
    Return a list of { name, path, has_git, remote_url } for every
    sub-directory inside *modules_path*.
    """
    base = Path(modules_path)
    if not base.exists():
        return []

    result = []
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        has_git = (entry / ".git").exists()
        remote_url: str | None = None
        if has_git:
            try:
                cfg = (entry / ".git" / "config").read_text(errors="replace")
                for line in cfg.splitlines():
                    line = line.strip()
                    if line.startswith("url = "):
                        remote_url = line[len("url = "):]
                        break
            except Exception:
                pass
        result.append({
            "name": entry.name,
            "path": str(entry),
            "has_git": has_git,
            "remote_url": remote_url,
        })
    return result


# ── Module installation ────────────────────────────────────────────────────────

async def install_module(
    clone_url: str,
    module_name: str,
    modules_path: str,
    branch: str | None = None,
) -> AsyncIterator[str]:
    """
    Clone *clone_url* into <modules_path>/<module_name>.

    Streams git output line-by-line as an async generator.
    The module_name has any trailing '-master'/'-main' suffix stripped per the
    official AzerothCore documentation.
    """
    # Sanitise name: strip common branch suffixes that would break CMake
    clean_name = module_name
    for suffix in ("-master", "-main", "-develop", "-dev"):
        if clean_name.lower().endswith(suffix):
            clean_name = clean_name[: -len(suffix)]
            break

    base = Path(modules_path)
    dest = base / clean_name

    if dest.exists():
        yield f"[error] Module directory already exists: {dest}"
        return

    base.mkdir(parents=True, exist_ok=True)

    branch_flag = f"--branch {branch}" if branch else ""
    cmd = f"git clone --recursive {branch_flag} {clone_url} {clean_name}"
    yield f"[info] Cloning into {dest} …"
    yield f"[cmd] {cmd}"

    rc: list[int] = []
    async for line in _run(cmd, cwd=str(base), rc_out=rc):
        yield line

    if rc and rc[0] == 0:
        yield f"[ok] Module '{clean_name}' installed successfully."
        yield "[done]"
    else:
        yield f"[error] git clone exited with code {rc[0] if rc else 'unknown'}."
        # Clean up partial clone
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
            yield "[info] Cleaned up partial clone."


# ── Module removal ─────────────────────────────────────────────────────────────

def remove_module(module_name: str, modules_path: str) -> dict:
    """
    Delete the module directory from the modules folder.
    Returns { success: bool, message: str }.
    """
    dest = Path(modules_path) / module_name
    if not dest.exists():
        return {"success": False, "message": f"Module '{module_name}' not found."}
    if not dest.is_dir():
        return {"success": False, "message": f"'{module_name}' is not a directory."}

    try:
        shutil.rmtree(dest)
        return {"success": True, "message": f"Module '{module_name}' removed."}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


# ── Source / module updates ────────────────────────────────────────────────────

async def update_azerothcore(ac_path: str) -> AsyncIterator[str]:
    """
    git pull --rebase + git submodule update for the AzerothCore source tree.
    Streams output line-by-line.
    """
    base = Path(ac_path)
    if not base.exists():
        yield f"[error] AzerothCore source path not found: {ac_path}"
        return
    if not (base / ".git").exists():
        yield f"[error] No .git directory at {ac_path} — cannot update a non-git directory."
        return

    yield f"[info] Updating AzerothCore source at {ac_path} …"

    rc: list[int] = []
    async for line in _run("git pull --rebase", cwd=ac_path, rc_out=rc):
        yield line
    if rc and rc[0] != 0:
        yield f"[error] git pull exited with code {rc[0]}."
        return

    rc.clear()
    yield "[info] Updating submodules …"
    async for line in _run(
        "git submodule update --init --recursive", cwd=ac_path, rc_out=rc
    ):
        yield line
    if rc and rc[0] != 0:
        yield f"[error] git submodule update exited with code {rc[0]}."
        return

    yield "[ok] AzerothCore source updated successfully."
    yield "[done]"


async def update_module(module_name: str, modules_path: str) -> AsyncIterator[str]:
    """
    git pull --rebase + submodule update for a single installed module.
    Streams output line-by-line.
    """
    dest = Path(modules_path) / module_name
    if not dest.exists():
        yield f"[error] Module '{module_name}' not found."
        return
    if not (dest / ".git").exists():
        yield f"[error] Module '{module_name}' has no .git directory — cannot update."
        return

    yield f"[info] Updating module '{module_name}' …"

    rc: list[int] = []
    async for line in _run("git pull --rebase", cwd=str(dest), rc_out=rc):
        yield line
    if rc and rc[0] != 0:
        yield f"[error] git pull exited with code {rc[0]}."
        return

    rc.clear()
    async for line in _run(
        "git submodule update --init --recursive", cwd=str(dest), rc_out=rc
    ):
        yield line
    if rc and rc[0] != 0:
        yield f"[error] git submodule update exited with code {rc[0]}."
        return

    yield f"[ok] Module '{module_name}' updated successfully."
    yield "[done]"


async def update_all_modules(modules_path: str) -> AsyncIterator[str]:
    """
    git pull --rebase for every installed module that has a .git directory.
    Streams output line-by-line with per-module headers.
    """
    base = Path(modules_path)
    if not base.exists():
        yield f"[error] Modules directory not found: {modules_path}"
        return

    modules = [
        e for e in sorted(base.iterdir())
        if e.is_dir() and (e / ".git").exists()
    ]

    if not modules:
        yield "[info] No git-tracked modules found — nothing to update."
        yield "[done]"
        return

    yield f"[info] Found {len(modules)} git-tracked module(s) to update."
    failed: list[str] = []

    for entry in modules:
        yield f"\n[info] ── {entry.name} ──"
        rc: list[int] = []
        async for line in _run("git pull --rebase", cwd=str(entry), rc_out=rc):
            yield line
        if rc and rc[0] != 0:
            yield f"[error] {entry.name}: git pull exited with code {rc[0]}."
            failed.append(entry.name)
            continue
        rc.clear()
        async for line in _run(
            "git submodule update --init --recursive", cwd=str(entry), rc_out=rc
        ):
            yield line
        if rc and rc[0] != 0:
            yield f"[error] {entry.name}: submodule update exited with code {rc[0]}."
            failed.append(entry.name)
        else:
            yield f"[ok] {entry.name} updated."

    if failed:
        yield f"\n[error] {len(failed)} module(s) failed to update: {', '.join(failed)}"
    else:
        yield f"\n[ok] All {len(modules)} module(s) updated successfully."
    yield "[done]"
