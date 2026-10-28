from typing import List

from app.rules.conflict.policies import DEFAULT_CONFLICT_POLICIES, action_priority
from app.rules.result import RESULT_CONFLICTED, RESULT_SUPPRESSED, EvaluationResult


def resolve_conflicts(results: List[EvaluationResult]) -> List[EvaluationResult]:
    """Deterministic per-entity conflict resolution by action priority + policies."""
    if len(results) <= 1:
        return results
    by_entity: dict = {}
    for result in results:
        key = (result.entity_type, result.entity_id)
        by_entity.setdefault(key, []).append(result)

    resolved: List[EvaluationResult] = []
    for _key, group in by_entity.items():
        if len(group) == 1:
            resolved.extend(group)
            continue
        group_sorted = sorted(group, key=lambda r: action_priority(r.action or ""), reverse=True)
        for i, winner in enumerate(group_sorted):
            for policy_a, policy_b, policy_action, reason in DEFAULT_CONFLICT_POLICIES:
                if winner.action != policy_a:
                    continue
                for loser in group_sorted[i + 1 :]:
                    if loser.action != policy_b:
                        continue
                    if policy_action == "SUPPRESS_B":
                        loser.result = RESULT_SUPPRESSED
                        loser.suppressed_reasons.append(reason)
                    elif policy_action == "DOWNGRADE_B":
                        loser.result = RESULT_CONFLICTED
                        loser.suppressed_reasons.append(reason)
        resolved.extend(group_sorted)
    return resolved
