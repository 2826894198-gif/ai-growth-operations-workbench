import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.etl.pipeline import run_shopify_pipeline
from app.ingestion.providers import get_provider
from app.integrations.shopify.webhooks import process_webhook_event
from app.models.commerce import Order, OrderAttribution
from app.models.data_source import DataSource
from app.models.raw import RawWebhookEvent
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ingestion.shopify_reconcile", bind=True)
def shopify_reconcile(self) -> None:
    from app.workers.etl_tasks import _enqueue_for_providers

    _enqueue_for_providers(["SHOPIFY"], "SHOPIFY_ORDER_RECONCILE", settings.shopify_reconcile_days)


@celery_app.task(name="ingestion.shopify_nightly", bind=True)
def shopify_nightly(self) -> None:
    from app.workers.etl_tasks import _enqueue_for_providers

    _enqueue_for_providers(["SHOPIFY"], "SHOPIFY_ORDER_RECONCILE", settings.shopify_nightly_reconcile_days)


def _webhook_order_payload(payload: dict) -> tuple:
    order = payload.get("order") or payload
    items = []
    for item in order.get("line_items") or []:
        items.append(
            {
                "order_external_id": order.get("id"),
                "line_item_id": item.get("id"),
                "product_external_id": item.get("product_id"),
                "variant_external_id": item.get("variant_id"),
                "sku": item.get("sku"),
                "title": item.get("title"),
                "quantity": item.get("quantity"),
                "unit_price": item.get("price"),
                "line_discount": item.get("total_discount"),
                "line_total": item.get("price") and float(item.get("price", 0)) * float(item.get("quantity", 0) or 1),
            }
        )
    refunds = []
    for refund in order.get("refunds") or []:
        refunds.append(
            {
                "order_external_id": order.get("id"),
                "refund_id": refund.get("id"),
                "created_at": refund.get("created_at"),
                "amount": sum(float(t.get("amount", 0) or 0) for t in refund.get("transactions") or []),
                "reason": None,
            }
        )
    staging = {
        "external_id": order.get("id"),
        "name": order.get("name"),
        "created_at": order.get("created_at"),
        "updated_at": order.get("updated_at"),
        "financial_status": order.get("financial_status"),
        "fulfillment_status": order.get("fulfillment_status"),
        "currency": order.get("currency"),
        "subtotal": order.get("subtotal_price"),
        "shipping": order.get("total_shipping_price_set", {}).get("shop_money", {}).get("amount"),
        "tax": order.get("total_tax_set", {}).get("shop_money", {}).get("amount"),
        "discount": order.get("total_discounts"),
        "total": order.get("total_price"),
        "cancelled_at": order.get("cancelled_at"),
        "source_name": order.get("source_name"),
        "customer_id_hash": (order.get("customer") or {}).get("id"),
    }
    return staging, items, refunds


@celery_app.task(name="ingestion.webhook_process", bind=True)
def webhook_process(self, event_id: str) -> None:
    async def _run() -> None:
        async with async_session_factory() as db:
            await process_webhook_event(db, event_id)

    asyncio.run(_run())


@celery_app.task(name="ingestion.webhook_order", bind=True)
def webhook_order(self, event_id: str) -> None:
    async def _run() -> None:
        async with async_session_factory() as db:
            event = (await db.execute(select(RawWebhookEvent).where(RawWebhookEvent.id == event_id))).scalar_one_or_none()
            if event is None or not event.payload:
                return
            order, items, refunds = _webhook_order_payload(event.payload)
            source = (
                await db.execute(
                    select(DataSource).where(
                        DataSource.provider == "SHOPIFY",
                        DataSource.external_account_id == event.shop_domain,
                    )
                )
            ).scalar_one_or_none()
            if source is None:
                event.processing_error = "no shopify data source matched"
                event.processed = True
                await db.commit()
                return
            await run_shopify_pipeline(
                db,
                str(source.id),
                products=[],
                variants=[],
                orders=[order],
                order_items=items,
                refunds=refunds,
                journeys=[],
                sync_job_id="webhook-" + str(event.id),
            )
            # Journey enrichment (PENDING; enrichment task fetches when ready).
            order_row = (
                await db.execute(
                    select(Order).where(
                        Order.data_source_id == str(source.id),
                        Order.external_order_id == order["external_id"],
                    )
                )
            ).scalar_one_or_none()
            if order_row is not None:
                from app.ingestion.idempotency import upsert_by

                await upsert_by(
                    db,
                    OrderAttribution,
                    ["order_id"],
                    {"order_id": str(order_row.id), "journey_ready": False, "journey_state": "PENDING"},
                )
            event.processed = True
            event.processing_error = None
            await db.commit()

    asyncio.run(_run())


@celery_app.task(name="ingestion.shopify_journey_enrich", bind=True)
def shopify_journey_enrich(self) -> None:
    async def _run() -> None:
        async with async_session_factory() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            rows = (
                await db.execute(
                    select(Order, OrderAttribution)
                    .join(OrderAttribution, OrderAttribution.order_id == Order.id)
                    .where(OrderAttribution.journey_state.in_(["PENDING", "RETRY"]))
                    .limit(100)
                )
            ).all()
            for order, attribution in rows:
                if attribution.fetched_at and attribution.fetched_at < cutoff:
                    attribution.journey_state = "EXPIRED"
                    continue
                provider = get_provider("SHOPIFY")
                journey = await provider.fetch_journey(order.external_order_id)
                attribution.journey_ready = bool(journey.get("ready"))
                attribution.days_to_conversion = journey.get("days_to_conversion")
                attribution.journey_state = "READY" if journey.get("ready") else "RETRY"
                attribution.fetched_at = datetime.now(timezone.utc)
            await db.commit()

    asyncio.run(_run())


@celery_app.task(name="ingestion.webhook_product", bind=True)
def webhook_product(self, event_id: str) -> None:
    async def _run() -> None:
        async with async_session_factory() as db:
            event = (await db.execute(select(RawWebhookEvent).where(RawWebhookEvent.id == event_id))).scalar_one_or_none()
            if event is None or not event.payload:
                return
            product = event.payload.get("product") or event.payload
            source = (
                await db.execute(
                    select(DataSource).where(
                        DataSource.provider == "SHOPIFY",
                        DataSource.external_account_id == event.shop_domain,
                    )
                )
            ).scalar_one_or_none()
            if source is None:
                event.processed = True
                await db.commit()
                return
            variants = []
            for variant in product.get("variants") or []:
                variants.append(
                    {
                        "external_id": variant.get("id"),
                        "product_external_id": product.get("id"),
                        "sku": variant.get("sku"),
                        "title": variant.get("title"),
                        "price": variant.get("price"),
                        "compare_at_price": variant.get("compare_at_price"),
                        "inventory_item_id": variant.get("inventory_item_id"),
                    }
                )
            await run_shopify_pipeline(
                db,
                str(source.id),
                products=[
                    {
                        "external_id": product.get("id"),
                        "title": product.get("title"),
                        "handle": product.get("handle"),
                        "vendor": product.get("vendor"),
                        "product_type": product.get("product_type"),
                        "status": product.get("status"),
                        "created_at": product.get("created_at"),
                        "updated_at": product.get("updated_at"),
                    }
                ],
                variants=variants,
                orders=[],
                order_items=[],
                refunds=[],
                journeys=[],
                sync_job_id="webhook-" + str(event.id),
            )
            event.processed = True
            await db.commit()

    asyncio.run(_run())
