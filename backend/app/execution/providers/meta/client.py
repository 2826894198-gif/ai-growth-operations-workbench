"""Meta Marketing API v26 write client (execution worker only)."""

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.execution.errors import ExecutionError, ExecutionErrorCode
from app.execution.providers.meta.exceptions import map_meta_write_error

logger = logging.getLogger(__name__)


class MetaWriteClient:
    BASE_URL = "https://graph.facebook.com"
    ENTITY_FIELDS = {
        "CAMPAIGN": "id,name,status,effective_status,daily_budget,lifetime_budget,objective,updated_time",
        "AD_SET": "id,campaign_id,name,status,effective_status,daily_budget,lifetime_budget,budget_remaining,updated_time",
        "AD": "id,campaign_id,adset_id,name,status,effective_status,updated_time",
    }

    def __init__(self, access_token: Optional[str] = None, api_version: Optional[str] = None):
        self.access_token = access_token or settings.meta_write_access_token
        self.api_version = api_version or settings.meta_graph_api_version
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    def _url(self, path: str) -> str:
        return f"{self.BASE_URL}/{self.api_version}/{path}"

    def _ensure_token(self) -> None:
        if not self.access_token:
            raise ExecutionError(
                ExecutionErrorCode.UNSUPPORTED_PROVIDER_CONFIGURATION.value,
                "META_WRITE_ACCESS_TOKEN is not configured; live Meta writes are disabled",
            )

    async def get_object(self, entity_id: str, entity_type: str) -> Dict[str, Any]:
        self._ensure_token()
        fields = self.ENTITY_FIELDS.get(entity_type.upper(), "id,status,effective_status,updated_time")
        try:
            response = await self._client.get(
                self._url(entity_id), params={"fields": fields, "access_token": self.access_token}
            )
        except httpx.TimeoutException as exc:
            raise ExecutionError(ExecutionErrorCode.PROVIDER_TIMEOUT.value, str(exc)) from exc
        body = response.json()
        if "error" in body:
            raise map_meta_write_error(body["error"])
        return body

    async def list_adsets(self, campaign_id: str) -> list:
        """Read ad sets under a campaign to resolve budget ownership (v26)."""
        self._ensure_token()
        params = {
            "fields": "id,daily_budget,lifetime_budget,budget_remaining,status,effective_status",
            "access_token": self.access_token,
        }
        try:
            response = await self._client.get(self._url(f"{campaign_id}/adsets"), params=params)
        except httpx.TimeoutException as exc:
            raise ExecutionError(ExecutionErrorCode.PROVIDER_TIMEOUT.value, str(exc)) from exc
        body = response.json()
        if "error" in body:
            raise map_meta_write_error(body["error"])
        return body.get("data") or []

    async def update_budget(self, entity_id: str, daily_budget_cents: int, currency: str) -> Dict[str, Any]:
        self._ensure_token()
        payload = {"daily_budget": daily_budget_cents, "access_token": self.access_token}
        try:
            response = await self._client.post(self._url(entity_id), data=payload)
        except httpx.TimeoutException as exc:
            raise ExecutionError(ExecutionErrorCode.PROVIDER_TIMEOUT.value, str(exc)) from exc
        body = response.json()
        if "error" in body:
            raise map_meta_write_error(body["error"])
        return body

    async def update_status(self, entity_id: str, status: str) -> Dict[str, Any]:
        self._ensure_token()
        payload = {"status": status, "access_token": self.access_token}
        try:
            response = await self._client.post(self._url(entity_id), data=payload)
        except httpx.TimeoutException as exc:
            raise ExecutionError(ExecutionErrorCode.PROVIDER_TIMEOUT.value, str(exc)) from exc
        body = response.json()
        if "error" in body:
            raise map_meta_write_error(body["error"])
        return body
