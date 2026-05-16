"""Plan → trim → select agent — clip-and-judge evidence loop.

See ``docs/plans/2026-05-16-clip-and-judge-flow.html`` for the design.

Three-step loop using only existing tools:

1. **Plan** — Sonnet emits a ``SearchPlan`` (which tools to call with what
   params). Existing tools only: ``gene_lookup``, ``evidence_retrieval``,
   ``gene_literature``.
2. **Trim** — orchestrator code runs the plan, collects all
   ``EvidenceClaimDraft`` records into a clip pool, then asks Haiku (one
   batch call per source paper) to keep the load-bearing clips.
3. **Select** — Sonnet sees the trimmed clip menu (each clip carries a
   stable ``clip_id``) and emits ``selections`` = list of
   ``{clip_id, classifications, claim_text}``. NO ``quote`` field — the
   orchestrator fills ``EvidenceClaim.quote`` from the pinned clip text
   on promotion. Paraphrase impossible by construction.
"""

from accessible_surfaceome.agents.plan_trim_select.runner import (
    PlanTrimSelectResult,
    run_plan_trim_select,
)

__all__ = ["PlanTrimSelectResult", "run_plan_trim_select"]
