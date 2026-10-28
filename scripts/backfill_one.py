"""Run a chunked backfill for a provider."""

import asyncio
import os
import sys

os.environ.setdefault("DATA_PROVIDER_MODE", "mock")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.ingestion.backfill import run_backfill  # noqa: E402
from app.models.data_source import DataSource  # noqa: E402


async def main(provider: str, days: int) -> int:
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
        result = await run_backfill(db, source.provider, str(source.id), days)
        print(f"{provider} backfill: {result['chunk_count']} chunks")
        for chunk in result["chunks"]:
            print(f"  {chunk['range_start']}..{chunk['range_end']} -> {chunk['status']}")
        return 0


if __name__ == "__main__":
    days_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "META_ADS", days_arg)))
