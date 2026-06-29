"""Upload surfaceome_v2 deep-dive runs to the Cloudflare D1
``surfaceome_agents`` database.

Mirror of :mod:`accessible_surfaceome.cloud.triage_upload` but for the
v2 annotator's ``SurfaceomeRecord`` output. One :class:`D1DeepDiveSink`
is constructed before the worker pool starts; it interns the composite
prompt SHA once and each worker calls :meth:`insert` after a successful
``annotate()``. Dedupe is by ``(run_id, gene_symbol)``: the second insert
for the same gene under the same sweep is a no-op so restarting a crashed
sweep with the same ``run_id`` skips genes already in D1.

The on-disk JSON record at ``data/annotations/{gene}.json`` (or the Modal
Volume mirror) is the canonical source of truth; this sink is a real-time
mirror. If a D1 insert fails the JSON write still landed and the row can
be back-filled later.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents.surfaceome_v2.orchestrator import AGENT_MODEL
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

from .d1_client import D1Client

logger = logging.getLogger(__name__)

V2_PROMPTS_DIR = (
    REPO_ROOT / "src" / "accessible_surfaceome" / "agents" / "surfaceome_v2" / "prompts"
)
# The synthesizer + plan-trim-select prompts also contribute to the
# end-to-end behaviour. We compose a single SHA across every prompt file
# that materially influences the annotator's output.
EXTRA_PROMPT_DIRS = [
    REPO_ROOT / "src" / "accessible_surfaceome" / "agents" / "surfaceome_synthesizer" / "prompts",
    REPO_ROOT / "src" / "accessible_surfaceome" / "agents" / "plan_trim_select" / "prompts",
]
COMPOSITE_PROMPT_FILENAME = "surfaceome_v2_composite.md"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class CompositePrompt:
    sha: str
    text: str
    n_lines: int
    schema_version: str


def _read_prompt_dir(d: Path) -> list[tuple[str, str]]:
    if not d.exists():
        return []
    out: list[tuple[str, str]] = []
    for p in sorted(d.glob("*.md")):
        out.append((p.name, p.read_text()))
    return out


def _build_composite_prompt(schema_version: str) -> CompositePrompt:
    """Concatenate every prompt file that influences v2's behaviour, in a
    stable order, and SHA the result. This is the signature recorded on
    every deep-dive row so a prompt edit produces a different SHA → a
    fresh row in ``prompt_version`` → joinable history of which prompt
    suite produced which row.
    """
    parts: list[str] = []
    for d in [V2_PROMPTS_DIR, *EXTRA_PROMPT_DIRS]:
        for fname, body in _read_prompt_dir(d):
            parts.append(f"### {d.name}/{fname}\n{body}\n")
    text = "".join(parts)
    return CompositePrompt(
        sha=_sha256(text),
        text=text,
        n_lines=len(text.splitlines()),
        schema_version=schema_version,
    )


def _ensure_unique_index(d1: D1Client) -> None:
    """Idempotently apply the (run_id, gene_symbol) UNIQUE INDEX that
    ``_insert_run``'s ``ON CONFLICT`` clause depends on. The schema file
    declares this index, but D1 doesn't auto-apply schema files — without
    this guard a sweep against a DB where the index was never installed
    fails every insert at the SQL parser, ``D1DeepDiveSink.insert()``
    swallows the error as a warning, and the caller exits 0 with zero D1
    rows. Sub-ms no-op when the index already exists.
    """
    d1.query(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_deep_dive_run_unique_gene "
        "ON deep_dive_run (run_id, gene_symbol);",
        [],
    )


def _intern_prompt(d1: D1Client, prompt: CompositePrompt) -> None:
    d1.query(
        "INSERT OR IGNORE INTO prompt_version "
        "(prompt_sha, prompt_filename, schema_version, text, n_lines) "
        "VALUES (?, ?, ?, ?, ?);",
        [
            prompt.sha,
            COMPOSITE_PROMPT_FILENAME,
            prompt.schema_version,
            prompt.text,
            prompt.n_lines,
        ],
    )


def _existing_genes(d1: D1Client, run_id: str) -> set[str]:
    rows = d1.query(
        "SELECT gene_symbol FROM deep_dive_run WHERE run_id = ?;",
        [run_id],
    )
    return {r["gene_symbol"] for r in rows}


def genes_done_at_schema(d1: D1Client, schema_version: str) -> set[str]:
    """Gene symbols with a completed ``deep_dive_run`` record at
    ``schema_version``, across **all** run_ids.

    Backs the global, schema-aware dispatch dedup that organizes an incremental
    rollout (run 25, then 100, then 1000 …): a gene is skipped iff it already
    has a current-schema record *anywhere*, so re-launching — even under a
    different run_id / batch tag — never re-spends on a successful gene, while a
    schema bump re-opens every stale gene for a fresh run. A ``deep_dive_run``
    row exists only for a gene whose record validated, so presence == success.
    Caller bypasses this with ``--force``.
    """
    rows = d1.query(
        "SELECT DISTINCT gene_symbol FROM deep_dive_run WHERE schema_version = ?;",
        [schema_version],
    )
    return {str(r["gene_symbol"]) for r in rows}


def _insert_run(
    d1: D1Client,
    *,
    run_id: str,
    record: SurfaceomeRecord,
    prompt_sha: str,
    cost_usd: float,
    latency_s: float,
    n_tool_calls: int,
) -> int | None:
    contradiction_flag = 1 if record.surface_evidence.contradicting_evidence else 0
    rationale = record.executive_summary.one_paragraph or ""
    # ON CONFLICT (run_id, gene_symbol) DO NOTHING relies on the
    # idx_deep_dive_run_unique_gene UNIQUE INDEX in cloudflare/d1_schema.sql.
    # When two driver processes race the same (run_id, gene), D1's UPSERT
    # makes the second INSERT a no-op — no row returned, child inserts
    # skipped (the existing parent's children are the source of truth).
    rows = d1.query(
        "INSERT INTO deep_dive_run ("
        " run_id, gene_symbol, uniprot_acc, canonical_isoform, isoform_flattened,"
        " model, model_path, prompt_sha, schema_version,"
        " targetability_verdict, confidence, contradiction_flag,"
        " primary_evidence_count, secondary_evidence_count, evidence_count, search_log_count,"
        " rationale, confidence_reasoning,"
        " cost_usd, latency_s, n_tool_calls,"
        " record_json"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT (run_id, gene_symbol) DO NOTHING"
        " RETURNING id;",
        [
            run_id,
            record.gene.hgnc_symbol,
            record.gene.uniprot_acc,
            None,  # canonical_isoform — not currently surfaced on the record
            0,  # isoform_flattened
            AGENT_MODEL,
            record.model_path,
            prompt_sha,
            record.schema_version,
            record.executive_summary.surface_accessibility,
            record.confidence,
            contradiction_flag,
            record.primary_evidence_count,
            record.secondary_evidence_count,
            record.evidence_count,
            len(record.search_log),
            rationale,
            record.confidence_reasoning,
            float(cost_usd),
            float(latency_s),
            int(n_tool_calls),
            record.model_dump_json(),
        ],
    )
    return rows[0].get("id") if rows else None


# Child inserts use an ``INSERT ... SELECT ... WHERE NOT EXISTS`` guard on the
# row's natural key rather than a plain ``VALUES`` insert. ``D1Client.query``
# retries transient failures, so every write is at-least-once: an ambiguous
# commit (D1 applied the row but the response was lost) would otherwise let the
# retry duplicate a child row — invisible to ``audit_deep_dive_orphans`` (it
# only flags *missing* children, i.e. actual < expected). The natural keys are
# ``(deep_dive_run_id, evidence_id)`` and ``(deep_dive_run_id, step_index)``;
# both are unique within a parent (evidence_id is a cross-reference handle,
# step_index is the enumerate order), so the guard skips only an exact re-insert
# of a row that already landed. A single writer owns each parent's children
# (the parent insert dedups on ``(run_id, gene_symbol)``), so there is no
# concurrent-insert race for the guard to miss.


def _insert_evidence_rows(
    d1: D1Client, deep_dive_run_id: int, record: SurfaceomeRecord
) -> None:
    for ev in record.evidence:
        source_db: str | None = None
        source_url: str | None = None
        span_text: str | None = None
        if ev.spans:
            first = ev.spans[0]
            source_db = first.source.source_type
            source_url = str(first.source.url) if first.source.url is not None else None
            span_text = first.quote
        d1.query(
            "INSERT INTO deep_dive_evidence "
            "(deep_dive_run_id, evidence_id, source_db, source_url,"
            " span_text, claim_kind, is_primary) "
            "SELECT ?, ?, ?, ?, ?, ?, ? "
            "WHERE NOT EXISTS ("
            " SELECT 1 FROM deep_dive_evidence"
            " WHERE deep_dive_run_id = ? AND evidence_id = ?"
            ");",
            [
                deep_dive_run_id,
                ev.evidence_id,
                source_db,
                source_url,
                span_text,
                ev.claim_type,
                1 if ev.evidence_tier == "primary" else 0,
                deep_dive_run_id,
                ev.evidence_id,
            ],
        )


def _insert_search_log_rows(
    d1: D1Client, deep_dive_run_id: int, record: SurfaceomeRecord
) -> None:
    for i, entry in enumerate(record.search_log):
        d1.query(
            "INSERT INTO deep_dive_search_log "
            "(deep_dive_run_id, step_index, source, query, hit_count, yielded_citation) "
            "SELECT ?, ?, ?, ?, ?, ? "
            "WHERE NOT EXISTS ("
            " SELECT 1 FROM deep_dive_search_log"
            " WHERE deep_dive_run_id = ? AND step_index = ?"
            ");",
            [
                deep_dive_run_id,
                i,
                entry.tool,
                str(entry.query) if entry.query else None,
                int(entry.n_results),
                1 if entry.sources_seen else 0,
                deep_dive_run_id,
                i,
            ],
        )


class D1DeepDiveSink:
    """Streaming sink for surfaceome_v2 deep-dive results.

    Thread-safe. :class:`D1Client` wraps httpx (which has thread-safe
    pooling); the only shared mutable state here is the existing-genes
    set, guarded by a lock.
    """

    def __init__(self, *, run_id: str, client: D1Client | None = None):
        self.run_id = run_id
        self._lock = threading.Lock()
        self._client = client if client is not None else D1Client()
        self._owns_client = client is None

        _ensure_unique_index(self._client)
        self._prompt = _build_composite_prompt(SurfaceomeRecord.model_fields["schema_version"].default)
        _intern_prompt(self._client, self._prompt)
        self._existing = _existing_genes(self._client, run_id)

        logger.info(
            "D1DeepDiveSink ready: run_id=%s prompt_sha=%s existing=%d",
            run_id, self._prompt.sha[:12], len(self._existing),
        )

    @property
    def prompt_sha(self) -> str:
        return self._prompt.sha

    def already_done(self, gene_symbol: str) -> bool:
        with self._lock:
            return gene_symbol in self._existing

    def insert(
        self,
        record: SurfaceomeRecord,
        *,
        cost_usd: float,
        latency_s: float,
        n_tool_calls: int = 0,
    ) -> bool:
        """Insert one record. Returns True on success / dedup-skip; False
        on D1 failure. Never raises so the worker pool keeps going.
        """
        gene = record.gene.hgnc_symbol
        with self._lock:
            if gene in self._existing:
                return True
            self._existing.add(gene)
        try:
            dd_id = _insert_run(
                self._client,
                run_id=self.run_id,
                record=record,
                prompt_sha=self._prompt.sha,
                cost_usd=cost_usd,
                latency_s=latency_s,
                n_tool_calls=n_tool_calls,
            )
            if dd_id is not None:
                _insert_evidence_rows(self._client, dd_id, record)
                _insert_search_log_rows(self._client, dd_id, record)
            return True
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._existing.discard(gene)
            logger.warning("D1DeepDiveSink: insert failed for %s: %s", gene, exc)
            return False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> D1DeepDiveSink:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


__all__ = ["CompositePrompt", "D1DeepDiveSink", "COMPOSITE_PROMPT_FILENAME"]
