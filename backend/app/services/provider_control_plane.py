"""Provider control plane — manifest + credential refs (review 4.4).

Shared control surface; read connectors and mutation adapters keep separate
interfaces and separate credential purposes (READ vs WRITE).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.governance import CredentialRef, ProviderManifest

MANIFESTS = [
    {
        "provider": "META",
        "platform": "INSTAGRAM",
        "auth_type": "OAUTH",
        "scopes": ["instagram_basic", "instagram_content_publish", "insights", "pages_show_list", "ads_read"],
        "capabilities": ["ACCOUNT_PROFILE", "CONTENT_LIST", "CONTENT_VIEWS", "PAID_CREATIVE_LINK", "ADS_READ"],
        "rate_limit": {"requests_per_minute": 200, "burst": 100},
        "health_probe": {"endpoint": "/me", "method": "GET"},
        "api_version": settings.meta_graph_api_version,
        "read_only": True,
    },
    {
        "provider": "INSTAGRAM",
        "platform": "INSTAGRAM",
        "auth_type": "OAUTH",
        "scopes": ["instagram_business_basic", "instagram_business_manage_insights"],
        "capabilities": [
            "ACCOUNT_PROFILE",
            "ACCOUNT_FOLLOWERS",
            "CONTENT_LIST",
            "CONTENT_VIEWS",
            "CONTENT_REACH",
            "CONTENT_LIKES",
            "CONTENT_COMMENTS",
            "CONTENT_SHARES",
            "CONTENT_SAVES",
        ],
        "rate_limit": {"requests_per_minute": 200, "burst": 100},
        "health_probe": {"endpoint": "/me", "method": "GET"},
        "api_version": settings.meta_graph_api_version,
        "read_only": True,
    },
    {
        "provider": "GOOGLE_ADS",
        "platform": "GOOGLE_ADS",
        "auth_type": "SERVICE_ACCOUNT",
        "scopes": ["https://www.googleapis.com/auth/adwords"],
        "capabilities": ["CAMPAIGN_READ", "BUDGET_READ", "NEGATIVE_KEYWORD_READ", "ADS_WRITE"],
        "rate_limit": {"operations_per_second": 30},
        "health_probe": {"query": "SELECT customer.id FROM customer"},
        "api_version": "v25",
        "read_only": True,
    },
    {
        "provider": "TIKTOK",
        "platform": "TIKTOK",
        "auth_type": "OAUTH",
        "scopes": ["user.info.basic", "video.list", "video.data"],
        "capabilities": ["ACCOUNT_PROFILE", "CONTENT_LIST", "CONTENT_VIEWS"],
        "rate_limit": {"requests_per_minute": 100},
        "api_version": "v2",
        "read_only": True,
    },
    {
        "provider": "YOUTUBE",
        "platform": "YOUTUBE",
        "auth_type": "API_KEY",
        "scopes": ["youtube.readonly", "yt-analytics.readonly"],
        "capabilities": ["ACCOUNT_PROFILE", "CONTENT_LIST", "CONTENT_VIEWS", "CONTENT_WATCH_TIME", "ACCOUNT_AUDIENCE"],
        "api_version": "v3",
        "read_only": True,
    },
    {
        "provider": "SHOPIFY",
        "platform": "SHOPIFY",
        "auth_type": "OFFLINE_TOKEN",
        "scopes": ["read_orders", "read_products", "read_customers"],
        "capabilities": ["ORDER_READ", "PRODUCT_READ"],
        "rate_limit": {"requests_per_second": 2},
        "api_version": "2026-07",
        "read_only": True,
    },
]


async def seed_provider_manifests(db: AsyncSession) -> int:
    created = 0
    for manifest in MANIFESTS:
        existing = (
            await db.execute(
                select(ProviderManifest).where(
                    ProviderManifest.provider == manifest["provider"],
                    ProviderManifest.platform == manifest["platform"],
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(ProviderManifest(**manifest, status="CONFIGURED"))
        created += 1
    if created:
        await db.flush()
    return created


async def list_manifests(db: AsyncSession) -> List[Dict[str, Any]]:
    rows = (await db.execute(select(ProviderManifest).order_by(ProviderManifest.provider))).scalars().all()
    return [
        {
            "id": str(r.id),
            "provider": r.provider,
            "platform": r.platform,
            "auth_type": r.auth_type,
            "scopes": r.scopes,
            "capabilities": r.capabilities,
            "rate_limit": r.rate_limit,
            "api_version": r.api_version,
            "read_only": r.read_only,
            "status": r.status,
        }
        for r in rows
    ]


async def register_credential_ref(
    db: AsyncSession,
    *,
    workspace_id: str,
    provider: str,
    purpose: str,
    secret_ref: str,
    connected_account_id: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    expires_at: Optional[datetime] = None,
) -> CredentialRef:
    if purpose not in ("READ", "WRITE"):
        raise ValueError("purpose must be READ or WRITE")
    row = CredentialRef(
        workspace_id=workspace_id,
        provider=provider,
        connected_account_id=connected_account_id,
        secret_ref=secret_ref,  # reference only; never the secret itself
        granted_scopes=scopes,
        expires_at=expires_at,
        purpose=purpose,
        status="ACTIVE",
    )
    db.add(row)
    await db.flush()
    return row


async def credential_health(db: AsyncSession, *, workspace_id: str, provider: Optional[str] = None) -> Dict[str, Any]:
    query = select(CredentialRef).where(CredentialRef.workspace_id == workspace_id)
    if provider:
        query = query.where(CredentialRef.provider == provider)
    rows = (await db.execute(query)).scalars().all()
    now = datetime.now(timezone.utc)
    from app.execution.timeutil import ensure_utc

    read = [r for r in rows if r.purpose == "READ"]
    write = [r for r in rows if r.purpose == "WRITE"]
    expiring = [r for r in rows if r.expires_at is not None and (ensure_utc(r.expires_at) - now).total_seconds() < 7 * 86400]
    return {
        "total": len(rows),
        "read": len(read),
        "write": len(write),
        "expiring_soon": len(expiring),
        "items": [
            {
                "id": str(r.id),
                "provider": r.provider,
                "purpose": r.purpose,
                "status": r.status,
                "scopes": r.granted_scopes,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            }
            for r in rows
        ],
    }
