from app.rules.context import RuleContext


def check_attribution_delay(context: RuleContext, guard_config: dict) -> tuple:
    buffer = guard_config.get("attribution_delay_minutes", 120)
    if context.entity_age_hours is not None and context.entity_age_hours * 60 < buffer:
        return False, "ATTRIBUTION_DELAY"
    return True, None
