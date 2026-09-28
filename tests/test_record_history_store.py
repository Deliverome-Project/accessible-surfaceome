"""Record-history store: DDL shape, key scheme, and the insert-if-changed SQL."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from accessible_surfaceome.cloud.record_history import store as record_history_store
from accessible_surfaceome.cloud.r2_client import R2Config
from accessible_surfaceome.cloud.record_history.store import (
    BUCKET,
    DDL,
    INSERT_REVISION_SQL,
    LATEST_REVISION_SQL,
    ArchiveError,
    CloudRevisionStore,
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


def test_duplicate_casing_never_both_get_revision_one() -> None:
    """The gap the COLLATE NOCASE column + PK close: two DIFFERENT casings
    of a gene's first-ever rows must share one revision sequence, never
    each independently land revision 1."""
    con = _db()
    assert _insert(con, "Cxorf1", "h1", None, None) == [(1,)]
    assert _insert(con, "CXORF1", "h2", None, None) == [(2,)]
    rows = con.execute(
        "SELECT gene_symbol, revision FROM record_revision ORDER BY revision"
    ).fetchall()
    # Stored casing is whatever the first insert used; never two rows at
    # revision 1 under different casings.
    assert rows == [("Cxorf1", 1), ("Cxorf1", 2)]


def test_latest_revision_lookup_uses_an_index() -> None:
    con = _db()
    _insert(con, "EGFR", "h1", None, None)
    plan = con.execute("EXPLAIN QUERY PLAN " + LATEST_REVISION_SQL, ["EGFR"]).fetchall()
    detail = " ".join(str(row[-1]) for row in plan)
    assert "SEARCH" in detail
    assert "SCAN" not in detail


def test_public_schema_file_documents_every_table() -> None:
    sql = (_ROOT / "cloudflare/d1_public_schema.sql").read_text()
    for table in ("record_revision", "data_release", "data_release_member"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql


# ---------------------------------------------------------------------------
# CloudRevisionStore.put_blob — R2 interaction, no real network / D1 calls.
# ---------------------------------------------------------------------------


class _FakeD1:
    """Stand-in for D1Client: put_blob never touches it."""

    def query(self, sql: str, params: list | None = None) -> list:  # noqa: ARG002
        raise AssertionError("put_blob should never query D1")

    def close(self) -> None:
        pass


def _fake_store(
    monkeypatch: pytest.MonkeyPatch, *, head_hit: bool, put_ok: bool = True
):
    calls: list[tuple[str, str, str]] = []

    def fake_head(*, key: str, cfg: R2Config):
        calls.append(("head", key, cfg.bucket))
        return {"ETag": "x"} if head_hit else None

    def fake_put(*, key: str, body: bytes, content_type: str, cfg: R2Config) -> bool:  # noqa: ARG001
        calls.append(("put", key, cfg.bucket))
        return put_ok

    monkeypatch.setattr(record_history_store.r2_client, "head_object", fake_head)
    monkeypatch.setattr(record_history_store.r2_client, "put_object", fake_put)

    # Deliberately name a DIFFERENT bucket — CloudRevisionStore must still
    # pin writes to BUCKET regardless of what's passed in.
    cfg = R2Config(account_id="acct", api_token="tok", bucket="some-other-bucket")
    store = CloudRevisionStore(_FakeD1(), cfg)  # ty: ignore[invalid-argument-type]
    return store, calls


def test_bucket_is_pinned_even_when_passed_config_names_another(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, calls = _fake_store(monkeypatch, head_hit=False)
    store.put_blob("records/sha256/aa.json", b"{}", "application/json")
    assert calls == [
        ("head", "records/sha256/aa.json", BUCKET),
        ("put", "records/sha256/aa.json", BUCKET),
    ]


def test_head_hit_skips_put(monkeypatch: pytest.MonkeyPatch) -> None:
    store, calls = _fake_store(monkeypatch, head_hit=True)
    store.put_blob("records/sha256/aa.json", b"{}", "application/json")
    assert calls == [("head", "records/sha256/aa.json", BUCKET)]


def test_put_failure_raises_archive_error(monkeypatch: pytest.MonkeyPatch) -> None:
    store, _calls = _fake_store(monkeypatch, head_hit=False, put_ok=False)
    with pytest.raises(ArchiveError):
        store.put_blob("records/sha256/aa.json", b"{}", "application/json")
