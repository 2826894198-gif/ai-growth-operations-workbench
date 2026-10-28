from app.core.config import settings
from app.workers.celery_app import celery_app
from app.workers.etl_tasks import _enqueue_for_providers


@celery_app.task(name="ingestion.meta_intraday", bind=True)
def meta_intraday(self) -> None:
    _enqueue_for_providers(["META_ADS"], "PERFORMANCE_INTRADAY")


@celery_app.task(name="ingestion.meta_nightly", bind=True)
def meta_nightly(self) -> None:
    _enqueue_for_providers(["META_ADS"], "PERFORMANCE_RECONCILE", settings.meta_nightly_reconcile_days)


@celery_app.task(name="ingestion.meta_weekly", bind=True)
def meta_weekly(self) -> None:
    _enqueue_for_providers(["META_ADS"], "PERFORMANCE_RECONCILE", settings.meta_weekly_reconcile_days)
