import fakeredis.aioredis
import pytest
import pytest_asyncio
from worker.locking import RedisLockManager


@pytest_asyncio.fixture
async def lock_manager():
    mgr = RedisLockManager("redis://localhost:6379/0")
    mgr._redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return mgr


@pytest.mark.asyncio
async def test_lock_exclusive_and_release(lock_manager):
    profile_id = "p1"
    ok1, token1 = await lock_manager.acquire(profile_id, ttl_ms=60000)
    ok2, _ = await lock_manager.acquire(profile_id, ttl_ms=60000)
    assert ok1 is True
    assert ok2 is False

    assert await lock_manager.release(profile_id, "wrong-token") is False
    assert await lock_manager.release(profile_id, token1) is True

    ok3, _ = await lock_manager.acquire(profile_id, ttl_ms=60000)
    assert ok3 is True


@pytest.mark.asyncio
async def test_lock_ttl_expires(lock_manager):
    profile_id = "p2"
    ok, _ = await lock_manager.acquire(profile_id, ttl_ms=10)
    assert ok
    await __import__("asyncio").sleep(1.2)
    ok2, _ = await lock_manager.acquire(profile_id, ttl_ms=60000)
    assert ok2 is True
