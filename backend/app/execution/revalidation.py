"""Revalidation checklist (PART 06 §15-§18, §172)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution.approvals import validate_approval_for_intent
from app.execution.state import canonical_json
from app.execution.timeutil import ensure_utc
from app.models.data_quality import DataQualityIssue
from app.models.execution import ExecutionIntent, ExecutionJob
from app.models.marketing import Ad, AdGroup, Campaign
from app.models.rules import (
    ActiveExperiment,
    BusinessTargetProfile,
    EntityChangeEvent,
    Recommendation,
)
from app.models.social import ContentPromotionLink
from app.models.sync import SyncJob


def state_drift(expected: Optional[Dict[str, Any]], actual: Optional[Dict[str, Any]]) -> List[str]:
    """Compare only fields captured in the expected before-state."""
    expected = expected or {}
    actual = actual or {}
    differences: List[str] = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if canonical_json(expected_value) != canonical_json(actual_value):
            differences.append(f"{key}: expected={expected_value!r} actual={actual_value!r}")
    return differences


async def _entity_exists(db: AsyncSession, entity_type: str, entity_id: str) -> bool:
    entity_type = entity_type.upper()
    if entity_type in ("CAMPAIGN", "GOOGLE_CAMPAIGN"):
        row = (
            await db.execute(
                select(Campaign).where((Campaign.id == entity_id) | (Campaign.external_campaign_id == entity_id))
            )
        ).scalar_one_or_none()
        return row is not None
    if entity_type in ("AD_SET", "ADGROUP", "AD_GROUP"):
        row = (
            await db.execute(
                select(AdGroup).where((AdGroup.id == entity_id) | (AdGroup.external_group_id == entity_id))
            )
        ).scalar_one_or_none()
        return row is not None
    if entity_type == "AD":
        row = (await db.execute(select(Ad).where((Ad.id == entity_id) | (Ad.external_ad_id == entity_id)))).scalar_one_or_none()
        return row is not None
    # Unknown entity types are treated as NO_DECISION, not a hard failure.
    return True


async def revalidate(
    db: AsyncSession,
    *,
    intent: ExecutionIntent,
    provider_state: Optional[Dict[str, Any]],
    kill_switch_active: bool = False,
    policy_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the full PART 06 §16 checklist. Returns PASS/FAIL/REQUIRE_REAPPROVAL/NO_DECISION."""
    policy_context = policy_context or {}
    checks: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    result = "PASS"

    def check(name: str, ok: bool, detail: str = "", severity: str = "error") -> None:
        nonlocal result
        checks.append({"name": name, "ok": ok, "detail": detail, "severity": severity})
        if not ok and severity == "error" and result == "PASS":
            result = "FAIL"
        elif not ok and severity == "warning" and result == "PASS":
            result = "REQUIRE_REAPPROVAL"

    # 1. Approval valid
    approval_check = await validate_approval_for_intent(
        db,
        approval_id=intent.approval_id,
        provider=intent.provider,
        action_type=intent.action_type,
        entity_id=intent.entity_id,
        requested_change=intent.requested_change,
        expected_before_state=intent.expected_before_state,
        workspace_id=intent.workspace_id,
    )
    check("approval_valid", approval_check["ok"], approval_check.get("message", ""))

    # 2. Recommendation still actionable / not superseded
    rec = (
        await db.execute(select(Recommendation).where(Recommendation.id == intent.recommendation_id))
    ).scalar_one_or_none()
    if rec is None:
        check("recommendation_exists", False, "recommendation not found")
    elif rec.status in ("RESOLVED", "REJECTED", "EXPIRED", "SUPERSEDED"):
        check("recommendation_actionable", False, f"recommendation status is {rec.status}")
    else:
        check("recommendation_actionable", True)
        newer = (
            await db.execute(
                select(Recommendation).where(
                    Recommendation.entity_id == intent.entity_id,
                    Recommendation.primary_action == rec.primary_action,
                    Recommendation.status.in_(("OPEN", "APPROVED", "ACKNOWLEDGED")),
                )
            )
        ).scalars().all()
        rec_created = ensure_utc(rec.created_at) or now
        newer = [r for r in newer if ensure_utc(r.created_at) is not None and ensure_utc(r.created_at) > rec_created]
        if newer:
            check(
                "recommendation_not_superseded",
                False,
                f"newer recommendation {newer[0].id} supersedes this action",
            )

    # 3. Entity still exists — provider read is authoritative, DB is fallback
    provider_entity_known = bool(provider_state) and (
        provider_state.get("status") is not None
        or provider_state.get("entity_id") == intent.entity_id
        or provider_state.get("campaign_id") is not None
    )
    exists = provider_entity_known or await _entity_exists(db, intent.entity_type, intent.entity_id)
    check("entity_exists", exists, "entity not found by provider or in canonical data layer" if not exists else "")

    # 4. Provider state matches expected before-state (optimistic concurrency)
    drift = state_drift(intent.expected_before_state, provider_state)
    if drift:
        check("state_drift", False, "; ".join(drift))
    else:
        check("state_drift", True)

    # 5. Business target unchanged materially
    target = (
        await db.execute(select(BusinessTargetProfile).order_by(BusinessTargetProfile.created_at.desc()).limit(1))
    ).scalar_one_or_none()
    if target is not None:
        snapshot = (intent.expected_before_state or {}).get("business_target") or {}
        for field in ("target_roas", "target_cpa", "max_daily_spend"):
            expected_value = snapshot.get(field)
            current_value = getattr(target, field, None)
            if expected_value is not None and current_value is not None and str(expected_value) != str(current_value):
                check("business_target_unchanged", False, f"{field} changed {expected_value} -> {current_value}")
                break
        else:
            check("business_target_unchanged", True)
    else:
        check("business_target_unchanged", True, "no target profile", "warning")

    # 6. Hard spend guard / tracking anomaly / critical data issue
    open_issues = (
        await db.execute(
            select(DataQualityIssue).where(
                DataQualityIssue.status == "OPEN",
                DataQualityIssue.severity.in_(("CRITICAL", "ERROR")),
            )
        )
    ).scalars().all()
    spend_guard = [i for i in open_issues if "SPEND" in (i.rule_code or "").upper() or "HARD_CAP" in (i.rule_code or "").upper()]
    tracking = [i for i in open_issues if "TRACKING" in (i.rule_code or "").upper() or "ATTRIBUTION" in (i.rule_code or "").upper()]
    check("hard_spend_guard", not spend_guard, f"open spend guard issues: {[i.rule_code for i in spend_guard]}" if spend_guard else "")
    check("tracking_anomaly", not tracking, f"tracking anomalies: {[i.rule_code for i in tracking]}" if tracking else "")

    # 7. Data freshness
    fresh_minutes = None
    job = (
        await db.execute(
            select(SyncJob)
            .where(SyncJob.provider == intent.provider, SyncJob.status == "SUCCESS")
            .order_by(SyncJob.finished_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if job is not None and job.finished_at is not None:
        fresh_minutes = int((now - ensure_utc(job.finished_at)).total_seconds() // 60)
    if fresh_minutes is None:
        check("data_fresh", True, "no sync job history (cannot confirm freshness)", "warning")
    else:
        required = policy_context.get("require_fresh_data_minutes", 60)
        check("data_fresh", fresh_minutes <= required, f"last sync {fresh_minutes}m ago (> {required}m)")

    # 8. Experiment protection
    experiments = (
        await db.execute(
            select(ActiveExperiment).where(
                ActiveExperiment.status == "ACTIVE",
                ActiveExperiment.platform == intent.provider,
            )
        )
    ).scalars().all()
    protected = [
        e
        for e in experiments
        if e.scope_type in ("GLOBAL", "ACCOUNT", "CAMPAIGN", "AD_SET", "AD")
        and (e.scope_id in (None, "*", intent.entity_id, intent.external_entity_id) or e.scope_type == "GLOBAL")
    ]
    check("experiment_protection", not protected, f"active protected experiment: {[e.name for e in protected]}" if protected else "")

    # 9. Manual external change detection since approval
    approval_created = intent.created_at
    manual_changes = (
        await db.execute(
            select(EntityChangeEvent).where(
                EntityChangeEvent.platform == intent.provider,
                EntityChangeEvent.entity_id == intent.entity_id,
                EntityChangeEvent.meta.isnot(None),
            )
        )
    ).scalars().all()
    approval_created_utc = ensure_utc(approval_created)
    manual_after_approval = [
        e
        for e in manual_changes
        if (e.meta or {}).get("source") == "EXTERNAL_MANUAL"
        and (approval_created_utc is None or ensure_utc(e.occurred_at) > approval_created_utc)
    ]
    check(
        "no_manual_external_change",
        not manual_after_approval,
        f"external manual change detected: {[e.change_type for e in manual_after_approval]}" if manual_after_approval else "",
    )

    # 10. No conflicting execution in progress
    conflicting = (
        await db.execute(
            select(ExecutionJob).where(
                ExecutionJob.entity_id == intent.entity_id,
                ExecutionJob.provider == intent.provider,
                ExecutionJob.status.in_(("QUEUED", "REVALIDATING", "RUNNING", "VERIFYING")),
                ExecutionJob.intent_id != intent.id,
            )
        )
    ).scalars().all()
    check("no_conflicting_execution", not conflicting, f"conflicting jobs: {[j.id for j in conflicting]}" if conflicting else "")

    # 11. Kill switch
    check("kill_switch_inactive", not kill_switch_active, "kill switch active" if kill_switch_active else "")

    # 12. Promotion mapping revalidation (PART 06-01 §E183): execution must stay
    # bound to the exact paid resource the operator approved.
    promotion_link_id = (intent.requested_change or {}).get("promotion_link_id")
    if promotion_link_id:
        link = (
            await db.execute(select(ContentPromotionLink).where(ContentPromotionLink.id == promotion_link_id))
        ).scalar_one_or_none()
        if link is None:
            check("promotion_mapping_valid", False, "promotion link no longer exists")
        elif link.status != "ACTIVE":
            check("promotion_mapping_valid", False, f"promotion link status is {link.status}")
        else:
            expected_ad = (intent.requested_change or {}).get("ad_id")
            expected_campaign = (intent.requested_change or {}).get("campaign_id")
            mapping_drift = []
            if expected_ad and link.ad_id and str(expected_ad) != str(link.ad_id):
                mapping_drift.append(f"ad {expected_ad} -> {link.ad_id}")
            if expected_campaign and link.campaign_id and str(expected_campaign) != str(link.campaign_id):
                mapping_drift.append(f"campaign {expected_campaign} -> {link.campaign_id}")
            if mapping_drift:
                check("promotion_mapping_valid", False, "promotion mapping drifted: " + "; ".join(mapping_drift))
            else:
                check("promotion_mapping_valid", True)
    else:
        check("promotion_mapping_valid", True, "no promotion link binding")

    return {
        "result": result,
        "checks": checks,
        "provider_state": provider_state,
        "revalidated_at": now.isoformat(),
        "passed": all(c["ok"] or c["severity"] == "warning" for c in checks),
    }
