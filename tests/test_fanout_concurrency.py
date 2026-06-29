"""Tests for the OTPM-derived Modal fan-out sizing (``_support.concurrency``).

Distinct from ``test_concurrency.py`` (which covers in-gene builder/trim
thread-pool parallelism). This pins the cross-gene fan-out cap that keeps the
sweep's aggregate Anthropic output rate under the OTPM ceiling.
"""

from __future__ import annotations

import pytest

from accessible_surfaceome.agents._support.concurrency import (
    SONNET_OTPM_LIMIT,
    per_gene_otpm,
    recommended_gene_concurrency,
    resolve_gene_concurrency,
)


def test_per_gene_otpm_is_tokens_per_minute() -> None:
    # 90k tokens over a 300s (5 min) gene → 18k output tok/min.
    assert per_gene_otpm(90_000, 300.0) == pytest.approx(18_000.0)


def test_recommended_concurrency_default_is_otpm_bound() -> None:
    # 0.6 × 2M ÷ 18k ≈ 66 — an order of magnitude below the old 800 fan-out.
    n = recommended_gene_concurrency()
    assert 50 <= n <= 80


def test_recommended_concurrency_scales_with_headroom() -> None:
    assert recommended_gene_concurrency(headroom=0.3) < recommended_gene_concurrency(
        headroom=0.9
    )


def test_recommended_concurrency_never_below_one() -> None:
    # A pathologically output-heavy gene still yields at least one worker.
    assert recommended_gene_concurrency(output_tokens=10_000_000, gene_wall_s=1.0) == 1


def test_projected_otpm_stays_under_limit_at_recommended() -> None:
    assert recommended_gene_concurrency() * per_gene_otpm() < SONNET_OTPM_LIMIT


def test_resolve_reads_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SURFACEOME_MAX_CONTAINERS", "32")
    monkeypatch.setenv("SURFACEOME_MAX_INPUTS", "2")
    assert resolve_gene_concurrency() == (32, 2)


def test_resolve_defaults_containers_to_recommendation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in (
        "SURFACEOME_MAX_CONTAINERS",
        "SURFACEOME_MAX_INPUTS",
        "SURFACEOME_PER_GENE_OTPM",
        "SURFACEOME_GENE_WALL_S",
    ):
        monkeypatch.delenv(var, raising=False)
    containers, inputs = resolve_gene_concurrency()
    assert containers == recommended_gene_concurrency()
    assert inputs == 1


def test_resolve_honors_per_gene_output_tokens_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SURFACEOME_MAX_CONTAINERS", raising=False)
    monkeypatch.delenv("SURFACEOME_MAX_INPUTS", raising=False)
    # Doubling the per-gene output estimate halves the recommended concurrency.
    monkeypatch.setenv("SURFACEOME_PER_GENE_OUTPUT_TOKENS", "180000")
    containers, _ = resolve_gene_concurrency()
    assert containers == recommended_gene_concurrency(output_tokens=180_000)


def test_raising_inputs_alone_keeps_total_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting MAX_INPUTS without MAX_CONTAINERS must NOT multiply total
    concurrency past the OTPM recommendation (P1-2)."""
    for var in (
        "SURFACEOME_MAX_CONTAINERS",
        "SURFACEOME_PER_GENE_OUTPUT_TOKENS",
        "SURFACEOME_GENE_WALL_S",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SURFACEOME_MAX_INPUTS", "2")
    containers, inputs = resolve_gene_concurrency()
    assert inputs == 2
    total = containers * inputs
    rec = recommended_gene_concurrency()
    # Total stays within one input's worth of the recommendation, not 2× it.
    assert rec - inputs <= total <= rec


def test_explicit_overcommit_is_honored_with_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An explicit container count is honored (operator override wins) but the
    over-OTPM case is warned, not silently clamped."""
    monkeypatch.setenv("SURFACEOME_MAX_CONTAINERS", "200")
    monkeypatch.setenv("SURFACEOME_MAX_INPUTS", "4")
    with caplog.at_level("WARNING"):
        assert resolve_gene_concurrency() == (200, 4)
    assert any("exceeds the OTPM-safe recommendation" in r.message for r in caplog.records)
