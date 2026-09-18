# Independent peer review of batch 2

Reviewed the 180-rule proposal against all 626 snapshot observations, the production matcher, cached deposited headers, primary structural records and selected clinical/localization literature. Every proposed rule matches an input observation. No effective identity/category collisions occur after PDB-specific precedence. No unsafe therapeutic-arm exclusion or parental-antibody/drug conflation was found in the TNF rules: the broad named aliases match the specified Fab/Fv deposits and named assays, and the report preserves arm provenance.

## Material corrections before acceptance

1. **Medium — identical constructs split into different display identities solely by PDB suffix.** Preserve the PDB-scoped rules but use one canonical label per verified identical pair:
   - Rules **127/128**, ITGB6 target P18564, ITGAV partner at **5FFG/5FFO**: complete deposited chain-A SEQRES is identical, 601 residues, SHA256 prefix `683d491559bf9eef`. Both show ITGAV M430C plus the same insertion/terminal construct sequence. The other bound molecules do not make this receptor partner a different molecular identity. [5FFG header](https://files.rcsb.org/header/5FFG.pdb), [5FFO header](https://files.rcsb.org/header/5FFO.pdb).
   - Rules **130/131**, same target/partner at **5NER/5NET**: complete deposited chain-A SEQRES is identical, 594 residues, prefix `60413b6ee3b5a999`. Preserve differences in the viral complexes as source context, not separate ITGAV names. [5NER header](https://files.rcsb.org/header/5NER.pdb), [5NET header](https://files.rcsb.org/header/5NET.pdb).
   - Rules **70/71**, LRP6 target O75581, DKK1 partner at **5FWW/5GJE**: complete deposited chain-C SEQRES is identical, 85 residues, prefix `a0addf377ec7a6d5`. Both map to O94907. A shared domain-construct label does not require claiming intact native DKK1. [5FWW header](https://files.rcsb.org/header/5FWW.pdb), [5GJE header](https://files.rcsb.org/header/5GJE.pdb).

   These three changes reduce artificially duplicated named groups by three across the batch. They do not justify merging the other ITGAV or DKK1 constructs; inspected sequences differ in length, insertions, deletions or tags.

2. **Medium — receptor-role category consistency.** Rules **74/75** identify an FZD8–FKBP fusion in an LRP6 assembly; rule **180** identifies sequence-discrepant B2M in an HLA-C complex. Keep the construct qualifiers, but use `receptor_partner` under the parent's established policy that engineering alters identity qualifiers rather than established receptor/assembly role. This does not imply wild-type sequence or native full-protein accessibility. [21KR](https://www.rcsb.org/structure/21KR), [21KS](https://www.rcsb.org/structure/21KS), [1QQD header](https://files.rcsb.org/header/1QQD.pdb).

## Checks accepted and nonblocking improvements

- **MR1 rules22/23,7RNO:** EC-only exclusion is defensible for this particular intracellular chaperone-loading assembly, with raw/all-scope observations retained. The primary work distinguishes native TAPBPR-mediated intracellular MR1 retention from a trafficking-permissive TAPBPR-TM construct. Keep the integrative docking/NMR/restrained-MD and human/bovine chimera caveats; do not call it an independent atomic crystal-contact experiment. This is a scoped localization judgment, not a claim that all B2M/MR1 complexes are intracellular. [Primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9703140/).
- **LY354740 rules24/27:** therapeutic classification is supported, but the present PMID13129812 citation is a review. Prefer the primary randomized phase-II trial [PMID16192835](https://pubmed.ncbi.nlm.nih.gov/16192835/) or primary human challenge study [PMID12709777](https://pubmed.ncbi.nlm.nih.gov/12709777/). Do not conflate with the prodrug LY544344.
- **JNJ-40411813 rule31:** primary human phase2a trial independently verified; lack of demonstrated efficacy does not undo investigational-therapeutic identity. [PMID41175011](https://pubmed.ncbi.nlm.nih.gov/41175011/).
- **BACE2 rules178/179:** global exact clone aliases only extend XA4813/XA4815 to same-named no-PDB assays. They do not match the unassigned, sequence-different 7D5B Xaperone. No blocker found.
- **ITGB6,LRP6,NRP2,AGER fragments:** labels appropriately avoid claiming whole native proteins where capped peptides, engineered latent TGFβ1, synthetic/foreign peptides or unresolved construct boundaries are represented. The unresolved category may remain conservative without deletion.
- **Matcher semantics:** raw numeric IEDB IDs are not used as names; exact labels and normalized Fab/Fv suffix behavior were checked. Each reference field is one URL. Scoped rules take precedence over broad aliases.

Safe subset recommendation: all 180 rules are acceptable after the nine affected rows above receive canonical-label/category corrections. These are review corrections, not a request to drop their observations. Primary clinical-citation improvement is nonblocking. The author has been notified directly; final corrected file should be checked once for the specific changes and matcher consistency.

## Final resolution

The parent authorized direct correction of this temporary proposal after the original author completed. Applied exactly nine row edits to `batch2-rules.json`:

- 70/71 → `DKK1 85-residue domain construct (5FWW/5GJE)`.
- 127/128 → `ITGAV M430C insertion construct (5FFG/5FFO)`.
- 130/131 → `ITGAV M430C construct (5NER/5NET)`.
- 74/75/180 → category `receptor_partner`, retaining existing qualified names.

All 180 rules remain. Re-ran the production matcher on all 626 observations: no conflicts. The final corrected rule set is accepted. The original author's report/ledger estimated counts precede these edits; parent will regenerate the final counts and documentation during integration. The independent sequence checks imply three fewer named construct groups than the pre-peer proposal.

The reciprocal ITGAV-target 5FFO TGFB1 correction is independently compatible with this review: it concerns the engineered TGFB1 ligand, whereas the 127/128 merge concerns the identical ITGAV receptor subunit observed against the ITGB6 target. Keep the shared `Engineered latent TGFB1 proprotein construct (5FFO)` tool label across reciprocal targets; do not merge that ligand with native mature TGFB1. The primary paper and SEQADV distinguish construct numbering from precursor numbering. [Primary 5FFO study](https://pmc.ncbi.nlm.nih.gov/articles/PMC5586147/).
