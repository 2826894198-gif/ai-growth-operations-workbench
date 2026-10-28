"""Google compensation builders (PART 06 §83-§84, T)."""

from typing import Any, Dict, List


def build_google_compensation(intent, before_state: Dict[str, Any], after_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    requested = intent.requested_change or {}
    action = intent.action_type.upper()
    if "BUDGET" in action:
        return [
            {
                "compensation_type": "RESTORE_BUDGET",
                "target_state": {
                    "proposed_budget": str(requested.get("current_budget")),
                    "budget_resource": requested.get("budget_resource") or after_state.get("budget_resource"),
                    "currency": requested.get("currency", "USD"),
                },
                "provider_resource_name": requested.get("budget_resource") or after_state.get("budget_resource"),
                "action_type": intent.action_type,
            }
        ]
    if "PAUSE" in action:
        return [
            {
                "compensation_type": "RE_ENABLE",
                "target_state": {"proposed_status": "ENABLED"},
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
    if "ADD_NEGATIVE_KEYWORD" in action:
        resource_name = requested.get("created_resource_name") or after_state.get("resource_name")
        if not resource_name:
            return []
        return [
            {
                "compensation_type": "REMOVE_CREATED_NEGATIVE",
                "target_state": {
                    "provider_resource_name": resource_name,
                    "keyword_text": requested.get("keyword_text"),
                    "match_type": requested.get("match_type"),
                    "scope": requested.get("scope"),
                },
                "provider_resource_name": resource_name,
                "action_type": "GOOGLE_REMOVE_SYSTEM_NEGATIVE_KEYWORD",
            }
        ]
    return []
