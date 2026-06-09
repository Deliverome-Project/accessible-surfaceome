#!/usr/bin/env python
"""Builders+synth replay from cached D1 intermediates.

Reconstructs a :class:`DualPlanTrimSelectResult` from the most recent
intermediates blob (claims + bundle + assorted metadata), then calls
``annotate(cached_dual=...)`` so the orchestrator runs everything
EXCEPT plan-trim-select: methods + grade + expression + modulation +
subloc + anatomical + contradictions + risks + biological_context_grade
builders, then synth, then orchestrator post-passes, then assembly.

Cost: ~\$0.65/iteration vs ~\$2 for a full annotate. Useful when the
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
    PlanTrimSelectResult,
)
from accessible_surfaceome.agents.surfaceome_v2.orchestrator import annotate
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.models import (
    EvidenceClaim,
    IdentifierBundle,
)


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

    The orchestrator's ``_annotate`` accesses ``dual.bundle``,
    ``dual.a1``, ``dual.a2``, ``dual.total_cost_usd``,
    ``dual.elapsed_s`` — populate enough of each for the downstream
    pipeline to run. Drafts are reconstructed from the persisted
    claim lists. Cost/elapsed are zero (this is a replay, no
    plan-trim-select cost incurred).
    """
    pts = blob.get("plan_trim_select", {})
    bundle_dict = blob.get("bundle")
    if not bundle_dict:
        raise SystemExit(
            "intermediates blob has no 'bundle' — too old for builders-"
            "replay (bundle persistence landed in v2.34). Re-run the "
            "annotate at least once to refresh."
        )
    bundle = IdentifierBundle.model_validate(bundle_dict)

    def _side(side_blob: dict[str, Any]) -> PlanTrimSelectResult:
        claims = [
            EvidenceClaim.model_validate(c) for c in side_blob.get("claims") or []
        ]
        # PlanTrimSelectResult is a dataclass with many fields; populate
        # the ones the orchestrator reads, defaulting the rest.
        return PlanTrimSelectResult(
            gene=blob.get("gene") or "<unknown>",
            agent_focus=side_blob.get("agent_focus") or "a1",
            bundle=bundle,
            claims=claims,
            search_log=[],          # stripped by slim; ok for replay
            iteration_log=[],
            triage_actions=[],
            pretrim_audits=[],
            n_claims=len(claims),
            n_anchored=side_blob.get("n_anchored") or len(claims),
            n_papers_total=side_blob.get("n_papers_total") or 0,
            n_drafts_total=side_blob.get("n_drafts_total") or 0,
            n_kept_after_trim=side_blob.get("n_kept_after_trim") or 0,
            n_iterations_run=side_blob.get("n_iterations_run") or 0,
            elapsed_s=0.0,
            cost_usd=0.0,
            warnings=[],
        )

    a1 = _side(pts.get("a1") or {})
    a2 = _side(pts.get("a2") or {})
    return DualPlanTrimSelectResult(
        gene=blob.get("gene") or "<unknown>",
        bundle=bundle,
        a1=a1,
        a2=a2,
        elapsed_s=0.0,
    )


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
