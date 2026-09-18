# Minimal HLA identity follow-up — six actual deposits

This is a preparatory schema proposal, not a record relabeling or deployment. The companion JSON maps **18 original observations across six deposits**, preserving the original release IDs and residue evidence. Public mmCIF files were checked in addition to the existing PDBe metadata. Each example records its mmCIF SHA256 and source URLs.

The minimum defensible change is to separate **the deposited molecular entity**, **the HLA/peptide context**, and **the source observation**. A display name or UniProt source-protein accession cannot serve as all three.

## What the six examples establish

Author chain identifiers and mmCIF label-asym identifiers are separate namespaces. All chains below are listed as **author / label**; entity IDs are deposition-local.

| Deposit / current target | HLA target and allele | Partner identity that can be recovered | Current information loss |
|---|---|---|---|
| 7STF / P04439 | entity4, A/D; HLA-A*03:01 | V2 Fab: heavy entity1 H/A, light entity3 L/C. KRAS G12V peptide: entity2 C/B, `VVVGAVGVGK`. B2M entity5 B/E. | Exported AACDB row drops antibody/target chains; upstream record4943 retains H/L→A. The raw KRAS source accession does not itself say “10-residue mutant peptide.” Bare `A` is particularly dangerous: author A is HLA, label A is Fab heavy chain. |
| 2CLR / P04439 | entity1, A/A or D/D; HLA-A*02:01 | CALR peptide entity3 C/C or F/F, `MLLSVPLLLG`; B2M entity2 B/B or E/E. | Two equivalent assemblies. Current observation cannot identify which copy generated contacts. CALR source accession is the same as the whole chaperone in 7QPD. Deposited HLA accession P01892 differs from gene-level P04439. |
| 7QPD / P04439 | entity4 M/D; HLA-A*03:01, peptide-receptive | CALR protein entity5 C/E, length400; PDIA3 entity3 E/C, length481; tapasin entity2 T/B, length428; B2M entity1 B/A. | No peptide polymer is modeled. This is ER loading machinery, not another CALR presented peptide. A protein-only residue footprint also omits the biologically important glycan bridge. |
| 5NI9 / P01903 | DRA entity1 A/A; DRA allele unresolved. DRB1 entity2 B/B, DRB1*04:01 | ENO1 peptide entity3 C/C, `KRIAKAVNEKSCNCL`, **Cys12–Cys14 disulfide explicitly deposited**. | BioLiP `peptide` and PDBe `P06733` have different current ligand IDs but resolve to the same deposited peptide entity. Current export drops BioLiP chain C. Plain sequence alone loses the disulfide/oxidation state. |
| 1AQD / P01903 | DRA entity1 A/A,D/D,G/G,J/J, DRA*01:01; DRB1 entity2 B/B,E/E,H/H,K/K, DRB1*01:01 | HLA-A-derived peptide entity3 C/C,F/F,I/I,L/L, `VGSDWRFLRGYHQYA`. | Four equivalent copies. “HLA-A” is a 15-residue peptide, not an intact class-I receptor. Raw source P04439 differs from deposited peptide accession P01892. |
| 6UJ9 / P01889 | entity1 A/A, HLA-B*07:02 | 2Q1 Fab heavy entity5 H/E, light entity4 L/D; IDH2 R140Q peptide entity3 C/C, `SPNGTIQNIL`; B2M entity2 B/B. | AACDB and anonymous SAbDab rows have different current IDs but share the directly recovered H/L→A chain assignment. The IDH2 accession labels a mutant peptide rather than the enzyme. |

Primary deposition evidence: [7STF](https://www.rcsb.org/structure/7STF), [2CLR](https://www.rcsb.org/structure/2CLR), [7QPD](https://www.rcsb.org/structure/7QPD), [5NI9](https://www.rcsb.org/structure/5NI9), [1AQD](https://www.rcsb.org/structure/1AQD), [6UJ9](https://www.rcsb.org/structure/6UJ9). The [7QPD primary paper](https://doi.org/10.1038/s41467-022-32384-z) identifies HLA-A*03:01 as the modeled/predominant allomorph and describes the empty peptide-receptive groove. Peptides used in its functional assays must not be attached to this deposited structure as if modeled there.

## Minimal fields

Add one optional `molecular_context` reference to a source observation and keep the richer information in a release sidecar. Do not replace the original `partner`, `partner_label`, `positions`, `ligand_id`, or `observation_id` in the first migration.

The sidecar needs four small record types:

1. **Deposition entity:** `pdb_id`, `entity_id`, deposited name, author/label chain mapping, deposited reference accessions, chemical residue tokens in order, intra- and inter-entity covalent connections, sequence/metadata provenance and completeness status. Preserve full entity sequence separately from observed coordinate coverage. Antibody partners reference an ordered heavy/light pair rather than pretending one chain is the whole Fab.
2. **HLA context:** target entity, class, each HLA component's explicit allele or null, target construct identity, presented peptide entity or a typed peptide state, and source provenance for every allele assignment. Class-II context includes the beta chain even when the requested target is DRA. “No peptide modeled / peptide-receptive” is different from “peptide identity unknown.”
3. **Observation-to-entity link:** original observation ID, target entity, partner entity or paired entities, partner role, source-chain evidence, candidate assembly/copy links and mapping confidence. A list of candidate equivalent copies is legitimate; inventing one selected copy is not.
4. **Identity/counting resolution:** resolved local construct-context group key, optional globally reconciled molecular key, and an explicit unresolved status. Source aliases are evidence attached to an identity, not ingredients of its key.

Use a short role enum independent of therapeutic/endogenous category: `presented_peptide`, `antibody`, `assembly_subunit`, `peptide_loading_chaperone`, `other`, `unresolved`. This already fixes the CALR peptide-versus-protein ambiguity without requiring a new pharmacology category.

## Reliable recovery and limits

**Entity and chain recovery:** mmCIF `_struct_asym` gives entity membership; `_pdbx_poly_seq_scheme` gives label/auth chain mappings. `_pdbx_struct_assembly_gen` gives assembly copies and operators. An assembly pair is only a co-assembly candidate, not proof that an original contact extractor used that pair or operator. The JSON explicitly avoids making that claim.

For the two antibody examples, the existing upstream AACDB evidence still has the chains. SAbDab 6UJ9 `observations.tsv.gz` details also retain `Hchain=H`, `Lchain=L`, `target_chain=A`. BioLiP 5NI9 retains `binder_identity=5ni9:C:0:326 ~ 339`; chain C is recoverable. Its source span text disagrees with the deposited complete 15-residue ENO1 range326–340, so preserve the original string and use the complete deposited entity for construct identity. Do not trim its sequence to fit a lossy span.

For generic PDBe protein-partner observations, current public records retain only accession, PDB and canonical target residue union. The six reviewed examples permit a curated unique-entity assignment, but multiple equivalent copies in 2CLR/1AQD remain indistinguishable. A different deposit could contain multiple peptides from the same accession, fused peptides, more than one allele or more than one Fab. There, return candidate entity sets and unresolved status; never choose the shortest peptide or the closest residue footprint as identity proof.

**Chemical identity:** `_entity_poly_seq.mon_id` preserves CCD residue tokens. `_struct_conn` contributes crosslinks and covalent attachments. At 5NI9 the peptide has standard one-letter residues but a deposited S–S link between Cys12 and Cys14. Therefore a sequence hash is insufficient. The JSON records intrachain links and external links, including tapasin–PDIA3 and glycan attachments in 7QPD. Deposit chemistry is still a model: terminal chemistry, unmodeled modifications, processing state and complete glycans have not all been independently validated. `global_unique_molecule_key` therefore remains null in these example outputs.

**Alleles:** recover explicit two-field names from deposition metadata or a primary paper. Do not infer an allele from current canonical UniProt alone. 2CLR uses deposited P01892 while the current target is P04439; 5NI9 DRB1 uses P13760 while source partner is P01911; 1AQD DRB1 uses P04229 while source partner is P01911. These are reviewed locus/allele correspondences, not exact accession equality. Preserve both and preserve the existing canonical-reference sequence hash. This proposal does not authorize changing residue numbering. DRA*01:01 is supported for 1AQD by deposited gene annotations; it is deliberately **not inferred for 5NI9**.

## Deterministic keys and honest counts

Implement identity in two stages so an incomplete migration cannot publish another misleading “unique ligand” number.

**Stage1, directly implementable with these examples:**

- `local_entity_key = pdb-entity:{pdb_lower}:{entity_id}`.
- A multi-chain partner is `pdb-partner:{pdb_lower}:{ordered_entity_ids}`, heavy then light for a Fab. Equivalent crystallographic copies share this identity.
- `target_context_key` hashes a versioned canonical JSON object containing target entity, the local deposition, HLA component allele assertions/fallback construct IDs, peptide entity or typed peptide state. The companion JSON provides actual bases and SHA256-derived keys.
- `local_context_group_key` hashes `[target_context_key, role, local_partner_key]`. Different data sources linking the same local construct receive the same group key even when their footprints differ; retain all footprints separately.
- Unknown entities have **no resolved group key**. Report their evidence count separately, rather than treating a generic string like `peptide` or `unknown` as one molecule or each unknown row as a new molecule.

Call the stage1 statistic **resolved construct-context groups**, not unique ligands. Do not total local groups across PDBs and call that a global molecular count. In these six examples, 18 source observations yield **16 local groups**: 5NI9 peptide/ENO1 coalesces, and 6UJ9 AACDB/SAbDab Fab coalesces. CALR 2CLR and 7QPD deliberately remain distinct. This is an executable local deduplication check, not a claim that the eight proteins or the full HLA cohort have 16 ligands.

**Stage2, only after chemical/allele reconciliation:** define a global molecular signature from ordered chemical residue tokens, chain topology, relevant modifications, covalent bonds and validated termini. Include actual chain composition for multi-chain binders. Use a separate interaction-context signature incorporating HLA allele pair/construct and presented peptide chemical signature. Unknown fields prevent global resolution instead of being normalized to a universal `null` that merges unrelated molecules. Gene/source accession is provenance and retrieval context, not a substitute for chemical identity. Full-drug identity remains distinct from a matched antibody arm.

The same chemical peptide can bind several alleles: its molecular key may be shared, but its interaction-context keys must differ. Conversely two distinct peptides from the same source accession must not share a molecular key. B2M assembly contacts can remain searchable without counting them as soluble peptide ligands.

## Narrow implementation sequence

1. Preserve chain/entity source details in the build intermediate before projection to public records. Currently the exporter creates `ligand_id` from the normalized display name or source label; that is the immediate cause of both false CALR merging and anonymous/source-duplicate splitting.
2. Build an optional context sidecar for these six reviewed deposits only; keep original IDs stable in this first additive migration. Record the mmCIF hash and provenance so future deposition changes are detectable.
3. Link observations only through explicit upstream chains or a reviewed unique entity assignment. Resolve neither multiple entities nor copy-specific footprints heuristically.
4. Add a separate “resolved construct-context groups” statistic, alongside unresolved evidence count. Keep legacy counts visibly versioned until a deliberate API migration.
5. Validate the six examples: author/label namespace correctness at7STF; CALR separation; no fabricated7QPD peptide; 5NI9 disulfide retained and duplicate merged; 1AQD four-copy ambiguity preserved; 6UJ9 Fab duplicate merged using chains; HLA allele/source accession differences retained.

No broad HLA relabel, biochemical-category reassignment, atom-level contact recomputation or production publication is implied by this proposal.
