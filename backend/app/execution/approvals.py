"""Approval binding, hash, expiry, revoke, single-use (PART 06 §10-§14)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.execution.actions.registry import get_action_spec
from app.execution.idempotency import build_approval_hash
from app.execution.state import state_hash
from app.execution.timeutil import ensure_utc
from app.models.execution import ExecutionApproval

ACTION_DEFAULT_EXPIRY_HOURS = {
    "META_CHANGE_BUDGET": 4,
    "META_PAUSE_ENTITY": 4,
    "META_ENABLE_ENTITY": 4,
    "GOOGLE_CHANGE_BUDGET": 4,
    "GOOGLE_PAUSE_CAMPAIGN": 4,
    "GOOGLE_ENABLE_CAMPAIGN": 4,
    "GOOGLE_ADD_NEGATIVE_KEYWORD": 24,
    "GOOGLE_REMOVE_SYSTEM_NEGATIVE_KEYWORD": 24,
}


def approval_expiry_for(action_type: str, base_hours: Optional[float] = None) -> datetime:
    hours = ACTION_DEFAULT_EXPIRY_HOURS.get(action_type, settings.execution_default_approval_expiry_hours)
    if base_hours is not None:
        hours = base_hours
    spec = get_action_spec(action_type)
    if spec is not None and spec.default_expiry_hours != 4:
        hours = spec.default_expiry_hours
    return datetime.now(timezone.utc) + timedelta(hours=hours)


async def create_approval(
    db: AsyncSession,
    *,
    workspace_id: Optional[str],
    recommendation_id: str,
    provider: str,
    action_type: str,
    entity_type: str,
    entity_id: str,
    external_entity_id: Optional[str],
    approved_change: Dict[str, Any],
    expected_before_state: Optional[Dict[str, Any]],
    approved_by: str,
    risk_level: str = "MEDIUM",
    status: str = "PENDING",
    expiry_hours: Optional[float] = None,
) -> ExecutionApproval:
    approval = ExecutionApproval(
        workspace_id=workspace_id,
        recommendation_id=recommendation_id,
        provider=provider,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        external_entity_id=external_entity_id,
        approved_change=approved_change,
        expected_before_state=expected_before_state,
        expected_before_hash=state_hash(expected_before_state),
        risk_level=risk_level,
        expires_at=approval_expiry_for(action_type, expiry_hours),
        status=status,
        approved_by=approved_by,
        approved_at=datetime.now(timezone.utc) if status == "APPROVED" else None,
    )
    approval.approval_hash = build_approval_hash(
        workspace_id=workspace_id,
        provider=provider,
        entity_id=entity_id,
        action_type=action_type,
        approved_change=approved_change,
        expected_before_state=expected_before_state,
    )
    db.add(approval)
    await db.flush()
    return approval


async def approve_approval(db: AsyncSession, approval_id: str, actor: str) -> ExecutionApproval:
    approval = await _get(db, approval_id)
    if approval.status != "PENDING":
        raise ValueError(f"approval cannot be approved from status {approval.status}")
    approval.status = "APPROVED"
    approval.approved_by = actor
    approval.approved_at = datetime.now(timezone.utc)
    await db.flush()
    return approval


async def reject_approval(db: AsyncSession, approval_id: str, actor: str) -> ExecutionApproval:
    approval = await _get(db, approval_id)
    if approval.status not in ("PENDING", "APPROVED"):
        raise ValueError(f"approval cannot be rejected from status {approval.status}")
    approval.status = "REJECTED"
    approval.revoked_by = actor
    approval.revoked_at = datetime.now(timezone.utc)
    approval.revocation_reason = "rejected by approver"
    await db.flush()
    return approval


async def revoke_approval(db: AsyncSession, approval_id: str, actor: str, reason: str = "revoked") -> ExecutionApproval:
    approval = await _get(db, approval_id)
    if approval.status in ("REJECTED", "REVOKED"):
        return approval
    if approval.status == "CONSUMED":
        raise ValueError("consumed approvals cannot be revoked")
    approval.status = "REVOKED"
    approval.revoked_by = actor
    approval.revoked_at = datetime.now(timezone.utc)
    approval.revocation_reason = reason
    await db.flush()
    return approval


async def consume_approval(db: AsyncSession, approval_id: str, intent_id: str) -> None:
    approval = await _get(db, approval_id)
    approval.status = "CONSUMED"
    approval.consumed_by_intent_id = intent_id
    await db.flush()


async def validate_approval_for_intent(
    db: AsyncSession,
    *,
    approval_id: str,
    provider: str,
    action_type: str,
    entity_id: str,
    requested_change: Dict[str, Any],
    expected_before_state: Optional[Dict[str, Any]],
    workspace_id: Optional[str],
) -> Dict[str, Any]:
    """Check approval exists, APPROVED, not expired, not consumed, matches intent."""
    approval = await _get(db, approval_id)
    if approval is None:
        return {"ok": False, "code": "APPROVAL_REQUIRED", "message": "approval not found"}
    if approval.status != "APPROVED":
        return {"ok": False, "code": f"APPROVAL_{approval.status}", "message": f"approval status is {approval.status}"}
    now = datetime.now(timezone.utc)
    if ensure_utc(approval.expires_at) <= now:
        return {"ok": False, "code": "APPROVAL_EXPIRED", "message": "approval has expired"}
    if approval.consumed_by_intent_id:
        return {"ok": False, "code": "APPROVAL_CONSUMED", "message": "approval already consumed"}
    expected_hash = build_approval_hash(
        workspace_id=workspace_id,
        provider=provider,
        entity_id=entity_id,
        action_type=action_type,
        approved_change=requested_change,
        expected_before_state=expected_before_state,
    )
    if expected_hash != approval.approval_hash:
        return {
            "ok": False,
            "code": "APPROVAL_MISMATCH",
            "message": "intent payload does not match the approved binding",
        }
    return {"ok": True, "code": "APPROVAL_VALID", "message": "approval valid", "approval": approval}


async def _get(db: AsyncSession, approval_id: str) -> Optional[ExecutionApproval]:
    return (await db.execute(select(ExecutionApproval).where(ExecutionApproval.id == approval_id))).scalar_one_or_none()
