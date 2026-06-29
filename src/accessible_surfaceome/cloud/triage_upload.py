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
from accessible_surfaceome.tools._shared.models import (
    TRIAGE_SCHEMA_VERSION,
    _REASONS_BY_VERDICT,
)

from .d1_client import D1Client

logger = logging.getLogger(__name__)


def _is_record_schema_valid(record: dict[str, Any]) -> bool:
    """Return True iff the ``(predicted_verdict, predicted_reason)``
    pair in ``record`` is consistent with the Pydantic
    ``TriageRecord._check_reason_matches_verdict`` validator.

    NULL verdicts (errored cells) are allowed through — those are
    legitimate failure rows the runner writes deliberately to record
    "we tried this gene and got nothing." A non-NULL verdict that's
    not in {yes, contextual, no} OR a verdict-reason mismatch is the
    failure mode we're guarding against.
    """
    v = record.get("predicted_verdict")
    if v is None:
        return True  # null verdict = errored cell; legitimate
    if v not in _REASONS_BY_VERDICT:
        return False  # verdict not in the closed enum
    r = record.get("predicted_reason")
    if r is None:
        return False  # verdict set but reason isn't — shouldn't happen
    return r in _REASONS_BY_VERDICT[v]

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


# Columns that DEFINE the curated benchmark — the ground truth a run is
# scored against. ``bench_version`` is the content hash of ONLY these
# columns, so it's stable across re-runs of
# ``scripts/tsv-export/augment_figure_tsvs_with_stable_ids.py`` (which rewrites the
# DERIVED columns — ``sonnet_verdict``, ``n_db_votes``, stable-IDs — in the
# same file from the genome sweep / candidate universe). Hashing the whole
# file would drift the version every time those derived columns refresh,
# even though the truth never changed. Order-independent + value-normalized
# so cosmetic column reordering or whitespace doesn't bump the version.
_BENCH_TRUTH_COLUMNS = (
    "gene_symbol",
    "uniprot_acc",
    "class",
    "ground_truth_verdict",
    "ground_truth_signal",
    "ground_truth_reason",
    "rationale",
)


def _bench_version(bench_tsv: Path) -> str:
    """Content-address the CURATED-TRUTH subset of the benchmark TSV.

    A bench_version that changes whenever the curated labels change (but
    NOT when derived/augmented columns refresh) lets us point old runs at
    the truth that was live then, and stays reproducible from the committed
    file regardless of augment state.
    """
    rows = _load_benchmark_rows(bench_tsv)
    # Canonical serialization: sort rows by gene_symbol, emit only the truth
    # columns in fixed order, tab-joined, newline-terminated.
    lines = []
    for r in sorted(rows, key=lambda x: x.get("gene_symbol", "")):
        lines.append("\t".join((r.get(c) or "") for c in _BENCH_TRUTH_COLUMNS))
    return _sha256("\n".join(lines))[:12]


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
    # Batched multi-row INSERT. A genome-wide gene-list is ~19k rows; one
    # INSERT per row over the D1 HTTP API is ~16 min of serial round-trips
    # BEFORE the first triage cell. 8 cols → 12 rows/batch keeps params
    # (96) under D1's ~100-bind limit, dropping the preamble to ~30s.
    cols = ("bench_version", "gene_symbol", "uniprot_acc", "class",
            "truth_verdict", "truth_signal", "truth_reason", "rationale")
    one = "(" + ",".join("?" * len(cols)) + ")"
    batch = 12
    for start in range(0, len(rows), batch):
        chunk = rows[start:start + batch]
        params: list[Any] = []
        for r in chunk:
            params += [
                bench_version,
                r["gene_symbol"],
                r.get("uniprot_acc", ""),
                r.get("class", ""),
                r.get("ground_truth_verdict", ""),
                r.get("ground_truth_signal", ""),
                r.get("ground_truth_reason", ""),
                r.get("rationale", ""),
            ]
        d1.query(
            f"INSERT OR IGNORE INTO benchmark_version ({', '.join(cols)}) "
            f"VALUES {', '.join([one] * len(chunk))};",
            params,
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
    hgnc_id: str | None = None,
    ensembl_gene: str | None = None,
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

    # Delete any prior row for this logical cell before inserting. triage_run
    # has no UNIQUE constraint on the natural key (only an autoincrement id),
    # so a resume that re-attempts a previously-ERRORED cell (now that
    # _existing_keys excludes null-verdict cells) would otherwise leave BOTH
    # the old null row and the new valid row. Deleting first makes the retry a
    # true replace — one row per (run_id, gene, model, variant, replicate,
    # prompt_sha). First-time inserts match nothing, so this is a no-op there.
    d1.query(
        "DELETE FROM triage_run WHERE run_id = ? AND gene_symbol = ? AND model = ? "
        "AND prompt_variant = ? AND replicate = ? AND prompt_sha = ?;",
        [run_id, record["gene_symbol"], record["model"], record["variant"],
         int(record.get("replicate", 0)), prompt_sha],
    )

    # SQLite RETURNING is supported on D1 (SQLite 3.35+). We need the new
    # row's id to write child rows in triage_search_log.
    rows = d1.query(
        "INSERT INTO triage_run ("
        " run_id, gene_symbol, uniprot_acc, hgnc_id, ensembl_gene,"
        " bench_version, model, prompt_variant,"
        " prompt_sha, schema_version, replicate, predicted_verdict, predicted_reason,"
        " verdict_reasoning, predicted_confidence, predicted_key_uncertainty,"
        " truth_verdict, truth_class, correct, prompt_tokens,"
        " completion_tokens, cache_creation_tokens, cache_read_tokens,"
        " n_web_searches, cost_usd, latency_s, error, raw_text,"
        " resolver_context_sha, temperature, top_p, max_tokens,"
        " api_response_id, api_stop_reason, api_model"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        " RETURNING id;",
        [
            run_id,
            record["gene_symbol"],
            uniprot_acc,
            hgnc_id,
            ensembl_gene,
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


# Columns the PUBLIC mirror (triage_run_public) carries. This is the
# whitelist — private-only columns (raw_text, resolver_context_sha,
# truth_verdict/class, api_*, temperature/top_p/max_tokens) are deliberately
# EXCLUDED so a direct public write can't leak them. `prompt_filename` is
# joined in from the prompt; `synced_at`/`id` are public-side defaults.
_PUBLIC_TRIAGE_COLUMNS = (
    "run_id", "gene_symbol", "uniprot_acc", "hgnc_id", "ensembl_gene",
    "bench_version", "model", "prompt_variant", "prompt_sha", "prompt_filename",
    "schema_version", "replicate", "predicted_verdict", "predicted_reason",
    "predicted_confidence", "predicted_key_uncertainty", "verdict_reasoning",
    "correct", "latency_s", "n_web_searches", "error",
    "cost_usd", "prompt_tokens", "completion_tokens",
    "cache_creation_tokens", "cache_read_tokens",
)


def _insert_run_public(
    pub: D1Client,
    *,
    run_id: str,
    record: dict[str, Any],
    prompt_sha: str,
    prompt_filename: str,
    bench_version: str,
    uniprot_acc: str | None,
    hgnc_id: str | None,
    ensembl_gene: str | None,
) -> None:
    """Insert ONE record directly into the public mirror, whitelisted.

    Mirrors what ``scripts/upload/sync_public_d1.py`` would push, but live as the
    sweep runs — for sweeps that want public-direct writes (e.g. the
    genome rerun). Only ``_PUBLIC_TRIAGE_COLUMNS`` cross over; raw_text and
    other private-only fields are never sent. Idempotent via OR REPLACE on
    the natural-key unique index, matching the sync script.
    """
    # created_at is NOT NULL in triage_run_public with no enforced default on
    # this binding, so set it explicitly to now() via a SQL literal (the
    # remaining columns are bound params).
    cols_sql = "created_at, " + ", ".join(_PUBLIC_TRIAGE_COLUMNS)
    placeholders = "datetime('now'), " + ",".join("?" * len(_PUBLIC_TRIAGE_COLUMNS))
    vals = [
        run_id,
        record["gene_symbol"],
        uniprot_acc,
        hgnc_id,
        ensembl_gene,
        bench_version,
        record["model"],
        record["variant"],
        prompt_sha,
        prompt_filename,
        TRIAGE_SCHEMA_VERSION,
        int(record.get("replicate", 0)),
        record.get("predicted_verdict"),
        record.get("predicted_reason"),
        record.get("predicted_confidence"),
        record.get("predicted_key_uncertainty"),
        record.get("verdict_reasoning") or "",
        1 if record.get("correct") else 0,
        float(record.get("latency_s") or 0.0),
        int(record.get("n_web_searches") or 0),
        record.get("error"),
        float(record.get("cost_usd") or 0.0),
        int(record.get("prompt_tokens") or 0),
        int(record.get("completion_tokens") or 0),
        int(record.get("cache_creation_tokens") or 0),
        int(record.get("cache_read_tokens") or 0),
    ]
    pub.query(
        f"INSERT OR REPLACE INTO triage_run_public "
        f"({cols_sql}) VALUES ({placeholders});",
        vals,
    )


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
    """Cells already DONE under this run_id — used by the runner's resume to
    skip them without re-paying for the API call.

    ONLY cells with a non-null ``predicted_verdict`` count as done. An errored
    cell (null verdict — transient API failure, parse failure, or a
    schema-mismatch that nulled out) is deliberately EXCLUDED so a resume
    re-attempts it. Counting errored cells as done was the issue-#48
    coverage-gap bug: a mid-run crash left those cells permanently errored,
    because the restart skipped them. For a genome-scale ~$200 sweep, a
    resume must converge to full coverage, so transient errors have to be
    retryable across restarts. (Structural resolver-fails — symbols with no
    reviewed human UniProt entry — will simply re-error each pass; that's
    correct and harmless, just a few wasted calls.)
    """
    rows = d1.query(
        "SELECT gene_symbol, model, prompt_variant, replicate, prompt_sha "
        "FROM triage_run WHERE run_id = ? AND predicted_verdict IS NOT NULL;",
        [run_id],
    )
    return {
        (r["gene_symbol"], r["model"], r["prompt_variant"], r["replicate"], r["prompt_sha"])
        for r in rows
    }


def _load_gene_identifier_map(
    d1: D1Client,
) -> dict[str, tuple[str | None, str | None, str | None]]:
    """Map gene_symbol → (uniprot_acc, hgnc_id, ensembl_gene) from the
    resolver's stable-ID cache (``gene_identifier``).

    Keyed by BOTH ``cohort_symbol`` and ``hgnc_symbol`` so a triage row's
    ``gene_symbol`` resolves the same way the HGNC-ID resolver + the D1
    backfill do (cohort_symbol wins on conflict — it's the symbol the
    genome/bench sweeps key on; hgnc_symbol covers the few rows stored
    canonically, e.g. ``MT-CO3``). One bulk read at sink construction; the
    ``insert`` hot path then does in-memory lookups and never re-resolves
    per cell. This is the sanctioned downstream path for stable IDs
    (CLAUDE.md "Gene identifier resolution": read ``gene_identifier``,
    never re-resolve from a bare symbol).
    """
    rows = d1.query(
        "SELECT hgnc_symbol, cohort_symbol, uniprot_acc, hgnc_id, ensembl_gene "
        "FROM gene_identifier;",
        [],
    )
    out: dict[str, tuple[str | None, str | None, str | None]] = {}
    for r in rows:  # hgnc_symbol first …
        if r.get("hgnc_symbol"):
            out[r["hgnc_symbol"]] = (
                r.get("uniprot_acc"), r.get("hgnc_id"), r.get("ensembl_gene"),
            )
    for r in rows:  # … cohort_symbol overrides (the sweep's key)
        if r.get("cohort_symbol"):
            out[r["cohort_symbol"]] = (
                r.get("uniprot_acc"), r.get("hgnc_id"), r.get("ensembl_gene"),
            )
    return out


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
        publish_public: bool = False,
    ):
        self.run_id = run_id
        # When True, each successful private insert is ALSO written to the
        # public mirror (triage_run_public) live, whitelisted — for sweeps
        # that want results in public as they land (e.g. the genome rerun)
        # without a separate sync step. Private D1 stays the full-fidelity
        # source of truth; only _PUBLIC_TRIAGE_COLUMNS cross over.
        self.publish_public = publish_public
        self._pub_client: D1Client | None = None
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
        if self.publish_public:
            # Read-only-by-convention helper points at the public mirror UUID;
            # we use it to write the whitelisted public row live.
            self._pub_client = D1Client.public()
        # Resolver stable-ID cache (uniprot/hgnc_id/ensembl_gene) loaded once,
        # so insert() persists the SAME identifiers the HGNC-ID resolver
        # produces — not the bench-pinned uniprot, and with hgnc_id +
        # ensembl_gene that the runner previously discarded.
        self._ids_by_symbol = _load_gene_identifier_map(self._client)
        # Intern prompts + benchmark snapshot once.
        for prompt in self._prompts_by_variant.values():
            _intern_prompt(self._client, prompt)
        # Only intern into benchmark_version for a LABELED curated benchmark
        # (rows carry ground_truth_verdict). An unlabeled genome-wide
        # gene-list (~19k rows, no truth columns) should NOT be written to
        # benchmark_version — that table is the curated-truth store, the rows
        # would be empty-truth noise, and the serial intern was a ~16-min
        # preamble before the first triage cell. The triage_run rows still
        # carry the gene-list's bench_version for provenance; nothing
        # downstream joins the genome sweep on benchmark_version.
        is_labeled = any(
            (r.get("ground_truth_verdict") or "").strip() for r in bench_rows
        )
        if is_labeled:
            _intern_benchmark(self._client, self.bench_version, bench_rows)
        else:
            logger.info(
                "D1RunSink: input is an unlabeled gene-list (%d rows, no "
                "ground_truth_verdict) — skipping benchmark_version intern.",
                len(bench_rows),
            )
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
        # Belt-and-suspenders: refuse to persist a record whose
        # (verdict, reason) pair violates the Pydantic
        # TriageRecord._check_reason_matches_verdict validator. The
        # runner's _run_one_with_retry should already null these out on
        # persistent invalidity (scripts/triage_runner.py), but the
        # 2026-05-12 mainbench sweep showed what happens when that leg
        # is missing — 15 invalid rows past the schema. Catching it
        # here too means a future runner that forgets the check still
        # can't write invalid combos to D1.
        if not _is_record_schema_valid(record):
            logger.warning(
                "D1RunSink: refusing schema-invalid record for %s/%s/%s "
                "(verdict=%r, reason=%r); writing NULL fields would lose "
                "the row entirely, so skipping the INSERT — fix the runner.",
                record.get("gene_symbol"), record.get("model"), variant,
                record.get("predicted_verdict"), record.get("predicted_reason"),
            )
            return False
        prompt = self._prompts_by_variant[variant]
        gene = record["gene_symbol"]
        bench_row = self._bench_by_gene.get(gene)
        # Stable IDs from the resolver cache (preferred). Fall back to the
        # bench-pinned uniprot only for genes absent from gene_identifier
        # (readthrough/fusion symbols etc.); hgnc_id / ensembl_gene have no
        # bench fallback and stay NULL there.
        res_uniprot, res_hgnc, res_ensembl = self._ids_by_symbol.get(
            gene, (None, None, None)
        )
        uniprot_acc: str | None = res_uniprot or (
            bench_row.get("uniprot_acc") if bench_row else None
        )
        hgnc_id: str | None = res_hgnc
        ensembl_gene: str | None = res_ensembl
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
                hgnc_id=hgnc_id,
                ensembl_gene=ensembl_gene,
                truth_class=truth_class,
            )
        except Exception as exc:  # noqa: BLE001
            # Roll the dedup-key back so a retry can re-attempt.
            with self._lock:
                self._existing.discard(key)
            logger.warning("D1RunSink: insert failed for %s/%s/%s: %s",
                           gene, record["model"], variant, exc)
            return False
        # Live public-mirror write (whitelisted). Best-effort: a public
        # failure does NOT fail the cell — private already has the
        # full-fidelity row, and sync_public_d1.py can backfill later.
        if self.publish_public and self._pub_client is not None:
            try:
                _insert_run_public(
                    self._pub_client,
                    run_id=self.run_id,
                    record=record,
                    prompt_sha=prompt.sha,
                    prompt_filename=prompt.filename,
                    bench_version=self.bench_version,
                    uniprot_acc=uniprot_acc,
                    hgnc_id=hgnc_id,
                    ensembl_gene=ensembl_gene,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("D1RunSink: PUBLIC insert failed for %s/%s/%s: %s "
                               "(private row OK; sync_public_d1 can backfill)",
                               gene, record["model"], variant, exc)
        return True

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
        if self._pub_client is not None:
            self._pub_client.close()

    def __enter__(self) -> D1RunSink:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


__all__ = ["PromptInfo", "D1RunSink"]
