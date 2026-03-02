"""
API endpoints for client data extraction.

Provides endpoints for:
- Checking data extraction status
- Downloading pre-extracted data
- Extracting from local client
- Cancelling running operations
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.core.security import get_current_user
from app.services.azerothcore import data_extractor
from app.services.panel_settings import get_settings_dict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data-extraction", tags=["Data Extraction"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class DownloadRequest(BaseModel):
    """Request to download pre-extracted data."""
    data_path: Optional[str] = None  # Uses AC_DATA_PATH from settings if not provided
    data_url: Optional[str] = None   # Uses default AzerothCore release URL if not provided


class ExtractionRequest(BaseModel):
    """Request to extract data from local client."""
    client_path: Optional[str] = None  # Uses AC_CLIENT_PATH from settings if not provided
    data_path: Optional[str] = None   # Uses AC_DATA_PATH from settings if not provided
    binary_path: Optional[str] = None  # Uses AC_BINARY_PATH from settings if not provided
    extract_dbc: bool = True
    extract_maps: bool = True
    extract_vmaps: bool = True
    generate_mmaps: bool = True


class ExtractionStatusResponse(BaseModel):
    """Response model for extraction status."""
    in_progress: bool
    current_step: Optional[str]
    progress_percent: int
    started_at: Optional[str]
    error: Optional[str]
    data_path: str
    has_dbc: bool
    has_maps: bool
    has_vmaps: bool
    has_mmaps: bool
    data_present: bool


# ---------------------------------------------------------------------------
# Status Endpoint
# ---------------------------------------------------------------------------

@router.get("/status", response_model=ExtractionStatusResponse)
async def get_extraction_status(_: dict = Depends(get_current_user)):
    """
    Get current extraction status and data presence.
    
    Returns information about:
    - Whether an extraction is in progress
    - Current step and progress percentage
    - Which data types are present (DBC, Maps, VMaps, MMaps)
    """
    status = data_extractor.get_extraction_status()
    return ExtractionStatusResponse(**status)


# ---------------------------------------------------------------------------
# Download Pre-Extracted Data
# ---------------------------------------------------------------------------

@router.post("/download")
async def download_data(
    req: DownloadRequest,
    _: dict = Depends(get_current_user),
):
    """
    Download pre-extracted client data from wowgaming/client-data releases.
    
    This is the recommended method - downloads data.zip (~1.5GB)
    and extracts to the data directory.
    
    Streams progress updates via Server-Sent Events (SSE).
    """
    # Check if extraction is already in progress
    status = data_extractor.get_extraction_status()
    if status["in_progress"]:
        raise HTTPException(
            status_code=409,
            detail="An extraction operation is already in progress"
        )
    
    # Get settings for paths
    settings = await get_settings_dict()
    data_path = req.data_path or settings.get("AC_DATA_PATH", "/opt/azerothcore/build/data")
    data_url = req.data_url or data_extractor.DATA_URL
    logger.info("Data download requested: url=%s path=%s", data_url, data_path)
    
    async def event_generator():
        async for line in data_extractor.download_preextracted_data(data_path, data_url):
            yield f"data: {line}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ---------------------------------------------------------------------------
# Extract from Local Client
# ---------------------------------------------------------------------------

@router.post("/extract")
async def extract_from_client(
    req: ExtractionRequest,
    _: dict = Depends(get_current_user),
):
    """
    Extract client data from a local WoW 3.3.5a client.
    
    Requires a valid World of Warcraft 3.3.5a (12340) client installation.
    Uses extraction tools built during compilation.
    
    Streams progress updates via Server-Sent Events (SSE).
    """
    # Check if extraction is already in progress
    status = data_extractor.get_extraction_status()
    if status["in_progress"]:
        raise HTTPException(
            status_code=409,
            detail="An extraction operation is already in progress"
        )
    
    # Get settings for paths
    settings = await get_settings_dict()
    from app.core.config import settings as boot_settings
    client_path = req.client_path or settings.get("AC_CLIENT_PATH", boot_settings.CLIENT_PATH)
    data_path = req.data_path or settings.get("AC_DATA_PATH", f"{boot_settings.AC_PATH}/build/data")
    binary_path = req.binary_path or settings.get("AC_BINARY_PATH", f"{boot_settings.AC_PATH}/build/bin")
    logger.info(
        "Client extraction requested: client=%s data=%s binary=%s options=%s",
        client_path, data_path, binary_path,
        {k: v for k, v in {"dbc": req.extract_dbc, "maps": req.extract_maps, "vmaps": req.extract_vmaps, "mmaps": req.generate_mmaps}.items()},
    )
    
    options = {
        "extract_dbc": req.extract_dbc,
        "extract_maps": req.extract_maps,
        "extract_vmaps": req.extract_vmaps,
        "generate_mmaps": req.generate_mmaps,
    }
    
    async def event_generator():
        async for line in data_extractor.extract_from_client(
            client_path, data_path, binary_path, options
        ):
            yield f"data: {line}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ---------------------------------------------------------------------------
# Cancel Operation
# ---------------------------------------------------------------------------

@router.post("/cancel")
async def cancel_extraction(_: dict = Depends(get_current_user)):
    """
    Cancel any running extraction operation.
    
    Returns True if an operation was cancelled, False if no operation was running.
    """
    logger.info("Cancel extraction requested")
    cancelled = await data_extractor.cancel_extraction()
    if cancelled:
        logger.info("Extraction operation cancelled")
    return {"cancelled": cancelled}
