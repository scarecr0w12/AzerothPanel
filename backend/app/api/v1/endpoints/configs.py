"""
Config file management endpoints.

GET  /configs              – list every .conf file in AC_CONF_PATH (recursive)
GET  /configs/{rel_path}   – return the raw text content of a config file
PUT  /configs/{rel_path}   – overwrite the content of a config file

rel_path is the path relative to AC_CONF_PATH, e.g.:
  worldserver.conf
  modules/mod_aoe_loot.conf
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.panel_settings import get_settings_dict

router = APIRouter(prefix="/configs", tags=["Configs"])

_CORE_NAMES = {"worldserver.conf", "authserver.conf"}


def _safe_path(conf_dir: Path, rel: str) -> Path:
    """
    Resolve a relative config path to an absolute path that must remain inside
    conf_dir.  Raises HTTPException 400 on traversal attempts.
    """
    resolved = (conf_dir / rel).resolve()
    conf_dir_resolved = conf_dir.resolve()
    if not str(resolved).startswith(str(conf_dir_resolved) + "/") and \
            resolved != conf_dir_resolved:
        raise HTTPException(status_code=400, detail="Path traversal detected.")
    if not rel.endswith(".conf"):
        raise HTTPException(status_code=400, detail="Only .conf files are allowed.")
    return resolved


async def _conf_dir() -> Path:
    s = await get_settings_dict()
    return Path(s["AC_CONF_PATH"])


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("")
async def list_configs(_: dict = Depends(get_current_user)):
    """
    Return a list of all .conf files in AC_CONF_PATH (searched recursively).
    Each entry: name (relative path), label, size_bytes, is_module (bool).
    """
    conf_dir = await _conf_dir()
    if not conf_dir.exists():
        return {"conf_dir": str(conf_dir), "files": []}

    files = []
    for p in sorted(conf_dir.rglob("*.conf")):
        rel = str(p.relative_to(conf_dir))   # e.g. "worldserver.conf" or "modules/mod_x.conf"
        # A file is a module config if it lives in a subdirectory OR its name is
        # not one of the two core config files.
        is_module = p.parent != conf_dir or p.name not in _CORE_NAMES
        files.append({
            "name":       rel,
            "label":      _pretty_label(p.name),
            "size_bytes": p.stat().st_size,
            "is_module":  is_module,
        })

    return {"conf_dir": str(conf_dir), "files": files}


def _pretty_label(filename: str) -> str:
    """Turn 'mod-aoe-loot.conf' → 'Mod Aoe Loot'."""
    stem = filename.removesuffix(".conf")
    return stem.replace("-", " ").replace("_", " ").title()


# ── Read ──────────────────────────────────────────────────────────────────────

# {rel_path:path} lets FastAPI match slashes, e.g. /configs/modules/foo.conf
@router.get("/{rel_path:path}")
async def get_config(rel_path: str, _: dict = Depends(get_current_user)):
    """Return the raw text content of a .conf file."""
    conf_dir = await _conf_dir()
    path = _safe_path(conf_dir, rel_path)

    if not path.exists():
        return {"filename": rel_path, "exists": False, "content": ""}
    return {
        "filename": rel_path,
        "exists": True,
        "content": path.read_text(errors="replace"),
    }


# ── Write ─────────────────────────────────────────────────────────────────────

class ConfigWriteBody(BaseModel):
    content: str


@router.put("/{rel_path:path}")
async def save_config(
    rel_path: str,
    body: ConfigWriteBody,
    _: dict = Depends(get_current_user),
):
    """Overwrite a .conf file with the provided content."""
    conf_dir = await _conf_dir()
    path = _safe_path(conf_dir, rel_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{rel_path} not found in {conf_dir}")

    path.write_text(body.content, encoding="utf-8")
    return {"success": True, "filename": rel_path}
