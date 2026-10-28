"""PART 06-01 golden unit tests: scope isolation, metric semantics, mapping."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.integrations.social.mock import MockSocialProvider
from app.models.social import (
    ContentPublication,
)
from app.services.oauth_service import start_oauth_transaction
from app.services.social.connection_service import (
    complete_oauth_callback,
    link_accounts,
)
from app.services.social.content_service import (
    create_manual_promotion_link,
    sync_content,
)
from app.services.social.metric_catalog import aggregate_values
from app.services.social.scope_service import resolve_accounts


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
async def test_workspace_isolation(db):
    tx = await start_oauth_transaction(db, workspace_id="ws_a", provider="META", initiated_by="test")
    connection = await complete_oauth_callback(db, workspace_id="ws_a", provider="META", state=tx["state"], code="c", actor="test")
    await db.flush()
    await link_accounts(
        db,
        connection_id=str(connection.id),
        external_account_ids=["ig_a"],
        workspace_id="ws_a",
        brand_id=None,
        account_group_id=None,
        actor="test",
    )
    await db.flush()
    accounts_a = await resolve_accounts(db, workspace_id="ws_a")
    accounts_b = await resolve_accounts(db, workspace_id="ws_b")
    assert len(accounts_a) == 1
    assert len(accounts_b) == 0


def test_metric_semantics_non_additive():
    result = aggregate_values([100, 200], {"aggregation_type": "NON_ADDITIVE"})
    assert result["value"] == 300
    assert "NOT a deduplicated unique audience" in result["caveat"]


def test_metric_semantics_unique_estimate():
    result = aggregate_values([100, 200], {"aggregation_type": "UNIQUE_ESTIMATE"})
    assert result["value"] == 300
    assert "NOT unique cross-platform reach" in result["caveat"]


def test_metric_semantics_rate_weighted():
    result = aggregate_values([0.1, 0.2], {"aggregation_type": "RATE"}, rates_denominator=[100, 300])
    assert result["value"] is not None
    assert 0.15 <= result["value"] <= 0.2


@pytest.mark.asyncio
async def test_promotion_mapping_drift_detected(db):
    from app.execution.revalidation import revalidate

    tx = await start_oauth_transaction(db, workspace_id="ws_main", provider="META", initiated_by="test")
    connection = await complete_oauth_callback(db, workspace_id="ws_main", provider="META", state=tx["state"], code="c", actor="test")
    linked = await link_accounts(
        db,
        connection_id=str(connection.id),
        external_account_ids=["ig_a"],
        workspace_id="ws_main",
        brand_id=None,
        account_group_id=None,
        actor="test",
    )
    await db.flush()
    account = linked[0]
    await sync_content(db, [str(account.id)], actor="test", days=5)
    publication = (await db.execute(__import__("sqlalchemy").select(ContentPublication).limit(1))).scalar_one()
    link = await create_manual_promotion_link(
        db,
        publication_id=str(publication.id),
        payload={"paid_platform": "META_ADS", "creative_id": "cr_1", "ad_id": "ad_1", "campaign_id": "camp_1"},
        actor="test",
    )
    await db.flush()
    fake_intent = SimpleNamespace(
        requested_change={"promotion_link_id": str(link.id), "ad_id": "ad_WRONG", "campaign_id": "camp_WRONG"},
        provider="META",
        action_type="META_CHANGE_BUDGET",
        entity_type="CAMPAIGN",
        entity_id="camp_1",
        external_entity_id=None,
        expected_before_state={},
        workspace_id=None,
        approval_id="x",
        id="fake",
        recommendation_id="x",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    result = await revalidate(db, intent=fake_intent, provider_state={})
    mapping_check = next(check for check in result["checks"] if check["name"] == "promotion_mapping_valid")
    assert mapping_check["ok"] is False
    assert "drifted" in mapping_check["detail"]


@pytest.mark.asyncio
async def test_mock_provider_discovery_multiple_accounts():
    provider = MockSocialProvider(platform="META")
    accounts = await provider.discover_accounts(SimpleNamespace(provider="META", external_identity_id="x"))
    assert len(accounts) >= 3
    capabilities = await provider.get_capabilities("ig_a")
    assert capabilities["CONTENT_VIEWS"] is True
