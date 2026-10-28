from datetime import timedelta, timezone

from app.rules.context import RuleContext


def check_recent_change(context: RuleContext, guard_config: dict) -> tuple:
    hours = guard_config.get("recent_change_hours", 24)
    if not context.recent_changes:
        return True, None
    cutoff = context.evaluation_time - timedelta(hours=hours)
    for change in context.recent_changes:
        occurred = change.get("occurred_at")
        if occurred is None:
            continue
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=timezone.utc)
        if occurred >= cutoff:
            return False, "RECENT_CHANGE_COOLDOWN"
    return True, None
