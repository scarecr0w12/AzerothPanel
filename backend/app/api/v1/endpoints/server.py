from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.models.schemas import (
    ServerStatusResponse,
    ServerActionResponse,
    SoapCommandRequest,
    SoapCommandResponse,
)
from app.services.azerothcore import server_manager as sm
from app.services.azerothcore import soap_client as soap

router = APIRouter(prefix="/server", tags=["Server Control"])


@router.get("/status", response_model=ServerStatusResponse)
async def get_status(_: dict = Depends(get_current_user)):
    """Get running status, PID, CPU, and memory for both server processes."""
    return ServerStatusResponse(
        worldserver=sm.get_process_status("worldserver"),
        authserver=sm.get_process_status("authserver"),
    )


# ---------------------------------------------------------------------------
# Worldserver actions
# ---------------------------------------------------------------------------

@router.post("/worldserver/start", response_model=ServerActionResponse)
async def start_worldserver(_: dict = Depends(get_current_user)):
    ok, msg = await sm.start_worldserver()
    return ServerActionResponse(success=ok, message=msg)


@router.post("/worldserver/stop", response_model=ServerActionResponse)
async def stop_worldserver(_: dict = Depends(get_current_user)):
    ok, msg = await sm.stop_worldserver()
    return ServerActionResponse(success=ok, message=msg)


@router.post("/worldserver/restart", response_model=ServerActionResponse)
async def restart_worldserver(_: dict = Depends(get_current_user)):
    ok, msg = await sm.restart_worldserver()
    return ServerActionResponse(success=ok, message=msg)


# ---------------------------------------------------------------------------
# Authserver actions
# ---------------------------------------------------------------------------

@router.post("/authserver/start", response_model=ServerActionResponse)
async def start_authserver(_: dict = Depends(get_current_user)):
    ok, msg = await sm.start_authserver()
    return ServerActionResponse(success=ok, message=msg)


@router.post("/authserver/stop", response_model=ServerActionResponse)
async def stop_authserver(_: dict = Depends(get_current_user)):
    ok, msg = await sm.stop_authserver()
    return ServerActionResponse(success=ok, message=msg)


@router.post("/authserver/restart", response_model=ServerActionResponse)
async def restart_authserver(_: dict = Depends(get_current_user)):
    ok, msg = await sm.restart_authserver()
    return ServerActionResponse(success=ok, message=msg)


# ---------------------------------------------------------------------------
# SOAP in-game commands
# ---------------------------------------------------------------------------

@router.post("/command", response_model=SoapCommandResponse)
async def execute_command(
    req: SoapCommandRequest, _: dict = Depends(get_current_user)
):
    """Send any GM command to the worldserver via SOAP."""
    ok, result = await soap.execute_command(req.command)
    return SoapCommandResponse(success=ok, result=result)


@router.get("/info")
async def server_info(_: dict = Depends(get_current_user)):
    """Fetch worldserver runtime info via SOAP (.server info)."""
    ok, result = await soap.get_server_info()
    return {"success": ok, "info": result}


@router.post("/announce")
async def announce(req: SoapCommandRequest, _: dict = Depends(get_current_user)):
    """Send a server-wide announcement message."""
    ok, result = await soap.send_announcement(req.command)
    return {"success": ok, "result": result}

