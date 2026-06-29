"""Resume + quarantine read-side helpers in ``cloud.intermediates``.

Covers the gating that decides whether a prior attempt's plan-trim-select dual
is safe to reuse (``resumable_pts_blob``) and which genes are over-cap and must
be quarantined from auto-resume (``fetch_quarantined_genes`` /
``fetch_latest_intermediates_row``). The D1 queries run against in-memory
``sqlite3`` (D1 is SQLite — same dialect).
"""

from __future__ import annotations

import sqlite3
from typing import Any, cast

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.intermediates import (
    fetch_latest_intermediates_row,
    fetch_quarantined_genes,
    resumable_pts_blob,
)
from accessible_surfaceome.tools._shared.failure_modes import (
    QUARANTINE_FAILURE_MODES,
    RESUMABLE_FAILURE_MODES,
)

SCHEMA = "v0.4.0"
CORPUS = "2.50.2"


def _row(
    *,
    failure_mode: str,
    record_valid: int = 0,
    schema_version: str = SCHEMA,
    prompt_corpus_version: str = CORPUS,
    has_pts: bool = True,
) -> dict[str, Any]:
    return {
        "record_valid": record_valid,
        "failure_mode": failure_mode,
        "schema_version": schema_version,
        "prompt_corpus_version": prompt_corpus_version,
        "intermediates_json": (
            '{"plan_trim_select": {"gene": "G"}}' if has_pts else "{}"
        ),
    }


# --------------------------------------------------------------------------
# resumable_pts_blob — the safety gate
# --------------------------------------------------------------------------


def test_resumable_none_row() -> None:
    assert resumable_pts_blob(None, current_schema_version=SCHEMA) is None


def test_resumable_happy_path() -> None:
    blob = resumable_pts_blob(
        _row(failure_mode="validation_failed"), current_schema_version=SCHEMA
    )
    assert blob is not None and "plan_trim_select" in blob


def test_resumable_pts_checkpoint_mode_is_resumable() -> None:
    assert (
        resumable_pts_blob(
            _row(failure_mode="pts_checkpoint"), current_schema_version=SCHEMA
        )
        is not None
    )


def test_not_resumable_when_record_valid() -> None:
    assert (
        resumable_pts_blob(
            _row(failure_mode="ok", record_valid=1), current_schema_version=SCHEMA
        )
        is None
    )


def test_over_cap_modes_never_resumable() -> None:
    # The core safety property: an over-cap gene is NEVER auto-resumed.
    for mode in ("cost_ceiling_pts", "cost_ceiling_total"):
        assert (
            resumable_pts_blob(_row(failure_mode=mode), current_schema_version=SCHEMA)
            is None
        ), mode


def test_not_resumable_on_schema_drift() -> None:
    assert (
        resumable_pts_blob(
            _row(failure_mode="validation_failed", schema_version="v0.3.0"),
            current_schema_version=SCHEMA,
        )
        is None
    )


def test_not_resumable_on_prompt_corpus_drift() -> None:
    assert (
        resumable_pts_blob(
            _row(failure_mode="validation_failed", prompt_corpus_version="9.9.9"),
            current_schema_version=SCHEMA,
            current_prompt_corpus_version=CORPUS,
        )
        is None
    )


def test_not_resumable_without_pts_payload() -> None:
    assert (
        resumable_pts_blob(
            _row(failure_mode="validation_failed", has_pts=False),
            current_schema_version=SCHEMA,
        )
        is None
    )


def test_not_resumable_on_model_mismatch() -> None:
    # blob carries model_id "claude-sonnet-4-6"; a different current model
    # must refuse the stale dual (P1-B).
    row = _row(failure_mode="validation_failed")
    row["intermediates_json"] = (
        '{"plan_trim_select": {"gene": "G"}, "model_id": "claude-sonnet-4-6"}'
    )
    assert (
        resumable_pts_blob(
            row, current_schema_version=SCHEMA, current_model_id="claude-opus-4-8"
        )
        is None
    )
    # Matching model → resumable.
    assert (
        resumable_pts_blob(
            row, current_schema_version=SCHEMA, current_model_id="claude-sonnet-4-6"
        )
        is not None
    )


def test_not_resumable_when_cost_exceeds_ceiling() -> None:
    # Defense-in-depth (P1-A): an over-cap dual that somehow reached a resumable
    # row is refused when its persisted cost exceeds the cap.
    row = _row(failure_mode="pts_checkpoint")
    row["intermediates_json"] = (
        '{"plan_trim_select": {"gene": "G"}, "cost_total_usd": 9.99}'
    )
    assert (
        resumable_pts_blob(
            row, current_schema_version=SCHEMA, max_resumable_cost_usd=5.0
        )
        is None
    )
    # Under the ceiling → resumable.
    row["intermediates_json"] = (
        '{"plan_trim_select": {"gene": "G"}, "cost_total_usd": 1.20}'
    )
    assert (
        resumable_pts_blob(
            row, current_schema_version=SCHEMA, max_resumable_cost_usd=5.0
        )
        is not None
    )


def test_failure_mode_sets_are_disjoint() -> None:
    assert QUARANTINE_FAILURE_MODES.isdisjoint(RESUMABLE_FAILURE_MODES)


# --------------------------------------------------------------------------
# D1 queries against in-memory SQLite
# --------------------------------------------------------------------------


class _SqliteD1:
    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            "CREATE TABLE agent_run_intermediates ("
            " gene_symbol TEXT, schema_version TEXT, prompt_corpus_version TEXT,"
            " created_at TEXT, record_valid INTEGER, failure_mode TEXT,"
            " cohort_run_id TEXT, intermediates_json TEXT);"
        )

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        cur = self._conn.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]

    def add(
        self,
        gene: str,
        *,
        created_at: str,
        failure_mode: str,
        record_valid: int = 0,
        cohort: str = "run1",
        pts: bool = True,
    ) -> None:
        self._conn.execute(
            "INSERT INTO agent_run_intermediates VALUES (?,?,?,?,?,?,?,?);",
            [
                gene, SCHEMA, CORPUS, created_at, record_valid, failure_mode, cohort,
                '{"plan_trim_select": {"gene": "G"}}' if pts else "{}",
            ],
        )
        self._conn.commit()


def _d1(fake: _SqliteD1) -> D1Client:
    return cast(D1Client, fake)


def test_fetch_quarantined_only_latest_row_counts() -> None:
    fake = _SqliteD1()
    # A: latest row is over-cap → quarantined.
    fake.add("A", created_at="2026-06-01T00:00:00", failure_mode="cost_ceiling_total")
    # B: over-cap then a later successful completion → NOT quarantined.
    fake.add("B", created_at="2026-06-01T00:00:00", failure_mode="cost_ceiling_pts")
    fake.add("B", created_at="2026-06-02T00:00:00", failure_mode="ok", record_valid=1)
    # C: graceful failure (resumable, not over-cap) → NOT quarantined.
    fake.add("C", created_at="2026-06-01T00:00:00", failure_mode="validation_failed")
    assert fetch_quarantined_genes(_d1(fake), cohort_run_id="run1") == {"A"}


def test_fetch_quarantined_scoped_by_cohort() -> None:
    fake = _SqliteD1()
    fake.add("A", created_at="2026-06-01T00:00:00", failure_mode="cost_ceiling_total",
             cohort="other_run")
    # Scoped to run1 → A's other-cohort over-cap row is invisible.
    assert fetch_quarantined_genes(_d1(fake), cohort_run_id="run1") == set()
    # Unscoped → picks it up.
    assert fetch_quarantined_genes(_d1(fake)) == {"A"}


def test_fetch_latest_intermediates_row_returns_newest() -> None:
    fake = _SqliteD1()
    fake.add("A", created_at="2026-06-01T00:00:00", failure_mode="validation_failed")
    fake.add("A", created_at="2026-06-03T00:00:00", failure_mode="pts_checkpoint")
    row = fetch_latest_intermediates_row(_d1(fake), "A")
    assert row is not None and row["failure_mode"] == "pts_checkpoint"
    assert fetch_latest_intermediates_row(_d1(fake), "NONE") is None
