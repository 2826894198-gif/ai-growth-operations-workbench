import asyncio
import logging
import time
from typing import Any, Dict, Optional

import httpx


class AdsPowerError(Exception):
    pass


class AdsPowerUnavailable(AdsPowerError):
    pass


class AdsPowerAuthFailed(AdsPowerError):
    pass


class AdsPowerApiError(AdsPowerError):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"AdsPower API error code={code} msg={message}")


class ProfileNotFound(AdsPowerError):
    pass


class ProfileStartFailed(AdsPowerError):
    pass


class ProfileStopFailed(AdsPowerError):
    pass


class _RateLimiter:
    def __init__(self, max_concurrency: int, requests_per_second: float):
        self._sem = asyncio.Semaphore(max(max_concurrency, 1))
        self._interval = 1.0 / max(float(requests_per_second), 0.1)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def __aenter__(self) -> "_RateLimiter":
        await self._sem.acquire()
        loop = asyncio.get_running_loop()
        async with self._lock:
            wait = self._last + self._interval - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = loop.time()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._sem.release()


class AdsPowerClient:
    """Standalone AdsPower client for the macOS browser worker."""

    START_DEFAULTS = {
        "headless": "0",
        "last_opened_tabs": "1",
        "proxy_detection": "0",
        "cdp_mask": "1",
        "delete_cache": "0",
    }

    def __init__(
        self,
        base_url: str,
        api_key: str,
        max_concurrency: int = 2,
        requests_per_second: float = 1.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._limiter = _RateLimiter(max_concurrency, requests_per_second)
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(15.0, connect=3.0),
        )
        self._logger = logging.getLogger("browser_worker.adspower")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, payload: Optional[Dict[str, Any]] = None, retry: bool = False
    ) -> Dict[str, Any]:
        attempts = 3 if retry else 1
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                async with self._limiter:
                    response = await self._client.request(
                        method,
                        path,
                        json=payload,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                    )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise AdsPowerUnavailable(str(exc)) from exc
            if response.status_code in (401, 403):
                raise AdsPowerAuthFailed("AdsPower rejected credentials")
            if response.status_code >= 500 and attempt + 1 < attempts:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            return self._parse(response)
        raise AdsPowerUnavailable(str(last_error))

    def _parse(self, response: httpx.Response) -> Dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise AdsPowerApiError(response.status_code, "invalid JSON") from exc
        code = body.get("code", -1)
        msg = str(body.get("msg", ""))
        if code != 0:
            if "not exist" in msg.lower() or code == 5004:
                raise ProfileNotFound(msg)
            if code in (5002, 5003) or "auth" in msg.lower():
                raise AdsPowerAuthFailed(msg)
            raise AdsPowerApiError(code, msg)
        return body.get("data") or body

    async def health_check(self) -> Dict[str, Any]:
        started = time.monotonic()
        await self._request("POST", "/api/v2/browser-profile/list", {"page": 1, "page_size": 1}, retry=True)
        return {"ok": True, "latency_ms": int((time.monotonic() - started) * 1000)}

    async def list_profiles(self, query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"page": 1, "page_size": 100}
        if query:
            payload.update(query)
        return await self._request("POST", "/api/v2/browser-profile/list", payload, retry=True)

    async def start_browser(self, profile_id: str) -> Dict[str, Any]:
        data = await self._request(
            "POST",
            "/api/v2/browser-profile/start",
            {"profile_id": profile_id, **self.START_DEFAULTS},
            retry=False,
        )
        if not data.get("debug_port") and not data.get("ws"):
            raise ProfileStartFailed("AdsPower returned no CDP endpoint")
        return data

    async def stop_browser(self, profile_id: str) -> Dict[str, Any]:
        return await self._request(
            "POST", "/api/v2/browser-profile/stop", {"profile_id": profile_id}, retry=False
        )
