#!/usr/bin/env python
"""Synth-only re-run from cached D1 intermediates.

Pulls the most recent intermediates blob for one gene from public
``surfaceome_agents`` D1, reconstructs the synthesizer's inputs from
it, and re-invokes the synthesizer. Skips the expensive
plan-trim-select stage (~70% of per-gene cost), so a prompt-iteration
loop on the synthesizer side costs ~$0.15/iteration instead of ~$2.

Useful when you're iterating on:
* The synthesizer's system prompt
* The orchestrator's post-passes (state-dep / surface floor / NO-bucket
  override / trafficking) — these run AFTER the synthesizer in this
  driver too
* The :class:`SurfaceomeRecord` validators

NOT useful for issues upstream of the synthesizer (plan-trim-select,
methods/grade/expression/etc. builders) — those outputs are taken
from the cached intermediates verbatim.

Usage:
    uv run python scripts/surfaceome_v2_replay_synth.py TGOLN2

    # Force a specific intermediates timestamp:
    uv run python scripts/surfaceome_v2_replay_synth.py TGOLN2 \\
        --at 2026-06-08T15:15:04

    # Compare two runs on the same ledger:
    uv run python scripts/surfaceome_v2_replay_synth.py TGOLN2 --n 3
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents.surfaceome_synthesizer.runner import (
    run_synthesizer_with_drafts,
)
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    BiologicalContextDraft,
    EvidenceClaim,
    SurfaceEvidenceDraft,
)


def _load_intermediates(
    gene_symbol: str, at: str | None = None
) -> dict[str, Any]:
    """Load a gene's intermediates blob from private D1."""
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


def _reconstruct_drafts(
    blob: dict[str, Any],
) -> tuple[SurfaceEvidenceDraft, BiologicalContextDraft, AccessibilityRisks]:
    """Reconstruct the synthesizer's three input drafts from intermediates."""
    pts = blob["plan_trim_select"]
    a1_claims = [EvidenceClaim.model_validate(c) for c in pts["a1"].get("claims") or []]
    a2_claims = [EvidenceClaim.model_validate(c) for c in pts["a2"].get("claims") or []]

    # SurfaceEvidenceDraft / BiologicalContextDraft expect a `claims` field.
    a1_draft = SurfaceEvidenceDraft(claims=a1_claims)
    a2_draft = BiologicalContextDraft(claims=a2_claims)

    canonical = blob.get("canonical_risks") or blob.get("risks_builder")
    if canonical is None:
        raise SystemExit(
            "intermediates blob has neither 'canonical_risks' nor "
            "'risks_builder' — too old to replay synth-only"
        )
    risks = AccessibilityRisks.model_validate(canonical)
    return a1_draft, a2_draft, risks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gene", help="Gene symbol")
    parser.add_argument(
        "--at",
        help="Optional intermediates timestamp prefix (e.g. 2026-06-08T15:15)",
    )
    parser.add_argument(
        "--n", type=int, default=1, help="How many synth calls to run (variance test)"
    )
    args = parser.parse_args()

    load_env()
    blob = _load_intermediates(args.gene, args.at)
    a1_draft, a2_draft, risks = _reconstruct_drafts(blob)

    # Triage summary lives in the intermediates blob since v2.34. Older
    # blobs may not have it — pass None and let the synth run unprimed.
    triage_summary = blob.get("triage_summary_json")
    # Deterministic features summary not strictly needed by the synth;
    # the deterministic_summary_json arg is the prompted text block.
    det_summary = None

    print(
        f"=== {args.gene} replay ({args.n}× synth-only on cached ledger) ===\n"
        f"  A1 claims:           {len(a1_draft.claims)}\n"
        f"  A2 claims:           {len(a2_draft.claims)}\n"
        f"  triage_summary_json: {'yes' if triage_summary else 'NO (older intermediates)'}\n"
        f"  risks loaded:        {'yes' if risks else 'NO'}\n"
    )

    client = get_client()
    for rep in range(args.n):
        b = run_synthesizer_with_drafts(
            args.gene,
            a1_draft=a1_draft,
            a2_draft=a2_draft,
            client=client,
            triage_summary_json=triage_summary,
            deterministic_summary_json=det_summary,
            accessibility_risks=risks,
        )
        if b.draft is None:
            print(f"  rep {rep + 1}: FAILED — validation_error={b.validation_error}")
            continue
        es = b.draft.executive_summary
        print(
            f"  rep {rep + 1}: "
            f"sa={es.surface_accessibility:8} "
            f"state={es.state_dependence:10} "
            f"reason={es.surface_call_reason:28} "
            f"conf={b.draft.confidence:10} "
            f"cost=${b.usage.cost_usd:.3f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
