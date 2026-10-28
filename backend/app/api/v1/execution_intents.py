"""Execution intents + approvals API (PART 06 §135-§136, §140-§143)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.execution_permissions import require_permission
from app.core.database import get_db
from app.execution.engine import dry_run_intent, execute_intent, shadow_execute_intent
from app.execution.intents import cancel_intent, get_intent
from app.execution.kill_switch import kill_switch_blocked
from app.execution.providers.factory import get_execution_provider
from app.execution.revalidation import revalidate
from app.execution.service import approve_and_create_intent, create_approval_from_recommendation
from app.models.execution import ExecutionApproval, ExecutionEvent, ExecutionIntent

router = APIRouter()


class ApprovalCreate(BaseModel):
    recommendation_id: str
    approved_by: str = "operator"
    force_mock_state: bool = True


class IntentAction(BaseModel):
    actor: str = "operator"


def _intent_dict(intent: ExecutionIntent) -> dict:
    return {
        "id": str(intent.id),
        "workspace_id": intent.workspace_id,
        "recommendation_id": intent.recommendation_id,
        "approval_id": intent.approval_id,
        "provider": intent.provider,
        "account_id": intent.account_id,
        "action_type": intent.action_type,
        "entity_type": intent.entity_type,
        "entity_id": intent.entity_id,
        "external_entity_id": intent.external_entity_id,
        "requested_change": intent.requested_change,
        "expected_before_hash": intent.expected_before_hash,
        "risk_level": intent.risk_level,
        "blast_radius": intent.blast_radius,
        "approval_required": intent.approval_required,
        "approval_expires_at": intent.approval_expires_at.isoformat() if intent.approval_expires_at else None,
        "execution_policy_version": intent.execution_policy_version,
        "status": intent.status,
        "idempotency_key": intent.idempotency_key,
        "shadow_only": intent.shadow_only,
        "created_at": intent.created_at.isoformat() if intent.created_at else None,
    }


def _approval_dict(approval: ExecutionApproval) -> dict:
    return {
        "id": str(approval.id),
        "recommendation_id": approval.recommendation_id,
        "approved_by": approval.approved_by,
        "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
        "provider": approval.provider,
        "action_type": approval.action_type,
        "entity_type": approval.entity_type,
        "entity_id": approval.entity_id,
        "approved_change": approval.approved_change,
        "risk_level": approval.risk_level,
        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        "status": approval.status,
        "approval_hash": approval.approval_hash,
        "consumed_by_intent_id": approval.consumed_by_intent_id,
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
    }


@router.get("/intents")
async def list_intents(
    status: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(ExecutionIntent).order_by(ExecutionIntent.created_at.desc()).limit(limit)
    if status:
        query = query.where(ExecutionIntent.status == status)
    if provider:
        query = query.where(ExecutionIntent.provider == provider.upper())
    if entity_id:
        query = query.where(ExecutionIntent.entity_id == entity_id)
    rows = (await db.execute(query)).scalars().all()
    return [_intent_dict(r) for r in rows]


@router.get("/intents/{intent_id}")
async def get_execution_intent(intent_id: str, db: AsyncSession = Depends(get_db)):
    intent = await get_intent(db, intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="intent not found")
    events = (
        await db.execute(select(ExecutionEvent).where(ExecutionEvent.execution_id == intent_id).order_by(ExecutionEvent.created_at))
    ).scalars().all()
    return {
        **_intent_dict(intent),
        "events": [
            {
                "event_type": e.event_type,
                "event_data": e.event_data,
                "actor": e.actor,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@router.get("/approvals")
async def list_approvals(
    status: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(ExecutionApproval).order_by(ExecutionApproval.created_at.desc()).limit(limit)
    if status:
        query = query.where(ExecutionApproval.status == status)
    if provider:
        query = query.where(ExecutionApproval.provider == provider.upper())
    rows = (await db.execute(query)).scalars().all()
    return [_approval_dict(r) for r in rows]


@router.get("/approvals/{approval_id}")
async def get_approval(approval_id: str, db: AsyncSession = Depends(get_db)):
    approval = (
        await db.execute(select(ExecutionApproval).where(ExecutionApproval.id == approval_id))
    ).scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="approval not found")
    return _approval_dict(approval)


@router.post("/approvals", dependencies=[Depends(require_permission("EXECUTION_APPROVE"))])
async def create_approval(data: ApprovalCreate, db: AsyncSession = Depends(get_db)):
    try:
        approval, detail = await create_approval_from_recommendation(
            db,
            recommendation_id=data.recommendation_id,
            approved_by=data.approved_by,
            force_mock=data.force_mock_state,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"approval": _approval_dict(approval), "preview": detail}


@router.post("/approvals/{approval_id}/approve", dependencies=[Depends(require_permission("EXECUTION_APPROVE"))])
async def approve_approval_endpoint(approval_id: str, data: IntentAction = None, db: AsyncSession = Depends(get_db)):
    actor = data.actor if data else "operator"
    try:
        intent = await approve_and_create_intent(db, approval_id, actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"approval_id": approval_id, "intent": _intent_dict(intent)}


@router.post("/approvals/{approval_id}/revoke", dependencies=[Depends(require_permission("EXECUTION_APPROVE"))])
async def revoke_approval_endpoint(approval_id: str, data: IntentAction = None, db: AsyncSession = Depends(get_db)):
    from app.execution.approvals import revoke_approval

    actor = data.actor if data else "operator"
    approval = await revoke_approval(db, approval_id, actor, reason="revoked by operator")
    await db.commit()
    return _approval_dict(approval)


@router.post("/intents/{intent_id}/cancel", dependencies=[Depends(require_permission("EXECUTION_APPROVE"))])
async def cancel_execution_intent(intent_id: str, data: IntentAction = None, db: AsyncSession = Depends(get_db)):
    intent = await get_intent(db, intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="intent not found")
    intent = await cancel_intent(db, intent, data.actor if data else "operator")
    await db.commit()
    return _intent_dict(intent)


@router.post("/intents/{intent_id}/approve", dependencies=[Depends(require_permission("EXECUTION_HIGH_RISK_APPROVE"))])
async def approve_execution_intent(intent_id: str, data: IntentAction = None, db: AsyncSession = Depends(get_db)):
    intent = await get_intent(db, intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="intent not found")
    from app.execution.approvals import approve_approval

    approval = await approve_approval(db, intent.approval_id, data.actor if data else "operator")
    intent.status = "APPROVED"
    await db.commit()
    return {"approval": _approval_dict(approval), "intent": _intent_dict(intent)}


@router.post("/intents/{intent_id}/reject", dependencies=[Depends(require_permission("EXECUTION_APPROVE"))])
async def reject_execution_intent(intent_id: str, data: IntentAction = None, db: AsyncSession = Depends(get_db)):
    intent = await get_intent(db, intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="intent not found")
    from app.execution.approvals import reject_approval

    approval = await reject_approval(db, intent.approval_id, data.actor if data else "operator")
    intent.status = "REJECTED"
    await db.commit()
    return {"approval": _approval_dict(approval), "intent": _intent_dict(intent)}


@router.post("/intents/{intent_id}/revalidate")
async def revalidate_execution_intent(intent_id: str, db: AsyncSession = Depends(get_db)):
    intent = await get_intent(db, intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="intent not found")
    provider = get_execution_provider(intent.provider, force_mock=True)
    current_state = await provider.get_current_state(intent)
    kill = await kill_switch_blocked(db, provider=intent.provider, action_type=intent.action_type, entity_id=intent.entity_id)
    result = await revalidate(db, intent=intent, provider_state=current_state, kill_switch_active=kill["ACTIVE"])
    await db.commit()
    return result


@router.post("/intents/{intent_id}/execute", dependencies=[Depends(require_permission("EXECUTION_APPROVE"))])
async def execute_execution_intent(intent_id: str, data: IntentAction = None, db: AsyncSession = Depends(get_db)):
    actor = data.actor if data else "operator"
    result = await execute_intent(db, intent_id=intent_id, actor=actor)
    await db.commit()
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post("/intents/{intent_id}/dry-run")
async def dry_run_execution_intent(intent_id: str, db: AsyncSession = Depends(get_db)):
    result = await dry_run_intent(db, intent_id=intent_id)
    await db.commit()
    return result


@router.post("/intents/{intent_id}/shadow-execute", dependencies=[Depends(require_permission("EXECUTION_APPROVE"))])
async def shadow_execute_execution_intent(intent_id: str, data: IntentAction = None, db: AsyncSession = Depends(get_db)):
    actor = data.actor if data else "operator"
    result = await shadow_execute_intent(db, intent_id=intent_id, actor=actor)
    await db.commit()
    return result
