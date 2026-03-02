"""
worldserver/instances  –  CRUD management for multiple worldserver instances.

Each instance maps to an independent worldserver process tracked by the
host daemon under a unique ``process_name`` (e.g. "worldserver-ptr").

Endpoints
---------
GET    /server/instances           – list all instances (with live status)
POST   /server/instances           – create a new instance
GET    /server/instances/{id}      – get one instance (with live status)
PUT    /server/instances/{id}      – update metadata (display_name, paths, …)
DELETE /server/instances/{id}      – delete an instance (stops it first)
POST   /server/instances/{id}/start
POST   /server/instances/{id}/stop
POST   /server/instances/{id}/restart
POST   /server/instances/{id}/command
GET    /server/instances/{id}/config       – read worldserver.conf
PUT    /server/instances/{id}/config       – write worldserver.conf
POST   /server/instances/{id}/generate-config  – create conf from defaults
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_panel_db
from app.core.security import get_current_user
from app.models.panel_models import WorldServerInstance
from app.models.schemas import (
    WorldServerInstanceCreate,
    WorldServerInstanceSchema,
    WorldServerInstanceUpdate,
    WorldServerInstanceListResponse,
    WorldServerProvisionRequest,
    ServerActionResponse,
    SoapCommandRequest,
    SoapCommandResponse,
)
from app.services.azerothcore import server_manager as sm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/server/instances", tags=["Worldserver Instances"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_instance_or_404(
    instance_id: int, db: AsyncSession
) -> WorldServerInstance:
    result = await db.execute(
        select(WorldServerInstance).where(WorldServerInstance.id == instance_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
    return obj


async def _enrich(inst: WorldServerInstance) -> WorldServerInstanceSchema:
    """Attach live process status to an ORM instance."""
    status = await sm.get_instance_status(inst.process_name)
    return WorldServerInstanceSchema(
        id=inst.id,
        display_name=inst.display_name,
        process_name=inst.process_name,
        binary_path=inst.binary_path,
        working_dir=inst.working_dir,
        conf_path=inst.conf_path,
        notes=inst.notes,
        sort_order=inst.sort_order,
        ac_path=inst.ac_path,
        build_path=inst.build_path,
        char_db_host=inst.char_db_host,
        char_db_port=inst.char_db_port,
        char_db_user=inst.char_db_user,
        char_db_password=inst.char_db_password,
        char_db_name=inst.char_db_name,
        soap_host=inst.soap_host,
        soap_port=inst.soap_port,
        soap_user=inst.soap_user,
        soap_password=inst.soap_password,
        status=status,
    )


def _patch_conf(content: str, overrides: dict[str, str]) -> str:
    """
    Apply key=value patches to a worldserver.conf text.
    Lines that already exist are updated in-place (preserving formatting).
    Keys that don't exist in the file are appended at the end.
    """
    for key, value in overrides.items():
        # Match lines like: KeyName = old   (with optional spaces / inline comment)
        pattern = re.compile(
            r'^(\s*' + re.escape(key) + r'\s*=\s*)([^\r\n]*)',
            re.MULTILINE,
        )
        replacement = f'\\g<1>{value}'
        new_content, n = re.subn(pattern, replacement, content)
        if n:
            content = new_content
        else:
            # Key not found — append it
            content = content.rstrip('\n') + f'\n{key} = {value}\n'
    return content


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=WorldServerInstanceListResponse)
async def list_instances(
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    """Return all configured worldserver instances sorted by sort_order."""
    result = await db.execute(
        select(WorldServerInstance).order_by(
            WorldServerInstance.sort_order, WorldServerInstance.id
        )
    )
    rows = result.scalars().all()
    enriched = [await _enrich(r) for r in rows]
    return WorldServerInstanceListResponse(instances=enriched)


@router.post("", response_model=WorldServerInstanceSchema, status_code=201)
async def create_instance(
    body: WorldServerInstanceCreate,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    """Create a new worldserver instance entry."""
    logger.info("Creating instance: process_name=%s display_name=%s", body.process_name, body.display_name)
    existing = await db.execute(
        select(WorldServerInstance).where(
            WorldServerInstance.process_name == body.process_name
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"An instance with process_name '{body.process_name}' already exists.",
        )

    obj = WorldServerInstance(
        display_name=body.display_name,
        process_name=body.process_name,
        binary_path=body.binary_path,
        working_dir=body.working_dir,
        conf_path=body.conf_path,
        notes=body.notes,
        sort_order=body.sort_order,
        ac_path=body.ac_path,
        build_path=body.build_path,
        char_db_host=body.char_db_host,
        char_db_port=body.char_db_port,
        char_db_user=body.char_db_user,
        char_db_password=body.char_db_password,
        char_db_name=body.char_db_name,
        soap_host=body.soap_host,
        soap_port=body.soap_port,
        soap_user=body.soap_user,
        soap_password=body.soap_password,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return await _enrich(obj)


@router.get("/{instance_id}", response_model=WorldServerInstanceSchema)
async def get_instance(
    instance_id: int,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    obj = await _get_instance_or_404(instance_id, db)
    return await _enrich(obj)


@router.put("/{instance_id}", response_model=WorldServerInstanceSchema)
async def update_instance(
    instance_id: int,
    body: WorldServerInstanceUpdate,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    """Update metadata for an existing instance."""
    obj = await _get_instance_or_404(instance_id, db)

    if body.display_name is not None:
        obj.display_name = body.display_name
    if body.binary_path is not None:
        obj.binary_path = body.binary_path
    if body.working_dir is not None:
        obj.working_dir = body.working_dir
    if body.conf_path is not None:
        obj.conf_path = body.conf_path
    if body.notes is not None:
        obj.notes = body.notes
    if body.sort_order is not None:
        obj.sort_order = body.sort_order
    # Per-instance path overrides
    if body.ac_path is not None:
        obj.ac_path = body.ac_path
    if body.build_path is not None:
        obj.build_path = body.build_path
    # Per-instance characters DB overrides
    if body.char_db_host is not None:
        obj.char_db_host = body.char_db_host
    if body.char_db_port is not None:
        obj.char_db_port = body.char_db_port
    if body.char_db_user is not None:
        obj.char_db_user = body.char_db_user
    if body.char_db_password is not None:
        obj.char_db_password = body.char_db_password
    if body.char_db_name is not None:
        obj.char_db_name = body.char_db_name
    # Per-instance SOAP overrides
    if body.soap_host is not None:
        obj.soap_host = body.soap_host
    if body.soap_port is not None:
        obj.soap_port = body.soap_port
    if body.soap_user is not None:
        obj.soap_user = body.soap_user
    if body.soap_password is not None:
        obj.soap_password = body.soap_password

    await db.commit()
    await db.refresh(obj)
    return await _enrich(obj)


@router.delete("/{instance_id}", response_model=ServerActionResponse)
async def delete_instance(
    instance_id: int,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    """Delete an instance.  If the process is running it will be stopped first."""
    obj = await _get_instance_or_404(instance_id, db)
    logger.info("Deleting instance %d (%s)", instance_id, obj.display_name)
    status = await sm.get_instance_status(obj.process_name)
    if status.running:
        await sm.stop_instance(obj.process_name)

    await db.delete(obj)
    await db.commit()
    return ServerActionResponse(success=True, message=f"Instance '{obj.display_name}' deleted")


# ---------------------------------------------------------------------------
# Process control
# ---------------------------------------------------------------------------

@router.post("/{instance_id}/start", response_model=ServerActionResponse)
async def start_instance(
    instance_id: int,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    obj = await _get_instance_or_404(instance_id, db)
    logger.info("Starting instance %d (%s)", instance_id, obj.process_name)
    ok, msg = await sm.start_instance(
        obj.process_name, obj.binary_path, obj.working_dir, obj.conf_path
    )
    logger.info("start_instance %s → ok=%s msg=%s", obj.process_name, ok, msg)
    return ServerActionResponse(success=ok, message=msg)


@router.post("/{instance_id}/stop", response_model=ServerActionResponse)
async def stop_instance(
    instance_id: int,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    obj = await _get_instance_or_404(instance_id, db)
    logger.info("Stopping instance %d (%s)", instance_id, obj.process_name)
    ok, msg = await sm.stop_instance(obj.process_name)
    logger.info("stop_instance %s → ok=%s msg=%s", obj.process_name, ok, msg)
    return ServerActionResponse(success=ok, message=msg)


@router.post("/{instance_id}/restart", response_model=ServerActionResponse)
async def restart_instance(
    instance_id: int,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    obj = await _get_instance_or_404(instance_id, db)
    ok, msg = await sm.restart_instance(
        obj.process_name, obj.binary_path, obj.working_dir, obj.conf_path
    )
    return ServerActionResponse(success=ok, message=msg)


@router.post("/{instance_id}/command", response_model=SoapCommandResponse)
async def instance_command(
    instance_id: int,
    req: SoapCommandRequest,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    """
    Send a console command to a specific worldserver instance.

    When the instance has ``soap_host`` / ``soap_user`` / ``soap_password``
    configured, the command is sent via that instance's SOAP endpoint.
    Otherwise falls back to the daemon stdin pipe.
    """
    obj = await _get_instance_or_404(instance_id, db)
    logger.info("Instance %d (%s) command: %r", instance_id, obj.process_name, req.command)

    if obj.soap_user and obj.soap_password:
        from app.services.azerothcore.soap_client import execute_command_for_instance
        ok, result = await execute_command_for_instance(req.command, obj.id)
    else:
        ok, result = await sm.send_instance_command(obj.process_name, req.command)

    return SoapCommandResponse(success=ok, result=result)


# ---------------------------------------------------------------------------
# Config file management
# ---------------------------------------------------------------------------

@router.get("/{instance_id}/config")
async def get_instance_config(
    instance_id: int,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    """
    Read the worldserver.conf assigned to this instance.
    Falls back to the global AC_WORLDSERVER_CONF if no conf_path is set.
    """
    obj = await _get_instance_or_404(instance_id, db)

    conf_file = obj.conf_path.strip()
    if not conf_file:
        # Fall back to the panel's global worldserver.conf path
        from app.services.panel_settings import get_settings_dict
        s = await get_settings_dict()
        conf_file = s.get("AC_WORLDSERVER_CONF", "")

    if not conf_file:
        return {"exists": False, "content": "", "path": ""}

    p = Path(conf_file)
    if not p.exists():
        return {"exists": False, "content": "", "path": conf_file}
    return {"exists": True, "content": p.read_text(errors="replace"), "path": conf_file}


@router.put("/{instance_id}/config", response_model=ServerActionResponse)
async def save_instance_config(
    instance_id: int,
    body: dict,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    """Write updated content to the instance's worldserver.conf."""
    obj = await _get_instance_or_404(instance_id, db)

    conf_file = obj.conf_path.strip()
    if not conf_file:
        from app.services.panel_settings import get_settings_dict
        s = await get_settings_dict()
        conf_file = s.get("AC_WORLDSERVER_CONF", "")

    if not conf_file:
        raise HTTPException(
            status_code=400,
            detail="No conf_path set for this instance and no global worldserver.conf configured.",
        )

    p = Path(conf_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.get("content", ""), encoding="utf-8")
    return ServerActionResponse(success=True, message=f"Config saved to {conf_file}")


@router.post("/{instance_id}/generate-config", response_model=ServerActionResponse)
async def generate_instance_config(
    instance_id: int,
    req: WorldServerProvisionRequest,
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_panel_db),
):
    """
    Generate a worldserver.conf for this instance by:
    1. Reading the global worldserver.conf as a template.
    2. Patching ports, realm name, realm ID, etc.
    3. Writing the result to ``req.conf_output_path``.
    4. Updating the instance's ``conf_path`` to point at the new file.
    """
    obj = await _get_instance_or_404(instance_id, db)

    # Read the source / template config
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    src_path = Path(s.get("AC_WORLDSERVER_CONF", ""))
    if not src_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Template worldserver.conf not found at {src_path}. "
                   "Install AzerothCore first or set AC_WORLDSERVER_CONF in Settings.",
        )

    content = src_path.read_text(errors="replace")

    # Derive a unique log directory for this instance so its logs are
    # separated from every other worldserver instance.
    out_stem = Path(req.conf_output_path).stem  # e.g. "worldserver-ptr"
    default_log_dir = str(Path(req.conf_output_path).parent.parent / "logs" / out_stem)

    # Build the patch dict
    overrides: dict[str, str] = {
        "RealmID": str(req.realm_id),
        "RealmName": req.realm_name,
        "WorldServerPort": str(req.worldserver_port),
        "InstanceserverPort": str(req.instance_port),
        "Ra.Port": str(req.ra_port),
        "LogsDir": default_log_dir,
    }
    if req.extra_overrides:
        overrides.update(req.extra_overrides)

    patched = _patch_conf(content, overrides)

    # Write output file
    out_path = Path(req.conf_output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(patched, encoding="utf-8")

    # Update the instance's conf_path in the DB
    obj.conf_path = str(out_path)

    # Auto-configure binary_path and working_dir when not already set.
    # After compilation the build step creates a symlink named process_name
    # (e.g. worldserver-ptr) alongside the worldserver binary.  Point at
    # that symlink so the daemon can uniquely identify this instance's process.
    bin_dir = s.get("AC_BINARY_PATH", "")  # e.g. /opt/azerothcore/bin
    if bin_dir and obj.process_name and obj.process_name != "worldserver":
        expected_binary = str(Path(bin_dir) / obj.process_name)
        if not obj.binary_path:
            obj.binary_path = expected_binary
        if not obj.working_dir:
            obj.working_dir = bin_dir

    await db.commit()

    binary_note = (
        f" Instance binary set to {obj.binary_path}."
        if (bin_dir and obj.process_name and obj.process_name != "worldserver")
        else " Run a compilation targeting this instance to create the named binary."
    )

    return ServerActionResponse(
        success=True,
        message=(
            f"Config generated at {out_path} with "
            f"RealmName={req.realm_name}, "
            f"WorldServerPort={req.worldserver_port}, "
            f"InstanceserverPort={req.instance_port}, "
            f"RealmID={req.realm_id}, "
            f"LogsDir={default_log_dir}."
            f"{binary_note}"
        ),
    )
