import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_source import DataSource
from app.models.raw import RawWebhookEvent

logger = logging.getLogger(__name__)


def task_name_for_topic(topic: str) -> Optional[str]:
    if topic in ("orders/create", "orders/updated", "orders/paid"):
        return "ingestion.webhook_order"
    if topic == "refunds/create":
        return "ingestion.webhook_refund"
    if topic == "products/update":
        return "ingestion.webhook_product"
    return None


async def process_webhook_event(db: AsyncSession, event_id: str) -> None:
    from sqlalchemy import select


    event = (await db.execute(select(RawWebhookEvent).where(RawWebhookEvent.id == event_id))).scalar_one_or_none()
    if event is None:
        return
    if event.topic == "app/uninstalled":
        source = (
            await db.execute(
                select(DataSource).where(
                    DataSource.external_account_id == event.shop_domain,
                    DataSource.provider == "SHOPIFY",
                )
            )
        ).scalar_one_or_none()
        if source:
            source.sync_enabled = False
            source.status = "DISABLED"
        event.processed = True
        await db.commit()
        return
    task_name = task_name_for_topic(event.topic or "")
    if task_name is None:
        event.processed = True
        event.processing_error = f"unsupported topic {event.topic}"
        await db.commit()
        return
    try:
        from app.workers.celery_app import celery_app

        celery_app.send_task(task_name, args=[event.id], queue="webhook")
        event.processed = True
    except Exception as exc:  # noqa: BLE001
        event.processing_error = str(exc)
    await db.commit()
