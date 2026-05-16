You are reviewing pre-extracted verbatim clips from a scientific paper to assemble the **surface-evidence ledger** (Section 1, "A1") of a deep-dive surface-accessibility annotation for the protein **{gene}**.

Your single job is to **decide which clips are load-bearing for A1's narrow focus** — the experimental evidence on whether {gene} is actually presented at the outer leaflet of the cell membrane, how that was measured, and what undermines or refuses that conclusion.

## What A1 cares about — KEEP these clips

A clip is load-bearing if it directly evidences one of these surface-evidence categories. Err on the side of **keeping** when in doubt: A1's selector is the gatekeeper for final inclusion, the trim pass should just protect it from obvious noise and from A2-only material.

1. **Surface-evidence methods (the hinge of A1).** The assay used to detect {gene} at the cell surface, with enough methods detail that A1's selector can fill `MethodObservation.method_family` / `method_subclass` / `permeabilization` / `antibodies` / `accessibility_relevance`. Includes:
   * Flow cytometry on live (non-permeabilized) cells with antibody against {gene}.
   * Cell-surface biotinylation (sulfo-NHS-biotin, sulfo-NHS-SS-biotin) followed by streptavidin pulldown + WB or MS.
   * Cell-surface-capture mass spectrometry / surfaceome MS (CSC, SUSPECS, etc.).
   * Non-permeabilized immunofluorescence on intact cells.
   * IHC scored explicitly for membrane staining pattern.
   * Live-cell tracking / surface-pool measurement / internalization-rate assays.
2. **Topology**: single-pass / multi-pass / 7TM / GPI-anchored, ECD vs ICD length, signal peptide presence, N-terminal vs C-terminal orientation, hydropathy / DeepTMHMM-style assignments. This anchors what counts as "the extracellular face" for A1.
3. **Shed or secreted forms.** Soluble {gene} in supernatant / serum / plasma, sheddase activity (ADAM10/17, MMPs, γ-secretase), constitutive secretion of a non-anchored isoform. Critical for `risks.shed_form` + `risks.secreted_form` downstream and for `therapeutic_engagement.surface_form_rationale`.
4. **Epitope masking** — glycan shielding, partner-protein coverage of the binding epitope, conformational occlusion (closed vs open conformer), heterodimerization that buries the epitope.
5. **Therapeutic engagement of the ECD.** Clinical or preclinical antibodies, ADCs, CAR-T constructs that bind {gene} at the surface. Stage / trial identifier / endpoint when available — this fills `TherapeuticEngagementContext`.
6. **Methodological rigor + antibody specificity.** Antibody clone IDs, RRIDs, KO-validation, paralog cross-reactivity tests, isotype controls, paired WB with fractionation step, blocking-peptide controls. These let A1 populate `AntibodyRef.validation_strategy` and `cross_reactivity_notes` — they are NOT background noise.
7. **Non-surface expression observations.** RNA (RT-qPCR, RNA-seq), whole-cell western blot WITHOUT a fractionation step, permeabilized IF, total-cell IHC without membrane scoring. KEEP these — they feed A1's `non_surface_expression` list (the bucket that *prevents* expression from being misread as accessibility). Mark them in your reason so the selector knows to file them on the non-surface side.
8. **Contradictions to surface presence.** Studies finding {gene} primarily intracellular, no detectable surface signal where another paper reported one, failure-to-replicate, paralog confound (an antibody that turns out to cross-react with a paralog).
9. **Structure of the ECD** — PDB entries, AlphaFold predictions explicitly framed as the extracellular domain, crystal structures of the ECD with a ligand or antibody.

## What A1 does NOT need — DROP these clips

These are A2's territory (the BiologicalContext block); keeping them in A1's menu wastes the selector's attention and biases the ledger toward biology that the A2 selector will pick up independently.

* **Tissue / cell-type expression panels.** "GPR75 is expressed in pancreas, kidney, and adipose..." → A2.
* **Cell-state / disease-context modulation.** "Surface levels increase under hypoxia / activation / EMT / chemotherapy..." → A2's `accessibility_modulation`. EXCEPTION: keep clips where the state-shift is being used as a method to *measure* surface presence (e.g., "biotinylation of activated vs resting T cells confirmed surface translocation") — these are methodological for A1.
* **Anatomical orientation** (apical vs basolateral, junctional, ciliary localization as a tissue-anatomy point) → A2's `anatomical_accessibility`. EXCEPTION: keep clips where the orientation is being framed as an *accessibility* claim about a systemic binder (e.g., "the apical-only localization explains why the antibody had no efficacy from the basolateral side").
* **Pure intracellular signaling cascades** unrelated to surface presentation (downstream second-messenger work, transcriptional targets, kinase activity assays).
* **Phenotype-only genetics** with no surface-protein readout (GWAS hits, knockout phenotypes without protein-level data) — unless the paper also reports surface-protein consequences.

## Universal drops (always)

* Generic background / introduction not specifically about {gene}'s surface biology.
* Acknowledgments, funding statements, conflict-of-interest declarations, ethics approvals.
* Pure methods recipes with no result tied to {gene} (a buffer composition or a flow-cytometer model isn't load-bearing).
* Figure schematics ("Schematic of the assay...", "Workflow for surfaceome profiling...") without an associated result.
* Paper-aim / motivation statements ("We aimed to assess...", "Here we report...", "The goal of this study was...") — these say what the paper *set out* to do, not what it *showed*.
* IHC / flow scoring rubrics on their own without the readout ("1+ for weak membrane staining in ≥10% of cells, 2+ for moderate..." but no per-sample score).

## Calibration

* If a paper is clearly an A1 paper (e.g., a surface biotinylation + MS surfaceome study), keep most of its clips even when individual clips are partial — A1's selector needs the methods detail, the antibody table, AND the result snippet to build a complete `MethodObservation`.
* If a paper is clearly an A2 paper (a tissue-expression atlas, a clinical-cohort tumor-expression study), keep only the universal-load-bearing items (any surface-method mention) and drop everything else.
* Borderline cases — when you can't tell — keep the clip and let the selector decide. Recall over precision at this layer.

## Output

Paper id: {paper_id}
Clips ({n_clips}):

{numbered_clips}

Respond ONLY with one fenced ```json block matching this TrimResponse schema:

```json
{schema}
```

List ONLY the clip_ids to keep. Anything not listed is dropped. The `reason` field (≤140 chars) should name the A1 category the clip serves (e.g. "surface biotinylation method", "shed form serum ELISA", "non-surface RNA expression for non_surface_expression list", "contradiction: intracellular only").
