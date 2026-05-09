"""Benchmark loader + programmatic OpenCell-vesicle augmentation.

Reads ``data/eval/triage_benchmark_v1.tsv`` (the named 23-protein core)
and, on demand, augments it with the top-K OpenCell-vesicle-in-M1
proteins ranked by ``n_sources_voting_surface``. Those programmatic
additions get appended to the loaded list with class
``opencell_vesicle_negative_programmatic`` and the standard
``ground_truth_verdict=no, ground_truth_signal=unlikely`` labels.

The augmented benchmark is the cohort every variant runs against.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from accessible_surfaceome.paths import DATA_DIR

BENCHMARK_TSV_DEFAULT = DATA_DIR / "eval" / "triage_benchmark_v1.tsv"
OPENCELL_TSV = DATA_DIR / "processed" / "controls" / "opencell_grade3_vesicles_non_membrane_in_m1.tsv"
CANDIDATE_UNIVERSE_TSV = DATA_DIR / "processed" / "candidate_universe" / "candidate_universe.tsv"


@dataclass(frozen=True)
class BenchmarkRow:
    gene_symbol: str
    uniprot_acc: str
    class_: str
    ground_truth_verdict: str  # "yes" | "maybe" | "no"
    ground_truth_signal: str  # "likely_accessible" | "possibly_accessible" | "unlikely" | "unknown"
    rationale: str


def load_benchmark(
    *,
    benchmark_tsv: Path = BENCHMARK_TSV_DEFAULT,
    opencell_top_k: int = 0,
) -> list[BenchmarkRow]:
    """Load the named benchmark TSV plus top-K programmatic OpenCell adds.

    The named rows come from the curated TSV. The programmatic rows come
    from joining ``opencell_grade3_vesicles_non_membrane_in_m1.tsv`` with
    the candidate-universe vote panel, sorting by descending
    ``n_sources_surface``, and taking the top K that aren't already in
    the named list. They are added with verdict=no, signal=unlikely.

    .. warning:: ``opencell_top_k`` defaults to ``0`` because the
        highest-M1-vote OpenCell entries (ATP1A1, SLC2A1, CD63, ...) are
        canonical PM proteins that *also* show vesicular grade-3
        signal. The OpenCell vesicular annotation doesn't preclude PM
        presence. Setting top-K > 0 would inject mislabeled negatives
        (verdict=no) for proteins that are actually surface-accessible.
        Use top-K > 0 only after manually filtering the candidates.
    """

    named = list(_iter_tsv_rows(benchmark_tsv))
    if opencell_top_k <= 0:
        return named

    named_symbols = {row.gene_symbol for row in named}
    programmatic = _top_k_opencell_programmatic(
        named_symbols=named_symbols, k=opencell_top_k
    )
    return named + programmatic


def _iter_tsv_rows(path: Path) -> Iterator[BenchmarkRow]:
    with path.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for raw in reader:
            yield BenchmarkRow(
                gene_symbol=raw["gene_symbol"],
                uniprot_acc=raw["uniprot_acc"],
                class_=raw["class"],
                ground_truth_verdict=raw["ground_truth_verdict"],
                ground_truth_signal=raw["ground_truth_signal"],
                rationale=raw["rationale"],
            )


def _top_k_opencell_programmatic(
    *, named_symbols: set[str], k: int
) -> list[BenchmarkRow]:
    """Pull top-K OpenCell-vesicle proteins by M1 vote count, excluding named ones.

    The OpenCell TSV gives gene_symbol; the candidate-universe TSV gives
    n_sources_surface. We join on gene_symbol, sort descending by votes,
    and take the first K that aren't in ``named_symbols``.
    """

    if not OPENCELL_TSV.exists() or not CANDIDATE_UNIVERSE_TSV.exists():
        return []

    opencell_symbols: set[str] = set()
    with OPENCELL_TSV.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            sym = (row.get("gene_symbol") or "").strip()
            if sym:
                opencell_symbols.add(sym)

    # Walk candidate universe, keep rows that are in the OpenCell set and
    # not already named. Sort by n_sources_surface desc.
    pool: list[tuple[int, str, str]] = []  # (n_votes, gene_symbol, uniprot_acc)
    with CANDIDATE_UNIVERSE_TSV.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            sym = (row.get("gene_symbol") or "").strip()
            if not sym or sym in named_symbols or sym not in opencell_symbols:
                continue
            try:
                n_votes = int(row.get("n_sources_surface") or row.get("n_sources_voting_surface") or 0)
            except (TypeError, ValueError):
                n_votes = 0
            uniprot_acc = (
                row.get("uniprot_accession")
                or row.get("uniprot_id")
                or row.get("uniprot_acc")
                or ""
            ).strip()
            if not uniprot_acc:
                continue
            pool.append((n_votes, sym, uniprot_acc))

    pool.sort(key=lambda t: (-t[0], t[1]))
    top = pool[:k]
    return [
        BenchmarkRow(
            gene_symbol=sym,
            uniprot_acc=acc,
            class_="opencell_vesicle_negative_programmatic",
            ground_truth_verdict="no",
            ground_truth_signal="unlikely",
            rationale=(
                f"OpenCell grade-3 vesicle in M1 with {n_votes} surface-source "
                f"votes; imaged-confirmed intracellular"
            ),
        )
        for n_votes, sym, acc in top
    ]


__all__ = ["BenchmarkRow", "load_benchmark", "BENCHMARK_TSV_DEFAULT"]
