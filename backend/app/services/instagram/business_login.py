"""Official Instagram Business Login authorization-code flow.

This module intentionally follows Meta's Instagram Login flow rather than the
legacy Facebook Page-token flow.  It keeps the authorization code, app secret,
and access token on the server side and emits only non-sensitive connection
status to callers.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlencode, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.secrets import resolve_secret
from app.execution.timeutil import ensure_utc
from app.models.governance import CredentialRef, OAuthTransaction
from app.models.social import ConnectedAccount, ConnectionAudit, ProviderConnection
from app.services.instagram.token_vault import InstagramTokenVaultError, store_access_token

REQUIRED_SCOPES = {"instagram_business_basic", "instagram_business_manage_insights"}
PLACEHOLDERS = {"", "CHANGE_ME", "YOUR_APP_ID", "your-app-id", "<app-id>"}


class InstagramBusinessLoginError(RuntimeError):
    """Safe OAuth/API failure; messages never include a token, code, or secret."""

    def __init__(
        self,
        message: str,
        *,
        http_status: Optional[int] = None,
        api_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.api_code = api_code


@dataclass(frozen=True)
class OAuthCompletion:
    success: bool
    message: str
    connection_id: Optional[str] = None
    workspace_id: Optional[str] = None


def _hash_state(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def configured_scopes() -> list[str]:
    return [item.strip() for item in settings.instagram_required_scopes.split(",") if item.strip()]


def _parse_scopes(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _absolute_redirect_uri() -> str:
    redirect_uri = settings.instagram_oauth_redirect_uri.strip()
    parsed = urlparse(redirect_uri)
    if not redirect_uri or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InstagramBusinessLoginError(
            "Instagram OAuth redirect URI is not an absolute HTTP(S) URL"
        )
    allowed = {
        item.strip() for item in settings.oauth_redirect_allowlist.split(",") if item.strip()
    }
    if redirect_uri not in allowed:
        raise InstagramBusinessLoginError("Instagram OAuth redirect URI is not allowlisted")
    if settings.app_env in {"staging", "production"} and (
        parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1"}
    ):
        raise InstagramBusinessLoginError(
            "staging/production Instagram OAuth requires a public HTTPS callback"
        )
    return redirect_uri


def _require_live_configuration() -> tuple[str, str, str]:
    if settings.instagram_oauth_mode != "instagram_login":
        raise InstagramBusinessLoginError(
            "Instagram Business Login is not the configured OAuth mode"
        )
    if (
        settings.instagram_demo_mode
        or not settings.instagram_sync_enabled
        or settings.social_provider_mode != "live"
    ):
        raise InstagramBusinessLoginError(
            "Instagram Live mode is not enabled; keep DEMO active until deployment preflight passes"
        )
    if settings.instagram_app_id.strip() in PLACEHOLDERS:
        raise InstagramBusinessLoginError("Instagram App ID is not configured")
    app_secret = resolve_secret(settings.instagram_app_secret_reference)
    if not app_secret:
        raise InstagramBusinessLoginError("Instagram App Secret is not available to the server")
    scopes = set(configured_scopes())
    if REQUIRED_SCOPES - scopes:
        raise InstagramBusinessLoginError(
            "Instagram Live configuration is missing a required read-only scope"
        )
    return settings.instagram_app_id.strip(), app_secret, _absolute_redirect_uri()


def authorization_url(*, app_id: str, redirect_uri: str, state: str, scopes: list[str]) -> str:
    """Build Meta's current Business Login URL without unsupported PKCE fields."""
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(scopes),
        "state": state,
        "force_reauth": "true",
    }
    return f"{settings.instagram_oauth_base_url.rstrip('/')}/oauth/authorize?{urlencode(params)}"


def _first_data(body: Dict[str, Any]) -> Dict[str, Any]:
    data = body.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return body


def _safe_error(response: httpx.Response) -> InstagramBusinessLoginError:
    code = None
    error_type = None
    try:
        body = response.json()
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            code = error.get("code")
            error_type = error.get("type")
        elif isinstance(body, dict):
            code = body.get("code")
            error_type = body.get("error_type")
    except (ValueError, TypeError):
        pass
    details = ", ".join(str(value) for value in (code, error_type) if value is not None)
    suffix = f" ({details})" if details else ""
    api_code = int(code) if isinstance(code, (int, str)) and str(code).isdigit() else None
    return InstagramBusinessLoginError(
        f"Instagram API rejected the request with HTTP {response.status_code}{suffix}",
        http_status=response.status_code,
        api_code=api_code,
    )


class InstagramBusinessLoginClient:
    """Small HTTP client whose public methods never return credential data to APIs."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _json_object(response: httpx.Response, *, operation: str) -> Dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise InstagramBusinessLoginError(
                f"Instagram {operation} returned an invalid response"
            ) from exc
        if not isinstance(body, dict):
            raise InstagramBusinessLoginError(f"Instagram {operation} returned an invalid response")
        return body

    async def _graph_get(
        self,
        path: str,
        *,
        access_token: str,
        params: Optional[Dict[str, Any]] = None,
        operation: str,
    ) -> Dict[str, Any]:
        """Read Graph data without putting a credential in the request URL."""

        response = await self._client.get(
            f"{settings.instagram_graph_api_base_url.rstrip('/')}/{settings.meta_graph_api_version}{path}",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.is_error:
            raise _safe_error(response)
        return self._json_object(response, operation=operation)

    async def exchange_authorization_code(
        self, *, app_id: str, app_secret: str, redirect_uri: str, code: str
    ) -> Dict[str, Any]:
        response = await self._client.post(
            settings.instagram_token_exchange_url,
            files={
                "client_id": (None, app_id),
                "client_secret": (None, app_secret),
                "grant_type": (None, "authorization_code"),
                "redirect_uri": (None, redirect_uri),
                "code": (None, code),
            },
        )
        if response.is_error:
            raise _safe_error(response)
        body = self._json_object(response, operation="token exchange")
        result = _first_data(body)
        if not isinstance(result.get("access_token"), str) or not result["access_token"]:
            raise InstagramBusinessLoginError("Instagram token exchange returned no access token")
        return result

    async def exchange_long_lived_token(
        self, *, app_secret: str, short_lived_token: str
    ) -> Dict[str, Any]:
        response = await self._client.get(
            f"{settings.instagram_graph_api_base_url.rstrip('/')}/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": app_secret,
                "access_token": short_lived_token,
            },
        )
        if response.is_error:
            raise _safe_error(response)
        body = self._json_object(response, operation="long-lived token exchange")
        if not isinstance(body.get("access_token"), str):
            raise InstagramBusinessLoginError(
                "Instagram long-lived token exchange returned an invalid response"
            )
        return body

    async def refresh_long_lived_token(self, *, access_token: str) -> Dict[str, Any]:
        response = await self._client.get(
            f"{settings.instagram_graph_api_base_url.rstrip('/')}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": access_token},
        )
        if response.is_error:
            raise _safe_error(response)
        body = self._json_object(response, operation="token refresh")
        if not isinstance(body.get("access_token"), str):
            raise InstagramBusinessLoginError(
                "Instagram token refresh returned an invalid response"
            )
        return body

    async def get_profile(self, *, access_token: str) -> Dict[str, Any]:
        fields = "user_id,username,name,account_type,profile_picture_url,followers_count,follows_count,media_count"
        body = await self._graph_get(
            "/me",
            access_token=access_token,
            params={"fields": fields},
            operation="profile request",
        )
        result = _first_data(body)
        if not isinstance(result.get("user_id"), (str, int)):
            raise InstagramBusinessLoginError(
                "Instagram profile request returned no professional account ID"
            )
        return result

    async def get_media(self, *, user_id: str, access_token: str, limit: int) -> Dict[str, Any]:
        """Fetch bounded media metadata; insights are fetched separately per media object."""

        fields = ",".join(
            (
                "id",
                "caption",
                "media_type",
                "media_product_type",
                "permalink",
                "thumbnail_url",
                "timestamp",
                "like_count",
                "comments_count",
            )
        )
        return await self._graph_get(
            f"/{user_id}/media",
            access_token=access_token,
            params={"fields": fields, "limit": max(1, min(limit, 100))},
            operation="media list request",
        )

    async def get_account_insights(
        self,
        *,
        user_id: str,
        access_token: str,
        period: str,
        since: Optional[date] = None,
        until: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Fetch the documented read-only account-insights set for one period."""

        params: Dict[str, Any] = {
            "metric": ",".join(
                (
                    "reach",
                    "profile_views",
                    "profile_links_taps",
                    "views",
                    "total_interactions",
                    "accounts_engaged",
                    "likes",
                    "comments",
                    "shares",
                    "saves",
                    "follows_and_unfollows",
                )
            ),
            "period": period,
        }
        if since is not None:
            params["since"] = since.isoformat()
        if until is not None:
            params["until"] = until.isoformat()
        return await self._graph_get(
            f"/{user_id}/insights",
            access_token=access_token,
            params=params,
            operation="account insights request",
        )

    async def get_media_insights(
        self,
        *,
        media_id: str,
        media_type: str,
        access_token: str,
    ) -> Dict[str, Any]:
        """Fetch metric names compatible with the media type, without inventing zeros."""

        metric_names = ["reach", "likes", "comments", "shares", "saved", "total_interactions"]
        if media_type == "REELS":
            metric_names.extend(
                (
                    "views",
                    "ig_reels_video_view_total_time",
                    "ig_reels_avg_watch_time",
                    "clips_replays_count",
                    "ig_reels_aggregated_all_plays_count",
                    "reels_skip_rate",
                )
            )
        return await self._graph_get(
            f"/{media_id}/insights",
            access_token=access_token,
            params={"metric": ",".join(metric_names)},
            operation="media insights request",
        )


async def _audit(
    db: AsyncSession,
    *,
    workspace_id: str,
    connection_id: Optional[str],
    actor: str,
    action: str,
    after: Dict[str, Any],
) -> None:
    db.add(
        ConnectionAudit(
            workspace_id=workspace_id,
            connection_id=connection_id,
            account_id=None,
            actor=actor,
            action=action,
            after=after,
        )
    )


async def start_business_login(
    db: AsyncSession, *, workspace_id: str, actor: str = "operator"
) -> Dict[str, Any]:
    app_id, _app_secret, redirect_uri = _require_live_configuration()
    state = secrets.token_urlsafe(32)
    transaction = OAuthTransaction(
        workspace_id=workspace_id,
        provider="INSTAGRAM",
        state_hash=_hash_state(state),
        pkce_verifier_reference=None,
        redirect_uri=redirect_uri,
        initiated_by=actor,
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.instagram_oauth_state_ttl_minutes),
        status="PENDING",
    )
    db.add(transaction)
    await db.flush()
    scopes = configured_scopes()
    await _audit(
        db,
        workspace_id=workspace_id,
        connection_id=None,
        actor=actor,
        action="INSTAGRAM_OAUTH_STARTED",
        after={"provider": "INSTAGRAM", "scopes": scopes, "transaction_id": str(transaction.id)},
    )
    login_url = authorization_url(
        app_id=app_id, redirect_uri=redirect_uri, state=state, scopes=scopes
    )
    return {
        "provider": "INSTAGRAM",
        "authorization_url": login_url,
        "oauth_url": login_url,
        "redirect_uri": redirect_uri,
        "expires_at": transaction.expires_at.isoformat(),
        "scopes": scopes,
        "note": "Open the authorization URL in the account owner's browser. No token is returned to the client.",
    }


async def _lookup_pending_transaction(db: AsyncSession, state: str) -> Optional[OAuthTransaction]:
    return (
        await db.execute(
            select(OAuthTransaction)
            .where(OAuthTransaction.state_hash == _hash_state(state))
            .with_for_update()
        )
    ).scalar_one_or_none()


def _expires_at(token_payload: Dict[str, Any]) -> Optional[datetime]:
    try:
        seconds = int(token_payload.get("expires_in"))
    except (TypeError, ValueError):
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=max(seconds, 0))


def _account_type(profile: Dict[str, Any]) -> str:
    value = str(profile.get("account_type") or "").upper()
    return "INSTAGRAM_CREATOR" if value in {"MEDIA_CREATOR", "CREATOR"} else "INSTAGRAM_BUSINESS"


async def _upsert_connection_and_account(
    db: AsyncSession,
    *,
    transaction: OAuthTransaction,
    profile: Dict[str, Any],
    scopes: list[str],
) -> tuple[ProviderConnection, ConnectedAccount]:
    professional_id = str(profile["user_id"])
    connection = (
        await db.execute(
            select(ProviderConnection).where(
                ProviderConnection.workspace_id == transaction.workspace_id,
                ProviderConnection.provider == "INSTAGRAM",
                ProviderConnection.external_identity_id == professional_id,
            )
        )
    ).scalar_one_or_none()
    scope_missing = bool(REQUIRED_SCOPES - set(scopes))
    if connection is None:
        connection = ProviderConnection(
            workspace_id=transaction.workspace_id,
            provider="INSTAGRAM",
            connection_type="OAUTH",
            external_identity_id=professional_id,
            status="SCOPE_MISSING" if scope_missing else "HEALTHY",
            authorized_scopes=scopes,
            app_id_reference="configured:instagram-business-login",
            webhook_status="NOT_CONFIGURED",
            meta={"auth_mode": "instagram_login", "token_storage": "encrypted_server_side"},
        )
        db.add(connection)
        await db.flush()
    else:
        connection.status = "SCOPE_MISSING" if scope_missing else "HEALTHY"
        connection.authorized_scopes = scopes
        connection.last_validated_at = datetime.now(timezone.utc)

    account = (
        await db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.workspace_id == transaction.workspace_id,
                ConnectedAccount.provider == "INSTAGRAM",
                ConnectedAccount.external_account_id == professional_id,
            )
        )
    ).scalar_one_or_none()
    if account is None:
        account = ConnectedAccount(
            workspace_id=transaction.workspace_id,
            connection_id=str(connection.id),
            provider="INSTAGRAM",
            platform="INSTAGRAM",
            account_type=_account_type(profile),
            external_account_id=professional_id,
            username=str(profile.get("username") or ""),
            display_name=str(profile.get("name") or profile.get("username") or ""),
            profile_url=None,
            avatar_url=profile.get("profile_picture_url"),
            status="LINKED",
            health_status="HEALTHY" if not scope_missing else "DEGRADED",
            is_test=True,
            meta={
                "followers_count": profile.get("followers_count"),
                "media_count": profile.get("media_count"),
                "oauth_source": "instagram_business_login",
            },
        )
        db.add(account)
        await db.flush()
    else:
        account.connection_id = str(connection.id)
        account.username = str(profile.get("username") or account.username or "")
        account.display_name = str(
            profile.get("name") or profile.get("username") or account.display_name or ""
        )
        account.account_type = _account_type(profile)
        account.avatar_url = profile.get("profile_picture_url") or account.avatar_url
        account.status = "LINKED"
        account.health_status = "HEALTHY" if not scope_missing else "DEGRADED"
        account.meta = {
            **(account.meta or {}),
            "followers_count": profile.get("followers_count"),
            "media_count": profile.get("media_count"),
            "oauth_source": "instagram_business_login",
        }
    return connection, account


async def _upsert_credential_reference(
    db: AsyncSession,
    *,
    workspace_id: str,
    account_id: str,
    reference: str,
    scopes: list[str],
    expires_at: Optional[datetime],
) -> None:
    row = (
        await db.execute(
            select(CredentialRef).where(
                CredentialRef.workspace_id == workspace_id,
                CredentialRef.provider == "INSTAGRAM",
                CredentialRef.connected_account_id == account_id,
                CredentialRef.purpose == "READ",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(
            CredentialRef(
                workspace_id=workspace_id,
                provider="INSTAGRAM",
                connected_account_id=account_id,
                secret_ref=reference,
                granted_scopes=scopes,
                expires_at=expires_at,
                purpose="READ",
                status="ACTIVE",
                meta={"storage": "encrypted_server_side"},
            )
        )
    else:
        row.secret_ref = reference
        row.granted_scopes = scopes
        row.expires_at = expires_at
        row.status = "ACTIVE"
    await db.flush()


async def complete_business_login(
    db: AsyncSession,
    *,
    state: str,
    code: Optional[str],
    error: Optional[str] = None,
    error_reason: Optional[str] = None,
) -> OAuthCompletion:
    transaction = await _lookup_pending_transaction(db, state)
    if transaction is None or transaction.provider != "INSTAGRAM":
        return OAuthCompletion(
            False, "The authorization session is invalid or has already been used."
        )
    now = datetime.now(timezone.utc)
    if (
        transaction.status != "PENDING"
        or transaction.expires_at is None
        or now > ensure_utc(transaction.expires_at)
    ):
        transaction.status = "EXPIRED" if transaction.status == "PENDING" else transaction.status
        await db.flush()
        return OAuthCompletion(
            False, "The authorization session has expired. Start a new connection attempt."
        )
    if error or not code:
        transaction.status = "REVOKED"
        await _audit(
            db,
            workspace_id=transaction.workspace_id,
            connection_id=None,
            actor=transaction.initiated_by or "operator",
            action="INSTAGRAM_OAUTH_DENIED",
            after={
                "provider": "INSTAGRAM",
                "reason": error_reason or error or "authorization_not_completed",
            },
        )
        await db.flush()
        return OAuthCompletion(
            False,
            "Instagram authorization was cancelled or denied.",
            workspace_id=transaction.workspace_id,
        )

    transaction.status = "PROCESSING"
    await db.flush()
    try:
        app_id, app_secret, redirect_uri = _require_live_configuration()
        client = InstagramBusinessLoginClient()
        try:
            short_lived = await client.exchange_authorization_code(
                app_id=app_id, app_secret=app_secret, redirect_uri=redirect_uri, code=code
            )
            long_lived = await client.exchange_long_lived_token(
                app_secret=app_secret, short_lived_token=str(short_lived["access_token"])
            )
            profile = await client.get_profile(access_token=str(long_lived["access_token"]))
        finally:
            await client.aclose()

        # The documented token response does not reliably echo granted scopes.
        # Treat the requested scope set as the authorization manifest and let
        # the first live insights pull verify individual capabilities.
        scopes = _parse_scopes(short_lived.get("permissions")) or configured_scopes()
        connection, account = await _upsert_connection_and_account(
            db, transaction=transaction, profile=profile, scopes=scopes
        )
        expires_at = _expires_at(long_lived)
        reference = await store_access_token(
            db,
            connection_id=str(connection.id),
            access_token=str(long_lived["access_token"]),
            token_type=str(
                long_lived.get("token_type") or short_lived.get("token_type") or "bearer"
            ),
            expires_at=expires_at,
            granted_scopes=scopes,
        )
        connection.credential_reference = reference
        connection.token_expires_at = expires_at
        connection.last_validated_at = now
        connection.last_refreshed_at = now
        await _upsert_credential_reference(
            db,
            workspace_id=transaction.workspace_id,
            account_id=str(account.id),
            reference=reference,
            scopes=scopes,
            expires_at=expires_at,
        )
        transaction.status = "COMPLETED"
        transaction.consumed_at = now
        await _audit(
            db,
            workspace_id=transaction.workspace_id,
            connection_id=str(connection.id),
            actor=transaction.initiated_by or "operator",
            action="INSTAGRAM_OAUTH_COMPLETED",
            after={
                "provider": "INSTAGRAM",
                "status": connection.status,
                "scopes": scopes,
                "credential_configured": True,
            },
        )
        await db.flush()
        return OAuthCompletion(
            True,
            "Instagram account connected. Initial data sync can now run from the server.",
            connection_id=str(connection.id),
            workspace_id=transaction.workspace_id,
        )
    except (InstagramBusinessLoginError, InstagramTokenVaultError, ValueError, httpx.HTTPError):
        transaction.status = "REVOKED"
        await _audit(
            db,
            workspace_id=transaction.workspace_id,
            connection_id=None,
            actor=transaction.initiated_by or "operator",
            action="INSTAGRAM_OAUTH_FAILED",
            after={"provider": "INSTAGRAM", "status": "FAILED"},
        )
        await db.flush()
        return OAuthCompletion(
            False,
            "Instagram could not complete this connection. No token was saved; start a new attempt after checking the server configuration.",
            workspace_id=transaction.workspace_id,
        )
