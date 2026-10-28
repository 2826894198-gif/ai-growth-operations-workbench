import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.integrations.shopify.hmac import compute_hmac, verify_webhook
from app.main import app
from app.models.raw import RawWebhookEvent


def test_hmac_verification():
    secret = "shpss_abc"
    body = b'{"id": 123}'
    signature = compute_hmac(body, secret)
    assert verify_webhook(body, secret, signature) is True
    assert verify_webhook(body, secret, "wrong") is False
    assert verify_webhook(body, "", signature) is False


@pytest.fixture
def webhook_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    old_secret = settings.shopify_webhook_secret
    old_mode = settings.data_provider_mode
    settings.shopify_webhook_secret = "test-secret"
    settings.data_provider_mode = "mock"
    with TestClient(app) as client:
        yield client, factory
    settings.shopify_webhook_secret = old_secret
    settings.data_provider_mode = old_mode
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def test_webhook_receive_dedup(webhook_client):
    client, factory = webhook_client
    body = json.dumps({"id": 1, "note": "x"}).encode()
    signature = compute_hmac(body, "test-secret")
    headers = {
        "X-Shopify-Hmac-SHA256": signature,
        "X-Shopify-Webhook-Id": "delivery-1",
        "X-Shopify-Topic": "orders/create",
        "X-Shopify-Shop-Domain": "demo.myshopify.com",
        "X-Shopify-API-Version": "2026-07",
    }
    first = client.post("/api/v1/webhooks/shopify", content=body, headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "received"

    second = client.post("/api/v1/webhooks/shopify", content=body, headers=headers)
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

    bad = client.post(
        "/api/v1/webhooks/shopify",
        content=body,
        headers={**headers, "X-Shopify-Webhook-Id": "delivery-2", "X-Shopify-Hmac-SHA256": "bad"},
    )
    assert bad.status_code == 401

    async def count():
        async with factory() as db:
            return len((await db.execute(select(RawWebhookEvent))).scalars().all())

    assert asyncio.run(count()) == 1
