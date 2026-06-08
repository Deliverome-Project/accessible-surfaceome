"""Cloudflare R2 client — REST API path with the existing API token.

R2 supports two auth paths:
1. S3-compatible API + R2 access keys (`CLOUDFLARE_R2_ACCESS_KEY_ID` +
   `_SECRET_ACCESS_KEY`) — requires provisioning new keys.
2. **Cloudflare REST API + the existing ``CLOUDFLARE_API_TOKEN``** —
   the same token that already works for D1 and Workers. Token must
   have the **R2:Edit** scope (which the deliverome account token
   already does — used by ``.github/workflows/d1-backup.yml`` for the
   D1→R2 backup pipeline).

This module uses path (2) so genome-wide intermediates spillover
doesn't need a new secret. One PUT per object via httpx; no boto3
session, no signed-URL plumbing.

Why we want R2 for intermediates: the D1 ``agent_run_intermediates``
row caps at ~900KB. Genome-wide there are heavy-lit genes (TGOLN2 at
99.7% of limit; many will exceed). The slim-fallback in
:mod:`intermediates` drops the bulky audit fields (search_log +
triage_actions) when the blob doesn't fit; R2 catches that overflow
so the forensic audit isn't lost.

Layout convention (matches the existing R2 backup taxonomy):
    {bucket}/agent_run_intermediates/{gene}/{schema}/{prompt_corpus}/{created_at}.json

A pointer key gets stored in the D1 row so a future audit query can
follow ``r2://{bucket}/{key}`` to the full blob.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


_R2_API_BASE = "https://api.cloudflare.com/client/v4"
_DEFAULT_BUCKET = "deliverome-d1-backups"
_R2_OBJECT_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class R2Config:
    """R2 connection config — pulled from the same env vars as D1."""

    account_id: str
    api_token: str
    bucket: str

    @classmethod
    def from_env(
        cls,
        bucket: str = _DEFAULT_BUCKET,
    ) -> R2Config:
        """Build from env. Raises when required keys are missing.

        Same auth surface as :class:`D1Config`: the API token doubles
        for D1 and R2 when scoped with both edit permissions, which is
        the deliverome convention.
        """
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
        missing = [
            name
            for name, val in (
                ("CLOUDFLARE_ACCOUNT_ID", account_id),
                ("CLOUDFLARE_API_TOKEN", api_token),
            )
            if not val
        ]
        if missing:
            raise RuntimeError(
                f"R2 config missing env vars: {missing}. Set the Cloudflare "
                "API token with R2:Edit scope (the same token already used "
                "for D1) plus the account ID."
            )
        # Bucket name override via env (rare; CI uses default).
        bucket = os.environ.get("CLOUDFLARE_R2_BUCKET") or bucket
        # Type checker: missing values above raised; api_token / account_id
        # are guaranteed non-None here.
        assert account_id is not None
        assert api_token is not None
        return cls(account_id=account_id, api_token=api_token, bucket=bucket)


def _object_url(cfg: R2Config, key: str) -> str:
    """REST API endpoint for one R2 object."""
    # Cloudflare R2 REST API: PUT/GET/DELETE /accounts/{id}/r2/buckets/{bucket}/objects/{key}
    return (
        f"{_R2_API_BASE}/accounts/{cfg.account_id}"
        f"/r2/buckets/{cfg.bucket}/objects/{key}"
    )


def put_object(
    *,
    key: str,
    body: bytes | str,
    content_type: str = "application/json",
    cfg: R2Config | None = None,
) -> bool:
    """Upload one object to R2. Returns True on success, False on any error.

    Never raises — caller (the intermediates spillover path) treats R2
    as best-effort: if it fails, the slim D1 row still publishes and
    the audit gap is logged. R2 outages should not block annotation.

    The body can be bytes or a string (which gets utf-8 encoded). For
    JSON intermediates, serialize with :func:`json.dumps` first; this
    function doesn't re-encode.
    """
    try:
        cfg = cfg or R2Config.from_env()
    except Exception as exc:  # noqa: BLE001
        logger.debug("R2 put skipped (config unavailable): %s", exc)
        return False

    if isinstance(body, str):
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = body

    url = _object_url(cfg, key)
    headers = {
        "Authorization": f"Bearer {cfg.api_token}",
        "Content-Type": content_type,
    }
    try:
        # Use a one-shot client. Per-call cost is tiny (~3KB header
        # overhead); the alternative (persistent client) wins on
        # latency but complicates lifecycle in the orchestrator's
        # publish path. Keep it simple.
        with httpx.Client(timeout=_R2_OBJECT_TIMEOUT_S) as c:
            resp = c.put(url, headers=headers, content=body_bytes)
        if resp.status_code in (200, 201, 204):
            logger.info(
                "R2 upload OK: %s (%d bytes, bucket=%s)",
                key, len(body_bytes), cfg.bucket,
            )
            return True
        logger.warning(
            "R2 upload failed (HTTP %d): %s. Body: %.200s",
            resp.status_code, key, resp.text,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("R2 upload errored for %s: %s", key, exc)
        return False


def head_object(
    *,
    key: str,
    cfg: R2Config | None = None,
) -> dict[str, Any] | None:
    """HEAD probe for an object. Returns response headers or None on miss.

    Used by analytics + back-fill scripts that want to know "did this
    intermediates spillover land?" without downloading the full blob.
    """
    try:
        cfg = cfg or R2Config.from_env()
    except Exception:  # noqa: BLE001
        return None
    url = _object_url(cfg, key)
    try:
        with httpx.Client(timeout=_R2_OBJECT_TIMEOUT_S) as c:
            resp = c.head(
                url,
                headers={"Authorization": f"Bearer {cfg.api_token}"},
            )
        if resp.status_code == 200:
            return dict(resp.headers)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.debug("R2 head errored for %s: %s", key, exc)
        return None


def intermediates_object_key(
    *,
    gene_symbol: str,
    schema_version: str,
    prompt_corpus_version: str,
    created_at: str,
) -> str:
    """Canonical R2 key for one intermediates spillover blob.

    Layout (mirrors the per-gene-D1-row primary key for predictability):
        agent_run_intermediates/{gene}/{schema}/{prompt_corpus}/{created_at}.json

    ``created_at`` should be an ISO-8601 timestamp; URL-unsafe chars
    (`:`) are tolerated by Cloudflare's REST endpoint.
    """
    return (
        "agent_run_intermediates/"
        f"{gene_symbol}/{schema_version}/{prompt_corpus_version}/"
        f"{created_at}.json"
    )


__all__ = [
    "R2Config",
    "put_object",
    "head_object",
    "intermediates_object_key",
]
