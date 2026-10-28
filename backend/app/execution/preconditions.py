"""Execution preconditions (PART 06 §85-§87, §154)."""

from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.execution.actions.registry import is_allowed_action
from app.models.execution import ExecutionIntent, ExecutionJob


async def check_duplicate(db: AsyncSession, intent: ExecutionIntent) -> Optional[Dict[str, Any]]:
    """Return ALREADY_EXECUTED if this idempotency key already succeeded."""
    if intent.status == "SUCCEEDED":
        return {"ok": False, "code": "ALREADY_EXECUTED", "message": "intent already succeeded"}
    job = (
        await db.execute(
            select(ExecutionJob).where(
                ExecutionJob.intent_id == intent.id,
                ExecutionJob.status == "SUCCEEDED",
            )
        )
    ).scalar_one_or_none()
    if job is not None:
        return {"ok": False, "code": "ALREADY_EXECUTED", "message": f"job {job.id} already succeeded"}
    return None


def check_execution_enabled() -> Optional[Dict[str, Any]]:
    if not settings.execution_enabled and not settings.execution_shadow_mode:
        return {"ok": False, "code": "EXECUTION_DISABLED", "message": "execution layer disabled"}
    return None


def check_mode(mode: str) -> Optional[Dict[str, Any]]:
    if mode == "observe":
        return {"ok": False, "code": "MODE_0_OBSERVE", "message": "execution mode is MODE_0_OBSERVE"}
    if mode not in ("manual", "guarded_auto"):
        return {"ok": False, "code": "PRECONDITION_FAILED", "message": f"unknown execution mode {mode}"}
    return None


def check_write_enabled(provider: str, shadow_only: bool = False) -> Optional[Dict[str, Any]]:
    if shadow_only:
        return None
    if provider.upper() == "META":
        if not settings.meta_write_enabled:
            return {"ok": False, "code": "EXECUTION_DISABLED", "message": "META_WRITE_ENABLED is false"}
    elif provider.upper() == "GOOGLE_ADS":
        if not settings.google_ads_write_enabled:
            return {"ok": False, "code": "EXECUTION_DISABLED", "message": "GOOGLE_ADS_WRITE_ENABLED is false"}
    return None


def check_action_allowed(provider: str, action_type: str) -> Optional[Dict[str, Any]]:
    if not is_allowed_action(action_type, provider):
        return {"ok": False, "code": "ACTION_NOT_ALLOWED", "message": f"{action_type} is not in the V1 action allowlist"}
    return None


def check_shared_budget_scope(intent: ExecutionIntent, provider_state: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Google shared budget guard (PART 06 §73-§74): block unless explicitly approved."""
    if "BUDGET" not in intent.action_type or intent.provider != "GOOGLE_ADS":
        return None
    state = provider_state or {}
    requested = intent.requested_change or {}
    if state.get("explicitly_shared") or state.get("shared") or (state.get("reference_count") or 0) > 1:
        if not requested.get("shared_budget_explicitly_approved"):
            return {
                "ok": False,
                "code": "SHARED_BUDGET_SCOPE_UNAPPROVED",
                "message": f"shared budget affects {state.get('reference_count', 'multiple')} campaigns; explicit approval required",
            }
    return None


def validate_typed_schema(
    action_type: str, requested_change: Dict[str, Any], provider: str, entity_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    from app.execution.actions.base import ACTION_SCHEMA_MAP

    if "ADD_NEGATIVE" in action_type:
        kind = "ADD_NEGATIVE_KEYWORD"
    elif "REMOVE_SYSTEM_NEGATIVE" in action_type:
        kind = "REMOVE_SYSTEM_NEGATIVE_KEYWORD"
    elif "PAUSE" in action_type or "ENABLE" in action_type:
        kind = "STATUS"
    elif "BUDGET" in action_type:
        kind = "CHANGE_BUDGET"
    else:
        kind = None
    model_cls = ACTION_SCHEMA_MAP.get(kind)
    if model_cls is None:
        return {"ok": False, "code": "PRECONDITION_FAILED", "message": f"no typed schema for {action_type}"}
    try:
        payload = {**requested_change, "action_type": kind}
        if entity_id is not None:
            payload["entity_id"] = entity_id
        if kind == "STATUS":
            payload["entity_type"] = requested_change.get("entity_type") or ("CAMPAIGN" if provider == "GOOGLE_ADS" else "CAMPAIGN")
        model_cls(**payload)
        return None
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "code": "PRECONDITION_FAILED", "message": f"invalid typed action payload: {exc}"}
