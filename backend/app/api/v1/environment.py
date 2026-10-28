from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_environment_health_service
from app.core.database import get_db
from app.schemas.environment import AlertOut, EnvironmentOverviewOut
from app.services.environment_health_service import EnvironmentHealthService

router = APIRouter()


@router.get("/overview", response_model=EnvironmentOverviewOut)
async def overview(
    db: AsyncSession = Depends(get_db),
    service: EnvironmentHealthService = Depends(get_environment_health_service),
):
    return await service.overview(db)


@router.get("/alerts", response_model=List[AlertOut])
async def alerts(
    db: AsyncSession = Depends(get_db),
    service: EnvironmentHealthService = Depends(get_environment_health_service),
):
    return await service.alerts(db)
