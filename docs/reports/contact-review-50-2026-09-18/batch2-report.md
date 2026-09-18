# Batch 2 manual contact-partner review

Reviewed all 16 target inventories and preserved all 626 source observations. 180 proposed rules match 525 observations, with zero competing identity/category outcomes at the most-specific PDB scope. Rules are proposals for cross-review; production is unchanged.

The ledger identifies every partner/PDB/context group and its exact observation IDs. “Unresolved” means retain raw evidence without new identity/category promotion; it does not mean absence of biological interaction. Counts below are estimated named display groups, not distinct whole molecules. Receptor subunit, HLA allele/peptide, construct and fusion contexts remain essential. After counts apply these proposals to this snapshot only; the authoritative rebuild may include other concurrent review rules.

Evidence: downloaded deposited headers (COMPND, DBREF, SEQADV, SEQRES), RCSB entry/CCD metadata, cached therapeutic-arm sequence evidence, and cited primary studies/official trial identity. A legacy PDB header retrieval failure is not evidence that a deposit is missing; 37 such entries have cached RCSB entry metadata. No footprint-only antibody equivalence is used. Exact matching follows the production normalized-name matcher and PDB-specific precedence.

## Coverage and display impact

| Target | Accession | Raw observations | Named EC before → estimated after | Named all before → estimated after |
|---|---|---:|---:|---:|
| GABRA1 | P14867 | 168 | 5 → 5 | 9 → 11 |
| MR1 | Q95460 | 105 | 5 → 4 | 5 → 6 |
| GRM2 | Q14416 | 59 | 8 → 7 | 12 → 11 |
| TNF | P01375 | 51 | 13 → 13 | 13 → 13 |
| GRM3 | Q14832 | 40 | 6 → 7 | 6 → 7 |
| LRP6 | O75581 | 31 | 6 → 13 | 6 → 13 |
| BACE2 | Q9Y5Z0 | 27 | 8 → 6 | 8 → 6 |
| HLA-C | P10321 | 25 | 5 → 6 | 5 → 6 |
| ITGB1 | P05556 | 23 | 6 → 8 | 6 → 8 |
| ITGB6 | P18564 | 19 | 4 → 13 | 4 → 13 |
| ITGB7 | P26010 | 17 | 5 → 6 | 5 → 6 |
| CDH1 | P12830 | 17 | 4 → 4 | 5 → 6 |
| NRP2 | O60462 | 13 | 4 → 3 | 4 → 3 |
| MADCAM1 | Q13477 | 11 | 6 → 4 | 6 → 4 |
| AGER | Q15109 | 10 | 5 → 9 | 5 → 9 |
| GRM8 | O00222 | 10 | 4 → 3 | 4 → 3 |

## Decisions and pending uncertainties

### GABRA1 — P14867

Exact neurotransmitter and drug CCDs resolved. Receptor-subunit labels are assembly-role groups, not assertions of identical full-length constructs. A50T gamma2 and the 8PET beta3 insertion are separate. Anonymous Fabs, megabody/scaffold or collagen-mapped fusion accessions remain unresolved; do not promote full native collagen from accession alone. Membrane-site anesthetic observations remain in their original compartment.

- Rule 1; 6X3T: **GABA** (endogenous_small). CCD ABU is gamma-aminobutyric acid, the native neurotransmitter; direct GABA-bound receptor structure. Other anesthetics in the assembly are distinct molecules. [Primary/deposit evidence](https://www.rcsb.org/structure/6X3T).
- Rule 2; explicit alias across source observations: **Flumazenil** (therapeutic). Exact chemical component and primary structural study identify Flumazenil; preserve source compartment and active-moiety identity. No inference that every receptor subunit contact is extracellular. [Primary/deposit evidence](https://www.rcsb.org/structure/6D6U).
- Rule 3; explicit alias across source observations: **Alprazolam** (therapeutic). Exact chemical component and primary structural study identify Alprazolam; preserve source compartment and active-moiety identity. No inference that every receptor subunit contact is extracellular. [Primary/deposit evidence](https://www.rcsb.org/structure/6HUO).
- Rule 4; explicit alias across source observations: **Diazepam** (therapeutic). Exact chemical component and primary structural study identify Diazepam; preserve source compartment and active-moiety identity. No inference that every receptor subunit contact is extracellular. [Primary/deposit evidence](https://www.rcsb.org/structure/6X3X).
- Rule 5; 6HUK: **Bicuculline methochloride** (tool). Exact CCD H0Z identifies the methochloride antagonist reagent, not an endogenous ligand or a generic unmodified bicuculline compound. [Primary/deposit evidence](https://www.rcsb.org/structure/6HUK).
- Rule 6; explicit alias across source observations: **GABRB1 receptor-subunit group** (receptor_partner). GABRB1 is an assembly subunit, not an independent administered binder. Group denotes protein role, not identical full constructs across deposits; source truncations/assembly/compartment remain. Verified variant overrides are scoped separately. [Primary/deposit evidence](https://www.rcsb.org/structure/9CXD).
- Rule 7; explicit alias across source observations: **GABRB2 receptor-subunit group** (receptor_partner). GABRB2 is an assembly subunit, not an independent administered binder. Group denotes protein role, not identical full constructs across deposits; source truncations/assembly/compartment remain. Verified variant overrides are scoped separately. [Primary/deposit evidence](https://www.rcsb.org/structure/6X3T).
- Rule 8; explicit alias across source observations: **GABRG2 receptor-subunit group** (receptor_partner). GABRG2 is an assembly subunit, not an independent administered binder. Group denotes protein role, not identical full constructs across deposits; source truncations/assembly/compartment remain. Verified variant overrides are scoped separately. [Primary/deposit evidence](https://www.rcsb.org/structure/6X3T).
- Rule 9; explicit alias across source observations: **GABRB3 receptor-subunit group** (receptor_partner). GABRB3 is an assembly subunit, not an independent administered binder. Group denotes protein role, not identical full constructs across deposits; source truncations/assembly/compartment remain. Verified variant overrides are scoped separately. [Primary/deposit evidence](https://www.rcsb.org/structure/6HUK).
- Rule 10; 9FFV: **GABRG2 A50T construct** (receptor_partner). SEQADV explicitly maps deposited A11T to P18507 A50T. Preserve engineered-subunit distinction; no native assembly claim. [Primary/deposit evidence](https://files.rcsb.org/header/9FFV.pdb).
- Rule 11; 9FFW: **GABRG2 A50T construct** (receptor_partner). SEQADV explicitly maps deposited A11T to P18507 A50T. Preserve engineered-subunit distinction; no native assembly claim. [Primary/deposit evidence](https://files.rcsb.org/header/9FFW.pdb).
- Rule 12; 9FFY: **GABRG2 A50T construct** (receptor_partner). SEQADV explicitly maps deposited A11T to P18507 A50T. Preserve engineered-subunit distinction; no native assembly claim. [Primary/deposit evidence](https://files.rcsb.org/header/9FFY.pdb).
- Rule 13; 9FFZ: **GABRG2 A50T construct** (receptor_partner). SEQADV explicitly maps deposited A11T to P18507 A50T. Preserve engineered-subunit distinction; no native assembly claim. [Primary/deposit evidence](https://files.rcsb.org/header/9FFZ.pdb).
- Rule 14; 9FG1: **GABRG2 A50T construct** (receptor_partner). SEQADV explicitly maps deposited A11T to P18507 A50T. Preserve engineered-subunit distinction; no native assembly claim. [Primary/deposit evidence](https://files.rcsb.org/header/9FG1.pdb).
- Rule 15; 9FG2: **GABRG2 A50T construct** (receptor_partner). SEQADV explicitly maps deposited A11T to P18507 A50T. Preserve engineered-subunit distinction; no native assembly claim. [Primary/deposit evidence](https://files.rcsb.org/header/9FG2.pdb).
- Rule 16; 9FG3: **GABRG2 A50T construct** (receptor_partner). SEQADV explicitly maps deposited A11T to P18507 A50T. Preserve engineered-subunit distinction; no native assembly claim. [Primary/deposit evidence](https://files.rcsb.org/header/9FG3.pdb).
- Rule 17; 8PET: **GABRB3 insertion construct (8PET)** (receptor_partner). SEQADV includes inserted GLY424/THR425 in deposited numbering. Keep this receptor construct separate from the generic subunit group; exact reference insertion coordinates remain unresolved. [Primary/deposit evidence](https://files.rcsb.org/header/8PET.pdb).

### MR1 — Q95460

MR1 groups are antigen-presentation partners, not independent full-protein antigen counts. Microbial metabolite 1VY remains unclassified rather than endogenous-human. TCR-variable/constant accessions remain raw pending receptor-chain reconciliation. 7RNO is an integrative docking/NMR/restrained-MD model using human-bovine hybrid MR1 and bovine B2M; TAPBPR ligand-loading chaperone evidence is retained in all-scope but excluded from EC overview. CD8A C54S is engineered.

- Rule 18; 4L4V: **RL-6-Me-7-OH (1VY)** (unclassified). Exact CCD and deposit identify the ribityllumazine metabolite antigen. Do not infer endogenous-human origin from MR1 biology; microbial/metabolite provenance needs a separate enum. [Primary/deposit evidence](https://www.rcsb.org/structure/4L4V).
- Rule 19; explicit alias across source observations: **B2M** (receptor_partner). Structural light-chain component of MR1, not a separate antibody or soluble inhibitor. Preserve allele/ligand context and expression tags; no generic TCR aliases are merged. [Primary/deposit evidence](https://www.rcsb.org/structure/4L4V).
- Rule 20; 7UMG: **CD8A C54S construct (7UMG)** (receptor_partner). SEQADV maps deposited C33S to P01732 C54S. Retain engineered co-receptor construct rather than a wild-type CD8A assertion. [Primary/deposit evidence](https://files.rcsb.org/header/7UMG.pdb).
- Rule 21; 9C9D: **LILRB2** (receptor_partner). Deposited human inhibitory receptor partner of MR1. Preserve ligand/construct context; no TCR or antibody equivalence. [Primary/deposit evidence](https://www.rcsb.org/structure/9C9D).
- Rule 22; 7RNO: **TAPBPR chaperone (7RNO integrative model)** (unclassified). 7RNO is an integrative docking/NMR/restrained-MD model of Ac-6-FP/human-bovine hybrid MR1/bovine B2M/TAPBPR, not an atomic crystal-contact experiment. Chaperone/ligand-loading evidence belongs in all-scope context; native TAPBPR retains MR1 intracellularly. Exclude only EC overview, not raw evidence. [Primary/deposit evidence](https://pmc.ncbi.nlm.nih.gov/articles/PMC9703140/).
- Rule 23; 7RNO: **Bovine B2M (7RNO integrative model)** (unclassified). Bovine B2M in the hybrid-MR1 integrative docking/NMR/MD model; not an endogenous-human ligand or independent atomic crystal contact. Keep raw all-scope evidence and distinguish species. [Primary/deposit evidence](https://www.rcsb.org/structure/7RNO).

### GRM2 — Q14416

Synthetic modulators mapped to exact CCDs and named compounds. Investigational drugs are not described as approved. Heterodimer labels denote receptor-subunit roles; FKBP/FRB fusions and truncations remain construct caveats. P42345 at7EPD and other generic fusion/scaffold accessions remain unresolved rather than assuming free mTOR ligand. Cytoplasmic G-protein/arrestin evidence retained.

- Rule 24; explicit alias across source observations: **LY354740 (eglumegad)** (therapeutic). CCD40F and structural papers identify LY354740; clinical investigation supports therapeutic category, not approved status. Preserve identity separately from its prodrug LY544344. [Primary/deposit evidence](https://pubmed.ncbi.nlm.nih.gov/13129812/).
- Rule 25; explicit alias across source observations: **LY341495** (tool). Exact CCD Z99 and antagonist-bound structures identify the experimental group-II mGlu antagonist. Not endogenous glutamate. [Primary/deposit evidence](https://www.rcsb.org/structure/3SM9).
- Rule 26; explicit alias across source observations: **LY379268** (tool). Experimental synthetic agonist, distinct from LY354740 and glutamate; exact named source ligand retained. [Primary/deposit evidence](https://www.rcsb.org/structure/8TR2).
- Rule 30; explicit alias across source observations: **L-glutamate** (endogenous_small). Native amino-acid neurotransmitter; GLU identity confirmed by deposited chemical component in these heterodimers. Preserve receptor-state and compartment context. [Primary/deposit evidence](https://www.rcsb.org/structure/8JD2).
- Rule 31; explicit alias across source observations: **JNJ-40411813** (therapeutic). Investigational mGlu2 positive allosteric modulator, exact HZR chemistry in structural data and human clinical study; retain transmembrane source context. [Primary/deposit evidence](https://pubmed.ncbi.nlm.nih.gov/41175011/).
- Rule 32; explicit alias across source observations: **NAM563** (tool). Structural study and exact deposited CCD J9R identify this experimental modulator. No verified clinical drug identity in this pass. [Primary/deposit evidence](https://www.rcsb.org/structure/7EPE).
- Rule 34; 7EPF: **NAM597** (tool). Exact deposited chemical name matches CCD J9U. Preserve synthetic experimental-ligand identity; no clinical or endogenous inference. [Primary/deposit evidence](https://www.rcsb.org/structure/7EPF).
- Rule 35; 7MTS: **ZQY mGlu2 modulator** (tool). Exact deposited chemical name matches CCD ZQY. Preserve synthetic experimental-ligand identity; no clinical or endogenous inference. [Primary/deposit evidence](https://www.rcsb.org/structure/7MTS).
- Rule 37; explicit alias across source observations: **GRM7 heterodimer subunit** (receptor_partner). Receptor-partner group from deposited heterodimer. Constructs can contain stabilizing FKBP/FRB fusions and truncations; this is an assembly-role annotation, not proof of identical native full-length proteins. Preserve source PDB and compartment. [Primary/deposit evidence](https://www.rcsb.org/structure/7EPD).
- Rule 38; explicit alias across source observations: **GRM3 heterodimer subunit** (receptor_partner). Receptor-partner group from deposited heterodimer. Constructs can contain stabilizing FKBP/FRB fusions and truncations; this is an assembly-role annotation, not proof of identical native full-length proteins. Preserve source PDB and compartment. [Primary/deposit evidence](https://www.rcsb.org/structure/8JD3).
- Rule 39; explicit alias across source observations: **GRM4 heterodimer subunit** (receptor_partner). Receptor-partner group from deposited heterodimer. Constructs can contain stabilizing FKBP/FRB fusions and truncations; this is an assembly-role annotation, not proof of identical native full-length proteins. Preserve source PDB and compartment. [Primary/deposit evidence](https://www.rcsb.org/structure/8JD5).

### TNF — P01375

Named therapeutic binding domains retained with explicit arm provenance, not claims of intact PEGylated/multidomain drugs. Llama VHH1/2/3 remain distinct clones. 3L9J is an engineered tetranectin CTLD antagonist, not native CLEC3B. TNFR1 double variant separated from native-role group. Bare numeric IEDB identifiers and unverified species/scaffold chains remain unresolved.

- Rule 51; explicit alias across source observations: **Adalimumab** (therapeutic). Deposited Fab/Fv/VHH binding-domain evidence supports named therapeutic Adalimumab; cached exact VH/VL matches retained where supplied. This does not claim intact drug, PEGylation or multi-domain architecture was observed. [Primary/deposit evidence](https://www.rcsb.org/structure/3WD5).
- Rule 52; explicit alias across source observations: **Certolizumab** (therapeutic). Deposited Fab/Fv/VHH binding-domain evidence supports named therapeutic Certolizumab; cached exact VH/VL matches retained where supplied. This does not claim intact drug, PEGylation or multi-domain architecture was observed. [Primary/deposit evidence](https://www.rcsb.org/structure/5WUX).
- Rule 53; explicit alias across source observations: **Golimumab** (therapeutic). Deposited Fab/Fv/VHH binding-domain evidence supports named therapeutic Golimumab; cached exact VH/VL matches retained where supplied. This does not claim intact drug, PEGylation or multi-domain architecture was observed. [Primary/deposit evidence](https://www.rcsb.org/structure/5YOY).
- Rule 54; explicit alias across source observations: **Infliximab** (therapeutic). Deposited Fab/Fv/VHH binding-domain evidence supports named therapeutic Infliximab; cached exact VH/VL matches retained where supplied. This does not claim intact drug, PEGylation or multi-domain architecture was observed. [Primary/deposit evidence](https://www.rcsb.org/structure/4G3Y).
- Rule 55; explicit alias across source observations: **Ozoralizumab** (therapeutic). Deposited Fab/Fv/VHH binding-domain evidence supports named therapeutic Ozoralizumab; cached exact VH/VL matches retained where supplied. This does not claim intact drug, PEGylation or multi-domain architecture was observed. [Primary/deposit evidence](https://www.rcsb.org/structure/8Z8M).
- Rule 56; 5M2I: **Llama VHH1** (tool). Distinct experimental llama VHH clone. Merge explicit source spellings only within this deposit; do not merge the three clones or infer a clinical VHH identity. [Primary/deposit evidence](https://www.rcsb.org/structure/5M2I).
- Rule 57; 5M2J: **Llama VHH2** (tool). Distinct experimental llama VHH clone. Merge explicit source spellings only within this deposit; do not merge the three clones or infer a clinical VHH identity. [Primary/deposit evidence](https://www.rcsb.org/structure/5M2J).
- Rule 58; 5M2M: **Llama VHH3** (tool). Distinct experimental llama VHH clone. Merge explicit source spellings only within this deposit; do not merge the three clones or infer a clinical VHH identity. [Primary/deposit evidence](https://www.rcsb.org/structure/5M2M).
- Rule 59; 3L9J: **Engineered tetranectin CTLD TNF antagonist (3L9J)** (tool). Primary study explicitly describes randomized-loop C-type lectin scaffold selected against TNF. The P05452 mapping and misleading TNFalpha entity name do not establish native CLEC3B binding; absent mutation flag is not evidence of wild type. [Primary/deposit evidence](https://doi.org/10.1074/jbc.M109.063305).
- Rule 60; 8ZUI: **TNFRSF1A** (receptor_partner). Deposited TNFR1 ectodomain receptor complex; not an antibody or independently administered drug. [Primary/deposit evidence](https://www.rcsb.org/structure/8ZUI).
- Rule 61; 7KPB: **TNFRSF1A N54D/C182S construct (7KPB)** (receptor_partner). SEQADV maps N25D/C153S deposited positions to P19438 N54D/C182S. Retain engineered receptor construct rather than native sequence. [Primary/deposit evidence](https://files.rcsb.org/header/7KPB.pdb).
- Rule 62; 3ALQ: **TNFRSF1B** (receptor_partner). Deposited TNFR2 receptor ectodomain complex; preserve receptor construct and oligomer context. [Primary/deposit evidence](https://www.rcsb.org/structure/3ALQ).
- Rule 174; 9BN7: **VNARC4** (tool). COMPND identifies the sole V-NAR entity as VNARC4 (chainsD/E/F); this PDB-scoped anonymous source ID can be named without implying clinical identity. [Primary/deposit evidence](https://files.rcsb.org/header/9BN7.pdb).

### GRM3 — Q14832

Synthetic agonists/antagonists remain separate from glutamate. GRM2 E555A scoped to8JCV. FKBP1A fusion modules named only within deposited fusion structures, not endogenous free extracellular partners. Other intracellular G-protein/arrestin and uncertain construct accessions retained unresolved.

- Rule 27; explicit alias across source observations: **LY354740 (eglumegad)** (therapeutic). CCD40F and structural papers identify LY354740; clinical investigation supports therapeutic category, not approved status. Preserve identity separately from its prodrug LY544344. [Primary/deposit evidence](https://pubmed.ncbi.nlm.nih.gov/13129812/).
- Rule 28; explicit alias across source observations: **LY341495** (tool). Exact CCD Z99 and antagonist-bound structures identify the experimental group-II mGlu antagonist. Not endogenous glutamate. [Primary/deposit evidence](https://www.rcsb.org/structure/3SM9).
- Rule 29; explicit alias across source observations: **LY379268** (tool). Experimental synthetic agonist, distinct from LY354740 and glutamate; exact named source ligand retained. [Primary/deposit evidence](https://www.rcsb.org/structure/8TR2).
- Rule 33; explicit alias across source observations: **LY2794193** (tool). Structural study and exact deposited CCD CWY identify this experimental modulator. No verified clinical drug identity in this pass. [Primary/deposit evidence](https://www.rcsb.org/structure/7WIH).
- Rule 36; 8TR2: **LY379268** (tool). Exact deposited chemical name matches CCD JIX. Preserve synthetic experimental-ligand identity; no clinical or endogenous inference. [Primary/deposit evidence](https://www.rcsb.org/structure/8TR2).
- Rule 40; explicit alias across source observations: **GRM2 heterodimer subunit** (receptor_partner). Receptor-partner group from deposited heterodimer. Constructs can contain stabilizing FKBP/FRB fusions and truncations; this is an assembly-role annotation, not proof of identical native full-length proteins. Preserve source PDB and compartment. [Primary/deposit evidence](https://www.rcsb.org/structure/8JD3).
- Rule 41; 8JCV: **GRM2 E555A heterodimer construct (8JCV)** (receptor_partner). SEQADV explicitly records E555A; retain engineered construct separately from the broader heterodimer group. [Primary/deposit evidence](https://files.rcsb.org/header/8JCV.pdb).
- Rule 42; 8JCU: **FKBP1A fusion module** (tool). DBREF/COMPND map a stabilizing fusion module within the receptor construct. This is assay-construct evidence, not an endogenous free extracellular protein ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/8JCU).
- Rule 43; 8JCV: **FKBP1A fusion module** (tool). DBREF/COMPND map a stabilizing fusion module within the receptor construct. This is assay-construct evidence, not an endogenous free extracellular protein ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/8JCV).
- Rule 44; 8JCW: **FKBP1A fusion module** (tool). DBREF/COMPND map a stabilizing fusion module within the receptor construct. This is assay-construct evidence, not an endogenous free extracellular protein ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/8JCW).
- Rule 45; 8JCX: **FKBP1A fusion module** (tool). DBREF/COMPND map a stabilizing fusion module within the receptor construct. This is assay-construct evidence, not an endogenous free extracellular protein ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/8JCX).
- Rule 46; 8JCY: **FKBP1A fusion module** (tool). DBREF/COMPND map a stabilizing fusion module within the receptor construct. This is assay-construct evidence, not an endogenous free extracellular protein ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/8JCY).
- Rule 47; 8JCZ: **FKBP1A fusion module** (tool). DBREF/COMPND map a stabilizing fusion module within the receptor construct. This is assay-construct evidence, not an endogenous free extracellular protein ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/8JCZ).
- Rule 48; 8JD0: **FKBP1A fusion module** (tool). DBREF/COMPND map a stabilizing fusion module within the receptor construct. This is assay-construct evidence, not an endogenous free extracellular protein ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/8JD0).
- Rule 49; 8JD1: **FKBP1A fusion module** (tool). DBREF/COMPND map a stabilizing fusion module within the receptor construct. This is assay-construct evidence, not an endogenous free extracellular protein ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/8JD1).
- Rule 50; 8JD2: **FKBP1A fusion module** (tool). DBREF/COMPND map a stabilizing fusion module within the receptor construct. This is assay-construct evidence, not an endogenous free extracellular protein ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/8JD2).

### LRP6 — O75581

Capped short SOST and DKK1 peptides separated from larger domain constructs. FZD8-FKBP fusion scoped. DKK1/SOST domain names remain PDB-qualified until exact construct identity reconciled. Mouse WNT3A/CAHD1, Xenopus WNT8 sequence conflicts, generic scaffold/accession chains, anonymous8FFE and intracellular GSK3/AP2 evidence stay unresolved without native-human promotion.

- Rule 63; 3SOB: **YW210.09** (tool). Deposited experimental binder; explicit clone names reconcile IEDB/source labels without matching bare numeric identifiers. Distinct binders remain separate. [Primary/deposit evidence](https://www.rcsb.org/structure/3SOB).
- Rule 64; 6H15: **L-P2-B10** (tool). Deposited experimental binder; explicit clone names reconcile IEDB/source labels without matching bare numeric identifiers. Distinct binders remain separate. [Primary/deposit evidence](https://www.rcsb.org/structure/6H15).
- Rule 65; 6H16: **L-P2-D07** (tool). Deposited experimental binder; explicit clone names reconcile IEDB/source labels without matching bare numeric identifiers. Distinct binders remain separate. [Primary/deposit evidence](https://www.rcsb.org/structure/6H16).
- Rule 66; 3SOV: **Capped SOST-derived peptide S (3SOV)** (tool). COMPND and DBREF identify SOST residues115–121; SEQADV records terminal acetylation/amidation. Synthetic capped peptide, not full native sclerostin. Generic peptide alias is restricted to this PDB. [Primary/deposit evidence](https://files.rcsb.org/header/3SOV.pdb).
- Rule 67; 3SOQ: **Capped DKK1-derived peptide (3SOQ)** (tool). Deposited DKK1 residues38–44 with acetyl/amidated caps; separate this synthetic peptide from larger DKK1 domains. [Primary/deposit evidence](https://files.rcsb.org/header/3SOQ.pdb).
- Rule 68; 3S2K: **DKK1 domain construct (3S2K)** (unclassified). Deposited DKK1 fragment/domain, not the capped 3SOQ peptide. Keep PDB-qualified construct until exact boundaries/variants are reconciled; do not claim intact native ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/3S2K).
- Rule 69; 3S8V: **DKK1 domain construct (3S8V)** (unclassified). Deposited DKK1 fragment/domain, not the capped 3SOQ peptide. Keep PDB-qualified construct until exact boundaries/variants are reconciled; do not claim intact native ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/3S8V).
- Rule 70; 5FWW: **DKK1 domain construct (5FWW)** (unclassified). Deposited DKK1 fragment/domain, not the capped 3SOQ peptide. Keep PDB-qualified construct until exact boundaries/variants are reconciled; do not claim intact native ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/5FWW).
- Rule 71; 5GJE: **DKK1 domain construct (5GJE)** (unclassified). Deposited DKK1 fragment/domain, not the capped 3SOQ peptide. Keep PDB-qualified construct until exact boundaries/variants are reconciled; do not claim intact native ligand. [Primary/deposit evidence](https://www.rcsb.org/structure/5GJE).
- Rule 72; 6L6R: **Sclerostin domain construct (6L6R)** (unclassified). DBREF maps SOST24–177. Preserve domain construct rather than conflating with synthetic capped peptideS. [Primary/deposit evidence](https://files.rcsb.org/header/6L6R.pdb).
- Rule 73; 5FWW: **KREMEN1 receptor ectodomain** (receptor_partner). Human KREMEN1 residues30–322 in a DKK1/LRP6 ternary assembly. Receptor-partner role does not certify a binary interaction independent of the bridge. [Primary/deposit evidence](https://www.rcsb.org/structure/5FWW).
- Rule 74; 21KR: **FZD8–FKBP fusion construct (21KR)** (tool). FZD8 cysteine-rich domain is fused through linkers to FKBP module in the engineered assembly. Do not count as unmodified native FZD8; preserve PDB chain context. [Primary/deposit evidence](https://www.rcsb.org/structure/21KR).
- Rule 75; 21KS: **FZD8–FKBP fusion construct (21KS)** (tool). FZD8 cysteine-rich domain is fused through linkers to FKBP module in the engineered assembly. Do not count as unmodified native FZD8; preserve PDB chain context. [Primary/deposit evidence](https://www.rcsb.org/structure/21KS).

### BACE2 — Q9Y5Z0

Fab1 and Fab9 and Xaperone XA4813/XA4815 kept distinct. Explicit no-PDB clone labels reconciled, never bare numeric IDs. Anonymous7D5B Xaperone not equated with XA4813 because sequence lengths/constructs differ. Exact CCD inhibitors named as research tools; no clinical drug inference from activity alone.

- Rule 76; 3ZKM: **Fab 1/9** (tool). Primary structural paper identifies Fab1/9 in these BACE2 complexes. Generic BACE2-binding label is PDB-scoped; surface-mutant target context remains. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 77; 3ZKN: **Fab 1/9** (tool). Primary structural paper identifies Fab1/9 in these BACE2 complexes. Generic BACE2-binding label is PDB-scoped; surface-mutant target context remains. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 78; 3ZKQ: **XA4813** (tool). Named Xaperone crystallization binder confirmed in the structural series. Distinct XA4813/XA4815 remain separate; numerical IEDB IDs are not aliases. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 79; 3ZKS: **XA4813** (tool). Named Xaperone crystallization binder confirmed in the structural series. Distinct XA4813/XA4815 remain separate; numerical IEDB IDs are not aliases. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 80; 3ZKX: **XA4813** (tool). Named Xaperone crystallization binder confirmed in the structural series. Distinct XA4813/XA4815 remain separate; numerical IEDB IDs are not aliases. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 81; 3ZLQ: **XA4813** (tool). Named Xaperone crystallization binder confirmed in the structural series. Distinct XA4813/XA4815 remain separate; numerical IEDB IDs are not aliases. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 82; 4BEL: **XA4813** (tool). Named Xaperone crystallization binder confirmed in the structural series. Distinct XA4813/XA4815 remain separate; numerical IEDB IDs are not aliases. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 83; 4BFB: **XA4813** (tool). Named Xaperone crystallization binder confirmed in the structural series. Distinct XA4813/XA4815 remain separate; numerical IEDB IDs are not aliases. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 84; 6JSZ: **XA4813** (tool). Named Xaperone crystallization binder confirmed in the structural series. Distinct XA4813/XA4815 remain separate; numerical IEDB IDs are not aliases. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 85; 7F1G: **XA4813** (tool). Named Xaperone crystallization binder confirmed in the structural series. Distinct XA4813/XA4815 remain separate; numerical IEDB IDs are not aliases. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 86; 7N4N: **XA4813** (tool). Named Xaperone crystallization binder confirmed in the structural series. Distinct XA4813/XA4815 remain separate; numerical IEDB IDs are not aliases. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 87; 3ZKX: **XA4815** (tool). Named Xaperone crystallization binder confirmed in the structural series. Distinct XA4813/XA4815 remain separate; numerical IEDB IDs are not aliases. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 88; 6JSZ: **C7O BACE2 inhibitor** (tool). Exact deposited small-molecule inhibitor, separate from Xaperone/Fab construct. Clinical identity was not established; no invented drug promotion. [Primary/deposit evidence](https://www.rcsb.org/structure/6JSZ).
- Rule 89; 7D5B: **66F BACE2 inhibitor** (tool). Exact deposited small-molecule inhibitor, separate from Xaperone/Fab construct. Clinical identity was not established; no invented drug promotion. [Primary/deposit evidence](https://www.rcsb.org/structure/7D5B).
- Rule 90; 2EWY: **DBO BACE2 inhibitor** (tool). Exact deposited small-molecule inhibitor, separate from Xaperone/Fab construct. Clinical identity was not established; no invented drug promotion. [Primary/deposit evidence](https://www.rcsb.org/structure/2EWY).
- Rule 178; explicit alias across source observations: **XA4813** (tool). Explicit clone name from the primary Xaperone study also identifies no-PDB IEDB assays. PDB-specific rules retain deposited construct context; no numeric-source aliases are used. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).
- Rule 179; explicit alias across source observations: **XA4815** (tool). Explicit clone name from the primary Xaperone study also identifies no-PDB IEDB assays. PDB-specific rules retain deposited construct context; no numeric-source aliases are used. [Primary/deposit evidence](https://doi.org/10.1107/S0907444913006574).

### HLA-C — P10321

Counts are partner groups and depend on allele/peptide context. 6PAG RYRPGTVAL is a presented peptide, not full histone H3. KIR receptor partners retain PDB scope. Other peptide-origin accessions (including KRAS/importin) and generic TCR chains remain unresolved rather than full endogenous surface ligands. 1QQD B2M sequence discrepancy retained explicitly.

- Rule 91; 1IM9: **KIR2DL1** (receptor_partner). Deposited inhibitory receptor partner. Preserve HLA-C allele and presented peptide: counts represent partner groups, not allele-independent binding species. [Primary/deposit evidence](https://www.rcsb.org/structure/1IM9).
- Rule 92; 1EFX: **KIR2DL2** (receptor_partner). Deposited inhibitory receptor partner. Preserve HLA-C allele and presented peptide: counts represent partner groups, not allele-independent binding species. [Primary/deposit evidence](https://www.rcsb.org/structure/1EFX).
- Rule 93; 6PA1: **KIR2DL2** (receptor_partner). Deposited inhibitory receptor partner. Preserve HLA-C allele and presented peptide: counts represent partner groups, not allele-independent binding species. [Primary/deposit evidence](https://www.rcsb.org/structure/6PA1).
- Rule 94; 6PAG: **KIR2DL3** (receptor_partner). Deposited inhibitory receptor partner. Preserve HLA-C allele and presented peptide: counts represent partner groups, not allele-independent binding species. [Primary/deposit evidence](https://www.rcsb.org/structure/6PAG).
- Rule 95; 1EFX: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/1EFX).
- Rule 96; 1IM9: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/1IM9).
- Rule 97; 4NT6: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/4NT6).
- Rule 98; 5VGD: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/5VGD).
- Rule 99; 5VGE: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/5VGE).
- Rule 100; 5W67: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/5W67).
- Rule 101; 5W69: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/5W69).
- Rule 102; 5W6A: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/5W6A).
- Rule 103; 6JTO: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/6JTO).
- Rule 104; 6PA1: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/6PA1).
- Rule 105; 6PAG: **B2M** (receptor_partner). Structural class-I light-chain partner, not a presented peptide or additional antibody. Preserve HLA allele and peptide context. [Primary/deposit evidence](https://www.rcsb.org/structure/6PAG).
- Rule 106; 6PAG: **RYRPGTVAL presented peptide (HLA-C*07:02)** (unclassified). Deposited chainC is RYRPGTVAL. Scope generic peptide and mapped histone accession to this specific antigen presentation record; no intact histone or endogenous free-peptide claim. [Primary/deposit evidence](https://files.rcsb.org/header/6PAG.pdb).
- Rule 180; 1QQD: **B2M sequence-discrepancy construct (1QQD)** (unclassified). Legacy DBREF/SEQADV use discrepant reference numbering and report sequence conflicts. Keep raw B2M identity but do not assert native sequence or merge blindly with other deposits; exact reconciliation remains pending. [Primary/deposit evidence](https://files.rcsb.org/header/1QQD.pdb).

### ITGB1 — P05556

SG/19 and TS2/16 constructs distinguished. 7CEB is an engineered Fv-clasp, not automatically identical to every TS2/16 format. RGD tripeptide and FN7–10 fragment remain constructs. ITGA5 I492V separated. ITGAV8W30 and cytoplasmic ICAP1/talin remain unresolved; no blanket removal of intracellular contacts.

- Rule 107; 3VI3: **SG/19** (tool). Deposited experimental antibody fragment; retain fragment architecture. No clinical identity or equivalence to other activating/blocking clones inferred. [Primary/deposit evidence](https://www.rcsb.org/structure/3VI3).
- Rule 108; 3VI4: **SG/19** (tool). Deposited experimental antibody fragment; retain fragment architecture. No clinical identity or equivalence to other activating/blocking clones inferred. [Primary/deposit evidence](https://www.rcsb.org/structure/3VI4).
- Rule 109; 7NWL: **TS2/16 Fv-clasp** (tool). Deposited experimental antibody fragment; retain fragment architecture. No clinical identity or equivalence to other activating/blocking clones inferred. [Primary/deposit evidence](https://www.rcsb.org/structure/7NWL).
- Rule 110; 4WK0: **RGD tripeptide (4WK0)** (tool). COMPND specifies Arg-Gly-Asp experimental peptide. Do not imply intact fibronectin or an endogenous free tripeptide. [Primary/deposit evidence](https://files.rcsb.org/header/4WK0.pdb).
- Rule 111; 9P6S: **Fibronectin FN7–10 construct (9P6S)** (unclassified). Deposit studies FN7–10 fragment; DBREF resolves only the modeled mapped segment. Keep domain/fragment construct explicit, not full native fibronectin. [Primary/deposit evidence](https://www.rcsb.org/structure/9P6S).
- Rule 112; 3VI3: **ITGA5 receptor subunit** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/3VI3.pdb).
- Rule 113; 3VI4: **ITGA5 receptor subunit** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/3VI4.pdb).
- Rule 114; 4WJK: **ITGA5 I492V construct** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/4WJK.pdb).
- Rule 115; 4WK0: **ITGA5 I492V construct** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/4WK0.pdb).
- Rule 116; 4WK2: **ITGA5 I492V construct** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/4WK2.pdb).
- Rule 117; 4WK4: **ITGA5 receptor subunit** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/4WK4.pdb).
- Rule 118; 7NXD: **ITGA5 receptor subunit** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/7NXD.pdb).
- Rule 119; 9CKV: **ITGA5 receptor subunit** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/9CKV.pdb).
- Rule 120; 9DIA: **ITGA5 receptor subunit** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/9DIA.pdb).
- Rule 121; 9EF2: **ITGA5 receptor subunit** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/9EF2.pdb).
- Rule 122; 9P6S: **ITGA5 receptor subunit** (receptor_partner). Integrin heterodimer subunit. For4WJK/4WK0/4WK2 SEQADV maps deposited I451V to reference I492V; those constructs remain distinct. Other source truncation/assembly context retained. [Primary/deposit evidence](https://files.rcsb.org/header/9P6S.pdb).
- Rule 175; 7CEB: **Engineered TS2/16 Fv-clasp (7CEB)** (tool). COMPND specifies TS2/16 VH(S112C)-SARAH and VL-SARAH(S37C) chimeras. Retain construct distinction; mutation notation follows deposited domain names. [Primary/deposit evidence](https://files.rcsb.org/header/7CEB.pdb).

### ITGB6 — P18564

TGFB3 capped LAP peptide distinct from engineered latent TGFB1 proprotein5FFO. Primary5FFO study reports mature/proprotein C4S/R249A/N107Q/N147Q; deposited SEQADV uses precursor N136Q/N176Q. Do not interpret missing mutation flags as wild type. ITGAV construct names are PDB-scoped; remaining9CZ-series assembly details and viral polyprotein mappings stay raw. A1A6H called compound30, not assumed identical to lead MORF627.

- Rule 123; 4UM9: **Capped TGFB3-derived LAP peptide Ac-HGRGDLGRLKK-NH2 (4UM9)** (tool). Chemically capped isolated LAP peptide, not full native TGFB3 or mature growth factor; exact sequence (ACE)HGRGDLGRLKK(NH2) from deposited entity. Reciprocal to reviewed ITGAV contact. [Primary/deposit evidence](https://www.rcsb.org/structure/4UM9).
- Rule 124; 5FFO: **Engineered latent TGFB1 proprotein construct (5FFO)** (tool). Primary methods report C4S,R249A,N107Q,N147Q in mature/proprotein numbering, including disabled furin cleavage and glycosylation sites. SEQADV independently records N136Q/N176Q in P01137 precursor numbering. Deposited sequence/methods discrepancies remain; do not imply native or mature active TGFB1. [Primary/deposit evidence](https://pmc.ncbi.nlm.nih.gov/articles/PMC5586147/).
- Rule 125; 4UM8: **Engineered ITGAV subunit (4UM8)** (receptor_partner). Engineered integrin construct: SEQADV records substitutions/insertions/deletions in this deposit. Preserve PDB-qualified identity and original chain numbering rather than merging wild-type/variant molecules. [Primary/deposit evidence](https://files.rcsb.org/header/4UM8.pdb).
- Rule 126; 4UM9: **Engineered ITGAV subunit (4UM9)** (receptor_partner). Engineered integrin construct: SEQADV records substitutions/insertions/deletions in this deposit. Preserve PDB-qualified identity and original chain numbering rather than merging wild-type/variant molecules. [Primary/deposit evidence](https://files.rcsb.org/header/4UM9.pdb).
- Rule 127; 5FFG: **Engineered ITGAV subunit (5FFG)** (receptor_partner). Engineered integrin construct: SEQADV records substitutions/insertions/deletions in this deposit. Preserve PDB-qualified identity and original chain numbering rather than merging wild-type/variant molecules. [Primary/deposit evidence](https://files.rcsb.org/header/5FFG.pdb).
- Rule 128; 5FFO: **Engineered ITGAV subunit (5FFO)** (receptor_partner). Engineered integrin construct: SEQADV records substitutions/insertions/deletions in this deposit. Preserve PDB-qualified identity and original chain numbering rather than merging wild-type/variant molecules. [Primary/deposit evidence](https://files.rcsb.org/header/5FFO.pdb).
- Rule 129; 5NEM: **Engineered ITGAV subunit (5NEM)** (receptor_partner). Engineered integrin construct: SEQADV records substitutions/insertions/deletions in this deposit. Preserve PDB-qualified identity and original chain numbering rather than merging wild-type/variant molecules. [Primary/deposit evidence](https://files.rcsb.org/header/5NEM.pdb).
- Rule 130; 5NER: **Engineered ITGAV subunit (5NER)** (receptor_partner). Engineered integrin construct: SEQADV records substitutions/insertions/deletions in this deposit. Preserve PDB-qualified identity and original chain numbering rather than merging wild-type/variant molecules. [Primary/deposit evidence](https://files.rcsb.org/header/5NER.pdb).
- Rule 131; 5NET: **Engineered ITGAV subunit (5NET)** (receptor_partner). Engineered integrin construct: SEQADV records substitutions/insertions/deletions in this deposit. Preserve PDB-qualified identity and original chain numbering rather than merging wild-type/variant molecules. [Primary/deposit evidence](https://files.rcsb.org/header/5NET.pdb).
- Rule 132; 8TCG: **Engineered ITGAV subunit (8TCG)** (receptor_partner). Engineered integrin construct: SEQADV records substitutions/insertions/deletions in this deposit. Preserve PDB-qualified identity and original chain numbering rather than merging wild-type/variant molecules. [Primary/deposit evidence](https://files.rcsb.org/header/8TCG.pdb).
- Rule 133; 9XMM: **Engineered ITGAV subunit (9XMM)** (receptor_partner). Engineered integrin construct: SEQADV records substitutions/insertions/deletions in this deposit. Preserve PDB-qualified identity and original chain numbering rather than merging wild-type/variant molecules. [Primary/deposit evidence](https://files.rcsb.org/header/9XMM.pdb).
- Rule 134; 9CZD: **Compound 30 (A1A6H)** (tool). 9CZD and exact CCD A1A6H identify compound30 from the MORF-627 discovery study. The paper title does not establish compound30 is the development candidate; retain experimental tool status. [Primary/deposit evidence](https://www.rcsb.org/ligand/A1A6H).

### ITGB7 — P26010

Experimental ACT-1 remains separate from humanized vedolizumab. ITGA4 R591A scoped. ITGAE and MADCAM1 assembly partners retained. RO0505376 is a synthetic tool. No-PDB ACT-1 aliases and intracellular filamin retained for further provenance checks; no false therapeutic promotion.

- Rule 135; 3V4P: **ACT-1** (tool). Deposited ACT-1 antibody fragment. Do not equate murine parent automatically with humanized vedolizumab; matched-arm catalogue evidence would need explicit support. [Primary/deposit evidence](https://www.rcsb.org/structure/3V4P).
- Rule 136; 3V4V: **ACT-1** (tool). Deposited ACT-1 antibody fragment. Do not equate murine parent automatically with humanized vedolizumab; matched-arm catalogue evidence would need explicit support. [Primary/deposit evidence](https://www.rcsb.org/structure/3V4V).
- Rule 137; 3V4V: **RO0505376** (tool). Exact deposited synthetic integrin antagonist; preserve separately from the ACT-1 Fab. No verified clinical status in this pass. [Primary/deposit evidence](https://www.rcsb.org/structure/3V4V).
- Rule 138; 3V4P: **ITGA4 R591A construct** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/3V4P.pdb).
- Rule 139; 3V4V: **ITGA4 R591A construct** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/3V4V.pdb).
- Rule 140; 9P95: **ITGA4 receptor subunit** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/9P95.pdb).
- Rule 141; 9P96: **ITGA4 receptor subunit** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/9P96.pdb).
- Rule 142; 8ZJF: **ITGAE receptor subunit** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/8ZJF.pdb).
- Rule 143; 9P97: **ITGAE receptor subunit** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/9P97.pdb).
- Rule 144; 9P98: **ITGAE receptor subunit** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/9P98.pdb).
- Rule 145; 9P99: **ITGAE receptor subunit** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/9P99.pdb).
- Rule 149; 9P95: **MADCAM1 ectodomain** (endogenous_large). Human MADCAM1 ectodomain in integrin adhesion complex. Preserve glycosylation and receptor construct context; not an antibody. [Primary/deposit evidence](https://www.rcsb.org/structure/9P95).

### CDH1 — P12830

mAb-1_19A11 source duplicates reconciled. KLRG1 human C131S construct distinguished from mouse partner. CTNND1 deletion-construct cytoplasmic evidence retained. Listeria InlA and engineered microbial variants remain unclassified, not endogenous human. Small peptidomimetic4RL stays distinct from protein partners.

- Rule 148; 9P99: **ITGAE receptor subunit** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/9P99.pdb).
- Rule 150; explicit alias across source observations: **mAb-1_19A11** (tool). Named experimental mouse antibody in deposits6CXY/7STZ; retain clone identity without clinical promotion. [Primary/deposit evidence](https://www.rcsb.org/structure/6CXY).
- Rule 151; 4ZTE: **4RL E-cadherin peptidomimetic inhibitor** (tool). Exact deposited peptidomimetic, not an endogenous peptide; target is isolated E-cadherin residues3–213. [Primary/deposit evidence](https://www.rcsb.org/structure/4ZTE).
- Rule 152; 3FF7: **KLRG1 C131S construct** (receptor_partner). SEQADV explicitly records reference C131S in human KLRG1. Preserve engineered receptor construct rather than native sequence. [Primary/deposit evidence](https://files.rcsb.org/header/3FF7.pdb).
- Rule 153; 3L6X: **CTNND1 deletion construct (3L6X)** (unclassified). Intracellular E-cadherin-tail complex. SEQADV lists internal deletions; retain construct-specific p120-catenin annotation without native full-length claim. All-contact evidence remains. [Primary/deposit evidence](https://files.rcsb.org/header/3L6X.pdb).
- Rule 154; 3L6Y: **CTNND1 deletion construct (3L6Y)** (unclassified). Intracellular E-cadherin-tail complex. SEQADV lists internal deletions; retain construct-specific p120-catenin annotation without native full-length claim. All-contact evidence remains. [Primary/deposit evidence](https://files.rcsb.org/header/3L6Y.pdb).
- Rule 176; 6CXY: **mAb-1_19A11** (tool). The only antibody heavy/light entity pair in6CXY belongs to mAb-1_19A11 per primary structure; narrow source-ID reconciliation, not a global immunoglobulin alias. [Primary/deposit evidence](https://www.rcsb.org/structure/6CXY).

### NRP2 — O60462

VEGFA/VEGFC C-terminal peptides distinguished from complete VEGF proteins; acetylated6TJT peptide scoped. YW68.11.26 binder retained. Viral complexes and anonymous8IVX remain unresolved; no clinical antibody alias inferred from footprint.

- Rule 155; 2QQK: **YW68.11.26** (tool). Deposited experimental semaphorin-blocking Fab; clone-specific annotation, not clinical drug identity. [Primary/deposit evidence](https://www.rcsb.org/structure/2QQK).
- Rule 156; 2QQL: **YW68.11.26** (tool). Deposited experimental semaphorin-blocking Fab; clone-specific annotation, not clinical drug identity. [Primary/deposit evidence](https://www.rcsb.org/structure/2QQL).
- Rule 157; 5DN2: **VEGFA C-terminal peptide (5DN2)** (tool). Deposited VEGF-A165-HBD peptide maps P15692 residues205–232. Experimental fragment, not intact VEGFA. [Primary/deposit evidence](https://doi.org/10.1111/febs.13711).
- Rule 158; 6TJT: **Acetylated VEGFC C-terminal peptide (6TJT)** (tool). Primary study/deposit use an acetylated C-terminal peptide; COMPND states acetylated N-terminal Ser and two Ile residues lack modeled density. Restrict generic peptide alias to6TJT; not intact VEGFC. [Primary/deposit evidence](https://doi.org/10.3390/biom12030372).

### MADCAM1 — Q13477

Ontamalimab/PF-00547659/PF-547659 Fab identity supported by official trial nomenclature, deposited Fab names and cached exact VH/VL evidence. 10G3 distinct research Fab and target loop-deletion context retained. Integrin subunit contacts are receptor assembly partners, not additional drugs.

- Rule 146; 9P95: **ITGA4 receptor subunit** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/9P95.pdb).
- Rule 147; 9P95: **ITGB7 receptor subunit** (receptor_partner). Deposited integrin partner/subunit.3V4P/3V4V ITGA4 has explicit R558A deposited=R591A precursor mutation; preserve it separately. Other truncation/assembly context remains. [Primary/deposit evidence](https://files.rcsb.org/header/9P95.pdb).
- Rule 159; 4HCR: **Ontamalimab** (therapeutic). Official clinical trial identifies PF-00547659 as ontamalimab;4HCR Fab plus cached exact VH/VL evidence support the named therapeutic. No intact IgG claim. [Primary/deposit evidence](https://clinicaltrials.gov/study/NCT03283085).
- Rule 160; 4HC1: **10G3** (tool). Distinct experimental Fab; deposited target is a loop-deleted MADCAM1 construct. Do not merge with ontamalimab. [Primary/deposit evidence](https://www.rcsb.org/structure/4HC1).
- Rule 177; 4HCR: **Ontamalimab** (therapeutic). COMPND names both Fab entities PF-547659, and official clinical identity/cached exactVHVL match establish ontamalimab. Narrow anonymous-source reconciliation; no intact-drug claim. [Primary/deposit evidence](https://clinicaltrials.gov/study/NCT03283085).

### AGER — Q15109

Human S100 native partners separated from S100A6 C3S and mouse variants. Target is sometimes isolated RAGE peptide/domain, not intact cell-surface receptor. HMGB1 B-box and modified bovine albumin-derived peptide are fragments, not full proteins. No unrestricted species conflation.

- Rule 161; 4XYN: **S100B** (endogenous_large). Human S100B directly deposited; target is a RAGE-derived peptide, so this does not independently demonstrate intact surface-receptor accessibility. [Primary/deposit evidence](https://www.rcsb.org/structure/4XYN).
- Rule 162; 5D7F: **S100B** (endogenous_large). Human S100B directly deposited; target is a RAGE-derived peptide, so this does not independently demonstrate intact surface-receptor accessibility. [Primary/deposit evidence](https://www.rcsb.org/structure/5D7F).
- Rule 163; 2M1K: **S100A6 C3S construct** (tool). SEQADV explicitly records P06703 C3S, not native S100A6; isolated RAGE-domain context retained. [Primary/deposit evidence](https://files.rcsb.org/header/2M1K.pdb).
- Rule 164; 4YBH: **S100A6** (endogenous_large). Human S100A6 with human RAGE ectodomain; keep separate from C3S and mouse variants. [Primary/deposit evidence](https://www.rcsb.org/structure/4YBH).
- Rule 165; 8I9M: **HMGB1 B-box fragment (8I9M)** (unclassified). DBREF maps P09429 residues89–163, an isolated B-box fragment rather than intact HMGB1. Deposit primary citation is to-be-published; no unsupported full-protein claim. [Primary/deposit evidence](https://files.rcsb.org/header/8I9M.pdb).
- Rule 166; 2MJW: **S100P** (endogenous_large). Human calcium-binding protein/domain in the deposited RAGE-domain interaction study. Preserve isolated-domain and NMR context; no full-cell accessibility inference. [Primary/deposit evidence](https://www.rcsb.org/structure/2MJW).
- Rule 167; 2LE9: **S100A13** (endogenous_large). Human calcium-binding protein/domain in the deposited RAGE-domain interaction study. Preserve isolated-domain and NMR context; no full-cell accessibility inference. [Primary/deposit evidence](https://www.rcsb.org/structure/2LE9).
- Rule 168; 2L7U: **Modified bovine albumin-derived peptide (2L7U)** (tool). Bovine albumin-derived seven-residue peptide, not human albumin. AGE-recognition experiment; preserve modification/fragment context without inferring an endogenous-human full-protein ligand. [Primary/deposit evidence](https://doi.org/10.1016/j.str.2011.02.013).
- Rule 169; 4P2Y: **Mouse S100A6 (4P2Y)** (unclassified). Cross-species mouse partner, not endogenous human S100A6.9S2X SEQADV records Y84C; maintain mutant distinction. [Primary/deposit evidence](https://files.rcsb.org/header/4P2Y.pdb).
- Rule 170; 9S2X: **Mouse S100A6 Y84C (9S2X)** (unclassified). Cross-species mouse partner, not endogenous human S100A6.9S2X SEQADV records Y84C; maintain mutant distinction. [Primary/deposit evidence](https://files.rcsb.org/header/9S2X.pdb).

### GRM8 — O00222

L-AP4, (S)-3,4-DCPG and LY341495 mapped through exact CCD chemistry, all synthetic tools. Cytoplasmic G-protein/arrestin constructs retained raw; receptor activity does not imply clinical drug identity.

- Rule 171; explicit alias across source observations: **L-AP4** (tool). Exact CCD and primary structure identify the synthetic receptor ligand. Not endogenous glutamate; drug/agonist activity alone does not establish clinical therapeutic identity. [Primary/deposit evidence](https://www.rcsb.org/structure/6BT5).
- Rule 172; explicit alias across source observations: **(S)-3,4-DCPG** (tool). Exact CCD and primary structure identify the synthetic receptor ligand. Not endogenous glutamate; drug/agonist activity alone does not establish clinical therapeutic identity. [Primary/deposit evidence](https://www.rcsb.org/structure/6E5V).
- Rule 173; explicit alias across source observations: **LY341495** (tool). Exact CCD and primary structure identify the synthetic receptor ligand. Not endogenous glutamate; drug/agonist activity alone does not establish clinical therapeutic identity. [Primary/deposit evidence](https://www.rcsb.org/structure/9MBB).

## Matching and preservation

Unmatched rule indices: []. These indicate aliases without a current observation and must not be interpreted as new evidence. Every matched source record keeps its original source, partner, PDB, positions, context and observation ID. Broad accession rules denote receptor assembly-role groups only; known construct overrides win by PDB specificity. Separate constructs are never equated merely because their contact residues overlap. Two 7RNO rules exclude EC overview only, retaining all-scope evidence; no rule excludes all-scope observations.

## Raw group ledger

This appendix is a readable rendering of batch2-ledger.json. Each row has a one-to-one ledger counterpart containing full observation IDs and URLs.

### GABRA1

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| ABU | 6X3T | extracellular_explicit | 1 | corrected / 1 |
| B5Z8H1 | 9FAJ | extracellular_explicit | 1 | unresolved |
| B5Z8H1 | 9FGA | extracellular_explicit | 1 | unresolved |
| B5Z8H1 | 9FGB | extracellular_explicit | 1 | unresolved |
| B5Z8H1 | 9FGC | extracellular_explicit | 1 | unresolved |
| B5Z8H1 | 9FGD | extracellular_explicit | 1 | unresolved |
| P01391 | 7PC0 | extracellular_explicit | 1 | unresolved |
| P18507 / GABRG2 | 9CTV | extracellular_explicit | 1 | corrected / 8 |
| P18507 / GABRG2 | 9CX7 | extracellular_explicit | 1 | corrected / 8 |
| P18507 / GABRG2 | 9CXA | extracellular_explicit | 1 | corrected / 8 |
| P18507 / GABRG2 | 9CXC | extracellular_explicit | 1 | corrected / 8 |
| CCD:08H / 8-chloro-1-methyl-6-phenyl-4H-[1,2,4]triazolo[4,3-a][1,4]benzodiazepine | 6HUO | extracellular_explicit | 1 | corrected / 3 |
| CCD:FYP / ethyl 8-fluoro-5-methyl-6-oxo-5,6-dihydro-4H-imidazo[1,5-a][1,4]benzodiazepine-3-carboxylate | 6D6T | extracellular_explicit | 1 | corrected / 2 |
| CCD:FYP / ethyl 8-fluoro-5-methyl-6-oxo-5,6-dihydro-4H-imidazo[1,5-a][1,4]benzodiazepine-3-carboxylate | 6D6U | extracellular_explicit | 1 | corrected / 2 |
| CCD:FYP / ethyl 8-fluoro-5-methyl-6-oxo-5,6-dihydro-4H-imidazo[1,5-a][1,4]benzodiazepine-3-carboxylate | 6X3U | extracellular_explicit | 1 | corrected / 2 |
| CCD:H0Z / bicuculline methochloride | 6HUK | extracellular_explicit | 1 | corrected / 5 |
| sabdab2_H01W4L01GS / sabdab2_H01W4L01GS (FV) | 6X3T | extracellular_explicit | 1 | unresolved |
| E0SJQ4 | 6CDU | membrane_spanning_site | 1 | unresolved |
| E0SJQ4 | 6D1S | membrane_spanning_site | 1 | unresolved |
| P18505 / GABRB1 | 9CXB | membrane_spanning_site | 1 | corrected / 6 |
| P18505 / GABRB1 | 9CXD | membrane_spanning_site | 1 | corrected / 6 |
| P18507 / GABRG2 | 6D6T | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6D6U | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6HUJ | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6HUK | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6HUO | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6HUP | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6I53 | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6X3S | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6X3T | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6X3U | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6X3V | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6X3W | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6X3X | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6X3Z | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 6X40 | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 7QNE | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 7T0W | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 7T0Z | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 8DD2 | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 8DD3 | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 8SGO | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 8SI9 | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 8SID | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 8VQY | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 8VRN | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9CRS | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9CRV | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9DRX | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9EQG | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FAJ | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FAK | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FAM | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FAP | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FAQ | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FAS | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FAT | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FFV | membrane_spanning_site | 1 | corrected / 10 |
| P18507 / GABRG2 | 9FFW | membrane_spanning_site | 1 | corrected / 11 |
| P18507 / GABRG2 | 9FFX | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FFY | membrane_spanning_site | 1 | corrected / 12 |
| P18507 / GABRG2 | 9FFZ | membrane_spanning_site | 1 | corrected / 13 |
| P18507 / GABRG2 | 9FG0 | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FG1 | membrane_spanning_site | 1 | corrected / 14 |
| P18507 / GABRG2 | 9FG2 | membrane_spanning_site | 1 | corrected / 15 |
| P18507 / GABRG2 | 9FG3 | membrane_spanning_site | 1 | corrected / 16 |
| P18507 / GABRG2 | 9FG7 | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FG8 | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FG9 | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FGA | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FGB | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FGC | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FGD | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FGF | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FGG | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9FGH | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9RGD | membrane_spanning_site | 1 | corrected / 8 |
| P18507 / GABRG2 | 9RGE | membrane_spanning_site | 1 | corrected / 8 |
| P28472 / GABRB3 | 6HUJ | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 6HUK | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 6HUO | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 6HUP | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 6I53 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 7PBD | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 7PBZ | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 7PC0 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 7QNE | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 8PET | membrane_spanning_site | 1 | corrected / 17 |
| P28472 / GABRB3 | 9CSB | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9CTJ | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9CX7 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9CXA | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9CXC | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9EQG | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FAJ | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FAK | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FAM | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FAP | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FAQ | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FAS | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FAT | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFL | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFM | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFN | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFO | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFP | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFQ | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFR | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFS | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFT | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFU | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFV | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFW | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFX | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFY | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FFZ | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FG0 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FG1 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FG2 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FG3 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FG4 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FG5 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FG6 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FG7 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FG8 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FG9 | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FGA | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FGB | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FGC | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FGD | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FGF | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FGG | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9FGH | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9RGD | membrane_spanning_site | 1 | corrected / 9 |
| P28472 / GABRB3 | 9RGE | membrane_spanning_site | 1 | corrected / 9 |
| P47870 / GABRB2 | 6D6T | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 6D6U | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 6X3S | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 6X3T | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 6X3U | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 6X3V | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 6X3W | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 6X3X | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 6X3Z | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 6X40 | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 7T0W | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 7T0Z | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 8DD2 | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 8DD3 | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 8SGO | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 8SI9 | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 8SID | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 8VQY | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 8VRN | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9CRS | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9CRV | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9CSB | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9CT0 | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9CTJ | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9CTP | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9CTV | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9CXA | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9CXB | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9CXD | membrane_spanning_site | 1 | corrected / 7 |
| P47870 / GABRB2 | 9DRX | membrane_spanning_site | 1 | corrected / 7 |
| Q53FP2 | 9H9E | membrane_spanning_site | 1 | unresolved |
| CCD:DZP / 7-CHLORO-1-METHYL-5-PHENYL-1,3-DIHYDRO-2H-1,4-BENZODIAZEPIN-2-ONE | 6HUP | membrane_spanning_site | 1 | corrected / 4 |
| CCD:DZP / 7-CHLORO-1-METHYL-5-PHENYL-1,3-DIHYDRO-2H-1,4-BENZODIAZEPIN-2-ONE | 6X3X | membrane_spanning_site | 1 | corrected / 4 |

### MR1

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| 1VY | 4L4V | extracellular_explicit | 1 | corrected / 18 |
| A0A0C4DH27 | 7LLI | extracellular_explicit | 1 | unresolved |
| A0JD37 | 7LLI | extracellular_explicit | 1 | unresolved |
| P01732 / CD8A | 7UMG | extracellular_explicit | 1 | corrected / 20 |
| P01848 | 8Y6X | extracellular_explicit | 1 | unresolved |
| P01850 | 4L4T | extracellular_explicit | 1 | unresolved |
| P01850 | 4L4V | extracellular_explicit | 1 | unresolved |
| P01850 | 4LCW | extracellular_explicit | 1 | unresolved |
| P01850 | 4NQD | extracellular_explicit | 1 | unresolved |
| P01850 | 4NQE | extracellular_explicit | 1 | unresolved |
| P01888 | 7RNO | extracellular_explicit | 1 | corrected / 23 |
| P0DTU3 | 9HI7 | extracellular_explicit | 1 | unresolved |
| P0DTU4 | 8Y6X | extracellular_explicit | 1 | unresolved |
| P0DTU4 | 9HI7 | extracellular_explicit | 1 | unresolved |
| P61769 / B2M | 26SJ | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 26SK | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 26SL | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4GUP | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4L4T | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4L4V | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4LCW | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4NQD | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4NQE | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJ5 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJ7 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJ8 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJ9 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJA | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJB | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJC | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJD | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJE | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJF | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJG | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJH | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJI | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 4PJX | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 5D5M | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 5D7I | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 5D7J | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 5D7L | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 5U16 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 5U17 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 5U1R | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 5U2V | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 5U6Q | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 5U72 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6MWR | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUC | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUD | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUE | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUF | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUG | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUH | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUI | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUJ | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUK | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUL | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PUM | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PVC | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6PVD | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6W9U | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6W9V | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 6XQP | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7LLI | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7LLJ | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7UFJ | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7UMG | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7ZT2 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7ZT3 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7ZT4 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7ZT5 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7ZT7 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7ZT8 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 7ZT9 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 8Y6X | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9BTX | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9BTY | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9BTZ | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9BU0 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9BYS | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9C42 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9C9D | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9CGR | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9CGS | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9EK6 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9EK7 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9HI7 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9MS0 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9O05 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9O06 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9O07 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9O08 | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9Y0T | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9Y0U | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9Y0V | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9Y0W | extracellular_explicit | 1 | corrected / 19 |
| P61769 / B2M | 9Z4R | extracellular_explicit | 1 | corrected / 19 |
| Q6P4G7 | 4L4V | extracellular_explicit | 1 | unresolved |
| Q6P4G7 | 4LCW | extracellular_explicit | 1 | unresolved |
| Q6P4G7 | 4NQD | extracellular_explicit | 1 | unresolved |
| Q6P4G7 | 4NQE | extracellular_explicit | 1 | unresolved |
| Q6P4G7 | 9C42 | extracellular_explicit | 1 | unresolved |
| Q8N423 / LILRB2 | 9C9D | extracellular_explicit | 1 | corrected / 21 |
| Q9BX59 / TAPBPL | 7RNO | extracellular_explicit | 1 | corrected / 22 |

### GRM2

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| 40F | 4XAQ | extracellular_explicit | 1 | corrected / 24 |
| L-glutamic acid | 8JD1 | extracellular_explicit | 1 | corrected / 30 |
| L-glutamic acid | 8JD2 | extracellular_explicit | 1 | corrected / 30 |
| L-glutamic acid | 8JD4 | extracellular_explicit | 1 | corrected / 30 |
| LY341495 | 8JCU | extracellular_explicit | 1 | corrected / 25 |
| LY341495 | 8JCV | extracellular_explicit | 1 | corrected / 25 |
| LY341495 | 8JCW | extracellular_explicit | 1 | corrected / 25 |
| LY341495 | 8JCX | extracellular_explicit | 1 | corrected / 25 |
| LY341495 | 8JCY | extracellular_explicit | 1 | corrected / 25 |
| LY341495 | 8JCZ | extracellular_explicit | 1 | corrected / 25 |
| LY379268 | 8WGC | extracellular_explicit | 1 | corrected / 26 |
| eglumegad | 7E9G | extracellular_explicit | 1 | corrected / 24 |
| A0A8V8TRG9 | 8JCU | extracellular_explicit | 1 | unresolved |
| A0A8V8TRG9 | 8JCV | extracellular_explicit | 1 | unresolved |
| A0A8V8TRG9 | 8JCW | extracellular_explicit | 1 | unresolved |
| A0A8V8TRG9 | 8JCX | extracellular_explicit | 1 | unresolved |
| A0A8V8TRG9 | 8JCY | extracellular_explicit | 1 | unresolved |
| A0A8V8TRG9 | 8JD0 | extracellular_explicit | 1 | unresolved |
| A0A8V8TRG9 | 8JD1 | extracellular_explicit | 1 | unresolved |
| P42345 | 7EPD | extracellular_explicit | 1 | unresolved |
| Q14831 / GRM7 | 7EPD | extracellular_explicit | 1 | corrected / 37 |
| Q14832 / GRM3 | 8JCU | extracellular_explicit | 1 | corrected / 38 |
| Q14832 / GRM3 | 8JCV | extracellular_explicit | 1 | corrected / 38 |
| Q14832 / GRM3 | 8JCW | extracellular_explicit | 1 | corrected / 38 |
| Q14832 / GRM3 | 8JCX | extracellular_explicit | 1 | corrected / 38 |
| Q14832 / GRM3 | 8JCY | extracellular_explicit | 1 | corrected / 38 |
| Q14832 / GRM3 | 8JD0 | extracellular_explicit | 1 | corrected / 38 |
| Q14832 / GRM3 | 8JD1 | extracellular_explicit | 1 | corrected / 38 |
| Q14833 / GRM4 | 8WG9 | extracellular_explicit | 1 | corrected / 39 |
| CCD:40F / (1S,2S,5R,6S)-2-aminobicyclo[3.1.0]hexane-2,6-dicarboxylic acid | 4XAQ | extracellular_explicit | 1 | corrected / 24 |
| CCD:40F / (1S,2S,5R,6S)-2-aminobicyclo[3.1.0]hexane-2,6-dicarboxylic acid | 7E9G | extracellular_explicit | 1 | corrected / 24 |
| CCD:40F / (1S,2S,5R,6S)-2-aminobicyclo[3.1.0]hexane-2,6-dicarboxylic acid | 7EPB | extracellular_explicit | 1 | corrected / 24 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 7MTQ | extracellular_explicit | 1 | corrected / 25 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCU | extracellular_explicit | 1 | corrected / 25 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCV | extracellular_explicit | 1 | corrected / 25 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCW | extracellular_explicit | 1 | corrected / 25 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCX | extracellular_explicit | 1 | corrected / 25 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCY | extracellular_explicit | 1 | corrected / 25 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCZ | extracellular_explicit | 1 | corrected / 25 |
| sabdab2_H02M4L0000 / sabdab2_H02M4L0000 (SD-H) | 7EPB | extracellular_explicit | 1 | unresolved |
| (8~{R})-4-[2,4-Bis(fluoranyl)phenyl]-8-methyl-7-[(2-methylpyrazol-3-yl)methyl]-6,8-dihydro-5~{H}-1,7-naphthyridine-2-carboxamide | 7EPF | membrane_spanning_site | 1 | corrected / 34 |
| 2-methoxy-6-propyl-N-(2-{4-[(1H-tetrazol-5-yl)methoxy]phenyl}ethyl)thieno[2,3-d]pyrimidin-4-amine | 7MTS | membrane_spanning_site | 1 | corrected / 35 |
| CHEMBL3894759 | 7EPE | membrane_spanning_site | 1 | corrected / 32 |
| CHEMBL3894759 | 8JD0 | membrane_spanning_site | 1 | corrected / 32 |
| JNJ-40411813 | 8JD3 | membrane_spanning_site | 1 | corrected / 31 |
| JNJ-40411813 | 8JD5 | membrane_spanning_site | 1 | corrected / 31 |
| A0A8V8TRG9 | 8JCZ | membrane_spanning_site | 1 | unresolved |
| A0A8V8TRG9 | 8JD2 | membrane_spanning_site | 1 | unresolved |
| A0A8V8TRG9 | 8JD4 | membrane_spanning_site | 1 | unresolved |
| P63096 | 7E9G | non_extracellular:cytoplasmic | 1 | unresolved |
| P63096 | 7MTS | non_extracellular:cytoplasmic | 1 | unresolved |
| P63096 | 8JD3 | non_extracellular:cytoplasmic | 1 | unresolved |
| P63096 | 8JD5 | non_extracellular:cytoplasmic | 1 | unresolved |
| Q14832 / GRM3 | 8JCZ | membrane_spanning_site | 1 | corrected / 38 |
| Q14832 / GRM3 | 8JD2 | membrane_spanning_site | 1 | corrected / 38 |
| Q14832 / GRM3 | 8JD3 | membrane_spanning_site | 1 | corrected / 38 |
| Q14833 / GRM4 | 8JD4 | membrane_spanning_site | 1 | corrected / 39 |
| Q14833 / GRM4 | 8JD5 | membrane_spanning_site | 1 | corrected / 39 |
| Q14833 / GRM4 | 8WGB | membrane_spanning_site | 1 | corrected / 39 |

### TNF

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| 1 VHH | 5M2I | extracellular_explicit | 2 | corrected / 56 |
| 2 VHH | 5M2J | extracellular_explicit | 1 | corrected / 57 |
| 3 VHH | 5M2M | extracellular_explicit | 5 | corrected / 58 |
| Adalimumab Fab | 3WD5 | extracellular_explicit | 1 | confirmed / 51 |
| Certolizumab Fab | 5WUX | extracellular_explicit | 3 | confirmed / 52 |
| Golimumab  Fv | 5YOY | extracellular_explicit | 2 | confirmed / 53 |
| Infliximab Fab | 4G3Y | extracellular_explicit | 1 | confirmed / 54 |
| 307 | 2AZ5 | extracellular_explicit | 1 | unresolved |
| 18520 / golimumab | 5YOY | extracellular_explicit | 1 | corrected / 53 |
| 18568 / VHH#3 | 5M2M | extracellular_explicit | 1 | corrected / 58 |
| 223318 / VHH#2 | 5M2J | extracellular_explicit | 1 | corrected / 57 |
| 481 / Infliximab | none | extracellular_explicit | 3 | confirmed / 54 |
| 481 / Infliximab | 4G3Y | extracellular_explicit | 1 | confirmed / 54 |
| 644 / Adalimumab | none | extracellular_explicit | 3 | confirmed / 51 |
| 644 / Adalimumab | 3WD5 | extracellular_explicit | 1 | confirmed / 51 |
| P05452 / CLEC3B | 3L9J | extracellular_explicit | 1 | corrected / 59 |
| P19438 / TNFRSF1A | 7KPB | extracellular_explicit | 1 | corrected / 61 |
| P19438 / TNFRSF1A | 8ZUI | extracellular_explicit | 1 | corrected / 60 |
| P20333 / TNFRSF1B | 3ALQ | extracellular_explicit | 1 | corrected / 62 |
| Q8JGJ1 | 9DJW | extracellular_explicit | 1 | unresolved |
| Q9DHW0 | 3IT8 | extracellular_explicit | 1 | unresolved |
| sabdab2_H05SFL0000 / sabdab2_H05SFL0000 (VNAR) | 9BN7 | extracellular_explicit | 1 | corrected / 174 |
| Certolizumab | 5WUX | extracellular_explicit | 3 | confirmed / 52 |
| Golimumab | 5YOY | extracellular_explicit | 2 | confirmed / 53 |
| Infliximab | 4G3Y | extracellular_explicit | 1 | confirmed / 54 |
| Ozoralizumab | 8Z8M | extracellular_explicit | 10 | confirmed / 55 |
| Q8IXJ6 | 4Y6O | non_extracellular:cytoplasmic | 1 | unresolved |

### GRM3

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| 40F | 4XAR | extracellular_explicit | 1 | corrected / 27 |
| (1S,4R,5R,6S)-4-amino-2-oxabicyclo[3.1.0]hexane-4,6-dicarboxylic acid | 8TR2 | extracellular_explicit | 1 | corrected / 36 |
| CHEMBL4081453 | 7WIH | extracellular_explicit | 1 | corrected / 33 |
| LY341495 | 7WI6 | extracellular_explicit | 1 | corrected / 28 |
| LY341495 | 7WI8 | extracellular_explicit | 1 | corrected / 28 |
| LY341495 | 8TR0 | extracellular_explicit | 1 | corrected / 28 |
| LY341495 | 8TRC | extracellular_explicit | 1 | corrected / 28 |
| LY341495 | 8TRD | extracellular_explicit | 1 | corrected / 28 |
| LY379268 | 8TQB | extracellular_explicit | 1 | corrected / 29 |
| P62942 | 8JCU | extracellular_explicit | 1 | corrected / 42 |
| P62942 | 8JCV | extracellular_explicit | 1 | corrected / 43 |
| P62942 | 8JCW | extracellular_explicit | 1 | corrected / 44 |
| P62942 | 8JCX | extracellular_explicit | 1 | corrected / 45 |
| P62942 | 8JCY | extracellular_explicit | 1 | corrected / 46 |
| P62942 | 8JD0 | extracellular_explicit | 1 | corrected / 48 |
| P62942 | 8JD1 | extracellular_explicit | 1 | corrected / 49 |
| Q14416 / GRM2 | 8JCU | extracellular_explicit | 1 | corrected / 40 |
| Q14416 / GRM2 | 8JCV | extracellular_explicit | 1 | corrected / 41 |
| Q14416 / GRM2 | 8JCW | extracellular_explicit | 1 | corrected / 40 |
| Q14416 / GRM2 | 8JCX | extracellular_explicit | 1 | corrected / 40 |
| Q14416 / GRM2 | 8JCY | extracellular_explicit | 1 | corrected / 40 |
| Q14416 / GRM2 | 8JD0 | extracellular_explicit | 1 | corrected / 40 |
| Q14416 / GRM2 | 8JD1 | extracellular_explicit | 1 | corrected / 40 |
| CCD:40F / (1S,2S,5R,6S)-2-aminobicyclo[3.1.0]hexane-2,6-dicarboxylic acid | 4XAR | extracellular_explicit | 1 | corrected / 27 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 3SM9 | extracellular_explicit | 1 | corrected / 28 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 7WI6 | extracellular_explicit | 1 | corrected / 28 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 7WI8 | extracellular_explicit | 1 | corrected / 28 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCU | extracellular_explicit | 1 | corrected / 28 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCV | extracellular_explicit | 1 | corrected / 28 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCW | extracellular_explicit | 1 | corrected / 28 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCX | extracellular_explicit | 1 | corrected / 28 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCY | extracellular_explicit | 1 | corrected / 28 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 8JCZ | extracellular_explicit | 1 | corrected / 28 |
| P49407 | 9II2 | non_extracellular:cytoplasmic | 1 | unresolved |
| P49407 | 9II3 | non_extracellular:cytoplasmic | 1 | unresolved |
| P62942 | 8JCZ | membrane_spanning_site | 1 | corrected / 47 |
| P62942 | 8JD2 | membrane_spanning_site | 1 | corrected / 50 |
| Q14416 / GRM2 | 8JCZ | membrane_spanning_site | 1 | corrected / 40 |
| Q14416 / GRM2 | 8JD2 | membrane_spanning_site | 1 | corrected / 40 |
| Q14416 / GRM2 | 8JD3 | membrane_spanning_site | 1 | corrected / 40 |

### LRP6

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| L-P2-B10 VHH | 6H15 | extracellular_explicit | 2 | corrected / 64 |
| L-P2-D07 VHH | 6H16 | extracellular_explicit | 1 | corrected / 65 |
| YW210.09 Fab | 3SOB | extracellular_explicit | 1 | corrected / 63 |
| peptide | 3SOV | extracellular_explicit | 1 | corrected / 66 |
| 1155 / YW210.09 | 3SOB | extracellular_explicit | 1 | corrected / 63 |
| 197720 / L-P2-B10 | 6H15 | extracellular_explicit | 1 | corrected / 64 |
| 197721 / L-P2-D07 | 6H16 | extracellular_explicit | 1 | corrected / 65 |
| O94907 | 3S2K | extracellular_explicit | 1 | corrected / 68 |
| O94907 | 3S8V | extracellular_explicit | 1 | corrected / 69 |
| O94907 | 3SOQ | extracellular_explicit | 1 | corrected / 67 |
| O94907 | 5FWW | extracellular_explicit | 1 | corrected / 70 |
| O94907 | 5GJE | extracellular_explicit | 1 | corrected / 71 |
| P27467 | 21KR | extracellular_explicit | 1 | unresolved |
| P27467 | 21KS | extracellular_explicit | 1 | unresolved |
| P27467 | 21KT | extracellular_explicit | 1 | unresolved |
| P28026 | 8CTG | extracellular_explicit | 1 | unresolved |
| P62942 | 21KR | extracellular_explicit | 1 | unresolved |
| P62942 | 21KS | extracellular_explicit | 1 | unresolved |
| Q6PDJ1 | 8S7C | extracellular_explicit | 1 | unresolved |
| Q96MU8 / KREMEN1 | 5FWW | extracellular_explicit | 1 | corrected / 73 |
| Q9BQB4 | 3SOV | extracellular_explicit | 1 | corrected / 66 |
| Q9BQB4 | 6L6R | extracellular_explicit | 1 | corrected / 72 |
| Q9H461 / FZD8 | 21KR | extracellular_explicit | 1 | corrected / 74 |
| Q9H461 / FZD8 | 21KS | extracellular_explicit | 1 | corrected / 75 |
| sabdab2_H00S8L00A9 / sabdab2_H00S8L00A9 (FAB) | 8FFE | extracellular_explicit | 1 | unresolved |
| P49841 | 4NM5 | non_extracellular:cytoplasmic | 1 | unresolved |
| P49841 | 4NM7 | non_extracellular:cytoplasmic | 1 | unresolved |
| P84092 | 9FIW | non_extracellular:cytoplasmic | 1 | unresolved |
| P84092 | 9FIX | non_extracellular:cytoplasmic | 1 | unresolved |
| P84092 | 9FIY | non_extracellular:cytoplasmic | 1 | unresolved |

### BACE2

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| BACE2-binding Fab | 3ZKM | extracellular_explicit | 1 | corrected / 76 |
| BACE2-binding Fab | 3ZKN | extracellular_explicit | 2 | corrected / 77 |
| C7O | 6JSZ | extracellular_explicit | 1 | corrected / 88 |
| 1138 / 1/9 | 3ZKM | extracellular_explicit | 1 | corrected / 76 |
| 1138 / 1/9 | 3ZKN | extracellular_explicit | 1 | corrected / 77 |
| 2063 / XA4813 | 3ZKQ | extracellular_explicit | 1 | corrected / 78 |
| 2063 / XA4813 | 3ZKS | extracellular_explicit | 1 | corrected / 79 |
| 2063 / XA4813 | 3ZKX | extracellular_explicit | 1 | corrected / 80 |
| 2063 / XA4813 | 3ZLQ | extracellular_explicit | 1 | corrected / 81 |
| 2063 / XA4813 | 4BEL | extracellular_explicit | 1 | corrected / 82 |
| 2063 / XA4813 | 4BFB | extracellular_explicit | 1 | corrected / 83 |
| 2063 / Xaperone XA4813 | 6JSZ | extracellular_explicit | 1 | corrected / 84 |
| 2063 / XA4813 | 7F1G | extracellular_explicit | 1 | corrected / 85 |
| 2063 / XA4813 | 7N4N | extracellular_explicit | 1 | corrected / 86 |
| 2064 / XA4815 | 3ZKX | extracellular_explicit | 1 | corrected / 87 |
| 446 / XA4813 | none | extracellular_explicit | 4 | corrected / 178 |
| 447 / XA4815 | none | extracellular_explicit | 4 | corrected / 179 |
| CCD:66F / N-{3-[(5R)-3-amino-2,5-dimethyl-1,1-dioxido-5,6-dihydro-2H-1,2,4-thiadiazin-5-yl]-4-fluorophenyl}-5-fluoropyridine-2-carboxamide | 7D5B | extracellular_explicit | 1 | corrected / 89 |
| CCD:DBO / N-{(1S,2R)-1-BENZYL-2-HYDROXY-3-[(3-METHYLBENZYL)AMINO]PROPYL}DIBENZO[B,F]OXEPINE-10-CARBOXAMIDE | 2EWY | extracellular_explicit | 1 | corrected / 90 |
| sabdab2_H00QEL0000 / sabdab2_H00QEL0000 (SD-H) | 7D5B | extracellular_explicit | 1 | unresolved |

### HLA-C

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| peptide | 6PAG | extracellular_explicit | 1 | corrected / 106 |
| D9J353 | 4NT6 | extracellular_explicit | 1 | unresolved |
| P01116 | 6JTO | extracellular_explicit | 1 | unresolved |
| P43626 / KIR2DL1 | 1IM9 | extracellular_explicit | 1 | corrected / 91 |
| P43627 / KIR2DL2 | 1EFX | extracellular_explicit | 1 | corrected / 92 |
| P43627 / KIR2DL2 | 6PA1 | extracellular_explicit | 1 | corrected / 93 |
| P43628 / KIR2DL3 | 6PAG | extracellular_explicit | 1 | corrected / 94 |
| P52292 | 1EFX | extracellular_explicit | 1 | unresolved |
| P61769 / B2M | 1EFX | extracellular_explicit | 1 | corrected / 95 |
| P61769 / B2M | 1IM9 | extracellular_explicit | 1 | corrected / 96 |
| P61769 / B2M | 1QQD | extracellular_explicit | 1 | corrected / 180 |
| P61769 / B2M | 4NT6 | extracellular_explicit | 1 | corrected / 97 |
| P61769 / B2M | 5VGD | extracellular_explicit | 1 | corrected / 98 |
| P61769 / B2M | 5VGE | extracellular_explicit | 1 | corrected / 99 |
| P61769 / B2M | 5W67 | extracellular_explicit | 1 | corrected / 100 |
| P61769 / B2M | 5W69 | extracellular_explicit | 1 | corrected / 101 |
| P61769 / B2M | 5W6A | extracellular_explicit | 1 | corrected / 102 |
| P61769 / B2M | 6JTO | extracellular_explicit | 1 | corrected / 103 |
| P61769 / B2M | 6PA1 | extracellular_explicit | 1 | corrected / 104 |
| P61769 / B2M | 6PAG | extracellular_explicit | 1 | corrected / 105 |
| P68431 | 5VGE | extracellular_explicit | 1 | unresolved |
| P68431 | 6PA1 | extracellular_explicit | 1 | unresolved |
| P68431 | 6PAG | extracellular_explicit | 1 | corrected / 106 |
| Q13761 | 5W69 | extracellular_explicit | 1 | unresolved |
| Q9NY61 | 5W6A | extracellular_explicit | 1 | unresolved |

### ITGB1

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| SG/19 Fab | 3VI3 | extracellular_explicit | 2 | corrected / 107 |
| SG/19 Fab | 3VI4 | extracellular_explicit | 1 | corrected / 108 |
| TS2/16 Fv | 7NWL | extracellular_explicit | 1 | corrected / 109 |
| peptide | 4WK0 | extracellular_explicit | 1 | corrected / 110 |
| 362 / SG/19 | 3VI3 | extracellular_explicit | 1 | corrected / 107 |
| 362 / SG/19 | 3VI4 | extracellular_explicit | 1 | corrected / 108 |
| P02751 / FN1 | 9P6S | extracellular_explicit | 1 | corrected / 111 |
| P06756 / ITGAV | 8W30 | extracellular_explicit | 1 | unresolved |
| P08648 / ITGA5 | 3VI3 | extracellular_explicit | 1 | corrected / 112 |
| P08648 / ITGA5 | 3VI4 | extracellular_explicit | 1 | corrected / 113 |
| P08648 / ITGA5 | 4WJK | extracellular_explicit | 1 | corrected / 114 |
| P08648 / ITGA5 | 4WK0 | extracellular_explicit | 1 | corrected / 115 |
| P08648 / ITGA5 | 4WK2 | extracellular_explicit | 1 | corrected / 116 |
| P08648 / ITGA5 | 4WK4 | extracellular_explicit | 1 | corrected / 117 |
| P08648 / ITGA5 | 7NXD | extracellular_explicit | 1 | corrected / 118 |
| P08648 / ITGA5 | 9CKV | extracellular_explicit | 1 | corrected / 119 |
| P08648 / ITGA5 | 9DIA | extracellular_explicit | 1 | corrected / 120 |
| P08648 / ITGA5 | 9EF2 | extracellular_explicit | 1 | corrected / 121 |
| P08648 / ITGA5 | 9P6S | extracellular_explicit | 1 | corrected / 122 |
| sabdab2_H01MGL01B6 / sabdab2_H01MGL01B6 (FV) | 7CEB | extracellular_explicit | 1 | corrected / 175 |
| O14713 | 4DX9 | non_extracellular:cytoplasmic | 1 | unresolved |
| Q71LX4 | 3G9W | non_extracellular:cytoplasmic | 1 | unresolved |

### ITGB6

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| A1A6H | 9CZD | extracellular_explicit | 1 | corrected / 134 |
| P01137 / TGFB1 | 5FFO | extracellular_explicit | 1 | corrected / 124 |
| P06756 / ITGAV | 4UM8 | extracellular_explicit | 1 | corrected / 125 |
| P06756 / ITGAV | 4UM9 | extracellular_explicit | 1 | corrected / 126 |
| P06756 / ITGAV | 5FFG | extracellular_explicit | 1 | corrected / 127 |
| P06756 / ITGAV | 5FFO | extracellular_explicit | 1 | corrected / 128 |
| P06756 / ITGAV | 5NEM | extracellular_explicit | 1 | corrected / 129 |
| P06756 / ITGAV | 5NER | extracellular_explicit | 1 | corrected / 130 |
| P06756 / ITGAV | 5NET | extracellular_explicit | 1 | corrected / 131 |
| P06756 / ITGAV | 8TCG | extracellular_explicit | 1 | corrected / 132 |
| P06756 / ITGAV | 9CZ7 | extracellular_explicit | 1 | unresolved |
| P06756 / ITGAV | 9CZA | extracellular_explicit | 1 | unresolved |
| P06756 / ITGAV | 9CZD | extracellular_explicit | 1 | unresolved |
| P06756 / ITGAV | 9CZF | extracellular_explicit | 1 | unresolved |
| P06756 / ITGAV | 9XMM | extracellular_explicit | 1 | corrected / 133 |
| P10600 / TGFβ3 (TGFB3) | 4UM9 | extracellular_explicit | 1 | corrected / 123 |
| Q6PMW3 | 5NET | extracellular_explicit | 1 | unresolved |
| Q98W00 | 5NEM | extracellular_explicit | 1 | unresolved |
| Q98W00 | 5NER | extracellular_explicit | 1 | unresolved |

### ITGB7

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| ACT-1 Fab | 3V4P | extracellular_explicit | 1 | corrected / 135 |
| Act-1 Fab | 3V4V | extracellular_explicit | 1 | corrected / 136 |
| 0DU | 3V4V | extracellular_explicit | 1 | corrected / 137 |
| 356 / Act-1 | none | extracellular_explicit | 1 | unresolved |
| 356 / Act-1 | 3V4P | extracellular_explicit | 1 | corrected / 135 |
| 356 / Act-1 | 3V4V | extracellular_explicit | 1 | corrected / 136 |
| P13612 / ITGA4 | 3V4P | extracellular_explicit | 1 | corrected / 138 |
| P13612 / ITGA4 | 3V4V | extracellular_explicit | 1 | corrected / 139 |
| P13612 / ITGA4 | 9P95 | extracellular_explicit | 1 | corrected / 140 |
| P13612 / ITGA4 | 9P96 | extracellular_explicit | 1 | corrected / 141 |
| P38570 / ITGAE | 8ZJF | extracellular_explicit | 1 | corrected / 142 |
| P38570 / ITGAE | 9P97 | extracellular_explicit | 1 | corrected / 143 |
| P38570 / ITGAE | 9P98 | extracellular_explicit | 1 | corrected / 144 |
| P38570 / ITGAE | 9P99 | extracellular_explicit | 1 | corrected / 145 |
| Q13477 / MADCAM1 | 9P95 | extracellular_explicit | 1 | corrected / 149 |
| sabdab2_H00QTL00N0 / sabdab2_H00QTL00N0 (FAB) | 3V4V | extracellular_explicit | 1 | unresolved |
| P21333 | 2BRQ | non_extracellular:cytoplasmic | 1 | unresolved |

### CDH1

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| mAb-1_19A11 Fab | 6CXY | extracellular_explicit | 1 | corrected / 150 |
| mAb-1_19A11 Fab | 7STZ | extracellular_explicit | 1 | corrected / 150 |
| 4RL | 4ZTE | extracellular_explicit | 1 | corrected / 151 |
| A4GWL5 | 2OMX | extracellular_explicit | 1 | unresolved |
| A4GWM6 | 2OMT | extracellular_explicit | 1 | unresolved |
| O88713 | 3FF8 | extracellular_explicit | 1 | unresolved |
| P0DJM0 | 1O6S | extracellular_explicit | 1 | unresolved |
| P0DJM0 | 2OMU | extracellular_explicit | 1 | unresolved |
| P0DJM0 | 2OMV | extracellular_explicit | 1 | unresolved |
| P0DJM0 | 2OMY | extracellular_explicit | 1 | unresolved |
| P0DJM0 | 2OMZ | extracellular_explicit | 1 | unresolved |
| P0DJM0 | 8H62 | extracellular_explicit | 1 | unresolved |
| P38570 / ITGAE | 9P99 | extracellular_explicit | 1 | corrected / 148 |
| Q96E93 / KLRG1 | 3FF7 | extracellular_explicit | 1 | corrected / 152 |
| sabdab2_H01VBL01G5 / sabdab2_H01VBL01G5 (FAB) | 6CXY | extracellular_explicit | 1 | corrected / 176 |
| O60716 / CTNND1 | 3L6X | non_extracellular:cytoplasmic | 1 | corrected / 153 |
| O60716 / CTNND1 | 3L6Y | non_extracellular:cytoplasmic | 1 | corrected / 154 |

### NRP2

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| YW68.11.26 Fab | 2QQK | extracellular_explicit | 1 | corrected / 155 |
| YW68.11.26 Fab | 2QQL | extracellular_explicit | 1 | corrected / 156 |
| peptide | 6TJT | extracellular_explicit | 1 | corrected / 158 |
| C5ILC1 | 6GH8 | extracellular_explicit | 1 | unresolved |
| F5HCP3 | 7T4S | extracellular_explicit | 1 | unresolved |
| F5HET4 | 7M22 | extracellular_explicit | 1 | unresolved |
| F5HET4 | 7T4S | extracellular_explicit | 1 | unresolved |
| P15692 / VEGFA | 5DN2 | extracellular_explicit | 1 | corrected / 157 |
| P16772 | 7M22 | extracellular_explicit | 1 | unresolved |
| P16837 | 7M22 | extracellular_explicit | 1 | unresolved |
| P49767 / VEGFC | 6TJT | extracellular_explicit | 1 | corrected / 158 |
| V9LLX6 | 7T4S | extracellular_explicit | 1 | unresolved |
| sabdab2_H04AYL03BJ / sabdab2_H04AYL03BJ (FAB) | 8IVX | extracellular_explicit | 1 | unresolved |

### MADCAM1

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| 10G3 Fab | 4HC1 | extracellular_explicit | 2 | corrected / 160 |
| PF-547659 Fab | 4HCR | extracellular_explicit | 2 | corrected / 159 |
| 18347 / 10G3 | 4HC1 | extracellular_explicit | 1 | corrected / 160 |
| 18348 / PF-00547659 | 4HCR | extracellular_explicit | 1 | corrected / 159 |
| P13612 / ITGA4 | 9P95 | extracellular_explicit | 1 | corrected / 146 |
| P26010 / ITGB7 | 9P95 | extracellular_explicit | 1 | corrected / 147 |
| sabdab2_H00YEL00TG / sabdab2_H00YEL00TG (FAB) | 4HCR | extracellular_explicit | 1 | corrected / 177 |
| Ontamalimab | 4HCR | extracellular_explicit | 2 | confirmed / 159 |

### AGER

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| P02769 | 2L7U | extracellular_explicit | 1 | corrected / 168 |
| P04271 / S100B | 4XYN | extracellular_explicit | 1 | corrected / 161 |
| P04271 / S100B | 5D7F | extracellular_explicit | 1 | corrected / 162 |
| P06703 / S100A6 | 2M1K | extracellular_explicit | 1 | corrected / 163 |
| P06703 / S100A6 | 4YBH | extracellular_explicit | 1 | corrected / 164 |
| P09429 / HMGB1 | 8I9M | extracellular_explicit | 1 | corrected / 165 |
| P14069 | 4P2Y | extracellular_explicit | 1 | corrected / 169 |
| P14069 | 9S2X | extracellular_explicit | 1 | corrected / 170 |
| P25815 / S100P | 2MJW | extracellular_explicit | 1 | corrected / 166 |
| Q99584 / S100A13 | 2LE9 | extracellular_explicit | 1 | corrected / 167 |

### GRM8

| Raw partner / label | PDB | Context | Observations | Disposition / rule |
|---|---|---|---:|---|
| E7P | 6BT5 | extracellular_explicit | 1 | corrected / 171 |
| CCD:E7P / (2S)-2-amino-4-phosphonobutanoic acid | 6BT5 | extracellular_explicit | 1 | corrected / 171 |
| CCD:E7P / (2S)-2-amino-4-phosphonobutanoic acid | 9N8Y | extracellular_explicit | 1 | corrected / 171 |
| CCD:E7P / (2S)-2-amino-4-phosphonobutanoic acid | 9N8Z | extracellular_explicit | 1 | corrected / 171 |
| CCD:HVG / 4-[(S)-amino(carboxy)methyl]benzene-1,2-dicarboxylic acid | 6E5V | extracellular_explicit | 1 | corrected / 172 |
| CCD:HVG / 4-[(S)-amino(carboxy)methyl]benzene-1,2-dicarboxylic acid | 9MB9 | extracellular_explicit | 1 | corrected / 172 |
| CCD:HVG / 4-[(S)-amino(carboxy)methyl]benzene-1,2-dicarboxylic acid | 9MBC | extracellular_explicit | 1 | corrected / 172 |
| CCD:Z99 / 2-[(1S,2S)-2-carboxycyclopropyl]-3-(9H-xanthen-9-yl)-D-alanine | 9MBB | extracellular_explicit | 1 | corrected / 173 |
| P49407 | 9MBA | non_extracellular:cytoplasmic | 1 | unresolved |
| P63096 | 9MB9 | non_extracellular:cytoplasmic | 1 | unresolved |

