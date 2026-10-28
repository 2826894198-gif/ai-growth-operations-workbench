"""Optimization pass unit tests: canonical entity, metrics, RBAC, bindings, jobs."""

from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.execution.bindings import (
    compute_action_package_hash,
    validate_binding,
)
from app.services import (
    entity_service,
    job_registry_service,
    metric_service,
)
from app.services.auth_service import (
    ensure_membership,
    get_or_create_user,
    has_permission,
    seed_demo_admin,
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
async def test_entity_registry_resolve_and_external_ref(db):
    entity = await entity_service.resolve_or_create_entity(
        db,
        workspace_id="ws_main",
        brand_id=None,
        entity_type="CAMPAIGN",
        display_name="META:camp_1001",
        external_refs=[{"provider": "META", "connected_account_id": "acc_1", "external_type": "PRIMARY", "external_id": "camp_1001"}],
    )
    await db.flush()
    assert entity.id is not None
    external_id = await entity_service.resolve_external_id(
        db,
        entity_id=str(entity.id),
        provider="META",
        connected_account_id="acc_1",
    )
    assert external_id == "camp_1001"
    found = await entity_service.find_entity_by_external(
        db,
        workspace_id="ws_main",
        provider="META",
        external_id="camp_1001",
        connected_account_id="acc_1",
    )
    assert found is not None and str(found.id) == str(entity.id)


@pytest.mark.asyncio
async def test_metric_definition_seed_and_query(db):
    created = await metric_service.seed_metric_definitions(db)
    await db.flush()
    assert created >= 10
    definition = await metric_service.get_definition(db, "paid_roas")
    assert definition is not None
    assert definition.measurement_basis == "PLATFORM_REPORTED"
    result = await metric_service.query_metric(db, workspace_id="ws_main", metric_key="content_count")
    assert result["ok"] is True
    assert result["value"] == 0.0


@pytest.mark.asyncio
async def test_rbac_workspace_membership(db):
    admin = await seed_demo_admin(db)
    await db.flush()
    assert await has_permission(db, user=admin, workspace_id="ws_main", permission="EXECUTE") is True
    viewer = await get_or_create_user(db, email="demo-user-002@example.test", roles=[])
    await ensure_membership(db, user_id=str(viewer.id), workspace_id="ws_main", role="VIEWER")
    await db.flush()
    assert await has_permission(db, user=viewer, workspace_id="ws_main", permission="READ") is True
    assert await has_permission(db, user=viewer, workspace_id="ws_main", permission="EXECUTE") is False
    assert await has_permission(db, user=viewer, workspace_id="ws_other", permission="READ") is False


def test_action_package_hash_binding():
    payload = {
        "workspace_id": "ws_main",
        "canonical_entity_id": "entity_1",
        "action_type": "META_CHANGE_BUDGET",
        "requested_change": {"proposed_budget": "115"},
        "policy_version": 1,
        "credential_version": "cred_v1",
        "metric_snapshot_id": "snap_1",
        "approval_id": "approval_1",
    }
    first = compute_action_package_hash(**payload)
    second = compute_action_package_hash(**payload)
    assert first == second
    changed = compute_action_package_hash(**{**payload, "requested_change": {"proposed_budget": "150"}})
    assert first != changed
    intent = SimpleNamespace(action_package_hash=first)
    valid = validate_binding(intent=intent, **payload)
    assert valid["ok"] is True
    intent.action_package_hash = changed
    mismatch = validate_binding(intent=intent, **payload)
    assert mismatch["ok"] is False
    assert mismatch["code"] == "APPROVAL_MISMATCH"


@pytest.mark.asyncio
async def test_job_registry_idempotent(db):
    run = await job_registry_service.start_job(
        db,
        job_type="execution",
        queue="execution",
        idempotency_key="job-key-1",
        workspace_id="ws_main",
    )
    await db.flush()
    duplicate = await job_registry_service.start_job(
        db,
        job_type="execution",
        queue="execution",
        idempotency_key="job-key-1",
        workspace_id="ws_main",
    )
    await db.flush()
    assert str(duplicate.id) == str(run.id)
    attempt = await job_registry_service.start_attempt(db, run)
    await db.flush()
    await job_registry_service.complete_attempt(db, run, attempt, result={"ok": True})
    await db.flush()
    assert run.status == "SUCCEEDED"
