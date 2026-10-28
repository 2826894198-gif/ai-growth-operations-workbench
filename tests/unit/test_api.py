import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_environment_health_service
from app.core.database import Base, get_db
from app.main import app
from app.models.browser_profile import BrowserProfile
from app.models.browser_profile_audit import BrowserProfileAudit
from app.models.browser_task import BrowserTask
from app.models.environment_health import EnvironmentHealthCheck
from app.services.environment_health_service import EnvironmentHealthService


@pytest.fixture
def app_fixture():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    async def init_schema():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_schema())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    yield factory
    asyncio.run(engine.dispose())


def test_healthz_and_overview(app_fixture):
    async def override_get_db():
        async with app_fixture() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_environment_health_service] = lambda: EnvironmentHealthService()
    with TestClient(app) as client:
        assert client.get("/healthz").json()["status"] == "ok"
        overview = client.get("/api/v1/environment/overview").json()
        assert overview == {
            "total_profiles": 0,
            "healthy_profiles": 0,
            "unhealthy_profiles": 0,
            "running_browsers": 0,
            "queued_tasks": 0,
            "failed_tasks": 0,
        }
        assert client.get("/api/v1/environment/alerts").json() == []
    app.dependency_overrides.clear()


def test_profile_detail_serializes_relations(app_fixture):
    async def override_get_db():
        async with app_fixture() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_environment_health_service] = lambda: EnvironmentHealthService()

    import asyncio

    async def seed():
        async with app_fixture() as session:
            profile = BrowserProfile(name="Test-US-01", profile_type="test", status="INACTIVE")
            session.add(profile)
            await session.flush()
            session.add(
                EnvironmentHealthCheck(
                    profile_id=profile.id,
                    status="HEALTHY",
                    country="US",
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.add(
                BrowserTask(
                    profile_id=profile.id,
                    task_type="smoke_test",
                    status="SUCCESS",
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.add(
                BrowserProfileAudit(
                    profile_id=profile.id,
                    field="profile.create",
                    source="test",
                    created_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
            return profile.id

    profile_id = asyncio.run(seed())

    with TestClient(app) as client:
        response = client.get(f"/api/v1/browser-profiles/{profile_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Test-US-01"
        assert body["health_checks"][0]["status"] == "HEALTHY"
        assert body["recent_tasks"][0]["task_type"] == "smoke_test"
        assert body["audits"][0]["field"] == "profile.create"
    app.dependency_overrides.clear()
