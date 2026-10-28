from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_data_source_service
from app.core.database import get_db
from app.schemas.part02 import DataSourceCreate, DataSourceOut
from app.services.data_source_service import DataSourceService

router = APIRouter()


@router.get("", response_model=List[DataSourceOut])
async def list_data_sources(
    workspace_id: str = Query("ws_main"),
    provider: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    service: DataSourceService = Depends(get_data_source_service),
):
    return [
        DataSourceOut.model_validate(s)
        for s in await service.list_sources(db, provider=provider, workspace_id=workspace_id)
    ]


@router.post("", response_model=DataSourceOut, status_code=status.HTTP_201_CREATED)
async def create_data_source(
    data: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    service: DataSourceService = Depends(get_data_source_service),
):
    source = await service.create_source(
        db,
        workspace_id=data.workspace_id,
        provider=data.provider,
        name=data.name,
        external_account_id=data.external_account_id,
        external_account_name=data.external_account_name,
        credential_reference=data.credential_reference,
        api_version=data.api_version,
        timezone=data.timezone,
        currency=data.currency,
        metadata=data.metadata,
    )
    return DataSourceOut.model_validate(source)


@router.get("/{source_id}", response_model=DataSourceOut)
async def get_data_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    service: DataSourceService = Depends(get_data_source_service),
):
    source = await service.get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="data source not found")
    return DataSourceOut.model_validate(source)


@router.post("/{source_id}/validate")
async def validate_data_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    service: DataSourceService = Depends(get_data_source_service),
):
    try:
        return await service.validate(db, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{source_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_data_source(
    source_id: str,
    job_type: str = Query("PERFORMANCE_INTRADAY", pattern="^(PERFORMANCE_INTRADAY|PERFORMANCE_RECONCILE|DIMENSION_SYNC|SHOPIFY_ORDER_RECONCILE)$"),
    days: Optional[int] = Query(None, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    service: DataSourceService = Depends(get_data_source_service),
):
    source = await service.get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="data source not found")
    service.enqueue_sync(source, job_type, days)
    return {"queued": True, "provider": source.provider, "job_type": job_type}


@router.post("/{source_id}/backfill", status_code=status.HTTP_202_ACCEPTED)
async def backfill_data_source(
    source_id: str,
    days: Optional[int] = Query(None, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    service: DataSourceService = Depends(get_data_source_service),
):
    source = await service.get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="data source not found")
    service.enqueue_backfill(source, days)
    return {"queued": True, "provider": source.provider, "job_type": "INITIAL_BACKFILL", "days": days}
