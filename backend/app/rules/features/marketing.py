from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.validators import safe_divide
from app.models.ad_performance import AdPerformanceDaily
from app.rules.features.anomalies import percent_change, zscore
from app.rules.features.windows import previous_range, rolling_range


def _agg_rows(rows) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = str(row.external_entity_id)
        item = out.setdefault(key, {})
        item["spend"] = float(row.spend or 0)
        item["impressions"] = float(row.impressions or 0)
        item["clicks"] = float(row.clicks or 0)
        item["purchases"] = float(getattr(row, "purchases", None) or 0)
        item["conversions"] = float(getattr(row, "conversions", None) or 0)
        item["conversion_value"] = float(getattr(row, "conversion_value", None) or 0)
        item["frequency"] = float(getattr(row, "frequency", None) or 0)
        item["cpm"] = float(getattr(row, "cpm", None) or 0)
        item["cpc"] = float(getattr(row, "cpc", None) or 0)
    return out


async def load_marketing_features(
    db: AsyncSession,
    platform: str,
    entity_type: str,
    external_ids: List[str],
    end: date,
    days: int = 7,
) -> Dict[str, Dict[str, Any]]:
    """Batch-load 7d/3d/previous-window features per entity (one query per window)."""
    if not external_ids:
        return {}
    features: Dict[str, Dict[str, Any]] = {eid: {} for eid in external_ids}

    for window_days, prefix in ((3, "3d"), (7, "7d"), (1, "1d")):
        start, stop = rolling_range(end, window_days)
        rows = (
            await db.execute(
                select(
                    AdPerformanceDaily.external_entity_id,
                    func.sum(AdPerformanceDaily.spend_amount).label("spend"),
                    func.sum(AdPerformanceDaily.impressions).label("impressions"),
                    func.sum(AdPerformanceDaily.clicks).label("clicks"),
                    func.sum(AdPerformanceDaily.platform_purchases).label("purchases"),
                    func.sum(AdPerformanceDaily.platform_conversions).label("conversions"),
                    func.sum(AdPerformanceDaily.platform_conversion_value).label("conversion_value"),
                    func.avg(AdPerformanceDaily.frequency).label("frequency"),
                    func.avg(AdPerformanceDaily.cpm).label("cpm"),
                    func.avg(AdPerformanceDaily.cpc).label("cpc"),
                )
                .where(
                    AdPerformanceDaily.platform == platform,
                    AdPerformanceDaily.entity_type == entity_type,
                    AdPerformanceDaily.external_entity_id.in_(external_ids),
                    AdPerformanceDaily.date >= start,
                    AdPerformanceDaily.date <= stop,
                )
                .group_by(AdPerformanceDaily.external_entity_id)
            )
        ).all()
        for row in rows:
            data = _agg_rows([row])[str(row.external_entity_id)]
            features[str(row.external_entity_id)].update(
                {
                    f"spend_{prefix}": data["spend"],
                    f"impressions_{prefix}": data["impressions"],
                    f"clicks_{prefix}": data["clicks"],
                    f"purchases_{prefix}": data["purchases"],
                    f"conversions_{prefix}": data["conversions"],
                    f"conversion_value_{prefix}": data["conversion_value"],
                    f"frequency_{prefix}": data["frequency"],
                    f"cpm_{prefix}": data["cpm"],
                    f"cpc_{prefix}": data["cpc"],
                }
            )

    prev_start, prev_stop = previous_range(end, 7)
    rows = (
        await db.execute(
            select(
                AdPerformanceDaily.external_entity_id,
                func.sum(AdPerformanceDaily.spend_amount).label("spend"),
                func.sum(AdPerformanceDaily.impressions).label("impressions"),
                func.sum(AdPerformanceDaily.clicks).label("clicks"),
                func.sum(AdPerformanceDaily.platform_purchases).label("purchases"),
                func.sum(AdPerformanceDaily.platform_conversion_value).label("conversion_value"),
                func.avg(AdPerformanceDaily.frequency).label("frequency"),
            )
            .where(
                AdPerformanceDaily.platform == platform,
                AdPerformanceDaily.entity_type == entity_type,
                AdPerformanceDaily.external_entity_id.in_(external_ids),
                AdPerformanceDaily.date >= prev_start,
                AdPerformanceDaily.date <= prev_stop,
            )
            .group_by(AdPerformanceDaily.external_entity_id)
        )
    ).all()
    prev = _agg_rows(rows)

    # 14-day series for z-scores
    series_rows = (
        await db.execute(
            select(
                AdPerformanceDaily.external_entity_id,
                AdPerformanceDaily.date,
                AdPerformanceDaily.cpm,
                AdPerformanceDaily.cpc,
            ).where(
                AdPerformanceDaily.platform == platform,
                AdPerformanceDaily.entity_type == entity_type,
                AdPerformanceDaily.external_entity_id.in_(external_ids),
                AdPerformanceDaily.date >= (end - timedelta(days=13)),
                AdPerformanceDaily.date <= end,
            )
        )
    ).all()
    series: Dict[str, Dict[str, List[float]]] = {}
    for row in series_rows:
        item = series.setdefault(str(row.external_entity_id), {"cpm": [], "cpc": []})
        if row.cpm is not None:
            item["cpm"].append(float(row.cpm))
        if row.cpc is not None:
            item["cpc"].append(float(row.cpc))

    for eid in external_ids:
        f = features[eid]
        cur = f.get("spend_7d", 0)
        base = prev.get(eid, {}).get("spend", 0)
        f["spend_change_pct_7d"] = percent_change(cur, base)
        ctr_cur = safe_divide(Decimal(f.get("clicks_7d") or 0), Decimal(f.get("impressions_7d") or 0))
        ctr_prev = safe_divide(Decimal(prev.get(eid, {}).get("clicks", 0)), Decimal(prev.get(eid, {}).get("impressions", 0)))
        f["ctr_7d"] = float(ctr_cur) if ctr_cur is not None else None
        f["ctr_change_pct_7d"] = percent_change(float(ctr_cur) if ctr_cur is not None else None, float(ctr_prev) if ctr_prev is not None else None)
        purchases = f.get("purchases_7d")
        spend = f.get("spend_7d")
        f["cpa_7d"] = float(safe_divide(Decimal(spend or 0), Decimal(purchases or 0))) if purchases else None
        f["roas_7d"] = float(safe_divide(Decimal(f.get("conversion_value_7d") or 0), Decimal(spend or 0))) if spend else None
        f["cvr_7d"] = float(safe_divide(Decimal(purchases or 0), Decimal(f.get("clicks_7d") or 0))) if f.get("clicks_7d") else None
        purchases_3d = f.get("purchases_3d")
        spend_3d = f.get("spend_3d")
        f["cpa_3d"] = float(safe_divide(Decimal(spend_3d or 0), Decimal(purchases_3d or 0))) if purchases_3d else None
        f["impressions_change_pct_7d"] = percent_change(
            f.get("impressions_7d"), prev.get(eid, {}).get("impressions", 0)
        )
        cpa_prev = (
            float(safe_divide(Decimal(prev.get(eid, {}).get("spend", 0)), Decimal(prev.get(eid, {}).get("purchases", 0))))
            if prev.get(eid, {}).get("purchases")
            else None
        )
        f["cpa_change_pct_7d"] = percent_change(f.get("cpa_7d"), cpa_prev)
        f["cpm_zscore_7d"] = zscore(series.get(eid, {}).get("cpm", []), f.get("cpm_7d"))
        f["cpc_zscore_7d"] = zscore(series.get(eid, {}).get("cpc", []), f.get("cpc_7d"))
    return features
