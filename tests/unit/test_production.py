"""PART 07 production hardening unit tests."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.services import (
    browser_node_service,
    oauth_service,
    release_service,
    retention_service,
)


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
async def test_oauth_transaction_single_use(db):
    tx = await oauth_service.start_oauth_transaction(db, workspace_id="ws_main", provider="META", initiated_by="test")
    consumed = await oauth_service.consume_oauth_transaction(db, workspace_id="ws_main", provider="META", state=tx["state"])
    assert consumed.status == "COMPLETED"
    with pytest.raises(ValueError):
        await oauth_service.consume_oauth_transaction(db, workspace_id="ws_main", provider="META", state=tx["state"])


@pytest.mark.asyncio
async def test_oauth_transaction_workspace_binding(db):
    tx = await oauth_service.start_oauth_transaction(db, workspace_id="ws_a", provider="META", initiated_by="test")
    with pytest.raises(ValueError):
        await oauth_service.consume_oauth_transaction(db, workspace_id="ws_b", provider="META", state=tx["state"])


@pytest.mark.asyncio
async def test_browser_node_heartbeat_and_revoke(db):
    node = await browser_node_service.register_node(
        db,
        name="mac-node-1",
        allowed_workspace_ids=["ws_main"],
        credential_reference="env:BROWSER_NODE_SECRET",
    )
    await db.flush()
    online = await browser_node_service.heartbeat(db, node_id=str(node.id), workspace_id="ws_main")
    assert online.status == "ONLINE"
    with pytest.raises(ValueError):
        await browser_node_service.heartbeat(db, node_id=str(node.id), workspace_id="ws_other")
    await browser_node_service.revoke_node(db, str(node.id), "admin")
    await db.flush()
    with pytest.raises(ValueError):
        await browser_node_service.heartbeat(db, node_id=str(node.id))


@pytest.mark.asyncio
async def test_release_and_retention(db):
    release = await release_service.record_release(
        db,
        version="0.1.0",
        git_sha="abc123",
        environment="staging",
        db_revision="0009_production_hardening",
    )
    await db.flush()
    assert release.id is not None
    created = await retention_service.seed_retention_policies(db)
    await db.flush()
    assert created >= 8
    policies = await retention_service.list_policies(db)
    assert any(p["category"] == "execution_audit" for p in policies)
