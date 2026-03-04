"""
Backup & Restore endpoints.

Destinations (CRUD):
  GET    /backup/destinations                – list all destinations
  POST   /backup/destinations                – create destination
  GET    /backup/destinations/{id}           – get destination
  PUT    /backup/destinations/{id}           – update destination
  DELETE /backup/destinations/{id}           – delete destination
  POST   /backup/destinations/{id}/test      – test connection

Jobs:
  GET    /backup/jobs                        – list all jobs (paged)
  GET    /backup/jobs/{id}                   – get job details
  DELETE /backup/jobs/{id}                   – delete job record
  GET    /backup/jobs/{id}/files             – list files from destination for this job's dest
  DELETE /backup/jobs/{id}/files/{filename}  – delete a remote file

Operations:
  POST   /backup/run                         – start a backup (SSE streaming)
  POST   /backup/restore                     – restore from a backup (SSE streaming)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.database import PanelSessionLocal, get_panel_db
from app.core.security import get_current_user
from app.models.panel_models import BackupDestination, BackupJob, WorldServerInstance
from app.models.schemas import (
    BackupDestinationCreate,
    BackupDestinationSchema,
    BackupDestinationUpdate,
    BackupJobCreate,
    BackupJobSchema,
    RestoreRequest,
)
from app.services.panel_settings import get_settings_dict
from app.services.backup.backup_manager import (
    run_backup_stream,
    run_restore_stream,
    test_destination_sync,
    list_destination_files_sync,
    delete_destination_file_sync,
    _now_ts,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backup", tags=["Backup"])


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

async def _get_dest_or_404(dest_id: int) -> BackupDestination:
    async with PanelSessionLocal() as db:
        result = await db.execute(
            select(BackupDestination).where(BackupDestination.id == dest_id)
        )
        dest = result.scalar_one_or_none()
    if dest is None:
        raise HTTPException(status_code=404, detail=f"Destination {dest_id} not found")
    return dest


async def _get_job_or_404(job_id: int) -> BackupJob:
    async with PanelSessionLocal() as db:
        result = await db.execute(
            select(BackupJob).where(BackupJob.id == job_id)
        )
        job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


def _dest_to_schema(dest: BackupDestination) -> BackupDestinationSchema:
    cfg = json.loads(dest.config) if dest.config else {}
    return BackupDestinationSchema(
        id=dest.id,
        name=dest.name,
        type=dest.type,
        config=cfg,
        enabled=dest.enabled,
        created_at=dest.created_at,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Destination CRUD
# ──────────────────────────────────────────────────────────────────────────────

VALID_TYPES = {"local", "sftp", "ftp", "s3", "gdrive", "onedrive"}


@router.get("/destinations")
async def list_destinations(_: dict = Depends(get_current_user)):
    async with PanelSessionLocal() as db:
        result = await db.execute(select(BackupDestination).order_by(BackupDestination.id))
        dests = result.scalars().all()
    return [_dest_to_schema(d) for d in dests]


@router.post("/destinations", status_code=201)
async def create_destination(
    body: BackupDestinationCreate,
    _: dict = Depends(get_current_user),
):
    if body.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {sorted(VALID_TYPES)}")
    dest = BackupDestination(
        name=body.name,
        type=body.type,
        config=json.dumps(body.config),
        enabled=body.enabled,
        created_at=_now_ts(),
    )
    async with PanelSessionLocal() as db:
        db.add(dest)
        await db.commit()
        await db.refresh(dest)
    return _dest_to_schema(dest)


@router.get("/destinations/{dest_id}")
async def get_destination(dest_id: int, _: dict = Depends(get_current_user)):
    dest = await _get_dest_or_404(dest_id)
    return _dest_to_schema(dest)


@router.put("/destinations/{dest_id}")
async def update_destination(
    dest_id: int,
    body: BackupDestinationUpdate,
    _: dict = Depends(get_current_user),
):
    dest = await _get_dest_or_404(dest_id)
    if body.type is not None and body.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {sorted(VALID_TYPES)}")
    async with PanelSessionLocal() as db:
        result = await db.execute(select(BackupDestination).where(BackupDestination.id == dest_id))
        dest = result.scalar_one_or_none()
        if dest is None:
            raise HTTPException(status_code=404)
        if body.name is not None:
            dest.name = body.name
        if body.type is not None:
            dest.type = body.type
        if body.config is not None:
            dest.config = json.dumps(body.config)
        if body.enabled is not None:
            dest.enabled = body.enabled
        await db.commit()
        await db.refresh(dest)
    return _dest_to_schema(dest)


@router.delete("/destinations/{dest_id}", status_code=204)
async def delete_destination(dest_id: int, _: dict = Depends(get_current_user)):
    async with PanelSessionLocal() as db:
        result = await db.execute(select(BackupDestination).where(BackupDestination.id == dest_id))
        dest = result.scalar_one_or_none()
        if dest is None:
            raise HTTPException(status_code=404)
        await db.delete(dest)
        await db.commit()


@router.post("/destinations/{dest_id}/test")
async def test_destination(dest_id: int, _: dict = Depends(get_current_user)):
    dest = await _get_dest_or_404(dest_id)
    cfg = json.loads(dest.config) if dest.config else {}
    import asyncio
    ok, msg = await asyncio.get_event_loop().run_in_executor(
        None, test_destination_sync, dest.type, cfg
    )
    return {"success": ok, "message": msg}


# ──────────────────────────────────────────────────────────────────────────────
# Job management
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    _: dict = Depends(get_current_user),
):
    async with PanelSessionLocal() as db:
        result = await db.execute(
            select(BackupJob).order_by(BackupJob.id.desc()).limit(limit).offset(offset)
        )
        jobs = result.scalars().all()
    return [BackupJobSchema.model_validate(j) for j in jobs]


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, _: dict = Depends(get_current_user)):
    job = await _get_job_or_404(job_id)
    return BackupJobSchema.model_validate(job)


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: int, _: dict = Depends(get_current_user)):
    async with PanelSessionLocal() as db:
        result = await db.execute(select(BackupJob).where(BackupJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            raise HTTPException(status_code=404)
        await db.delete(job)
        await db.commit()


@router.get("/jobs/{job_id}/files")
async def list_job_destination_files(job_id: int, _: dict = Depends(get_current_user)):
    """List all .tar.gz files at the destination associated with this job."""
    job = await _get_job_or_404(job_id)
    if job.destination_id is None:
        # Local – list local path parent directory
        import os
        from pathlib import Path
        parent = Path(job.local_path).parent if job.local_path else None
        if parent and parent.exists():
            files = []
            for p in sorted(parent.glob("*.tar.gz"), reverse=True):
                files.append({
                    "filename": p.name,
                    "size_bytes": p.stat().st_size,
                    "modified": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
                })
            return files
        return []
    dest = await _get_dest_or_404(job.destination_id)
    cfg = json.loads(dest.config) if dest.config else {}
    import asyncio
    files = await asyncio.get_event_loop().run_in_executor(
        None, list_destination_files_sync, dest.type, cfg
    )
    return files


@router.delete("/jobs/{job_id}/files/{filename}", status_code=204)
async def delete_job_file(
    job_id: int,
    filename: str,
    _: dict = Depends(get_current_user),
):
    """Delete a specific backup file from its destination."""
    job = await _get_job_or_404(job_id)
    if job.destination_id is None:
        from pathlib import Path
        parent = Path(job.local_path).parent if job.local_path else None
        if parent:
            target = parent / filename
            if target.exists():
                target.unlink()
        return
    dest = await _get_dest_or_404(job.destination_id)
    cfg = json.loads(dest.config) if dest.config else {}
    import asyncio
    await asyncio.get_event_loop().run_in_executor(
        None, delete_destination_file_sync, dest.type, cfg, filename
    )


# ──────────────────────────────────────────────────────────────────────────────
# Run backup (SSE)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/run")
async def run_backup(
    body: BackupJobCreate,
    _: dict = Depends(get_current_user),
):
    """
    Start a backup job.  Returns a streaming SSE response with progress lines.
    The last event will be ``{"done": true}`` or ``{"error": "..."}``
    """
    # Resolve destination
    dest_type: str | None = None
    dest_config: dict = {}

    if body.destination_id is not None:
        dest = await _get_dest_or_404(body.destination_id)
        dest_type = dest.type
        dest_config = json.loads(dest.config) if dest.config else {}
    else:
        # Default local storage
        dest_type = "local"
        dest_config = {}

    settings = await get_settings_dict()

    # Collect per-instance conf files (secondary worldservers with custom conf_path)
    instance_conf_files: list[tuple[str, str]] = []
    async with PanelSessionLocal() as db:
        result = await db.execute(
            select(WorldServerInstance).where(WorldServerInstance.conf_path != "")
        )
        for inst in result.scalars().all():
            instance_conf_files.append((inst.display_name, inst.conf_path))

    # Create job record
    job = BackupJob(
        destination_id=body.destination_id,
        status="running",
        include_configs=body.include_configs,
        include_databases=body.include_databases,
        include_server_files=body.include_server_files,
        notes=body.notes,
        started_at=_now_ts(),
    )
    async with PanelSessionLocal() as db:
        db.add(job)
        await db.commit()
        await db.refresh(job)
    job_id = job.id

    async def event_stream():
        async for event_type, message in run_backup_stream(
            job_id=job_id,
            dest_type=dest_type,
            dest_config=dest_config,
            include_configs=body.include_configs,
            include_databases=body.include_databases,
            include_server_files=body.include_server_files,
            settings=settings,
            instance_conf_files=instance_conf_files,
        ):
            if event_type == "log":
                yield f"data: {json.dumps({'line': message})}\n\n"
            elif event_type == "result":
                result_data = json.loads(message)
                # Update job record
                async with PanelSessionLocal() as db:
                    result = await db.execute(select(BackupJob).where(BackupJob.id == job_id))
                    j = result.scalar_one_or_none()
                    if j:
                        j.status = "completed"
                        j.filename = result_data["filename"]
                        j.local_path = result_data["local_path"]
                        j.size_bytes = result_data["size_bytes"]
                        j.completed_at = _now_ts()
                        await db.commit()
                yield f"data: {json.dumps({'done': True, 'job_id': job_id, **result_data})}\n\n"
            elif event_type == "error":
                async with PanelSessionLocal() as db:
                    result = await db.execute(select(BackupJob).where(BackupJob.id == job_id))
                    j = result.scalar_one_or_none()
                    if j:
                        j.status = "failed"
                        j.error = message
                        j.completed_at = _now_ts()
                        await db.commit()
                yield f"data: {json.dumps({'error': message, 'job_id': job_id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Restore (SSE)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/restore")
async def restore_backup(
    body: RestoreRequest,
    _: dict = Depends(get_current_user),
):
    """
    Restore from a completed backup job.  Returns a streaming SSE response.
    """
    job = await _get_job_or_404(body.job_id)
    if job.status not in ("completed",):
        raise HTTPException(status_code=400, detail=f"Job {body.job_id} is not in 'completed' state")

    dest_type: str | None = None
    dest_config: dict = {}
    if job.destination_id is not None:
        dest = await _get_dest_or_404(job.destination_id)
        dest_type = dest.type
        dest_config = json.loads(dest.config) if dest.config else {}

    settings = await get_settings_dict()

    # Collect per-instance conf files for restore
    instance_conf_files: list[tuple[str, str]] = []
    async with PanelSessionLocal() as db:
        result = await db.execute(
            select(WorldServerInstance).where(WorldServerInstance.conf_path != "")
        )
        for inst in result.scalars().all():
            instance_conf_files.append((inst.display_name, inst.conf_path))

    async def event_stream():
        async for event_type, message in run_restore_stream(
            filename=job.filename,
            local_path=job.local_path,
            dest_type=dest_type,
            dest_config=dest_config,
            restore_configs=body.restore_configs,
            restore_databases=body.restore_databases,
            restore_server_files=body.restore_server_files,
            settings=settings,
            instance_conf_files=instance_conf_files,
        ):
            if event_type == "log":
                yield f"data: {json.dumps({'line': message})}\n\n"
            elif event_type == "result":
                yield f"data: {json.dumps({'done': True})}\n\n"
            elif event_type == "error":
                yield f"data: {json.dumps({'error': message})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# List files for a specific destination (not tied to a job)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/destinations/{dest_id}/files")
async def list_destination_files(dest_id: int, _: dict = Depends(get_current_user)):
    """List all backup archives in the given destination."""
    dest = await _get_dest_or_404(dest_id)
    cfg = json.loads(dest.config) if dest.config else {}
    import asyncio
    try:
        files = await asyncio.get_event_loop().run_in_executor(
            None, list_destination_files_sync, dest.type, cfg
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return files
