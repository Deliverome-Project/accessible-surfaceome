# Consolidated overnight contact review — 32 additional proteins

Status: **draft and unpublished**. PR #224 was merged into `dev`; the current production API still serves `contacts-ba6680878403e6980464`. The new reviewed release is `contacts-a263bf5f433dba68c0c4`. Neither this data update nor site-ordering PR #234 has been merged or deployed.

Three initial reviews and three independent cross-reviews, followed by an independently reviewed eight-target extension and five construct verifications, covered 3,042 observations for the 32 proteins below. Curated rules preserve every original label, residue array, structure identifier, reference and compartment. Across the full export, all 29,182 observations for 5,106 proteins were compared against the production-release snapshot and conserved.

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
| HLA-DRA | P01903 | 23 | 23 | 312 | 16 |
| HLA-A | P04439 | 19 | 16 | 792 | 11 |
| HLA-DRB1 | P01911 | 13 | 14 | 227 | 10 |
| HLA-B | P01889 | 8 | 8 | 447 | 5 |
| BACE1 | P56817 | 16 | 15 | 24 | 0 |
| INSR | P06213 | 8 | 14 | 143 | 2 |
| ITGAV | P06756 | 11 | 18 | 85 | 1 |
| F3 | P13726 | 7 | 10 | 21 | 0 |
| NT5E | P21589 | 7 | 5 | 15 | 0 |
| DPP4 | P27487 | 7 | 12 | 25 | 3 |
| IL3RA | P26951 | 6 | 6 | 15 | 0 |
| FCGRT | P55899 | 6 | 12 | 61 | 0 |
| CD3E | P07766 | 6 | 5 | 186 | 0 |
| IL2RA | P01589 | 5 | 6 | 23 | 0 |
| KIT | P10721 | 5 | 3 | 28 | 0 |
| **Total** | | **349** | **332** | **3,042** | **61** |

More names after review can be correct: INSR and ITGAV gain separately identified engineered analogues or peptide constructs that were previously collapsed under native-protein labels. The goal is supported identity, not the lowest count.

## Accepted decisions

- Preserve legitimate therapeutic-arm matches as separately named therapeutics, explicitly identified as sequence/arm evidence. Absence of a complete drug in a crystal is not grounds for removing its supported arm association. Nine proposed exclusions were reversed during peer review.
- Preserve valid intracellular EGFR/bosutinib contacts in all-contact views. ER/endosomal loading-machinery observations use an EC-overview-only exclusion while retaining raw compartment evidence and all-contact access.
- Separate native SIRPα from the engineered IMM01 binding domain; Ipi.105/Ipi.106 from parent ipilimumab; fluorescent 5C8 variants from parent 5C8; synthetic insulin/fibronectin/TGFβ-derived constructs from native-protein labels.
- Retain the Ibritumomab–3BKY/C2H7 association as an unresolved source identity conflict, narrowly excluded from named overview only at 3BKY. Do not reinterpret it as a proven therapeutic structure.
- Narrow generic Ab1/Ab2, parental 22B3/25F7 and humanized 5C8 aliases to supported PDBs. Explicit structure-specific rules take precedence over broad aliases regardless of JSON order; contradictory rules at the same specificity fail the build.
- Preserve canonical reviewed names including construct qualifiers. Resolved anonymous/accession-only source records can now appear under their reviewed names.
- HLA peptide-family counts and APP target-fragment limitations appear in the coverage tooltip and evidence details. Allele, peptide chemistry, tethering and TCR clonotype are not yet a complete unique-molecule schema.

## Focused follow-ups and remaining uncertainty

The five previously held target/PDB scopes are now resolved against deposited sequences and stable UniProt reference intervals: APP/5AM8, APP/5AMB and APP/2WK3, plus HLA-DRA and HLA-DRB1 at 3S4S. ACE constructs remain distinct, IDE retains its engineered substitutions, and CD4 numbering is reconciled. Deposit sequence does not prove the physical sample matched the deposit; the ACE paper/deposit discrepancy remains explicit. See the [sequence verification](contact-review-2026-09-18/held-scopes-second-pass.md).

The eight-target extension covers F3, NT5E, DPP4, IL3RA, FCGRT, CD3E, IL2RA and KIT. It preserves engineered cytokine/Fc/albumin distinctions, independently verified therapeutic-arm names, and intracellular kinase contacts. Cross-species ADA constructs and an unidentified CD3E-associated peptide remain unclassified rather than guessed. IL-3 W32Y precursor numbering and W13Y mature numbering are reconciled; source truncation information remains in provenance.

The [HLA identity proposal](contact-review-2026-09-18/hla-identity-proposal.md) is preparatory only. Six mmCIF examples link 18 original observations to 16 deposition-local construct-context groups; root validation checks source IDs, sequences, deposited-file hashes and deterministic keys. It preserves allele differences, author/label chain namespaces, peptide chemistry including a disulfide, and unresolved copy mappings. No global molecular keys, new API schema or HLA count migration are published.

Existing source uncertainties remain explicit, including hAB21/Fab25 versus AB21, MSLN 3F2 versus paper nomenclature, GA101/B-Ly1 source aggregates, and HLA sequence/allele grouping. Source sequence-match claims were audited with cached provenance; they were not all independently recomputed against complete drug sequences.

## Implementation and validation

- 397 total curated rules cover the 38 reviewed targets (six previously published, 32 new). All accepted rules match existing observations.
- Updated representative-site ordering from PR #234 is included: category first, greatest contact-residue overlap next, sequence position as fallback. Ligand identities and footprints remain separate.
- Regression tests check exact original-field hashes for all 3,042 reviewed observations, scoped variant precedence, conflict rejection, canonical-name visibility, retained intracellular evidence and EC-only exclusions.
- The immutable release exporter and publisher dry run validate the draft without writing D1. Full viewer build and focused Node/Python checks are recorded in the PR.
- Production activation, merge and any new deployment are held. Existing production data remains unchanged.

## Review trail

Initial proposal reports are retained as review history; their uncorrected rules/counts are superseded by this consolidated report and the committed reviewed_contact_partners.json.
- [checkpoints initial review](contact-review-2026-09-18/checkpoints-report.md) and [independent critique](contact-review-2026-09-18/checkpoints-peer-review.md).
- [therapeutic_targets initial review](contact-review-2026-09-18/therapeutic_targets-report.md) and [independent critique](contact-review-2026-09-18/therapeutic_targets-peer-review.md).
- [complex_ligands initial review](contact-review-2026-09-18/complex_ligands-report.md) and [independent critique](contact-review-2026-09-18/complex_ligands-peer-review.md).

- [Eight-target follow-up](contact-review-2026-09-18/next_targets-report.md) and [independent critique](contact-review-2026-09-18/next_targets-peer-review.md).
