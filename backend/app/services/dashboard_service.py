from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.validators import safe_divide
from app.models.ad_performance import AdPerformanceDaily, GoogleSearchTermDaily
from app.models.ai import AIAgentRun
from app.models.commerce import Order
from app.models.marketing import Ad, Creative
from app.models.rules import Recommendation, RuleEvaluation
from app.services.metrics_service import MetricsService


def _pct(current, baseline):
    change = safe_divide(Decimal(current) - Decimal(baseline) if current is not None and baseline is not None else None, Decimal(baseline)) if baseline else None
    return round(float(change * 100), 1) if change is not None else None


def _kpi_status(current, target, direction: str, warning_pct: float = 10.0) -> str:
    if current is None or target is None:
        return "UNKNOWN"
    if direction == "down":
        good = current <= target
        warning = current <= target * (1 + warning_pct / 100)
    else:
        good = current >= target
        warning = current >= target * (1 - warning_pct / 100)
    if good:
        return "GOOD"
    if warning:
        return "WATCH"
    return "BAD"


class DashboardService:
    async def overview(
        self,
        db: AsyncSession,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        compare: str = "PREVIOUS_PERIOD",
    ) -> Dict[str, Any]:
        end = date.fromisoformat(end_date) if end_date else date.today()
        start = date.fromisoformat(start_date) if start_date else end - timedelta(days=6)
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=(end - start).days)

        metrics = MetricsService()
        current = await metrics.commerce(db, start.isoformat(), end.isoformat())
        previous = await metrics.commerce(db, prev_start.isoformat(), prev_end.isoformat())
        platforms = await metrics.platforms(db, start.isoformat(), end.isoformat())
        paid_spend = sum(p["spend"] for p in platforms)
        net_revenue = current["net_revenue"]
        blended_roas = float(safe_divide(Decimal(net_revenue), Decimal(paid_spend))) if paid_spend else None
        prev_spend = sum(
            p["spend"]
            for p in await metrics.platforms(db, prev_start.isoformat(), prev_end.isoformat())
        )
        targets = await self._targets(db)
        break_even = targets.get("break_even_roas")
        if blended_roas is None:
            business_status = "UNKNOWN"
        elif break_even and blended_roas < break_even:
            business_status = "AT_RISK"
        elif paid_spend > (targets.get("max_daily_spend") or 10**9) * (end - start).days:
            business_status = "CRITICAL"
        elif blended_roas >= (targets.get("target_roas") or break_even or 1.0):
            business_status = "HEALTHY"
        else:
            business_status = "WATCH"

        kpis = [
            {"key": "paid_spend", "label": "广告花费", "value": paid_spend, "format": "currency", "positive_direction": "down", "compare_pct": _pct(paid_spend, prev_spend), "target": targets.get("max_daily_spend"), "status": "UNKNOWN"},
            {"key": "net_revenue", "label": "净收入", "value": net_revenue, "format": "currency", "positive_direction": "up", "compare_pct": _pct(net_revenue, previous["net_revenue"]), "status": "GOOD" if net_revenue >= (previous["net_revenue"] or 0) else "WATCH"},
            {"key": "orders", "label": "订单数", "value": current["orders"], "format": "integer", "positive_direction": "up", "compare_pct": _pct(current["orders"], previous["orders"]), "status": "GOOD" if current["orders"] >= (previous["orders"] or 0) else "WATCH"},
            {"key": "blended_roas", "label": "混合 ROAS", "value": blended_roas, "format": "ratio", "positive_direction": "up", "compare_pct": _pct(blended_roas, (float(safe_divide(Decimal(previous["net_revenue"]), Decimal(prev_spend))) if prev_spend else None)), "target": targets.get("target_roas"), "status": _kpi_status(blended_roas, targets.get("target_roas") or break_even, "up")},
            {"key": "aov", "label": "客单价", "value": current["aov"], "format": "currency", "positive_direction": "up", "compare_pct": _pct(current["aov"], previous["aov"]), "status": "UNKNOWN"},
            {"key": "refund_rate", "label": "退款率", "value": current["refunds"] / current["gross_revenue"] if current["gross_revenue"] else None, "format": "percent", "positive_direction": "down", "target": targets.get("refund_rate_critical"), "status": _kpi_status(current["refunds"] / current["gross_revenue"] if current["gross_revenue"] else None, targets.get("refund_rate_critical"), "down")},
        ]

        recs = (
            await db.execute(
                select(Recommendation)
                .where(Recommendation.status.in_(["OPEN", "ACKNOWLEDGED"]))
                .order_by(Recommendation.severity.desc(), Recommendation.confidence.desc(), Recommendation.created_at.desc())
                .limit(5)
            )
        ).scalars().all()
        trend = await self._trend(db, start, end)
        highlights = await self._highlights(db, start, end)
        brief = await self._daily_brief(db)
        freshness = await self._freshness(db)
        return {
            "business_status": business_status,
            "kpis": kpis,
            "recommendations": [
                {
                    "id": str(r.id),
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "platform": r.platform,
                    "primary_action": r.primary_action,
                    "reason_group": r.reason_group,
                    "severity": r.severity,
                    "confidence": r.confidence,
                    "evidence": r.evidence,
                }
                for r in recs
            ],
            "platforms": platforms,
            "trend": trend,
            "highlights": highlights,
            "daily_brief": brief,
            "freshness": freshness,
            "meta": {"data_as_of": end.isoformat(), "timezone": "America/New_York", "currency": "USD", "partial": False},
        }

    async def _targets(self, db: AsyncSession) -> Dict[str, Any]:
        from app.models.rules import BusinessTargetProfile

        rows = (await db.execute(select(BusinessTargetProfile))).scalars().all()
        result: Dict[str, Any] = {}
        for row in rows:
            for key in ("target_cpa", "target_roas", "break_even_roas", "max_daily_spend", "refund_rate_critical"):
                value = getattr(row, key)
                if value is not None:
                    result[key] = value
        return result

    async def _trend(self, db: AsyncSession, start: date, end: date) -> List[Dict[str, Any]]:
        perf_rows = (
            await db.execute(
                select(AdPerformanceDaily.date, func.sum(AdPerformanceDaily.spend_amount).label("spend"))
                .where(AdPerformanceDaily.entity_type == "CAMPAIGN", AdPerformanceDaily.date >= start, AdPerformanceDaily.date <= end)
                .group_by(AdPerformanceDaily.date)
                .order_by(AdPerformanceDaily.date)
            )
        ).all()
        order_rows = (
            await db.execute(
                select(func.date(Order.order_created_at).label("day"), func.sum(Order.net_revenue_amount).label("net"))
                .where(func.date(Order.order_created_at) >= start, func.date(Order.order_created_at) <= end)
                .group_by(func.date(Order.order_created_at))
                .order_by(func.date(Order.order_created_at))
            )
        ).all()
        spend_map = {r.date.isoformat(): float(r.spend or 0) for r in perf_rows}
        net_map = {str(r.day): float(r.net or 0) for r in order_rows}
        result = []
        cursor = start
        while cursor <= end:
            day = cursor.isoformat()
            spend = spend_map.get(day, 0)
            net = net_map.get(day, 0)
            result.append({"date": day, "spend": spend, "net_revenue": net, "blended_roas": float(safe_divide(Decimal(net), Decimal(spend))) if spend else None})
            cursor += timedelta(days=1)
        return result

    async def _highlights(self, db: AsyncSession, start: date, end: date) -> Dict[str, Any]:
        winner = (
            await db.execute(
                select(AdPerformanceDaily.external_entity_id, func.sum(AdPerformanceDaily.platform_purchases).label("purchases"))
                .where(AdPerformanceDaily.entity_type == "AD", AdPerformanceDaily.platform == "META_ADS", AdPerformanceDaily.date >= start, AdPerformanceDaily.date <= end)
                .group_by(AdPerformanceDaily.external_entity_id)
                .order_by(func.sum(AdPerformanceDaily.platform_purchases).desc())
                .limit(1)
            )
        ).first()
        creative = None
        if winner:
            creative = (
                await db.execute(
                    select(Creative)
                    .join(Ad, Ad.creative_id == Creative.external_creative_id)
                    .where(Ad.external_ad_id == winner.external_entity_id)
                    .limit(1)
                )
            ).scalar_one_or_none()
        top_waste = (
            await db.execute(
                select(GoogleSearchTermDaily.search_term, func.sum(GoogleSearchTermDaily.cost).label("spend"))
                .where(GoogleSearchTermDaily.date >= start)
                .group_by(GoogleSearchTermDaily.search_term)
                .order_by(func.sum(GoogleSearchTermDaily.cost).desc())
                .limit(1)
            )
        ).first()
        return {
            "creative_winner": {"creative_id": creative.external_creative_id if creative else None, "name": creative.title if creative else None, "ad_id": winner.external_entity_id if winner else None},
            "search_waste": {"term": top_waste.search_term if top_waste else None, "spend": float(top_waste.spend or 0) if top_waste else None},
            "funnel_drop": {"stage": "CHECKOUT_TO_PURCHASE", "note": "see Funnel page"},
        }

    async def _daily_brief(self, db: AsyncSession) -> Dict[str, Any]:
        run = (
            await db.execute(
                select(AIAgentRun)
                .where(AIAgentRun.task_type == "DAILY_GROWTH_REVIEW")
                .order_by(AIAgentRun.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if run is None:
            return {"available": False, "message": "运行 make ai-run-daily 生成今日简报"}
        strategy = (run.meta or {}).get("strategy_output") or {}
        return {
            "available": True,
            "run_id": str(run.id),
            "executive_summary": strategy.get("executive_summary", "（无简报内容）"),
            "actions_now": strategy.get("actions_now", []),
            "do_not_change": strategy.get("do_not_change", []),
            "confidence": strategy.get("confidence", 0),
            "source": "AI",
        }

    async def _freshness(self, db: AsyncSession) -> List[Dict[str, Any]]:
        from app.services.data_health_service import DataHealthService

        return await DataHealthService().freshness(db)

    async def live(self, db: AsyncSession) -> Dict[str, Any]:
        today = date.today()
        start, end = today, today
        overview = await self.overview(db, start_date=start.isoformat(), end_date=end.isoformat())
        alerts = (
            await db.execute(
                select(Recommendation)
                .where(Recommendation.status.in_(["OPEN", "ACKNOWLEDGED"]), Recommendation.severity.in_(["HIGH", "CRITICAL"]))
                .order_by(Recommendation.severity.desc())
                .limit(20)
            )
        ).scalars().all()
        campaigns = (
            await db.execute(
                select(
                    AdPerformanceDaily.external_entity_id,
                    AdPerformanceDaily.platform,
                    func.sum(AdPerformanceDaily.spend_amount).label("spend"),
                    func.sum(AdPerformanceDaily.platform_purchases).label("conversions"),
                )
                .where(AdPerformanceDaily.entity_type == "CAMPAIGN", AdPerformanceDaily.date == today)
                .group_by(AdPerformanceDaily.external_entity_id, AdPerformanceDaily.platform)
                .order_by(func.sum(AdPerformanceDaily.spend_amount).desc())
                .limit(50)
            )
        ).all()
        timeline = (
            await db.execute(
                select(RuleEvaluation)
                .order_by(RuleEvaluation.evaluated_at.desc())
                .limit(20)
            )
        ).scalars().all()
        kpis = {k["key"]: k["value"] for k in overview["kpis"]}
        return {
            "today": {
                "spend": kpis.get("paid_spend"),
                "orders": kpis.get("orders"),
                "net_revenue": kpis.get("net_revenue"),
                "blended_roas": kpis.get("blended_roas"),
                "provisional": True,
            },
            "velocity": {"spend_expected_note": "same-weekday baseline (see Data Health)"},
            "alerts": [
                {"id": str(r.id), "severity": r.severity, "message": f"{r.reason_group} on {r.entity_type} {r.entity_id}", "primary_action": r.primary_action}
                for r in alerts
            ],
            "campaigns": [
                {"campaign_id": r.external_entity_id, "platform": r.platform, "spend": float(r.spend or 0), "conversions": float(r.conversions or 0)}
                for r in campaigns
            ],
            "timeline": [
                {"time": r.evaluated_at.isoformat() if r.evaluated_at else None, "rule": r.rule_key, "entity": r.entity_id, "result": r.result}
                for r in timeline
            ],
            "freshness": overview["freshness"],
        }


async def metric_metadata() -> List[Dict[str, Any]]:
    return [
        {"key": "paid_spend", "label": "广告花费", "format": "currency", "positive_direction": "down"},
        {"key": "net_revenue", "label": "净收入", "format": "currency", "positive_direction": "up"},
        {"key": "orders", "label": "订单数", "format": "integer", "positive_direction": "up"},
        {"key": "blended_roas", "label": "混合 ROAS", "format": "ratio", "positive_direction": "up"},
        {"key": "aov", "label": "客单价", "format": "currency", "positive_direction": "up"},
        {"key": "refund_rate", "label": "退款率", "format": "percent", "positive_direction": "down"},
        {"key": "cpa", "label": "CPA", "format": "currency", "positive_direction": "down"},
        {"key": "ctr", "label": "CTR", "format": "percent", "positive_direction": "up"},
        {"key": "cvr", "label": "CVR", "format": "percent", "positive_direction": "up"},
    ]
