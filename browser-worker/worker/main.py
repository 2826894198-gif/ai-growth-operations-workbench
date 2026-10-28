import argparse
import asyncio
import sys

from celery import Celery

from worker.config import get_settings
from worker.executor import execute_task
from worker.observability.logger import configure_logging
from worker.smoke import run_smoke


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery("ai_dtc_growth_worker", broker=settings.redis_url, backend=settings.redis_url)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_default_queue=settings.browser_worker_queue,
        task_default_exchange=settings.browser_worker_queue,
        task_default_routing_key=settings.browser_worker_queue,
        task_track_started=True,
        worker_prefetch_multiplier=1,
    )

    @app.task(name="browser_worker.execute", bind=True)
    def execute(self, task_id: str) -> dict:
        return asyncio.run(execute_task(task_id))

    return app


celery_app = create_celery_app()


def main(argv=None) -> int:
    configure_logging(get_settings().log_level, get_settings().service_name)
    parser = argparse.ArgumentParser(prog="browser-worker")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("worker", help="run the Celery worker consuming browser tasks")
    sub.add_parser("smoke", help="run the live AdsPower smoke test")
    once = sub.add_parser("once", help="execute a single task by id (debugging)")
    once.add_argument("task_id")
    args = parser.parse_args(argv)

    if args.command == "worker":
        celery_app.worker_main(["worker", "--loglevel=INFO", "-n", "browser-worker@%h"])
        return 0
    if args.command == "smoke":
        return asyncio.run(run_smoke())
    if args.command == "once":
        result = asyncio.run(execute_task(args.task_id))
        print(result)
        return 0 if result.get("status") == "SUCCESS" else 1
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
