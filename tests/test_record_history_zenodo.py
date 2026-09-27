"""Drafting a new Zenodo data-record version never publishes."""

from __future__ import annotations

from pathlib import Path

import httpx

from accessible_surfaceome.cloud.record_history.zenodo import create_draft_version

API = "https://zenodo.test/api"


def test_draft_version_flow(tmp_path: Path) -> None:
    tarball = tmp_path / "deep_dives_1.3.0.tar.gz"
    tarball.write_bytes(b"tgz")
    calls: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        p = req.url.path
        if p == "/api/records/20805383/versions/latest":
            return httpx.Response(200, json={"id": 20805384})
        if p == "/api/deposit/depositions/20805384/actions/newversion":
            return httpx.Response(
                201, json={"links": {"latest_draft": f"{API}/deposit/depositions/999"}}
            )
        if p == "/api/deposit/depositions/999" and req.method == "GET":
            return httpx.Response(
                200,
                json={
                    "metadata": {"title": "t", "version": ""},
                    "files": [
                        {
                            "filename": "deep_dives_all.tar.gz",
                            "links": {"self": f"{API}/files/old"},
                        },
                        {
                            "filename": "README.md",
                            "links": {"self": f"{API}/files/readme"},
                        },
                    ],
                    "links": {
                        "bucket": f"{API}/files/bucket",
                        "self": f"{API}/deposit/depositions/999",
                        "html": "https://zenodo.test/deposit/999",
                    },
                },
            )
        return httpx.Response(200, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    url = create_draft_version(
        token="t", tarball=tarball, version="1.3.0", http=http, api=API
    )

    assert url == "https://zenodo.test/deposit/999"
    assert ("DELETE", "/api/files/old") in calls  # old tarball replaced
    assert ("DELETE", "/api/files/readme") not in calls  # other files kept
    assert ("PUT", "/api/files/bucket/deep_dives_1.3.0.tar.gz") in calls
    assert ("PUT", "/api/deposit/depositions/999") in calls  # metadata
    assert not any("publish" in path for _, path in calls)
