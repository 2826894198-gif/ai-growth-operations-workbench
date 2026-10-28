ACTION_RISK = {
    "OBSERVE": "LOW",
    "INVESTIGATE": "LOW",
    "CHECK_DATA_SOURCE": "LOW",
    "CHECK_TRACKING": "LOW",
    "CHECK_LANDING_PAGE": "LOW",
    "CHECK_PRODUCT_PAGE": "LOW",
    "CHECK_CART": "LOW",
    "CHECK_CHECKOUT": "LOW",
    "CHECK_REFUND": "LOW",
    "CHECK_INVENTORY": "LOW",
    "REFRESH_CREATIVE": "MEDIUM",
    "REVIEW_AUDIENCE_EXPANSION": "MEDIUM",
    "REVIEW_ADD_KEYWORD": "MEDIUM",
    "REVIEW_SCALE": "MEDIUM",
    "REVIEW_REDUCE_BUDGET": "MEDIUM",
    "REVIEW_PAUSE": "HIGH",
    "REVIEW_NEGATIVE_KEYWORD": "HIGH",
    "REVIEW_EMERGENCY_BUDGET_CONTROL": "CRITICAL",
}


def action_risk(action: str, severity: str) -> str:
    base = ACTION_RISK.get(action, "LOW")
    if severity == "CRITICAL" and base in ("LOW", "MEDIUM"):
        return "HIGH"
    return base


def approval_required(action: str, risk: str, auto_eligible: bool) -> tuple:
    if risk in ("HIGH", "CRITICAL"):
        return True, False
    return not auto_eligible, auto_eligible
