from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import CreativeAIAnalysis
from app.models.marketing import Creative


async def get_creative_metadata(db: AsyncSession, creative_id: str) -> Dict[str, Any]:
    row = (await db.execute(select(Creative).where(Creative.external_creative_id == creative_id))).scalar_one_or_none()
    if row is None:
        return {"creative_id": creative_id, "metadata": None}
    return {"creative_id": creative_id, "metadata": {"name": row.name, "title": row.title, "body": row.body, "image_url": row.image_url, "video_id": row.video_id, "landing_page_url": row.landing_page_url, "cta_type": row.cta_type}}


async def get_creative_asset(db: AsyncSession, creative_id: str) -> Dict[str, Any]:
    data = await get_creative_metadata(db, creative_id)
    return {**data, "asset_ref": f"creative://{creative_id}/asset"}


async def get_creative_performance_history(db: AsyncSession, creative_id: str) -> Dict[str, Any]:
    from app.ai.tools.metrics import get_creative_performance

    return await get_creative_performance(db, creative_id)


async def get_creative_ai_analysis(db: AsyncSession, creative_id: str) -> Dict[str, Any]:
    rows = (
        await db.execute(
            select(CreativeAIAnalysis)
            .where(CreativeAIAnalysis.creative_id == creative_id)
            .order_by(CreativeAIAnalysis.created_at.desc())
            .limit(1)
        )
    ).scalars().all()
    return {"creative_id": creative_id, "analysis": [dict(r.__table__.columns) for r in rows]}


async def save_creative_ai_analysis(db: AsyncSession, creative_id: str, dna: dict, analysis_mode: str, source_asset_hash: str, confidence: float, blind: bool = False) -> Dict[str, Any]:
    row = CreativeAIAnalysis(
        creative_id=creative_id,
        creative_dna=dna,
        analysis_mode=analysis_mode,
        source_asset_hash=source_asset_hash,
        confidence=confidence,
        blind=blind,
    )
    db.add(row)
    await db.commit()
    return {"creative_id": creative_id, "saved": True, "analysis_id": str(row.id)}
