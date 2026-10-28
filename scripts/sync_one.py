"""Run one intraday sync for a provider against its first enabled data source."""

import asyncio
import os
import sys
from datetime import date

os.environ.setdefault("DATA_PROVIDER_MODE", "mock")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.ingestion.orchestrator import run_sync  # noqa: E402
from app.models.data_source import DataSource  # noqa: E402


async def main(provider: str) -> int:
    async with async_session_factory() as db:
        source = (
            await db.execute(
                select(DataSource).where(
                    DataSource.provider == provider.upper(),
                    DataSource.sync_enabled.is_(True),
                ).order_by(DataSource.created_at.asc()).limit(1)
            )
        ).scalar_one_or_none()
        if source is None:
            print(f"no enabled {provider} data source found")
            return 1
        today = date.today().isoformat()
        job = await run_sync(db, source.provider, str(source.id), "PERFORMANCE_INTRADAY", today, today)
        print(f"{provider} sync job {job.id} status={job.status} inserted={job.records_inserted} updated={job.records_updated}")
        return 0 if job.status in ("SUCCESS", "PARTIAL_SUCCESS") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "META_ADS")))
