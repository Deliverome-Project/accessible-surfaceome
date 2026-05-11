"""Smoke-test the Cloudflare D1 client without hitting the network.

Tests that:
- D1Config.from_env raises a clear error when vars are missing.
- The envelope unwrapping handles the actual Cloudflare response shape.
- A failure body raises D1Error.
"""

from __future__ import annotations


import httpx
import pytest

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config, D1Error


def test_d1config_raises_with_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    with pytest.raises(D1Error, match="Missing D1 environment variables"):
        D1Config.from_env()


def test_d1config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "db")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    cfg = D1Config.from_env()
    assert cfg.account_id == "acct"
    assert cfg.database_id == "db"
    assert cfg.api_token == "tok"


def _mock_transport(responses: list[dict]) -> httpx.MockTransport:
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=queue.pop(0))

    return httpx.MockTransport(handler)


def _make_client(transport: httpx.MockTransport) -> D1Client:
    cfg = D1Config(account_id="acct", database_id="db", api_token="tok")
    client = D1Client(cfg)
    client._client.close()
    client._client = httpx.Client(transport=transport, headers=client._headers)
    return client


def test_query_unwraps_results() -> None:
    transport = _mock_transport([
        {
            "success": True,
            "result": [{"results": [{"a": 1}, {"a": 2}], "success": True}],
            "errors": [],
            "messages": [],
        }
    ])
    with _make_client(transport) as client:
        rows = client.query("SELECT a FROM t;")
    assert rows == [{"a": 1}, {"a": 2}]


def test_query_raises_on_failure() -> None:
    transport = _mock_transport([
        {
            "success": False,
            "result": None,
            "errors": [{"code": 7500, "message": "syntax error"}],
            "messages": [],
        }
    ])
    with _make_client(transport) as client:
        with pytest.raises(D1Error, match="syntax error"):
            client.query("BROKEN SQL;")


def test_batch_executes_multiple() -> None:
    transport = _mock_transport([
        {
            "success": True,
            "result": [
                {"success": True, "results": []},
                {"success": True, "results": [{"id": 1}]},
            ],
            "errors": [],
            "messages": [],
        }
    ])
    with _make_client(transport) as client:
        results = client.batch([
            ("INSERT INTO t VALUES (?);", [1]),
            ("SELECT id FROM t;", []),
        ])
    assert results == [[], [{"id": 1}]]
