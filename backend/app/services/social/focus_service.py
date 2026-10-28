"""Focus Monitor + watchlist service (E73-E83, E136-E139)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.execution import ExecutionJob
from app.models.rules import Recommendation
from app.models.social import FocusMonitor, Watchlist, WatchlistItem
from app.services.social.content_service import content_detail, publication_detail

FOCUS_SCOPE_TYPES = ("ACCOUNT", "CONTENT_ASSET", "PUBLICATION", "PROMOTION", "CAMPAIGN", "AD", "SEARCH_TERM")


async def create_focus(db: AsyncSession, *, workspace_id: str, payload: Dict[str, Any], actor: str) -> FocusMonitor:
    scope_type = (payload.get("scope_type") or "PUBLICATION").upper()
    if scope_type not in FOCUS_SCOPE_TYPES:
        raise ValueError(f"invalid focus scope_type: {scope_type}")
    count = (
        await db.execute(select(FocusMonitor).where(FocusMonitor.workspace_id == workspace_id, FocusMonitor.status == "ACTIVE"))
    ).scalars().all()
    if len(count) >= settings.focus_max_monitors_per_workspace:
        raise ValueError("focus monitor limit reached for workspace")
    monitor = FocusMonitor(
        workspace_id=workspace_id,
        scope_type=scope_type,
        scope_id=payload["scope_id"],
        name=payload.get("name") or f"{scope_type} focus",
        priority=(payload.get("priority") or settings.focus_default_priority).upper(),
        metrics=payload.get("metrics") or _default_metrics(scope_type),
        rules=payload.get("rules"),
        refresh_interval_minutes=payload.get("refresh_interval_minutes", settings.focus_default_refresh_minutes),
        notification_policy=payload.get("notification_policy") or {"alerts": "HIGH", "channels": ["in_app"]},
        baseline_strategy=payload.get("baseline_strategy", "PREVIOUS_PERIOD"),
        started_at=payload.get("started_at") or datetime.now(timezone.utc),
        ends_at=payload.get("ends_at"),
        status="ACTIVE",
        created_by=actor,
    )
    db.add(monitor)
    await db.flush()
    watchlist_id = payload.get("watchlist_id")
    if watchlist_id:
        db.add(
            WatchlistItem(
                watchlist_id=watchlist_id,
                focus_monitor_id=str(monitor.id),
                scope_type=scope_type,
                scope_id=payload["scope_id"],
            )
        )
    await db.flush()
    return monitor


def _default_metrics(scope_type: str) -> List[str]:
    if scope_type in ("PROMOTION", "CAMPAIGN", "AD"):
        return ["paid_spend", "paid_revenue", "roas", "cpa", "purchases"]
    if scope_type == "PUBLICATION":
        return ["views", "likes", "comments", "shares", "paid_spend", "paid_revenue"]
    return ["followers", "views", "engagements", "content_count"]


async def list_focus(db: AsyncSession, workspace_id: str, status: Optional[str] = None) -> List[FocusMonitor]:
    query = select(FocusMonitor).where(FocusMonitor.workspace_id == workspace_id).order_by(FocusMonitor.created_at.desc())
    if status:
        query = query.where(FocusMonitor.status == status)
    return list((await db.execute(query)).scalars().all())


async def get_focus(db: AsyncSession, monitor_id: str) -> Optional[FocusMonitor]:
    return (await db.execute(select(FocusMonitor).where(FocusMonitor.id == monitor_id))).scalar_one_or_none()


async def stop_focus(db: AsyncSession, monitor: FocusMonitor, actor: str) -> FocusMonitor:
    monitor.status = "STOPPED"
    monitor.ends_at = datetime.now(timezone.utc)
    await db.flush()
    return monitor


async def focus_detail(db: AsyncSession, monitor: FocusMonitor, days: int = 7) -> Dict[str, Any]:
    """Focus room: organic + paid + velocity + rule alerts + execution events (E77-E79, E138-E139)."""
    scope = monitor.scope_id
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    organic = {"views": 0, "likes": 0, "comments": 0, "shares": 0}
    paid = {"spend": 0, "revenue": 0, "purchases": 0, "roas": None, "cpa": None}
    if monitor.scope_type == "PUBLICATION":
        detail = await publication_detail(db, scope, days=days)
        organic = detail["organic"]
        paid = detail["paid"]
    elif monitor.scope_type == "CONTENT_ASSET":
        detail = await content_detail(db, scope)
        organic = detail["organic_total"]
        paid = detail["paid_total"]
    recommendations = (
        await db.execute(
            select(Recommendation)
            .where(Recommendation.entity_id == scope, Recommendation.status.in_(("OPEN", "APPROVED")))
            .order_by(Recommendation.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    execution_events = (
        await db.execute(
            select(ExecutionJob)
            .where(ExecutionJob.entity_id == scope, ExecutionJob.created_at >= start)
            .order_by(ExecutionJob.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return {
        "monitor": {
            "id": str(monitor.id),
            "name": monitor.name,
            "scope_type": monitor.scope_type,
            "scope_id": monitor.scope_id,
            "priority": monitor.priority,
            "status": monitor.status,
            "metrics": monitor.metrics,
            "refresh_interval_minutes": monitor.refresh_interval_minutes,
            "baseline_strategy": monitor.baseline_strategy,
        },
        "organic": organic,
        "paid": paid,
        "velocity": {
            "views_per_day": round(organic.get("views", 0) / max(days, 1), 1),
            "spend_per_day": round(paid.get("spend", 0) / max(days, 1), 2),
            "caveat": "velocity is observed rate, not forecast",
        },
        "alerts": [
            {"type": "RULE", "recommendation_id": str(r.id), "primary_action": r.primary_action, "severity": r.severity, "confidence": r.confidence}
            for r in recommendations
        ],
        "execution_events": [
            {"job_id": str(j.id), "status": j.status, "action_type": j.action_type, "error_code": j.error_code, "created_at": j.created_at.isoformat()}
            for j in execution_events
        ],
        "caveat": "Focus reuses PART 03 rules and PART 06 execution guards; it does not reimplement a rule engine (E136)",
    }


async def create_watchlist(db: AsyncSession, *, workspace_id: str, name: str, description: Optional[str], actor: str) -> Watchlist:
    watchlist = Watchlist(workspace_id=workspace_id, name=name, description=description, created_by=actor)
    db.add(watchlist)
    await db.flush()
    return watchlist


async def list_watchlists(db: AsyncSession, workspace_id: str) -> List[Dict[str, Any]]:
    watchlists = (
        await db.execute(select(Watchlist).where(Watchlist.workspace_id == workspace_id).order_by(Watchlist.created_at.desc()))
    ).scalars().all()
    out = []
    for watchlist in watchlists:
        items = (
            await db.execute(select(WatchlistItem).where(WatchlistItem.watchlist_id == str(watchlist.id)))
        ).scalars().all()
        out.append(
            {
                "id": str(watchlist.id),
                "name": watchlist.name,
                "description": watchlist.description,
                "is_default": watchlist.is_default,
                "items": [
                    {"id": str(i.id), "scope_type": i.scope_type, "scope_id": i.scope_id, "focus_monitor_id": i.focus_monitor_id}
                    for i in items
                ],
            }
        )
    return out
