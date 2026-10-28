import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base
from app.etl.pipeline import run_meta_pipeline
from app.models.data_source import DataSource
from app.models.rules import (
    BusinessTargetProfile,
    Recommendation,
    RuleDefinition,
    RuleEvaluation,
)
from app.rules.engine import run_evaluation
from app.rules.simulation.replay import replay_rule
from app.rules.simulation.simulator import simulate_rule

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import generate_fixtures

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
async def test_rule_engine_pipeline(db):
    old_mode = settings.rule_engine_mode
    settings.rule_engine_mode = "active"
    try:
        await _run_pipeline(db)
    finally:
        settings.rule_engine_mode = old_mode


async def _run_pipeline(db):
    rng = random.Random("rules-demo")
    meta = generate_fixtures.build_meta(7, rng, "zero_purchase_burn")
    source = DataSource(provider="META_ADS", name="Rules Meta", external_account_id="act_rules", meta={"scenario": "healthy_growth"})
    source.last_successful_sync_at = datetime.now(timezone.utc)
    db.add(source)
    await db.commit()
    await db.refresh(source)
    await run_meta_pipeline(
        db, str(source.id),
        accounts=meta["accounts"], campaigns=meta["campaigns"], ad_groups=meta["ad_groups"],
        ads=meta["ads"], creatives=meta["creatives"], performance=meta["performance"],
        sync_job_id="rules-seed",
    )
    db.add(
        BusinessTargetProfile(
            name="Global",
            scope_type="GLOBAL",
            currency="USD",
            target_cpa=30.0,
            target_roas=2.2,
            break_even_roas=1.2,
            max_daily_spend=2000.0,
            refund_rate_critical=0.10,
        )
    )
    # Load a minimal rule set directly into the DB (META_NO_PURCHASE_BURN + DATA_STALE).
    db.add(
        RuleDefinition(
            rule_key="META_NO_PURCHASE_BURN",
            name="No Purchase Burn",
            category="CAMPAIGN",
            platform="META",
            evaluation_level="AD",
            severity="HIGH",
            version=1,
            status="ACTIVE",
            enabled=True,
            conditions={
                "all": [
                    {"metric": "purchases_3d", "operator": "eq", "value": 0},
                    {"metric": "spend_3d", "operator": "target_multiple_gte", "target": "target_cpa", "multiple": 2.0},
                ]
            },
            guards={"min_age_hours": 24, "data_freshness_minutes": 60, "min_clicks": 10},
            action_template={"type": "REVIEW_PAUSE", "reason": "NO_PURCHASE_BURN", "risk": "MEDIUM"},
            cooldown_minutes=1440,
        )
    )
    await db.commit()

    as_of = datetime.now(timezone.utc)
    run = await run_evaluation(db, trigger_type="MANUAL", as_of=as_of)
    assert run is not None
    assert run.rules_evaluated == 1
    evaluations = (await db.execute(select(RuleEvaluation))).scalars().all()
    assert len(evaluations) > 0
    recommendations = (await db.execute(select(Recommendation))).scalars().all()
    assert len(recommendations) > 0

    # Replay determinism: same as-of → same triggered count.
    run2 = await run_evaluation(db, trigger_type="REPLAY", as_of=as_of)
    assert run2.triggered == run.triggered

    # Simulation isolation: candidate rule leaves no trace.
    today = datetime.now(timezone.utc).date()
    result = await simulate_rule(
        db, "META_NO_PURCHASE_BURN", {"multiple": 1.5},
        (today - timedelta(days=2)).isoformat(), today.isoformat(),
    )
    assert result["total_triggers"] >= 0
    assert (await db.execute(select(func.count()).select_from(RuleDefinition).where(RuleDefinition.rule_key.like("%__SIM%")))).scalar_one() == 0

    replay = await replay_rule(
        db, "META_NO_PURCHASE_BURN",
        (today - timedelta(days=2)).isoformat(), today.isoformat(),
    )
    assert replay["approximate"] is True
    assert len(replay["days"]) >= 1
