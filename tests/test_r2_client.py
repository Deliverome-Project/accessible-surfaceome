"""Unit tests for ``r2_client.head_object`` — the existence probe.

Cloudflare's REST endpoint for an R2 object returns HTTP 405 on a bare
``HEAD`` request (probed 2026-06-08 — see
``docs/audit/r2_and_reproducibility_2026_06_08.md``), so we instead issue a
``Range: bytes=0-15`` GET. These tests pin that wire shape so a future
refactor doesn't silently regress to HEAD.

Driven through an httpx ``MockTransport`` so no network is touched.
"""

from __future__ import annotations


import httpx
import pytest

from accessible_surfaceome.cloud import r2_client
from accessible_surfaceome.cloud.r2_client import R2Config, head_object


def _cfg() -> R2Config:
    return R2Config(account_id="acct", api_token="tok", bucket="buk")


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    handler,
) -> dict[str, httpx.Request]:
    """Patch ``httpx.Client`` inside r2_client with a MockTransport-backed one.

    Returns a dict that captures the last request so tests can assert the
    verb / headers / URL the function actually sent.
    """
    captured: dict[str, httpx.Request] = {}
    real_client = httpx.Client  # capture before patching to avoid recursion

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return handler(request)

    def factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        return real_client(transport=httpx.MockTransport(wrapped))

    monkeypatch.setattr(r2_client.httpx, "Client", factory)
    return captured


def test_head_object_returns_headers_on_206(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            206,
            headers={"Content-Length": "16", "ETag": '"abc"'},
            content=b"0123456789abcdef",
        )

    captured = _patch_client(monkeypatch, handler)
    result = head_object(key="agent_run_intermediates/X.json", cfg=_cfg())
    assert result is not None
    assert result.get("etag") == '"abc"'
    # The fix: GET with a Range header, not HEAD.
    req = captured["request"]
    assert req.method == "GET"
    assert req.headers.get("Range") == "bytes=0-15"
    assert "agent_run_intermediates/X.json" in str(req.url)


def test_head_object_returns_none_on_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    _patch_client(monkeypatch, handler)
    assert head_object(key="missing.json", cfg=_cfg()) is None


def test_head_object_returns_none_on_405_no_regression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If a future refactor regresses to HEAD, Cloudflare will return 405 and
    # the function should still soft-fail (None) rather than raise — but the
    # request method assertion above is the real guard.
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(405, text="method not allowed")

    _patch_client(monkeypatch, handler)
    assert head_object(key="anything.json", cfg=_cfg()) is None
