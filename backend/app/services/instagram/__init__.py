"""Pure Instagram metric and baseline engines."""

from app.services.instagram.baseline import (
    BaselineObservation,
    BaselineResult,
    BaselineStatus,
    build_account_baseline,
    build_content_baseline,
    relative_baseline_score,
    summarize_baseline,
)
from app.services.instagram.health import (
    HEALTH_CALCULATION_VERSION,
    HEALTH_DIMENSION_WEIGHTS,
    HealthScoreResult,
    calculate_internal_growth_health,
    freshness_factor,
    sample_factor,
)
from app.services.instagram.metrics import (
    CALCULATION_VERSION,
    MetricResult,
    engagement_metrics,
    follower_growth_metrics,
    profile_link_tap_rate,
    replay_metrics,
    safe_divide,
    watch_ratio,
)
from app.services.instagram.rules import (
    RULE_VERSION,
    InstagramRuleCode,
    RuleContext,
    RuleEvaluation,
    evaluate_instagram_rules,
)

__all__ = [
    "BaselineObservation",
    "BaselineResult",
    "BaselineStatus",
    "CALCULATION_VERSION",
    "HEALTH_CALCULATION_VERSION",
    "HEALTH_DIMENSION_WEIGHTS",
    "HealthScoreResult",
    "InstagramRuleCode",
    "RULE_VERSION",
    "RuleContext",
    "RuleEvaluation",
    "MetricResult",
    "build_account_baseline",
    "build_content_baseline",
    "engagement_metrics",
    "calculate_internal_growth_health",
    "freshness_factor",
    "evaluate_instagram_rules",
    "follower_growth_metrics",
    "profile_link_tap_rate",
    "relative_baseline_score",
    "replay_metrics",
    "safe_divide",
    "sample_factor",
    "summarize_baseline",
    "watch_ratio",
]
