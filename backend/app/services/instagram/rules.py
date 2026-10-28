"""Deterministic Instagram rule evaluation and evidence packs."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Mapping, Optional, Sequence, Tuple, Union

from app.instagram.contracts import InstagramAvailability

RULE_VERSION = "instagram-rules-v1.0"


class InstagramRuleCode(str, Enum):
    WINNING_CONTENT = "WINNING_CONTENT"
    BREAKOUT_CANDIDATE = "BREAKOUT_CANDIDATE"
    ENGAGEMENT_ANOMALY = "ENGAGEMENT_ANOMALY"
    AUDIENCE_DRIFT = "AUDIENCE_DRIFT"
    PROFILE_LINK_LEAKAGE = "PROFILE_LINK_LEAKAGE"
    HIGH_REACH_LOW_INTENT = "HIGH_REACH_LOW_INTENT"
    STRONG_INTENT_LOW_DISTRIBUTION = "STRONG_INTENT_LOW_DISTRIBUTION"
    CONTENT_DECAY = "CONTENT_DECAY"


RULE_ORDER = tuple(InstagramRuleCode)
DEFAULT_RULE_PARAMETERS = {
    "min_confidence": 0.50,
    "winning_content_score": 80.0,
    "breakout_reach_ratio": 2.0,
    "breakout_content_score": 75.0,
    "engagement_high_ratio": 1.50,
    "engagement_low_ratio": 0.50,
    "audience_drift_delta": -15.0,
    "profile_link_leakage_rate": 0.03,
    "high_reach_score": 75.0,
    "low_intent_score": 40.0,
    "strong_intent_score": 75.0,
    "low_distribution_score": 40.0,
    "content_decay_ratio": 0.50,
    "content_decay_score": 40.0,
}

RuleValue = Optional[Union[int, float]]


@dataclass(frozen=True)
class RuleContext:
    subject_ref: str
    values: Mapping[str, RuleValue]
    availability: Mapping[str, Union[str, InstagramAvailability]]
    confidence: Optional[float]
    evidence_refs: Tuple[str, ...] = ()
    parameters: Mapping[str, float] = None

    def parameter_map(self) -> Dict[str, float]:
        values = dict(DEFAULT_RULE_PARAMETERS)
        if self.parameters:
            values.update(self.parameters)
        return values


@dataclass(frozen=True)
class RuleEvaluation:
    rule_code: InstagramRuleCode
    rule_version: str
    subject_ref: str
    status: str
    triggered: bool
    confidence: Optional[float]
    evidence: Dict[str, object]
    missing_fields: Tuple[str, ...]

    def as_dict(self) -> Dict[str, object]:
        return {
            "rule_code": self.rule_code.value,
            "rule_version": self.rule_version,
            "subject_ref": self.subject_ref,
            "status": self.status,
            "triggered": self.triggered,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "missing_fields": list(self.missing_fields),
        }


def _available(context: RuleContext, key: str) -> bool:
    raw_reason = context.availability.get(key, InstagramAvailability.UNAVAILABLE)
    try:
        reason = raw_reason if isinstance(raw_reason, InstagramAvailability) else InstagramAvailability(raw_reason)
    except ValueError:
        reason = InstagramAvailability.UNAVAILABLE
    value = context.values.get(key)
    return reason is InstagramAvailability.AVAILABLE and value is not None


def _value(context: RuleContext, key: str) -> Optional[float]:
    if not _available(context, key):
        return None
    value = context.values[key]
    return float(value) if value is not None else None


def _evaluation(
    context: RuleContext,
    code: InstagramRuleCode,
    *,
    triggered: bool,
    observations: Mapping[str, object],
    required_fields: Sequence[str],
    parameters: Mapping[str, float],
) -> RuleEvaluation:
    missing = tuple(field for field in required_fields if not _available(context, field))
    if missing:
        status = "INSUFFICIENT_DATA"
        triggered = False
        confidence = None
    elif context.confidence is None or context.confidence < parameters["min_confidence"]:
        status = "INSUFFICIENT_DATA"
        triggered = False
        confidence = context.confidence
    else:
        status = "TRIGGERED" if triggered else "NOT_TRIGGERED"
        confidence = context.confidence
    return RuleEvaluation(
        rule_code=code,
        rule_version=RULE_VERSION,
        subject_ref=context.subject_ref,
        status=status,
        triggered=triggered,
        confidence=confidence,
        evidence={
            "observations": dict(observations),
            "parameters": dict(parameters),
            "input_refs": list(context.evidence_refs),
        },
        missing_fields=missing,
    )


def evaluate_instagram_rules(context: RuleContext) -> Tuple[RuleEvaluation, ...]:
    """Evaluate all V1 rules in stable order without fabricating missing inputs."""

    parameters = context.parameter_map()
    content_score = _value(context, "content_score")
    reach_score = _value(context, "reach_score")
    intent_score = _value(context, "intent_score")
    evaluations = []

    evaluations.append(
        _evaluation(
            context,
            InstagramRuleCode.WINNING_CONTENT,
            triggered=(content_score is not None and content_score >= parameters["winning_content_score"]),
            observations={"content_score": content_score},
            required_fields=("content_score",),
            parameters=parameters,
        )
    )

    reach_ratio = _value(context, "reach_to_baseline_ratio")
    evaluations.append(
        _evaluation(
            context,
            InstagramRuleCode.BREAKOUT_CANDIDATE,
            triggered=(
                reach_ratio is not None
                and content_score is not None
                and reach_ratio >= parameters["breakout_reach_ratio"]
                and content_score >= parameters["breakout_content_score"]
            ),
            observations={"reach_to_baseline_ratio": reach_ratio, "content_score": content_score},
            required_fields=("reach_to_baseline_ratio", "content_score"),
            parameters=parameters,
        )
    )

    engagement_ratio = _value(context, "engagement_to_baseline_ratio")
    evaluations.append(
        _evaluation(
            context,
            InstagramRuleCode.ENGAGEMENT_ANOMALY,
            triggered=(
                engagement_ratio is not None
                and (
                    engagement_ratio >= parameters["engagement_high_ratio"]
                    or engagement_ratio <= parameters["engagement_low_ratio"]
                )
            ),
            observations={"engagement_to_baseline_ratio": engagement_ratio},
            required_fields=("engagement_to_baseline_ratio",),
            parameters=parameters,
        )
    )

    audience_delta = _value(context, "audience_fit_delta")
    evaluations.append(
        _evaluation(
            context,
            InstagramRuleCode.AUDIENCE_DRIFT,
            triggered=(audience_delta is not None and audience_delta <= parameters["audience_drift_delta"]),
            observations={"audience_fit_delta": audience_delta},
            required_fields=("audience_fit_delta",),
            parameters=parameters,
        )
    )

    profile_link_rate = _value(context, "profile_link_tap_rate")
    profile_views = _value(context, "profile_views")
    evaluations.append(
        _evaluation(
            context,
            InstagramRuleCode.PROFILE_LINK_LEAKAGE,
            triggered=(
                profile_views is not None
                and profile_views > 0
                and profile_link_rate is not None
                and profile_link_rate < parameters["profile_link_leakage_rate"]
            ),
            observations={"profile_views": profile_views, "profile_link_tap_rate": profile_link_rate},
            required_fields=("profile_views", "profile_link_tap_rate"),
            parameters=parameters,
        )
    )

    evaluations.append(
        _evaluation(
            context,
            InstagramRuleCode.HIGH_REACH_LOW_INTENT,
            triggered=(
                reach_score is not None
                and intent_score is not None
                and reach_score >= parameters["high_reach_score"]
                and intent_score <= parameters["low_intent_score"]
            ),
            observations={"reach_score": reach_score, "intent_score": intent_score},
            required_fields=("reach_score", "intent_score"),
            parameters=parameters,
        )
    )

    evaluations.append(
        _evaluation(
            context,
            InstagramRuleCode.STRONG_INTENT_LOW_DISTRIBUTION,
            triggered=(
                intent_score is not None
                and reach_score is not None
                and intent_score >= parameters["strong_intent_score"]
                and reach_score <= parameters["low_distribution_score"]
            ),
            observations={"reach_score": reach_score, "intent_score": intent_score},
            required_fields=("reach_score", "intent_score"),
            parameters=parameters,
        )
    )

    content_ratio = _value(context, "content_to_baseline_ratio")
    evaluations.append(
        _evaluation(
            context,
            InstagramRuleCode.CONTENT_DECAY,
            triggered=(
                content_ratio is not None
                and content_score is not None
                and content_ratio <= parameters["content_decay_ratio"]
                and content_score <= parameters["content_decay_score"]
            ),
            observations={"content_to_baseline_ratio": content_ratio, "content_score": content_score},
            required_fields=("content_to_baseline_ratio", "content_score"),
            parameters=parameters,
        )
    )
    return tuple(evaluations)
