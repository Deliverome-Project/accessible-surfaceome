"""Pure helpers for the ``n_papers_found`` D1-direct backfill.

``n_papers_found`` is the pre-trim discovery corpus size — the honest
"is this gene generally understudied?" signal the low-lit badge and the
catalog's "understudied" chip read via
``n_papers_found < LOW_LIT_PAPERS_MAX`` (=100). It is shed at publish
time, so a NULL value means "corpus size unknown" (distinct from a real
0), and the badge/chip conservatively withhold on unknown.

~485/5130 published ``surface_annotation`` rows carry a NULL
``n_papers_found`` even at schema 2.14.2 — a per-record capture gap
(replay / re-synthesis paths that reused cached drafts without a fresh
discovery pass), not a clean schema-vintage split. These genes live only
in D1 with no committed viewer snapshot, so the snapshot-scoped legacy
path in ``scripts/build/backfill_n_papers_found.py`` cannot reach them;
the ``--from-d1`` mode there uses the helpers below to select the null
rows, patch the recomputed count into a copy of the record, and republish
through ``publish_record`` (which validates + purges the edge cache).

The recompute itself (``discover_n_papers_found``) stays in the script —
it is the network edge; everything testable-offline lives here.
"""
from __future__ import annotations

from typing import Any

# Identifier-only projection for the rows that need a backfill: gene_symbol +
# the record's stable HGNC id (the resolver entry point — never the bare
# symbol; see CLAUDE.md "Gene identifier resolution"). Deliberately does NOT
# select the ~120 KB annotation_json blob — pulling the full blob for the whole
# cohort is the ~145 MB isolate-memory-cap crash of PR #104. The per-gene full
# record is fetched one row at a time only for the genes that need patching.
NEEDS_BACKFILL_SQL = (
    "SELECT gene_symbol, "
    "json_extract(annotation_json, '$.gene.hgnc_id') AS hgnc_id "
    "FROM surface_annotation "
    "WHERE json_extract(annotation_json, '$.filters.n_papers_found') IS NULL "
    "ORDER BY gene_symbol;"
)


def needs_backfill(record: dict[str, Any]) -> bool:
    """True when the record's discovery-corpus count was never persisted.

    ``None`` / a missing key / an absent ``filters`` block all mean
    "unknown corpus" → needs a discover-only recompute. A real integer
    (including ``0`` — a genuinely empty corpus is a valid measurement)
    is left alone.
    """
    filters = record.get("filters")
    if not isinstance(filters, dict):
        return True
    return filters.get("n_papers_found") is None


def patch_n_papers_found(record: dict[str, Any], n_found: int) -> dict[str, Any]:
    """Return a copy of ``record`` with ``filters.n_papers_found`` set.

    Touches only that one field: the ``filters`` block is shallow-copied
    and the scalar replaced, every other key is carried through unchanged,
    and the input is not mutated — so the result still validates against
    ``SurfaceomeRecord`` (asserted in the tests, enforced at call time by
    routing the patched dict through ``publish_record``).
    """
    if not isinstance(n_found, int) or isinstance(n_found, bool):
        raise ValueError(f"n_papers_found must be an int, got {n_found!r}")
    if n_found < 0:
        raise ValueError(f"n_papers_found must be >= 0, got {n_found}")
    patched = dict(record)
    filters = dict(patched.get("filters") or {})
    filters["n_papers_found"] = n_found
    patched["filters"] = filters
    return patched
