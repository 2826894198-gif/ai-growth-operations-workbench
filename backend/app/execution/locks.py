"""Distributed per-resource execution locks (PART 06 §24-§25).

Uses Redis when available; falls back to an in-process asyncio lock map so
tests and local demo runs stay functional without Redis.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Optional
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)


class ResourceLockManager:
    def __init__(self, redis_url: Optional[str] = None, ttl_seconds: Optional[int] = None):
        self._redis = None
        self._redis_url = redis_url or settings.redis_url
        self._ttl = ttl_seconds or settings.execution_resource_lock_ttl_seconds
        self._mem_locks: Dict[str, asyncio.Lock] = {}
        self._mem_holders: Dict[str, str] = {}
        self._mem_lock = asyncio.Lock()
        self._redis_disabled = os.environ.get("EXECUTION_REDIS_LOCK", "1") != "1"

    def _get_redis(self):
        if self._redis is None and not self._redis_disabled:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            except Exception:  # noqa: BLE001
                logger.warning("redis unavailable; using in-memory execution locks", extra={"event": "lock_fallback"})
                self._redis = None
        return self._redis

    def lock_key(self, provider: str, resource_id: str) -> str:
        return f"execution:{provider}:{resource_id}"

    async def acquire(self, provider: str, resource_id: str, wait_seconds: float = 15.0) -> str:
        key = self.lock_key(provider, resource_id)
        token = str(uuid4())
        client = self._get_redis()
        if client is not None:
            try:
                deadline = asyncio.get_event_loop().time() + wait_seconds
                while True:
                    acquired = await client.set(key, token, nx=True, ex=self._ttl)
                    if acquired:
                        return token
                    if asyncio.get_event_loop().time() >= deadline:
                        raise TimeoutError(f"resource lock not acquired: {key}")
                    await asyncio.sleep(0.2)
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, TimeoutError) and "not acquired" in str(exc):
                    raise
                logger.warning("redis lock unavailable; using in-memory locks", extra={"event": "lock_fallback"})
                self._redis = None
                self._redis_disabled = True

        async with self._mem_lock:
            existing = self._mem_holders.get(key)
            if existing:
                deadline = asyncio.get_event_loop().time() + wait_seconds
                while existing and asyncio.get_event_loop().time() < deadline:
                    await asyncio.sleep(0.2)
                    existing = self._mem_holders.get(key)
                if existing:
                    raise TimeoutError(f"resource lock not acquired: {key}")
            lock = self._mem_locks.setdefault(key, asyncio.Lock())
        await lock.acquire()
        async with self._mem_lock:
            self._mem_holders[key] = token
        return token

    async def release(self, provider: str, resource_id: str, token: str) -> None:
        key = self.lock_key(provider, resource_id)
        client = self._get_redis()
        if client is not None:
            try:
                current = await client.get(key)
                if current == token:
                    await client.delete(key)
                return
            except Exception:  # noqa: BLE001
                self._redis = None
                self._redis_disabled = True
        async with self._mem_lock:
            if self._mem_holders.get(key) == token:
                del self._mem_holders[key]
        lock = self._mem_locks.get(key)
        if lock is not None and lock.locked():
            lock.release()

    @asynccontextmanager
    async def locked(self, provider: str, resource_ids):
        """Acquire one or more locks; release all afterwards."""
        if isinstance(resource_ids, str):
            resource_ids = [resource_ids]
        tokens = []
        try:
            for resource_id in resource_ids:
                tokens.append((resource_id, await self.acquire(provider, resource_id)))
            yield
        finally:
            for resource_id, token in reversed(tokens):
                try:
                    await self.release(provider, resource_id, token)
                except Exception:  # noqa: BLE001
                    logger.exception("failed to release execution lock", extra={"resource": resource_id})


lock_manager = ResourceLockManager()
