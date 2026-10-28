from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.etl.validators import (
    dq_impressions_lt_clicks,
    dq_negative_spend,
    dq_order_total_invalid,
    dq_refund_gt_order,
    dq_unknown_currency,
)
from app.models.ad_performance import AdPerformanceDaily
from app.services.metrics_service import MetricsService


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
async def test_platform_metrics_exclude_ad_grain(db):
    db.add(
        AdPerformanceDaily(
            data_source_id="ds1", platform="META_ADS", entity_type="CAMPAIGN",
            external_entity_id="c1", date=date(2026, 8, 1), currency="USD", spend_amount=Decimal(100),
            impressions=1000, clicks=10,
        )
    )
    db.add(
        AdPerformanceDaily(
            data_source_id="ds1", platform="META_ADS", entity_type="AD",
            external_entity_id="a1", date=date(2026, 8, 1), currency="USD", spend_amount=Decimal(999999),
            impressions=1, clicks=1,
        )
    )
    await db.commit()
    platforms = await MetricsService().platforms(db, "2026-08-01", "2026-08-01")
    assert platforms[0]["spend"] == 100.0


def test_dq_rules():
    assert dq_negative_spend(Decimal(-1), "x") is not None
    assert dq_negative_spend(Decimal(0), "x") is None
    assert dq_impressions_lt_clicks(Decimal(1), Decimal(2), "x") is not None
    assert dq_unknown_currency("US", "x") is not None
    assert dq_unknown_currency("USD", "x") is None
    assert dq_refund_gt_order(Decimal(11), Decimal(10), "o1") is not None
    assert dq_order_total_invalid(Decimal(103), Decimal(100), Decimal(5), Decimal(8), Decimal(10), "o1") is not None
    assert dq_order_total_invalid(Decimal(113), Decimal(100), Decimal(5), Decimal(8), Decimal(10), "o1") is None
