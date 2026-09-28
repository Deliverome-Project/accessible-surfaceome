"""``cloud/record_history/rate_limit.py``: pacing, disabling, and the env var.

Every test injects a fake clock/sleep so nothing here does a real wall-clock
wait.
"""

from __future__ import annotations

import pytest

from accessible_surfaceome.cloud.record_history.rate_limit import (
    DEFAULT_D1_QPS,
    QPS_ENV_VAR,
    RateLimiter,
    d1_qps_from_env,
)


class FakeClock:
    """A monotonically-advancing fake clock; `sleep` just advances it."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_enforces_minimum_interval_between_acquires() -> None:
    fc = FakeClock()
    limiter = RateLimiter(2.0, clock=fc.clock, sleep=fc.sleep)  # 0.5s interval

    limiter.acquire()  # first call: no wait
    limiter.acquire()  # second call: must wait ~0.5s

    assert fc.slept == [0.5]
    assert fc.now == pytest.approx(0.5)


def test_no_wait_when_calls_are_already_spaced_out() -> None:
    fc = FakeClock()
    limiter = RateLimiter(2.0, clock=fc.clock, sleep=fc.sleep)  # 0.5s interval

    limiter.acquire()
    fc.now += 10.0  # plenty of real time passed between calls
    limiter.acquire()

    assert fc.slept == []  # no throttling needed


def test_qps_zero_disables_limiting_entirely() -> None:
    fc = FakeClock()
    limiter = RateLimiter(0, clock=fc.clock, sleep=fc.sleep)

    assert limiter.enabled is False
    for _ in range(5):
        limiter.acquire()

    assert fc.slept == []


def test_negative_qps_also_disables() -> None:
    limiter = RateLimiter(-1)
    assert limiter.enabled is False


def test_three_calls_pace_to_two_intervals() -> None:
    fc = FakeClock()
    limiter = RateLimiter(10.0, clock=fc.clock, sleep=fc.sleep)  # 0.1s interval

    for _ in range(3):
        limiter.acquire()

    assert fc.slept == [pytest.approx(0.1), pytest.approx(0.1)]


def test_default_qps_from_env_is_two_point_five(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(QPS_ENV_VAR, raising=False)
    assert d1_qps_from_env() == DEFAULT_D1_QPS == 2.5


def test_qps_from_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(QPS_ENV_VAR, "0")
    assert d1_qps_from_env() == 0.0

    monkeypatch.setenv(QPS_ENV_VAR, "7.5")
    assert d1_qps_from_env() == 7.5


def test_qps_from_env_garbage_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(QPS_ENV_VAR, "not-a-number")
    assert d1_qps_from_env() == DEFAULT_D1_QPS


def test_concurrent_acquires_are_serialized_and_all_paced() -> None:
    """Thread-safety smoke test: N threads racing `acquire()` must each get
    a distinct, monotonically increasing slot — never two threads computing
    the same `wait` from a torn read of `_next_allowed`."""
    import threading

    fc = FakeClock()
    lock = threading.Lock()
    limiter = RateLimiter(100.0, clock=fc.clock, sleep=lambda s: None)  # no real wait

    # Patch the limiter's internal clock reads to be thread-safe under the
    # fake (real time.monotonic is thread-safe already; the fake needs the
    # same guarantee for this test to be meaningful).
    orig_clock = limiter._clock

    def safe_clock() -> float:
        with lock:
            return orig_clock()

    limiter._clock = safe_clock  # type: ignore[assignment]

    results: list[float] = []
    results_lock = threading.Lock()

    def worker() -> None:
        limiter.acquire()
        with results_lock:
            results.append(limiter._next_allowed)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 20 distinct scheduled slots, each 0.01s apart (100 qps).
    assert len(set(results)) == 20
