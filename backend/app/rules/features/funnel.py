from datetime import date
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.validators import safe_divide
from app.models.ad_performance import MetaActionDaily
from app.rules.features.windows import rolling_range


async def load_funnel_features(
    db: AsyncSession,
    entity_type: str,
    external_ids,
    end: date,
    days: int = 7,
) -> Dict[str, Dict[str, Any]]:
    start, stop = rolling_range(end, days)
    rows = (
        await db.execute(
            select(
                MetaActionDaily.entity_external_id,
                MetaActionDaily.action_type,
                func.sum(MetaActionDaily.action_count).label("count"),
            )
            .where(
                MetaActionDaily.entity_type == entity_type,
                MetaActionDaily.entity_external_id.in_(list(external_ids)),
                MetaActionDaily.date >= start,
                MetaActionDaily.date <= stop,
            )
            .group_by(MetaActionDaily.entity_external_id, MetaActionDaily.action_type)
        )
    ).all()
    out: Dict[str, Dict[str, Any]] = {str(eid): {} for eid in external_ids}
    for row in rows:
        out[str(row.entity_external_id)][str(row.action_type)] = float(row.count or 0)
    for eid, counts in out.items():
        link_clicks = counts.get("link_click", 0)
        lpv = counts.get("landing_page_view", 0)
        atc = counts.get("add_to_cart", 0)
        checkout = counts.get("initiate_checkout", 0)
        purchase = counts.get("purchase", 0)
        out[eid].update(
            {
                "click_to_lpv_7d": float(safe_divide(Decimal(lpv), Decimal(link_clicks))) if link_clicks else None,
                "lpv_to_atc_7d": float(safe_divide(Decimal(atc), Decimal(lpv))) if lpv else None,
                "atc_to_checkout_7d": float(safe_divide(Decimal(checkout), Decimal(atc))) if atc else None,
                "checkout_to_purchase_7d": float(safe_divide(Decimal(purchase), Decimal(checkout))) if checkout else None,
            }
        )
    return out
