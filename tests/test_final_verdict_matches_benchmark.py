"""Final-verdict round-trip test — locks the synth's
``(surface_accessibility, surface_call_reason)`` pair to the
benchmark's ``ground_truth_verdict`` for 5 genes that previously had
no CI coverage at the verdict level: **HMGB1, C3, ABCB9, LYN, BAX**.

Why this exists separately from ``test_pipeline_validation_genes.py``:
that suite asserts field-by-field expectations (one row per
(gene, field) pair) but never composes the synth's two-field call
(``sa``, ``scr``) back into the triage-style verdict the benchmark
uses. A drift where the synth, e.g., calls ABCB9 ``sa=low`` +
``scr=dual_localization`` would map to ``contextual`` while the
benchmark says ``no`` — neither the field tests nor the cross-block
validators catch that round-trip on their own.

The mapping ``synth_to_triage_verdict`` below is the load-bearing
piece; it encodes the bucket partitioning of ``surface_call_reason``
documented in
``src/accessible_surfaceome/agents/surfaceome_synthesizer/prompts/system.md``
(YES / CONTEXTUAL / NO buckets). When that bucketing changes, update
this helper in lockstep — the test fails otherwise and points at the
gene whose call has flipped.

**Failure protocol.** A red here is one of two things:

1. The synth made a wrong call → re-annotate
   (``scripts/surfaceome_v2_annotate.py <SYMBOL>``) after fixing the
   prompt section that owns the relevant bucket.
2. The benchmark needs updating → only if the literature has actually
   shifted; treat this case skeptically because the 5 genes were
   chosen as canonical archetypes.

**Auto-skip.** Mirrors ``test_pipeline_validation_genes.py``: when
``CLOUDFLARE_API_TOKEN`` is unset (offline CI smoke), the fixture
``pytest.skip``s. CI has the token; local runs without ``.env``
loaded will skip cleanly.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import httpx
import pytest

_PUBLIC_API = "https://api.deliverome.org/surfaceome/v1/genes"

# Genes under test. Picked because they had no verdict-level CI
# coverage and span the three triage buckets (HMGB1, C3 → contextual;
# ABCB9, LYN, BAX → no). No 'yes' archetype here intentionally — the
# existing pipeline_validation_genes suite has heavy YES-bucket coverage
# (TACSTD2, PVRIG, SRC); the gap was 'contextual' + 'no' round-trips.
_BENCH_GENES: tuple[str, ...] = ("HMGB1", "C3", "ABCB9", "LYN", "BAX")

_BENCHMARK_TSV = (
    Path(__file__).resolve().parent.parent
    / "data" / "eval" / "triage_benchmark_v1.tsv"
)


# ---- surface_call_reason bucket constants ----
#
# Source of truth:
#   src/accessible_surfaceome/agents/surfaceome_synthesizer/prompts/system.md
#   ("YES-bucket" / "CONTEXTUAL-bucket" / "NO-bucket" section under
#   surface_call_reason).
#
# `other` is allowed in ALL three buckets — partitioning falls back to
# the polarity of `surface_accessibility` (see synth_to_triage_verdict).
_YES_BUCKET: frozenset[str] = frozenset({
    "classical_surface_receptor",
    "gpi_anchored",
    "multipass_with_exposed_loops",
    "extracellular_face_protein",
    "stable_complex_partner",
})
_CONTEXTUAL_BUCKET: frozenset[str] = frozenset({
    "cell_state_induced",
    "tissue_restricted_surface",
    "lysosomal_exocytosis",
    "dual_localization",
    "stable_surface_attachment",
})
_NO_BUCKET: frozenset[str] = frozenset({
    "cytoplasmic",
    "nuclear",
    "mitochondrial_internal",
    "endomembrane_resident",
    "nuclear_envelope",
    "inner_leaflet_anchored",
    "secreted_only",
    "pmhc_only_intracellular",
})


def synth_to_triage_verdict(sa: str, scr: str) -> str:
    """Map the synth's ``(surface_accessibility, surface_call_reason)``
    pair to the triage verdict the benchmark uses
    (``yes`` / ``contextual`` / ``no``).

    Rules (from the bucket partitioning in the synth prompt's
    ``surface_call_reason`` section):

    * ``sa == 'no'`` → ``'no'`` (regardless of ``scr``)
    * ``sa == 'low'`` → ``'contextual'`` (some-state surface access)
    * ``sa ∈ {high, moderate}`` AND ``scr ∈ YES_BUCKET`` → ``'yes'``
    * ``sa ∈ {high, moderate}`` AND ``scr ∈ CONTEXTUAL_BUCKET``
      → ``'contextual'``
    * ``sa ∈ {high, moderate}`` AND ``scr == 'other'`` → ``'yes'``
      (sa polarity wins when ``scr`` is the catch-all)

    Returns a sentinel string starting with ``INCONSISTENT(`` when the
    pair is internally inconsistent (sa=high/moderate paired with a
    NO-bucket scr), or ``UNKNOWN_SCR(`` for an out-of-enum scr. Both
    fail the equality assertion cleanly with a self-documenting message
    rather than silently coercing to a verdict.
    """
    if sa == "no":
        return "no"
    if sa == "low":
        return "contextual"
    # sa ∈ {high, moderate}
    if scr in _YES_BUCKET:
        return "yes"
    if scr in _CONTEXTUAL_BUCKET:
        return "contextual"
    if scr in _NO_BUCKET:
        # sa=high/mod with a NO-bucket scr is a validator-caught
        # inconsistency upstream; surface it rather than guess.
        return f"INCONSISTENT(sa={sa},scr={scr})"
    if scr == "other":
        return "yes"
    return f"UNKNOWN_SCR({scr})"


def _load_ground_truth() -> dict[str, dict[str, str]]:
    """Read the 5 benchmark rows once at module import.

    The benchmark TSV is small (148 rows total) and shipped in-repo, so
    loading it at module scope (not inside a fixture) is the cleanest
    pattern — pytest collection is fast and the data is static.

    Returns ``{gene_symbol: {field: value, ...}}`` for the 5 target
    genes; raises ``RuntimeError`` if any gene is missing from the TSV
    (a typo here would silently pass the parameterized test).
    """
    by_gene: dict[str, dict[str, str]] = {}
    with _BENCHMARK_TSV.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            sym = row.get("gene_symbol", "")
            if sym in _BENCH_GENES:
                by_gene[sym] = row
    missing = [g for g in _BENCH_GENES if g not in by_gene]
    if missing:
        raise RuntimeError(
            f"Benchmark TSV at {_BENCHMARK_TSV} is missing target genes: "
            f"{missing}. Either the benchmark was rebuilt without these "
            f"genes (update _BENCH_GENES) or the TSV path is wrong."
        )
    return by_gene


_GROUND_TRUTH: dict[str, dict[str, str]] = _load_ground_truth()


@pytest.fixture(scope="session")
def records() -> dict[str, dict[str, Any]]:
    """Fetch all 5 records from the public Worker once per session.

    Auto-skips when ``CLOUDFLARE_API_TOKEN`` is unset — same offline-CI
    pattern as :mod:`tests.test_pipeline_validation_genes`. The Worker
    is open-read (no auth header), but the env var is a clean
    "is this a network-enabled run" gate.
    """
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        pytest.skip(
            "CLOUDFLARE_API_TOKEN not set — final-verdict tests skipped "
            "in offline CI smoke. Run with .env loaded to enable."
        )

    out: dict[str, dict[str, Any]] = {}
    with httpx.Client(timeout=30.0) as c:
        for sym in _BENCH_GENES:
            try:
                r = c.get(f"{_PUBLIC_API}/{sym}")
                r.raise_for_status()
                out[sym] = r.json()
            except (httpx.HTTPError, ValueError) as exc:
                pytest.skip(
                    f"Worker unreachable / returned non-JSON for {sym}: "
                    f"{exc!r} — final-verdict tests can't run without a "
                    f"live public API."
                )
    return out


@pytest.mark.parametrize("gene", _BENCH_GENES)
def test_synth_verdict_matches_benchmark(
    records: dict[str, dict[str, Any]],
    gene: str,
) -> None:
    """Round-trip the synth's ``(sa, scr)`` to a triage verdict and
    assert it matches the benchmark ``ground_truth_verdict``.

    Failure message includes (gene, expected, sa, scr, derived
    verdict, and the benchmark's ``ground_truth_reason``) so the
    operator can decide between re-annotation and benchmark update
    without leaving the diff.
    """
    truth_row = _GROUND_TRUTH[gene]
    expected = truth_row["ground_truth_verdict"]

    record = records[gene]
    exec_summary = record.get("executive_summary") or {}
    sa = exec_summary.get("surface_accessibility")
    scr = exec_summary.get("surface_call_reason")

    assert sa is not None, (
        f"\n  Gene: {gene}"
        f"\n  Missing executive_summary.surface_accessibility on the "
        f"record. Worker probably served a stale schema or a non-200 "
        f"response. Re-annotate via "
        f"scripts/surfaceome_v2_annotate.py {gene}."
    )
    assert scr is not None, (
        f"\n  Gene: {gene}"
        f"\n  Missing executive_summary.surface_call_reason on the "
        f"record. Re-annotate via "
        f"scripts/surfaceome_v2_annotate.py {gene}."
    )

    derived = synth_to_triage_verdict(sa, scr)
    assert derived == expected, (
        f"\n  Gene:               {gene}"
        f"\n  Benchmark verdict:  {expected!r}"
        f"\n  Synth sa:           {sa!r}"
        f"\n  Synth scr:          {scr!r}"
        f"\n  Derived verdict:    {derived!r}"
        f"\n  Benchmark reason:   {truth_row.get('ground_truth_reason')!r}"
        f"\n  Benchmark signal:   {truth_row.get('ground_truth_signal')!r}"
        f"\n  ---"
        f"\n  Map: sa=no → no | sa=low → contextual | "
        f"sa∈{{high,moderate}} + scr∈YES_BUCKET → yes | "
        f"sa∈{{high,moderate}} + scr∈CONTEXTUAL_BUCKET → contextual."
        f"\n  Owner: synth surface_call_reason bucket partitioning in "
        f"surfaceome_synthesizer/prompts/system.md."
        f"\n  Decide: re-annotate the synth (most likely) OR update the "
        f"benchmark only if the literature has actually shifted."
    )


def test_all_target_genes_in_benchmark() -> None:
    """Sanity guard: every gene in :data:`_BENCH_GENES` resolves in the
    benchmark TSV. Without this, a typo in ``_BENCH_GENES`` would
    silently pass the round-trip test (KeyError on the parameterized
    row → fixture skip)."""
    missing = [g for g in _BENCH_GENES if g not in _GROUND_TRUTH]
    assert not missing, (
        f"Target genes missing from {_BENCHMARK_TSV.name}: {missing}. "
        f"Fix the symbol list or refresh the benchmark."
    )


# ---- Unit tests for synth_to_triage_verdict (offline-safe) ----
#
# These don't need the Worker, so they run in every CI smoke pass and
# guard the mapping helper itself. If someone edits the bucket
# partitioning in the synth prompt without updating this helper, these
# tests catch it before the network-dependent ones even try.

@pytest.mark.parametrize(
    "sa,scr,expected",
    [
        # NO via sa polarity (scr irrelevant)
        ("no", "cytoplasmic", "no"),
        ("no", "classical_surface_receptor", "no"),  # inconsistent upstream, sa wins
        # LOW always contextual
        ("low", "dual_localization", "contextual"),
        ("low", "endomembrane_resident", "contextual"),
        # YES bucket pairings
        ("high", "classical_surface_receptor", "yes"),
        ("moderate", "gpi_anchored", "yes"),
        ("moderate", "stable_complex_partner", "yes"),
        # CONTEXTUAL bucket pairings
        ("moderate", "cell_state_induced", "contextual"),
        ("high", "stable_surface_attachment", "contextual"),
        ("moderate", "tissue_restricted_surface", "contextual"),
        # `other` falls back to sa polarity at high/moderate
        ("high", "other", "yes"),
        ("moderate", "other", "yes"),
        # Inconsistency surfaced rather than coerced
        ("high", "cytoplasmic", "INCONSISTENT(sa=high,scr=cytoplasmic)"),
        ("moderate", "secreted_only", "INCONSISTENT(sa=moderate,scr=secreted_only)"),
        # Out-of-enum scr surfaced rather than silently coerced
        ("high", "totally_made_up_value", "UNKNOWN_SCR(totally_made_up_value)"),
    ],
)
def test_synth_to_triage_verdict_mapping(
    sa: str, scr: str, expected: str
) -> None:
    """Pin the bucket partitioning. Update in lockstep with the synth
    prompt's surface_call_reason section."""
    assert synth_to_triage_verdict(sa, scr) == expected


def test_bucket_partitions_are_disjoint() -> None:
    """The three buckets must be mutually exclusive — overlap means
    the helper's lookup order silently picks a winner and the round-
    trip becomes order-dependent."""
    overlap_yes_ctx = _YES_BUCKET & _CONTEXTUAL_BUCKET
    overlap_yes_no = _YES_BUCKET & _NO_BUCKET
    overlap_ctx_no = _CONTEXTUAL_BUCKET & _NO_BUCKET
    assert not overlap_yes_ctx, (
        f"YES and CONTEXTUAL buckets overlap: {sorted(overlap_yes_ctx)}. "
        f"Pick one bucket per scr value in the synth prompt."
    )
    assert not overlap_yes_no, (
        f"YES and NO buckets overlap: {sorted(overlap_yes_no)}."
    )
    assert not overlap_ctx_no, (
        f"CONTEXTUAL and NO buckets overlap: {sorted(overlap_ctx_no)}."
    )
