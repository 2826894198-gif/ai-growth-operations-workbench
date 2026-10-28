from datetime import date
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.validators import safe_divide
from app.models.ad_performance import GoogleKeywordDaily, GoogleSearchTermDaily
from app.rules.features.anomalies import percent_change
from app.rules.features.windows import previous_range, rolling_range

SEMANTIC_WASTE_TERMS = ("free", "repair", "manual", "diy", "download", "job", "wholesale")


async def load_search_term_features(
    db: AsyncSession, terms: List[str], end: date, days: int = 30
) -> Dict[str, Dict[str, Any]]:
    start, stop = rolling_range(end, days)
    rows = (
        await db.execute(
            select(
                GoogleSearchTermDaily.search_term,
                func.sum(GoogleSearchTermDaily.cost).label("cost"),
                func.sum(GoogleSearchTermDaily.clicks).label("clicks"),
                func.sum(GoogleSearchTermDaily.conversions).label("conversions"),
                func.sum(GoogleSearchTermDaily.conversion_value).label("conversion_value"),
            )
            .where(
                GoogleSearchTermDaily.search_term.in_(terms),
                GoogleSearchTermDaily.date >= start,
                GoogleSearchTermDaily.date <= stop,
            )
            .group_by(GoogleSearchTermDaily.search_term)
        )
    ).all()
    out: Dict[str, Dict[str, Any]] = {term: {} for term in terms}
    for row in rows:
        cost = float(row.cost or 0)
        conversions = float(row.conversions or 0)
        out[row.search_term] = {
            "search_term_spend_30d": cost,
            "search_term_conversions_30d": conversions,
            "search_term_cpa_30d": float(safe_divide(Decimal(cost), Decimal(conversions))) if conversions else None,
            "search_term_semantic_waste": any(word in row.search_term.lower() for word in SEMANTIC_WASTE_TERMS),
        }
    return out


async def load_keyword_features(
    db: AsyncSession, criterion_ids: List[str], end: date, days: int = 7
) -> Dict[str, Dict[str, Any]]:
    start, stop = rolling_range(end, days)
    rows = (
        await db.execute(
            select(
                GoogleKeywordDaily.criterion_id,
                func.sum(GoogleKeywordDaily.cost).label("cost"),
                func.sum(GoogleKeywordDaily.clicks).label("clicks"),
                func.sum(GoogleKeywordDaily.conversions).label("conversions"),
                func.sum(GoogleKeywordDaily.impressions).label("impressions"),
            )
            .where(
                GoogleKeywordDaily.criterion_id.in_(criterion_ids),
                GoogleKeywordDaily.date >= start,
                GoogleKeywordDaily.date <= stop,
            )
            .group_by(GoogleKeywordDaily.criterion_id)
        )
    ).all()
    prev_start, prev_stop = previous_range(end, days)
    prev_rows = (
        await db.execute(
            select(
                GoogleKeywordDaily.criterion_id,
                func.sum(GoogleKeywordDaily.cost).label("cost"),
                func.sum(GoogleKeywordDaily.clicks).label("clicks"),
                func.sum(GoogleKeywordDaily.conversions).label("conversions"),
                func.sum(GoogleKeywordDaily.impressions).label("impressions"),
            )
            .where(
                GoogleKeywordDaily.criterion_id.in_(criterion_ids),
                GoogleKeywordDaily.date >= prev_start,
                GoogleKeywordDaily.date <= prev_stop,
            )
            .group_by(GoogleKeywordDaily.criterion_id)
        )
    ).all()
    out: Dict[str, Dict[str, Any]] = {cid: {} for cid in criterion_ids}
    prev_map = {str(row.criterion_id): row for row in prev_rows}
    for row in rows:
        cost = float(row.cost or 0)
        conversions = float(row.conversions or 0)
        impressions = float(row.impressions or 0)
        clicks = float(row.clicks or 0)
        prev = prev_map.get(str(row.criterion_id))
        prev_ctr = safe_divide(Decimal(prev.clicks or 0), Decimal(prev.impressions or 0)) if prev else None
        cur_ctr = safe_divide(Decimal(clicks), Decimal(impressions)) if impressions else None
        out[str(row.criterion_id)] = {
            "keyword_spend_7d": cost,
            "keyword_conversions_7d": conversions,
            "keyword_cpa_7d": float(safe_divide(Decimal(cost), Decimal(conversions))) if conversions else None,
            "keyword_ctr_change_pct_7d": percent_change(
                float(cur_ctr) if cur_ctr is not None else None,
                float(prev_ctr) if prev_ctr is not None else None,
            ),
        }
    return out
