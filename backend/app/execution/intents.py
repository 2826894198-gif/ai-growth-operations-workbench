"""Execution intent creation and lifecycle (PART 06 §8-§9)."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution.bindings import compute_action_package_hash
from app.execution.idempotency import build_idempotency_key
from app.execution.state import state_hash
from app.models.execution import ExecutionApproval, ExecutionIntent


async def create_intent(
    db: AsyncSession,
    *,
    workspace_id: Optional[str],
    recommendation_id: str,
    approval: ExecutionApproval,
    provider: str,
    action_type: str,
    entity_type: str,
    entity_id: str,
    external_entity_id: Optional[str],
    requested_change: Dict[str, Any],
    expected_before_state: Optional[Dict[str, Any]],
    account_id: Optional[str] = None,
    policy_version: Optional[int] = None,
    blast_radius: Optional[str] = None,
    shadow_only: bool = False,
    status: str = "APPROVED",
    canonical_entity_id: Optional[str] = None,
    credential_version: Optional[str] = None,
    metric_snapshot_id: Optional[str] = None,
) -> ExecutionIntent:
    idempotency_key = build_idempotency_key(
        workspace_id=workspace_id,
        provider=provider,
        entity_id=entity_id,
        action_type=action_type,
        requested_change=requested_change,
        approval_id=str(approval.id),
    )
    duplicate = (
        await db.execute(select(ExecutionIntent).where(ExecutionIntent.idempotency_key == idempotency_key))
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ValueError("intent with identical idempotency key already exists (ALREADY_EXECUTED)")
    intent = ExecutionIntent(
        workspace_id=workspace_id,
        recommendation_id=recommendation_id,
        approval_id=str(approval.id),
        provider=provider,
        account_id=account_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        external_entity_id=external_entity_id,
        requested_change=requested_change,
        expected_before_state=expected_before_state,
        expected_before_hash=state_hash(expected_before_state),
        risk_level=approval.risk_level,
        blast_radius=blast_radius,
        approval_required=True,
        approval_expires_at=approval.expires_at,
        execution_policy_version=policy_version,
        status=status,
        idempotency_key=idempotency_key,
        shadow_only=shadow_only,
    )
    intent.action_package_hash = compute_action_package_hash(
        workspace_id=workspace_id,
        canonical_entity_id=canonical_entity_id,
        action_type=action_type,
        requested_change=requested_change,
        policy_version=policy_version,
        credential_version=credential_version,
        metric_snapshot_id=metric_snapshot_id,
        approval_id=str(approval.id),
    )
    intent.credential_version = credential_version
    intent.metric_snapshot_id = metric_snapshot_id
    db.add(intent)
    await db.flush()
    return intent


async def get_intent(db: AsyncSession, intent_id: str) -> Optional[ExecutionIntent]:
    return (await db.execute(select(ExecutionIntent).where(ExecutionIntent.id == intent_id))).scalar_one_or_none()


async def cancel_intent(db: AsyncSession, intent: ExecutionIntent, actor: str, reason: str = "cancelled") -> ExecutionIntent:
    if intent.status in ("SUCCEEDED", "CONSUMED", "CANCELLED"):
        return intent
    intent.status = "CANCELLED"
    await db.flush()
    return intent


async def supersede_intent(db: AsyncSession, intent: ExecutionIntent, superseded_by: str) -> None:
    if intent.status in ("SUCCEEDED", "CONSUMED", "CANCELLED", "FAILED"):
        return
    intent.status = "SUPERSEDED"
    intent.superseded_by_recommendation_id = superseded_by
    intent.updated_at = datetime.now(timezone.utc)
    await db.flush()
