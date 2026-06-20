"""Per-(run, gene, paper) discovery log → private D1.

The discovery layer (Europe PMC + PubTator + gene2pubmed + OpenAlex)
surfaces a pool of candidate papers per gene per sweep. Pre-this-module
the pool only lived as JSON inside :mod:`cloud.intermediates`'s
``intermediates_json`` blob — readable, but not joinable to anything,
not indexable, not diff-able across sweeps without per-row JSON parse.

This module materializes that pool as a flat ``harvested_paper`` table.
One row per (run_id, gene_symbol, paper_id). Cheap analytics:

* "Which papers landed in CD20's pool for the first time when we
  widened SRC:PPR?" — single SQL diff between two sweep ids
* "How many DataCite-resolved papers per gene?" — single GROUP BY
* "What axis surfaced the highest-yield papers?" — JOIN to
  ``triage_run`` on ``paper_id`` and GROUP BY ``axis_label``

Storage cost at our scale (6,521 cohort genes × ~50 new papers/year
each = ~325k rows/year × ~200 B = ~65 MB/year): under $1/year on
D1's $0.75/GB/month and ~$0.33/year on write fees. Effectively free.

The schema is independent of :mod:`cloud.intermediates`'s blob payload;
the two coexist (intermediates remains the source of truth for the
prose-heavy builder state, harvested_paper is the flat row-indexable
discovery log). No backfill from intermediates is wired here — that's
a separate maintenance job once the writer is in production.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

from accessible_surfaceome.cloud.d1_client import D1Client

logger = logging.getLogger(__name__)


# Schema. One CREATE + index statements, all idempotent. Matches the
# convention in :mod:`cloud.intermediates` (one ``_SCHEMA_SQL`` list,
# applied via :func:`ensure_schema`).
_SCHEMA_SQL = [
    # The flat per-paper row. PRIMARY KEY is (run_id, gene_symbol,
    # paper_id) so re-running a sweep with the same run_id appends new
    # papers but doesn't duplicate the ones already landed. ``paper_id``
    # uses the same canonical key as ``paper_source_id`` in
    # ``abstract_triage`` (``PMC:<id>`` > ``PMID:<id>`` > ``DOI:<doi>``)
    # so this table joins cleanly to ``triage_run.id`` via the agent's
    # ``paper_id`` field on each action.
    """
    CREATE TABLE IF NOT EXISTS harvested_paper (
        run_id        TEXT NOT NULL,
        gene_symbol   TEXT NOT NULL,
        paper_id      TEXT NOT NULL,
        source        TEXT NOT NULL,
        axis_label    TEXT,
        bucket        TEXT,
        body_source   TEXT,
        doi           TEXT,
        pmid          INTEGER,
        pmc_id        TEXT,
        year          INTEGER,
        title         TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (run_id, gene_symbol, paper_id)
    );
    """,
    # Per-gene history across sweeps: "show me every paper we've ever
    # discovered for CD20" — one query, no JSON parse.
    """
    CREATE INDEX IF NOT EXISTS idx_harvested_paper_gene
        ON harvested_paper (gene_symbol, created_at DESC);
    """,
    # Per-sweep scope: "all papers from sweep X" — the diff query is
    # ``WHERE run_id IN (X, Y) GROUP BY gene_symbol, paper_id``.
    """
    CREATE INDEX IF NOT EXISTS idx_harvested_paper_run
        ON harvested_paper (run_id);
    """,
    # Per-source analytics: "how much did SRC:PPR add when we widened
    # the Europe PMC filter" — single GROUP BY on source.
    """
    CREATE INDEX IF NOT EXISTS idx_harvested_paper_source
        ON harvested_paper (source, run_id);
    """,
    # Bucket analytics: "what fraction of discovered papers got
    # `worth_fetching` triage" — useful for tuning the triage prompt.
    """
    CREATE INDEX IF NOT EXISTS idx_harvested_paper_bucket
        ON harvested_paper (bucket, run_id);
    """,
]


@dataclass(frozen=True)
class HarvestedPaper:
    """One discovered paper. Caller assembles from probe / runner state.

    ``paper_id`` is the canonical source key the rest of the chain uses
    (``PMC:<id>`` > ``PMID:<id>`` > ``DOI:<doi>``) — keep this consistent
    with ``paper_source_id`` in :mod:`agents.plan_trim_select.abstract_triage`
    so downstream joins to ``triage_run.paper_id`` hit.

    ``source`` is which discovery axis surfaced it
    (``"europepmc_med"`` / ``"europepmc_ppr"`` / ``"pubtator"`` /
    ``"openalex"`` / ``"gene2pubmed"`` / ``"datacite"``).

    ``axis_label`` is the per-axis tag (the evidence_retrieval category,
    the topic_search anchor, the OpenAlex axis name). Nullable for
    broad-recall axes that don't carry a label.

    ``bucket`` is the triage outcome (``"pmc"`` / ``"unpaywall"`` /
    ``"bot_blocked"`` / ``"datacite_oa_repo"`` / ``"no_oa"``). Nullable
    until triage runs; the writer is willing to insert pre-triage rows
    so discovery + triage can be decoupled at the runner level.

    ``body_source`` is which fetch chain tier returned a body
    (``"pmc_xml"`` / ``"unpaywall_pdf"`` / ``"datacite_pdf"`` / null).
    """

    run_id: str
    gene_symbol: str
    paper_id: str
    source: str
    axis_label: str | None = None
    bucket: str | None = None
    body_source: str | None = None
    doi: str | None = None
    pmid: int | None = None
    pmc_id: str | None = None
    year: int | None = None
    title: str | None = None


def ensure_schema(d1: D1Client | None = None) -> None:
    """Apply the harvested_paper DDL to the private D1.

    Idempotent. Mirrors ``cloud.intermediates.ensure_schema`` (same
    duplicate-column / already-exists swallow) so a fresh worktree can
    bring the table up without wrangler.
    """
    owns_client = d1 is None
    client = d1 or D1Client()
    try:
        for stmt in _SCHEMA_SQL:
            try:
                client.query(stmt.strip(), [])
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                if "duplicate column" in msg or "already exists" in msg:
                    logger.debug(
                        "harvested_paper schema stmt no-op: %s",
                        stmt.strip()[:60],
                    )
                    continue
                raise
        logger.info("harvested_paper schema applied")
    finally:
        if owns_client:
            client.close()


def publish_harvested_papers(
    papers: Iterable[HarvestedPaper],
    *,
    d1: D1Client | None = None,
) -> int:
    """INSERT OR REPLACE the given papers into ``harvested_paper``. Returns
    the number of rows written.

    Uses ``INSERT OR REPLACE`` on the natural key (``run_id``,
    ``gene_symbol``, ``paper_id``) so a sweep that re-emits a paper (the
    same gene's pool partially overlapping across re-runs of the same
    run_id) overwrites rather than duplicates. Caller is expected to
    have stable run_ids.

    D1's HTTP API doesn't accept multi-statement batches, so this loops
    one statement per call. At our scale (a few hundred papers per
    gene-sweep batch) this is acceptable; for bulk backfill we'd want
    a chunked INSERT VALUES variant — separate concern.
    """
    owns_client = d1 is None
    client = d1 or D1Client()
    try:
        n = 0
        for p in papers:
            client.query(
                """
                INSERT OR REPLACE INTO harvested_paper (
                    run_id, gene_symbol, paper_id, source, axis_label,
                    bucket, body_source, doi, pmid, pmc_id, year, title,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """.strip(),
                [
                    p.run_id, p.gene_symbol, p.paper_id, p.source,
                    p.axis_label, p.bucket, p.body_source,
                    p.doi, p.pmid, p.pmc_id, p.year, p.title,
                    datetime.now(UTC).isoformat(),
                ],
            )
            n += 1
        return n
    finally:
        if owns_client:
            client.close()


__all__ = [
    "HarvestedPaper",
    "ensure_schema",
    "publish_harvested_papers",
]
