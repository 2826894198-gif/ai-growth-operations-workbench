from typing import Optional, Tuple
from uuid import uuid4

import redis.asyncio as aioredis
from redis.exceptions import WatchError


class RedisLockManager:
    """Redis distributed lock keyed by profile id.

    TTL = task timeout + safety margin so a crashed worker cannot deadlock a
    profile forever.
    """

    LOCK_PREFIX = "lock:browser_profile:"

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

    async def _client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    async def acquire(self, profile_id: str, ttl_ms: int, token: Optional[str] = None) -> Tuple[bool, str]:
        client = await self._client()
        token = token or str(uuid4())
        acquired = await client.set(
            f"{self.LOCK_PREFIX}{profile_id}",
            token,
            nx=True,
            px=max(ttl_ms, 1000),
        )
        return bool(acquired), token

    async def release(self, profile_id: str, token: str) -> bool:
        client = await self._client()
        key = f"{self.LOCK_PREFIX}{profile_id}"
        async with client.pipeline() as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    current = await pipe.get(key)
                    if current != token:
                        await pipe.unwatch()
                        return False
                    pipe.multi()
                    pipe.delete(key)
                    await pipe.execute()
                    return True
                except WatchError:
                    continue

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
