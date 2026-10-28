"""P0 account detection and review invariants."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.data_source import DataSource
from app.models.review import AccountDetectionSetting
from app.models.social import ConnectedAccount, ProviderConnection
from app.services.account_health_service import (
    account_health_detail,
    evaluate_account,
    health_summary,
    update_event_workflow,
)
from app.services.data_health_service import DataHealthService
from app.services.metric_service import seed_metric_definitions
from app.services.review_service import build_trends, create_review, resolve_period


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_health_dimensions_are_independent_and_workspace_scoped(db):
    now = datetime.now(timezone.utc)
    connection = ProviderConnection(
        workspace_id="ws_a",
        provider="META",
        status="HEALTHY",
        authorized_scopes=["read_insights"],
    )
    db.add(connection)
    await db.flush()
    account = ConnectedAccount(
        workspace_id="ws_a",
        connection_id=str(connection.id),
        provider="META",
        platform="INSTAGRAM",
        account_type="BUSINESS",
        external_account_id="ig_1",
        username="brand",
        status="LINKED",
        health_status="HEALTHY",
        last_profile_sync_at=now,
        last_content_sync_at=now,
        last_analytics_sync_at=now,
    )
    db.add(account)
    await db.flush()

    detail = await evaluate_account(db, account, now=now)
    assert detail["statuses"] == {
        "connection": "HEALTHY",
        "data": "HEALTHY",
        "performance": "HEALTHY",
        "content": "HEALTHY",
        "overall": "HEALTHY",
    }
    assert detail["data_usable"] is True
    assert (await health_summary(db, workspace_id="ws_b"))["counts"]["total_accounts"] == 0


@pytest.mark.asyncio
async def test_stale_data_blocks_business_conclusion(db):
    now = datetime.now(timezone.utc)
    connection = ProviderConnection(workspace_id="ws_main", provider="META", status="HEALTHY")
    db.add(connection)
    await db.flush()
    account = ConnectedAccount(
        workspace_id="ws_main",
        connection_id=str(connection.id),
        provider="META",
        platform="INSTAGRAM",
        account_type="BUSINESS",
        external_account_id="ig_stale",
        username="stale_brand",
        status="LINKED",
        health_status="HEALTHY",
        last_analytics_sync_at=now - timedelta(hours=2),
        last_content_sync_at=now - timedelta(hours=2),
    )
    db.add(account)
    await db.flush()

    detail = await evaluate_account(db, account, now=now)
    assert detail["statuses"]["connection"] == "HEALTHY"
    assert detail["statuses"]["data"] == "AT_RISK"
    assert detail["statuses"]["overall"] == "AT_RISK"
    assert detail["data_usable"] is False
    assert any(event["rule_code"] == "DATA_STALE" for event in detail["events"])


@pytest.mark.asyncio
async def test_data_health_does_not_cross_workspace(db):
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            DataSource(workspace_id="ws_a", provider="SHOPIFY", name="A", last_successful_sync_at=now),
            DataSource(workspace_id="ws_b", provider="SHOPIFY", name="B", last_successful_sync_at=now),
        ]
    )
    await db.flush()
    rows = await DataHealthService().freshness(db, workspace_id="ws_a")
    assert [row["name"] for row in rows] == ["A"]


def test_review_periods_use_complete_comparable_windows():
    daily = resolve_period("DAILY", end_date=datetime(2026, 8, 10, tzinfo=timezone.utc).date())
    assert daily["period_start"].isoformat() == "2026-08-10"
    assert daily["baseline_end"].isoformat() == "2026-08-09"

    weekly = resolve_period("WEEKLY", end_date=datetime(2026, 8, 9, tzinfo=timezone.utc).date())
    assert weekly["period_start"].isoformat() == "2026-08-03"
    assert weekly["baseline_start"].isoformat() == "2026-07-27"


@pytest.mark.asyncio
async def test_review_persists_an_immutable_metric_snapshot(db):
    await seed_metric_definitions(db)
    review = await create_review(
        db,
        workspace_id="ws_main",
        review_type="DAILY",
        days=None,
        end_date=datetime(2026, 8, 10, tzinfo=timezone.utc).date(),
        account_ids=[],
        summary="测试复盘",
        created_by="tester",
    )
    await db.flush()
    assert review.summary == "测试复盘"
    assert review.metric_snapshot["net_revenue"]["status"] == "NO_DATA"
    assert review.data_status == "UNKNOWN"


@pytest.mark.asyncio
async def test_workspace_detection_rules_and_event_workflow_are_persisted(db):
    now = datetime.now(timezone.utc)
    db.add(
        AccountDetectionSetting(
            workspace_id="ws_rules",
            sync_delay_minutes=10,
            sync_stale_minutes=30,
            content_inactive_days=3,
        )
    )
    connection = ProviderConnection(
        workspace_id="ws_rules",
        provider="META",
        status="HEALTHY",
    )
    db.add(connection)
    await db.flush()
    account = ConnectedAccount(
        workspace_id="ws_rules",
        connection_id=str(connection.id),
        provider="META",
        platform="INSTAGRAM",
        account_type="BUSINESS",
        external_account_id="ig_rules",
        username="rules_brand",
        status="LINKED",
        health_status="HEALTHY",
        last_analytics_sync_at=now - timedelta(minutes=20),
        last_content_sync_at=now - timedelta(minutes=20),
    )
    db.add(account)
    await db.flush()

    detail = await account_health_detail(
        db,
        workspace_id="ws_rules",
        account_id=str(account.id),
    )
    assert detail is not None
    assert detail["statuses"]["data"] == "WARNING"
    event = next(item for item in detail["events"] if item["rule_code"] == "DATA_DELAYED")
    assert event["workflow_status"] == "OPEN"

    updated = await update_event_workflow(
        db,
        workspace_id="ws_rules",
        account_id=str(account.id),
        rule_code="DATA_DELAYED",
        status="IN_PROGRESS",
        owner_id="operator",
    )
    assert updated is not None
    await db.flush()
    summary = await health_summary(db, workspace_id="ws_rules")
    assert summary["workflow_counts"]["IN_PROGRESS"] == 1
    assert summary["top_events"][0]["owner_id"] == "operator"


@pytest.mark.asyncio
async def test_review_trend_returns_complete_calendar_without_filling_unknowns(db):
    await seed_metric_definitions(db)
    trend = await build_trends(db, workspace_id="ws_empty", days=7)
    assert len(trend["rows"]) == 7
    assert trend["rows"][0]["net_revenue"] is None
    assert trend["rows"][0]["paid_spend"] is None
