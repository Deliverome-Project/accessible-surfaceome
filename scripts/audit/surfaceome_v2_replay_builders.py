#!/usr/bin/env python
"""Builders+synth replay from cached D1 intermediates.

Reconstructs a :class:`DualPlanTrimSelectResult` from the most recent
intermediates blob (claims + bundle + assorted metadata), then calls
``annotate(cached_dual=...)`` so the orchestrator runs everything
EXCEPT plan-trim-select: methods + grade + expression + modulation +
subloc + anatomical + contradictions + risks + biological_context_grade
builders, then synth, then orchestrator post-passes, then assembly.

Cost: ~$0.65/iteration vs ~$2 for a full annotate. Useful when the
prompt change is in a builder OR the synthesizer (or both) and you
don't want to re-pay for retrieval (~70% of per-gene cost).

NOT useful for prompt changes UPSTREAM of the builders (search planner,
trim filter, abstract triage, selector) — those run inside plan-trim-
select, which this driver skips.

Usage:
    uv run python scripts/surfaceome_v2_replay_builders.py TGOLN2

    # Pin to a specific intermediates timestamp:
    uv run python scripts/surfaceome_v2_replay_builders.py TGOLN2 \\
        --at 2026-06-08T15:15

    # Publish the resulting record to public D1 (default: just print):
    uv run python scripts/surfaceome_v2_replay_builders.py TGOLN2 --publish
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from accessible_surfaceome.agents.plan_trim_select.runner import (
    DualPlanTrimSelectResult,
)
from accessible_surfaceome.agents.surfaceome_v2.a1_recovery import (
    reconstruct_dual_from_blob,
)
from accessible_surfaceome.agents.surfaceome_v2.orchestrator import annotate
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env


def _load_intermediates(
    gene_symbol: str, at: str | None = None
) -> dict[str, Any]:
    with D1Client(D1Config.from_env()) as c:
        if at:
            rows = c.query(
                "SELECT intermediates_json FROM agent_run_intermediates "
                "WHERE gene_symbol = ? AND created_at LIKE ? "
                "ORDER BY created_at DESC LIMIT 1",
                [gene_symbol, f"{at}%"],
            )
        else:
            rows = c.query(
                "SELECT intermediates_json FROM agent_run_intermediates "
                "WHERE gene_symbol = ? ORDER BY created_at DESC LIMIT 1",
                [gene_symbol],
            )
    if not rows:
        raise SystemExit(f"No intermediates row for {gene_symbol}")
    return json.loads(rows[0]["intermediates_json"])


def _reconstruct_dual(blob: dict[str, Any]) -> DualPlanTrimSelectResult:
    """Reconstruct a :class:`DualPlanTrimSelectResult` from intermediates.

    Delegates to :func:`a1_recovery.reconstruct_dual_from_blob` — the single
    source of truth for the reconstruction shape — so this driver and the
    A1-recovery backfill can never drift. (The previous inline copy passed a
    removed ``cost_usd`` kwarg and omitted the now-required ``plan`` /
    ``selection_response`` fields, so it raised ``TypeError`` on every gene.)
    """
    return reconstruct_dual_from_blob(blob)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gene", help="Gene symbol")
    parser.add_argument(
        "--at", help="Intermediates timestamp prefix (e.g. 2026-06-08T15:15)"
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Push the resulting record to public D1 (default: print only)",
    )
    args = parser.parse_args()

    load_env()
    blob = _load_intermediates(args.gene, args.at)
    dual = _reconstruct_dual(blob)
    # reconstruct_dual_from_blob raises when the bundle is absent, so it is
    # non-None here — assert narrows the type for the accesses below.
    assert dual.bundle is not None
    print(
        f"=== {args.gene}: replay from cached dual ===\n"
        f"  A1 claims: {len(dual.a1.claims)}  A2 claims: {len(dual.a2.claims)}\n"
        f"  bundle:    {dual.bundle.hgnc_symbol} → {dual.bundle.uniprot_acc}\n"
    )

    result = annotate(args.gene, cached_dual=dual, persist=args.publish)
    if result.record is None:
        print(f"FAILED: {result.error}")
        return 1
    es = result.record.executive_summary
    se = result.record.surface_evidence
    print(
        f"  sa={es.surface_accessibility:8} "
        f"state={es.state_dependence:10} "
        f"reason={es.surface_call_reason:28} "
        f"grade={se.evidence_grade:24} "
        f"conf={result.record.confidence:10}\n"
        f"  cost (builders+synth, no plan-trim-select): ${result.total_cost_usd:.3f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
