"""Seed 30 days of demo data through the real ETL pipeline (mock mode).

Usage:  DATABASE_URL=sqlite+aiosqlite:///./demo_data.db python scripts/seed_demo_data.py
"""

import asyncio
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./demo_data.db")
os.environ.setdefault("DATA_PROVIDER_MODE", "mock")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_fixtures  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.etl.pipeline import (  # noqa: E402
    run_google_pipeline,
    run_meta_pipeline,
    run_shopify_pipeline,
)
from app.models.data_source import DataSource  # noqa: E402
from app.models.mixins import new_uuid  # noqa: E402


async def main() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    rng = random.Random("demo-30d")
    days = 30
    meta = generate_fixtures.build_meta(days, rng, "healthy_growth")
    google = generate_fixtures.build_google(days, rng, "healthy_growth")
    shopify = generate_fixtures.build_shopify(days, rng, "healthy_growth")

    async with factory() as db:
        source_defs = {
            "META_ADS": DataSource(
                workspace_id="ws_main",
                provider="META_ADS",
                name="Meta Brand Main",
                external_account_id="act_987654321",
                api_version="v26.0",
                timezone="America/New_York",
                currency="USD",
                status="HEALTHY",
                meta={"scenario": "healthy_growth"},
            ),
            "GOOGLE_ADS": DataSource(
                workspace_id="ws_main",
                provider="GOOGLE_ADS",
                name="Google Brand Main",
                external_account_id="123-456-7890",
                api_version="v25",
                timezone="America/New_York",
                currency="USD",
                status="HEALTHY",
                meta={"scenario": "healthy_growth"},
            ),
            "SHOPIFY": DataSource(
                workspace_id="ws_main",
                provider="SHOPIFY",
                name="Example Store",
                external_account_id="shop.example.test",
                api_version="2026-07",
                timezone="America/New_York",
                currency="USD",
                status="HEALTHY",
                meta={"scenario": "healthy_growth"},
            ),
        }
        sources = {}
        for provider, definition in source_defs.items():
            existing = (
                await db.execute(
                    select(DataSource).where(
                        DataSource.provider == provider,
                        DataSource.external_account_id == definition.external_account_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                definition.id = new_uuid()
                db.add(definition)
                await db.flush()
                sources[provider] = definition
            else:
                sources[provider] = existing
        await db.flush()

        meta_counts = await run_meta_pipeline(
            db,
            str(sources["META_ADS"].id),
            accounts=meta["accounts"],
            campaigns=meta["campaigns"],
            ad_groups=meta["ad_groups"],
            ads=meta["ads"],
            creatives=meta["creatives"],
            performance=meta["performance"],
            sync_job_id="seed",
        )
        google_counts = await run_google_pipeline(
            db,
            str(sources["GOOGLE_ADS"].id),
            accounts=google["accounts"],
            campaigns=google["campaigns"],
            ad_groups=google["ad_groups"],
            ads=google["ads"],
            asset_groups=google["asset_groups"],
            keywords=google["keywords"],
            search_terms=google["search_terms"],
            conversion_actions=google["conversion_actions"],
            performance=google["performance"],
            sync_job_id="seed",
        )
        shopify_counts = await run_shopify_pipeline(
            db,
            str(sources["SHOPIFY"].id),
            products=shopify["products"],
            variants=shopify["variants"],
            orders=shopify["orders"],
            order_items=shopify["order_items"],
            refunds=shopify["refunds"],
            journeys=shopify["journeys"],
            sync_job_id="seed",
        )
        for source in sources.values():
            source.last_successful_sync_at = datetime.now(timezone.utc)
        await db.commit()

    print(f"seeded {days} days into {os.environ['DATABASE_URL']}")
    print(f"meta:    {meta_counts.inserted} inserted / {meta_counts.updated} updated / {meta_counts.failed} failed")
    print(f"google:  {google_counts.inserted} inserted / {google_counts.updated} updated / {google_counts.failed} failed")
    print(f"shopify: {shopify_counts.inserted} inserted / {shopify_counts.updated} updated / {shopify_counts.failed} failed")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
