"""Cloudflare R2 via its S3-compatible API — for high-volume object I/O.

The REST-API path in :mod:`accessible_surfaceome.cloud.r2_client` calls
``api.cloudflare.com`` per object (a HEAD-equivalent Range GET *and* a PUT),
which shares the account-wide Cloudflare API budget (1,200 requests / 5 min,
covering every ``api.cloudflare.com`` call — D1 queries included) with
everything else running against the account. A cohort-scale record-history
seed or sweep (thousands of objects) can single-handedly exhaust that
budget and starve concurrent D1 traffic.

R2's S3-compatible endpoint (``{account_id}.r2.cloudflarestorage.com``) is a
**separate** API surface with its own limits, so routing bulk object I/O
through it frees essentially all of the shared Cloudflare API budget for D1
and everything else.

Credential derivation
----------------------
R2's S3 API normally wants dedicated R2 access keys, but Cloudflare
documents a deterministic derivation from an existing API token (so no new
secret has to be provisioned or rotated separately):

* **access key id** — the token's own id, from
  ``GET https://api.cloudflare.com/client/v4/user/tokens/verify``
  (``result.id``).
* **secret access key** — the SHA-256 hex digest of the token *value*
  itself.

Neither value is ever logged. ``R2_ACCESS_KEY_ID`` + ``R2_SECRET_ACCESS_KEY``
(both must be set) override the derivation entirely, for a deployment that
already provisioned dedicated R2 keys.
"""

from __future__ import annotations

import hashlib
import logging
import os
from functools import lru_cache
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TOKEN_VERIFY_URL = "https://api.cloudflare.com/client/v4/user/tokens/verify"
_VERIFY_TIMEOUT_S = 15.0

# botocore retry/pool tuning: adaptive retry mode backs off on both
# throttling and transient errors; a wider connection pool than the
# ~10-connection default matters once callers fan out across a thread pool
# (the seed's R2 uploads run 16-wide).
_MAX_ATTEMPTS = 8
_MAX_POOL_CONNECTIONS = 32


class R2S3CredentialError(RuntimeError):
    """R2 S3-compatible credentials could not be derived or constructed."""


def _verify_token_id(token: str) -> str:
    """The token's own id — the Cloudflare-documented S3 access key id.

    Never includes the token value itself in any exception message or log.
    """
    resp = httpx.get(
        TOKEN_VERIFY_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=_VERIFY_TIMEOUT_S,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        raise R2S3CredentialError(
            "CLOUDFLARE_API_TOKEN verify call did not report success"
        )
    token_id = (body.get("result") or {}).get("id")
    if not token_id:
        raise R2S3CredentialError("token verify response is missing result.id")
    return str(token_id)


def _derive_credentials() -> tuple[str, str]:
    """(access_key_id, secret_access_key) for the R2 S3-compatible API.

    Prefers an explicit ``R2_ACCESS_KEY_ID`` + ``R2_SECRET_ACCESS_KEY``
    override (both must be set); otherwise derives from
    ``CLOUDFLARE_API_TOKEN`` per the module docstring. Values are returned,
    never logged.
    """
    env_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    env_secret = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    if env_key and env_secret:
        return env_key, env_secret

    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not token:
        raise R2S3CredentialError(
            "R2 S3 credentials unavailable: set both R2_ACCESS_KEY_ID and "
            "R2_SECRET_ACCESS_KEY, or CLOUDFLARE_API_TOKEN to derive from"
        )
    access_key_id = _verify_token_id(token)
    secret_access_key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return access_key_id, secret_access_key


@lru_cache(maxsize=1)
def r2_s3_client() -> Any:
    """A cached boto3 S3 client targeting the R2 S3-compatible endpoint.

    Raises :class:`R2S3CredentialError` (missing ``CLOUDFLARE_ACCOUNT_ID``,
    or credential derivation failure) — callers that want a soft-fail
    REST fallback should catch that (and only that; a genuine boto3/network
    problem inside client construction is unexpected and should surface).

    Cached with ``lru_cache`` — call ``r2_s3_client.cache_clear()`` (tests
    do this) to force a fresh client after changing env vars or mocks.
    """
    import boto3
    from botocore.config import Config

    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if not account_id:
        raise R2S3CredentialError("CLOUDFLARE_ACCOUNT_ID is unset")
    access_key_id, secret_access_key = _derive_credentials()
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
        config=Config(
            retries={"max_attempts": _MAX_ATTEMPTS, "mode": "adaptive"},
            max_pool_connections=_MAX_POOL_CONNECTIONS,
        ),
    )


__all__ = ["R2S3CredentialError", "r2_s3_client"]
