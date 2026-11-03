"""Persist a tag-site run's intermediates to private D1.

The run artifacts under ``data/external/tag_site_runs/`` are gitignored derived
data: they survive on one machine, they are not in any backup, and they are one
``rm -rf`` from gone. Every real diagnosis today came out of them — which clip
pool existed, what the model was shown, why a site was not proposed — so losing
them loses the only account of why a record says what it says.

The deep dive solved this already: ``deep_dive_run`` in the private database
carries its per-gene history with prompts, costs and prose. This is the same
table for the tag-site agent, keyed the same way, in the same database.

PRIVATE, not public. It holds the full ledger, the agent's notes, and every
rejection — prose reasoning that belongs beside the deep dive's, not on the
public mirror the viewer reads.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.cloud.d1_client import D1Client

logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS tag_site_run (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    gene_symbol      TEXT NOT NULL,
    uniprot_acc      TEXT,
    model            TEXT NOT NULL,
    prompt_sha       TEXT NOT NULL,
    prompt_version   TEXT NOT NULL,
    schema_version   TEXT,
    n_papers         INTEGER,
    n_clips          INTEGER,
    n_boosted        INTEGER,
    n_model_calls    INTEGER,
    cost_usd         REAL,
    n_sites          INTEGER,
    n_rejected       INTEGER,
    n_other_positions INTEGER,
    notes            TEXT,
    ledger_json      TEXT,
    rejected_json    TEXT,
    other_positions_json TEXT,
    boosted_json     TEXT,
    synthesis_meta_json  TEXT
);
"""
INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_tag_site_run_gene ON tag_site_run (gene_symbol);",
    "CREATE INDEX IF NOT EXISTS idx_tag_site_run_run ON tag_site_run (run_id);",
    "CREATE INDEX IF NOT EXISTS idx_tag_site_run_sha ON tag_site_run (prompt_sha);",
)

_COLS = (
    "run_id", "created_at", "gene_symbol", "uniprot_acc", "model", "prompt_sha",
    "prompt_version", "schema_version", "n_papers", "n_clips", "n_boosted",
    "n_model_calls", "cost_usd", "n_sites", "n_rejected", "n_other_positions",
    "notes", "ledger_json", "rejected_json", "other_positions_json",
    "boosted_json", "synthesis_meta_json",
)


#: The DDL is idempotent, but it is three round trips, and a sweep runs one
#: process per gene. Once per process is enough; the table does not disappear
#: between two genes.
_ensured = False


def ensure_table(client: D1Client) -> None:
    global _ensured
    if _ensured:
        return
    client.query(DDL, [])
    for idx in INDEXES:
        client.query(idx, [])
    _ensured = True


def row_for(intermediates: dict[str, Any], *, run_id: str, uniprot_acc: str = "") -> dict[str, Any]:
    """Flatten one run's intermediates into a `tag_site_run` row (pure; tested)."""
    d = intermediates
    return {
        "run_id": run_id,
        "created_at": d.get("generated_at") or datetime.now(UTC).isoformat(),
        "gene_symbol": d.get("gene_symbol", ""),
        "uniprot_acc": uniprot_acc,
        "model": d.get("model", ""),
        "prompt_sha": d.get("prompt_sha", ""),
        "prompt_version": d.get("prompt_version", ""),
        "schema_version": d.get("schema_version", ""),
        "n_papers": d.get("n_papers"),
        "n_clips": d.get("n_clips"),
        "n_boosted": d.get("n_boosted"),
        "n_model_calls": d.get("n_model_calls"),
        "cost_usd": d.get("cost_usd"),
        "n_sites": d.get("n_sites"),
        "n_rejected": len(d.get("rejected") or []),
        "n_other_positions": len(d.get("other_positions") or []),
        "notes": d.get("notes") or "",
        "ledger_json": json.dumps(d.get("ledger") or []),
        "rejected_json": json.dumps(d.get("rejected") or []),
        "other_positions_json": json.dumps(d.get("other_positions") or []),
        "boosted_json": json.dumps(d.get("boosted") or {}),
        "synthesis_meta_json": json.dumps(d.get("synthesis_meta") or {}),
    }


def publish_run(
    intermediates: dict[str, Any],
    *,
    run_id: str,
    uniprot_acc: str = "",
    client: D1Client | None = None,
) -> bool:
    """Append one run. Never raises: losing the archive copy must not fail a run
    that already produced a record on disk."""
    owns = client is None
    try:
        client = client or D1Client()          # private database
        ensure_table(client)
        row = row_for(intermediates, run_id=run_id, uniprot_acc=uniprot_acc)
        cols = ", ".join(_COLS)
        marks = ", ".join(["?"] * len(_COLS))
        client.query(f"INSERT INTO tag_site_run ({cols}) VALUES ({marks});",
                     [row[c] for c in _COLS])
        return True
    except Exception as exc:  # noqa: BLE001 - archival is best-effort
        logger.warning("could not archive tag-site run for %s: %s",
                       intermediates.get("gene_symbol"), exc)
        return False
    finally:
        if owns and client is not None:
            client.close()
