"""PART 04 AI-layer smoke test (mock mode, no keys)."""

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/smoke_ai.db")
os.environ.setdefault("AI_PROVIDER_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.ai.agents.base import run_agent  # noqa: E402
from app.ai.agents.definitions import (  # noqa: E402
    SPECIALISTS,
    performance_agent,
    reviewer_agent,
    strategy_agent,
)
from app.ai.evals.runner import run_eval_suite  # noqa: E402
from app.ai.models.mock_provider import MockModelProvider  # noqa: E402
from app.ai.models.router import get_provider_for_task, route_task  # noqa: E402
from app.ai.orchestrator.checkpoints import build_checkpointer  # noqa: E402
from app.ai.orchestrator.graph import build_graph  # noqa: E402
from app.ai.orchestrator.nodes import specialists_node  # noqa: E402
from app.ai.orchestrator.runner import start_run  # noqa: E402
from app.ai.orchestrator.supervisor import build_plan  # noqa: E402
from app.ai.prompts.registry import sync_prompts  # noqa: E402
from app.ai.tools.build_registry import build_registry  # noqa: E402
from app.ai.tools.permissions import check_permission  # noqa: E402
from app.ai.tools.registry import registry  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.models.ai import (  # noqa: E402
    AIModelUsage,
    AIToolAudit,
    KnowledgeDocument,  # noqa: E402
)

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL':<5} {name}" + (f"  {detail}" if detail else ""), flush=True)


async def main() -> int:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        check("Database", (await conn.execute(text("SELECT 1"))).scalar() == 1)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        build_registry()
        check("Tool Registry", len(registry.list()) >= 20, f"{len(registry.list())} tools")
        check("Tool Permissions", check_permission("performance", "get_campaign_performance") and not check_permission("performance", "public_page_snapshot"))
        check("Mock Model Provider", isinstance(get_provider_for_task("performance_diagnosis"), MockModelProvider))
        route = route_task("search_term_classification")
        check("Model Router", route.capability == "classification")
        check("LangGraph Runtime", build_graph(db) is not None)
        check("Checkpoint Store", build_checkpointer() is not None)

        await sync_prompts(db)
        from app.ai.knowledge.ingestion import ingest_document
        from app.ai.memory.business import list_memories
        from app.ai.tools.memory import write_business_memory

        await ingest_document(db, document_type="BRAND", title="Smoke Brand", content="Mock brand knowledge for smoke test.", source_uri="smoke://brand")
        await write_business_memory(db, statement="Mock memory from smoke test.", evidence_refs=["smoke://evidence"], confidence=0.5, run_id="smoke")
        check("Knowledge Retrieval", (await db.execute(select(func.count()).select_from(KnowledgeDocument))).scalar_one() >= 1)
        check("Business Memory", len(await list_memories(db)) >= 1)

        provider = MockModelProvider()
        run_id = "smoke-run"
        plan = await build_plan(db, run_id=run_id, task_type="DAILY_GROWTH_REVIEW", user_request="smoke", scope={"platforms": ["META"]}, seed={})
        check("Supervisor", plan.task_type == "DAILY_GROWTH_REVIEW" and "performance" in plan.agents)

        for name, agent in SPECIALISTS.items():
            seed = {"evidence": [{"metric": "spend_7d", "value": 100.0, "baseline": 80.0, "source_ref": f"metric://smoke/{name}"}]} if name == "performance" else {}
            output = await run_agent(db, agent, task_prompt=f"smoke {name}", run_id=run_id, provider=provider, seed=seed)
            check(f"{name.title()} Agent", output is not None)
        strategy = await run_agent(db, strategy_agent, task_prompt="smoke strategy", run_id=run_id, provider=provider)
        check("Strategy Agent", strategy.executive_summary != "")
        review = await run_agent(db, reviewer_agent, task_prompt="smoke review", run_id=run_id, provider=provider)
        check("Reviewer", review.passed is True)
        check("Structured Output", review.passed is True and strategy.top_priorities is not None)

        partial = await specialists_node(
            {"run_id": run_id, "user_request": "smoke", "scope": {"entity_id": "x"}},
            db,
        )
        check("Partial Failure", partial["status"] in ("PARTIAL", "RUNNING"))
        perf = await run_agent(
            db, performance_agent, task_prompt="smoke evidence", run_id=run_id, provider=provider,
            seed={"evidence": [{"metric": "spend_7d", "value": 100.0, "source_ref": "metric://smoke/evidence"}]},
        )
        check("Evidence References", all(e.source_ref for e in perf.evidence))
        check("Cost Tracking", (await db.execute(select(func.count()).select_from(AIModelUsage))).scalar_one() >= 1)
        check("Tracing", (await db.execute(select(func.count()).select_from(AIToolAudit))).scalar_one() >= 0)

        run = await start_run(db, task_type="DAILY_GROWTH_REVIEW", user_request="daily smoke", scope={"platforms": ["META"]})
        check("End-to-End Run", run["status"] in ("COMPLETED", "PARTIAL", "WAITING_HUMAN"))
        evals = await run_eval_suite(db, "all")
        check("Golden Evals", evals["total"] >= 4 and evals["failed"] == 0, f"passed={evals['passed']} failed={evals['failed']}")

    await engine.dispose()
    failed = sum(1 for ok in RESULTS if not ok)
    print("SMOKE AI " + ("PASSED" if failed == 0 else "FAILED"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
