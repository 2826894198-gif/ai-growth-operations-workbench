from celery.schedules import crontab

from app.core.config import settings
from app.workers.celery_app import celery_app


def build_beat_schedule() -> dict:
    return {
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
    }


def configure_beat() -> None:
    celery_app.conf.beat_schedule = build_beat_schedule()
    celery_app.conf.timezone = "UTC"
