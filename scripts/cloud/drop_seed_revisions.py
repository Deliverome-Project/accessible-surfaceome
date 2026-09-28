#!/usr/bin/env python3
"""One-off: remove the seeded ``seed:zenodo-1.0.0`` rows from public D1
record history and renumber each affected gene's later revisions down by
one (dry-run by default).

    uv run python scripts/cloud/drop_seed_revisions.py             # dry-run
    uv run python scripts/cloud/drop_seed_revisions.py --execute

Background: record history briefly seeded every gene's revision 1 from the
2026-08-15 Zenodo deposit (``source='seed:zenodo-1.0.0'``), with release
1.0.0 pinning that snapshot. That design was reverted — API record history
now holds only states the API actually SERVED, and the Zenodo deposit was
never itself served through the Worker. Release 1.0.0 stays as a
Zenodo-only ``data_release`` row (``archive_scope='zenodo_only'``, no
``data_release_member`` rows) rather than a row-1 pointer into
``record_revision``. This script undoes what
``scripts/cloud/seed_record_history.py`` wrote (that script now refuses to
run at all — see its docstring).

What it does, in collision-free order:

    (a) DELETE FROM data_release_member WHERE version = '1.0.0'
    (b) DELETE FROM record_revision WHERE source = 'seed:zenodo-1.0.0'
    (c) for k = 2..max: UPDATE record_revision SET revision = k-1
        WHERE revision = k AND gene_symbol IN (<genes still needing it>)
    (d) idempotently ALTER TABLE data_release ADD COLUMN archive_scope,
        then UPDATE data_release SET archive_scope = 'zenodo_only',
        notes = ... WHERE version = '1.0.0'

Resumability, with NO persisted external state. Step (c)'s gene set is
re-derived from CURRENT D1 state on every run, never reused from an
earlier in-memory snapshot: a gene needs shifting iff its current
``record_revision`` rows are not exactly the contiguous sequence
``1..N`` (``MIN(revision) <> 1 OR COUNT(*) <> MAX(revision) - MIN(revision)
+ 1``, see ``GENES_NEEDING_SHIFT_SQL``). Only a gene mid-migration can ever
have a gap or a non-1 minimum — ``INSERT_REVISION_SQL`` (the only other
writer of this table) always keeps a gene contiguous from 1 — so this
query can never misidentify an ordinary gene as needing work, and a gene
this script already finished shifting drops out of it on its own (no
separate "already done" bookkeeping needed). That is also what makes
REPLAYING the whole k-loop from k=2 safe after any interruption: for a
gene whose earlier k's already landed, ``WHERE revision = k`` simply
matches nothing for those already-vacated slots, so re-running is a no-op
for the part that's done and picks up exactly where a crash left off for
the part that isn't. Steps (a)/(b)/(d) are plain idempotent
DELETE/UPDATE-if-needed statements.

Preflight (read-only, always runs — including under ``--execute``) refuses
before any write if:

  * ``data_release`` has any version other than 1.0.0 — a later release
    (e.g. 1.3.0) would have pinned ``data_release_member`` revision numbers
    against the OLD (seed-inclusive) numbering; renumbering underneath it
    would silently break its citations.

It prints "already migrated" and exits 0, writing nothing, when the state
is EXACTLY the fully-migrated one: no ``seed:zenodo-1.0.0`` rows, no
1.0.0 member rows, no gene has a numbering gap, and 1.0.0's
``archive_scope`` is already ``'zenodo_only'``.

Throttled: every D1 call goes through ``CloudRevisionStore.d1`` (public
D1, ``CloudRevisionStore``'s own ``RECORD_HISTORY_D1_QPS``-paced wrapper —
this script never touches R2/blobs, only ``.d1``). ``gene_symbol IN (...)``
lists are chunked to ``GENE_CHUNK`` per statement, well under D1's
100-bound-parameter cap (2 fixed params — the old and new revision — plus
the gene list).

After a successful ``--execute``, purges the Worker's cache for
``/v1/releases``, ``/v1/releases/1.0.0``, and every affected gene's
``/v1/genes/{SYMBOL}/revisions`` list (soft-skips with a warning if
Cloudflare config is absent, same posture as every other purge call in
this codebase).

The R2 objects the original seed wrote (``records/sha256/{hash}.json`` for
the Zenodo deposit's record bodies) are left alone — the bucket is
write-once and nothing else references those keys now that their
``record_revision`` rows are gone; there is no reason to reclaim them.
"""

from __future__ import annotations

import argparse
from typing import Any

from accessible_surfaceome.cloud.record_history.store import (
    ALTER_DATA_RELEASE_ADD_ARCHIVE_SCOPE_SQL,
    CloudRevisionStore,
)
from accessible_surfaceome.cloud.surface_annotation import purge_paths
from accessible_surfaceome.env import load_env

SEED_SOURCE = "seed:zenodo-1.0.0"
RELEASE_VERSION = "1.0.0"
ARCHIVE_SCOPE = "zenodo_only"
ARCHIVE_NOTE = (
    "Initial data deposit (Zenodo record 20805384); records as deposited, "
    "evidence inline, no Markdown. This release predates the API's "
    "per-gene record history and is archived only in the Zenodo deposit — "
    "it has no data_release_member rows and is not individually served "
    "through the /v1/genes/{symbol}/revisions or /v1/releases/1.0.0/genes "
    "routes."
)

# A gene needs shifting iff its CURRENT record_revision rows are not
# exactly the contiguous sequence 1..N. INSERT_REVISION_SQL (the only
# other writer of this table) always keeps a gene contiguous from 1, so
# only a gene mid-migration can ever match this — no external state
# needed to tell "not started" from "partially shifted" apart from
# "done"; both look the same here (still gapped / still not-starting-at-1)
# and both get the correct next shift applied by the k-loop below.
GENES_NEEDING_SHIFT_SQL = """
SELECT gene_symbol, MIN(revision) AS min_rev, MAX(revision) AS max_rev, COUNT(*) AS n
FROM record_revision
GROUP BY gene_symbol
HAVING MIN(revision) <> 1 OR COUNT(*) <> (MAX(revision) - MIN(revision) + 1)
"""

# 2 fixed params (old revision, new revision) + gene symbols; stay well
# under D1's 100-bound-parameter cap.
GENE_CHUNK = 90

PURGE_CHUNK = 30


def genes_with_seed_rows(d1: Any) -> list[str]:
    rows = d1.query(
        "SELECT DISTINCT gene_symbol FROM record_revision WHERE source = ?",
        [SEED_SOURCE],
    )
    return sorted({r["gene_symbol"] for r in rows}, key=str.casefold)


def genes_needing_shift(d1: Any) -> dict[str, tuple[int, int, int]]:
    """``{gene_symbol: (min_rev, max_rev, n)}`` for every gene whose current
    revisions aren't a contiguous 1..N sequence."""
    rows = d1.query(GENES_NEEDING_SHIFT_SQL, [])
    return {
        r["gene_symbol"]: (int(r["min_rev"]), int(r["max_rev"]), int(r["n"]))
        for r in rows
    }


def revision_counts(d1: Any) -> dict[int, int]:
    rows = d1.query(
        "SELECT revision, COUNT(*) AS n FROM record_revision GROUP BY revision "
        "ORDER BY revision",
        [],
    )
    return {int(r["revision"]): int(r["n"]) for r in rows}


def other_release_versions(d1: Any) -> list[str]:
    rows = d1.query(
        "SELECT version FROM data_release WHERE version <> ? ORDER BY version",
        [RELEASE_VERSION],
    )
    return [r["version"] for r in rows]


def release_100_state(d1: Any) -> dict[str, Any] | None:
    rows = d1.query(
        "SELECT version, zenodo_version_doi, n_genes, archive_scope "
        "FROM data_release WHERE version = ?",
        [RELEASE_VERSION],
    )
    return rows[0] if rows else None


def already_migrated(d1: Any) -> bool:
    seed_rows = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE source = ?", [SEED_SOURCE]
    )
    if int(seed_rows[0]["n"]) != 0:
        return False
    member_rows = d1.query(
        "SELECT COUNT(*) AS n FROM data_release_member WHERE version = ?",
        [RELEASE_VERSION],
    )
    if int(member_rows[0]["n"]) != 0:
        return False
    if genes_needing_shift(d1):
        return False
    rel = release_100_state(d1)
    return rel is not None and rel.get("archive_scope") == ARCHIVE_SCOPE


def ensure_archive_scope_column(d1: Any) -> None:
    """Idempotent ``ALTER TABLE data_release ADD COLUMN archive_scope``.

    ``record_history/store.py``'s ``DDL`` now declares this column on a
    FRESH table, but public D1's `data_release` predates it — ``CREATE
    TABLE IF NOT EXISTS`` never retrofits a column onto an existing table,
    and SQLite/D1 has no ``ADD COLUMN IF NOT EXISTS`` — so this runs the
    ALTER and treats a "duplicate column name" failure (already applied,
    by an earlier run or by a fresh DDL apply) as success.
    """
    try:
        d1.query(ALTER_DATA_RELEASE_ADD_ARCHIVE_SCOPE_SQL, [])
    except Exception as exc:  # noqa: BLE001 - only "already applied" is swallowed
        if "duplicate column" not in str(exc).lower():
            raise


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def shift_revisions_down(d1: Any) -> int:
    """Run the k-loop; returns the number of UPDATE statements issued."""
    needing = genes_needing_shift(d1)
    if not needing:
        return 0
    genes = sorted(needing, key=str.casefold)
    max_k = max(max_rev for _min, max_rev, _n in needing.values())
    n_statements = 0
    for k in range(2, max_k + 1):
        for chunk in _chunks(genes, GENE_CHUNK):
            placeholders = ",".join("?" * len(chunk))
            d1.query(
                "UPDATE record_revision SET revision = ? "
                f"WHERE revision = ? AND gene_symbol IN ({placeholders})",
                [k - 1, k, *chunk],
            )
            n_statements += 1
    return n_statements


def apply_migration(d1: Any) -> list[str]:
    """Runs (a)-(d); returns the gene symbols this run touched (for the
    caller to purge) — the union of genes with a still-present seed row
    (about to be deleted) and genes already mid-shift from an earlier,
    interrupted run."""
    affected = sorted(
        set(genes_with_seed_rows(d1)) | set(genes_needing_shift(d1)),
        key=str.casefold,
    )

    d1.query("DELETE FROM data_release_member WHERE version = ?", [RELEASE_VERSION])
    d1.query("DELETE FROM record_revision WHERE source = ?", [SEED_SOURCE])
    shift_revisions_down(d1)
    ensure_archive_scope_column(d1)
    d1.query(
        "UPDATE data_release SET archive_scope = ?, notes = ? "
        "WHERE version = ? AND (archive_scope IS NULL OR archive_scope <> ?)",
        [ARCHIVE_SCOPE, ARCHIVE_NOTE, RELEASE_VERSION, ARCHIVE_SCOPE],
    )
    return affected


def verify(d1: Any) -> None:
    problems: list[str] = []
    seed_rows = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE source = ?", [SEED_SOURCE]
    )
    if int(seed_rows[0]["n"]) != 0:
        problems.append(f"{seed_rows[0]['n']} seed:zenodo-1.0.0 rows remain")

    gapped = genes_needing_shift(d1)
    if gapped:
        sample = ", ".join(sorted(gapped, key=str.casefold)[:10])
        problems.append(f"{len(gapped)} genes still have a numbering gap: {sample}")

    member_rows = d1.query(
        "SELECT COUNT(*) AS n FROM data_release_member WHERE version = ?",
        [RELEASE_VERSION],
    )
    if int(member_rows[0]["n"]) != 0:
        problems.append(
            f"{member_rows[0]['n']} data_release_member rows remain for {RELEASE_VERSION}"
        )

    rel = release_100_state(d1)
    if rel is None:
        problems.append(f"data_release row for {RELEASE_VERSION} is missing")
    else:
        if rel.get("archive_scope") != ARCHIVE_SCOPE:
            problems.append(
                f"{RELEASE_VERSION}.archive_scope = {rel.get('archive_scope')!r}, "
                f"expected {ARCHIVE_SCOPE!r}"
            )
        if not rel.get("zenodo_version_doi"):
            problems.append(f"{RELEASE_VERSION}.zenodo_version_doi is missing")

    if problems:
        raise SystemExit("verification failed: " + "; ".join(problems))


def purge_affected(genes: list[str]) -> None:
    paths = ["/v1/releases", f"/v1/releases/{RELEASE_VERSION}"]
    paths += [f"/v1/genes/{sym}/revisions" for sym in genes]
    for chunk in _chunks(paths, PURGE_CHUNK):
        purge_paths(chunk)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    load_env()
    with CloudRevisionStore.from_env() as store:
        d1 = store.d1

        others = other_release_versions(d1)
        if others:
            raise SystemExit(
                "data_release has version(s) other than 1.0.0: "
                f"{', '.join(others)} — a later release would have pinned "
                "data_release_member revision numbers against the old "
                "(seed-inclusive) numbering; refusing to renumber underneath it"
            )

        if already_migrated(d1):
            print("already migrated")
            return

        seeded = genes_with_seed_rows(d1)
        gapped = genes_needing_shift(d1)
        counts = revision_counts(d1)
        print(f"genes with a seed:zenodo-1.0.0 row: {len(seeded)}")
        print(f"genes with a numbering gap (mid-migration): {len(gapped)}")
        print(f"revision counts (all genes): {counts}")
        members = d1.query(
            "SELECT COUNT(*) AS n FROM data_release_member WHERE version = ?",
            [RELEASE_VERSION],
        )
        print(f"1.0.0 member rows: {members[0]['n']}")

        if not args.execute:
            print("[dry-run] pass --execute to drop the seed and renumber")
            return

        affected = apply_migration(d1)
        verify(d1)
        print(f"migrated; {len(affected)} genes touched")

    purge_affected(affected)
    print("cache purged")


if __name__ == "__main__":
    main()
