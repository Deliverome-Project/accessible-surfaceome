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
#
# ``cohort_run_id`` is added as a nullable column (back-compat with rows
# written before the column existed) — sweep drivers stamp it on every
# row so "all rows from cohort sweep X" is a single SELECT rather than a
# fragile timestamp-window query (per the R2/reproducibility audit).
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
        cohort_run_id         TEXT,
        code_sha              TEXT,
        failure_mode          TEXT,
        PRIMARY KEY (gene_symbol, schema_version, prompt_corpus_version, created_at)
    );
    """,
    # Idempotent ALTER for DBs created before ``cohort_run_id`` landed.
    # SQLite has no ``ADD COLUMN IF NOT EXISTS``, so ``ensure_schema``
    # swallows the duplicate-column failure when this is a no-op.
    """
    ALTER TABLE agent_run_intermediates ADD COLUMN cohort_run_id TEXT;
    """,
    # Tier-3 reproducibility columns (Wave 2 follow-up — see
    # ``docs/audit/reproducibility_followup_2026_06_09.md``). Both are
    # nullable so pre-Tier-3 rows back-compat cleanly; new rows always
    # populate them via ``publish_intermediates``.
    """
    ALTER TABLE agent_run_intermediates ADD COLUMN code_sha TEXT;
    """,
    """
    ALTER TABLE agent_run_intermediates ADD COLUMN failure_mode TEXT;
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
    # Cohort scope: "all rows from sweep X" — the analytic query the
    # audit identified as the single biggest reproducibility gap.
    """
    CREATE INDEX IF NOT EXISTS idx_agent_run_intermediates_cohort
        ON agent_run_intermediates (cohort_run_id, created_at DESC);
    """,
    # Failure-mode analytics: "how many runs hit cost_ceiling_pts in this
    # sweep" should be a single SELECT, not a per-row JSON parse.
    """
    CREATE INDEX IF NOT EXISTS idx_agent_run_intermediates_failure_mode
        ON agent_run_intermediates (failure_mode, created_at DESC);
    """,
]


def _slim_intermediates_for_d1(blob: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `blob` with the bulkiest audit-only fields removed.

    Preserves everything the synth-only / builders-only retry path needs:
      * `plan_trim_select.{a1,a2}.claims` (the trimmed evidence ledger)
      * `plan_trim_select.{a1,a2}.{n_claims, n_anchored, ...}` summary
      * `builders.*` (all builder outputs)
      * `risks_builder`, `canonical_risks`, `deterministic_features`
      * `synthesizer.{draft, raw_json, validation_error, n_repair_attempts}`
      * `bundle`, `triage_summary` (when present)
      * `cost_total_usd`, `cost_per_builder` (when present)

    Drops audit-only bulk:
      * `plan_trim_select.{a1,a2}.search_log` (per-iteration search results)
      * `plan_trim_select.{a1,a2}.triage_actions` (per-paper triage decisions)
      * `plan_trim_select.{a1,a2}.pretrim_audits` (pretrim filter decisions)
      * Paper metadata (`paper_abstract`) on any remaining audit list

    The forensic audit (which papers triaged + dropped) goes to R2 in
    a follow-up — D1 keeps the slim retry-path payload only.
    """
    out: dict[str, Any] = {}
    for k, v in blob.items():
        if k == "plan_trim_select" and isinstance(v, dict):
            pts: dict[str, Any] = {}
            for side, side_blob in v.items():
                if not isinstance(side_blob, dict):
                    pts[side] = side_blob
                    continue
                pts[side] = {
                    sk: sv
                    for sk, sv in side_blob.items()
                    if sk not in (
                        "search_log",
                        "triage_actions",
                        "pretrim_audits",
                        "iteration_log",
                    )
                }
            out[k] = pts
        else:
            out[k] = v
    return out


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
    # Cohort sweep tag stamped on the published row. ``None`` for the
    # single-gene CLI driver path (no cohort context); set by the
    # sweep driver to the per-sweep UUID — same value the matching
    # ``deep_dive_run.run_id`` carries, so the two tables join cleanly.
    cohort_run_id: str | None = None


def ensure_schema(d1: D1Client | None = None) -> None:
    """Apply the intermediates DDL to the private D1.

    Idempotent for the ``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF
    NOT EXISTS`` statements. The ``ALTER TABLE ADD COLUMN cohort_run_id``
    needed for backfilling pre-cohort DBs has no ``IF NOT EXISTS``
    syntax in SQLite, so we swallow its "duplicate column" failure on
    DBs that already carry the column. Useful for one-off bring-up in a
    fresh worktree without needing wrangler.
    """
    owns_client = d1 is None
    client = d1 or D1Client()
    try:
        for stmt in _SCHEMA_SQL:
            try:
                client.query(stmt.strip(), [])
            except Exception as exc:  # noqa: BLE001 — ALTER may already be applied
                msg = str(exc).lower()
                if "duplicate column" in msg or "already exists" in msg:
                    logger.debug(
                        "intermediates schema stmt no-op (already applied): %s",
                        stmt.strip()[:60],
                    )
                    continue
                raise
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
    cohort_run_id: str | None = None,
    failure_mode: str | None = None,
) -> IntermediatesPushResult:
    """Push one run's intermediates to private D1.

    Caller is the annotate driver; one call per annotate run, AFTER the
    canonical record publish (so a publish failure on the record side
    doesn't lose the diagnostic blob — pushing intermediates is its own
    network round-trip).

    ``record_valid`` reflects whether the annotate run produced a
    schema-validating ``SurfaceomeRecord``. Failed runs are still
    preserved here — that's the whole point of the audit trail.

    ``cohort_run_id`` (optional) stamps the row with the sweep tag —
    same UUID the matching ``deep_dive_run.run_id`` carries so post-sweep
    analytics can SELECT all rows from a given cohort in one query
    rather than via a fragile timestamp window. ``None`` for the
    single-gene CLI path; the cohort sweep driver supplies one per
    invocation.

    ``failure_mode`` (optional) denormalizes the
    :class:`AnnotateResultV2.failure_mode` tag onto the row's own column
    so cohort analytics can query ``WHERE failure_mode = 'cost_ceiling_pts'``
    without per-row JSON parsing. ``None`` for the back-compat CLI path
    or any caller that hasn't been threaded yet — that just falls through
    to the column default (NULL). See ``tools/_shared/failure_modes.py``
    for the enum.

    Returns an :class:`IntermediatesPushResult` with the bytes pushed
    and any skip reason. The function NEVER raises on a D1 / credentials
    miss; misses log + return a skipped result so the annotate driver
    can continue.
    """
    # Stamp run-level reproducibility metadata before serializing — these
    # are fields that must travel with the blob so a 1-year-later audit
    # can fully reproduce the record from saved metadata alone. See
    # ``agents/_support/run_metadata.py`` for the helpers and
    # ``docs/audit/r2_and_reproducibility_2026_06_08.md`` for the
    # original audit that surfaced the gaps.
    #
    # The ``{**intermediates, ...}`` pattern keeps the caller's dict
    # immutable — same convention ``_slim_intermediates_for_d1`` uses
    # below.
    from accessible_surfaceome.agents._support.run_metadata import code_sha
    # Lazy import — ``agents.surfaceome_v2.orchestrator`` imports
    # ``cloud.*`` transitively for D1 reads, so doing this at module
    # level would race the orchestrator's own import chain. The model
    # id is a constant string in practice (no runtime mutation), so the
    # cost of resolving it per-publish is negligible.
    from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
        AGENT_MODEL,
    )
    intermediates = {
        **intermediates,
        "code_sha": code_sha(),
        "model_id": AGENT_MODEL,
    }
    blob = json.dumps(intermediates, separators=(",", ":"))
    n_bytes = len(blob.encode("utf-8"))
    stamp = created_at or datetime.now(UTC).isoformat()

    # Slim-fallback when the full blob would exceed D1's row limit.
    # Drop the bulkiest pieces (per-side plan-trim-select search_log +
    # triage_actions + paper-metadata fields) and keep what the synth-
    # only retry path actually needs: claims, builder outputs,
    # deterministic_features, canonical_risks, synthesizer raw_json,
    # bundle, triage_summary. Observed: TGOLN2 v2.32 at 897KB (99.7%
    # of 900KB limit) — heavier genes WILL exceed.
    if n_bytes > _MAX_INTERMEDIATES_BYTES:
        logger.warning(
            "intermediates for %s would exceed D1 row limit "
            "(%d bytes > %d). Stripping bulky audit fields "
            "(search_log + triage_actions + paper_metadata) so the "
            "slim blob fits; full blob spilling to R2.",
            gene_symbol, n_bytes, _MAX_INTERMEDIATES_BYTES,
        )
        # R2 full-audit offload: upload the FULL pre-slim blob to R2
        # using the existing CLOUDFLARE_API_TOKEN (Option A — no new
        # access keys needed). Best-effort: R2 outages should not
        # block the slim-D1 publish. The R2 key gets stitched into
        # the slim blob so a future audit query can follow the
        # pointer.
        try:
            from accessible_surfaceome.cloud import r2_client
            r2_key = r2_client.intermediates_object_key(
                gene_symbol=gene_symbol,
                schema_version=schema_version,
                prompt_corpus_version=PROMPT_CORPUS_VERSION,
                created_at=stamp,
            )
            r2_ok = r2_client.put_object(key=r2_key, body=blob)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "R2 spillover for %s skipped (%s); slim D1 will publish "
                "without an audit-blob pointer",
                gene_symbol, exc,
            )
            r2_key = None
            r2_ok = False
        # Slim AFTER the R2 upload — preserves the original blob shape
        # for the audit copy.
        slim = _slim_intermediates_for_d1(intermediates)
        if r2_ok:
            slim["_r2_full_audit_key"] = r2_key
            slim["_r2_full_audit_bucket"] = (
                r2_client.R2Config.from_env().bucket
            )
        elif r2_key:
            slim["_r2_full_audit_attempted_key"] = r2_key
            slim["_r2_full_audit_status"] = "upload_failed"
        blob = json.dumps(slim, separators=(",", ":"))
        n_bytes_slim = len(blob.encode("utf-8"))
        logger.info(
            "intermediates slimmed for %s: %d → %d bytes (%.1f%% saved); "
            "R2 audit blob: %s",
            gene_symbol, n_bytes, n_bytes_slim,
            100.0 * (1 - n_bytes_slim / n_bytes),
            "uploaded" if r2_ok else "skipped",
        )
        n_bytes = n_bytes_slim
        # Defensive: if even the slim blob exceeds the limit (some
        # genes have giant builder outputs), fall back to skip rather
        # than corrupt D1 with a truncation.
        if n_bytes > _MAX_INTERMEDIATES_BYTES:
            logger.warning(
                "intermediates for %s still exceed limit after slimming "
                "(%d bytes). Skipping push — review whether deterministic_"
                "features or claims need further compression.",
                gene_symbol, n_bytes,
            )
            return IntermediatesPushResult(
                gene_symbol=gene_symbol,
                pushed=False,
                skipped_reason=f"size {n_bytes} > limit even after slim",
                intermediates_bytes=n_bytes,
                created_at=stamp,
                schema_version=schema_version,
                prompt_corpus_version=PROMPT_CORPUS_VERSION,
                cohort_run_id=cohort_run_id,
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
            cohort_run_id=cohort_run_id,
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
            cohort_run_id=cohort_run_id,
        )

    # ``code_sha`` is denormalized off the blob into its own column for
    # analytics (so "all rows from commit X" is a SELECT, not a JSON
    # parse). We read it back from the blob rather than recomputing —
    # avoids a drift window between the stamped value and the column
    # value if the helper got called twice with different env state.
    code_sha_col = intermediates.get("code_sha")
    try:
        with D1Client(cfg, timeout_s=60.0) as client:
            client.query(
                "INSERT INTO agent_run_intermediates ("
                "gene_symbol, schema_version, prompt_corpus_version, "
                "created_at, record_valid, intermediates_bytes, "
                "intermediates_json, cohort_run_id, code_sha, failure_mode"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    gene_symbol,
                    schema_version,
                    PROMPT_CORPUS_VERSION,
                    stamp,
                    1 if record_valid else 0,
                    n_bytes,
                    blob,
                    cohort_run_id,
                    code_sha_col,
                    failure_mode,
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
            cohort_run_id=cohort_run_id,
        )

    logger.info(
        "intermediates pushed to private D1: %s @ %s "
        "(prompt_corpus=%s, cohort=%s, %d bytes)",
        gene_symbol,
        schema_version,
        PROMPT_CORPUS_VERSION,
        cohort_run_id or "<none>",
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
        cohort_run_id=cohort_run_id,
    )


__all__ = [
    "IntermediatesPushResult",
    "ensure_schema",
    "publish_intermediates",
]
