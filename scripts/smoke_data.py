"""PART 02 data-platform smoke test (works in mock mode without credentials).

Usage:  DATABASE_URL=sqlite+aiosqlite:///./smoke.db REDIS_URL=redis://127.0.0.1:6379/0 \
        DATA_PROVIDER_MODE=mock python scripts/smoke_data.py
"""

import asyncio
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/smoke_data.db")
os.environ.setdefault("DATA_PROVIDER_MODE", "mock")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import generate_fixtures  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.etl.pipeline import run_google_pipeline, run_meta_pipeline  # noqa: E402
from app.integrations.shopify.hmac import compute_hmac, verify_webhook  # noqa: E402
from app.models.ad_performance import AdPerformanceDaily  # noqa: E402
from app.models.data_source import DataSource  # noqa: E402
from app.services.metrics_service import MetricsService  # noqa: E402

RESULTS = []


def check(name: str, ok: bool, detail: str = "", skipped: bool = False) -> None:
    RESULTS.append((name, ok, detail, skipped))
    print(f"{'SKIP' if skipped else 'PASS' if ok else 'FAIL':<5} {name}" + (f"  {detail}" if detail else ""), flush=True)


async def redis_ping() -> bool:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=2)
        result = await client.ping()
        await client.aclose()
        return bool(result)
    except Exception:  # noqa: BLE001
        return False


async def main() -> int:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        result = await conn.execute(text("SELECT 1"))
        check("Database", result.scalar() == 1, "SQLite/PostgreSQL reachable")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    check("Redis", await redis_ping(), "redis ping", skipped=False)

    rng = random.Random("smoke")
    meta = generate_fixtures.build_meta(7, rng, "healthy_growth")
    google = generate_fixtures.build_google(7, rng, "healthy_growth")
    async with factory() as db:
        sources = [
            DataSource(provider="META_ADS", name="Smoke Meta", external_account_id="act_smoke", status="UNKNOWN", meta={"scenario": "healthy_growth"}),
            DataSource(provider="GOOGLE_ADS", name="Smoke Google", external_account_id="smoke-google", status="UNKNOWN", meta={"scenario": "healthy_growth"}),
            DataSource(provider="SHOPIFY", name="Smoke Shopify", external_account_id="smoke-shop.test", status="UNKNOWN", meta={"scenario": "healthy_growth"}),
        ]
        db.add_all(sources)
        await db.flush()
        source_map = {s.provider: s for s in sources}
        source_ids = {provider: str(source.id) for provider, source in source_map.items()}

        from app.ingestion.orchestrator import run_connection_test

        for provider in ("META_ADS", "GOOGLE_ADS", "SHOPIFY"):
            result = await run_connection_test(db, provider, source_ids[provider])
            check(f"{provider} Connection", result.get("ok"), "mock validate_connection")

        meta_counts = await run_meta_pipeline(
            db, source_ids["META_ADS"],
            accounts=meta["accounts"], campaigns=meta["campaigns"], ad_groups=meta["ad_groups"],
            ads=meta["ads"], creatives=meta["creatives"], performance=meta["performance"],
            sync_job_id="smoke",
        )
        google_counts = await run_google_pipeline(
            db, source_ids["GOOGLE_ADS"],
            accounts=google["accounts"], campaigns=google["campaigns"], ad_groups=google["ad_groups"],
            ads=google["ads"], asset_groups=google["asset_groups"], keywords=google["keywords"],
            search_terms=google["search_terms"], conversion_actions=google["conversion_actions"],
            performance=google["performance"], sync_job_id="smoke",
        )
        check("Mock Backfill", meta_counts.inserted > 0 and google_counts.inserted > 0, "7-day fixtures through ETL")
        check("ETL", meta_counts.failed == 0 and google_counts.failed == 0, f"failed={meta_counts.failed + google_counts.failed}")

        before = (await db.execute(select(func.count(AdPerformanceDaily.id)))).scalar_one()
        await run_meta_pipeline(
            db, source_ids["META_ADS"],
            accounts=[], campaigns=meta["campaigns"], ad_groups=[], ads=[], creatives=[],
            performance=meta["performance"], sync_job_id="smoke-again",
        )
        after = (await db.execute(select(func.count(AdPerformanceDaily.id)))).scalar_one()
        check("Idempotency", before == after, f"daily facts before={before} after={after}")

        secret = "smoke-secret"
        body = b'{"id": 1}'
        signature = compute_hmac(body, secret)
        check("Webhook HMAC", verify_webhook(body, secret, signature) and not verify_webhook(body, secret, "bad"), "sha256 hmac")

        await db.commit()
        from app.models.raw import RawWebhookEvent

        db.add(RawWebhookEvent(provider="SHOPIFY", delivery_id="d1", topic="orders/create", payload={"id": 1}, verified=True))
        await db.flush()
        try:
            db.add(RawWebhookEvent(provider="SHOPIFY", delivery_id="d1", topic="orders/create", payload={"id": 1}, verified=True))
            await db.flush()
            check("Webhook Dedup", False, "duplicate delivery accepted")
        except Exception:  # noqa: BLE001
            check("Webhook Dedup", True, "unique(provider, delivery_id)")
            await db.rollback()

        # Grain safety: insert an AD row on the same platform/date; platform metric must not double count.
        campaign_row = (
            await db.execute(
                select(AdPerformanceDaily).where(
                    AdPerformanceDaily.entity_type == "CAMPAIGN",
                    AdPerformanceDaily.platform == "META_ADS",
                ).limit(1)
            )
        ).scalar_one()
        ad_row = dict(
            data_source_id=campaign_row.data_source_id,
            marketing_account_id=campaign_row.marketing_account_id,
            platform="META_ADS",
            entity_type="AD",
            entity_id=None,
            external_entity_id="smoke-ad",
            date=campaign_row.date,
            currency="USD",
            spend_amount=999999,
            impressions=1,
            clicks=1,
        )
        db.add(AdPerformanceDaily(**ad_row))
        await db.commit()
        metrics = MetricsService()
        platforms = await metrics.platforms(db, campaign_row.date.isoformat(), campaign_row.date.isoformat())
        meta_platform = next(p for p in platforms if p["platform"] == "META_ADS")
        check("Metric Grain Safety", meta_platform["spend"] < 900000, "AD row excluded from platform total")

        overview = await metrics.overview(db)
        check("Metrics Overview", "paid_spend" in overview and "blended_roas" in overview, "overview shape")

        refreshed = (await db.execute(select(DataSource).where(DataSource.id == source_ids["META_ADS"]))).scalar_one()
        check("Freshness", refreshed.last_successful_sync_at is not None, "source last_successful_sync_at set")

        from app.etl.validators import dq_negative_spend

        check("DQ Check", dq_negative_spend(__import__("decimal").Decimal("-1"), "x") is not None, "negative spend rule")

    await engine.dispose()
    failed = sum(1 for _, ok, _, skipped in RESULTS if not ok and not skipped)
    print("SMOKE DATA " + ("PASSED" if failed == 0 else "FAILED"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
