"""Run the sequential dual plan→trim→select (A1 then A2) for one gene.

Out-of-band evaluator — does NOT wire into surfaceome_v1.annotate. The
point is to confirm A1+A2 prompt specialization produces a richer ledger
than the unified MVP path before promoting either into the orchestrator.

Usage:

    uv run python scripts/plan_trim_select_dual_run.py HGNC:4526
    uv run python scripts/plan_trim_select_dual_run.py Q9BPV8
    uv run python scripts/plan_trim_select_dual_run.py GPR75   # symbol → needs D1

Writes ``.runs/plan_trim_select_<id>_dual.json`` with the A1 + A2
sub-results stitched together so the QC HTML renderer can show both
ledgers side-by-side.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from accessible_surfaceome.agents.plan_trim_select import (
    PlanTrimSelectResult,
    run_plan_trim_select_dual,
)
from accessible_surfaceome.env import load_env


def _result_to_jsonable(result: PlanTrimSelectResult) -> dict:
    return {
        "gene": result.gene,
        "agent_focus": result.agent_focus,
        "uniprot_acc": result.bundle.uniprot_acc if result.bundle else None,
        "bundle": result.bundle.model_dump(mode="json") if result.bundle else None,
        "elapsed_s": result.elapsed_s,
        "n_iterations_run": result.n_iterations_run,
        "iteration_log": [asdict(e) for e in result.iteration_log],
        "n_drafts_total": result.n_drafts_total,
        "n_papers_total": result.n_papers_total,
        "n_kept_after_trim": result.n_kept_after_trim,
        "n_claims": result.n_claims,
        "n_anchored": result.n_anchored,
        "pct_anchored": result.pct_anchored,
        "warnings": result.warnings,
        "plan": result.plan.model_dump() if result.plan else None,
        "search_log": [asdict(s) for s in result.search_log],
        "selection_response": (
            result.selection_response.model_dump()
            if result.selection_response
            else None
        ),
        "claims": [c.model_dump() for c in result.claims],
        "usage": {
            "plan": {
                "n_iterations": result.plan_usage.n_iterations,
                "input_tokens": result.plan_usage.input_tokens,
                "output_tokens": result.plan_usage.output_tokens,
                "cost_usd": result.plan_usage.cost_usd,
            },
            "trim": {
                "n_iterations": result.trim_usage.n_iterations,
                "input_tokens": result.trim_usage.input_tokens,
                "output_tokens": result.trim_usage.output_tokens,
                "cost_usd": result.trim_usage.cost_usd,
            },
            "select": {
                "n_iterations": result.select_usage.n_iterations,
                "input_tokens": result.select_usage.input_tokens,
                "output_tokens": result.select_usage.output_tokens,
                "cost_usd": result.select_usage.cost_usd,
            },
            "total_cost_usd": round(result.total_cost_usd, 4),
        },
    }


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("gene", help="Gene symbol / HGNC ID / UniProt acc")
    args = parser.parse_args(argv)

    print(f"=== plan_trim_select_dual: {args.gene} ===", flush=True)
    dual = run_plan_trim_select_dual(args.gene)

    safe_id = args.gene.replace(":", "_")
    out_path = Path(f".runs/plan_trim_select_{safe_id}_dual.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "gene": dual.gene,
                "uniprot_acc": dual.bundle.uniprot_acc if dual.bundle else None,
                "bundle": dual.bundle.model_dump(mode="json") if dual.bundle else None,
                "elapsed_s": dual.elapsed_s,
                "total_cost_usd": round(dual.total_cost_usd, 4),
                "total_claims": dual.total_claims,
                "total_anchored": dual.total_anchored,
                "pct_anchored": dual.pct_anchored,
                "a1": _result_to_jsonable(dual.a1),
                "a2": _result_to_jsonable(dual.a2),
            },
            indent=2,
        )
    )

    print()
    print(f"gene:             {dual.gene}")
    print(f"uniprot_acc:      {dual.bundle.uniprot_acc if dual.bundle else '<unresolved>'}")
    print(f"elapsed:          {dual.elapsed_s}s")
    print(f"total claims:     {dual.total_claims}  ({dual.a1.n_claims} A1 + {dual.a2.n_claims} A2)")
    pct = dual.pct_anchored
    print(
        f"anchored:         {dual.total_anchored}/{dual.total_claims} "
        f"({pct:.1f}%)" if pct is not None else "  (no claims)"
    )
    print(f"total spend:      ${dual.total_cost_usd:.4f}  "
          f"(A1 ${dual.a1.total_cost_usd:.4f} + A2 ${dual.a2.total_cost_usd:.4f})")

    for label, sub in (("A1 (surface evidence)", dual.a1), ("A2 (biological context)", dual.a2)):
        print()
        print(f"--- {label} ---")
        print(f"  claims:            {sub.n_claims}  (anchored "
              f"{sub.n_anchored}/{sub.n_claims}, "
              f"{sub.pct_anchored:.1f}%)" if sub.pct_anchored is not None else "  (no claims)")
        print(f"  iterations:        {sub.n_iterations_run}")
        print(f"  drafts pooled:     {sub.n_drafts_total} across {sub.n_papers_total} papers")
        print(f"  kept after trim:   {sub.n_kept_after_trim}")
        if sub.claims:
            ct_counts = Counter(c.claim_type for c in sub.claims)
            tier_counts = Counter(c.evidence_tier for c in sub.claims)
            print(f"  claim_type:        {dict(ct_counts)}")
            print(f"  evidence_tier:     {dict(tier_counts)}")

    if dual.a1.warnings or dual.a2.warnings:
        print()
        print("--- warnings ---")
        for w in dual.a1.warnings:
            print(f"  A1: {w}")
        for w in dual.a2.warnings:
            print(f"  A2: {w}")

    print()
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
