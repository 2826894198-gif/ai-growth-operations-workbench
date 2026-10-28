"""Meta execution state schemas (mirrors what the client returns)."""

from typing import Any, Dict, Optional


class MetaEntityState:
    entity_id: str
    entity_type: str
    status: Optional[str] = None
    effective_status: Optional[str] = None
    daily_budget: Optional[int] = None
    lifetime_budget: Optional[int] = None
    budget_owner: Optional[str] = None
    budget_owner_entity_id: Optional[str] = None

    @classmethod
    def from_dict(cls, entity_id: str, entity_type: str, data: Dict[str, Any]) -> "MetaEntityState":
        state = cls()
        state.entity_id = entity_id
        state.entity_type = entity_type
        state.status = data.get("status")
        state.effective_status = data.get("effective_status")
        state.daily_budget = data.get("daily_budget")
        state.lifetime_budget = data.get("lifetime_budget")
        state.budget_owner = data.get("budget_owner")
        state.budget_owner_entity_id = data.get("budget_owner_entity_id")
        return state
