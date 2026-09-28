"""``cloud/r2_s3.py``: credential derivation, env override, and client caching.

Never makes a real network call — the token-verify HTTP call is driven
through an ``httpx.MockTransport``-backed monkeypatch of ``httpx.get``.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator

import httpx
import pytest

from accessible_surfaceome.cloud import r2_s3
from accessible_surfaceome.cloud.r2_s3 import R2S3CredentialError, r2_s3_client


@pytest.fixture(autouse=True)
def _clear_client_cache() -> Iterator[None]:
    r2_s3_client.cache_clear()
    yield
    r2_s3_client.cache_clear()


def _patch_verify(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def fake_get(url: str, *, headers: dict, timeout: float) -> httpx.Response:
        req = httpx.Request("GET", url, headers=headers)
        seen.append(req)
        resp = handler(req)
        resp.request = req  # raise_for_status() needs this set
        return resp

    monkeypatch.setattr(r2_s3.httpx, "get", fake_get)
    return seen


def test_derive_credentials_from_token(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "cfut_supersecrettoken12345"
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", token)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["Authorization"] == f"Bearer {token}"
        return httpx.Response(200, json={"success": True, "result": {"id": "tok-id-abc"}})

    _patch_verify(monkeypatch, handler)

    access_key_id, secret_access_key = r2_s3._derive_credentials()

    assert access_key_id == "tok-id-abc"
    assert secret_access_key == hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_derive_credentials_verify_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
    _patch_verify(
        monkeypatch, lambda _req: httpx.Response(200, json={"success": False, "errors": []})
    )

    with pytest.raises(R2S3CredentialError):
        r2_s3._derive_credentials()


def test_derive_credentials_missing_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)

    with pytest.raises(R2S3CredentialError):
        r2_s3._derive_credentials()


def test_env_override_skips_token_verify_entirely(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "override-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "override-secret")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")  # must be ignored

    def _boom(*_a: object, **_kw: object) -> None:
        raise AssertionError("token verify must not be called when both env keys are set")

    monkeypatch.setattr(r2_s3.httpx, "get", _boom)

    access_key_id, secret_access_key = r2_s3._derive_credentials()

    assert (access_key_id, secret_access_key) == ("override-key", "override-secret")


def test_env_override_requires_both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "only-key")
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "result": {"id": "tok-id"}})

    _patch_verify(monkeypatch, handler)

    # Falls through to token derivation since only one of the pair is set.
    access_key_id, _secret = r2_s3._derive_credentials()
    assert access_key_id == "tok-id"


def test_nothing_sensitive_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    token = "cfut_do-not-log-me-either"
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", token)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "result": {"id": "tok-id-xyz"}})

    _patch_verify(monkeypatch, handler)

    with caplog.at_level(logging.DEBUG):
        access_key_id, secret_access_key = r2_s3._derive_credentials()

    log_text = caplog.text
    assert token not in log_text
    assert secret_access_key not in log_text
    assert access_key_id not in log_text  # not secret, but no reason to log it either


def test_r2_s3_client_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")

    first = r2_s3_client()
    second = r2_s3_client()

    assert first is second


def test_r2_s3_client_missing_account_id_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "s")

    with pytest.raises(R2S3CredentialError, match="CLOUDFLARE_ACCOUNT_ID"):
        r2_s3_client()


def test_r2_s3_client_uses_account_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")

    client = r2_s3_client()

    assert client.meta.endpoint_url == "https://acct123.r2.cloudflarestorage.com"
    assert client.meta.region_name == "auto"
