import asyncio


class AdsPowerRateLimiter:
    """Async rate limiter: max concurrency + minimum interval between requests."""

    def __init__(self, max_concurrency: int = 2, requests_per_second: float = 1.0):
        self._max_concurrency = max(max_concurrency, 1)
        self._min_interval = 1.0 / max(float(requests_per_second), 0.1)
        self._semaphore = None
        self._interval_lock = None
        self._last_request_at: float = 0.0

    async def _ensure_ready(self) -> None:
        if self._semaphore is None:
            # asyncio primitives bind to the running loop at creation time on
            # Python 3.9, so create them lazily inside the event loop.
            self._semaphore = asyncio.Semaphore(self._max_concurrency)
            self._interval_lock = asyncio.Lock()

    async def acquire(self) -> None:
        await self._ensure_ready()
        assert self._semaphore is not None and self._interval_lock is not None
        await self._semaphore.acquire()
        loop = asyncio.get_running_loop()
        async with self._interval_lock:
            now = loop.time()
            wait = self._last_request_at + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = loop.time()
            self._last_request_at = now

    def release(self) -> None:
        self._semaphore.release()

    async def __aenter__(self) -> "AdsPowerRateLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.release()
