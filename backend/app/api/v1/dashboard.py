from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_dashboard_service
from app.core.database import get_db
from app.services.dashboard_service import DashboardService, metric_metadata

router = APIRouter()


@router.get("/overview")
async def dashboard_overview(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    compare: str = Query("PREVIOUS_PERIOD"),
    timezone: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    service: DashboardService = Depends(get_dashboard_service),
):
    return await service.overview(db, start_date=start_date, end_date=end_date, compare=compare)


@router.get("/live")
async def dashboard_live(
    db: AsyncSession = Depends(get_db),
    service: DashboardService = Depends(get_dashboard_service),
):
    return await service.live(db)


@router.get("/metric-metadata")
async def dashboard_metric_metadata():
    return await metric_metadata()
