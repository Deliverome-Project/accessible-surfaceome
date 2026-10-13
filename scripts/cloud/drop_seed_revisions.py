#!/usr/bin/env python3
"""One-off: remove the seeded ``seed:zenodo-1.0.0`` rows from public D1
record history and renumber each affected gene's later revisions down by
one (dry-run by default).

    uv run python scripts/cloud/drop_seed_revisions.py                            # dry-run
    uv run python scripts/cloud/drop_seed_revisions.py --backup PATH --execute

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

Renumbering changes what a ``/v1/genes/{sym}/revisions/{n}`` URL fetched in
the last few hours points at, even though that route is served
``immutable`` — a caller who fetched revision 2 an hour ago and refetches
it today gets a DIFFERENT body (what used to be revision 3). This is
accepted deliberately: record history went live only hours before this
migration and nothing has been cited yet (see the PR that introduced this
script). Deploy the Worker for this PR LAST in the rollout (after the
migration has run and verified) — its new edge-cache namespace makes any
already-cached ``immutable`` `/v1/releases/1.0.0` response unreachable, so
readers can't be served a stale (pre-migration) shape from cache.

``--execute`` requires ``--backup PATH``: before any write, every row this
migration is about to touch is dumped to ``PATH`` as JSONL (one ``{"table":
..., "row": {...}}`` per line) — every ``record_revision`` row for a gene
that currently has a seed row (i.e. in the OLD, pre-migration numbering),
every ``data_release_member`` row for 1.0.0, and the ``data_release`` row
for 1.0.0 itself. A failed dump refuses the whole run before anything is
written.

What it does, in collision-free order:

    (a) idempotently ALTER TABLE data_release ADD COLUMN archive_scope
        (see ``record_history.store.ensure_archive_scope_column`` — public
        D1's live table predates the column; this MUST run before any
        query that SELECTs it, including the already-migrated check below)
    (b) DELETE FROM data_release_member WHERE version = '1.0.0'
    (c) DELETE FROM record_revision WHERE source = 'seed:zenodo-1.0.0'
    (d) shift every gapped gene's later revisions down so they're
        contiguous from 1 again (see ``shift_revisions_down``)
    (e) UPDATE data_release SET archive_scope = 'zenodo_only',
        notes = ... WHERE version = '1.0.0'

Resumability, with NO persisted external state. Step (d)'s gene set is
re-derived from CURRENT D1 state on every pass, never reused from an
earlier in-memory snapshot: a gene needs shifting iff its current
``record_revision`` rows are not exactly the contiguous sequence
``1..N`` (``MIN(revision) <> 1 OR COUNT(*) <> MAX(revision) - MIN(revision)
+ 1``, see ``GENES_NEEDING_SHIFT_SQL``). Only a gene mid-migration can ever
have a gap or a non-1 minimum — ``INSERT_REVISION_SQL`` (the only other
writer of this table) always keeps a gene contiguous from 1 — so this
query can never misidentify an ordinary gene as needing work, and a gene
this script already finished shifting drops out of it on its own (no
separate "already done" bookkeeping needed).

Each shift UPDATE is **guarded**: it only moves a row into a currently
EMPTY slot (``AND NOT EXISTS (... WHERE revision = k-1)``). This is what
makes replaying an already-applied ``k`` step safe — without the guard, a
naive ``SET revision = k-1 WHERE revision = k`` replayed after a gene
already finished migrating would try to move its (now legitimate) row at
revision ``k`` on top of its own already-occupied revision ``k-1``, which
the ``(gene_symbol, revision)`` PRIMARY KEY rejects with a UNIQUE
violation — exactly what happened before this guard was added (a resumed
run, or a concurrent publish landing a new revision mid-migration, could
wedge the whole script). ``shift_revisions_down`` also loops the whole
inner ``k=2..max`` pass up to ``MAX_SHIFT_PASSES`` times, re-deriving the
gapped-gene set and ``max`` each time: a concurrent write during a pass
(e.g. a publish inserting revision 5 for a gene this script is mid-way
through shifting) can leave a gap the CURRENT pass's fixed ``max`` never
reaches: the next pass picks it up.

Preflight (read-only, always runs — including under ``--execute``) refuses
before any write if:

  * ``data_release`` has any version other than 1.0.0 — a later release
    (e.g. 1.3.0) would have pinned ``data_release_member`` revision numbers
    against the OLD (seed-inclusive) numbering; renumbering underneath it
    would silently break its citations.

It prints "already migrated" and exits 0, writing nothing, when the state
is EXACTLY the fully-migrated one: no ``seed:zenodo-1.0.0`` rows, no
1.0.0 member rows, no gene has a numbering gap, and 1.0.0's
``archive_scope`` is already ``'zenodo_only'``. A dry-run against a
`data_release` table that doesn't have `archive_scope` YET (production,
before this script's first ``--execute``) reports "column missing — will
be added" instead of crashing on that SELECT.

Throttled: every D1 call goes through ``CloudRevisionStore.d1`` (public
D1, ``CloudRevisionStore``'s own ``RECORD_HISTORY_D1_QPS``-paced wrapper —
this script never touches R2/blobs, only ``.d1``). ``gene_symbol IN (...)``
lists are chunked to ``GENE_CHUNK`` per statement, well under D1's
100-bound-parameter cap (3 fixed params — the old revision, the new
revision, and the guard's old-revision-again — plus the gene list).

After a successful ``--execute``, purges the Worker's cache for
``/v1/releases`` and ``/v1/releases/1.0.0`` (soft-skips with a warning if
Cloudflare config is absent, same posture as every other purge call in
this codebase). Deliberately does NOT purge every affected gene's
``/v1/genes/{SYMBOL}/revisions`` list — that would be ~5,130 unpaced
purge_cache calls, well over the shared account's 1,200-request/5-min
Cloudflare API budget, and that route already has only a 60 s TTL, so it
self-heals without a purge.

The R2 objects the original seed wrote (``records/sha256/{hash}.json`` for
the Zenodo deposit's record bodies) are left alone — the bucket is
write-once and nothing else references those keys now that their
``record_revision`` rows are gone; there is no reason to reclaim them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from accessible_surfaceome.cloud.record_history.store import (
    CloudRevisionStore,
    ensure_archive_scope_column,
    has_archive_scope_column,
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
# and both get the correct next shift applied by shift_revisions_down.
GENES_NEEDING_SHIFT_SQL = """
SELECT gene_symbol, MIN(revision) AS min_rev, MAX(revision) AS max_rev, COUNT(*) AS n
FROM record_revision
GROUP BY gene_symbol
HAVING MIN(revision) <> 1 OR COUNT(*) <> (MAX(revision) - MIN(revision) + 1)
"""

# 3 fixed params (old revision, new revision, guard's old-revision-again) +
# gene symbols; stay well under D1's 100-bound-parameter cap.
GENE_CHUNK = 90

# shift_revisions_down's outer bound: each pass makes monotonic progress
# (every row still gapped after a pass had no empty slot to move into,
# which only happens when ANOTHER row is still ahead of it in the same
# gene — so the NEXT pass, after that row has moved, always succeeds), so
# this is generous headroom over even a heavily-revised gene, not a normal
# operating limit.
MAX_SHIFT_PASSES = 10


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


def member_count_100(d1: Any) -> int:
    rows = d1.query(
        "SELECT COUNT(*) AS n FROM data_release_member WHERE version = ?",
        [RELEASE_VERSION],
    )
    return int(rows[0]["n"])


def release_100_state(d1: Any) -> dict[str, Any] | None:
    """Requires `archive_scope` to already exist — callers must have run
    ``ensure_archive_scope_column`` (or otherwise confirmed
    ``has_archive_scope_column``) first."""
    rows = d1.query(
        "SELECT version, zenodo_version_doi, n_genes, archive_scope "
        "FROM data_release WHERE version = ?",
        [RELEASE_VERSION],
    )
    return rows[0] if rows else None


def already_migrated(d1: Any) -> bool:
    """Requires `archive_scope` to already exist — see `release_100_state`."""
    seed_rows = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE source = ?", [SEED_SOURCE]
    )
    if int(seed_rows[0]["n"]) != 0:
        return False
    if member_count_100(d1) != 0:
        return False
    if genes_needing_shift(d1):
        return False
    rel = release_100_state(d1)
    return rel is not None and rel.get("archive_scope") == ARCHIVE_SCOPE


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _run_shift_pass(d1: Any, needing: dict[str, tuple[int, int, int]]) -> None:
    genes = sorted(needing, key=str.casefold)
    max_k = max(max_rev for _min, max_rev, _n in needing.values())
    for k in range(2, max_k + 1):
        for chunk in _chunks(genes, GENE_CHUNK):
            placeholders = ",".join("?" * len(chunk))
            d1.query(
                "UPDATE record_revision SET revision = ? "
                f"WHERE revision = ? AND gene_symbol IN ({placeholders}) "
                "AND NOT EXISTS (SELECT 1 FROM record_revision r2 "
                " WHERE r2.gene_symbol = record_revision.gene_symbol "
                "   AND r2.revision = ?)",
                [k - 1, k, *chunk, k - 1],
            )


def shift_revisions_down(d1: Any) -> None:
    """Bounded outer loop over ``_run_shift_pass``, re-deriving the gapped
    gene set and ``max`` each pass.

    Each inner UPDATE is guarded (``NOT EXISTS`` on the target slot), so
    replaying an already-completed step is always a safe no-op — this is
    what makes the whole thing resumable after a crash, AND tolerant of a
    concurrent write (e.g. a publish landing a new revision for one of
    these genes) that a single fixed-`max` pass wouldn't reach: the next
    pass's fresh `genes_needing_shift` picks up whatever's still gapped.
    """
    for _pass in range(MAX_SHIFT_PASSES):
        needing = genes_needing_shift(d1)
        if not needing:
            return
        _run_shift_pass(d1, needing)
    remaining = genes_needing_shift(d1)
    if remaining:
        sample = ", ".join(sorted(remaining, key=str.casefold)[:10])
        raise SystemExit(
            f"shift_revisions_down: {len(remaining)} genes still gapped after "
            f"{MAX_SHIFT_PASSES} passes (e.g. {sample}) — investigate before "
            "re-running (a write racing this migration on every single pass "
            "would be unusual; a stuck gap more likely means a genuine bug)"
        )


def write_backup(d1: Any, path: Path) -> int:
    """JSONL dump of every row this migration is about to touch, written
    BEFORE any write (including the archive_scope ALTER). Raises
    (refusing the run) if the file can't be written.

    Rows are read in the OLD (pre-migration) numbering: every
    ``record_revision`` row for a gene that currently has a seed row,
    every ``data_release_member`` row for 1.0.0, and the ``data_release``
    row for 1.0.0 itself (``SELECT *`` there so this works whether or not
    `archive_scope` exists yet).
    """
    entries: list[dict[str, Any]] = []
    seeded = genes_with_seed_rows(d1)
    for chunk in _chunks(seeded, GENE_CHUNK):
        placeholders = ",".join("?" * len(chunk))
        for row in d1.query(
            f"SELECT * FROM record_revision WHERE gene_symbol IN ({placeholders})",
            list(chunk),
        ):
            entries.append({"table": "record_revision", "row": row})
    for row in d1.query(
        "SELECT * FROM data_release_member WHERE version = ?", [RELEASE_VERSION]
    ):
        entries.append({"table": "data_release_member", "row": row})
    for row in d1.query(
        "SELECT * FROM data_release WHERE version = ?", [RELEASE_VERSION]
    ):
        entries.append({"table": "data_release", "row": row})

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, sort_keys=True, default=str) + "\n")
    except OSError as exc:
        raise SystemExit(
            f"backup write to {path} failed ({exc}) — refusing to --execute "
            "without a safety copy of the pre-migration state"
        ) from exc
    return len(entries)


def apply_migration(d1: Any) -> list[str]:
    """Runs (a)-(e); returns the gene symbols this run touched, for the
    printed report — the union of genes with a still-present seed row
    (about to be deleted) and genes already mid-shift from an earlier,
    interrupted run.

    ``ensure_archive_scope_column`` runs FIRST, before anything else in
    this function (or, in `main`, before any other read that SELECTs
    `archive_scope`) — public D1's live `data_release` table predates the
    column, so any such SELECT would 500 until this ALTER has landed.
    """
    ensure_archive_scope_column(d1)

    affected = sorted(
        set(genes_with_seed_rows(d1)) | set(genes_needing_shift(d1)),
        key=str.casefold,
    )

    d1.query("DELETE FROM data_release_member WHERE version = ?", [RELEASE_VERSION])
    d1.query("DELETE FROM record_revision WHERE source = ?", [SEED_SOURCE])
    shift_revisions_down(d1)
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

    if member_count_100(d1) != 0:
        problems.append(f"data_release_member rows remain for {RELEASE_VERSION}")

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


def purge_release_surfaces() -> None:
    """Only the two cohort-level release surfaces — NOT a per-gene
    `/v1/genes/{sym}/revisions` purge (see the module docstring: that
    would be thousands of unpaced Cloudflare API calls for a route that
    already self-heals on a 60 s TTL)."""
    purge_paths(["/v1/releases", f"/v1/releases/{RELEASE_VERSION}"])


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--execute", action="store_true")
    ap.add_argument(
        "--backup",
        type=Path,
        default=None,
        help="JSONL path — required with --execute; dumped before any write",
    )
    args = ap.parse_args()
    if args.execute and args.backup is None:
        raise SystemExit("--execute requires --backup PATH")

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

        col_exists = has_archive_scope_column(d1)
        if col_exists and already_migrated(d1):
            print("already migrated")
            return

        seeded = genes_with_seed_rows(d1)
        gapped = genes_needing_shift(d1)
        counts = revision_counts(d1)
        if not col_exists:
            print("data_release.archive_scope column missing — will be added")
        print(f"genes with a seed:zenodo-1.0.0 row: {len(seeded)}")
        print(f"genes with a numbering gap (mid-migration): {len(gapped)}")
        print(f"revision counts (all genes): {counts}")
        print(f"1.0.0 member rows: {member_count_100(d1)}")

        if not args.execute:
            print("[dry-run] pass --backup PATH --execute to drop the seed and renumber")
            return

        n_backed_up = write_backup(d1, args.backup)
        print(f"backup: {n_backed_up} rows written to {args.backup}")

        affected = apply_migration(d1)
        verify(d1)
        print(f"migrated; {len(affected)} genes touched")

    purge_release_surfaces()
    print("cache purged")


if __name__ == "__main__":
    main()
