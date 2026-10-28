"""Execution worker tasks (queue: execution / compensation).

Run as a dedicated worker process:
    celery -A app.workers.celery_app worker -Q execution,compensation \
        -n execution-worker@%h --concurrency=2
"""

import asyncio
import logging

from app.core.database import async_session_factory
from app.execution.compensation import approve_compensation, run_compensation
from app.execution.engine import execute_intent
from app.execution.providers.factory import get_execution_provider
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="execution.run_job", bind=True, queue="execution")
def execution_run_job(self, intent_id: str, actor: str = "system") -> dict:
    async def _run() -> dict:
        async with async_session_factory() as db:
            return await execute_intent(db, intent_id=intent_id, actor=actor)

    return asyncio.run(_run())


@celery_app.task(name="execution.run_compensation", bind=True, queue="compensation")
def execution_run_compensation(self, compensation_id: str, actor: str = "system") -> dict:
    async def _run() -> dict:
        async with async_session_factory() as db:
            from sqlalchemy import select

            from app.models.execution import ExecutionCompensation

            compensation = (
                await db.execute(select(ExecutionCompensation).where(ExecutionCompensation.id == compensation_id))
            ).scalar_one_or_none()
            if compensation is None:
                return {"ok": False, "error": "compensation not found"}
            if compensation.status == "PENDING":
                compensation = await approve_compensation(db, compensation_id, actor)
            provider = get_execution_provider(compensation.provider)
            result = await run_compensation(db, compensation=compensation, provider_impl=provider, actor=actor)
            await db.commit()
            return result

    return asyncio.run(_run())
