"""Connection Center service — OAuth, discovery, linking, capabilities, health (E11-E19)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.social.factory import get_social_provider
from app.models.social import (
    AccountCapability,
    ConnectedAccount,
    ConnectionAudit,
    ProviderCapability,
    ProviderConnection,
)
from app.services.oauth_service import consume_oauth_transaction, start_oauth_transaction

PROVIDER_SCOPES = {
    "META": ["instagram_basic", "instagram_content_publish", "insights", "pages_show_list", "ads_read"],
    # Instagram API with Instagram Login. Keep this separate from the legacy
    # META/Facebook Login manifest because it does not require Page or Ads
    # permissions for the V1 growth intelligence read path.
    "INSTAGRAM": ["instagram_business_basic", "instagram_business_manage_insights"],
    "TIKTOK": ["user.info.basic", "video.list", "video.data"],
    "YOUTUBE": ["youtube.readonly", "yt-analytics.readonly"],
}


async def audit(
    db: AsyncSession,
    *,
    workspace_id: Optional[str],
    connection_id: Optional[str],
    account_id: Optional[str],
    actor: str,
    action: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    db.add(
        ConnectionAudit(
            workspace_id=workspace_id,
            connection_id=connection_id,
            account_id=account_id,
            actor=actor,
            action=action,
            before=before,
            after=after,
            metadata=metadata,
        )
    )


def serialize_connection(connection: ProviderConnection) -> Dict[str, Any]:
    """Never expose raw tokens/secrets (E100)."""
    return {
        "id": str(connection.id),
        "workspace_id": connection.workspace_id,
        "provider": connection.provider,
        "connection_type": connection.connection_type,
        "external_identity_id": connection.external_identity_id,
        "credential_configured": bool(connection.credential_reference),
        "status": connection.status,
        "authorized_scopes": connection.authorized_scopes,
        "token_expires_at": connection.token_expires_at.isoformat() if connection.token_expires_at else None,
        "last_validated_at": connection.last_validated_at.isoformat() if connection.last_validated_at else None,
        "last_refreshed_at": connection.last_refreshed_at.isoformat() if connection.last_refreshed_at else None,
        "app_id_reference": connection.app_id_reference,
        "webhook_status": connection.webhook_status,
        "webhook_last_event_at": connection.webhook_last_event_at.isoformat() if connection.webhook_last_event_at else None,
        "webhook_failure_count": connection.webhook_failure_count,
        "rate_limit_status": connection.rate_limit_status,
        "rate_limit_retry_after": connection.rate_limit_retry_after,
        "metadata": connection.meta,
        "created_at": connection.created_at.isoformat() if connection.created_at else None,
    }


async def start_oauth(db: AsyncSession, *, workspace_id: str, provider: str, actor: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    provider = provider.upper()
    scopes = PROVIDER_SCOPES.get(provider, [])
    transaction = await start_oauth_transaction(
        db,
        workspace_id=workspace_id,
        provider=provider,
        redirect_uri=redirect_uri,
        initiated_by=actor,
    )
    await audit(
        db,
        workspace_id=workspace_id,
        connection_id=None,
        account_id=None,
        actor=actor,
        action="OAUTH_STARTED",
        after={"provider": provider, "state_hash": transaction["state"][:12] + "...", "scopes": scopes},
        metadata={"redirect_uri": redirect_uri},
    )
    await db.flush()
    return {
        "provider": provider,
        "oauth_url": transaction["oauth_url"],
        "state": transaction["state"],
        "transaction_id": transaction["transaction_id"],
        "scopes": scopes,
        "redirect_uri": transaction["redirect_uri"],
        "note": "single-use transaction with PKCE; callback validates state/expiry/workspace/provider",
    }


async def complete_oauth_callback(db: AsyncSession, *, workspace_id: str, provider: str, state: str, code: str, actor: str) -> ProviderConnection:
    provider = provider.upper()
    await consume_oauth_transaction(db, workspace_id=workspace_id, provider=provider, state=state)
    connection = ProviderConnection(
        workspace_id=workspace_id,
        provider=provider,
        connection_type="OAUTH",
        external_identity_id=f"{provider.lower()}_identity_{uuid4().hex[:6]}",
        credential_reference=f"enc://{provider.lower()}_credential_{uuid4().hex[:8]}",  # reference only
        status="HEALTHY",
        authorized_scopes=PROVIDER_SCOPES.get(provider, []),
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=60),
        last_validated_at=datetime.now(timezone.utc),
        last_refreshed_at=datetime.now(timezone.utc),
        app_id_reference=f"{provider.lower()}-app-ref",
        webhook_status="HEALTHY",
    )
    db.add(connection)
    await db.flush()
    await audit(
        db,
        workspace_id=workspace_id,
        connection_id=str(connection.id),
        account_id=None,
        actor=actor,
        action="OAUTH_COMPLETED",
        after={"provider": provider, "status": "HEALTHY", "scopes": connection.authorized_scopes},
    )
    await db.flush()
    return connection


async def validate_connection(db: AsyncSession, connection_id: str, actor: str) -> Dict[str, Any]:
    connection = (await db.execute(select(ProviderConnection).where(ProviderConnection.id == connection_id))).scalar_one_or_none()
    if connection is None:
        raise ValueError("connection not found")
    provider = get_social_provider(connection.provider)
    result = await provider.validate_connection(connection)
    connection.status = result.get("status", connection.status)
    connection.last_validated_at = datetime.now(timezone.utc)
    await audit(
        db,
        workspace_id=connection.workspace_id,
        connection_id=connection_id,
        account_id=None,
        actor=actor,
        action="CONNECTION_VALIDATED",
        after={"status": connection.status},
    )
    await db.flush()
    return {"connection": serialize_connection(connection), "validation": result}


async def discover_accounts(db: AsyncSession, connection_id: str, actor: str) -> Dict[str, Any]:
    connection = (await db.execute(select(ProviderConnection).where(ProviderConnection.id == connection_id))).scalar_one_or_none()
    if connection is None:
        raise ValueError("connection not found")
    provider = get_social_provider(connection.provider)
    discovered = await provider.discover_accounts(connection)
    await audit(
        db,
        workspace_id=connection.workspace_id,
        connection_id=connection_id,
        account_id=None,
        actor=actor,
        action="DISCOVERED",
        after={"count": len(discovered), "accounts": [a.external_account_id for a in discovered]},
    )
    await db.flush()
    return {
        "connection_id": connection_id,
        "provider": connection.provider,
        "discovered": [vars(a) for a in discovered],
        "count": len(discovered),
    }


async def link_accounts(
    db: AsyncSession,
    *,
    connection_id: str,
    external_account_ids: List[str],
    workspace_id: str,
    brand_id: Optional[str],
    account_group_id: Optional[str],
    actor: str,
) -> List[ConnectedAccount]:
    connection = (await db.execute(select(ProviderConnection).where(ProviderConnection.id == connection_id))).scalar_one_or_none()
    if connection is None:
        raise ValueError("connection not found")
    provider = get_social_provider(connection.provider)
    discovered = {a.external_account_id: a for a in await provider.discover_accounts(connection)}
    linked: List[ConnectedAccount] = []
    for external_id in external_account_ids:
        if external_id not in discovered:
            continue
        account_data = discovered[external_id]
        existing = (
            await db.execute(
                select(ConnectedAccount).where(
                    ConnectedAccount.workspace_id == workspace_id,
                    ConnectedAccount.provider == connection.provider,
                    ConnectedAccount.external_account_id == external_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.status = "LINKED"
            existing.brand_id = brand_id or existing.brand_id
            existing.account_group_id = account_group_id or existing.account_group_id
            row = existing
        else:
            row = ConnectedAccount(
                workspace_id=workspace_id,
                brand_id=brand_id,
                account_group_id=account_group_id,
                connection_id=connection_id,
                provider=connection.provider,
                platform=account_data.platform.upper(),
                account_type=account_data.account_type,
                external_account_id=account_data.external_account_id,
                external_parent_id=account_data.external_parent_id,
                username=account_data.username,
                display_name=account_data.display_name,
                profile_url=account_data.profile_url,
                avatar_url=account_data.avatar_url,
                country=account_data.country,
                timezone=account_data.timezone,
                status="LINKED",
                health_status="HEALTHY",
                metadata={"followers": account_data.followers},
            )
            db.add(row)
            await db.flush()
        linked.append(row)
        await audit(
            db,
            workspace_id=workspace_id,
            connection_id=connection_id,
            account_id=str(row.id),
            actor=actor,
            action="LINKED",
            after={"external_account_id": external_id, "platform": row.platform},
        )
    await db.flush()
    return linked


async def refresh_capabilities(db: AsyncSession, account: ConnectedAccount, actor: str) -> int:
    provider = get_social_provider(account.platform)
    capabilities = await provider.get_capabilities(account.external_account_id)
    count = 0
    for capability_key, supported in capabilities.items():
        existing = (
            await db.execute(
                select(AccountCapability).where(
                    AccountCapability.account_id == str(account.id),
                    AccountCapability.capability_key == capability_key,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                AccountCapability(
                    account_id=str(account.id),
                    capability_key=capability_key,
                    supported=supported,
                    permission_granted=supported,
                    last_verified_at=datetime.now(timezone.utc),
                )
            )
            count += 1
        else:
            existing.supported = supported
            existing.permission_granted = supported
            existing.last_verified_at = datetime.now(timezone.utc)
            count += 1
    await audit(
        db,
        workspace_id=account.workspace_id,
        connection_id=str(account.connection_id) if account.connection_id else None,
        account_id=str(account.id),
        actor=actor,
        action="CAPABILITIES_REFRESHED",
        after={"capabilities": capabilities},
    )
    await db.flush()
    return count


async def connection_health(db: AsyncSession, connection_id: str) -> Dict[str, Any]:
    connection = (await db.execute(select(ProviderConnection).where(ProviderConnection.id == connection_id))).scalar_one_or_none()
    if connection is None:
        raise ValueError("connection not found")
    now = datetime.now(timezone.utc)
    expires_in_days = None
    if connection.token_expires_at is not None:
        from app.execution.timeutil import ensure_utc

        expires_in_days = (ensure_utc(connection.token_expires_at) - now).total_seconds() / 86400
    account_count = (
        await db.execute(select(ConnectedAccount).where(ConnectedAccount.connection_id == connection_id))
    ).scalars().all()
    return {
        "connection": serialize_connection(connection),
        "token_expires_in_days": round(expires_in_days, 1) if expires_in_days is not None else None,
        "token_expiring_soon": expires_in_days is not None and expires_in_days < 7,
        "accounts_linked": len(account_count),
        "webhook": {"status": connection.webhook_status, "failure_count": connection.webhook_failure_count},
        "rate_limit": {"status": connection.rate_limit_status, "retry_after": connection.rate_limit_retry_after},
    }


async def reauthorize(db: AsyncSession, connection_id: str, actor: str) -> Dict[str, Any]:
    connection = (await db.execute(select(ProviderConnection).where(ProviderConnection.id == connection_id))).scalar_one_or_none()
    if connection is None:
        raise ValueError("connection not found")
    before_scopes = list(connection.authorized_scopes or [])
    connection.status = "HEALTHY"
    connection.last_refreshed_at = datetime.now(timezone.utc)
    connection.token_expires_at = datetime.now(timezone.utc) + timedelta(days=60)
    after_scopes = PROVIDER_SCOPES.get(connection.provider.upper(), before_scopes)
    connection.authorized_scopes = after_scopes
    missing = [s for s in before_scopes if s not in after_scopes]
    if missing:
        connection.status = "SCOPE_MISSING"
    await audit(
        db,
        workspace_id=connection.workspace_id,
        connection_id=connection_id,
        account_id=None,
        actor=actor,
        action="REAUTHORIZED",
        before={"scopes": before_scopes},
        after={"scopes": after_scopes, "status": connection.status},
    )
    await db.flush()
    return {
        "connection": serialize_connection(connection),
        "scope_diff": {"before": before_scopes, "after": after_scopes, "missing": missing},
        "capability_degraded": bool(missing),
    }


async def disconnect_account(db: AsyncSession, account: ConnectedAccount, actor: str) -> ConnectedAccount:
    account.status = "DISCONNECTED"
    account.health_status = "DISCONNECTED"
    await audit(
        db,
        workspace_id=account.workspace_id,
        connection_id=str(account.connection_id) if account.connection_id else None,
        account_id=str(account.id),
        actor=actor,
        action="UNLINKED",
        before={"status": "LINKED"},
        after={"status": "DISCONNECTED"},
        metadata={"note": "history retained; data deletion requires admin workflow (E151)"},
    )
    await db.flush()
    return account


async def reconnect_account(db: AsyncSession, account: ConnectedAccount, actor: str) -> ConnectedAccount:
    """Reconnect by matching the same external_account_id (E152)."""
    account.status = "LINKED"
    account.health_status = "HEALTHY"
    await audit(
        db,
        workspace_id=account.workspace_id,
        connection_id=str(account.connection_id) if account.connection_id else None,
        account_id=str(account.id),
        actor=actor,
        action="RECONNECTED",
        after={"status": "LINKED"},
    )
    await db.flush()
    return account


async def seed_provider_capabilities(db: AsyncSession) -> int:
    definitions = {
        ("META", "INSTAGRAM"): {
            "ACCOUNT_PROFILE": True,
            "ACCOUNT_FOLLOWERS": True,
            "CONTENT_LIST": True,
            "CONTENT_VIEWS": True,
            "CONTENT_REACH": True,
            "CONTENT_LIKES": True,
            "CONTENT_COMMENTS": True,
            "CONTENT_SHARES": True,
            "CONTENT_SAVES": True,
            "CONTENT_WATCH_TIME": False,
            "CONTENT_SKIP_RATE": False,
            "PAID_CREATIVE_LINK": True,
            "ADS_READ": True,
        },
        # Instagram Login V1 intentionally does not advertise Ads or paid
        # attribution capabilities. Those require a separate, explicit Meta
        # Ads connection and are outside this monitor's scope.
        ("INSTAGRAM", "INSTAGRAM"): {
            "ACCOUNT_PROFILE": True,
            "ACCOUNT_FOLLOWERS": True,
            "CONTENT_LIST": True,
            "CONTENT_VIEWS": True,
            "CONTENT_REACH": True,
            "CONTENT_LIKES": True,
            "CONTENT_COMMENTS": True,
            "CONTENT_SHARES": True,
            "CONTENT_SAVES": True,
            "CONTENT_WATCH_TIME": False,
            "CONTENT_SKIP_RATE": False,
            "PAID_CREATIVE_LINK": False,
            "ADS_READ": False,
        },
        ("TIKTOK", "TIKTOK"): {
            "ACCOUNT_PROFILE": True,
            "ACCOUNT_FOLLOWERS": True,
            "CONTENT_LIST": True,
            "CONTENT_VIEWS": True,
            "CONTENT_LIKES": True,
            "CONTENT_COMMENTS": True,
            "CONTENT_SHARES": True,
            "CONTENT_WATCH_TIME": False,
            "PAID_CREATIVE_LINK": False,
        },
        ("YOUTUBE", "YOUTUBE"): {
            "ACCOUNT_PROFILE": True,
            "ACCOUNT_FOLLOWERS": True,
            "CONTENT_LIST": True,
            "CONTENT_VIEWS": True,
            "CONTENT_LIKES": True,
            "CONTENT_COMMENTS": True,
            "CONTENT_WATCH_TIME": True,
            "CONTENT_COMPLETION": True,
            "CONTENT_TRAFFIC_SOURCE": True,
            "ACCOUNT_AUDIENCE": True,
            "PAID_CREATIVE_LINK": True,
        },
    }
    created = 0
    for (provider, platform), capabilities in definitions.items():
        for capability_key, supported in capabilities.items():
            existing = (
                await db.execute(
                    select(ProviderCapability).where(
                        ProviderCapability.provider == provider,
                        ProviderCapability.platform == platform,
                        ProviderCapability.capability_key == capability_key,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue
            db.add(
                ProviderCapability(
                    provider=provider,
                    platform=platform,
                    capability_key=capability_key,
                    default_supported=supported,
                    provider_version=(
                        settings.meta_graph_api_version
                        if provider in {"META", "INSTAGRAM"}
                        else "v2"
                        if provider == "TIKTOK"
                        else "v3"
                    ),
                    description=f"{capability_key.replace('_', ' ').title()} for {platform}",
                )
            )
            created += 1
    if created:
        await db.flush()
    return created
