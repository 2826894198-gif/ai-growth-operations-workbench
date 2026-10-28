import logging

from app.core.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

TASK_NAME = "browser_worker.execute"


def enqueue_browser_task(task_id: str, countdown: int = 0) -> None:
    """Push a browser task onto the Redis queue consumed by the macOS worker."""
    logger.info("enqueueing browser task", extra={"event": "task_enqueued", "task_id": task_id})
    celery_app.send_task(
        TASK_NAME,
        args=[task_id],
        queue=settings.browser_worker_queue,
        countdown=max(countdown, 0),
    )


@celery_app.task(name=TASK_NAME, bind=True)
def execute(self, task_id: str):
    """Executed by the browser worker process on the macOS host.

    The backend container does not run this worker; when the browser-worker
    package is installed, the actual implementation lives in
    ``worker.executor.execute_task``.
    """
    try:
        from worker.executor import execute_task
    except ImportError as exc:
        raise RuntimeError(
            "browser-worker package is not installed here; "
            "run the macOS browser worker (python -m worker.main worker)"
        ) from exc
    return execute_task(task_id)
