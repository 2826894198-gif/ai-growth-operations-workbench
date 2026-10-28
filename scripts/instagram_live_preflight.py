"""Validate the non-secret prerequisites for Instagram Live API mode.

This check deliberately prints names and statuses only. It never prints an App
Secret, access token, authorization header, or resolved secret value.
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

from app.core.config import settings
from app.core.secrets import resolve_secret

PLACEHOLDERS = {"", "CHANGE_ME", "YOUR_APP_ID", "your-app-id", "<app-id>"}
REQUIRED_SCOPES = {"instagram_business_basic", "instagram_business_manage_insights"}


def _is_placeholder(value: str | None) -> bool:
    return (value or "").strip() in PLACEHOLDERS


def _check() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if settings.instagram_demo_mode:
        errors.append("INSTAGRAM_DEMO_MODE must be false for Live API mode")
    if not settings.instagram_sync_enabled:
        errors.append("INSTAGRAM_SYNC_ENABLED must be true for Live API mode")
    if settings.social_provider_mode != "live":
        errors.append("SOCIAL_PROVIDER_MODE must be live for the provider connector")
    if settings.instagram_oauth_mode != "instagram_login":
        errors.append(
            "INSTAGRAM_OAUTH_MODE must be instagram_login for Growth Intelligence V1"
        )
    if _is_placeholder(settings.instagram_app_id):
        errors.append("INSTAGRAM_APP_ID is not configured")
    if not settings.instagram_app_secret_reference:
        errors.append("INSTAGRAM_APP_SECRET_REFERENCE is empty")
    elif resolve_secret(settings.instagram_app_secret_reference) is None:
        errors.append(
            "INSTAGRAM_APP_SECRET_REFERENCE cannot be resolved by the configured SecretProvider"
        )
    if not settings.instagram_token_encryption_key_reference:
        errors.append("INSTAGRAM_TOKEN_ENCRYPTION_KEY_REFERENCE is empty")
    elif (
        settings.app_env in {"staging", "production"}
        and resolve_secret(settings.instagram_token_encryption_key_reference) is None
    ):
        errors.append(
            "INSTAGRAM_TOKEN_ENCRYPTION_KEY_REFERENCE cannot be resolved by the configured SecretProvider"
        )

    scopes = {
        item.strip()
        for item in settings.instagram_required_scopes.split(",")
        if item.strip()
    }
    missing_scopes = sorted(REQUIRED_SCOPES - scopes)
    if missing_scopes:
        errors.append(f"INSTAGRAM_REQUIRED_SCOPES missing: {', '.join(missing_scopes)}")

    redirect_uri = settings.instagram_oauth_redirect_uri.strip()
    if not redirect_uri:
        errors.append("INSTAGRAM_OAUTH_REDIRECT_URI is empty")
    else:
        parsed = urlparse(redirect_uri)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(
                "INSTAGRAM_OAUTH_REDIRECT_URI must be an absolute http(s) URL"
            )
        allowlist = {
            item.strip()
            for item in settings.oauth_redirect_allowlist.split(",")
            if item.strip()
        }
        if redirect_uri not in allowlist:
            errors.append(
                "INSTAGRAM_OAUTH_REDIRECT_URI must also appear in OAUTH_REDIRECT_ALLOWLIST"
            )
        if settings.app_env in {"staging", "production"}:
            if parsed.scheme != "https" or parsed.hostname in {
                "localhost",
                "127.0.0.1",
            }:
                errors.append(
                    "staging/production OAuth redirect must use a public HTTPS hostname"
                )
            if parsed.hostname and parsed.hostname.endswith(".example.com"):
                errors.append(
                    "staging/production OAuth redirect must not use an example.com placeholder"
                )

    # OAuth creates the account token after the callback. A preconfigured token
    # is optional for the preflight, but a legacy direct setting is called out.
    if (
        settings.instagram_access_token
        and not settings.instagram_access_token_reference
    ):
        warnings.append(
            "legacy INSTAGRAM_ACCESS_TOKEN is set without a token reference; use SecretProvider reference"
        )
    if settings.instagram_access_token_reference:
        warnings.append(
            "INSTAGRAM_ACCESS_TOKEN_REFERENCE is a legacy adapter setting; Business Login uses the encrypted OAuth vault"
        )

    if os.environ.get("INSTAGRAM_API_VERSION"):
        warnings.append("INSTAGRAM_API_VERSION is ignored; use META_GRAPH_API_VERSION")

    return errors, warnings


def main() -> int:
    errors, warnings = _check()
    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"FAIL  {error}")
    if errors:
        print(f"Instagram Live API preflight: FAIL ({len(errors)} blocking checks)")
        return 1
    print("Instagram Live API preflight: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
