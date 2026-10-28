"""Execution health endpoint (PART 06 §162)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.execution.kill_switch import list_active_kill_switches
from app.models.execution import ExecutionApproval, ExecutionJob

router = APIRouter()


@router.get("/execution/health")
async def execution_health(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    jobs_24h = (await db.execute(select(ExecutionJob).where(ExecutionJob.created_at >= day_ago))).scalars().all()
    succeeded = sum(1 for j in jobs_24h if j.status == "SUCCEEDED")
    failed = sum(1 for j in jobs_24h if j.status == "FAILED")
    unknown = sum(1 for j in jobs_24h if j.status == "UNKNOWN" or j.error_code in ("PROVIDER_TIMEOUT", "PROVIDER_OUTCOME_UNKNOWN"))
    verification_failures = sum(1 for j in jobs_24h if j.verification_result == "MISMATCHED")
    pending_approvals = (
        await db.execute(
            select(func.count(ExecutionApproval.id)).where(
                ExecutionApproval.status == "PENDING",
                ExecutionApproval.expires_at > now,
            )
        )
    ).scalar_one()
    switches = await list_active_kill_switches(db)
    total_jobs = len(jobs_24h)
    return {
        "execution_enabled": settings.execution_enabled,
        "execution_mode": settings.execution_mode,
        "global_kill_switch": settings.execution_global_kill_switch or any(s.scope_type == "GLOBAL" for s in switches),
        "active_kill_switches": [{"scope_type": s.scope_type, "scope_id": s.scope_id, "reason": s.reason} for s in switches],
        "meta_write_health": {"enabled": settings.meta_write_enabled, "status": "CONFIGURED" if settings.meta_write_enabled else "DISABLED"},
        "google_write_health": {
            "enabled": settings.google_ads_write_enabled,
            "status": "CONFIGURED" if settings.google_ads_write_enabled else "DISABLED",
        },
        "queue": {
            "execution": settings.execution_queue,
            "compensation": settings.execution_compensation_queue,
            "worker_concurrency": settings.execution_worker_concurrency,
        },
        "last_24h": {
            "total": total_jobs,
            "succeeded": succeeded,
            "failed": failed,
            "unknown_outcomes": unknown,
            "verification_failures": verification_failures,
            "failure_rate": round(failed / total_jobs, 4) if total_jobs else 0.0,
        },
        "pending_approvals": pending_approvals,
        "safety_slo": {
            "duplicate_live_mutation": "0 (enforced by idempotency)",
            "unauthorized_mutation": "0 (permission gated)",
            "execution_without_valid_approval": "0 (approval validation)",
            "unverified_successful_mutation": "0 (read-after-write required)",
        },
    }
