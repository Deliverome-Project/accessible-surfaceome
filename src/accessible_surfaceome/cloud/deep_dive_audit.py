"""Audit + repair for incomplete ``deep_dive_run`` parent rows.

The Modal sweep streams a parent row plus its evidence/search-log
children into D1 across three HTTP calls. If the parent insert succeeds
but a child insert fails partway through, the next ``insert()`` retry
hits ``ON CONFLICT (run_id, gene_symbol) DO NOTHING`` and returns no
``dd_id`` — the parent already exists, so the helper silently skips
child inserts, leaving the parent permanently orphaned.

This module:

* ``find_orphans(d1, run_id)`` — detects parents whose child-row counts
  are less than the parent's denormalized ``evidence_count`` /
  ``search_log_count``.
* ``backfill_from_record(d1, parent_id, record)`` — destructive-but-safe
  repair: deletes the current (incomplete) children, re-inserts every
  row from the canonical ``SurfaceomeRecord`` on disk. Idempotent.

Use via ``scripts/audit/audit_deep_dive_orphans.py`` — that CLI does the
disk-loading + reporting.
"""

from __future__ import annotations

from dataclasses import dataclass

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.deep_dive_upload import (
    _insert_evidence_rows,
    _insert_search_log_rows,
)
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord


@dataclass(frozen=True)
class OrphanRow:
    """One parent row whose denormalized child counts disagree with the
    actual rows in ``deep_dive_evidence`` / ``deep_dive_search_log``.

    ``actual_*`` < ``expected_*`` means children failed to land. The
    other direction (actual > expected) shouldn't happen — counts are
    written from the same record that drove the inserts — but the
    detection logic ignores it rather than crashing.
    """

    parent_id: int
    run_id: str
    gene_symbol: str
    expected_evidence: int
    actual_evidence: int
    expected_search_log: int
    actual_search_log: int

    @property
    def missing_evidence(self) -> int:
        return max(0, self.expected_evidence - self.actual_evidence)

    @property
    def missing_search_log(self) -> int:
        return max(0, self.expected_search_log - self.actual_search_log)

    @property
    def needs_backfill(self) -> bool:
        return self.missing_evidence > 0 or self.missing_search_log > 0


def find_orphans(d1: D1Client, run_id: str) -> list[OrphanRow]:
    """Return every parent under ``run_id`` whose stored child-row counts
    fall short of the parent's recorded ``evidence_count`` /
    ``search_log_count``.

    Uses correlated subqueries — fine at sweep scale (~5,680 parents);
    re-evaluate if the ``deep_dive_run`` table grows past tens of
    thousands.
    """
    rows = d1.query(
        "SELECT "
        "  r.id AS parent_id, "
        "  r.run_id AS run_id, "
        "  r.gene_symbol AS gene_symbol, "
        "  r.evidence_count AS expected_evidence, "
        "  r.search_log_count AS expected_search_log, "
        "  (SELECT COUNT(*) FROM deep_dive_evidence "
        "     WHERE deep_dive_run_id = r.id) AS actual_evidence, "
        "  (SELECT COUNT(*) FROM deep_dive_search_log "
        "     WHERE deep_dive_run_id = r.id) AS actual_search_log "
        "FROM deep_dive_run r "
        "WHERE r.run_id = ?;",
        [run_id],
    )
    out: list[OrphanRow] = []
    for row in rows:
        orphan = OrphanRow(
            parent_id=int(row["parent_id"]),
            run_id=row["run_id"],
            gene_symbol=row["gene_symbol"],
            expected_evidence=int(row["expected_evidence"]),
            actual_evidence=int(row["actual_evidence"]),
            expected_search_log=int(row["expected_search_log"]),
            actual_search_log=int(row["actual_search_log"]),
        )
        if orphan.needs_backfill:
            out.append(orphan)
    return out


def backfill_from_record(
    d1: D1Client, *, parent_id: int, record: SurfaceomeRecord
) -> None:
    """Replace all child rows for ``parent_id`` with rows derived from
    ``record``.

    The on-disk JSON record at
    ``data/annotations/<run_id>/<symbol>.json`` is the canonical source
    of truth (per PR #41 + #43); this function is destructive-but-safe
    against D1 because the JSON keeps every claim and search-log
    entry. Running twice produces the same final state.

    Order of operations matters: DELETE then INSERT, both via the same
    D1Client. The two DELETEs run sequentially (D1's HTTP API doesn't
    do multi-statement batches), then ``_insert_evidence_rows`` and
    ``_insert_search_log_rows`` from the sink module re-issue the same
    statements the streaming path would have used.
    """
    d1.query(
        "DELETE FROM deep_dive_evidence WHERE deep_dive_run_id = ?;",
        [parent_id],
    )
    d1.query(
        "DELETE FROM deep_dive_search_log WHERE deep_dive_run_id = ?;",
        [parent_id],
    )
    _insert_evidence_rows(d1, parent_id, record)
    _insert_search_log_rows(d1, parent_id, record)


__all__ = ["OrphanRow", "find_orphans", "backfill_from_record"]
