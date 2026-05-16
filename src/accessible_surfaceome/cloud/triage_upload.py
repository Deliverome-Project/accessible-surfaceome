"""Upload triage agent runs to the Cloudflare D1 ``surfaceome_agents`` database.

Provides :class:`D1RunSink` — a streaming sink wired into the triage
runner's hot path. The sink is created before the worker pool starts,
interns the prompt + benchmark snapshots once, then each worker calls
:meth:`D1RunSink.insert` after a successful per-cell completion. Dedup
is by (run_id, model, variant, gene_symbol, replicate, prompt_sha):
existing rows are skipped, so re-runs of the same sweep are safe.

The batch ``upload_subbench_runs`` helper that used to live here was
removed when the 17-row sub-bench cohort was retired (2026-05-16);
genome-scale and mainbench sweeps now go straight through ``D1RunSink``
without ever materializing a per-cell JSON tree on disk.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.models import TRIAGE_SCHEMA_VERSION

from .d1_client import D1Client

logger = logging.getLogger(__name__)

PROMPTS_DIR = REPO_ROOT / "src" / "accessible_surfaceome" / "agents" / "surface_triage" / "prompts"

# Maps the runner's variant slug → prompt filename. Keep in sync with
# scripts/triage_runner.py:VARIANTS. Missing-variant entries
# cause D1RunSink to silently skip cells under that variant — the
# 2026-05-11 slim sweep was lost to D1 because this map was stale; the
# log shows "D1RunSink: unknown variant 'slim'; skipping" repeated 147x.
VARIANT_TO_PROMPT = {
    "naive":             "system_naive.md",
    "ncbi":              "system.md",
    "web_naive":         "system_web_naive.md",
    "web_ncbi":          "system_web.md",
    # Variants that share a prompt with another variant but vary the
    # tool-call envelope (max_tokens, max_uses). Same prompt content,
    # so they share the prompt_sha row in prompt_version.
    "web_ncbi_reduced":  "system_web.md",
    "pubmed_ncbi":       "system_pubmed.md",
}


@dataclass
class PromptInfo:
    sha: str
    filename: str
    text: str
    n_lines: int
    schema_version: str


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_benchmark_rows(bench_tsv: Path) -> list[dict[str, str]]:
    with bench_tsv.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _bench_version(bench_tsv: Path) -> str:
    """Content-address the benchmark TSV with a short SHA prefix.

    A bench_version that changes whenever the TSV changes lets us
    point old runs at the labels that were live then.
    """
    return _sha256(bench_tsv.read_text())[:12]


def _intern_prompt(d1: D1Client, prompt: PromptInfo) -> None:
    """INSERT OR IGNORE so concurrent uploaders don't race."""
    d1.query(
        "INSERT OR IGNORE INTO prompt_version "
        "(prompt_sha, prompt_filename, schema_version, text, n_lines) "
        "VALUES (?, ?, ?, ?, ?);",
        [prompt.sha, prompt.filename, prompt.schema_version, prompt.text, prompt.n_lines],
    )


def _intern_benchmark(d1: D1Client, bench_version: str, rows: list[dict[str, str]]) -> None:
    """INSERT OR IGNORE every benchmark / gene-list row under the given
    bench_version.

    Handles two input shapes:

    * Labeled benchmark TSV (``triage_benchmark_v1.tsv``): has
      uniprot_acc + class + ground_truth_* columns. Stored verbatim —
      the truth join from triage_run → benchmark_version returns the
      ground truth that was live at sweep time.

    * Unlabeled gene-list TSV (``whole_genome_minus_m1.tsv``,
      genome-wide candidate sets): only gene_symbol guaranteed; truth
      columns are empty strings. The benchmark_version row still gets
      written so the sweep's input gene-set is queryable later — the
      truth join returns empty strings, which the caller interprets as
      "unlabeled".

    If the user re-labels a protein and re-runs, the new TSV gets a new
    content SHA → new bench_version → fresh insertion path. Old rows
    coexist forever.
    """
    for r in rows:
        d1.query(
            "INSERT OR IGNORE INTO benchmark_version "
            "(bench_version, gene_symbol, uniprot_acc, class, "
            " truth_verdict, truth_signal, truth_reason, rationale) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            [
                bench_version,
                r["gene_symbol"],
                r.get("uniprot_acc", ""),
                r.get("class", ""),
                r.get("ground_truth_verdict", ""),
                r.get("ground_truth_signal", ""),
                r.get("ground_truth_reason", ""),
                r.get("rationale", ""),
            ],
        )


def _intern_resolver_context(
    d1: D1Client,
    *,
    gene_symbol: str,
    user_message: str,
    hgnc_gene_groups: str | None = None,
    cd_designation: str | None = None,
    ncbi_summary: str | None = None,
) -> str:
    """Content-address a resolver/user_message snapshot.

    Returns the SHA. INSERT OR IGNORE keeps races safe. Caller passes
    optional pre-parsed denormalized fields for hot-query convenience —
    omit them and they'll just be NULL.
    """
    sha = _sha256(user_message)
    d1.query(
        "INSERT OR IGNORE INTO resolver_context_version "
        "(context_sha, gene_symbol, text, hgnc_gene_groups, "
        " cd_designation, ncbi_summary) VALUES (?, ?, ?, ?, ?, ?);",
        [sha, gene_symbol, user_message,
         hgnc_gene_groups, cd_designation, ncbi_summary],
    )
    return sha


def _insert_run(
    d1: D1Client,
    *,
    run_id: str,
    record: dict[str, Any],
    prompt_sha: str,
    bench_version: str,
    uniprot_acc: str | None,
    truth_class: str,
) -> None:
    # Resolver context — content-address whatever the agent saw as its
    # user message, if the record carries it. Pre-2026-05 runner output
    # lacks this field, in which case the join column stays NULL.
    resolver_context_sha: str | None = None
    user_message = record.get("user_message")
    if user_message:
        resolver_context_sha = _intern_resolver_context(
            d1,
            gene_symbol=record["gene_symbol"],
            user_message=user_message,
            hgnc_gene_groups=record.get("resolver_hgnc_gene_groups"),
            cd_designation=record.get("resolver_cd_designation"),
            ncbi_summary=record.get("resolver_ncbi_summary"),
        )

    # SQLite RETURNING is supported on D1 (SQLite 3.35+). We need the new
    # row's id to write child rows in triage_search_log.
    rows = d1.query(
        "INSERT INTO triage_run ("
        " run_id, gene_symbol, uniprot_acc, bench_version, model, prompt_variant,"
        " prompt_sha, schema_version, replicate, predicted_verdict, predicted_reason,"
        " verdict_reasoning, predicted_confidence, predicted_key_uncertainty,"
        " truth_verdict, truth_class, correct, prompt_tokens,"
        " completion_tokens, cache_creation_tokens, cache_read_tokens,"
        " n_web_searches, cost_usd, latency_s, error, raw_text,"
        " resolver_context_sha, temperature, top_p, max_tokens,"
        " api_response_id, api_stop_reason, api_model"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        " RETURNING id;",
        [
            run_id,
            record["gene_symbol"],
            uniprot_acc,
            bench_version,
            record["model"],
            record["variant"],
            prompt_sha,
            TRIAGE_SCHEMA_VERSION,
            record["replicate"],
            record.get("predicted_verdict"),
            record.get("predicted_reason"),
            record.get("verdict_reasoning") or "",
            record.get("predicted_confidence"),
            record.get("predicted_key_uncertainty"),
            record["truth_verdict"],
            truth_class,
            1 if record.get("correct") else 0,
            int(record.get("prompt_tokens") or 0),
            int(record.get("completion_tokens") or 0),
            int(record.get("cache_creation_tokens") or 0),
            int(record.get("cache_read_tokens") or 0),
            int(record.get("n_web_searches") or 0),
            float(record.get("cost_usd") or 0.0),
            float(record.get("latency_s") or 0.0),
            record.get("error"),
            record.get("raw_text") or None,
            resolver_context_sha,
            _maybe_float(record.get("temperature")),
            _maybe_float(record.get("top_p")),
            _maybe_int(record.get("max_tokens")),
            record.get("api_response_id"),
            record.get("api_stop_reason"),
            record.get("api_model"),
        ],
    )

    # Persist any tool-call traces the runner captured. Each entry is
    # {step_index, tool, query, n_results, top_results: [{title, url, snippet}, ...]}.
    # No-op for naive/ncbi/pubmed_ncbi variants (search_log stays empty there).
    search_log = record.get("search_log") or []
    if rows and search_log:
        triage_run_id = rows[0].get("id")
        if triage_run_id is not None:
            _insert_search_log_rows(d1, triage_run_id, search_log)


def _insert_search_log_rows(
    d1: D1Client,
    triage_run_id: int,
    search_log: list[dict[str, Any]],
) -> None:
    """Batch-insert one triage_search_log row per tool call."""
    statements: list[tuple[str, list[Any]]] = []
    for entry in search_log:
        top_results = entry.get("top_results")
        # Skip rows that didn't pair with a result block (None top_results
        # would mean the runner saw a server_tool_use without a matching
        # web_search_tool_result — recording with NULL is still useful).
        results_json = json.dumps(top_results) if top_results is not None else None
        statements.append((
            "INSERT INTO triage_search_log "
            "(triage_run_id, step_index, tool, query, n_results, top_results_json) "
            "VALUES (?, ?, ?, ?, ?, ?);",
            [
                triage_run_id,
                int(entry.get("step_index") or 0),
                str(entry.get("tool") or "unknown"),
                entry.get("query"),
                _maybe_int(entry.get("n_results")),
                results_json,
            ],
        ))
    if statements:
        d1.batch(statements)


def _maybe_float(v: Any) -> float | None:
    return None if v is None else float(v)


def _maybe_int(v: Any) -> int | None:
    return None if v is None else int(v)


def _existing_keys(d1: D1Client, run_id: str) -> set[tuple[str, str, str, int, str]]:
    rows = d1.query(
        "SELECT gene_symbol, model, prompt_variant, replicate, prompt_sha "
        "FROM triage_run WHERE run_id = ?;",
        [run_id],
    )
    return {
        (r["gene_symbol"], r["model"], r["prompt_variant"], r["replicate"], r["prompt_sha"])
        for r in rows
    }


class D1RunSink:
    """Streaming sink that writes triage runs to D1 as they complete.

    Designed for the runner's hot path: one ``D1RunSink`` is created
    before the worker pool starts, prompt + benchmark snapshots are
    interned once, and each worker calls :meth:`insert` after a
    successful per-cell completion. Thread-safe — ``D1Client.query``
    uses httpx, and the only shared mutable state is the existing-keys
    set protected by an internal lock.

    The on-disk JSON record under
    ``data/eval/triage_<sub?>bench_v1/<model>/<variant>/<gene>_run<N>.json``
    remains the canonical source of truth — the sink is a *real-time
    mirror*, not a replacement. If a D1 insert fails (network blip, rate
    limit), the error is logged and the JSON write still landed; the
    batch uploader can fill in the gap later.
    """

    def __init__(
        self,
        *,
        run_id: str,
        bench_tsv: Path,
        prompt_filenames_by_variant: dict[str, str] | None = None,
        prompts_dir: Path | None = None,
    ):
        self.run_id = run_id
        self._lock = threading.Lock()
        bench_rows = _load_benchmark_rows(bench_tsv)
        self.bench_version = _bench_version(bench_tsv)
        self._bench_by_gene = {r["gene_symbol"]: r for r in bench_rows}
        variant_to_filename = prompt_filenames_by_variant or VARIANT_TO_PROMPT
        # Pre-load every prompt we might see — cheap (4 files, ~20KB each).
        prompts_dir = prompts_dir or PROMPTS_DIR
        self._prompts_by_variant: dict[str, PromptInfo] = {}
        for variant, fname in variant_to_filename.items():
            path = prompts_dir / fname
            if not path.exists():
                continue
            text = path.read_text()
            self._prompts_by_variant[variant] = PromptInfo(
                sha=_sha256(text),
                filename=fname,
                text=text,
                n_lines=len(text.splitlines()),
                schema_version=TRIAGE_SCHEMA_VERSION,
            )

        self._client = D1Client()
        # Intern prompts + benchmark snapshot once.
        for prompt in self._prompts_by_variant.values():
            _intern_prompt(self._client, prompt)
        _intern_benchmark(self._client, self.bench_version, bench_rows)
        # Reload the (run_id, …) key set so re-runs of the same sweep
        # don't double-insert.
        self._existing = _existing_keys(self._client, self.run_id)

        logger.info(
            "D1RunSink ready: run_id=%s bench_version=%s prompts=%d bench_rows=%d existing=%d",
            self.run_id, self.bench_version, len(self._prompts_by_variant),
            len(bench_rows), len(self._existing),
        )

    def insert(self, record: dict[str, Any]) -> bool:
        """Insert one per-cell record. Returns True on success / dedup-skip,
        False if the record was unprocessable. Never raises on D1
        failures — logs and returns False so the runner can keep going.
        """
        variant = record.get("variant")
        if variant not in self._prompts_by_variant:
            logger.warning("D1RunSink: unknown variant %r; skipping", variant)
            return False
        prompt = self._prompts_by_variant[variant]
        gene = record["gene_symbol"]
        bench_row = self._bench_by_gene.get(gene)
        uniprot_acc: str | None = bench_row.get("uniprot_acc") if bench_row else None
        truth_class: str = (
            bench_row.get("class", "") if bench_row else record.get("truth_class", "") or ""
        )
        key = (
            gene, record["model"], variant,
            int(record.get("replicate", 0)), prompt.sha,
        )
        with self._lock:
            if key in self._existing:
                return True
            self._existing.add(key)
        try:
            _insert_run(
                self._client,
                run_id=self.run_id,
                record=record,
                prompt_sha=prompt.sha,
                bench_version=self.bench_version,
                uniprot_acc=uniprot_acc,
                truth_class=truth_class,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            # Roll the dedup-key back so a retry can re-attempt.
            with self._lock:
                self._existing.discard(key)
            logger.warning("D1RunSink: insert failed for %s/%s/%s: %s",
                           gene, record["model"], variant, exc)
            return False

    def already_done(
        self,
        *,
        gene_symbol: str,
        model: str,
        variant: str,
        replicate: int,
    ) -> bool:
        """Has this exact cell already been inserted under our run_id?

        Lets the runner skip the API call entirely for cells that landed
        in a prior pass — important for genome-scale sweeps where a
        crash mid-run would otherwise re-pay for thousands of cells on
        restart. Mirrors the dedup logic in ``insert`` but uses no
        network — just the cached ``_existing`` set loaded at
        construction.
        """
        prompt = self._prompts_by_variant.get(variant)
        if prompt is None:
            return False
        key = (gene_symbol, model, variant, int(replicate), prompt.sha)
        with self._lock:
            return key in self._existing

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> D1RunSink:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


__all__ = ["PromptInfo", "D1RunSink"]
