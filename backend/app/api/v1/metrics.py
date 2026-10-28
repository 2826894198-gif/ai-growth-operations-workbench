from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_metrics_service
from app.core.database import get_db
from app.services.metrics_service import MetricsService

router = APIRouter()


@router.get("/overview")
async def metrics_overview(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    timezone: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    service: MetricsService = Depends(get_metrics_service),
):
    return await service.overview(db, start_date, end_date, timezone, currency)


@router.get("/platforms")
async def metrics_platforms(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    timezone: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    service: MetricsService = Depends(get_metrics_service),
):
    return await service.platforms(db, start_date, end_date, timezone, currency)


@router.get("/campaigns")
async def metrics_campaigns(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    timezone: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    service: MetricsService = Depends(get_metrics_service),
):
    return await service.campaigns(db, start_date, end_date, timezone, currency, limit=limit)


@router.get("/commerce")
async def metrics_commerce(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    timezone: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    service: MetricsService = Depends(get_metrics_service),
):
    return await service.commerce(db, start_date, end_date, timezone, currency)
