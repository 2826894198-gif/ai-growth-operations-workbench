"""Content pipeline: assets, publications, organic metrics, promotion mapping (E49-E72)."""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.social.factory import get_social_provider
from app.integrations.social.mock import MockSocialProvider
from app.models.ad_performance import AdPerformanceDaily
from app.models.social import (
    ConnectedAccount,
    ContentAsset,
    ContentPerformanceSnapshot,
    ContentPromotionLink,
    ContentPublication,
    FactContentPerformanceDaily,
)
from app.services.social.connection_service import audit
from app.services.social.scope_service import resolve_accounts


async def _upsert_asset(db: AsyncSession, workspace_id: str, brand_id: Optional[str], content) -> ContentAsset:
    if content.asset_hash:
        existing = (
            await db.execute(
                select(ContentAsset).where(
                    ContentAsset.workspace_id == workspace_id,
                    ContentAsset.asset_hash == content.asset_hash,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    title = content.caption or content.external_post_id
    asset = ContentAsset(
        workspace_id=workspace_id,
        brand_id=brand_id,
        asset_type=content.content_type,
        title=title[:500],
        internal_name=f"Asset {content.external_post_id}",
        thumbnail_uri=content.thumbnail_uri,
        asset_hash=content.asset_hash,
        duration=content.duration,
        created_at_source=content.published_at,
        metadata={"source_post_id": content.external_post_id},
    )
    db.add(asset)
    await db.flush()
    return asset


async def _upsert_publication(
    db: AsyncSession,
    *,
    asset: ContentAsset,
    account: ConnectedAccount,
    content,
) -> ContentPublication:
    existing = (
        await db.execute(
            select(ContentPublication).where(
                ContentPublication.provider == account.provider,
                ContentPublication.external_post_id == content.external_post_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.content_asset_id = str(asset.id)
        existing.account_id = str(account.id)
        existing.caption = content.caption
        existing.published_at = content.published_at
        existing.public_url = content.public_url
        existing.provider_status = "PUBLISHED"
        return existing
    publication = ContentPublication(
        content_asset_id=str(asset.id),
        account_id=str(account.id),
        provider=account.provider,
        platform=account.platform,
        external_post_id=content.external_post_id,
        external_media_id=content.external_media_id,
        content_type=content.content_type,
        caption=content.caption,
        published_at=content.published_at,
        public_url=content.public_url,
        provider_status="PUBLISHED",
    )
    db.add(publication)
    await db.flush()
    return publication


async def ingest_content_metrics(
    db: AsyncSession,
    *,
    account: ConnectedAccount,
    publication: ContentPublication,
    metrics_list,
) -> int:
    created = 0
    for metrics in metrics_list:
        observed = metrics.observed_at
        day = observed.date().isoformat()
        snapshot = (
            await db.execute(
                select(ContentPerformanceSnapshot).where(
                    ContentPerformanceSnapshot.publication_id == str(publication.id),
                    ContentPerformanceSnapshot.observed_at == observed,
                )
            )
        ).scalar_one_or_none()
        if snapshot is None:
            db.add(
                ContentPerformanceSnapshot(
                    publication_id=str(publication.id),
                    observed_at=observed,
                    views=metrics.views,
                    reach=metrics.reach,
                    likes=metrics.likes,
                    comments=metrics.comments,
                    shares=metrics.shares,
                    saves=metrics.saves,
                    watch_time=metrics.watch_time,
                    average_watch_time=metrics.average_watch_time,
                    completion_rate=metrics.completion_rate,
                    skip_rate=metrics.skip_rate,
                    profile_visits=metrics.profile_visits,
                    follows=metrics.follows,
                    provider_native_metrics=metrics.provider_native,
                    source="API",
                )
            )
            created += 1
        fact = (
            await db.execute(
                select(FactContentPerformanceDaily).where(
                    FactContentPerformanceDaily.publication_id == str(publication.id),
                    FactContentPerformanceDaily.date == day,
                )
            )
        ).scalar_one_or_none()
        if fact is None:
            db.add(
                FactContentPerformanceDaily(
                    workspace_id=account.workspace_id,
                    account_id=str(account.id),
                    content_asset_id=publication.content_asset_id,
                    publication_id=str(publication.id),
                    date=day,
                    views=metrics.views,
                    reach=metrics.reach,
                    likes=metrics.likes,
                    comments=metrics.comments,
                    shares=metrics.shares,
                    saves=metrics.saves,
                    watch_time=metrics.watch_time,
                    follows=metrics.follows,
                    provider_native_metrics=metrics.provider_native,
                )
            )
            created += 1
    await db.flush()
    return created


async def sync_account_content(db: AsyncSession, account: ConnectedAccount, *, actor: str, days: int = 30) -> Dict[str, Any]:
    provider = get_social_provider(account.platform)
    content_items = await provider.list_content(account.external_account_id)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    publications = 0
    snapshots = 0
    for item in content_items:
        asset = await _upsert_asset(db, account.workspace_id, account.brand_id, item)
        publication = await _upsert_publication(db, asset=asset, account=account, content=item)
        publications += 1
        metrics = await provider.get_content_metrics(account.external_account_id, item.external_post_id, start, end)
        snapshots += await ingest_content_metrics(db, account=account, publication=publication, metrics_list=metrics)
    account.last_content_sync_at = datetime.now(timezone.utc)
    account.last_analytics_sync_at = datetime.now(timezone.utc)
    await db.flush()
    return {"account_id": str(account.id), "publications": publications, "snapshots": snapshots}


async def sync_content(db: AsyncSession, account_ids: List[str], *, actor: str, days: int = 30) -> Dict[str, Any]:
    results = []
    for account_id in account_ids:
        account = (
            await db.execute(select(ConnectedAccount).where(ConnectedAccount.id == account_id, ConnectedAccount.status == "LINKED"))
        ).scalar_one_or_none()
        if account is None:
            continue
        result = await sync_account_content(db, account, actor=actor, days=days)
        results.append(result)
    return {"results": results, "total_publications": sum(r["publications"] for r in results)}


async def auto_map_promotions(db: AsyncSession, *, actor: str = "system") -> int:
    """Create promotion links from provider-native creative relationships (E59)."""
    provider = MockSocialProvider(platform="META")
    created = 0
    publications = (await db.execute(select(ContentPublication))).scalars().all()
    creative_map = {}
    for platform_creatives in provider.store.get("paid_creatives", {}).values():
        for creative in platform_creatives:
            creative_map[creative["media_id"]] = creative
    for publication in publications:
        if publication.external_media_id not in creative_map:
            continue
        creative = creative_map[publication.external_media_id]
        account = (
            await db.execute(select(ConnectedAccount).where(ConnectedAccount.id == publication.account_id))
        ).scalar_one_or_none()
        existing = (
            await db.execute(
                select(ContentPromotionLink).where(
                    ContentPromotionLink.publication_id == str(publication.id),
                    ContentPromotionLink.creative_id == creative["creative_id"],
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(
            ContentPromotionLink(
                workspace_id=account.workspace_id if account else None,
                content_asset_id=publication.content_asset_id,
                publication_id=str(publication.id),
                paid_platform="META_ADS" if creative.get("campaign_id", "").startswith("camp_") else "GOOGLE_ADS",
                paid_account_id=None,
                creative_id=creative["creative_id"],
                ad_id=creative.get("ad_id"),
                campaign_id=creative.get("campaign_id"),
                promotion_type="PAID_BOOST",
                started_at=publication.published_at + timedelta(days=1),
                mapping_confidence=0.92,
                mapping_source="CREATIVE_ID",
                status="ACTIVE",
                metadata={"media_id": publication.external_media_id},
            )
        )
        await audit(
            db,
            workspace_id=None,
            connection_id=None,
            account_id=str(publication.account_id),
            actor=actor,
            action="MAPPED",
            after={"publication_id": str(publication.id), "creative_id": creative["creative_id"], "source": "CREATIVE_ID"},
        )
        created += 1
    await db.flush()
    return created


async def create_manual_promotion_link(
    db: AsyncSession,
    *,
    publication_id: str,
    payload: Dict[str, Any],
    actor: str,
) -> ContentPromotionLink:
    publication = (await db.execute(select(ContentPublication).where(ContentPublication.id == publication_id))).scalar_one_or_none()
    if publication is None:
        raise ValueError("publication not found")
    account = (await db.execute(select(ConnectedAccount).where(ConnectedAccount.id == publication.account_id))).scalar_one_or_none()
    link = ContentPromotionLink(
        workspace_id=account.workspace_id if account else None,
        content_asset_id=publication.content_asset_id,
        publication_id=publication_id,
        paid_platform=payload.get("paid_platform", "META_ADS"),
        paid_account_id=payload.get("paid_account_id"),
        creative_id=payload.get("creative_id"),
        ad_id=payload.get("ad_id"),
        ad_group_id=payload.get("ad_group_id"),
        campaign_id=payload.get("campaign_id"),
        promotion_type=payload.get("promotion_type", "PAID_BOOST"),
        started_at=payload.get("started_at"),
        ended_at=payload.get("ended_at"),
        mapping_confidence=payload.get("mapping_confidence", 0.8),
        mapping_source="MANUAL",
        status="ACTIVE",
    )
    db.add(link)
    await db.flush()
    await audit(
        db,
        workspace_id=None,
        connection_id=None,
        account_id=str(publication.account_id),
        actor=actor,
        action="MAPPED",
        before=None,
        after={
            "publication_id": publication_id,
            "creative_id": payload.get("creative_id"),
            "ad_id": payload.get("ad_id"),
            "campaign_id": payload.get("campaign_id"),
            "source": "MANUAL",
        },
    )
    await db.flush()
    return link


async def delete_promotion_link(db: AsyncSession, link_id: str, actor: str) -> None:
    link = (await db.execute(select(ContentPromotionLink).where(ContentPromotionLink.id == link_id))).scalar_one_or_none()
    if link is None:
        raise ValueError("promotion link not found")
    await audit(
        db,
        workspace_id=None,
        connection_id=None,
        account_id=None,
        actor=actor,
        action="UNMAPPED",
        before={"link_id": link_id, "creative_id": link.creative_id, "ad_id": link.ad_id},
        after=None,
    )
    await db.delete(link)
    await db.flush()


async def paid_summary_for_links(db: AsyncSession, links: List[ContentPromotionLink], start: Optional[date], end: Optional[date]) -> Dict[str, Any]:
    if not links:
        return {
            "spend": 0,
            "impressions": 0,
            "clicks": 0,
            "purchases": 0,
            "revenue": 0,
            "roas": None,
            "cpa": None,
            "campaigns": [],
        }
    ad_ids = [link.ad_id for link in links if link.ad_id]
    creative_ids = [link.creative_id for link in links if link.creative_id]
    campaign_ids = [link.campaign_id for link in links if link.campaign_id]
    query = select(AdPerformanceDaily).where(AdPerformanceDaily.date >= (start or date(2020, 1, 1)))
    if end:
        query = query.where(AdPerformanceDaily.date <= end)
    if ad_ids:
        query = query.where(AdPerformanceDaily.external_entity_id.in_(ad_ids + creative_ids + campaign_ids))
    rows = (await db.execute(query)).scalars().all()
    spend = sum(float(r.spend_amount or 0) for r in rows)
    impressions = sum(float(r.impressions or 0) for r in rows)
    clicks = sum(float(r.link_clicks or r.clicks or 0) for r in rows)
    purchases = sum(float(r.platform_purchases or 0) for r in rows)
    revenue = sum(float(r.platform_purchase_value or 0) for r in rows)
    return {
        "spend": round(spend, 2),
        "impressions": round(impressions, 0),
        "clicks": round(clicks, 0),
        "purchases": round(purchases, 2),
        "revenue": round(revenue, 2),
        "roas": round(revenue / spend, 2) if spend else None,
        "cpa": round(spend / purchases, 2) if purchases else None,
        "campaigns": list({link.campaign_id for link in links if link.campaign_id}),
        "caveat": "paid metrics are observed after promotion start; not causal attribution",
    }


async def publication_detail(db: AsyncSession, publication_id: str, days: int = 30) -> Dict[str, Any]:
    publication = (await db.execute(select(ContentPublication).where(ContentPublication.id == publication_id))).scalar_one_or_none()
    if publication is None:
        raise ValueError("publication not found")
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    start_at = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    snapshots = (
        await db.execute(
            select(ContentPerformanceSnapshot)
            .where(
                ContentPerformanceSnapshot.publication_id == publication_id,
                ContentPerformanceSnapshot.observed_at >= start_at,
            )
            .order_by(ContentPerformanceSnapshot.observed_at)
        )
    ).scalars().all()
    links = (
        await db.execute(select(ContentPromotionLink).where(ContentPromotionLink.publication_id == publication_id))
    ).scalars().all()
    paid = await paid_summary_for_links(db, list(links), start, end)
    def sum_supported(metric: str, empty_value=0):
        if not snapshots:
            return empty_value
        values = [getattr(snapshot, metric) for snapshot in snapshots if getattr(snapshot, metric) is not None]
        return sum(float(value) for value in values) if values else None

    organic = {
        "views": sum_supported("views"),
        "reach": sum_supported("reach", None),
        "likes": sum_supported("likes"),
        "comments": sum_supported("comments"),
        "shares": sum_supported("shares"),
        "saves": sum_supported("saves"),
        "watch_time": sum_supported("watch_time"),
        "average_watch_time": (snapshots[-1].average_watch_time if snapshots else None),
        "completion_rate": (snapshots[-1].completion_rate if snapshots else None),
        "skip_rate": (snapshots[-1].skip_rate if snapshots else None),
        "profile_visits": sum_supported("profile_visits", None),
        "follows": sum_supported("follows", None),
        "caveat": "organic metrics are provider-reported event sums",
    }
    timeline = [
        {
            "date": s.observed_at.date().isoformat(),
            "views": s.views,
            "likes": s.likes,
            "comments": s.comments,
            "shares": s.shares,
            "saves": s.saves,
            "reach": s.reach,
            "watch_time": s.watch_time,
            "profile_visits": s.profile_visits,
            "follows": s.follows,
        }
        for s in snapshots
    ]
    return {
        "publication": {
            "id": str(publication.id),
            "asset_id": publication.content_asset_id,
            "account_id": publication.account_id,
            "platform": publication.platform,
            "external_post_id": publication.external_post_id,
            "content_type": publication.content_type,
            "caption": publication.caption,
            "published_at": publication.published_at.isoformat() if publication.published_at else None,
            "public_url": publication.public_url,
        },
        "organic": organic,
        "paid": paid,
        "business": {"orders": None, "net_revenue": None, "caveat": "requires attribution link (E65)"},
        "timeline": timeline,
        "promotions": [
            {
                "id": str(link.id),
                "paid_platform": link.paid_platform,
                "creative_id": link.creative_id,
                "ad_id": link.ad_id,
                "campaign_id": link.campaign_id,
                "mapping_source": link.mapping_source,
                "mapping_confidence": link.mapping_confidence,
                "status": link.status,
                "started_at": link.started_at.isoformat() if link.started_at else None,
            }
            for link in links
        ],
    }


async def content_detail(db: AsyncSession, asset_id: str) -> Dict[str, Any]:
    asset = (await db.execute(select(ContentAsset).where(ContentAsset.id == asset_id))).scalar_one_or_none()
    if asset is None:
        raise ValueError("content asset not found")
    publications = (
        await db.execute(select(ContentPublication).where(ContentPublication.content_asset_id == asset_id))
    ).scalars().all()
    details = [await publication_detail(db, str(p.id)) for p in publications]

    def sum_publication_metric(metric: str):
        values = [detail["organic"][metric] for detail in details if detail["organic"].get(metric) is not None]
        return sum(values) if values else None

    organic_total = {
        "views": sum_publication_metric("views"),
        "likes": sum_publication_metric("likes"),
        "comments": sum_publication_metric("comments"),
        "shares": sum_publication_metric("shares"),
        "caveat": "across publications: sum of provider events, not deduplicated audience (E149)",
    }
    paid_total = {
        "spend": sum(d["paid"]["spend"] for d in details),
        "purchases": sum(d["paid"]["purchases"] for d in details),
        "revenue": sum(d["paid"]["revenue"] for d in details),
        "roas": round(sum(d["paid"]["revenue"] for d in details) / sum(d["paid"]["spend"] for d in details), 2)
        if sum(d["paid"]["spend"] for d in details)
        else None,
    }
    return {
        "asset": {
            "id": str(asset.id),
            "title": asset.title,
            "internal_name": asset.internal_name,
            "asset_type": asset.asset_type,
            "thumbnail_uri": asset.thumbnail_uri,
            "duration": asset.duration,
            "asset_hash": asset.asset_hash,
        },
        "publications": details,
        "organic_total": organic_total,
        "paid_total": paid_total,
        "lifecycle": _lifecycle(organic_total, paid_total),
        "caveat": "organic and paid are reported separately and never mixed into one total (E64)",
    }


def _lifecycle(organic: Dict[str, Any], paid: Dict[str, Any]) -> str:
    organic_views = organic.get("views") or 0
    paid_spend = paid.get("spend") or 0
    if paid_spend > 0 and paid.get("roas"):
        return "SCALING" if paid["roas"] >= 1.2 else "PAID_TEST"
    if organic_views > 20000:
        return "ORGANIC_WINNER"
    if organic_views > 5000:
        return "ORGANIC_TEST"
    return "PUBLISHED"


async def content_matrix(db: AsyncSession, *, workspace_id: str, account_ids: List[str], days: int = 30) -> Dict[str, Any]:
    """Content Matrix scatter data: organic percentile vs paid efficiency (E70)."""
    rows = []
    accounts = await resolve_accounts(db, workspace_id=workspace_id, account_ids=account_ids or None)
    scoped_account_ids = [str(account.id) for account in accounts]
    publications = (
        await db.execute(
            select(ContentPublication).where(ContentPublication.account_id.in_(scoped_account_ids))
        )
    ).scalars().all()
    for publication in publications:
        detail = await publication_detail(db, str(publication.id), days=days)
        organic_views = detail["organic"]["views"]
        paid_spend = detail["paid"]["spend"]
        paid_revenue = detail["paid"]["revenue"]
        rows.append(
            {
                "publication_id": str(publication.id),
                "asset_id": publication.content_asset_id,
                "account_id": publication.account_id,
                "platform": publication.platform,
                "caption": (publication.caption or "")[:80],
                "organic_views": organic_views,
                "paid_spend": paid_spend,
                "paid_revenue": paid_revenue,
                "paid_roas": round(paid_revenue / paid_spend, 2) if paid_spend else None,
                "thumbnail_uri": (publication.meta or {}).get("thumbnail_uri"),
            }
        )
    organic_values = sorted([r["organic_views"] for r in rows])
    for row in rows:
        row["organic_percentile"] = _percentile(row["organic_views"], organic_values)
    paid_values = sorted([r["paid_roas"] for r in rows if r["paid_roas"] is not None])
    for row in rows:
        row["paid_percentile"] = _percentile(row["paid_roas"], paid_values) if row["paid_roas"] is not None else 0
        row["quadrant"] = _quadrant(row["organic_percentile"], row["paid_percentile"])
    paid_comparable_count = sum(1 for row in rows if row["paid_roas"] is not None)
    matrix_status = "ready" if len(rows) >= 8 and paid_comparable_count >= 8 else "partial" if rows else "empty"
    return {
        "rows": rows,
        "mode": "percentile",
        "caveat": "percentile of provider-reported metrics within selected scope",
        "quality": {
            "status": matrix_status,
            "source": "ContentPublication + FactContentPerformanceDaily + AdPerformanceDaily",
            "sample_size": len(rows),
            "comparable_sample_size": paid_comparable_count,
            "caveat": "少于 8 条同时具备自然与付费结果的内容时，矩阵只保留表格复核。",
        },
        "scope": {"workspace_id": workspace_id, "days": days, "account_ids": scoped_account_ids},
    }


def _percentile(value: Any, sorted_values: List[Any]) -> float:
    if not sorted_values:
        return 0.0
    position = sum(1 for v in sorted_values if v is not None and v <= (value or 0)) - 1
    return round(max(0.0, position / max(len(sorted_values) - 1, 1)) * 100, 1)


def _quadrant(organic_pct: float, paid_pct: float) -> str:
    if organic_pct >= 60 and paid_pct >= 60:
        return "SCALE_STAR"
    if organic_pct < 40 and paid_pct >= 60:
        return "HIDDEN_PAID_WINNER"
    if organic_pct >= 60 and paid_pct < 40:
        return "ATTENTION_WINNER"
    return "RETIRE_OR_REVIEW"


async def organic_series(db: AsyncSession, *, account_ids: List[str], days: int = 30) -> List[Dict[str, Any]]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    facts = (
        await db.execute(
            select(FactContentPerformanceDaily).where(
                FactContentPerformanceDaily.account_id.in_(account_ids) if account_ids else FactContentPerformanceDaily.id.isnot(None),
                FactContentPerformanceDaily.date >= start.isoformat(),
                FactContentPerformanceDaily.date <= end.isoformat(),
            )
        )
    ).scalars().all()
    by_date: Dict[str, Dict[str, float]] = {}
    for fact in facts:
        bucket = by_date.setdefault(fact.date, {"views": 0, "likes": 0, "comments": 0, "shares": 0, "follows": 0, "content_count": 0})
        bucket["views"] += float(fact.views or 0)
        bucket["likes"] += float(fact.likes or 0)
        bucket["comments"] += float(fact.comments or 0)
        bucket["shares"] += float(fact.shares or 0)
        bucket["follows"] += float(fact.follows or 0)
        bucket["content_count"] += 1
    return [{"date": day, **by_date[day]} for day in sorted(by_date)]
