"""Unified metric query service (review 4.3).

API, rules, AI and frontend must read metrics through this service instead of
each consumer assembling its own SQL. Definitions live in metric_definitions
(metrics-as-code); values carry measurement_basis + freshness + caveats.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ad_performance import AdPerformanceDaily
from app.models.commerce import Order
from app.models.data_source import DataSource
from app.models.governance import MetricDefinition
from app.models.marketing import MarketingAccount
from app.models.social import ConnectedAccount, ContentPublication, FactContentPerformanceDaily
from app.services.social.scope_service import resolve_accounts

METRIC_SEEDS = [
    {"metric_key": "social_views", "display_name": "自然浏览", "business_definition": "Provider-reported content views (event sums, not unique people)", "numerator": "views", "source": "SOCIAL", "measurement_basis": "PLATFORM_REPORTED", "freshness_sla_minutes": 60, "owner": "data"},
    {"metric_key": "social_likes", "display_name": "点赞", "business_definition": "Provider-reported likes", "numerator": "likes", "source": "SOCIAL", "measurement_basis": "PLATFORM_REPORTED", "owner": "data"},
    {"metric_key": "social_comments", "display_name": "评论", "business_definition": "Provider-reported comments", "numerator": "comments", "source": "SOCIAL", "measurement_basis": "PLATFORM_REPORTED", "owner": "data"},
    {"metric_key": "social_shares", "display_name": "分享", "business_definition": "Provider-reported shares", "numerator": "shares", "source": "SOCIAL", "measurement_basis": "PLATFORM_REPORTED", "owner": "data"},
    {"metric_key": "social_follows", "display_name": "新增关注", "business_definition": "Provider-reported follows attributed to content", "numerator": "follows", "source": "SOCIAL", "measurement_basis": "PLATFORM_REPORTED", "owner": "data"},
    {"metric_key": "paid_spend", "display_name": "广告花费", "business_definition": "Platform-reported ad spend", "numerator": "spend_amount", "source": "ADS", "currency": "USD", "measurement_basis": "PLATFORM_REPORTED", "freshness_sla_minutes": 15, "owner": "media"},
    {"metric_key": "paid_revenue", "display_name": "广告收入", "business_definition": "Platform-reported conversion value", "numerator": "platform_conversion_value", "source": "ADS", "currency": "USD", "measurement_basis": "PLATFORM_REPORTED", "owner": "media"},
    {"metric_key": "paid_purchases", "display_name": "广告订单", "business_definition": "Platform-reported purchases", "numerator": "platform_purchases", "source": "ADS", "measurement_basis": "PLATFORM_REPORTED", "owner": "media"},
    {"metric_key": "paid_roas", "display_name": "广告 ROAS", "business_definition": "Platform-reported ROAS; do not merge with first-party attribution", "numerator": "platform_conversion_value", "denominator": "spend_amount", "source": "ADS", "currency": "USD", "measurement_basis": "PLATFORM_REPORTED", "owner": "media"},
    {"metric_key": "paid_cpa", "display_name": "广告 CPA", "business_definition": "Platform-reported cost per action", "numerator": "spend_amount", "denominator": "platform_purchases", "source": "ADS", "currency": "USD", "measurement_basis": "PLATFORM_REPORTED", "owner": "media"},
    {"metric_key": "orders", "display_name": "订单数", "business_definition": "First-party Shopify orders", "numerator": "order_count", "source": "COMMERCE", "currency": "USD", "measurement_basis": "FIRST_PARTY", "owner": "commerce"},
    {"metric_key": "net_revenue", "display_name": "净收入", "business_definition": "First-party Shopify net revenue", "numerator": "total_revenue", "source": "COMMERCE", "currency": "USD", "measurement_basis": "FIRST_PARTY", "owner": "commerce"},
    {"metric_key": "content_count", "display_name": "发布内容", "business_definition": "Number of publications in scope", "numerator": "publication_count", "source": "SOCIAL", "measurement_basis": "FIRST_PARTY", "owner": "content"},
]


async def seed_metric_definitions(db: AsyncSession) -> int:
    created = 0
    for seed in METRIC_SEEDS:
        existing = (await db.execute(select(MetricDefinition).where(MetricDefinition.metric_key == seed["metric_key"]))).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(MetricDefinition(**seed))
        created += 1
    if created:
        await db.flush()
    return created


async def get_definition(db: AsyncSession, metric_key: str) -> Optional[MetricDefinition]:
    return (await db.execute(select(MetricDefinition).where(MetricDefinition.metric_key == metric_key))).scalar_one_or_none()


async def list_definitions(db: AsyncSession) -> List[Dict[str, Any]]:
    rows = (await db.execute(select(MetricDefinition).order_by(MetricDefinition.metric_key))).scalars().all()
    return [
        {
            "metric_key": r.metric_key,
            "display_name": r.display_name,
            "business_definition": r.business_definition,
            "numerator": r.numerator,
            "denominator": r.denominator,
            "source": r.source,
            "currency": r.currency,
            "measurement_basis": r.measurement_basis,
            "freshness_sla_minutes": r.freshness_sla_minutes,
            "data_quality_status": r.data_quality_status,
            "owner": r.owner,
            "version": r.version,
        }
        for r in rows
    ]


async def query_metric(
    db: AsyncSession,
    *,
    workspace_id: str,
    metric_key: str,
    account_ids: Optional[List[str]] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> Dict[str, Any]:
    """Single entrypoint for metric values with semantics + freshness + caveats."""
    definition = await get_definition(db, metric_key)
    if definition is None:
        return {"ok": False, "metric_key": metric_key, "error": "unknown metric key"}
    end = end or datetime.now(timezone.utc).date()
    start = start or end - timedelta(days=30)
    requested_account_ids = list(account_ids or [])
    if not account_ids:
        accounts = await resolve_accounts(db, workspace_id=workspace_id)
        account_ids = [str(a.id) for a in accounts]
    source_scope = DataSource.workspace_id == workspace_id
    if workspace_id == "ws_main":
        source_scope = or_(source_scope, DataSource.workspace_id.is_(None))
    sources = list((await db.execute(select(DataSource).where(source_scope))).scalars().all())
    ad_source_ids = [str(source.id) for source in sources if source.provider in {"META_ADS", "GOOGLE_ADS"}]
    commerce_source_ids = [str(source.id) for source in sources if source.provider == "SHOPIFY"]
    value: Optional[float] = None
    caveat: Optional[str] = None
    series: List[Dict[str, Any]] = []
    freshness: Optional[str] = None

    if metric_key.startswith("social_"):
        facts = (
            await db.execute(
                select(FactContentPerformanceDaily).where(
                    FactContentPerformanceDaily.workspace_id == workspace_id,
                    FactContentPerformanceDaily.account_id.in_(account_ids) if account_ids else FactContentPerformanceDaily.id.isnot(None),
                    FactContentPerformanceDaily.date >= start.isoformat(),
                    FactContentPerformanceDaily.date <= end.isoformat(),
                )
            )
        ).scalars().all()
        field_map = {
            "social_views": "views",
            "social_likes": "likes",
            "social_comments": "comments",
            "social_shares": "shares",
            "social_follows": "follows",
        }
        field = field_map[metric_key]
        by_date: Dict[str, float] = {}
        for fact in facts:
            by_date[fact.date] = by_date.get(fact.date, 0) + float(getattr(fact, field) or 0)
        values = list(by_date.values())
        value = float(sum(values)) if facts else None
        series = [{"date": day, "value": by_date[day]} for day in sorted(by_date)]
        caveat = "平台报告事件合计，不代表去重用户。"
        freshness = _freshness_label(facts[-1].created_at if facts else None)

    elif metric_key.startswith("paid_"):
        marketing_account_ids: Optional[List[str]] = None
        if requested_account_ids:
            external_ids = list(
                (
                    await db.execute(
                        select(ConnectedAccount.external_account_id).where(
                            ConnectedAccount.workspace_id == workspace_id,
                            ConnectedAccount.id.in_(requested_account_ids),
                        )
                    )
                ).scalars().all()
            )
            marketing_account_ids = list(
                (
                    await db.execute(
                        select(MarketingAccount.id).where(
                            MarketingAccount.data_source_id.in_(ad_source_ids) if ad_source_ids else MarketingAccount.id.is_(None),
                            MarketingAccount.external_account_id.in_(external_ids) if external_ids else MarketingAccount.id.is_(None),
                        )
                    )
                ).scalars().all()
            )
        rows = (
            await db.execute(
                select(AdPerformanceDaily).where(
                    AdPerformanceDaily.data_source_id.in_(ad_source_ids) if ad_source_ids else AdPerformanceDaily.id.is_(None),
                    AdPerformanceDaily.marketing_account_id.in_(marketing_account_ids)
                    if marketing_account_ids is not None
                    else AdPerformanceDaily.id.isnot(None),
                    AdPerformanceDaily.date >= start,
                    AdPerformanceDaily.date <= end,
                    AdPerformanceDaily.platform.in_(("META_ADS", "GOOGLE_ADS")),
                )
            )
        ).scalars().all()
        spend = sum(float(r.spend_amount or 0) for r in rows)
        revenue = sum(float(r.platform_conversion_value or 0) for r in rows)
        purchases = sum(float(r.platform_purchases or 0) for r in rows)
        paid_by_date: Dict[str, Dict[str, float]] = {}
        for row in rows:
            day = row.date.isoformat()
            bucket = paid_by_date.setdefault(
                day,
                {"spend": 0.0, "revenue": 0.0, "purchases": 0.0},
            )
            bucket["spend"] += float(row.spend_amount or 0)
            bucket["revenue"] += float(row.platform_conversion_value or 0)
            bucket["purchases"] += float(row.platform_purchases or 0)
        if not ad_source_ids:
            value = None
        elif metric_key == "paid_spend":
            value = spend
        elif metric_key == "paid_revenue":
            value = revenue
        elif metric_key == "paid_purchases":
            value = purchases
        elif metric_key == "paid_roas":
            value = round(revenue / spend, 2) if spend else None
            caveat = "平台归因 ROAS，必须与第一方收入回报分开。"
        elif metric_key == "paid_cpa":
            value = round(spend / purchases, 2) if purchases else None
        for day in sorted(paid_by_date):
            bucket = paid_by_date[day]
            if metric_key == "paid_spend":
                day_value = bucket["spend"]
            elif metric_key == "paid_revenue":
                day_value = bucket["revenue"]
            elif metric_key == "paid_purchases":
                day_value = bucket["purchases"]
            elif metric_key == "paid_roas":
                day_value = (
                    round(bucket["revenue"] / bucket["spend"], 2)
                    if bucket["spend"]
                    else None
                )
            else:
                day_value = (
                    round(bucket["spend"] / bucket["purchases"], 2)
                    if bucket["purchases"]
                    else None
                )
            series.append({"date": day, "value": day_value})
        freshness = _freshness_label(rows[-1].source_updated_at if rows else None)

    elif metric_key in ("orders", "net_revenue"):
        end_exclusive = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        orders = (
            await db.execute(
                select(Order).where(
                    Order.data_source_id.in_(commerce_source_ids) if commerce_source_ids else Order.id.is_(None),
                    Order.order_created_at >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
                    Order.order_created_at < end_exclusive,
                )
            )
        ).scalars().all()
        if not commerce_source_ids:
            value = None
        elif metric_key == "orders":
            value = float(len(orders))
        else:
            value = float(sum(float(o.net_revenue_amount or o.gross_amount or 0) for o in orders))
        commerce_by_date: Dict[str, Dict[str, float]] = {}
        for order in orders:
            day = order.order_created_at.date().isoformat()
            bucket = commerce_by_date.setdefault(
                day,
                {"orders": 0.0, "revenue": 0.0},
            )
            bucket["orders"] += 1
            bucket["revenue"] += float(
                order.net_revenue_amount or order.gross_amount or 0
            )
        series = [
            {
                "date": day,
                "value": commerce_by_date[day][
                    "orders" if metric_key == "orders" else "revenue"
                ],
            }
            for day in sorted(commerce_by_date)
        ]
        caveat = "Shopify 第一方数据；归因模型尚未确定。"

    elif metric_key == "content_count":
        end_exclusive = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        pubs = (
            await db.execute(
                select(ContentPublication).where(
                    ContentPublication.account_id.in_(account_ids) if account_ids else ContentPublication.id.is_(None),
                    ContentPublication.published_at >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
                    ContentPublication.published_at < end_exclusive,
                )
            )
        ).scalars().all()
        # Preserve the existing metric contract: an empty publication set is a
        # valid zero.  Consumers must still inspect data-health before drawing
        # a business conclusion from that zero.
        value = float(len(pubs))
        content_by_date: Dict[str, float] = {}
        for publication in pubs:
            day = publication.published_at.date().isoformat()
            content_by_date[day] = content_by_date.get(day, 0) + 1
        series = [
            {"date": day, "value": content_by_date[day]}
            for day in sorted(content_by_date)
        ]

    return {
        "ok": True,
        "metric_key": metric_key,
        "display_name": definition.display_name,
        "definition": {
            "business_definition": definition.business_definition,
            "numerator": definition.numerator,
            "denominator": definition.denominator,
            "source": definition.source,
            "currency": definition.currency,
            "measurement_basis": definition.measurement_basis,
            "freshness_sla_minutes": definition.freshness_sla_minutes,
            "data_quality_status": definition.data_quality_status,
            "version": definition.version,
        },
        "value": value,
        "caveat": caveat,
        "freshness": freshness,
        "series": series,
        "window": {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days},
        "scope": {"workspace_id": workspace_id, "account_ids": account_ids},
    }


def _freshness_label(updated_at: Optional[datetime]) -> str:
    if updated_at is None:
        return "未记录更新时间"
    from app.execution.timeutil import ensure_utc

    minutes = int((datetime.now(timezone.utc) - ensure_utc(updated_at)).total_seconds() // 60)
    return f"更新于 {minutes} 分钟前"
