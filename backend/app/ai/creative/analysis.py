from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.base import run_agent
from app.ai.agents.definitions import creative_agent
from app.ai.media.preprocess import inspect_media
from app.ai.tools.registry import registry
from app.models.ai import CreativeAIAnalysis


async def analyze_creative(db: AsyncSession, creative_id: str, blind: bool = False, force: bool = False) -> Dict[str, Any]:
    meta = await registry.call(db, agent_type="creative", tool_name="get_creative_metadata", run_id=None, step_id=None, kwargs={"creative_id": creative_id})
    if not meta.get("metadata"):
        return {"error": "creative not found"}
    media = await inspect_media(f"creative://{creative_id}/asset")
    asset_hash = media["asset_hash"]
    if not force:
        existing = (
            await db.execute(
                select(CreativeAIAnalysis)
                .where(CreativeAIAnalysis.creative_id == creative_id, CreativeAIAnalysis.source_asset_hash == asset_hash)
                .order_by(CreativeAIAnalysis.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {
                "creative_id": creative_id,
                "cached": True,
                "analysis_id": str(existing.id),
                "creative_dna": existing.creative_dna,
                "analysis_mode": existing.analysis_mode,
                "source_asset_hash": asset_hash,
            }
    task = f"Analyze creative {creative_id}. Media: {media}"
    if blind:
        task += "\nBLIND MODE: do not use performance labels."
    output = await run_agent(
        db,
        creative_agent,
        task_prompt=task,
        run_id="creative-analysis",
        seed={
            "creative_id": creative_id,
            "analysis_mode": "FRAME_SAMPLE",
            "source_asset_hash": asset_hash,
            "blind": blind,
        },
    )
    dna = output.model_dump()
    saved = await registry.call(
        db,
        agent_type="creative",
        tool_name="save_creative_ai_analysis",
        run_id=None,
        step_id=None,
        kwargs={
            "creative_id": creative_id,
            "dna": dna.get("dna"),
            "analysis_mode": dna.get("analysis_mode", "FRAME_SAMPLE"),
            "source_asset_hash": asset_hash,
            "confidence": (dna.get("dna") or {}).get("confidence", 0.5),
            "blind": blind,
        },
    )
    return {"creative_id": creative_id, "cached": False, **saved, "analysis": dna}
