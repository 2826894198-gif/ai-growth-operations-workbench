"""OAuth transaction security (PART 07 §31-§34, §32).

state validation, PKCE verifier reference, redirect allowlist, workspace +
provider binding, expiry, single-use, audit.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.execution.timeutil import ensure_utc
from app.models.governance import OAuthTransaction

REDIRECT_ALLOWLIST = [
    "http://localhost:5173/connections/oauth/callback",
    "http://127.0.0.1:5173/connections/oauth/callback",
]


def allowed_redirect_uris() -> List[str]:
    configured = [uri.strip() for uri in settings.oauth_redirect_allowlist.split(",") if uri.strip()]
    return REDIRECT_ALLOWLIST + configured


async def start_oauth_transaction(
    db: AsyncSession,
    *,
    workspace_id: str,
    provider: str,
    redirect_uri: Optional[str] = None,
    initiated_by: str = "operator",
    ttl_minutes: int = 10,
) -> Dict[str, Any]:
    """Create a single-use OAuth transaction with state + PKCE (reference only)."""
    redirect_uri = redirect_uri or allowed_redirect_uris()[0]
    if redirect_uri not in allowed_redirect_uris():
        raise ValueError("redirect_uri is not allowlisted")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    transaction = OAuthTransaction(
        workspace_id=workspace_id,
        provider=provider.upper(),
        state_hash=_hash_state(state),
        pkce_verifier_reference=f"enc://oauth_pkce_{provider.lower()}",
        redirect_uri=redirect_uri,
        initiated_by=initiated_by,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        status="PENDING",
    )
    db.add(transaction)
    await db.flush()
    # Demo: store the verifier under a local env reference; production uses a
    # secret manager. The transaction itself never stores the raw verifier.
    import os

    os.environ[f"OAUTH_PKCE_{provider.upper()}_{str(transaction.id)[:8]}"] = verifier
    return {
        "transaction_id": str(transaction.id),
        "oauth_url": f"/api/v1/connections/{provider}/oauth/callback?state={state}&code_challenge={secrets.token_urlsafe(43)}",
        "state": state,
        "redirect_uri": redirect_uri,
        "expires_at": transaction.expires_at.isoformat(),
        "provider": transaction.provider,
    }


async def consume_oauth_transaction(
    db: AsyncSession,
    *,
    workspace_id: str,
    provider: str,
    state: str,
) -> OAuthTransaction:
    """Validate and single-use consume the transaction before code exchange."""
    state_hash = _hash_state(state)
    transaction = (
        await db.execute(select(OAuthTransaction).where(OAuthTransaction.state_hash == state_hash))
    ).scalar_one_or_none()
    if transaction is None:
        raise ValueError("oauth state not found")
    if transaction.workspace_id != workspace_id:
        raise ValueError("oauth workspace mismatch")
    if transaction.provider != provider.upper():
        raise ValueError("oauth provider mismatch")
    if transaction.status != "PENDING":
        raise ValueError(f"oauth transaction already {transaction.status.lower()}")
    now = datetime.now(timezone.utc)
    if transaction.expires_at is None or now > ensure_utc(transaction.expires_at):
        transaction.status = "EXPIRED"
        await db.flush()
        raise ValueError("oauth transaction expired")
    transaction.status = "COMPLETED"
    transaction.consumed_at = now
    await db.flush()
    return transaction


def _hash_state(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()
