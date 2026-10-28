from typing import Dict, List

from app.rules.result import EvaluationResult


def dedup_by_action_reason(results: List[EvaluationResult]) -> List[EvaluationResult]:
    """Merge triggered results with the same entity+action+reason group."""
    merged: Dict[tuple, EvaluationResult] = {}
    for result in results:
        if result.result != "TRIGGERED":
            continue
        key = (result.entity_type, result.entity_id, result.action, result.reason_group)
        if key not in merged:
            merged[key] = result
            continue
        existing = merged[key]
        existing.evidence.extend(result.evidence)
        existing.reason_codes.extend(result.reason_codes)
        existing.suppressed_reasons.extend(result.suppressed_reasons)
    return list(merged.values())
