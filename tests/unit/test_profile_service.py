import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.security import encrypt_secret
from app.integrations.adspower.client import AdsPowerClient
from app.integrations.adspower.mapper import FINGERPRINT_BASELINE, build_create_payload
from app.integrations.adspower.profile_service import AdsPowerProfileService
from app.integrations.adspower.schemas import CreateProfileData
from app.models.browser_profile import BrowserProfile
from app.models.browser_profile_audit import BrowserProfileAudit
from app.models.proxy import Proxy
from app.schemas.browser_profile import BrowserProfileCreate


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def test_build_create_payload_uses_baseline_and_proxy():
    profile = BrowserProfile(name="Brand-US-01", profile_type="brand", platform="instagram", country="US")
    proxy = Proxy(
        provider="isp",
        proxy_type="http",
        host="us-proxy.example.com",
        port=8080,
        country="US",
    )
    payload = build_create_payload(profile, proxy, "user", "pass")
    assert payload["name"] == "Brand-US-01"
    assert payload["group_name"] == "BRAND"
    assert payload["user_proxy_config"]["proxy_host"] == "us-proxy.example.com"
    assert payload["user_proxy_config"]["proxy_user"] == "user"
    assert payload["fingerprint_config"]["webrtc"] == "disabled"
    assert payload["fingerprint_config"]["language"] == ["en-US", "en"]
    assert payload["fingerprint_config"] == FINGERPRINT_BASELINE


@pytest.mark.asyncio
async def test_create_profile_creates_ads_power_profile_and_audit(db, monkeypatch):
    proxy = Proxy(
        provider="isp",
        proxy_type="http",
        host="1.2.3.4",
        port=8080,
        country="US",
        username_encrypted=encrypt_secret("u"),
        password_encrypted=encrypt_secret("p"),
    )
    db.add(proxy)
    await db.commit()
    await db.refresh(proxy)

    client = AdsPowerClient(base_url="http://localhost:50325", api_key="k")

    async def fake_create(payload):
        return CreateProfileData(profile_id="ap-123", message="success")

    monkeypatch.setattr(client, "create_profile", fake_create)
    service = AdsPowerProfileService(client)
    profile = await service.create_profile(
        db,
        BrowserProfileCreate(
            name="Test-US-01",
            profile_type="test",
            proxy_id=proxy.id,
            country="US",
        ),
    )
    assert profile.provider_profile_id == "ap-123"
    assert profile.status == "INACTIVE"

    audits = list((await db.execute(select(BrowserProfileAudit))).scalars())
    assert len(audits) == 1
    assert audits[0].field == "profile.create"
