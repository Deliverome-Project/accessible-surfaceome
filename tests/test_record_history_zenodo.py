"""Drafting a new Zenodo data-record version never publishes."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from accessible_surfaceome.cloud.record_history.zenodo import (
    ZenodoDraftError,
    create_draft_version,
)

API = "https://zenodo.test/api"


def _draft_json() -> dict:
    return {
        # doi / prereserve_doi are the kind of server-assigned fields a
        # real Zenodo draft echoes back on GET — must not be replayed.
        "metadata": {
            "title": "t",
            "version": "",
            "doi": "10.5281/zenodo.999",
            "prereserve_doi": {"doi": "10.5281/zenodo.999"},
        },
        "files": [
            {
                "filename": "deep_dives_all.tar.gz",
                "links": {"self": f"{API}/files/old"},
            },
            {"filename": "README.md", "links": {"self": f"{API}/files/readme"}},
        ],
        "links": {
            "bucket": f"{API}/files/bucket",
            "self": f"{API}/deposit/depositions/999",
            "html": "https://zenodo.test/deposit/999",
        },
    }


class _Recorder:
    """Captures every request the handler sees, keyed by (method, path)."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def record(self, req: httpx.Request) -> None:
        self.requests.append(req)

    def get(self, method: str, path: str) -> httpx.Request:
        return next(
            r for r in self.requests if r.method == method and r.url.path == path
        )

    def calls(self) -> list[tuple[str, str]]:
        return [(r.method, r.url.path) for r in self.requests]


def test_draft_version_flow(tmp_path: Path) -> None:
    tarball = tmp_path / "deep_dives_1.3.0.tar.gz"
    tarball.write_bytes(b"tgz")
    rec = _Recorder()

    def handler(req: httpx.Request) -> httpx.Response:
        rec.record(req)
        p = req.url.path
        if p == "/api/records/20805383/versions/latest":
            return httpx.Response(200, json={"id": 20805384})
        if p == "/api/deposit/depositions/20805384/actions/newversion":
            return httpx.Response(
                201, json={"links": {"latest_draft": f"{API}/deposit/depositions/999"}}
            )
        if p == "/api/deposit/depositions/999" and req.method == "GET":
            return httpx.Response(200, json=_draft_json())
        return httpx.Response(200, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    url = create_draft_version(
        token="t", tarball=tarball, version="1.3.0", http=http, api=API
    )

    calls = rec.calls()
    assert url == "https://zenodo.test/deposit/999"
    assert ("DELETE", "/api/files/old") in calls  # old tarball replaced
    assert ("DELETE", "/api/files/readme") not in calls  # other files kept
    assert ("PUT", "/api/files/bucket/deep_dives_1.3.0.tar.gz") in calls
    assert ("PUT", "/api/deposit/depositions/999") in calls  # metadata
    assert not any("publish" in path for _, path in calls)

    # The public records read carries no credential at all — no header,
    # no access_token query param.
    records_req = rec.get("GET", "/api/records/20805383/versions/latest")
    assert "authorization" not in records_req.headers
    assert "access_token" not in records_req.url.params

    # Every deposit/file-API call carries the token as a Bearer header and
    # NEVER as an access_token query param.
    for req in rec.requests:
        if req is records_req:
            continue
        assert req.headers.get("authorization") == "Bearer t"
        assert "access_token" not in req.url.params

    # doi / prereserve_doi were stripped before the metadata PUT.
    metadata_req = rec.get("PUT", "/api/deposit/depositions/999")
    body = json.loads(metadata_req.content)
    assert "doi" not in body["metadata"]
    assert "prereserve_doi" not in body["metadata"]
    assert body["metadata"]["version"] == "1.3.0"


def test_draft_version_400_on_newversion_raises_clear_error(tmp_path: Path) -> None:
    tarball = tmp_path / "deep_dives_1.3.0.tar.gz"
    tarball.write_bytes(b"tgz")

    def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/api/records/20805383/versions/latest":
            return httpx.Response(200, json={"id": 20805384})
        if p == "/api/deposit/depositions/20805384/actions/newversion":
            return httpx.Response(
                400, json={"message": "already has an unpublished draft"}
            )
        return httpx.Response(200, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ZenodoDraftError, match="Publish or discard"):
        create_draft_version(
            token="t", tarball=tarball, version="1.3.0", http=http, api=API
        )


def test_draft_version_missing_latest_draft_link_raises_clear_error(
    tmp_path: Path,
) -> None:
    tarball = tmp_path / "deep_dives_1.3.0.tar.gz"
    tarball.write_bytes(b"tgz")

    def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/api/records/20805383/versions/latest":
            return httpx.Response(200, json={"id": 20805384})
        if p == "/api/deposit/depositions/20805384/actions/newversion":
            return httpx.Response(201, json={"links": {}})
        return httpx.Response(200, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ZenodoDraftError, match="Publish or discard"):
        create_draft_version(
            token="t", tarball=tarball, version="1.3.0", http=http, api=API
        )
