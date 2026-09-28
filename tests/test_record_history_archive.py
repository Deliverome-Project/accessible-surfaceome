"""archive_gene: fetch what the Worker served, write only what changed."""

from __future__ import annotations

import json
from typing import cast

import httpx
import pytest

from accessible_surfaceome.cloud.d1_client import D1Error
from accessible_surfaceome.cloud.record_history.archive import (
    BYPASS_HEADER,
    BYPASS_HONORED_HEADER,
    archive_gene,
)
from accessible_surfaceome.cloud.record_history.hashing import content_hash_record
from accessible_surfaceome.cloud.record_history.store import (
    ArchiveError,
    LatestRevision,
    blob_key,
)

BASE = "https://api.test/surfaceome"
RECORD = {
    "gene": {"hgnc_symbol": "EGFR", "hgnc_id": "HGNC:3236"},
    "schema_version": "2.14.4",
    "prompt_corpus_version": "2.50.2",
    "record_generated_at": "2026-09-27T00:00:00Z",
    "confidence": "high",
}
EVIDENCE = {"gene": "EGFR", "evidence": [{"id": "e1"}], "papers": {}}
MD = "# EGFR\n\n*Schema v2.14.4 · generated 2026-09-27T00:00:00Z · model `m`*\n"


class FakeStore:
    def __init__(self, latest: LatestRevision | None = None) -> None:
        self._latest = latest
        self.blobs: dict[str, bytes] = {}
        self.inserts: list[list[object]] = []
        self.fail_insert_once = False

    def latest(self, gene_symbol: str) -> LatestRevision | None:
        return self._latest

    def put_blob(self, key: str, body: bytes, content_type: str) -> None:
        self.blobs[key] = body

    def insert_revision(self, params: list[object]) -> int | None:
        if self.fail_insert_once:
            self.fail_insert_once = False
            raise D1Error("UNIQUE constraint failed: record_revision.gene_symbol")
        self.inserts.append(params)
        return (self._latest.revision if self._latest else 0) + 1


def _latest_from(params: list[object], *, revision: int) -> LatestRevision:
    """Typed reconstruction of a `LatestRevision` from a captured insert's
    params list (whose element type is `object`, since `RevisionStore` is a
    structural Protocol) — avoids `ty` flagging `object` where `str | None`
    is expected."""
    return LatestRevision(
        revision=revision,
        json_hash=cast(str, params[2]),
        evidence_hash=cast("str | None", params[3]),
        md_hash=cast("str | None", params[4]),
    )


def _http(
    record=RECORD,
    evidence=EVIDENCE,
    md=MD,
    seen: list | None = None,
    honored: bool = True,
) -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(req)
        path = req.url.path
        if path.endswith("/v1/genes/EGFR"):
            headers = {BYPASS_HONORED_HEADER: "1"} if honored else {}
            if record:
                return httpx.Response(200, json=record, headers=headers)
            return httpx.Response(
                404, json={"error": "gene_not_annotated"}, headers=headers
            )
        if path.endswith("/v1/genes/EGFR/evidence"):
            if evidence:
                return httpx.Response(200, json=evidence)
            return httpx.Response(404, json={"error": "gene_not_annotated"})
        if path.endswith("/v1/genes/EGFR.md"):
            if md:
                return httpx.Response(200, text=md)
            return httpx.Response(404, json={"error": "markdown_not_found"})
        return httpx.Response(404, json={"error": "route_not_found"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _run(store, http, **kw):
    return archive_gene(
        "EGFR", source="sweep", http=http, store=store, token="tok", base=BASE, **kw
    )


def test_first_archive_writes_three_blobs_and_revision_one() -> None:
    store, seen = FakeStore(), []
    purged: list[list[str]] = []
    result = _run(store, _http(seen=seen), purge=purged.append)
    assert (result.status, result.revision) == ("created", 1)
    assert len(store.blobs) == 3
    # Stored bytes are exactly what the server sent; compare parsed.
    assert (
        json.loads(store.blobs[blob_key(content_hash_record(RECORD), "json")]) == RECORD
    )
    params = store.inserts[0]
    assert params[0] == "EGFR" and params[1] == "HGNC:3236" and params[6] == "sweep"
    assert all(r.headers[BYPASS_HEADER] == "tok" for r in seen)
    assert purged == [["/v1/genes/EGFR/revisions", "/v1/releases"]]


def test_unchanged_writes_nothing() -> None:
    first = FakeStore()
    _run(first, _http())
    latest = _latest_from(first.inserts[0], revision=4)
    store = FakeStore(latest)
    result = _run(store, _http())
    assert (result.status, result.revision) == ("unchanged", 4)
    assert store.blobs == {} and store.inserts == []


def test_timestamp_only_change_is_unchanged() -> None:
    first = FakeStore()
    _run(first, _http())
    latest = _latest_from(first.inserts[0], revision=1)
    bumped = {**RECORD, "record_generated_at": "2026-10-01T00:00:00Z"}
    md2 = MD.replace("2026-09-27T00:00:00Z", "2026-10-01T00:00:00Z")
    assert _run(FakeStore(latest), _http(record=bumped, md=md2)).status == "unchanged"


def test_missing_md_and_evidence_are_null_hashes() -> None:
    store = FakeStore()
    _run(store, _http(evidence=None, md=None))
    assert store.inserts[0][3] is None and store.inserts[0][4] is None
    assert len(store.blobs) == 1


def test_not_annotated_gene() -> None:
    store = FakeStore()
    assert _run(store, _http(record=None)).status == "not_annotated"
    assert store.inserts == []


def test_lost_race_is_retried_once() -> None:
    store = FakeStore()
    store.fail_insert_once = True
    result = _run(store, _http())
    assert result.status == "created"
    assert result.revision == 1
    assert len(store.inserts) == 1


def test_missing_token_refuses() -> None:
    with pytest.raises(ArchiveError, match="ARCHIVE_BYPASS_TOKEN"):
        archive_gene(
            "EGFR", source="sweep", http=_http(), store=FakeStore(), token="", base=BASE
        )


def test_server_error_propagates() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    with pytest.raises(httpx.HTTPStatusError):
        _run(FakeStore(), http)


def test_uses_canonical_symbol_for_followup_fetches() -> None:
    """The record route may be reached with a non-canonical casing (e.g. a
    caller-supplied "egfr"), but the Markdown route is matched exactly
    against its R2 key — so evidence and .md must be re-fetched with the
    record's own gene.hgnc_symbol, not the caller's symbol."""
    seen_syms: list[str] = []

    class TrackingStore(FakeStore):
        def latest(self, gene_symbol: str) -> LatestRevision | None:
            seen_syms.append(gene_symbol)
            return super().latest(gene_symbol)

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path.endswith("/v1/genes/egfr"):
            return httpx.Response(
                200, json=RECORD, headers={BYPASS_HONORED_HEADER: "1"}
            )
        if path.endswith("/v1/genes/EGFR/evidence"):
            return httpx.Response(200, json=EVIDENCE)
        if path.endswith("/v1/genes/EGFR.md"):
            return httpx.Response(200, text=MD)
        return httpx.Response(404, json={"error": "route_not_found"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    store = TrackingStore()
    result = archive_gene(
        "egfr", source="sweep", http=http, store=store, token="tok", base=BASE
    )
    assert result.status == "created"
    assert seen_syms == ["EGFR"]
    assert store.inserts[0][0] == "EGFR"
    assert store.inserts[0][4] is not None  # md_hash
    assert len(store.blobs) == 3


def test_missing_bypass_honored_header_raises() -> None:
    store = FakeStore()
    with pytest.raises(ArchiveError, match="bypass not honoured"):
        _run(store, _http(honored=False))
    assert store.blobs == {} and store.inserts == []


def test_wrong_404_reason_on_record_raises() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json={"error": "route_not_found"}, headers={BYPASS_HONORED_HEADER: "1"}
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    store = FakeStore()
    with pytest.raises(ArchiveError, match="unexpected 404"):
        _run(store, http)
    assert store.blobs == {} and store.inserts == []


def test_wrong_404_reason_on_md_raises() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path.endswith("/v1/genes/EGFR"):
            return httpx.Response(
                200, json=RECORD, headers={BYPASS_HONORED_HEADER: "1"}
            )
        if path.endswith("/v1/genes/EGFR/evidence"):
            return httpx.Response(200, json=EVIDENCE)
        if path.endswith("/v1/genes/EGFR.md"):
            return httpx.Response(404, json={"error": "markdown_unavailable"})
        return httpx.Response(404, json={"error": "route_not_found"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    store = FakeStore()
    with pytest.raises(ArchiveError, match="unexpected 404"):
        _run(store, http)
    assert store.blobs == {} and store.inserts == []


def test_evidence_5xx_aborts() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path.endswith("/v1/genes/EGFR"):
            return httpx.Response(
                200, json=RECORD, headers={BYPASS_HONORED_HEADER: "1"}
            )
        if path.endswith("/v1/genes/EGFR/evidence"):
            return httpx.Response(503)
        return httpx.Response(404, json={"error": "route_not_found"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    store = FakeStore()
    with pytest.raises(httpx.HTTPStatusError):
        _run(store, http)
    assert store.blobs == {} and store.inserts == []


def test_non_unique_d1_error_propagates() -> None:
    class ExplodingStore(FakeStore):
        def insert_revision(self, params: list[object]) -> int | None:
            raise D1Error("SQLITE_ERROR: database is locked")

    with pytest.raises(D1Error, match="database is locked"):
        _run(ExplodingStore(), _http())


def test_insert_returns_none_calls_purge_and_reads_latest() -> None:
    """A ``None`` from ``insert_revision`` without an exception means
    another writer (or a retried-but-already-committed insert) landed the
    identical content between our `latest()` check and our insert attempt.
    We report the now-current revision as unchanged, but still purge —
    that other writer's content may not have been purged yet."""

    class RacedStore(FakeStore):
        def insert_revision(self, params: list[object]) -> int | None:
            self.inserts.append(params)
            return None

    latest = LatestRevision(
        revision=7, json_hash="stale", evidence_hash=None, md_hash=None
    )
    store = RacedStore(latest)
    purged: list[list[str]] = []
    result = _run(store, _http(), purge=purged.append)
    assert (result.status, result.revision) == ("unchanged", 7)
    assert purged == [["/v1/genes/EGFR/revisions", "/v1/releases"]]
