"""Seed demo data for the Part 01 dashboard (no AdsPower required).

Usage (from repo root):
    DATABASE_URL=sqlite+aiosqlite:///./demo.db python scripts/seed_demo.py
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./demo.db")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.core.security import encrypt_secret  # noqa: E402
from app.integrations.adspower.mapper import FINGERPRINT_BASELINE  # noqa: E402
from app.models.browser_profile import BrowserProfile  # noqa: E402
from app.models.browser_profile_audit import BrowserProfileAudit  # noqa: E402
from app.models.browser_task import BrowserTask  # noqa: E402
from app.models.environment_health import EnvironmentHealthCheck  # noqa: E402
from app.models.mixins import new_uuid  # noqa: E402
from app.models.proxy import Proxy  # noqa: E402


def now(**delta) -> datetime:
    return datetime.now(timezone.utc) - timedelta(**delta)


async def main() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        proxies = {
            "east": Proxy(
                id=new_uuid(),
                provider="demo-isp",
                proxy_type="http",
                host="198.51.100.10",
                port=8080,
                username_encrypted=encrypt_secret("demo-user"),
                password_encrypted=encrypt_secret("demo-pass"),
                country="US",
                region="New York",
                city="New York",
                is_static=True,
                status="HEALTHY",
                last_ip="198.51.100.10",
                last_checked_at=now(hours=1),
                latency_ms=48,
            )
        }
        db.add_all(proxies.values())

        profiles = [
            BrowserProfile(
                id=new_uuid(),
                provider="adspower",
                provider_profile_id="ap-demo-1001",
                profile_no="01",
                name="Brand-US-East",
                profile_type="brand",
                platform="instagram",
                proxy_id=proxies["east"].id,
                country="US",
                region="New York",
                city="New York",
                timezone="America/New_York",
                language="en-US",
                browser_engine="ads_power_auto",
                os_type="auto",
                fingerprint_config=FINGERPRINT_BASELINE,
                status="INACTIVE",
                last_health_check_at=now(hours=2),
            ),
            BrowserProfile(
                id=new_uuid(),
                provider="adspower",
                provider_profile_id="ap-demo-1002",
                profile_no="02",
                name="Research-US-East",
                profile_type="research",
                platform="instagram",
                proxy_id=proxies["east"].id,
                country="US",
                region="California",
                city="San Francisco",
                timezone="America/Los_Angeles",
                language="en-US",
                fingerprint_config=FINGERPRINT_BASELINE,
                status="RUNNING",
                last_opened_at=now(minutes=10),
                last_health_check_at=now(hours=1),
            ),
            BrowserProfile(
                id=new_uuid(),
                provider="adspower",
                provider_profile_id="ap-demo-1003",
                profile_no="03",
                name="Competitor-US-East",
                profile_type="competitor",
                platform="meta",
                country="US",
                region="Texas",
                city="Dallas",
                timezone="America/Chicago",
                language="en-US",
                status="INACTIVE",
                last_health_check_at=now(days=1),
            ),
            BrowserProfile(
                id=new_uuid(),
                provider="adspower",
                provider_profile_id="ap-demo-1004",
                profile_no="04",
                name="Test-US-East",
                profile_type="test",
                platform="general",
                country="US",
                region="Virginia",
                city="Ashburn",
                timezone="America/New_York",
                language="en-US",
                status="INACTIVE",
            ),
        ]
        e2e_profile_id = os.environ.get("E2E_PROFILE_ID")
        if e2e_profile_id:
            profiles[3].provider_profile_id = e2e_profile_id
        db.add_all(profiles)
        await db.flush()

        checks = []
        for profile in profiles:
            checks.append(
                EnvironmentHealthCheck(
                    profile_id=profile.id,
                    status="HEALTHY",
                    public_ip="198.51.100.10",
                    country="US",
                    timezone=profile.timezone or "America/New_York",
                    language="en-US",
                    proxy_latency_ms=48,
                    browser_launch_ms=3200,
                    checks={
                        "api": {"ok": True},
                        "proxy": {"ok": True},
                        "country": {"ok": True},
                        "browser_launch": {"ok": True},
                        "cdp": {"ok": True},
                        "page_load": {"ok": True},
                        "timezone": {"ok": True},
                        "language": {"ok": True},
                    },
                    created_at=now(days=2),
                )
            )
        checks.append(
            EnvironmentHealthCheck(
                profile_id=profiles[1].id,
                status="DEGRADED",
                public_ip="198.51.100.10",
                country="US",
                timezone="Asia/Tokyo",
                language="en-US",
                proxy_latency_ms=210,
                browser_launch_ms=1800,
                checks={
                    "timezone": {"ok": False, "expected": "America/Los_Angeles"},
                },
                created_at=now(hours=1),
            )
        )
        db.add_all(checks)

        tasks = [
            BrowserTask(
                profile_id=profiles[0].id,
                task_type="environment_check",
                task_name="environment_check",
                status="SUCCESS",
                payload={},
                result={"environment": {"status": "HEALTHY"}},
                started_at=now(hours=3),
                finished_at=now(hours=3) + timedelta(minutes=2),
                created_at=now(hours=3),
            ),
            BrowserTask(
                profile_id=profiles[0].id,
                task_type="smoke_test",
                task_name="smoke_test",
                status="SUCCESS",
                payload={},
                result={"title": "Example Domain"},
                started_at=now(days=1),
                finished_at=now(days=1) + timedelta(minutes=1),
                created_at=now(days=1),
            ),
            BrowserTask(
                profile_id=profiles[1].id,
                task_type="environment_check",
                task_name="environment_check",
                status="FAILED",
                payload={},
                error_code="ENV_TIMEZONE_MISMATCH",
                error_message="timezone mismatch: America/Los_Angeles != Asia/Tokyo",
                started_at=now(hours=1),
                finished_at=now(hours=1) + timedelta(minutes=2),
                created_at=now(hours=1),
            ),
            BrowserTask(
                profile_id=profiles[2].id,
                task_type="public_page_snapshot",
                task_name="snapshot",
                status="QUEUED",
                payload={"url": "https://example.com"},
                created_at=now(minutes=5),
            ),
        ]
        db.add_all(tasks)
        db.add_all(
            [
                BrowserProfileAudit(
                    profile_id=profiles[0].id,
                    field="profile.create",
                    old_value=None,
                    new_value="created with US-East baseline",
                    operator="seed",
                    source="demo",
                    created_at=now(days=5),
                )
            ]
        )
        await db.commit()

    print(f"seeded demo data into {os.environ['DATABASE_URL']}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
