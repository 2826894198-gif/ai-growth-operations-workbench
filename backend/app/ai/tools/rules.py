from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rules import BusinessTargetProfile, Recommendation, RuleEvaluation


async def get_open_recommendations(db: AsyncSession, platform: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    query = (
        select(Recommendation)
        .where(Recommendation.status.in_(["OPEN", "ACKNOWLEDGED"]))
        .order_by(Recommendation.created_at.desc())
        .limit(limit)
    )
    if platform:
        query = query.where(Recommendation.platform == platform)
    rows = (await db.execute(query)).scalars().all()
    return {
        "recommendations": [
            {
                "id": str(r.id),
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "platform": r.platform,
                "primary_action": r.primary_action,
                "reason_group": r.reason_group,
                "severity": r.severity,
                "confidence": r.confidence,
                "evidence": r.evidence,
            }
            for r in rows
        ],
        "_output_ref": "rule://recommendations/open",
    }


async def get_entity_rule_findings(db: AsyncSession, entity_type: str, entity_id: str, limit: int = 10) -> Dict[str, Any]:
    rows = (
        await db.execute(
            select(RuleEvaluation)
            .where(RuleEvaluation.entity_type == entity_type, RuleEvaluation.entity_id == entity_id)
            .order_by(RuleEvaluation.evaluated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return {
        "findings": [
            {"rule_key": r.rule_key, "rule_version": r.rule_version, "result": r.result, "confidence": r.confidence, "reason_codes": r.reason_codes}
            for r in rows
        ],
        "_output_ref": f"rule://{entity_type}/{entity_id}",
    }


async def get_rule_evidence(db: AsyncSession, recommendation_id: str) -> Dict[str, Any]:
    rec = (await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))).scalar_one_or_none()
    if rec is None:
        return {"evidence": [], "error": "not found"}
    return {"evidence": rec.evidence or [], "supporting_rules": rec.supporting_rules or [], "suppressed_reasons": rec.suppressed_reasons or []}


async def get_suppressed_decisions(db: AsyncSession, limit: int = 20) -> Dict[str, Any]:
    rows = (
        await db.execute(
            select(RuleEvaluation)
            .where(RuleEvaluation.result == "SUPPRESSED")
            .order_by(RuleEvaluation.evaluated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return {"suppressed": [{"rule_key": r.rule_key, "entity_id": r.entity_id, "reason_codes": r.reason_codes} for r in rows]}


async def get_business_targets(db: AsyncSession) -> Dict[str, Any]:
    rows = (await db.execute(select(BusinessTargetProfile))).scalars().all()
    return {"targets": [{"name": r.name, "scope_type": r.scope_type, "target_cpa": r.target_cpa, "target_roas": r.target_roas, "break_even_roas": r.break_even_roas} for r in rows]}
