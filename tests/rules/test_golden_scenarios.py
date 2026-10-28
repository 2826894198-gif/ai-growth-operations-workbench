import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.rules.confidence.scorer import confidence_band
from app.rules.context import RuleContext
from app.rules.evaluator import evaluate_rule

SCENARIO_DIR = Path(__file__).parent / "scenarios"


def _scenarios():
    return sorted(SCENARIO_DIR.glob("*.json"))


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
@pytest.mark.parametrize("path", _scenarios(), ids=lambda p: p.stem)
async def test_golden_scenario(db, path):
    scenario = json.loads(path.read_text(encoding="utf-8"))
    context_data = scenario["context"]
    context = RuleContext(
        evaluation_time=datetime.now(timezone.utc),
        entity_type="AD",
        entity_id="scenario-entity",
        metrics=context_data.get("metrics", {}),
        business_targets=context_data.get("business_targets", {}),
        data_freshness_minutes=context_data.get("data_freshness_minutes"),
        entity_age_hours=context_data.get("entity_age_hours"),
        recent_changes=context_data.get("recent_changes", []),
        active_experiments=context_data.get("active_experiments", []),
        platform=scenario["rule"].get("platform"),
        extra=context_data.get("extra", {}),
    )
    result = await evaluate_rule(db, scenario["rule"], context, scenario.get("defaults", {}))
    expected = scenario["expected"]
    assert result.result == expected["result"], f"{path.name}: {result.reason_codes}"
    if expected.get("action"):
        assert result.action == expected["action"]
    if expected.get("severity"):
        assert result.severity == expected["severity"]
    if expected.get("confidence_band"):
        assert confidence_band(result.confidence) == expected["confidence_band"]
