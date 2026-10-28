from typing import Dict, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.rules.context import RuleContext
from app.rules.guards.attribution_delay import check_attribution_delay
from app.rules.guards.cooldown import check_cooldown
from app.rules.guards.experiment import check_experiment
from app.rules.guards.freshness import check_freshness
from app.rules.guards.learning import check_learning
from app.rules.guards.recent_change import check_recent_change
from app.rules.guards.sample import check_sample


async def run_guards(
    db: AsyncSession,
    context: RuleContext,
    rule: dict,
    action: str,
    defaults: dict,
) -> Tuple[bool, List[str], Dict[str, object]]:
    guards = rule.get("guards") or {}
    failures: List[str] = []
    meta: Dict[str, object] = {}

    category = rule.get("category", "")
    if category == "DATA":
        # Data-staleness rules are the detector; do not block them on freshness/sample.
        meta["freshness"] = True
        meta["sample"] = True
    else:
        ok, reason = check_freshness(context, guards)
        if not ok:
            failures.append(reason)
        meta["freshness"] = ok

        if category == "SAFETY":
            meta["sample"] = True
        else:
            ok, reason = check_sample(context, guards, defaults.get("sample_reliability", {}))
            if not ok:
                failures.append(reason)
            meta["sample"] = ok

    ok, reason = check_attribution_delay(context, guards)
    if not ok:
        failures.append(reason)
    meta["attribution_delay"] = ok

    ok, reason = check_learning(context, guards)
    if not ok:
        failures.append(reason)
    meta["learning"] = ok

    ok, reason = check_recent_change(context, guards)
    if not ok:
        failures.append(reason)
    meta["recent_change"] = ok

    ok, reason = check_experiment(context, action)
    if not ok:
        failures.append(reason)
    meta["experiment"] = ok

    cooldown_ok, reason = await check_cooldown(
        db,
        context.entity_type or "",
        context.entity_id or "",
        action,
        (rule.get("action") or {}).get("reason", "GENERIC"),
        rule.get("cooldown_minutes", 1440),
        rule.get("severity", "MEDIUM"),
        ignore=bool(context.extra.get("ignore_cooldown")),
    )
    meta["cooldown"] = cooldown_ok
    if not cooldown_ok:
        failures.append(reason)

    return not failures, failures, meta
