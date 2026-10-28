from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("ai_dtc_growth", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
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
    beat_schedule={
        "meta_intraday": {
            "task": "ingestion.meta_intraday",
            "schedule": settings.meta_intraday_sync_minutes * 60.0,
        },
        "google_intraday": {
            "task": "ingestion.google_intraday",
            "schedule": settings.google_intraday_sync_minutes * 60.0,
        },
        "shopify_reconcile": {
            "task": "ingestion.shopify_reconcile",
            "schedule": settings.shopify_reconcile_minutes * 60.0,
        },
        "nightly_reconcile": {
            "task": "ingestion.nightly_reconcile",
            "schedule": crontab(hour=3, minute=0),
        },
        "weekly_reconcile": {
            "task": "ingestion.weekly_reconcile",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),
        },
        "shopify_journey_enrich": {
            "task": "ingestion.shopify_journey_enrich",
            "schedule": 600.0,
        },
        "data_quality_sweep": {
            "task": "data_quality.sweep",
            "schedule": 1800.0,
        },
    },
)

# Register Part 02 worker tasks (imported after app creation to avoid cycles).
from app.workers import (  # noqa: E402,F401
    ai_tasks,
    dq_tasks,
    etl_tasks,
    google_tasks,
    meta_tasks,
    rule_tasks,
    shopify_tasks,
)
