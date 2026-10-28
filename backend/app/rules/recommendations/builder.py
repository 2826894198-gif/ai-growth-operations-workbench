from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rules import Recommendation
from app.rules.recommendations.risk import action_risk, approval_required
from app.rules.result import EvaluationResult


async def persist_recommendations(db: AsyncSession, results: List[EvaluationResult], shadow: bool) -> int:
    created = 0
    for result in results:
        if result.result != "TRIGGERED" or result.action is None:
            continue
        risk = action_risk(result.action, result.severity)
        approval, auto_eligible = approval_required(result.action, risk, False)
        db.add(
            Recommendation(
                entity_type=result.entity_type,
                entity_id=result.entity_id,
                platform=result.platform,
                primary_action=result.action,
                reason_group=result.reason_group or "GENERIC",
                severity=result.severity,
                confidence=result.confidence,
                status="OPEN" if not shadow else "OPEN",
                approval_required=approval,
                auto_execution_eligible=auto_eligible,
                evidence=result.evidence,
                supporting_rules=[{"rule_key": result.rule_key, "version": result.rule_version}],
                suppressed_reasons=result.suppressed_reasons,
                suggested_change_pct=result.suggested_change_pct,
                current_budget=result.current_budget,
                proposed_budget=result.proposed_budget,
            )
        )
        created += 1
    return created
