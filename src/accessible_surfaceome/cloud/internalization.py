"""Publish an ``InternalizationRecord`` to public D1's ``surface_internalization``.

The sequence sweep (:mod:`scripts.internalization_seq_sweep`) writes
model-prior-only rows; a later literature run UPSERTs the same
``(gene_symbol, schema_version)`` key with ``has_literature=1``. Mirrors the
:mod:`accessible_surfaceome.cloud.surface_annotation` pattern (INSERT OR REPLACE,
drop-stale-versions) but for the separate internalization record.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from urllib.parse import urlparse

from accessible_surfaceome.agents.internalization.models import InternalizationRecord
from accessible_surfaceome.cloud.d1_client import D1Client

logger = logging.getLogger(__name__)

# Edge-cache keys the Worker uses for the internalization surfaces — MUST match
# ``cloudflare/workers/surfaceome_api/src/index.js``. ``withEdgeCache`` keys BOTH
# ``caches.default`` and the ``RECORD_CACHE`` KV mirror on the synthetic host
# ``https://surfaceome-api.cache`` + the UNSTRIPPED request pathname (which
# carries the ``/surfaceome`` route prefix); ``handleCatalog`` uses its own
# synthetic host ``https://catalog.cache`` + a hardcoded ``/v1/catalog``.
# NOTE: surface_annotation.py purges the per-gene ``caches.default`` key under a
# DIFFERENT host (``cache.internal``) — that host does not match the deployed
# Worker's key, so its file-purge silently misses (only its KV delete lands).
# We use the correct ``surfaceome-api.cache`` host here for BOTH layers.
_PUBLIC_API_BASE = os.environ.get(
    "SURFACEOME_PUBLIC_API_BASE", "https://api.deliverome.org/surfaceome"
)
_CACHE_KEY_BASE = f"https://surfaceome-api.cache{urlparse(_PUBLIC_API_BASE).path.rstrip('/')}"
_CATALOG_CACHE_URL = "https://catalog.cache/v1/catalog"


def _purge_internalization_cache(sym: str) -> None:
    """Best-effort edge-cache invalidation after an internalization D1 write.

    A republish must evict the gene's ``/v1/internalization/{sym}`` entry from
    BOTH ``caches.default`` (per-POP) and the ``RECORD_CACHE`` KV mirror, plus the
    genome-wide ``/v1/catalog`` (its ``intern``/``intern_lit_grade`` column for
    this row changed) — otherwise the re-graded record serves stale until the
    Worker's Cache-Control TTL (up to 1 day for a per-gene record).

    Never raises and soft-skips with a warning when the Cloudflare env isn't
    configured (same posture as the D1 push itself, so CI / offline dev never
    breaks — the record then just goes live on the TTL). Reuses
    surface_annotation's Cloudflare API helpers for the actual calls but pins the
    keys to the internalization route on the host the Worker really uses.
    """
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    zone = os.environ.get("CLOUDFLARE_ZONE_ID", "").strip()
    if not (token and zone):
        logger.warning(
            "CLOUDFLARE_ZONE_ID / CLOUDFLARE_API_TOKEN not set — skipping "
            "internalization edge-cache purge for %s (record goes live on the "
            "Worker's Cache-Control TTL, up to 1 day, rather than immediately).",
            sym,
        )
        return
    import httpx

    from accessible_surfaceome.cloud.surface_annotation import (
        _delete_kv_key,
        _purge_cf_cache,
    )

    rec_url = f"{_CACHE_KEY_BASE}/v1/internalization/{sym}"
    try:
        with httpx.Client(timeout=30.0) as client:
            _purge_cf_cache(
                [rec_url, _CATALOG_CACHE_URL], zone_id=zone, token=token, client=client
            )
            acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
            ns = os.environ.get("CLOUDFLARE_KV_RECORD_CACHE_ID", "").strip()
            if acct and ns:
                _delete_kv_key(
                    rec_url, account_id=acct, namespace_id=ns, token=token, client=client
                )
            else:
                logger.warning(
                    "CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_KV_RECORD_CACHE_ID not set "
                    "— purged caches.default but not the KV mirror for %s; the KV "
                    "entry serves stale until its expiration TTL (1 day).",
                    sym,
                )
        logger.info("internalization edge-cache purged for %s (per-gene + catalog)", sym)
    except Exception as exc:  # noqa: BLE001 — purge is best-effort, never fatal
        logger.warning(
            "internalization edge-cache purge failed for %s (%s) — record stale "
            "until TTL",
            sym,
            exc,
        )

# DDL kept in sync with cloudflare/d1_internalization_schema.sql. D1's HTTP API
# rejects multi-statement batches, so each statement is submitted separately.
DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS surface_internalization (
      gene_symbol                  TEXT NOT NULL,
      schema_version               TEXT NOT NULL,
      hgnc_id                      TEXT,
      uniprot_acc                  TEXT,
      runner_version               TEXT,
      seq_model                    TEXT,
      seq_prompt_sha               TEXT,
      seq_prompt_version           TEXT,
      seq_scope                    TEXT,
      seq_overall_grade            TEXT,
      seq_overall_confidence       TEXT,
      seq_canonical_grade          TEXT,
      seq_canonical_confidence     TEXT,
      n_seq_motifs                 INTEGER,
      n_seq_functional_motifs      INTEGER,
      has_literature               INTEGER NOT NULL DEFAULT 0,
      lit_overall_grade            TEXT,
      lit_n_observations           INTEGER,
      lit_n_modulator_observations INTEGER,
      lit_prompt_sha               TEXT,
      lit_prompt_version           TEXT,
      record_json                  TEXT NOT NULL,
      generated_at                 TEXT,
      updated_at                   TEXT,
      PRIMARY KEY (gene_symbol, schema_version)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_surface_internalization_symbol "
    "ON surface_internalization (gene_symbol);",
    "CREATE INDEX IF NOT EXISTS idx_surface_internalization_seq_grade "
    "ON surface_internalization (seq_overall_grade);",
    "CREATE INDEX IF NOT EXISTS idx_surface_internalization_has_lit "
    "ON surface_internalization (has_literature);",
)

_COLS: tuple[str, ...] = (
    "gene_symbol", "schema_version", "hgnc_id", "uniprot_acc", "runner_version",
    "seq_model", "seq_prompt_sha", "seq_prompt_version", "seq_scope",
    "seq_overall_grade", "seq_overall_confidence",
    "seq_canonical_grade", "seq_canonical_confidence", "n_seq_motifs",
    "n_seq_functional_motifs", "has_literature", "lit_overall_grade",
    "lit_n_observations", "lit_n_modulator_observations",
    "lit_prompt_sha", "lit_prompt_version", "record_json",
    "generated_at", "updated_at",
)


# Columns added AFTER the table first shipped live (the seq sweep created it
# without them). SQLite/D1 has no ``ADD COLUMN IF NOT EXISTS``, so ensure_table
# runs these and tolerates the duplicate-column error on an already-migrated DB.
# Keep in sync with the CREATE TABLE above.
_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE surface_internalization ADD COLUMN lit_prompt_sha TEXT;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_prompt_version TEXT;",
)


def ensure_table(client: D1Client) -> None:
    """Idempotently create the table + indexes, then bring an existing table up
    to the current column set via tolerated ALTERs (one statement per call)."""
    for stmt in DDL:
        client.query(stmt, [])
    for stmt in _MIGRATIONS:
        try:
            client.query(stmt, [])
        except Exception as exc:  # noqa: BLE001 — duplicate column on a migrated DB is fine
            if "duplicate column" not in str(exc).lower():
                raise


def flat_row(record: InternalizationRecord) -> dict[str, object]:
    """Project a record into the flat ``surface_internalization`` columns."""
    # The sequence sweep runs one model (Opus); take the first track if present.
    seq = record.model_priors[0] if record.model_priors else None
    canonical = None
    if seq is not None:
        canonical = next(
            (iso for iso in seq.per_isoform if iso.is_canonical),
            seq.per_isoform[0] if seq.per_isoform else None,
        )
    motifs = list(canonical.motifs) if canonical else []
    lit = record.literature
    return {
        "gene_symbol": record.gene_symbol,
        "schema_version": record.schema_version,
        "hgnc_id": record.hgnc_id,
        "uniprot_acc": record.uniprot_acc,
        "runner_version": record.runner_version,
        "seq_model": seq.model if seq else None,
        "seq_prompt_sha": seq.prompt_sha if seq else None,
        "seq_prompt_version": seq.prompt_version if seq else None,
        "seq_scope": seq.scope if seq else None,
        "seq_overall_grade": seq.overall_grade if seq else None,
        "seq_overall_confidence": seq.overall_confidence if seq else None,
        "seq_canonical_grade": canonical.grade if canonical else None,
        "seq_canonical_confidence": canonical.confidence if canonical else None,
        "n_seq_motifs": len(motifs),
        "n_seq_functional_motifs": sum(1 for m in motifs if m.functional_context),
        "has_literature": 1 if lit is not None else 0,
        "lit_overall_grade": lit.overall_grade if lit else None,
        "lit_n_observations": lit.n_observations if lit else None,
        "lit_n_modulator_observations": (
            lit.n_modulator_observations if lit else None
        ),
        "lit_prompt_sha": lit.prompt_sha if lit else None,
        "lit_prompt_version": lit.prompt_version if lit else None,
        "record_json": record.model_dump_json(),
        "generated_at": record.generated_at.isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def publish_seq_record(
    record: InternalizationRecord, *, client: D1Client | None = None
) -> None:
    """Validate + UPSERT one record into public D1 (INSERT OR REPLACE on the
    ``(gene_symbol, schema_version)`` PK). Drops stale-schema rows for the gene
    first, so a schema bump never leaves a resurfaceable old row. Caller owns the
    client lifecycle when one is passed; otherwise a public client is opened."""
    # Re-validate defensively (a caller might hand us a dict-built record).
    record = InternalizationRecord.model_validate(record.model_dump())
    row = flat_row(record)

    owns = client is None
    client = client or D1Client.public()
    try:
        ensure_table(client)
        # drop stale schema_versions for this gene before upserting
        existing = client.query(
            "SELECT schema_version FROM surface_internalization WHERE gene_symbol = ?;",
            [record.gene_symbol],
        )
        for r in existing:
            ver = r.get("schema_version")
            if ver and ver != record.schema_version:
                client.query(
                    "DELETE FROM surface_internalization "
                    "WHERE gene_symbol = ? AND schema_version = ?;",
                    [record.gene_symbol, ver],
                )
        cols = ", ".join(_COLS)
        placeholders = ", ".join(["?"] * len(_COLS))
        client.query(
            f"INSERT OR REPLACE INTO surface_internalization ({cols}) "
            f"VALUES ({placeholders});",
            [row[c] for c in _COLS],
        )
        # Evict the gene's cached Worker responses so a re-grade goes live
        # immediately rather than on the Cache-Control TTL (up to 1 day).
        _purge_internalization_cache(record.gene_symbol)
    finally:
        if owns:
            client.close()
