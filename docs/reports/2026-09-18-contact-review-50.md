# Additional 50-protein contact review — 2026-09-18

Reviewed 50 previously unreviewed protein partner inventories, covering 1,893 observations. Targets were selected by extracellular named-partner count, then unclassified count and stable accession, excluding previously curated targets and EGFR. This adds 50 to the previous 32-protein overnight review (82 additional proteins total); it is not the total database coverage.

The database still contains 1,680 proteins with mapped evidence among 5,106 unambiguously resolved audited proteins. All 29,182 original observations, source references, residue positions and context fields are preserved. No new experimental evidence or gene coverage was manufactured by relabeling.

## Results

| Metric | Before | After |
|---|---:|---:|
| Named extracellular partner groups | 300 | 345 |
| endogenous_large | 1 | 38 |
| endogenous_small | 0 | 2 |
| receptor_partner | 0 | 109 |
| therapeutic | 14 | 33 |
| tool | 0 | 128 |
| unclassified | 285 | 35 |

Counts are target–partner display groups, not globally unique molecules. HLA peptide and allele identities remain incompletely resolved. Consolidation and scoped localization exclusions can reduce display counts while all raw observations remain available.

## Review and corrections

508 new evidence rules were independently cross-reviewed, bringing the canonical file to 905 rules across 88 targets (the initial six plus the additional 82; EGFR was reviewed separately). The uniform ledger traces all 1,893 observations, including unresolved or unpromoted records. Review examined partner inventories and selected primary identity evidence, not every atom or full sequence.

Primary-source corrections include therapeutic antibody-arm identities, engineered receptor and ligand qualifiers, peptide fragments, small-molecule names, and identical construct aliases. Three sequence-identical construct pairs were consolidated across PDBs. A narrow reciprocal ITGAV/5FFO correction identifies the same engineered latent TGFB1 construct already reviewed against ITGB6. Only supported CD74/CTSL and MR1 loading-complex records are excluded from the extracellular overview; all-contact evidence remains.

Final batch 3 decisions: H2AX peptide lengths are structure-specific; SRC/4HXJ is an SH3 domain; the inconsistent 4MMY motif stays a qualified engineered FN10 construct; 8VS6 chain E supports TGFB3 identity; DA5/DA10/DA330 remain unresolved aliases. The non-acylated cagrilintide backbone is a qualified therapeutic component, not an assertion that intact acylated drug was observed. Redundant receptor-role suffixes were normalized, while domain, construct and variant qualifiers remain.

Agent reports document proposals; the peer reviews, final committed rules and uniform ledger supersede proposal counts.

## Evidence and traceability

- [Batch 1 report](contact-review-50-2026-09-18/batch1-report.md) / [independent review](contact-review-50-2026-09-18/batch1-peer-review.md)
- [Batch 2 report](contact-review-50-2026-09-18/batch2-report.md) / [independent review](contact-review-50-2026-09-18/batch2-peer-review.md)
- [Batch 3 report](contact-review-50-2026-09-18/batch3-report.md) / [independent review](contact-review-50-2026-09-18/batch3-peer-review.md)
- [Root source checks](contact-review-50-2026-09-18/root-cross-review.md)

Final decisions and full observation ledger: `data/analysis/deep_dive_binding_sites/contact_review_50_decisions.json` and `contact_review_50_ledger.json`. Preservation checks now cover 82 reviewed proteins.

## Validation and release

Unpublished release: `contacts-b960b69373f6486dc9e9`. Publisher dry run: 5,106 genes, 5,418 ligand identities, 8,157 gene–ligand associations and 29,182 observations. These identity counts are not an exhaustive ligand census.

17 focused Python tests passed; 20 Node tests passed; scoped Ruff and type checks passed. Full viewer build and CI status are recorded in the draft PR. No production database writes, deployment or merge.

## Targets

ACE, AGER, BACE2, BTN3A1, CACNA2D1, CALCRL, CD3D, CD74, CD81, CD8A, CD9, CDH1, CDH3, CSF2RB, EPHA4, EPOR, GABRA1, GABRG2, GRIN1, GRM2, GRM3, GRM8, HLA-C, HLA-DQA1, HLA-E, HLA-G, IL2RB, IL2RG, ITGAL, ITGAM, ITGB1, ITGB3, ITGB6, ITGB7, ITGB8, LRP6, MADCAM1, MR1, NCSTN, NOTCH3, NRP1, NRP2, PRNP, PTCH1, RAMP1, RET, TGFA, TMPRSS2, TNF, TNFSF13B.
