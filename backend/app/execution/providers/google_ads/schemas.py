"""Google execution state schemas."""

from typing import Any, Dict, Optional


class GoogleCampaignBudgetState:
    resource_name: Optional[str] = None
    amount_micros: Optional[int] = None
    explicitly_shared: bool = False
    period: Optional[str] = None
    campaigns: list = []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoogleCampaignBudgetState":
        state = cls()
        state.resource_name = data.get("budget_resource")
        state.amount_micros = data.get("amount_micros")
        state.explicitly_shared = bool(data.get("explicitly_shared"))
        state.period = data.get("period")
        state.campaigns = data.get("campaigns") or []
        return state
