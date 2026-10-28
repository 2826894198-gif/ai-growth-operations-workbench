import asyncio
from datetime import date
from typing import Optional

from app.core.config import settings
from app.core.database import async_session_factory
from app.ingestion.backfill import run_backfill
from app.ingestion.orchestrator import run_sync
from app.ingestion.reconciliation import run_reconciliation
from app.workers.celery_app import celery_app


@celery_app.task(name="ingestion.run_sync_task", bind=True)
def run_sync_task(self, provider: str, source_id: str, job_type: str, days: Optional[int] = None) -> dict:
    async def _run() -> dict:
        async with async_session_factory() as db:
            if job_type in ("PERFORMANCE_RECONCILE", "SHOPIFY_ORDER_RECONCILE"):
                reconcile_days = days or (settings.shopify_reconcile_days if provider == "SHOPIFY" else 3)
                return await run_reconciliation(db, provider, source_id, reconcile_days)
            if job_type == "PERFORMANCE_INTRADAY":
                today = date.today().isoformat()
                job = await run_sync(db, provider, source_id, job_type, today, today)
            else:
                job = await run_sync(db, provider, source_id, job_type)
            return {"id": str(job.id), "status": job.status}

    return asyncio.run(_run())


@celery_app.task(name="ingestion.run_backfill_task", bind=True)
def run_backfill_task(self, provider: str, source_id: str, days: Optional[int] = None) -> dict:
    async def _run() -> dict:
        async with async_session_factory() as db:
            return await run_backfill(db, provider, source_id, days)

    return asyncio.run(_run())


def _enqueue_for_providers(providers: list, job_type: str, days: Optional[int] = None) -> None:
    from sqlalchemy import select

    from app.models.data_source import DataSource

    async def _dispatch() -> None:
        async with async_session_factory() as db:
            sources = (
                await db.execute(
                    select(DataSource).where(
                        DataSource.provider.in_(providers),
                        DataSource.sync_enabled.is_(True),
                    )
                )
            ).scalars().all()
        for source in sources:
            queue = {"META_ADS": "meta", "GOOGLE_ADS": "google", "SHOPIFY": "shopify"}.get(source.provider, "etl")
            celery_app.send_task(
                "ingestion.run_sync_task",
                args=[source.provider, str(source.id), job_type],
                kwargs={"days": days} if days else {},
                queue=queue,
            )

    asyncio.run(_dispatch())


@celery_app.task(name="ingestion.nightly_reconcile", bind=True)
def nightly_reconcile(self) -> None:
    _enqueue_for_providers(
        ["META_ADS", "GOOGLE_ADS", "SHOPIFY"],
        "PERFORMANCE_RECONCILE",
        settings.meta_nightly_reconcile_days,
    )


@celery_app.task(name="ingestion.weekly_reconcile", bind=True)
def weekly_reconcile(self) -> None:
    _enqueue_for_providers(["META_ADS", "GOOGLE_ADS"], "PERFORMANCE_RECONCILE", settings.meta_weekly_reconcile_days)
