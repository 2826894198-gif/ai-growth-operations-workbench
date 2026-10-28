import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.ai.knowledge.chunking import chunk_text
from app.ai.memory.policy import memory_write_allowed
from app.ai.models.base import ModelCallResult, ModelSchemaError, validate_structured
from app.ai.models.mock_provider import MockModelProvider
from app.ai.models.router import route_task
from app.ai.orchestrator.router import classify_intent, try_direct_answer
from app.ai.schemas.review import ReviewResult
from app.ai.tools.build_registry import build_registry
from app.ai.tools.permissions import check_permission
from app.ai.tools.registry import registry
from app.core.database import Base
from app.models.ad_performance import AdPerformanceDaily


def test_intent_classification():
    assert classify_intent("Why did Meta ROAS decline?") == "PERFORMANCE_QA"
    assert classify_intent("search term waste review") == "SEARCH_QA"
    assert classify_intent("本周竞品动态") == "COMPETITOR_QA"
    assert classify_intent("daily growth review") == "DAILY_GROWTH_REVIEW"


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
async def test_direct_query_gate_zero_llm(db):
    db.add(
        AdPerformanceDaily(
            data_source_id="ds1", platform="META_ADS", entity_type="CAMPAIGN",
            external_entity_id="c1", date=datetime.now(timezone.utc).date() - timedelta(days=1), currency="USD",
            spend_amount=Decimal("123.45"),
        )
    )
    await db.commit()
    answer = await try_direct_answer(db, "How much did Meta spend yesterday?")
    assert answer is not None and answer["mode"] == "direct"
    assert "123.45" in answer["answer"]


def test_tool_permission_matrix():
    build_registry()
    assert check_permission("performance", "get_campaign_performance") is True
    assert check_permission("performance", "public_page_snapshot") is False
    assert check_permission("competitor", "public_page_snapshot") is True
    assert check_permission("strategy", "get_campaign_performance") is False
    names = {t["name"] for t in registry.list()}
    forbidden = {"pause_campaign", "change_budget", "change_bid", "create_negative_keyword", "run_sql"}
    assert forbidden.isdisjoint(names)


def test_structured_output_validation():
    result = asyncio.run(MockModelProvider().generate_structured("", "", ReviewResult, seed={}))
    parsed = validate_structured(result, ReviewResult)
    assert parsed.passed is True
    with pytest.raises(ModelSchemaError):
        validate_structured(ModelCallResult(content="", structured={"bad": 1}), ReviewResult)


def test_memory_write_policy():
    ok, _ = memory_write_allowed("Tactile hooks perform well", ["rule://x"])
    assert ok is True
    ok, reason = memory_write_allowed("customer email is demo-user-001@example.test", [])
    assert ok is False and reason == "FORBIDDEN_CONTENT"
    ok, reason = memory_write_allowed("claim without evidence", [], status="VERIFIED")
    assert ok is False and reason == "VERIFIED_REQUIRES_EVIDENCE"


def test_chunking():
    chunks = chunk_text("A" * 2500, max_chars=800, overlap=50)
    assert len(chunks) >= 3
    assert all(chunk for chunk in chunks)


def test_model_router_mock_mode():
    route = route_task("search_term_classification")
    assert route.capability == "classification"
    assert route.provider_name == "mock"
