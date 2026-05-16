"""Backfill HGNC ID + Ensembl gene + NCBI gene ID into the four figure TSVs.

The figure scripts under ``data/analysis/figures/`` read four TSVs over
``raw.githubusercontent.com``: ``candidate_universe.tsv``,
``mainbench_canonical_v1.tsv``, ``triage_benchmark_v1.tsv``, and
``db_optimized_cutoffs.tsv``. Originally only ``uniprot_accession`` (or
``gene_symbol``) was carried; this script joins each TSV against the
``gene_identifier_public`` D1 table to append the stable identifiers a
reanalyst would need to cross-reference any other genes-keyed data
source.

Per CLAUDE.md's "Gene identifier resolution" section, ``hgnc_id`` is the
canonical stable key — symbol-only joins silently misroute ~0.2% of
human genes (the COX1 / WAS class). Carrying ``hgnc_id`` lets a reader
join figure inputs to any other table that follows the same convention
without re-resolving from a fragile symbol.

Run::

    uv run python scripts/augment_figure_tsvs_with_stable_ids.py
    uv run python scripts/augment_figure_tsvs_with_stable_ids.py --dry-run

Idempotent: re-running drops any pre-existing stable-ID columns and
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


def augment_candidate_universe(by_uniprot: dict[str, StableID]) -> tuple[int, int]:
    """Add stable IDs by joining on ``uniprot_accession``. Returns (n, n_matched)."""
    fields, rows = _read_tsv(CAND_TSV)
    add = ["hgnc_id", "hgnc_symbol", "ncbi_gene_id", "ensembl_gene",
           "ensembl_canonical_protein"]
    fields = _drop_stale(fields, rows, add) + add
    matched = 0
    for r in rows:
        acc = (r.get("uniprot_accession") or "").strip()
        sid = by_uniprot.get(acc)
        if sid:
            matched += 1
            r["hgnc_id"] = sid.hgnc_id
            r["hgnc_symbol"] = sid.hgnc_symbol
            r["ncbi_gene_id"] = sid.ncbi_gene_id
            r["ensembl_gene"] = sid.ensembl_gene
            r["ensembl_canonical_protein"] = sid.ensembl_canonical_protein
        else:
            for k in add:
                r[k] = ""
    _write_tsv(CAND_TSV, fields, rows)
    return len(rows), matched


def augment_triage_benchmark(by_uniprot: dict[str, StableID],
                             by_symbol: dict[str, StableID]) -> tuple[int, int]:
    """Add hgnc_id + ensembl + ncbi. Uses uniprot_acc as primary join (curated
    in the bench), falls back to gene_symbol when a row's UniProt doesn't
    appear in gene_identifier_public."""
    fields, rows = _read_tsv(BENCH_TSV)
    add = ["hgnc_id", "hgnc_symbol", "ncbi_gene_id", "ensembl_gene"]
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
        else:
            for k in add:
                r[k] = ""
    _write_tsv(BENCH_TSV, fields, rows)
    return len(rows), matched


def augment_mainbench(by_symbol: dict[str, StableID]) -> tuple[int, int]:
    """Add uniprot_acc + hgnc_id + ensembl + ncbi to the predictions TSV.

    Keyed by ``gene_symbol`` (the bench gene-symbol column). hgnc_symbol
    in gene_identifier_public is the authoritative join field — it
    survives symbol drift for the resolver-v3-fixed genes.
    """
    fields, rows = _read_tsv(MAINBENCH_TSV)
    add = ["uniprot_acc", "hgnc_id", "ncbi_gene_id", "ensembl_gene"]
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
            for k in add:
                r[k] = ""
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
    n, m = augment_candidate_universe(by_uniprot)
    summaries.append(("candidate_universe", n, m))
    n, m = augment_triage_benchmark(by_uniprot, by_symbol)
    summaries.append(("triage_benchmark_v1", n, m))
    n, m = augment_mainbench(by_symbol)
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
