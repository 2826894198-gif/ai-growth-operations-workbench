"""Server-side, read-only synchronization for Instagram Business Login.

The sync keeps Meta responses in the RAW layer, records each run, and carries
availability separately from values.  In particular, an empty Insights
response remains ``empty``/``null`` instead of becoming a synthetic zero.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.data_source import DataSource
from app.models.instagram import (
    InstagramAccountSnapshot,
    InstagramCapability,
    InstagramMediaSnapshot,
    InstagramSyncRun,
)
from app.models.raw import RawApiPayload
from app.models.social import ConnectedAccount, ConnectionAudit, ProviderConnection
from app.services.instagram.business_login import (
    InstagramBusinessLoginClient,
    InstagramBusinessLoginError,
)
from app.services.instagram.token_vault import InstagramTokenVaultError, load_access_token
from app.services.social.content_service import (
    _upsert_asset,
    _upsert_publication,
    ingest_content_metrics,
)

ACCOUNT_METRIC_KEYS = (
    "follower_count",
    "reach",
    "profile_views",
    "profile_links_taps",
    "views",
    "total_interactions",
    "accounts_engaged",
    "likes",
    "comments",
    "shares",
    "saved",
    "follows",
    "unfollows",
)
MEDIA_METRIC_KEYS = (
    "reach",
    "likes",
    "comments",
    "shares",
    "saved",
    "total_interactions",
    "views",
    "watch_time",
    "average_watch_time",
    "replays",
    "plays",
    "skip_rate",
)
MEDIA_METRIC_ALIASES = {
    "ig_reels_video_view_total_time": "watch_time",
    "ig_reels_avg_watch_time": "average_watch_time",
    "clips_replays_count": "replays",
    "ig_reels_aggregated_all_plays_count": "plays",
    "reels_skip_rate": "skip_rate",
}
SENSITIVE_KEY_PARTS = ("token", "secret", "authorization", "password", "code")


class InstagramLiveSyncError(RuntimeError):
    """A safe synchronization failure suitable for API and audit records."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _safe_payload(value: Any) -> Any:
    """Remove accidental credentials before persisting a provider response."""

    if isinstance(value, dict):
        return {
            str(key): "[redacted]"
            if any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS)
            else _safe_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_payload(item) for item in value]
    return value


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_dedupe(*parts: object) -> str:
    return f"instagram:{_stable_hash(list(map(str, parts)))}"


def _safe_error_payload(exc: BaseException) -> Dict[str, object]:
    if isinstance(exc, InstagramBusinessLoginError):
        return {
            "kind": "instagram_api_error",
            "http_status": exc.http_status,
            "api_code": exc.api_code,
        }
    if isinstance(exc, httpx.HTTPError):
        return {"kind": "network_error"}
    return {"kind": "sync_error"}


def _availability_for_error(exc: BaseException) -> str:
    if isinstance(exc, InstagramBusinessLoginError) and exc.api_code in {10, 200}:
        return "permission_denied"
    if isinstance(exc, InstagramBusinessLoginError) and exc.http_status == 403:
        return "permission_denied"
    return "unavailable"


def _record_status(availability: Dict[str, str]) -> str:
    reasons = set(availability.values())
    if reasons == {"available"}:
        return "COMPLETE"
    if reasons == {"empty"}:
        return "EMPTY"
    return "PARTIAL"


def _latest_value(values: object) -> object:
    if not isinstance(values, list) or not values:
        return None
    for item in reversed(values):
        if isinstance(item, dict) and "value" in item:
            return item["value"]
    return None


def _insight_values(payload: Dict[str, Any]) -> Dict[str, object]:
    """Normalize Meta's ``data -> values -> value`` envelope to field values."""

    values: Dict[str, object] = {}
    data = payload.get("data")
    if not isinstance(data, list):
        return values
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        value = _latest_value(item.get("values"))
        if value is not None:
            values[item["name"]] = value
    return values


def _account_metrics(
    profile: Dict[str, Any],
    insight_payload: Dict[str, Any],
    *,
    error: Optional[BaseException] = None,
) -> Tuple[Dict[str, Optional[float]], Dict[str, str]]:
    default_reason = _availability_for_error(error) if error else "empty"
    metrics = {key: None for key in ACCOUNT_METRIC_KEYS}
    availability = {key: default_reason for key in ACCOUNT_METRIC_KEYS}

    follower_count = _number(profile.get("followers_count"))
    if follower_count is not None:
        metrics["follower_count"] = follower_count
        availability["follower_count"] = "available"
    elif error is None:
        availability["follower_count"] = "unavailable"

    for source_name, value in _insight_values(insight_payload).items():
        if source_name == "follows_and_unfollows" and isinstance(value, dict):
            for source_key, target_key in (("follows", "follows"), ("unfollows", "unfollows")):
                numeric = _number(value.get(source_key))
                if numeric is not None:
                    metrics[target_key] = numeric
                    availability[target_key] = "available"
            continue
        if source_name not in metrics:
            continue
        numeric = _number(value)
        if numeric is not None:
            metrics[source_name] = numeric
            availability[source_name] = "available"
    return metrics, availability


def _media_metrics(
    media: Dict[str, Any],
    insight_payload: Dict[str, Any],
    *,
    error: Optional[BaseException] = None,
) -> Tuple[Dict[str, Optional[float]], Dict[str, str]]:
    default_reason = _availability_for_error(error) if error else "empty"
    metrics = {key: None for key in MEDIA_METRIC_KEYS}
    availability = {key: default_reason for key in MEDIA_METRIC_KEYS}

    for source_key, target_key in (("like_count", "likes"), ("comments_count", "comments")):
        numeric = _number(media.get(source_key))
        if numeric is not None:
            metrics[target_key] = numeric
            availability[target_key] = "available"

    for source_name, value in _insight_values(insight_payload).items():
        target_key = MEDIA_METRIC_ALIASES.get(source_name, source_name)
        if target_key not in metrics:
            continue
        numeric = _number(value)
        if numeric is not None:
            metrics[target_key] = numeric
            availability[target_key] = "available"
    return metrics, availability


def _parse_timestamp(value: object, *, fallback: datetime) -> datetime:
    if not isinstance(value, str) or not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _media_type(media: Dict[str, Any]) -> str:
    product_type = str(media.get("media_product_type") or "").upper()
    raw_type = str(media.get("media_type") or "").upper()
    if product_type == "REELS":
        return "REELS"
    if raw_type in {"IMAGE", "VIDEO", "CAROUSEL_ALBUM", "STORIES", "LIVE"}:
        return raw_type
    return "VIDEO"


def _account_period(days: int) -> Tuple[str, Optional[date], Optional[date]]:
    if days <= 7:
        return "week", None, None
    if days <= 31:
        return "days_28", None, None
    end = _now().date()
    return "total_over_range", end - timedelta(days=days - 1), end


async def _get_data_source(db: AsyncSession, account: ConnectedAccount) -> DataSource:
    row = (
        await db.execute(
            select(DataSource).where(
                DataSource.workspace_id == account.workspace_id,
                DataSource.provider == "INSTAGRAM",
                DataSource.external_account_id == account.external_account_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = DataSource(
            workspace_id=account.workspace_id,
            provider="INSTAGRAM",
            name=f"Instagram @{account.username or account.external_account_id}",
            external_account_id=account.external_account_id,
            external_account_name=account.display_name or account.username,
            status="RUNNING",
            api_version=settings.meta_graph_api_version,
            timezone=account.timezone or "UTC",
            credential_reference="server-managed",
            sync_enabled=True,
            meta={"auth_mode": "instagram_business_login", "read_only": True},
        )
        db.add(row)
        await db.flush()
    return row


async def _persist_raw(
    db: AsyncSession,
    *,
    data_source: DataSource,
    endpoint: str,
    payload: Dict[str, Any],
    sync_run_id: str,
    request_metadata: Dict[str, Any],
) -> RawApiPayload:
    safe_payload = _safe_payload(payload)
    row = RawApiPayload(
        provider="INSTAGRAM",
        data_source_id=str(data_source.id),
        endpoint=endpoint,
        api_version=settings.meta_graph_api_version,
        request_hash=_stable_hash(request_metadata),
        request_metadata={"mode": "LIVE", **request_metadata},
        payload=safe_payload,
        fetched_at=_now(),
        sync_job_id=sync_run_id,
    )
    db.add(row)
    await db.flush()
    return row


async def _upsert_capabilities(
    db: AsyncSession,
    *,
    account: ConnectedAccount,
    metric_level: str,
    metrics: Dict[str, Optional[float]],
    availability: Dict[str, str],
    media_type: Optional[str] = None,
) -> None:
    checked_at = _now()
    for metric_key in metrics:
        scope_key = f"{metric_level}:{media_type or '*'}:{metric_key}"
        row = (
            await db.execute(
                select(InstagramCapability).where(
                    InstagramCapability.account_id == str(account.id),
                    InstagramCapability.scope_key == scope_key,
                )
            )
        ).scalar_one_or_none()
        reason = availability[metric_key]
        if row is None:
            row = InstagramCapability(
                account_id=str(account.id),
                metric_key=metric_key,
                metric_level=metric_level,
                media_type=media_type,
                scope_key=scope_key,
                supported=reason != "unsupported",
                permission_granted=reason != "permission_denied",
                reason=reason,
                provider_field=metric_key,
                provider_version=settings.meta_graph_api_version,
                last_checked_at=checked_at,
                meta={"source": "live_sync"},
            )
            db.add(row)
        else:
            row.supported = reason != "unsupported"
            row.permission_granted = reason != "permission_denied"
            row.reason = reason
            row.provider_field = metric_key
            row.provider_version = settings.meta_graph_api_version
            row.last_checked_at = checked_at
    await db.flush()


async def _persist_media(
    db: AsyncSession,
    *,
    account: ConnectedAccount,
    data_source: DataSource,
    sync_run: InstagramSyncRun,
    media: Dict[str, Any],
    insight_payload: Dict[str, Any],
    error: Optional[BaseException],
    observed_at: datetime,
) -> Tuple[int, int]:
    media_id = str(media.get("id") or "")
    if not media_id:
        return 0, 0
    media_type = _media_type(media)
    metrics, availability = _media_metrics(media, insight_payload, error=error)
    raw = await _persist_raw(
        db,
        data_source=data_source,
        endpoint="GET /{ig_media_id}/insights",
        payload={"media": media, "insights": insight_payload},
        sync_run_id=str(sync_run.id),
        request_metadata={
            "kind": "media_insights",
            "media_type": media_type,
            "metric_keys": sorted(metrics),
        },
    )
    published_at = _parse_timestamp(media.get("timestamp"), fallback=observed_at)
    content = SimpleNamespace(
        asset_hash=f"instagram:{account.external_account_id}:{media_id}",
        caption=str(media.get("caption") or ""),
        external_post_id=media_id,
        external_media_id=media_id,
        thumbnail_uri=media.get("thumbnail_url"),
        duration=None,
        published_at=published_at,
        content_type=media_type,
        public_url=media.get("permalink"),
    )
    asset = await _upsert_asset(db, account.workspace_id, account.brand_id, content)
    publication = await _upsert_publication(db, asset=asset, account=account, content=content)
    snapshot = InstagramMediaSnapshot(
        account_id=str(account.id),
        publication_id=str(publication.id),
        external_media_id=media_id,
        observed_at=observed_at,
        media_type=media_type,
        source_layer="RAW",
        source_mode="LIVE",
        api_version=settings.meta_graph_api_version,
        raw_payload_id=str(raw.id),
        metrics=metrics,
        metric_availability=availability,
        record_status=_record_status(availability),
        dedupe_key=_snapshot_dedupe("media", account.id, media_id, observed_at.isoformat()),
    )
    db.add(snapshot)
    await db.flush()
    await ingest_content_metrics(
        db,
        account=account,
        publication=publication,
        metrics_list=[
            SimpleNamespace(
                observed_at=observed_at,
                views=metrics["views"],
                reach=metrics["reach"],
                likes=metrics["likes"],
                comments=metrics["comments"],
                shares=metrics["shares"],
                saves=metrics["saved"],
                watch_time=metrics["watch_time"],
                average_watch_time=metrics["average_watch_time"],
                completion_rate=None,
                skip_rate=metrics["skip_rate"],
                profile_visits=None,
                follows=None,
                provider_native={"metric_availability": availability},
            )
        ],
    )
    await _upsert_capabilities(
        db,
        account=account,
        metric_level="MEDIA",
        metrics=metrics,
        availability=availability,
        media_type=media_type,
    )
    return 1, 1


async def _connection_and_account(
    db: AsyncSession, *, workspace_id: str, connection_id: str
) -> Tuple[ProviderConnection, ConnectedAccount]:
    connection = (
        await db.execute(
            select(ProviderConnection).where(
                ProviderConnection.id == connection_id,
                ProviderConnection.workspace_id == workspace_id,
                ProviderConnection.provider == "INSTAGRAM",
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        raise InstagramLiveSyncError("Instagram connection was not found in this workspace")
    account = (
        await db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.connection_id == str(connection.id),
                ConnectedAccount.workspace_id == workspace_id,
                ConnectedAccount.provider == "INSTAGRAM",
                ConnectedAccount.status == "LINKED",
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise InstagramLiveSyncError("Instagram connection has no linked professional account")
    return connection, account


def _require_live_sync() -> None:
    if (
        settings.instagram_demo_mode
        or not settings.instagram_sync_enabled
        or settings.social_provider_mode != "live"
    ):
        raise InstagramLiveSyncError(
            "Instagram Live sync is disabled until deployment preflight passes"
        )


async def sync_instagram_connection(
    db: AsyncSession,
    *,
    workspace_id: str,
    connection_id: str,
    days: int = 28,
    actor: str = "operator",
    client: Optional[InstagramBusinessLoginClient] = None,
) -> Dict[str, Any]:
    """Synchronize one linked account using an encrypted server-side credential."""

    _require_live_sync()
    if not 7 <= days <= 90:
        raise InstagramLiveSyncError("Instagram sync window must be between 7 and 90 days")
    connection, account = await _connection_and_account(
        db, workspace_id=workspace_id, connection_id=connection_id
    )
    observed_at = _now()
    window_end = observed_at.date()
    window_start = window_end - timedelta(days=days - 1)
    period, since, until = _account_period(days)
    sync_run = InstagramSyncRun(
        workspace_id=workspace_id,
        account_id=str(account.id),
        run_type="FULL_READ",
        source_mode="LIVE",
        status="RUNNING",
        requested_window_start=window_start,
        requested_window_end=window_end,
        started_at=observed_at,
        meta={
            "api_version": settings.meta_graph_api_version,
            "window_days": days,
            "period": period,
        },
    )
    db.add(sync_run)
    await db.flush()
    db.add(
        ConnectionAudit(
            workspace_id=workspace_id,
            connection_id=str(connection.id),
            account_id=str(account.id),
            actor=actor,
            action="INSTAGRAM_SYNC_STARTED",
            after={"source_mode": "LIVE", "window_days": days, "sync_run_id": str(sync_run.id)},
        )
    )

    owns_client = client is None
    client = client or InstagramBusinessLoginClient()
    items_seen = 0
    items_written = 0
    raw_payloads_written = 0
    media_failures = 0
    account_insight_error: Optional[BaseException] = None
    try:
        access_token = await load_access_token(db, str(connection.id))
        profile = await client.get_profile(access_token=access_token)
        account.external_account_id = str(profile["user_id"])
        account.username = str(profile.get("username") or account.username or "")
        account.display_name = str(
            profile.get("name") or profile.get("username") or account.display_name or ""
        )
        account.avatar_url = profile.get("profile_picture_url") or account.avatar_url
        account.last_profile_sync_at = observed_at
        account.meta = {
            **(account.meta or {}),
            "followers_count": profile.get("followers_count"),
            "media_count": profile.get("media_count"),
            "oauth_source": "instagram_business_login",
        }
        data_source = await _get_data_source(db, account)

        try:
            account_insights = await client.get_account_insights(
                user_id=account.external_account_id,
                access_token=access_token,
                period=period,
                since=since,
                until=until,
            )
        except (InstagramBusinessLoginError, httpx.HTTPError) as exc:
            account_insight_error = exc
            account_insights = {"data": [], "request_error": _safe_error_payload(exc)}
        account_metrics, account_availability = _account_metrics(
            profile, account_insights, error=account_insight_error
        )
        account_raw = await _persist_raw(
            db,
            data_source=data_source,
            endpoint="GET /me + /{ig_user_id}/insights",
            payload={"profile": profile, "insights": account_insights},
            sync_run_id=str(sync_run.id),
            request_metadata={
                "kind": "account_profile_and_insights",
                "period": period,
                "window_days": days,
                "metric_keys": sorted(account_metrics),
            },
        )
        raw_payloads_written += 1
        db.add(
            InstagramAccountSnapshot(
                account_id=str(account.id),
                observed_at=observed_at,
                window_start=window_start,
                window_end=window_end,
                source_layer="RAW",
                source_mode="LIVE",
                api_version=settings.meta_graph_api_version,
                raw_payload_id=str(account_raw.id),
                timezone=account.timezone or "UTC",
                metrics=account_metrics,
                metric_availability=account_availability,
                record_status=_record_status(account_availability),
                dedupe_key=_snapshot_dedupe("account", account.id, observed_at.isoformat(), days),
            )
        )
        items_written += 1
        await _upsert_capabilities(
            db,
            account=account,
            metric_level="ACCOUNT",
            metrics=account_metrics,
            availability=account_availability,
        )

        media_payload = await client.get_media(
            user_id=account.external_account_id,
            access_token=access_token,
            limit=settings.instagram_sync_max_media,
        )
        media_items = [item for item in media_payload.get("data", []) if isinstance(item, dict)]
        items_seen = len(media_items) + 1
        await _persist_raw(
            db,
            data_source=data_source,
            endpoint="GET /{ig_user_id}/media",
            payload=media_payload,
            sync_run_id=str(sync_run.id),
            request_metadata={"kind": "media_list", "limit": settings.instagram_sync_max_media},
        )
        raw_payloads_written += 1

        for media in media_items:
            media_type = _media_type(media)
            media_error: Optional[BaseException] = None
            try:
                media_insights = await client.get_media_insights(
                    media_id=str(media["id"]),
                    media_type=media_type,
                    access_token=access_token,
                )
            except (InstagramBusinessLoginError, httpx.HTTPError) as exc:
                media_error = exc
                media_failures += 1
                media_insights = {"data": [], "request_error": _safe_error_payload(exc)}
            written, raw_count = await _persist_media(
                db,
                account=account,
                data_source=data_source,
                sync_run=sync_run,
                media=media,
                insight_payload=media_insights,
                error=media_error,
                observed_at=observed_at,
            )
            items_written += written
            raw_payloads_written += raw_count

        account.last_content_sync_at = observed_at
        account.last_analytics_sync_at = observed_at
        connection.last_validated_at = observed_at
        data_source.last_successful_sync_at = observed_at
        data_source.status = "DEGRADED" if account_insight_error or media_failures else "HEALTHY"
        connection.status = (
            "SCOPE_MISSING"
            if _availability_for_error(account_insight_error) == "permission_denied"
            else "DEGRADED"
            if account_insight_error or media_failures
            else "HEALTHY"
        )
        sync_run.status = (
            "PARTIAL_SUCCESS" if account_insight_error or media_failures else "SUCCESS"
        )
        sync_run.finished_at = _now()
        sync_run.items_seen = items_seen
        sync_run.items_written = items_written
        sync_run.raw_payloads_written = raw_payloads_written
        sync_run.meta = {
            **(sync_run.meta or {}),
            "media_page_truncated": bool(
                isinstance(media_payload.get("paging"), dict)
                and media_payload["paging"].get("next")
            ),
            "media_failures": media_failures,
            "account_insights_available": account_insight_error is None,
        }
        db.add(
            ConnectionAudit(
                workspace_id=workspace_id,
                connection_id=str(connection.id),
                account_id=str(account.id),
                actor=actor,
                action="INSTAGRAM_SYNC_COMPLETED",
                after={
                    "status": sync_run.status,
                    "items_seen": items_seen,
                    "items_written": items_written,
                    "raw_payloads_written": raw_payloads_written,
                    "media_failures": media_failures,
                },
            )
        )
        await db.flush()
        return {
            "sync_run_id": str(sync_run.id),
            "connection_id": str(connection.id),
            "account_id": str(account.id),
            "status": sync_run.status,
            "items_seen": items_seen,
            "items_written": items_written,
            "raw_payloads_written": raw_payloads_written,
            "media_failures": media_failures,
        }
    except (
        InstagramLiveSyncError,
        InstagramTokenVaultError,
        InstagramBusinessLoginError,
        httpx.HTTPError,
    ) as exc:
        if isinstance(exc, InstagramBusinessLoginError) and exc.api_code == 190:
            connection.status = "REAUTH_REQUIRED"
        else:
            connection.status = "DEGRADED"
        sync_run.status = "FAILED"
        sync_run.finished_at = _now()
        sync_run.error_code = "INSTAGRAM_SYNC_FAILED"
        sync_run.error_detail = str(exc)
        sync_run.items_seen = items_seen
        sync_run.items_written = items_written
        sync_run.raw_payloads_written = raw_payloads_written
        db.add(
            ConnectionAudit(
                workspace_id=workspace_id,
                connection_id=str(connection.id),
                account_id=str(account.id),
                actor=actor,
                action="INSTAGRAM_SYNC_FAILED",
                after={"error_code": sync_run.error_code, "status": sync_run.status},
            )
        )
        await db.flush()
        return {
            "sync_run_id": str(sync_run.id),
            "connection_id": str(connection.id),
            "account_id": str(account.id),
            "status": "FAILED",
            "safe_error": "Instagram data could not be synchronized. Check connection health and retry.",
        }
    finally:
        if owns_client:
            await client.aclose()
