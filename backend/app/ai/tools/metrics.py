from datetime import date
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketing import Ad
from app.rules.features.funnel import load_funnel_features
from app.rules.features.marketing import load_marketing_features
from app.services.metrics_service import MetricsService


async def _entity_features(db: AsyncSession, platform: str, entity_type: str, entity_id: str, days: int = 7) -> Dict[str, Any]:
    features = await load_marketing_features(db, platform, entity_type, [entity_id], date.today(), days)
    return features.get(entity_id, {})


async def get_growth_overview(db: AsyncSession, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    return await MetricsService().overview(db, start_date, end_date)


async def get_platform_performance(db: AsyncSession, platform: Optional[str] = None) -> Dict[str, Any]:
    platforms = await MetricsService().platforms(db)
    if platform:
        platforms = [p for p in platforms if p["platform"] == platform]
    return {"platforms": platforms}


async def get_campaign_performance(db: AsyncSession, campaign_id: str = None, entity_id: str = None) -> Dict[str, Any]:
    entity = entity_id or campaign_id
    if not entity:
        return {"campaigns": await MetricsService().campaigns(db)}
    features = await _entity_features(db, "META_ADS", "CAMPAIGN", entity)
    return {"campaign_id": entity, "features": features, "_output_ref": f"metric://campaign/{entity}"}


async def get_ad_group_performance(db: AsyncSession, entity_id: str) -> Dict[str, Any]:
    features = await _entity_features(db, "META_ADS", "AD_GROUP", entity_id)
    return {"ad_group_id": entity_id, "features": features, "_output_ref": f"metric://ad-group/{entity_id}"}


async def get_ad_performance(db: AsyncSession, entity_id: str) -> Dict[str, Any]:
    features = await _entity_features(db, "META_ADS", "AD", entity_id)
    return {"ad_id": entity_id, "features": features, "_output_ref": f"metric://ad/{entity_id}"}


async def get_creative_performance(db: AsyncSession, creative_id: str) -> Dict[str, Any]:
    ad_ids = list(
        (await db.execute(select(Ad.external_ad_id).where(Ad.creative_id == creative_id))).scalars().all()
    )
    features = await load_marketing_features(db, "META_ADS", "AD", ad_ids, date.today(), 14)
    return {"creative_id": creative_id, "ads": ad_ids, "features": features, "_output_ref": f"metric://creative/{creative_id}"}


async def get_funnel_performance(db: AsyncSession, entity_type: str = "AD", entity_id: str = None) -> Dict[str, Any]:
    if not entity_id:
        return {"funnel": "provide entity_id"}
    funnel = await load_funnel_features(db, entity_type, [entity_id], date.today())
    return {"entity_id": entity_id, "funnel": funnel.get(entity_id, {})}


async def get_metric_baseline(db: AsyncSession, metric: str = "spend", entity_type: str = "CAMPAIGN", entity_id: str = None, days: int = 14) -> Dict[str, Any]:
    if not entity_id:
        return {"baseline": None}
    features = await _entity_features(db, "META_ADS", entity_type, entity_id, days)
    return {"metric": metric, "baseline_features": features}
