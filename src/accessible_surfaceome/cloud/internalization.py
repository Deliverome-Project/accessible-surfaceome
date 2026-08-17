"""Publish an ``InternalizationRecord`` to public D1's ``surface_internalization``.

The sequence sweep (:mod:`scripts.internalization_seq_sweep`) writes
model-prior-only rows; a later literature run UPSERTs the same
``(gene_symbol, schema_version)`` key with ``has_literature=1``. Mirrors the
:mod:`accessible_surfaceome.cloud.surface_annotation` pattern (INSERT OR REPLACE,
drop-stale-versions) but for the separate internalization record.
"""

from __future__ import annotations

from datetime import UTC, datetime

from accessible_surfaceome.agents.internalization.models import InternalizationRecord
from accessible_surfaceome.cloud.d1_client import D1Client

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
    "lit_n_observations", "lit_n_modulator_observations", "record_json",
    "generated_at", "updated_at",
)


def ensure_table(client: D1Client) -> None:
    """Idempotently create the table + indexes (one statement per call)."""
    for stmt in DDL:
        client.query(stmt, [])


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
    finally:
        if owns:
            client.close()
