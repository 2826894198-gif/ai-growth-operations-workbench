from typing import Any, Dict, Tuple

from app.rules.confidence.components import (
    cross_source_score,
    freshness_score,
    rule_strength_score,
    sample_score,
    signal_agreement_score,
)


def score_confidence(
    *,
    freshness_minutes,
    sample_reliability: float,
    evidence: list,
    rule_strength_thresholds: dict,
    context: Dict[str, Any],
    weights: Dict[str, float],
    penalties: list = None,
) -> Tuple[float, Dict[str, Any]]:
    components = {
        "data_freshness": freshness_score(freshness_minutes),
        "sample_reliability": sample_score(sample_reliability),
        "rule_strength": rule_strength_score(evidence, rule_strength_thresholds),
        "signal_agreement": signal_agreement_score(evidence),
        "cross_source": cross_source_score(context),
    }
    score = sum(components[k] * weights.get(k, 0.2) for k in components)
    for penalty in penalties or []:
        score -= penalty
    return round(max(0.0, min(1.0, score)), 3), components


def confidence_band(score: float) -> str:
    if score < 0.4:
        return "LOW"
    if score < 0.7:
        return "MEDIUM"
    if score < 0.85:
        return "HIGH"
    return "VERY_HIGH"
