"""Execution engine — the only path from frozen intent to provider mutation.

Pipeline (PART 06 §202):
  Frozen Intent -> Fresh State -> Revalidation -> Policy -> Provider Validation
  -> Mutation -> Read-after-write -> Audit -> Compensation review
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.execution.approvals import consume_approval
from app.execution.audit import log_event, write_audit
from app.execution.bindings import validate_binding
from app.execution.compensation import build_compensation_plan, run_compensation
from app.execution.errors import ExecutionError
from app.execution.intents import get_intent
from app.execution.kill_switch import check_auto_kill_triggers, kill_switch_blocked
from app.execution.locks import lock_manager
from app.execution.outcomes import create_outcome
from app.execution.policies import evaluate_policy, primary_policy_code
from app.execution.preconditions import (
    check_action_allowed,
    check_duplicate,
    check_execution_enabled,
    check_mode,
    check_shared_budget_scope,
    check_write_enabled,
    validate_typed_schema,
)
from app.execution.providers.base import OperationResult, desired_state_matches
from app.execution.providers.factory import get_execution_provider
from app.execution.revalidation import revalidate
from app.execution.verification import verify_with_retry
from app.models.execution import ExecutionIntent, ExecutionJob
from app.models.rules import EntityChangeEvent, Recommendation

logger = logging.getLogger(__name__)


def _verification_retries() -> Sequence[float]:
    try:
        return tuple(float(x) for x in settings.execution_verification_retry_seconds.split(",") if x.strip())
    except ValueError:
        return (2.0, 5.0, 10.0)


async def execute_intent(
    db: AsyncSession,
    *,
    intent_id: str,
    actor: str = "system",
    provider_impl=None,
    shadow: bool = False,
    verification_retries: Optional[Sequence[float]] = None,
    auto_compensation: Optional[bool] = None,
    metrics_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the full execution lifecycle for one frozen intent."""
    metrics_context = metrics_context or {}
    intent = await get_intent(db, intent_id)
    if intent is None:
        raise ExecutionError("INTENT_NOT_FOUND", "execution intent not found")
    if shadow:
        intent.shadow_only = True
    verification_retries = verification_retries or _verification_retries()
    auto_compensation = settings.execution_auto_compensation if auto_compensation is None else auto_compensation

    duplicate = await check_duplicate(db, intent)
    if duplicate:
        await log_event(db, execution_id=intent_id, event_type="ALREADY_EXECUTED", event_data=duplicate, actor=actor)
        return {"ok": False, "code": duplicate["code"], "message": duplicate["message"], "intent_id": intent_id}

    blocked = check_execution_enabled() if not shadow else None
    if blocked:
        return {"ok": False, "code": blocked["code"], "message": blocked["message"], "intent_id": intent_id}

    mode_blocked = check_mode(settings.execution_mode) if not shadow else None
    if mode_blocked:
        return {"ok": False, "code": mode_blocked["code"], "message": mode_blocked["message"], "intent_id": intent_id}

    provider = provider_impl or get_execution_provider(intent.provider, force_mock=shadow)
    write_blocked = None if getattr(provider, "provider", "") == "MOCK" else check_write_enabled(intent.provider, shadow_only=shadow)
    action_blocked = check_action_allowed(intent.provider, intent.action_type)
    schema_blocked = validate_typed_schema(intent.action_type, intent.requested_change, intent.provider, entity_id=intent.entity_id)
    for check in (write_blocked, action_blocked, schema_blocked):
        if check:
            await log_event(db, execution_id=intent_id, event_type="BLOCKED", event_data=check, actor=actor)
            return {"ok": False, **check, "intent_id": intent_id}

    job = ExecutionJob(
        intent_id=intent_id,
        approval_id=intent.approval_id,
        provider=intent.provider,
        action_type=intent.action_type,
        entity_type=intent.entity_type,
        entity_id=intent.entity_id,
        external_entity_id=intent.external_entity_id,
        status="REVALIDATING",
        attempt=1,
        shadow_only=shadow,
    )
    db.add(job)
    await db.flush()
    intent.status = "EXECUTING"
    intent.updated_at = datetime.now(timezone.utc)
    await log_event(db, execution_id=intent_id, job_id=str(job.id), event_type="REVALIDATION_STARTED", actor=actor)

    try:
        # Read current provider state (pre-lock snapshot for lock resolution)
        try:
            initial_state = await provider.get_current_state(intent)
        except Exception as exc:  # noqa: BLE001
            await _fail_job(db, job, intent, code="PROVIDER_MUTATION_FAILED", message=f"state read failed: {exc}", actor=actor)
            return {"ok": False, "code": "PROVIDER_MUTATION_FAILED", "message": str(exc), "intent_id": intent_id}

        lock_resources = provider.resolve_lock_resources(intent, initial_state)
        async with lock_manager.locked(intent.provider, lock_resources):
            current_state = await provider.get_current_state(intent)
            job.before_state = current_state
            job.requested_state = intent.requested_change
            await db.flush()
            noop = desired_state_matches(current_state, intent.requested_change, intent.action_type)

            # Action package binding: entity/policy/credential/metric snapshot versions
            binding = validate_binding(
                intent=intent,
                workspace_id=intent.workspace_id,
                canonical_entity_id=intent.canonical_entity_id,
                action_type=intent.action_type,
                requested_change=intent.requested_change,
                policy_version=intent.execution_policy_version,
                credential_version=intent.credential_version,
                metric_snapshot_id=intent.metric_snapshot_id,
                approval_id=intent.approval_id,
            )
            if not binding["ok"]:
                await _fail_job(db, job, intent, code=binding["code"], message=binding["message"], actor=actor)
                return {"ok": False, **binding, "intent_id": intent_id}

            # Kill switch + revalidation + policy inside the lock
            kill = await kill_switch_blocked(
                db,
                provider=intent.provider,
                action_type=intent.action_type,
                account_id=intent.account_id,
                entity_id=intent.entity_id,
                workspace_id=intent.workspace_id,
            )
            if kill["ACTIVE"]:
                await _fail_job(db, job, intent, code="KILL_SWITCH_ACTIVE", message="kill switch active", actor=actor)
                return {"ok": False, "code": "KILL_SWITCH_ACTIVE", "message": "kill switch active", "intent_id": intent_id}

            revalidation = await revalidate(
                db,
                intent=intent,
                provider_state=current_state,
                kill_switch_active=kill["ACTIVE"],
                policy_context={"noop": noop},
            )
            job.revalidation_result = revalidation["result"]
            await db.flush()
            if revalidation["result"] != "PASS":
                await log_event(
                    db,
                    execution_id=intent_id,
                    job_id=str(job.id),
                    event_type="REVALIDATION_FAILED",
                    event_data={"result": revalidation["result"], "checks": revalidation["checks"]},
                    actor=actor,
                )
                code = _revalidation_code(revalidation)
                await _fail_job(db, job, intent, code=code, message=revalidation["result"], actor=actor)
                return {
                    "ok": False,
                    "code": code,
                    "message": revalidation["result"],
                    "revalidation": revalidation,
                    "intent_id": intent_id,
                }

            policy = await evaluate_policy(
                db,
                provider=intent.provider,
                action_type=intent.action_type,
                entity_id=intent.entity_id,
                risk_level=intent.risk_level,
                blast_radius=intent.blast_radius or "SMALL",
                confidence=await _intent_confidence(db, intent),
                requested_change=intent.requested_change,
                expected_before_state=intent.expected_before_state,
                affected_campaigns=(current_state or {}).get("reference_count", 1),
                workspace_id=intent.workspace_id,
                context={
                    "kill_switch_active": kill["ACTIVE"],
                    "data_fresh_minutes": None,
                    "shared_budget": bool((current_state or {}).get("explicitly_shared")),
                    "noop": noop,
                },
            )
            if not policy["allowed"]:
                await log_event(
                    db,
                    execution_id=intent_id,
                    job_id=str(job.id),
                    event_type="POLICY_BLOCKED",
                    event_data={"policy_reason_codes": policy["policy_reason_codes"]},
                    actor=actor,
                )
                await _fail_job(
                    db,
                    job,
                    intent,
                    code=primary_policy_code(policy["policy_reason_codes"]),
                    message="; ".join(policy["policy_reason_codes"]),
                    actor=actor,
                )
                return {"ok": False, "code": primary_policy_code(policy["policy_reason_codes"]), "policy": policy, "intent_id": intent_id}

            shared = check_shared_budget_scope(intent, current_state)
            if shared:
                await _fail_job(db, job, intent, code=shared["code"], message=shared["message"], actor=actor)
                return {"ok": False, **shared, "intent_id": intent_id}

            # Provider-side validation (Google validate_only where supported)
            job.status = "VALIDATING_PROVIDER"
            await log_event(db, execution_id=intent_id, job_id=str(job.id), event_type="PROVIDER_VALIDATION_STARTED", actor=actor)
            validation = await provider.validate_operation(intent, current_state)
            job.provider_validation_result = "PASSED" if validation.get("ok") else "FAILED"
            await db.flush()
            if not validation.get("ok"):
                await _fail_job(
                    db,
                    job,
                    intent,
                    code=validation.get("code", "PROVIDER_VALIDATE_FAILED"),
                    message=validation.get("message", "provider validation failed"),
                    actor=actor,
                )
                return {"ok": False, "code": validation.get("code", "PROVIDER_VALIDATE_FAILED"), "intent_id": intent_id}

            # Execute
            job.status = "RUNNING"
            job.started_at = datetime.now(timezone.utc)
            await db.flush()
            await log_event(db, execution_id=intent_id, job_id=str(job.id), event_type="EXECUTION_STARTED", actor=actor)
            if shadow:
                result = OperationResult(
                    provider=provider.provider,
                    operation_type=intent.action_type,
                    provider_request_id=f"shadow_{intent.id[:8]}",
                    provider_resource=intent.entity_id,
                    before_state=current_state,
                    requested_state=intent.requested_change,
                    provider_response={"shadow": True, "would_execute": True},
                    status="SUCCESS",
                    executed_at=datetime.now(timezone.utc).isoformat(),
                )
            else:
                try:
                    result = await provider.execute(intent, current_state)
                except TimeoutError as exc:
                    result = OperationResult(
                        provider=provider.provider,
                        operation_type=intent.action_type,
                        provider_request_id=f"timeout_{intent.id[:8]}",
                        provider_resource=intent.entity_id,
                        before_state=current_state,
                        requested_state=intent.requested_change,
                        status="UNKNOWN",
                        error_code="PROVIDER_TIMEOUT",
                        error_message=str(exc),
                        executed_at=datetime.now(timezone.utc).isoformat(),
                    )

            job.provider_request_id = result.provider_request_id
            job.provider_resource_name = result.provider_resource
            job.after_state = result.after_state
            await log_event(
                db,
                execution_id=intent_id,
                job_id=str(job.id),
                event_type="PROVIDER_RESPONSE",
                event_data={"status": result.status, "request_id": result.provider_request_id},
                actor=actor,
            )

            # Unknown outcome flow (PART 06 §S): read provider state first
            if result.status == "UNKNOWN" or result.error_code in ("PROVIDER_TIMEOUT", "PROVIDER_OUTCOME_UNKNOWN"):
                try:
                    check_state = await provider.get_current_state(intent)
                    already_done = desired_state_matches(check_state, intent.requested_change, intent.action_type)
                except Exception:  # noqa: BLE001
                    check_state = None
                    already_done = False
                if already_done:
                    result.status = "SUCCESS"
                    result.after_state = check_state
                    result.error_code = None
                    result.error_message = "unknown outcome resolved: desired state already present"
                else:
                    job.status = "UNKNOWN"
                    job.error_code = "PROVIDER_OUTCOME_UNKNOWN"
                    job.error_message = result.error_message or "provider outcome unknown after timeout"
                    job.finished_at = datetime.now(timezone.utc)
                    intent.status = "UNKNOWN"
                    await db.flush()
                    await log_event(
                        db,
                        execution_id=intent_id,
                        job_id=str(job.id),
                        event_type="UNKNOWN_OUTCOME",
                        event_data={"recheck": already_done},
                        actor=actor,
                    )
                    await _audit_and_compensation_review(db, job, intent, provider, result, {}, None, actor)
                    await check_auto_kill_triggers(db)
                    await db.commit()
                    return {"ok": False, "code": "PROVIDER_OUTCOME_UNKNOWN", "job_id": str(job.id), "intent_id": intent_id}

            if result.status == "FAILED":
                job.status = "FAILED"
                job.error_code = result.error_code or "PROVIDER_MUTATION_FAILED"
                job.error_message = result.error_message
                job.finished_at = datetime.now(timezone.utc)
                intent.status = "FAILED"
                await db.flush()
                await log_event(
                    db,
                    execution_id=intent_id,
                    job_id=str(job.id),
                    event_type="FAILED",
                    event_data={"error_code": job.error_code, "error_message": job.error_message},
                    actor=actor,
                )
                await _audit_and_compensation_review(db, job, intent, provider, result, {}, None, actor)
                await check_auto_kill_triggers(db)
                await db.commit()
                return {"ok": False, "code": job.error_code, "job_id": str(job.id), "intent_id": intent_id}

            # Verification: read-after-write with bounded retry
            job.status = "VERIFYING"
            await db.flush()
            await log_event(db, execution_id=intent_id, job_id=str(job.id), event_type="VERIFY_STARTED", actor=actor)
            verification = await verify_with_retry(provider, intent, intent.requested_change, verification_retries)
            job.verification_result = verification["result"]
            if shadow:
                verification = {"result": "MATCHED", "provider_state": current_state, "matched": True, "shadow": True}

            if verification["result"] == "MATCHED":
                job.status = "SUCCEEDED"
                job.after_state = verification.get("provider_state") or result.after_state
                job.finished_at = datetime.now(timezone.utc)
                intent.status = "SUCCEEDED"
                if not shadow:
                    await consume_approval(db, intent.approval_id, intent_id)
                    db.add(
                        EntityChangeEvent(
                            platform=intent.provider,
                            entity_type=intent.entity_type,
                            entity_id=intent.entity_id,
                            change_type=intent.action_type,
                            old_value=current_state,
                            new_value=verification.get("provider_state"),
                            meta={"source": "SYSTEM_EXECUTION", "execution_id": intent_id, "job_id": str(job.id)},
                        )
                    )
                await db.flush()
                await log_event(db, execution_id=intent_id, job_id=str(job.id), event_type="VERIFIED", event_data={"result": "MATCHED"}, actor=actor)
                await _audit_and_compensation_review(db, job, intent, provider, result, revalidation, verification, actor)
                await create_outcome(
                    db,
                    job_id=str(job.id),
                    intent_id=intent_id,
                    before_metrics=metrics_context.get("before_metrics"),
                    after_metrics=metrics_context.get("after_metrics"),
                    expected_signal=metrics_context.get("expected_signal"),
                    observed_signal={"action": intent.action_type},
                )
                await check_auto_kill_triggers(db)
                await db.commit()
                return {"ok": True, "job_id": str(job.id), "intent_id": intent_id, "verification": "MATCHED"}

            # Verification failed / unavailable -> failed + compensation review
            job.status = "FAILED" if verification["result"] == "MISMATCHED" else "UNKNOWN"
            job.error_code = "VERIFICATION_FAILED" if verification["result"] == "MISMATCHED" else "VERIFICATION_UNAVAILABLE"
            job.error_message = f"verification result: {verification['result']}"
            job.finished_at = datetime.now(timezone.utc)
            intent.status = job.status
            await db.flush()
            await log_event(
                db,
                execution_id=intent_id,
                job_id=str(job.id),
                event_type="FAILED" if job.status == "FAILED" else "UNKNOWN_OUTCOME",
                event_data={"verification": verification["result"]},
                actor=actor,
            )
            compensation = await _audit_and_compensation_review(
                db, job, intent, provider, result, revalidation, verification, actor
            )
            if auto_compensation and compensation and compensation.get("records"):
                for record in compensation["records"]:
                    await run_compensation(db, compensation=record, provider_impl=provider, actor=actor)
            await check_auto_kill_triggers(db)
            await db.commit()
            return {
                "ok": False,
                "code": job.error_code,
                "job_id": str(job.id),
                "intent_id": intent_id,
                "compensation_pending": bool(compensation and compensation.get("records")),
            }
    except ExecutionError as exc:
        await _fail_job(db, job, intent, code=exc.code, message=exc.message, actor=actor)
        await check_auto_kill_triggers(db)
        await db.commit()
        return {"ok": False, "code": exc.code, "message": exc.message, "intent_id": intent_id}
    except Exception as exc:  # noqa: BLE001
        logger.exception("execution engine error", extra={"intent_id": intent_id})
        await _fail_job(db, job, intent, code="PRECONDITION_FAILED", message=str(exc), actor=actor)
        await db.commit()
        return {"ok": False, "code": "PRECONDITION_FAILED", "message": str(exc), "intent_id": intent_id}


async def _fail_job(db: AsyncSession, job: ExecutionJob, intent: ExecutionIntent, *, code: str, message: str, actor: str) -> None:
    blocked_codes = (
        "KILL_SWITCH_ACTIVE",
        "SHARED_BUDGET_SCOPE_UNAPPROVED",
        "ACTION_NOT_ALLOWED",
        "STATE_DRIFT",
        "PRECONDITION_FAILED",
        "APPROVAL_EXPIRED",
        "APPROVAL_REVOKED",
        "APPROVAL_MISMATCH",
        "DATA_STALE",
        "CHANGE_LIMIT_EXCEEDED",
        "DAILY_CUMULATIVE_LIMIT_EXCEEDED",
        "RATE_LIMIT_EXCEEDED",
        "EXPERIMENT_PROTECTED",
        "TRACKING_ANOMALY_ACTIVE",
        "ACTION_RISK_TOO_HIGH",
        "COOLDOWN_ACTIVE",
        "BLAST_RADIUS_EXCEEDED",
        "RECOMMENDATION_SUPERSEDED",
        "HARD_SPEND_GUARD_ACTIVE",
        "APPROVAL_INVALID",
    )
    job.status = "BLOCKED" if code in blocked_codes else "FAILED"
    job.error_code = code
    job.error_message = message
    job.finished_at = datetime.now(timezone.utc)
    if intent.status in ("PENDING", "EXECUTING", "APPROVED"):
        intent.status = "FAILED" if job.status != "BLOCKED" else "BLOCKED"
    intent.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await log_event(
        db,
        execution_id=str(intent.id),
        job_id=str(job.id),
        event_type="REVALIDATION_FAILED" if code == "STATE_DRIFT" else "FAILED",
        event_data={"error_code": code, "error_message": message},
        actor=actor,
    )


async def _audit_and_compensation_review(
    db: AsyncSession,
    job: ExecutionJob,
    intent: ExecutionIntent,
    provider,
    result: OperationResult,
    revalidation: Dict[str, Any],
    verification: Optional[Dict[str, Any]],
    actor: str,
) -> Optional[Dict[str, Any]]:
    compensation = None
    if job.status in ("FAILED", "UNKNOWN") and result.status == "SUCCESS":
        compensation = await build_compensation_plan(db, provider_impl=provider, job=job, intent=intent, actor=actor)
    await write_audit(
        db,
        workspace_id=intent.workspace_id,
        recommendation_id=intent.recommendation_id,
        approval_id=intent.approval_id,
        intent_id=str(intent.id),
        job_id=str(job.id),
        policy_version=intent.execution_policy_version,
        provider=intent.provider,
        action_type=intent.action_type,
        entity_id=intent.entity_id,
        revalidation=revalidation or None,
        before_state=job.before_state,
        provider_request={"requested_change": intent.requested_change},
        provider_response=result.provider_response,
        after_state=job.after_state,
        verification=verification,
        compensation={"eligibility": compensation["eligibility"] if compensation else None, "plan": compensation["plan"] if compensation else None},
        actor=actor,
    )
    await db.flush()
    return compensation


async def dry_run_intent(db: AsyncSession, *, intent_id: str, actor: str = "api") -> Dict[str, Any]:
    """Dry-run / preview: everything except the provider mutation (PART 06 §140)."""
    intent = await get_intent(db, intent_id)
    if intent is None:
        raise ExecutionError("INTENT_NOT_FOUND", "execution intent not found")
    provider = get_execution_provider(intent.provider, force_mock=True)
    current_state = await provider.get_current_state(intent)
    revalidation = await revalidate(db, intent=intent, provider_state=current_state, kill_switch_active=False)
    policy = await evaluate_policy(
        db,
        provider=intent.provider,
        action_type=intent.action_type,
        entity_id=intent.entity_id,
        risk_level=intent.risk_level,
        blast_radius=intent.blast_radius or "SMALL",
        confidence=(intent.requested_change or {}).get("confidence", 0.0),
        requested_change=intent.requested_change,
        expected_before_state=intent.expected_before_state,
        affected_campaigns=(current_state or {}).get("reference_count", 1),
        workspace_id=intent.workspace_id,
        context={
            "kill_switch_active": False,
            "data_fresh_minutes": None,
            "shared_budget": bool((current_state or {}).get("explicitly_shared")),
        },
    )
    validation = await provider.validate_operation(intent, current_state)
    shared = check_shared_budget_scope(intent, current_state)
    return {
        "intent_id": intent_id,
        "current_state": current_state,
        "revalidation": revalidation,
        "policy": policy,
        "provider_validation": validation,
        "shared_budget_check": shared,
        "would_execute": revalidation["result"] == "PASS" and policy["allowed"] and validation.get("ok") and not shared,
        "provider_write_required": False,
    }


async def shadow_execute_intent(db: AsyncSession, *, intent_id: str, actor: str = "system") -> Dict[str, Any]:
    """Shadow execution: full lifecycle, no provider write (PART 06 §114)."""
    return await execute_intent(db, intent_id=intent_id, actor=actor, shadow=True)


async def _intent_confidence(db: AsyncSession, intent: ExecutionIntent) -> float:
    requested = intent.requested_change or {}
    if requested.get("confidence") is not None:
        return float(requested["confidence"])
    rec = (await db.execute(select(Recommendation).where(Recommendation.id == intent.recommendation_id))).scalar_one_or_none()
    return float(rec.confidence) if rec is not None and rec.confidence is not None else 0.0


def _revalidation_code(revalidation: Dict[str, Any]) -> str:
    """Map a failed revalidation check to its execution error code."""
    mapping = {
        "state_drift": "STATE_DRIFT",
        "tracking_anomaly": "TRACKING_ANOMALY_ACTIVE",
        "experiment_protection": "EXPERIMENT_PROTECTED",
        "data_fresh": "DATA_STALE",
        "hard_spend_guard": "HARD_SPEND_GUARD_ACTIVE",
        "kill_switch_inactive": "KILL_SWITCH_ACTIVE",
        "approval_valid": "APPROVAL_INVALID",
        "no_conflicting_execution": "RESOURCE_LOCKED",
        "recommendation_not_superseded": "RECOMMENDATION_SUPERSEDED",
        "no_manual_external_change": "STATE_DRIFT",
        "execution_cooldown": "COOLDOWN_ACTIVE",
        "promotion_mapping_valid": "STATE_DRIFT",
    }
    for check in revalidation.get("checks", []):
        if not check.get("ok") and check.get("severity") == "error":
            if check.get("name") == "approval_valid":
                detail = check.get("detail", "")
                if "expired" in detail:
                    return "APPROVAL_EXPIRED"
                if "revoked" in detail:
                    return "APPROVAL_REVOKED"
                if "does not match" in detail or "mismatch" in detail.lower():
                    return "APPROVAL_MISMATCH"
                return "APPROVAL_INVALID"
            return mapping.get(check.get("name"), "PRECONDITION_FAILED")
    return "PRECONDITION_FAILED"
