from app.rules.context import RuleContext


def check_sample(context: RuleContext, guard_config: dict, defaults: dict) -> tuple:
    metrics = context.metrics
    min_age = guard_config.get("min_age_hours", defaults.get("min_active_hours", 24))
    min_clicks = guard_config.get("min_clicks", defaults.get("min_clicks_units", 50))
    min_purchases = guard_config.get("min_purchases", guard_config.get("min_conversions"))
    min_spend = guard_config.get("min_spend", defaults.get("min_spend_units", 30))
    age = context.entity_age_hours
    if age is not None and age < min_age:
        return False, "SAMPLE_TOO_NEW"
    clicks = metrics.get("clicks_7d") or 0
    if clicks < min_clicks:
        return False, "SAMPLE_CLICKS_INSUFFICIENT"
    purchases = (
        metrics.get("purchases_7d")
        or metrics.get("conversions_7d")
        or metrics.get("keyword_conversions_7d")
        or metrics.get("search_term_conversions_30d")
        or 0
    )
    if min_purchases is not None and purchases < min_purchases:
        return False, "SAMPLE_PURCHASES_INSUFFICIENT"
    spend = metrics.get("spend_7d") or 0
    if spend < min_spend:
        return False, "SAMPLE_SPEND_INSUFFICIENT"
    return True, None
