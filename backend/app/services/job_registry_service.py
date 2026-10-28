"""Unified job registry + transactional outbox (review 4.6)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import JobAttempt, JobEvent, JobRun, OutboxMessage


async def start_job(
    db: AsyncSession,
    *,
    job_type: str,
    queue: str,
    idempotency_key: str,
    workspace_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
    max_attempts: int = 3,
) -> JobRun:
    existing = (await db.execute(select(JobRun).where(JobRun.idempotency_key == idempotency_key))).scalar_one_or_none()
    if existing is not None:
        return existing
    run = JobRun(
        workspace_id=workspace_id,
        job_type=job_type,
        queue=queue,
        idempotency_key=idempotency_key,
        trace_id=trace_id or uuid4().hex[:16],
        status="PENDING",
        payload=payload,
        max_attempts=max_attempts,
    )
    db.add(run)
    await db.flush()
    await log_event(db, job_run_id=str(run.id), event_type="JOB_CREATED", event_data={"job_type": job_type, "queue": queue})
    return run


async def start_attempt(db: AsyncSession, job_run: JobRun) -> JobAttempt:
    attempt_number = (job_run.meta or {}).get("attempt_count", 0) + 1
    job_run.status = "RUNNING"
    job_run.started_at = datetime.now(timezone.utc)
    job_run.meta = {**(job_run.meta or {}), "attempt_count": attempt_number}
    attempt = JobAttempt(job_run_id=str(job_run.id), attempt_number=attempt_number, status="RUNNING")
    db.add(attempt)
    await db.flush()
    await log_event(db, job_run_id=str(job_run.id), attempt_id=str(attempt.id), event_type="ATTEMPT_STARTED", event_data={"attempt": attempt_number})
    return attempt


async def complete_attempt(db: AsyncSession, job_run: JobRun, attempt: JobAttempt, result: Optional[Dict[str, Any]] = None) -> None:
    attempt.status = "SUCCEEDED"
    attempt.finished_at = datetime.now(timezone.utc)
    job_run.status = "SUCCEEDED"
    job_run.result = result
    job_run.finished_at = datetime.now(timezone.utc)
    await db.flush()
    await log_event(db, job_run_id=str(job_run.id), attempt_id=str(attempt.id), event_type="JOB_SUCCEEDED")


async def fail_attempt(
    db: AsyncSession,
    job_run: JobRun,
    attempt: JobAttempt,
    *,
    error_code: str,
    error_message: str,
    retry: bool = True,
) -> None:
    attempt.status = "FAILED"
    attempt.error_code = error_code
    attempt.error_message = error_message
    attempt.finished_at = datetime.now(timezone.utc)
    attempts = (job_run.meta or {}).get("attempt_count", 0)
    if retry and attempts < job_run.max_attempts:
        job_run.status = "PENDING"
    else:
        job_run.status = "FAILED"
        job_run.error_code = error_code
        job_run.error_message = error_message
        job_run.finished_at = datetime.now(timezone.utc)
    await db.flush()
    await log_event(db, job_run_id=str(job_run.id), attempt_id=str(attempt.id), event_type="ATTEMPT_FAILED", event_data={"error_code": error_code})


async def log_event(db: AsyncSession, *, job_run_id: str, attempt_id: Optional[str] = None, event_type: str, event_data: Optional[Dict[str, Any]] = None) -> None:
    db.add(JobEvent(job_run_id=job_run_id, attempt_id=attempt_id, event_type=event_type, event_data=event_data or {}))


async def list_job_runs(db: AsyncSession, *, workspace_id: Optional[str] = None, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    query = select(JobRun).order_by(JobRun.created_at.desc()).limit(limit)
    if workspace_id:
        query = query.where(JobRun.workspace_id == workspace_id)
    if status:
        query = query.where(JobRun.status == status)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(r.id),
            "workspace_id": r.workspace_id,
            "job_type": r.job_type,
            "queue": r.queue,
            "status": r.status,
            "trace_id": r.trace_id,
            "idempotency_key": r.idempotency_key,
            "error_code": r.error_code,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def enqueue_outbox(
    db: AsyncSession,
    *,
    aggregate_type: str,
    aggregate_id: str,
    message_type: str,
    payload: Dict[str, Any],
) -> OutboxMessage:
    message = OutboxMessage(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        message_type=message_type,
        payload=payload,
        status="PENDING",
    )
    db.add(message)
    await db.flush()
    return message
