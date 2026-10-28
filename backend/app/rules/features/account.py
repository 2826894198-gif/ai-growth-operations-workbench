from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.validators import safe_divide
from app.models.ad_performance import AdPerformanceDaily
from app.models.commerce import Order
from app.rules.features.windows import rolling_range


async def load_account_features(db: AsyncSession, end: date) -> Dict[str, Any]:
    today = end
    yesterday = end - timedelta(days=1)

    def where_day(day: date):
        return (AdPerformanceDaily.date == day,)

    today_rows = (
        await db.execute(
            select(
                func.sum(AdPerformanceDaily.spend_amount).label("spend"),
                func.sum(AdPerformanceDaily.impressions).label("impressions"),
                func.sum(AdPerformanceDaily.clicks).label("clicks"),
                func.sum(AdPerformanceDaily.platform_conversions).label("conversions"),
                func.sum(AdPerformanceDaily.platform_conversion_value).label("conversion_value"),
            ).where(*where_day(today))
        )
    ).one()
    yesterday_rows = (
        await db.execute(
            select(
                func.sum(AdPerformanceDaily.spend_amount).label("spend"),
                func.sum(AdPerformanceDaily.platform_conversions).label("conversions"),
            ).where(*where_day(yesterday))
        )
    ).one()
    total_spend_today = float(today_rows.spend or 0)
    total_conversions_today = float(today_rows.conversions or 0)
    total_conversions_yesterday = float(yesterday_rows.conversions or 0)

    # Same-weekday baseline for spend velocity (previous 4 same weekdays).
    baseline_days = [today - timedelta(weeks=w) for w in range(1, 5)]
    baseline_rows = (
        await db.execute(
            select(func.sum(AdPerformanceDaily.spend_amount).label("spend")).where(
                AdPerformanceDaily.date.in_(baseline_days)
            )
        )
    ).one()
    baseline_spend = float(baseline_rows.spend or 0) / 4.0
    spend_velocity = float(safe_divide(Decimal(total_spend_today), Decimal(baseline_spend))) if baseline_spend else None

    start7, stop7 = rolling_range(end, 7)
    perf7 = (
        await db.execute(
            select(
                AdPerformanceDaily.platform,
                func.sum(AdPerformanceDaily.spend_amount).label("spend"),
                func.sum(AdPerformanceDaily.platform_conversion_value).label("conv_value"),
            )
            .where(AdPerformanceDaily.date >= start7, AdPerformanceDaily.date <= stop7)
            .group_by(AdPerformanceDaily.platform)
        )
    ).all()
    total_spend_7d = sum(float(r.spend or 0) for r in perf7)
    platform_spend = {str(r.platform): float(r.spend or 0) for r in perf7}
    platform_conv_value = sum(float(r.conv_value or 0) for r in perf7)

    order_rows = (
        await db.execute(
            select(
                func.sum(Order.net_revenue_amount).label("net"),
                func.count(Order.id).label("orders"),
            ).where(func.date(Order.order_created_at) >= start7, func.date(Order.order_created_at) <= stop7)
        )
    ).one()
    net_7d = float(order_rows.net or 0)

    return {
        "total_spend_today": total_spend_today,
        "total_spend_7d": total_spend_7d,
        "spend_velocity_multiple": spend_velocity,
        "blended_roas_7d": float(safe_divide(Decimal(net_7d), Decimal(total_spend_7d))) if total_spend_7d else None,
        "attribution_overlap_multiple": float(safe_divide(Decimal(platform_conv_value), Decimal(net_7d))) if net_7d else None,
        "channel_concentration": max(platform_spend.values()) / total_spend_7d if total_spend_7d else None,
        "metric_discontinuity": total_spend_today > 0 and total_conversions_today == 0 and total_conversions_yesterday > 0,
        "tracking_loss_signal": False,
        "conversion_tracking_anomaly": False,
        "source_stale": False,
        "shopify_stale": False,
    }
