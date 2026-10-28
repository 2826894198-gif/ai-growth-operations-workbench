from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_sync_service
from app.core.database import get_db
from app.schemas.part02 import SyncJobOut
from app.services.sync_service import SyncService

router = APIRouter()


@router.get("", response_model=List[SyncJobOut])
async def list_sync_jobs(
    data_source_id: Optional[str] = Query(None),
    job_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    service: SyncService = Depends(get_sync_service),
):
    jobs = await service.list_jobs(db, data_source_id=data_source_id, status=job_status, limit=limit)
    return [SyncJobOut.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=SyncJobOut)
async def get_sync_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    service: SyncService = Depends(get_sync_service),
):
    job = await service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="sync job not found")
    return SyncJobOut.model_validate(job)


@router.post("/{job_id}/retry", response_model=SyncJobOut)
async def retry_sync_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    service: SyncService = Depends(get_sync_service),
):
    try:
        job = await service.retry_job(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SyncJobOut.model_validate(job)
