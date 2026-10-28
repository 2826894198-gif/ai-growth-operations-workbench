
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.ai.evals.runner import run_eval_suite
from app.ai.orchestrator.nodes import specialists_node
from app.ai.orchestrator.runner import start_run
from app.ai.prompts.registry import sync_prompts
from app.ai.tools.build_registry import build_registry
from app.core.config import settings
from app.core.database import Base
from app.models.ai import AIAgentRun, AIAgentStep, AIEvalRun, AIModelUsage

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
async def test_ai_graph_daily_review(db):
    old_mode = settings.ai_provider_mode
    settings.ai_provider_mode = "mock"
    try:
        build_registry()
        await sync_prompts(db)
        run = await start_run(
            db,
            task_type="DAILY_GROWTH_REVIEW",
            user_request="daily review",
            scope={"platforms": ["META"]},
        )
        assert run["status"] in ("COMPLETED", "PARTIAL", "WAITING_HUMAN")
        steps = (await db.execute(select(AIAgentStep))).scalars().all()
        assert len(steps) >= 3
        usage = (await db.execute(select(func.count()).select_from(AIModelUsage))).scalar_one()
        assert usage >= 1
        row = (await db.execute(select(AIAgentRun))).scalar_one()
        assert row.status == "COMPLETED"
    finally:
        settings.ai_provider_mode = old_mode


@pytest.mark.asyncio
async def test_ai_partial_failure_and_evals(db):
    build_registry()
    result = await specialists_node(
        {"run_id": "r1", "user_request": "x", "scope": {"entity_id": "c1"}},
        db,
    )
    assert result["status"] in ("PARTIAL", "RUNNING")
    eval_result = await run_eval_suite(db, "all")
    assert eval_result["total"] >= 4
    assert eval_result["failed"] == 0
    assert (await db.execute(select(func.count()).select_from(AIEvalRun))).scalar_one() >= 1
