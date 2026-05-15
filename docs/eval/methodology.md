# Testing-and-improving methodology for the v1.0.0 deep-dive pipeline

How to push a multi-agent / multi-tool pipeline from "produces output"
to "produces *correct* output you'd put in a paper." Distilled from the
5-round push that took CD81 from 21.4% → 88.9% substring-anchored
evidence at 3.3× lower cost.

Other agents working on this pipeline: use this as the default loop
when you're asked to improve quality or cut cost.

## The loop, in one sentence

**Instrument → run real → audit critically → name the failure mode →
fix at the lowest layer that solves it → re-run → repeat.**

The bottleneck always moves. That's the signal you're making progress.

## 1. Instrument before optimizing

Before changing anything, make the thing measurable. For each
agent / tool call, capture:

- Token usage (input / output / cache-write / cache-read) and dollar
  cost per call, per agent, per gene. Persist per-iteration traces to
  `.runs/{agent}_<gene>.meta.json`.
- Tool-call counts and per-tool error rate.
- Output quality signals (substring-anchored fraction, claim count,
  category coverage, source diversity).

The instrumentation is the foundation of every later decision. If you
can't see it, you can't fix it — and you can't tell whether a "fix"
actually helped.

See `src/accessible_surfaceome/agents/_support/pricing.py` for the
cost-capture pattern.

## 2. Run real, not mocked

Use the actual end-to-end pipeline against real APIs. Mocked tests
pass on stub responses but miss the failure modes that drive quality:

- Agent paraphrase ("I'll synthesize this nicely") fails the substring
  check.
- Agent source-mis-cite ("PMID looks cleaner than PMC") fails the
  substring check.
- Snippets that exist in retrieval but the agent doesn't pick.

None of these surface in unit tests. They only show up in live runs
against real Anthropic + EuropePMC + PubTator + UniProt traffic.

**Budget gate before live runs.** If a single test-gene run costs
>$1.50, confirm with the user before kicking off a multi-gene sweep.
Cost-of-test is a real constraint; surfaceome papers don't need 50
samples to learn what's broken.

## 3. Pick one worked example, audit it deeply

Don't average across genes until you've understood one gene
completely. For each round:

- Run the full pipeline on one well-studied gene (CD81 is a good
  reference — tetraspanin, lots of literature, both surface biology
  and high-throughput methods).
- Open `data/annotations/<GENE>.json` and read every evidence row by
  hand. Look at: source_id, section, quote, anchored flag, validation
  warnings, claim_type, evidence_tier.
- Open `.runs/{a1,a2,b}_<GENE>.meta.json` to see what tool calls were
  made and how the iteration cost grew.

A 30-minute manual audit of one gene's record beats two hours of
spreadsheet aggregation across 7 genes.

## 4. Audit critically — the % anchored number is not the whole story

`entailment_verified=True` means "quote substring-matches the source
body." It does **not** mean:

- The claim is scientifically supported by the quoted text.
- The quote is load-bearing (it might be shallow methodology).
- The tier classification (primary / secondary) is right.
- The source is the *best* one (a PMID:abstract anchor is much weaker
  than a PMC:results-section anchor).

For each anchored claim, ask: would I cite this in a paper? Is this
actually evidence of surface accessibility, or is it incidental? Is
the tier right? Is the cited paper duplicated under different
source_ids?

For each unanchored claim, ask: is the agent paraphrasing real
content, or inventing? Check `validation_warnings`.

Critical-lens audit is the most under-rated step. The hard
single-sample finding ("CD81 false-positive shedding flag") matters
more than the easy aggregate ("71.9% anchored").

## 5. Trace failures to a specific stage with a diagnostic script

When a category produces 0 anchored claims, don't speculate — write
a diagnostic that traces the funnel stage by stage. Example pattern:

```text
discovery: PubTator N papers + EuropePMC M papers → union K
  → PMC-OA non-retracted: K'
  → backfill loop: per-paper fetch + extract trace:
     ✓ PMC123456 sections=[methods=1, results=1, ...] → 3 snippets
     ✗ PMC789012 sections=[...] → 0 snippets (after gene-proximity filter)
```

See `scripts/audit_evidence_retrieval.py`. It tells you *exactly*
where papers drop out — retrieval, filter, fetch, hallmark match,
proximity. That tells you which stage's code to fix.

Critical: the right fix depends on the failure mode. Conflating them
costs you days.

## 6. Name the failure mode before fixing

Distinguish at least these classes:

| Failure mode | Symptom | Right fix |
|---|---|---|
| Retrieval too narrow | 0 papers / 0 snippets | Broaden query, add discovery source |
| Filter overshoots | snippets exist but get dropped | Loosen filter per-category |
| Agent doesn't pick available material | snippets exist, agent uses other categories | Prompt nudge or score reweighting |
| Agent paraphrases | claim text is summary-of-snippet, anchor fails | Pre-built drafts the agent can't reword |
| Agent mis-cites source | anchor fails because PMID:abstract cited but quote came from PMC:body | Lock (quote, source_id) pair structurally |
| Agent invents source | "source not in session store" warning | Schema/validator enforcement |
| Synthesizer over-reaches | risk flag fires on weak evidence chain | Surface anchored-vs-not back to B |

Different mechanisms; different fixes. Naming the class lets you pick
the right intervention without thrashing.

## 7. Prefer tool-level fixes over agent / prompt-level fixes

Order of preference, lowest-blast-radius first:

1. **Improve tool output shape.** Pre-build the load-bearing structure
   the agent would otherwise have to assemble manually. E.g.,
   `EvidenceClaimDraft` locks (quote, source_id) together; the agent
   can't paraphrase what it never types.
2. **Add an adjacent tool.** Coverage gap → new tool. Don't add an
   agent.
3. **Tighten the tool description.** The agent reads this on every
   call. Cheap to change; high leverage.
4. **Tighten the system prompt.** Slower to change because the agent's
   behaviour around it has dependencies. Save for after tool fixes.
5. **Add an agent.** Last resort. New agent = new orchestration,
   new cost, new failure modes. Don't reach for this when a better
   tool would suffice.

The user's framing: *"We're looking for ways to make the tools better
or add tools rather than add more agents right now."* This is the
right default.

## 8. Iterate in rounds; tabulate side-by-side

Each round = one focused fix + one full re-run + one critical audit.
Tabulate the headline numbers across all prior rounds:

```
| | r1 baseline | r2 cache+compact | r3 proximity | r4 target-mention | r5 drafts |
|---|---|---|---|---|---|
| cost | $4.43 | $1.37 | $1.28 | $1.25 | $1.35 |
| % anchored | 21.4% | 71.9% | 57.6% | 50.0% | 88.9% |
| HT anchored | 0 | 1 | 2 | 1 | 7 |
```

Read across the row. If the metric stalled or regressed, the bottleneck
moved — say *where* it moved and target the next round there. A
single-sample regression isn't always a real regression; note when it
might be variance.

## 9. Persist the diagnostic so the next person can re-run it

Whatever script you wrote to trace the funnel, commit it under
`scripts/`. The next agent (or future you) wants to re-run the same
diagnostic against a different gene without re-deriving it.

Same for the eval driver (`scripts/v1_cost_stress_test.py`). It IS the
methodology made executable.

## 10. Document the surprising findings, not the easy ones

When you write up a round, lead with what you didn't expect:

- "Stripping `paper.sections` from transport unexpectedly *improved*
  quality 21% → 72% because the agent was forced to use snippets."
- "0/22 papers contributed snippets even though the literal
  CD81-engineered-binder paper was right there in the candidate pool —
  the gene-proximity filter was rejecting it."

Easy findings ("we added caching, it got cheaper") don't help readers
calibrate. Surprises do.

## What this loop is *not* for

- Aesthetic refactors. Use it when there's a measurable quality or
  cost problem.
- Speculative engineering. The instrumentation tells you what to fix,
  not your prior.
- Schema rewrites. If the deeper schema is wrong, that's a different
  conversation — don't bury a schema redesign inside a quality push.

## Anchors

- Worked example: `docs/eval/v1-cost-stress-test.md`
- Per-call cost capture: `src/accessible_surfaceome/agents/_support/pricing.py`
- Caching + compaction: `src/accessible_surfaceome/agents/_support/payload.py`
- Retrieval diagnostic: `scripts/audit_evidence_retrieval.py`
- Eval driver: `scripts/v1_cost_stress_test.py`
- Pre-built claim drafts: `EvidenceClaimDraft` in
  `src/accessible_surfaceome/tools/_shared/models.py`
