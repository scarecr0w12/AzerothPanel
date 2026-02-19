from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import json

from app.core.security import get_current_user
from app.models.schemas import BuildConfig, BuildStatusResponse
from app.services.azerothcore.compiler import run_build, get_build_status

router = APIRouter(prefix="/compilation", tags=["Compilation"])


@router.get("/status", response_model=BuildStatusResponse)
async def build_status(_: dict = Depends(get_current_user)):
    """Get the current state of an ongoing or completed build."""
    s = get_build_status()
    return BuildStatusResponse(
        running=s.get("running", False),
        progress_percent=s.get("progress"),
        current_step=s.get("step"),
        elapsed_seconds=s.get("elapsed_seconds"),
        error=s.get("error"),
    )


@router.post("/build")
async def start_build(
    config: BuildConfig,
    _: dict = Depends(get_current_user),
):
    """
    Start a build of AzerothCore.
    Returns a streaming Server-Sent Events (SSE) response of build log lines.
    """
    async def event_stream():
        async for line in run_build(
            build_type=config.build_type,
            jobs=config.jobs,
            cmake_extra=config.cmake_extra,
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

