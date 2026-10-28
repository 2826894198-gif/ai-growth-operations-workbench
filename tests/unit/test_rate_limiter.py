import asyncio

import pytest

from app.integrations.adspower.rate_limiter import AdsPowerRateLimiter


@pytest.mark.asyncio
async def test_min_interval_between_requests():
    limiter = AdsPowerRateLimiter(max_concurrency=1, requests_per_second=10.0)
    timestamps = []
    for _ in range(3):
        async with limiter:
            timestamps.append(asyncio.get_running_loop().time())
    assert timestamps[1] - timestamps[0] >= 0.09
    assert timestamps[2] - timestamps[1] >= 0.09


@pytest.mark.asyncio
async def test_concurrency_cap():
    limiter = AdsPowerRateLimiter(max_concurrency=1, requests_per_second=1000.0)
    active = 0
    max_active = 0

    async def worker():
        nonlocal active, max_active
        async with limiter:
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1

    await asyncio.gather(*[worker() for _ in range(5)])
    assert max_active == 1
