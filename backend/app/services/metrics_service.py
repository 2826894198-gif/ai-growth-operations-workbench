from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.validators import safe_divide
from app.models.ad_performance import AdPerformanceDaily
from app.models.commerce import Order


class MetricsService:
    async def overview(
        self,
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timezone: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        start, end = self._range(start_date, end_date)
        platforms = await self.platforms(db, start.isoformat(), end.isoformat(), timezone, currency)
        commerce = await self.commerce(db, start.isoformat(), end.isoformat(), timezone, currency)
        paid_spend = Decimal(sum((p.get("spend") or 0) for p in platforms))
        net_revenue = Decimal(commerce.get("net_revenue") or 0)
        return {
            "paid_spend": float(paid_spend),
            "shopify_net_revenue": float(net_revenue),
            "orders": commerce.get("orders", 0),
            "blended_roas": float(safe_divide(net_revenue, paid_spend)) if paid_spend else None,
            "platforms": platforms,
        }

    def _range(self, start_date: Optional[str], end_date: Optional[str]) -> tuple:
        end = date.fromisoformat(end_date) if end_date else date.today()
        start = date.fromisoformat(start_date) if start_date else end - timedelta(days=6)
        return start, end

    async def platforms(
        self,
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timezone: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start, end = self._range(start_date, end_date)
        rows = (
            await db.execute(
                select(
                    AdPerformanceDaily.platform,
                    func.sum(AdPerformanceDaily.spend_amount).label("spend"),
                    func.sum(AdPerformanceDaily.impressions).label("impressions"),
                    func.sum(AdPerformanceDaily.clicks).label("clicks"),
                    func.sum(AdPerformanceDaily.platform_conversions).label("platform_conversions"),
                    func.sum(AdPerformanceDaily.platform_conversion_value).label("platform_conversion_value"),
                    func.sum(AdPerformanceDaily.platform_purchases).label("platform_purchases"),
                    func.sum(AdPerformanceDaily.platform_purchase_value).label("platform_purchase_value"),
                )
                .where(
                    AdPerformanceDaily.entity_type == "CAMPAIGN",
                    AdPerformanceDaily.date >= start,
                    AdPerformanceDaily.date <= end,
                )
                .group_by(AdPerformanceDaily.platform)
            )
        ).all()
        result = []
        for row in rows:
            spend = Decimal(row.spend or 0)
            platform_roas = safe_divide(row.platform_conversion_value, spend)
            result.append(
                {
                    "platform": row.platform,
                    "spend": float(spend),
                    "impressions": int(row.impressions or 0),
                    "clicks": int(row.clicks or 0),
                    "platform_conversions": float(row.platform_conversions or 0),
                    "platform_conversion_value": float(row.platform_conversion_value or 0),
                    "platform_roas": float(platform_roas) if platform_roas is not None else None,
                }
            )
        return result

    async def campaigns(
        self,
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timezone: Optional[str] = None,
        currency: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        start, end = self._range(start_date, end_date)
        rows = (
            await db.execute(
                select(
                    AdPerformanceDaily.external_entity_id,
                    AdPerformanceDaily.platform,
                    AdPerformanceDaily.date,
                    func.sum(AdPerformanceDaily.spend_amount).label("spend"),
                    func.sum(AdPerformanceDaily.impressions).label("impressions"),
                    func.sum(AdPerformanceDaily.clicks).label("clicks"),
                    func.sum(AdPerformanceDaily.platform_conversions).label("platform_conversions"),
                    func.sum(AdPerformanceDaily.platform_conversion_value).label("platform_conversion_value"),
                )
                .where(
                    AdPerformanceDaily.entity_type == "CAMPAIGN",
                    AdPerformanceDaily.date >= start,
                    AdPerformanceDaily.date <= end,
                )
                .group_by(
                    AdPerformanceDaily.external_entity_id,
                    AdPerformanceDaily.platform,
                    AdPerformanceDaily.date,
                )
                .order_by(AdPerformanceDaily.date.desc())
                .limit(limit)
            )
        ).all()
        return [
            {
                "date": row.date.isoformat(),
                "platform": row.platform,
                "campaign_external_id": row.external_entity_id,
                "spend": float(row.spend or 0),
                "impressions": int(row.impressions or 0),
                "clicks": int(row.clicks or 0),
                "platform_conversions": float(row.platform_conversions or 0),
                "platform_conversion_value": float(row.platform_conversion_value or 0),
            }
            for row in rows
        ]

    async def commerce(
        self,
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timezone: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        start, end = self._range(start_date, end_date)
        rows = (
            await db.execute(
                select(
                    func.count(Order.id).label("orders"),
                    func.sum(Order.gross_amount).label("gross"),
                    func.sum(Order.discount_amount).label("discounts"),
                    func.sum(Order.refunded_amount).label("refunds"),
                    func.sum(Order.net_revenue_amount).label("net"),
                ).where(func.date(Order.order_created_at) >= start, func.date(Order.order_created_at) <= end)
            )
        ).one()
        orders = int(rows.orders or 0)
        net = Decimal(rows.net or 0)
        return {
            "orders": orders,
            "gross_revenue": float(rows.gross or 0),
            "discounts": float(rows.discounts or 0),
            "refunds": float(rows.refunds or 0),
            "net_revenue": float(net),
            "aov": float(safe_divide(net, Decimal(orders))) if orders else None,
        }
