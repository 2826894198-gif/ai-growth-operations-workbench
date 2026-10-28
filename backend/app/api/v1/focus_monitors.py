"""Focus Monitor API (E168)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.social.focus_service import (
    create_focus,
    focus_detail,
    get_focus,
    list_focus,
    stop_focus,
)

router = APIRouter()


class FocusCreate(BaseModel):
    workspace_id: str
    scope_type: str
    scope_id: str
    name: Optional[str] = None
    priority: str = "NORMAL"
    metrics: Optional[list] = None
    rules: Optional[dict] = None
    refresh_interval_minutes: int = 15
    baseline_strategy: str = "PREVIOUS_PERIOD"
    watchlist_id: Optional[str] = None
    actor: str = "operator"


class FocusAction(BaseModel):
    actor: str = "operator"


def _focus_dict(monitor) -> dict:
    return {
        "id": str(monitor.id),
        "workspace_id": monitor.workspace_id,
        "scope_type": monitor.scope_type,
        "scope_id": monitor.scope_id,
        "name": monitor.name,
        "priority": monitor.priority,
        "metrics": monitor.metrics,
        "refresh_interval_minutes": monitor.refresh_interval_minutes,
        "baseline_strategy": monitor.baseline_strategy,
        "status": monitor.status,
        "created_by": monitor.created_by,
        "created_at": monitor.created_at.isoformat() if monitor.created_at else None,
    }


@router.get("")
async def list_focus_monitors(workspace_id: str = Query(...), status: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    monitors = await list_focus(db, workspace_id, status=status)
    return [_focus_dict(m) for m in monitors]


@router.post("")
async def create_focus_monitor(data: FocusCreate, db: AsyncSession = Depends(get_db)):
    try:
        monitor = await create_focus(db, workspace_id=data.workspace_id, payload=data.model_dump(exclude_none=True), actor=data.actor)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _focus_dict(monitor)


@router.get("/{monitor_id}")
async def get_focus_monitor(monitor_id: str, days: int = Query(7, ge=1, le=90), db: AsyncSession = Depends(get_db)):
    monitor = await get_focus(db, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="focus monitor not found")
    return await focus_detail(db, monitor, days=days)


@router.post("/{monitor_id}/stop")
async def stop_focus_monitor(monitor_id: str, data: FocusAction = None, db: AsyncSession = Depends(get_db)):
    monitor = await get_focus(db, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="focus monitor not found")
    monitor = await stop_focus(db, monitor, data.actor if data else "operator")
    await db.commit()
    return _focus_dict(monitor)


@router.get("/watchlists/list")
async def watchlists(workspace_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    from app.services.social.focus_service import list_watchlists

    return await list_watchlists(db, workspace_id)
