"""A small thread-safe pacing limiter for record history's D1 traffic.

The shared Cloudflare account API limit (1,200 requests / 5 min, covering
every ``api.cloudflare.com`` call — R2 REST object ops and D1 REST queries
alike) is a budget the whole account draws from, not just this pipeline. A
cohort-scale sweep or seed issuing D1 calls as fast as it can — especially
from a thread pool — can burn through most of that budget on its own and
starve concurrent sessions. :class:`RateLimiter` paces calls to a fixed
ceiling so roughly half the budget stays free for everything else.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable

DEFAULT_D1_QPS = 2.5
QPS_ENV_VAR = "RECORD_HISTORY_D1_QPS"


class RateLimiter:
    """Paces ``acquire()`` calls to at most ``qps`` per second.

    ``qps <= 0`` disables limiting entirely (``acquire`` is then a no-op —
    no lock, no clock read). Thread-safe: concurrent callers serialize
    briefly on a lock while computing/advancing the next allowed time, but
    the (possibly blocking) sleep itself happens outside the lock so one
    slow sleeper doesn't hold up everyone else's bookkeeping.

    ``clock`` / ``sleep`` are injectable so tests can drive this without a
    real wall-clock wait.
    """

    def __init__(
        self,
        qps: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = 1.0 / qps if qps > 0 else 0.0
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_allowed = clock()

    @property
    def enabled(self) -> bool:
        return self._interval > 0

    def acquire(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            now = self._clock()
            start = max(now, self._next_allowed)
            wait = start - now
            self._next_allowed = start + self._interval
        if wait > 0:
            self._sleep(wait)


def d1_qps_from_env() -> float:
    raw = os.environ.get(QPS_ENV_VAR, "").strip()
    if not raw:
        return DEFAULT_D1_QPS
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_D1_QPS


__all__ = ["DEFAULT_D1_QPS", "QPS_ENV_VAR", "RateLimiter", "d1_qps_from_env"]
