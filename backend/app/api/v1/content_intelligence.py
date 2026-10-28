"""Content intelligence API (E166-E167)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.social import ContentAsset
from app.services.social.content_service import (
    content_detail,
    create_manual_promotion_link,
    delete_promotion_link,
    publication_detail,
)

router = APIRouter()


class PromotionLinkCreate(BaseModel):
    paid_platform: str = "META_ADS"
    paid_account_id: Optional[str] = None
    creative_id: Optional[str] = None
    ad_id: Optional[str] = None
    ad_group_id: Optional[str] = None
    campaign_id: Optional[str] = None
    promotion_type: str = "PAID_BOOST"
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    mapping_confidence: float = 0.8
    actor: str = "operator"


@router.get("")
async def list_content(
    workspace_id: str = Query(...),
    account_id: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(ContentAsset).order_by(ContentAsset.created_at.desc())
    if workspace_id:
        query = query.where(ContentAsset.workspace_id == workspace_id)
    rows = (await db.execute(query.offset(offset).limit(limit))).scalars().all()
    return {
        "total": len(rows),
        "rows": [
            {
                "id": str(r.id),
                "title": r.title,
                "asset_type": r.asset_type,
                "thumbnail_uri": r.thumbnail_uri,
                "duration": r.duration,
                "asset_hash": r.asset_hash,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/assets/{asset_id}")
async def get_content_asset(asset_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await content_detail(db, asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/publications/{publication_id}")
async def get_publication(publication_id: str, days: int = Query(30, ge=1, le=180), db: AsyncSession = Depends(get_db)):
    try:
        return await publication_detail(db, publication_id, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/publications/{publication_id}/organic")
async def publication_organic(publication_id: str, db: AsyncSession = Depends(get_db)):
    detail = await publication_detail(db, publication_id)
    return {"organic": detail["organic"], "timeline": detail["timeline"]}


@router.get("/publications/{publication_id}/paid")
async def publication_paid(publication_id: str, db: AsyncSession = Depends(get_db)):
    detail = await publication_detail(db, publication_id)
    return {"paid": detail["paid"], "promotions": detail["promotions"]}


@router.get("/publications/{publication_id}/promotions")
async def publication_promotions(publication_id: str, db: AsyncSession = Depends(get_db)):
    detail = await publication_detail(db, publication_id)
    return {"promotions": detail["promotions"], "paid": detail["paid"]}


@router.post("/publications/{publication_id}/promotion-links")
async def create_link(publication_id: str, data: PromotionLinkCreate, db: AsyncSession = Depends(get_db)):
    try:
        link = await create_manual_promotion_link(
            db,
            publication_id=publication_id,
            payload=data.model_dump(exclude_none=True),
            actor=data.actor,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(link.id), "mapping_source": "MANUAL", "status": "ACTIVE"}


@router.delete("/publications/{publication_id}/promotion-links/{link_id}")
async def remove_link(publication_id: str, link_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await delete_promotion_link(db, link_id, "operator")
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.get("/promotion-links")
async def list_promotion_links(limit: int = Query(200, ge=1, le=1000), db: AsyncSession = Depends(get_db)):
    from app.models.social import ContentPromotionLink

    rows = (await db.execute(select(ContentPromotionLink).order_by(ContentPromotionLink.created_at.desc()).limit(limit))).scalars().all()
    return [
        {
            "id": str(r.id),
            "content_asset_id": r.content_asset_id,
            "publication_id": r.publication_id,
            "paid_platform": r.paid_platform,
            "creative_id": r.creative_id,
            "ad_id": r.ad_id,
            "campaign_id": r.campaign_id,
            "mapping_source": r.mapping_source,
            "mapping_confidence": r.mapping_confidence,
            "status": r.status,
        }
        for r in rows
    ]
