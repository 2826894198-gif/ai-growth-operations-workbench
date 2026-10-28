from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.ad_performance import AdPerformanceDaily
from app.models.commerce import Order
from app.models.product import Experiment, Notification
from app.models.rules import BusinessTargetProfile
from app.services.dashboard_service import DashboardService

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
async def test_dashboard_overview_and_live(db):
    today = datetime.now(timezone.utc).date()
    db.add(
        AdPerformanceDaily(
            data_source_id="ds1", platform="META_ADS", entity_type="CAMPAIGN",
            external_entity_id="c1", date=today, currency="USD",
            spend_amount=Decimal(100), impressions=1000, clicks=10,
            platform_purchases=1, platform_conversion_value=Decimal(150),
        )
    )
    db.add(
        Order(
            data_source_id="ds1", external_order_id="o1", order_name="#1",
            order_created_at=datetime.now(timezone.utc),
            gross_amount=Decimal(80), refunded_amount=Decimal(0),
            net_revenue_amount=Decimal(80), currency="USD",
        )
    )
    db.add(BusinessTargetProfile(name="Global", scope_type="GLOBAL", target_roas=1.5, break_even_roas=1.0, max_daily_spend=500.0))
    await db.commit()

    service = DashboardService()
    overview = await service.overview(db, start_date=today.isoformat(), end_date=today.isoformat())
    assert overview["business_status"] in ("HEALTHY", "WATCH", "AT_RISK", "CRITICAL")
    assert len(overview["kpis"]) == 6
    assert overview["trend"][0]["date"] == today.isoformat()
    live = await service.live(db)
    assert live["today"]["spend"] == 100.0


@pytest.mark.asyncio
async def test_experiments_and_notifications(db):
    db.add(Experiment(name="CTA Test", status="PLANNED", primary_metric="roas"))
    db.add(Notification(type="RECOMMENDATION", severity="HIGH", title="Test", body="body"))
    await db.commit()
    from sqlalchemy import select

    experiments = (await db.execute(select(Experiment))).scalars().all()
    notifications = (await db.execute(select(Notification))).scalars().all()
    assert len(experiments) == 1
    assert len(notifications) == 1
