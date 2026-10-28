"""PART 06 §32-§36 — typed action registry (allowlist only)."""

from typing import Dict, Optional

from pydantic import BaseModel


class ActionSpec(BaseModel):
    action_type: str
    provider: str  # META | GOOGLE_ADS
    kind: str  # budget | status | negative_keyword
    base_risk: str  # MEDIUM | HIGH
    compensatable: str  # COMPENSATABLE | PARTIALLY_COMPENSATABLE | NON_COMPENSATABLE
    entity_types: tuple
    description: str
    auto_execution_default: bool = False
    default_expiry_hours: int = 4
    approval_expiry_hours_override: Optional[int] = None


ACTION_REGISTRY: Dict[str, ActionSpec] = {
    "META_CHANGE_BUDGET": ActionSpec(
        action_type="META_CHANGE_BUDGET",
        provider="META",
        kind="budget",
        base_risk="MEDIUM",
        compensatable="COMPENSATABLE",
        entity_types=("CAMPAIGN", "AD_SET"),
        description="Meta campaign or ad-set daily budget change",
    ),
    "META_PAUSE_ENTITY": ActionSpec(
        action_type="META_PAUSE_ENTITY",
        provider="META",
        kind="status",
        base_risk="HIGH",
        compensatable="PARTIALLY_COMPENSATABLE",
        entity_types=("CAMPAIGN", "AD_SET", "AD"),
        description="Meta campaign/ad-set/ad pause",
    ),
    "META_ENABLE_ENTITY": ActionSpec(
        action_type="META_ENABLE_ENTITY",
        provider="META",
        kind="status",
        base_risk="MEDIUM",
        compensatable="PARTIALLY_COMPENSATABLE",
        entity_types=("CAMPAIGN", "AD_SET", "AD"),
        description="Meta campaign/ad-set/ad enable",
    ),
    "GOOGLE_CHANGE_BUDGET": ActionSpec(
        action_type="GOOGLE_CHANGE_BUDGET",
        provider="GOOGLE_ADS",
        kind="budget",
        base_risk="MEDIUM",
        compensatable="COMPENSATABLE",
        entity_types=("CAMPAIGN", "BUDGET"),
        description="Google CampaignBudget amount change",
    ),
    "GOOGLE_PAUSE_CAMPAIGN": ActionSpec(
        action_type="GOOGLE_PAUSE_CAMPAIGN",
        provider="GOOGLE_ADS",
        kind="status",
        base_risk="HIGH",
        compensatable="PARTIALLY_COMPENSATABLE",
        entity_types=("CAMPAIGN",),
        description="Google campaign pause",
    ),
    "GOOGLE_ENABLE_CAMPAIGN": ActionSpec(
        action_type="GOOGLE_ENABLE_CAMPAIGN",
        provider="GOOGLE_ADS",
        kind="status",
        base_risk="MEDIUM",
        compensatable="PARTIALLY_COMPENSATABLE",
        entity_types=("CAMPAIGN",),
        description="Google campaign enable",
    ),
    "GOOGLE_ADD_NEGATIVE_KEYWORD": ActionSpec(
        action_type="GOOGLE_ADD_NEGATIVE_KEYWORD",
        provider="GOOGLE_ADS",
        kind="negative_keyword",
        base_risk="HIGH",
        compensatable="COMPENSATABLE",
        entity_types=("CAMPAIGN", "AD_GROUP", "SHARED_SET", "ACCOUNT"),
        description="Google negative keyword creation (approved PART 03 candidate only)",
        default_expiry_hours=24,
    ),
    "GOOGLE_REMOVE_SYSTEM_NEGATIVE_KEYWORD": ActionSpec(
        action_type="GOOGLE_REMOVE_SYSTEM_NEGATIVE_KEYWORD",
        provider="GOOGLE_ADS",
        kind="negative_keyword",
        base_risk="MEDIUM",
        compensatable="NON_COMPENSATABLE",
        entity_types=("CAMPAIGN", "AD_GROUP", "SHARED_SET", "ACCOUNT"),
        description="Remove only a negative keyword created by this system",
        default_expiry_hours=24,
    ),
}


def get_action_spec(action_type: str) -> Optional[ActionSpec]:
    return ACTION_REGISTRY.get(action_type)


def is_allowed_action(action_type: str, provider: str) -> bool:
    spec = ACTION_REGISTRY.get(action_type)
    return spec is not None and spec.provider == provider
