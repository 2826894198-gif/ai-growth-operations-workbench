"""Execution policy engine: modes, risk, limits, cooldown, kill switches,
blast radius, standing policies, canary scope (PART 06 §37-§50, §88-§89).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.execution.actions.registry import ACTION_REGISTRY
from app.execution.risk import risk_at_most
from app.execution.timeutil import ensure_utc
from app.models.execution import ExecutionJob, ExecutionPolicy

SEED_POLICIES = [
    {
        "name": "Meta budget changes - manual (v1)",
        "provider": "META",
        "action_type": "META_CHANGE_BUDGET",
        "max_risk_level": "HIGH",
        "min_confidence": 0.55,
        "max_change_pct": 20.0,
        "cooldown_minutes": 1440,
    },
    {
        "name": "Meta pause - manual (v1)",
        "provider": "META",
        "action_type": "META_PAUSE_ENTITY",
        "max_risk_level": "HIGH",
        "min_confidence": 0.60,
        "cooldown_minutes": 720,
    },
    {
        "name": "Meta enable - manual (v1)",
        "provider": "META",
        "action_type": "META_ENABLE_ENTITY",
        "max_risk_level": "MEDIUM",
        "min_confidence": 0.55,
        "cooldown_minutes": 720,
    },
    {
        "name": "Google budget changes - manual (v1)",
        "provider": "GOOGLE_ADS",
        "action_type": "GOOGLE_CHANGE_BUDGET",
        "max_risk_level": "HIGH",
        "min_confidence": 0.55,
        "max_change_pct": 20.0,
        "cooldown_minutes": 1440,
    },
    {
        "name": "Google campaign pause - manual (v1)",
        "provider": "GOOGLE_ADS",
        "action_type": "GOOGLE_PAUSE_CAMPAIGN",
        "max_risk_level": "HIGH",
        "min_confidence": 0.60,
        "cooldown_minutes": 720,
    },
    {
        "name": "Google campaign enable - manual (v1)",
        "provider": "GOOGLE_ADS",
        "action_type": "GOOGLE_ENABLE_CAMPAIGN",
        "max_risk_level": "MEDIUM",
        "min_confidence": 0.55,
        "cooldown_minutes": 720,
    },
    {
        "name": "Google negative keyword - manual (v1)",
        "provider": "GOOGLE_ADS",
        "action_type": "GOOGLE_ADD_NEGATIVE_KEYWORD",
        "max_risk_level": "HIGH",
        "min_confidence": 0.65,
        "cooldown_minutes": 60,
    },
    {
        "name": "Google remove system negative - manual (v1)",
        "provider": "GOOGLE_ADS",
        "action_type": "GOOGLE_REMOVE_SYSTEM_NEGATIVE_KEYWORD",
        "max_risk_level": "MEDIUM",
        "min_confidence": 0.60,
        "cooldown_minutes": 60,
    },
]


async def seed_default_policies(db: AsyncSession, actor: str = "system") -> int:
    created = 0
    for seed in SEED_POLICIES:
        existing = (
            await db.execute(
                select(ExecutionPolicy).where(
                    ExecutionPolicy.provider == seed["provider"],
                    ExecutionPolicy.action_type == seed["action_type"],
                    ExecutionPolicy.workspace_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(
            ExecutionPolicy(
                workspace_id=None,
                name=seed["name"],
                provider=seed["provider"],
                action_type=seed["action_type"],
                mode="manual",
                max_risk_level=seed["max_risk_level"],
                min_confidence=seed["min_confidence"],
                max_change_pct=seed.get("max_change_pct"),
                max_actions_per_hour=settings.execution_max_actions_per_hour,
                max_actions_per_day=settings.execution_max_actions_per_day,
                max_total_budget_change_pct_per_day=settings.execution_max_daily_cumulative_budget_change_pct,
                allowed_scope={"all": False},
                require_fresh_data_minutes=60,
                cooldown_minutes=seed["cooldown_minutes"],
                max_affected_campaigns=1,
                auto_execution_eligible=False,
                standing_approval=False,
                canary_scope=None,
                enabled=True,
                version=1,
                created_by=actor,
            )
        )
        created += 1
    if created:
        await db.flush()
    return created


async def get_active_policy(
    db: AsyncSession, provider: str, action_type: str, workspace_id: Optional[str] = None
) -> Optional[ExecutionPolicy]:
    query = (
        select(ExecutionPolicy)
        .where(
            ExecutionPolicy.provider == provider,
            ExecutionPolicy.action_type == action_type,
            ExecutionPolicy.enabled.is_(True),
        )
        .order_by(ExecutionPolicy.version.desc())
    )
    if workspace_id:
        query = query.where(ExecutionPolicy.workspace_id == workspace_id)
    else:
        query = query.where(ExecutionPolicy.workspace_id.is_(None))
    return (await db.execute(query.limit(1))).scalar_one_or_none()


def _to_decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, dict) and "__decimal__" in value:
        value = value["__decimal__"]
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return None


def _delta_pct(current: Any, proposed: Any) -> Optional[Decimal]:
    current_dec = _to_decimal(current)
    proposed_dec = _to_decimal(proposed)
    if current_dec is None or proposed_dec is None:
        return None
    if not current_dec:
        return None
    return (proposed_dec - current_dec) / current_dec * Decimal("100")


async def _recent_jobs(
    db: AsyncSession,
    *,
    provider: str,
    entity_id: Optional[str] = None,
    action_type: Optional[str] = None,
    since: datetime,
    statuses: Optional[tuple] = None,
) -> List[ExecutionJob]:
    query = select(ExecutionJob).where(ExecutionJob.provider == provider)
    if statuses is not None:
        query = query.where(ExecutionJob.status.in_(statuses))
    else:
        query = query.where(ExecutionJob.status.notin_(("CANCELLED", "BLOCKED", "EXPIRED")))
    if entity_id:
        query = query.where(ExecutionJob.entity_id == entity_id)
    if action_type:
        query = query.where(ExecutionJob.action_type == action_type)
    rows = list((await db.execute(query)).scalars().all())
    return [r for r in rows if ensure_utc(r.created_at) is not None and ensure_utc(r.created_at) >= since]


async def evaluate_policy(
    db: AsyncSession,
    *,
    provider: str,
    action_type: str,
    entity_id: str,
    risk_level: str,
    blast_radius: str = "SMALL",
    confidence: float = 0.0,
    requested_change: Optional[Dict[str, Any]] = None,
    expected_before_state: Optional[Dict[str, Any]] = None,
    affected_campaigns: int = 1,
    workspace_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate the execution policy and return a PolicyDecision dict."""
    context = context or {}
    reasons: List[str] = []
    now = datetime.now(timezone.utc)
    policy = await get_active_policy(db, provider, action_type, workspace_id)
    mode = settings.execution_mode
    if policy is not None:
        mode = policy.mode if policy.mode != "manual" else mode

    if action_type not in ACTION_REGISTRY:
        reasons.append("ACTION_NOT_ALLOWLISTED")
        return _decision(False, risk_level, reasons, policy=policy, mode=mode)

    if settings.execution_mode == "observe":
        reasons.append("MODE_0_OBSERVE")
        return _decision(False, risk_level, reasons, policy=policy, mode=mode)

    if context.get("kill_switch_active"):
        reasons.append("KILL_SWITCH_ACTIVE")
        return _decision(False, risk_level, reasons, policy=policy, mode=mode)

    if context.get("shared_budget") and not (requested_change or {}).get("shared_budget_explicitly_approved"):
        reasons.append("SHARED_BUDGET_SCOPE_UNAPPROVED")

    if policy is None:
        reasons.append("NO_EXECUTION_POLICY")
        return _decision(False, risk_level, reasons, policy=policy, mode=mode)

    if not policy.enabled:
        reasons.append("POLICY_DISABLED")
        return _decision(False, risk_level, reasons, policy=policy, mode=mode)

    if not risk_at_most(risk_level, policy.max_risk_level):
        reasons.append("ACTION_RISK_TOO_HIGH")
    if confidence < policy.min_confidence:
        reasons.append("LOW_CONFIDENCE")

    if policy.max_change_pct is not None and requested_change:
        current = requested_change.get("current_budget")
        proposed = requested_change.get("proposed_budget")
        delta = _delta_pct(current, proposed)
        if delta is not None and abs(delta) > Decimal(str(policy.max_change_pct)):
            reasons.append("CHANGE_LIMIT_EXCEEDED")

    # Daily cumulative budget change (provider-level, budget actions)
    if "BUDGET" in action_type:
        day_ago = now - timedelta(hours=24)
        budget_jobs = await _recent_jobs(db, provider=provider, since=day_ago, statuses=("SUCCEEDED",))
        cumulative = Decimal("0")
        for job in budget_jobs:
            before = (job.requested_state or {}).get("current_budget")
            after = (job.requested_state or {}).get("proposed_budget")
            delta = _delta_pct(before, after)
            if delta is not None:
                cumulative += abs(delta)
        if cumulative > Decimal(str(policy.max_total_budget_change_pct_per_day)):
            reasons.append("DAILY_CUMULATIVE_LIMIT_EXCEEDED")

    # Rate / volume limits
    hour_jobs = await _recent_jobs(db, provider=provider, since=now - timedelta(hours=1), statuses=("SUCCEEDED", "RUNNING", "VERIFYING", "UNKNOWN", "FAILED"))
    day_jobs = await _recent_jobs(db, provider=provider, since=now - timedelta(hours=24), statuses=("SUCCEEDED", "RUNNING", "VERIFYING", "UNKNOWN", "FAILED"))
    if len(hour_jobs) >= policy.max_actions_per_hour:
        reasons.append("RATE_LIMIT_EXCEEDED")
    if len(day_jobs) >= policy.max_actions_per_day:
        reasons.append("DAILY_ACTION_LIMIT_EXCEEDED")
    if affected_campaigns > policy.max_affected_campaigns:
        reasons.append("BLAST_RADIUS_EXCEEDED")

    # Cooldown: same entity + same action (NOOP executions do not need cooldown)
    if not context.get("noop"):
        cooldown_jobs = await _recent_jobs(
            db,
            provider=provider,
            entity_id=entity_id,
            action_type=action_type,
            since=now - timedelta(minutes=policy.cooldown_minutes),
            statuses=("SUCCEEDED",),
        )
        if cooldown_jobs:
            reasons.append("COOLDOWN_ACTIVE")

    # Scope / canary allowlist
    scope = policy.allowed_scope or {}
    if not scope.get("all"):
        allow_ids = set(scope.get("entity_ids") or []) | set(scope.get("campaign_ids") or [])
        allow_account_ids = set(scope.get("allowed_account_ids") or [])
        account_id = context.get("account_id")
        if allow_account_ids and account_id and account_id not in allow_account_ids:
            reasons.append("ACCOUNT_NOT_ALLOWED")
        if allow_ids and entity_id not in allow_ids:
            reasons.append("SCOPE_NOT_ALLOWED")
    canary = policy.canary_scope or {}
    if canary.get("entity_ids") and entity_id not in set(canary["entity_ids"]):
        reasons.append("CANARY_SCOPE_EXCLUDED")

    # Data freshness
    fresh_minutes = context.get("data_fresh_minutes")
    if fresh_minutes is not None and fresh_minutes > policy.require_fresh_data_minutes:
        reasons.append("DATA_STALE")

    allowed = not reasons
    # Guarded Auto requires standing policy + allowlist + confidence/risk + eligibility
    requires_approval = True
    if allowed and mode == "guarded_auto":
        if policy.auto_execution_eligible and policy.standing_approval:
            requires_approval = False
        else:
            reasons.append("GUARDED_AUTO_NOT_ELIGIBLE")
            allowed = False
    return _decision(allowed, risk_level, reasons, policy=policy, mode=mode, requires_approval=requires_approval)


def primary_policy_code(reasons: List[str]) -> str:
    """Pick the most safety-critical reason code for the job error."""
    priority = (
        "KILL_SWITCH_ACTIVE",
        "SHARED_BUDGET_SCOPE_UNAPPROVED",
        "APPROVAL_EXPIRED",
        "APPROVAL_REVOKED",
        "APPROVAL_MISMATCH",
        "STATE_DRIFT",
        "DATA_STALE",
        "TRACKING_ANOMALY_ACTIVE",
        "EXPERIMENT_PROTECTED",
        "ACTION_RISK_TOO_HIGH",
        "CHANGE_LIMIT_EXCEEDED",
        "DAILY_CUMULATIVE_LIMIT_EXCEEDED",
        "DAILY_ACTION_LIMIT_EXCEEDED",
        "RATE_LIMIT_EXCEEDED",
        "BLAST_RADIUS_EXCEEDED",
        "COOLDOWN_ACTIVE",
        "ACCOUNT_NOT_ALLOWED",
        "SCOPE_NOT_ALLOWED",
        "CANARY_SCOPE_EXCLUDED",
        "LOW_CONFIDENCE",
        "ACTION_NOT_ALLOWLISTED",
        "NO_EXECUTION_POLICY",
        "POLICY_DISABLED",
        "MODE_0_OBSERVE",
        "GUARDED_AUTO_NOT_ELIGIBLE",
    )
    for code in priority:
        if code in reasons:
            return code
    return reasons[0] if reasons else "POLICY_BLOCKED"


def _decision(
    allowed: bool,
    risk: str,
    reasons: List[str],
    *,
    policy: Optional[ExecutionPolicy],
    mode: str,
    requires_approval: bool = True,
) -> Dict[str, Any]:
    return {
        "allowed": allowed,
        "risk": risk,
        "requires_approval": requires_approval if allowed else True,
        "approval_valid": None,
        "max_change_pct": policy.max_change_pct if policy else None,
        "cooldown_ok": "COOLDOWN_ACTIVE" not in reasons,
        "kill_switch": "KILL_SWITCH_ACTIVE" in reasons,
        "mode": mode,
        "policy_version": policy.version if policy else None,
        "policy_reason_codes": reasons,
        "reasons": reasons,
    }
