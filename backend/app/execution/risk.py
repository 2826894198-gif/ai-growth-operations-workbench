"""Risk classification (PART 06 §35-§36, §116-§117)."""

from decimal import Decimal
from typing import Optional

from app.execution.actions.registry import ActionSpec, get_action_spec

RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def risk_rank(risk: str) -> int:
    return RISK_ORDER.get(risk.upper(), 3)


def risk_at_most(risk: str, max_risk: str) -> bool:
    return risk_rank(risk) <= risk_rank(max_risk)


def classify_budget_change_pct(delta_pct: Decimal) -> str:
    """Budget deltas above 20% are HIGH regardless of action base risk."""
    magnitude = abs(delta_pct)
    if magnitude > 50:
        return "CRITICAL"
    if magnitude > 20:
        return "HIGH"
    return "MEDIUM"


def classify_risk(
    action_type: str,
    blast_radius: str = "SMALL",
    delta_pct: Optional[Decimal] = None,
    shared_budget: bool = False,
) -> str:
    """Combine action base risk + blast radius + change size (PART 06 §117)."""
    spec: Optional[ActionSpec] = get_action_spec(action_type)
    base = spec.base_risk if spec else "MEDIUM"
    if shared_budget:
        base = "HIGH"
    if delta_pct is not None:
        change_risk = classify_budget_change_pct(delta_pct)
        base = change_risk if risk_rank(change_risk) > risk_rank(base) else base
    if blast_radius == "ACCOUNT_WIDE":
        base = "CRITICAL"
    elif blast_radius == "LARGE" and risk_rank(base) < risk_rank("HIGH"):
        base = "HIGH"
    return base


def classify_blast_radius(
    *,
    affected_campaigns: int = 1,
    daily_spend: Optional[Decimal] = None,
    shared_budget: bool = False,
    revenue_exposure: Optional[Decimal] = None,
) -> str:
    """Blast radius levels: SMALL / MEDIUM / LARGE / ACCOUNT_WIDE."""
    if affected_campaigns >= 20 or shared_budget and affected_campaigns >= 5:
        return "ACCOUNT_WIDE"
    if affected_campaigns >= 5:
        return "LARGE"
    if shared_budget:
        return "LARGE"
    if revenue_exposure is not None and revenue_exposure > 10000:
        return "LARGE"
    if daily_spend is not None and daily_spend > 5000:
        return "LARGE"
    if affected_campaigns > 1:
        return "MEDIUM"
    return "SMALL"
