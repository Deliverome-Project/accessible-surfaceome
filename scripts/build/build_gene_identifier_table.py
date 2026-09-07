"""Populate D1's ``gene_identifier`` table by resolving every cohort
gene through the HGNC-ID-keyed resolver.

This is the single-source-of-truth build for stable identifiers. After
running once, every downstream tool (D1 query, viewer, figure script,
agent tool) can look up the canonical (uniprot_acc, ensembl_gene,
ncbi_gene_id) for a gene via a sub-millisecond D1 SELECT instead of
re-resolving from symbol — which is where the resolver bugs entered
the pipeline historically (see
``scripts/audit_resolver_hgnc_id_v3.py``).

Input:
  * ``data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv``
    — 19,464 rows with HGNC IDs (100% coverage).

Output:
  * ``gene_identifier`` rows in the private ``surfaceome_agents`` D1.
    The mirror sync script propagates to ``surfaceome_public.gene_identifier_public``.

Cost: every cohort symbol incurs at most one HGNC API call + one UniProt
API call (both cached for 90 + 30 days respectively). On a cold cache the
full run takes ~60-90 minutes serial (well under the public APIs' rate
limits at concurrency=3). On a warm cache (e.g. after running the audit
first), well under 5 minutes.

Resolver version is pinned at run time from ``git rev-parse HEAD`` so a
future resolver refinement is detectable by comparing
``MAX(resolver_version)`` against the current HEAD.

Idempotent — UPSERTs on hgnc_id, so re-runs after resolver upgrades
update in place. Use ``--force`` to overwrite even when the current row
was resolved with the same resolver version (useful after picker logic
changes within a single SHA).

Usage::

    uv run python scripts/build_gene_identifier_table.py            # dry-run
    uv run python scripts/build_gene_identifier_table.py --execute  # do it
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools.gene_lookup import (
    _entry_primary_symbol,
    _hgnc_record_by_id,
    _pick_canonical_uniprot,
    _uniprot_entry,
    _uniprot_search_by_symbol,
)

load_env()

COHORT_TSV = (
    REPO_ROOT
    / "data"
    / "external"
    / "ncbi_gene_info"
    / "Homo_sapiens.protein_coding.with_hgnc.tsv"
)

# Resolver concurrency. Lower than the audit's 3 to stay under the public
# APIs' rate limits over a longer wall-clock run; the audit's per-symbol
# work is bounded, this one's per-symbol work has extra UniProt fetches
# (one per candidate in HGNC's xref, deeper for merge-chain follow).
N_WORKERS = 3


def _resolver_version() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), text=True
        ).strip()
    except subprocess.CalledProcessError:
        return "unknown"


def _load_cohort() -> list[tuple[str, str]]:
    """Return (hgnc_id, gene_symbol) pairs from the cohort. The two
    columns we need; everything else is reconstructed from HGNC + UniProt
    at resolve time."""

    out: list[tuple[str, str]] = []
    with COHORT_TSV.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            hgnc_id = row.get("hgnc_id")
            symbol = row.get("gene_symbol")
            if hgnc_id and symbol:
                out.append((hgnc_id, symbol))
    return out


def _classify_path(hgnc_record: dict, *, used_fallback: bool, used_prev_symbol: bool) -> str:
    """Bucket which resolver path produced the row, for audit visibility.
    Mirrors the branch structure in resolve_by_hgnc_id."""

    if used_prev_symbol:
        return "hgnc_prev_symbol_fallback"
    if used_fallback:
        return "hgnc_symbol_fallback"
    xref_count = len((hgnc_record or {}).get("uniprot_ids") or [])
    return "hgnc_xref_single" if xref_count == 1 else "hgnc_xref_primary_name_age"


def _resolve_for_row(hgnc_id: str, cohort_symbol: str, *, http) -> dict | None:
    """Resolve one cohort row to a gene_identifier dict, or None if the
    resolver can't reach a UniProt acc (cohort row is genuinely out of
    study scope — gets logged but not row'd)."""

    try:
        hgnc_record = _hgnc_record_by_id(hgnc_id, http=http) or {}
    except Exception:
        hgnc_record = {}

    used_fallback = False
    used_prev_symbol = False
    uniprot_acc: str | None = None
    xref = list(hgnc_record.get("uniprot_ids") or [])
    primary_symbol = (hgnc_record.get("symbol") or "").strip()

    if xref:
        try:
            uniprot_acc = _pick_canonical_uniprot(
                xref, http=http, prefer_primary_name=primary_symbol or None
            )
        except LookupError:
            uniprot_acc = None
    elif primary_symbol:
        uniprot_acc = _uniprot_search_by_symbol(primary_symbol, http=http)
        used_fallback = True
        if uniprot_acc is None:
            for prev in hgnc_record.get("prev_symbol") or []:
                uniprot_acc = _uniprot_search_by_symbol(prev, http=http)
                if uniprot_acc:
                    used_prev_symbol = True
                    break

    needs_review = 0
    ensembl_canonical_protein: str | None = None
    if uniprot_acc:
        try:
            entry = _uniprot_entry(uniprot_acc, http=http)
            picked_primary = (_entry_primary_symbol(entry) or "").strip().upper()
            if primary_symbol and picked_primary != primary_symbol.upper():
                needs_review = 1
            # Pull the Ensembl canonical protein from xrefs if present.
            for x in (entry.get("uniProtKBCrossReferences") or []):
                if x.get("database") == "Ensembl":
                    for prop in x.get("properties") or []:
                        if prop.get("key") == "ProteinId":
                            ensembl_canonical_protein = prop.get("value")
                            break
                    if ensembl_canonical_protein:
                        break
        except Exception:
            pass

    entrez_id = hgnc_record.get("entrez_id")
    return {
        "hgnc_id": hgnc_id,
        "hgnc_symbol": primary_symbol or cohort_symbol,
        "cohort_symbol": cohort_symbol,
        "uniprot_acc": uniprot_acc,
        "ncbi_gene_id": int(entrez_id) if entrez_id else None,
        "ensembl_gene": hgnc_record.get("ensembl_gene_id"),
        "ensembl_canonical_protein": ensembl_canonical_protein,
        "resolver_path": _classify_path(
            hgnc_record, used_fallback=used_fallback, used_prev_symbol=used_prev_symbol
        ),
        "hgnc_xref_count": len(xref),
        "needs_review": needs_review,
    }


def _upsert(rows: list[dict], *, resolver_version: str, execute: bool) -> int:
    """Chunked UPSERT into D1 ``gene_identifier``. SQLite UPSERT syntax
    (ON CONFLICT) is supported by D1."""

    if not rows:
        return 0
    if not execute:
        print(f"  (dry-run) would UPSERT {len(rows)} rows")
        return 0

    sql = """
        INSERT INTO gene_identifier (
            hgnc_id, hgnc_symbol, cohort_symbol,
            uniprot_acc, ncbi_gene_id, ensembl_gene, ensembl_canonical_protein,
            resolver_path, resolver_version, resolved_at,
            hgnc_xref_count, needs_review
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)
        ON CONFLICT(hgnc_id) DO UPDATE SET
            hgnc_symbol               = excluded.hgnc_symbol,
            cohort_symbol             = excluded.cohort_symbol,
            uniprot_acc               = excluded.uniprot_acc,
            ncbi_gene_id              = excluded.ncbi_gene_id,
            ensembl_gene              = excluded.ensembl_gene,
            ensembl_canonical_protein = excluded.ensembl_canonical_protein,
            resolver_path             = excluded.resolver_path,
            resolver_version          = excluded.resolver_version,
            resolved_at               = datetime('now'),
            hgnc_xref_count           = excluded.hgnc_xref_count,
            needs_review              = excluded.needs_review;
    """
    n = 0
    with D1Client() as d1:
        for r in rows:
            d1.query(
                sql,
                [
                    r["hgnc_id"], r["hgnc_symbol"], r["cohort_symbol"],
                    r["uniprot_acc"], r["ncbi_gene_id"], r["ensembl_gene"],
                    r["ensembl_canonical_protein"],
                    r["resolver_path"], resolver_version,
                    r["hgnc_xref_count"], r["needs_review"],
                ],
            )
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--execute", action="store_true",
                    help="Actually UPSERT into D1. Without this, runs the resolver "
                         "and reports counts but doesn't write.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Only resolve N cohort rows (smoke-test).")
    args = ap.parse_args()

    cohort = _load_cohort()
    if args.limit:
        cohort = cohort[: args.limit]
    print(f"Cohort: {len(cohort):,} (hgnc_id, gene_symbol) pairs")
    resolver_version = _resolver_version()
    print(f"Resolver version: {resolver_version[:12]}…")
    print()

    http = open_default_client()
    print_lock = threading.Lock()
    done = [0]
    rows: list[dict] = []
    no_acc = 0
    errors = 0
    start = time.time()

    def work(pair):
        hgnc_id, sym = pair
        try:
            row = _resolve_for_row(hgnc_id, sym, http=http)
        except Exception as e:
            return ("error", hgnc_id, sym, str(e)[:200])
        if row is None or row["uniprot_acc"] is None:
            return ("no_acc", hgnc_id, sym, row)
        return ("ok", hgnc_id, sym, row)

    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
        futures = {ex.submit(work, p): p for p in cohort}
        for fut in as_completed(futures):
            kind, hgnc_id, sym, payload = fut.result()
            if kind == "ok":
                rows.append(payload)
            elif kind == "no_acc":
                no_acc += 1
                if payload is not None:
                    # Still upsert the row (with uniprot_acc=NULL) so
                    # the audit trail is complete.
                    rows.append(payload)
            else:
                errors += 1
            with print_lock:
                done[0] += 1
                if done[0] % 500 == 0 or done[0] == len(cohort):
                    elapsed = time.time() - start
                    rate = done[0] / elapsed if elapsed > 0 else 0
                    eta = (len(cohort) - done[0]) / rate if rate > 0 else 0
                    print(
                        f"  [{done[0]:>6}/{len(cohort)}]  ok={len(rows)}  "
                        f"no_acc={no_acc}  errors={errors}  "
                        f"rate={rate:.0f}/s  eta={eta:.0f}s",
                        flush=True,
                    )
    http.close()

    print()
    n_upserted = _upsert(rows, resolver_version=resolver_version, execute=args.execute)
    print()
    print(f"Resolved:    {len(rows):,}")
    print(f"  with acc:  {len(rows) - no_acc:,}")
    print(f"  no acc:    {no_acc:,}  (HGNC returned no UniProt and symbol fallback also missed)")
    print(f"Errors:      {errors:,}")
    print(f"UPSERTed:    {n_upserted:,}" if args.execute else "(dry-run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
