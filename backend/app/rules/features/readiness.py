from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_source import DataSource


def _ensure_aware(value) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def source_freshness(db: AsyncSession, provider: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    query = select(DataSource)
    if provider:
        query = query.where(DataSource.provider == provider)
    sources = (await db.execute(query)).scalars().all()
    result = {"stale": False, "shopify_stale": False, "minutes": None}
    for source in sources:
        last = _ensure_aware(source.last_successful_sync_at)
        lag_minutes = (now - last).total_seconds() / 60 if last else 99999
        result["minutes"] = min(result["minutes"] or lag_minutes, lag_minutes)
        if lag_minutes > 30:
            result["stale"] = True
        if source.provider == "SHOPIFY" and lag_minutes > 30:
            result["shopify_stale"] = True
    return result


def sample_reliability_score(context_metrics: Dict[str, Any], weights: Dict[str, float]) -> float:
    """Seed 0-100 reliability score from spend/clicks/purchases/age maturity."""
    spend = float(context_metrics.get("spend_7d") or 0)
    clicks = float(context_metrics.get("clicks_7d") or 0)
    purchases = float(context_metrics.get("purchases_7d") or 0)
    age_hours = float(context_metrics.get("entity_age_hours") or 0)
    spend_score = min(100.0, spend / 100.0 * 100.0)
    click_score = min(100.0, clicks / 100.0 * 100.0)
    purchase_score = min(100.0, purchases / 10.0 * 100.0)
    age_score = min(100.0, age_hours / 72.0 * 100.0)
    score = (
        spend_score * weights.get("spend_maturity_pct", 30)
        + click_score * weights.get("click_maturity_pct", 20)
        + purchase_score * weights.get("purchase_maturity_pct", 30)
        + age_score * weights.get("active_duration_pct", 20)
    ) / 100.0
    return round(score, 1)
