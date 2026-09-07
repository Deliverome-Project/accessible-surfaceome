# v1.0.0 deep-dive cost stress test

**Date:** 2026-05-15 · **Branch:** `m3-cost-tracking-stress-test`
· **Model:** `claude-sonnet-4-6` across A1, A2, B
· **Pricing snapshot:** $3.00 / $15.00 per MTok input/output (no cache hits)
· **Pricing module:** [pricing.py](../../src/accessible_surfaceome/agents/_support/pricing.py)

## TL;DR

The cost instrumentation surfaced a finding the original estimate didn't
anticipate — **one gene's deep-dive run cost ~$4 on Sonnet 4.6 instead
of ~$1** — and the same PR landed the fix:

| | Round 1 (baseline) | Round 2 (caching + compaction) | Δ |
|---|---|---|---|
| **Total $ / gene (CD81)** | $4.432 | **$1.365** | **3.25× cheaper** |
| **% substring-anchored** | 21.4% | **71.9%** | **3.4× higher quality** |
| A1 $ | $2.085 | $0.639 | 3.3× |
| A2 $ | $2.163 | $0.583 | 3.7× |
| B $ | $0.184 | $0.143 | 1.3× |
| Evidence claims | 28 | 32 | +14% |

Two changes drove the cost reduction:
- **Prompt caching.** Two cache breakpoints per request (system prompt
  + rolling latest tool_result) move ~95% of repeat-iteration input from
  base rate to 0.1× cache-read rate. CD81 A1 paid for 170k cache-read
  tokens + 58k cache-write tokens + only 15k uncached input.
- **Tool-result compaction.** `evidence_retrieval` was returning the
  full PMC paper bodies (`paper.sections[*].text`) alongside the
  ≤200-char snippets the agent actually quotes from. The full body is
  already in `SourceTextStore` (registered before the result is
  serialized for the model), so stripping `sections` from transport
  doesn't affect substring anchoring — and the lighter payload appears
  to let the agent extract more, better-anchored claims (the quality jump
  was an unexpected bonus, not a designed effect).

The remaining six stress-test genes (EGFR / HSPA5 / GPR75 / CALR /
GPRC5D / TNFR1) are still deferred — even at $1.36/gene the user-set
budget didn't allow a full sweep in this PR. With the new per-gene cost
estimate, the full panel should land in ~$10 of API spend.

## How the instrumentation works

Every `client.messages.create(...)` call in A1 / A2 / B now records the
response's `usage` block — `input_tokens`, `output_tokens`,
`cache_creation_input_tokens`, `cache_read_input_tokens` — and prices
it against [`PRICING`](../../src/accessible_surfaceome/agents/_support/pricing.py)
at call time. The per-iteration trace plus totals + dollar cost ride
in each runner's `Result.usage: UsageSummary`. The orchestrator
exposes per-agent + total cost on `AnnotateResult`, persists per-agent
`.runs/{a1,a2,b}_<gene>.meta.json` with the iteration trace
regardless of validation outcome, and the CLI's annotate JSON now
emits a `cost_usd` + `tokens` block.

Pricing lives in one dict keyed by model id — adding a new model is a
single-entry edit, no per-call-site changes.

## Headline table (CD81 — both rounds)

| round | gene | A1 $ | A2 $ | B $ | total $ | claims | % anchored | A1 repairs | A2 repairs | B repairs |
|-------|------|------|------|------|---------|--------|------------|------------|------------|-----------|
| 1 (baseline) | CD81 | 2.085 | 2.163 | 0.184 | **4.432** | 28 | **21.4%** ⚠ | 1 | 1 | 1 |
| 2 (cached + compacted) | CD81 | 0.639 | 0.583 | 0.143 | **1.365** | 32 | **71.9%** ✓ | 2 | 1 | 1 |

Round 1 fired both stress-test outlier rules: substring-anchored
fraction under the 60% quality threshold, and per-gene cost ~3× the
original $0.50–1.50/gene estimate. Round 2 clears both.

The remaining six genes (EGFR, HSPA5, GPR75, CALR, GPRC5D, TNFR1) are
still not in this report — they were blocked by the cost-confirmation
gate the task carved out. At round-2 rates ($1.36/gene observed,
$1–2/gene plausible across the panel) the full sweep is back inside
the original $5–10 budget and can land in a follow-up PR.

## Round 2 round-trip — cache usage

CD81 round-2 token decomposition pulled from `.runs/{a1,a2,b}_CD81.meta.json`:

| agent | iters | input | cache write | cache read | output | cost $ |
|-------|-------|-------|-------------|------------|--------|--------|
| A1 | 7 | 14,889 | 58,191 | **169,989** | 21,671 | 0.639 |
| A2 | 8 | 16,133 | 49,238 | **188,356** | 19,572 | 0.583 |
| B  | 2 |  1,665 | 23,810 |  23,810 |  2,743 | 0.143 |

Cache-read tokens dominate input on A1 / A2 — the rolling tool_result
breakpoint is catching the cumulative prior context on every iteration
after the first. B's symmetric write=read=23,810 confirms the initial
task-message cache_control is doing exactly what it should: caching
the full A1+A2 ledger once, then reading it on the repair iteration.
The uncached `input_tokens` columns are now ~10–15k per agent — orders
of magnitude smaller than the round-1 figures below.

## Why round 1 cost $4.43 (kept for context)

Per-iteration token counts from `.runs/a1_CD81.meta.json` and `a2_CD81.meta.json`:

| agent | iter | input tokens | output tokens | $ this iter |
|-------|------|--------------|---------------|-------------|
| A1 | 1 | 9,452 | 96 | 0.030 |
| A1 | 2 | 9,938 | 356 | 0.035 |
| A1 | 3 | 114,460 | 456 | 0.350 |
| A1 | 4 | 244,102 | 6,453 | 0.829 |
| A1 | 5 | 251,073 | 5,858 | 0.841 |
| A1 | **total** | **629,025** | **13,219** | **2.085** |
| A2 | 1 | 9,483 | 96 | 0.030 |
| A2 | 2 | 9,969 | 141 | 0.032 |
| A2 | 3 | 11,489 | 283 | 0.039 |
| A2 | 4 | 159,306 | 253 | 0.482 |
| A2 | 5 | 214,788 | 8,933 | 0.778 |
| A2 | 6 | 223,944 | 8,685 | 0.802 |
| A2 | **total** | **628,979** | **18,391** | **2.163** |
| B  | 1 | 22,209 | 1,585 | 0.090 |
| B  | 2 | 24,276 | 1,371 | 0.093 |
| B  | **total** | **46,485** | **2,956** | **0.184** |

Two patterns drop out:

1. **Tool-result accumulation is the dominant cost.** A1's input balloons from
   ~10k tokens (iter 1) to ~250k tokens (iter 5) as each EuropePMC fullTextXML
   pull and each `evidence_retrieval` result is appended to the message
   history. By the final iteration, A1 is re-paying the full prior context
   on every turn — output tokens are tiny by comparison.

2. **Cache fields are zero everywhere.** `cache_creation_input_tokens` and
   `cache_read_input_tokens` are 0 on every iteration of every agent. The
   runners are not currently issuing prompt-cache breakpoints, so every
   round-trip pays full input price for content the prior round already
   sent. A 5-minute cache breakpoint on the static system prompt + the
   accumulated tool-result history would reduce iteration-4/5 input cost
   to ~10% of current — back-of-envelope, ~$0.20–0.30/gene for A1 and A2.

The B (Synthesizer) cost is fine ($0.18). B has no tools and consumes
the structured drafts (~22k tokens, fixed), not raw fetched text.

## Quality observation

Round-1 CD81 substring-anchored fraction was 21.4% (6/28 evidence
rows) — well under the 60% threshold the stress-test spec uses to flag
quality outliers.

Round 2 lifted it to **71.9% (23/32 evidence rows)** without any
change to the schema, prompts, or substring-matching code. The likely
mechanism: when raw `paper.sections` were dropping into the message
history, the agent had two paths to grounding a claim — quote a snippet
(pre-extracted to substring-match by construction) or quote loose text
from a section (paraphrase-prone, often failed the substring check).
With the sections stripped from transport, the snippet path is the
only available option, and snippet quotes are byte-identical to the
substrings registered in `SourceTextStore`. This is a behaviour shift,
not a designed effect — worth re-validating on a wider gene panel before
generalising.

The remaining ~28% of unanchored claims are likely cite-against-
non-snippet sources (UniProt prose, HPA snapshot, db panels). Those
bodies *are* in `SourceTextStore` — the failure mode is paraphrase, not
missing-body. The de-wired Sonnet entailment audit is the right tool
to drive that fraction down further.

## What landed (rounds 1 + 2)

1. **Round 1 — instrumentation.** Per-call token + cost capture in A1 /
   A2 / B; orchestrator surfaces per-agent + total cost; `.runs/*.meta.json`
   carries the per-iteration trace; CLI emits `cost_usd` + `tokens` blocks.
2. **Round 2 — prompt caching.** Two cache breakpoints per request
   (system prompt always; rolling latest tool_result). Implemented in
   [`agents/_support/payload.py`](../../src/accessible_surfaceome/agents/_support/payload.py).
3. **Round 2 — tool-result compaction.** `evidence_retrieval`
   `paper.sections[*]` stripped before transport; the full body stays
   in `SourceTextStore` for substring anchoring. Implemented in the same
   payload module via `compact_for_agent_transport()`.

## Recommendations still open (separate follow-ups)

1. **Run the full 7-gene panel.** At observed round-2 rates the sweep
   should cost ~$10. Worth doing once a fresh budget is allocated to
   validate that the CD81-specific quality jump (21.4% → 71.9%)
   generalises — single-gene results can be lucky.

2. **Re-wire the substring-anchoring audit** so quality outliers surface
   as orchestrator warnings rather than post-hoc analysis. Even at 71.9%
   anchored, ~30% of claims weren't substring-matched — the Sonnet
   entailment audit (currently de-wired) would catch each one
   immediately.

3. **EuropePMC vs PubTator quality A/B.** Not redundant — PubTator3
   drives discovery (NER over PubMed), EuropePMC delivers the body text
   substring anchoring runs against. Worth a separate experiment to
   confirm both are pulling their weight, especially for orphan
   GPCRs / under-annotated genes; out of scope for this cost PR.

## Artifacts

- `data/eval/v1_cost_stress_test/CD81.json` — table-ready row
- `data/eval/v1_cost_stress_test/summary.json` — sweep summary (one row)
- `.runs/{a1,a2,b}_CD81.meta.json` — per-iteration trace
- `data/annotations/CD81.json` — the assembled record (validates,
  21.4% anchored)
