from __future__ import annotations

import pytest

from accessible_surfaceome.tools._shared.ratelimit import (
    RateLimiter,
    default_limiter,
    reserve_slot,
    set_external_rate_limit_gate,
)


def teardown_function() -> None:
    set_external_rate_limit_gate(None)


def _recorder(calls: list[tuple[str, float]], wait: float = 0.0):
    """A gate hook that records (state_key, interval_s) and returns ``wait``.

    The gate contract is now ``-> float`` (seconds for the caller to sleep);
    these gates return 0.0 so the limiter does not actually sleep in the test.
    """

    def gate(state_key: str, interval_s: float) -> float:
        calls.append((state_key, interval_s))
        return wait

    return gate


def test_external_gate_receives_host_and_interval() -> None:
    calls: list[tuple[str, float]] = []
    set_external_rate_limit_gate(_recorder(calls))

    limiter = RateLimiter({"example.org": 250})
    limiter.wait("https://example.org/resource")

    assert calls == [("example.org", 0.25)]


def test_external_gate_hashes_sensitive_buckets() -> None:
    calls: list[tuple[str, float]] = []
    secret = "ncbi-secret-key"
    set_external_rate_limit_gate(_recorder(calls))

    limiter = RateLimiter({"eutils.ncbi.nlm.nih.gov": 350})
    limiter.wait(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        bucket=f"api_key:{secret}",
        interval_ms=110,
    )

    assert len(calls) == 1
    state_key, interval_s = calls[0]
    assert state_key.startswith("eutils.ncbi.nlm.nih.gov\0bucket:")
    assert secret not in state_key
    assert "api_key" not in state_key
    assert interval_s == 0.11


def test_external_gate_not_called_for_unlimited_host() -> None:
    calls: list[tuple[str, float]] = []
    set_external_rate_limit_gate(_recorder(calls))

    limiter = RateLimiter({})
    limiter.wait("https://unlimited.example/resource")

    assert calls == []


def test_caller_sleeps_for_gate_returned_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate returns the wait; the limiter sleeps locally (not the gate)."""
    slept: list[float] = []
    monkeypatch.setattr(
        "accessible_surfaceome.tools._shared.ratelimit.time.sleep",
        lambda s: slept.append(s),
    )
    set_external_rate_limit_gate(lambda _k, _i: 0.5)

    RateLimiter({"example.org": 250}).wait("https://example.org/x")

    assert slept == [0.5]


def test_zero_or_negative_gate_wait_does_not_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr(
        "accessible_surfaceome.tools._shared.ratelimit.time.sleep",
        lambda s: slept.append(s),
    )
    set_external_rate_limit_gate(lambda _k, _i: 0.0)

    RateLimiter({"example.org": 250}).wait("https://example.org/x")

    assert slept == []


def test_reserve_slot_first_call_no_wait() -> None:
    assert reserve_slot({}, "k", 0.25, now=100.0) == 0.0


def test_reserve_slot_zero_interval_no_wait() -> None:
    assert reserve_slot({}, "k", 0.0, now=100.0) == 0.0


def test_reserve_slot_monotonic_increasing_for_one_key() -> None:
    table: dict[str, float] = {}
    waits = [reserve_slot(table, "k", 0.25, now=100.0) for _ in range(4)]
    assert waits == pytest.approx([0.0, 0.25, 0.5, 0.75])


def test_reserve_slot_keys_are_independent() -> None:
    table: dict[str, float] = {}
    reserve_slot(table, "a", 0.25, now=100.0)
    reserve_slot(table, "a", 0.25, now=100.0)  # queue up key "a"
    # key "b" is its own schedule line — unaffected by a's queue.
    assert reserve_slot(table, "b", 0.25, now=100.0) == 0.0


def test_reserve_slot_consumes_elapsed_real_time() -> None:
    table: dict[str, float] = {}
    reserve_slot(table, "k", 1.0, now=100.0)  # reserves t=100
    # One full interval later, the next call needs no wait.
    assert reserve_slot(table, "k", 1.0, now=101.0) == pytest.approx(0.0)


def test_reserve_slot_caps_wait_under_heavy_contention() -> None:
    table: dict[str, float] = {}
    # 1000 back-to-back reservations on a 1 qps key would queue ~1000s without
    # a cap; max_wait_s degrades it to a bounded over-rate instead.
    for _ in range(1000):
        reserve_slot(table, "k", 1.0, now=100.0, max_wait_s=5.0)
    assert reserve_slot(table, "k", 1.0, now=100.0, max_wait_s=5.0) == 5.0


def test_oa_hosts_are_throttled() -> None:
    """Unpaywall / DataCite / Crossref Labs must have a per-host cap so they
    don't pass through at interval=0 under Modal fan-out."""
    limiter = default_limiter()
    for host in ("api.unpaywall.org", "api.datacite.org", "api.labs.crossref.org"):
        assert limiter._intervals_ms.get(host, 0.0) > 0.0, host
