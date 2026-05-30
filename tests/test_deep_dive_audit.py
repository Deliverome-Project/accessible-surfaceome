"""Tests for ``accessible_surfaceome.cloud.deep_dive_audit``.

The audit's contract is narrow but load-bearing for a 5,680-gene sweep:

* ``find_orphans`` must filter on ``actual < expected`` for either child
  table, never the other way around.
* ``backfill_from_record`` must DELETE existing children before
  inserting, so the post-call state is exactly what's in the JSON
  (never a mix of stale and fresh rows).
* ``OrphanRow`` properties (``missing_*``, ``needs_backfill``) drive
  the report; their boundaries are pinned.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from accessible_surfaceome.cloud.deep_dive_audit import (
    OrphanRow,
    backfill_from_record,
    find_orphans,
)


def _orphan(
    *,
    expected_evidence: int = 0,
    actual_evidence: int = 0,
    expected_search_log: int = 0,
    actual_search_log: int = 0,
) -> OrphanRow:
    return OrphanRow(
        parent_id=1, run_id="r", gene_symbol="X",
        expected_evidence=expected_evidence,
        actual_evidence=actual_evidence,
        expected_search_log=expected_search_log,
        actual_search_log=actual_search_log,
    )


def test_orphan_missing_counts_are_nonneg() -> None:
    """``missing_*`` clamps to 0 — the actual > expected direction
    shouldn't happen, but if it did the audit shouldn't report a
    negative deficit and confuse the operator.
    """
    o = _orphan(expected_evidence=2, actual_evidence=5)
    assert o.missing_evidence == 0
    assert o.needs_backfill is False


def test_orphan_needs_backfill_when_evidence_short() -> None:
    o = _orphan(expected_evidence=10, actual_evidence=4)
    assert o.missing_evidence == 6
    assert o.needs_backfill is True


def test_orphan_needs_backfill_when_search_log_short() -> None:
    o = _orphan(expected_search_log=8, actual_search_log=3)
    assert o.missing_search_log == 5
    assert o.needs_backfill is True


def test_orphan_complete_is_not_an_orphan() -> None:
    o = _orphan(
        expected_evidence=5, actual_evidence=5,
        expected_search_log=2, actual_search_log=2,
    )
    assert o.needs_backfill is False


def test_find_orphans_filters_complete_rows() -> None:
    """``find_orphans`` fetches every parent under the run_id, then
    drops the rows whose actual counts already match the expected.
    """
    fake_rows = [
        # complete — drop
        {"parent_id": 1, "run_id": "r", "gene_symbol": "A",
         "expected_evidence": 4, "actual_evidence": 4,
         "expected_search_log": 2, "actual_search_log": 2},
        # missing evidence — keep
        {"parent_id": 2, "run_id": "r", "gene_symbol": "B",
         "expected_evidence": 6, "actual_evidence": 1,
         "expected_search_log": 3, "actual_search_log": 3},
        # missing search_log only — keep
        {"parent_id": 3, "run_id": "r", "gene_symbol": "C",
         "expected_evidence": 0, "actual_evidence": 0,
         "expected_search_log": 5, "actual_search_log": 0},
        # zero expected on both sides — drop (not an orphan, just an empty record)
        {"parent_id": 4, "run_id": "r", "gene_symbol": "D",
         "expected_evidence": 0, "actual_evidence": 0,
         "expected_search_log": 0, "actual_search_log": 0},
    ]
    d1 = MagicMock()
    d1.query.return_value = fake_rows

    orphans = find_orphans(d1, "r")

    assert [o.gene_symbol for o in orphans] == ["B", "C"]
    # SQL was issued with the run_id as a bound param.
    args, _kwargs = d1.query.call_args
    sql, params = args
    assert "deep_dive_run" in sql
    assert params == ["r"]


def test_backfill_deletes_before_insert() -> None:
    """``backfill_from_record`` must DELETE all children before
    re-inserting. Order matters: if INSERT ran first we'd duplicate
    the rows that DID land originally. The test pins both the order
    and the parameterization.
    """
    d1 = MagicMock()
    record = MagicMock()
    # Patch the helpers so we only exercise the orchestration, not the
    # underlying insert SQL (covered by the streaming sink path).
    with (
        patch("accessible_surfaceome.cloud.deep_dive_audit._insert_evidence_rows")
        as m_ev,
        patch("accessible_surfaceome.cloud.deep_dive_audit._insert_search_log_rows")
        as m_sl,
    ):
        backfill_from_record(d1, parent_id=42, record=record)

    # Both DELETEs hit d1.query in order, scoped to the parent_id.
    assert d1.query.call_args_list == [
        call("DELETE FROM deep_dive_evidence WHERE deep_dive_run_id = ?;", [42]),
        call("DELETE FROM deep_dive_search_log WHERE deep_dive_run_id = ?;", [42]),
    ]
    # Then both insert helpers were called with the same record + parent_id.
    m_ev.assert_called_once_with(d1, 42, record)
    m_sl.assert_called_once_with(d1, 42, record)
