"""Meta read-after-write verification (PART 06 §62, R)."""

from typing import Any, Dict

from app.execution.providers.meta.client import MetaWriteClient


async def verify_state(client: MetaWriteClient, entity_id: str, entity_type: str, requested_state: Dict[str, Any]) -> Dict[str, Any]:
    current = await client.get_object(entity_id, entity_type)
    matched = False
    if "BUDGET" in (requested_state.get("action_type") or ""):
        field = "daily_budget"
        requested_value = requested_state.get("proposed_budget_cents")
        matched = current.get(field) is not None and int(current[field]) == int(requested_value)
    else:
        requested_status = requested_state.get("proposed_status", "").upper()
        current_status = str(current.get("status", "")).upper()
        matched = current_status == ("ACTIVE" if requested_status in ("ENABLED", "ACTIVE") else "PAUSED")
    return {
        "result": "MATCHED" if matched else "MISMATCHED",
        "current": current,
        "requested": requested_state,
        "matched": matched,
    }
