"""Meta budget owner resolution + budget mutation (PART 06 §56-§58, P)."""

from decimal import Decimal
from typing import Any, Dict

from app.execution.errors import ExecutionError, ExecutionErrorCode
from app.execution.providers.meta.client import MetaWriteClient


def cents_to_decimal(cents: Any) -> Decimal:
    return Decimal(str(cents or 0)) / Decimal("100")


def decimal_to_cents(value: Any) -> int:
    return int((Decimal(str(value)) * Decimal("100")).to_integral_value())


async def resolve_budget_owner(client: MetaWriteClient, campaign_id: str) -> Dict[str, Any]:
    """Determine whether the budget lives on the campaign or its ad sets."""
    campaign = await client.get_object(campaign_id, "CAMPAIGN")
    if campaign.get("daily_budget") is not None or campaign.get("lifetime_budget") is not None:
        return {
            "owner": "CAMPAIGN",
            "owner_entity_id": campaign_id,
            "daily_budget_cents": campaign.get("daily_budget"),
            "lifetime_budget_cents": campaign.get("lifetime_budget"),
            "currency_known": False,
            "campaign_status": campaign.get("status"),
            "effective_status": campaign.get("effective_status"),
        }
    # Ad-set level: ad sets with daily_budget/lifetime_budget
    adsets = await client.list_adsets(campaign_id)
    budgeted = [a for a in adsets if a.get("daily_budget") is not None or a.get("lifetime_budget") is not None]
    if not budgeted:
        return {"owner": "UNKNOWN", "owner_entity_id": None, "campaign_status": campaign.get("status")}
    if len(budgeted) > 1:
        # Multiple independently-budgeted ad sets: do not guess a single budget target.
        return {
            "owner": "MULTIPLE_AD_SETS",
            "owner_entity_id": None,
            "ad_sets": [a["id"] for a in budgeted],
            "campaign_status": campaign.get("status"),
        }
    adset = budgeted[0]
    return {
        "owner": "AD_SET",
        "owner_entity_id": adset["id"],
        "daily_budget_cents": adset.get("daily_budget"),
        "lifetime_budget_cents": adset.get("lifetime_budget"),
        "campaign_status": campaign.get("status"),
    }


async def change_budget(client: MetaWriteClient, owner_entity_id: str, proposed_budget: Decimal, currency: str) -> Dict[str, Any]:
    if owner_entity_id is None:
        raise ExecutionError(
            ExecutionErrorCode.UNSUPPORTED_PROVIDER_CONFIGURATION.value,
            "budget owner could not be resolved; blocking instead of guessing",
        )
    return await client.update_budget(owner_entity_id, decimal_to_cents(proposed_budget), currency)
