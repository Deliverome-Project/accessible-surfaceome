# Consolidated overnight contact review — 24 additional proteins

Status: **draft and unpublished**. PR #224 was merged into `dev`; the current production API still serves `contacts-ba6680878403e6980464`. The new reviewed release is `contacts-2237ef21c0d1e257f446`. Neither this data update nor site-ordering PR #234 has been merged or deployed.

Three initial reviews and three independent cross-reviews covered 2,668 observations for the 24 proteins below. Curated rules preserve every original label, residue array, structure identifier, reference and compartment. Across the full export, all 29,182 observations for 5,106 proteins were compared against the production-release snapshot and conserved.

## Counts

These are named mapped partner groups, not an exhaustive ligand census or a count of independently crystallized full therapeutics. HLA names may combine peptide sequences/alleles; the viewer explicitly labels them **partner groups**. APP evidence includes fragments and does not establish intact cell-surface accessibility.

| Protein | UniProt | Previous EC groups | Reviewed EC groups | Preserved observations | Unclassified EC groups |
|---|---|---:|---:|---:|---:|
| CTLA4 | P16410 | 18 | 18 | 80 | 1 |
| CD40 | P25942 | 14 | 9 | 35 | 0 |
| TNFRSF4 | P43489 | 10 | 5 | 21 | 0 |
| TNFRSF9 | Q07011 | 8 | 7 | 36 | 0 |
| TIGIT | Q495A1 | 8 | 8 | 19 | 0 |
| CD27 | P26842 | 8 | 5 | 18 | 0 |
| BTLA | Q7Z6A9 | 7 | 5 | 8 | 0 |
| CD40LG | P29965 | 10 | 8 | 15 | 0 |
| CD38 | P28907 | 16 | 11 | 26 | 0 |
| ERBB3 | P21860 | 11 | 9 | 42 | 0 |
| CD47 | Q08722 | 11 | 11 | 24 | 0 |
| SIRPA | P78324 | 10 | 9 | 24 | 1 |
| TNFRSF17 | Q02223 | 9 | 9 | 15 | 0 |
| MSLN | Q13421 | 9 | 5 | 18 | 1 |
| MS4A1 | P11836 | 8 | 7 | 57 | 1 |
| TNFRSF10B | O14763 | 15 | 10 | 41 | 0 |
| APP | P05067 | 30 | 29 | 159 | 9 |
| HLA-DRA | P01903 | 23 | 23 | 312 | 17 |
| HLA-A | P04439 | 19 | 16 | 792 | 11 |
| HLA-DRB1 | P01911 | 13 | 14 | 227 | 11 |
| HLA-B | P01889 | 8 | 8 | 447 | 5 |
| BACE1 | P56817 | 16 | 15 | 24 | 0 |
| INSR | P06213 | 8 | 14 | 143 | 2 |
| ITGAV | P06756 | 11 | 18 | 85 | 1 |
| **Total** | | **300** | **273** | **2,668** | **60** |

More names after review can be correct: INSR and ITGAV gain separately identified engineered analogues or peptide constructs that were previously collapsed under native-protein labels. The goal is supported identity, not the lowest count.

## Accepted decisions

- Preserve legitimate therapeutic-arm matches as separately named therapeutics, explicitly identified as sequence/arm evidence. Absence of a complete drug in a crystal is not grounds for removing its supported arm association. Nine proposed exclusions were reversed during peer review.
- Preserve valid intracellular EGFR/bosutinib contacts in all-contact views. ER/endosomal loading-machinery observations use an EC-overview-only exclusion while retaining raw compartment evidence and all-contact access.
- Separate native SIRPα from the engineered IMM01 binding domain; Ipi.105/Ipi.106 from parent ipilimumab; fluorescent 5C8 variants from parent 5C8; synthetic insulin/fibronectin/TGFβ-derived constructs from native-protein labels.
- Retain the Ibritumomab–3BKY/C2H7 association as an unresolved source identity conflict, narrowly excluded from named overview only at 3BKY. Do not reinterpret it as a proven therapeutic structure.
- Narrow generic Ab1/Ab2, parental 22B3/25F7 and humanized 5C8 aliases to supported PDBs. Explicit structure-specific rules take precedence over broad aliases regardless of JSON order; contradictory rules at the same specificity fail the build.
- Preserve canonical reviewed names including construct qualifiers. Resolved anonymous/accession-only source records can now appear under their reviewed names.
- HLA peptide-family counts and APP target-fragment limitations appear in the coverage tooltip and evidence details. Allele, peptide chemistry, tethering and TCR clonotype are not yet a complete unique-molecule schema.

## Remaining held scopes

No new identity/category assertion was applied to these five target/PDB scopes; raw records remain available:
- Original complex-review rule 16, **5AM8**: Soluble ACE-domain complex with a short APP/amyloid-beta-derived fragment. Cached entity mutation_flag is YES without verified mutation identity; insufficient evidence for a specific replacement construct. Raw contact retained; this is not intact cell-surface APP binding evidence. [Source](https://www.rcsb.org/structure/5AM8).
- Original complex-review rule 16, **5AMB**: Soluble ACE-domain complex with a short APP/amyloid-beta-derived fragment. Cached entity mutation_flag is YES without verified mutation identity; insufficient evidence for a specific replacement construct. Raw contact retained; this is not intact cell-surface APP binding evidence. [Source](https://www.rcsb.org/structure/5AMB).
- Original complex-review rule 17, **2WK3**: IDE is marked mutant (mutation_flag YES), but the mutation identity was not verified in the bounded evidence. APP target is an amyloid-beta-derived fragment. Preserve raw observation without a new identity/category rule. [Source](https://www.rcsb.org/structure/2WK3).
- Original complex-review rule 21, **3S4S**: Primary study establishes affinity-engineered CD4 (https://doi.org/10.1073/pnas.1109438108), despite a null cached mutation flag. This bounded replacement pass does not certify the complete mutation set of this exact 191-residue deposited construct. Hold exact assignment rather than invent equivalence to 3S5L or 3T0E; raw evidence remains. [Source](https://www.rcsb.org/structure/3S4S).
- Original complex-review rule 28, **3S4S**: Primary study establishes affinity-engineered CD4 (https://doi.org/10.1073/pnas.1109438108), despite a null cached mutation flag. This bounded replacement pass does not certify the complete mutation set of this exact 191-residue deposited construct. Hold exact assignment rather than invent equivalence to 3S5L or 3T0E; raw evidence remains. [Source](https://www.rcsb.org/structure/3S4S).

Existing source uncertainties remain explicit, including hAB21/Fab25 versus AB21, MSLN 3F2 versus paper nomenclature, GA101/B-Ly1 source aggregates, and HLA sequence/allele grouping. Source sequence-match claims were audited with cached provenance; they were not all independently recomputed against complete drug sequences.

## Implementation and validation

- 312 total curated rules cover the 30 reviewed targets (six previously published, 24 new). All accepted rules match existing observations.
- Updated representative-site ordering from PR #234 is included: category first, greatest contact-residue overlap next, sequence position as fallback. Ligand identities and footprints remain separate.
- Regression tests check exact original-field hashes for all 2,668 reviewed observations, scoped variant precedence, conflict rejection, canonical-name visibility, retained intracellular evidence and EC-only exclusions.
- The immutable release exporter and publisher dry run validate the draft without writing D1. Full viewer build and focused Node/Python checks are recorded in the PR.
- Production activation, merge and any new deployment are held. Existing production data remains unchanged.

## Review trail

Initial proposal reports are retained as review history; their uncorrected rules/counts are superseded by this consolidated report and the committed reviewed_contact_partners.json.
- [checkpoints initial review](contact-review-2026-09-18/checkpoints-report.md) and [independent critique](contact-review-2026-09-18/checkpoints-peer-review.md).
- [therapeutic_targets initial review](contact-review-2026-09-18/therapeutic_targets-report.md) and [independent critique](contact-review-2026-09-18/therapeutic_targets-peer-review.md).
- [complex_ligands initial review](contact-review-2026-09-18/complex_ligands-report.md) and [independent critique](contact-review-2026-09-18/complex_ligands-peer-review.md).
