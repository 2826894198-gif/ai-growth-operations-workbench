from app.core.config import settings
from app.workers.celery_app import celery_app
from app.workers.etl_tasks import _enqueue_for_providers


@celery_app.task(name="ingestion.google_intraday", bind=True)
def google_intraday(self) -> None:
    _enqueue_for_providers(["GOOGLE_ADS"], "PERFORMANCE_INTRADAY")


@celery_app.task(name="ingestion.google_nightly", bind=True)
def google_nightly(self) -> None:
    _enqueue_for_providers(["GOOGLE_ADS"], "PERFORMANCE_RECONCILE", settings.google_nightly_reconcile_days)


@celery_app.task(name="ingestion.google_weekly", bind=True)
def google_weekly(self) -> None:
    _enqueue_for_providers(["GOOGLE_ADS"], "PERFORMANCE_RECONCILE", settings.google_weekly_reconcile_days)
