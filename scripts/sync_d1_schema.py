"""Backfill ``cloudflare/d1_public_schema.sql`` from live public-D1 DDL.

Why this exists: the schema file is hand-maintained, so it drifts every
time a table or index is applied to D1 without someone remembering to
mirror the DDL. That drift is invisible locally (the check is
network-gated) and it has twice been discovered late — once as a silent
Worker-overlay gap (``schweke_homomer_*``, June 2026), once as a red CI
blocking every open PR (``surface_internalization`` / ``tag_site_public``,
August 2026).

``tests/test_d1_schema_in_sync.py --run-network`` tells you *that* the
file is stale. This script tells you *what* to add, and can append it
for you::

    uv run python scripts/sync_d1_schema.py            # report only
    uv run python scripts/sync_d1_schema.py --write    # append missing DDL

``--write`` only ever APPENDS, into a clearly-marked section at the end
of the file. It never edits or reorders what's already there, so a
hand-written comment or column-alignment in the curated part of the file
survives untouched. Review the diff before committing — an appended
table often also needs wiring into the Worker's ``handleGene``
enrichment, which this script cannot do for you.

Requires ``CLOUDFLARE_ACCOUNT_ID``, ``CLOUDFLARE_API_TOKEN`` and
``CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID`` (``.env`` is loaded automatically).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

SCHEMA_FILE = REPO_ROOT / "cloudflare" / "d1_public_schema.sql"

# Kept in lockstep with tests/test_d1_schema_in_sync.py — Cloudflare-managed
# virtual tables that are present in sqlite_master but are not ours to track.
IGNORED_NAMES = frozenset(
    {"_cf_KV", "sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}
)


def _config() -> D1Config:
    load_env()
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not (acct and token and db):
        raise SystemExit(
            "error: CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN / "
            "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID must be set (see .env)."
        )
    return D1Config(account_id=acct, database_id=db, api_token=token)


def live_ddl() -> list[dict]:
    """Every user-authored table/index in the live public DB, with its DDL.

    ``sqlite_autoindex_*`` entries are dropped: SQLite creates those
    implicitly for PRIMARY KEY / UNIQUE constraints, they carry a NULL
    ``sql``, and they follow mechanically from the table DDL.
    """
    with D1Client(_config()) as d1:
        rows = d1.query(
            """
            SELECT type, name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'index')
            ORDER BY type DESC, name
            """,
            [],
        )
    return [
        r
        for r in rows
        if r["name"] not in IGNORED_NAMES
        and not r["name"].startswith("sqlite_autoindex_")
        and r.get("sql")
    ]


def _declared(text: str, obj: dict) -> bool:
    """Is this object already declared in the schema file?

    Substring match on the CREATE forms the file uses, mirroring the
    test's logic so the two can never disagree about what counts as
    'present'.
    """
    name = obj["name"]
    if obj["type"] == "table":
        forms = (f"CREATE TABLE IF NOT EXISTS {name}", f"CREATE TABLE {name}")
    else:
        forms = (
            f"CREATE INDEX IF NOT EXISTS {name}",
            f"CREATE INDEX {name}",
            f"CREATE UNIQUE INDEX IF NOT EXISTS {name}",
            f"CREATE UNIQUE INDEX {name}",
        )
    return any(f in text for f in forms)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--write",
        action="store_true",
        help="Append the missing DDL to the schema file (default: report only).",
    )
    args = ap.parse_args()

    text = SCHEMA_FILE.read_text()
    missing = [o for o in live_ddl() if not _declared(text, o)]

    if not missing:
        print(f"✓ {SCHEMA_FILE.relative_to(REPO_ROOT)} is in sync with live D1.")
        return 0

    tables = [o for o in missing if o["type"] == "table"]
    indexes = [o for o in missing if o["type"] == "index"]
    print(
        f"{len(missing)} object(s) in live D1 but not in "
        f"{SCHEMA_FILE.relative_to(REPO_ROOT)} "
        f"({len(tables)} table(s), {len(indexes)} index(es)):"
    )
    for o in missing:
        print(f"  {o['type']:<5} {o['name']}")

    if not args.write:
        print("\nRe-run with --write to append these, then review the diff.")
        return 1

    # Append-only, into a dated block: the curated part of the file has
    # hand-written comments and column alignment worth preserving, and a
    # regenerate-in-place would flatten all of it.
    chunks = [
        f"\n\n-- ── Backfilled from live D1 by scripts/sync_d1_schema.py "
        f"on {date.today().isoformat()} ──\n"
        "-- Review before committing. A new table that feeds a "
        "deterministic-features\n"
        "-- field also needs wiring into the Worker's handleGene enrichment.\n"
    ]
    for o in tables + indexes:
        chunks.append(f"\n{o['sql'].rstrip().rstrip(';')};\n")

    with SCHEMA_FILE.open("a") as fh:
        fh.write("".join(chunks))

    print(
        f"\n✓ Appended {len(missing)} object(s) to "
        f"{SCHEMA_FILE.relative_to(REPO_ROOT)}. Review the diff, then verify:\n"
        "    uv run pytest tests/test_d1_schema_in_sync.py --run-network"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
