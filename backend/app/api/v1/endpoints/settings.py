"""
Settings management endpoints.

GET  /api/v1/settings                – return all current runtime settings
PUT  /api/v1/settings                – update one or more settings (partial update)
POST /api/v1/settings/test-db        – test a database connection with given credentials
GET  /api/v1/settings/panel-version  – return current git version / branch / commits-behind
POST /api/v1/settings/update-panel   – pull latest code & rebuild Docker containers
"""
import asyncio
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.models.schemas import PanelSettingsResponse, PanelSettingsUpdate, TestDbRequest

from app.services.panel_settings import get_settings_dict, update_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])

# ─── Daemon helpers (shared with server_manager) ─────────────────────────────

_DAEMON_HOST: str = os.environ.get("AC_DAEMON_HOST", "127.0.0.1")
_DAEMON_PORT: int = int(os.environ.get("AC_DAEMON_PORT", "7879"))


async def _daemon_send(request: dict, timeout: float = 660.0) -> dict | None:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(_DAEMON_HOST, _DAEMON_PORT), timeout=5.0
        )
        try:
            writer.write(json.dumps(request).encode() + b"\n")
            await writer.drain()
            raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
            return json.loads(raw.decode())
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    except (ConnectionRefusedError, asyncio.TimeoutError, OSError) as exc:
        logger.debug(f"Daemon unavailable: {exc}")
        return None
    except Exception as exc:
        logger.warning(f"Daemon communication error: {exc}")
        return None


@router.get("", response_model=PanelSettingsResponse)
async def get_settings_endpoint(_: dict = Depends(get_current_user)):
    """Return all current runtime settings."""
    return await get_settings_dict()


@router.put("", response_model=PanelSettingsResponse)
async def update_settings_endpoint(
    body: PanelSettingsUpdate,
    _: dict = Depends(get_current_user),
):
    """
    Update runtime settings.  Only fields that are explicitly provided
    (non-null) will be written to the database.
    """
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided to update.")
    return await update_settings(updates)


@router.post("/test-db")
async def test_db_connection(
    body: TestDbRequest,
    _: dict = Depends(get_current_user),
):
    """
    Test a MySQL database connection with the provided credentials.
    Returns {"success": true} or {"success": false, "error": "..."}.
    """
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        url = (
            f"mysql+aiomysql://{body.user}:{body.password}"
            f"@{body.host}:{body.port}/{body.db_name}"
        )
        engine = create_async_engine(url, echo=False, pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"success": True}
        finally:
            await engine.dispose()
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.get("/panel-version")
async def panel_version(_: dict = Depends(get_current_user)):
    """
    Return current git version information for the AzerothPanel installation.
    Queries the host daemon (which runs outside Docker) so git is reachable.
    """
    resp = await _daemon_send({"cmd": "version"}, timeout=30.0)
    if resp is None:
        raise HTTPException(
            status_code=503,
            detail="Host daemon is not reachable. Run 'make daemon-start' on the host.",
        )
    return resp


@router.post("/update-panel")
async def update_panel(_: dict = Depends(get_current_user)):
    """
    Pull the latest AzerothPanel code from GitHub and rebuild/restart the containers.
    Runs on the host via the AC daemon – the update will restart this very service.
    """
    resp = await _daemon_send({"cmd": "update"}, timeout=660.0)
    if resp is None:
        raise HTTPException(
            status_code=503,
            detail="Host daemon is not reachable. Run 'make daemon-start' on the host.",
        )
    if not resp.get("success"):
        raise HTTPException(status_code=500, detail=resp.get("message", "Update failed"))
    return resp
