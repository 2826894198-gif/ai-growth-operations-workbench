import asyncio
import time
from typing import Any, Dict, Optional

import httpx

from app.core.logging import get_logger
from app.integrations.adspower.exceptions import (
    AdsPowerApiError,
    AdsPowerAuthFailed,
    AdsPowerUnavailable,
    ProfileNotFound,
    ProfileStartFailed,
    ProfileStopFailed,
)
from app.integrations.adspower.rate_limiter import AdsPowerRateLimiter
from app.integrations.adspower.schemas import CreateProfileData, ProfileListData, StartBrowserData

START_DEFAULTS: Dict[str, Any] = {
    "headless": "0",
    "last_opened_tabs": "1",
    "proxy_detection": "0",
    "cdp_mask": "1",
    "delete_cache": "0",
}


class AdsPowerClient:
    """Async client for the AdsPower Local API (V2 endpoints preferred).

    Responsibilities: HTTP transport, authentication, timeouts, retry policy,
    rate limiting, error mapping and structured logging.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        max_concurrency: int = 2,
        requests_per_second: float = 1.0,
        connect_timeout: float = 3.0,
        read_timeout: float = 15.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._limiter = AdsPowerRateLimiter(max_concurrency, requests_per_second)
        self._timeout = httpx.Timeout(read_timeout, connect=connect_timeout)
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        self._logger = get_logger("adspower.client")

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def base_url(self) -> str:
        return self._base_url

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        retry: bool = False,
        retries: int = 2,
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None
        attempts = retries + 1 if retry else 1
        for attempt in range(attempts):
            started = time.monotonic()
            try:
                async with self._limiter:
                    response = await self._client.request(
                        method, path, json=payload, headers=self._headers()
                    )
            except httpx.HTTPError as exc:
                last_error = exc
                self._logger.warning(
                    "adspower request transport error",
                    extra={"event": "adspower_transport_error", "path": path, "attempt": attempt + 1},
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise AdsPowerUnavailable(f"AdsPower Local API unreachable: {exc}") from exc

            duration_ms = int((time.monotonic() - started) * 1000)
            if response.status_code in (401, 403):
                raise AdsPowerAuthFailed("AdsPower rejected credentials")
            if response.status_code >= 500 and attempt + 1 < attempts:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            body = self._parse_response(response, path)
            self._logger.debug(
                "adspower request ok",
                extra={"event": "adspower_request", "path": path, "status": response.status_code, "duration_ms": duration_ms},
            )
            return body

        raise AdsPowerUnavailable(f"AdsPower request failed after retries: {last_error}")

    def _parse_response(self, response: httpx.Response, path: str) -> Dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise AdsPowerApiError(response.status_code, "invalid JSON response") from exc
        if not isinstance(body, dict):
            raise AdsPowerApiError(response.status_code, "unexpected response shape")
        code = body.get("code", -1)
        msg = str(body.get("msg", ""))
        if code != 0:
            if "not exist" in msg.lower() or "not found" in msg.lower() or code == 5004:
                raise ProfileNotFound(msg)
            if code in (5002, 5003) or "auth" in msg.lower():
                raise AdsPowerAuthFailed(msg)
            if "start" in path:
                raise ProfileStartFailed(msg)
            if "stop" in path or "close" in path:
                raise ProfileStopFailed(msg)
            raise AdsPowerApiError(code, msg)
        return body.get("data") if body.get("data") is not None else body

    async def health_check(self) -> Dict[str, Any]:
        started = time.monotonic()
        await self._request("POST", "/api/v2/browser-profile/list", {"page": 1, "page_size": 1})
        latency_ms = int((time.monotonic() - started) * 1000)
        return {"ok": True, "latency_ms": latency_ms}

    async def create_profile(self, payload: Dict[str, Any]) -> CreateProfileData:
        # Write operation: never blindly retry (avoids duplicate profiles).
        data = await self._request("POST", "/api/v2/browser-profile/create", payload, retry=False)
        return CreateProfileData(**data)

    async def list_profiles(self, query: Optional[Dict[str, Any]] = None) -> ProfileListData:
        payload = {"page": 1, "page_size": 100}
        if query:
            payload.update(query)
        data = await self._request("POST", "/api/v2/browser-profile/list", payload, retry=True)
        return ProfileListData(**data)

    async def start_browser(self, profile_id: str) -> StartBrowserData:
        payload = {"profile_id": profile_id, **START_DEFAULTS}
        data = await self._request("POST", "/api/v2/browser-profile/start", payload, retry=False)
        if not data.get("debug_port") and not data.get("ws"):
            raise ProfileStartFailed("AdsPower returned no CDP endpoint")
        return StartBrowserData(**data)

    async def stop_browser(self, profile_id: str) -> Dict[str, Any]:
        data = await self._request(
            "POST", "/api/v2/browser-profile/stop", {"profile_id": profile_id}, retry=False
        )
        return data

    async def delete_profile(self, profile_id: str) -> Dict[str, Any]:
        """Used by integration tests/cleanup only. Not exposed through the public API."""
        return await self._request(
            "POST", "/api/v2/browser-profile/delete", {"profile_ids": [profile_id]}, retry=False
        )
