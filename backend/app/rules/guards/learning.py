from app.rules.context import RuleContext


def check_learning(context: RuleContext, guard_config: dict) -> tuple:
    if context.metrics.get("in_learning"):
        return False, "LEARNING_PROTECTION"
    min_age = guard_config.get("min_stable_hours", 48)
    if context.entity_age_hours is not None and context.entity_age_hours < min_age:
        return False, "LEARNING_PROTECTION"
    return True, None
