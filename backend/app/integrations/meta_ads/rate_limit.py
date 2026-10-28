import asyncio
from typing import Optional


class MetaRateLimiter:
    """Simple async rate limiter for Meta Graph API requests."""

    def __init__(self, max_concurrency: int = 4, requests_per_second: float = 8.0):
        self._max_concurrency = max(max_concurrency, 1)
        self._min_interval = 1.0 / max(float(requests_per_second), 0.1)
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._interval_lock: Optional[asyncio.Lock] = None
        self._last_request_at: float = 0.0

    async def _ensure_ready(self) -> None:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrency)
            self._interval_lock = asyncio.Lock()

    async def __aenter__(self) -> "MetaRateLimiter":
        await self._ensure_ready()
        assert self._semaphore is not None and self._interval_lock is not None
        await self._semaphore.acquire()
        loop = asyncio.get_running_loop()
        async with self._interval_lock:
            wait = self._last_request_at + self._min_interval - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = loop.time()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        assert self._semaphore is not None
        self._semaphore.release()
