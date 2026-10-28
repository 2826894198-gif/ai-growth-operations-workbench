from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.etl.validators import safe_divide
from app.models.ad_performance import GoogleKeywordDaily, GoogleSearchTermDaily

router = APIRouter()


@router.get("/terms")
async def search_terms(days: int = Query(30), db: AsyncSession = Depends(get_db)):
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
            .limit(500)
        )
    ).all()
    return [
        {
            "term": r.search_term,
            "spend": float(r.spend or 0),
            "clicks": int(r.clicks or 0),
            "conversions": float(r.conversions or 0),
            "cpa": float(safe_divide(Decimal(r.spend or 0), Decimal(r.conversions or 0))) if r.conversions else None,
            "intent": "UNKNOWN",
            "commercial_relevance": "UNKNOWN",
        }
        for r in rows
    ]


@router.get("/keywords")
async def keywords(days: int = Query(30), db: AsyncSession = Depends(get_db)):
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
            .limit(500)
        )
    ).all()
    return [dict(r._mapping) for r in rows]


@router.get("/clusters")
async def clusters(db: AsyncSession = Depends(get_db)):
    return {"clusters": [{"cluster_name": "mock_cluster", "query_count": 0, "semantic_class": "UNKNOWN", "spend": 0, "conversions": 0}]}


@router.get("/negative-candidates")
async def negative_candidates(days: int = Query(30), db: AsyncSession = Depends(get_db)):
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
            .having(func.sum(GoogleSearchTermDaily.conversions) == 0)
            .order_by(func.sum(GoogleSearchTermDaily.cost).desc())
            .limit(100)
        )
    ).all()
    return [
        {
            "term": r.search_term,
            "spend": float(r.spend or 0),
            "clicks": int(r.clicks or 0),
            "conversions": 0,
            "semantic_class": "UNKNOWN",
            "negative_candidate_confidence": 0.5,
            "recommended_match_type": "human review",
        }
        for r in rows
        if (r.clicks or 0) >= 10
    ]


@router.get("/expansion-candidates")
async def expansion_candidates(days: int = Query(30), db: AsyncSession = Depends(get_db)):
    start = date.today() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(
                GoogleSearchTermDaily.search_term,
                func.sum(GoogleSearchTermDaily.cost).label("spend"),
                func.sum(GoogleSearchTermDaily.conversions).label("conversions"),
                func.sum(GoogleSearchTermDaily.conversion_value).label("conversion_value"),
            )
            .where(GoogleSearchTermDaily.date >= start)
            .group_by(GoogleSearchTermDaily.search_term)
            .having(func.sum(GoogleSearchTermDaily.conversions) >= 3)
            .order_by(func.sum(GoogleSearchTermDaily.conversions).desc())
            .limit(100)
        )
    ).all()
    return [
        {
            "term": r.search_term,
            "conversions": float(r.conversions or 0),
            "cpa": float(safe_divide(Decimal(r.spend or 0), Decimal(r.conversions or 0))) if r.conversions else None,
            "conversion_value": float(r.conversion_value or 0),
        }
        for r in rows
    ]
