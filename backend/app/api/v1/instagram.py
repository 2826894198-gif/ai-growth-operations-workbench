"""Read-only Instagram Growth Intelligence V1 contract endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.instagram.demo_service import demo_content, demo_overview, load_demo_fixture
from app.services.instagram.live_read_model import (
    InstagramLiveReadError,
    live_capabilities,
    live_content,
    live_overview,
    live_readiness,
)
from app.services.instagram.live_sync import InstagramLiveSyncError, sync_instagram_connection

router = APIRouter()


class InstagramSyncRequest(BaseModel):
    connection_id: str = Field(min_length=1)
    workspace_id: str = Field(default="ws_main", min_length=1)
    days: int = Field(default=28, ge=7, le=90)
    actor: str = Field(default="operator", min_length=1, max_length=128)


def _live_read_error(exc: InstagramLiveReadError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


def _require_live_read_mode() -> None:
    if not settings.instagram_sync_enabled or settings.social_provider_mode != "live":
        raise HTTPException(
            status_code=503,
            detail="Instagram Live mode is not enabled; keep the explicit DEMO source active until preflight passes",
        )


@router.get("/overview")
async def instagram_overview(
    workspace_id: str = Query("ws_main"),
    days: int = Query(28, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
):
    if settings.instagram_demo_mode:
        return demo_overview(workspace_id=workspace_id, days=days)
    _require_live_read_mode()
    try:
        return await live_overview(db, workspace_id=workspace_id, days=days)
    except InstagramLiveReadError as exc:
        raise _live_read_error(exc) from exc


@router.get("/capabilities")
async def instagram_capabilities(
    workspace_id: str = Query("ws_main"), db: AsyncSession = Depends(get_db)
):
    if settings.instagram_demo_mode:
        fixture = load_demo_fixture()
        return {
            "workspace_id": workspace_id,
            "source": {
                "mode": fixture.source_mode.value,
                "is_live": False,
                "fixture_version": fixture.fixture_version,
            },
            "items": [
                {**capability.model_dump(mode="json"), "scope_key": capability.scope_key}
                for capability in fixture.capabilities
            ],
        }
    _require_live_read_mode()
    try:
        return await live_capabilities(db, workspace_id=workspace_id)
    except InstagramLiveReadError as exc:
        raise _live_read_error(exc) from exc


@router.get("/content")
async def instagram_content(
    workspace_id: str = Query("ws_main"),
    media_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if settings.instagram_demo_mode:
        return demo_content(workspace_id=workspace_id, media_type=media_type)
    _require_live_read_mode()
    try:
        return await live_content(db, workspace_id=workspace_id, media_type=media_type)
    except InstagramLiveReadError as exc:
        raise _live_read_error(exc) from exc


@router.get("/readiness")
async def instagram_readiness(
    workspace_id: str = Query("ws_main"), db: AsyncSession = Depends(get_db)
):
    return await live_readiness(db, workspace_id=workspace_id)


@router.post("/sync")
async def instagram_sync(data: InstagramSyncRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await sync_instagram_connection(
            db,
            workspace_id=data.workspace_id,
            connection_id=data.connection_id,
            days=data.days,
            actor=data.actor,
        )
        await db.commit()
        return result
    except InstagramLiveSyncError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
