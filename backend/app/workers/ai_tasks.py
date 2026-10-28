import asyncio

from app.ai.creative.analysis import analyze_creative
from app.ai.evals.runner import run_eval_suite
from app.ai.orchestrator.runner import start_run
from app.core.database import async_session_factory
from app.workers.celery_app import celery_app


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(name="ai.daily_review", bind=True)
def daily_review(self) -> dict:
    async def _run_async():
        async with async_session_factory() as db:
            return await start_run(db, task_type="DAILY_GROWTH_REVIEW", user_request="Daily growth review from rule findings", scope={"platforms": ["META", "GOOGLE"]})

    return _run(_run_async())


@celery_app.task(name="ai.weekly_review", bind=True)
def weekly_review(self) -> dict:
    async def _run_async():
        async with async_session_factory() as db:
            return await start_run(
                db,
                task_type="WEEKLY_GROWTH_REVIEW",
                user_request="Weekly growth and market intelligence review",
                scope={"platforms": ["META", "GOOGLE"], "include_competitor": True},
                plan_agents_override=["performance", "search", "funnel", "creative", "competitor", "strategy"],
            )

    return _run(_run_async())


@celery_app.task(name="ai.analyze_creative", bind=True)
def analyze_creative_task(self, creative_id: str, blind: bool = False) -> dict:
    async def _run_async():
        async with async_session_factory() as db:
            return await analyze_creative(db, creative_id, blind=blind)

    return _run(_run_async())


@celery_app.task(name="ai.run_evals", bind=True)
def run_evals(self, suite: str = "all") -> dict:
    async def _run_async():
        async with async_session_factory() as db:
            return await run_eval_suite(db, suite)

    return _run(_run_async())
