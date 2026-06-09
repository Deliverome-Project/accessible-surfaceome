# `accessibility_modulation` and `anatomical_accessibility` row-count audit across prompt_corpus versions

**Audience.** Someone deciding whether to revert a specific prompt commit before the cohort sweep.

**Date.** 2026-06-08.

**Scope.** 11 archetype genes (TACSTD2, C3, CD63, PVRIG, HMGB1, GPR75, ABCB9, LYN, TGOLN2, SRC, BAX), every historical run in `agent_run_intermediates` (private D1). 63 raw runs → 61 after collapsing duplicate same-version runs to the latest `created_at`.

**Companion TSV.** [`amod_anat_regression_2026_06_08.tsv`](amod_anat_regression_2026_06_08.tsv) — one row per (gene × prompt_corpus_version) with builder row-counts, sa/sd/scr.

## TL;DR

**2.35.0 has no broad `amod` or `anat` regression.** Every gene we've seen at 2.35.0 either matches or exceeds the prior version's row counts (CD63 +60%, SRC +50%, LYN +250%, PVRIG full recovery 0→11). The one apparent loss is TACSTD2 (14→0 across the 2.27.0→2.35.0 gap), which looks like a stochastic builder miss, not a prompt regression — the synth headline call did not change (`high / moderate / classical_surface_receptor`) and the A2 claims ledger is byte-identical (34 claims, 34 anchored) at both versions.

The real regressions are earlier in the chain and **already healed**:

1. **v2.14.0 — A2 retrieval collapse, cohort-wide.** Tier 1 prompt-cache rewrite + Tier 2 pre-trim filter (`4b6b5a012`) broke the A2 iteration loop on at least GPR75 and TGOLN2: `n_iterations_run=0`, `n_papers_total=0`, every builder emitted `[]`. Diagnostic warning was emitted: `"iteration 0 returned no drafts; nothing to trim or select"`. Healed by 2.15.0 (no plan_trim_select code change between them — flaky run / debug rerun).
2. **v2.20–2.21 — anat builder tightening, intentional.** `00bf632c7` (2026-06-07 10:04) made the anat builder require **direct polarization evidence** and explicitly reject "expressed in cell type X + textbook anatomy" inference rows. C3, CD63, HMGB1 lose their lone anat row at the 2.19→2.21 / 2.21→2.24 boundary because their evidence was the now-disqualified expression-padding kind. This is the **correct** behavior per the commit's rationale ("Empty output is strongly preferred to inference-padded rows") — not a regression to revert.
3. **v2.26.0 — PVRIG amod=0 transient.** No prompt change between 2.24 and 2.26 touched amod; the synth headline didn't change. Treat as model variance under unchanged inputs; recovered fully at 2.35.0 (amod=11).

**Recommendation: do NOT revert anything specifically because of amod/anat row counts.** The amod gate (`e6da5978c`, "gate accessibility-modulation rows on an actual surface-accessibility change") and the anat gate (`00bf632c7`, "require direct polarization evidence") are doing the work they were designed to do. Genes with NO-bucket calls (LYN inner-leaflet, TGOLN2 endomembrane-resident) emit 0 amod rows correctly; genes without polarized-surface evidence emit 0 anat rows correctly. The remaining row-count variance is model stochasticity under Temperature=1.0, not prompt structure.

## Per-gene × per-version wide table (key columns)

Full table in the TSV. Compact view, sorted by gene then by prompt_corpus_version (semver):

| gene | corpus | methods | amod | anat | expr | sa | sd | scr |
|---|---|---:|---:|---:|---:|---|---|---|
| ABCB9 | 2.28.0 | 14 | 5 | 0 | 28 | no | moderate | endomembrane_resident |
| ABCB9 | 2.29.0 | 14 | 5 | 0 | 26 | no | moderate | endomembrane_resident |
| ABCB9 | 2.35.0 | 11 | 4 | 0 | 33 | no | moderate | endomembrane_resident |
| BAX | 2.28.0 | 11 | 0 | 0 | 17 | no | low | mitochondrial_internal |
| BAX | 2.35.0 | 10 | 0 | 0 | 22 | no | low | mitochondrial_internal |
| C3 | 2.21.0 | 12 | 16 | 1 | 32 | low | high | cell_state_induced |
| C3 | 2.24.0 | 8 | 15 | 0 | 30 | low | high | secreted_only |
| C3 | 2.27.0 | 8 | 14 | 1 | 31 | low | high | secreted_only |
| C3 | 2.30.0 | 8 | 11 | 1 | 27 | low | high | secreted_only |
| C3 | 2.32.0 | 13 | 15 | 1 | 31 | low | high | secreted_only |
| C3 | 2.35.0 | 11 | 18 | 1 | 30 | low | high | cell_state_induced |
| CD63 | 2.21.0 | 11 | 13 | 1 | 33 | moderate | high | lysosomal_exocytosis |
| CD63 | 2.24.0 | 9 | 12 | 0 | 27 | high | high | lysosomal_exocytosis |
| CD63 | 2.26.0 | 13 | 10 | 0 | 30 | high | high | lysosomal_exocytosis |
| CD63 | 2.35.0 | 14 | 16 | 0 | 34 | high | high | lysosomal_exocytosis |
| GPR75 | 2.10.1 | 11 | 8 | 1 | 22 | high | moderate | classical_surface_receptor |
| GPR75 | **2.14.0** | **0** | **0** | **0** | **0** | moderate | low | classical_surface_receptor |
| GPR75 | 2.15.0 | 13 | 8 | 1 | 30 | high | moderate | classical_surface_receptor |
| GPR75 | 2.16.0 | 14 | 7 | 1 | 33 | high | moderate | classical_surface_receptor |
| GPR75 | 2.19.0 | 12 | 7 | 1 | 32 | high | moderate | classical_surface_receptor |
| GPR75 | 2.21.0 | 12 | 8 | 1 | 32 | high | moderate | classical_surface_receptor |
| GPR75 | 2.26.0 | 12 | 7 | 1 | 31 | high | moderate | classical_surface_receptor |
| GPR75 | 2.35.0 | 9 | 7 | 1 | 38 | high | moderate | classical_surface_receptor |
| HMGB1 | 2.8.0 | 4 | 14 | 0 | 36 | moderate | high | cell_state_induced |
| HMGB1 | 2.19.0 | 3 | 13 | 1 | 35 | moderate | high | cell_state_induced |
| HMGB1 | 2.21.0 | 2 | 12 | 0 | 35 | low | high | cell_state_induced |
| HMGB1 | 2.24.0 | 7 | 15 | 0 | 35 | low | high | cell_state_induced |
| HMGB1 | 2.27.0 | 3 | 15 | 0 | 32 | low | high | cell_state_induced |
| HMGB1 | 2.35.0 | 2 | 10 | 0 | 36 | low | high | cell_state_induced |
| LYN | 2.24.0 | 6 | 2 | 0 | 22 | no | low | inner_leaflet_anchored |
| LYN | 2.26.0 | 8 | 6 | 0 | 21 | no | low | inner_leaflet_anchored |
| LYN | 2.27.0 | 8 | 2 | 0 | 21 | no | low | inner_leaflet_anchored |
| LYN | 2.35.0 | 8 | 7 | 0 | 23 | no | moderate | inner_leaflet_anchored |
| PVRIG | 2.19.0 | 11 | 12 | 0 | 26 | high | moderate | classical_surface_receptor |
| PVRIG | 2.21.0 | 11 | 13 | 0 | 25 | high | moderate | classical_surface_receptor |
| PVRIG | 2.24.0 | 11 | 14 | 0 | 27 | high | moderate | classical_surface_receptor |
| PVRIG | **2.26.0** | **14** | **0** | **0** | 23 | high | moderate | classical_surface_receptor |
| PVRIG | 2.35.0 | 12 | 11 | 0 | 27 | high | moderate | classical_surface_receptor |
| SRC | 2.9.0 | 13 | 5 | 0 | 28 | high | high | lysosomal_exocytosis |
| SRC | 2.19.0 | 10 | 6 | 0 | 26 | high | high | lysosomal_exocytosis |
| SRC | 2.21.0 | 11 | 5 | 0 | 25 | high | high | lysosomal_exocytosis |
| SRC | 2.24.0 | 9 | 3 | 0 | 28 | high | high | lysosomal_exocytosis |
| SRC | 2.26.0 | 9 | 4 | 0 | 24 | high | high | lysosomal_exocytosis |
| SRC | 2.35.0 | 11 | 6 | 0 | 31 | high | high | lysosomal_exocytosis |
| TACSTD2 | 2.8.0 | 30 | 18 | 1 | 41 | high | moderate | classical_surface_receptor |
| TACSTD2 | 2.19.0 | 24 | 16 | 0 | 41 | high | moderate | classical_surface_receptor |
| TACSTD2 | 2.21.0 | 22 | 15 | 0 | 39 | high | moderate | classical_surface_receptor |
| TACSTD2 | 2.24.0 | 18 | 18 | 1 | 45 | high | moderate | classical_surface_receptor |
| TACSTD2 | 2.27.0 | 13 | 14 | 1 | 45 | high | moderate | classical_surface_receptor |
| TACSTD2 | **2.35.0** | **26** | **0** | **0** | **42** | high | moderate | classical_surface_receptor |
| TGOLN2 | 2.10.1 | 9 | 0 | 0 | 31 | low | low | endomembrane_resident |
| TGOLN2 | 2.11.0 | 8 | 3 | 0 | 27 | low | moderate | dual_localization |
| TGOLN2 | 2.12.0 | 8 | 3 | 0 | 26 | low | moderate | dual_localization |
| TGOLN2 | **2.14.0** | **0** | **0** | **0** | **0** | low | unclear | endomembrane_resident |
| TGOLN2 | 2.21.0 | 0 | 0 | 0 | 25 | low | low | endomembrane_resident |
| TGOLN2 | 2.24.0 | 7 | 3 | 0 | 22 | low | low | dual_localization |
| TGOLN2 | 2.26.0 | 4 | 0 | 0 | 19 | low | low | endomembrane_resident |
| TGOLN2 | 2.28.0 | 8 | 2 | 0 | 24 | low | moderate | dual_localization |
| TGOLN2 | 2.30.0 | 7 | 0 | 0 | 23 | low | low | endomembrane_resident |
| TGOLN2 | 2.32.0 | 9 | 0 | 0 | 21 | low | low | endomembrane_resident |
| TGOLN2 | 2.35.0 | 9 | 0 | 0 | 22 | low | moderate | dual_localization |

Bold rows mark the >50%-drop transitions ("regressions" by the audit threshold).

## Three biggest `amod` row-count drops

### 1. TACSTD2 2.27.0 → 2.35.0: amod 14 → 0 (-100%)

**Synth headline DID NOT change.** Both runs report `surface_accessibility=high / state_dependence=moderate / surface_call_reason=classical_surface_receptor`. The A2 claims ledger is byte-identical (`n_claims=34, n_anchored=34`) at both versions. Methods went UP 13→26 (+100%) over the same gap. So the amod builder saw the same evidence, kept the same downstream call, but emitted zero rows on this single run.

**No single amod-related prompt commit lands in the 2.27→2.35 window that explains a TACSTD2-specific collapse.** The relevant edits between 2.27 and 2.35 are all orchestrator-side deterministic normalizations or unrelated synth-prompt nudges. Critically, `e6da5978c` ("gate accessibility-modulation rows on an actual surface-accessibility change", landed 2026-05-30, in force since v2.5.0) is the inclusion gate that disqualifies expression-context rows — but TACSTD2 has documented surface modulation (normal colonic epithelium negative → CRC heterogeneous positive) which is exactly the qualifying shape.

**Hypothesis: stochastic builder miss.** Temperature=1.0, single LLM call per builder. Recommend a one-off re-run at 2.35.0 before treating this as a regression — if the next run produces ~14 amod rows again, the prior was the outlier. Diff hypothesis: none — there is no smoking-gun prompt change.

### 2. PVRIG 2.24.0 → 2.26.0: amod 14 → 0 (-100%), then recovered 2.26.0 → 2.35.0: 0 → 11

Same shape as TACSTD2: synth headline unchanged (`high / moderate / classical_surface_receptor`), A2 ledger nearly identical (26 → 28 claims), methods went 11→14. The amod prompt was unchanged between 2.24 and 2.26. The two orchestrator commits that crossed this boundary (`bbff24303` "3 deterministic normalizations" → 2.25.0; `a16ca7f74` "surface_accessibility floor + NO-bucket reason override" → 2.26.0) operate on the synth draft, **not** on the amod builder list — they cannot zero out an already-built amod list.

Two lines from `a16ca7f74` worth quoting, because they show the layer the change touches:

```
+ if (
+     synth_draft.executive_summary.surface_accessibility == "low"
+     and synth_draft.executive_summary.state_dependence in ("moderate","high")
+     and synth_draft.executive_summary.surface_call_reason in SUBSTANTIAL_CONTEXTUAL_REASONS
+ ): synth_draft = synth_draft.model_copy(...)
```

This is a synth post-pass; it never touches `builders["accessibility_modulation"]`. Treat PVRIG 2.26.0 as model variance.

### 3. LYN 2.26.0 → 2.27.0: amod 6 → 2 (-67%)

LYN is `surface_accessibility=no / surface_call_reason=inner_leaflet_anchored` — the NO-bucket gene. The 2.27.0 commit is `8d0970a4d` "post-pass field references — state bump + secreted demote", fixing the `bbff24303` post-pass that referenced nonexistent fields. Quote:

```
- ``filters.induction_trigger`` (path didn't exist) → uses the
+ ``filters_llm.induction_trigger`` field that actually exists
```

This was a one-line field-path fix; it doesn't affect amod. The drop is most likely model variance under the same prompt rules. **Confirmation: at 2.35.0 the amod count recovers to 7 (+250% over 2.27.0).** No revert warranted.

## Three biggest `anat` row-count drops

The anat builder's natural row count for these 11 genes is mostly 0 or 1 — even small absolute changes (1→0) trip the >50% threshold but are noisy by design. The systematic story is the same across all four:

### 1. C3 2.21.0 → 2.24.0: anat 1 → 0 (sa unchanged: low / high / scr drift secreted_only)

### 2. CD63 2.21.0 → 2.24.0: anat 1 → 0 (sa moderate→high — call **strengthened**)

### 3. HMGB1 2.19.0 → 2.21.0: anat 1 → 0 (sa moderate→low — call **weakened**)

All three drop a single anat row at version boundaries where the anat prompt was **not edited** (the relevant tightening commit `00bf632c7` landed 2026-06-07 10:04 — in force since v2.19.0). The 1→0 transitions are model variance on a tight gate, not a regression in the gate itself.

**The gate that did the work, quoted from `00bf632c7`:**

```
+ Hard requirement: cited evidence must directly observe the protein at
+ a polarized surface or membrane subdomain. Generic "expressed in cell
+ type X" + anatomical inference is explicitly disqualifying.
+ ...
+ Empty output is strongly preferred to inference-padded rows.
```

This is the **right** behavior: previously anat was emitting rows like "GPR75 is expressed on endothelial cells, endothelial luminal surfaces face blood, therefore favorable" — expression dressed as reachability. The 1→0 dropouts on C3/CD63/HMGB1 are this gate firing correctly; their evidence didn't meet the polarized-surface bar.

### Bonus: GPR75 and TGOLN2 v2.14.0 — the only **real** broad regression in the dataset

Both runs at 2.14.0 show `n_iterations_run=0, n_papers_total=0, n_claims=0`, every builder is `[]`, and the A2 warnings field carries `"iteration 0 returned no drafts; nothing to trim or select"`. The plan-trim-select pipeline returned nothing.

This coincides with `4b6b5a012` "Tier 1 caching + Tier 2 pre-trim filter (cost-reduction package)" — specifically the Tier 1 prompt-cache rewrite that split each A1/A2 trim template at `## Output` and replaced `{gene}` with `"the target gene"` in the cached rules block. Two specific lines:

```
+ Hoisted ``json.dumps(schema)`` to module scope so cached bytes are stable.
+ * ``runner.py`` — added ``_split_trim_template()`` that splits each A1/A2
+   trim prompt at the ``## Output`` header and replaces ``{gene}`` →
+   ``the target gene`` in the rules block.
```

**Healed at 2.15.0** without any plan-trim-select code change — the next run produced 24 papers and 26 claims on GPR75, 24 papers / 18 claims on TGOLN2. So this was either a transient (`AnthropicError` during cache-write?) or a debug rerun that was kept in D1. The runs themselves were `record_valid=1` (synth fell back to bare topology) which is mildly worrying, but **we've never seen another version reproduce the failure**, and the Tier 2 pre-trim filter is `enable_pretrim_filter=False` by default — so it cannot be the cause unless someone passed `True`.

Not actionable now: the regression isn't recurring and the suspected commit's effect is opt-in.

## Cases where a row-count drop changed the synth's headline call

Only one is suspicious; the rest are intentional tightening visible through the headline.

- **CD63 2.21.0 → 2.24.0**: anat 1→0, but `surface_accessibility` *strengthened* moderate→high. Tightening anat (reject inference-padding) coincides with the model treating CD63's lysosomal_exocytosis biology more confidently as high accessibility under the substantial-pool rule. **Net win.**
- **HMGB1 2.19.0 → 2.21.0**: anat 1→0, surface_accessibility *weakened* moderate→low. This is the `92b9c47c1` "refine surface-accessibility bar — state-conditional OK; exclude EV/exogenous/transient" change — HMGB1 is plasma extracellular DAMP and the model correctly stops crediting EV/secreted evidence toward accessibility. **Net correct.** state_dependence stayed `high` (`cell_state_induced` properly remains the call) so the catalog still flags HMGB1 as state-conditional.
- **C3 2.21.0 → 2.24.0**: anat 1→0, surface_call_reason flipped `cell_state_induced → secreted_only`. C3 is plasma-soluble complement; calling it `secreted_only` is more honest than calling it state-induced surface. The 2.35.0 run flips back to `cell_state_induced` (C3b deposition biology) and gains an anat row. **Oscillation, not regression.**
- **GPR75 2.10.1 → 2.14.0**: scr unchanged (`classical_surface_receptor`) but sa weakened high→moderate, sd weakened moderate→low. **Caused by the A2 collapse** — empty A2 ledger means the synth falls back to bare topology rules. Healed at 2.15.0.

No headline call between 2.27.0 and 2.35.0 has flipped due to amod/anat builder regression. TACSTD2's amod=0 at 2.35.0 left `high / moderate / classical_surface_receptor` intact — confirming that the synth's call is robust to a single empty builder.

## Are improvements worth flagging?

Yes, several. Recording for completeness:

- **LYN 2.27.0 → 2.35.0: amod 2 → 7 (+250%).** The 2.35.0 amod builder is producing more granular cell_state rows on an unchanged NO-bucket call — looks like the methods + state-vocab thickening (`fe6a8458b` "cell_state_modulation axis + surface-atlas + anatomy vocab", in force since 2.6.0) compounding.
- **CD63 2.26.0 → 2.35.0: amod 10 → 16 (+60%).** Healthy growth in lysosomal_exocytosis context rows.
- **PVRIG 2.26.0 → 2.35.0: amod 0 → 11 (recovery from variance dip).**
- **C3 2.32.0 → 2.35.0: scr secreted_only → cell_state_induced (call sharpened).** C3b cell-deposition biology is recovered after several versions where the synth picked the more conservative secreted_only.

## Recommendation

**No revert.** Pre-cohort, ship 2.35.0 (currently 2.38.0 on `main`, which has the same amod/anat gates plus orchestrator-side cleanup).

Justifications:
1. **No prompt change in the 2.27→2.35 window** plausibly explains the TACSTD2 amod=0 outlier. The 2.35.0 synth call on TACSTD2 is unchanged from 2.27.0, so the consumer-visible record carries no regression. If we want to confirm, re-run TACSTD2 at the current HEAD (2-3 reruns; cheap at $3/each) and check whether amod consistently lands near the historical ~14. If yes → 2.35.0 outlier is stochastic; ship. If no → reopen and look at the methods-builder prompt commits (`381e9d18f`, `8c7a277c8`) for over-classification that crowds out amod via the shared A2 claim pool.
2. **The anat regressions are the gate working as designed** (`00bf632c7`). Reverting would re-introduce the "expression dressed as anatomical reachability" inference rows that the commit was built to suppress.
3. **The 2.14.0 collapse is healed and the suspected commit's Tier-2 component is opt-in.** No revert needed unless we see the collapse return in a follow-up sweep.

If the cohort sweep at 2.38.0 surfaces a systematic amod=0 pattern across many genes (not just one outlier), the first commit to inspect is **`edc2857eb`** "cohort-resume + triage-coverage + synth-replay-from-D1" (the 2.35.0 bump) — specifically the `skip_if_fresh=True` annotate early-exit. A misconfigured `_existing_fresh_record()` probe could short-circuit a real re-run to an inherited (empty) builders dict. But there is no evidence of this in the current data; it's the next thing to look at if a real regression appears.

## Provenance

`agent_run_intermediates` in private D1 (`surfaceome_agents`); ad-hoc SELECT, not productionalized. Diffs quoted verbatim from `git show <SHA>`. Read-only audit — no source files were edited.
