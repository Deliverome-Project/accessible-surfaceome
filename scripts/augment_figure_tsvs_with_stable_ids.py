"""Backfill stable IDs + reanalysis-friendly denormalized columns into the
four figure TSVs.

The figure scripts under ``data/analysis/figures/`` read four TSVs over
``raw.githubusercontent.com``: ``candidate_universe.tsv``,
``mainbench_canonical_v1.tsv``, ``triage_benchmark_v1.tsv``, and
``db_optimized_cutoffs.tsv``. Originally only ``uniprot_accession`` (or
``gene_symbol``) was carried; this script joins each TSV against:

  * ``gene_identifier_public`` — adds ``hgnc_id``, ``hgnc_symbol``,
    ``ncbi_gene_id``, ``ensembl_gene``, ``ensembl_canonical_protein``
  * ``triage_run_public`` (Sonnet, ``genome_full_sonnet_ncbi_v1``,
    prompt_variant=``ncbi``) — adds ``sonnet_verdict``, ``sonnet_reason``
  * ``surface_annotation`` — adds ``has_deep_dive`` (0/1)
  * the curated bench TSV — adds bench-member + truth flags where
    relevant

Per CLAUDE.md's "Gene identifier resolution" section, ``hgnc_id`` is the
canonical stable key — symbol-only joins silently misroute ~0.2% of
human genes (the COX1 / WAS class). Carrying it + the LLM verdict +
deep-dive flag in the TSV row removes the most-common multi-file joins
a reanalyst has to do today.

Run::

    uv run python scripts/augment_figure_tsvs_with_stable_ids.py
    uv run python scripts/augment_figure_tsvs_with_stable_ids.py --dry-run

Idempotent: re-running drops any pre-existing augment-owned columns and
re-derives them. Output is byte-stable apart from the added columns
(``lineterminator='\n'``, preserved row order).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

load_env()

# ------------------------------ D1 access ----------------------------------

def _query_public(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    missing = [k for k, v in [
        ("CLOUDFLARE_ACCOUNT_ID", acct),
        ("CLOUDFLARE_API_TOKEN", token),
        ("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", db),
    ] if not v]
    if missing:
        raise SystemExit("Missing env vars: " + ", ".join(missing))
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/d1/database/{db}/query"
    resp = httpx.post(url, json={"sql": sql, "params": params or []},
                      headers={"Authorization": f"Bearer {token}"}, timeout=60)
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 error: {data}")
    result = data.get("result")
    if isinstance(result, list) and result:
        return list(result[0].get("results") or [])
    return []


# ------------------------------ Identifier index ---------------------------

@dataclass(slots=True)
class StableID:
    hgnc_id: str
    hgnc_symbol: str
    uniprot_acc: str
    ncbi_gene_id: str
    ensembl_gene: str
    ensembl_canonical_protein: str


def _load_gene_identifier_index() -> tuple[dict[str, StableID], dict[str, StableID]]:
    """Return (by_uniprot, by_symbol) views of ``gene_identifier_public``.

    The table is keyed by ``hgnc_id`` with at most one row per HGNC gene; we
    materialize two lookup dicts for ergonomic joins downstream. Symbol
    lookups use ``hgnc_symbol`` (the authoritative HGNC symbol), not the
    ``cohort_symbol`` field — the latter preserves cohort-input drift and
    isn't what a reanalyst would type.
    """
    rows = _query_public(
        "SELECT hgnc_id, hgnc_symbol, uniprot_acc, ncbi_gene_id, ensembl_gene, "
        "ensembl_canonical_protein FROM gene_identifier_public"
    )
    by_uniprot: dict[str, StableID] = {}
    by_symbol: dict[str, StableID] = {}
    for r in rows:
        sid = StableID(
            hgnc_id=str(r.get("hgnc_id") or ""),
            hgnc_symbol=str(r.get("hgnc_symbol") or ""),
            uniprot_acc=str(r.get("uniprot_acc") or ""),
            ncbi_gene_id=str(r.get("ncbi_gene_id") or ""),
            ensembl_gene=str(r.get("ensembl_gene") or ""),
            ensembl_canonical_protein=str(r.get("ensembl_canonical_protein") or ""),
        )
        if sid.uniprot_acc:
            by_uniprot.setdefault(sid.uniprot_acc, sid)
        if sid.hgnc_symbol:
            by_symbol.setdefault(sid.hgnc_symbol, sid)
    return by_uniprot, by_symbol


# ------------------------------ Sonnet verdict index -----------------------

SONNET_RUN_ID = "genome_full_sonnet_ncbi_v1"
SONNET_MODEL = "claude-sonnet-4-6"
SONNET_VARIANT = "ncbi"


def _load_sonnet_verdict_index() -> dict[str, tuple[str, str]]:
    """Return ``{gene_symbol: (predicted_verdict, predicted_reason)}`` for the
    canonical genome-wide Sonnet sweep. Public D1 already holds the
    resolver-v3-fixed rows under the same run_id (verified — 45 fix-run
    cells overwrote the originals in place), so no COALESCE is needed.
    """
    rows = _query_public(
        "SELECT gene_symbol, predicted_verdict, predicted_reason "
        "FROM triage_run_public "
        "WHERE run_id = ? AND model = ? AND prompt_variant = ? AND replicate = 1",
        [SONNET_RUN_ID, SONNET_MODEL, SONNET_VARIANT],
    )
    out: dict[str, tuple[str, str]] = {}
    for r in rows:
        sym = str(r.get("gene_symbol") or "").strip()
        if not sym:
            continue
        out[sym] = (
            str(r.get("predicted_verdict") or ""),
            str(r.get("predicted_reason") or ""),
        )
    return out


# ------------------------------ Deep-dive index ----------------------------

def _load_deep_dive_index() -> set[str]:
    """Return the set of gene_symbols with a published SurfaceomeRecord
    (any schema_version) in ``surface_annotation``."""
    rows = _query_public(
        "SELECT DISTINCT gene_symbol FROM surface_annotation"
    )
    return {str(r.get("gene_symbol") or "").strip() for r in rows if r.get("gene_symbol")}


# ------------------------------ Bench index --------------------------------

def _load_bench_index() -> dict[str, dict[str, str]]:
    """Return ``{gene_symbol: {class, ground_truth_verdict, n_db_votes_at_curation}}``
    from the local triage_benchmark_v1.tsv. n_db_votes is computed later from
    the candidate-universe row; this lookup only needs class + verdict.
    """
    _, rows = _read_tsv(BENCH_TSV)
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        sym = (r.get("gene_symbol") or "").strip()
        if not sym:
            continue
        out[sym] = {
            "class": r.get("class") or "",
            "ground_truth_verdict": r.get("ground_truth_verdict") or "",
        }
    return out


def _is_soft_match(predicted: str, truth: str) -> int:
    """Soft-credit match rule used by the bench figures: predicted-yes
    matches truth-yes-or-contextual, predicted-contextual matches
    truth-yes-or-contextual, predicted-no matches truth-no only.
    Returns 1 on match, 0 otherwise.
    """
    p, t = (predicted or "").strip(), (truth or "").strip()
    if not p or not t:
        return 0
    if p == t:
        return 1
    if p in ("yes", "contextual") and t in ("yes", "contextual"):
        return 1
    return 0


# ------------------------------ TSV I/O helper -----------------------------

def _read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fields = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return fields, rows


def _write_tsv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    """Write with ``\\n`` line endings so the on-repo TSV survives diff
    cosmetic noise. Empty values stay empty strings (no ``"None"``)."""
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t",
                           lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k, "")) for k in fields})


def _drop_stale(fields: list[str], rows: list[dict[str, str]], drop: list[str]) -> list[str]:
    """Drop columns from the fieldnames + every row so re-runs are idempotent."""
    drop_set = set(drop)
    for r in rows:
        for k in drop_set:
            r.pop(k, None)
    return [f for f in fields if f not in drop_set]


# ------------------------------ Per-TSV augmentations ----------------------

CAND_TSV = REPO_ROOT / "data/processed/candidate_universe/candidate_universe.tsv"
BENCH_TSV = REPO_ROOT / "data/eval/triage_benchmark_v1.tsv"
MAINBENCH_TSV = REPO_ROOT / "data/processed/triage_bench/mainbench_canonical_v1.tsv"
CUTOFFS_TSV = REPO_ROOT / "data/processed/triage_bench/db_optimized_cutoffs.tsv"


def augment_candidate_universe(
    by_uniprot: dict[str, StableID],
    sonnet: dict[str, tuple[str, str]],
    deep_dive: set[str],
    bench: dict[str, dict[str, str]],
) -> tuple[int, int]:
    """Augment candidate_universe.tsv.

    Adds:
      * Stable IDs (hgnc_id, hgnc_symbol, ncbi_gene_id, ensembl_gene,
        ensembl_canonical_protein) — joined on uniprot_accession.
      * Sonnet verdict + reason from triage_run_public.genome_full_sonnet_ncbi_v1
        (joined on gene_symbol). Empty when Sonnet hasn't rated this row.
      * has_deep_dive (0/1) — whether a SurfaceomeRecord exists.
      * is_bench_member (0/1) — whether the gene is in triage_benchmark_v1.

    Note: ``selection_reason`` (db_only / triage_only / both) was considered
    but every row in this file has ``in_db_union=1`` by construction, so it
    would always reduce to ``sonnet_verdict in ('yes','contextual')``. Use
    the raw ``sonnet_verdict`` column for that filter instead.

    Returns (n_rows, n_stable_id_matched).
    """
    fields, rows = _read_tsv(CAND_TSV)
    add = [
        "hgnc_id", "hgnc_symbol", "ncbi_gene_id", "ensembl_gene",
        "ensembl_canonical_protein",
        "sonnet_verdict", "sonnet_reason",
        "has_deep_dive", "is_bench_member",
    ]
    # Drop the legacy selection_reason if a prior run wrote it.
    fields = _drop_stale(fields, rows, add + ["selection_reason"]) + add
    matched = 0
    for r in rows:
        acc = (r.get("uniprot_accession") or "").strip()
        sym = (r.get("gene_symbol") or "").strip()
        sid = by_uniprot.get(acc)
        if sid:
            matched += 1
            r["hgnc_id"] = sid.hgnc_id
            r["hgnc_symbol"] = sid.hgnc_symbol
            r["ncbi_gene_id"] = sid.ncbi_gene_id
            r["ensembl_gene"] = sid.ensembl_gene
            r["ensembl_canonical_protein"] = sid.ensembl_canonical_protein
        else:
            for k in ("hgnc_id", "hgnc_symbol", "ncbi_gene_id",
                      "ensembl_gene", "ensembl_canonical_protein"):
                r[k] = ""
        v, why = sonnet.get(sym, ("", ""))
        r["sonnet_verdict"] = v
        r["sonnet_reason"] = why
        r["has_deep_dive"] = "1" if sym in deep_dive else "0"
        r["is_bench_member"] = "1" if sym in bench else "0"
    _write_tsv(CAND_TSV, fields, rows)
    return len(rows), matched


def augment_triage_benchmark(
    by_uniprot: dict[str, StableID],
    by_symbol: dict[str, StableID],
    n_db_votes_by_acc: dict[str, int],
) -> tuple[int, int]:
    """Add stable IDs (incl. ensembl_canonical_protein) + ``n_db_votes`` to
    the bench TSV. Uses uniprot_acc as primary join (curated in the
    bench), falls back to gene_symbol when a row's UniProt doesn't
    appear in gene_identifier_public.
    """
    fields, rows = _read_tsv(BENCH_TSV)
    add = ["hgnc_id", "hgnc_symbol", "ncbi_gene_id", "ensembl_gene",
           "ensembl_canonical_protein", "n_db_votes"]
    fields = _drop_stale(fields, rows, add) + add
    matched = 0
    for r in rows:
        acc = (r.get("uniprot_acc") or "").strip()
        sid = by_uniprot.get(acc)
        if not sid:
            sym = (r.get("gene_symbol") or "").strip()
            sid = by_symbol.get(sym)
        if sid:
            matched += 1
            r["hgnc_id"] = sid.hgnc_id
            r["hgnc_symbol"] = sid.hgnc_symbol
            r["ncbi_gene_id"] = sid.ncbi_gene_id
            r["ensembl_gene"] = sid.ensembl_gene
            r["ensembl_canonical_protein"] = sid.ensembl_canonical_protein
        else:
            for k in ("hgnc_id", "hgnc_symbol", "ncbi_gene_id",
                      "ensembl_gene", "ensembl_canonical_protein"):
                r[k] = ""
        # n_db_votes: count of 5 gating-DB surface_flag positives from
        # candidate_universe. Bench-only genes that aren't in the universe
        # (the "DB-zero rescues") get 0 — that's the analyst-friendly answer.
        r["n_db_votes"] = str(n_db_votes_by_acc.get(acc, 0))
    _write_tsv(BENCH_TSV, fields, rows)
    return len(rows), matched


def augment_mainbench(
    by_symbol: dict[str, StableID],
    bench: dict[str, dict[str, str]],
) -> tuple[int, int]:
    """Add stable IDs + ground-truth + per-cell soft-match flag to the
    predictions TSV.

    Adds:
      * uniprot_acc, hgnc_id, ncbi_gene_id, ensembl_gene — joined on
        gene_symbol via gene_identifier_public.
      * ground_truth_verdict, ground_truth_class — joined on gene_symbol
        from data/eval/triage_benchmark_v1.tsv.
      * is_match (0/1) — predicted_verdict matches truth under the
        soft-credit rule used by the bench figures: ``yes`` matches
        ``yes`` or ``contextual``; ``no`` matches ``no`` only. Lets a
        reader compute precision / recall in one groupby instead of a
        manual recode + join.

    Keyed by ``gene_symbol``. hgnc_symbol in gene_identifier_public is
    the authoritative join field — it survives symbol drift for the
    resolver-v3-fixed genes.
    """
    fields, rows = _read_tsv(MAINBENCH_TSV)
    add = ["uniprot_acc", "hgnc_id", "ncbi_gene_id", "ensembl_gene",
           "ground_truth_verdict", "ground_truth_class", "is_match"]
    fields = _drop_stale(fields, rows, add) + add
    matched = 0
    for r in rows:
        sym = (r.get("gene_symbol") or "").strip()
        sid = by_symbol.get(sym)
        if sid:
            matched += 1
            r["uniprot_acc"] = sid.uniprot_acc
            r["hgnc_id"] = sid.hgnc_id
            r["ncbi_gene_id"] = sid.ncbi_gene_id
            r["ensembl_gene"] = sid.ensembl_gene
        else:
            for k in ("uniprot_acc", "hgnc_id", "ncbi_gene_id", "ensembl_gene"):
                r[k] = ""
        b = bench.get(sym) or {}
        r["ground_truth_verdict"] = b.get("ground_truth_verdict", "")
        r["ground_truth_class"] = b.get("class", "")
        r["is_match"] = str(_is_soft_match(
            r.get("predicted_verdict", ""), r["ground_truth_verdict"]
        ))
    _write_tsv(MAINBENCH_TSV, fields, rows)
    return len(rows), matched


def augment_db_optimized_cutoffs(by_uniprot: dict[str, StableID]) -> tuple[int, int]:
    """Add gene_symbol + stable IDs. Joins on ``accession`` (UniProt)."""
    fields, rows = _read_tsv(CUTOFFS_TSV)
    add = ["gene_symbol", "hgnc_id", "hgnc_symbol", "ncbi_gene_id", "ensembl_gene"]
    fields = _drop_stale(fields, rows, add) + add
    matched = 0
    for r in rows:
        acc = (r.get("accession") or "").strip()
        sid = by_uniprot.get(acc)
        if sid:
            matched += 1
            r["gene_symbol"] = sid.hgnc_symbol  # canonical, not cohort_symbol
            r["hgnc_id"] = sid.hgnc_id
            r["hgnc_symbol"] = sid.hgnc_symbol
            r["ncbi_gene_id"] = sid.ncbi_gene_id
            r["ensembl_gene"] = sid.ensembl_gene
        else:
            for k in add:
                r[k] = ""
    _write_tsv(CUTOFFS_TSV, fields, rows)
    return len(rows), matched


# ------------------------------ Entry point --------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Report coverage without writing.")
    args = ap.parse_args()

    print("Loading gene_identifier_public from public D1 ...")
    by_uniprot, by_symbol = _load_gene_identifier_index()
    print(f"  {len(by_uniprot):,} UniProt-indexed rows  ·  "
          f"{len(by_symbol):,} HGNC-symbol-indexed rows")

    print(f"Loading Sonnet verdicts ({SONNET_RUN_ID}, {SONNET_MODEL}/{SONNET_VARIANT}) ...")
    sonnet = _load_sonnet_verdict_index()
    print(f"  {len(sonnet):,} gene-symbol verdicts")

    print("Loading deep-dive gene set from surface_annotation ...")
    deep_dive = _load_deep_dive_index()
    print(f"  {len(deep_dive):,} genes with a published SurfaceomeRecord")

    print("Loading bench truth from local triage_benchmark_v1.tsv ...")
    bench = _load_bench_index()
    print(f"  {len(bench):,} curated bench rows")

    # n_db_votes per uniprot_accession, computed from candidate_universe's
    # n_sources_surface column. Used to populate the bench TSV's "DB baseline"
    # column without re-deriving the count in every consumer.
    _, cand_rows = _read_tsv(CAND_TSV)
    n_db_votes_by_acc: dict[str, int] = {}
    for r in cand_rows:
        acc = (r.get("uniprot_accession") or "").strip()
        if not acc:
            continue
        try:
            n_db_votes_by_acc[acc] = int(r.get("n_sources_surface") or 0)
        except ValueError:
            n_db_votes_by_acc[acc] = 0

    if args.dry_run:
        # Just read each TSV and report what coverage we'd see.
        for label, path, key in [
            ("candidate_universe", CAND_TSV, "uniprot_accession"),
            ("triage_benchmark_v1", BENCH_TSV, "uniprot_acc"),
            ("mainbench_canonical_v1", MAINBENCH_TSV, "gene_symbol"),
            ("db_optimized_cutoffs", CUTOFFS_TSV, "accession"),
        ]:
            _, rows = _read_tsv(path)
            if key == "gene_symbol":
                covered = sum(1 for r in rows if (r.get(key) or "").strip() in by_symbol)
            else:
                covered = sum(1 for r in rows if (r.get(key) or "").strip() in by_uniprot)
            print(f"  {label:>28s}  {covered:>5,} / {len(rows):>5,} would be matched")
        return 0

    summaries = []
    n, m = augment_candidate_universe(by_uniprot, sonnet, deep_dive, bench)
    summaries.append(("candidate_universe", n, m))
    n, m = augment_triage_benchmark(by_uniprot, by_symbol, n_db_votes_by_acc)
    summaries.append(("triage_benchmark_v1", n, m))
    n, m = augment_mainbench(by_symbol, bench)
    summaries.append(("mainbench_canonical_v1", n, m))
    n, m = augment_db_optimized_cutoffs(by_uniprot)
    summaries.append(("db_optimized_cutoffs", n, m))

    print("\nAugmentation summary:")
    for label, n, m in summaries:
        pct = (100 * m / n) if n else 0
        print(f"  {label:>28s}  {m:>5,} / {n:>5,} rows matched  ({pct:5.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
