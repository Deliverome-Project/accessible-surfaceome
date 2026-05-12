"""Resolver-collision fix — delete contaminated triage_run rows and
re-run the affected genes under the canonical Sonnet/ncbi sweep.

Context: a bug in ``gene_lookup._uniprot_search_by_symbol`` (UniProt
``gene_exact:`` queries with ``size=1`` and no primary-name preference)
caused a subset of cells in ``run_id=genome_full_sonnet_ncbi_v1`` to
be answered by Sonnet against the wrong protein — entries where the
query symbol appears as a synonym of a different gene. CCR4 was fed
NOCT (Q9UK39), SMO was fed SMOX (Q9NWM0), etc. See the resolver-fix
commit and the audit at
``data/analysis/resolver_definitive_audit.tsv``.

This script:

  1. Loads the audit TSV (one row per (gene_symbol, old_uniprot,
     new_uniprot) where the old and new resolver disagree).
  2. Snapshots every contaminated D1 row to
     ``data/analysis/resolver_collision_d1_backup_<ts>.tsv`` so the
     mutation is fully reversible.
  3. ``DELETE FROM triage_run WHERE run_id=? AND gene_symbol IN (...)``
     in 50-symbol chunks (D1's parameter cap is ~100). The child
     ``triage_search_log`` rows cascade via the schema's
     ``ON DELETE CASCADE`` clause — empty for variant=ncbi cells
     anyway, but the cascade keeps the data model self-consistent.
  4. Invokes ``scripts/triage_subbench_runner.py`` with
     ``--gene-list`` pointing at the affected symbols, ``--variants
     ncbi``, ``--model claude-sonnet-4-6``, ``--replicates 1``, and
     ``--d1 --run-id genome_full_sonnet_ncbi_v1``. New rows land in
     D1 under the same canonical run, replacing the deleted ones.

Safety properties (verified before this script was written):

  * DELETE is exactly 1 row per gene_symbol — no symbol has >1 row
    under the canonical run, so we don't risk over-deleting.
  * The runner's resolver path uses a new cache key (size=25,
    fields=accession,gene_names) so it cannot accidentally re-use
    the old wrong-accession cache entries.
  * The backup TSV preserves every column of every deleted row,
    including the full verdict_reasoning prose — full restore is a
    single INSERT.

Usage::

    uv run python scripts/fix_resolver_collisions.py            # dry-run
    uv run python scripts/fix_resolver_collisions.py --execute  # do it

Estimated cost: ~$0.0105 per cell × N affected cells ≈ $2 for ~200
cells. Wall time ~5 min with the runner's default concurrency.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import subprocess
import sys
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

load_env()

AUDIT_TSV = REPO_ROOT / "data/analysis/resolver_definitive_audit.tsv"
ANALYSIS_DIR = REPO_ROOT / "data/analysis"
RUNNER = REPO_ROOT / "scripts/triage_subbench_runner.py"
CANONICAL_RUN_ID = "genome_full_sonnet_ncbi_v1"
CHUNK = 50  # D1 SQL-variable cap is ~100; stay well under


def _load_affected() -> list[dict[str, str]]:
    if not AUDIT_TSV.exists():
        sys.exit(
            f"missing audit TSV: {AUDIT_TSV.relative_to(REPO_ROOT)}\n"
            f"run scripts/audit_resolver_collisions.py first."
        )
    with AUDIT_TSV.open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _backup_and_delete(affected: list[dict[str, str]], *, execute: bool) -> int:
    symbols = [r["gene_symbol"] for r in affected]
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = ANALYSIS_DIR / f"resolver_collision_d1_backup_{ts}.tsv"

    backed_up = 0
    deleted = 0
    with D1Client() as d1:
        # 1. SNAPSHOT — pull every row that's about to be deleted
        all_rows: list[dict] = []
        for i in range(0, len(symbols), CHUNK):
            chunk = symbols[i:i + CHUNK]
            placeholders = ",".join("?" * len(chunk))
            rows = d1.query(
                f"SELECT * FROM triage_run "
                f"WHERE run_id = ? AND gene_symbol IN ({placeholders});",
                [CANONICAL_RUN_ID, *chunk],
            )
            all_rows.extend(rows)
        backed_up = len(all_rows)
        if all_rows:
            with backup_path.open("w", newline="") as fh:
                w = csv.DictWriter(
                    fh, fieldnames=list(all_rows[0].keys()), delimiter="\t"
                )
                w.writeheader()
                w.writerows(all_rows)
            print(f"  ✓ snapshot → {backup_path.relative_to(REPO_ROOT)} "
                  f"({backed_up} rows)")
        else:
            print("  (no rows to back up — nothing matched)")

        # 2. DELETE — chunked to dodge D1's SQL-variable cap
        if not execute:
            print(f"  (dry-run) would DELETE {backed_up} rows")
            return backed_up

        for i in range(0, len(symbols), CHUNK):
            chunk = symbols[i:i + CHUNK]
            placeholders = ",".join("?" * len(chunk))
            # D1Client.query() handles both reads and writes — write returns
            # an empty result set, which we discard. There is no separate
            # execute() method.
            d1.query(
                f"DELETE FROM triage_run "
                f"WHERE run_id = ? AND gene_symbol IN ({placeholders});",
                [CANONICAL_RUN_ID, *chunk],
            )
            deleted += len(chunk)
            print(f"  ✓ deleted chunk {i}-{i + len(chunk)} ({deleted}/{len(symbols)})")
    return backed_up


def _write_rerun_input(affected: list[dict[str, str]]) -> Path:
    out = ANALYSIS_DIR / "resolver_collision_rerun_input.tsv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["gene_symbol", "uniprot_acc"], delimiter="\t"
        )
        w.writeheader()
        for r in affected:
            w.writerow({
                "gene_symbol": r["gene_symbol"],
                "uniprot_acc": r["new_uniprot"],
            })
    print(f"  ✓ wrote rerun input → {out.relative_to(REPO_ROOT)} ({len(affected)} rows)")
    return out


def _run_runner(gene_list_tsv: Path, *, execute: bool) -> int:
    cmd = [
        "uv", "run", "python", str(RUNNER),
        "--gene-list", str(gene_list_tsv),
        "--variants", "ncbi",
        "--model", "claude-sonnet-4-6",
        "--replicates", "1",
        "--d1",
        "--run-id", CANONICAL_RUN_ID,
        "--concurrency", "8",
    ]
    print()
    print("  Runner command:")
    print("    " + " ".join(cmd))
    if not execute:
        print("  (dry-run) skipping runner invocation")
        return 0
    print()
    return subprocess.call(cmd, cwd=REPO_ROOT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--execute", action="store_true",
        help="Actually perform the DELETE + re-run. Without this flag, "
             "the script writes the backup snapshot and prints the "
             "planned commands but does NOT mutate D1.",
    )
    args = ap.parse_args()

    affected = _load_affected()
    print(f"Loaded {len(affected)} affected symbols from "
          f"{AUDIT_TSV.relative_to(REPO_ROOT)}")
    print()

    print("Step 1: snapshot + DELETE the contaminated rows")
    n_deleted = _backup_and_delete(affected, execute=args.execute)
    print()

    print("Step 2: write the runner's --gene-list input TSV")
    gene_list = _write_rerun_input(affected)

    print()
    print("Step 3: re-run the affected cells under the canonical run_id")
    rc = _run_runner(gene_list, execute=args.execute)

    print()
    if args.execute:
        print(f"Done. Deleted {n_deleted} rows; runner exited with rc={rc}.")
        print("Backup retained for rollback: data/analysis/resolver_collision_d1_backup_*.tsv")
    else:
        print("Dry-run complete. Re-run with --execute to apply.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
