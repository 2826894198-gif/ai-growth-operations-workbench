from app.integrations.base import (
    ProviderAuthFailed,
    ProviderPermissionDenied,
    ProviderRateLimited,
    ProviderSchemaChanged,
    ProviderTimeout,
)


def map_google_error(exc: Exception) -> Exception:
    message = str(exc)
    lowered = message.lower()
    if "authentication" in lowered or "authorization" in lowered or "developer token" in lowered:
        return ProviderAuthFailed(message)
    if "permission" in lowered:
        return ProviderPermissionDenied(message)
    if "resource_exhausted" in lowered or "rate" in lowered or "quota" in lowered:
        return ProviderRateLimited(message)
    if "timeout" in lowered:
        return ProviderTimeout(message)
    if "field" in lowered or "schema" in lowered or "unsupported" in lowered:
        return ProviderSchemaChanged(message)
    return exc


__all__ = [
    "ProviderAuthFailed",
    "ProviderPermissionDenied",
    "ProviderRateLimited",
    "ProviderSchemaChanged",
    "ProviderTimeout",
    "map_google_error",
]
