import threading
import time
from collections.abc import Callable


class RateLimiter:
    """Client-side request pacing, shared by all worker threads.

    Spaces request starts evenly so at most `per_minute` start in any 60 s window.
    `per_minute=None` disables pacing (paid tiers with high limits).
    """

    def __init__(
        self,
        per_minute: int | None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = 60.0 / per_minute if per_minute else 0.0
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self) -> None:
        if not self._interval:
            return
        with self._lock:
            now = self._clock()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self._interval
        if slot > now:
            self._sleep(slot - now)
