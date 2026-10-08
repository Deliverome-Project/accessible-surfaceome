#!/usr/bin/env python
"""Repair private D1's ``compara_paralog.ecd_pct_similarity`` drift.

``cloudflare/d1_schema.sql`` declares the column; the live private table does
not have it. Surfaced by ``merge_paralog_release.py``, which reconciles its
column list against the live table and warned rather than failing — the merge
proceeded on the intersection, so no data was lost, but the two D1s are now
structurally different.

This does not gate a deep-dive run: the deterministic loader
(``d1_deterministic._query_public``) reads the PUBLIC mirror, which has the
column populated. It matters because private is the restore source — a
recovery from the R2 dumps would silently reintroduce the drift, and a future
sync that assumes column parity would fail or drop data.

Two steps, both idempotent:

  1. ``ALTER TABLE compara_paralog ADD COLUMN ecd_pct_similarity REAL`` when
     the column is absent.
  2. Copy the non-NULL values across from public, keyed on the shared PK
     ``(paralog_version, human_ensembl_gene, paralog_ensembl_gene)``.

Only ~683 of 92k pairs carry a value (it is computed for close pairs at >=80%
full-length identity), so the copy is small. Statements go out from a small
thread pool because D1's HTTP API takes one statement per call; each UPDATE is
idempotent on its key, which is what makes ``D1Client``'s at-least-once retry
safe here.

Usage::

    uv run python scripts/cloud/backfill_private_paralog_similarity.py
    uv run python scripts/cloud/backfill_private_paralog_similarity.py --execute
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env

COLUMN = "ecd_pct_similarity"


def _has_column(d1: D1Client) -> bool:
    return COLUMN in {
        r["name"] for r in d1.query("PRAGMA table_info(compara_paralog);", [])
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true", help="default is dry-run")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv)
    load_env()

    with D1Client(config=D1Config.from_env_public()) as pub:
        if not _has_column(pub):
            raise SystemExit(
                "public compara_paralog is ALSO missing the column — nothing to "
                "copy from. Recompute it upstream instead of running this."
            )
        rows = pub.query(
            f"SELECT paralog_version, human_ensembl_gene, paralog_ensembl_gene, "
            f"{COLUMN} FROM compara_paralog WHERE {COLUMN} IS NOT NULL;",
            [],
        )
    print(f"public rows carrying {COLUMN}: {len(rows):,}")

    with D1Client() as priv:
        present = _has_column(priv)
        print(f"private compara_paralog has {COLUMN}: {present}")
        if not args.execute:
            print(
                f"  [dry-run] would {'' if present else 'ADD COLUMN, then '}"
                f"copy {len(rows):,} value(s). Re-run with --execute"
            )
            return 0

        if not present:
            priv.query(
                f"ALTER TABLE compara_paralog ADD COLUMN {COLUMN} REAL;", []
            )
            print(f"  ALTER TABLE: added {COLUMN}")

        sql = (
            f"UPDATE compara_paralog SET {COLUMN} = ? WHERE paralog_version = ? "
            f"AND human_ensembl_gene = ? AND paralog_ensembl_gene = ?;"
        )
        done = failed = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    priv.query,
                    sql,
                    [
                        r[COLUMN],
                        r["paralog_version"],
                        r["human_ensembl_gene"],
                        r["paralog_ensembl_gene"],
                    ],
                ): r
                for r in rows
            }
            for f in as_completed(futures):
                try:
                    f.result()
                    done += 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    r = futures[f]
                    print(f"  FAILED {r['human_ensembl_gene']}: {exc}")
        print(f"  updated {done:,}/{len(rows):,} (failed {failed})")

        got = priv.query(
            f"SELECT COUNT(*) n FROM compara_paralog WHERE {COLUMN} IS NOT NULL;",
            [],
        )[0]["n"]
        print(f"  private now carries {COLUMN} on {got:,} row(s)")
        if got != len(rows):
            print("  WARNING: private count != public count — investigate before")
            print("           treating the two databases as structurally in sync.")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
