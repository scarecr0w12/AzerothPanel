"""
Settings management endpoints.

GET  /api/v1/settings           – return all current runtime settings
PUT  /api/v1/settings           – update one or more settings (partial update)
POST /api/v1/settings/test-db   – test a database connection with given credentials
"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.models.schemas import PanelSettingsResponse, PanelSettingsUpdate, TestDbRequest
from app.services.panel_settings import get_settings_dict, update_settings

router = APIRouter(prefix="/settings", tags=["Settings"])


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

