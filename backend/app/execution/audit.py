"""Append-only execution audit + timeline events (PART 06 §90-§94, Z)."""

from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import redact_secrets
from app.models.execution import ExecutionAudit, ExecutionEvent


def redact_payload(value: Any) -> Any:
    """Best-effort recursive redaction of provider payloads."""
    if isinstance(value, dict):
        return {str(k): redact_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_payload(v) for v in value]
    if isinstance(value, str):
        return redact_secrets(value)
    return value


async def write_audit(
    db: AsyncSession,
    *,
    workspace_id: Optional[str] = None,
    recommendation_id: Optional[str] = None,
    approval_id: Optional[str] = None,
    intent_id: Optional[str] = None,
    job_id: Optional[str] = None,
    policy_version: Optional[int] = None,
    provider: Optional[str] = None,
    action_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    revalidation: Optional[Dict[str, Any]] = None,
    before_state: Optional[Dict[str, Any]] = None,
    provider_request: Optional[Dict[str, Any]] = None,
    provider_response: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    verification: Optional[Dict[str, Any]] = None,
    compensation: Optional[Dict[str, Any]] = None,
    actor: str = "system",
    event: str = "EXECUTION_AUDIT",
) -> None:
    db.add(
        ExecutionAudit(
            workspace_id=workspace_id,
            recommendation_id=recommendation_id,
            approval_id=approval_id,
            intent_id=intent_id,
            job_id=job_id,
            policy_version=policy_version,
            provider=provider,
            action_type=action_type,
            entity_id=entity_id,
            revalidation=redact_payload(revalidation),
            before_state=redact_payload(before_state),
            provider_request=redact_payload(provider_request),
            provider_response=redact_payload(provider_response),
            after_state=redact_payload(after_state),
            verification=redact_payload(verification),
            compensation=redact_payload(compensation),
            actor=actor,
            event=event,
        )
    )


async def log_event(
    db: AsyncSession,
    *,
    execution_id: Optional[str] = None,
    job_id: Optional[str] = None,
    event_type: str,
    event_data: Optional[Dict[str, Any]] = None,
    actor: Optional[str] = None,
) -> None:
    db.add(
        ExecutionEvent(
            execution_id=execution_id,
            job_id=job_id,
            event_type=event_type,
            event_data=redact_payload(event_data or {}),
            actor=actor,
        )
    )
