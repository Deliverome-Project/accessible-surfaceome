"""Publish tag-sites to public D1's ``tag_site_public`` table.

One row per :class:`TaggedSite` (the ``viewer/lib/tag-sites-types.ts`` contract,
i.e. exactly what ``viewer/public/tag-sites/{SYMBOL}.json`` already holds). Mirrors
:mod:`accessible_surfaceome.cloud.internalization` / ``surface_annotation``
(INSERT OR REPLACE; replace-all-per-gene so a re-derivation that drops a site
never leaves a stale row). The Worker serves these at ``/v1/tag-sites/:symbol``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.cloud.d1_client import D1Client

# DDL kept in sync with cloudflare/d1_tag_sites_schema.sql. D1's HTTP API rejects
# multi-statement batches, so each statement is submitted separately.
DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS tag_site_public (
      gene_symbol                TEXT NOT NULL,
      uniprot_acc                TEXT NOT NULL,
      site_id                    TEXT NOT NULL,
      provenance                 TEXT NOT NULL,
      det_path                   TEXT,
      site_kind                  TEXT NOT NULL,
      insert_after_residue       INTEGER,
      residue_before             TEXT,
      residue_after              TEXT,
      residue_label              TEXT,
      residue_range              TEXT,
      topology_state             TEXT,
      extracellular              INTEGER NOT NULL,
      compartment                TEXT,
      tag_type                   TEXT,
      tag_length_aa              INTEGER,
      linker                     TEXT,
      evidence_type              TEXT,
      functional_impact_measured TEXT,
      confidence                 TEXT,
      rationale                  TEXT,
      sources_json               TEXT,
      plddt                      REAL,
      conservation_rank          INTEGER,
      median_conservation        REAL,
      tag_sites_version          TEXT NOT NULL,
      synced_at                  TEXT NOT NULL,
      PRIMARY KEY (uniprot_acc, site_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_tag_site_symbol "
    "ON tag_site_public (gene_symbol);",
    "CREATE INDEX IF NOT EXISTS idx_tag_site_provenance "
    "ON tag_site_public (provenance);",
)

_COLS: tuple[str, ...] = (
    "gene_symbol", "uniprot_acc", "site_id", "provenance", "det_path", "site_kind",
    "insert_after_residue", "residue_before", "residue_after", "residue_label",
    "residue_range", "topology_state", "extracellular", "compartment", "tag_type",
    "tag_length_aa", "linker", "evidence_type", "functional_impact_measured",
    "confidence", "rationale", "sources_json", "plddt", "conservation_rank",
    "median_conservation", "tag_sites_version", "synced_at",
)


def ensure_table(client: D1Client) -> None:
    """Idempotently create the table + indexes (one statement per call)."""
    for stmt in DDL:
        client.query(stmt, [])


def flat_row(
    site: dict[str, Any], *, gene_symbol: str, uniprot_acc: str, version: str, synced_at: str
) -> dict[str, Any]:
    """Project one TaggedSite dict into the flat ``tag_site_public`` columns.
    ``sources`` (a JSON array) is serialized to ``sources_json``; ``extracellular``
    becomes 0/1."""
    return {
        "gene_symbol": site.get("gene_symbol", gene_symbol),
        "uniprot_acc": site.get("uniprot_acc", uniprot_acc),
        "site_id": site["site_id"],
        "provenance": site["provenance"],
        "det_path": site.get("det_path"),
        "site_kind": site["site_kind"],
        "insert_after_residue": site.get("insert_after_residue"),
        "residue_before": site.get("residue_before"),
        "residue_after": site.get("residue_after"),
        "residue_label": site.get("residue_label"),
        "residue_range": site.get("residue_range"),
        "topology_state": site.get("topology_state"),
        "extracellular": 1 if site.get("extracellular") else 0,
        "compartment": site.get("compartment"),
        "tag_type": site.get("tag_type"),
        "tag_length_aa": site.get("tag_length_aa"),
        "linker": site.get("linker"),
        "evidence_type": site.get("evidence_type"),
        "functional_impact_measured": site.get("functional_impact_measured"),
        "confidence": site.get("confidence"),
        "rationale": site.get("rationale"),
        "sources_json": json.dumps(site.get("sources", [])),
        "plddt": site.get("plddt"),
        "conservation_rank": site.get("conservation_rank"),
        "median_conservation": site.get("median_conservation"),
        "tag_sites_version": version,
        "synced_at": synced_at,
    }


def rows_for_file(data: dict[str, Any], *, version: str, synced_at: str) -> list[dict[str, Any]]:
    """Flatten a TaggedSitesFile dict into per-site rows (pure; used by tests)."""
    gene = data["gene_symbol"]
    acc = data["uniprot_acc"]
    return [
        flat_row(s, gene_symbol=gene, uniprot_acc=acc, version=version, synced_at=synced_at)
        for s in data.get("sites", [])
    ]


def publish_tag_sites(
    data: dict[str, Any], *, tag_sites_version: str, client: D1Client | None = None
) -> int:
    """UPSERT one gene's tag-sites into public D1 and return the row count written.

    Replace-all per gene: every existing row for ``gene_symbol`` is deleted first,
    so a re-derivation that drops a site leaves no stale row. Idempotent — re-runs
    converge on the same rows. Caller owns ``client`` when passed; otherwise a
    public client is opened + closed."""
    synced_at = datetime.now(UTC).isoformat()
    rows = rows_for_file(data, version=tag_sites_version, synced_at=synced_at)

    owns = client is None
    client = client or D1Client.public()
    try:
        ensure_table(client)
        client.query(
            "DELETE FROM tag_site_public WHERE gene_symbol = ?;", [data["gene_symbol"]]
        )
        cols = ", ".join(_COLS)
        placeholders = ", ".join(["?"] * len(_COLS))
        for row in rows:
            client.query(
                f"INSERT OR REPLACE INTO tag_site_public ({cols}) VALUES ({placeholders});",
                [row[c] for c in _COLS],
            )
    finally:
        if owns:
            client.close()
    return len(rows)
