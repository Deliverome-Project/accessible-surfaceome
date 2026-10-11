"""Per-GENE tag-site facts for the public mirror: did we look, and what else did we find.

``tag_site_public`` holds one row per SITE, so a gene the literature agent
searched and found nothing in has no rows at all — identical, from the outside,
to a gene nobody ever searched. That is the same defect the record's
``prompt_sha`` exists to prevent, one level up: a zero that cannot be dated has
to be re-run before it can be trusted, and a reader cannot tell "no published
tag site exists for this protein" from "we have not got to it yet". 1,106 of
the first sweep's 1,824 genes are exactly this case.

It also carries ``other_positions`` — the published insertion points that are
NOT surface tag sites. A tolerated insertion facing the cytoplasm is the right
answer for a snorkel or an intracellular label, and a position a paper reports
as abrogating function is evidence about a known-bad site. Both were being
captured into the private run archive and going no further, so the surface a
reader opens could not show either. They are per-gene, not per-site, which is
why they live here rather than as rows in the site table.

One row per gene the agent RAN. Presence of the row is the claim "this gene was
searched, under this prompt, on this date" — so a gene absent from this table is
unsearched, and that distinction is the whole point.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.cloud.d1_client import D1Client

logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS tag_site_gene_public (
    gene_symbol          TEXT PRIMARY KEY,
    uniprot_acc          TEXT,
    searched_at          TEXT,
    prompt_sha           TEXT,
    prompt_version       TEXT,
    model                TEXT,
    schema_version       TEXT,
    n_papers             INTEGER,
    n_sites              INTEGER NOT NULL DEFAULT 0,
    n_other_positions    INTEGER NOT NULL DEFAULT 0,
    other_positions_json TEXT,
    notes                TEXT,
    tag_sites_version    TEXT,
    synced_at            TEXT
);
"""
INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_tsgp_prompt ON tag_site_gene_public (prompt_sha);",
    "CREATE INDEX IF NOT EXISTS idx_tsgp_nsites ON tag_site_gene_public (n_sites);",
)

_COLS = (
    "gene_symbol",
    "uniprot_acc",
    "searched_at",
    "prompt_sha",
    "prompt_version",
    "model",
    "schema_version",
    "n_papers",
    "n_sites",
    "n_other_positions",
    "other_positions_json",
    "notes",
    "tag_sites_version",
    "synced_at",
)

_ensured = False


def ensure_table(client: D1Client) -> None:
    global _ensured
    if _ensured:
        return
    client.query(DDL, [])
    for idx in INDEXES:
        client.query(idx, [])
    _ensured = True


def row_for(
    record: dict[str, Any],
    *,
    version: str,
    n_papers: int | None = None,
    synced_at: str | None = None,
) -> dict[str, Any] | None:
    """One gene's row from its viewer record, or None if the agent never ran it.

    ``prompt_sha`` is the test for "ran": the literature agent stamps it on every
    result including an empty one, and a record that has none was written by the
    deterministic pipeline alone."""
    if not record.get("prompt_sha"):
        return None
    others = record.get("literature_other_positions") or []
    sites = [
        s
        for s in (record.get("sites") or [])
        if s.get("provenance") == "literature_retrieved"
    ]
    return {
        "gene_symbol": record.get("gene_symbol", ""),
        "uniprot_acc": record.get("uniprot_acc") or "",
        "searched_at": record.get("generated_at") or "",
        "prompt_sha": record.get("prompt_sha") or "",
        "prompt_version": record.get("prompt_version") or "",
        "model": record.get("model") or "",
        "schema_version": record.get("schema_version") or "",
        "n_papers": n_papers,
        "n_sites": len(sites),
        "n_other_positions": len(others),
        "other_positions_json": json.dumps(others),
        "notes": record.get("literature_notes") or "",
        "tag_sites_version": version,
        "synced_at": synced_at or datetime.now(UTC).isoformat(),
    }


def publish_gene_rows(
    rows: list[dict[str, Any]], *, client: D1Client | None = None
) -> int:
    """UPSERT by gene_symbol. Idempotent; re-runs converge."""
    if not rows:
        return 0
    owns = client is None
    client = client or D1Client.public()
    try:
        ensure_table(client)
        cols = ", ".join(_COLS)
        marks = ", ".join(["?"] * len(_COLS))
        n = 0
        for row in rows:
            client.query(
                f"INSERT OR REPLACE INTO tag_site_gene_public ({cols}) VALUES ({marks});",
                [row[c] for c in _COLS],
            )
            n += 1
        return n
    finally:
        if owns:
            client.close()
