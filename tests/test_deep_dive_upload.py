"""Idempotency of the deep-dive child-row inserts under retry.

``D1Client.query`` retries transient failures, so every write is
at-least-once: an ambiguous commit (D1 applied the row but the response was
lost) re-runs the identical statement. The evidence / search-log child inserts
must therefore be idempotent on their natural keys — otherwise a retry
duplicates a child row, which ``audit_deep_dive_orphans`` cannot see (it only
flags *missing* children, actual < expected).

These tests run the real ``INSERT ... WHERE NOT EXISTS`` statements against an
in-memory ``sqlite3`` (D1 is SQLite, same dialect) and call each inserter twice
to simulate the retry. The guard must keep the row count at N, not 2N.
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.deep_dive_upload import (
    _insert_evidence_rows,
    _insert_search_log_rows,
)
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord


def _ins_evidence(d1: "_SqliteD1", parent_id: int, record: SimpleNamespace) -> None:
    """Call the real inserter with the structural fakes, satisfying the type
    checker (the fakes are duck-compatible at runtime)."""
    _insert_evidence_rows(cast(D1Client, d1), parent_id, cast(SurfaceomeRecord, record))


def _ins_search_log(d1: "_SqliteD1", parent_id: int, record: SimpleNamespace) -> None:
    _insert_search_log_rows(cast(D1Client, d1), parent_id, cast(SurfaceomeRecord, record))


class _SqliteD1:
    """Minimal ``D1Client``-shaped shim backed by in-memory SQLite.

    Only ``query(sql, params)`` is exercised by the inserters; ``?`` binding
    and the SQL dialect match D1, so the statements run unmodified.
    """

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        cur = self._conn.execute(sql, params or [])
        rows = [dict(r) for r in cur.fetchall()]
        self._conn.commit()
        return rows

    def count(self, table: str) -> int:
        return self.query(f"SELECT COUNT(*) AS n FROM {table};")[0]["n"]


def _make_child_tables(d1: _SqliteD1) -> None:
    d1.query(
        "CREATE TABLE deep_dive_evidence ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " deep_dive_run_id INTEGER NOT NULL,"
        " evidence_id TEXT NOT NULL,"
        " source_db TEXT, source_url TEXT, span_text TEXT,"
        " claim_kind TEXT, is_primary INTEGER NOT NULL DEFAULT 0);"
    )
    d1.query(
        "CREATE TABLE deep_dive_search_log ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " deep_dive_run_id INTEGER NOT NULL,"
        " step_index INTEGER NOT NULL,"
        " source TEXT NOT NULL, query TEXT, hit_count INTEGER,"
        " yielded_citation INTEGER NOT NULL DEFAULT 0);"
    )


def _fake_record() -> SimpleNamespace:
    """A record carrying just the attributes the inserters read.

    Covers a span-bearing evidence row, a span-less one (exercises the
    ``None`` source/url/quote branch), and search-log rows with and without
    a query / sources_seen.
    """
    ev1 = SimpleNamespace(
        evidence_id="evi_001",
        claim_type="topology",
        evidence_tier="primary",
        spans=[
            SimpleNamespace(
                source=SimpleNamespace(source_type="uniprot", url=None),
                quote="extracellular domain",
            )
        ],
    )
    ev2 = SimpleNamespace(
        evidence_id="evi_002",
        claim_type="expression",
        evidence_tier="secondary",
        spans=[],
    )
    sl1 = SimpleNamespace(
        tool="europepmc_search", query="surface marker", n_results=3,
        sources_seen=["PMID:1"],
    )
    sl2 = SimpleNamespace(
        tool="pubtator", query=None, n_results=0, sources_seen=[],
    )
    return SimpleNamespace(evidence=[ev1, ev2], search_log=[sl1, sl2])


def test_evidence_insert_is_idempotent_under_retry() -> None:
    d1 = _SqliteD1()
    _make_child_tables(d1)
    record = _fake_record()

    _ins_evidence(d1, 1, record)
    assert d1.count("deep_dive_evidence") == 2

    # Simulate an at-least-once retry re-running the identical batch.
    _ins_evidence(d1, 1, record)
    assert d1.count("deep_dive_evidence") == 2  # no duplication

    # The span-less row persisted its NULLs (not a phantom dedup miss).
    null_rows = d1.query(
        "SELECT evidence_id FROM deep_dive_evidence WHERE source_db IS NULL;"
    )
    assert [r["evidence_id"] for r in null_rows] == ["evi_002"]


def test_search_log_insert_is_idempotent_under_retry() -> None:
    d1 = _SqliteD1()
    _make_child_tables(d1)
    record = _fake_record()

    _ins_search_log(d1, 1, record)
    assert d1.count("deep_dive_search_log") == 2

    _ins_search_log(d1, 1, record)
    assert d1.count("deep_dive_search_log") == 2  # no duplication


def test_distinct_parents_do_not_collide() -> None:
    """The natural key is scoped by ``deep_dive_run_id`` — the same
    evidence_id / step_index under a different parent must still insert.
    """
    d1 = _SqliteD1()
    _make_child_tables(d1)
    record = _fake_record()

    _ins_evidence(d1, 1, record)
    _ins_evidence(d1, 2, record)  # different parent, same evidence_ids
    assert d1.count("deep_dive_evidence") == 4

    _ins_search_log(d1, 1, record)
    _ins_search_log(d1, 2, record)
    assert d1.count("deep_dive_search_log") == 4
