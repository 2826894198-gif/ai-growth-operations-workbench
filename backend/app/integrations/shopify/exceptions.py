from app.integrations.base import (
    ProviderAuthFailed,
    ProviderPermissionDenied,
    ProviderRateLimited,
    ProviderSchemaChanged,
    ProviderTimeout,
)


def map_shopify_error(exc: Exception) -> Exception:
    message = str(exc).lower()
    if "unauthorized" in message or "invalid token" in message or "access denied" in message:
        return ProviderAuthFailed(str(exc))
    if "permission" in message or "scope" in message:
        return ProviderPermissionDenied(str(exc))
    if "throttled" in message or "rate limit" in message:
        return ProviderRateLimited(str(exc))
    if "timeout" in message:
        return ProviderTimeout(str(exc))
    if "field" in message or "schema" in message or "not found" in message:
        return ProviderSchemaChanged(str(exc))
    return exc


__all__ = [
    "ProviderAuthFailed",
    "ProviderPermissionDenied",
    "ProviderRateLimited",
    "ProviderSchemaChanged",
    "ProviderTimeout",
    "map_shopify_error",
]
