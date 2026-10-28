"""Account analytics: portfolio, platform view, single account (E36-E48, E84-E91)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.social.factory import get_social_provider
from app.models.social import (
    AccountCapability,
    ConnectedAccount,
    ContentPromotionLink,
    ContentPublication,
)
from app.services.social.content_service import organic_series, paid_summary_for_links
from app.services.social.metric_catalog import aggregate_values
from app.services.social.scope_service import resolve_accounts


async def account_capabilities(db: AsyncSession, account_id: str) -> Dict[str, Any]:
    rows = (
        await db.execute(
            select(AccountCapability).where(AccountCapability.account_id == account_id).order_by(AccountCapability.capability_key)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "capability_key": r.capability_key,
                "supported": r.supported,
                "permission_granted": r.permission_granted,
                "last_verified_at": r.last_verified_at.isoformat() if r.last_verified_at else None,
                "limitations": r.limitations,
            }
            for r in rows
        ],
        "supported": [r.capability_key for r in rows if r.supported],
        "missing": [r.capability_key for r in rows if not r.supported],
    }


async def account_overview(db: AsyncSession, account: ConnectedAccount, days: int = 30) -> Dict[str, Any]:
    provider = get_social_provider(account.platform)
    profile = await provider.get_account_profile(account.external_account_id)
    capabilities = await account_capabilities(db, str(account.id))
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    account_metrics = await provider.get_account_metrics(account.external_account_id, start, end)
    followers_series = [
        {"date": row["date"], "followers": row.get("followers")}
        for row in account_metrics
        if row.get("followers") is not None
    ]
    organic = await organic_series(db, account_ids=[str(account.id)], days=days)
    publications = (
        await db.execute(
            select(ContentPublication)
            .where(ContentPublication.account_id == str(account.id))
            .order_by(ContentPublication.published_at.desc())
            .limit(10)
        )
    ).scalars().all()
    links = (
        await db.execute(select(ContentPromotionLink).where(ContentPromotionLink.paid_account_id == str(account.id)))
    ).scalars().all()
    paid = await paid_summary_for_links(db, list(links), start, end)
    top_content = []
    for publication in publications:
        from app.services.social.content_service import publication_detail

        detail = await publication_detail(db, str(publication.id), days=days)
        top_content.append(
            {
                "id": str(publication.id),
                "asset_id": publication.content_asset_id,
                "content_type": publication.content_type,
                "caption": publication.caption,
                "published_at": publication.published_at.isoformat() if publication.published_at else None,
                "views": detail["organic"]["views"],
                "likes": detail["organic"]["likes"],
                "comments": detail["organic"]["comments"],
                "paid_spend": detail["paid"]["spend"],
            }
        )
    total_views = sum(float(f.get("views") or 0) for f in organic)
    total_likes = sum(float(f.get("likes") or 0) for f in organic)
    total_comments = sum(float(f.get("comments") or 0) for f in organic)
    return {
        "header": {
            "id": str(account.id),
            "username": account.username or profile.username,
            "display_name": account.display_name or profile.display_name,
            "platform": account.platform,
            "account_type": account.account_type,
            "avatar_url": account.avatar_url or profile.avatar_url,
            "followers": profile.followers,
            "health_status": account.health_status,
            "connection_status": "HEALTHY",
            "last_sync": account.last_analytics_sync_at.isoformat() if account.last_analytics_sync_at else None,
        },
        "kpis": {
            "followers": {"value": profile.followers, "semantics": "NON_ADDITIVE"},
            "views": {"value": total_views, "semantics": "SEMI_ADDITIVE", "caveat": "平台报告事件合计，不代表去重用户。"},
            "engagements": {"value": total_likes + total_comments, "semantics": "ADDITIVE"},
            "content_count": {"value": len(publications), "semantics": "ADDITIVE"},
            "paid_spend": {"value": paid["spend"], "semantics": "ADDITIVE"},
            "paid_revenue": {"value": paid["revenue"], "semantics": "ADDITIVE"},
            "paid_roas": {"value": paid["roas"], "semantics": "RATE", "caveat": "平台归因 ROAS，与第一方收入回报分开。"},
        },
        "growth": followers_series,
        "organic_series": organic,
        "top_content": top_content,
        "paid": paid,
        "capabilities": capabilities,
        "caveats": [
            "指标按账号能力返回；不支持的指标不显示为零。",
            "自然表现与付费表现保持分离。",
        ],
    }


async def portfolio_overview(
    db: AsyncSession,
    *,
    workspace_id: str,
    platforms: Optional[List[str]] = None,
    account_ids: Optional[List[str]] = None,
    days: int = 30,
) -> Dict[str, Any]:
    accounts = await resolve_accounts(db, workspace_id=workspace_id, platforms=platforms, account_ids=account_ids)
    account_rows = []
    for account in accounts:
        overview = await account_overview(db, account, days=days)
        account_rows.append(
            {
                "id": str(account.id),
                "username": account.username,
                "display_name": account.display_name,
                "platform": account.platform,
                "avatar_url": account.avatar_url,
                "health_status": account.health_status,
                "followers": overview["header"]["followers"],
                "views": overview["kpis"]["views"]["value"],
                "engagements": overview["kpis"]["engagements"]["value"],
                "content_count": overview["kpis"]["content_count"]["value"],
                "paid_spend": overview["kpis"]["paid_spend"]["value"],
                "paid_revenue": overview["kpis"]["paid_revenue"]["value"],
                "paid_roas": overview["kpis"]["paid_roas"]["value"],
                "growth_series": overview["growth"],
            }
        )
    followers_values = [r["followers"] for r in account_rows if r["followers"] is not None]
    views_values = [r["views"] for r in account_rows if r["views"] is not None]
    spend_values = [r["paid_spend"] for r in account_rows if r["paid_spend"] is not None]
    revenue_values = [r["paid_revenue"] for r in account_rows if r["paid_revenue"] is not None]
    return {
        "scope": {
            "workspace_id": workspace_id,
            "platforms": [p.upper() for p in platforms] if platforms else None,
            "account_ids": account_ids,
            "accounts": len(accounts),
        },
        "kpis": {
            "published_content": aggregate_values([r["content_count"] for r in account_rows], {"aggregation_type": "ADDITIVE"}),
            "views": aggregate_values(views_values, {"aggregation_type": "SEMI_ADDITIVE"}, ),
            "engagements": aggregate_values([r["engagements"] for r in account_rows], {"aggregation_type": "ADDITIVE"}),
            "followers": aggregate_values(followers_values, {"aggregation_type": "NON_ADDITIVE"}),
            "paid_spend": aggregate_values(spend_values, {"aggregation_type": "ADDITIVE"}),
            "paid_revenue": aggregate_values(revenue_values, {"aggregation_type": "ADDITIVE"}),
        },
        "accounts": account_rows,
        "caveats": [
            "views are summed provider events, not deduplicated people；浏览量不代表去重用户。",
            "reach is never summed into a unique cross-platform audience；触达不汇总为跨平台唯一受众。",
        ],
    }


async def portfolio_content(db: AsyncSession, *, workspace_id: str, account_ids: List[str], days: int = 30) -> Dict[str, Any]:
    accounts = await resolve_accounts(db, workspace_id=workspace_id, account_ids=account_ids or None)
    scoped_account_ids = [str(account.id) for account in accounts]
    publications = (
        await db.execute(
            select(ContentPublication).where(
                ContentPublication.account_id.in_(scoped_account_ids)
            )
        )
    ).scalars().all()
    rows = []
    for publication in publications:
        from app.services.social.content_service import publication_detail

        detail = await publication_detail(db, str(publication.id), days=days)
        rows.append(
            {
                "id": str(publication.id),
                "asset_id": publication.content_asset_id,
                "account_id": publication.account_id,
                "platform": publication.platform,
                "content_type": publication.content_type,
                "caption": (publication.caption or "")[:100],
                "published_at": publication.published_at.isoformat() if publication.published_at else None,
                "organic_views": detail["organic"]["views"],
                "paid_spend": detail["paid"]["spend"],
                "paid_revenue": detail["paid"]["revenue"],
            }
        )
    rows.sort(key=lambda r: r["organic_views"], reverse=True)
    series = await organic_series(db, account_ids=scoped_account_ids, days=days)
    status = "ready" if rows and series else "partial" if rows or series else "empty"
    return {
        "rows": rows,
        "total": len(rows),
        "series": series,
        "quality": {
            "status": status,
            "source": "ContentPublication + FactContentPerformanceDaily",
            "sample_size": len(rows),
            "caveat": "自然指标为平台报告事件合计，不代表去重用户；付费结果独立呈现。",
        },
        "scope": {"workspace_id": workspace_id, "days": days, "account_ids": scoped_account_ids},
    }
