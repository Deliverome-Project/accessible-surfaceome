"""Unit tests for the exponential-backoff wrapper around messages.create.

Verifies the contract documented in ``api_retry.messages_create_with_backoff``:

* Transient ``RateLimitError`` (HTTP 429) is retried until success or
  the per-call attempt cap is reached.
* 5xx ``APIStatusError`` is retried (gateway / internal / overloaded).
* 4xx ``APIStatusError`` is NOT retried — those are about the request
  itself, not transient errors. Retrying just burns budget.
* The exception is re-raised after the attempt cap with the original
  type preserved (the orchestrator records it as a gene-level failure).

We patch ``time.sleep`` so tests don't actually wait the exponential
backoff intervals; only the retry-decision logic matters.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest

from accessible_surfaceome.agents._support.api_retry import (
    messages_create_with_backoff,
)


def _make_response(status: int) -> httpx.Response:
    """Synthetic httpx.Response for ``APIStatusError(response=...)``.

    ``APIStatusError`` requires a non-None ``response`` because it
    pulls ``status_code`` off it (and our retry predicate reads the
    same attribute). ``request`` is supplied because httpx requires
    it on a manually-constructed Response.
    """
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx.Response(status_code=status, request=req)


def _rate_limit_error() -> anthropic.RateLimitError:
    """Build a RateLimitError shaped like what the SDK raises."""
    resp = _make_response(429)
    return anthropic.RateLimitError(
        message="Rate limit exceeded",
        response=resp,
        body=None,
    )


def _internal_server_error() -> anthropic.InternalServerError:
    """5xx — should be retried."""
    resp = _make_response(500)
    return anthropic.InternalServerError(
        message="Internal server error",
        response=resp,
        body=None,
    )


def _bad_request_error() -> anthropic.BadRequestError:
    """4xx that ISN'T 429 — must NOT be retried."""
    resp = _make_response(400)
    return anthropic.BadRequestError(
        message="Bad request",
        response=resp,
        body=None,
    )


def _fake_message_response() -> Any:
    """Minimal stand-in for an anthropic Message. The retry helper only
    cares that the call returns *something* — we don't assert against
    the shape, just that the right value propagates back."""
    mock = MagicMock()
    mock.usage = MagicMock(
        input_tokens=42,
        output_tokens=10,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    return mock


@pytest.fixture(autouse=True)
def _no_sleep() -> Any:
    """Make tenacity's wait_exponential() instantaneous so tests don't
    actually sleep 2-32s during retries. tenacity calls ``time.sleep``
    inside its retry loop; patching it module-wide is the simplest
    way to keep the tests fast."""
    with patch("tenacity.nap.time.sleep") as patched:
        yield patched


def test_succeeds_on_first_call_without_retry() -> None:
    """Happy path: a successful response returns immediately, no retry."""
    client = MagicMock()
    expected = _fake_message_response()
    client.messages.create.return_value = expected

    result = messages_create_with_backoff(
        client, model="claude-haiku-4-5", max_tokens=100, messages=[]
    )

    assert result is expected
    assert client.messages.create.call_count == 1


def test_retries_on_429_then_succeeds() -> None:
    """A transient 429 followed by success: the helper transparently
    retries and returns the eventual success without surfacing the
    intermediate error."""
    client = MagicMock()
    expected = _fake_message_response()
    client.messages.create.side_effect = [_rate_limit_error(), expected]

    result = messages_create_with_backoff(
        client, model="claude-haiku-4-5", max_tokens=100, messages=[]
    )

    assert result is expected
    assert client.messages.create.call_count == 2


def test_retries_on_500_then_succeeds() -> None:
    """A 5xx status error should be retried like a 429.

    Anthropic surfaces ``InternalServerError`` as the typical
    ``APIStatusError`` subclass for 5xx. The retry predicate reads
    ``status_code`` off the exception, which it inherits from
    ``APIStatusError``.
    """
    client = MagicMock()
    expected = _fake_message_response()
    client.messages.create.side_effect = [_internal_server_error(), expected]

    result = messages_create_with_backoff(
        client, model="claude-sonnet-4-6", max_tokens=100, messages=[]
    )

    assert result is expected
    assert client.messages.create.call_count == 2


def test_does_not_retry_on_4xx_other_than_429() -> None:
    """A 400 BadRequest must NOT be retried — the request itself is
    wrong (auth / schema / over-size). Retrying it burns API budget
    without changing the outcome.

    The original exception must propagate so the caller (orchestrator
    or builder repair-loop) sees the exact failure mode.
    """
    client = MagicMock()
    err = _bad_request_error()
    client.messages.create.side_effect = err

    with pytest.raises(anthropic.BadRequestError):
        messages_create_with_backoff(
            client, model="claude-haiku-4-5", max_tokens=100, messages=[]
        )

    assert client.messages.create.call_count == 1


def test_gives_up_after_max_attempts() -> None:
    """When the API stays unhealthy through the full retry budget,
    the helper gives up and re-raises the LAST exception with the
    original type. The orchestrator's per-gene error handler then
    records the gene as a transport failure rather than aborting
    the cohort run."""
    client = MagicMock()
    # 5 attempts (the documented cap) — all fail with 429.
    client.messages.create.side_effect = [_rate_limit_error()] * 5

    with pytest.raises(anthropic.RateLimitError):
        messages_create_with_backoff(
            client, model="claude-haiku-4-5", max_tokens=100, messages=[]
        )

    assert client.messages.create.call_count == 5


def test_kwargs_passthrough_to_create() -> None:
    """The wrapper is a thin pass-through: every kwarg lands on
    ``client.messages.create`` verbatim. Regressions here would silently
    drop ``system=`` (cache control), ``tools=`` (web search), or
    ``max_tokens=`` overrides."""
    client = MagicMock()
    expected = _fake_message_response()
    client.messages.create.return_value = expected

    system = [{"type": "text", "text": "sys"}]
    tools = [{"type": "web_search_20250305", "name": "web_search"}]
    messages = [{"role": "user", "content": "hi"}]

    messages_create_with_backoff(
        client,
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system,
        tools=tools,
        messages=messages,
    )

    args, kwargs = client.messages.create.call_args
    assert args == ()
    assert kwargs["model"] == "claude-sonnet-4-6"
    assert kwargs["max_tokens"] == 4096
    assert kwargs["system"] is system
    assert kwargs["tools"] is tools
    assert kwargs["messages"] is messages


def test_mixed_500_then_429_then_success() -> None:
    """Realistic shape: a 5xx, then a 429, then success. The wrapper
    must treat both as retryable and converge."""
    client = MagicMock()
    expected = _fake_message_response()
    client.messages.create.side_effect = [
        _internal_server_error(),
        _rate_limit_error(),
        expected,
    ]

    result = messages_create_with_backoff(
        client, model="claude-haiku-4-5", max_tokens=100, messages=[]
    )

    assert result is expected
    assert client.messages.create.call_count == 3
