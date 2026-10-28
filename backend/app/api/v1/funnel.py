from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.ad_performance import MetaActionDaily

router = APIRouter()


@router.get("/overview")
async def funnel_overview(
    days: int = Query(7),
    entity_type: str = Query("AD"),
    entity_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    start = date.today() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(MetaActionDaily.action_type, func.sum(MetaActionDaily.action_count).label("count"))
            .where(MetaActionDaily.entity_type == entity_type, MetaActionDaily.date >= start)
            .group_by(MetaActionDaily.action_type)
        )
    ).all()
    counts = {str(r.action_type): float(r.count or 0) for r in rows}
    link_clicks = counts.get("link_click")
    lpv = counts.get("landing_page_view")
    atc = counts.get("add_to_cart")
    checkout = counts.get("initiate_checkout")
    purchase = counts.get("purchase")
    stages = []
    for label, value, prev in (
        ("CLICK", link_clicks, None),
        ("LANDING_PAGE", lpv, link_clicks),
        ("ADD_TO_CART", atc, lpv),
        ("CHECKOUT", checkout, atc),
        ("PURCHASE", purchase, checkout),
    ):
        stages.append(
            {
                "stage": label,
                "volume": value,
                "step_conversion": round(value / prev, 4) if value is not None and prev else None,
                "baseline": None,
                "available": value is not None,
            }
        )
    diagnosis = {"primary_problem": "CHECKOUT_TO_PURCHASE" if checkout and purchase and purchase / checkout < 0.4 else None, "source": "RULE"}
    return {"stages": stages, "diagnosis": diagnosis}


@router.get("/landing-pages")
async def landing_pages(days: int = Query(7), db: AsyncSession = Depends(get_db)):
    return {"landing_pages": [], "note": "landing-page data requires site analytics source"}


@router.get("/devices")
async def devices(days: int = Query(7), db: AsyncSession = Depends(get_db)):
    return {"devices": [], "note": "device breakdown requires breakdown data source"}


@router.get("/geography")
async def geography(days: int = Query(7), db: AsyncSession = Depends(get_db)):
    return {"geography": [], "note": "geo breakdown requires breakdown data source"}
