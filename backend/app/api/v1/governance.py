"""Optimization-pass APIs: entities, metrics, recommendation cases,
decision assistant, job registry, provider control plane, auth."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_permission
from app.core.database import get_db
from app.models.governance import EntityRegistry, User
from app.services import (
    entity_service,
    job_registry_service,
    metric_service,
    provider_control_plane,
)
from app.services.auth_service import seed_demo_admin, user_dict
from app.services.recommendation_case_service import build_case, simulate, transition

router = APIRouter()


class EntityCreate(BaseModel):
    workspace_id: str
    brand_id: Optional[str] = None
    entity_type: str
    display_name: Optional[str] = None
    external_refs: Optional[List[Dict[str, Any]]] = None


class MetricQuery(BaseModel):
    workspace_id: str
    metric_key: str
    account_ids: Optional[List[str]] = None
    start: Optional[str] = None
    end: Optional[str] = None


class CaseTransition(BaseModel):
    target: str
    actor: str = "operator"
    reason: Optional[str] = None


class CaseSimulate(BaseModel):
    actor: str = "operator"
    parameters: Optional[Dict[str, Any]] = None


class AssistantRequest(BaseModel):
    workspace_id: str
    user_request: str
    scope: Optional[Dict[str, Any]] = None


class DraftIntent(BaseModel):
    recommendation_id: str
    actor: str = "assistant"


class CredentialCreate(BaseModel):
    workspace_id: str
    provider: str
    purpose: str
    secret_ref: str
    connected_account_id: Optional[str] = None
    scopes: Optional[List[str]] = None
    expires_at: Optional[str] = None


def _entity_dict(entity: EntityRegistry) -> dict:
    return entity_service.entity_dict(entity)


@router.get("/entities", dependencies=[Depends(require_permission("READ"))])
async def list_entities(
    workspace_id: str = Query(...),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    query = select(EntityRegistry).where(EntityRegistry.workspace_id == workspace_id).order_by(EntityRegistry.created_at.desc()).limit(limit)
    if entity_type:
        query = query.where(EntityRegistry.entity_type == entity_type.upper())
    rows = (await db.execute(query)).scalars().all()
    return [_entity_dict(r) for r in rows]


@router.post("/entities", dependencies=[Depends(require_permission("ANALYZE"))])
async def create_entity(data: EntityCreate, db: AsyncSession = Depends(get_db)):
    entity = await entity_service.resolve_or_create_entity(
        db,
        workspace_id=data.workspace_id,
        brand_id=data.brand_id,
        entity_type=data.entity_type,
        display_name=data.display_name,
        external_refs=data.external_refs,
    )
    await db.commit()
    return _entity_dict(entity)


@router.get("/entities/{entity_id}", dependencies=[Depends(require_permission("READ"))])
async def get_entity(entity_id: str, db: AsyncSession = Depends(get_db)):
    entity = await entity_service.get_entity(db, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="entity not found")
    return _entity_dict(entity)


@router.get("/entities/{entity_id}/resolve-external", dependencies=[Depends(require_permission("READ"))])
async def resolve_external(
    entity_id: str,
    provider: str = Query(...),
    connected_account_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    external_id = await entity_service.resolve_external_id(
        db,
        entity_id=entity_id,
        provider=provider,
        connected_account_id=connected_account_id,
    )
    return {"entity_id": entity_id, "provider": provider, "external_id": external_id}


@router.get("/metrics/definitions", dependencies=[Depends(require_permission("READ"))])
async def metric_definitions(db: AsyncSession = Depends(get_db)):
    return await metric_service.list_definitions(db)


@router.post("/metrics/seed", dependencies=[Depends(require_permission("ANALYZE"))])
async def seed_metrics(db: AsyncSession = Depends(get_db)):
    created = await metric_service.seed_metric_definitions(db)
    await db.commit()
    return {"created": created}


@router.post("/metrics/query", dependencies=[Depends(require_permission("READ"))])
async def query_metric(data: MetricQuery, db: AsyncSession = Depends(get_db)):
    from datetime import date

    start = date.fromisoformat(data.start) if data.start else None
    end = date.fromisoformat(data.end) if data.end else None
    return await metric_service.query_metric(
        db,
        workspace_id=data.workspace_id,
        metric_key=data.metric_key,
        account_ids=data.account_ids,
        start=start,
        end=end,
    )


@router.get("/recommendation-cases/{recommendation_id}", dependencies=[Depends(require_permission("READ"))])
async def get_case(recommendation_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await build_case(db, recommendation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/recommendation-cases/{recommendation_id}/simulate", dependencies=[Depends(require_permission("ANALYZE"))])
async def simulate_case(recommendation_id: str, data: CaseSimulate = None, db: AsyncSession = Depends(get_db)):
    await simulate(db, recommendation_id, data.actor if data else "operator", parameters=data.parameters if data else None)
    await db.commit()
    return await build_case(db, recommendation_id)


@router.post("/recommendation-cases/{recommendation_id}/transition", dependencies=[Depends(require_permission("APPROVE"))])
async def transition_case(recommendation_id: str, data: CaseTransition, db: AsyncSession = Depends(get_db)):
    try:
        await transition(db, recommendation_id, data.target.upper(), data.actor, data.reason)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await build_case(db, recommendation_id)


@router.post("/recommendation-cases/{recommendation_id}/draft-intent", dependencies=[Depends(require_permission("APPROVE"))])
async def draft_intent(recommendation_id: str, data: DraftIntent = None, db: AsyncSession = Depends(get_db)):
    from app.ai.decision_assistant import draft_execution_intent

    result = await draft_execution_intent(db, recommendation_id=recommendation_id, actor=data.actor if data else "assistant")
    await db.rollback()
    return result


@router.post("/decision-assistant", dependencies=[Depends(require_permission("ANALYZE"))])
async def decision_assistant(data: AssistantRequest, db: AsyncSession = Depends(get_db)):
    from app.ai.decision_assistant import run_decision_assistant

    return await run_decision_assistant(db, workspace_id=data.workspace_id, user_request=data.user_request, scope=data.scope)


@router.get("/job-registry", dependencies=[Depends(require_permission("READ"))])
async def job_registry(
    workspace_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await job_registry_service.list_job_runs(db, workspace_id=workspace_id, status=status, limit=limit)


@router.get("/provider-manifests", dependencies=[Depends(require_permission("READ"))])
async def provider_manifests(db: AsyncSession = Depends(get_db)):
    return await provider_control_plane.list_manifests(db)


@router.get("/credential-health", dependencies=[Depends(require_permission("READ"))])
async def credential_health(
    workspace_id: str = Query(...),
    provider: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await provider_control_plane.credential_health(db, workspace_id=workspace_id, provider=provider)


@router.post("/credentials", dependencies=[Depends(require_permission("CONNECTION_ADMIN"))])
async def create_credential(data: CredentialCreate, db: AsyncSession = Depends(get_db)):
    from datetime import datetime

    expires = datetime.fromisoformat(data.expires_at) if data.expires_at else None
    try:
        row = await provider_control_plane.register_credential_ref(
            db,
            workspace_id=data.workspace_id,
            provider=data.provider,
            purpose=data.purpose,
            secret_ref=data.secret_ref,
            connected_account_id=data.connected_account_id,
            scopes=data.scopes,
            expires_at=expires,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(row.id), "provider": row.provider, "purpose": row.purpose, "status": row.status}


@router.get("/auth/me")
async def auth_me(user: Optional[User] = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user_dict(user)


@router.post("/auth/seed-admin", dependencies=[Depends(require_permission("CONNECTION_ADMIN"))])
async def seed_admin(db: AsyncSession = Depends(get_db)):
    user = await seed_demo_admin(db)
    await db.commit()
    return user_dict(user)
