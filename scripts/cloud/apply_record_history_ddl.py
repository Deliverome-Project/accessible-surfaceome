#!/usr/bin/env python3
"""Create the record-history tables in public D1 (dry-run by default).

    uv run python scripts/cloud/apply_record_history_ddl.py            # print
    uv run python scripts/cloud/apply_record_history_ddl.py --execute  # apply

Idempotent (CREATE ... IF NOT EXISTS). D1's HTTP API takes one statement
per call, so each DDL statement is sent separately. Also idempotently
applies ``ALTER TABLE data_release ADD COLUMN archive_scope`` — a fresh
install gets that column from ``DDL``'s ``CREATE TABLE`` directly, but a
pre-existing `data_release` table (this script already having run once
before the column existed) needs the retrofit; running it again here is
the general "keep the live schema caught up" path, same as
``drop_seed_revisions.py``'s own (execute-time-only) call to the same
helper.
"""

from __future__ import annotations

import argparse

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.record_history.store import (
    DDL,
    ensure_archive_scope_column,
)
from accessible_surfaceome.env import load_env


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true", help="apply to public D1")
    args = ap.parse_args()
    if not args.execute:
        for stmt in DDL:
            print(stmt.strip() + ";\n")
        print("[dry-run] plus an idempotent ALTER TABLE data_release ADD "
              "COLUMN archive_scope if it isn't already there.")
        print(f"[dry-run] {len(DDL)} statements; pass --execute to apply.")
        return
    load_env()
    with D1Client.public() as d1:
        for stmt in DDL:
            d1.query(stmt, [])
            print("applied:", stmt.split("(")[0].strip())
        ensure_archive_scope_column(d1)
        print("applied: data_release.archive_scope (idempotent ALTER)")


if __name__ == "__main__":
    main()
