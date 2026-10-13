"""Guard: Supp S1's precomputed points are scored against the current bench.

``data/processed/triage_bench/db_cutoff_tradeoff_points.tsv`` is a frozen,
committed artifact — ``scripts/figures/db_cutoff_tradeoff.py`` reads it and is
explicitly forbidden from recomputing. Freezing it stops a stray render from
silently overwriting the published numbers, but with no link back to the
curated benchmark it also let the file outlive its own truth.

It did. The file encoded a **98 surface / 49 non-surface** split — the state
before 2026-06-07, when HMGB1 was corrected from ``no`` to ``contextual``
(commit a98afa880 took the bench to 99/48). Every recall in Supp S1 was
therefore divided by 98 against a curated 99, and one gene was scored on the
wrong side. All 17 plotted points were off by roughly a percentage point on
each axis. No conclusion changed, but no test noticed for four months.

``tests/test_mainbench_truth_drift.py`` pins the curated TSV itself; this pins
the derived artifact to it, which is where the drift actually happened.

HPA is deliberately exempt: only part of the benchmark has HPA coverage, so its
points use their own smaller denominators by design.
"""
from __future__ import annotations

import csv
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data/eval/triage_benchmark_v1.tsv"
POINTS = ROOT / "data/processed/triage_bench/db_cutoff_tradeoff_points.tsv"

# Coverage-restricted sources score against the subset they cover, not the
# whole benchmark, so their denominators legitimately differ.
PARTIAL_COVERAGE_GROUPS = {"HPA"}


def _bench_split() -> tuple[int, int]:
    """(surface, non-surface) under the soft-credit rule the figures use."""
    surface = non_surface = 0
    with BENCH.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            verdict = (row.get("ground_truth_verdict") or "").strip().lower()
            if verdict in {"yes", "contextual"}:
                surface += 1
            elif verdict == "no":
                non_surface += 1
    return surface, non_surface


def _denominator(value: str) -> int:
    """Smallest denominator that reproduces the stored fraction exactly."""
    return Fraction(float(value)).limit_denominator(1000).denominator


def test_cutoff_points_use_the_current_bench_denominators() -> None:
    surface, non_surface = _bench_split()
    bad: list[str] = []
    with POINTS.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["group"] in PARTIAL_COVERAGE_GROUPS:
                continue
            label = f"{row['group']} · {row['label'].replace(chr(10), ' ')}"
            # 0 and 1 carry no denominator information; skip them rather than
            # pretend they confirm anything.
            for axis, total in (("pos", surface), ("neg", non_surface)):
                value = float(row[axis])
                if value in (0.0, 1.0):
                    continue
                if total % _denominator(row[axis]) != 0:
                    bad.append(
                        f"{label}: {axis}={row[axis]} implies a denominator of "
                        f"{_denominator(row[axis])}, which does not divide the "
                        f"curated {total}"
                    )
    assert not bad, (
        "db_cutoff_tradeoff_points.tsv was scored against a different benchmark "
        "than data/eval/triage_benchmark_v1.tsv now holds "
        f"({surface} surface / {non_surface} non-surface). Regenerate it:\n"
        "    DUMP_CUTOFF_POINTS=1 uv run python -c \"import importlib.util,pathlib;"
        "s=importlib.util.spec_from_file_location('m','scripts/figures/triage_bench_db_barplot.py');"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "m.make_db_tradeoff_plot(pathlib.Path('data/analysis/triage_bench'))\"\n"
        "then re-render scripts/figures/db_cutoff_tradeoff.py.\n  "
        + "\n  ".join(bad)
    )
