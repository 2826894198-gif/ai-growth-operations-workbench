import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.etl.pipeline import run_meta_pipeline
from app.models.ad_performance import AdPerformanceDaily
from app.models.marketing import Campaign


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
async def test_meta_pipeline_idempotent(db):
    from app.integrations.mock_provider import MockProvider

    provider = MockProvider("META_ADS", scenario="healthy_growth")
    accounts = await provider.sync_accounts()
    dims = await provider.sync_dimensions()
    performance = await provider.sync_performance("2026-08-01", "2026-08-03")

    first = await run_meta_pipeline(
        db, "ds1",
        accounts=accounts, campaigns=dims["campaigns"], ad_groups=dims["ad_groups"],
        ads=dims["ads"], creatives=dims["creatives"], performance=performance, sync_job_id="job-1",
    )
    await db.commit()
    campaign_count_1 = (await db.execute(select(func.count()).select_from(Campaign))).scalar_one()
    perf_count_1 = (await db.execute(select(func.count()).select_from(AdPerformanceDaily))).scalar_one()
    assert first.inserted > 0

    second = await run_meta_pipeline(
        db, "ds1",
        accounts=accounts, campaigns=dims["campaigns"], ad_groups=dims["ad_groups"],
        ads=dims["ads"], creatives=dims["creatives"], performance=performance, sync_job_id="job-2",
    )
    await db.commit()
    campaign_count_2 = (await db.execute(select(func.count()).select_from(Campaign))).scalar_one()
    perf_count_2 = (await db.execute(select(func.count()).select_from(AdPerformanceDaily))).scalar_one()
    assert campaign_count_1 == campaign_count_2
    assert perf_count_1 == perf_count_2
    assert second.inserted == 0
