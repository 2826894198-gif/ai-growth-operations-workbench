"""Read models for persisted Instagram LIVE data.

The public shape deliberately mirrors the explicit DEMO read model so the UI
can render either source without confusing stored API data with fixture data.
Raw payload contents are never returned here; callers receive their opaque
references and normalized, availability-aware fields only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.instagram.contracts import InstagramMediaType, InstagramMetricLevel
from app.models.instagram import (
    InstagramAccountSnapshot,
    InstagramCapability,
    InstagramMediaSnapshot,
)
from app.models.social import ConnectedAccount, ContentPublication
from app.services.instagram.health import calculate_internal_growth_health
from app.services.instagram.metrics import (
    engagement_metrics,
    follower_growth_metrics,
    profile_link_tap_rate,
    replay_metrics,
    watch_ratio,
)
from app.services.instagram.rules import RuleContext, evaluate_instagram_rules


class InstagramLiveReadError(RuntimeError):
    """There is no persisted LIVE source for the requested workspace yet."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _source() -> Dict[str, object]:
    return {
        "mode": "LIVE",
        "is_live": True,
        "data_layer": "RAW",
        "api_version": settings.meta_graph_api_version,
        "label": "Live Instagram API data",
    }


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _account_type(value: object) -> str:
    return "CREATOR" if str(value).upper() == "INSTAGRAM_CREATOR" else "BUSINESS"


def _account_identity(
    account: ConnectedAccount, current: Optional[InstagramAccountSnapshot]
) -> Dict[str, object]:
    metadata = account.meta or {}
    metrics = current.metrics if current else {}
    return {
        "account_ref": str(account.id),
        "external_account_id": account.external_account_id,
        "username": account.username or "instagram_account",
        "display_name": account.display_name,
        "avatar_url": account.avatar_url,
        "followers_count": metrics.get("follower_count", metadata.get("followers_count")),
        "media_count": metadata.get("media_count"),
        "account_type": _account_type(account.account_type),
        "connected_at": _iso(account.created_at),
        "last_sync": _iso(account.last_analytics_sync_at),
        "timezone": account.timezone or "UTC",
        "source_mode": "LIVE",
        "data_layer": "RAW",
    }


def _account_snapshot(
    snapshot: Optional[InstagramAccountSnapshot], account: ConnectedAccount
) -> Dict[str, object]:
    if snapshot is None:
        return {
            "account_ref": str(account.id),
            "observed_at": None,
            "window_start": None,
            "window_end": None,
            "source_mode": "LIVE",
            "api_version": settings.meta_graph_api_version,
            "raw_payload_ref": None,
            "timezone": account.timezone or "UTC",
            "metrics": {},
            "metric_availability": {},
            "record_status": "EMPTY",
            "source_layer": "RAW",
        }
    return {
        "account_ref": str(account.id),
        "observed_at": _iso(snapshot.observed_at),
        "window_start": snapshot.window_start.isoformat(),
        "window_end": snapshot.window_end.isoformat(),
        "source_mode": snapshot.source_mode,
        "api_version": snapshot.api_version,
        "raw_payload_ref": f"raw:{snapshot.raw_payload_id}",
        "timezone": snapshot.timezone,
        "metrics": snapshot.metrics,
        "metric_availability": snapshot.metric_availability,
        "record_status": snapshot.record_status,
        "source_layer": snapshot.source_layer,
    }


def _media_snapshot(
    snapshot: InstagramMediaSnapshot, account: ConnectedAccount
) -> Dict[str, object]:
    return {
        "account_ref": str(account.id),
        "external_media_id": snapshot.external_media_id,
        "observed_at": _iso(snapshot.observed_at),
        "media_type": snapshot.media_type,
        "source_mode": snapshot.source_mode,
        "api_version": snapshot.api_version,
        "raw_payload_ref": f"raw:{snapshot.raw_payload_id}",
        "metrics": snapshot.metrics,
        "metric_availability": snapshot.metric_availability,
        "record_status": snapshot.record_status,
        "source_layer": snapshot.source_layer,
    }


async def _live_account(db: AsyncSession, workspace_id: str) -> ConnectedAccount:
    account = (
        (
            await db.execute(
                select(ConnectedAccount)
                .where(
                    ConnectedAccount.workspace_id == workspace_id,
                    ConnectedAccount.provider == "INSTAGRAM",
                    ConnectedAccount.status == "LINKED",
                )
                .order_by(
                    ConnectedAccount.last_analytics_sync_at.desc().nullslast(),
                    ConnectedAccount.created_at.desc(),
                )
            )
        )
        .scalars()
        .first()
    )
    if account is None:
        raise InstagramLiveReadError(
            "No linked Instagram LIVE account is available for this workspace"
        )
    return account


async def _account_snapshots(
    db: AsyncSession, account: ConnectedAccount
) -> list[InstagramAccountSnapshot]:
    return (
        (
            await db.execute(
                select(InstagramAccountSnapshot)
                .where(
                    InstagramAccountSnapshot.account_id == str(account.id),
                    InstagramAccountSnapshot.source_mode == "LIVE",
                )
                .order_by(InstagramAccountSnapshot.observed_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def _capabilities(db: AsyncSession, account: ConnectedAccount) -> list[Dict[str, object]]:
    rows = (
        (
            await db.execute(
                select(InstagramCapability)
                .where(InstagramCapability.account_id == str(account.id))
                .order_by(
                    InstagramCapability.metric_level,
                    InstagramCapability.media_type,
                    InstagramCapability.metric_key,
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "account_ref": str(account.id),
            "metric_key": row.metric_key,
            "metric_level": row.metric_level,
            "media_type": row.media_type,
            "scope_key": row.scope_key,
            "supported": row.supported,
            "permission_granted": row.permission_granted,
            "reason": row.reason,
            "provider_field": row.provider_field,
            "provider_version": row.provider_version,
            "last_checked_at": _iso(row.last_checked_at),
        }
        for row in rows
    ]


async def live_overview(db: AsyncSession, *, workspace_id: str, days: int) -> Dict[str, object]:
    account = await _live_account(db, workspace_id)
    snapshots = await _account_snapshots(db, account)
    if not snapshots:
        raise InstagramLiveReadError(
            "Instagram Live is connected but has no completed server-side sync yet"
        )
    requested = [
        item for item in snapshots if (item.window_end - item.window_start).days + 1 == days
    ]
    comparable = requested or snapshots
    current = comparable[0]
    previous = comparable[1] if len(comparable) > 1 else None
    engagement = engagement_metrics(current.metrics, current.metric_availability)
    growth = follower_growth_metrics(
        current.metrics,
        current.metric_availability,
        previous.metrics if previous else {},
        previous.metric_availability if previous else {},
    )
    link_rate = profile_link_tap_rate(current.metrics, current.metric_availability)
    media_count = (
        await db.execute(
            select(InstagramMediaSnapshot.external_media_id)
            .where(
                InstagramMediaSnapshot.account_id == str(account.id),
                InstagramMediaSnapshot.source_mode == "LIVE",
            )
            .distinct()
        )
    ).all()
    health = calculate_internal_growth_health(
        {
            "content_quality": None,
            "growth": None,
            "engagement": None,
            "audience_fit": None,
            "conversion_intent": None,
        },
        content_sample_size=len(media_count),
        account_snapshot_days=len({item.observed_at.date() for item in snapshots}),
        last_sync_at=account.last_analytics_sync_at,
        now=_now(),
    )
    caveats = [
        "Live Meta values are read-only and scoped to this linked professional account.",
        "Empty Insights responses remain null with an availability reason; they are never converted to zero.",
        "Health and content scores remain calibrating until the V1 sample thresholds are met.",
    ]
    if current.record_status != "COMPLETE":
        caveats.insert(
            0,
            "The latest account snapshot is partial; inspect capability reasons before comparison.",
        )
    return {
        "workspace_id": workspace_id,
        "requested_window_days": days,
        "available_windows": sorted(
            {(item.window_end - item.window_start).days + 1 for item in snapshots}
        ),
        "source": _source(),
        "account": _account_identity(account, current),
        "capabilities": await _capabilities(db, account),
        "raw": {
            "current_account_snapshot": _account_snapshot(current, account),
            "previous_account_snapshot": _account_snapshot(previous, account),
        },
        "derived": {
            **{key: value.as_dict() for key, value in engagement.items()},
            **{key: value.as_dict() for key, value in growth.items()},
            "profile_link_tap_rate": link_rate.as_dict(),
        },
        "health": health.as_dict(),
        "caveats": caveats,
    }


def _media_metadata(
    snapshot: InstagramMediaSnapshot,
    account: ConnectedAccount,
    publication: Optional[ContentPublication],
) -> Dict[str, object]:
    return {
        "account_ref": str(account.id),
        "external_media_id": snapshot.external_media_id,
        "media_type": snapshot.media_type,
        "published_at": _iso(publication.published_at if publication else snapshot.observed_at),
        "caption": publication.caption if publication else None,
        "permalink": publication.public_url if publication else None,
        "duration_seconds": None,
        "source_mode": "LIVE",
        "data_layer": "RAW",
    }


async def live_content(
    db: AsyncSession,
    *,
    workspace_id: str,
    media_type: Optional[str] = None,
) -> Dict[str, object]:
    account = await _live_account(db, workspace_id)
    snapshots = (
        (
            await db.execute(
                select(InstagramMediaSnapshot)
                .where(
                    InstagramMediaSnapshot.account_id == str(account.id),
                    InstagramMediaSnapshot.source_mode == "LIVE",
                )
                .order_by(InstagramMediaSnapshot.observed_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest: Dict[str, InstagramMediaSnapshot] = {}
    for snapshot in snapshots:
        latest.setdefault(snapshot.external_media_id, snapshot)
    rows = list(latest.values())
    if media_type:
        rows = [row for row in rows if row.media_type == media_type.upper()]

    publication_ids = [row.publication_id for row in rows if row.publication_id]
    publications = (
        (
            await db.execute(
                select(ContentPublication).where(ContentPublication.id.in_(publication_ids))
            )
        )
        .scalars()
        .all()
        if publication_ids
        else []
    )
    publication_by_id = {str(item.id): item for item in publications}
    response_rows = []
    for snapshot in rows:
        try:
            normalized_type = InstagramMediaType(snapshot.media_type)
        except ValueError:
            normalized_type = InstagramMediaType.VIDEO
        derived = engagement_metrics(
            snapshot.metrics,
            snapshot.metric_availability,
            metric_level=InstagramMetricLevel.MEDIA,
            media_type=normalized_type,
        )
        derived["profile_link_tap_rate"] = profile_link_tap_rate(
            snapshot.metrics, snapshot.metric_availability
        )
        if normalized_type is InstagramMediaType.REELS:
            derived["watch_ratio"] = watch_ratio(
                snapshot.metrics, snapshot.metric_availability, media_type=normalized_type
            )
            derived.update(
                replay_metrics(
                    snapshot.metrics, snapshot.metric_availability, media_type=normalized_type
                )
            )
        rules = evaluate_instagram_rules(
            RuleContext(
                subject_ref=snapshot.external_media_id,
                values={},
                availability={},
                confidence=0.0,
                evidence_refs=(f"raw:{snapshot.raw_payload_id}",),
            )
        )
        response_rows.append(
            {
                "media": _media_metadata(
                    snapshot, account, publication_by_id.get(str(snapshot.publication_id))
                ),
                "raw": _media_snapshot(snapshot, account),
                "derived": {key: value.as_dict() for key, value in derived.items()},
                "content_score": None,
                "content_score_status": "CALIBRATING",
                "rule_evaluations": [evaluation.as_dict() for evaluation in rules],
            }
        )
    return {
        "workspace_id": workspace_id,
        "source": _source(),
        "media_type": media_type.upper() if media_type else None,
        "rows": response_rows,
        "total": len(response_rows),
        "caveats": [
            "Content values are the latest persisted LIVE snapshots, not a fabricated baseline score.",
            "Paid, revenue, ROAS, interest and purchase attribution are intentionally absent.",
        ],
    }


async def live_capabilities(db: AsyncSession, *, workspace_id: str) -> Dict[str, object]:
    account = await _live_account(db, workspace_id)
    return {
        "workspace_id": workspace_id,
        "source": _source(),
        "items": await _capabilities(db, account),
    }


async def live_readiness(db: AsyncSession, *, workspace_id: str) -> Dict[str, object]:
    connections = (
        (
            await db.execute(
                select(ConnectedAccount)
                .where(
                    ConnectedAccount.workspace_id == workspace_id,
                    ConnectedAccount.provider == "INSTAGRAM",
                )
                .order_by(ConnectedAccount.last_analytics_sync_at.desc().nullslast())
            )
        )
        .scalars()
        .all()
    )
    return {
        "workspace_id": workspace_id,
        "mode": "LIVE" if not settings.instagram_demo_mode else "DEMO",
        "checks": {
            "demo_mode_disabled": not settings.instagram_demo_mode,
            "sync_enabled": settings.instagram_sync_enabled,
            "provider_mode_live": settings.social_provider_mode == "live",
            "oauth_mode": settings.instagram_oauth_mode,
            "redirect_uri_allowlisted": settings.instagram_oauth_redirect_uri
            in {
                item.strip()
                for item in settings.oauth_redirect_allowlist.split(",")
                if item.strip()
            },
        },
        "linked_accounts": [
            {
                "account_id": str(account.id),
                "status": account.status,
                "last_sync": _iso(account.last_analytics_sync_at),
            }
            for account in connections
        ],
        "note": "This readiness response contains configuration states only; it never includes a secret or token.",
    }
