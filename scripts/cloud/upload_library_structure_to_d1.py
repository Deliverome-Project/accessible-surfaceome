#!/usr/bin/env python
"""Load the library structure index into public D1.

Says, per library member, WHICH structure the viewer should render and which it should
not. The viewer's default -- the AlphaFold DB model for the member's canonical accession
-- is the wrong protein for a few hundred L1 members: some have no AFDB model at all, some
have a model of a different proteoform (measured residue-exact against the designed CDS),
and some have one where the ordered protein is a subsequence and is therefore numbered
wrong without ``residue_offset``. One row per (member, structure); ``is_chosen = 1`` is the
one to render, and the model it replaces travels with ``is_chosen = 0`` and a note so an
alternate stays visible and labelled rather than silently disappearing.

The payload is built offline by ``build_library_structure_payload.py`` in
deliverome-analysis, from that repo's ``candidate_manifest_tranches.tsv`` -- the order of
record -- so only ACTIVE members appear. That filter is the whole point of re-running this
loader: a member retired from the panel keeps its rows in D1 until a fresh payload is
loaded, and the gene page then offers a design that is no longer in the library.

    cp <deliverome-analysis>/analysis/sprint4/s4e9-orf-design-fg-panel/\\
        library_structure_payload.tsv data/external/library_structures/
    uv run python scripts/cloud/upload_library_structure_to_d1.py --dry-run
    uv run python scripts/cloud/upload_library_structure_to_d1.py

The payload is not kept in this repository: it is built in the private design repository
and this one is public.

REPLACE IN PLACE, NOT ADDITIVE. The Worker reads this table with no ``release`` filter, so
every row is live the moment it is written and a half-applied load is visible on the public
gene page. The load is therefore staged in a scratch table and swapped in one request; see
``_d1_library_index.staged_replace``. No Worker deploy is needed or wanted -- the Worker
already reads this table.
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
import collections
import csv
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _d1_library_index import ddl_from_schema, query, rows_of, staged_replace  # noqa: E402

PAYLOAD = REPO / "data/external/library_structures/library_structure_payload.tsv"
SCHEMA = REPO / "cloudflare/d1_public_schema.sql"
TABLE = "library_structure_public"

#: The table's columns, in schema order. ``synced_at`` is excluded on purpose so the
#: table's own default stamps the swap. ``s3_key`` is in the payload but NOT in this table:
#: the public API does not hand out processed-bucket keys.
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--payload", type=Path, default=PAYLOAD)
    args = ap.parse_args(argv)

    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not (account and token and db):
        raise SystemExit(
            "need CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN and "
            "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID"
        )

    with args.payload.open() as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    missing = [c for c in COLS if rows and c not in rows[0]]
    if missing:
        raise SystemExit(f"payload is missing column(s) {missing}")
    releases = sorted({r["release"] for r in rows})
    members = {r["candidate_id"] for r in rows}
    chosen = [r for r in rows if r["is_chosen"] == "1"]
    print(f"{len(rows)} rows, {len(members)} members, release(s) {releases}")
    print(
        f"  chosen    {len(chosen)}  by source {dict(collections.Counter(r['source'] for r in chosen))}"
    )
    print(
        "  alternate "
        f"{len(rows) - len(chosen)}  by match "
        f"{dict(collections.Counter(r['proteoform_match'] for r in rows if r['is_chosen'] != '1'))}"
    )
    # One chosen structure per member, or the page has two answers for one design.
    dupes = [
        c
        for c, n in collections.Counter(r["candidate_id"] for r in chosen).items()
        if n > 1
    ]
    if dupes:
        raise SystemExit(
            f"{len(dupes)} member(s) have more than one chosen structure: {dupes[:10]}"
        )
    no_chosen = sorted(members - {r["candidate_id"] for r in chosen})
    if no_chosen:
        print(
            f"  {len(no_chosen)} member(s) with only alternates (held back): {no_chosen[:10]}"
        )

    before = rows_of(
        query(
            account,
            db,
            token,
            f"SELECT COUNT(*) AS rows_now, COUNT(DISTINCT candidate_id) AS members_now FROM {TABLE}",
        )
    )
    print(f"  in D1 before: {before and before[0]}")
    live = {
        r["candidate_id"]
        for r in rows_of(
            query(account, db, token, f"SELECT DISTINCT candidate_id FROM {TABLE}")
        )
    }
    evicted = sorted(live - members)
    print(f"  members this load evicts: {len(evicted)}  adds: {len(members - live)}")
    if evicted:
        print(f"    e.g. {evicted[:8]}")

    if args.dry_run:
        print("dry run — nothing written")
        return 0

    for stmt in ddl_from_schema(
        SCHEMA.read_text(),
        TABLE,
        "CREATE INDEX IF NOT EXISTS idx_library_structure_public_symbol",
    ).split(";"):
        if stmt.strip():
            query(account, db, token, stmt)
    print(f"  {TABLE} ensured")

    window = staged_replace(
        account, db, token, table=TABLE, cols=COLS, rows=rows, releases=releases
    )
    print(f"  swap completed in {window * 1000:.0f} ms")

    after = rows_of(
        query(
            account,
            db,
            token,
            f"SELECT COUNT(*) AS n, COUNT(DISTINCT candidate_id) AS members, "
            f"COUNT(DISTINCT release) AS releases, "
            f"SUM(CASE WHEN is_chosen = 1 THEN 1 ELSE 0 END) AS chosen FROM {TABLE}",
        )
    )
    print("  in D1 now:", after and after[0])
    if int(after[0]["n"]) != len(rows):
        raise SystemExit(
            f"post-check failed: {after[0]['n']} rows in D1 but the payload has {len(rows)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
