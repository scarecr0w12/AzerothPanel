from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import json

from pathlib import Path

from app.core.security import get_current_user
from app.models.schemas import InstallConfig
from app.services.azerothcore.installer import run_installation
from app.services.panel_settings import get_settings_dict

router = APIRouter(prefix="/installation", tags=["Installation"])


@router.get("/status")
async def installation_status(_: dict = Depends(get_current_user)):
    """Check whether AzerothCore appears to be installed."""
    s = await get_settings_dict()
    ac_path = Path(s["AC_PATH"])
    binary_path = Path(s["AC_BINARY_PATH"])

    checks = {
        "repo_cloned": (ac_path / ".git").exists(),
        "compiled": (binary_path / "worldserver").exists(),
        "authserver_binary": (binary_path / "authserver").exists(),
        "worldserver_conf": Path(s["AC_WORLDSERVER_CONF"]).exists(),
        "authserver_conf": Path(s["AC_AUTHSERVER_CONF"]).exists(),
        "data_dir": Path(s["AC_DATA_PATH"]).exists(),
        "log_dir": Path(s["AC_LOG_PATH"]).exists(),
    }
    overall = all(checks.values())
    return {"installed": overall, "checks": checks, "ac_path": str(ac_path)}


@router.post("/run")
async def run_install(
    config: InstallConfig,
    _: dict = Depends(get_current_user),
):
    """
    Start the automated AzerothCore installation.
    Returns a streaming response of log lines (text/event-stream).
    """
    config_dict = config.model_dump()

    async def event_stream():
        async for line in run_installation(config_dict):
            data = json.dumps({"line": line})
            yield f"data: {data}\n\n"
        yield "data: {\"done\": true}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/config/worldserver")
async def get_worldserver_config(_: dict = Depends(get_current_user)):
    """Read the worldserver.conf file content."""
    s = await get_settings_dict()
    path = Path(s["AC_WORLDSERVER_CONF"])
    if not path.exists():
        return {"exists": False, "content": ""}
    return {"exists": True, "content": path.read_text(errors="replace")}


@router.put("/config/worldserver")
async def save_worldserver_config(body: dict, _: dict = Depends(get_current_user)):
    """Save updated worldserver.conf content."""
    s = await get_settings_dict()
    path = Path(s["AC_WORLDSERVER_CONF"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.get("content", ""), encoding="utf-8")
    return {"success": True}


@router.get("/config/authserver")
async def get_authserver_config(_: dict = Depends(get_current_user)):
    """Read the authserver.conf file content."""
    s = await get_settings_dict()
    path = Path(s["AC_AUTHSERVER_CONF"])
    if not path.exists():
        return {"exists": False, "content": ""}
    return {"exists": True, "content": path.read_text(errors="replace")}


@router.put("/config/authserver")
async def save_authserver_config(body: dict, _: dict = Depends(get_current_user)):
    """Save updated authserver.conf content."""
    s = await get_settings_dict()
    path = Path(s["AC_AUTHSERVER_CONF"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.get("content", ""), encoding="utf-8")
    return {"success": True}

