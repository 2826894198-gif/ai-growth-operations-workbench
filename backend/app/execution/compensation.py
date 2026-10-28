"""Compensation builders + manual/auto compensation execution (PART 06 §99-§106)."""

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution.actions.registry import get_action_spec
from app.models.execution import ExecutionCompensation, ExecutionJob


async def build_compensation_plan(
    db: AsyncSession,
    *,
    provider_impl,
    job: ExecutionJob,
    intent,
    actor: str = "system",
) -> Dict[str, Any]:
    """Build a compensation plan and persist PENDING compensation records."""
    spec = get_action_spec(job.action_type)
    eligibility = spec.compensatable if spec else "NON_COMPENSATABLE"
    before_state = job.before_state or {}
    after_state = job.after_state or {}
    plan_items = await provider_impl.build_compensation(intent, before_state, after_state)
    records = []
    for item in plan_items:
        record = ExecutionCompensation(
            execution_job_id=str(job.id),
            compensation_type=item.get("compensation_type", "COMPENSATION"),
            provider=job.provider,
            action_type=item.get("action_type", job.action_type),
            entity_type=job.entity_type,
            entity_id=job.entity_id,
            before_state=before_state,
            target_state=item.get("target_state") or {},
            status="PENDING",
            provider_resource_name=item.get("provider_resource_name"),
        )
        db.add(record)
        records.append(record)
    await db.flush()
    return {
        "eligibility": eligibility,
        "plan": plan_items,
        "records": records,
        "auto_compensatable": False,
        "note": "compensation is manual by default (EXECUTION_AUTO_COMPENSATION=false)",
    }


async def approve_compensation(db: AsyncSession, compensation_id: str, actor: str) -> ExecutionCompensation:
    compensation = (
        await db.execute(select(ExecutionCompensation).where(ExecutionCompensation.id == compensation_id))
    ).scalar_one_or_none()
    if compensation is None:
        raise ValueError("compensation not found")
    compensation.status = "APPROVED"
    compensation.approved_by = actor
    await db.flush()
    return compensation


async def run_compensation(
    db: AsyncSession,
    *,
    compensation: ExecutionCompensation,
    provider_impl,
    actor: str,
) -> Dict[str, Any]:
    """Execute one approved compensation record against the provider."""
    if compensation.status not in ("APPROVED", "PENDING"):
        raise ValueError(f"compensation cannot run from status {compensation.status}")
    compensation.status = "RUNNING"
    compensation.started_at = datetime.now(timezone.utc)
    await db.flush()
    try:
        job = (
            await db.execute(select(ExecutionJob).where(ExecutionJob.id == compensation.execution_job_id))
        ).scalar_one_or_none()
        target = compensation.target_state or {}
        fake_intent = _compensation_intent(job, compensation, target)
        current = await provider_impl.get_current_state(fake_intent)
        result = await provider_impl.execute(fake_intent, current)
        if result.status != "SUCCESS":
            raise RuntimeError(result.error_message or "compensation provider execution failed")
        verification = await provider_impl.verify(fake_intent, current, target)
        if verification.get("result") != "MATCHED":
            raise RuntimeError("compensation verification did not match")
        compensation.status = "SUCCEEDED"
        compensation.provider_request_id = result.provider_request_id
        compensation.finished_at = datetime.now(timezone.utc)
        await db.flush()
        return {"ok": True, "compensation_id": str(compensation.id), "provider_request_id": result.provider_request_id}
    except Exception as exc:  # noqa: BLE001
        compensation.status = "FAILED"
        compensation.error = str(exc)
        compensation.finished_at = datetime.now(timezone.utc)
        await db.flush()
        return {"ok": False, "compensation_id": str(compensation.id), "error": str(exc)}


def _compensation_intent(job: ExecutionJob, compensation: ExecutionCompensation, target: Dict[str, Any]):
    """Build a lightweight intent-like object from stored compensation data."""
    from types import SimpleNamespace

    return SimpleNamespace(
        id=f"comp-{job.intent_id}",
        provider=job.provider,
        action_type=compensation.action_type,
        entity_type=job.entity_type,
        entity_id=job.entity_id,
        external_entity_id=job.external_entity_id,
        requested_change=target,
        expected_before_state=None,
        workspace_id=None,
    )
