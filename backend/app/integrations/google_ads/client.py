import logging
from typing import Any, Dict, List

from app.core.config import settings
from app.integrations.google_ads.exceptions import map_google_error

logger = logging.getLogger(__name__)


class GoogleAdsClient:
    """Thin wrapper around the official google-ads Python client (read-only).

    The google-ads package is an optional extra (`pip install -e ".[google]"`).
    Live mode requires a Developer Token + Service Account JSON + Customer ID.
    """

    def __init__(self):
        self._client = None
        self._service = None

    def _ensure(self):
        if self._client is not None:
            return
        try:
            from google.ads.googleads.client import GoogleAdsClient as OfficialClient
        except ImportError as exc:
            raise RuntimeError(
                "google-ads package not installed; run: pip install -e '.[google]' "
                "or use DATA_PROVIDER_MODE=mock"
            ) from exc
        config: Dict[str, Any] = {
            "developer_token": settings.google_ads_developer_token,
            "use_proto_plus": True,
            "login_customer_id": settings.google_ads_login_customer_id or None,
        }
        if settings.google_ads_service_account_json_path:
            config["json_key_file_path"] = settings.google_ads_service_account_json_path
        else:
            config["client_id"] = ""
            config["client_secret"] = ""
            config["refresh_token"] = ""
        self._client = OfficialClient.load_from_dict(config)
        self._service = self._client.get_service("GoogleAdsService")

    def customer_id(self) -> str:
        return settings.google_ads_customer_id.replace("-", "")

    def _row_to_dict(self, row) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for field_descriptor, value in row:
            name = field_descriptor.name
            out[name] = value
        return out

    def search_stream(self, query: str) -> List[Dict[str, Any]]:
        self._ensure()
        try:
            request = self._client.get_type("SearchGoogleAdsStreamRequest")
            request.customer_id = self.customer_id()
            request.query = query
            rows: List[Dict[str, Any]] = []
            stream = self._service.search_stream(request)
            for batch in stream:
                for row in batch.results:
                    rows.append(self._row_to_dict(row))
            return rows
        except Exception as exc:  # noqa: BLE001
            raise map_google_error(exc) from exc

    def search(self, query: str) -> List[Dict[str, Any]]:
        self._ensure()
        try:
            request = self._client.get_type("SearchGoogleAdsRequest")
            request.customer_id = self.customer_id()
            request.query = query
            rows: List[Dict[str, Any]] = []
            response = self._service.search(request)
            for row in response.results:
                rows.append(self._row_to_dict(row))
            return rows
        except Exception as exc:  # noqa: BLE001
            raise map_google_error(exc) from exc
