"""Run the v1.0.0 deep-dive orchestrator across a curated stress-test set.

Sequential by design: each gene's run already spawns A1∥A2 in parallel
inside the orchestrator, so we don't fan out at this layer — that would
multiply the Anthropic-API rate-limit pressure without buying much
wall-clock back.

Writes ``data/eval/v1_cost_stress_test/{gene}.json`` per gene with the
table-ready stats, plus a top-level ``summary.json``.

Usage:

    uv run python scripts/v1_cost_stress_test.py            # run all 7
    uv run python scripts/v1_cost_stress_test.py EGFR CD81  # subset
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from accessible_surfaceome.agents import surfaceome_v1
from accessible_surfaceome.env import load_env


STRESS_GENES = [
    "EGFR",     # well-studied baseline
    "HSPA5",    # ER↔PM cycling, DB disagreement
    "GPR75",    # orphan GPCR, sparse evidence
    "CALR",     # sibling-filter case (CD47 cross-misfire)
    "GPRC5D",   # sibling-filter case (BCMA cross-misfire)
    "CD81",     # tetraspanin, minimal ECD loops
    "TNFR1",    # shed receptor with soluble pool
]

OUT_DIR = Path("data/eval/v1_cost_stress_test")


def _percent_anchored(annotation_path: Path) -> tuple[int, float | None]:
    """Read the assembled record JSON, return (n_evidence, pct_anchored).

    ``entailment_verified`` on each Evidence is the substring-anchor flag set
    by ``promote_claim`` — True when the quote substring-matched into the
    shared SourceTextStore.
    """
    data = json.loads(annotation_path.read_text())
    evidence = data.get("evidence", []) or []
    if not evidence:
        return 0, None
    n_anchored = sum(1 for e in evidence if e.get("entailment_verified"))
    return len(evidence), 100.0 * n_anchored / len(evidence)


def run_one(gene: str) -> dict[str, object]:
    """Run the orchestrator on one gene and return a one-row stats dict.

    Catches all exceptions — a single gene failing should not abort the
    sweep. The error is recorded in the row.
    """
    t0 = time.time()
    try:
        result = surfaceome_v1.annotate(gene)
    except Exception as exc:  # noqa: BLE001 — sweep-level robustness
        elapsed = time.time() - t0
        logging.exception("annotate(%s) raised", gene)
        return {
            "gene": gene,
            "error": f"exception: {type(exc).__name__}: {exc}",
            "elapsed_s": round(elapsed, 1),
        }
    elapsed = time.time() - t0

    n_evidence, pct_anchored = (None, None)
    if result.annotation_path is not None and result.annotation_path.exists():
        n_evidence, pct_anchored = _percent_anchored(result.annotation_path)

    a1 = result.a1
    a2 = result.a2
    b = result.b
    return {
        "gene": result.gene,
        "error": result.error,
        "elapsed_s": round(elapsed, 1),
        "annotation_path": str(result.annotation_path) if result.annotation_path else None,
        "a1_cost_usd": round(result.a1_cost_usd, 6),
        "a2_cost_usd": round(result.a2_cost_usd, 6),
        "b_cost_usd": round(result.b_cost_usd, 6),
        "total_cost_usd": round(result.total_cost_usd, 6),
        "a1_tool_calls": a1.n_tool_calls if a1 else None,
        "a2_tool_calls": a2.n_tool_calls if a2 else None,
        "a1_repair_attempts": a1.n_repair_attempts if a1 else None,
        "a2_repair_attempts": a2.n_repair_attempts if a2 else None,
        "b_repair_attempts": b.n_repair_attempts if b else None,
        "a1_input_tokens": a1.usage.input_tokens if a1 else None,
        "a1_output_tokens": a1.usage.output_tokens if a1 else None,
        "a2_input_tokens": a2.usage.input_tokens if a2 else None,
        "a2_output_tokens": a2.usage.output_tokens if a2 else None,
        "b_input_tokens": b.usage.input_tokens if b else None,
        "b_output_tokens": b.usage.output_tokens if b else None,
        "evidence_count": n_evidence,
        "pct_substring_anchored": round(pct_anchored, 1) if pct_anchored is not None else None,
    }


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    args = argv if argv is not None else sys.argv[1:]
    genes = args or STRESS_GENES

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for gene in genes:
        print(f"\n=== stress-test: {gene} ({genes.index(gene) + 1}/{len(genes)}) ===", flush=True)
        row = run_one(gene)
        rows.append(row)
        (OUT_DIR / f"{gene}.json").write_text(json.dumps(row, indent=2))
        print(json.dumps(row, indent=2), flush=True)

    summary = {
        "genes": genes,
        "rows": rows,
        "total_cost_usd": round(
            sum(r.get("total_cost_usd") or 0.0 for r in rows), 4  # type: ignore[arg-type]
        ),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n=== sweep done — total spend: ${summary['total_cost_usd']:.4f} ===")
    print(f"summary: {OUT_DIR / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
