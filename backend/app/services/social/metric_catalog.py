"""Social metric catalog + cross-network aggregation semantics (E20-E22)."""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social import SocialMetricCatalog

METRIC_DEFS = [
    {"metric_key": "followers", "canonical_name": "Followers", "metric_level": "ACCOUNT", "aggregation_type": "NON_ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP"},
    {"metric_key": "follower_growth", "canonical_name": "Follower Growth", "metric_level": "ACCOUNT", "aggregation_type": "SEMI_ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP"},
    {"metric_key": "views", "canonical_name": "Views", "metric_level": "CONTENT", "aggregation_type": "SEMI_ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP", "availability_notes": "provider-reported views are event sums, not unique people"},
    {"metric_key": "reach", "canonical_name": "Reach", "metric_level": "CONTENT", "aggregation_type": "UNIQUE_ESTIMATE", "unit": "count", "comparable_cross_platform": False, "positive_direction": "UP", "availability_notes": "never claim cross-platform unique reach"},
    {"metric_key": "likes", "canonical_name": "Likes", "metric_level": "CONTENT", "aggregation_type": "ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP"},
    {"metric_key": "comments", "canonical_name": "Comments", "metric_level": "CONTENT", "aggregation_type": "ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP"},
    {"metric_key": "shares", "canonical_name": "Shares", "metric_level": "CONTENT", "aggregation_type": "ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP"},
    {"metric_key": "saves", "canonical_name": "Saves", "metric_level": "CONTENT", "aggregation_type": "ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP"},
    {"metric_key": "engagements", "canonical_name": "Engagement Events", "metric_level": "CONTENT", "aggregation_type": "ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP"},
    {"metric_key": "engagement_rate", "canonical_name": "Engagement Rate", "metric_level": "CONTENT", "aggregation_type": "RATE", "unit": "percent", "comparable_cross_platform": False, "positive_direction": "UP", "availability_notes": "do not blindly average cross-platform rates"},
    {"metric_key": "watch_time", "canonical_name": "Watch Time", "metric_level": "CONTENT", "aggregation_type": "ADDITIVE", "unit": "seconds", "comparable_cross_platform": True, "positive_direction": "UP"},
    {"metric_key": "average_watch_time", "canonical_name": "Avg Watch Time", "metric_level": "CONTENT", "aggregation_type": "SEMI_ADDITIVE", "unit": "seconds", "comparable_cross_platform": False, "positive_direction": "UP"},
    {"metric_key": "completion_rate", "canonical_name": "Completion Rate", "metric_level": "CONTENT", "aggregation_type": "RATE", "unit": "percent", "comparable_cross_platform": False, "positive_direction": "UP"},
    {"metric_key": "skip_rate", "canonical_name": "Skip Rate", "metric_level": "CONTENT", "aggregation_type": "PROVIDER_NATIVE_ONLY", "unit": "percent", "comparable_cross_platform": False, "positive_direction": "DOWN"},
    {"metric_key": "profile_visits", "canonical_name": "Profile Visits", "metric_level": "CONTENT", "aggregation_type": "ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP"},
    {"metric_key": "follows", "canonical_name": "Follows", "metric_level": "CONTENT", "aggregation_type": "ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP"},
    {"metric_key": "content_count", "canonical_name": "Published Content", "metric_level": "ACCOUNT", "aggregation_type": "ADDITIVE", "unit": "count", "comparable_cross_platform": True, "positive_direction": "UP"},
]


async def seed_metric_catalog(db: AsyncSession) -> int:
    created = 0
    for definition in METRIC_DEFS:
        existing = (
            await db.execute(
                select(SocialMetricCatalog).where(
                    SocialMetricCatalog.metric_key == definition["metric_key"],
                    SocialMetricCatalog.provider.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(SocialMetricCatalog(**definition, provider=None))
        created += 1
    if created:
        await db.flush()
    return created


async def metric_semantics(db: AsyncSession, metric_key: str) -> Dict[str, Any]:
    row = (
        await db.execute(select(SocialMetricCatalog).where(SocialMetricCatalog.metric_key == metric_key))
    ).scalar_one_or_none()
    if row is None:
        return {"metric_key": metric_key, "aggregation_type": "PROVIDER_NATIVE_ONLY", "comparable_cross_platform": False}
    return {
        "metric_key": row.metric_key,
        "canonical_name": row.canonical_name,
        "aggregation_type": row.aggregation_type,
        "unit": row.unit,
        "comparable_cross_platform": row.comparable_cross_platform,
        "positive_direction": row.positive_direction,
    }


def aggregate_values(values: List[float], semantics: Dict[str, Any], *, rates_denominator: Optional[List[float]] = None) -> Dict[str, Any]:
    """Aggregate metric values according to the catalog semantics (E85/E145)."""
    agg_type = semantics.get("aggregation_type", "PROVIDER_NATIVE_ONLY")
    values = [v for v in values if v is not None]
    if not values:
        return {"value": None, "semantics": agg_type, "caveat": None}
    if agg_type == "RATE":
        if rates_denominator:
            denominator = sum(r for r in rates_denominator if r is not None)
            numerator = sum(v * d for v, d in zip(values, rates_denominator) if v is not None and d is not None)
            value = numerator / denominator if denominator else None
        else:
            value = None
        return {
            "value": value,
            "semantics": agg_type,
            "caveat": "weighted average; rates are not blindly averaged across platforms",
        }
    if agg_type == "NON_ADDITIVE":
        return {
            "value": sum(values),
            "semantics": agg_type,
            "caveat": "combined count shown; this is NOT a deduplicated unique audience",
        }
    if agg_type == "UNIQUE_ESTIMATE":
        return {
            "value": sum(values),
            "semantics": agg_type,
            "caveat": "provider-reported reach summed; NOT unique cross-platform reach",
        }
    if agg_type == "PROVIDER_NATIVE_ONLY":
        return {"value": values[-1] if len(values) == 1 else None, "semantics": agg_type, "caveat": "provider-native metric; not aggregated"}
    return {"value": sum(values), "semantics": agg_type, "caveat": None}
