import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.integrations.shopify.hmac import verify_webhook
from app.models.raw import RawWebhookEvent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/shopify")
async def shopify_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    delivery_id = request.headers.get("X-Shopify-Webhook-Id", "")
    topic = request.headers.get("X-Shopify-Topic", "")
    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
    api_version = request.headers.get("X-Shopify-API-Version", "")

    if settings.shopify_webhook_secret:
        if not verify_webhook(raw_body, settings.shopify_webhook_secret, signature):
            return JSONResponse({"error": "WEBHOOK_HMAC_INVALID"}, status_code=401)
    elif settings.data_provider_mode != "mock":
        return JSONResponse({"error": "SHOPIFY_WEBHOOK_SECRET_NOT_CONFIGURED"}, status_code=503)

    if delivery_id:
        existing = (
            await db.execute(
                select(RawWebhookEvent).where(
                    RawWebhookEvent.provider == "SHOPIFY",
                    RawWebhookEvent.delivery_id == delivery_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"status": "duplicate", "delivery_id": delivery_id}

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    event = RawWebhookEvent(
        provider="SHOPIFY",
        delivery_id=delivery_id,
        topic=topic,
        shop_domain=shop_domain,
        api_version=api_version,
        headers_metadata={
            "topic": topic,
            "delivery_id": delivery_id,
            "shop_domain": shop_domain,
            "api_version": api_version,
        },
        payload=payload,
        verified=bool(settings.shopify_webhook_secret),
        processed=False,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    try:
        from app.workers.celery_app import celery_app

        celery_app.send_task("ingestion.webhook_process", args=[str(event.id)], queue="webhook")
    except Exception:  # noqa: BLE001
        logger.warning("failed to enqueue webhook processing", extra={"event": "webhook_enqueue_failed"})

    return {"status": "received", "delivery_id": delivery_id, "topic": topic}
