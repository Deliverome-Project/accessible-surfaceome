"""Add the v0.9.0 confidence columns to an existing D1 triage_run table.

The schema in cloudflare/d1_schema.sql now declares
``predicted_confidence`` and ``predicted_key_uncertainty`` on
``triage_run``. Fresh databases get them via ``CREATE TABLE``. Existing
databases need an ``ALTER TABLE ADD COLUMN`` per missing column — SQLite
doesn't support ``ADD COLUMN IF NOT EXISTS``, so we check
``PRAGMA table_info`` first and only add the columns that are missing.

Idempotent: safe to run repeatedly.
"""

from __future__ import annotations

import sys

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env

load_env()

NEW_COLUMNS: list[tuple[str, str]] = [
    ("predicted_confidence", "TEXT"),
    ("predicted_key_uncertainty", "TEXT"),
]


def main() -> int:
    with D1Client() as d1:
        existing = {row["name"] for row in d1.query("PRAGMA table_info(triage_run);")}
        print(f"triage_run currently has {len(existing)} columns")
        for col, typ in NEW_COLUMNS:
            if col in existing:
                print(f"  ✓ {col} already present")
                continue
            print(f"  + adding {col} {typ}")
            d1.query(f"ALTER TABLE triage_run ADD COLUMN {col} {typ};")
        final = {row["name"] for row in d1.query("PRAGMA table_info(triage_run);")}
        print(f"triage_run now has {len(final)} columns")
        added = final - existing
        if added:
            print(f"Added: {sorted(added)}")
        else:
            print("No-op — all columns already existed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
