"""Regression tests for data/eval/triage_benchmark_v1.tsv.

Catches the kinds of benchmark-drift bugs that have bitten us before:

* `ground_truth_verdict` outside the schema's `TriageVerdict` literals
* `ground_truth_reason` outside the schema's `TriageReason` literals
* (verdict, reason) pair that the TriageRecordDraft model_validator rejects
* signal value outside the documented set

The benchmark is the gold-standard reference for the surface_triage eval —
if the TSV silently drifts away from the schema, scoring runs go quiet
instead of failing. Block that here.
"""

from __future__ import annotations

import pytest

from accessible_surfaceome.agents._eval.benchmark import load_benchmark
from accessible_surfaceome.tools._shared.models import (
    GeneIdentifier,
    TriageRecordDraft,
    _REASONS_BY_VERDICT,
)

_ALLOWED_VERDICTS = frozenset({"yes", "contextual", "no"})
_ALLOWED_SIGNALS = frozenset(
    {"likely_accessible", "possibly_accessible", "unlikely", "unknown"}
)


@pytest.fixture(scope="module")
def benchmark_rows() -> list:
    return load_benchmark()


def test_benchmark_non_empty(benchmark_rows: list) -> None:
    assert len(benchmark_rows) > 0, "benchmark TSV produced zero rows"


def test_every_verdict_is_schema_literal(benchmark_rows: list) -> None:
    bad = [
        (r.gene_symbol, r.ground_truth_verdict)
        for r in benchmark_rows
        if r.ground_truth_verdict not in _ALLOWED_VERDICTS
    ]
    assert not bad, f"non-schema verdicts: {bad}"


def test_every_signal_is_recognised(benchmark_rows: list) -> None:
    bad = [
        (r.gene_symbol, r.ground_truth_signal)
        for r in benchmark_rows
        if r.ground_truth_signal not in _ALLOWED_SIGNALS
    ]
    assert not bad, f"unrecognised signals: {bad}"


def test_every_reason_is_set(benchmark_rows: list) -> None:
    missing = [r.gene_symbol for r in benchmark_rows if not r.ground_truth_reason.strip()]
    assert not missing, f"rows missing ground_truth_reason: {missing}"


def test_every_reason_matches_verdict_via_schema(benchmark_rows: list) -> None:
    """Construct a TriageRecordDraft per row; rely on the model_validator."""
    failures: list[str] = []
    for r in benchmark_rows:
        for reason in r.accepted_reasons:
            try:
                TriageRecordDraft(
                    gene=GeneIdentifier(
                        hgnc_symbol=r.gene_symbol,
                        hgnc_id="HGNC:0",  # placeholder; schema only checks shape
                        uniprot_acc=r.uniprot_acc,
                    ),
                    verdict=r.ground_truth_verdict,
                    verdict_reasoning="benchmark roundtrip",
                    reason=reason,
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    f"{r.gene_symbol} ({r.ground_truth_verdict} / {reason}): {exc}"
                )
    assert not failures, "\n".join(failures)


def test_reason_is_in_allowed_set_for_verdict(benchmark_rows: list) -> None:
    """Belt-and-braces companion to the model_validator check.

    Spells out the failure mode rather than letting the validator's
    error message be the only signal. Catches reasons that are in
    `TriageReason` but disallowed for the row's verdict (e.g. `gpi_anchored`
    on a `no` row).
    """
    failures: list[str] = []
    for r in benchmark_rows:
        allowed = _REASONS_BY_VERDICT.get(r.ground_truth_verdict, frozenset())
        for reason in r.accepted_reasons:
            if reason not in allowed:
                failures.append(
                    f"{r.gene_symbol}: reason={reason!r} not allowed for verdict={r.ground_truth_verdict!r}"
                )
    assert not failures, "\n".join(failures)
