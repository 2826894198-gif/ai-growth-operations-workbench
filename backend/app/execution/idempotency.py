"""System-level idempotency keys (PART 06 §21-§22)."""

import hashlib
from typing import Any, Dict, Optional

from app.execution.state import canonical_json


def build_idempotency_key(
    *,
    workspace_id: Optional[str],
    provider: str,
    entity_id: str,
    action_type: str,
    requested_change: Dict[str, Any],
    approval_id: str,
) -> str:
    payload = {
        "workspace_id": workspace_id or "",
        "provider": provider,
        "entity_id": entity_id,
        "action_type": action_type,
        "requested_change": requested_change,
        "approval_id": approval_id,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def build_approval_hash(
    *,
    workspace_id: Optional[str],
    provider: str,
    entity_id: str,
    action_type: str,
    approved_change: Dict[str, Any],
    expected_before_state: Optional[Dict[str, Any]] = None,
) -> str:
    payload = {
        "workspace_id": workspace_id or "",
        "provider": provider,
        "entity_id": entity_id,
        "action_type": action_type,
        "approved_change": approved_change,
        "expected_before_state": expected_before_state or {},
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
