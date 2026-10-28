import asyncio

from app.core.database import async_session_factory
from app.rules.engine import run_evaluation
from app.rules.simulation.replay import replay_rule
from app.rules.simulation.simulator import simulate_rule
from app.workers.celery_app import celery_app


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(name="rules.evaluate_intraday", bind=True)
def evaluate_intraday(self) -> dict:
    async def _run_async():
        async with async_session_factory() as db:
            run = await run_evaluation(db, trigger_type="INTRADAY")
            return {"run_id": str(run.id) if run else None}

    return _run(_run_async())


@celery_app.task(name="rules.evaluate_daily", bind=True)
def evaluate_daily(self) -> dict:
    async def _run_async():
        async with async_session_factory() as db:
            run = await run_evaluation(db, trigger_type="DAILY")
            return {"run_id": str(run.id) if run else None}

    return _run(_run_async())


@celery_app.task(name="rules.evaluate_weekly", bind=True)
def evaluate_weekly(self) -> dict:
    async def _run_async():
        async with async_session_factory() as db:
            run = await run_evaluation(db, trigger_type="WEEKLY")
            return {"run_id": str(run.id) if run else None}

    return _run(_run_async())


@celery_app.task(name="rules.replay", bind=True)
def replay(self, rule_key: str, start_date: str, end_date: str) -> dict:
    async def _run_async():
        async with async_session_factory() as db:
            return await replay_rule(db, rule_key, start_date, end_date)

    return _run(_run_async())


@celery_app.task(name="rules.simulate", bind=True)
def simulate(self, rule_key: str, candidate_parameters: dict, start_date: str, end_date: str) -> dict:
    async def _run_async():
        async with async_session_factory() as db:
            return await simulate_rule(db, rule_key, candidate_parameters, start_date, end_date)

    return _run(_run_async())
