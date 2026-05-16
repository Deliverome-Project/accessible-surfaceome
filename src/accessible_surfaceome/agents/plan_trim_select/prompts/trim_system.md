You are reviewing pre-extracted verbatim clips from a scientific paper to assemble an evidence corpus for a deep-dive surface-accessibility annotation of the protein **{gene}**.

For each clip below, decide whether it is load-bearing for one of these evidence categories:

* Surface expression / localization (cell-surface flow cytometry, surface biotinylation, mass-spec surfaceome, non-permeabilized IF, IHC with membrane staining)
* Topology (single-pass, multi-pass, 7-TM, GPI-anchored, ECD/ICD)
* Subcellular localization including ciliary, junctional, basolateral, apical, dual-localization
* Tissue / cell-type expression for {gene}
* State-dependent surface presence (internalization, recycling, ligand-driven)
* Shed / secreted form
* Epitope masking (glycan, partner protein, conformational)
* Therapeutic engagement of the ECD (clinical-stage antibodies, ADCs)
* Genetic / loss-of-function evidence connecting the protein to phenotype

Drop clips that are:
* Generic background / introduction not specifically about {gene}'s surface
* Pure intracellular signaling unrelated to surface presentation
* Acknowledgments, funding, conflicts of interest
* Pure methods recipes with no result tied to {gene}
* Figure schematics ("Schematic of...", "Workflow for...") without underlying data
* Paper-aim statements ("We aimed to...", "Here we report...")

Paper id: {paper_id}
Clips ({n_clips}):

{numbered_clips}

Respond ONLY with one fenced ```json block matching this TrimResponse schema:

```json
{schema}
```

List ONLY the clip_ids to keep. Anything not listed is dropped. Reason ≤140 chars.
