from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.ingestion.orchestrator import run_sync
from app.models.sync import SyncJob


async def run_backfill(
    db: AsyncSession,
    provider: str,
    data_source_id: str,
    days: Optional[int] = None,
) -> dict:
    days = days or settings.initial_backfill_days
    chunk_days = (
        settings.meta_backfill_chunk_days
        if provider == "META_ADS"
        else settings.google_backfill_chunk_days
        if provider == "GOOGLE_ADS"
        else 7
    )
    end = date.today()
    start = end - timedelta(days=days - 1)
    jobs: list = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        job: SyncJob = await run_sync(
            db,
            provider,
            data_source_id,
            "INITIAL_BACKFILL",
            cursor.isoformat(),
            chunk_end.isoformat(),
        )
        jobs.append({"id": str(job.id), "status": job.status, "range_start": job.range_start, "range_end": job.range_end})
        cursor = chunk_end + timedelta(days=1)
    return {"chunks": jobs, "chunk_count": len(jobs)}
