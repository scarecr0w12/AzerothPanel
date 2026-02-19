"""
WebSocket endpoint for real-time log streaming.

Connect to: ws://host/ws/logs/{source}?token=<jwt>

The client can send a JSON message to update the filter:
  {"level": "ERROR"}  – only stream ERROR lines
  {"level": null}     – stream all lines
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from app.core.config import settings
from app.services.logs.log_manager import tail_follow

router = APIRouter()
ALGORITHM = "HS256"


def _verify_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub") is not None
    except JWTError:
        return False


@router.websocket("/ws/logs/{source}")
async def ws_logs(
    websocket: WebSocket,
    source: str,
    token: str = Query(...),
):
    """
    Stream live log lines for a given source to the browser.
    Authentication is via `?token=<jwt>` query parameter.
    """
    if not _verify_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    active_level_filter: list[str | None] = [None]

    async def _recv_loop():
        """Listen for filter-update messages from the client."""
        try:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                active_level_filter[0] = msg.get("level")
        except Exception:
            pass

    recv_task = asyncio.create_task(_recv_loop())

    try:
        async for line in tail_follow(source):
            # Apply level filter if set
            lvl = active_level_filter[0]
            if lvl:
                upper = line.upper()
                if lvl.upper() not in upper:
                    continue

            payload = json.dumps({"line": line, "source": source})
            try:
                await websocket.send_text(payload)
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        recv_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass

