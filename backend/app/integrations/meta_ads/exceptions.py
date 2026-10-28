from app.integrations.base import (
    ProviderAuthFailed,
    ProviderInvalidAccount,
    ProviderPermissionDenied,
    ProviderRateLimited,
    ProviderSchemaChanged,
    ProviderTimeout,
)


class MetaApiError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Meta API error {code}: {message}")


def map_meta_error(error: dict) -> Exception:
    code = int(error.get("code", 0) or 0)
    message = error.get("message", "")
    if code in (190, 10, 200):
        return ProviderAuthFailed(message)
    if code in (200, 268):
        return ProviderPermissionDenied(message)
    if code in (4, 17, 32, 613, 80004):
        return ProviderRateLimited(message)
    if code in (803, 100):
        return ProviderInvalidAccount(message)
    return MetaApiError(code, message)


__all__ = [
    "MetaApiError",
    "ProviderAuthFailed",
    "ProviderInvalidAccount",
    "ProviderPermissionDenied",
    "ProviderRateLimited",
    "ProviderSchemaChanged",
    "ProviderTimeout",
    "map_meta_error",
]
