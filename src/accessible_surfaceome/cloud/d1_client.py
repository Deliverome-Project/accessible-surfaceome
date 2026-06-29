"""Minimal Cloudflare D1 HTTP client.

D1 exposes a REST endpoint at::

    POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query

Body is JSON: ``{"sql": "INSERT ...", "params": [...]}``. Supports parameter
binding via ``?`` placeholders, batch execution via ``raw=true``, and
multi-statement scripts.

We use only ``query`` for both reads and writes — that's the only endpoint
that returns rows. Auth is via a bearer API token scoped to D1:Edit on the
target account.

Every request retries transient failures (HTTP 429 / 5xx and transport-level
errors such as connection resets and read timeouts) with bounded exponential
backoff + jitter — see :data:`RETRYABLE_STATUS` and ``_post_with_retry``. This
matters at cohort scale: a multi-day sweep issues hundreds of thousands of D1
calls across many concurrent workers, so transient blips are statistically
inevitable, and an un-retried drop silently loses a row (a missing private
parent → re-spend on resume, or a missing public ``surface_annotation`` row →
viewer drift). Permanent errors (bad SQL, auth, validation) are *not* retried —
those are signals about the request itself, not transient conditions.

Caveat — writes are retried at-least-once. A 5xx/timeout almost always means the
statement was not applied, but a response lost *after* a successful commit would
be retried, double-applying a *non-idempotent* ``INSERT``. The deep-dive sink's
writes are all idempotent on their natural keys (parent: ``ON CONFLICT (run_id,
gene_symbol) DO NOTHING``; evidence / search-log children:
``INSERT ... WHERE NOT EXISTS`` in ``deep_dive_upload.py``), so a retry can't
duplicate a row there. **Any new high-volume write path must do the same** — a
plain ``INSERT ... VALUES`` on this retrying client is an at-least-once
duplicate hazard. (``cloud/triage_upload.py`` predates this client-level retry
and still uses plain child inserts; lower-risk because the triage sweep runs
separately, but worth the same treatment before it next scales.)

Env vars consumed (loaded by :mod:`accessible_surfaceome.env`):

  * ``CLOUDFLARE_ACCOUNT_ID``      — 32-char hex from the dashboard URL
  * ``CLOUDFLARE_D1_SURFACEOME_AGENTS_ID``     — UUID of the surfaceome_agents D1 database
  * ``CLOUDFLARE_API_TOKEN``        — bearer token with D1:Edit permission
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)

API_ROOT = "https://api.cloudflare.com/client/v4"
DEFAULT_TIMEOUT_S = 30.0

# HTTP statuses worth retrying: 429 (rate limited) plus the transient 5xx
# family Cloudflare returns under load / gateway blips. 4xx other than 429
# (400 bad SQL, 401/403 auth, 404) are request-level and never retried.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Bounded retry budget. 4 attempts with jittered exponential backoff
# (multiplier 0.5, cap 20s) gives a worst-case added latency of well under
# a minute before we surface the failure to the caller, while the random
# jitter keeps many concurrent workers from retrying in lockstep (a
# thundering herd against the same just-overloaded endpoint).
DEFAULT_MAX_ATTEMPTS = 4
_RETRY_WAIT_MULTIPLIER = 0.5
_RETRY_WAIT_MAX_S = 20.0


class D1Error(RuntimeError):
    """Raised on any non-success response from the D1 HTTP API."""


class _TransientD1Error(D1Error):
    """A retryable D1 failure (HTTP 429 / 5xx).

    Subclasses :class:`D1Error` so callers that already catch ``D1Error`` keep
    handling the exhausted-retries case unchanged. Raised inside the retry loop
    to trigger a backoff; if retries are exhausted ``reraise=True`` propagates
    this as the final exception.
    """


@dataclass(frozen=True)
class D1Config:
    account_id: str
    database_id: str
    api_token: str

    @classmethod
    def from_env(cls) -> D1Config:
        """Config for the PRIVATE ``surfaceome_agents`` DB — the write target
        (run recording, gene_identifier, etc.). Default for back-compat."""
        return cls._from_env_db("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID")

    @classmethod
    def from_env_public(cls) -> D1Config:
        """Config for the read-only ``surfaceome_public`` mirror — the
        column-whitelisted subset the Worker + viewer serve. Use for
        analysis / read queries so they can't touch the private DB.

        Note: the public mirror does NOT carry private-only columns
        (e.g. ``triage_run.error`` / ``raw_text`` / ``verdict_reasoning``);
        reach for the private DB only when you genuinely need those."""
        return cls._from_env_db("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID")

    @classmethod
    def _from_env_db(cls, db_var: str) -> D1Config:
        missing: list[str] = []
        account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        db = os.environ.get(db_var, "").strip()
        token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
        if not account:
            missing.append("CLOUDFLARE_ACCOUNT_ID")
        if not db:
            missing.append(db_var)
        if not token:
            missing.append("CLOUDFLARE_API_TOKEN")
        if missing:
            raise D1Error(
                "Missing D1 environment variables: " + ", ".join(missing) +
                ". See cloudflare/README.md for the provisioning walkthrough."
            )
        return cls(account_id=account, database_id=db, api_token=token)


class D1Client:
    """Thin wrapper over the D1 query endpoint with httpx.

    Use ``query`` for ad-hoc reads / writes (one statement per call), or
    ``batch`` for an atomic transaction of multiple parameterized statements.
    """

    def __init__(
        self,
        config: D1Config | None = None,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ):
        self.config = config or D1Config.from_env()
        self._url = (
            f"{API_ROOT}/accounts/{self.config.account_id}/d1/database/"
            f"{self.config.database_id}/query"
        )
        self._headers = {
            "Authorization": f"Bearer {self.config.api_token}",
            "Content-Type": "application/json",
        }
        # max_attempts=1 disables retry (used by tests to avoid backoff sleeps).
        self._max_attempts = max(1, int(max_attempts))
        self._client = httpx.Client(timeout=timeout_s, headers=self._headers)

    @classmethod
    def public(cls, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> D1Client:
        """Read-only client targeting the PUBLIC ``surfaceome_public`` mirror.

        Prefer this for analysis / read queries — it can't reach the private
        ``surfaceome_agents`` DB. Writers (run recording, gene_identifier,
        publish) must keep using the default ``D1Client()`` (private) or an
        explicit private config; this helper is reads only by convention
        (the public DB is a read-only mirror)."""
        return cls(D1Config.from_env_public(), timeout_s=timeout_s)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> D1Client:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    # -- core operations ----------------------------------------------------

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Execute one SQL statement. Returns the result rows (empty for writes).

        Transient transport errors and HTTP 429 / 5xx are retried with bounded
        backoff (see the module docstring); permanent errors (bad SQL, auth) and
        ``success: false`` envelopes propagate immediately as :class:`D1Error`.
        """
        payload: dict[str, Any] = {"sql": sql}
        if params:
            payload["params"] = list(params)
        resp = self._post_with_retry(json.dumps(payload), sql)
        return _unwrap(resp)

    def _post_with_retry(self, content: str, sql: str) -> httpx.Response:
        """POST the query body, retrying transient failures.

        The retry decorator is built per-call so each call gets a fresh retry
        state (accurate per-attempt logging) and so ``self._max_attempts`` is
        honored even when it's changed after construction.
        """

        @retry(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_random_exponential(
                multiplier=_RETRY_WAIT_MULTIPLIER, max=_RETRY_WAIT_MAX_S
            ),
            retry=retry_if_exception_type((_TransientD1Error, httpx.TransportError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def _do() -> httpx.Response:
            resp = self._client.post(self._url, content=content)
            if resp.status_code in RETRYABLE_STATUS:
                raise _TransientD1Error(
                    f"D1 HTTP {resp.status_code} (retryable) for "
                    f"sql={sql[:80]!r}: {resp.text[:200]!r}"
                )
            return resp

        return _do()

    def batch(self, statements: list[tuple[str, list[Any]]]) -> list[list[dict[str, Any]]]:
        """Execute several statements sequentially via the single-statement
        ``/query`` endpoint.

        Originally this method sent the whole list as a top-level JSON array
        to a single ``/query`` POST, but the D1 HTTP API tightened its input
        validation and now rejects the array shape with
        ``"Expected object, received array"``. Cloudflare's Workers binding
        still exposes a real ``.batch()`` op but the public HTTP API only
        accepts one ``{sql, params}`` object per request.

        We keep the ``batch`` signature for callers (so callers don't have to
        manage their own loop and unwrap) but unroll into N sequential
        ``query`` calls. Same atomicity story as before — *not* atomic across
        statements — and the only meaningful difference is latency (N
        round-trips instead of 1). The fastpath for atomic multi-statement
        execution is a single semicolon-joined ``sql`` via :meth:`query`.
        """
        if not statements:
            return []
        return [[*self.query(sql, list(params))] for sql, params in statements]


# ---------------------------------------------------------------------------
# response unwrapping
# ---------------------------------------------------------------------------


def _unwrap(resp: httpx.Response) -> list[dict[str, Any]]:
    """For single-statement query: returns the first result's rows."""
    results = _unwrap_envelope(resp)
    if not results:
        return []
    return _unwrap_one(results[0])


def _unwrap_one(result: dict[str, Any]) -> list[dict[str, Any]]:
    if not result.get("success", True):
        raise D1Error(f"D1 statement failed: {result!r}")
    return list(result.get("results") or [])


def _unwrap_envelope(resp: httpx.Response) -> list[dict[str, Any]]:
    """Parse the standard Cloudflare API envelope, raising on errors."""
    try:
        body = resp.json()
    except json.JSONDecodeError as exc:
        raise D1Error(
            f"D1 returned non-JSON ({resp.status_code}): {resp.text[:300]!r}"
        ) from exc
    if not body.get("success", False):
        errors = body.get("errors") or []
        msg = "; ".join(str(e) for e in errors) or f"HTTP {resp.status_code}"
        raise D1Error(f"D1 API error: {msg}  body={body!r}")
    result = body.get("result")
    if result is None:
        return []
    if isinstance(result, dict):  # single-statement convenience shape
        return [result]
    return list(result)
