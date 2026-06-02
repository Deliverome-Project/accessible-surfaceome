"""Unit tests for ``CachedHTTP.get_bytes`` — the binary (PDF) fetch path.

``get_bytes`` caches to an on-disk blob dir (not the SQLite text cache). These
tests drive it through an httpx ``MockTransport`` so no network is touched, and
an injected tmp ``blob_dir`` so the on-disk cache is isolated per test.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

import httpx
import pytest

from accessible_surfaceome.tools._shared import http as http_mod
from accessible_surfaceome.tools._shared.cache import Cache
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.ratelimit import RateLimiter

_PDF_BYTES = b"%PDF-1.7\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _make_http(
    tmp_path: Path, handler: Callable[[httpx.Request], httpx.Response]
) -> CachedHTTP:
    cache = Cache(tmp_path / "cache.sqlite")
    http = CachedHTTP(cache, RateLimiter({}), blob_dir=tmp_path / "blob")
    # Swap the real client for one backed by the mock transport. CachedHTTP
    # owns ``_client``; reaching in is acceptable in a unit test.
    http._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "test"},
        follow_redirects=True,
    )
    return http


def test_get_bytes_fetches_and_caches(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, content=_PDF_BYTES)

    http = _make_http(tmp_path, handler)
    got = http.get_bytes("https://ex.org/a.pdf", source="unpaywall_pdf", ttl_days=180)
    assert got == _PDF_BYTES
    assert calls["n"] == 1

    # Blob written under <blob>/<source>/<key>.bin, no leftover .tmp.
    blobs = list((tmp_path / "blob" / "unpaywall_pdf").glob("*.bin"))
    assert len(blobs) == 1
    assert not list((tmp_path / "blob" / "unpaywall_pdf").glob("*.tmp"))

    # Second call within TTL is a cache hit — transport not invoked again.
    got2 = http.get_bytes("https://ex.org/a.pdf", source="unpaywall_pdf", ttl_days=180)
    assert got2 == _PDF_BYTES
    assert calls["n"] == 1


def test_get_bytes_distinct_urls_distinct_blobs(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-" + request.url.path.encode())

    http = _make_http(tmp_path, handler)
    a = http.get_bytes("https://ex.org/a.pdf", source="s", ttl_days=1)
    b = http.get_bytes("https://ex.org/b.pdf", source="s", ttl_days=1)
    assert a != b
    assert len(list((tmp_path / "blob" / "s").glob("*.bin"))) == 2


def test_get_bytes_ttl_expiry_refetches(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, content=_PDF_BYTES)

    http = _make_http(tmp_path, handler)
    http.get_bytes("https://ex.org/a.pdf", source="s", ttl_days=180)
    assert calls["n"] == 1

    # Age the blob 10s into the past, then read with a 0-day TTL → stale → refetch.
    blob = next((tmp_path / "blob" / "s").glob("*.bin"))
    old = time.time() - 10
    os.utime(blob, (old, old))
    http.get_bytes("https://ex.org/a.pdf", source="s", ttl_days=0)
    assert calls["n"] == 2


def test_get_bytes_rejects_oversized_via_content_length(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 5000)  # Content-Length: 5000

    http = _make_http(tmp_path, handler)
    with pytest.raises(ValueError):
        http.get_bytes("https://ex.org/big.pdf", source="s", ttl_days=1, max_bytes=1000)
    # Nothing cached on rejection.
    assert not list((tmp_path / "blob" / "s").glob("*.bin"))


def test_get_bytes_under_cap_succeeds(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_PDF_BYTES)

    http = _make_http(tmp_path, handler)
    got = http.get_bytes("https://ex.org/a.pdf", source="s", ttl_days=1, max_bytes=10_000)
    assert got == _PDF_BYTES


def test_get_bytes_retries_on_transient_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(http_mod.time, "sleep", lambda *_a, **_k: None)
    seq = [503, 503, 200]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        status = seq[calls["n"]]
        calls["n"] += 1
        if status == 200:
            return httpx.Response(200, content=_PDF_BYTES)
        return httpx.Response(status, content=b"err")

    http = _make_http(tmp_path, handler)
    got = http.get_bytes("https://ex.org/a.pdf", source="s", ttl_days=1)
    assert got == _PDF_BYTES
    assert calls["n"] == 3
