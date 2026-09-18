# Independent peer review — batch 3

Reviewed the 17-target, 633-observation snapshot against the current 129 proposed rules. Proposal SHA256: `7ff608f5e649c190d94d7fecb7b4f5506aa1c9bc1bdb21b13dda4495a6761fb1`. Independent production-matcher simulation: 479 matched observations, 0 identity/category collisions; unmatched rule indices []. No shared files or original proposals were edited by this reviewer.

**Recommendation: accept current proposals with the explicit caveats below.** Material errors found during review were reported to root and corrected in the current JSON. No blanket exclusions, unsupported drug-arm exclusions, or unsafe bare numeric aliases were found. Acceptance of broad receptor-subunit groups is conditional on their stated role-group semantics; it is not a complete sequence-equivalence certification across all constructs.

## Findings corrected by author

- Original rules102/103, HLA-G/P16104 at2D31/2DYP: deposited peptide is **RIIPRHLQL, nine residues**, whereas the original reason incorrectly said eight. Rule104/9RWI is **IIPRHLQL, eight residues**. Distinct PDB-qualified identities should remain. Independently checked PDBe entity sequences and [2D31 deposited entity3](https://www.rcsb.org/structure/2D31), [2DYP](https://www.rcsb.org/structure/2DYP), [9RWI](https://www.rcsb.org/structure/9RWI). These are presented fragments, not full histone H2AX; source-protein uniqueness cannot be concluded from the short sequence alone.
- Rule23, ITGB3/SRC at4HXJ: the deposited partner is the **SRC SH3 domain**, about60 residues, bound to the target's **RGT tripeptide**. Original generic SRC name was insufficiently specific. Root corrected the name; intracellular evidence appropriately remains all-scope. [4HXJ](https://www.rcsb.org/structure/4HXJ).
- Rule16, ITGB3/FN1 at4MMY: entry title says **IAKGDWND**, but entity3 polymer sequence contains **IARGDWNDG**, and mutation annotation says TGRGDSPASS→IARGDWNDG. Root replaced the motif-specific canonical name with a deposit-qualified engineered FN10 construct and documents this inconsistency. Do not resolve it from the title alone. [4MMY](https://www.rcsb.org/structure/4MMY), [primary paper](https://doi.org/10.1038/nsmb.2797).

## 8VS6 generic peptide decision independently resolved

Accept rule75's narrowly scoped merger. The upstream BioLiP evidence row (not just the footprint) has `binder_identity=8vs6:E:0:240 ~ 249`. PDBe UniProt mapping assigns **author chain E** to **P10600/TGFB3**, entity1, deposited389-residue proprotein, mapping UniProt24–412. The other two protein entities are ITGAV and ITGB8. Thus the short BioLiP projection and unrestricted PDB/PDBe accession row describe portions of the same deposited TGFB3 construct. This is not a free10-residue ligand claim and not inference from matching contact sites.

Evidence: [PDBe entity metadata](https://www.ebi.ac.uk/pdbe/api/pdb/entry/molecules/8vs6), [PDBe UniProt mappings](https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/8vs6), [primary study PMID39288764](https://pubmed.ncbi.nlm.nih.gov/39288764/). Local source: `/private/tmp/surfaceome-binder-coverage/data/analysis/deep_dive_binding_sites/biolip_gpcrdb_evidence.tsv.gz`; exact snapshot observations `obs-2e56f8bafe4a6c3320f87176e24a02e2` and `obs-98c639ab3724a90d94aff3ddcdfe1b77`. Keep unclassified construct category until cleavage/chemical details are reconciled.

## Held aliases and context limitations

- **EPOR DA5/DA10/DA330 remain separate unresolved IEDB names.** Snapshot has PDB-linked IEDB rows (2445265→4Y5V;2399546→4Y5X;2399543→4Y5Y) plus no-PDB rows, but this alone does not independently prove clone equivalence to305/310/330. 4Y5X title says305 while entity description says310. Avoid numeric667/668/669 rules. [IEDB2445265](https://www.iedb.org/assay/2445265), [IEDB2399546](https://www.iedb.org/assay/2399546), [IEDB2399543](https://www.iedb.org/assay/2399543), [4Y5X](https://www.rcsb.org/structure/4Y5X). Using the exact assay URLs in rules45–47 would improve references over the current IEDB homepage.
- **ITGB3/2Q6W target peptide is engineered.** Deposited target entity3 is12-residue AWRSDEALPLGS with C26R annotation. Rules11/12 correctly avoid an intact integrin/receptor claim; add the target C26R construct caveat in the ledger/overview rather than naming a native platelet peptide without qualification. [2Q6W](https://www.rcsb.org/structure/2Q6W).
- **RAMP1 native CGRP entries retain terminal-chemistry caveat.** 6E3Y/9AUC explicitly encode terminal amidation;7KNU polymer text lacks that marker. This is an annotation difference, not sufficient evidence to invent a deamidated variant. Named peptide role group is acceptable; do not claim chemically identical preparations without the primary methods. [6E3Y](https://www.rcsb.org/structure/6E3Y), [7KNU](https://www.rcsb.org/structure/7KNU), [9AUC](https://www.rcsb.org/structure/9AUC).
- **HLA counts remain partner groups, not unique peptides or whole-protein ligands.** HLA-C leader VMAPRALLL, HLA-A leader VMAPRTLVL and HLA-G leader VMAPRTLFL have direct deposited nine-residue sequences. Native-derived peptide category is defensible with the explicit fragment names, but no full HLA protein interaction follows from them. Generic antigen/tethered peptides remain unclassified.

## Coverage of targeted independent checks

| Target | Check and disposition |
|---|---|
| CD3D | Broad receptor-subunit roles and scoped unresolved9C3E peptide acceptable; no free therapeutic clone inferred from TCR-complex membership. |
| ITGB3 | Checked FN10 motifs, fibrinogen peptide scope, SRC fragment, and HLA-presented target fragment. Corrections above; LM609 remains distinct from humanized etaracizumab, abciximab remains named therapeutic Fab evidence. |
| HLA-E | Directly read leader-peptide sequences at3BZF/5W1W/3BZE/3CDG/3CII and microbial7P4B IMYNYPAML. Fragment distinctions retained. |
| BTN3A1 | Separate103.2/20.1/CTX-2026 clones and assembly-role groups; no unsupported drug synonym promotion. |
| EPOR | Independent1CN4/1EER deposited EPO sequences support N24K/N38K/N83K, with additional P121N/P122S only1EER in construct numbering. DA aliases remain held; methylated residues in4Y5Y do not establish native-parent chemical identity. |
| CACNA2D1 | Channel-subunit role groups acceptable; all raw structure and compartment context retained, no identical whole-construct claim. |
| RAMP1 |5V6Y deposit directly supports AM37–52 S45W/K46L/Q50W/Y52F amidated fragment and receptor fusion.9BLW sequence/deposit supports non-acylated cagrilintide backbone, not native amylin or complete lipidated drug. |
| PRNP | ICSM18/PRN100 distinction preserved; Nb484 and POM1 remain distinct tools. |
| ITGB8 | TGFB1 latent constructs remain unclassified;6OM2 peptide distinct.8VS6 chain identity now positively verified.130H2 variable-domain construct not intact IgG. |
| HLA-DQA1 | DQN clones scoped to exact peptide/HLA deposits.6U3M21-residue alpha1a entity AQPMPMPELPYPGSGGSIEGR retained unclassified rather than human endogenous protein. |
| TNFSF13B | Belibumab spelling corrected to belimumab with deposited named chains at5Y9J/6FXN; target H218A does not change antibody identity.1OQE receptor fragment uniquely31 residues, correctly scoped. |
| RET |6Q2S artemin and yeast SUMO map same fusion entity;6Q2N/O/R/J ligand domains preserve multicomponent context. Vandetanib kinase context retained. |
| HLA-G | Nine- versus eight-residue histone fragments corrected; no full histone ligand claim. |
| CD8A |8EW6 exact VHH5 scope; broad MR1/HLA roles preserve deposit context.7UMG target CD8A is engineered C54S in UniProt numbering, as reciprocal batch2 review records. |
| ACE |5AM8FRHDSGY and5AMB MVGGVVIA verify Aβ4–10/Aβ35–42;4APH DRVYIHPF is angiotensinII;4APJ pyroglutamyl venom peptide is not human bradykinin. |
| CDH3 | Experimental TSP7/TSP11/CQY684 remain separate; no therapeutic inference for G60. |
| CD9 | AT1412dm construct separated from unmodified parent and clinical claims;4C8 and4E8 remain distinct. |

The five appended receptor-mutant overrides retain exact PDB scope and do not introduce global aliases. This bounded peer pass independently checked high-risk deposited entity/sequence claims and matching safety; it does not claim re-reading every full primary article for all633 observations. Unresolved raw observations and missing chemistry remain explicit, with no publication/deployment implied.
