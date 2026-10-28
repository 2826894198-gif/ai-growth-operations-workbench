from typing import List, Tuple

# Priority: DATA/TRACKING > SAFETY > COMMERCE > PAUSE/REDUCE > CREATIVE > SCALE > OBSERVE
CATEGORY_PRIORITY = {
    "DATA": 7,
    "SAFETY": 6,
    "COMMERCE": 5,
    "ATTRIBUTION": 4,
    "PAUSE": 4,
    "REDUCE": 4,
    "FUNNEL": 4,
    "CREATIVE": 3,
    "AUDIENCE": 3,
    "CAMPAIGN": 3,
    "BUDGET": 3,
    "SEARCH_TERM": 3,
    "KEYWORD": 3,
    "ANOMALY": 2,
    "OBSERVE": 1,
}

ACTION_PRIORITY = {
    "CHECK_TRACKING": 7,
    "CHECK_DATA_SOURCE": 7,
    "REVIEW_EMERGENCY_BUDGET_CONTROL": 6,
    "CHECK_REFUND": 5,
    "CHECK_CHECKOUT": 5,
    "CHECK_LANDING_PAGE": 5,
    "CHECK_PRODUCT_PAGE": 5,
    "CHECK_CART": 5,
    "REVIEW_PAUSE": 4,
    "REVIEW_REDUCE_BUDGET": 4,
    "REFRESH_CREATIVE": 3,
    "REVIEW_NEGATIVE_KEYWORD": 3,
    "REVIEW_AUDIENCE_EXPANSION": 3,
    "REVIEW_ADD_KEYWORD": 3,
    "REVIEW_SCALE": 2,
    "INVESTIGATE": 1,
    "OBSERVE": 1,
}

DEFAULT_CONFLICT_POLICIES: List[Tuple[str, str, str, str]] = [
    ("CHECK_TRACKING", "REVIEW_SCALE", "SUPPRESS_B", "tracking issue blocks scale"),
    ("CHECK_DATA_SOURCE", "REVIEW_SCALE", "SUPPRESS_B", "data issue blocks scale"),
    ("LEARNING_PROTECTION", "REVIEW_SCALE", "SUPPRESS_B", "learning protection blocks scale"),
    ("REVIEW_EMERGENCY_BUDGET_CONTROL", "REVIEW_SCALE", "SUPPRESS_B", "hard spend guard wins over scale"),
    ("CHECK_CHECKOUT", "REVIEW_PAUSE", "DOWNGRADE_B", "funnel issue downgrades creative kill"),
    ("CHECK_CHECKOUT", "REFRESH_CREATIVE", "DOWNGRADE_B", "funnel issue downgrades creative refresh"),
    ("REVIEW_NEGATIVE_KEYWORD", "REVIEW_REDUCE_BUDGET", "SUPPRESS_B", "search term waste precedes campaign budget reduce"),
]


def action_priority(action: str) -> int:
    return ACTION_PRIORITY.get(action, 1)
