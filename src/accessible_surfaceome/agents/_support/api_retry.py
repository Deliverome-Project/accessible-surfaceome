"""Exponential-backoff wrapper around ``client.messages.create``.

At cohort scale (~90,000 ``messages.create`` calls across a 6,500-gene
sweep) transient rate-limits + 5xx are statistically inevitable. The
Anthropic SDK itself retries up to ``max_retries`` (configured in
``_support.client.get_client`` to 5), but the SDK's retry policy is
focused on connection / handshake / TCP-level blips. It does NOT retry
on every shape of rate-limit response the API returns, and an
``anthropic.RateLimitError`` raised after the SDK's own retries are
exhausted is what cohort runs actually see.

``messages_create_with_backoff`` wraps a single ``client.messages.create``
call in a ``tenacity`` retry loop that fires on:

* ``anthropic.RateLimitError`` — HTTP 429.
* ``anthropic.APIStatusError`` with ``status_code >= 500`` — gateway /
  internal / overloaded / etc. We don't retry 4xx (auth, validation,
  schema-too-large) because those are signals about the request itself,
  not transient errors.

Each retry doubles the wait (``wait_exponential(multiplier=2, min=2,
max=60)``); 5 attempts gives an absolute upper bound of
``2 + 4 + 8 + 16 + 32 = 62`` seconds across the worst case before we
give up. That's enough to ride out the typical rate-limit window
without piling latency onto every healthy call.

Other call-site notes:

* Each call site already maintains its own validation-error /
  repair-loop (the v2 ``call_builder`` and the trim ``_call_with_repair``
  helpers retry on schema-validation failures). Those loops do NOT
  catch transport-level errors — that's exactly the gap this helper
  fills. The two loops compose: a transient 429 is retried at the
  transport level by ``messages_create_with_backoff``, and a schema-
  invalid response (which the API never sees as an error) is retried
  at the application level by the existing repair loop.
* The wrapper is intentionally a thin pass-through. It exposes the same
  call shape as ``client.messages.create``; call sites that previously
  read ``client.messages.create(model=..., messages=...)`` swap to
  ``messages_create_with_backoff(client, model=..., messages=...)`` —
  the only change is the helper's first positional arg.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
from anthropic.types.message import Message
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# Hard cap on retry attempts. 5 attempts with the (2, 4, 8, 16, 32)s
# wait sequence gives a worst-case wall-clock of 62s before we give up
# — enough to ride out a typical org-level rate-limit window without
# piling latency onto every healthy call.
_MAX_ATTEMPTS = 5

# Exponential-backoff parameters. ``multiplier=2`` doubles each step;
# ``min=2`` keeps the first wait short enough that a flaky single call
# doesn't dominate end-to-end latency; ``max=60`` caps the per-step
# wait so the final attempt isn't an unbounded sleep.
_WAIT_MULTIPLIER = 2
_WAIT_MIN_S = 2
_WAIT_MAX_S = 60


def _is_retryable_5xx(exc: BaseException) -> bool:
    """True for ``APIStatusError`` with ``status_code >= 500``.

    Anthropic groups gateway, internal, overloaded, etc. under
    ``APIStatusError`` (parent of ``InternalServerError`` and friends).
    A bare ``APIStatusError`` is rare in practice; most 5xx responses
    arrive as the more-specific subclasses but they all carry the
    ``status_code`` attribute.

    We deliberately do NOT retry 4xx (auth, validation, schema
    rejection) — those are signals about the request itself, not
    transient errors. Retrying them just burns API budget without
    changing the outcome.
    """
    if not isinstance(exc, anthropic.APIStatusError):
        return False
    status = getattr(exc, "status_code", None)
    if not isinstance(status, int):
        return False
    return status >= 500


def _log_before_sleep(retry_state: RetryCallState) -> None:
    """Log every retry decision at INFO level.

    Surfaces the attempt count, the next-sleep duration, and the
    underlying error so a cohort run's logs show exactly when and why
    a call was retried. INFO-level (not WARNING) because transient
    rate-limits at cohort scale are routine, not anomalies.
    """
    outcome = retry_state.outcome
    if outcome is None:
        return
    exc = outcome.exception()
    if exc is None:
        return
    next_action = retry_state.next_action
    sleep_for = next_action.sleep if next_action is not None else 0.0
    attempt = retry_state.attempt_number
    exc_name = type(exc).__name__
    exc_msg = str(exc)[:200]
    logger.info(
        "messages.create retry attempt=%d/%d sleeping=%.1fs after %s: %s",
        attempt,
        _MAX_ATTEMPTS,
        sleep_for,
        exc_name,
        exc_msg,
    )


def messages_create_with_backoff(
    client: anthropic.Anthropic,
    **kwargs: Any,
) -> Message:
    """Wrap ``client.messages.create`` in tenacity-driven exponential backoff.

    Retries on ``anthropic.RateLimitError`` and any ``APIStatusError``
    with ``status_code >= 500``. 4xx errors (other than 429) propagate
    immediately — they are not retryable.

    The ``kwargs`` are passed through to ``messages.create`` verbatim;
    this helper is otherwise a thin transparent wrapper.

    Returns the parsed ``Message`` response on success. Raises the
    original exception once ``_MAX_ATTEMPTS`` has been exhausted —
    callers should let that propagate to the orchestrator's per-gene
    error handler, where it'll be recorded as a gene-level failure
    rather than aborting the cohort run.
    """
    # The wrapped callable is built per-call (not module-level) so each
    # call gets a fresh tenacity ``RetryCallState`` — important for
    # the per-attempt logging to be accurate. The decorator pattern
    # creates a closure over the captured client + kwargs.
    @retry(
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=_WAIT_MULTIPLIER,
            min=_WAIT_MIN_S,
            max=_WAIT_MAX_S,
        ),
        retry=(
            retry_if_exception_type(anthropic.RateLimitError)
            | retry_if_exception(_is_retryable_5xx)
        ),
        before_sleep=_log_before_sleep,
        reraise=True,
    )
    def _call() -> Message:
        return client.messages.create(**kwargs)

    return _call()


__all__ = ["messages_create_with_backoff"]
