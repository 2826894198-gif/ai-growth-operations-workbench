from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.rules import (
    Recommendation,
    RecommendationFeedback,
    RuleDefinition,
    RuleEvaluationRun,
)

router = APIRouter()


@router.get("")
async def rule_health(db: AsyncSession = Depends(get_db)):
    rules = (await db.execute(select(RuleDefinition))).scalars().all()
    active = sum(1 for r in rules if r.status == "ACTIVE")
    shadow = sum(1 for r in rules if r.status == "SHADOW")
    paused = sum(1 for r in rules if r.status == "PAUSED")
    recs = (await db.execute(select(Recommendation))).scalars().all()
    open_recs = sum(1 for r in recs if r.status in ("OPEN", "ACKNOWLEDGED"))
    high_severity = sum(1 for r in recs if r.severity in ("HIGH", "CRITICAL") and r.status in ("OPEN", "ACKNOWLEDGED"))
    runs = (await db.execute(select(RuleEvaluationRun).order_by(RuleEvaluationRun.created_at.desc()).limit(20))).scalars().all()
    feedback_rows = (await db.execute(select(RecommendationFeedback))).scalars().all()
    accepted = sum(1 for f in feedback_rows if f.operator_decision == "ACCEPT")
    rejected = sum(1 for f in feedback_rows if f.operator_decision in ("REJECT", "FALSE_POSITIVE"))
    feedback_total = len(feedback_rows)
    return {
        "active_rules": active,
        "shadow_rules": shadow,
        "paused_rules": paused,
        "open_recommendations": open_recs,
        "high_severity": high_severity,
        "feedback_acceptance_rate": round(accepted / feedback_total, 3) if feedback_total else None,
        "feedback_rejection_rate": round(rejected / feedback_total, 3) if feedback_total else None,
        "recent_runs": [
            {
                "id": str(run.id),
                "trigger_type": run.trigger_type,
                "triggered": run.triggered,
                "suppressed": run.suppressed,
                "status": run.status,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
            for run in runs
        ],
    }
