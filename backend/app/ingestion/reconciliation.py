from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.orchestrator import run_sync


async def run_reconciliation(
    db: AsyncSession,
    provider: str,
    data_source_id: str,
    days: Optional[int] = None,
) -> dict:
    if provider == "SHOPIFY":
        job_type = "SHOPIFY_ORDER_RECONCILE"
    else:
        job_type = "PERFORMANCE_RECONCILE"
    end = date.today()
    start = end - timedelta(days=(days or 3) - 1)
    job = await run_sync(db, provider, data_source_id, job_type, start.isoformat(), end.isoformat())
    return {"id": str(job.id), "status": job.status, "range_start": job.range_start, "range_end": job.range_end}
