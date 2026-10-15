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
    gene_symbol          TEXT NOT NULL,
    -- The library MEMBER this search describes, or '' for a gene-level search.
    -- Empty string rather than NULL: a NULL in a primary key does not compare
    -- equal to itself, so NULL-keyed rows multiply silently on every UPSERT.
    candidate_id         TEXT NOT NULL DEFAULT '',
    -- Which pass this is. The two literature passes are different searches of
    -- the same gene and both answers are worth keeping, so the series is part
    -- of the key rather than something one overwrites the other through.
    run_series           TEXT NOT NULL DEFAULT 'literature_v1',
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
    synced_at            TEXT,
    PRIMARY KEY (gene_symbol, candidate_id, run_series)
);
"""
INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_tsgp_prompt ON tag_site_gene_public (prompt_sha);",
    "CREATE INDEX IF NOT EXISTS idx_tsgp_nsites ON tag_site_gene_public (n_sites);",
)

_COLS = (
    "gene_symbol",
    "candidate_id",
    "run_series",
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
        "candidate_id": record.get("candidate_id") or "",
        "run_series": record.get("run_series") or "literature_v1",
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
    """UPSERT by (gene_symbol, candidate_id, run_series). Idempotent."""
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


#: Suffix for the retained pre-migration table. A rename is reversible while
#: the old bytes still exist; a DROP is not, and this table's 1,415 dated zeros
#: each cost a real literature search to reproduce.
_LEGACY_SUFFIX = "_legacy_single_key"


def migrate_gene_key(client: D1Client, *, execute: bool = False) -> dict[str, Any]:
    """Re-key ``tag_site_gene_public`` to ``(gene_symbol, candidate_id, run_series)``.

    The table's primary key is ``gene_symbol`` alone, so a second search of the
    same gene — the enrichment pass — would OVERWRITE the first and destroy the
    dated zero that distinguishes "no published tag site exists for this
    protein" from "we have not got to it yet". 1,415 of its 2,370 rows are
    exactly that.

    D1 cannot ``ALTER`` a primary key, so: create, copy, VERIFY, rename. The
    verify is the point — a copy that lost rows must leave the live table
    exactly as it was rather than replace it with a short one. One statement per
    HTTP call, because D1's HTTP API rejects multi-statement batches.

    Existing rows become ``candidate_id = ''`` (gene-level, no specific member)
    and ``run_series = 'literature_v1'``.

    **This does not make the Worker safe to read two rows.** ``handleTagSites``
    selects with ``.first()`` and no ``ORDER BY``; while every gene still has
    exactly one row that is deterministic, and this migration preserves it. But
    writing enrichment rows before the Worker is taught to choose would make a
    gene answer differently depending on which row came back. Migrate, deploy
    the Worker, then write.
    """
    report: dict[str, Any] = {
        "executed": execute, "already_migrated": False, "aborted": False,
        "before": 0, "copied": 0, "after": 0,
    }
    cols = {
        c["name"]
        for c in client.query("PRAGMA table_info(tag_site_gene_public);", [])
    }
    if not cols:
        report["aborted"] = True
        report["reason"] = "tag_site_gene_public does not exist"
        return report
    if "candidate_id" in cols and "run_series" in cols:
        report["already_migrated"] = True
        report["before"] = report["after"] = _count(client, "tag_site_gene_public")
        return report

    report["before"] = _count(client, "tag_site_gene_public")
    carried = [c for c in _COLS if c not in ("candidate_id", "run_series")]
    if not execute:
        return report

    client.query("DROP TABLE IF EXISTS tag_site_gene_public_v2;", [])
    client.query(DDL.replace("tag_site_gene_public", "tag_site_gene_public_v2"), [])
    client.query(
        f"INSERT INTO tag_site_gene_public_v2 "
        f"(gene_symbol, candidate_id, run_series, {', '.join(c for c in carried if c != 'gene_symbol')}) "
        f"SELECT gene_symbol, '', 'literature_v1', "
        f"{', '.join(c for c in carried if c != 'gene_symbol')} "
        f"FROM tag_site_gene_public;",
        [],
    )
    report["copied"] = _count(client, "tag_site_gene_public_v2")
    if report["copied"] != report["before"]:
        # Verify BEFORE the rename, so a lossy copy is a no-op rather than a
        # replacement. The scratch table is left for inspection.
        report["aborted"] = True
        report["reason"] = (
            f"copy has {report['copied']} rows against {report['before']}; "
            f"left tag_site_gene_public_v2 in place and renamed nothing"
        )
        return report

    client.query(
        f"ALTER TABLE tag_site_gene_public RENAME TO "
        f"tag_site_gene_public{_LEGACY_SUFFIX};",
        [],
    )
    client.query(
        "ALTER TABLE tag_site_gene_public_v2 RENAME TO tag_site_gene_public;", []
    )
    for idx in INDEXES:
        client.query(idx, [])
    report["after"] = _count(client, "tag_site_gene_public")
    return report


def _count(client: D1Client, table: str) -> int:
    rows = client.query(f"SELECT COUNT(*) AS n FROM {table};", [])
    return int(rows[0]["n"]) if rows else 0
