"""Per-cell runner for the triage-bench eval.

A "cell" is one (variant, model) combination. The runner walks every
benchmark protein, invokes the variant for each, and persists a per-run
record under
``data/eval/triage_bench_v1/<cell_label>/<gene>.json``.

Per-run record shape:

* ``triage_draft``: the variant's emitted ``TriageRecordDraft`` dict (or
  None if it failed to produce one).
* ``ground_truth_verdict`` / ``ground_truth_signal``: from the benchmark.
* ``correct_verdict`` / ``correct_signal``: bools.
* ``cost_usd``, ``latency_s``, ``prompt_tokens``, ``completion_tokens``,
  ``n_tool_calls``: telemetry.

Records are written one-at-a-time so a partial run is reusable; the
runner skips proteins whose record already exists unless ``force=True``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents._support import client as _client_module
from accessible_surfaceome.paths import DATA_DIR
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client

from .benchmark import BenchmarkRow, load_benchmark
from .variant_a_no_tools import (
    load_triage_system_prompt,
    run_variant_a,
)
from .variant_b_deterministic import run_variant_b

logger = logging.getLogger(__name__)

EVAL_ROOT = DATA_DIR / "eval" / "triage_bench_v1"


@dataclass
class CellSpec:
    """One (variant, model) cell to run across the benchmark."""

    variant: str  # "A" | "B" | "C" | "D"
    model: str | None  # None for variant B
    label: str  # filesystem-friendly cell label

    @property
    def cell_dir(self) -> Path:
        return EVAL_ROOT / self.label


def cell_spec(variant: str, model: str | None) -> CellSpec:
    label = variant if model is None else f"{variant}_{_compact_model_name(model)}"
    return CellSpec(variant=variant, model=model, label=label)


def _compact_model_name(model: str) -> str:
    return (
        model.replace("claude-", "")
        .replace("anthropic-", "")
        .replace("-20251001", "")
        .replace("/", "-")
    )


def run_cell(
    cell: CellSpec,
    *,
    benchmark: list[BenchmarkRow] | None = None,
    force: bool = False,
    only_gene: str | None = None,
) -> dict[str, Any]:
    """Run a single cell across the benchmark.

    ``only_gene`` limits to one protein (for smoke-testing). Returns a
    dict with ``cell_label``, ``n_runs``, ``n_correct_verdict``,
    ``n_correct_signal``, ``total_cost_usd``.
    """

    benchmark = benchmark or load_benchmark()
    cell.cell_dir.mkdir(parents=True, exist_ok=True)

    rows = [r for r in benchmark if only_gene is None or r.gene_symbol == only_gene]
    if not rows:
        raise ValueError(f"benchmark filter only_gene={only_gene!r} matched 0 rows")

    n_runs = 0
    n_correct_verdict = 0
    n_correct_signal = 0
    total_cost = 0.0

    for row in rows:
        out_path = cell.cell_dir / f"{row.gene_symbol}.json"
        if out_path.exists() and not force:
            logger.info("skip %s/%s (exists; pass force=True to redo)", cell.label, row.gene_symbol)
            data = json.loads(out_path.read_text())
        else:
            data = _run_one(cell=cell, row=row)
            out_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

        n_runs += 1
        if data.get("correct_verdict"):
            n_correct_verdict += 1
        if data.get("correct_signal"):
            n_correct_signal += 1
        total_cost += float(data.get("cost_usd") or 0.0)

    return {
        "cell_label": cell.label,
        "variant": cell.variant,
        "model": cell.model,
        "n_runs": n_runs,
        "n_correct_verdict": n_correct_verdict,
        "n_correct_signal": n_correct_signal,
        "verdict_accuracy": (n_correct_verdict / n_runs) if n_runs else 0.0,
        "signal_accuracy": (n_correct_signal / n_runs) if n_runs else 0.0,
        "total_cost_usd": total_cost,
    }


def _run_one(*, cell: CellSpec, row: BenchmarkRow) -> dict[str, Any]:
    """Dispatch by variant; return the per-run record dict."""

    started = time.monotonic()
    if cell.variant == "A":
        if cell.model is None:
            raise ValueError("variant A requires a model")
        return _run_one_variant_a(cell=cell, row=row, started=started)
    if cell.variant == "B":
        return _run_one_variant_b(row=row, started=started)
    raise NotImplementedError(f"variant {cell.variant!r} not implemented yet")


def _run_one_variant_a(*, cell: CellSpec, row: BenchmarkRow, started: float) -> dict[str, Any]:
    client = _client_module.get_client()
    system_prompt = load_triage_system_prompt()
    draft, telemetry = run_variant_a(
        gene_symbol=row.gene_symbol,
        model=cell.model or "",
        system_prompt=system_prompt,
        client=client,
    )
    record = _envelope(
        cell=cell,
        row=row,
        draft=draft,
        cost_usd=telemetry.cost_usd,
        latency_s=telemetry.latency_s,
        prompt_tokens=telemetry.prompt_tokens,
        completion_tokens=telemetry.completion_tokens,
        n_tool_calls=0,
    )
    record["raw_response"] = telemetry.raw_response
    return record


def _run_one_variant_b(*, row: BenchmarkRow, started: float) -> dict[str, Any]:
    http = open_default_client()
    try:
        draft, telemetry = run_variant_b(
            gene_symbol=row.gene_symbol,
            uniprot_acc=row.uniprot_acc,
            hgnc_id=None,
            http=http,
        )
    finally:
        http.close()
    record = _envelope(
        cell=cell_spec("B", None),
        row=row,
        draft=draft,
        cost_usd=0.0,
        latency_s=telemetry.latency_s,
        prompt_tokens=0,
        completion_tokens=0,
        n_tool_calls=0,
    )
    record["surface_hits"] = telemetry.surface_hits
    record["total_hits"] = telemetry.total_hits
    record["surface_fraction"] = telemetry.surface_fraction
    return record


def _envelope(
    *,
    cell: CellSpec,
    row: BenchmarkRow,
    draft: dict[str, Any] | None,
    cost_usd: float,
    latency_s: float,
    prompt_tokens: int,
    completion_tokens: int,
    n_tool_calls: int,
) -> dict[str, Any]:
    """Standard per-run record shape — same fields across all variants."""

    if draft is None:
        verdict = None
        signal = None
    else:
        verdict = draft.get("verdict")
        signal = draft.get("accessibility_signal")

    return {
        "cell_label": cell.label,
        "variant": cell.variant,
        "model": cell.model,
        "gene_symbol": row.gene_symbol,
        "uniprot_acc": row.uniprot_acc,
        "class": row.class_,
        "ground_truth_verdict": row.ground_truth_verdict,
        "ground_truth_signal": row.ground_truth_signal,
        "emitted_verdict": verdict,
        "emitted_signal": signal,
        "correct_verdict": verdict == row.ground_truth_verdict if verdict else False,
        "correct_signal": signal == row.ground_truth_signal if signal else False,
        "cost_usd": cost_usd,
        "latency_s": latency_s,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "n_tool_calls": n_tool_calls,
        "triage_draft": draft,
    }


def open_http_for_variant_b() -> CachedHTTP:
    """Public helper for callers that want to share an HTTP client across runs."""

    return open_default_client()


__all__ = ["CellSpec", "cell_spec", "run_cell", "EVAL_ROOT"]
