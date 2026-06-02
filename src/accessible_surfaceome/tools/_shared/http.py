"""Cached, rate-limited HTTP client used by every custom tool.

Thin wrapper around ``httpx.Client`` that integrates the SQLite cache and the
per-host rate limiter. Returns response *bodies* (text/JSON) rather than
``Response`` objects so cache hits and live fetches go through the same path
without needing to reconstruct a synthetic Response.
"""

from __future__ import annotations

import json as _json
import os
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from .cache import Cache, cache_key
from .ratelimit import RateLimiter

USER_AGENT = "accessible-surfaceome/0.1 (research; https://github.com/Deliverome-Project)"
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)
# PDFs are larger and served by slower publisher hosts than the JSON/XML APIs,
# so the binary path (``get_bytes``) gets a longer read budget than DEFAULT_TIMEOUT.
PDF_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class CachedHTTP:
    """Stateful HTTP client. Keep one instance per process; close on exit."""

    def __init__(
        self,
        cache: Cache,
        limiter: RateLimiter,
        *,
        max_retries: int = 3,
        blob_dir: Path | None = None,
    ):
        self._client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._cache = cache
        self._limiter = limiter
        self._max_retries = max_retries
        # On-disk cache for binary bodies (PDFs). Resolved lazily so tests can
        # inject a tmp dir and non-PDF callers never touch the filesystem.
        self._blob_dir_path = blob_dir

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

    def get_bytes(
        self,
        url: str,
        *,
        source: str,
        ttl_days: int,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | float | None = None,
        max_bytes: int | None = None,
    ) -> bytes:
        """Fetch a binary body (e.g. a publisher PDF) with on-disk caching.

        Unlike ``get_text``/``get_json``, binary payloads are cached as files
        under ``blob_dir/<source>/<key>.bin`` rather than the SQLite text cache
        (which only holds text). TTL is enforced by file mtime. The body is
        streamed (not buffered whole) so ``max_bytes`` aborts an oversized or
        adversarial download — both via the ``Content-Length`` header when
        present and by capping the accumulated chunks — before it can exhaust
        memory. Returns the raw bytes; the caller validates content (e.g. a
        ``%PDF`` magic-byte check), since a 200 can still be an HTML paywall.
        """

        canonical_url = url
        if params:
            qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            canonical_url = f"{url}?{qs}"
        key = cache_key("GET", canonical_url)
        blob_path = self._blob_dir() / source / f"{key}.bin"
        if blob_path.is_file():
            age_s = time.time() - blob_path.stat().st_mtime
            if age_s <= ttl_days * 86_400:
                return blob_path.read_bytes()

        content = self._stream_with_retries(
            url,
            params=params,
            headers=headers,
            timeout=timeout or PDF_TIMEOUT,
            max_bytes=max_bytes,
        )
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a unique temp sibling then atomically replace: a crashed
        # fetch never leaves a truncated blob that reads as a cache hit, and
        # concurrent fetch workers don't collide on a shared temp path.
        tmp = blob_path.with_name(f"{blob_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            tmp.write_bytes(content)
            tmp.replace(blob_path)
        finally:
            tmp.unlink(missing_ok=True)
        return content

    def _stream_with_retries(
        self,
        url: str,
        *,
        params: dict[str, Any] | None,
        headers: dict[str, str] | None,
        timeout: httpx.Timeout | float | None,
        max_bytes: int | None,
    ) -> bytes:
        """Stream a GET with the same limiter/retry policy, capped at max_bytes.

        Separate from ``_send_with_retries`` (which buffers + returns the
        response for the text path) because the binary path must stream to
        enforce the size cap without first loading the whole body into memory.
        """

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            self._limiter.wait(url)
            try:
                with self._client.stream(
                    "GET", url, params=params, headers=headers, timeout=timeout
                ) as resp:
                    if resp.status_code in RETRYABLE_STATUS and attempt < self._max_retries:
                        time.sleep(min(2**attempt, 8))
                        continue
                    resp.raise_for_status()
                    if max_bytes is not None:
                        cl = resp.headers.get("content-length")
                        if cl is not None and cl.isdigit() and int(cl) > max_bytes:
                            raise ValueError(
                                f"content-length {cl} exceeds max_bytes {max_bytes}"
                            )
                    buf = bytearray()
                    for chunk in resp.iter_bytes():
                        buf += chunk
                        if max_bytes is not None and len(buf) > max_bytes:
                            raise ValueError(f"download exceeded max_bytes {max_bytes}")
                    return bytes(buf)
            except httpx.RequestError as e:
                last_exc = e
                if attempt == self._max_retries:
                    raise
                time.sleep(min(2**attempt, 8))

        assert last_exc is not None  # unreachable: loop exits via return or raise
        raise last_exc

    def _blob_dir(self) -> Path:
        if self._blob_dir_path is None:
            from accessible_surfaceome.paths import DATA_EXTERNAL_DIR

            self._blob_dir_path = DATA_EXTERNAL_DIR / "blob_cache"
        return self._blob_dir_path

    def _send_with_retries(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | float | None = None,
    ) -> httpx.Response:
        """Issue one request with rate-limit gating + retry on transient errors.

        Returns the ``raise_for_status``'d response. Shared by the text path
        (``_fetch``) and the binary path (``get_bytes``) so retry/limiter policy
        lives in one place. When ``timeout`` is ``None`` the kwarg is omitted so
        the httpx client default applies — passing ``timeout=None`` to httpx
        would *disable* the timeout instead.
        """

        extra: dict[str, Any] = {} if timeout is None else {"timeout": timeout}
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            self._limiter.wait(url)
            try:
                if method == "GET":
                    resp = self._client.get(url, params=params, headers=headers, **extra)
                elif method == "POST":
                    resp = self._client.post(url, json=json_body, headers=headers, **extra)
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
            return resp

        assert last_exc is not None  # unreachable: loop exits via return or raise
        raise last_exc

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

        resp = self._send_with_retries(
            method, url, params=params, json_body=json_body, headers=headers
        )
        text = resp.text
        self._cache.put(source, key, text)
        return text


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
