from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class ProviderError(Exception):
    """Base error for all data provider adapters."""

    error_code = "PROVIDER_ERROR"


class ProviderAuthFailed(ProviderError):
    error_code = "PROVIDER_AUTH_FAILED"


class ProviderPermissionDenied(ProviderError):
    error_code = "PROVIDER_PERMISSION_DENIED"


class ProviderRateLimited(ProviderError):
    error_code = "PROVIDER_RATE_LIMITED"


class ProviderTimeout(ProviderError):
    error_code = "PROVIDER_TIMEOUT"


class ProviderSchemaChanged(ProviderError):
    error_code = "PROVIDER_SCHEMA_CHANGED"


class ProviderInvalidAccount(ProviderError):
    error_code = "PROVIDER_INVALID_ACCOUNT"


@dataclass
class ConnectionResult:
    ok: bool
    checks: Dict[str, Any] = field(default_factory=dict)
    currency: Optional[str] = None
    timezone: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None


@dataclass
class SyncResult:
    provider: str
    job_type: str
    records_received: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_failed: int = 0
    api_requests: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MarketingDataProvider(Protocol):
    provider: str

    async def validate_connection(self) -> ConnectionResult: ...

    async def sync_accounts(self) -> List[Dict[str, Any]]: ...

    async def sync_dimensions(self) -> Dict[str, List[Dict[str, Any]]]: ...

    async def sync_performance(self, start_date: str, end_date: str) -> List[Dict[str, Any]]: ...

    async def sync_commerce(self, start_date: str, end_date: str) -> Dict[str, List[Dict[str, Any]]]: ...

    async def fetch_journey(self, external_order_id: str) -> Dict[str, Any]: ...

    async def backfill(self, start_date: str, end_date: str) -> SyncResult: ...
