"""Meta compensation builders (PART 06 §64, T)."""

from typing import Any, Dict, List


def build_meta_compensation(intent, before_state: Dict[str, Any], after_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    requested = intent.requested_change or {}
    action = intent.action_type.upper()
    if "BUDGET" in action:
        return [
            {
                "compensation_type": "RESTORE_BUDGET",
                "target_state": {
                    "proposed_budget": str(requested.get("current_budget")),
                    "currency": requested.get("currency", "USD"),
                },
                "provider_resource_name": requested.get("budget_owner_entity_id") or intent.entity_id,
                "action_type": intent.action_type,
            }
        ]
    if "PAUSE" in action:
        return [
            {
                "compensation_type": "RE_ENABLE",
                "target_state": {"proposed_status": "ACTIVE"},
                "provider_resource_name": intent.entity_id,
                "action_type": intent.action_type.replace("PAUSE", "ENABLE"),
            }
        ]
    if "ENABLE" in action:
        return [
            {
                "compensation_type": "RE_PAUSE",
                "target_state": {"proposed_status": "PAUSED"},
                "provider_resource_name": intent.entity_id,
                "action_type": intent.action_type.replace("ENABLE", "PAUSE"),
            }
        ]
    return []
