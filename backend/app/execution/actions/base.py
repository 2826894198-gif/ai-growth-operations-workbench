"""Typed action schemas — no generic mutate() interface (PART 06 §33)."""

from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, validator


class TypedAction(BaseModel):
    """Base class for all V1 execution actions."""

    entity_id: str
    external_entity_id: Optional[str] = None

    def to_requested_change(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ChangeBudgetAction(TypedAction):
    action_type: Literal["CHANGE_BUDGET"] = "CHANGE_BUDGET"
    current_budget: Decimal
    proposed_budget: Decimal
    currency: str = "USD"
    # Meta: campaign-level vs ad-set-level budget owner
    budget_owner: Optional[str] = None  # CAMPAIGN | AD_SET
    budget_owner_entity_id: Optional[str] = None
    # Google: independent CampaignBudget resource
    budget_resource: Optional[str] = None
    affected_campaigns: List[str] = Field(default_factory=list)
    shared_budget_explicitly_approved: bool = False

    @validator("proposed_budget")
    def _positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("proposed_budget must be positive")
        return value


class StatusAction(TypedAction):
    action_type: Literal["STATUS"] = "STATUS"
    entity_type: str
    current_status: str
    proposed_status: str  # PAUSED / ENABLED / ACTIVE
    parent_campaign_status: Optional[str] = None


class NegativeKeywordAction(TypedAction):
    action_type: Literal["ADD_NEGATIVE_KEYWORD"] = "ADD_NEGATIVE_KEYWORD"
    keyword_text: str
    match_type: str  # EXACT / PHRASE / BROAD
    scope: str  # AD_GROUP / CAMPAIGN / SHARED_SET / ACCOUNT / PMAX_CAMPAIGN
    target_resource: str
    campaign_id: str
    campaign_type: Optional[str] = None  # SEARCH / PERFORMANCE_MAX / ...
    created_resource_name: Optional[str] = None

    @validator("keyword_text")
    def _nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("keyword_text is required")
        return value

    @validator("match_type")
    def _match_type(cls, value: str) -> str:
        if value not in ("EXACT", "PHRASE", "BROAD"):
            raise ValueError("match_type must be EXACT, PHRASE or BROAD")
        return value


class RemoveSystemNegativeKeywordAction(TypedAction):
    action_type: Literal["REMOVE_SYSTEM_NEGATIVE_KEYWORD"] = "REMOVE_SYSTEM_NEGATIVE_KEYWORD"
    keyword_text: str
    match_type: str
    scope: str
    provider_resource_name: str


ACTION_SCHEMA_MAP = {
    "CHANGE_BUDGET": ChangeBudgetAction,
    "STATUS": StatusAction,
    "ADD_NEGATIVE_KEYWORD": NegativeKeywordAction,
    "REMOVE_SYSTEM_NEGATIVE_KEYWORD": RemoveSystemNegativeKeywordAction,
}
