"""Unified account API (E164)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.social import AccountGroup, Brand, ConnectedAccount
from app.services.social.account_service import account_capabilities, account_overview
from app.services.social.connection_service import refresh_capabilities

router = APIRouter()


class CapabilityRefresh(BaseModel):
    actor: str = "operator"


def _account_dict(account: ConnectedAccount, *, brand_name: Optional[str] = None, account_group_name: Optional[str] = None) -> dict:
    metadata = account.meta if isinstance(account.meta, dict) else {}
    account_scope = str(metadata.get("account_scope") or metadata.get("owner_scope") or "").upper()
    if account_scope not in {"COMPANY", "EMPLOYEE", "UNASSIGNED"}:
        account_scope = None
    safe_metadata = {
        "account_scope": account_scope,
        "owner_label": str(metadata.get("owner_label"))[:128] if metadata.get("owner_label") else None,
        "channel_role": str(metadata.get("channel_role"))[:128] if metadata.get("channel_role") else None,
    }
    return {
        "id": str(account.id),
        "workspace_id": account.workspace_id,
        "brand_id": account.brand_id,
        "brand_name": brand_name,
        "account_group_id": account.account_group_id,
        "account_group_name": account_group_name,
        "connection_id": account.connection_id,
        "provider": account.provider,
        "platform": account.platform,
        "account_type": account.account_type,
        "external_account_id": account.external_account_id,
        "username": account.username,
        "display_name": account.display_name,
        "avatar_url": account.avatar_url,
        "country": account.country,
        "timezone": account.timezone,
        "status": account.status,
        "health_status": account.health_status,
        "is_primary": account.is_primary,
        "is_test": account.is_test,
        **safe_metadata,
        "last_profile_sync_at": account.last_profile_sync_at.isoformat() if account.last_profile_sync_at else None,
        "last_content_sync_at": account.last_content_sync_at.isoformat() if account.last_content_sync_at else None,
        "last_analytics_sync_at": account.last_analytics_sync_at.isoformat() if account.last_analytics_sync_at else None,
    }


async def _account_dicts(db: AsyncSession, accounts: list[ConnectedAccount]) -> list[dict]:
    brand_ids = {str(account.brand_id) for account in accounts if account.brand_id}
    group_ids = {str(account.account_group_id) for account in accounts if account.account_group_id}
    brands = {}
    groups = {}
    if brand_ids:
        brands = {
            str(row.id): row.name
            for row in (await db.execute(select(Brand).where(Brand.id.in_(brand_ids)))).scalars().all()
        }
    if group_ids:
        groups = {
            str(row.id): row.name
            for row in (await db.execute(select(AccountGroup).where(AccountGroup.id.in_(group_ids)))).scalars().all()
        }
    return [
        _account_dict(
            account,
            brand_name=brands.get(str(account.brand_id)) if account.brand_id else None,
            account_group_name=groups.get(str(account.account_group_id)) if account.account_group_id else None,
        )
        for account in accounts
    ]


async def _get_account(db: AsyncSession, account_id: str, workspace_id: str = "ws_main") -> ConnectedAccount:
    account = (
        await db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.id == account_id,
                ConnectedAccount.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    return account


@router.get("")
async def list_accounts(
    workspace_id: str = Query(...),
    platform: Optional[str] = Query(None),
    brand_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    query = select(ConnectedAccount).where(ConnectedAccount.workspace_id == workspace_id)
    if platform:
        query = query.where(ConnectedAccount.platform == platform.upper())
    if brand_id:
        query = query.where(ConnectedAccount.brand_id == brand_id)
    if status:
        query = query.where(ConnectedAccount.status == status)
    accounts = list((await db.execute(query.order_by(ConnectedAccount.created_at.asc()).limit(limit))).scalars().all())
    return await _account_dicts(db, accounts)


@router.get("/{account_id}")
async def get_account(
    account_id: str,
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    return (await _account_dicts(db, [await _get_account(db, account_id, workspace_id)]))[0]


@router.get("/{account_id}/overview")
async def account_overview_endpoint(
    account_id: str,
    days: int = Query(30, ge=1, le=180),
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_account(db, account_id, workspace_id)
    return await account_overview(db, account, days=days)


@router.get("/{account_id}/content")
async def account_content(
    account_id: str,
    days: int = Query(30, ge=1, le=180),
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    from app.models.social import ContentPublication
    from app.services.social.content_service import publication_detail

    await _get_account(db, account_id, workspace_id)
    publications = (
        await db.execute(
            select(ContentPublication)
            .where(ContentPublication.account_id == account_id)
            .order_by(ContentPublication.published_at.desc())
            .limit(100)
        )
    ).scalars().all()
    rows = []
    for publication in publications:
        detail = await publication_detail(db, str(publication.id), days=days)
        rows.append(
            {
                "id": str(publication.id),
                "asset_id": publication.content_asset_id,
                "platform": publication.platform,
                "content_type": publication.content_type,
                "caption": publication.caption,
                "published_at": publication.published_at.isoformat() if publication.published_at else None,
                "organic_views": detail["organic"]["views"],
                "reach": detail["organic"]["reach"],
                "likes": detail["organic"]["likes"],
                "comments": detail["organic"]["comments"],
                "shares": detail["organic"]["shares"],
                "saves": detail["organic"]["saves"],
                "watch_time": detail["organic"]["watch_time"],
                "average_watch_time": detail["organic"]["average_watch_time"],
                "completion_rate": detail["organic"]["completion_rate"],
                "skip_rate": detail["organic"]["skip_rate"],
                "profile_visits": detail["organic"]["profile_visits"],
                "follows": detail["organic"]["follows"],
                "paid_spend": detail["paid"]["spend"],
                "paid_revenue": detail["paid"]["revenue"],
                "paid_roas": detail["paid"]["roas"],
            }
        )
    view_values = [float(row["organic_views"]) for row in rows if row["organic_views"] is not None]
    interaction_values = [
        float(row[key])
        for row in rows
        for key in ("likes", "comments", "shares", "saves")
        if row[key] is not None
    ]
    follow_values = [float(row["follows"]) for row in rows if row["follows"] is not None]
    total_views = sum(view_values) if view_values else None
    total_interactions = sum(interaction_values) if interaction_values else None
    return {
        "account_id": account_id,
        "days": days,
        "rows": rows,
        "total": len(rows),
        "summary": {
            "views": total_views,
            "interactions": total_interactions,
            "average_views": round(total_views / len(view_values), 2) if view_values else None,
            "follows": sum(follow_values) if follow_values else None,
            "paid_spend": round(sum(float(row["paid_spend"] or 0) for row in rows), 2),
        },
        "caveat": "metrics use the selected observation window; publication list contains the latest 100 posts",
    }


@router.get("/{account_id}/analytics")
async def account_analytics(
    account_id: str,
    days: int = Query(30, ge=1, le=180),
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    from app.services.social.content_service import organic_series

    await _get_account(db, account_id, workspace_id)
    return {"series": await organic_series(db, account_ids=[account_id], days=days)}


@router.get("/{account_id}/capabilities")
async def get_account_capabilities(
    account_id: str,
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    await _get_account(db, account_id, workspace_id)
    return await account_capabilities(db, account_id)


@router.post("/{account_id}/refresh-capabilities")
async def refresh_account_capabilities(
    account_id: str,
    data: CapabilityRefresh = None,
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_account(db, account_id, workspace_id)
    count = await refresh_capabilities(db, account, data.actor if data else "operator")
    await db.commit()
    return {"account_id": account_id, "capabilities_refreshed": count, "capabilities": await account_capabilities(db, account_id)}


@router.get("/{account_id}/health")
async def account_health(
    account_id: str,
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    from app.services.account_health_service import evaluate_account

    account = await _get_account(db, account_id, workspace_id)
    return await evaluate_account(db, account)
