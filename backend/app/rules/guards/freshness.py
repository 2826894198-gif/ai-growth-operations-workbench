from app.rules.context import RuleContext


def check_freshness(context: RuleContext, guard_config: dict) -> tuple:
    threshold = guard_config.get("data_freshness_minutes", 30)
    lag = context.data_freshness_minutes
    if lag is None:
        return False, "DATA_FRESHNESS_UNKNOWN"
    if lag > threshold:
        return False, "DATA_STALE"
    return True, None
