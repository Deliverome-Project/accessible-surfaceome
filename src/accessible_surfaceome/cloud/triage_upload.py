"""Upload triage agent runs to the Cloudflare D1 ``surfaceome_agents`` database.

Walks ``data/eval/triage_subbench_v1/<model>/<variant>/<gene>_run<N>.json``
records, looks up each one's prompt SHA (interning new prompt versions
into ``prompt_version``), interns the benchmark snapshot into
``benchmark_version``, and inserts one row per record into ``triage_run``.

Idempotent on (run_id, model, variant, gene_symbol, replicate, prompt_sha):
existing rows with the same composite key are skipped. To force a re-upload,
DELETE the matching rows first or use ``--run-id <new_value>``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from accessible_surfaceome.paths import DATA_DIR, REPO_ROOT
from accessible_surfaceome.tools._shared.models import TRIAGE_SCHEMA_VERSION

from .d1_client import D1Client

logger = logging.getLogger(__name__)

PROMPTS_DIR = REPO_ROOT / "src" / "accessible_surfaceome" / "agents" / "surface_triage" / "prompts"
SUBBENCH_TSV = DATA_DIR / "eval" / "triage_subbench_v1.tsv"
SUBBENCH_RUNS = DATA_DIR / "eval" / "triage_subbench_v1"

# Maps the runner's variant slug → prompt filename. Keep in sync with
# scripts/triage_subbench_runner.py:VARIANTS.
VARIANT_TO_PROMPT = {
    "naive":     "system_naive.md",
    "ncbi":      "system.md",
    "web_naive": "system_web_naive.md",
    "web_ncbi":  "system_web.md",
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


def _load_prompt(variant: str) -> PromptInfo:
    fname = VARIANT_TO_PROMPT[variant]
    text = (PROMPTS_DIR / fname).read_text()
    return PromptInfo(
        sha=_sha256(text),
        filename=fname,
        text=text,
        n_lines=len(text.splitlines()),
        schema_version=TRIAGE_SCHEMA_VERSION,
    )


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

    * Labeled benchmark TSV (``triage_benchmark_v1.tsv``,
      ``triage_subbench_v1.tsv``): has uniprot_acc + class +
      ground_truth_* columns. Stored verbatim — the truth join from
      triage_run → benchmark_version returns the ground truth that was
      live at sweep time.

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
    d1.query(
        "INSERT INTO triage_run ("
        " run_id, gene_symbol, uniprot_acc, bench_version, model, prompt_variant,"
        " prompt_sha, schema_version, replicate, predicted_verdict, predicted_reason,"
        " verdict_reasoning, predicted_confidence, predicted_key_uncertainty,"
        " truth_verdict, truth_class, correct, prompt_tokens,"
        " completion_tokens, n_web_searches, cost_usd, latency_s, error, raw_text"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);",
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
            int(record.get("n_web_searches") or 0),
            float(record.get("cost_usd") or 0.0),
            float(record.get("latency_s") or 0.0),
            record.get("error"),
            record.get("raw_text") or None,
        ],
    )


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


def upload_subbench_runs(
    *,
    bench_tsv: Path = SUBBENCH_TSV,
    runs_root: Path = SUBBENCH_RUNS,
    run_id: str | None = None,
    dry_run: bool = False,
    since_mtime: float | None = None,
) -> dict[str, Any]:
    """Upload every per-cell JSON under ``runs_root`` to D1.

    Args:
        bench_tsv: TSV with ground-truth labels matching the runs.
        runs_root: directory containing ``<model>/<variant>/<gene>_run<N>.json``.
        run_id: tag to group this upload. Defaults to a fresh uuid.
        dry_run: print what would be uploaded, but don't insert.
        since_mtime: if set, skip per-cell record files modified before this
            POSIX timestamp. Lets you scope an upload to "the latest sweep"
            without manually pruning the records directory.

    Returns:
        Counters dict — int counts for ``prompts``, ``bench_rows``,
        ``runs_inserted``, ``runs_skipped``, plus the string fields
        ``run_id`` and ``bench_version`` used by this upload.
    """
    run_id = run_id or str(uuid.uuid4())
    bench_rows = _load_benchmark_rows(bench_tsv)
    bench_version = _bench_version(bench_tsv)
    bench_by_gene = {r["gene_symbol"]: r for r in bench_rows}

    # Pre-load prompts for every variant we'll see.
    prompts = {v: _load_prompt(v) for v in VARIANT_TO_PROMPT}

    # Collect every run record, filtered by mtime if --since was passed.
    # Skip directories whose names start with '_' (convention: backup /
    # archival snapshots of prior prompt versions, e.g.
    # ``_prev_naive_pre_gene_specific``). Those shouldn't go to D1 — they
    # were committed for diff-history not for re-ingestion.
    records: list[tuple[Path, dict[str, Any]]] = []
    n_skipped_by_since = 0
    n_skipped_by_backup_dir = 0
    for path in sorted(runs_root.rglob("*_run*.json")):
        if any(part.startswith("_") for part in path.relative_to(runs_root).parts):
            n_skipped_by_backup_dir += 1
            continue
        if since_mtime is not None and path.stat().st_mtime < since_mtime:
            n_skipped_by_since += 1
            continue
        try:
            records.append((path, json.loads(path.read_text())))
        except json.JSONDecodeError:
            logger.warning("skipping unreadable %s", path)
            continue

    if n_skipped_by_backup_dir:
        logger.info("backup-dir filter: skipped %d records under _*/ subdirs",
                    n_skipped_by_backup_dir)

    if since_mtime is not None:
        logger.info(
            "since filter: kept %d records, skipped %d older than %s",
            len(records), n_skipped_by_since,
            __import__("datetime").datetime.fromtimestamp(since_mtime).isoformat(),
        )

    if not records:
        logger.warning("no run records under %s", runs_root)
        return {"prompts": 0, "bench_rows": 0, "runs_inserted": 0, "runs_skipped": 0}

    if dry_run:
        return _summarize_dry(records, prompts, bench_version, bench_by_gene)

    counters: dict[str, Any] = {
        "prompts": 0, "bench_rows": 0,
        "runs_inserted": 0, "runs_skipped": 0,
    }
    with D1Client() as d1:
        # 1. intern prompt versions
        for prompt in prompts.values():
            _intern_prompt(d1, prompt)
            counters["prompts"] += 1

        # 2. intern benchmark snapshot
        _intern_benchmark(d1, bench_version, bench_rows)
        counters["bench_rows"] = len(bench_rows)

        # 3. find what's already in this run_id so we don't double-insert
        already = _existing_keys(d1, run_id)

        # 4. insert runs
        for path, rec in records:
            variant = rec.get("variant")
            if variant not in prompts:
                logger.warning("unknown variant %r in %s; skipping", variant, path)
                counters["runs_skipped"] += 1
                continue
            prompt = prompts[variant]
            bench_row = bench_by_gene.get(rec["gene_symbol"])
            uniprot_acc: str | None = bench_row.get("uniprot_acc") if bench_row else None
            truth_class: str = (
                bench_row.get("class", "") if bench_row else rec.get("truth_class", "") or ""
            )
            key = (
                rec["gene_symbol"], rec["model"], variant,
                int(rec.get("replicate", 0)), prompt.sha,
            )
            if key in already:
                counters["runs_skipped"] += 1
                continue
            _insert_run(
                d1,
                run_id=run_id,
                record=rec,
                prompt_sha=prompt.sha,
                bench_version=bench_version,
                uniprot_acc=uniprot_acc,
                truth_class=truth_class,
            )
            counters["runs_inserted"] += 1

    counters["run_id"] = run_id
    counters["bench_version"] = bench_version
    return counters


def _summarize_dry(
    records: list[tuple[Path, dict[str, Any]]],
    prompts: dict[str, PromptInfo],
    bench_version: str,
    bench_by_gene: dict[str, dict[str, str]],
) -> dict[str, int]:
    from collections import Counter
    by_variant = Counter(rec.get("variant") for _, rec in records)
    print("DRY RUN — would upload to D1")
    print(f"  bench_version: {bench_version}")
    print("  prompt SHAs to intern:")
    for v, p in prompts.items():
        print(f"    {v:10s} {p.filename:25s} sha={p.sha[:12]}…  ({p.n_lines} lines, {p.schema_version})")
    print(f"  total run records: {len(records)}")
    print("  by variant:")
    for v, n in by_variant.most_common():
        print(f"    {v:10s} {n}")
    print(f"  benchmark rows: {len(bench_by_gene)}")
    return {"prompts": len(prompts), "bench_rows": len(bench_by_gene),
            "runs_inserted": 0, "runs_skipped": 0, "would_insert": len(records)}


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

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> D1RunSink:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


__all__ = ["upload_subbench_runs", "PromptInfo", "D1RunSink"]
