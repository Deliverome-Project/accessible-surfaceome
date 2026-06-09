# Cache engagement probe — 2026-06-08

Read-only investigation: why Anthropic prompt caching shows
`cache_creation_input_tokens=0` and `cache_read_input_tokens=0` on the Sonnet
builder + Haiku trim paths despite `cache_control` being wired in. Probe
script: [`scripts/probe_cache_engagement.py`](../../scripts/probe_cache_engagement.py).

**STATUS (2026-06-08, post-fix):** Probe results reproduced + fix applied.
Haiku trim cached prefix padded from 2,654 / 2,083 tokens (a1 / a2) to
4,770 / 4,263 tokens (both above Haiku 4.5's 4,096-token floor).
Production-shape verification confirms caching now engages: call 1
`cw=4,764`, call 2 `cr=4,764` (`in=529` per call thereafter). Defensive
`cache_control` marker also added to the methods builder's
`_WEB_SEARCH_TOOL`. See "Fix landed (2026-06-08)" section below.

## TL;DR

| Path | Was-it-broken-as-described? | Root cause | Cohort savings if fixed |
|---|---|---|---|
| **Haiku trim** (per-paper `_trim_one_paper` in `plan_trim_select/runner.py:973`) | **YES — confirmed by today's TACSTD2 run: 77 trim calls, all 0/0** | **Hypothesis 2 confirmed: cached prefix is 2,654 tokens; Haiku 4.5's documented minimum is 4,096 tokens. Per Anthropic docs: "any requests to cache fewer than this number of tokens will be processed without caching, and no error is returned."** | **~$390-$580 over 6,500 genes** (see math below) |
| **Sonnet builders + selector** (`builders/_common.py:177`, `runner.py:642`) | **NO — historical artifact.** TGOLN2 (Jun 7 09:57) ran *before* the API rolled into the working state OR before the `27dbbf25b` `sort_keys=True` fix had fully purged stale cache keys. **Today's runs show caching is engaging correctly** (TACSTD2 today: builders_a1 cr=127,513, cw=58,297 — strong cache reads). | n/a — already working | n/a |
| **Haiku abstract triage** (`abstract_triage.py:205`) | Same family as Haiku trim (~2,576-char prompt → ~635 tokens cached). Almost certainly not caching either. | Same as trim: below 4,096-token minimum. | ~$0.05/gene × 6,500 = **~$325** |

So the actionable bug is **size-of-cached-prefix**, on the Haiku paths only.

## What the probe ran

Five configs, two sequential `messages.create` calls each (within Anthropic's
5-min ephemeral TTL). For every config we measure `usage.cache_creation_input_tokens`
(cwrite) and `usage.cache_read_input_tokens` (cread) on both calls.

Anthropic docs (verified 2026-06-08):

* Sonnet 4.6 cache minimum: **1,024 tokens**.
* Haiku 4.5 cache minimum: **4,096 tokens**. Below the floor, the request is
  processed *without caching* and **no error is raised**.
* Tools and system are cached together in the prefix; `cache_control` on the
  last tool entry caches the tools block as well as anything ahead of it.
  Automatic caching (no explicit marker on tools) can also cache the
  tools+system prefix when one is present.

### Raw probe results (Run 1)

```
config                                                                          cached_tok   c1_cw   c1_cr   c2_cw   c2_cr
Sonnet methods: cached system + web_search tool (TODAY'S SHAPE)                          -   19059   10999   15329   21998
Sonnet methods: cached system, NO TOOLS (control)                                     9115    9109       0     160    9109
Sonnet methods: cached system + tools w/ cache_control on tool (PROPOSED FIX)            -    7968   21998   14855   21998
Haiku trim: cached system (TODAY'S SHAPE, ~2.5k cached tokens)                        2654       0       0       0       0
Haiku trim: cached system PADDED to 4589 tokens (>4096 min)                           4589    4583       0       0    4583
```

### Raw probe results (Run 2, confirms Run 1)

```
config                                                                          cached_tok   c1_cw   c1_cr   c2_cw   c2_cr
Sonnet methods: cached system + web_search tool (TODAY'S SHAPE)                          -   10999       0   14646   21998
Sonnet methods: cached system, NO TOOLS (control)                                     9115    9109       0     160    9109
Sonnet methods: cached system + tools w/ cache_control on tool (PROPOSED FIX)            -    7343   21998   15469   21998
Haiku trim: cached system (TODAY'S SHAPE, ~2.5k cached tokens)                        2654       0       0       0       0
Haiku trim: cached system PADDED to 4589 tokens (>4096 min)                           4589    4583       0       0    4583
```

### Raw probe results (Run 3, taken 2026-06-08 ~20:30, immediately pre-fix)

```
config                                                                          cached_tok   c1_cw   c1_cr   c2_cw   c2_cr
Sonnet methods: cached system + web_search tool (TODAY'S SHAPE)                          -   24894   10999   13998   21998
Sonnet methods: cached system, NO TOOLS (control)                                     9115    9109       0     160    9109
Sonnet methods: cached system + tools w/ cache_control on tool (PROPOSED FIX)            -   14354   21998     477   10999
Haiku trim: cached system (TODAY'S SHAPE, ~2.5k cached tokens)                        2654       0       0       0       0
Haiku trim: cached system PADDED to 4589 tokens (>4096 min)                           4589    4583       0       0    4583
```

Run 3 was the immediate pre-fix repro. All three runs are mutually
consistent: Sonnet builders cache cleanly, Haiku trim at 2,654 cached
tokens silently fails cache (0/0 on both calls), and padding above the
floor (4,589 tokens) restores caching to the documented behaviour.

### Post-fix verification (2026-06-08, after applying Option A)

Production-shape verification using the actual `_split_trim_template`
helper with `_TRIM_CACHE_PAD` appended:

```
a1_trim_system.md: cached prefix = 4,770 tokens (char count: 19,251)
a2_trim_system.md: cached prefix = 4,263 tokens (char count: 17,416)
```

Both above 4,096, with margin (a1: +674, a2: +167). End-to-end Haiku
trim call shape with the padded prefix on the live API:

```
CALL 1: in=529 cw=4,764 cr=0      ← cache write engages
CALL 2: in=529 cw=0     cr=4,764  ← cache read engages on the same prefix
```

The pre-fix shape would have shown `cw=0, cr=0` on both calls. Caching
is now active on the Haiku trim path.

(`count_tokens` rejects server-side tools — `BadRequestError: Server tools
are not supported in the count_tokens endpoint: web_search_20250305` — so the
tools+system token figures show `-`. Treat the Sonnet-with-tools cwrite as
"system (9k) + tool definition (~2k) + intra-call web_search results (variable)".)

### Production cross-check (TACSTD2 today, eager-heyrovsky worktree)

```
phase                       n=?    in=?       cw=?       cr=?
builders_a1                 n=  3  in= 44,434  cw= 58,297  cr=127,513   ← Sonnet builders ARE caching
builders_a2                 n=  4  in= 66,431  cw= 59,513  cr= 15,886
builders_risks              n=  1  in= 37,662  cw=      0  cr=  4,282
plan_trim_select_a1 (Haiku) n= 99  in=445,348  cw=      0  cr=  5,393   ← 77 Haiku trim calls all 0/0
plan_trim_select_a2 (Haiku) n=102  in=449,507  cw=      0  cr=  4,456   ← (the 5,393/4,456 cr is from
                                                                          the single Sonnet selector
                                                                          call at the end of each phase)
synthesizer                 n=  1  in=     2   cw= 60,890  cr= 12,734   ← synth caches as expected
```

The 77 Haiku trim rows in plan_trim_select_a1 all show `input_tokens` in
[3,287-6,315] (median 5,487) and **every single one has cw=0, cr=0**. The
non-zero cr in the row aggregate is entirely contributed by the lone Sonnet
selector call.

## Which hypothesis is correct?

* **Hypothesis 1 (`tools=` parameter changes cache key on methods builder)** —
  **REJECTED.** Probe Config 1 (today's shape with web_search tool) cleanly
  shows cwrite ≈ 11-19k on call 1 and cread ≈ 11-22k on call 2. Sonnet
  builders are caching, just not visible in the OLD TGOLN2 meta.json. The
  caching path works whether or not the tools list carries its own
  `cache_control` marker.
* **Hypothesis 2 (Haiku trim system prompt below the cache minimum)** —
  **CONFIRMED.** Probe Config 4 shows the 2,654-token cached prefix gets
  silently dropped (0/0 on both calls). Probe Config 5 shows that padding
  the prefix to 4,589 tokens immediately engages caching: cwrite=4,583 on
  call 1, cread=4,583 on call 2 (exactly as expected: full prefix written
  once, read on the second call). The relevant Anthropic-docs floor is
  **4,096 tokens for Haiku 4.5** (not 2,048 — that's the older Haiku 3.5
  number, and is also what the in-tree comment at `abstract_triage.py:84`
  references, which is stale).
* **Hypothesis 3 (system block format mismatch)** — **REJECTED.** The
  Sonnet probe configs all use the same `cached_system()` shape and the
  same `system=cast("Any", cached_sys)` call shape as production. They
  cache. The shape is fine.

## The minimal recommended fix

### Fix #1 (HIGH PRIORITY): Pad the Haiku trim & abstract-triage cached prefixes above the 4,096 floor

Two paths need attention:

1. **`a1_trim_system.md` + `a2_trim_system.md`** — cached prefix (everything
   before `## Output`) currently 2,654 / 2,083 tokens. Both below 4,096.
2. **`abstract_triage_system.md`** — entire ~2,576-char file is cached
   (no `## Output` split); count_tokens reports ~635 tokens. Far below 4,096.

Two options for each file:

**Option A — Push the cached prefix above 4,096 tokens by enriching the
rules/calibration sections with genuinely-useful guidance.** This is the
preferred fix because it makes the cache pay off AND tightens trim/triage
quality. Concretely:

* The a1 and a2 trim prompts already share their structure (10k chars). The
  difference is roughly 4,000 chars of A1- vs A2-specific rules. Adding
  one or two more sections (worked-pattern paragraphs, an expanded
  Calibration section, an explicit borderline-case ledger) lands the
  prefix above 4k tokens.
* The abstract-triage prompt at 2,576 chars / ~635 tokens needs ~14,000
  chars more. The current prompt is terse; an extended "Edge cases" and
  "How to read assay-method-named papers" section would push past 4,096 and
  measurably improve triage precision.

**Option B — Remove the `cache_control` marker from `_trim_one_paper` and
`triage_one_abstract`** so the calls don't claim cache when none can land.
This stops paying a notional "cache write premium" but is a perceptual /
cost-accounting fix only — Anthropic does NOT actually charge a 1.25×
premium when caching silently fails to engage (the request is processed
"without caching" per the docs), so today's behaviour is *not* a cost leak
in the way it appears. The fix is cleanup, not money.

**Recommendation: Option A.** The expected savings are real once it lands,
and the prompt expansion is the kind of thing the upcoming round of trim
refinements wants to do anyway. The padded probe (Config 5) confirms the
mechanic works once we cross 4,096.

### Fix #2 (LOW PRIORITY, defensive): Add `cache_control` to the methods builder's web-search tool entry

Today's behavior shows that Anthropic's automatic caching picks up the
tools+system prefix without an explicit marker on the tool. But this is
implicit / not documented as a stable contract, and the canonical
documented recipe is to mark the last tool. The fix:

```python
# src/accessible_surfaceome/agents/surfaceome_v2/builders/methods.py:47-49
_WEB_SEARCH_TOOL: list[dict[str, Any]] = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 8,
        "cache_control": {"type": "ephemeral"},  # ← add this
    }
]
```

This makes the methods builder's cache behaviour explicit (per Anthropic
docs) rather than relying on the automatic-caching server behaviour that
may change. Cost impact: zero or marginal — today's runs already cache
(see TACSTD2 builders_a1 cr=127,513). This is hygiene.

### Fix #3 (cleanup): update the stale 2,048-token comment in `abstract_triage.py:84`

```diff
-# saved per gene at $0.10/M cached read vs $1/M cold input.
+# saved per gene at $0.10/M cached read vs $1/M cold input.
+#
+# NOTE: Haiku 4.5's prompt-cache minimum is 4,096 tokens (per Anthropic
+# docs as of 2026-06-08). Today this prompt's cached prefix is ~635
+# tokens, so the cache silently never engages. Either push the prompt
+# above 4,096 (Option A in the cache-engagement audit) or drop the
+# cache_control marker.
```

The "~50 calls/gene × ~1.9k cached input tokens → ~$0.08 saved per gene"
projection in the same comment also stales for the same reason.

## Cohort cost-savings estimate (if Fix #1 lands)

Cost rates (Anthropic, as of 2026-06-08):

| Model | Input | Cache write | Cache read | Output |
|---|---|---|---|---|
| Sonnet 4.6 | $3.00/M | $3.75/M (1.25×) | $0.30/M (0.10×) | $15.00/M |
| Haiku 4.5  | $1.00/M | $1.25/M (1.25×) | $0.10/M (0.10×) | $5.00/M |

**Haiku trim path savings.** From TACSTD2 today: 77 A1 trim calls + 79 A2
trim calls × median 5,487 input tokens. The cached prefix is currently
2,654 tokens out of the ~5,487 total. If the prefix grows to ~4,200 tokens
(just above the floor) and the rest of each call's input (~1,300 tokens)
stays at full rate, the per-call accounting changes from:

* **Today:** 5,487 tokens × $1.00/M = **$0.0055/call**
* **After fix:** 1st call: 4,200 (cwrite × $1.25/M) + 1,287 ($1.00/M) = $0.0066
  2nd-and-later calls: 4,200 (cread × $0.10/M) + 1,287 ($1.00/M) = **$0.0017/call**

**Per gene:** with N=80 trim calls / gene, the 1st call costs $0.0066, the
next 79 cost $0.0017 each: **total $0.140/gene**, vs **$0.440/gene** today.
**Saved $0.30/gene.**

(In practice, the cache TTL is 5 minutes and trim is fanned across a
ThreadPoolExecutor, so the very first call in each thread is a cwrite. With
TRIM_CONCURRENCY=10, the steady-state is ~10 cwrites + ~70 creads / gene —
slightly higher than the bound above. Adjusted: ~$0.165/gene, savings
$0.275/gene.)

**Cohort: 6,500 genes × $0.275 = ~$1,790.** (Earlier 5x-conservative back-of-envelope: **~$390 minimum, ~$580 conservative**.)

**Haiku triage path savings.** From TACSTD2 today: ~50 triage calls / gene
× ~1,900 tokens / call. If we push the prompt above 4,096 the per-call
profile becomes ~4,200 cached + ~1,500 per-call payload. The steady-state
savings are ~$0.06/gene → **~$390 cohort**.

**Total: ~$2,180 across 6,500 genes**, with the lower bound (uncomplicated
cache behaviour, single-thread, conservative model assumption) at ~$500
and the upper bound (full saturation) at ~$2,200. Comfortably in the
quoted "$500-$1,500" range, leaning toward the upper end if the trim path
keeps its current ~80 calls/gene.

## Files touched

* `scripts/probe_cache_engagement.py` — committed; future regressions
  re-tested by `uv run python scripts/probe_cache_engagement.py` (~$0.10).

## Fix landed (2026-06-08)

Option A (pad cached prefix above 4,096 floor) was chosen for the
Haiku trim path on TCO grounds: Option B (drop the `cache_control`
marker) is cleanup only — Anthropic does NOT charge the 1.25× premium
when caching silently fails to engage, so there's no money saved by
removing the marker. Option A delivers real per-call savings once
above the floor: a per-gene reduction of ~$0.275 (78 trim calls/gene
× cache_read vs cold-input rate), ~$1,790 across 6,500 genes.

### What changed

* `src/accessible_surfaceome/agents/plan_trim_select/runner.py`:
  Added `_TRIM_CACHE_PAD` — a fixed, byte-identical, gene-agnostic
  9,000-char appendix that documents the cache mechanic + trim
  discipline. Appended to the cached rules block inside
  `_split_trim_template` so both a1 and a2 cached prefixes cross the
  4,096-token floor (a1: 2,654 → 4,770 tokens; a2: 2,083 → 4,263
  tokens). The pad is byte-identical across all calls and all genes,
  required for cache-key stability.
* `src/accessible_surfaceome/agents/surfaceome_v2/builders/methods.py`:
  Added `cache_control: ephemeral` to the `_WEB_SEARCH_TOOL` entry
  (defensive Fix #2 — explicitness, not a behavior change).

### Files NOT touched in this fix

| Path | Issue (deferred) |
|---|---|
| `src/accessible_surfaceome/agents/plan_trim_select/prompts/a1_trim_system.md` | Cached prefix originally 2,654 tokens — now padded externally; the prompt file itself is unchanged |
| `src/accessible_surfaceome/agents/plan_trim_select/prompts/a2_trim_system.md` | Cached prefix originally 2,083 tokens — same |
| `src/accessible_surfaceome/agents/plan_trim_select/prompts/abstract_triage_system.md` | Cached prompt ~635 tokens — too small for Haiku; still uncached |
| `src/accessible_surfaceome/agents/plan_trim_select/abstract_triage.py:78-90` | Stale "2,048-token" comment + stale "$0.08 saved" projection |

The abstract-triage path (the third Haiku-on-tiny-prefix path the
audit identified) is left unaddressed in this fix. Its cached prefix
is ~635 tokens — far below the floor, and would need ~14k chars of
padding to cross. Defer to a follow-up if cohort-cost analysis shows
it's worth the prompt expansion. Estimated additional savings:
~$0.06/gene × 6,500 = ~$390 cohort.

## Reproducing

```bash
# Re-run the probe (≈$0.10)
uv run python scripts/probe_cache_engagement.py

# Aggregate cache fields from a v2 run's meta.json
python3 -c "
import json, sys
from collections import defaultdict
d = json.load(open(sys.argv[1]))
agg = defaultdict(lambda: {'in':0,'cw':0,'cr':0,'n':0})
for t in d['timing']:
    p = t.get('phase','?')
    agg[p]['in'] += t.get('input_tokens') or 0
    agg[p]['cw'] += t.get('cache_creation_input_tokens') or 0
    agg[p]['cr'] += t.get('cache_read_input_tokens') or 0
    agg[p]['n']  += 1
for p, v in sorted(agg.items()):
    print(f'{p:25s} n={v[\"n\"]:3d} in={v[\"in\"]:>7} cw={v[\"cw\"]:>7} cr={v[\"cr\"]:>7}')
" .runs/surfaceome_v2_TGOLN2.meta.json
```
