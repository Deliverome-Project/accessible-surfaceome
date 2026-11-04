# Independent peer review: next eight targets

Final independent review, 2026-09-18. Reviewed all 80 rules, the delivered report, all 374 raw observation labels, focused cached polymer evidence and independently retrieved primary PDB/source records. **Accept all 80 for observation-level annotations after the applied bovine ADA correction.** No remaining material unsafe rule or matcher conflict found. This is not certification that every contact is physiological or demonstrates intact surface accessibility.

## Independently verified points

- Current matcher semantics (Fab/Fv/VHH suffix normalization, terminal-parenthetical normalization, PDB-specific precedence) give 263 effective rule hits, no unmatched rule, and no conflicting identities/categories.
- PDB headers support native-sequence partner distinctions for factor VIIa in 1J9C/2PUQ/8CN9/8UUD, IL-2 in 1Z92/2B5I/9KMC, and SCF in 2E9W/8DFP/8DFQ. The visible engineered substitutions are in separate receptor/target entities.
- 1A81 contains a phosphotyrosyl CD3E target peptide; this does not make the SYK partner an engineered enzyme. Cytoplasmic target context remains necessary.
- Official [Thera-SAbDab Bexatamig](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/therasummary/?INN=Bexatamig) gives paired VH/VL sequences and a 100% Fv match to 4JZJ AB/HL. This independently strengthens the weaker cached match-method string. Keep the named therapeutic arm under the root-approved policy; do not claim the complete multispecific drug was crystallized.
- [7Q15](https://www.rcsb.org/structure/7Q15) explicitly identifies efgartigimod Fc-MST-HN. FcRn IgG1 YTE and monomeric IgG4 constructs remain experimental Fc ligands, not generic Fab antibodies or unmodified serum IgG. [6WOL](https://www.rcsb.org/structure/6WOL) and cached polymer metadata support distinct engineered Fc identity.
- [AP2](https://www.rcsb.org/ligand/AP2) and [A12](https://www.rcsb.org/ligand/A12) have the same deposited InChIKey and molecular formula; their AMPCP tool classification is supported. They are not endogenous AMP/ADP.

## Nonblocking display/provenance caveats

9T46 is a 40G5c Fab bound to a CD3 epsilon peptide, not the intact multisubunit TCR-CD3 complex. Preserve peptide/arm context alongside the Mosunetuzumab group. Generic 9CI8 peptide stays unresolved; source labels alone cannot decide whether a receptor subunit or structural antibody is intended. Named TCR/CD3 subunit contacts are assembly partners, not proof of an independently administered surface binder.

A PDB-wide mutation flag is insufficient to reclassify every partner in that PDB. Conversely, a null flag is insufficient to establish wild type. The proposed PDB-specific cytokine/Fc/albumin rules mostly handle this correctly; sequence identity was checked in cached polymers for the important FcRn cases.

## Material correction applied

Zero-based rule 65 initially labeled bovine ADA at 2BGN endogenous_large. The [2BGN deposit](https://www.rcsb.org/structure/2BGN) explicitly identifies Bos taurus and reports three sequence differences for entity 2, despite absent cached entity mutation text. Natural sourcing does not establish an endogenous human ligand or a verified wild-type sequence. The author corrected it to `Bovine adenosine deaminase (2BGN construct)`, unclassified, with the unresolved sequence caveat. Rule 79 treats 1W1I similarly. No observation is removed.

## Final variant checks

Rule 78 correctly uses `IL-2 C125A variant` for [2ERJ](https://www.rcsb.org/structure/2ERJ), without propagating the misleading deposited aldesleukin synonym. IL-3 numbering was reconciled to W13Y mature nomenclature; PDB provenance retains differing truncation/tag context. These groups are not a molecular-species denominator.

I independently compared cached HSAopt sequences: 4K71, 6QIO and 6QIP are identical at 585 residues. The 6WNA and 6WOL IgG4 Fc sequences differ (207 versus 209 residues). Thus absence of the 6QIP mutation field does not justify calling it native, while the two engineered Fc constructs should remain separate.

The final report preserves unresolved viral/polyprotein, generic antibody and TCR assembly mappings instead of inventing equivalence. Named therapeutic-arm groups remain included under the confirmed review policy; no ADC/bispecific completeness claim is implied.

## Scope and documentation

All 80 rules match at least one observation, with 263 effective rule hits and zero conflicting effective annotations among 374 observations. No blanket exclusions are introduced. Exact labels and lower-case PDB scopes were checked. The report initially referenced a counts table/raw appendix that was absent; the author corrected an output-path error and supplied the complete table/appendix before integration.

No original rules, source observations or shared repository files were modified by this peer review.

Reviewed rules SHA-256: `e245b605209c1f47502fcbad18cb7f941913a6593618ca2a2e74cbc285742066`.
