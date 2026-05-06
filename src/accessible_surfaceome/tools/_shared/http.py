"""Cached, rate-limited HTTP client used by every custom tool.

Thin wrapper around ``httpx.Client`` that integrates the SQLite cache and the
per-host rate limiter. Returns response *bodies* (text/JSON) rather than
``Response`` objects so cache hits and live fetches go through the same path
without needing to reconstruct a synthetic Response.
"""

from __future__ import annotations

import json as _json
import time
from pathlib import Path
from typing import Any

import httpx

from .cache import Cache, cache_key
from .ratelimit import RateLimiter

USER_AGENT = "accessible-surfaceome/0.1 (research; https://github.com/Deliverome-Project)"
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class CachedHTTP:
    """Stateful HTTP client. Keep one instance per process; close on exit."""

    def __init__(self, cache: Cache, limiter: RateLimiter, *, max_retries: int = 3):
        self._client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._cache = cache
        self._limiter = limiter
        self._max_retries = max_retries

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CachedHTTP:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get_text(
        self,
        url: str,
        *,
        source: str,
        ttl_days: int,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        return self._fetch("GET", url, source=source, ttl_days=ttl_days, params=params, headers=headers)

    def get_json(
        self,
        url: str,
        *,
        source: str,
        ttl_days: int,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        body = self.get_text(url, source=source, ttl_days=ttl_days, params=params, headers=headers)
        return _json.loads(body)

    def post_json(
        self,
        url: str,
        *,
        source: str,
        ttl_days: int,
        json_body: Any,
        headers: dict[str, str] | None = None,
    ) -> Any:
        canon = _json.dumps(json_body, sort_keys=True).encode()
        body = self._fetch(
            "POST",
            url,
            source=source,
            ttl_days=ttl_days,
            json_body=json_body,
            body_for_key=canon,
            headers=headers,
        )
        return _json.loads(body)

    def _fetch(
        self,
        method: str,
        url: str,
        *,
        source: str,
        ttl_days: int,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        body_for_key: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        canonical_url = url
        if params:
            qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            canonical_url = f"{url}?{qs}"
        key = cache_key(method, canonical_url, body_for_key)
        cached = self._cache.get(source, key, ttl_days=ttl_days)
        if cached is not None:
            return cached

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            self._limiter.wait(url)
            try:
                if method == "GET":
                    resp = self._client.get(url, params=params, headers=headers)
                elif method == "POST":
                    resp = self._client.post(url, json=json_body, headers=headers)
                else:
                    raise ValueError(f"unsupported method: {method}")
            except httpx.RequestError as e:
                last_exc = e
                if attempt == self._max_retries:
                    raise
                time.sleep(min(2**attempt, 8))
                continue
            if resp.status_code in RETRYABLE_STATUS and attempt < self._max_retries:
                time.sleep(min(2**attempt, 8))
                continue
            resp.raise_for_status()
            text = resp.text
            self._cache.put(source, key, text)
            return text

        assert last_exc is not None  # unreachable: loop exits via return or raise
        raise last_exc


def default_cache_path() -> Path:
    from accessible_surfaceome.paths import DATA_EXTERNAL_DIR

    return DATA_EXTERNAL_DIR / "tool_cache.sqlite"


def open_default_client() -> CachedHTTP:
    """Construct a CachedHTTP wired to the default cache path and limiter.

    Convenience for one-off scripts and the orchestrator. Long-lived processes
    (e.g. batch annotation) should construct their own and pass it explicitly.
    """

    from .ratelimit import default_limiter

    cache = Cache(default_cache_path())
    return CachedHTTP(cache, default_limiter())
