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


def _status_transport(statuses: list[int | dict]) -> tuple[httpx.MockTransport, list[int]]:
    """Transport that replays a fixed sequence of responses.

    Each entry is either an int (return that HTTP status with a tiny body) or a
    dict (return HTTP 200 with that JSON envelope). Returns the transport plus a
    one-element call-counter list the test can assert on.
    """
    queue: list[int | dict] = list(statuses)
    calls = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        item = queue.pop(0)
        if isinstance(item, int):
            return httpx.Response(item, text="upstream error")
        return httpx.Response(200, json=item)

    return httpx.MockTransport(handler), calls


def _ok_envelope() -> dict:
    return {
        "success": True,
        "result": [{"results": [{"a": 1}], "success": True}],
        "errors": [],
        "messages": [],
    }


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip tenacity's real backoff sleeps so retry tests run instantly."""
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _s: None)


def test_query_retries_transient_5xx_then_succeeds() -> None:
    transport, calls = _status_transport([503, 503, _ok_envelope()])
    with _make_client(transport) as client:
        rows = client.query("SELECT a FROM t;")
    assert rows == [{"a": 1}]
    assert calls[0] == 3  # two retries, then success


def test_query_retries_429() -> None:
    transport, calls = _status_transport([429, _ok_envelope()])
    with _make_client(transport) as client:
        rows = client.query("SELECT a FROM t;")
    assert rows == [{"a": 1}]
    assert calls[0] == 2


def test_query_gives_up_after_max_attempts() -> None:
    transport, calls = _status_transport([503, 503, 503, 503, 503])
    with _make_client(transport) as client:
        with pytest.raises(D1Error, match="retryable"):
            client.query("SELECT a FROM t;")
    assert calls[0] == 4  # DEFAULT_MAX_ATTEMPTS


def test_query_does_not_retry_4xx() -> None:
    # A 400 (bad SQL) is a request-level error — surface it without retrying.
    transport, calls = _status_transport([400])
    with _make_client(transport) as client:
        with pytest.raises(D1Error):
            client.query("BROKEN SQL;")
    assert calls[0] == 1


def test_query_retries_transport_error_then_succeeds() -> None:
    calls = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        if calls[0] == 1:
            raise httpx.ConnectError("connection reset", request=request)
        return httpx.Response(200, json=_ok_envelope())

    with _make_client(httpx.MockTransport(handler)) as client:
        rows = client.query("SELECT a FROM t;")
    assert rows == [{"a": 1}]
    assert calls[0] == 2


def test_max_attempts_one_disables_retry() -> None:
    transport, calls = _status_transport([503, _ok_envelope()])
    cfg = D1Config(account_id="acct", database_id="db", api_token="tok")
    client = D1Client(cfg, max_attempts=1)
    client._client.close()
    client._client = httpx.Client(transport=transport, headers=client._headers)
    with client:
        with pytest.raises(D1Error):
            client.query("SELECT a FROM t;")
    assert calls[0] == 1


def test_batch_executes_multiple() -> None:
    # `D1Client.batch` was reshaped (see its docstring) to unroll into
    # N sequential `query` POSTs after Cloudflare's HTTP API tightened
    # `/query` to reject top-level arrays. Each statement now expects
    # its own response envelope; the test mock queues one response per
    # statement.
    transport = _mock_transport([
        {
            "success": True,
            "result": [{"success": True, "results": []}],
            "errors": [],
            "messages": [],
        },
        {
            "success": True,
            "result": [{"success": True, "results": [{"id": 1}]}],
            "errors": [],
            "messages": [],
        },
    ])
    with _make_client(transport) as client:
        results = client.batch([
            ("INSERT INTO t VALUES (?);", [1]),
            ("SELECT id FROM t;", []),
        ])
    assert results == [[], [{"id": 1}]]
