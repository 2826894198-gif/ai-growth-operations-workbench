from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.ad_performance import AdPerformanceDaily
from app.models.ai import CreativeAIAnalysis
from app.models.marketing import Ad, Creative
from app.models.product import CreativeBrief

router = APIRouter()


class BriefCreate(BaseModel):
    title: str
    objective: Optional[str] = None
    audience: Optional[str] = None
    hypothesis: Optional[str] = None
    hook: Optional[str] = None
    first_3_seconds: Optional[str] = None
    scene_sequence: Optional[list] = None
    product_actions: Optional[list] = None
    proof: Optional[list] = None
    cta: Optional[str] = None
    audio_direction: Optional[str] = None
    duration: Optional[str] = None
    aspect_ratio: Optional[str] = None
    avoid: Optional[list] = None
    measurement_plan: Optional[str] = None


async def _perf(db: AsyncSession, creative_id: str, days: int = 14):
    ad_ids = list((await db.execute(select(Ad.external_ad_id).where(Ad.creative_id == creative_id))).scalars().all())
    if not ad_ids:
        return {}
    start = date.today() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(
                AdPerformanceDaily.date,
                func.sum(AdPerformanceDaily.spend_amount).label("spend"),
                func.sum(AdPerformanceDaily.platform_purchases).label("purchases"),
                func.sum(AdPerformanceDaily.impressions).label("impressions"),
                func.sum(AdPerformanceDaily.clicks).label("clicks"),
            )
            .where(AdPerformanceDaily.entity_type == "AD", AdPerformanceDaily.external_entity_id.in_(ad_ids), AdPerformanceDaily.date >= start)
            .group_by(AdPerformanceDaily.date)
            .order_by(AdPerformanceDaily.date)
        )
    ).all()
    return [dict(r._mapping) for r in rows]


@router.get("/creatives")
async def list_creatives(
    lifecycle: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Creative).order_by(Creative.external_creative_id.asc())
    if platform:
        query = query.where(Creative.platform == platform)
    rows = (await db.execute(query)).scalars().all()
    result = []
    for row in rows:
        perf = await _perf(db, row.external_creative_id, 30)
        total_spend = sum(float(p.get("spend") or 0) for p in perf)
        total_purchases = sum(float(p.get("purchases") or 0) for p in perf)
        if lifecycle:
            label = "WINNER" if total_purchases >= 5 and total_spend > 100 else "TESTING" if total_spend < 50 else "STABLE"
            if label != lifecycle:
                continue
        result.append(
            {
                "creative_id": row.external_creative_id,
                "name": row.name,
                "title": row.title,
                "platform": row.platform,
                "thumbnail_url": row.thumbnail_url,
                "image_url": row.image_url,
                "video_id": row.video_id,
                "cta_type": row.cta_type,
                "landing_page_url": row.landing_page_url,
                "spend_30d": total_spend,
                "purchases_30d": total_purchases,
                "roas_30d": round(total_purchases * 60 / total_spend, 2) if total_spend else None,
            }
        )
    return result


@router.get("/creatives/{creative_id}")
async def get_creative(creative_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Creative).where(Creative.external_creative_id == creative_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="creative not found")
    analyses = (
        await db.execute(
            select(CreativeAIAnalysis)
            .where(CreativeAIAnalysis.creative_id == creative_id)
            .order_by(CreativeAIAnalysis.created_at.desc())
            .limit(5)
        )
    ).scalars().all()
    return {
        "creative_id": creative_id,
        "name": row.name,
        "title": row.title,
        "body": row.body,
        "thumbnail_url": row.thumbnail_url,
        "image_url": row.image_url,
        "video_id": row.video_id,
        "landing_page_url": row.landing_page_url,
        "cta_type": row.cta_type,
        "performance": await _perf(db, creative_id),
        "ai_analyses": [
            {"id": str(a.id), "analysis_mode": a.analysis_mode, "creative_dna": a.creative_dna, "confidence": a.confidence, "blind": a.blind, "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in analyses
        ],
    }


@router.get("/creatives/{creative_id}/performance")
async def creative_performance(creative_id: str, days: int = Query(14), db: AsyncSession = Depends(get_db)):
    return {"creative_id": creative_id, "daily": await _perf(db, creative_id, days)}


@router.get("/creative-briefs")
async def list_briefs(status: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    query = select(CreativeBrief).order_by(CreativeBrief.created_at.desc())
    if status:
        query = query.where(CreativeBrief.status == status)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "objective": r.objective,
            "hook": r.hook,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/creative-briefs")
async def create_brief(data: BriefCreate, db: AsyncSession = Depends(get_db)):
    row = CreativeBrief(**data.model_dump(), status="DRAFT")
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": str(row.id), "status": row.status}
