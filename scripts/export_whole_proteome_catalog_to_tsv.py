#!/usr/bin/env python3
"""Export the whole-proteome catalog from public D1 to a flat TSV
serializable via raw.githubusercontent.com so the
``db_vs_sonnet_whole_proteome`` and ``zero_db_rescues_by_triage``
gists can run as self-contained scripts without depending on the
Worker being live.

Reads:
  D1 candidate_universe_public  — per-gene DB-vote profile (~19,324 rows)
  D1 gene_identifier_public     — stable IDs per HGNC
  D1 triage_run_public          — canonical Sonnet+NCBI verdict / reason

Writes:
  data/processed/catalog/whole_proteome_catalog.tsv

Columns (expanded, one row per protein-coding human gene):

  hgnc_id, hgnc_symbol, uniprot_acc, ensembl_gene, ncbi_gene_id
  uniprot_surface_flag, go_surface_flag, hpa_surface_flag,
  surfy_surface_flag, cspa_surface_flag
  n_sources_surface
  sonnet_verdict, sonnet_reason
  universe_version

The 5 per-DB ``*_surface_flag`` columns reproduce the v1-style flag
names so the existing figure scripts can swap ``CATALOG_URL`` →
``WHOLE_PROTEOME_TSV`` without renaming every column access. Stable
IDs are denormalized so the same TSV serves as the "nice table" for
any downstream join.

Triage source: the canonical bench run
``genome_full_sonnet_ncbi_v1`` and its 45-cell resolver-v3 fix
``genome_full_sonnet_ncbi_v1__resolver_v3_fix``. Per
``CLAUDE.md``'s composite-source convention, the fix row wins over
the original when both exist for the same gene.

Usage::

    uv run python scripts/export_whole_proteome_catalog_to_tsv.py             # dry-run (count + preview)
    uv run python scripts/export_whole_proteome_catalog_to_tsv.py --execute   # write the TSV

Idempotent: just regenerates the TSV from the live D1 state. Bump
when D1 universe/triage state changes (e.g. after the
``backfill_sonnet_only_uniprots_to_d1.py`` patch). Track the output
TSV in ``.gitattributes`` with the ``-filter -diff -merge text``
exemption so raw.githubusercontent.com serves plain text, not an LFS
pointer.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402
from accessible_surfaceome.env import load_env  # noqa: E402

# ----------------------------------------------------------------------
# Constants — bump when the universe / triage release advances.
# ----------------------------------------------------------------------

UNIVERSE_VERSION = "cu_2026_05_12_post_silentdrop_fix"

# Genome-wide Sonnet+NCBI sweep. As of 2026-06, the canonical sweep
# is ``genome_full_sonnet_ncbi_v2`` (19,324 rows, post-v1 resolver-v3
# fix already baked in — no separate fix-run needed for v2). If a
# later sweep ships under a different run_id, bump this constant.
TRIAGE_RUN_PRIMARY = "genome_full_sonnet_ncbi_v2"
TRIAGE_RUN_FIX = "genome_full_sonnet_ncbi_v2"  # same — no separate fix layer at v2
TRIAGE_MODEL = "claude-sonnet-4-6"  # canonical sonnet (matches catalog API's models[1])
TRIAGE_PROMPT_VARIANT = "ncbi"

OUT_PATH = (
    REPO_ROOT / "data" / "processed" / "catalog" / "whole_proteome_catalog.tsv"
)

COLS = [
    "hgnc_id",
    "hgnc_symbol",
    "uniprot_acc",
    "ensembl_gene",
    "ncbi_gene_id",
    "uniprot_surface_flag",
    "go_surface_flag",
    "hpa_surface_flag",
    "surfy_surface_flag",
    "cspa_surface_flag",
    "n_sources_surface",
    "sonnet_verdict",
    "sonnet_reason",
    "universe_version",
]


def _query_universe(d1: D1Client) -> dict[str, dict[str, object]]:
    """One row per (gene_symbol) from candidate_universe_public for
    the active universe_version. The gene_symbol is keyed because
    triage_run_public is also gene_symbol-keyed; uniprot_acc may be
    NULL for non-surface genes, so we can't use it as a join key."""
    rows = d1.query(
        """
        SELECT gene_symbol,
               uniprot_acc,
               n_sources_surface,
               uniprot_surface_flag,
               go_surface_flag,
               surfy_surface_flag,
               cspa_surface_flag,
               hpa_surface_flag
        FROM candidate_universe_public
        WHERE universe_version = ?;
        """,
        [UNIVERSE_VERSION],
    )
    return {r["gene_symbol"]: r for r in rows}


def _query_gene_identifier(d1: D1Client) -> dict[str, dict[str, str | None]]:
    """One row per HGNC symbol from gene_identifier_public. Returns
    ``{hgnc_symbol: {hgnc_id, uniprot_acc, ensembl_gene, ncbi_gene_id}}``.
    ``uniprot_acc`` here is the resolver-canonical accession; for non-
    surface genes whose universe row has uniprot_acc='', this is the
    accession to use."""
    rows = d1.query(
        """
        SELECT hgnc_id, hgnc_symbol, uniprot_acc, ensembl_gene, ncbi_gene_id
        FROM gene_identifier_public;
        """,
        [],
    )
    return {
        r["hgnc_symbol"]: {
            "hgnc_id": r.get("hgnc_id"),
            "uniprot_acc": r.get("uniprot_acc"),
            "ensembl_gene": r.get("ensembl_gene"),
            "ncbi_gene_id": r.get("ncbi_gene_id"),
        }
        for r in rows
        if r.get("hgnc_symbol")
    }


def _query_triage(d1: D1Client) -> dict[str, dict[str, str]]:
    """One row per gene_symbol with the Sonnet verdict + reason,
    preferring the resolver-v3 fix run over the original when both
    have a row for the same gene. Both runs are model=sonnet,
    prompt_variant=ncbi, replicate=1.

    Pull pattern: union the two runs in a single query, sorted so the
    fix row comes first within each gene; Python dict-insertion order
    keeps the first-seen value, so the fix wins when present.
    """
    rows = d1.query(
        """
        SELECT run_id, gene_symbol, predicted_verdict, predicted_reason
        FROM triage_run_public
        WHERE model = ?
          AND prompt_variant = ?
          AND replicate = 1
          AND run_id IN (?, ?)
        ORDER BY gene_symbol,
                 CASE WHEN run_id = ? THEN 0 ELSE 1 END;
        """,
        [
            TRIAGE_MODEL,
            TRIAGE_PROMPT_VARIANT,
            TRIAGE_RUN_PRIMARY,
            TRIAGE_RUN_FIX,
            TRIAGE_RUN_FIX,
        ],
    )
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        sym = r.get("gene_symbol")
        if sym and sym not in out:
            out[sym] = {
                "sonnet_verdict": r.get("predicted_verdict") or "",
                "sonnet_reason": r.get("predicted_reason") or "",
            }
    return out


def _build_rows() -> list[dict[str, object]]:
    print("--- querying D1 ---")
    with D1Client.public() as d1:
        universe = _query_universe(d1)
        gid = _query_gene_identifier(d1)
        triage = _query_triage(d1)
    print(f"  universe rows    : {len(universe)} (genome-wide catalog)")
    print(f"  gene_identifier  : {len(gid)} HGNC entries")
    print(f"  triage rows      : {len(triage)} (sonnet+ncbi, fix-preferred)")

    print("--- joining ---")
    out_rows: list[dict[str, object]] = []
    n_with_uniprot = 0
    n_with_hgnc_id = 0
    n_with_triage = 0
    for sym, urow in universe.items():
        # Stable IDs from gene_identifier_public; fall back to the
        # universe row's uniprot_acc if gid has nothing.
        gid_row = gid.get(sym, {})
        uniprot_acc = urow.get("uniprot_acc") or gid_row.get("uniprot_acc") or ""
        hgnc_id = gid_row.get("hgnc_id") or ""
        ensembl_gene = gid_row.get("ensembl_gene") or ""
        ncbi_gene_id = gid_row.get("ncbi_gene_id") or ""
        if uniprot_acc:
            n_with_uniprot += 1
        if hgnc_id:
            n_with_hgnc_id += 1

        tr_row = triage.get(sym, {})
        if tr_row:
            n_with_triage += 1

        out_rows.append(
            {
                "hgnc_id": hgnc_id,
                "hgnc_symbol": sym,
                "uniprot_acc": uniprot_acc,
                "ensembl_gene": ensembl_gene,
                "ncbi_gene_id": ncbi_gene_id,
                "uniprot_surface_flag": urow.get("uniprot_surface_flag", 0) or 0,
                "go_surface_flag": urow.get("go_surface_flag", 0) or 0,
                "hpa_surface_flag": urow.get("hpa_surface_flag", 0) or 0,
                "surfy_surface_flag": urow.get("surfy_surface_flag", 0) or 0,
                "cspa_surface_flag": urow.get("cspa_surface_flag", 0) or 0,
                "n_sources_surface": urow.get("n_sources_surface", 0) or 0,
                "sonnet_verdict": tr_row.get("sonnet_verdict", ""),
                "sonnet_reason": tr_row.get("sonnet_reason", ""),
                "universe_version": UNIVERSE_VERSION,
            }
        )
    print(f"  joined rows      : {len(out_rows)}")
    print(f"    with uniprot   : {n_with_uniprot}")
    print(f"    with hgnc_id   : {n_with_hgnc_id}")
    print(f"    with triage    : {n_with_triage}")
    return out_rows


def _write_tsv(rows: list[dict[str, object]]) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(COLS)
        for r in sorted(rows, key=lambda x: str(x["hgnc_symbol"])):
            w.writerow([r[c] for c in COLS])
    size = OUT_PATH.stat().st_size
    print(f"--- wrote TSV ---")
    print(f"  path             : {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  size             : {size / 1024:.1f} KB ({size / (1024*1024):.2f} MB)")
    if size > 5 * 1024 * 1024:
        print("  WARNING: > 5 MB practical cap for un-LFS raw.github serving.")
    elif size > 100 * 1024 * 1024:
        print("  ERROR: > 100 MB GitHub hard cap on non-LFS files.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the TSV. Default is dry-run (counts only).",
    )
    args = parser.parse_args()

    load_env()
    rows = _build_rows()
    if args.execute:
        _write_tsv(rows)
    else:
        print("--- dry run — pass --execute to write the TSV ---")
        print("  preview of first 5 rows:")
        for r in rows[:5]:
            print(f"    {r['hgnc_symbol']:12s} | hgnc_id={r['hgnc_id']:>14s} | "
                  f"uniprot={r['uniprot_acc']:>10s} | n_sources={r['n_sources_surface']} | "
                  f"sonnet={r['sonnet_verdict']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
