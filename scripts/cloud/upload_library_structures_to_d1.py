#!/usr/bin/env python
"""Load the library structure index into public D1.

Says, per library member, which structure the viewer should render and which it should
not. The default -- AlphaFold DB's model for the member's canonical accession -- is the
wrong protein for 296 of 2,725 L1 members, so the viewer needs to be told.

Coordinates are not loaded here and must not be: D1 caps a row at 2 MB. Ours live in the
public R2 bucket ``surfaceome-structures`` under ``library-colabfold/`` and this table
carries the key. Same split as ``schweke_homomer_public``.

    uv run python scripts/cloud/upload_library_structures_to_d1.py --dry-run
    uv run python scripts/cloud/upload_library_structures_to_d1.py

The table is additive: nothing reads it until the Worker is taught to, and the Worker
deploy is a separate manual step that ships to production.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAYLOAD = REPO / "data/external/library_structures/library_structure_payload.tsv"
SCHEMA = REPO / "cloudflare/d1_public_schema.sql"
TABLE = "library_structure_public"
API_ROOT = "https://api.cloudflare.com/client/v4"
#: Rows per INSERT. D1 caps bound parameters per query at 100, and each row binds one
#: per column, so 50 rows (800 variables) is rejected with "too many SQL variables".
BATCH = 100 // 16

COLS = [
    "release",
    "candidate_id",
    "uniprot_acc",
    "gene_symbol",
    "species",
    "candidate_set",
    "source",
    "r2_key",
    "model_url",
    "proteoform_match",
    "residue_offset",
    "ordered_length_aa",
    "model_length_aa",
    "is_chosen",
    "mean_plddt",
    "note",
]


def _query(
    account: str, db: str, token: str, sql: str, params: list | None = None
) -> dict:
    body = json.dumps({"sql": sql, "params": params or []}).encode()
    req = urllib.request.Request(
        f"{API_ROOT}/accounts/{account}/d1/database/{db}/query",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"D1 query failed: {exc.code} {exc.read().decode()[:400]}"
        ) from exc


def _create_table_sql() -> str:
    """The CREATE statements for this table, read from the committed schema file.

    Taking them from the schema rather than restating them here is what keeps the file
    and the database from drifting -- the repo's rule is to fix the records and re-sync,
    never to let a loader carry its own private idea of the shape.
    """
    text = SCHEMA.read_text()
    start = text.index(f"CREATE TABLE IF NOT EXISTS {TABLE}")
    tail = text[start:]
    end = tail.rindex("CREATE INDEX IF NOT EXISTS idx_library_structure_public_symbol")
    end = tail.index(";", end) + 1
    block = tail[:end]
    # Strip `--` comments before the caller splits on ";". The column comments contain
    # semicolons of their own ("-- denormalized; never a join key"), and splitting the
    # raw text chopped the CREATE TABLE into four fragments that D1 rejected as
    # "incomplete input".
    return "\n".join(line.split("--")[0].rstrip() for line in block.splitlines())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not (account and token and db):
        raise SystemExit(
            "need CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN and "
            "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID"
        )

    with PAYLOAD.open() as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    releases = {r["release"] for r in rows}
    chosen = sum(1 for r in rows if r["is_chosen"] == "1")
    print(
        f"{len(rows)} rows, {len({r['candidate_id'] for r in rows})} members, "
        f"release(s) {sorted(releases)}"
    )
    print(f"  chosen {chosen}; alternates {len(rows) - chosen}")
    if args.dry_run:
        print("dry run — nothing written")
        return 0

    for stmt in _create_table_sql().split(";"):
        if stmt.strip():
            _query(account, db, token, stmt)
    print(f"  {TABLE} ensured")

    # Replace this release wholesale: a refold is a new set of rows, not an edit of the
    # old ones, and a half-replaced release would mix two answers for one member.
    for release in sorted(releases):
        _query(account, db, token, f"DELETE FROM {TABLE} WHERE release = ?", [release])
    # Multi-row INSERT: one statement per BATCH rows rather than one per row, which is
    # the difference between ~60 round trips and ~2,900.
    one = "(" + ", ".join("?" for _ in COLS) + ")"
    written = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        sql = f"INSERT INTO {TABLE} ({', '.join(COLS)}) VALUES " + ", ".join(
            one for _ in chunk
        )
        params: list = []
        for r in chunk:
            params.extend((r[c] if r[c] != "" else None) for c in COLS)
        _query(account, db, token, sql, params)
        written += len(chunk)
        print(f"  {written}/{len(rows)}", end="\r", flush=True)
    print(f"\nwrote {written} row(s) to {TABLE}")

    got = _query(
        account,
        db,
        token,
        f"SELECT COUNT(*) AS n, SUM(is_chosen) AS chosen FROM {TABLE}",
    )
    print("  in D1 now:", (got.get("result") or [{}])[0].get("results"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
