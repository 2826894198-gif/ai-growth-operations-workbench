"""PART 06 smoke execution — full golden scenario run against Mock provider.

Usage:
    cd backend && DATABASE_URL=sqlite+aiosqlite:////tmp/smoke_execution.db \
        .venv/bin/python ../scripts/smoke_execution.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/smoke_execution.db")
os.environ.setdefault("DATA_PROVIDER_MODE", "mock")
os.environ.setdefault("EXECUTION_ENABLED", "true")
os.environ.setdefault("EXECUTION_MODE", "manual")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.execution.approvals import create_approval, revoke_approval  # noqa: E402
from app.execution.compensation import approve_compensation, run_compensation  # noqa: E402
from app.execution.engine import execute_intent  # noqa: E402
from app.execution.intents import create_intent  # noqa: E402
from app.execution.policies import seed_default_policies  # noqa: E402
from app.execution.providers.mock import MockExecutionProvider  # noqa: E402
from app.execution.service import approve_and_create_intent, create_approval_from_recommendation  # noqa: E402
from app.models.data_quality import DataQualityIssue  # noqa: E402
from app.models.execution import ExecutionCompensation, ExecutionJob, ExecutionKillSwitch, ExecutionPolicy  # noqa: E402
from app.models.rules import ActiveExperiment, EntityChangeEvent, Recommendation  # noqa: E402

RESULTS = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


async def make_rec(db, *, platform, entity_type, entity_id, primary_action, pct=None, confidence=0.8, status="OPEN"):
    rec = Recommendation(
        entity_type=entity_type,
        entity_id=entity_id,
        platform=platform,
        primary_action=primary_action,
        reason_group="SMOKE",
        severity="MEDIUM",
        confidence=confidence,
        status=status,
        approval_required=True,
        suggested_change_pct=pct,
    )
    db.add(rec)
    await db.flush()
    return rec


async def intent_from_approval(db, provider_impl, rec, *, action_type, requested_change, actor="tester"):
    """Create PENDING approval with explicit action payload, then approve -> intent."""
    requested_change = {**requested_change}
    state = await provider_impl.get_current_state(
        SimpleNamespace(
            id=f"pre-{rec.id}",
            provider="META" if (rec.platform or "").upper() == "META_ADS" else "GOOGLE_ADS",
            action_type=action_type,
            entity_type=(rec.entity_type or "CAMPAIGN").upper(),
            entity_id=rec.entity_id,
            external_entity_id=rec.entity_id,
            requested_change=requested_change,
            expected_before_state=None,
            workspace_id=None,
        )
    )
    if "BUDGET" in action_type:
        if "current_budget" not in requested_change or "proposed_budget" not in requested_change:
            current_budget = state.get("budget") or state.get("daily_budget")
            if current_budget is None and state.get("amount_micros") is not None:
                from app.execution.providers.google_ads.budget import micros_to_decimal

                current_budget = micros_to_decimal(state["amount_micros"])
            pct = rec.suggested_change_pct if rec.suggested_change_pct is not None else 10
            current_budget = float(current_budget)
            requested_change["current_budget"] = str(current_budget)
            requested_change["proposed_budget"] = str(current_budget * (1 + pct / 100))
        if action_type.startswith("META_"):
            requested_change.setdefault("budget_owner", state.get("budget_owner") or "CAMPAIGN")
            requested_change.setdefault("budget_owner_entity_id", state.get("budget_owner_entity_id") or rec.entity_id)
        else:
            requested_change.setdefault("budget_resource", state.get("budget_resource"))
            requested_change.setdefault("affected_campaigns", [c.get("id") for c in state.get("campaigns", [])])
        requested_change.setdefault("currency", "USD")
    approval = await create_approval(
        db,
        workspace_id=None,
        recommendation_id=str(rec.id),
        provider="META" if (rec.platform or "").upper() == "META_ADS" else "GOOGLE_ADS",
        action_type=action_type,
        entity_type=(rec.entity_type or "CAMPAIGN").upper(),
        entity_id=rec.entity_id,
        external_entity_id=rec.entity_id,
        approved_change=requested_change,
        expected_before_state=state,
        approved_by=actor,
        risk_level="MEDIUM",
        status="PENDING",
        expiry_hours=requested_change.pop("_expiry_hours", None),
    )
    intent = await approve_and_create_intent(db, str(approval.id), actor)
    return intent


async def run(db, provider_impl, rec, *, actor="tester", retries=(0, 0), direct=None):
    if direct is not None:
        intent = await intent_from_approval(db, provider_impl, rec, **direct)
    else:
        approval, _ = await create_approval_from_recommendation(
            db,
            recommendation_id=str(rec.id),
            approved_by=actor,
            force_mock=True,
            provider_override=provider_impl,
            commit=False,
        )
        intent = await approve_and_create_intent(db, str(approval.id), actor)
    result = await execute_intent(
        db,
        intent_id=str(intent.id),
        actor=actor,
        provider_impl=provider_impl,
        verification_retries=retries,
    )
    await db.commit()
    return result, intent


async def main() -> None:
    db_path = os.environ["DATABASE_URL"]
    if os.path.exists("/tmp/smoke_execution.db"):
        os.remove("/tmp/smoke_execution.db")
    engine = create_async_engine(db_path, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        await seed_default_policies(db, actor="smoke")
        await db.commit()
        provider = MockExecutionProvider()

        # ---- 1. meta_budget_change_success
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1001", primary_action="REVIEW_SCALE", pct=15)
        result, _ = await run(db, provider, rec)
        record("meta_budget_change_success", result.get("ok") and result.get("verification") == "MATCHED", str(result.get("code", "")))
        record("meta_budget_value", abs(provider.store["meta_campaigns"]["camp_1001"]["budget"] - 115.0) < 0.001, str(provider.store["meta_campaigns"]["camp_1001"]["budget"]))

        # ---- 2. meta_budget_state_drift
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1001", primary_action="REVIEW_SCALE", pct=10)
        approval, _ = await create_approval_from_recommendation(
            db, recommendation_id=str(rec.id), approved_by="tester", force_mock=True, provider_override=provider, commit=False
        )
        provider.store["meta_campaigns"]["camp_1001"]["budget"] = 150  # external manual change
        intent = await approve_and_create_intent(db, str(approval.id), "tester")
        result = await execute_intent(db, intent_id=str(intent.id), actor="tester", provider_impl=provider, verification_retries=(0,))
        await db.commit()
        record("meta_budget_state_drift", result.get("code") == "STATE_DRIFT", str(result.get("code")))
        provider.store["meta_campaigns"]["camp_1001"]["budget"] = 115.0

        # Permissive Meta policy (cooldown 0) so later Meta scenarios are isolated.
        db.add(
            ExecutionPolicy(
                workspace_id=None,
                name="Meta smoke permissive v2",
                provider="META",
                action_type="META_CHANGE_BUDGET",
                mode="manual",
                max_risk_level="CRITICAL",
                min_confidence=0.5,
                max_change_pct=50.0,
                max_actions_per_hour=100,
                max_actions_per_day=100,
                max_total_budget_change_pct_per_day=500.0,
                allowed_scope={"all": True},
                require_fresh_data_minutes=1440,
                cooldown_minutes=0,
                max_affected_campaigns=5,
                enabled=True,
                version=2,
                created_by="smoke",
            )
        )
        await db.commit()

        # ---- 3. meta_pause_success
        rec = await make_rec(db, platform="META_ADS", entity_type="AD", entity_id="ad_3001", primary_action="REVIEW_PAUSE")
        result, _ = await run(db, provider, rec)
        record("meta_pause_success", result.get("ok") and provider.store["meta_ads"]["ad_3001"]["status"] == "PAUSED", str(result.get("code", "")))

        # ---- 4. meta_pause_already_paused (NOOP)
        rec = await make_rec(db, platform="META_ADS", entity_type="AD", entity_id="ad_3001", primary_action="REVIEW_PAUSE")
        result, _ = await run(db, provider, rec)
        record("meta_pause_already_paused", result.get("ok"), "desired state already satisfied (NOOP)")

        # ---- 5. meta_timeout_unknown_outcome
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1001", primary_action="REVIEW_SCALE", pct=10)
        result, _ = await run(
            db,
            provider,
            rec,
            direct={
                "action_type": "META_CHANGE_BUDGET",
                "requested_change": {"_expiry_hours": 4, "simulate_timeout": True, "confidence": 0.9},
            },
        )
        record("meta_timeout_unknown_outcome", result.get("code") == "PROVIDER_OUTCOME_UNKNOWN", str(result.get("code")))

        # ---- 5b. unknown outcome resolved to success after re-read
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1001", primary_action="REVIEW_SCALE", pct=10)
        result, _ = await run(
            db,
            provider,
            rec,
            direct={
                "action_type": "META_CHANGE_BUDGET",
                "requested_change": {"_expiry_hours": 4, "simulate_timeout_after_mutation": True, "confidence": 0.9},
            },
        )
        record("meta_timeout_resolved_success", result.get("ok"), str(result.get("verification", "")))

        # ---- 6. google_budget_change_success
        rec = await make_rec(db, platform="GOOGLE_ADS", entity_type="CAMPAIGN", entity_id="camp_g1001", primary_action="REVIEW_SCALE", pct=10)
        result, _ = await run(db, provider, rec)
        budget = provider.store["google_budgets"]["customers/1/campaignBudgets/5001"]
        record("google_budget_change_success", result.get("ok") and budget["amount_micros"] == 110_000_000, str(result.get("code", "")))

        # ---- 7. google_shared_budget_block (default conservative policy)
        rec = await make_rec(db, platform="GOOGLE_ADS", entity_type="CAMPAIGN", entity_id="camp_g1002", primary_action="REVIEW_SCALE", pct=10)
        result, _ = await run(db, provider, rec)
        record("google_shared_budget_block", result.get("code") == "SHARED_BUDGET_SCOPE_UNAPPROVED", str(result.get("code")))

        # ---- 8. google_shared_budget_explicit_approval (policy v2 allows 2 campaigns)
        db.add(
            ExecutionPolicy(
                workspace_id=None,
                name="Google shared budget - smoke",
                provider="GOOGLE_ADS",
                action_type="GOOGLE_CHANGE_BUDGET",
                mode="manual",
                max_risk_level="CRITICAL",
                min_confidence=0.5,
                max_change_pct=20.0,
                max_actions_per_hour=100,
                max_actions_per_day=100,
                max_total_budget_change_pct_per_day=100.0,
                allowed_scope={"all": True},
                require_fresh_data_minutes=1440,
                cooldown_minutes=0,
                max_affected_campaigns=5,
                auto_execution_eligible=False,
                standing_approval=False,
                canary_scope=None,
                enabled=True,
                version=2,
                created_by="smoke",
            )
        )
        await db.commit()
        rec = await make_rec(db, platform="GOOGLE_ADS", entity_type="CAMPAIGN", entity_id="camp_g1002", primary_action="REVIEW_SCALE", pct=10)
        result, _ = await run(
            db,
            provider,
            rec,
            direct={
                "action_type": "GOOGLE_CHANGE_BUDGET",
                "requested_change": {"_expiry_hours": 4, "shared_budget_explicitly_approved": True, "confidence": 0.9},
            },
        )
        record("google_shared_budget_explicit_approval", result.get("ok"), str(result.get("code", "")))

        # ---- 9. google_pause_success
        rec = await make_rec(db, platform="GOOGLE_ADS", entity_type="CAMPAIGN", entity_id="camp_g1001", primary_action="REVIEW_PAUSE")
        result, _ = await run(db, provider, rec)
        record("google_pause_success", result.get("ok") and provider.store["google_campaigns"]["camp_g1001"]["status"] == "PAUSED", str(result.get("code", "")))
        provider.store["google_campaigns"]["camp_g1001"]["status"] = "ENABLED"

        # ---- 10. google_negative_keyword_success
        db.add(
            ExecutionPolicy(
                workspace_id=None,
                name="Google negative - smoke",
                provider="GOOGLE_ADS",
                action_type="GOOGLE_ADD_NEGATIVE_KEYWORD",
                mode="manual",
                max_risk_level="CRITICAL",
                min_confidence=0.5,
                max_actions_per_hour=100,
                max_actions_per_day=100,
                max_total_budget_change_pct_per_day=100.0,
                allowed_scope={"all": True},
                require_fresh_data_minutes=1440,
                cooldown_minutes=0,
                max_affected_campaigns=5,
                enabled=True,
                version=2,
                created_by="smoke",
            )
        )
        await db.commit()
        rec = await make_rec(db, platform="GOOGLE_ADS", entity_type="CAMPAIGN", entity_id="camp_g1001", primary_action="REVIEW_PAUSE")
        result, _ = await run(
            db,
            provider,
            rec,
            direct={
                "action_type": "GOOGLE_ADD_NEGATIVE_KEYWORD",
                "requested_change": {
                    "_expiry_hours": 24,
                    "keyword_text": "free shoes",
                    "match_type": "EXACT",
                    "scope": "CAMPAIGN",
                    "target_resource": "customers/1/campaigns/1",
                    "campaign_id": "camp_g1001",
                    "confidence": 0.9,
                },
            },
        )
        record("google_negative_keyword_success", result.get("ok"), str(result.get("code", "")))

        # ---- 11. google_negative_keyword_duplicate_noop
        rec = await make_rec(db, platform="GOOGLE_ADS", entity_type="CAMPAIGN", entity_id="camp_g1001", primary_action="REVIEW_PAUSE")
        result, _ = await run(
            db,
            provider,
            rec,
            direct={
                "action_type": "GOOGLE_ADD_NEGATIVE_KEYWORD",
                "requested_change": {
                    "_expiry_hours": 24,
                    "keyword_text": "free shoes",
                    "match_type": "EXACT",
                    "scope": "CAMPAIGN",
                    "target_resource": "customers/1/campaigns/1",
                    "campaign_id": "camp_g1001",
                    "confidence": 0.9,
                },
            },
        )
        record("google_negative_keyword_duplicate_noop", result.get("ok"), str(result.get("code", "")))

        # ---- 12. google_negative_keyword_wrong_scope_block
        rec = await make_rec(db, platform="GOOGLE_ADS", entity_type="CAMPAIGN", entity_id="camp_g1001", primary_action="REVIEW_PAUSE")
        result, _ = await run(
            db,
            provider,
            rec,
            direct={
                "action_type": "GOOGLE_ADD_NEGATIVE_KEYWORD",
                "requested_change": {
                    "_expiry_hours": 24,
                    "keyword_text": "bad keyword",
                    "match_type": "EXACT",
                    "scope": "GARBAGE",
                    "target_resource": "x",
                    "campaign_id": "camp_g1001",
                    "confidence": 0.9,
                },
            },
        )
        record("google_negative_keyword_wrong_scope_block", result.get("code") == "ACTION_NOT_ALLOWED", str(result.get("code")))

        # ---- 13. approval_expired
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        result, _ = await run(
            db,
            provider,
            rec,
            direct={"action_type": "META_CHANGE_BUDGET", "requested_change": {"_expiry_hours": -1, "confidence": 0.9}},
        )
        record("approval_expired", result.get("code") == "APPROVAL_EXPIRED", str(result.get("code")))

        # ---- 14. approval_payload_mismatch (intent tampered after freeze)
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        approval, _ = await create_approval_from_recommendation(
            db, recommendation_id=str(rec.id), approved_by="tester", force_mock=True, provider_override=provider, commit=False
        )
        intent = await approve_and_create_intent(db, str(approval.id), "tester")
        intent.requested_change = {**intent.requested_change, "proposed_budget": "9999"}
        await db.flush()
        result = await execute_intent(db, intent_id=str(intent.id), actor="tester", provider_impl=provider, verification_retries=(0,))
        await db.commit()
        record("approval_payload_mismatch", result.get("code") == "APPROVAL_MISMATCH", str(result.get("code")))

        # ---- 15. kill_switch_block
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        db.add(ExecutionKillSwitch(scope_type="GLOBAL", scope_id=None, enabled=True, reason="smoke", activated_by="smoke"))
        await db.commit()
        result, _ = await run(db, provider, rec)
        record("kill_switch_block", result.get("code") == "KILL_SWITCH_ACTIVE", str(result.get("code")))
        switch = (await db.execute(select(ExecutionKillSwitch).where(ExecutionKillSwitch.scope_type == "GLOBAL"))).scalar_one()
        switch.enabled = False
        await db.commit()

        # ---- 16. daily_change_limit_block
        db.add(
            ExecutionPolicy(
                workspace_id=None,
                name="Meta daily cap - smoke",
                provider="META",
                action_type="META_CHANGE_BUDGET",
                mode="manual",
                max_risk_level="HIGH",
                min_confidence=0.5,
                max_change_pct=20.0,
                max_actions_per_hour=100,
                max_actions_per_day=100,
                max_total_budget_change_pct_per_day=5.0,
                allowed_scope={"all": True},
                require_fresh_data_minutes=1440,
                cooldown_minutes=0,
                max_affected_campaigns=5,
                enabled=True,
                version=3,
                created_by="smoke",
            )
        )
        await db.commit()
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        result, _ = await run(db, provider, rec)
        record("daily_change_limit_block", result.get("code") == "DAILY_CUMULATIVE_LIMIT_EXCEEDED", str(result.get("code")))
        # Restore a permissive Meta policy for the remaining scenarios.
        db.add(
            ExecutionPolicy(
                workspace_id=None,
                name="Meta smoke permissive",
                provider="META",
                action_type="META_CHANGE_BUDGET",
                mode="manual",
                max_risk_level="CRITICAL",
                min_confidence=0.5,
                max_change_pct=50.0,
                max_actions_per_hour=100,
                max_actions_per_day=100,
                max_total_budget_change_pct_per_day=500.0,
                allowed_scope={"all": True},
                require_fresh_data_minutes=1440,
                cooldown_minutes=0,
                max_affected_campaigns=5,
                enabled=True,
                version=4,
                created_by="smoke",
            )
        )
        await db.commit()

        # ---- 17. cooldown_block
        db.add(
            ExecutionPolicy(
                workspace_id=None,
                name="Google cooldown - smoke",
                provider="GOOGLE_ADS",
                action_type="GOOGLE_CHANGE_BUDGET",
                mode="manual",
                max_risk_level="HIGH",
                min_confidence=0.5,
                max_change_pct=20.0,
                max_actions_per_hour=100,
                max_actions_per_day=100,
                max_total_budget_change_pct_per_day=100.0,
                allowed_scope={"all": True},
                require_fresh_data_minutes=1440,
                cooldown_minutes=1440,
                max_affected_campaigns=5,
                enabled=True,
                version=3,
                created_by="smoke",
            )
        )
        await db.commit()
        rec = await make_rec(db, platform="GOOGLE_ADS", entity_type="CAMPAIGN", entity_id="camp_g1003", primary_action="REVIEW_SCALE", pct=5)
        result, _ = await run(db, provider, rec)
        record("cooldown_first_ok", result.get("ok"))
        result, _ = await run(db, provider, rec)
        record("cooldown_block", result.get("code") == "COOLDOWN_ACTIVE", str(result.get("code")))

        # ---- 18. tracking_anomaly_block
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        db.add(DataQualityIssue(rule_code="TRACKING_ANOMALY", severity="CRITICAL", entity_type="CAMPAIGN", entity_id="camp_1002", status="OPEN", message="smoke"))
        await db.commit()
        result, _ = await run(db, provider, rec)
        record("tracking_anomaly_block", result.get("code") == "TRACKING_ANOMALY_ACTIVE", str(result.get("code")))
        issue = (await db.execute(select(DataQualityIssue).order_by(DataQualityIssue.created_at.desc()).limit(1))).scalar_one()
        issue.status = "RESOLVED"
        await db.commit()

        # ---- 19. experiment_protection_block
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        db.add(ActiveExperiment(name="smoke exp", platform="META", scope_type="CAMPAIGN", scope_id="camp_1002", status="ACTIVE"))
        await db.commit()
        result, _ = await run(db, provider, rec)
        record("experiment_protection_block", result.get("code") == "EXPERIMENT_PROTECTED", str(result.get("code")))
        exp = (await db.execute(select(ActiveExperiment).order_by(ActiveExperiment.created_at.desc()).limit(1))).scalar_one()
        exp.status = "ENDED"
        await db.commit()

        # ---- 20. provider_validate_fail
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        result, _ = await run(
            db,
            provider,
            rec,
            direct={
                "action_type": "META_CHANGE_BUDGET",
                "requested_change": {"_expiry_hours": 4, "simulate_validate_fail": True, "confidence": 0.9},
            },
        )
        record("provider_validate_fail", result.get("code") == "PROVIDER_VALIDATE_FAILED", str(result.get("code")))

        # ---- 21. verification_fail + compensation_budget
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        result, _ = await run(
            db,
            provider,
            rec,
            direct={
                "action_type": "META_CHANGE_BUDGET",
                "requested_change": {"_expiry_hours": 4, "simulate_verification_failure": True, "confidence": 0.9},
            },
        )
        record("verification_fail", result.get("code") == "VERIFICATION_FAILED", str(result.get("code")))
        job = (await db.execute(select(ExecutionJob).order_by(ExecutionJob.created_at.desc()).limit(1))).scalar_one()
        comp = (
            await db.execute(
                select(ExecutionCompensation).where(ExecutionCompensation.execution_job_id == job.id)
            )
        ).scalars().all()
        record("compensation_budget_plan", any(c.compensation_type == "RESTORE_BUDGET" for c in comp), str([c.compensation_type for c in comp]))
        if comp:
            comp_record = await approve_compensation(db, str(comp[0].id), "tester")
            result_comp = await run_compensation(db, compensation=comp_record, provider_impl=provider, actor="tester")
            await db.commit()
            record("compensation_budget_run", result_comp.get("ok"), str(result_comp.get("error", "")))
            record("compensation_budget_restored", abs(provider.store["meta_adsets"]["adset_2001"]["daily_budget"] - 80.0) < 0.001, str(provider.store["meta_adsets"]["adset_2001"]["daily_budget"]))

        # ---- 22. compensation_negative_keyword
        rec = await make_rec(db, platform="GOOGLE_ADS", entity_type="CAMPAIGN", entity_id="camp_g1001", primary_action="REVIEW_PAUSE")
        result, _ = await run(
            db,
            provider,
            rec,
            direct={
                "action_type": "GOOGLE_ADD_NEGATIVE_KEYWORD",
                "requested_change": {
                    "_expiry_hours": 24,
                    "keyword_text": "to be removed",
                    "match_type": "EXACT",
                    "scope": "CAMPAIGN",
                    "target_resource": "customers/1/campaigns/1",
                    "campaign_id": "camp_g1001",
                    "simulate_verification_failure": True,
                    "confidence": 0.9,
                },
            },
        )
        job = (await db.execute(select(ExecutionJob).order_by(ExecutionJob.created_at.desc()).limit(1))).scalar_one()
        comps = (
            await db.execute(select(ExecutionCompensation).where(ExecutionCompensation.execution_job_id == job.id))
        ).scalars().all()
        record("compensation_negative_keyword_plan", any(c.compensation_type == "REMOVE_CREATED_NEGATIVE" for c in comps), str([c.compensation_type for c in comps]))
        if comps:
            comp_record = await approve_compensation(db, str(comps[0].id), "tester")
            comp_result = await run_compensation(db, compensation=comp_record, provider_impl=provider, actor="tester")
            await db.commit()
            removed = all(
                value.get("keyword_text") != "to be removed"
                for value in provider.store["google_negatives"].values()
            )
            record("compensation_negative_keyword_run", comp_result.get("ok") and removed, str(comp_result.get("error", "")))

        # ---- 23. manual_external_change_drift
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        result, intent = await run(db, provider, rec)
        # rebuild then insert manual change event before execution
        rec2 = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        approval, _ = await create_approval_from_recommendation(
            db, recommendation_id=str(rec2.id), approved_by="tester", force_mock=True, provider_override=provider, commit=False
        )
        intent2 = await approve_and_create_intent(db, str(approval.id), "tester")
        db.add(
            EntityChangeEvent(
                platform="META",
                entity_type="CAMPAIGN",
                entity_id="camp_1002",
                change_type="BUDGET_CHANGED",
                occurred_at=datetime.now(timezone.utc) + timedelta(seconds=2),
                meta={"source": "EXTERNAL_MANUAL"},
            )
        )
        await db.commit()
        result = await execute_intent(db, intent_id=str(intent2.id), actor="tester", provider_impl=provider, verification_retries=(0,))
        await db.commit()
        record("manual_external_change_drift", result.get("code") == "STATE_DRIFT", str(result.get("code")))
        # Clean up the manual-change event so later scenarios are unaffected.
        event = (await db.execute(select(EntityChangeEvent).order_by(EntityChangeEvent.occurred_at.desc()).limit(1))).scalar_one()
        await db.delete(event)
        await db.commit()

        # ---- 24. duplicate_idempotency
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        result, intent = await run(db, provider, rec)
        record("duplicate_first_ok", result.get("ok"))
        result2 = await execute_intent(db, intent_id=str(intent.id), actor="tester", provider_impl=provider, verification_retries=(0,))
        await db.commit()
        record("duplicate_idempotency", result2.get("code") == "ALREADY_EXECUTED", str(result2.get("code")))

        # ---- 25. approval revoke blocks execution
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        approval, _ = await create_approval_from_recommendation(
            db, recommendation_id=str(rec.id), approved_by="tester", force_mock=True, provider_override=provider, commit=False
        )
        await revoke_approval(db, str(approval.id), "tester", reason="smoke revoke")
        await db.commit()
        try:
            intent = await approve_and_create_intent(db, str(approval.id), "tester")
            record("approval_revoke_blocks", False, "revoked approval was still usable")
        except ValueError:
            record("approval_revoke_blocks", True, "revoked approval rejected")

        # ---- 26. shadow execution (would-execute, no write)
        rec = await make_rec(db, platform="META_ADS", entity_type="CAMPAIGN", entity_id="camp_1002", primary_action="REVIEW_SCALE", pct=10)
        approval, _ = await create_approval_from_recommendation(
            db, recommendation_id=str(rec.id), approved_by="tester", force_mock=True, provider_override=provider, commit=False
        )
        intent = await approve_and_create_intent(db, str(approval.id), "tester")
        before = provider.store["meta_adsets"]["adset_2001"]["daily_budget"]
        result = await execute_intent(db, intent_id=str(intent.id), actor="tester", provider_impl=provider, shadow=True, verification_retries=(0,))
        await db.commit()
        record("shadow_execution", result.get("ok") and provider.store["meta_adsets"]["adset_2001"]["daily_budget"] == before, str(result.get("code", "")))

    failed = [r for r in RESULTS if not r[1]]
    print("\n===== SMOKE EXECUTION SUMMARY =====")
    print(f"PASS: {len(RESULTS) - len(failed)}/{len(RESULTS)}")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAIL {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
