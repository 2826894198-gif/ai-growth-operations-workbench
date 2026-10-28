from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.rules.context import RuleContext
from app.rules.guards.attribution_delay import check_attribution_delay
from app.rules.guards.freshness import check_freshness
from app.rules.guards.learning import check_learning
from app.rules.guards.recent_change import check_recent_change
from app.rules.guards.sample import check_sample


def _context(**kwargs):
    kwargs.setdefault("evaluation_time", datetime.now(timezone.utc))
    return RuleContext(**kwargs)


def test_freshness_guard():
    assert check_freshness(_context(data_freshness_minutes=5), {"data_freshness_minutes": 30}) == (True, None)
    ok, reason = check_freshness(_context(data_freshness_minutes=45), {"data_freshness_minutes": 30})
    assert ok is False and reason == "DATA_STALE"


def test_sample_guard():
    defaults = {"min_active_hours": 24, "min_clicks_units": 30, "min_purchases_units": 3, "min_spend_units": 20}
    ctx = _context(
        entity_age_hours=72,
        metrics={"clicks_7d": 100, "purchases_7d": 5, "spend_7d": 200},
    )
    assert check_sample(ctx, {}, defaults) == (True, None)
    ok, reason = check_sample(_context(entity_age_hours=3, metrics={"clicks_7d": 100, "purchases_7d": 5, "spend_7d": 200}), {}, defaults)
    assert ok is False and reason == "SAMPLE_TOO_NEW"


def test_attribution_delay_and_learning():
    ctx = _context(entity_age_hours=1)
    ok, reason = check_attribution_delay(ctx, {"attribution_delay_minutes": 120})
    assert ok is False and reason == "ATTRIBUTION_DELAY"
    ctx = _context(entity_age_hours=30, metrics={"in_learning": True})
    ok, reason = check_learning(ctx, {})
    assert ok is False and reason == "LEARNING_PROTECTION"


def test_recent_change_guard():
    now = datetime.now(timezone.utc)
    ctx = _context(
        evaluation_time=now,
        recent_changes=[{"occurred_at": now - timedelta(hours=4)}],
    )
    ok, reason = check_recent_change(ctx, {"recent_change_hours": 24})
    assert ok is False and reason == "RECENT_CHANGE_COOLDOWN"


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
async def test_cooldown_guard(db):
    from app.rules.guards.cooldown import check_cooldown

    ok, reason = await check_cooldown(db, "AD", "ad1", "REVIEW_PAUSE", "NO_PURCHASE_BURN", 1440, "HIGH")
    assert ok is True
    from app.models.rules import Recommendation

    db.add(Recommendation(entity_type="AD", entity_id="ad1", primary_action="REVIEW_PAUSE", reason_group="NO_PURCHASE_BURN", severity="MEDIUM", confidence=0.8))
    await db.commit()
    ok, reason = await check_cooldown(db, "AD", "ad1", "REVIEW_PAUSE", "NO_PURCHASE_BURN", 1440, "HIGH")
    assert ok is True and reason == "ESCALATION"
    ok, reason = await check_cooldown(db, "AD", "ad1", "REVIEW_PAUSE", "NO_PURCHASE_BURN", 1440, "MEDIUM")
    assert ok is False and reason == "COOLDOWN"
