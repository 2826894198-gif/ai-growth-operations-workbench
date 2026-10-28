from datetime import date
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.validators import safe_divide
from app.models.commerce import Order
from app.rules.features.anomalies import percent_change
from app.rules.features.windows import previous_range, rolling_range


async def load_commerce_features(db: AsyncSession, end: date) -> Dict[str, Any]:
    start, stop = rolling_range(end, 7)
    prev_start, prev_stop = previous_range(end, 7)
    out: Dict[str, Any] = {}

    async def sums(lo: date, hi: date) -> Dict[str, Any]:
        row = (
            await db.execute(
                select(
                    func.count(Order.id).label("orders"),
                    func.sum(Order.gross_amount).label("gross"),
                    func.sum(Order.refunded_amount).label("refunded"),
                    func.sum(Order.net_revenue_amount).label("net"),
                ).where(func.date(Order.order_created_at) >= lo, func.date(Order.order_created_at) <= hi)
            )
        ).one()
        return {
            "orders": float(row.orders or 0),
            "gross": float(row.gross or 0),
            "refunded": float(row.refunded or 0),
            "net": float(row.net or 0),
        }

    cur = await sums(start, stop)
    prev = await sums(prev_start, prev_stop)
    out["shopify_orders_1d"] = cur["orders"]
    out["shopify_net_revenue_1d"] = cur["net"]
    out["revenue_change_pct_7d"] = percent_change(cur["net"], prev["net"])
    aov = safe_divide(Decimal(cur["net"]), Decimal(cur["orders"])) if cur["orders"] else None
    prev_aov = safe_divide(Decimal(prev["net"]), Decimal(prev["orders"])) if prev["orders"] else None
    out["aov_change_pct_7d"] = percent_change(float(aov) if aov else None, float(prev_aov) if prev_aov else None)

    start30, stop30 = rolling_range(end, 30)
    row30 = (
        await db.execute(
            select(
                func.sum(Order.gross_amount).label("gross"),
                func.sum(Order.refunded_amount).label("refunded"),
            ).where(func.date(Order.order_created_at) >= start30, func.date(Order.order_created_at) <= stop30)
        )
    ).one()
    gross30 = float(row30.gross or 0)
    refunded30 = float(row30.refunded or 0)
    out["refund_rate_30d"] = float(safe_divide(Decimal(refunded30), Decimal(gross30))) if gross30 else None
    out["product_mix_shift"] = False
    out["inventory_capability"] = False
    return out
