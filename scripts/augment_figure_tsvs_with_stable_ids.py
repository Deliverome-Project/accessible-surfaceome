"""Backfill stable IDs + reanalysis-friendly denormalized columns into the
four figure TSVs.

The figure scripts under ``data/analysis/figures/`` read four TSVs over
``raw.githubusercontent.com``: ``candidate_universe.tsv``,
``mainbench_canonical_v2.tsv``, ``triage_benchmark_v1.tsv``, and
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

SONNET_RUN_ID = "genome_full_sonnet_ncbi_v2"
SONNET_MODEL = "claude-sonnet-4-6"
SONNET_VARIANT = "ncbi"


def _load_sonnet_verdict_index() -> dict[str, tuple[str, str]]:
    """Return ``{gene_symbol: (predicted_verdict, predicted_reason)}`` for the
    canonical genome-wide Sonnet sweep. As of the SurfaceBench v2 cutover
    (commit 45fbaffdb), the live sweep is ``genome_full_sonnet_ncbi_v2``
    (19,324 rows, replicate=1 only) — v1 has been replaced in public D1
    rather than coexisting, so no COALESCE / preference logic is needed.
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
    """Return ``{gene_symbol: {class, ground_truth_verdict}}`` for the
    canonical benchmark.

    Truth labels are sourced from the **committed** working-tree TSV
    ``data/eval/triage_benchmark_v1.tsv`` — the human-curated, code-
    reviewed source of bench ground truth. Reading from D1's
    ``benchmark_version`` (the previous behavior) was an anti-pattern:
    D1 stores multiple historical versions of the bench, the picker
    heuristic was brittle (lex sort, row-count, recency all picked
    different winners at different times), and the figures' truth
    labels could silently regress on a stale D1 read — exactly what
    happened on 2026-06-30 when a heuristic picked an old
    ``fc7ddee89155`` snapshot and downgraded HMGB1 / DLL3 truth
    labels from the curator's intent. The committed TSV is git-
    tracked, code-reviewed, drift-guarded by
    ``tests/test_mainbench_truth_drift.py``, and is the canonical
    source per PR #86's "builder → committed TSV → consumers" spine.

    This function used to fall back to the local TSV only if D1
    failed; that fallback is now the primary (and only) path.
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
    print(f"  bench truth from committed {BENCH_TSV.name} ({len(out)} genes)")
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
MAINBENCH_TSV = REPO_ROOT / "data/processed/triage_bench/mainbench_canonical_v2.tsv"
# Per-replicate companion to MAINBENCH_TSV (one row per gene×model×variant×rep).
# Drives the SEM + individual-replicate-point overlays on the bar figures.
# Augmented with the same truth + is_match join as the majority TSV.
REPLICATES_TSV = REPO_ROOT / "data/processed/triage_bench/mainbench_replicates_v2.tsv"
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
    sonnet: dict[str, tuple[str, str]],
    bench: dict[str, dict[str, str]],
) -> tuple[int, int]:
    """Add stable IDs + ``n_db_votes`` + genome-sweep Sonnet verdict to the
    bench TSV. Uses uniprot_acc as primary join (curated in the bench),
    falls back to gene_symbol when a row's UniProt doesn't appear in
    gene_identifier_public.

    ``sonnet_verdict`` / ``sonnet_reason`` are pulled from the
    ``genome_full_sonnet_ncbi_v1`` run (the same source the catalog
    serves) — direct comparison against the curated truth without
    joining mainbench.

    Also RECONCILES the TSV's own ``ground_truth_verdict`` / ``class``
    columns against the D1-sourced ``bench`` index (public
    benchmark_version, the published origin). The working-tree TSV is not
    the authority for labels — it can silently revert — so any drift is
    corrected from D1 here and reported loudly, keeping the on-repo figure
    inputs tied to the published benchmark.
    """
    fields, rows = _read_tsv(BENCH_TSV)
    add = ["hgnc_id", "hgnc_symbol", "ncbi_gene_id", "ensembl_gene",
           "ensembl_canonical_protein", "n_db_votes",
           "sonnet_verdict", "sonnet_reason"]
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
        # Genome-sweep Sonnet verdict for this bench gene.
        sym = (r.get("gene_symbol") or "").strip()
        v, why = sonnet.get(sym, ("", ""))
        r["sonnet_verdict"] = v
        r["sonnet_reason"] = why
    # Truth-label reconciliation block removed 2026-06-30. It used to
    # cross-check the TSV's ground_truth_verdict against a D1 origin
    # and overwrite divergent rows — but D1's `benchmark_version` is
    # now no longer the source. The committed TSV is. A "reconcile"
    # against itself would be a no-op and the loop misleadingly
    # implied D1 was authoritative. The truth-drift guard
    # `tests/test_mainbench_truth_drift.py` is the right place to
    # catch label regressions in the committed TSV.
    _write_tsv(BENCH_TSV, fields, rows)
    return len(rows), matched


def augment_mainbench(
    by_symbol: dict[str, StableID],
    bench: dict[str, dict[str, str]],
    db_flags_by_acc: dict[str, dict[str, int]],
    n_db_votes_by_acc: dict[str, int],
    deep_dive: set[str],
    tsv_path: Path = MAINBENCH_TSV,
) -> tuple[int, int]:
    """Add stable IDs + ground-truth + per-cell soft-match flag + per-DB
    membership flags to the predictions TSV.

    Adds:
      * uniprot_acc, hgnc_id, ncbi_gene_id, ensembl_gene — joined on
        gene_symbol via gene_identifier_public.
      * ground_truth_verdict, ground_truth_class — joined on gene_symbol
        from data/eval/triage_benchmark_v1.tsv.
      * is_match (0/1) — predicted_verdict matches truth under the
        soft-credit rule used by the bench figures: ``yes`` matches
        ``yes`` or ``contextual``; ``no`` matches ``no`` only.
      * uniprot/go/surfy/cspa/hpa_surface_flag — per-DB canonical
        membership, joined on uniprot_acc via candidate_universe. Bench
        rows whose UniProt isn't in the universe (the "DB-zero rescue"
        class) get 0s.
      * n_db_votes — 0–5 sum of the above.
      * has_deep_dive — 1 if the gene has a published SurfaceomeRecord.

    Keyed by ``gene_symbol``. hgnc_symbol in gene_identifier_public is
    the authoritative join field — it survives symbol drift for the
    resolver-v3-fixed genes.
    """
    fields, rows = _read_tsv(tsv_path)
    add = [
        "uniprot_acc", "hgnc_id", "ncbi_gene_id", "ensembl_gene",
        "ground_truth_verdict", "ground_truth_class", "is_match",
        "uniprot_surface_flag", "go_surface_flag", "surfy_surface_flag",
        "cspa_surface_flag", "hpa_surface_flag",
        "n_db_votes", "has_deep_dive",
    ]
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
        # Per-DB flags from candidate_universe (canonical cutoffs). Bench
        # genes that aren't in the universe land all zeros.
        acc = r["uniprot_acc"]
        flags = db_flags_by_acc.get(acc, {})
        for k in ("uniprot_surface_flag", "go_surface_flag",
                  "surfy_surface_flag", "cspa_surface_flag",
                  "hpa_surface_flag"):
            r[k] = str(flags.get(k, 0))
        r["n_db_votes"] = str(n_db_votes_by_acc.get(acc, 0))
        r["has_deep_dive"] = "1" if sym in deep_dive else "0"
    _write_tsv(tsv_path, fields, rows)
    return len(rows), matched


def augment_db_optimized_cutoffs(
    by_uniprot: dict[str, StableID],
    db_flags_by_acc: dict[str, dict[str, int]],
    n_db_votes_by_acc: dict[str, int],
) -> tuple[int, int]:
    """Add stable IDs + canonical per-DB membership alongside the existing
    optimized flags. Joins on ``accession`` (UniProt).

    After augmentation each row carries both the canonical-cutoff DB
    votes (from candidate_universe) and the bench-optimized cutoffs
    (the file's original purpose), so a reanalyst can read off
    "canonical vs optimized" per (accession, DB) without joining
    candidate_universe.

    Note: only UniProt and CSPA have an optimized cutoff variant; GO,
    SURFY, and HPA carry only their canonical flags (no `_optimized`
    column exists for them, since their inclusion rules are binary).
    """
    fields, rows = _read_tsv(CUTOFFS_TSV)
    add = [
        "gene_symbol", "hgnc_id", "hgnc_symbol", "ncbi_gene_id", "ensembl_gene",
        "uniprot_surface_flag", "go_surface_flag", "surfy_surface_flag",
        "cspa_surface_flag", "hpa_surface_flag",
        "n_sources_surface", "n_sources_optimized",
    ]
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
            for k in ("gene_symbol", "hgnc_id", "hgnc_symbol",
                      "ncbi_gene_id", "ensembl_gene"):
                r[k] = ""
        # Canonical per-DB flags from candidate_universe.
        flags = db_flags_by_acc.get(acc, {})
        for k in ("uniprot_surface_flag", "go_surface_flag",
                  "surfy_surface_flag", "cspa_surface_flag",
                  "hpa_surface_flag"):
            r[k] = str(flags.get(k, 0))
        r["n_sources_surface"] = str(n_db_votes_by_acc.get(acc, 0))
        # Optimized-cutoff count: uniprot_optimized + go + surfy +
        # cspa_optimized + hpa (the three middle DBs have no optimized
        # variant, so their canonical flag stands in).
        try:
            uo = int(r.get("uniprot_optimized") or 0)
            co = int(r.get("cspa_optimized") or 0)
        except ValueError:
            uo = co = 0
        go = int(flags.get("go_surface_flag", 0))
        sy = int(flags.get("surfy_surface_flag", 0))
        hp = int(flags.get("hpa_surface_flag", 0))
        r["n_sources_optimized"] = str(uo + go + sy + co + hp)
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

    print("Loading bench truth ...")
    bench = _load_bench_index()
    print(f"  {len(bench):,} curated bench rows")

    # n_db_votes + per-DB flags per uniprot_accession, computed from
    # candidate_universe's surface_flag columns. Used to denormalize the
    # 5 gating-DB flags into bench / mainbench / cutoffs TSVs without
    # forcing reanalysts to join against candidate_universe.
    _, cand_rows = _read_tsv(CAND_TSV)
    n_db_votes_by_acc: dict[str, int] = {}
    db_flags_by_acc: dict[str, dict[str, int]] = {}
    flag_cols = ("uniprot_surface_flag", "go_surface_flag",
                 "surfy_surface_flag", "cspa_surface_flag",
                 "hpa_surface_flag")
    for r in cand_rows:
        acc = (r.get("uniprot_accession") or "").strip()
        if not acc:
            continue
        try:
            n_db_votes_by_acc[acc] = int(r.get("n_sources_surface") or 0)
        except ValueError:
            n_db_votes_by_acc[acc] = 0
        flags: dict[str, int] = {}
        for k in flag_cols:
            try:
                flags[k] = int(r.get(k) or 0)
            except ValueError:
                flags[k] = 0
        db_flags_by_acc[acc] = flags

    if args.dry_run:
        # Just read each TSV and report what coverage we'd see.
        for label, path, key in [
            ("candidate_universe", CAND_TSV, "uniprot_accession"),
            ("triage_benchmark_v1", BENCH_TSV, "uniprot_acc"),
            ("mainbench_canonical_v2", MAINBENCH_TSV, "gene_symbol"),
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
    n, m = augment_triage_benchmark(
        by_uniprot, by_symbol, n_db_votes_by_acc, sonnet, bench,
    )
    summaries.append(("triage_benchmark_v1", n, m))
    n, m = augment_mainbench(
        by_symbol, bench, db_flags_by_acc, n_db_votes_by_acc, deep_dive,
    )
    summaries.append(("mainbench_canonical_v2", n, m))
    # Per-replicate companion — same join, so the bar figures can compute
    # per-rep accuracy (points) + SEM. Only when the file exists (it's
    # produced by `export_mainbench_to_tsv.py --per-rep`).
    if REPLICATES_TSV.exists():
        n, m = augment_mainbench(
            by_symbol, bench, db_flags_by_acc, n_db_votes_by_acc, deep_dive,
            tsv_path=REPLICATES_TSV,
        )
        summaries.append(("mainbench_replicates_v2", n, m))
    n, m = augment_db_optimized_cutoffs(
        by_uniprot, db_flags_by_acc, n_db_votes_by_acc,
    )
    summaries.append(("db_optimized_cutoffs", n, m))

    print("\nAugmentation summary:")
    for label, n, m in summaries:
        pct = (100 * m / n) if n else 0
        print(f"  {label:>28s}  {m:>5,} / {n:>5,} rows matched  ({pct:5.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
