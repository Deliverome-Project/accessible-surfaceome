#!/usr/bin/env python
"""Load the library topology pointer index into public D1.

Says, per library member, WHICH ``topology_public`` row describes the protein that member
actually encodes. The Worker cannot work this out: its topology lookups are keyed by
``uniprot_acc`` within ``human_canonical`` / ``human_isoforms``, and a member's protein is
its designed CDS translated -- an Ensembl-transcript product that for a substantial
minority corresponds to a UniProt *isoform* record instead (816 of 5,896 resolved members,
and 119 of the 121 whose AlphaFold model turned out to be the wrong protein). Resolving by
accession hands those a different protein's topology, with a plausible length and a
plausible helix count.

Matching by sequence is correct but needs a full scan of ~71k long TEXT rows
(``topology_public.sequence`` is unindexed), so it is resolved offline -- by
``build_library_topology_index.py`` in deliverome-analysis -- and stored here as an
explicit pointer the Worker joins on.

Only members whose EXACT designed sequence has a v1 topology appear. A member with no row
needs a DeepTMHMM run and must not be shown the canonical instead.

    uv run python scripts/cloud/upload_library_topology_to_d1.py --dry-run
    uv run python scripts/cloud/upload_library_topology_to_d1.py

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
PAYLOAD = REPO / "data/external/library_structures/library_topology_index.tsv"
SCHEMA = REPO / "cloudflare/d1_public_schema.sql"
TABLE = "library_topology_public"
API_ROOT = "https://api.cloudflare.com/client/v4"
#: Rows per INSERT. D1 caps bound parameters per query at 100, and each row binds one
#: per column, so 50 rows (800 variables) is rejected with "too many SQL variables".
BATCH = 100 // 12

COLS = [
    "release",
    "candidate_id",
    "library",
    "candidate_set",
    "species",
    "gene_symbol",
    "topology_tool",
    "topology_cohort",
    "topology_version",
    "topology_acc",
    "ordered_length_aa",
    "sequence_sha256",
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
    end = tail.rindex("CREATE INDEX IF NOT EXISTS idx_library_topology_public_target")
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
    print(
        f"{len(rows)} rows, {len({r['candidate_id'] for r in rows})} members, "
        f"release(s) {sorted(releases)}"
    )
    by_cohort: dict[str, int] = {}
    by_library: dict[str, int] = {}
    for r in rows:
        by_cohort[r["topology_cohort"]] = by_cohort.get(r["topology_cohort"], 0) + 1
        by_library[r["library"]] = by_library.get(r["library"], 0) + 1
    print(f"  by library: {dict(sorted(by_library.items()))}")
    print(
        f"  by source cohort: {dict(sorted(by_cohort.items(), key=lambda kv: -kv[1]))}"
    )
    tools = {r["topology_tool"] for r in rows}
    if tools != {"deeptmhmm_v1"}:
        raise SystemExit(
            f"expected deeptmhmm_v1 only (it is the topology of record); got {sorted(tools)}"
        )
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

    # Post-check the invariant that actually matters here: every stored pointer aims at
    # a v1 run. A dtm2 version among these would mean the resolver regressed to selecting
    # on "has a per_residue_topology" -- which a dtm2 row also has, as the lossy back
    # projection -- and the index would claim v1 while meaning v2.
    got = _query(
        account,
        db,
        token,
        f"SELECT COUNT(*) AS n, COUNT(DISTINCT topology_version) AS versions, "
        f"SUM(CASE WHEN topology_version LIKE '%dtm2%' THEN 1 ELSE 0 END) AS dtm2_pointers, "
        f"SUM(CASE WHEN topology_version LIKE '%test%' THEN 1 ELSE 0 END) AS test_pointers "
        f"FROM {TABLE}",
    )
    stats = ((got.get("result") or [{}])[0].get("results") or [{}])[0]
    print("  in D1 now:", stats)
    if stats.get("dtm2_pointers") or stats.get("test_pointers"):
        raise SystemExit(
            f"refusing to leave the index in this state: "
            f"{stats.get('dtm2_pointers')} pointers aim at a dtm2 version and "
            f"{stats.get('test_pointers')} at a provisional one; v1 is the topology of record"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
