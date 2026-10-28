"""Google read-after-write verification (PART 06 §R, §95-§98)."""

from typing import Any, Dict

from app.execution.providers.google_ads.client import GoogleWriteClient


async def verify_state(client: GoogleWriteClient, intent, requested_state: Dict[str, Any]) -> Dict[str, Any]:
    action = intent.action_type.upper()
    if "BUDGET" in action:
        budget_resource = requested_state.get("budget_resource") or intent.requested_change.get("budget_resource")
        from app.execution.providers.google_ads.budget import get_budget_state

        current = await get_budget_state(client, budget_resource)
        expected_micros = int(Decimal(str(requested_state.get("proposed_budget", 0))) * 1000000)
        matched = current.get("amount_micros") is not None and int(current["amount_micros"]) == expected_micros
        return {"result": "MATCHED" if matched else "MISMATCHED", "current": current, "requested": requested_state, "matched": matched}
    if "PAUSE" in action or "ENABLE" in action:
        from app.execution.providers.google_ads.campaign import get_campaign_state

        current = await get_campaign_state(client, intent.entity_id)
        requested_status = requested_state.get("proposed_status", "PAUSED").upper()
        matched = str(current.get("status", "")).upper() == ("ENABLED" if requested_status in ("ENABLED", "ACTIVE") else "PAUSED")
        return {"result": "MATCHED" if matched else "MISMATCHED", "current": current, "requested": requested_state, "matched": matched}
    if "ADD_NEGATIVE_KEYWORD" in action:
        resource_name = requested_state.get("created_resource_name")
        query = (
            "SELECT ad_group_criterion.resource_name, ad_group_criterion.keyword.text, "
            "ad_group_criterion.keyword.match_type, ad_group_criterion.negative "
            "FROM ad_group_criterion WHERE ad_group_criterion.resource_name = '{rn}'".format(rn=resource_name)
            if resource_name and "/adGroupCriteria/" in resource_name
            else "SELECT campaign_criterion.resource_name, campaign_criterion.keyword.text, campaign_criterion.keyword.match_type, "
            "campaign_criterion.negative FROM campaign_criterion WHERE campaign_criterion.resource_name = '{rn}'".format(rn=resource_name)
        )
        rows = client.search(query)
        matched = bool(rows)
        return {"result": "MATCHED" if matched else "MISMATCHED", "current": rows, "requested": requested_state, "matched": matched}
    return {"result": "UNAVAILABLE", "current": None, "requested": requested_state, "matched": False}


from decimal import Decimal  # noqa: E402
