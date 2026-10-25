import time
from collections.abc import Callable


class RateLimiter:
    """Keeps calls to wait() at least min_interval seconds apart."""

    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        if self._last is not None:
            remaining = self._last + self._min_interval - self._clock()
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()
