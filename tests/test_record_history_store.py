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
    LatestRevision,
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
    # Force the REST fallback path regardless of this process's env (a real
    # CLOUDFLARE_ACCOUNT_ID/CLOUDFLARE_API_TOKEN, if ever set, must not make
    # these tests silently try to build a real S3 client).
    monkeypatch.setattr(record_history_store, "_s3_client_or_none", lambda: None)

    # Deliberately name a DIFFERENT bucket — CloudRevisionStore must still
    # pin writes to BUCKET regardless of what's passed in.
    cfg = R2Config(account_id="acct", api_token="tok", bucket="some-other-bucket")
    store = CloudRevisionStore(_FakeD1(), cfg, d1_qps=0)  # ty: ignore[invalid-argument-type]
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


# ---------------------------------------------------------------------------
# CloudRevisionStore.put_blob — S3 path (the preferred one; REST is only the
# fallback exercised above).
# ---------------------------------------------------------------------------


def _client_error(status: int, code: str = "404") -> Exception:
    from botocore.exceptions import ClientError

    return ClientError(
        {
            "Error": {"Code": code, "Message": "boom"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "HeadObject",
    )


class _FakeS3Client:
    def __init__(
        self,
        *,
        head_error: Exception | None = None,
        put_error: Exception | None = None,
    ) -> None:
        self.head_calls: list[tuple[str, str]] = []
        self.put_calls: list[tuple[str, str, bytes, str]] = []
        self._head_error = head_error
        self._put_error = put_error

    def head_object(self, *, Bucket: str, Key: str) -> dict:
        self.head_calls.append((Bucket, Key))
        if self._head_error is not None:
            raise self._head_error
        return {"ContentLength": 2}

    def put_object(
        self, *, Bucket: str, Key: str, Body: bytes, ContentType: str
    ) -> dict:
        self.put_calls.append((Bucket, Key, Body, ContentType))
        if self._put_error is not None:
            raise self._put_error
        return {}


def _s3_store(monkeypatch: pytest.MonkeyPatch, client: _FakeS3Client) -> CloudRevisionStore:
    monkeypatch.setattr(record_history_store, "_s3_client_or_none", lambda: client)
    cfg = R2Config(account_id="acct", api_token="tok", bucket="some-other-bucket")
    return CloudRevisionStore(_FakeD1(), cfg, d1_qps=0)  # ty: ignore[invalid-argument-type]


def test_s3_head_hit_skips_put(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeS3Client()  # head succeeds -> object already present
    store = _s3_store(monkeypatch, client)

    store.put_blob("records/sha256/aa.json", b"{}", "application/json")

    assert client.head_calls == [(BUCKET, "records/sha256/aa.json")]
    assert client.put_calls == []


def test_s3_head_404_falls_through_to_put(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeS3Client(head_error=_client_error(404))
    store = _s3_store(monkeypatch, client)

    store.put_blob("records/sha256/aa.json", b'{"x":1}', "application/json")

    assert client.head_calls == [(BUCKET, "records/sha256/aa.json")]
    assert client.put_calls == [
        (BUCKET, "records/sha256/aa.json", b'{"x":1}', "application/json")
    ]


def test_s3_head_other_client_error_raises_archive_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeS3Client(head_error=_client_error(403, code="AccessDenied"))
    store = _s3_store(monkeypatch, client)

    with pytest.raises(ArchiveError):
        store.put_blob("k", b"{}", "application/json")
    assert client.put_calls == []


def test_s3_put_object_error_raises_archive_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeS3Client(
        head_error=_client_error(404), put_error=_client_error(500, code="500")
    )
    store = _s3_store(monkeypatch, client)

    with pytest.raises(ArchiveError):
        store.put_blob("k", b"{}", "application/json")


def test_s3_unavailable_warns_once_then_falls_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(record_history_store, "_s3_fallback_warned", False)

    def _raise_credential_error() -> None:
        raise record_history_store.R2S3CredentialError("no token")

    monkeypatch.setattr(record_history_store, "r2_s3_client", _raise_credential_error)
    calls: list[str] = []
    monkeypatch.setattr(
        record_history_store.r2_client,
        "head_object",
        lambda *, key, cfg: (calls.append(key), None)[1],
    )
    monkeypatch.setattr(
        record_history_store.r2_client,
        "put_object",
        lambda *, key, body, content_type, cfg: (calls.append(key), True)[1],
    )
    cfg = R2Config(account_id="a", api_token="t", bucket="b")
    store = CloudRevisionStore(_FakeD1(), cfg, d1_qps=0)  # ty: ignore[invalid-argument-type]

    import logging

    with caplog.at_level(logging.WARNING):
        store.put_blob("k1", b"{}", "application/json")
        store.put_blob("k2", b"{}", "application/json")

    assert calls == ["k1", "k1", "k2", "k2"]  # head+put, twice
    assert sum("R2 S3 client unavailable" in r.message for r in caplog.records) == 1


def test_require_s3_raises_instead_of_falling_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        record_history_store,
        "r2_s3_client",
        lambda: (_ for _ in ()).throw(record_history_store.R2S3CredentialError("no token")),
    )

    def _must_not_run(*_a: object, **_kw: object) -> None:
        raise AssertionError("REST fallback must not run under require_s3=True")

    monkeypatch.setattr(record_history_store.r2_client, "head_object", _must_not_run)
    monkeypatch.setattr(record_history_store.r2_client, "put_object", _must_not_run)
    cfg = R2Config(account_id="a", api_token="t", bucket="b")
    store = CloudRevisionStore(
        _FakeD1(), cfg, d1_qps=0, require_s3=True  # ty: ignore[invalid-argument-type]
    )

    with pytest.raises(ArchiveError, match="require_s3"):
        store.put_blob("k", b"{}", "application/json")


def test_require_s3_false_keeps_the_rest_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default (publish path) is unaffected by require_s3."""
    monkeypatch.setattr(
        record_history_store,
        "r2_s3_client",
        lambda: (_ for _ in ()).throw(record_history_store.R2S3CredentialError("no token")),
    )
    monkeypatch.setattr(
        record_history_store.r2_client, "head_object", lambda *, key, cfg: None
    )
    put_calls: list[str] = []
    monkeypatch.setattr(
        record_history_store.r2_client,
        "put_object",
        lambda *, key, body, content_type, cfg: (put_calls.append(key), True)[1],
    )
    cfg = R2Config(account_id="a", api_token="t", bucket="b")
    store = CloudRevisionStore(_FakeD1(), cfg, d1_qps=0)  # ty: ignore[invalid-argument-type]

    store.put_blob("k", b"{}", "application/json")  # must not raise

    assert put_calls == ["k"]


# ---------------------------------------------------------------------------
# CloudRevisionStore.prefetch_latest — a JOIN query + a verification COUNT,
# then a cached latest().
# ---------------------------------------------------------------------------


class _ScriptedD1:
    """Returns canned rows keyed by a substring match on the SQL text."""

    def __init__(self, responses: dict[str, list[dict]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, list]] = []

    def query(self, sql: str, params: list | None = None) -> list[dict]:
        self.calls.append((sql, params or []))
        for needle, rows in self._responses.items():
            if needle in sql:
                return rows
        raise AssertionError(f"unscripted query: {sql[:60]!r}")

    def close(self) -> None:
        pass


def _prefetch_store(d1: _ScriptedD1) -> CloudRevisionStore:
    cfg = R2Config(account_id="a", api_token="t", bucket="b")
    return CloudRevisionStore(d1, cfg, d1_qps=0)  # ty: ignore[invalid-argument-type]


def test_prefetch_latest_and_latest_then_serves_from_cache() -> None:
    d1 = _ScriptedD1(
        {
            "record_revision r\nJOIN": [
                {
                    "gene_symbol": "EGFR",
                    "revision": 3,
                    "json_hash": "h3",
                    "evidence_hash": "e3",
                    "md_hash": None,
                }
            ],
            "COUNT(DISTINCT gene_symbol)": [{"n": 1}],
        }
    )
    store = _prefetch_store(d1)

    store.prefetch_latest()
    assert len(d1.calls) == 2  # the JOIN + the verification COUNT

    result = store.latest("EGFR")
    assert len(d1.calls) == 2  # no new query — served from cache
    assert result == LatestRevision(revision=3, json_hash="h3", evidence_hash="e3", md_hash=None)


def test_prefetch_latest_cache_is_case_insensitive() -> None:
    d1 = _ScriptedD1(
        {
            "record_revision r\nJOIN": [
                {
                    "gene_symbol": "Cxorf1",
                    "revision": 1,
                    "json_hash": "h1",
                    "evidence_hash": None,
                    "md_hash": None,
                }
            ],
            "COUNT(DISTINCT gene_symbol)": [{"n": 1}],
        }
    )
    store = _prefetch_store(d1)
    store.prefetch_latest()

    assert store.latest("CXORF1") is not None
    assert store.latest("cxorf1") is not None
    cached = store.latest("Cxorf1")
    assert cached is not None
    assert cached.revision == 1
    assert len(d1.calls) == 2


def test_gene_absent_from_primed_cache_returns_none_with_no_query() -> None:
    d1 = _ScriptedD1(
        {"record_revision r\nJOIN": [], "COUNT(DISTINCT gene_symbol)": [{"n": 0}]}
    )
    store = _prefetch_store(d1)
    store.prefetch_latest()

    assert store.latest("NOPE") is None
    assert len(d1.calls) == 2


def test_prefetch_latest_raises_when_count_disagrees_with_cache() -> None:
    """A join bug that silently drops a row must not prime a cache that
    would then misreport a real gene as never-archived."""
    d1 = _ScriptedD1(
        {
            "record_revision r\nJOIN": [
                {
                    "gene_symbol": "EGFR",
                    "revision": 1,
                    "json_hash": "h1",
                    "evidence_hash": None,
                    "md_hash": None,
                }
            ],
            # The join found 1 gene, but the table actually has 2 distinct
            # gene_symbol values — a dropped row.
            "COUNT(DISTINCT gene_symbol)": [{"n": 2}],
        }
    )
    store = _prefetch_store(d1)

    with pytest.raises(ArchiveError, match="prefetch_latest"):
        store.prefetch_latest()


def test_latest_without_prefetch_falls_back_to_per_gene_query() -> None:
    d1 = _ScriptedD1(
        {
            "ORDER BY revision DESC": [
                {
                    "revision": 1,
                    "json_hash": "h1",
                    "evidence_hash": None,
                    "md_hash": None,
                }
            ]
        }
    )
    store = _prefetch_store(d1)

    result = store.latest("EGFR")
    assert len(d1.calls) == 1
    assert result == LatestRevision(revision=1, json_hash="h1", evidence_hash=None, md_hash=None)


def test_insert_revision_updates_the_primed_cache_without_a_requery() -> None:
    d1 = _ScriptedD1(
        {
            "record_revision r\nJOIN": [],
            "COUNT(DISTINCT gene_symbol)": [{"n": 0}],
            "RETURNING revision": [{"revision": 5}],
        }
    )
    store = _prefetch_store(d1)
    store.prefetch_latest()
    assert store.latest("EGFR") is None

    revision = store.insert_revision(
        ["EGFR", "HGNC:3236", "newhash", None, None, "2026-09-27T00:00:00Z", "sweep", "s", "p"]
    )

    assert revision == 5
    assert len(d1.calls) == 3  # prefetch (2) + the one insert — no extra latest() query
    cached = store.latest("egfr")
    assert cached == LatestRevision(revision=5, json_hash="newhash", evidence_hash=None, md_hash=None)
    assert len(d1.calls) == 3  # still served from the updated cache


def test_insert_revision_unchanged_refreshes_the_cached_entry_via_requery() -> None:
    """`insert_revision` reporting "unchanged" (``None``) means some row —
    possibly not the one our cache thinks is latest — is now the real
    latest. Regardless of whether the gene was already cached, the cache
    entry is refreshed from a fresh per-gene query rather than left as-is."""
    d1 = _ScriptedD1(
        {
            "record_revision r\nJOIN": [
                {
                    "gene_symbol": "EGFR",
                    "revision": 2,
                    "json_hash": "h2",
                    "evidence_hash": None,
                    "md_hash": None,
                }
            ],
            "COUNT(DISTINCT gene_symbol)": [{"n": 1}],
            "RETURNING revision": [],  # unchanged: no row returned
            "ORDER BY revision DESC": [
                {
                    "revision": 2,
                    "json_hash": "h2",
                    "evidence_hash": None,
                    "md_hash": None,
                }
            ],
        }
    )
    store = _prefetch_store(d1)
    store.prefetch_latest()  # 2 calls
    assert len(d1.calls) == 2

    revision = store.insert_revision(
        ["EGFR", "HGNC:3236", "h2", None, None, "2026-09-27T00:00:00Z", "sweep", "s", "p"]
    )

    assert revision is None
    # prefetch (2) + insert (1) + the refresh re-query (1) = 4 total.
    assert len(d1.calls) == 4
    assert store.latest("EGFR") == LatestRevision(
        revision=2, json_hash="h2", evidence_hash=None, md_hash=None
    )
    assert len(d1.calls) == 4  # served from the (refreshed) cache, no new query


def test_insert_revision_none_for_gene_absent_from_cache_populates_it_via_requery() -> None:
    """Reproduces the bug this refresh fixes: a concurrent writer inserts a
    brand-new gene's revision 1 after our `prefetch_latest()` snapshot. Our
    `insert_revision` call for that same content then reports "unchanged"
    (``None``), but the gene was never in our cache — without the refresh,
    `latest()` would then wrongly report ``None`` for a gene D1 actually
    has a real revision for."""
    d1 = _ScriptedD1(
        {
            "record_revision r\nJOIN": [],  # prefetch ran before EGFR existed
            "COUNT(DISTINCT gene_symbol)": [{"n": 0}],
            "RETURNING revision": [],  # unchanged — another writer already landed it
            "ORDER BY revision DESC": [
                {
                    "revision": 1,
                    "json_hash": "h1",
                    "evidence_hash": None,
                    "md_hash": None,
                }
            ],
        }
    )
    store = _prefetch_store(d1)
    store.prefetch_latest()
    assert store.latest("EGFR") is None  # not in the (empty) cache yet

    revision = store.insert_revision(
        ["EGFR", "HGNC:3236", "h1", None, None, "2026-09-27T00:00:00Z", "sweep", "s", "p"]
    )

    assert revision is None
    assert store.latest("EGFR") == LatestRevision(
        revision=1, json_hash="h1", evidence_hash=None, md_hash=None
    )
