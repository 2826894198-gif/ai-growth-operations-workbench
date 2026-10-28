from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import Notification

router = APIRouter()


@router.get("")
async def list_notifications(
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    if severity:
        query = query.where(Notification.severity == severity)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(r.id),
            "type": r.type,
            "severity": r.severity,
            "title": r.title,
            "body": r.body,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "recommendation_id": r.recommendation_id,
            "read": r.read_at is not None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Notification).where(Notification.id == notification_id))).scalar_one_or_none()
    if row is None:
        return {"error": "not found"}
    from datetime import datetime, timezone

    row.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": notification_id, "read": True}
