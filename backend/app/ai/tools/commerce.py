from datetime import date, timedelta
from typing import Any, Dict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commerce import Order, OrderAttribution, OrderItem, Product, Refund
from app.services.metrics_service import MetricsService


async def get_store_overview(db: AsyncSession, days: int = 7) -> Dict[str, Any]:
    return await MetricsService().commerce(db)


async def get_orders_summary(db: AsyncSession, days: int = 7) -> Dict[str, Any]:
    start = date.today() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(
                func.count(Order.id).label("orders"),
                func.sum(Order.gross_amount).label("gross"),
                func.sum(Order.net_revenue_amount).label("net"),
            ).where(func.date(Order.order_created_at) >= start)
        )
    ).one()
    return {"orders": int(rows.orders or 0), "gross": float(rows.gross or 0), "net": float(rows.net or 0)}


async def get_refund_summary(db: AsyncSession, days: int = 30) -> Dict[str, Any]:
    start = date.today() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(
                func.count(Refund.id).label("refunds"),
                func.sum(Refund.refund_amount).label("amount"),
            ).where(func.date(Refund.refund_created_at) >= start)
        )
    ).one()
    return {"refunds": int(rows.refunds or 0), "refund_amount": float(rows.amount or 0)}


async def get_aov_trend(db: AsyncSession, days: int = 14) -> Dict[str, Any]:
    return {"aov_trend": "see get_store_overview", "note": "day-level AOV trend available via metrics API"}


async def get_product_performance(db: AsyncSession, product_id: str = None) -> Dict[str, Any]:
    query = select(
        Product.external_product_id,
        Product.title,
        func.count(OrderItem.id).label("items"),
        func.sum(OrderItem.line_total).label("revenue"),
    ).join(OrderItem, OrderItem.product_id == Product.id)
    if product_id:
        query = query.where(Product.external_product_id == product_id)
    rows = (await db.execute(query.group_by(Product.external_product_id, Product.title).limit(50))).all()
    return {"products": [dict(r._mapping) for r in rows]}


async def get_order_attribution_summary(db: AsyncSession, days: int = 30) -> Dict[str, Any]:
    start = date.today() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(
                OrderAttribution.first_source,
                func.count(Order.id).label("orders"),
            )
            .join(Order, Order.id == OrderAttribution.order_id)
            .where(func.date(Order.order_created_at) >= start)
            .group_by(OrderAttribution.first_source)
        )
    ).all()
    return {"attribution": [{"first_source": r.first_source, "orders": int(r.orders)} for r in rows]}
