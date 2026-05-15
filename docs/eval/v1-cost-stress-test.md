# v1.0.0 deep-dive cost stress test

**Date:** 2026-05-15 · **Branch:** `m3-cost-tracking-stress-test`
· **Model:** `claude-sonnet-4-6` across A1, A2, B
· **Pricing snapshot:** $3.00 / $15.00 per MTok input/output (no cache hits)
· **Pricing module:** [pricing.py](../../src/accessible_surfaceome/agents/_support/pricing.py)

## TL;DR

The newly-wired cost instrumentation surfaced a finding the original
estimate didn't anticipate: **one gene's deep-dive run costs ~$4 on
Sonnet 4.6, not ~$1**. A single live worked example (CD81) blew the
$5–10 sweep budget on its own. The remaining six stress-test genes are
deferred to a follow-up that lands prompt caching first; this PR ships
the instrumentation, the CD81 worked example, and a per-iteration
decomposition that pinpoints the cause.

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

## Headline table (CD81)

| gene | A1 $ | A2 $ | B $ | total $ | claims | % anchored | A1 repairs | A2 repairs | B repairs |
|------|------|------|------|---------|--------|------------|------------|------------|-----------|
| CD81 | 2.085 | 2.163 | 0.184 | **4.432** | 28 | **21.4%** ⚠ | 1 | 1 | 1 |

Both stress-test outlier rules fire on CD81: substring-anchored
fraction (21.4%) is well under the 60% quality threshold, and the
per-gene cost is ~3× the original $0.50–1.50/gene estimate.

The remaining six genes (EGFR, HSPA5, GPR75, CALR, GPRC5D, TNFR1) are
not in this report — they were blocked by the cost-confirmation gate
the task carved out, after CD81 alone hit the budget.

## Why CD81 cost $4.43

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

CD81 substring-anchored fraction (21.4%, 6/28 evidence rows) is well
under the 60% threshold the stress-test spec uses to flag quality
outliers. The 22 unanchored claims emitted by the agents did not match
into the shared `SourceTextStore` at promotion time. Two plausible
explanations, each independently fixable:

- **Quote drift.** Agents paraphrasing rather than copying the exact
  ≤200-char substring from tool-result bodies. The schema requires
  verbatim quotes; a Sonnet entailment audit (currently de-wired,
  separate follow-up PR) would catch this.

- **Body never landed in the store.** Some `evidence_retrieval`
  categories may produce summary structures rather than full text the
  store can index against. The promotion code is the right place to
  audit which sources actually feed `SourceTextStore`.

Both belong in their own diagnostic pass — not in this PR.

## Recommendations (separate follow-ups, in priority order)

1. **Prompt caching on the static prefix** in A1 / A2 (system prompt +
   the schema-bearing task message). Likely 5–10× cost reduction per
   gene; gate the full 7-gene sweep on this landing.

2. **Cap or summarise huge tool results** before they hit the model.
   Full PMC XML pulls are the biggest single source of message-history
   bloat; a tool-side truncation budget (with the full body remaining
   in `SourceTextStore` for substring anchoring) would compound with
   #1.

3. **Re-wire the substring-anchoring audit** so quality outliers like
   CD81's 21.4% surface as orchestrator warnings rather than
   post-hoc analysis.

Once #1 and #2 land, re-run the full 7-gene panel; expected spend
should drop from ~$30 back into the originally-budgeted $5–10 range.

## Artifacts

- `data/eval/v1_cost_stress_test/CD81.json` — table-ready row
- `data/eval/v1_cost_stress_test/summary.json` — sweep summary (one row)
- `.runs/{a1,a2,b}_CD81.meta.json` — per-iteration trace
- `data/annotations/CD81.json` — the assembled record (validates,
  21.4% anchored)
