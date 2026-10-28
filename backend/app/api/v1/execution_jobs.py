"""Execution jobs API (PART 06 §137)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.execution_permissions import require_permission
from app.core.database import get_db
from app.execution.compensation import approve_compensation, run_compensation
from app.execution.engine import execute_intent
from app.execution.providers.factory import get_execution_provider
from app.models.execution import ExecutionCompensation, ExecutionEvent, ExecutionJob

router = APIRouter()


class JobAction(BaseModel):
    actor: str = "operator"


def _job_dict(job: ExecutionJob) -> dict:
    return {
        "id": str(job.id),
        "intent_id": job.intent_id,
        "approval_id": job.approval_id,
        "provider": job.provider,
        "action_type": job.action_type,
        "entity_type": job.entity_type,
        "entity_id": job.entity_id,
        "status": job.status,
        "attempt": job.attempt,
        "provider_request_id": job.provider_request_id,
        "provider_resource_name": job.provider_resource_name,
        "before_state": job.before_state,
        "requested_state": job.requested_state,
        "after_state": job.after_state,
        "revalidation_result": job.revalidation_result,
        "provider_validation_result": job.provider_validation_result,
        "verification_result": job.verification_result,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "shadow_only": job.shadow_only,
    }


@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(ExecutionJob).order_by(ExecutionJob.created_at.desc()).limit(limit)
    if status:
        query = query.where(ExecutionJob.status == status)
    if provider:
        query = query.where(ExecutionJob.provider == provider.upper())
    if entity_id:
        query = query.where(ExecutionJob.entity_id == entity_id)
    rows = (await db.execute(query)).scalars().all()
    return [_job_dict(r) for r in rows]


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(ExecutionJob).where(ExecutionJob.id == job_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    events = (
        await db.execute(select(ExecutionEvent).where(ExecutionEvent.job_id == job_id).order_by(ExecutionEvent.created_at))
    ).scalars().all()
    compensations = (
        await db.execute(select(ExecutionCompensation).where(ExecutionCompensation.execution_job_id == job_id))
    ).scalars().all()
    return {
        **_job_dict(job),
        "events": [
            {"event_type": e.event_type, "event_data": e.event_data, "actor": e.actor, "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in events
        ],
        "compensations": [
            {
                "id": str(c.id),
                "compensation_type": c.compensation_type,
                "status": c.status,
                "target_state": c.target_state,
                "provider_resource_name": c.provider_resource_name,
                "error": c.error,
            }
            for c in compensations
        ],
    }


@router.post("/jobs/{job_id}/retry", dependencies=[Depends(require_permission("EXECUTION_APPROVE"))])
async def retry_job(job_id: str, data: JobAction = None, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(ExecutionJob).where(ExecutionJob.id == job_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status in ("SUCCEEDED", "RUNNING", "VERIFYING", "QUEUED"):
        raise HTTPException(status_code=409, detail=f"job cannot be retried from status {job.status}")
    result = await execute_intent(db, intent_id=job.intent_id, actor=data.actor if data else "operator")
    await db.commit()
    return result


@router.post("/jobs/{job_id}/compensate", dependencies=[Depends(require_permission("EXECUTION_COMPENSATE"))])
async def compensate_job(job_id: str, data: JobAction = None, db: AsyncSession = Depends(get_db)):
    compensations = (
        await db.execute(select(ExecutionCompensation).where(ExecutionCompensation.execution_job_id == job_id))
    ).scalars().all()
    if not compensations:
        raise HTTPException(status_code=404, detail="no compensation records for job")
    actor = data.actor if data else "operator"
    results = []
    for compensation in compensations:
        if compensation.status in ("SUCCEEDED", "FAILED"):
            results.append({"id": str(compensation.id), "status": compensation.status})
            continue
        compensation = await approve_compensation(db, str(compensation.id), actor)
        provider = get_execution_provider(compensation.provider)
        result = await run_compensation(db, compensation=compensation, provider_impl=provider, actor=actor)
        results.append(result)
    await db.commit()
    return {"job_id": job_id, "results": results}
