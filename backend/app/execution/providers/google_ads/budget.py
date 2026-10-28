"""Google CampaignBudget read/update + shared budget guard (PART 06 §72-§75)."""

from decimal import Decimal
from typing import Any, Dict

from app.execution.errors import ExecutionError, ExecutionErrorCode
from app.execution.providers.google_ads.client import GoogleWriteClient


def decimal_to_micros(value: Any) -> int:
    return int((Decimal(str(value)) * Decimal("1000000")).to_integral_value())


def micros_to_decimal(value: Any) -> Decimal:
    return Decimal(str(value)) / Decimal("1000000")


def _field(row: Dict[str, Any], *path: str) -> Any:
    current: Any = row
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


async def get_budget_state(client: GoogleWriteClient, budget_resource: str) -> Dict[str, Any]:
    if not budget_resource:
        raise ExecutionError(ExecutionErrorCode.PRECONDITION_FAILED.value, "campaign_budget resource name missing")
    query = (
        "SELECT campaign.id, campaign.name, campaign.status, campaign.campaign_budget, "
        "campaign_budget.resource_name, campaign_budget.amount_micros, campaign_budget.explicitly_shared, "
        "campaign_budget.period "
        f"FROM campaign WHERE campaign.campaign_budget = '{budget_resource}'"
    )
    rows = client.search(query)
    campaigns = []
    for row in rows:
        campaigns.append(
            {
                "id": _field(row, "campaign", "id"),
                "name": _field(row, "campaign", "name"),
                "status": _field(row, "campaign", "status"),
            }
        )
    if not campaigns:
        budget_row = client.search(
            "SELECT campaign_budget.resource_name, campaign_budget.amount_micros, campaign_budget.explicitly_shared, "
            f"campaign_budget.period FROM campaign_budget WHERE campaign_budget.resource_name = '{budget_resource}'"
        )
        if not budget_row:
            raise ExecutionError(ExecutionErrorCode.PRECONDITION_FAILED.value, f"budget resource not found: {budget_resource}")
        row = budget_row[0]
    else:
        row = campaigns[0]
    state = {
        "budget_resource": budget_resource,
        "amount_micros": _field(row, "campaign_budget", "amount_micros"),
        "explicitly_shared": bool(_field(row, "campaign_budget", "explicitly_shared")),
        "period": _field(row, "campaign_budget", "period"),
        "campaigns": campaigns,
        "reference_count": len(campaigns),
    }
    return state


async def change_budget(client: GoogleWriteClient, budget_resource: str, proposed_budget: Decimal, validate_only: bool = False) -> Dict[str, Any]:
    service = client.service("CampaignBudgetService")
    operation = client.get_type("CampaignBudgetOperation")
    budget = client.get_type("CampaignBudget")
    budget.resource_name = budget_resource
    budget.amount_micros = decimal_to_micros(proposed_budget)
    operation.update = budget
    operation.update_mask.paths.append("amount_micros")
    request = client.get_type("MutateCampaignBudgetsRequest")
    request.customer_id = client.customer_id()
    request.operations.append(operation)
    request.validate_only = validate_only
    request.partial_failure = False
    response = service.mutate_campaign_budgets(request)
    result = response.results[0] if response.results else None
    return {
        "resource_name": getattr(result, "resource_name", budget_resource) if result else budget_resource,
        "validate_only": validate_only,
        "response": str(response),
    }
