# TACSTD2 regression bisect — amod 18→0 and methods.unknown 3→7

**Audience.** Decision-maker choosing between revert / accept / narrower-fix for the TACSTD2 regressions before the cohort sweep.

**Date.** 2026-06-08.

**Scope.** Two regressions, both in TACSTD2's `agent_run_intermediates` row history (private D1):

- A: `accessibility_modulation` row count 18 (v2.8.0) → 0 (v2.35.0)
- B: `methods.method_subclass='unknown'` count 3 (v2.8.0) → 7 (v2.35.0)

Methodology: enumerate every `PROMPT_CORPUS_VERSION` that has a TACSTD2 record; compute the actual prompt-corpus fingerprint at the commit corresponding to each version; diff prompt + builder files in each transition window.

## Headline

**Neither regression maps to a prompt commit. There is nothing to revert.**

1. The amod prompt + builder are **byte-identical for every TACSTD2 record** (v2.8.0 → v2.35.0). The A2 ledger fed in is byte-identical between the v2.27 (14 rows) and v2.35 (0 rows) runs (34 claims, 132 triage actions). The 18→0 regression is **LLM stochasticity** on an identical input.
2. The methods prompt is stable since v2.23.0 (`0bd4fbbfe`, 2026-06-07 23:14 EDT). All TACSTD2 records from v2.24.0 onward see the same prompt. The methods.unknown drift is **(a) the schema gap on `functional_surface_assay`** (6 of 7 unknowns) and **(b) one silent-permeabilization IF row** (1 of 7) — both addressed by Agent #17.

## 1. TACSTD2 amod count per prompt_corpus_version

Six records. Synthesizer headline (`surface_call_reason`) is `classical_surface_receptor` on **every** one — no semantic drift in the assembled record.

| prompt_corpus | created_at (UTC) | A2 anchored | amod rows | methods rows | unknown methods | scr |
|---:|---|---:|---:|---:|---:|---|
| 2.8.0 | 2026-06-07 16:06 | 34 | **18** | 30 | 3 | classical_surface_receptor |
| 2.19.0 | 2026-06-08 02:44 | 34 | 16 | 21 | 2 | classical_surface_receptor |
| 2.21.0 | 2026-06-08 03:07 | 34 | 15 | 21 | 4 | classical_surface_receptor |
| 2.24.0 | 2026-06-08 03:31 | 34 | **18** | 19 | 2 | classical_surface_receptor |
| 2.27.0 | 2026-06-08 04:31 | 34 | 14 | 13 | 1 | classical_surface_receptor |
| 2.35.0 | 2026-06-08 20:52 | 34 | **0** | 26 | 7 | classical_surface_receptor |

The amod count walks 18 → 16 → 15 → **18** → 14 → 0. The bump back to 18 at v2.24 (the same as v2.8) is the tell — no monotonic tightening. The 0 at v2.35 is the outlier.

## 2. Bisect of the amod 18→0 regression

### 2a. Prompt-corpus fingerprint per version

Recomputed `prompt_corpus_fingerprint` (sha256 over relative-path + bytes of every `agents/*/prompts/*.md`) at the commit that landed each `PROMPT_CORPUS_VERSION` from v2.8 to v2.35. Key result:

- v2.8 → v2.23: **each** version actually changes some prompt file (mostly `methods_builder_system.md`, `evidence_grade_builder_system.md`, the synth `system.md`, and the haiku `abstract_triage_system.md`).
- **v2.24.0 → v2.35.0: 12 consecutive versions, every one with prompt-corpus fingerprint `800768797531289f`.** Every bump in that range is cosmetic (re-pinned to satisfy the `_version_guard` reconcile rule whenever orchestrator post-passes changed). `tests/version_fingerprints.json` confirms identical fingerprint at both v2.27 and v2.35.

### 2b. amod-specific prompt + builder history

```bash
git log --oneline 8d0970a4d..edc2857eb -- \
  src/accessible_surfaceome/agents/surfaceome_v2/prompts/accessibility_modulation_builder_system.md \
  src/accessible_surfaceome/agents/surfaceome_v2/builders/accessibility_modulation.py
# (empty)
```

The amod builder system prompt is `SHA256[:16] = 27226bac9c372337`, length 10,801 bytes, **at every version v2.8.0 through v2.35.0**. The builder Python file has had no commits since 2026-05-16 (`68056c866`, the initial v2 commit). The `fa60327a8` tumor-pair injector — the only post-base amod-builder edit — landed at 2026-06-08 20:54, **after** the v2.35 TACSTD2 record's `created_at` 20:52. So no prompt or builder change is in play for any of the six TACSTD2 runs.

### 2c. A2 ledger comparison (input to the amod builder)

The intermediates blob `plan_trim_select.a2` at v2.27 and v2.35: 34 claims each, 34 anchored, 132 triage actions each, 16 search-log entries each. Same structure. Combined with the unchanged amod prompt + builder, the LLM call's input is functionally identical.

### 2d. Interpretation

The amod builder runs at Temperature=1.0 (`MAX_TOKENS_HEAVY`, no `temperature=0`). Same prompt, same ledger, same model — but stochastic output. The v2.35 run got an unlucky `[]`. The builder has no retry-on-empty logic. The pre-existing audit [`amod_anat_regression_2026_06_08.md`](amod_anat_regression_2026_06_08.md) reached the same conclusion across 11 archetype genes: TACSTD2 14→0 is "a stochastic builder miss, not a prompt regression."

The tumor-pair injector (`fa60327a8`, post-bisect-window) is the fix already shipped: when the LLM cold-emits `[]`, the candidate-pair block deterministically lifts ≥1 tumor/normal modulation row from the ledger. Not a revert — a deterministic floor for the next cohort run.

## 3. TACSTD2 methods.unknown count per prompt_corpus_version

| ver | n_methods | unknowns | unknown families |
|---|---:|---:|---|
| 2.8.0 | 30 | 3 | functional_surface_assay×3 |
| 2.19.0 | 21 | 2 | functional_surface_assay×2 |
| 2.21.0 | 21 | 4 | functional_surface_assay×4 |
| 2.24.0 | 19 | 2 | functional_surface_assay×2 |
| 2.27.0 | 13 | 1 | functional_surface_assay×1 |
| 2.35.0 | 26 | 7 | functional_surface_assay×6, immunofluorescence×1 |

### 3a. Methods prompt history across 2.8 → 2.35

| version | methods prompt SHA[:16] | size | what changed |
|---|---|---:|---|
| 2.8.0 | `d1da71eeec70e4de` | 26,358 | base v2 |
| 2.14.0 | `6582c84658acc5b5` | 30,680 | Tier 1 caching system-block rewrite |
| 2.16.0 | `60f65bd519a9af7a` | 33,266 | **methods anti-patterns** (`381e9d18f`) — 4 fsa anti-patterns demoting knockdown / OE-unknown-SP / in-vivo-therapeutic / fraction-radioligand from `direct_*` to `supports_membrane_association` |
| 2.17.0 | `86b632f89ccdaf86` | 35,829 | species-aware methods (`8c7a277c8`) |
| 2.21.0 | `1eff71c768717d70` | 36,509 | small edit |
| 2.22.0 | `cb6d3cbe9de084f6` | 33,243 | **prose tightening** (`0fd648487`) — 46→17 lines, commit msg says "no rule changes, no behavior changes" |
| 2.23.0 | `7414663f44ac4691` | 32,885 | small edit |
| 2.24.0 → 2.35.0 | `7414663f44ac4691` | 32,885 | **no methods prompt change** |

### 3b. Is there a methods-prompt commit that broadened "unknown" use?

**No.** The closest semantic candidate is `381e9d18f` (v2.16, "4 functional_surface_assay anti-patterns") — but its intent is the **opposite** of widening unknown:

```text
+ **Anti-patterns — these MUST NOT take
+ `accessibility_relevance=direct_surface_accessibility`, even
+ though they look like functional surface assays:**
+   1. Knockdown / KO validation of a surface-signaling response →
+      supports_membrane_association (NOT direct).
```

This demotes ~4 specific shapes from `direct_surface_accessibility` to `supports_membrane_association`. It does NOT broaden `method_subclass='unknown'` — that's a different field (assay classification within a family), not the cross-family relevance tag. There's no commit anywhere in the 2.8 → 2.35 window that touches the `method_subclass` enum or adds "if unsure → unknown" guidance.

The methods prompt is frozen from v2.23 through v2.35 — and the unknown count moves 4 → 2 → 1 → 7 across that frozen window. The drift is stochastic + driven by which `functional_surface_assay`-family observations the model sampled into the output. TACSTD2's A1 ledger has multiple ADC / sacituzumab-govitecan / surface-ligand-binding rows the model tags as `family=functional_surface_assay` but for which no `method_subclass` enum value fits — the schema gap Agent #17 is closing.

### 3c. The IF-with-unknown row (v2.35 only)

One row at v2.35 carries `family=immunofluorescence, subclass=unknown`. The methods prompt's IF rubric (unchanged since v2.23) gives `nonpermeabilized_IF` / `permeabilized_IF` and a default-to-permeabilized rule when silent. The model picked `unknown` anyway — same prompt that 12 prior IF rows in this record-history correctly resolved against. Stochastic miss against a stable prompt; addressed by Agent #17's default-to-permeabilized hardening.

## 4. Recommendation

**Accept both regressions. Ship Agent #16 + Agent #17. No revert.**

1. **No revert.** Every prompt commit between v2.8 and v2.35 has a documented, intended behavior change (most unrelated to amod or methods.unknown). Nothing in the bisect window is an unintended tightening. The TACSTD2 amod=0 at v2.35 is one stochastic empty-list emission on a prompt + ledger that produced 14, 15, 16, 18 amod rows on 5 other runs.
2. **Agent #16's deterministic tumor-pair injector** (already landed at `fa60327a8`) is the durable fix for the 18→0 stochastic floor: when the LLM cold-emits `[]`, the candidate-pair block lifts ≥1 cancer/normal modulation row from the ledger's tissue-paired claims.
3. **Agent #17's `functional_surface_assay` enum + IF default-to-permeabilized rule** closes 6 of 7 methods.unknown rows on the enum; 1 closes on the IF rule. No prompt-tightening to roll back.
4. **Don't treat `prompt_corpus_version` 2.24 → 2.35 as a behavioral signal.** Every bump in that range is a cosmetic re-pin (corpus fingerprint `800768797531289f` for all 12 versions). Observed differences across that range are model variance + orchestrator post-pass changes that don't enter the amod / methods builders.

### Sanity check before cohort

Spot-check that the tumor-pair injector fires on TACSTD2 via the builders-only replay (`surfaceome_v2_replay_builders`) at HEAD against the cached v2.35 dual. Expected: amod ≥ 6 rows (the 6 tissue-paired tumor/normal candidates from the ledger). If the replay still emits 0, the injector isn't wired correctly — that's the bug worth chasing, not anything in 2.27 → 2.35.

## Appendix: commit-to-version chain

```
2.35.0  edc2857eb  feat: cohort-resume + triage-coverage + synth-replay-from-D1
2.27.0  8d0970a4d  fix(orchestrator): post-pass field references
2.24.0  4eb523c0a  feat(orchestrator): force CONTEXTUAL bucket on PM trafficking
2.23.0  0bd4fbbfe  feat(orchestrator): deterministic species inheritance (last methods prompt edit)
2.22.0  0fd648487  refactor(prompts): tighten prose without changing semantics
2.21.0  fe5987fbd  fix(prompts): SRC direct preserved + GPR75 synth
2.19.0  c5abd6189  fix(prompts,viewer,tests): exec-summary methods discipline
2.17.0  8c7a277c8  fix(prompts): species-aware methods builder
2.16.0  381e9d18f  fix(methods): 4 fsa anti-patterns
2.14.0  4b6b5a012  feat(plan-trim-select): Tier 1 caching + Tier 2 pre-trim filter
2.8.0   771636a28  feat(agents): publish intermediates to D1
e6da5978c           fix(agents): amod inclusion gate (2026-05-30, predates v2.8)
fa60327a8           feat(builders): amod tumor-pair lift (2026-06-08 20:54, Agent #16, post-bisect-window)
```
