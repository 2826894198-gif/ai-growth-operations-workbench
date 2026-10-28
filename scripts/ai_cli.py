"""AI layer CLI: daily/weekly runs, query, creative analysis, evals."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./demo_data.db")
os.environ.setdefault("AI_PROVIDER_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.ai.creative.analysis import analyze_creative  # noqa: E402
from app.ai.evals.runner import run_eval_suite  # noqa: E402
from app.ai.orchestrator.router import classify_intent, try_direct_answer  # noqa: E402
from app.ai.orchestrator.runner import start_run  # noqa: E402
from app.ai.tools.build_registry import build_registry  # noqa: E402
from app.core.database import Base  # noqa: E402


async def _session(fn):
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            build_registry()
            return await fn(db)
    finally:
        await engine.dispose()


async def cmd_daily(db):
    return await start_run(db, task_type="DAILY_GROWTH_REVIEW", user_request="Daily growth review", scope={"platforms": ["META", "GOOGLE"]})


async def cmd_weekly(db):
    return await start_run(
        db,
        task_type="WEEKLY_GROWTH_REVIEW",
        user_request="Weekly growth and market intelligence review",
        scope={"platforms": ["META", "GOOGLE"], "include_competitor": True},
        plan_agents_override=["performance", "search", "funnel", "creative", "competitor", "strategy"],
    )


async def cmd_query(db, query: str):
    direct = await try_direct_answer(db, query)
    if direct:
        return direct
    return await start_run(db, task_type=classify_intent(query), user_request=query, scope={})


async def cmd_creative(db, creative_id: str, blind: bool = False):
    return await analyze_creative(db, creative_id, blind=blind)


async def cmd_evals(db, suite: str):
    return await run_eval_suite(db, suite)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("daily")
    sub.add_parser("weekly")
    query = sub.add_parser("query")
    query.add_argument("query")
    creative = sub.add_parser("creative")
    creative.add_argument("creative_id")
    creative.add_argument("--blind", action="store_true")
    evals = sub.add_parser("evals")
    evals.add_argument("--suite", default="all")
    args = parser.parse_args()
    if args.command == "daily":
        result = asyncio.run(_session(cmd_daily))
    elif args.command == "weekly":
        result = asyncio.run(_session(cmd_weekly))
    elif args.command == "query":
        result = asyncio.run(_session(lambda db: cmd_query(db, args.query)))
    elif args.command == "creative":
        result = asyncio.run(_session(lambda db: cmd_creative(db, args.creative_id, args.blind)))
    else:
        result = asyncio.run(_session(lambda db: cmd_evals(db, args.suite)))
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
