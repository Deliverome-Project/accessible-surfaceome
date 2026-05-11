"""Minimal Cloudflare D1 HTTP client.

D1 exposes a REST endpoint at::

    POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query

Body is JSON: ``{"sql": "INSERT ...", "params": [...]}``. Supports parameter
binding via ``?`` placeholders, batch execution via ``raw=true``, and
multi-statement scripts.

We use only ``query`` for both reads and writes — that's the only endpoint
that returns rows. Auth is via a bearer API token scoped to D1:Edit on the
target account.

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

logger = logging.getLogger(__name__)

API_ROOT = "https://api.cloudflare.com/client/v4"
DEFAULT_TIMEOUT_S = 30.0


class D1Error(RuntimeError):
    """Raised on any non-success response from the D1 HTTP API."""


@dataclass(frozen=True)
class D1Config:
    account_id: str
    database_id: str
    api_token: str

    @classmethod
    def from_env(cls) -> D1Config:
        missing: list[str] = []
        account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "").strip()
        token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
        if not account:
            missing.append("CLOUDFLARE_ACCOUNT_ID")
        if not db:
            missing.append("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID")
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

    def __init__(self, config: D1Config | None = None, *, timeout_s: float = DEFAULT_TIMEOUT_S):
        self.config = config or D1Config.from_env()
        self._url = (
            f"{API_ROOT}/accounts/{self.config.account_id}/d1/database/"
            f"{self.config.database_id}/query"
        )
        self._headers = {
            "Authorization": f"Bearer {self.config.api_token}",
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(timeout=timeout_s, headers=self._headers)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> D1Client:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    # -- core operations ----------------------------------------------------

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Execute one SQL statement. Returns the result rows (empty for writes)."""
        payload: dict[str, Any] = {"sql": sql}
        if params:
            payload["params"] = list(params)
        resp = self._client.post(self._url, content=json.dumps(payload))
        return _unwrap(resp)

    def batch(self, statements: list[tuple[str, list[Any]]]) -> list[list[dict[str, Any]]]:
        """Execute several statements in one round-trip.

        Cloudflare's D1 query endpoint accepts a JSON array of {sql, params}
        objects when invoked with ``raw=false`` (the default). Each statement
        executes in its own implicit transaction; this is *not* atomic across
        the batch — for atomicity use a single multi-statement ``sql`` with
        ``BEGIN/COMMIT``.
        """
        if not statements:
            return []
        payload = [
            {"sql": sql, "params": list(params)} for sql, params in statements
        ]
        resp = self._client.post(self._url, content=json.dumps(payload))
        return [_unwrap_one(r) for r in _unwrap_envelope(resp)]


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
