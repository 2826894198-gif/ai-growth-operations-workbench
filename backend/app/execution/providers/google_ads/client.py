"""Google Ads API v25 write client (execution worker only, official SDK)."""

import logging
from typing import Any, Dict, List

from app.core.config import settings
from app.execution.errors import ExecutionError, ExecutionErrorCode
from app.execution.providers.google_ads.exceptions import map_google_write_error

logger = logging.getLogger(__name__)


class GoogleWriteClient:
    """Lazy wrapper around the official google-ads Python client.

    The google-ads package is an optional extra (`pip install -e ".[google]"`).
    Live writes additionally require GOOGLE_ADS_WRITE_ENABLED=true and write
    credentials; the read-only provider client is never reused for mutations.
    """

    def __init__(self):
        self._client = None
        self._services: Dict[str, Any] = {}

    def _ensure(self):
        if self._client is not None:
            return
        if not settings.google_ads_write_enabled:
            raise ExecutionError(
                ExecutionErrorCode.EXECUTION_DISABLED.value,
                "GOOGLE_ADS_WRITE_ENABLED is false; live Google writes disabled",
            )
        try:
            from google.ads.googleads.client import GoogleAdsClient as OfficialClient
        except ImportError as exc:
            raise ExecutionError(
                ExecutionErrorCode.UNSUPPORTED_PROVIDER_CONFIGURATION.value,
                "google-ads package not installed; run pip install -e '.[google]'",
            ) from exc
        config: Dict[str, Any] = {
            "developer_token": settings.google_ads_developer_token,
            "use_proto_plus": True,
            "login_customer_id": settings.google_ads_login_customer_id or None,
            "version": settings.google_ads_api_version,
        }
        if settings.google_ads_service_account_json_path:
            config["json_key_file_path"] = settings.google_ads_service_account_json_path
        else:
            config["client_id"] = ""
            config["client_secret"] = ""
            config["refresh_token"] = ""
        self._client = OfficialClient.load_from_dict(config)

    def service(self, name: str):
        self._ensure()
        if name not in self._services:
            self._services[name] = self._client.get_service(name)
        return self._services[name]

    def get_type(self, name: str):
        self._ensure()
        return self._client.get_type(name)

    def customer_id(self) -> str:
        return settings.google_ads_customer_id.replace("-", "")

    def search(self, query: str) -> List[Dict[str, Any]]:
        self._ensure()
        try:
            service = self.service("GoogleAdsService")
            request = self.get_type("SearchGoogleAdsRequest")
            request.customer_id = self.customer_id()
            request.query = query
            rows: List[Dict[str, Any]] = []
            response = service.search(request)
            for row in response.results:
                rows.append(self._row_to_dict(row))
            return rows
        except Exception as exc:  # noqa: BLE001
            raise map_google_write_error(exc) from exc

    def _row_to_dict(self, row) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for field_descriptor, value in row:
            name = field_descriptor.name
            if hasattr(value, "SerializeToString"):
                out[name] = self._message_to_dict(value)
            elif hasattr(value, "__iter__") and not isinstance(value, str):
                out[name] = [self._message_to_dict(item) if hasattr(item, "SerializeToString") else str(item) for item in value]
            else:
                out[name] = getattr(value, "value", value)
        return out

    def _message_to_dict(self, message) -> Dict[str, Any]:
        try:
            from google.protobuf.json_format import MessageToDict

            return MessageToDict(message, preserving_proto_field_name=True)
        except Exception:  # noqa: BLE001
            return {"serialized": str(message)}
