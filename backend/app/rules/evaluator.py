from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.rules.confidence.scorer import score_confidence
from app.rules.context import RuleContext
from app.rules.guards.runner import run_guards
from app.rules.operators import evaluate_operator
from app.rules.result import (
    RESULT_NO_DECISION,
    RESULT_NOT_TRIGGERED,
    RESULT_TRIGGERED,
    EvaluationResult,
)


def _condition_metric(condition: Dict[str, Any]) -> str:
    return str(condition.get("metric", ""))


async def evaluate_rule(
    db: AsyncSession,
    rule: Dict[str, Any],
    context: RuleContext,
    defaults: Dict[str, Any],
) -> EvaluationResult:
    action_config = rule.get("action") or {}
    action = action_config.get("type", "OBSERVE")
    reason = action_config.get("reason", "GENERIC")
    result = EvaluationResult(
        rule_key=rule["rule_key"],
        rule_version=rule.get("version", 1),
        entity_type=context.entity_type or "",
        entity_id=context.entity_id or "",
        platform=context.platform,
        action=action,
        reason_group=reason,
        severity=rule.get("severity", "MEDIUM"),
        feature_snapshot=dict(context.metrics),
    )

    guards_ok, guard_failures, guard_meta = await run_guards(db, context, rule, action, defaults)
    result.guards = guard_meta
    critical_safety = rule.get("category") == "SAFETY" and rule.get("severity") == "CRITICAL"
    if not guards_ok:
        allowed_failures = {"LEARNING_PROTECTION", "EXPERIMENT_PROTECTION", "RECENT_CHANGE_COOLDOWN"}
        if critical_safety and set(guard_failures).issubset(allowed_failures):
            pass  # Critical safety rules bypass learning/experiment/recent-change guards.
        else:
            result.result = RESULT_NO_DECISION
            result.reason_codes = guard_failures
            return result

    conditions = rule.get("conditions") or {}
    all_conditions = conditions.get("all", [])
    any_conditions = conditions.get("any", [])
    if not all_conditions and not any_conditions:
        result.result = RESULT_NOT_TRIGGERED
        return result

    missing: List[str] = []

    def check_condition(condition: Dict[str, Any]) -> bool:
        metric_name = _condition_metric(condition)
        value = context.metrics.get(metric_name)
        if value is None and condition.get("operator") not in ("is_null", "not_null"):
            missing.append(metric_name)
            return False
        target_value = None
        target_key = condition.get("target")
        if target_key:
            target_value = context.business_targets.get(target_key)
        return evaluate_operator(
            condition.get("operator", "eq"),
            value,
            condition.get("value"),
            target_value,
            condition.get("multiple"),
        )

    if all_conditions:
        if missing:
            result.result = RESULT_NO_DECISION
            result.reason_codes = [f"MISSING_FEATURE:{name}" for name in sorted(set(missing))]
            return result
        if not all(check_condition(c) for c in all_conditions):
            result.result = RESULT_NOT_TRIGGERED
            return result
    if any_conditions:
        if not any(check_condition(c) for c in any_conditions):
            result.result = RESULT_NOT_TRIGGERED
            return result

    result.result = RESULT_TRIGGERED
    result.evidence = build_evidence(context, rule)
    result.confidence, result.confidence_components = score_confidence(
        freshness_minutes=context.data_freshness_minutes,
        sample_reliability=float(context.metrics.get("sample_reliability_score") or 0),
        evidence=result.evidence,
        rule_strength_thresholds={},
        context={"cross_source_confirmed": context.extra.get("cross_source_confirmed")},
        weights=defaults.get("confidence_weights", {}),
        penalties=[],
    )
    result.suggested_change_pct = suggested_step(rule, context)
    return result


def build_evidence(context: RuleContext, rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence = []
    conditions = (rule.get("conditions") or {}).get("all", [])
    for condition in conditions[:5]:
        metric = _condition_metric(condition)
        evidence.append(
            {
                "metric": metric,
                "window": condition.get("window"),
                "current": context.metrics.get(metric),
                "target": context.business_targets.get(condition.get("target")),
                "operator": condition.get("operator"),
                "value": condition.get("value"),
                "source": context.platform,
            }
        )
    return evidence


def suggested_step(rule: Dict[str, Any], context: RuleContext) -> Any:
    action = (rule.get("action") or {}).get("type")
    if action == "REVIEW_SCALE":
        return 10.0
    if action == "REVIEW_REDUCE_BUDGET":
        return -10.0
    return None
