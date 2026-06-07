"""Push per-run intermediate artifacts to the private ``surfaceome_agents`` D1.

Companion to :mod:`cloud.surface_annotation` (which publishes the final
``SurfaceomeRecord`` to public D1). This module persists the heavier
behind-the-scenes artifacts an annotate run produces:

* the A1/A2 evidence ledgers + search logs from ``plan_trim_select``
* per-builder raw outputs (methods, evidence_grade, expression, etc.)
* pre- and post-postpass risks
* the synthesizer's raw JSON (pre-Pydantic-validation) + validation
  errors + repair-attempt counts

Why D1 and not local disk: the annotate driver runs on Modal in the
production sweep. Local files in ``.runs/`` don't survive container
shutdown, so we'd lose every post-mortem artifact for the
~$2-3/gene runs we just paid for. Writing intermediates to D1 keeps
them queryable forever from any worktree (or the viewer / a notebook)
without depending on a particular Modal worker's disk.

The bytes go into one row of ``agent_run_intermediates`` keyed by
``(gene_symbol, schema_version, prompt_corpus_version, created_at)`` —
preserves every re-run rather than overwriting. Apply the schema once
per fresh D1 via either ``wrangler d1 execute … --file=cloudflare/
d1_schema.sql`` or by calling ``ensure_schema()`` below from a one-off
script. The DDL is idempotent (``CREATE TABLE IF NOT EXISTS``).

Size guard: D1 caps a row at ~1 MB. A heavy gene's intermediates can
breach that on big ledgers + verbose synthesizer raw JSON. We emit a
warning and SKIP the push (rather than failing the whole annotate run)
when the serialized blob exceeds ``_MAX_INTERMEDIATES_BYTES`` — a
follow-up R2 spillover can land later when this surfaces in practice.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome._version_guard import PROMPT_CORPUS_VERSION
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config

logger = logging.getLogger(__name__)


# D1 row size soft limit. Cloudflare documents a hard 1 MB row limit;
# 900 KB leaves headroom for the per-cell + per-column overhead the
# REST layer adds. Blobs above this are skipped with a warning rather
# than crashing the publish path.
_MAX_INTERMEDIATES_BYTES = 900 * 1024


# Idempotent DDL — mirrors the block at the tail of
# ``cloudflare/d1_schema.sql``. Kept here too so ``ensure_schema()`` can
# bring up a fresh private D1 from Python without needing wrangler.
_SCHEMA_SQL = [
    # The intermediates row. PRIMARY KEY includes ``created_at`` so a
    # re-run on the same (gene, schema_version, prompt_corpus_version)
    # appends a new audit row rather than overwriting — preserving the
    # full re-annotation history for post-mortem.
    """
    CREATE TABLE IF NOT EXISTS agent_run_intermediates (
        gene_symbol           TEXT NOT NULL,
        schema_version        TEXT NOT NULL,
        prompt_corpus_version TEXT NOT NULL,
        created_at            TEXT NOT NULL,
        record_valid          INTEGER NOT NULL,
        intermediates_bytes   INTEGER NOT NULL,
        intermediates_json    TEXT NOT NULL,
        PRIMARY KEY (gene_symbol, schema_version, prompt_corpus_version, created_at)
    );
    """,
    # Most common lookup: latest intermediates for a gene.
    """
    CREATE INDEX IF NOT EXISTS idx_agent_run_intermediates_gene
        ON agent_run_intermediates (gene_symbol, created_at DESC);
    """,
    # Cross-cohort sweeps: "all runs in the last N days" /
    # "everything under prompt_corpus 2.7.0".
    """
    CREATE INDEX IF NOT EXISTS idx_agent_run_intermediates_created
        ON agent_run_intermediates (created_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_agent_run_intermediates_prompt_corpus
        ON agent_run_intermediates (prompt_corpus_version, created_at DESC);
    """,
]


@dataclass(frozen=True)
class IntermediatesPushResult:
    """Outcome of one :func:`publish_intermediates` call."""

    gene_symbol: str
    pushed: bool
    skipped_reason: str | None
    intermediates_bytes: int
    created_at: str
    schema_version: str
    prompt_corpus_version: str


def ensure_schema(d1: D1Client | None = None) -> None:
    """Apply the intermediates DDL to the private D1.

    Idempotent — the ``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF
    NOT EXISTS`` statements are safe to call repeatedly. Useful for
    one-off bring-up in a fresh worktree without needing wrangler.
    """
    owns_client = d1 is None
    client = d1 or D1Client()
    try:
        for stmt in _SCHEMA_SQL:
            client.query(stmt.strip(), [])
        logger.info("agent_run_intermediates schema applied")
    finally:
        if owns_client:
            client.close()


def publish_intermediates(
    *,
    gene_symbol: str,
    intermediates: dict[str, Any],
    schema_version: str,
    record_valid: bool,
    push_to_d1: bool = True,
    created_at: str | None = None,
) -> IntermediatesPushResult:
    """Push one run's intermediates to private D1.

    Caller is the annotate driver; one call per annotate run, AFTER the
    canonical record publish (so a publish failure on the record side
    doesn't lose the diagnostic blob — pushing intermediates is its own
    network round-trip).

    ``record_valid`` reflects whether the annotate run produced a
    schema-validating ``SurfaceomeRecord``. Failed runs are still
    preserved here — that's the whole point of the audit trail.

    Returns an :class:`IntermediatesPushResult` with the bytes pushed
    and any skip reason. The function NEVER raises on a D1 / credentials
    miss; misses log + return a skipped result so the annotate driver
    can continue.
    """
    blob = json.dumps(intermediates, separators=(",", ":"))
    n_bytes = len(blob.encode("utf-8"))
    stamp = created_at or datetime.now(UTC).isoformat()

    if n_bytes > _MAX_INTERMEDIATES_BYTES:
        logger.warning(
            "intermediates for %s exceed D1 row soft-limit "
            "(%d bytes > %d). Skipping push — file a follow-up to "
            "spill these to R2 with a D1 pointer.",
            gene_symbol,
            n_bytes,
            _MAX_INTERMEDIATES_BYTES,
        )
        return IntermediatesPushResult(
            gene_symbol=gene_symbol,
            pushed=False,
            skipped_reason=f"size {n_bytes} > limit {_MAX_INTERMEDIATES_BYTES}",
            intermediates_bytes=n_bytes,
            created_at=stamp,
            schema_version=schema_version,
            prompt_corpus_version=PROMPT_CORPUS_VERSION,
        )

    if not push_to_d1:
        return IntermediatesPushResult(
            gene_symbol=gene_symbol,
            pushed=False,
            skipped_reason="push_to_d1=False",
            intermediates_bytes=n_bytes,
            created_at=stamp,
            schema_version=schema_version,
            prompt_corpus_version=PROMPT_CORPUS_VERSION,
        )

    # Use the private surfaceome_agents D1 — same credentials path the
    # triage runner uses. Missing CLOUDFLARE_* env (typical for CI / a
    # fresh-clone smoke build) → skip with a warning, never raise.
    try:
        cfg = D1Config.from_env()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "intermediates push for %s skipped: private D1 config "
            "unavailable (%s). Set CLOUDFLARE_ACCOUNT_ID + "
            "CLOUDFLARE_D1_SURFACEOME_AGENTS_ID + "
            "CLOUDFLARE_API_TOKEN to enable.",
            gene_symbol,
            exc,
        )
        return IntermediatesPushResult(
            gene_symbol=gene_symbol,
            pushed=False,
            skipped_reason=f"D1 config missing: {exc}",
            intermediates_bytes=n_bytes,
            created_at=stamp,
            schema_version=schema_version,
            prompt_corpus_version=PROMPT_CORPUS_VERSION,
        )

    try:
        with D1Client(cfg, timeout_s=60.0) as client:
            client.query(
                "INSERT INTO agent_run_intermediates ("
                "gene_symbol, schema_version, prompt_corpus_version, "
                "created_at, record_valid, intermediates_bytes, "
                "intermediates_json"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    gene_symbol,
                    schema_version,
                    PROMPT_CORPUS_VERSION,
                    stamp,
                    1 if record_valid else 0,
                    n_bytes,
                    blob,
                ],
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "intermediates push for %s failed: %s. The record itself "
            "is unaffected; only the diagnostic blob is lost for this "
            "run.",
            gene_symbol,
            exc,
        )
        return IntermediatesPushResult(
            gene_symbol=gene_symbol,
            pushed=False,
            skipped_reason=f"D1 write failed: {exc}",
            intermediates_bytes=n_bytes,
            created_at=stamp,
            schema_version=schema_version,
            prompt_corpus_version=PROMPT_CORPUS_VERSION,
        )

    logger.info(
        "intermediates pushed to private D1: %s @ %s "
        "(prompt_corpus=%s, %d bytes)",
        gene_symbol,
        schema_version,
        PROMPT_CORPUS_VERSION,
        n_bytes,
    )
    return IntermediatesPushResult(
        gene_symbol=gene_symbol,
        pushed=True,
        skipped_reason=None,
        intermediates_bytes=n_bytes,
        created_at=stamp,
        schema_version=schema_version,
        prompt_corpus_version=PROMPT_CORPUS_VERSION,
    )


__all__ = [
    "IntermediatesPushResult",
    "ensure_schema",
    "publish_intermediates",
]
