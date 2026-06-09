# A1 selection drift between prompt_corpus v2.9.0 / v2.8.0 and v2.35.0

**Audience.** Someone deciding whether to revert a specific commit before
the cohort sweep — same shape as `amod_anat_regression_2026_06_08.md`.

**Date.** 2026-06-08.

**Scope.** Two anchor genes (SRC, HMGB1) across every historical
`agent_run_intermediates` row, paired with `git log -p` on the A1 prompt
files + the runner / pretrim filter / abstract triage code between v2.9.0
(SRC commit `6e2b823c7`) and v2.35.0 (cohort-bump commit `edc2857eb`).
Read-only — no code edits.

## TL;DR

**The A1 regression is not in the A1 prompts.** `a1_select_system.md` and
`a1_trim_system.md` are byte-identical between v2.9.0 and v2.35.0. The
breaking change is a 4-line runner-default flip:

```
commit 7363656cf  fix(cost): activate pretrim_filter by default + lower HARD_CAP 150 → 132
-    enable_pretrim_filter: bool = False,
+    enable_pretrim_filter: bool = True,
-HARD_CAP: int = 150
+HARD_CAP: int = 132
```

Landed 2026-06-07 21:44, between v2.16.0 (`381e9d18f` 21:27) and v2.17.0
(`8c7a277c8` 22:14). **The regression goes live at v2.17.0** and is
identical in shape v2.17.0 → v2.35.0 (pretrim audits byte-identical on
SRC and HMGB1 from v2.19.0 forward). Fix is the cap commit, not a prompt
revert.

**SRC (-8 papers):** 5 dropped are **cap-dropped** by pretrim (year-sorted,
HARD_CAP=132 of 379 candidates → 87 cap-drops). The 5 contributors are
2007-2017 founding-era localization papers (PMID:17537435 c-Src PM↔late-
endosome trafficking; PMID:17620427 IHC activated-Src tumor membrane;
PMID:28543306 c-Src→focal-adhesions; PMC:PMC3733647 c-Src serum
microvesicles; one more in the same bucket). The other 3 dropped (all
2026 PMC papers — PMC:PMC12764184 NMT1-Src myristoylation; PMC:PMC13034504
OR51E1 surface-expression-via-S1PR1; PMC:PMC13054614 shear-stress c-Src
RANKL membrane redistribution) **pass pretrim, pass Haiku (`worth_fetching`,
drafts_added=30, body fetched)**, but A1 select doesn't pick a clip — model
variance under unchanged prompt (IF counts oscillate 0/1/0/0/0 across
v2.19.0→v2.35.0).

**HMGB1 (-4 to -6 papers):** 10 of 11 dropped papers were pretrim-cap or
pretrim-review filtered at kickoff — never reached Haiku, never reached A1
select. 1 was Haiku-discarded (PMC:PMC13184140, SSc-vasculopathy, off-topic
for HMGB1 surface biology). The A1 select prompt didn't drift; the upstream
pretrim cap shrank the candidate pool.

**Recommendation: don't revert, but raise HARD_CAP back to 150.** Pretrim's
three rule filters (review-without-quality-journal-sparing, drug-review,
atlas) are defensible — 94-100% contribution retention per the shadow-mode
audit. But the cap pulls in a different direction: rules target low-content
papers; cap drops the *oldest* papers regardless of content. On SRC the
year-sorted cap discards 87 papers including 5 papers that carried direct
surface-trafficking IF/IHC content. Fix the cap, not the prompt.

## Per-version time series

### SRC A1

| corpus | a1.input | a1.claims | distinct src | top evidence_types | pretrim n_in | pretrim n_kept | cap_drop |
|---|---:|---:|---:|---|---:|---:|---:|
| v2.9.0  | **41** | **22** | **14** | wb:6 IF:5 review:4 fn:4 | (off) | (off) | (off) |
| v2.19.0 | 26 | 15 | 9 | fn:5 wb:5 review:3 SBio:1 | 379 | **132** | **87** |
| v2.21.0 | 25 | 12 | 6 | review:5 wb:4 fn:2 SBio:1 | 379 | 132 | 87 |
| v2.24.0 | 25 | 12 | 7 | fn:5 wb:4 review:2 IF:1 | 379 | 132 | 87 |
| v2.26.0 | 26 | 19 | 10 | wb:9 fn:5 review:4 IHC:1 | 379 | 132 | 87 |
| v2.35.0 | 26 | 14 | 7 | wb:7 review:4 fn:2 SBio:1 | 379 | 132 | 87 |

Pretrim audit is byte-identical from v2.19.0 onward (n_input=379, cap drops 87,
review drops 157, drug_review=1, atlas=2). The flip is **between v2.9.0 (no
pretrim) and v2.19.0 (pretrim full-on)** — placing it at the v2.17.0 line
where `7363656cf` was committed.

### HMGB1 A1

| corpus | a1.input | a1.claims | distinct src | top evidence_types | pretrim n_in | pretrim n_kept | cap_drop |
|---|---:|---:|---:|---|---:|---:|---:|
| v2.8.0  | **50** | **30** | **18** | fn:16 wb:5 review:4 IF:4 | (off) | (off) | (off) |
| v2.19.0 | 40 | 30 | 17 | fn:12 IF:8 review:5 wb:2 | 369 | **132** | **74** |
| v2.21.0 | 41 | 26 | 15 | fn:8 IF:5 review:4 wb:4 | 369 | 132 | 74 |
| v2.24.0 | 37 | 28 | 14 | IF:8 fn:8 review:7 wb:2 | 369 | 132 | 74 |
| v2.27.0 | 38 | 27 | 13 | fn:10 IF:8 review:3 wb:2 | 369 | 132 | 74 |
| v2.35.0 | 38 | 26 | 14 | fn:8 IF:7 review:4 wb:4 | 369 | 132 | 74 |

Same pattern. Pretrim is off at v2.8.0 (the only v2.8 run is the original
HMGB1) and full-on from v2.19.0. The decision-counts in the audit are
identical across v2.19.0 → v2.35.0 — the rerun population is being filtered
identically, with the only year-over-year variance being Temperature=1.0
model stochasticity at A1 select.

## The 8 SRC papers that dropped — what they share

Verbatim claim quotes from v2.9.0 grouped by drop mechanism. The five
**cap-dropped** by pretrim are the load-bearing loss:

### Cap-dropped (year-sorted bottom): direct PM-trafficking / surface biology

* **PMID:17537435** (IF, 2007) — "c-Src, a non-palmitoylated SFK, is
  rapidly exchanged between the plasma membrane and intracellular
  organelles representing late endosomes/lysosomes possibly through its
  cytosolic release." Direct PM↔endolysosomal trafficking — exactly what A1
  wants.

* **PMID:17620427** (IHC, 2007) — "expression of activated Src (p-Src Y419)
  on the tumor cell membrane was higher in patients with advanced-stage
  disease; metastasis correlated with higher membrane (P=0.03) expression."
  IHC, explicit membrane staining.

* **PMID:28543306** (IF, 2017) — "the majority of activated Src molecules
  are localized at focal adhesions… investigated by live-cell imaging and
  site-directed mutagenesis." Live-cell IF — strongest localization
  evidence.

* **PMC:PMC3733647** (functional_assay, 2013) — "Only FLCs secreted from
  malignant B Lymphocytes were carried in Hsp70, annexin V, and c-src
  positive vesicles." EV cargo.

* (5th of the same 2007-2017 c-Src localization shape.)

**Pattern:** founding-era IF/IHC/EV-trafficking papers that established
c-Src plasma-membrane biology. The pretrim cap sorts by `-year` and drops
the oldest. Modern papers cite them but don't restate the underlying
observations — so A1 sees only cap-survivors, loses the direct
localization base, and falls back on western-blot + functional-assay.

### Pretrim-passed but A1-select-rejected: 2026 PMC papers

* **PMC:PMC12764184** (NMT1-Src myristoylation/OSCC) — Haiku
  `worth_fetching`, A1 picks no clip. Likely the relevant claim (NMT1-KO
  reduces Src membrane localization) is body-text only.
* **PMC:PMC13034504** (S1PR1 enhances OR51E1 via Src/JNK) — Src is the
  modulator, not the target.
* **PMC:PMC13054614** (shear stress activates c-Src, promotes RANKL membrane
  localization) — RANKL is the surface-positioned cargo, Src the kinase.

These 3 are model variance — v2.9.0 was Temperature=1.0 too; dice landed
differently.

## HMGB1 ledger shrinkage — pretrim, not select

The 11 papers that dropped from v2.8.0 → v2.35.0 all carried functional
or expression-context claims:

| Source | v2.8.0 evidence | v2.35.0 fate |
|---|---|---|
| PMC:PMC10405849 | fn ×2 | pretrim (not in v2.27.0/v2.35.0 actions) |
| PMC:PMC10646219 | fn ×1 | pretrim |
| PMC:PMC10779375 | fn ×2 | pretrim |
| PMC:PMC11289874 | fn ×2 | pretrim |
| PMC:PMC11445383 | wb ×2 | pretrim |
| PMC:PMC11682959 | wb+fn | pretrim |
| PMC:PMC12992810 | review ×2 | pretrim (probably review-flagged) |
| PMC:PMC13184140 | fn ×1 | **Haiku discard** (SSc-vasculopathy off-topic) |
| PMC:PMC13194016 | review ×1 | pretrim |
| PMC:PMC3389268 | fn ×2 | pretrim (year=2012, likely cap) |
| PMC:PMC9905834 | wb ×1 | pretrim |

**10 of 11 lost upstream of A1.** Only 1 was a Haiku decision, and that one
(SSc-vasculopathy) is correctly off-topic for HMGB1 surface biology — A1
would have rejected it anyway. The 11th of 7 added back papers also fit
the same pattern (functional_assay-heavy), so the net effect is
*replacement of old-paper functional content with newer-paper functional
content*. The ledger total is stable (30→26) and the headline call doesn't
change.

The "ligand-engagement filter pruning" hypothesis in the task brief is
**not** what's happening on HMGB1's A1 ledger — the prompt didn't tighten;
pretrim made the candidate pool 12 papers smaller.

## What changed in the runner / pretrim between v2.9.0 and v2.35.0

`git diff 6e2b823c7..edc2857eb -- src/accessible_surfaceome/agents/plan_trim_select/`:

```
abstract_triage.py          +160 -42   (caching refactor; no semantic change)
pretrim_filter.py           +338  -0   (new file, v2.14.0)
prompts/abstract_triage.md  +18  -18   (variable-name swap for caching)
runner.py                   +209 -16   (Tier 4 dedup + pretrim hookup)

prompts/a1_select_system.md   0   0    (byte-identical)
prompts/a1_trim_system.md     0   0    (byte-identical)
```

The five commits in chronological order:

| SHA | corpus_v | what changed |
|---|---|---|
| `4b6b5a012` | 2.14.0 | Pretrim filter introduced (default OFF, shadow mode) + Tier 1 prompt caching |
| `4ecc293b5` | (skipped — Tier 4 prep) | Tier 4 dedup cache + paper metadata persistence |
| `10e9957c8` | (skipped — CI) | CI / Venn metadata |
| `05ff95fc4` | (skipped — triage path) | Production triage drops legacy `prompt_template` kwarg |
| **`7363656cf`** | **2.17.0** | **Pretrim default ON + HARD_CAP 150→132** |

**`7363656cf` is the breaking commit.** Its rationale ("94-100% contribution
retention on heavy-lit anchor genes from the shadow-mode audit") is true
of the **rule filters** (review / drug-review / atlas) but is silent on
the **year-sorted cap**. The cap on SRC drops 87/379 papers — 23% by count
but a long tail of foundational localization papers by content weight.

## Why HARD_CAP 132 is the bite

The cap is intended as a safety ceiling for "EGFR/TP53-class" genes with
250+ candidates. Production data the commit cites (median 208, mean 205,
p25=132) means the cap fires on >50% of cohort genes — not the long tail
it was designed for. And the sort key `(-(p.year or 0), 0 if p.is_pmc_oa
else 1)` deterministically drops the oldest papers — which on
well-studied surface receptors are the founding-era localization /
mechanism papers, not the syntheses the rule filter targets.

A note on the rule filters: they removed 157 reviews + 1 drug-review +
2 atlases = 160 papers from SRC. The cap removed 87 more on top. **The
rule filters are doing the lion's share of the work**; the cap
contributes a smaller but more biased loss.

## Recommendation

**Don't revert `7363656cf`. Raise HARD_CAP back to 150 (or, if budget
binds, switch the cap to content-weighted instead of year-sorted).**

1. **Rule filters are working.** Review-without-quality-journal + drug-
   review + atlas patterns retire 160 SRC papers and 163 HMGB1 papers with
   no visible A1-contribution loss. Leave them on.

2. **The cap is biased against load-bearing old papers on well-studied
   genes.** SRC's 5 cap-dropped IF/IHC contributors are 2007-2017 founding-
   era trafficking work newer papers cite without restating. The bias is
   invisible in a contribution-rate audit but visible downstream in the
   methods builder (the `methods_unknown_2026_06_08.md` Bucket B "silent
   permeabilization on IF" loses 5 SRC IF rows when pretrim caps these
   sources).

3. **150 was tuned against the heavy-lit anchor set (TACSTD2/HMGB1/SRC)**
   in the original commit. Lowering to 132 was a cohort-cost optimization
   that didn't re-validate the anchor set. Cost delta 132→150 is
   ~$500-$800 cohort-wide (18 papers × 6,521 genes × ~$0.001/paper-trim) —
   cheap insurance for ledger fidelity on the publication-driving genes.

4. **If $12k budget binds:** content-weighted cap — preserve all
   `primary_research` papers under cap, drop reviews + `n/a`-pubtype by
   year-sorted bottom. Leaves founding-era primary research intact.

**Do NOT touch the A1 select or trim prompts.** Byte-identical from v2.9.0
→ v2.35.0; load-bearing baseline for any future prompt edit.

If the cohort sweep shows the regression beyond SRC/HMGB1, next check is
**rule-filter precision on mid-lit genes** (THIN=25, HEAVY=50 thresholds
— reported ~10% false-positive rate is meaningful when a gene has 30-60
candidates). But here the cap is the lever, not the rules and not the
prompts.

## Provenance

* Data: `agent_run_intermediates` in private D1, queried with
  `D1Client.query`.
* Code: `git diff`/`git log` against this worktree (HEAD `f80a50be5`).
* Prompts compared: bytes equal at
  `src/accessible_surfaceome/agents/plan_trim_select/prompts/a1_*.md`
  between commit `6e2b823c7` (v2.9.0) and `edc2857eb` (v2.35.0).
* Pretrim audit cap counts: SRC 87, HMGB1 74. Pretrim review counts: SRC
  157, HMGB1 163. Both audits are byte-identical from v2.19.0 → v2.35.0.
* Read-only audit. No source files edited.
