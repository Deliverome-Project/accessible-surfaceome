#!/usr/bin/env python3
"""Backfill recovered UniProt accessions onto sonnet_only rows in
``candidate_universe_public`` on the public ``surfaceome_public`` D1.

Background
----------
The genome-wide catalog the Worker's ``/v1/catalog`` endpoint serves
lives in ``candidate_universe_public``. Each row is one protein-coding
human gene + its per-DB surface-vote profile, written by
``scripts/upload_candidate_universe_to_d1.py`` against the M1 merge
artifact ``data/processed/candidate_universe/candidate_universe.tsv``.

That artifact carries a UniProt accession only for genes the M1 merge
saw (i.e. genes any of the 5 surface DBs voted for). The v2 universe
update added a second arm — genes that no DB voted for but the
sonnet triage classified as ``yes`` or ``contextual`` (the
"sonnet_only" rows of ``candidate_universe_v2.tsv``). The v2 build
script lost the UniProt accs for those rows (per memory
``v2_sonnet_only_missing_uniprot``), so when the catalog uploader ran
it wrote 846 rows with ``uniprot_acc=''`` for the sonnet_only genes.
Downstream consumers (the catalog UI, the Schweke join, the PVRIG
figure) silently drop these because their joins are uniprot-keyed.

The recovered accs live in
``data/external/schweke_homomer_atlas/surfaceome_x_schweke_homomers_full.tsv``
(per-row ``uniprot_accession`` column populated from D1's
``triage_run_public`` + UniProt + HGNC for any sonnet_only row the v2
TSV left blank). This script reads them and UPDATEs the corresponding
``candidate_universe_public`` rows in-place: same primary-key
``(universe_version, gene_symbol)`` end of the PK, only the
``uniprot_acc`` field changes from ``''`` to the recovered value.

Safe:
  * UPDATE (not DELETE+INSERT), so no risk of dropping a row we'd
    fail to re-insert.
  * Only touches rows where ``uniprot_acc=''`` — won't clobber M1-side
    rows that already have an acc.
  * Idempotent: a second run finds zero empty rows and exits clean.

Usage::

    uv run python scripts/backfill_sonnet_only_uniprots_to_d1.py             # dry-run
    uv run python scripts/backfill_sonnet_only_uniprots_to_d1.py --execute   # push
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

# Source TSV — the surfaceome × Schweke join file, which carries the
# recovered uniprots for sonnet_only genes.
SOURCE_TSV = (
    REPO_ROOT
    / "data"
    / "external"
    / "schweke_homomer_atlas"
    / "surfaceome_x_schweke_homomers_full.tsv"
)

# The universe version currently in D1. The release dance is to bump
# this when re-uploading whole new builds, but a sonnet_only acc
# backfill is a correction to the *current* release, not a new
# release, so we patch in place. If you bump the canonical universe
# version, update this constant too.
UNIVERSE_VERSION = "cu_2026_05_12_post_silentdrop_fix"


def _read_recovered_accs() -> list[tuple[str, str]]:
    """Return [(gene_symbol, uniprot_acc), …] for every sonnet_only
    row in the source TSV that has a non-empty uniprot."""
    out: list[tuple[str, str]] = []
    with SOURCE_TSV.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if (
                row.get("source") == "sonnet_only"
                and (row.get("uniprot_accession") or "").strip()
            ):
                out.append((row["gene_symbol"], row["uniprot_accession"].strip()))
    return out


def _find_empty_uniprot_targets(
    d1: D1Client, candidates: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Filter ``candidates`` to those whose D1 row currently has
    ``uniprot_acc=''``. Anything already non-empty is left untouched
    so we don't overwrite an M1-side resolution with a sonnet-side
    one (or vice versa)."""
    targets: list[tuple[str, str]] = []
    CHUNK = 50  # D1 caps placeholders well below SQLite's upstream limit
    for i in range(0, len(candidates), CHUNK):
        batch = candidates[i : i + CHUNK]
        symbols = [s for s, _ in batch]
        placeholders = ",".join("?" * len(symbols))
        sql = (
            "SELECT gene_symbol FROM candidate_universe_public "
            "WHERE universe_version = ? AND uniprot_acc = '' "
            f"AND gene_symbol IN ({placeholders});"
        )
        rows = d1.query(sql, [UNIVERSE_VERSION, *symbols])
        empty_symbols = {r["gene_symbol"] for r in rows}
        for sym, acc in batch:
            if sym in empty_symbols:
                targets.append((sym, acc))
    return targets


def _push_updates(d1: D1Client, targets: list[tuple[str, str]]) -> None:
    """Execute the per-row UPDATE. One statement per row — D1's HTTP
    API doesn't accept multi-statement batches, and 846 rows finishes
    in ~30-60 s sequentially."""
    sql = (
        "UPDATE candidate_universe_public "
        "SET uniprot_acc = ?, synced_at = datetime('now') "
        "WHERE universe_version = ? AND gene_symbol = ? AND uniprot_acc = '';"
    )
    for i, (sym, acc) in enumerate(targets):
        d1.query(sql, [acc, UNIVERSE_VERSION, sym])
        if (i + 1) % 50 == 0 or i + 1 == len(targets):
            print(f"  update progress  : {i + 1}/{len(targets)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Push UPDATEs to D1. Default is dry-run (counts only).",
    )
    args = parser.parse_args()

    load_env()
    print("--- reading recovered sonnet_only accs ---")
    candidates = _read_recovered_accs()
    print(f"  candidates       : {len(candidates)} sonnet_only rows with uniprot")

    print("--- finding rows that still have uniprot_acc='' in D1 ---")
    with D1Client.public() as d1:
        targets = _find_empty_uniprot_targets(d1, candidates)
    print(f"  targets          : {len(targets)} (skipping already-resolved rows)")
    skipped = len(candidates) - len(targets)
    if skipped:
        print(f"  already-resolved : {skipped} (left untouched)")

    if not targets:
        print("--- nothing to do, exiting ---")
        return 0

    if args.execute:
        print("--- pushing UPDATEs to D1 ---")
        with D1Client.public() as d1:
            _push_updates(d1, targets)
        # Verify
        with D1Client.public() as d1:
            r = d1.query(
                "SELECT COUNT(*) AS n FROM candidate_universe_public "
                "WHERE universe_version = ? AND uniprot_acc = '';",
                [UNIVERSE_VERSION],
            )
            remaining = r[0]["n"]
        print(f"--- done. remaining empty uniprot rows: {remaining} ---")
    else:
        print("--- dry run — pass --execute to push to D1 ---")
        print("  preview of first 5 updates:")
        for sym, acc in targets[:5]:
            print(f"    {sym:12s} → uniprot_acc='{acc}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
