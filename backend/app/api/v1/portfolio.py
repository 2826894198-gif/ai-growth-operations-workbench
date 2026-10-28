"""Portfolio API (E165)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.social.account_service import portfolio_content, portfolio_overview

router = APIRouter()


@router.get("/overview")
async def portfolio_overview_endpoint(
    workspace_id: str = Query(...),
    platforms: Optional[str] = Query(None, description="comma-separated"),
    account_ids: Optional[str] = Query(None, description="comma-separated"),
    days: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_overview(
        db,
        workspace_id=workspace_id,
        platforms=platforms.split(",") if platforms else None,
        account_ids=account_ids.split(",") if account_ids else None,
        days=days,
    )


@router.get("/accounts")
async def portfolio_accounts(
    workspace_id: str = Query(...),
    platform: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
):
    result = await portfolio_overview(db, workspace_id=workspace_id, platforms=[platform] if platform else None, days=days)
    return {"accounts": result["accounts"], "kpis": result["kpis"], "caveats": result["caveats"]}


@router.get("/content")
async def portfolio_content_endpoint(
    workspace_id: str = Query(...),
    account_ids: str = Query(""),
    days: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_content(db, workspace_id=workspace_id, account_ids=account_ids.split(",") if account_ids else [], days=days)


@router.get("/content-matrix")
async def portfolio_content_matrix(
    workspace_id: str = Query(...),
    account_ids: str = Query(""),
    days: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
):
    from app.services.social.content_service import content_matrix

    return await content_matrix(db, workspace_id=workspace_id, account_ids=account_ids.split(",") if account_ids else [], days=days)
