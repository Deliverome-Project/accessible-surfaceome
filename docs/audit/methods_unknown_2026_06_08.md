# Audit: `method_subclass='unknown'` in v2.35.0 methods builder

**Date:** 2026-06-08
**Cohort:** 11 most recent v2.35.0 reruns: TACSTD2, C3, CD63, PVRIG, HMGB1, GPR75, ABCB9, LYN, TGOLN2, SRC, BAX
**Read-only investigation — no code changes.**

## Headline

**30 of 105 `MethodObservation` rows (28.6%) carry `method_subclass='unknown'`.**
Per-gene breakdown:

| Gene | Methods rows | Unknown | % |
|---|---:|---:|---:|
| TACSTD2 | 26 | 7 | 27% |
| C3 | 11 | 3 | 27% |
| CD63 | 14 | 3 | 21% |
| PVRIG | 12 | 6 | **50%** |
| HMGB1 | 2 | 0 | 0% |
| GPR75 | 9 | 4 | **44%** |
| ABCB9 | 8 | 2 | 25% |
| LYN | 8 | 1 | 12% |
| TGOLN2 | 9 | 1 | 11% |
| SRC | 3 | 1 | 33% |
| BAX | 3 | 2 | **67%** |
| **Total** | **105** | **30** | **28.6%** |

(Task brief mentioned 121 rows; the most-recent-per-gene query for v2.35.0
returned 105 — the failure pattern is unchanged.)

## The 16-row root cause — `functional_surface_assay` has no matching subclass

The single biggest driver is a **schema gap**. **Every single
`functional_surface_assay` row in the cohort (16/16) lands at
`subclass='unknown'`.** The enum (methods_builder_system.md L329-332)
does not contain a functional-assay subclass — the closest values
(`live_cell_flow`, `surface_biotinylation`, etc.) are antibody-staining
methods, not ADC / CAR-T / pharmacological-blockade demonstrations.

The prompt at L286-298 defines `method_family=functional_surface_assay`
in detail ("antibody-mediated tumor killing", "ADC efficacy",
"radioligand binding on live cells") **without ever telling the model
what `method_subclass` to pick**. The model correctly identifies the
family but has no enum slot for it.

## Failure-mode buckets

### Bucket A — `functional_surface_assay` has no enum slot (16 rows, 53%)

Affected: TACSTD2 ×6, PVRIG ×3, GPR75 ×3, C3 ×1, CD63 ×1, SRC ×1.

These are *the strongest direct-accessibility evidence in the cohort*
(FDA-approved ADCs, clinical-stage mAbs, CAR-T killing, KO-validated
cytotoxicity) — and downstream they sit at `subclass=unknown`,
invisible to any filter keyed on subclass.

> "TROP2 is the target of the ADC sacituzumab govitecan, which is
> FDA-approved for TNBC, as well as the ADC datopotamab deruxtecan,
> which was recently FDA-approved for NSCLC." — TACSTD2

> "TROP2-targeted CAR T cells showed in vitro activity against TROP2+
> cell lines … Cytotoxicity was abrogated if TROP2 was knocked out."
> — TACSTD2

> "COM701 is a humanized anti-PVRIG hinge-stabilized IgG4 … blocks
> the interaction of PVRIG with PVRL2." — PVRIG

> "anti-Src antibody-based therapies mediated tumor cell killing in
> cell culture systems and in mouse xenograft models." — SRC

The model already picked
`accessibility_relevance=direct_surface_accessibility` on most of
these — it knows what they are. It just has nowhere to put them.

### Bucket B — silent permeabilization on IF (6 rows, 20%)

Affected: TACSTD2 ×1; C3 ×2; CD63 ×1; ABCB9 ×2.

Paper does not state `permeabilized` / `non-permeabilized`. The enum
offers `permeabilized_IF` vs `nonpermeabilized_IF` — both feel wrong
when silent — so the model goes `unknown`. The prompt at L335 says
`permeabilization` should default to `unknown` when silent, but it
does NOT instruct what `method_subclass` to do in the parallel case.

> "Multiplex immunofluorescence (mIF) demonstrated elevated EGFR and
> TROP2 expression in the majority of samples." — TACSTD2

> "Immunofluorescence staining of CD63-positive compartments (green)
> and ganglioside GM1 (red)." — CD63

The right call is **default to `permeabilized_IF` when perm is
silent** — most fixed-cell / tissue IF is permeabilized; non-perm
would be named.

### Bucket C — tissue IHC without a membranous staining pattern (4 rows, 13%)

Affected: PVRIG ×3; BAX ×1.

The enum has only one IHC subclass: `IHC_membranous`. When tissue
IHC reports total expression without describing a membranous staining
pattern, the model can't pick `IHC_membranous` honestly and has no
"IHC_cellular" / "IHC_total" slot.

> "PVRIG expression on immune cells was confirmed in COAD patient
> tumor sections by IHC (red arrows in Fig. 1b)." — PVRIG

> "Immunohistochemistry showed that both BAX and Bcl-2 proteins were
> upregulated." — BAX

These are correctly `accessibility_relevance=expression_only`, but
the subclass should be `IHC_total` / `IHC_cellular`, not `unknown`.

### Bucket D — proximity labeling + CLEM/EM have no enum slot (2 rows, 7%)

Affected: BAX (APEX2-BAX, mitochondrial); TGOLN2 (CLEM with GFP-TGN46 OE).

> "To identify components of the mitochondrial apoptotic pore, we
> generated APEX2-tagged fusion constructs with BAX and BAK." — BAX

> "CLEM-Reg … to unambiguously identify TGN46-positive transport
> carriers … between the trans-Golgi network and plasma membrane."
> — TGOLN2

`method_family=proximity_labeling` is in the family enum (L284) but
has no subclass; CLEM isn't named anywhere. The BAX APEX2 row is
also a *non-surface* assay (mitochondrial) — it arguably shouldn't
emit a `MethodObservation` at all per the L96 inclusion criterion.

### Bucket E — flow cytometry with silent permeabilization (2 rows, 7%)

Affected: GPR75; LYN. Same pattern as Bucket B.

> "Both qPCR and flow cytometry show that these cells express GPR75
> but do not express CCR5, CCR3 or CCR1 receptors." — GPR75

Right default is `live_cell_flow` — fixed flow is the named
exception and would be described if used.

## Prompt-edit recommendations (no edits applied)

Line numbers refer to `methods_builder_system.md`.

1. **(Bucket A — ~16 rows, biggest win)** Extend the `method_subclass`
   enum at **L329-332** with a `functional_surface_assay` slot (or
   split into `adc_or_car_target`, `mab_engagement`,
   `radioligand_live_cell`, `surface_pharmacology`). Mirror the
   change in `MethodSubclass`
   (`src/accessible_surfaceome/tools/_shared/models.py:1198`). This
   is the only *schema change*; the rest are prompt-default fixes.

2. **(Bucket B — ~6 rows)** Add a default after L335: *"When the
   paper does NOT state the permeabilization condition for an IF
   assay on fixed cells / tissue sections, default `method_subclass`
   to `permeabilized_IF` — most fixed-cell / tissue IF is
   permeabilized unless non-perm is named."*

3. **(Bucket C — ~4 rows)** Add `IHC_cellular` or `IHC_total` to
   L329-332. Add a one-line rule near L498: *"For tissue IHC that
   reports expression without describing a membranous staining
   pattern, use `IHC_cellular` — `IHC_membranous` is reserved for
   explicit membrane-staining patterns."*

4. **(Bucket D — ~2 rows)** Add a rule near L286 that
   *intracellular proximity labeling (APEX2 / BioID directed at
   mitochondria, ER, cytosol) does NOT emit a `MethodObservation`*
   — the row would be rejected by the L96 inclusion criterion. CLEM
   stays unknown (true enum gap) — defensible at ≤1 row of residual.

5. **(Bucket E — ~2 rows)** Add a default near L329: *"When the paper
   says 'flow cytometry' without specifying live vs fixed cells,
   default `method_subclass=live_cell_flow` — fixed flow is the named
   exception and would be described if used."*

6. **(Optional, cross-cutting)** Add a hard rule at the end of
   "Field-by-field rules" (around L525): *"`method_subclass` may be
   `unknown` ONLY when the assay is one the closed enum demonstrably
   does not cover AND you have considered each enum value. Defaulting
   to `unknown` because the paper is silent on a sub-detail is wrong
   — pick the most-likely value per the defaults above."*

## Estimated yield

If recommendations 1–5 land: Bucket A (16) and Bucket C (4) resolve
fully via new enum slots; Buckets B (6) and E (2) resolve via the
silent-default rules; Bucket D resolves 1 of 2 (BAX APEX2 dropped at
inclusion; TGOLN2 CLEM stays as residual). **~29 of 30 unknowns
resolved (~97%).** Residual rate ~1/105 ≈ 1% — the floor for genuine
enum gaps. Recommendation 1 alone takes the unknown-rate from 28.6%
→ 13.3% even if nothing else changes; it's the highest-leverage
single edit.
