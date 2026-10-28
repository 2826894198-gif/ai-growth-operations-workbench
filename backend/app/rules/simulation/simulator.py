from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rules import RuleDefinition, RuleEvaluation
from app.rules.engine import run_evaluation
from app.rules.registry import load_rule_packs


def _apply_params(rule: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    rule = {**rule}
    conditions = {"all": [], "any": rule.get("conditions", {}).get("any", [])}
    for condition in rule.get("conditions", {}).get("all", []):
        updated = {**condition}
        for key, value in params.items():
            if key in condition:
                updated[key] = value
            if key == "multiple" and "multiple" in condition:
                updated["multiple"] = value
        conditions["all"].append(updated)
    rule["conditions"] = conditions
    guards = {**(rule.get("guards") or {})}
    for key, value in params.items():
        if key in guards:
            guards[key] = value
    rule["guards"] = guards
    return rule


async def simulate_rule(
    db: AsyncSession,
    rule_key: str,
    candidate_parameters: Dict[str, Any],
    start_date: str,
    end_date: str,
    scope: str = "ALL",
) -> dict:
    """Evaluate a candidate rule config without altering active rules or recommendations."""
    yaml_rules = load_rule_packs(include_disabled=True)
    base = next((r for r in yaml_rules if r["rule_key"] == rule_key), None)
    if base is None:
        raise ValueError(f"unknown rule: {rule_key}")
    candidate = _apply_params(base, candidate_parameters)
    candidate_key = f"{rule_key}__SIM"

    temp = RuleDefinition(
        rule_key=candidate_key,
        name=f"Simulation {rule_key}",
        category=base.get("category", "CAMPAIGN"),
        platform=base.get("platform"),
        evaluation_level=base.get("evaluation_level", "AD"),
        severity=base.get("severity", "MEDIUM"),
        status="DRAFT",
        enabled=False,
        version=1,
        conditions=candidate["conditions"],
        guards=candidate["guards"],
        action_template=candidate["action"],
        cooldown_minutes=candidate.get("cooldown_minutes", 1440),
    )
    db.add(temp)
    await db.flush()
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        days = []
        total = 0
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            as_of = datetime.combine(day, time(23, 59), tzinfo=timezone.utc)
            run = await run_evaluation(db, trigger_type="SIMULATION", rule_keys=[candidate_key], as_of=as_of, shadow=True)
            if run is None:
                continue
            days.append({"date": day.isoformat(), "triggered": run.triggered})
            total += run.triggered
        return {
            "rule_key": rule_key,
            "candidate_parameters": candidate_parameters,
            "start_date": start_date,
            "end_date": end_date,
            "total_triggers": total,
            "days": days,
        }
    finally:
        await db.execute(delete(RuleEvaluation).where(RuleEvaluation.rule_key == candidate_key))
        await db.execute(delete(RuleDefinition).where(RuleDefinition.id == temp.id))
        await db.commit()
