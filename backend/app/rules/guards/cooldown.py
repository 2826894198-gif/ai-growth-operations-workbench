from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rules import Recommendation


async def check_cooldown(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
    action: str,
    reason_group: str,
    cooldown_minutes: int,
    severity: str,
    ignore: bool = False,
) -> tuple:
    if cooldown_minutes <= 0 or ignore:
        return True, None
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
    existing = (
        await db.execute(
            select(Recommendation).where(
                Recommendation.entity_type == entity_type,
                Recommendation.entity_id == entity_id,
                Recommendation.primary_action == action,
                Recommendation.reason_group == reason_group,
                Recommendation.created_at >= cutoff,
                Recommendation.status.in_(["OPEN", "ACKNOWLEDGED"]),
            )
        )
    ).scalars().all()
    if not existing:
        return True, None
    # Escalation breaks cooldown when severity increased.
    severity_rank = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    for rec in existing:
        if severity_rank.get(severity, 2) > severity_rank.get(rec.severity, 2):
            return True, "ESCALATION"
    return False, "COOLDOWN"
