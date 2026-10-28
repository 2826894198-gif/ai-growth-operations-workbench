"""Execution action-package bindings + state machine (review 4.5).

An approval freezes: intent hash + entity version + policy version +
credential version + metric snapshot + action + parameters + expiry. If any
binding changes during revalidation, execution returns to approval.
"""

import hashlib
from typing import Any, Dict, Optional

from app.execution.state import canonical_json

INTENT_TRANSITIONS = {
    "PENDING": {"APPROVED", "CANCELLED", "REJECTED"},
    "APPROVED": {"EXECUTING", "CANCELLED", "REJECTED", "EXPIRED"},
    "EXECUTING": {"SUCCEEDED", "FAILED", "UNKNOWN", "BLOCKED"},
    "SUCCEEDED": set(),
    "FAILED": {"CANCELLED"},
    "UNKNOWN": {"SUCCEEDED", "FAILED", "CANCELLED"},
    "BLOCKED": {"CANCELLED", "EXPIRED"},
    "CANCELLED": set(),
    "REJECTED": set(),
    "EXPIRED": set(),
}

JOB_TRANSITIONS = {
    "PENDING_APPROVAL": {"APPROVED", "REJECTED", "CANCELLED"},
    "APPROVED": {"REVALIDATING", "CANCELLED"},
    "REVALIDATING": {"VALIDATING_PROVIDER", "QUEUED", "BLOCKED", "FAILED"},
    "VALIDATING_PROVIDER": {"QUEUED", "RUNNING", "BLOCKED", "FAILED"},
    "QUEUED": {"RUNNING", "CANCELLED"},
    "RUNNING": {"VERIFYING", "UNKNOWN", "FAILED"},
    "VERIFYING": {"SUCCEEDED", "FAILED", "UNKNOWN"},
    "SUCCEEDED": set(),
    "FAILED": {"COMPENSATING", "CANCELLED"},
    "UNKNOWN": {"COMPENSATING", "SUCCEEDED", "FAILED", "CANCELLED"},
    "COMPENSATING": {"ROLLED_BACK", "COMPENSATION_FAILED", "SUCCEEDED"},
    "ROLLED_BACK": set(),
    "COMPENSATION_FAILED": {"COMPENSATING", "CANCELLED"},
    "BLOCKED": {"CANCELLED", "EXPIRED"},
    "EXPIRED": set(),
    "CANCELLED": set(),
}


def assert_intent_transition(current: str, target: str) -> None:
    if target not in INTENT_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid intent transition {current} -> {target}")


def assert_job_transition(current: str, target: str) -> None:
    if target not in JOB_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid job transition {current} -> {target}")


def compute_action_package_hash(
    *,
    workspace_id: Optional[str],
    canonical_entity_id: Optional[str],
    action_type: str,
    requested_change: Dict[str, Any],
    policy_version: Optional[int],
    credential_version: Optional[str],
    metric_snapshot_id: Optional[str],
    approval_id: str,
) -> str:
    payload = {
        "workspace_id": workspace_id or "",
        "canonical_entity_id": canonical_entity_id or "",
        "action_type": action_type,
        "requested_change": requested_change,
        "policy_version": policy_version,
        "credential_version": credential_version or "",
        "metric_snapshot_id": metric_snapshot_id or "",
        "approval_id": approval_id,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def validate_binding(
    *,
    intent,
    workspace_id: Optional[str],
    canonical_entity_id: Optional[str],
    action_type: str,
    requested_change: Dict[str, Any],
    policy_version: Optional[int],
    credential_version: Optional[str],
    metric_snapshot_id: Optional[str],
    approval_id: str,
) -> Dict[str, Any]:
    """Recompute the frozen action package and compare with the stored hash."""
    expected = compute_action_package_hash(
        workspace_id=workspace_id,
        canonical_entity_id=canonical_entity_id,
        action_type=action_type,
        requested_change=requested_change,
        policy_version=policy_version,
        credential_version=credential_version,
        metric_snapshot_id=metric_snapshot_id,
        approval_id=approval_id,
    )
    if intent.action_package_hash and expected != intent.action_package_hash:
        return {
            "ok": False,
            "code": "APPROVAL_MISMATCH",
            "message": "action package binding changed; a new approval is required",
        }
    return {"ok": True, "code": "BINDING_VALID", "message": "action package binding valid"}
