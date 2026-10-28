from typing import Any, Dict


def freshness_score(context_minutes) -> float:
    if context_minutes is None:
        return 0.0
    if context_minutes <= 5:
        return 1.0
    if context_minutes <= 15:
        return 0.9
    if context_minutes <= 30:
        return 0.7
    if context_minutes <= 60:
        return 0.5
    return 0.2


def sample_score(sample_reliability: float) -> float:
    if sample_reliability is None:
        return 0.0
    return min(1.0, sample_reliability / 100.0)


def rule_strength_score(evidence: list, thresholds: dict) -> float:
    """Distance-from-threshold based strength (0-1)."""
    if not evidence:
        return 0.5
    ratios = []
    for item in evidence:
        threshold = thresholds.get(item.get("metric"))
        current = item.get("current")
        if threshold and current is not None:
            ratios.append(abs(float(current)) / abs(float(threshold)))
    if not ratios:
        return 0.5
    return min(1.0, max(ratios) / 2.0)


def signal_agreement_score(evidence: list) -> float:
    if len(evidence) <= 1:
        return 0.5
    return min(1.0, 0.5 + 0.15 * (len(evidence) - 1))


def cross_source_score(context: Dict[str, Any]) -> float:
    if context.get("cross_source_confirmed") is True:
        return 1.0
    if context.get("cross_source_confirmed") is False:
        return 0.2
    return 0.5
