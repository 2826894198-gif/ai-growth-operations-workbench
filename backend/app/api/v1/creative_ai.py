
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.creative.analysis import analyze_creative
from app.core.database import get_db
from app.models.ai import CreativeAIAnalysis

router = APIRouter()


class CreativeAnalysisRequest(BaseModel):
    blind: bool = False
    force: bool = False


@router.post("/creatives/{creative_id}/ai-analysis")
async def create_creative_analysis(creative_id: str, data: CreativeAnalysisRequest, db: AsyncSession = Depends(get_db)):
    result = await analyze_creative(db, creative_id, blind=data.blind, force=data.force)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/creatives/{creative_id}/ai-analysis")
async def get_creative_analysis(creative_id: str, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(CreativeAIAnalysis)
            .where(CreativeAIAnalysis.creative_id == creative_id)
            .order_by(CreativeAIAnalysis.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "analysis_version": r.analysis_version,
            "model_provider": r.model_provider,
            "model_name": r.model_name,
            "creative_dna": r.creative_dna,
            "analysis_mode": r.analysis_mode,
            "confidence": r.confidence,
            "source_asset_hash": r.source_asset_hash,
            "blind": r.blind,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
