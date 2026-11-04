> Review history: this is an initial proposal or independent critique, not the final accepted rule set. See the consolidated report for accepted corrections and final counts.

# Independent peer review of complex-ligand rules

Reviewed 2026-09-18. **Indices below are zero-based JSON `rules` indices**, with one-based numbers where helpful. Reviewed all 99 proposed rules, their report, the 2,189-observation snapshot and relevant cached PDBe entities. Independently opened primary papers/PDB records for the material issues. No source rules or shared repository files were edited.

**Recommendation: do not apply all 99 unchanged as a native extracellular-ligand curation.** The rule matcher is mechanically sound, but several canonical labels erase engineered-molecule or compartment distinctions. Most remaining rules are suitable as identity/category annotations if the existing fragment and evidence caveats remain visible.

## Material changes required

### 1. Rules 21 and 28 (22nd and 29th): engineered CD4 variants become one native-looking CD4 partner

Targets P01903 and P01911; names P01730/CD4; unrestricted PDB; canonical `CD4`, category `receptor_partner`.

Each rule matches three observations, at 3S4S, 3S5L and 3T0E. These are deliberately affinity-enhanced CD4 constructs. The primary 3S4S/3S5L study identifies Q40Y/T45W affinity enhancement and explicitly calls the mutants experimental tools. Cached 3S5L entity 4 additionally lists S60R/D63R; 3T0E entity 5 lists Q40Y/T45W. Thus the broad canonical label combines differing engineered molecules. The reason's generic warning does not preserve that distinction in an aggregated named partner.

**Hold 21/28; replace with PDB-specific engineered-CD4 labels, retaining the exact mutation set where verified.** `tool` describes the construct, while receptor/co-receptor role should be separate metadata. If `receptor_partner` must be retained, at least put “engineered CD4” in the canonical label and do not claim wild-type affinity. Do not trust a missing mutation flag: 3S4S cached flag is null although the paper explicitly describes the mutant.

Primary evidence: [affinity maturation study, DOI 10.1073/pnas.1109438108](https://doi.org/10.1073/pnas.1109438108), [3S4S](https://www.rcsb.org/structure/3S4S), [3S5L](https://www.rcsb.org/structure/3S5L), [3T0E](https://www.rcsb.org/structure/3T0E).

### 2. Rule 98 (99th): capped synthetic peptide and large latent TGFβ3 share an endogenous label

Target P06756; P10600/TGFβ3 aliases; unrestricted PDB; canonical `TGFβ3 latency-associated region`, category `endogenous_large`.

It matches 4UM9 and 8VS6. Cached 4UM9 entity 4 is **`(ACE)HGRGDLGRLKK(NH2)`**, a terminally acetylated/amidated peptide, not an intact native latent protein. By contrast 8VS6 deposits a TGFβ3 proprotein complex. Normalizing the chemical sequence to `XHGRGDLGRLKKX` hides precisely the modifications needed here.

**Hold 98 and split by PDB:** label 4UM9 as the capped TGFB3-derived LAP peptide (`tool`, retaining sequence/modifications); retain an endogenous latent-protein label for 8VS6 after checking that construct. Same source accession is not molecule equivalence. No contact evidence should be deleted.

Primary evidence: [4UM9 deposit](https://www.rcsb.org/structure/4UM9), [PDBe entity metadata](https://www.ebi.ac.uk/pdbe/api/pdb/entry/molecules/4um9), [8VS6 deposit](https://www.rcsb.org/structure/8VS6).

### 3. Rules 16–18 (17th–19th): APP-fragment complexes become unqualified endogenous protein partners

Target P05067; ACE, IDE, MMP2; unrestricted PDB; all `endogenous_large`, all included in overview.

- **16 ACE:** two contacts, 5AM8 and 5AMB, bind short Aβ fragments with soluble ACE domains. Cached ACE mutation flag is `YES` in both deposits. The rule currently only says “Human enzyme partner.”
- **17 IDE:** three contacts, 2G47/2WK3/4M1C, involve Aβ fragments. Cached 2G47 and 4M1C IDE list E111Q; 2WK3 also flags a mutant.
- **18 MMP2:** 3AYU is an active-site-mutant catalytic-domain complex with a 10-residue APP-derived inhibitor. Cached entity 1 lists E108K/Q110V/E121A. Canonical `MMP2`/`endogenous_large` misrepresents the observed engineered construct if interpreted as a native partner.

**Hold these rules for the native-surface overview.** For retained contact evidence, use PDB/construct-qualified labels (e.g. engineered IDE–Aβ substrate complex) and a target-fragment field. The study can support a biological relationship without establishing that the intact cell-surface APP molecule was bound in the experiment. At minimum 18 requires an engineered-MMP2 label rather than a bare endogenous assignment. Rules 16/17 likewise need explicit domain/mutation and Aβ context before becoming a native ligand count.

Primary deposits: [5AM8](https://www.rcsb.org/structure/5AM8), [5AMB](https://www.rcsb.org/structure/5AMB), [2G47](https://www.rcsb.org/structure/2G47), [2WK3](https://www.rcsb.org/structure/2WK3), [4M1C](https://www.rcsb.org/structure/4M1C), [3AYU](https://www.rcsb.org/structure/3AYU). Exact mutation strings above are from corresponding cached PDBe entity records, not inferred from shared footprints.

### 4. Rules 22, 23 and 29 (23rd, 24th, 30th): endosomal peptide editor remains in extracellular overview

These classify HLA-DMA/HLA-DMB contacts from 4FQX as `receptor_partner` with `exclude_from_overview: false`. The primary study concerns **endosomal HLA-DM-catalyzed peptide selection**. This is the same compartment error that proposed rules 43/44 correctly address for ER loading machinery. An HLA ectodomain’s eventual cell-surface topology does not make the DM encounter extracellular.

**Hold for a native cell-surface overview, or narrow to 4FQX and exclude from that overview while retaining “HLA-DM peptide editor” evidence.** A dedicated `chaperone/peptide_editor` role and `endosomal` compartment are preferable to receptor partner. This finding does not deny that the proteins bind; it concerns the claim made by the surface overview.

Primary study: [Pos et al., Cell 2012, DOI 10.1016/j.cell.2012.11.025](https://doi.org/10.1016/j.cell.2012.11.025), [4FQX](https://www.rcsb.org/structure/4FQX).

## Conditional scopes and nonblocking corrections

- **Rule 97:** TGFB1 matches 5FFO, 6OM2, 7Y1T and 8VSD. 6OM2 deposits isolated `GRRGDLATIHG`; the others are larger latent/proprotein assemblies. “Latency-associated region” is a good biological qualification, but not one molecular identity. Keep separate peptide-versus-proprotein constructs if the count means distinct molecules. A native-sequence peptide alone does not prove an endogenous free peptide species. [6OM2](https://www.rcsb.org/structure/6OM2), [5FFO](https://www.rcsb.org/structure/5FFO).
- **Rules 0–13 and 19–20:** antibody/tool lineage and engineered-APPI labels are useful, but leave APP-fragment observations included. They are safe as contact annotations, not as verified intact-surface-APP accessibility. Apply a fragment-aware gate to existing APP therapeutic rows too; merely changing new research-antibody categories would be inconsistent. This is a schema/display issue rather than evidence that their names are false.
- **Rules 37–38:** Fab V2 and 2Q1 are correctly PDB-scoped, but their canonical names omit the peptide-HLA restriction. Prefer visible labels including KRAS G12V/HLA-A*03:01 and IDH2 R140Q/HLA-B*07:02. These are not pan-HLA binders. [7STF](https://www.rcsb.org/structure/7STF), [6UJ9](https://www.rcsb.org/structure/6UJ9).
- **Rules 65–68 are supportable; do not reject solely because the deposited B-chain mapping says INS-IGF2.** I independently checked the primary study: methods explicitly use recombinant human insulin, and the reagents section identifies Sigma 91077C. This independently supports the insulin identity across 7YQ3/4/5 and 8GUY despite the 25-residue deposited fragment and readthrough accession. Strengthen their reference/reason with the primary methods rather than just a PDB title or sequence resemblance. [Kim et al., 2022, methods and reagents](https://www.nature.com/articles/s41467-022-34292-8).

## HLA presented peptides: no blanket endogenous-rule defect found

The proposal correctly leaves human-source HLA peptide families unclassified rather than assigning all of them `endogenous_small` or `endogenous_large`. There is **no proposed blanket endogenous HLA-peptide rule to remove**. Rule 45 correctly restricts ENO1/generic peptide reconciliation to 5NI9; 39–42 correctly scope the reciprocal HLA-A-fragment target exclusions. Preserve these precautions.

However, unchanged names such as CAMP, VIM, ENO1, insulin and HLA-A still represent different presented sequences/chemical species. They should not count as full proteins or one distinct ligand per accession. Needed fields: target HLA allele, target/partner entity and chain, deposited peptide sequence including nonstandard residues and caps, peptide register, tether/fusion status and paired TCR variable clonotype. Do not infer ligand category from human origin or an entity’s protein name. The report already documents these unresolved cases accurately.

## Safe-subset recommendation

For **observation-level identity annotations with explicit construct/evidence caveats**, retain the following zero-based indices without a material identity/category objection from this bounded review:

`0–15, 19–20, 24–27, 30–96`.

That is **89 rules**. Hold `16–18, 21–23, 28–29, 98` (**9 rules**) pending the changes above. Rule `97` (**1 additional rule**) is conditional on whether the overview groups source regions or distinct molecules; split it before using it for a molecular-species denominator. Including that conditional rule would give a 90-rule subset.

These are safety classifications for the proposed diff, not a certification that all unchanged source records or every footprint is biologically correct. For **verified native intact-surface-binding counts**, also withhold the APP-fragment groups `0–13,19–20` until the target-fragment display/gate is implemented. A mere rule-index subset cannot solve those already-existing source semantics.

## Mechanical checks

Reimplemented the current normalization/matching semantics against all raw observations: **99/99 rules match at least one record; 1,104 total rule matches; zero multi-rule collisions**. These checks include PDB restrictions. Numeric IEDB IDs are appropriately avoided where they would mix variants. Do not broaden PDB-scoped insulin, fibronectin or HLA exclusions; apply rules before aggregation. The matcher cannot distinguish chains, sequences, assays or mutant identity within one PDB, and exclusions are sticky.

Only this peer-review document was written. No rule-file edits, shared repository mutations, remote writes, merges or publication were performed.
