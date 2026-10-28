"""Deterministic daily/weekly review previews and durable review records."""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ad_performance import AdPerformanceDaily
from app.models.data_source import DataSource
from app.models.marketing import Campaign, MarketingAccount
from app.models.review import ReviewFollowup, ReviewRun
from app.models.social import ConnectedAccount
from app.services.data_health_service import DataHealthService
from app.services.metric_service import query_metric

CORE_METRICS = (
    "net_revenue",
    "orders",
    "paid_spend",
    "paid_purchases",
    "paid_roas",
    "paid_cpa",
    "content_count",
    "social_views",
)

METRIC_META = {
    "net_revenue": ("净收入", "currency"),
    "orders": ("订单", "count"),
    "paid_spend": ("广告花费", "currency"),
    "paid_purchases": ("平台购买", "count"),
    "paid_roas": ("平台 ROAS", "ratio"),
    "paid_cpa": ("平台 CPA", "currency"),
    "content_count": ("发布内容", "count"),
    "social_views": ("内容浏览", "count"),
    "blended_roas": ("Blended ROAS", "ratio"),
    "aov": ("客单价 AOV", "currency"),
}


def resolve_period(review_type: str, *, days: Optional[int] = None, end_date: Optional[date] = None) -> Dict[str, date]:
    today = datetime.now(timezone.utc).date()
    review_type = review_type.upper()
    if end_date is None:
        if review_type == "WEEKLY":
            end_date = today - timedelta(days=today.weekday() + 1)
        else:
            end_date = today - timedelta(days=1)
    if review_type == "DAILY":
        period_days = 1
    elif review_type == "WEEKLY":
        period_days = 7
    else:
        period_days = max(1, min(days or 7, 90))
    start_date = end_date - timedelta(days=period_days - 1)
    baseline_end = start_date - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=period_days - 1)
    return {
        "period_start": start_date,
        "period_end": end_date,
        "baseline_start": baseline_start,
        "baseline_end": baseline_end,
    }


def _delta(value: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if value is None or baseline is None or baseline == 0:
        return None
    return round((value - baseline) / abs(baseline) * 100, 1)


def _metric_payload(key: str, current: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    value = current.get("value") if current.get("ok") else None
    baseline_value = baseline.get("value") if baseline.get("ok") else None
    label, unit = METRIC_META[key]
    definition = current.get("definition") or {}
    return {
        "metric_key": key,
        "label": label,
        "unit": unit,
        "value": value,
        "baseline_value": baseline_value,
        "delta_percent": _delta(value, baseline_value),
        "source": definition.get("source"),
        "measurement_basis": definition.get("measurement_basis"),
        "freshness": current.get("freshness"),
        "caveat": current.get("caveat"),
        "status": "AVAILABLE" if value is not None else "NO_DATA",
    }


def _derived_metric(key: str, numerator: Dict[str, Any], denominator: Dict[str, Any]) -> Dict[str, Any]:
    label, unit = METRIC_META[key]
    top = numerator.get("value")
    bottom = denominator.get("value")
    baseline_top = numerator.get("baseline_value")
    baseline_bottom = denominator.get("baseline_value")
    value = round(float(top) / float(bottom), 2) if top is not None and bottom not in (None, 0) else None
    baseline = (
        round(float(baseline_top) / float(baseline_bottom), 2)
        if baseline_top is not None and baseline_bottom not in (None, 0)
        else None
    )
    return {
        "metric_key": key,
        "label": label,
        "unit": unit,
        "value": value,
        "baseline_value": baseline,
        "delta_percent": _delta(value, baseline),
        "source": ["COMMERCE", "ADS"] if key == "blended_roas" else "COMMERCE",
        "measurement_basis": "FIRST_PARTY_DERIVED",
        "freshness": numerator.get("freshness") or denominator.get("freshness"),
        "caveat": (
            "Shopify 净收入 / 广告平台花费；与平台归因 ROAS 分开。"
            if key == "blended_roas"
            else "Shopify 净收入 / Shopify 订单数。"
        ),
        "status": "AVAILABLE" if value is not None else "NO_DATA",
    }


def _findings(metrics: Dict[str, Dict[str, Any]], data_status: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    if data_status in {"STALE", "BLOCKED", "UNKNOWN"}:
        findings.append(
            {
                "type": "DATA_RISK",
                "severity": "AT_RISK",
                "title": "数据状态限制本次经营判断",
                "description": "先处理数据新鲜度或缺失问题，再确认经营变化。",
                "metric_key": None,
            }
        )
    for key in ("net_revenue", "paid_spend", "blended_roas", "paid_roas", "social_views"):
        metric = metrics[key]
        delta = metric.get("delta_percent")
        if delta is None or abs(delta) < 10:
            continue
        improving = delta > 0
        harmful_up = key in {"paid_spend"}
        severity = "WARNING" if improving == harmful_up else "INFO"
        direction = "上升" if improving else "下降"
        findings.append(
            {
                "type": "CHANGE",
                "severity": severity,
                "title": f"{metric['label']}较上一周期{direction} {abs(delta):.1f}%",
                "description": "这是同期变化，不代表已确认因果；需结合账号和活动明细验证。",
                "metric_key": key,
            }
        )
    return findings[:6]


def _summary(metrics: Dict[str, Dict[str, Any]], data_status: str) -> str:
    revenue = metrics["net_revenue"]
    spend = metrics["paid_spend"]
    if revenue["status"] == "NO_DATA" and spend["status"] == "NO_DATA":
        return "本周期暂无可用于经营判断的收入与花费数据，请先检查数据源和同步状态。"
    parts = []
    if revenue.get("delta_percent") is not None:
        direction = "上升" if revenue["delta_percent"] >= 0 else "下降"
        parts.append(f"净收入较上一周期{direction} {abs(revenue['delta_percent']):.1f}%")
    if spend.get("delta_percent") is not None:
        direction = "上升" if spend["delta_percent"] >= 0 else "下降"
        parts.append(f"广告花费{direction} {abs(spend['delta_percent']):.1f}%")
    if not parts:
        parts.append("核心指标已有数据，但上一周期基线不足，暂无法计算环比")
    suffix = "；数据状态正常，可继续拆解账号与活动驱动。" if data_status == "COMPLETE" else "；当前数据不完整，结论仅供初步观察。"
    return "，".join(parts) + suffix


async def build_preview(
    db: AsyncSession,
    *,
    workspace_id: str,
    review_type: str = "DAILY",
    days: Optional[int] = None,
    end_date: Optional[date] = None,
    account_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    period = resolve_period(review_type, days=days, end_date=end_date)
    metrics: Dict[str, Dict[str, Any]] = {}
    for key in CORE_METRICS:
        current = await query_metric(
            db,
            workspace_id=workspace_id,
            metric_key=key,
            account_ids=account_ids,
            start=period["period_start"],
            end=period["period_end"],
        )
        baseline = await query_metric(
            db,
            workspace_id=workspace_id,
            metric_key=key,
            account_ids=account_ids,
            start=period["baseline_start"],
            end=period["baseline_end"],
        )
        metrics[key] = _metric_payload(key, current, baseline)

    metrics["blended_roas"] = _derived_metric("blended_roas", metrics["net_revenue"], metrics["paid_spend"])
    metrics["aov"] = _derived_metric("aov", metrics["net_revenue"], metrics["orders"])

    sources = await DataHealthService().freshness(db, workspace_id=workspace_id)
    source_statuses = {str(source["status"]) for source in sources}
    if not sources:
        data_status = "UNKNOWN"
    elif "STALE" in source_statuses or "UNKNOWN" in source_statuses:
        data_status = "STALE"
    elif "DELAYED" in source_statuses:
        data_status = "PARTIAL"
    else:
        data_status = "COMPLETE"

    findings = _findings(metrics, data_status)
    caveats = sorted(
        {
            str(metric["caveat"])
            for metric in metrics.values()
            if metric.get("caveat")
        }
    )
    return {
        "workspace_id": workspace_id,
        "review_type": review_type.upper(),
        "period": {key: value.isoformat() for key, value in period.items()},
        "scope": {"account_ids": account_ids or []},
        "data_status": data_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": _summary(metrics, data_status),
        "metrics": metrics,
        "findings": findings,
        "sources": sources,
        "caveats": caveats,
    }


async def build_trends(
    db: AsyncSession,
    *,
    workspace_id: str,
    days: int = 7,
    account_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=max(1, min(days, 30)) - 1)
    metric_keys = (
        "net_revenue",
        "paid_spend",
        "orders",
        "social_views",
        "content_count",
    )
    series_maps: Dict[str, Dict[str, Optional[float]]] = {}
    for key in metric_keys:
        result = await query_metric(
            db,
            workspace_id=workspace_id,
            metric_key=key,
            account_ids=account_ids,
            start=start,
            end=end,
        )
        series_maps[key] = {
            str(item["date"]): item.get("value") for item in result.get("series", [])
        }

    rows = []
    current = start
    while current <= end:
        day = current.isoformat()
        row: Dict[str, Any] = {"date": day}
        for key in metric_keys:
            row[key] = series_maps[key].get(day)
        spend = row["paid_spend"]
        revenue = row["net_revenue"]
        row["blended_roas"] = (
            round(float(revenue) / float(spend), 2)
            if revenue is not None and spend not in (None, 0)
            else None
        )
        rows.append(row)
        current += timedelta(days=1)
    return {
        "workspace_id": workspace_id,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "rows": rows,
        "caveat": "趋势仅展示已入库事实；空值不会自动按零处理。",
    }


async def _campaign_period_map(
    db: AsyncSession,
    *,
    workspace_id: str,
    start: date,
    end: date,
    account_ids: Optional[List[str]],
) -> Dict[str, Dict[str, Any]]:
    source_scope = DataSource.workspace_id == workspace_id
    if workspace_id == "ws_main":
        source_scope = or_(source_scope, DataSource.workspace_id.is_(None))
    source_ids = list(
        (
            await db.execute(
                select(DataSource.id).where(
                    source_scope,
                    DataSource.provider.in_(("META_ADS", "GOOGLE_ADS")),
                )
            )
        ).scalars().all()
    )
    if not source_ids:
        return {}

    marketing_account_ids: Optional[List[str]] = None
    if account_ids:
        external_ids = list(
            (
                await db.execute(
                    select(ConnectedAccount.external_account_id).where(
                        ConnectedAccount.workspace_id == workspace_id,
                        ConnectedAccount.id.in_(account_ids),
                    )
                )
            ).scalars().all()
        )
        marketing_account_ids = list(
            (
                await db.execute(
                    select(MarketingAccount.id).where(
                        MarketingAccount.data_source_id.in_(source_ids),
                        MarketingAccount.external_account_id.in_(external_ids)
                        if external_ids
                        else MarketingAccount.id.is_(None),
                    )
                )
            ).scalars().all()
        )

    join_condition = and_(
        Campaign.data_source_id == AdPerformanceDaily.data_source_id,
        Campaign.external_campaign_id == AdPerformanceDaily.external_entity_id,
    )
    query = (
        select(
            Campaign.external_campaign_id,
            Campaign.name,
            Campaign.platform,
            Campaign.status,
            func.sum(AdPerformanceDaily.spend_amount).label("spend"),
            func.sum(AdPerformanceDaily.platform_purchases).label("purchases"),
            func.sum(AdPerformanceDaily.platform_conversion_value).label("revenue"),
            func.sum(AdPerformanceDaily.impressions).label("impressions"),
            func.sum(AdPerformanceDaily.clicks).label("clicks"),
        )
        .join(AdPerformanceDaily, join_condition)
        .where(
            Campaign.data_source_id.in_(source_ids),
            AdPerformanceDaily.entity_type == "CAMPAIGN",
            AdPerformanceDaily.date >= start,
            AdPerformanceDaily.date <= end,
        )
        .group_by(
            Campaign.external_campaign_id,
            Campaign.name,
            Campaign.platform,
            Campaign.status,
        )
    )
    if marketing_account_ids is not None:
        query = query.where(
            Campaign.marketing_account_id.in_(marketing_account_ids)
            if marketing_account_ids
            else Campaign.id.is_(None)
        )
    rows = (await db.execute(query)).all()
    result = {}
    for row in rows:
        spend = float(row.spend or 0)
        purchases = float(row.purchases or 0)
        revenue = float(row.revenue or 0)
        impressions = float(row.impressions or 0)
        clicks = float(row.clicks or 0)
        result[row.external_campaign_id] = {
            "campaign_id": row.external_campaign_id,
            "name": row.name or row.external_campaign_id,
            "platform": row.platform,
            "status": row.status,
            "spend": spend,
            "purchases": purchases,
            "revenue": revenue,
            "roas": round(revenue / spend, 2) if spend else None,
            "cpa": round(spend / purchases, 2) if purchases else None,
            "impressions": int(impressions),
            "clicks": int(clicks),
            "ctr": round(clicks / impressions * 100, 2) if impressions else None,
        }
    return result


async def build_campaign_breakdown(
    db: AsyncSession,
    *,
    workspace_id: str,
    review_type: str = "DAILY",
    days: Optional[int] = None,
    end_date: Optional[date] = None,
    account_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    period = resolve_period(review_type, days=days, end_date=end_date)
    current = await _campaign_period_map(
        db,
        workspace_id=workspace_id,
        start=period["period_start"],
        end=period["period_end"],
        account_ids=account_ids,
    )
    baseline = await _campaign_period_map(
        db,
        workspace_id=workspace_id,
        start=period["baseline_start"],
        end=period["baseline_end"],
        account_ids=account_ids,
    )
    rows = []
    for campaign_id, item in current.items():
        previous = baseline.get(campaign_id, {})
        rows.append(
            {
                **item,
                "baseline_spend": previous.get("spend"),
                "baseline_roas": previous.get("roas"),
                "spend_delta_percent": _delta(
                    item.get("spend"), previous.get("spend")
                ),
                "roas_delta_percent": _delta(
                    item.get("roas"), previous.get("roas")
                ),
            }
        )
    rows.sort(key=lambda item: float(item.get("spend") or 0), reverse=True)
    return {
        "workspace_id": workspace_id,
        "period": {key: value.isoformat() for key, value in period.items()},
        "rows": rows,
        "total": len(rows),
        "caveat": "Campaign 收入与 ROAS 为平台归因口径，不等同于第一方净收入。",
    }


def serialize_review(review: ReviewRun, followups: Optional[List[ReviewFollowup]] = None) -> Dict[str, Any]:
    result = {
        "id": str(review.id),
        "workspace_id": review.workspace_id,
        "review_type": review.review_type,
        "period": {
            "period_start": review.period_start.isoformat(),
            "period_end": review.period_end.isoformat(),
            "baseline_start": review.baseline_start.isoformat(),
            "baseline_end": review.baseline_end.isoformat(),
        },
        "scope": review.scope,
        "data_status": review.data_status,
        "metrics": review.metric_snapshot,
        "summary": review.summary,
        "caveats": review.caveats or [],
        "status": review.status,
        "created_by": review.created_by,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        "locked_at": review.locked_at.isoformat() if review.locked_at else None,
    }
    if followups is not None:
        result["followups"] = [serialize_followup(item) for item in followups]
    return result


def serialize_followup(item: ReviewFollowup) -> Dict[str, Any]:
    return {
        "id": str(item.id),
        "review_id": item.review_id,
        "workspace_id": item.workspace_id,
        "title": item.title,
        "owner_id": item.owner_id,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "status": item.status,
        "result": item.result,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


async def create_review(
    db: AsyncSession,
    *,
    workspace_id: str,
    review_type: str,
    days: Optional[int],
    end_date: Optional[date],
    account_ids: Optional[List[str]],
    summary: Optional[str],
    created_by: str,
) -> ReviewRun:
    preview = await build_preview(
        db,
        workspace_id=workspace_id,
        review_type=review_type,
        days=days,
        end_date=end_date,
        account_ids=account_ids,
    )
    period = preview["period"]
    review = ReviewRun(
        workspace_id=workspace_id,
        review_type=preview["review_type"],
        period_start=date.fromisoformat(period["period_start"]),
        period_end=date.fromisoformat(period["period_end"]),
        baseline_start=date.fromisoformat(period["baseline_start"]),
        baseline_end=date.fromisoformat(period["baseline_end"]),
        scope=preview["scope"],
        data_status=preview["data_status"],
        metric_snapshot=preview["metrics"],
        summary=summary or preview["summary"],
        caveats=preview["caveats"],
        created_by=created_by,
    )
    db.add(review)
    await db.flush()
    return review


async def list_reviews(db: AsyncSession, *, workspace_id: str, limit: int = 50) -> List[ReviewRun]:
    return list(
        (
            await db.execute(
                select(ReviewRun)
                .where(ReviewRun.workspace_id == workspace_id)
                .order_by(ReviewRun.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    )


async def get_review(db: AsyncSession, *, workspace_id: str, review_id: str) -> Optional[Dict[str, Any]]:
    review = (
        await db.execute(
            select(ReviewRun).where(ReviewRun.id == review_id, ReviewRun.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()
    if review is None:
        return None
    followups = list(
        (
            await db.execute(
                select(ReviewFollowup)
                .where(
                    ReviewFollowup.review_id == review_id,
                    ReviewFollowup.workspace_id == workspace_id,
                )
                .order_by(ReviewFollowup.created_at.asc())
            )
        ).scalars().all()
    )
    return serialize_review(review, followups)
