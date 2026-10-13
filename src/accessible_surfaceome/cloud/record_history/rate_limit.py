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

import logging
import math
import os
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

DEFAULT_D1_QPS = 2.5
QPS_ENV_VAR = "RECORD_HISTORY_D1_QPS"

# Independent pacing axis: how fast a sweep (scripts/cloud/sweep_record_history.py)
# is allowed to START fetching genes through the public Worker's archive-bypass
# header, which skips the Worker's own caches. A sweep with no D1 writes to
# pace against (nothing changed for any gene) has nothing else throttling its
# fetch rate, and 8 threads issuing bypassed fetches as fast as possible costs
# ~17 D1 queries per gene on the SAME public D1 that serves users — see the
# 2026-09 incident this constant exists to prevent. Deliberately a much lower
# default than DEFAULT_D1_QPS: it paces GENES, and each gene's fetch fans out
# into several D1 queries downstream of the Worker.
DEFAULT_SWEEP_GPS = 2.0
SWEEP_GPS_ENV_VAR = "RECORD_HISTORY_SWEEP_GPS"


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


def _qps_from_env(env_var: str, default: float) -> float:
    """Shared parsing behind :func:`d1_qps_from_env` / :func:`sweep_gps_from_env`.

    Only a literal ``0`` disables the limiter (see :class:`RateLimiter`).
    Anything unparseable, negative, or non-finite (``inf``/``nan`` — ``float()``
    happily accepts those spellings) logs a warning and falls back to the
    default rather than silently disabling throttling or pacing at some
    nonsensical rate.
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "%s=%r is not a number; using the default %s qps", env_var, raw, default
        )
        return default
    if not math.isfinite(value) or value < 0:
        logger.warning(
            "%s=%r must be a finite number >= 0; using the default %s qps",
            env_var, raw, default,
        )
        return default
    return value


def d1_qps_from_env() -> float:
    """``RECORD_HISTORY_D1_QPS``, defaulting to :data:`DEFAULT_D1_QPS`."""
    return _qps_from_env(QPS_ENV_VAR, DEFAULT_D1_QPS)


def sweep_gps_from_env() -> float:
    """``RECORD_HISTORY_SWEEP_GPS``, defaulting to :data:`DEFAULT_SWEEP_GPS`.

    Paces how many genes a record-history sweep (``--execute`` or
    ``--check-stability``) may START fetching per second through the public
    Worker's archive-bypass header — independent of ``RECORD_HISTORY_D1_QPS``,
    which only paces D1 calls. See :data:`DEFAULT_SWEEP_GPS`'s docstring for
    why this axis exists on its own.
    """
    return _qps_from_env(SWEEP_GPS_ENV_VAR, DEFAULT_SWEEP_GPS)


__all__ = [
    "DEFAULT_D1_QPS",
    "DEFAULT_SWEEP_GPS",
    "QPS_ENV_VAR",
    "SWEEP_GPS_ENV_VAR",
    "RateLimiter",
    "d1_qps_from_env",
    "sweep_gps_from_env",
]
