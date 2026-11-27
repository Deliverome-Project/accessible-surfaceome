"""Publish an ``InternalizationRecord`` to public D1's ``surface_internalization``.

The sequence sweep (:mod:`scripts.internalization_seq_sweep`) writes
model-prior-only rows; a later literature run UPSERTs the same
``(gene_symbol, schema_version)`` key with ``has_literature=1``. Mirrors the
:mod:`accessible_surfaceome.cloud.surface_annotation` pattern (INSERT OR REPLACE,
drop-stale-versions) but for the separate internalization record.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

from accessible_surfaceome.agents.internalization.models import InternalizationRecord
from accessible_surfaceome.cloud.d1_client import D1Client

logger = logging.getLogger(__name__)

# Both cache tiers use the Worker's deployment epoch before the route prefix.
_PUBLIC_API_BASE = os.environ.get(
    "SURFACEOME_PUBLIC_API_BASE", "https://api.deliverome.org/surfaceome"
)
_ROUTE_PREFIX = urlparse(_PUBLIC_API_BASE).path.rstrip("/")


def _purge_internalization_cache(sym: str, *, include_catalog: bool = True) -> None:
    """Best-effort edge-cache invalidation after an internalization D1 write.

    A republish must evict the gene's ``/v1/internalization/{sym}`` entry from
    BOTH ``caches.default`` (per-POP) and the ``RECORD_CACHE`` KV mirror, plus
    (when ``include_catalog=True``) the genome-wide ``/v1/catalog``. During a
    large cohort sweep, pass ``include_catalog=False`` per gene and call
    :func:`purge_catalog_cache` once at the end of the sweep.
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
        _cache_epoch,
        _delete_kv_key,
        _purge_cf_cache,
    )

    epoch = _cache_epoch()
    rec_url = f"https://surfaceome-api.cache/{epoch}{_ROUTE_PREFIX}/v1/internalization/{sym}"
    urls = [rec_url]
    if include_catalog:
        urls.append(f"https://catalog.cache/{epoch}/v1/catalog")
    try:
        with httpx.Client(timeout=30.0) as client:
            _purge_cf_cache(urls, zone_id=zone, token=token, client=client)
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
        logger.info("internalization edge-cache purged for %s (catalog=%s)", sym, include_catalog)
    except Exception as exc:  # noqa: BLE001 — purge is best-effort, never fatal
        logger.warning(
            "internalization edge-cache purge failed for %s (%s) — record stale "
            "until TTL",
            sym,
            exc,
        )


def purge_catalog_cache() -> None:
    """Evict the genome-wide ``/v1/catalog`` cache once after a batch sweep."""
    purge_internalization_batch([], include_catalog=True)


def purge_internalization_batch(
    symbols: list[str],
    *,
    include_catalog: bool = False,
) -> None:
    """Batch-evict ``/v1/internalization/{sym}`` edge cache (in chunks of 30
    URLs, Cloudflare's per-call limit) + KV mirror entries using ONE httpx client.

    Cuts 3,213 individual zone-purge API calls down to ~108 batched calls so a
    large cohort sweep stays well under Cloudflare's purge rate limits.
    """
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    zone = os.environ.get("CLOUDFLARE_ZONE_ID", "").strip()
    if not (token and zone):
        return
    import httpx

    from accessible_surfaceome.cloud.surface_annotation import (
        _cache_epoch,
        _delete_kv_key,
        _purge_cf_cache,
    )

    epoch = _cache_epoch()
    rec_urls = [
        f"https://surfaceome-api.cache/{epoch}{_ROUTE_PREFIX}/v1/internalization/{sym}"
        for sym in dict.fromkeys(symbols)
        if sym
    ]
    all_urls = list(rec_urls)
    if include_catalog:
        all_urls.append(f"https://catalog.cache/{epoch}/v1/catalog")
    if not all_urls:
        return

    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    ns = os.environ.get("CLOUDFLARE_KV_RECORD_CACHE_ID", "").strip()
    try:
        with httpx.Client(timeout=30.0) as client:
            for i in range(0, len(all_urls), 30):
                _purge_cf_cache(all_urls[i : i + 30], zone_id=zone, token=token, client=client)
            if acct and ns:
                for rec_url in rec_urls:
                    try:
                        _delete_kv_key(
                            rec_url,
                            account_id=acct,
                            namespace_id=ns,
                            token=token,
                            client=client,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("KV delete failed for %s: %s", rec_url, exc)
        logger.info(
            "batch-purged edge cache for %d internalization record(s) (catalog=%s)",
            len(rec_urls),
            include_catalog,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("batch edge-cache purge failed (%s)", exc)

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
      lit_overall_confidence       TEXT,
      lit_basal_grade              TEXT,
      lit_native_ligand_grade      TEXT,
      lit_therapeutic_grade        TEXT,
      lit_pathogen_entry_grade     TEXT,
      lit_predominant_fate         TEXT,
      lit_has_primary_or_invivo    INTEGER,
      lit_has_quant                INTEGER,
      lit_has_fitted_kinetics      INTEGER,
      lit_binder_types             TEXT,
      lit_mechanisms               TEXT,
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
    "lit_overall_confidence", "lit_basal_grade", "lit_native_ligand_grade",
    "lit_therapeutic_grade", "lit_pathogen_entry_grade", "lit_predominant_fate",
    "lit_has_primary_or_invivo", "lit_has_quant", "lit_has_fitted_kinetics",
    "lit_binder_types", "lit_mechanisms",
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
    "ALTER TABLE surface_internalization ADD COLUMN lit_overall_confidence TEXT;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_basal_grade TEXT;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_native_ligand_grade TEXT;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_therapeutic_grade TEXT;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_pathogen_entry_grade TEXT;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_predominant_fate TEXT;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_has_primary_or_invivo INTEGER;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_has_quant INTEGER;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_has_fitted_kinetics INTEGER;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_binder_types TEXT;",
    "ALTER TABLE surface_internalization ADD COLUMN lit_mechanisms TEXT;",
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
    lit_binders: str | None = None
    lit_mechs: str | None = None
    lit_has_quant: int | None = None
    lit_has_fitted: int | None = None
    if lit is not None:
        obs = list(lit.observations)
        binders = sorted({o.binder_type for o in obs if o.binder_type != "unknown"})
        mechs = sorted(
            {
                o.mechanism
                for o in obs
                if o.mechanism and o.mechanism not in {"unknown", "receptor_mediated_unspecified"}
            }
        )
        lit_binders = json.dumps(binders) if binders else None
        lit_mechs = json.dumps(mechs) if mechs else None
        lit_has_quant = (
            1
            if any(
                o.quant.rate_value is not None
                or o.quant.derived_t_half_min is not None
                or o.quant.derived_ke_min_inv is not None
                or o.quant.apparent_t_half_min is not None
                for o in obs
            )
            else 0
        )
        lit_has_fitted = (
            1
            if any(
                o.quant.derived_t_half_min is not None
                or o.quant.derived_ke_min_inv is not None
                for o in obs
            )
            else 0
        )
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
        "lit_overall_confidence": lit.overall_confidence if lit else None,
        "lit_basal_grade": lit.grades_by_mode.basal.grade if lit else None,
        "lit_native_ligand_grade": lit.grades_by_mode.native_ligand.grade if lit else None,
        "lit_therapeutic_grade": lit.grades_by_mode.therapeutic.grade if lit else None,
        "lit_pathogen_entry_grade": (
            lit.grades_by_mode.pathogen_entry.grade
            if lit and lit.grades_by_mode.pathogen_entry
            else None
        ),
        "lit_predominant_fate": lit.predominant_fate if lit else None,
        "lit_has_primary_or_invivo": (
            (1 if lit.has_primary_or_invivo_evidence else 0) if lit else None
        ),
        "lit_has_quant": lit_has_quant,
        "lit_has_fitted_kinetics": lit_has_fitted,
        "lit_binder_types": lit_binders,
        "lit_mechanisms": lit_mechs,
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
    record: InternalizationRecord,
    *,
    client: D1Client | None = None,
    purge_catalog: bool = True,
    ensure_schema: bool = True,
    purge_edge: bool = True,
    max_retries: int = 3,
) -> None:
    """Validate + UPSERT one record into public D1 (INSERT OR REPLACE on the
    ``(gene_symbol, schema_version)`` PK). Drops stale-schema rows for the gene
    first, so a schema bump never leaves a resurfaceable old row. Caller owns the
    client lifecycle when one is passed; otherwise a public client is opened.

    Batch sweeps should call :func:`ensure_table` once up front, pass
    ``ensure_schema=False, purge_edge=False``, and call
    :func:`purge_internalization_batch` periodically + at end of sweep.
    """
    # Re-validate defensively (a caller might hand us a dict-built record).
    record = InternalizationRecord.model_validate(record.model_dump())
    row = flat_row(record)

    owns = client is None
    client = client or D1Client.public()
    cols = ", ".join(_COLS)
    placeholders = ", ".join(["?"] * len(_COLS))
    values = [row[c] for c in _COLS]
    try:
        if ensure_schema:
            ensure_table(client)

        last_exc: Exception | None = None
        attempts = max(1, max_retries)
        for attempt in range(1, attempts + 1):
            try:
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
                client.query(
                    f"INSERT OR REPLACE INTO surface_internalization ({cols}) "
                    f"VALUES ({placeholders});",
                    values,
                )
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < attempts:
                    wait_s = float(2 ** (attempt - 1))
                    logger.warning(
                        "D1 publish failed for %s (attempt %d/%d, retrying in %.0fs): %s",
                        record.gene_symbol,
                        attempt,
                        attempts,
                        wait_s,
                        exc,
                    )
                    time.sleep(wait_s)
        if last_exc is not None:
            raise last_exc

        # Evict the gene's cached Worker responses so a re-grade goes live
        # immediately rather than on the Cache-Control TTL (up to 1 day).
        if purge_edge:
            _purge_internalization_cache(record.gene_symbol, include_catalog=purge_catalog)
    finally:
        if owns:
            client.close()
