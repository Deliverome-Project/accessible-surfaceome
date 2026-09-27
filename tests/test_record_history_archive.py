"""archive_gene: fetch what the Worker served, write only what changed."""

from __future__ import annotations

import json

import httpx
import pytest

from accessible_surfaceome.cloud.d1_client import D1Error
from accessible_surfaceome.cloud.record_history.archive import (
    BYPASS_HEADER,
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


def _http(
    record=RECORD, evidence=EVIDENCE, md=MD, seen: list | None = None
) -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(req)
        path = req.url.path
        if path.endswith("/v1/genes/EGFR"):
            return httpx.Response(200, json=record) if record else httpx.Response(404)
        if path.endswith("/v1/genes/EGFR/evidence"):
            return (
                httpx.Response(200, json=evidence) if evidence else httpx.Response(404)
            )
        if path.endswith("/v1/genes/EGFR.md"):
            return httpx.Response(200, text=md) if md else httpx.Response(404)
        return httpx.Response(404)

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
    p = first.inserts[0]
    latest = LatestRevision(
        revision=4, json_hash=p[2], evidence_hash=p[3], md_hash=p[4]
    )
    store = FakeStore(latest)
    result = _run(store, _http())
    assert (result.status, result.revision) == ("unchanged", 4)
    assert store.blobs == {} and store.inserts == []


def test_timestamp_only_change_is_unchanged() -> None:
    first = FakeStore()
    _run(first, _http())
    p = first.inserts[0]
    latest = LatestRevision(
        revision=1, json_hash=p[2], evidence_hash=p[3], md_hash=p[4]
    )
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
    assert _run(store, _http()).status == "created"


def test_missing_token_refuses() -> None:
    with pytest.raises(ArchiveError, match="ARCHIVE_BYPASS_TOKEN"):
        archive_gene(
            "EGFR", source="sweep", http=_http(), store=FakeStore(), token="", base=BASE
        )


def test_server_error_propagates() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    with pytest.raises(httpx.HTTPStatusError):
        _run(FakeStore(), http)
