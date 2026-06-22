from __future__ import annotations

from pathlib import Path

import httpx

from accessible_surfaceome.tools._shared.cache import Cache
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.ratelimit import RateLimiter


def _make_http(
    tmp_path: Path, handler: httpx.MockTransport | httpx.BaseTransport
) -> CachedHTTP:
    http = CachedHTTP(Cache(tmp_path / "cache.sqlite"), RateLimiter({}))
    http._client = httpx.Client(
        transport=handler,
        headers={"User-Agent": "test"},
        follow_redirects=True,
    )
    return http


def test_ncbi_api_key_is_not_part_of_text_cache_key(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    http = _make_http(tmp_path, httpx.MockTransport(handler))
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"

    first = http.get_json(
        url,
        source="ncbi",
        ttl_days=90,
        params={"db": "pmc", "id": "1", "api_key": "key-a"},
    )
    second = http.get_json(
        url,
        source="ncbi",
        ttl_days=90,
        params={"db": "pmc", "id": "1", "api_key": "key-b"},
    )

    assert first == second == {"ok": True}
    assert len(calls) == 1
    assert "api_key=key-a" in calls[0]


def test_non_ncbi_api_key_stays_part_of_text_cache_key(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"url": str(request.url)})

    http = _make_http(tmp_path, httpx.MockTransport(handler))
    url = "https://api.example.test/resource"

    http.get_json(url, source="x", ttl_days=90, params={"id": "1", "api_key": "a"})
    http.get_json(url, source="x", ttl_days=90, params={"id": "1", "api_key": "b"})

    assert len(calls) == 2
