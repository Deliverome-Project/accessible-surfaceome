"""Run the plan → trim → select agent against one gene and dump a JSON report.

Out-of-band evaluator — does NOT wire into surfaceome_v1.annotate. The point
is to compare anchored-rate + cost + claim quality against A1's output on
the same gene before deciding to wire it in.

Usage:

    uv run python scripts/plan_trim_select_run.py GPR75
    uv run python scripts/plan_trim_select_run.py EGFR

Writes ``.runs/plan_trim_select_<gene>.json`` with:
* The full SearchPlan + SelectionResponse the agents emitted
* The search log (one entry per dispatched search)
* The promoted EvidenceClaim list
* Per-stage usage + cost
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from accessible_surfaceome.agents.plan_trim_select import run_plan_trim_select
from accessible_surfaceome.env import load_env


def _result_to_jsonable(result) -> dict:
    return {
        "gene": result.gene,
        "uniprot_acc": result.bundle.uniprot_acc if result.bundle else None,
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
    parser.add_argument("gene", help="Gene symbol (e.g. GPR75)")
    args = parser.parse_args(argv)

    print(f"=== plan_trim_select: {args.gene} ===", flush=True)
    result = run_plan_trim_select(args.gene)

    out_path = Path(f".runs/plan_trim_select_{args.gene}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_result_to_jsonable(result), indent=2))

    print()
    print(f"gene:                   {result.gene}")
    print(f"uniprot_acc:            {result.bundle.uniprot_acc if result.bundle else '<unresolved>'}")
    print(f"elapsed:                {result.elapsed_s}s")
    print(f"iterations run:         {result.n_iterations_run}")
    print(f"searches planned:       {len(result.plan.searches) if result.plan else 0} (initial)")
    print(f"drafts pooled:          {result.n_drafts_total}")
    print(f"papers in pool:         {result.n_papers_total}")
    print(f"kept after Haiku trim:  {result.n_kept_after_trim} (final iteration)")
    print(f"claims selected:        {result.n_claims}")

    if result.iteration_log:
        print()
        print("--- iteration log ---")
        for e in result.iteration_log:
            print(
                f"  iter {e.iteration}: +{e.new_searches} searches → +{e.new_drafts} drafts "
                f"(pool: {e.n_drafts_after}/{e.n_papers_after}) | "
                f"trim kept {e.n_kept_after_trim} | "
                f"selected {e.n_selections} | "
                f"more={'YES' if e.needs_more_searches else 'no'}"
            )
    print(f"% substring-anchored:   "
          f"{result.pct_anchored:.1f}%" if result.pct_anchored is not None else "  (no claims)")
    print()
    print("--- per-stage cost ---")
    print(f"plan   (Sonnet): ${result.plan_usage.cost_usd:.4f}  "
          f"({result.plan_usage.input_tokens}in / {result.plan_usage.output_tokens}out)")
    print(f"trim   (Haiku):  ${result.trim_usage.cost_usd:.4f}  "
          f"({result.trim_usage.input_tokens}in / {result.trim_usage.output_tokens}out, "
          f"{result.trim_usage.n_iterations} calls)")
    print(f"select (Sonnet): ${result.select_usage.cost_usd:.4f}  "
          f"({result.select_usage.input_tokens}in / {result.select_usage.output_tokens}out)")
    print(f"TOTAL:           ${result.total_cost_usd:.4f}")

    if result.claims:
        ct_counts = Counter(c.claim_type for c in result.claims)
        et_counts = Counter(c.evidence_type for c in result.claims)
        tier_counts = Counter(c.evidence_tier for c in result.claims)
        sources = Counter(c.source_id for c in result.claims)
        print()
        print("--- claim breakdown ---")
        print(f"claim_type:    {dict(ct_counts)}")
        print(f"evidence_type: {dict(et_counts)}")
        print(f"evidence_tier: {dict(tier_counts)}")
        print(f"sources ({len(sources)} unique):")
        for sid, n in sources.most_common():
            print(f"  {sid}: {n}")

    if result.warnings:
        print()
        print("--- warnings ---")
        for w in result.warnings:
            print(f"  {w}")

    print()
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
