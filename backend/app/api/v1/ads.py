from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.ad_performance import AdPerformanceDaily
from app.models.marketing import Ad, AdGroup, Campaign
from app.models.rules import Recommendation, RuleEvaluation

router = APIRouter()


def _window(start_date: Optional[str], end_date: Optional[str], days: int = 7):
    end = date.fromisoformat(end_date) if end_date else date.today()
    start = date.fromisoformat(start_date) if start_date else end - timedelta(days=days - 1)
    return start, end


async def _perf_map(db: AsyncSession, platform: Optional[str], entity_type: str, start: date, end: date):
    query = (
        select(
            AdPerformanceDaily.external_entity_id,
            func.sum(AdPerformanceDaily.spend_amount).label("spend"),
            func.sum(AdPerformanceDaily.impressions).label("impressions"),
            func.sum(AdPerformanceDaily.clicks).label("clicks"),
            func.sum(AdPerformanceDaily.platform_purchases).label("purchases"),
            func.sum(AdPerformanceDaily.platform_conversion_value).label("conversion_value"),
        )
        .where(
            AdPerformanceDaily.entity_type == entity_type,
            AdPerformanceDaily.date >= start,
            AdPerformanceDaily.date <= end,
        )
        .group_by(AdPerformanceDaily.external_entity_id)
    )
    if platform:
        query = query.where(AdPerformanceDaily.platform == platform)
    rows = (await db.execute(query)).all()
    return {str(r.external_entity_id): dict(r._mapping) for r in rows}


async def _rule_status(db: AsyncSession, entity_type: str, entity_id: str) -> dict:
    row = (
        await db.execute(
            select(RuleEvaluation)
            .where(RuleEvaluation.entity_type == entity_type, RuleEvaluation.entity_id == entity_id)
            .order_by(RuleEvaluation.evaluated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return {"rule_result": row.result if row else "UNKNOWN", "rule_key": row.rule_key if row else None}


@router.get("/campaigns")
async def list_campaigns(
    platform: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    start, end = _window(start_date, end_date)
    query = select(Campaign).order_by(Campaign.name.asc())
    if platform:
        query = query.where(Campaign.platform == platform)
    rows = (await db.execute(query)).scalars().all()
    perf = await _perf_map(db, platform, "CAMPAIGN", start, end)
    result = []
    for row in rows:
        p = perf.get(row.external_campaign_id, {})
        spend = float(p.get("spend") or 0)
        purchases = float(p.get("purchases") or 0)
        result.append(
            {
                "id": str(row.id),
                "campaign_id": row.external_campaign_id,
                "name": row.name,
                "platform": row.platform,
                "status": row.status,
                "objective": row.objective,
                "spend": spend,
                "impressions": int(p.get("impressions") or 0),
                "clicks": int(p.get("clicks") or 0),
                "ctr": round(float(p.get("clicks") or 0) / float(p.get("impressions") or 1), 4) if p.get("impressions") else None,
                "conversions": purchases,
                "cpa": round(spend / purchases, 2) if purchases else None,
                "platform_roas": round(float(p.get("conversion_value") or 0) / spend, 2) if spend else None,
                **await _rule_status(db, "CAMPAIGN", row.external_campaign_id),
            }
        )
    return result


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Campaign).where(Campaign.external_campaign_id == campaign_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    start, end = _window(None, None)
    perf = await _perf_map(db, row.platform, "CAMPAIGN", start, end)
    p = perf.get(campaign_id, {})
    recs = (
        await db.execute(
            select(Recommendation)
            .where(Recommendation.entity_type == "CAMPAIGN", Recommendation.entity_id == campaign_id)
            .order_by(Recommendation.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    groups = (
        await db.execute(select(AdGroup).where(AdGroup.campaign_id == row.id).order_by(AdGroup.name.asc()))
    ).scalars().all()
    return {
        "id": str(row.id),
        "campaign_id": campaign_id,
        "name": row.name,
        "platform": row.platform,
        "status": row.status,
        "objective": row.objective,
        "channel_type": row.channel_type,
        "spend": float(p.get("spend") or 0),
        "conversions": float(p.get("purchases") or 0),
        "recommendations": [
            {"id": str(r.id), "primary_action": r.primary_action, "reason_group": r.reason_group, "severity": r.severity, "confidence": r.confidence}
            for r in recs
        ],
        "ad_groups": [{"id": str(g.id), "external_id": g.external_group_id, "name": g.name, "status": g.status} for g in groups],
    }


@router.get("/ad-groups")
async def list_ad_groups(
    campaign_id: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    start, end = _window(start_date, end_date)
    query = select(AdGroup).order_by(AdGroup.name.asc())
    if campaign_id:
        query = query.where(AdGroup.external_group_id == campaign_id)
    if platform:
        query = query.where(AdGroup.platform == platform)
    rows = (await db.execute(query)).scalars().all()
    perf = await _perf_map(db, platform, "AD_GROUP", start, end)
    return [
        {
            "id": str(r.id),
            "ad_group_id": r.external_group_id,
            "name": r.name,
            "platform": r.platform,
            "status": r.status,
            "spend": float((perf.get(r.external_group_id) or {}).get("spend") or 0),
            "conversions": float((perf.get(r.external_group_id) or {}).get("purchases") or 0),
            **await _rule_status(db, "AD_GROUP", r.external_group_id),
        }
        for r in rows
    ]


@router.get("/ads")
async def list_ads(
    campaign_id: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    start, end = _window(start_date, end_date)
    query = select(Ad).order_by(Ad.external_ad_id.asc())
    if campaign_id:
        query = query.where(Ad.external_ad_id == campaign_id)
    if platform:
        query = query.where(Ad.platform == platform)
    rows = (await db.execute(query)).scalars().all()
    perf = await _perf_map(db, platform, "AD", start, end)
    return [
        {
            "id": str(r.id),
            "ad_id": r.external_ad_id,
            "name": r.name,
            "platform": r.platform,
            "status": r.status,
            "creative_id": r.creative_id,
            "spend": float((perf.get(r.external_ad_id) or {}).get("spend") or 0),
            "conversions": float((perf.get(r.external_ad_id) or {}).get("purchases") or 0),
            **await _rule_status(db, "AD", r.external_ad_id),
        }
        for r in rows
    ]
