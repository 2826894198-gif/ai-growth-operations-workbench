"""Encrypted persistence for Instagram Business Login access tokens.

The connection table and all API responses store only opaque references.  This
module is the narrow server-side boundary allowed to decrypt a token for an
outbound Meta request.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.secrets import resolve_secret
from app.models.instagram import InstagramOAuthCredential

TOKEN_KEY_VERSION = "instagram-token-v1"
TOKEN_REFERENCE_PREFIX = "vault://instagram-oauth/"


class InstagramTokenVaultError(RuntimeError):
    """Raised without including encrypted or raw credential material."""


def credential_reference(connection_id: str) -> str:
    return f"{TOKEN_REFERENCE_PREFIX}{connection_id}"


def _fernet() -> Fernet:
    configured_key = resolve_secret(settings.instagram_token_encryption_key_reference)
    if not configured_key:
        if settings.app_env in {"staging", "production"}:
            raise InstagramTokenVaultError(
                "Instagram token encryption key is not configured for this deployment"
            )
        configured_key = settings.secret_key

    try:
        return Fernet(configured_key.encode("utf-8"))
    except (TypeError, ValueError):
        # A secret-manager value may be an ordinary high-entropy secret instead
        # of an already encoded Fernet key.  Domain separation keeps it distinct
        # from any other use of the same server secret.
        material = b"instagram-oauth-token-v1:\x00" + configured_key.encode("utf-8")
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(material).digest()))


def _encrypt(payload: Dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")


def _decrypt(ciphertext: str) -> Dict[str, Any]:
    try:
        payload = json.loads(_fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8"))
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstagramTokenVaultError("Instagram token vault data cannot be decrypted") from exc
    if not isinstance(payload, dict):
        raise InstagramTokenVaultError("Instagram token vault data has an invalid format")
    return payload


async def store_access_token(
    db: AsyncSession,
    *,
    connection_id: str,
    access_token: str,
    token_type: Optional[str],
    expires_at: Optional[datetime],
    granted_scopes: list[str],
) -> str:
    """Encrypt and upsert a token without exposing it outside this module."""
    if not access_token:
        raise InstagramTokenVaultError("Instagram access token exchange returned no token")

    encrypted = _encrypt({"access_token": access_token, "stored_at": datetime.now(timezone.utc).isoformat()})
    row = (
        await db.execute(
            select(InstagramOAuthCredential).where(
                InstagramOAuthCredential.connection_id == connection_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = InstagramOAuthCredential(
            connection_id=connection_id,
            key_version=TOKEN_KEY_VERSION,
            ciphertext=encrypted,
            token_type=token_type,
            expires_at=expires_at,
            granted_scopes=granted_scopes,
        )
        db.add(row)
    else:
        row.key_version = TOKEN_KEY_VERSION
        row.ciphertext = encrypted
        row.token_type = token_type
        row.expires_at = expires_at
        row.granted_scopes = granted_scopes
        row.revoked_at = None
    await db.flush()
    return credential_reference(connection_id)


async def load_access_token(db: AsyncSession, connection_id: str) -> str:
    """Return a token only to the server-side Meta client."""
    row = (
        await db.execute(
            select(InstagramOAuthCredential).where(
                InstagramOAuthCredential.connection_id == connection_id
            )
        )
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        raise InstagramTokenVaultError("Instagram connection has no active server-side credential")
    payload = _decrypt(row.ciphertext)
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise InstagramTokenVaultError("Instagram token vault data has no usable access token")
    return token


async def revoke_access_token(db: AsyncSession, connection_id: str) -> None:
    """Cryptographically overwrite a local credential on disconnect/revocation."""
    row = (
        await db.execute(
            select(InstagramOAuthCredential).where(
                InstagramOAuthCredential.connection_id == connection_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return
    row.ciphertext = _encrypt({"revoked": True})
    row.revoked_at = datetime.now(timezone.utc)
    await db.flush()
