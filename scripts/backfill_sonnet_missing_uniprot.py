"""Backfill missing ``uniprot_acc`` on sonnet-positive D1 rows.

**Why this script exists.** The triage runner writes
``triage_run_public`` rows whose ``uniprot_acc`` comes from
``gene_identifier_public`` at triage time. When the resolver returned
``None`` for a gene (134 such genes in the mirror as of 2026-06-07),
the triage row inherits ``NULL`` and the bug cascades into
``candidate_universe_public`` (which mirrors from the same source).

This audit-and-fix script identifies every sonnet-positive D1 row with
``uniprot_acc IS NULL OR ''`` across three tables and backfills via a
two-tier resolution:

1. First try ``gene_identifier_public`` (the canonical resolver
   mirror) — this catches genes that gained a uniprot since the
   triage run.
2. Fallback: UniProt REST ``gene_exact:`` search — catches the genes
   the resolver missed entirely. The recovered accession is also
   written back to ``gene_identifier_public`` so the next triage run
   has it.

**Idempotent.** Safe to run repeatedly — the ``WHERE uniprot_acc IS
NULL OR uniprot_acc = ''`` guard means already-populated rows are
left untouched.

Run from the repo root (writes go to public D1):

    uv run python scripts/backfill_sonnet_missing_uniprot.py            # dry-run
    uv run python scripts/backfill_sonnet_missing_uniprot.py --execute  # write
"""
from __future__ import annotations
import argparse
import time
import urllib.parse

import httpx

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env


def find_affected_symbols(d1: D1Client) -> list[str]:
    """Symbols with sonnet yes/contextual but no uniprot_acc in either
    ``triage_run_public`` or ``candidate_universe_public``."""
    # candidate_universe_public sonnet-positive rows missing uniprot
    cu_rows = d1.query(
        "SELECT DISTINCT cu.gene_symbol AS sym FROM candidate_universe_public cu "
        "JOIN triage_run_public t "
        "  ON t.gene_symbol = cu.gene_symbol "
        " AND t.model LIKE '%sonnet%' "
        " AND t.prompt_variant = 'ncbi' "
        "WHERE (cu.uniprot_acc IS NULL OR cu.uniprot_acc = '') "
        "  AND t.predicted_verdict IN ('yes', 'contextual')",
        [],
    )
    # triage_run_public sonnet+ncbi rows missing uniprot (covers verdict='no' too)
    trp_rows = d1.query(
        "SELECT DISTINCT gene_symbol AS sym FROM triage_run_public "
        "WHERE model LIKE '%sonnet%' AND prompt_variant = 'ncbi' "
        "  AND (uniprot_acc IS NULL OR uniprot_acc = '')",
        [],
    )
    return sorted({r["sym"] for r in cu_rows} | {r["sym"] for r in trp_rows})


def resolve_via_resolver(d1: D1Client, symbols: list[str]) -> dict[str, str]:
    """Look up uniprot via gene_identifier_public for as many symbols as
    possible. Batches of 80 to stay under D1's parameter-count limits."""
    found: dict[str, str] = {}
    BATCH = 80
    for chunk_start in range(0, len(symbols), BATCH):
        chunk = symbols[chunk_start : chunk_start + BATCH]
        ph = ",".join("?" for _ in chunk)
        rows = d1.query(
            f"SELECT hgnc_symbol, uniprot_acc FROM gene_identifier_public "
            f"WHERE hgnc_symbol IN ({ph}) AND uniprot_acc IS NOT NULL AND uniprot_acc != ''",
            chunk,
        )
        for r in rows:
            found[r["hgnc_symbol"]] = r["uniprot_acc"]
    return found


def resolve_via_uniprot_rest(symbols: list[str]) -> dict[str, str]:
    """Fallback: UniProt REST ``gene_exact:`` search per symbol. Tries
    ``reviewed:true`` (Swiss-Prot) first, then any reviewed status."""
    found: dict[str, str] = {}
    headers = {"User-Agent": "accessible-surfaceome-backfill/1.0"}
    with httpx.Client(timeout=15.0, headers=headers) as c:
        for sym in symbols:
            for q in (
                f"gene_exact:{sym} AND organism_id:9606 AND reviewed:true",
                f"gene_exact:{sym} AND organism_id:9606",
            ):
                url = (
                    "https://rest.uniprot.org/uniprotkb/search?"
                    f"query={urllib.parse.quote(q)}&fields=accession&format=json&size=1"
                )
                try:
                    r = c.get(url)
                    if r.status_code != 200:
                        continue
                    data = r.json()
                    results = data.get("results", [])
                    if results:
                        acc = results[0].get("primaryAccession")
                        if acc:
                            found[sym] = acc
                            break
                except Exception:
                    continue
                time.sleep(0.2)
    return found


def apply_backfill(d1: D1Client, mapping: dict[str, str]) -> dict[str, int]:
    """Issue UPDATE statements across the three affected tables.

    The same uniprot_acc lands in ``candidate_universe_public``,
    ``triage_run_public``, and ``gene_identifier_public`` so the
    resolver-miss cascade is closed at every level."""
    counts = {"cu": 0, "trp": 0, "gi": 0}
    for sym, acc in mapping.items():
        d1.query(
            "UPDATE candidate_universe_public SET uniprot_acc = ? "
            "WHERE gene_symbol = ? AND (uniprot_acc IS NULL OR uniprot_acc = '')",
            [acc, sym],
        )
        counts["cu"] += 1
        d1.query(
            "UPDATE triage_run_public SET uniprot_acc = ? "
            "WHERE gene_symbol = ? AND (uniprot_acc IS NULL OR uniprot_acc = '')",
            [acc, sym],
        )
        counts["trp"] += 1
        d1.query(
            "UPDATE gene_identifier_public SET uniprot_acc = ? "
            "WHERE hgnc_symbol = ? AND (uniprot_acc IS NULL OR uniprot_acc = '')",
            [acc, sym],
        )
        counts["gi"] += 1
    return counts


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true", help="Write to D1 (default: dry-run)")
    args = ap.parse_args()

    import os
    cfg = D1Config(
        account_id=os.environ["CLOUDFLARE_ACCOUNT_ID"],
        database_id=os.environ["CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID"],
        api_token=os.environ["CLOUDFLARE_API_TOKEN"],
    )
    with D1Client(cfg) as d1:
        affected = find_affected_symbols(d1)
        print(f"Affected genes: {len(affected)}")
        if not affected:
            print("Nothing to backfill — all sonnet rows have uniprot_acc populated.")
            return 0

        # Resolution: try resolver mirror first, then UniProt REST
        found = resolve_via_resolver(d1, affected)
        print(f"  Resolved via gene_identifier_public: {len(found)} / {len(affected)}")
        unresolved = [s for s in affected if s not in found]
        if unresolved:
            rest_found = resolve_via_uniprot_rest(unresolved)
            found.update(rest_found)
            print(f"  Resolved via UniProt REST fallback: {len(rest_found)} / {len(unresolved)}")
        still_missing = [s for s in affected if s not in found]
        if still_missing:
            print(f"  Still unresolved (would skip): {still_missing[:10]}")

        print(f"\nResolutions ready to apply: {len(found)} of {len(affected)} affected.")
        if not args.execute:
            print("Dry-run only. Pass --execute to write to D1.")
            return 0

        counts = apply_backfill(d1, found)
        print(f"\nIssued: cu={counts['cu']}, trp={counts['trp']}, gi={counts['gi']} UPDATEs")

        # Verify
        rows = d1.query(
            "SELECT COUNT(*) as n FROM triage_run_public "
            "WHERE model LIKE '%sonnet%' AND prompt_variant = 'ncbi' "
            "AND (uniprot_acc IS NULL OR uniprot_acc = '')",
            [],
        )
        print(f"  triage_run_public still missing: {rows[0]['n']}")
        rows = d1.query(
            "SELECT COUNT(DISTINCT cu.gene_symbol) as n FROM candidate_universe_public cu "
            "JOIN triage_run_public t ON t.gene_symbol = cu.gene_symbol "
            "AND t.model LIKE '%sonnet%' AND t.prompt_variant = 'ncbi' "
            "WHERE (cu.uniprot_acc IS NULL OR cu.uniprot_acc = '') "
            "AND t.predicted_verdict IN ('yes','contextual')",
            [],
        )
        print(f"  candidate_universe_public sonnet-positive still missing: {rows[0]['n']}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
