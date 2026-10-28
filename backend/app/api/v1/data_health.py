from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_data_health_service
from app.core.database import get_db
from app.services.data_health_service import DataHealthService

router = APIRouter()


@router.get("/freshness")
async def data_freshness(
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
    service: DataHealthService = Depends(get_data_health_service),
):
    return {
        "workspace_id": workspace_id,
        "sources": await service.freshness(db, workspace_id=workspace_id),
        "webhooks": await service.webhook_lag(db, workspace_id=workspace_id),
    }


@router.get("/quality")
async def data_quality(
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
    service: DataHealthService = Depends(get_data_health_service),
):
    return await service.quality(db, workspace_id=workspace_id)


@router.get("/jobs")
async def recent_jobs(
    workspace_id: str = Query("ws_main"),
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    service: DataHealthService = Depends(get_data_health_service),
):
    return await service.recent_jobs(db, limit=limit, workspace_id=workspace_id)
