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

REPLACE IN PLACE. The Worker now reads this table and its join carries no ``release``
filter, so every row is live the moment it is written and a half-applied load is visible on
the public gene page. The load is therefore staged in a scratch table and swapped in one
request; see ``_d1_library_index.staged_replace``. No Worker deploy is needed or wanted --
the Worker already reads this table.

Re-running it is how a member retired from the panel loses its row: the payload is built
from deliverome-analysis's ``candidate_manifest_tranches.tsv``, the order of record, and
carries active members only.
AFTER LOADING, PURGE THE RECORD CACHE. The gene record is served through two cache tiers
(``caches.default`` and the ``RECORD_CACHE`` KV mirror), and a KV hit is answered before
the handler ever reads D1 -- so a correct D1 table is invisible until the cached records
are evicted. Both tiers, for the genes whose rows changed, not just the one you
spot-checked::

    uv run python scripts/cloud/purge_gene_cache.py --surfaces record \\
        --genes <affected symbols> --execute

``CLOUDFLARE_KV_RECORD_CACHE_ID`` must be set or the KV tier soft-skips and the mirror
keeps serving the old record for up to a day. Verify with the archive bypass
(``X-Archive-Bypass: $ARCHIVE_BYPASS_TOKEN``) to read past both tiers, and then again
without it to confirm the public answer actually changed.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _d1_library_index import ddl_from_schema, query, rows_of, staged_replace  # noqa: E402

PAYLOAD = REPO / "data/external/library_structures/library_topology_index.tsv"
SCHEMA = REPO / "cloudflare/d1_public_schema.sql"
TABLE = "library_topology_public"

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
    # What this load takes away, named before it happens: these rows are live to the
    # public page, and a member evicted here is one the panel no longer orders.
    members = {r["candidate_id"] for r in rows}
    live = {
        r["candidate_id"]
        for r in rows_of(
            query(account, db, token, f"SELECT DISTINCT candidate_id FROM {TABLE}")
        )
    }
    evicted = sorted(live - members)
    print(
        f"  in D1 now: {len(live)} members; this load evicts {len(evicted)}, adds {len(members - live)}"
    )
    if evicted:
        print(f"    e.g. {evicted[:8]}")

    if args.dry_run:
        print("dry run — nothing written")
        return 0

    for stmt in ddl_from_schema(
        SCHEMA.read_text(),
        TABLE,
        "CREATE INDEX IF NOT EXISTS idx_library_topology_public_target",
    ).split(";"):
        if stmt.strip():
            query(account, db, token, stmt)
    print(f"  {TABLE} ensured")

    # Replace these releases wholesale: a new resolve is a new set of pointers, not an
    # edit of the old ones, and a half-replaced release would mix two answers for one
    # member. Staged and swapped in one request so the public page never sees the gap.
    window = staged_replace(
        account, db, token, table=TABLE, cols=COLS, rows=rows, releases=sorted(releases)
    )
    print(f"  swap completed in {window * 1000:.0f} ms")

    # Post-check the invariant that actually matters here: every stored pointer aims at
    # a v1 run. A dtm2 version among these would mean the resolver regressed to selecting
    # on "has a per_residue_topology" -- which a dtm2 row also has, as the lossy back
    # projection -- and the index would claim v1 while meaning v2.
    stats_rows = rows_of(
        query(
            account,
            db,
            token,
            f"SELECT COUNT(*) AS n, COUNT(DISTINCT topology_version) AS versions, "
            f"SUM(CASE WHEN topology_version LIKE '%dtm2%' THEN 1 ELSE 0 END) AS dtm2_pointers, "
            f"SUM(CASE WHEN topology_version LIKE '%test%' THEN 1 ELSE 0 END) AS test_pointers "
            f"FROM {TABLE}",
        )
    )
    stats = (stats_rows or [{}])[0]
    print("  in D1 now:", stats)
    if int(stats.get("n") or 0) != len(rows):
        raise SystemExit(
            f"post-check failed: {stats.get('n')} rows in D1 but the payload has {len(rows)}"
        )
    if stats.get("dtm2_pointers") or stats.get("test_pointers"):
        raise SystemExit(
            f"refusing to leave the index in this state: "
            f"{stats.get('dtm2_pointers')} pointers aim at a dtm2 version and "
            f"{stats.get('test_pointers')} at a provisional one; v1 is the topology of record"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
