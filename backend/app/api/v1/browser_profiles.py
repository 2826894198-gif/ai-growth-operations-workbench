from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_adspower_browser_service,
    get_browser_profile_service,
    get_browser_task_service,
)
from app.core.database import get_db
from app.integrations.adspower.browser_service import AdsPowerBrowserService
from app.integrations.adspower.exceptions import AdsPowerError
from app.models.environment_health import EnvironmentHealthCheck
from app.schemas.browser_profile import (
    BrowserProfileCreate,
    BrowserProfileOut,
    BrowserProfileStatusOut,
    BrowserProfileUpdate,
    ProfileDetailOut,
)
from app.schemas.browser_task import BrowserTaskOut
from app.services.browser_profile_service import BrowserProfileService
from app.services.browser_task_service import BrowserTaskService

router = APIRouter()


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")


def _serialize_orm(obj) -> dict:
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}


@router.get("", response_model=List[BrowserProfileOut])
async def list_profiles(
    profile_type: Optional[str] = Query(None),
    profile_status: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    service: BrowserProfileService = Depends(get_browser_profile_service),
):
    profiles = await service.list_profiles(db, profile_type=profile_type, status=profile_status)
    items = []
    for profile in profiles:
        out = BrowserProfileOut.model_validate(profile)
        latest = (
            await db.execute(
                select(EnvironmentHealthCheck)
                .where(EnvironmentHealthCheck.profile_id == profile.id)
                .order_by(desc(EnvironmentHealthCheck.created_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        out.health = latest.status if latest else "UNKNOWN"
        items.append(out)
    return items


@router.get("/{profile_id}", response_model=ProfileDetailOut)
async def get_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    service: BrowserProfileService = Depends(get_browser_profile_service),
):
    detail = await service.detail(db, profile_id)
    if detail is None:
        raise _not_found()
    return ProfileDetailOut(
        **BrowserProfileOut.model_validate(detail["profile"]).model_dump(),
        audits=[_serialize_orm(a) for a in detail["audits"]],
        health_checks=[_serialize_orm(c) for c in detail["health_checks"]],
        recent_tasks=[_serialize_orm(t) for t in detail["recent_tasks"]],
    )


@router.post("", response_model=BrowserProfileOut, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: BrowserProfileCreate,
    db: AsyncSession = Depends(get_db),
    service: BrowserProfileService = Depends(get_browser_profile_service),
):
    try:
        profile = await service.create_profile(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except AdsPowerError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return BrowserProfileOut.model_validate(profile)


@router.patch("/{profile_id}", response_model=BrowserProfileOut)
async def update_profile(
    profile_id: str,
    data: BrowserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    service: BrowserProfileService = Depends(get_browser_profile_service),
):
    profile = await service.get_profile(db, profile_id)
    if profile is None:
        raise _not_found()
    profile = await service.update_profile(db, profile, data)
    return BrowserProfileOut.model_validate(profile)


@router.post("/{profile_id}/sync")
async def sync_profiles(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    service: BrowserProfileService = Depends(get_browser_profile_service),
):
    if await service.get_profile(db, profile_id) is None:
        raise _not_found()
    synced = await service.sync(db)
    return {"synced": synced}


@router.post("/{profile_id}/health-check", response_model=BrowserTaskOut, status_code=status.HTTP_202_ACCEPTED)
async def health_check_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    profile_service: BrowserProfileService = Depends(get_browser_profile_service),
    task_service: BrowserTaskService = Depends(get_browser_task_service),
):
    if await profile_service.get_profile(db, profile_id) is None:
        raise _not_found()
    from app.schemas.browser_task import BrowserTaskCreate

    task = await task_service.create_task(db, BrowserTaskCreate(profile_id=profile_id, task_type="environment_check"))
    return BrowserTaskOut.model_validate(task)


@router.post("/{profile_id}/open")
async def open_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    profile_service: BrowserProfileService = Depends(get_browser_profile_service),
    browser_service: AdsPowerBrowserService = Depends(get_adspower_browser_service),
):
    profile = await profile_service.get_profile(db, profile_id)
    if profile is None:
        raise _not_found()
    try:
        data = await browser_service.start(db, profile)
    except AdsPowerError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"status": "RUNNING", "debug_port": data.debug_port, "webdriver": data.webdriver}


@router.post("/{profile_id}/close")
async def close_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    profile_service: BrowserProfileService = Depends(get_browser_profile_service),
    browser_service: AdsPowerBrowserService = Depends(get_adspower_browser_service),
):
    profile = await profile_service.get_profile(db, profile_id)
    if profile is None:
        raise _not_found()
    try:
        await browser_service.stop(db, profile)
    except AdsPowerError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"status": "INACTIVE"}


@router.get("/{profile_id}/status", response_model=BrowserProfileStatusOut)
async def profile_status(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    service: BrowserProfileService = Depends(get_browser_profile_service),
):
    profile = await service.get_profile(db, profile_id)
    if profile is None:
        raise _not_found()
    running = profile.status == "RUNNING"
    return BrowserProfileStatusOut(
        id=profile.id,
        name=profile.name,
        status=profile.status,
        running=running,
        provider_profile_id=profile.provider_profile_id,
        last_opened_at=profile.last_opened_at,
        last_closed_at=profile.last_closed_at,
    )
