from __future__ import annotations

from accessible_surfaceome.tools._shared.ratelimit import (
    RateLimiter,
    set_external_rate_limit_gate,
)


def teardown_function() -> None:
    set_external_rate_limit_gate(None)


def test_external_gate_receives_host_and_interval() -> None:
    calls: list[tuple[str, float]] = []

    set_external_rate_limit_gate(lambda state_key, interval_s: calls.append((state_key, interval_s)))

    limiter = RateLimiter({"example.org": 250})
    limiter.wait("https://example.org/resource")

    assert calls == [("example.org", 0.25)]


def test_external_gate_hashes_sensitive_buckets() -> None:
    calls: list[tuple[str, float]] = []
    secret = "ncbi-secret-key"

    set_external_rate_limit_gate(lambda state_key, interval_s: calls.append((state_key, interval_s)))

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

    set_external_rate_limit_gate(lambda state_key, interval_s: calls.append((state_key, interval_s)))

    limiter = RateLimiter({})
    limiter.wait("https://unlimited.example/resource")

    assert calls == []
