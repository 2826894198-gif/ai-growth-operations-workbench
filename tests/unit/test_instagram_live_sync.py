from datetime import datetime, timezone

import pytest
from app.core.config import settings
from app.core.database import Base
from app.models.instagram import InstagramOAuthCredential, InstagramSyncRun
from app.models.raw import RawApiPayload
from app.models.social import ConnectedAccount, ProviderConnection
from app.services.instagram.business_login import authorization_url
from app.services.instagram.live_read_model import live_content, live_overview
from app.services.instagram.live_sync import sync_instagram_connection
from app.services.instagram.token_vault import store_access_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


class FakeInstagramClient:
    async def get_profile(self, *, access_token):
        return {
            "user_id": "ig_live_test_001",
            "username": "integration_test_account",
            "name": "Integration Test Account",
            "account_type": "CREATOR",
            "followers_count": 120,
            "media_count": 1,
        }

    async def get_account_insights(self, **_kwargs):
        return {
            "data": [
                {"name": "reach", "values": [{"value": 200}]},
                {"name": "profile_views", "values": [{"value": 20}]},
                {"name": "profile_links_taps", "values": [{"value": 3}]},
                {"name": "views", "values": [{"value": 300}]},
                {"name": "total_interactions", "values": [{"value": 33}]},
                {
                    "name": "follows_and_unfollows",
                    "values": [{"value": {"follows": 5, "unfollows": 1}}],
                },
            ]
        }

    async def get_media(self, **_kwargs):
        return {
            "data": [
                {
                    "id": "ig_live_media_001",
                    "media_type": "VIDEO",
                    "media_product_type": "REELS",
                    "caption": "test reel",
                    "timestamp": "2026-08-24T00:00:00+00:00",
                    "like_count": 10,
                    "comments_count": 2,
                }
            ]
        }

    async def get_media_insights(self, **_kwargs):
        return {
            "data": [
                {"name": "reach", "values": [{"value": 80}]},
                {"name": "shares", "values": [{"value": 4}]},
                {"name": "saved", "values": [{"value": 5}]},
                {"name": "views", "values": [{"value": 120}]},
            ]
        }

    async def aclose(self):
        return None


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def live_mode():
    original = (
        settings.instagram_demo_mode,
        settings.instagram_sync_enabled,
        settings.social_provider_mode,
    )
    settings.instagram_demo_mode = False
    settings.instagram_sync_enabled = True
    settings.social_provider_mode = "live"
    try:
        yield
    finally:
        (
            settings.instagram_demo_mode,
            settings.instagram_sync_enabled,
            settings.social_provider_mode,
        ) = original


@pytest.mark.asyncio
async def test_live_sync_persists_raw_snapshots_without_exposing_token(db, live_mode):
    connection = ProviderConnection(
        workspace_id="ws_live_test",
        provider="INSTAGRAM",
        connection_type="OAUTH",
        external_identity_id="ig_live_test_001",
        status="HEALTHY",
        authorized_scopes=[
            "instagram_business_basic",
            "instagram_business_manage_insights",
        ],
    )
    db.add(connection)
    await db.flush()
    account = ConnectedAccount(
        workspace_id="ws_live_test",
        connection_id=str(connection.id),
        provider="INSTAGRAM",
        platform="INSTAGRAM",
        account_type="INSTAGRAM_CREATOR",
        external_account_id="ig_live_test_001",
        username="integration_test_account",
        status="LINKED",
    )
    db.add(account)
    await db.flush()
    connection.credential_reference = await store_access_token(
        db,
        connection_id=str(connection.id),
        access_token="test-only-token-not-user-data",
        token_type="bearer",
        expires_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        granted_scopes=[
            "instagram_business_basic",
            "instagram_business_manage_insights",
        ],
    )
    await db.commit()

    result = await sync_instagram_connection(
        db,
        workspace_id="ws_live_test",
        connection_id=str(connection.id),
        client=FakeInstagramClient(),
    )
    await db.commit()

    overview = await live_overview(db, workspace_id="ws_live_test", days=28)
    content = await live_content(db, workspace_id="ws_live_test")
    raw_rows = (await db.execute(select(RawApiPayload))).scalars().all()
    credential = (await db.execute(select(InstagramOAuthCredential))).scalar_one()
    sync_run = (await db.execute(select(InstagramSyncRun))).scalar_one()

    assert result["status"] == "SUCCESS"
    assert sync_run.status == "SUCCESS"
    assert overview["source"]["mode"] == "LIVE"
    assert (
        overview["raw"]["current_account_snapshot"]["metrics"]["follower_count"]
        == 120.0
    )
    assert content["total"] == 1
    assert all(
        "test-only-token-not-user-data" not in str(row.payload) for row in raw_rows
    )
    assert "test-only-token-not-user-data" not in credential.ciphertext


def test_business_login_authorization_url_uses_state_not_pkce():
    url = authorization_url(
        app_id="test-app-id",
        redirect_uri="https://staging.example.invalid/api/v1/connections/instagram/oauth/callback",
        state="state-value",
        scopes=["instagram_business_basic", "instagram_business_manage_insights"],
    )

    assert "state=state-value" in url
    assert "instagram_business_manage_insights" in url
    assert "enable_fb_login" not in url
    assert "code_challenge" not in url
