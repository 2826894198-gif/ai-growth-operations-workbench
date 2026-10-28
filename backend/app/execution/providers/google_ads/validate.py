"""Google validate_only helpers (PART 06 §68, K)."""

from typing import Any, Dict

from app.core.config import settings
from app.execution.providers.google_ads.client import GoogleWriteClient


async def provider_validate(
    client: GoogleWriteClient,
    intent,
    current_state: Dict[str, Any],
) -> Dict[str, Any]:
    """Run provider-side dry validation when the resource supports it."""
    action = intent.action_type.upper()
    requested = intent.requested_change or {}
    supported = True
    if not settings.google_ads_validate_only_first:
        return {"ok": True, "validate_only": False, "supported": False, "message": "validate_only disabled by config"}
    try:
        if "BUDGET" in action:
            from app.execution.providers.google_ads.budget import change_budget

            await change_budget(
                client,
                requested.get("budget_resource") or current_state.get("budget_resource"),
                requested.get("proposed_budget", 0),
                validate_only=True,
            )
        elif "PAUSE" in action or "ENABLE" in action:
            from app.execution.providers.google_ads.campaign import change_campaign_status

            await change_campaign_status(client, intent.entity_id, requested.get("proposed_status", "PAUSED"), validate_only=True)
        elif "ADD_NEGATIVE_KEYWORD" in action:
            from app.execution.providers.google_ads.negative_keyword import add_negative_keyword

            await add_negative_keyword(
                client,
                keyword_text=requested.get("keyword_text", ""),
                match_type=requested.get("match_type", "EXACT"),
                scope=requested.get("scope", "CAMPAIGN"),
                target_resource=requested.get("target_resource", ""),
                campaign_id=intent.entity_id,
                campaign_type=current_state.get("advertising_channel_type") or requested.get("campaign_type", "SEARCH"),
                validate_only=True,
            )
        elif "REMOVE_SYSTEM_NEGATIVE_KEYWORD" in action:
            from app.execution.providers.google_ads.negative_keyword import (
                remove_system_negative_keyword,
            )

            await remove_system_negative_keyword(client, requested.get("provider_resource_name", ""), validate_only=True)
        else:
            supported = False
            return {"ok": False, "validate_only": False, "supported": False, "message": f"no validate_only path for {action}"}
        return {"ok": True, "validate_only": True, "supported": True, "message": "provider validate_only passed"}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "validate_only": True,
            "supported": supported,
            "code": "PROVIDER_VALIDATE_FAILED",
            "message": str(exc),
        }
