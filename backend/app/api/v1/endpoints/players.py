import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from typing import Optional

from app.core.security import get_current_user
from app.core.database import get_auth_db, get_char_db_for_instance
from app.models.schemas import BanRequest, AnnouncementRequest, ModifyPlayerRequest
from app.services.azerothcore import soap_client as soap

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/players", tags=["Player Management"])


@router.get("/online")
async def get_online_players(_: dict = Depends(get_current_user)):
    """Get list of currently online players via SOAP."""
    ok, result = await soap.get_online_players()
    return {"success": ok, "data": result}


@router.get("/accounts")
async def list_accounts(
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _: dict = Depends(get_current_user),
    db=Depends(get_auth_db),
):
    """List game accounts with pagination and optional search."""
    offset = (page - 1) * page_size
    if search:
        q = text(
            "SELECT id, username, email, gmlevel, locked, last_ip, "
            "DATE_FORMAT(last_login, '%Y-%m-%d %H:%i:%s') as last_login "
            "FROM account WHERE username LIKE :pattern "
            "ORDER BY id LIMIT :limit OFFSET :offset"
        )
        rows = await db.execute(q, {"pattern": f"%{search}%", "limit": page_size, "offset": offset})
    else:
        q = text(
            "SELECT id, username, email, gmlevel, locked, last_ip, "
            "DATE_FORMAT(last_login, '%Y-%m-%d %H:%i:%s') as last_login "
            "FROM account ORDER BY id LIMIT :limit OFFSET :offset"
        )
        rows = await db.execute(q, {"limit": page_size, "offset": offset})
    results = [dict(r._mapping) for r in rows]
    return {"accounts": results, "page": page, "page_size": page_size}


@router.get("/characters")
async def list_characters(
    search: Optional[str] = Query(default=None),
    online_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    instance_id: Optional[int] = Query(default=None, description="Worldserver instance ID (scopes characters DB)"),
    _: dict = Depends(get_current_user),
):
    """List characters with pagination, search, and online filter."""
    offset = (page - 1) * page_size
    conditions = []
    params: dict = {"limit": page_size, "offset": offset}
    if search:
        conditions.append("name LIKE :pattern")
        params["pattern"] = f"%{search}%"
    if online_only:
        conditions.append("online = 1")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    q = text(
        f"SELECT guid, account, name, race, class, level, gender, zone, online, money "
        f"FROM characters {where} ORDER BY online DESC, level DESC "
        f"LIMIT :limit OFFSET :offset"
    )
    async for db in get_char_db_for_instance(instance_id):
        rows = await db.execute(q, params)
        results = [dict(r._mapping) for r in rows]
    return {"characters": results, "page": page, "page_size": page_size}


@router.get("/characters/{guid}")
async def get_character(
    guid: int,
    instance_id: Optional[int] = Query(default=None, description="Worldserver instance ID (scopes characters DB)"),
    _: dict = Depends(get_current_user),
):
    """Get detailed information about a specific character."""
    q = text(
        "SELECT guid, account, name, race, class, level, gender, zone, "
        "online, money, xp, totalKills, totalHonorPoints, arenaPoints "
        "FROM characters WHERE guid = :guid"
    )
    async for db in get_char_db_for_instance(instance_id):
        row = (await db.execute(q, {"guid": guid})).first()
    if not row:
        raise HTTPException(status_code=404, detail="Character not found")
    return dict(row._mapping)


@router.post("/ban")
async def ban_account(req: BanRequest, _: dict = Depends(get_current_user)):
    """Ban a game account via SOAP command."""
    logger.info("Ban request for account_id=%s duration=%s reason=%r", req.account_id, req.duration, req.reason)
    ok, result = await soap.ban_account(
        str(req.account_id), req.duration, req.reason
    )
    if not ok:
        logger.warning("Ban failed for account_id=%s: %s", req.account_id, result)
    return {"success": ok, "result": result}


@router.post("/unban/{account_id}")
async def unban_account(account_id: int, _: dict = Depends(get_current_user)):
    """Unban a game account via SOAP command."""
    logger.info("Unban request for account_id=%s", account_id)
    ok, result = await soap.unban_account(str(account_id))
    return {"success": ok, "result": result}


@router.post("/kick/{player_name}")
async def kick_player(player_name: str, _: dict = Depends(get_current_user)):
    """Kick an online player from the server."""
    logger.info("Kick request for player '%s'", player_name)
    ok, result = await soap.kick_player(player_name)
    if not ok:
        logger.warning("Kick failed for player '%s': %s", player_name, result)
    return {"success": ok, "result": result}


@router.post("/announce")
async def announce(req: AnnouncementRequest, _: dict = Depends(get_current_user)):
    """Send an in-game announcement or whisper to a specific player."""
    if req.target == "all":
        ok, result = await soap.send_announcement(req.message)
    else:
        ok, result = await soap.whisper_player(req.target, req.message)
    return {"success": ok, "result": result}


@router.post("/modify")
async def modify_player(req: ModifyPlayerRequest, _: dict = Depends(get_current_user)):
    """Modify a player's attributes (level, money) via SOAP."""
    logger.info("Modify player guid=%s field=%s value=%s", req.guid, req.field, req.value)
    if req.field == "level":
        ok, result = await soap.modify_player_level(str(req.guid), int(req.value))
    elif req.field == "money":
        ok, result = await soap.add_money(str(req.guid), int(req.value))
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported field: {req.field}")
    return {"success": ok, "result": result}

