"""Standalone execution worker (queue:execution / queue:compensation).

Independent process with its own permissions and write credentials. Bounded
concurrency (default 2) and no batch fan-out.
"""

import argparse
import asyncio
import logging

from app.core.config import settings
from app.core.database import async_session_factory
from app.execution.compensation import approve_compensation, run_compensation
from app.execution.engine import execute_intent
from app.execution.providers.factory import get_execution_provider

logger = logging.getLogger(__name__)


async def _poll_loop(queue_name: str, concurrency: int) -> None:
    import redis.asyncio as aioredis

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    semaphore = asyncio.Semaphore(concurrency)

    async def handle(payload: str) -> None:
        async with semaphore:
            try:
                task_type, record_id, actor = payload.split("|", 2)
                if task_type == "EXECUTE":
                    async with async_session_factory() as db:
                        result = await execute_intent(db, intent_id=record_id, actor=actor or "worker")
                        await db.commit()
                        logger.info("execution job done", extra={"job": record_id, "result": result})
                elif task_type == "COMPENSATE":
                    async with async_session_factory() as db:
                        from sqlalchemy import select

                        from app.models.execution import ExecutionCompensation

                        compensation = (
                            await db.execute(
                                select(ExecutionCompensation).where(ExecutionCompensation.id == record_id)
                            )
                        ).scalar_one_or_none()
                        if compensation is None:
                            return
                        if compensation.status == "PENDING":
                            compensation = await approve_compensation(db, record_id, actor or "worker")
                        provider = get_execution_provider(compensation.provider)
                        result = await run_compensation(db, compensation=compensation, provider_impl=provider, actor=actor or "worker")
                        await db.commit()
                        logger.info("compensation job done", extra={"job": record_id, "result": result})
            except Exception:  # noqa: BLE001
                logger.exception("worker task failed", extra={"payload": payload})

    logger.info("execution worker polling", extra={"queue": queue_name, "concurrency": concurrency})
    while True:
        try:
            item = await redis_client.blpop(queue_name, timeout=1)
            if item:
                await handle(item[1])
        except Exception:  # noqa: BLE001
            logger.exception("worker poll error")
            await asyncio.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone execution worker")
    parser.add_argument("--queue", default=settings.execution_queue, help="Redis queue to consume")
    parser.add_argument("--concurrency", type=int, default=settings.execution_worker_concurrency)
    args = parser.parse_args()
    logging.basicConfig(level=settings.log_level)
    asyncio.run(_poll_loop(args.queue, args.concurrency))


if __name__ == "__main__":
    main()
