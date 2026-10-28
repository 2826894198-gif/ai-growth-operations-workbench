from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl.validators import safe_divide
from app.models.ad_performance import GoogleKeywordDaily, GoogleSearchTermDaily


async def get_search_term_performance(db: AsyncSession, days: int = 30) -> Dict[str, Any]:
    start = date.today() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(
                GoogleSearchTermDaily.search_term,
                func.sum(GoogleSearchTermDaily.cost).label("spend"),
                func.sum(GoogleSearchTermDaily.clicks).label("clicks"),
                func.sum(GoogleSearchTermDaily.conversions).label("conversions"),
            )
            .where(GoogleSearchTermDaily.date >= start)
            .group_by(GoogleSearchTermDaily.search_term)
            .order_by(func.sum(GoogleSearchTermDaily.cost).desc())
            .limit(100)
        )
    ).all()
    return {
        "search_terms": [
            {
                "term": r.search_term,
                "spend": float(r.spend or 0),
                "clicks": int(r.clicks or 0),
                "conversions": float(r.conversions or 0),
                "cpa": float(safe_divide(Decimal(r.spend or 0), Decimal(r.conversions or 0))) if r.conversions else None,
            }
            for r in rows
        ],
        "_output_ref": "search-term://performance/30d",
    }


async def get_keyword_performance(db: AsyncSession, days: int = 30) -> Dict[str, Any]:
    start = date.today() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(
                GoogleKeywordDaily.criterion_id,
                GoogleKeywordDaily.keyword_text,
                GoogleKeywordDaily.match_type,
                func.sum(GoogleKeywordDaily.cost).label("spend"),
                func.sum(GoogleKeywordDaily.conversions).label("conversions"),
            )
            .where(GoogleKeywordDaily.date >= start)
            .group_by(GoogleKeywordDaily.criterion_id, GoogleKeywordDaily.keyword_text, GoogleKeywordDaily.match_type)
            .order_by(func.sum(GoogleKeywordDaily.cost).desc())
            .limit(100)
        )
    ).all()
    return {"keywords": [dict(r._mapping) for r in rows]}


async def get_query_clusters(db: AsyncSession, terms: List[str] = None) -> Dict[str, Any]:
    if not terms:
        data = await get_search_term_performance(db, 30)
        terms = [t["term"] for t in data["search_terms"][:50]]
    return {
        "clusters": [
            {
                "cluster_name": "mock_cluster",
                "query_count": len(terms),
                "semantic_class": "UNKNOWN",
                "commercial_relevance": "UNKNOWN",
            }
        ],
        "note": "AI semantic classification runs via Search Agent",
    }


async def get_negative_candidates(db: AsyncSession, days: int = 30) -> Dict[str, Any]:
    data = await get_search_term_performance(db, days)
    candidates = []
    for item in data["search_terms"]:
        if item["spend"] and item["conversions"] == 0 and item["clicks"] and item["clicks"] >= 10:
            candidates.append(
                {
                    "term": item["term"],
                    "spend": item["spend"],
                    "clicks": item["clicks"],
                    "conversions": 0,
                    "negative_candidate_confidence": 0.5,
                    "recommended_match_type": "human review",
                }
            )
    return {"negative_candidates": candidates[:50]}
