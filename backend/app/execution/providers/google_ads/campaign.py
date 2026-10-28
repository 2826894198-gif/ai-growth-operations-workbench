"""Google campaign read + typed pause/enable (PART 06 §70-§71, J)."""

from typing import Any, Dict

from app.execution.errors import ExecutionError, ExecutionErrorCode
from app.execution.providers.google_ads.client import GoogleWriteClient


def _field(row: Dict[str, Any], *path: str) -> Any:
    current: Any = row
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


async def get_campaign_state(client: GoogleWriteClient, campaign_id: str) -> Dict[str, Any]:
    query = (
        "SELECT campaign.id, campaign.name, campaign.status, campaign.campaign_budget, "
        "campaign.start_date, campaign.end_date, campaign.advertising_channel_type, campaign.advertising_channel_sub_type "
        f"FROM campaign WHERE campaign.id = {campaign_id}"
    )
    rows = client.search(query)
    if not rows:
        raise ExecutionError(ExecutionErrorCode.PRECONDITION_FAILED.value, f"campaign not found: {campaign_id}")
    row = rows[0]
    return {
        "campaign_id": str(_field(row, "campaign", "id")),
        "name": _field(row, "campaign", "name"),
        "status": _field(row, "campaign", "status"),
        "budget_resource": _field(row, "campaign", "campaign_budget"),
        "start_date": _field(row, "campaign", "start_date"),
        "end_date": _field(row, "campaign", "end_date"),
        "advertising_channel_type": _field(row, "campaign", "advertising_channel_type"),
        "advertising_channel_sub_type": _field(row, "campaign", "advertising_channel_sub_type"),
    }


async def change_campaign_status(
    client: GoogleWriteClient, campaign_id: str, proposed_status: str, validate_only: bool = False
) -> Dict[str, Any]:
    google_status = "ENABLED" if proposed_status.upper() in ("ENABLED", "ACTIVE") else "PAUSED"
    service = client.service("CampaignService")
    operation = client.get_type("CampaignOperation")
    campaign = client.get_type("Campaign")
    campaign.resource_name = f"customers/{client.customer_id()}/campaigns/{campaign_id}"
    campaign.status = client.get_type("CampaignStatusEnum").CampaignStatus.Value(google_status)
    operation.update = campaign
    operation.update_mask.paths.append("status")
    request = client.get_type("MutateCampaignsRequest")
    request.customer_id = client.customer_id()
    request.operations.append(operation)
    request.validate_only = validate_only
    request.partial_failure = False
    response = service.mutate_campaigns(request)
    return {"resource_name": response.results[0].resource_name if response.results else None, "validate_only": validate_only}
