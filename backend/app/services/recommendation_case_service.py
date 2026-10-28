"""Recommendation Case workflow (review §5/§7) — one evidence-backed decision.

A case merges: rule evidence + AI explanation + simulation + approval + intent +
execution timeline. Status machine:
DRAFT → SIMULATED → PENDING_APPROVAL → APPROVED → EXECUTED / REJECTED / EXPIRED
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import ExecutionApproval, ExecutionIntent, ExecutionJob
from app.models.rules import Recommendation

CASE_TRANSITIONS = {
    "DRAFT": {"SIMULATED", "REJECTED"},
    "SIMULATED": {"PENDING_APPROVAL", "REJECTED"},
    "PENDING_APPROVAL": {"APPROVED", "REJECTED", "EXPIRED"},
    "APPROVED": {"EXECUTED", "EXPIRED", "REJECTED"},
    "EXECUTED": set(),
    "REJECTED": set(),
    "EXPIRED": set(),
}


def transition_case(current: str, target: str) -> bool:
    return target in CASE_TRANSITIONS.get(current, set())


async def build_case(db: AsyncSession, recommendation_id: str, days: int = 30) -> Dict[str, Any]:
    rec = (await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))).scalar_one_or_none()
    if rec is None:
        raise ValueError("recommendation not found")
    approvals = (
        await db.execute(select(ExecutionApproval).where(ExecutionApproval.recommendation_id == recommendation_id).order_by(ExecutionApproval.created_at))
    ).scalars().all()
    intents = (
        await db.execute(select(ExecutionIntent).where(ExecutionIntent.recommendation_id == recommendation_id).order_by(ExecutionIntent.created_at))
    ).scalars().all()
    jobs = []
    if intents:
        jobs = (
            await db.execute(select(ExecutionJob).where(ExecutionJob.intent_id.in_([str(i.id) for i in intents])).order_by(ExecutionJob.created_at))
        ).scalars().all()
    timeline: List[Dict[str, Any]] = [
        {"at": rec.created_at.isoformat() if rec.created_at else None, "type": "RECOMMENDATION_CREATED", "detail": rec.primary_action}
    ]
    for approval in approvals:
        timeline.append(
            {
                "at": approval.created_at.isoformat() if approval.created_at else None,
                "type": f"APPROVAL_{approval.status}",
                "detail": f"risk={approval.risk_level} by={approval.approved_by}",
            }
        )
    for intent in intents:
        timeline.append(
            {
                "at": intent.created_at.isoformat() if intent.created_at else None,
                "type": f"INTENT_{intent.status}",
                "detail": intent.action_type,
            }
        )
    for job in jobs:
        timeline.append(
            {
                "at": job.created_at.isoformat() if job.created_at else None,
                "type": f"JOB_{job.status}",
                "detail": job.error_code or job.verification_result or "",
            }
        )
    return {
        "recommendation": {
            "id": str(rec.id),
            "canonical_entity_id": rec.canonical_entity_id,
            "entity_type": rec.entity_type,
            "entity_id": rec.entity_id,
            "platform": rec.platform,
            "primary_action": rec.primary_action,
            "reason_group": rec.reason_group,
            "severity": rec.severity,
            "confidence": rec.confidence,
            "status": rec.status,
            "case_status": rec.case_status,
            "evidence": rec.evidence,
            "supporting_rules": rec.supporting_rules,
            "suppressed_reasons": rec.suppressed_reasons,
            "suggested_change_pct": rec.suggested_change_pct,
            "current_budget": rec.current_budget,
            "proposed_budget": rec.proposed_budget,
            "simulated_impact": rec.simulated_impact,
            "ai_explanation": rec.ai_explanation,
            "decision_reason": rec.decision_reason,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
        },
        "approvals": [
            {
                "id": str(a.id),
                "status": a.status,
                "approved_by": a.approved_by,
                "risk_level": a.risk_level,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                "approved_change": a.approved_change,
            }
            for a in approvals
        ],
        "intents": [
            {
                "id": str(i.id),
                "status": i.status,
                "action_type": i.action_type,
                "requested_change": i.requested_change,
                "action_package_hash": i.action_package_hash,
            }
            for i in intents
        ],
        "jobs": [
            {
                "id": str(j.id),
                "status": j.status,
                "action_type": j.action_type,
                "verification_result": j.verification_result,
                "error_code": j.error_code,
            }
            for j in jobs
        ],
        "timeline": timeline,
        "allowed_transitions": sorted(CASE_TRANSITIONS.get(rec.case_status, set())),
        "caveat": "case merges rule evidence + AI explanation; decision remains human-owned",
    }


async def transition(db: AsyncSession, recommendation_id: str, target: str, actor: str, reason: Optional[str] = None) -> Recommendation:
    rec = (await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))).scalar_one_or_none()
    if rec is None:
        raise ValueError("recommendation not found")
    if not transition_case(rec.case_status, target):
        raise ValueError(f"invalid case transition {rec.case_status} -> {target}")
    rec.case_status = target
    if reason:
        rec.decision_reason = reason
    if target in ("APPROVED", "REJECTED", "EXECUTED", "EXPIRED"):
        rec.status = "APPROVED" if target == "APPROVED" else "REJECTED" if target == "REJECTED" else "RESOLVED" if target == "EXPIRED" else "RESOLVED"
        rec.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    return rec


async def simulate(db: AsyncSession, recommendation_id: str, actor: str, parameters: Optional[Dict[str, Any]] = None) -> Recommendation:
    """Deterministic impact simulation for a budget change case (review 4.5)."""
    rec = (await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))).scalar_one_or_none()
    if rec is None:
        raise ValueError("recommendation not found")
    current = rec.current_budget or 0
    pct = rec.suggested_change_pct or 0
    proposed = rec.proposed_budget or current * (1 + pct / 100)
    rec.simulated_impact = {
        "current_budget": current,
        "proposed_budget": float(proposed),
        "delta_pct": round((float(proposed) - float(current)) / float(current) * 100, 2) if current else None,
        "mode": "deterministic_estimate",
        "caveat": "budget-only estimate; does not model auction or audience effects",
        "parameters": parameters or {},
        "simulated_at": datetime.now(timezone.utc).isoformat(),
        "simulated_by": actor,
    }
    if transition_case(rec.case_status, "SIMULATED"):
        rec.case_status = "SIMULATED"
    await db.flush()
    return rec
