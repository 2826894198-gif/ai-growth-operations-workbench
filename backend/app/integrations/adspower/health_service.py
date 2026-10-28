import logging
import time
from typing import Any, Dict, Optional

import httpx

from app.integrations.adspower.client import AdsPowerClient
from app.integrations.adspower.mapper import proxy_url
from app.models.proxy import Proxy

logger = logging.getLogger(__name__)


class AdsPowerHealthService:
    def __init__(self, client: AdsPowerClient):
        self.client = client

    async def check_api(self) -> Dict[str, Any]:
        return await self.client.health_check()

    async def check_proxy(
        self,
        proxy: Optional[Proxy],
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        if proxy is None:
            return {"ok": False, "error": "PROXY_UNAVAILABLE", "latency_ms": None, "ip": None}
        url = proxy_url(proxy, username, password)
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(proxy=url, timeout=timeout) as client:
                response = await client.get("https://api.ipify.org?format=json")
                response.raise_for_status()
                ip = response.json().get("ip")
                return {
                    "ok": True,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "ip": ip,
                }
        except Exception as exc:  # noqa: BLE001 - normalize all proxy failures
            logger.warning("proxy check failed", extra={"event": "proxy_check_failed"})
            return {"ok": False, "error": "PROXY_UNAVAILABLE", "latency_ms": None, "ip": None, "detail": str(exc)}
