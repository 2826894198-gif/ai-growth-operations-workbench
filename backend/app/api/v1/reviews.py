"""Daily and weekly business review APIs."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_permission
from app.core.database import get_db
from app.models.review import ReviewFollowup, ReviewRun
from app.services.review_service import (
    build_campaign_breakdown,
    build_preview,
    build_trends,
    create_review,
    get_review,
    list_reviews,
    serialize_followup,
    serialize_review,
)

router = APIRouter()


class ReviewCreate(BaseModel):
    workspace_id: str = "ws_main"
    review_type: str = Field("DAILY", pattern="^(DAILY|WEEKLY|CUSTOM)$")
    days: Optional[int] = Field(None, ge=1, le=90)
    end_date: Optional[date] = None
    account_ids: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    created_by: str = "operator"


class FollowupCreate(BaseModel):
    workspace_id: str = "ws_main"
    title: str = Field(..., min_length=1, max_length=512)
    owner_id: Optional[str] = None
    due_date: Optional[date] = None


class FollowupUpdate(BaseModel):
    workspace_id: str = "ws_main"
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|DONE|CANCELLED)$")
    result: Optional[str] = None


@router.get("/preview", dependencies=[Depends(require_permission("READ"))])
async def preview(
    workspace_id: str = Query("ws_main"),
    review_type: str = Query("DAILY", pattern="^(DAILY|WEEKLY|CUSTOM)$"),
    days: Optional[int] = Query(None, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    account_ids: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    return await build_preview(
        db,
        workspace_id=workspace_id,
        review_type=review_type,
        days=days,
        end_date=end_date,
        account_ids=[item for item in account_ids.split(",") if item],
    )


@router.get("/trends", dependencies=[Depends(require_permission("READ"))])
async def trends(
    workspace_id: str = Query("ws_main"),
    days: int = Query(7, ge=1, le=30),
    account_ids: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    return await build_trends(
        db,
        workspace_id=workspace_id,
        days=days,
        account_ids=[item for item in account_ids.split(",") if item],
    )


@router.get("/campaigns", dependencies=[Depends(require_permission("READ"))])
async def campaigns(
    workspace_id: str = Query("ws_main"),
    review_type: str = Query("DAILY", pattern="^(DAILY|WEEKLY|CUSTOM)$"),
    days: Optional[int] = Query(None, ge=1, le=90),
    end_date: Optional[date] = Query(None),
    account_ids: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    return await build_campaign_breakdown(
        db,
        workspace_id=workspace_id,
        review_type=review_type,
        days=days,
        end_date=end_date,
        account_ids=[item for item in account_ids.split(",") if item],
    )


@router.get("", dependencies=[Depends(require_permission("READ"))])
async def reviews_list(
    workspace_id: str = Query("ws_main"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return [serialize_review(item) for item in await list_reviews(db, workspace_id=workspace_id, limit=limit)]


@router.post("", dependencies=[Depends(require_permission("ANALYZE"))])
async def reviews_create(data: ReviewCreate, db: AsyncSession = Depends(get_db)):
    review = await create_review(
        db,
        workspace_id=data.workspace_id,
        review_type=data.review_type,
        days=data.days,
        end_date=data.end_date,
        account_ids=data.account_ids,
        summary=data.summary,
        created_by=data.created_by,
    )
    await db.commit()
    await db.refresh(review)
    return serialize_review(review)


@router.get("/{review_id}", dependencies=[Depends(require_permission("READ"))])
async def reviews_detail(
    review_id: str,
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    review = await get_review(db, workspace_id=workspace_id, review_id=review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="review not found in workspace")
    return review


@router.post("/{review_id}/followups", dependencies=[Depends(require_permission("ANALYZE"))])
async def followup_create(review_id: str, data: FollowupCreate, db: AsyncSession = Depends(get_db)):
    review = (
        await db.execute(
            select(ReviewRun).where(ReviewRun.id == review_id, ReviewRun.workspace_id == data.workspace_id)
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="review not found in workspace")
    item = ReviewFollowup(
        review_id=review_id,
        workspace_id=data.workspace_id,
        title=data.title,
        owner_id=data.owner_id,
        due_date=data.due_date,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return serialize_followup(item)


@router.patch("/followups/{followup_id}", dependencies=[Depends(require_permission("ANALYZE"))])
async def followup_update(followup_id: str, data: FollowupUpdate, db: AsyncSession = Depends(get_db)):
    item = (
        await db.execute(
            select(ReviewFollowup).where(
                ReviewFollowup.id == followup_id,
                ReviewFollowup.workspace_id == data.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="followup not found in workspace")
    item.status = data.status
    item.result = data.result
    await db.commit()
    await db.refresh(item)
    return serialize_followup(item)
