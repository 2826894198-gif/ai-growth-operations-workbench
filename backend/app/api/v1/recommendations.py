from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.rules import Recommendation, RecommendationFeedback
from app.rules.audit import audit

router = APIRouter()


class FeedbackCreate(BaseModel):
    operator_decision: str
    reason: Optional[str] = None
    notes: Optional[str] = None


async def _get(db: AsyncSession, recommendation_id: str) -> Recommendation:
    rec = (await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))).scalar_one_or_none()
    if rec is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    return rec


@router.get("")
async def list_recommendations(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    rec_status: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(Recommendation).order_by(Recommendation.created_at.desc()).limit(limit)
    if entity_type:
        query = query.where(Recommendation.entity_type == entity_type)
    if entity_id:
        query = query.where(Recommendation.entity_id == entity_id)
    if platform:
        query = query.where(Recommendation.platform == platform)
    if rec_status:
        query = query.where(Recommendation.status == rec_status)
    if severity:
        query = query.where(Recommendation.severity == severity)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(r.id),
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "platform": r.platform,
            "primary_action": r.primary_action,
            "reason_group": r.reason_group,
            "severity": r.severity,
            "confidence": r.confidence,
            "status": r.status,
            "approval_required": r.approval_required,
            "evidence": r.evidence,
            "supporting_rules": r.supporting_rules,
            "suppressed_reasons": r.suppressed_reasons,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/{recommendation_id}")
async def get_recommendation(recommendation_id: str, db: AsyncSession = Depends(get_db)):
    rec = await _get(db, recommendation_id)
    return {
        "id": str(rec.id),
        "entity_type": rec.entity_type,
        "entity_id": rec.entity_id,
        "platform": rec.platform,
        "primary_action": rec.primary_action,
        "reason_group": rec.reason_group,
        "severity": rec.severity,
        "confidence": rec.confidence,
        "status": rec.status,
        "approval_required": rec.approval_required,
        "auto_execution_eligible": rec.auto_execution_eligible,
        "evidence": rec.evidence,
        "supporting_rules": rec.supporting_rules,
        "suppressed_reasons": rec.suppressed_reasons,
        "suggested_change_pct": rec.suggested_change_pct,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


async def _transition(db: AsyncSession, recommendation_id: str, status: str) -> dict:
    rec = await _get(db, recommendation_id)
    before = {"status": rec.status}
    rec.status = status
    if status in ("APPROVED", "REJECTED", "RESOLVED", "EXPIRED", "SUPERSEDED"):
        rec.resolved_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    await audit(db, actor="api", action=f"recommendation_{status.lower()}", target=recommendation_id, before=before, after={"status": status})
    await db.commit()
    return {"id": recommendation_id, "status": status}


@router.post("/{recommendation_id}/acknowledge")
async def acknowledge(recommendation_id: str, db: AsyncSession = Depends(get_db)):
    return await _transition(db, recommendation_id, "ACKNOWLEDGED")


@router.post("/{recommendation_id}/approve")
async def approve(recommendation_id: str, db: AsyncSession = Depends(get_db)):
    return await _transition(db, recommendation_id, "APPROVED")


@router.post("/{recommendation_id}/reject")
async def reject(recommendation_id: str, db: AsyncSession = Depends(get_db)):
    return await _transition(db, recommendation_id, "REJECTED")


@router.post("/{recommendation_id}/feedback")
async def feedback(recommendation_id: str, data: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    await _get(db, recommendation_id)
    db.add(
        RecommendationFeedback(
            recommendation_id=recommendation_id,
            operator_decision=data.operator_decision,
            reason=data.reason,
            notes=data.notes,
        )
    )
    await db.commit()
    return {"status": "recorded"}


@router.post("/{recommendation_id}/execution-preview")
async def execution_preview(recommendation_id: str, db: AsyncSession = Depends(get_db)):
    """PART 06 §141 — preview without creating an execution job or writing."""
    from app.execution.service import create_approval_from_recommendation

    try:
        preview = await create_approval_from_recommendation(
            db,
            recommendation_id=recommendation_id,
            approved_by="preview",
            force_mock=True,
            commit=False,
        )
        await db.rollback()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    approval, detail = preview
    return {
        "recommendation_id": recommendation_id,
        "would_execute": True,
        "action_type": approval.action_type,
        "provider": approval.provider,
        "risk_level": approval.risk_level,
        "approved_change": approval.approved_change,
        "expected_before_state": approval.expected_before_state,
        "expires_at": approval.expires_at.isoformat(),
        "detail": detail,
    }


@router.post("/{recommendation_id}/explain")
async def explain_recommendation(recommendation_id: str, db: AsyncSession = Depends(get_db)):
    """Explain an existing recommendation from its stored evidence (no rule mutation)."""
    rec = await _get(db, recommendation_id)
    evidence_lines = []
    for item in rec.evidence or []:
        current = item.get("current")
        baseline = item.get("baseline")
        if current is not None:
            evidence_lines.append(f"{item.get('metric')}: {current}" + (f" (baseline {baseline})" if baseline is not None else ""))
    explanation = (
        f"Recommendation {rec.primary_action} for {rec.entity_type} {rec.entity_id} "
        f"triggered by {rec.reason_group} with confidence {rec.confidence:.2f}."
        + (" Evidence: " + "; ".join(evidence_lines) if evidence_lines else " No quantitative evidence stored.")
    )
    return {
        "recommendation_id": str(rec.id),
        "explanation": explanation,
        "evidence": rec.evidence,
        "supporting_rules": rec.supporting_rules,
        "suppressed_reasons": rec.suppressed_reasons,
        "source": "evidence-based deterministic explanation",
    }
