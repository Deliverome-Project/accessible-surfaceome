"""Per-database baselines for the triage benchmark.

For each M1 source database (excluding DeepTMHMM, which we removed from
the triage stack), computes the binary classification metrics — accuracy,
recall on the accessible class, specificity on the inaccessible class,
and F2 — against the benchmark ground truth.

Mapping:
* DB vote = ``true``  → predicted accessible (1)
* DB vote = ``false`` → predicted skip       (0)
* Truth   = yes|contextual → 1
* Truth   = no        → 0
* Proteins not in M1 are treated as DB-vote=0 across the board (failed
  every M1 rule).

We weight recall higher than precision via F2 because the operational
cost of a false negative (silently dropping a real candidate from the
genome-wide queue) is higher than the cost of a false positive (one
extra protein in the deep-dive queue).

Usage::

    from accessible_surfaceome.agents._eval.database_baselines import (
        compute_database_baselines,
        consistently_missed_accessibles,
    )

The returned baseline rows share the schema of CellSummary, so they
can be appended to the same summary.tsv as the variant cells.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass

from accessible_surfaceome.paths import DATA_DIR

from .benchmark import load_benchmark
from .scoring import CellSummary

CANDIDATE_UNIVERSE_TSV = (
    DATA_DIR / "processed" / "candidate_universe" / "candidate_universe.tsv"
)

# 5 databases (DeepTMHMM excluded — see docs/superpowers/specs/2026-05-06-...).
DB_FLAG_COLUMNS: tuple[str, ...] = (
    "surfy_surface_flag",
    "cspa_surface_flag",
    "uniprot_surface_flag",
    "go_surface_flag",
    "hpa_surface_flag",
)


@dataclass(frozen=True)
class _Vote:
    """Per-protein record of which sources voted ``true``."""

    flags: dict[str, bool]
    in_m1: bool


def _load_votes(uniprot_accs: set[str]) -> dict[str, _Vote]:
    votes: dict[str, _Vote] = {}
    if not CANDIDATE_UNIVERSE_TSV.exists():
        return {acc: _Vote(flags={c: False for c in DB_FLAG_COLUMNS}, in_m1=False) for acc in uniprot_accs}
    with CANDIDATE_UNIVERSE_TSV.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            acc = row.get("uniprot_accession") or ""
            if acc not in uniprot_accs:
                continue
            votes[acc] = _Vote(
                flags={c: row.get(c, "0") == "1" for c in DB_FLAG_COLUMNS},
                in_m1=True,
            )
    for acc in uniprot_accs:
        votes.setdefault(
            acc,
            _Vote(flags={c: False for c in DB_FLAG_COLUMNS}, in_m1=False),
        )
    return votes


def _binary_metrics(
    *, predictions: dict[str, int], truths: dict[str, int]
) -> tuple[int, int, int, int, float, float, float, float]:
    tp = tn = fp = fn = 0
    for key, truth in truths.items():
        pred = predictions.get(key, 0)
        if pred == 1 and truth == 1:
            tp += 1
        elif pred == 0 and truth == 0:
            tn += 1
        elif pred == 1 and truth == 0:
            fp += 1
        else:
            fn += 1
    n = tp + tn + fp + fn
    acc = (tp + tn) / n if n else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    if prec + recall > 0:
        f2 = (1 + 4) * prec * recall / ((4 * prec) + recall)
    else:
        f2 = 0.0
    return tp, tn, fp, fn, acc, recall, spec, f2


def _baseline_summary(
    cell_label: str,
    *,
    n_runs: int,
    tp: int,
    tn: int,
    fp: int,
    fn: int,
    binary_acc: float,
    recall: float,
    spec: float,
    f2: float,
) -> CellSummary:
    return CellSummary(
        cell_label=cell_label,
        variant="DB",
        model=None,
        n_runs=n_runs,
        # The DB baselines don't emit 3-way verdicts; we leave the
        # 3-way fields equal to the binary fields so the row is still
        # well-formed in summary.tsv.
        n_correct_verdict=tp + tn,
        n_correct_signal=tp + tn,
        verdict_accuracy=binary_acc,
        signal_accuracy=binary_acc,
        binary_accuracy=binary_acc,
        accessible_recall=recall,
        inaccessible_specificity=spec,
        f2_score=f2,
        total_cost_usd=0.0,
        mean_latency_s=0.0,
    )


def compute_database_baselines() -> list[CellSummary]:
    """Score every individual DB + a few combination rules against the benchmark."""

    rows = load_benchmark()
    truths = {r.uniprot_acc: 1 if r.ground_truth_verdict in ("yes", "contextual") else 0 for r in rows}
    votes = _load_votes(set(truths))
    summaries: list[CellSummary] = []

    # Each individual DB
    for src in DB_FLAG_COLUMNS:
        preds = {acc: 1 if votes[acc].flags[src] else 0 for acc in truths}
        tp, tn, fp, fn, acc, recall, spec, f2 = _binary_metrics(predictions=preds, truths=truths)
        label = "DB_" + src.replace("_surface_flag", "")
        summaries.append(
            _baseline_summary(
                label,
                n_runs=len(truths),
                tp=tp,
                tn=tn,
                fp=fp,
                fn=fn,
                binary_acc=acc,
                recall=recall,
                spec=spec,
                f2=f2,
            )
        )

    # Combinations
    for k, label in [
        (1, "DB_any_of_6"),
        (2, "DB_>=2_of_6"),
        (3, "DB_>=3_of_6"),
    ]:
        preds = {
            acc: 1 if sum(votes[acc].flags[s] for s in DB_FLAG_COLUMNS) >= k else 0
            for acc in truths
        }
        tp, tn, fp, fn, acc_, recall, spec, f2 = _binary_metrics(predictions=preds, truths=truths)
        summaries.append(
            _baseline_summary(
                label,
                n_runs=len(truths),
                tp=tp,
                tn=tn,
                fp=fp,
                fn=fn,
                binary_acc=acc_,
                recall=recall,
                spec=spec,
                f2=f2,
            )
        )

    return summaries


def consistently_missed_accessibles(*, max_db_votes: int = 1) -> list[dict[str, object]]:
    """Return rows for benchmark proteins whose ground truth = accessible
    but at most ``max_db_votes`` of the 6 DBs voted ``true``.

    These are the proteins where the deterministic stack's consensus
    breaks down; the LLM variants are most differentiated on these.
    """

    rows = load_benchmark()
    votes = _load_votes({r.uniprot_acc for r in rows})
    out: list[dict[str, object]] = []
    for r in rows:
        if r.ground_truth_verdict not in ("yes", "contextual"):
            continue
        n_votes = sum(votes[r.uniprot_acc].flags[s] for s in DB_FLAG_COLUMNS)
        if n_votes <= max_db_votes:
            out.append(
                {
                    "gene_symbol": r.gene_symbol,
                    "uniprot_acc": r.uniprot_acc,
                    "ground_truth_verdict": r.ground_truth_verdict,
                    "class": r.class_,
                    "n_db_votes": n_votes,
                    "in_m1": votes[r.uniprot_acc].in_m1,
                }
            )
    out.sort(key=lambda d: (-int(d["in_m1"]), d["gene_symbol"]))
    return out


__all__ = [
    "compute_database_baselines",
    "consistently_missed_accessibles",
    "DB_FLAG_COLUMNS",
]
