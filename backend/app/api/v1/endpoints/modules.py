"""
Module management endpoints.

GET    /modules/catalogue              – search the AzerothCore online catalogue
GET    /modules/installed              – list locally installed modules
POST   /modules/install               – clone a module (streaming SSE)
POST   /modules/update-azerothcore    – git pull AzerothCore source (streaming SSE)
POST   /modules/update-all            – git pull all git-tracked modules (streaming SSE)
POST   /modules/{module_name}/update  – git pull a single module (streaming SSE)
DELETE /modules/{module_name}         – remove a module from the modules dir
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import json

from app.core.security import get_current_user
from app.services.panel_settings import get_settings_dict
from app.services.azerothcore.module_manager import (
    fetch_catalogue,
    fetch_rate_limit,
    list_installed_modules,
    install_module,
    remove_module,
    update_azerothcore,
    update_module,
    update_all_modules,
    CATALOGUE_CATEGORIES,
)

router = APIRouter(prefix="/modules", tags=["Modules"])


# ── Catalogue ─────────────────────────────────────────────────────────────────

@router.get("/catalogue")
async def get_catalogue(
    category: str = Query("modules", description="Category filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    _: dict = Depends(get_current_user),
):
    """
    Proxy the GitHub Search API for AzerothCore catalogue repositories.
    Supported categories: modules, premium, tools, lua, sql
    """
    if category not in CATALOGUE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category '{category}'. Valid: {list(CATALOGUE_CATEGORIES)}",
        )
    s = await get_settings_dict()
    github_token = s.get("GITHUB_TOKEN") or None

    try:
        data = await fetch_catalogue(
            category=category,
            page=page,
            per_page=per_page,
            github_token=github_token,
        )
    except RuntimeError as exc:
        # Rate-limit error – pass the human-readable message through as 429
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {exc}") from exc

    # Augment items with installed status
    modules_path = str(Path(s["AC_PATH"]) / "modules")
    installed = {m["name"] for m in list_installed_modules(modules_path)}
    for item in data["items"]:
        item["installed"] = item["name"] in installed

    return data


# ── GitHub rate-limit / token test ───────────────────────────────────────────

@router.get("/github/rate-limit")
async def github_rate_limit(_: dict = Depends(get_current_user)):
    """Return the current GitHub API search rate-limit status."""
    s = await get_settings_dict()
    github_token = s.get("GITHUB_TOKEN") or None
    try:
        return await fetch_rate_limit(github_token=github_token)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {exc}") from exc


# ── Installed modules ─────────────────────────────────────────────────────────

@router.get("/installed")
async def get_installed_modules(_: dict = Depends(get_current_user)):
    """List all modules currently present in the AzerothCore modules directory."""
    s = await get_settings_dict()
    modules_path = str(Path(s["AC_PATH"]) / "modules")
    modules = list_installed_modules(modules_path)
    return {"modules_path": modules_path, "modules": modules}


# ── Install a module ──────────────────────────────────────────────────────────


from pydantic import BaseModel


class InstallModuleBody(BaseModel):
    clone_url: str
    module_name: str
    branch: str | None = None


@router.post("/install")
async def install_module_endpoint(
    body: InstallModuleBody,
    _: dict = Depends(get_current_user),
):
    """
    Clone a module repository into the AzerothCore modules directory.
    Returns a streaming SSE response of git output lines.
    """
    s = await get_settings_dict()
    modules_path = str(Path(s["AC_PATH"]) / "modules")

    async def event_stream():
        async for line in install_module(
            clone_url=body.clone_url,
            module_name=body.module_name,
            modules_path=modules_path,
            branch=body.branch,
        ):
            payload = json.dumps({"line": line})
            yield f"data: {payload}\n\n"
        yield 'data: {"done": true}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Remove a module ───────────────────────────────────────────────────────────

@router.delete("/{module_name}")
async def delete_module(
    module_name: str,
    _: dict = Depends(get_current_user),
):
    """Remove a module directory from the AzerothCore modules folder."""
    # Basic path traversal guard
    if "/" in module_name or "\\" in module_name or module_name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid module name.")

    s = await get_settings_dict()
    modules_path = str(Path(s["AC_PATH"]) / "modules")
    result = remove_module(module_name, modules_path)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


# ── Update AzerothCore source ─────────────────────────────────────────────────

@router.post("/update-azerothcore")
async def update_azerothcore_endpoint(_: dict = Depends(get_current_user)):
    """
    git pull --rebase the AzerothCore source tree and update submodules.
    Returns a streaming SSE response of git output lines.
    """
    s = await get_settings_dict()
    ac_path = s["AC_PATH"]

    async def event_stream():
        async for line in update_azerothcore(ac_path):
            payload = json.dumps({"line": line})
            yield f"data: {payload}\n\n"
        yield 'data: {"done": true}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Update a single module ────────────────────────────────────────────────────

@router.post("/{module_name}/update")
async def update_module_endpoint(
    module_name: str,
    _: dict = Depends(get_current_user),
):
    """
    git pull --rebase + submodule update for a single installed module.
    Returns a streaming SSE response of git output lines.
    """
    if "/" in module_name or "\\" in module_name or module_name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid module name.")

    s = await get_settings_dict()
    modules_path = str(Path(s["AC_PATH"]) / "modules")

    async def event_stream():
        async for line in update_module(module_name, modules_path):
            payload = json.dumps({"line": line})
            yield f"data: {payload}\n\n"
        yield 'data: {"done": true}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Update all modules ────────────────────────────────────────────────────────

@router.post("/update-all")
async def update_all_modules_endpoint(_: dict = Depends(get_current_user)):
    """
    git pull --rebase for every installed module that has a .git directory.
    Returns a streaming SSE response of git output lines.
    """
    s = await get_settings_dict()
    modules_path = str(Path(s["AC_PATH"]) / "modules")

    async def event_stream():
        async for line in update_all_modules(modules_path):
            payload = json.dumps({"line": line})
            yield f"data: {payload}\n\n"
        yield 'data: {"done": true}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
