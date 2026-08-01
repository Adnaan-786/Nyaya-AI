import asyncio
import time

import pytest

from app.core.rate_limiter import TokenBucket


@pytest.mark.asyncio
async def test_token_bucket_allows_burst_up_to_capacity():
    bucket = TokenBucket(rate=1.0, capacity=3)

    start = time.monotonic()
    for _ in range(3):
        await bucket.acquire()
    elapsed = time.monotonic() - start

    # All 3 tokens were available immediately (capacity=3).
    assert elapsed < 0.2


@pytest.mark.asyncio
async def test_token_bucket_paces_beyond_capacity():
    bucket = TokenBucket(rate=10.0, capacity=1)

    start = time.monotonic()
    await bucket.acquire()  # consumes the only token immediately
    await bucket.acquire()  # must wait ~1/rate seconds for a refill
    elapsed = time.monotonic() - start

    assert elapsed >= 0.08  # ~0.1s expected at rate=10/s, allow jitter
