import asyncio
import time


class TokenBucket:
    """
    Minimal async token bucket: `rate` tokens refill per second, up to
    `capacity`. `await bucket.acquire()` blocks until a token is
    available. Good enough for pacing outbound eCourts provider calls
    from a single worker process; if this ever needs to be shared
    across multiple worker processes, back it with a Redis counter
    instead (same interface).
    """

    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._last_refill = now
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

                if self._tokens >= 1:
                    self._tokens -= 1
                    return

                wait_time = (1 - self._tokens) / self.rate
                await asyncio.sleep(wait_time)
