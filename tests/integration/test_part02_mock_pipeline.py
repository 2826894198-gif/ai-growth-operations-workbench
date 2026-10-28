
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.ingestion.orchestrator import run_sync
from app.models.ad_performance import AdPerformanceDaily
from app.models.commerce import Order
from app.models.data_source import DataSource
from app.models.sync import SyncJob
from app.services.metrics_service import MetricsService

pytestmark = pytest.mark.integration


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_mock_providers_full_pipeline(db):
    sources = {
        "META_ADS": DataSource(provider="META_ADS", name="Mock Meta", external_account_id="act_x", meta={"scenario": "healthy_growth"}),
        "GOOGLE_ADS": DataSource(provider="GOOGLE_ADS", name="Mock Google", external_account_id="g_x", meta={"scenario": "healthy_growth"}),
        "SHOPIFY": DataSource(provider="SHOPIFY", name="Mock Shopify", external_account_id="s_x", meta={"scenario": "healthy_growth"}),
    }
    db.add_all(sources.values())
    await db.commit()
    for source in sources.values():
        await db.refresh(source)

    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=2)).isoformat()
    end = today.isoformat()
    for provider, source in sources.items():
        job = await run_sync(db, provider, str(source.id), "PERFORMANCE_INTRADAY", start, end)
        assert job.status in ("SUCCESS", "PARTIAL_SUCCESS"), job.error_message

    perf_rows = (await db.execute(select(func.count()).select_from(AdPerformanceDaily))).scalar_one()
    order_rows = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
    assert perf_rows > 0
    assert order_rows > 0

    overview = await MetricsService().overview(db, start, end)
    assert overview["paid_spend"] > 0
    assert overview["orders"] > 0

    jobs = (await db.execute(select(SyncJob))).scalars().all()
    assert len(jobs) == 3
    sources_refreshed = (await db.execute(select(DataSource))).scalars().all()
    assert all(s.last_successful_sync_at is not None for s in sources_refreshed)
