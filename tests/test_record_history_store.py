"""Record-history store: DDL shape, key scheme, and the insert-if-changed SQL."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from accessible_surfaceome.cloud.record_history.store import (
    BUCKET,
    DDL,
    INSERT_REVISION_SQL,
    blob_key,
)

_ROOT = Path(__file__).resolve().parents[1]


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    for stmt in DDL:
        con.execute(stmt)
    return con


def _insert(
    con: sqlite3.Connection, sym: str, j: str, e: str | None, m: str | None
) -> list:
    return con.execute(
        INSERT_REVISION_SQL,
        [sym, "HGNC:1", j, e, m, "2026-09-27T00:00:00Z", "sweep", "2.14.4", "2.50.2"],
    ).fetchall()


def test_blob_key_and_bucket() -> None:
    assert BUCKET == "surfaceome-record-history"
    assert blob_key("ab" * 32, "json") == f"records/sha256/{'ab' * 32}.json"


def test_first_insert_is_revision_one() -> None:
    con = _db()
    assert _insert(con, "EGFR", "h1", "e1", "m1") == [(1,)]


def test_unchanged_insert_writes_nothing() -> None:
    con = _db()
    _insert(con, "EGFR", "h1", "e1", None)
    assert _insert(con, "EGFR", "h1", "e1", None) == []
    assert con.execute("SELECT count(*) FROM record_revision").fetchone() == (1,)


def test_any_part_change_is_a_new_revision() -> None:
    con = _db()
    _insert(con, "EGFR", "h1", "e1", "m1")
    assert _insert(con, "EGFR", "h1", "e1", "m2") == [(2,)]
    assert _insert(con, "EGFR", "h1", "e2", "m2") == [(3,)]


def test_revert_is_a_new_revision() -> None:
    con = _db()
    _insert(con, "EGFR", "h1", None, None)
    _insert(con, "EGFR", "h2", None, None)
    assert _insert(con, "EGFR", "h1", None, None) == [(3,)]


def test_revisions_are_per_gene_and_case_insensitive() -> None:
    con = _db()
    _insert(con, "C11orf24", "h1", None, None)
    assert _insert(con, "EGFR", "h9", None, None) == [(1,)]
    assert _insert(con, "c11ORF24", "h1", None, None) == []


def test_public_schema_file_documents_every_table() -> None:
    sql = (_ROOT / "cloudflare/d1_public_schema.sql").read_text()
    for table in ("record_revision", "data_release", "data_release_member"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
