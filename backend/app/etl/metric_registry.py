from typing import Any, Dict


def _metric(name: str, description: str, numerator: str, denominator: str, source: str, currency_behavior: str, null_behavior: str) -> Dict[str, Any]:
    return {
        "metric_name": name,
        "description": description,
        "numerator": numerator,
        "denominator": denominator,
        "source": source,
        "currency_behavior": currency_behavior,
        "null_behavior": null_behavior,
    }


METRICS: Dict[str, Dict[str, Any]] = {
    "spend": _metric(
        "spend", "Platform-reported ad spend", "sum(spend_amount)", "1",
        "provider", "source_currency_preserved", "NULL if unavailable; never 0 by default",
    ),
    "platform_roas": _metric(
        "platform_roas", "Platform attributed conversion value / platform spend",
        "platform_conversion_value", "spend_amount", "provider", "source_currency_preserved", "NULL when spend is 0",
    ),
    "blended_roas": _metric(
        "blended_roas", "Shopify net revenue / total paid media spend",
        "shopify_net_revenue", "total_paid_spend", "shopify+providers", "reporting_currency", "NULL when spend is 0",
    ),
    "net_revenue": _metric(
        "net_revenue", "Shopify actual net revenue after refunds", "sum(net_revenue_amount)", "1",
        "shopify", "source_currency_preserved", "NULL if unavailable; never 0 by default",
    ),
    "aov": _metric(
        "aov", "Average order value", "net_revenue", "orders", "shopify", "source_currency_preserved", "NULL when orders is 0",
    ),
    "cpc": _metric(
        "cpc", "Cost per click", "spend_amount", "clicks", "provider", "source_currency_preserved", "NULL when clicks is 0",
    ),
    "ctr": _metric(
        "ctr", "Click-through rate", "clicks", "impressions", "provider", "ratio", "NULL when impressions is 0",
    ),
}


def get_metric(name: str) -> Dict[str, Any]:
    return METRICS[name]
