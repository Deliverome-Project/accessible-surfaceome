# RYK — Surface Accessibility Brief

*Schema v2.13.0 · generated 2026-06-24T16:28:28.501952Z · model `claude-sonnet-4-6`*

> RYK is constitutively surface-accessible as a pan-tissue single-pass type I Wnt co-receptor RTK. Direct multi-method support: a cell-surface-displayed transmembrane protein library screen identified RYK on intact hepatocytes with genetic KO validation (a1_evi_14), and functional antibody blockade on intact human cardiac endothelial cells abolished HGF/IgG-mediated protection (a1_evi_15); WIF1 domain antagonism on live HCAEC with siRNA phenocopy further confirms ECD accessibility (a1_evi_16). Surface levels are moderately state-modulated, upregulated in glioblastoma, malignant ovarian carcinoma, and injury-reactive astrocytes (a2_evi_04, a2_evi_03, a2_evi_08), and reduced in pneumonitis lung stroma (a2_evi_11). Moderate-severity ADAM-family ectodomain shedding is the principal binder-engineering caveat (a1_evi_19); low-severity epitope masking via EphB2/EphB3 complex and absence of an obligate co-receptor requirement rule out constitutive occlusion and trafficking-dependency concerns.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:10481](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:10481) |
| UniProt | [P34925](https://www.uniprot.org/uniprotkb/P34925) |
| NCBI Gene | [6259](https://www.ncbi.nlm.nih.gov/gene/6259) |
| Ensembl | [ENSG00000163785](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000163785) |
| Subcategory | Single-pass type I |
| Surface accessibility | High |
| Confidence | High |
| Evidence grade | Direct, multi-method |
| Triage signal | Likely accessible |
| Headline risks | Shed Form |

## 1. Executive summary

**Constitutively surface-accessible across normal and tumor tissue in multiple cell types (endothelium, hepatocytes, astrocytes, neurons); surface levels are moderately upregulated in glioblastoma, malignant ovarian carcinoma, and injury-reactive astrocytes, and transiently reduced by ligand-induced endocytosis and gamma-secretase cleavage under specific disease states.**

RYK is constitutively surface-accessible as a pan-tissue single-pass type I Wnt co-receptor RTK. Direct multi-method support: a cell-surface-displayed transmembrane protein library screen identified RYK on intact hepatocytes with genetic KO validation (a1_evi_14), and functional antibody blockade on intact human cardiac endothelial cells abolished HGF/IgG-mediated protection (a1_evi_15); WIF1 domain antagonism on live HCAEC with siRNA phenocopy further confirms ECD accessibility (a1_evi_16). Surface levels are moderately state-modulated, upregulated in glioblastoma, malignant ovarian carcinoma, and injury-reactive astrocytes (a2_evi_04, a2_evi_03, a2_evi_08), and reduced in pneumonitis lung stroma (a2_evi_11). Moderate-severity ADAM-family ectodomain shedding is the principal binder-engineering caveat (a1_evi_19); low-severity epitope masking via EphB2/EphB3 complex and absence of an obligate co-receptor requirement rule out constitutive occlusion and trafficking-dependency concerns.

**Family / classification** — UniProt family: protein kinase superfamily. Tyr protein kinase family · HGNC gene group(s): Receptor tyrosine kinases; WNT binding RTK type pseudokinases · functional class: Receptor.

**Triage first-pass reasoning** — RYK is a single-pass type I transmembrane receptor tyrosine kinase with a leucine-rich extracellular domain (Wnt-binding WIF domain) and an intracellular kinase domain. It is a classical surface receptor that is stably expressed on the plasma membrane outer leaflet. It functions as a co-receptor for Wnt ligands, and its extracellular domain is well-documented as accessible on intact, non-permeabilized cells via flow cytometry and surface biotinylation studies. Anti-RYK antibodies targeting the extracellular domain have been characterized in multiple studies on intact cells. Its topology is unambiguous: N-terminal ectodomain → single TM helix → cytoplasmic kinase domain.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=High · subcategory=Single-pass type I · ecd=Moderate |
| Classification | reason=Classical Surface Receptor · family=Receptor · state-dependence=Moderate · induction-trigger=Oncogenic |
| Expression | level=Moderate · breadth=Pan Tissue · specificity=Surface Dominant · low-endogenous=false · tumor-associated=true · orphan-receptor=false · OE-precedent=true |
| Risks | shed=true · secreted=true · co-receptor=None · masking=false · restricted-subdomain=true |
| Evidence | grade=Direct, multi-method · density=High · live-cell-surface=false · supporting(hi)=4 · contradicting(hi)=0 |
| Cross-species | mouse=96.0% · cyno=98.3% |
| Paralogs | max %ECD identity = 39.7% |
| Topology | TM=1 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: Northern blot detects RYK mRNA in all adult human tissues examined (a2_evi_01, a2_evi_02); protein-level expression across endothelium, hepatocytes, astrocytes, and neurons is consistently moderate, with high-level induction in tumor and injury contexts (a2_evi_04, a2_evi_08).
- *Expression breadth*: RYK mRNA is expressed in all adult human tissues by Northern blot (a2_evi_01); ISH confirms epithelial and stromal expression in brain, lung, colon, kidney, and breast (a2_evi_02); protein confirmed in liver, heart, spinal cord, peripheral nerve, and pleura across multiple independent studies.
- *Surface specificity*: Multiple live-cell functional assays on intact human primary cells confirm plasma membrane dominance (a1_evi_14, a1_evi_15, a1_evi_16); ligand-induced endocytosis and disease-state gamma-secretase cleavage create minor intracellular pools but do not displace the constitutive surface-dominant localization (a2_evi_21, a2_evi_22).
- *Known ligand*: Wnt5a is a validated endogenous ligand engaging the RYK WIF domain on intact cells (a1_evi_16, a2_evi_18); GDF15 ectodomain (G-ECD) is a second validated endogenous binding partner identified by cell-surface library screen (a1_evi_14).
- *Low endogenous expression*: Northern blot detects RYK mRNA in all adult human tissues examined (a2_evi_01, a2_evi_02); protein-level expression across endothelium, hepatocytes, astrocytes, and neurons is consistently moderate, with high-level induction in tumor and injury contexts (a2_evi_04, a2_evi_08).
- *Overexpression surface localization*: 2 method observation(s) pair an overexpression/mixed expression system with a surface-localization readout (cites a1_evi_14, a1_evi_22).

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Direct, multi-method

Multiple independent direct-surface-accessibility method types support RYK surface exposure. (1) Cell-surface-displayed transmembrane protein library screen in mouse hepatocytes identified RYK as a functional surface receptor for G-ECD, with hepatocyte-specific KO ablating the effect (a1_evi_14) — the library format requires surface display. (2) Functional antibody blockade on intact human cardiac endothelial cells (HCAEC): anti-RYK antibody abolished HGF/IgG-mediated vascular protection (a1_evi_15); WIF1 antagonist blocked Wnt5A-RYK signaling on intact HCAEC with Ryk siRNA phenocopy (a1_evi_16). (3) Function-blocking anti-Ryk mAb in 5XFAD mouse model with conditional KO phenocopy validating antibody specificity (a1_evi_13). These span ≥2 distinct direct method types (surface-display library screen; functional antibody blockade on intact cells) across human and mouse, with genetic KO/KD controls on multiple claims. IHC with KO-validated antibody in human spinal cord (a1_evi_08, a1_evi_10) and topology crystal structures (a1_evi_04, a1_evi_06) further corroborate. Ectodomain shedding (a1_evi_19, a1_evi_21) is tangential — it confirms a surface-anchored ECD exists prior to shedding. Graded direct_multi_method.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Moderate | Original cloning topology description — establishes single-pass type I architecture, baseline context |
| a1_evi_02 | Tangential | Low | Early discrepant 2-TM model, superseded by current consensus; not a contradiction of surface evidence |
| a1_evi_03 | Tangential | Moderate | Review-level topology classification as single-pass Wnt co-receptor; supports baseline architecture |
| a1_evi_04 | Tangential | Moderate | Drosophila ortholog crystal structures confirm extracellular WIF domain architecture; non-human |
| a1_evi_05 | Tangential | Moderate | Nrk ECR crystal structure 1.75 Å; Drosophila ortholog, confirms ECD topology but non-human |
| a1_evi_06 | Tangential | Moderate | Human RYK pseudokinase domain crystal structure (PDB:6TUA); confirms intracellular domain, supports single-pass topology |
| a1_evi_07 | Tangential | Moderate | gamma-secretase RIP cleavage in mouse; confirms single-pass TM topology, presupposes surface ECD |
| a1_evi_08 | Supports Surface | Moderate | IHC on human spinal cord tissue; explicit 'cell-surface receptor' claim, injury-induced in astrocytes |
| a1_evi_09 | Supports Surface | Moderate | IHC on mouse spinal cord post-injury with GFAP/fibronectin co-stain; permeabilization unspecified |
| a1_evi_10 | Supports Surface | High | Conditional KO (Ryk flox x GFAPcre-ERT2) abolishes Ryk IHC signal — validates antibody specificity |
| a1_evi_11 | Supports Surface | Moderate | IHC on mouse peripheral nerve conduit; RYK on axons, Wnt5a on Schwann cells; permeabilization unspecified |
| a1_evi_12 | Supports Surface | Moderate | IF on adult mouse brain tissue; RYK at glutamatergic synapses; permeabilized IF, mouse only |
| a1_evi_13 | Supports Surface | High | Function-blocking anti-Ryk mAb in 5XFAD mouse model; KO phenocopy validates antibody specificity; mouse in vivo |
| a1_evi_14 | Supports Surface | High | Cell-surface-displayed TM protein library screen identified RYK; mouse hepatocytes; KO validation; direct surface display format |
| a1_evi_15 | Supports Surface | Moderate | Antibody blockade of RYK on intact human cardiac endothelial cells abolished HGF/IgG protection; live cells |
| a1_evi_16 | Supports Surface | High | WIF1 antagonist blocks Wnt5A-RYK signaling on intact HCAEC; Ryk siRNA KD phenocopy; human primary endothelial cells |
| a1_evi_17 | Supports Surface | Moderate | IF + PLA shows progranulin-RYK co-localization in vesicular compartments in mesothelioma cells; permeabilization unspecified |
| a1_evi_18 | Supports Surface | Moderate | RYK ubiquitination and caveolin-1 endocytosis in mesothelioma cells; confirms PM-resident pool undergoing regulated internalization |
| a1_evi_19 | Tangential | Moderate | RIP/ectodomain shedding mechanism; confirms surface-anchored ECD exists prior to shedding; ambiguous for steady-state surface level |
| a1_evi_20 | Tangential | Low | Methodological detail of CTF accumulation screen in transfected cells; overexpression context |
| a1_evi_21 | Tangential | Low | ADAM sheddase mechanism for ECD shedding; reduces surface ECD under stimulation but does not refute basal surface expression |
| a1_evi_22 | Supports Surface | Moderate | Human RYK ECD required for EphB2/EphB3 association; confirms ECD accessible for protein-protein interaction at cell surface |
| a1_evi_23 | Expression Only | Moderate | IHC on human ovarian cancer tissue; increased expression in malignant epithelium; no membrane-specific scoring |
| a1_evi_24 | Expression Only | Moderate | IHC on 41 human glioblastoma specimens; no membrane-specific scoring or surface fractionation |
| a1_evi_25 | Expression Only | Moderate | RT-qPCR showing RYK mRNA upregulation in glioblastoma vs normal tissue; RNA-level only |
| a1_evi_26 | Supports Surface | Moderate | RYK siRNA KD in mesothelioma cells validates RYK as functional target; pairs with progranulin surface-engagement claims |

### Immunofluorescence (2 methods)

#### Permeabilized IF — Expression Only · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-Ryk — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Adult mouse brain glutamatergic synapses at 2, 4, and 6 months of age; Ryk co-present with PCP components Celsr3 and Vangl2 at synaptic puncta | Ex Vivo | Moderate | 1 |

#### Permeabilized IF — Expression Only · Intracellular Pool

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-RYK — Unknown epitope; Unknown; Moderate validation (SiRNA Knockdown); RYK siRNA knockdown (Dharmacon L-003174-00-0005) used in same paper to validate RYK functional role in mesothelioma cells.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human mesothelioma cell lines; progranulin and RYK co-localized in distinct vesicular compartments by immunofluorescence and proximity ligation assay | Established Cell Line | Moderate | 1 |

### Immunohistochemistry (4 methods)

#### IHC — Expression Only · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-Ryk — Unknown epitope; Polyclonal; Strong validation (Genetic KO); Lab-generated polyclonal; specificity confirmed by conditional Ryk KO (Ryk floxed × GFAPcreERT2) abolishing immunoreactivity in astrocytes.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Astrocytes in mouse spinal cord after C5 dorsal column lesion; Ryk expression significantly increased 1–7 days post-injury, co-localizing with GFAP; signal abolished in Ryk cKO mice | Ex Vivo | Moderate | 2 |
| Astrocytes in human spinal cord tissue after spinal cord injury; RYK described as induced cell-surface receptor in astrocytes | Primary Human Tissue | Moderate | 1 |

#### IHC — Expression Only · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-Ryk — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Axons traversing the nerve injury conduit (NIC) in mouse peripheral nerve; Ryk expressed by axons while Wnt5a expressed by Schwann cells | Ex Vivo | Moderate | 1 |

#### IHC — Expression Only · Unclear

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-H-RYK — Unknown epitope; Polyclonal; None validation (None); Polyclonal antisera raised against synthetic RYK peptides; recognizes a 100-kD protein in ovarian cancer cells by western blot.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human ovarian tissue; minimal-to-absent RYK on normal surface epithelium; increased expression in malignant epithelium of ovarian cancer specimens (n=24) | Primary Human Tissue | Low | 1 |

#### IHC — Expression Only · Unclear

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-Ryk — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Primary glioblastoma specimens (n=41); IHC staining for Ryk alongside Wnt5a, Fzd2, Fzd6 to assess influence on patient survival | Patient Sample | Moderate | 1 |

### Functional surface assay (7 methods)

#### Functional Surface Assay — Supports Membrane Association · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-Ryk (function-blocking monoclonal) — Extracellular epitope; Monoclonal; Strong validation (Genetic KO); Antigen: WIF domain of Ryk (aa 90–183); Ryk cKO produced the same protective phenotype, validating antibody specificity.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Neurons in 5XFAD Alzheimer's disease mouse model; function-blocking monoclonal Ryk antibody infusion protected synapses and preserved cognitive function, matching Ryk cKO phenotype | Ex Vivo | Moderate | 1 |

#### Functional Surface Assay — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Mixed*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Cell-surface-displayed transmembrane protein library screen identified RYK as functional receptor for GDF15 ectodomain (G-ECD); hepatocyte-specific Ryk ablation abolished G-ECD pathogenic effects in MASH model | Primary Human Cell | Moderate | 1 |

*Overexpression construct* — SP source: Unspecified. *(cites: a1_evi_14)*

#### Functional Surface Assay — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-RYK (blocking antibody) — Extracellular epitope; Unknown; None validation (None); Used to block RYK on intact cardiac endothelial cells; enhanced vascular protection from HGF/IgG complexes was lost after antibody blockade.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human cardiac endothelial cells; RYK phosphorylated after HGF/IgG complex exposure; antibody blockade of RYK abolished enhanced vascular protection | Primary Human Cell | Moderate | 1 |

#### Functional Surface Assay — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human coronary artery endothelial cells (HCAEC); WIF1 antagonist targeting the WIF domain of Ryk prevented Wnt5A-induced actin polymerization and endothelial hyperpermeability; Ryk silencing completely prevented Wnt5A-induced effects | Primary Human Cell | Moderate | 1 |

#### Functional Surface Assay — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human mesothelioma cell lines; progranulin promoted RYK ubiquitination and endocytosis via caveolin-1-enriched pathways; downstream signaling sensitive to endocytosis inhibitors, indicating RYK PM residence and regulated internalization | Established Cell Line | Moderate | 1 |

#### Functional Surface Assay — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Unknown · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human RYK expressed via chimeric receptor approach; association with EphB2 and EphB3 requires both extracellular and cytoplasmic domains of RYK, confirming ECD accessibility for protein-protein interaction | Established Cell Line | Moderate | 1 |

*Overexpression construct* — SP source: Unspecified. *(cites: a1_evi_22)*

#### Functional Surface Assay — Supports Membrane Association · Unclear

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human mesothelioma cell lines; RYK siRNA knockdown (Dharmacon L-003174-00-0005, 50 nM) used to validate RYK as functional target; pairs with progranulin/RYK surface-engagement claims | Established Cell Line | Moderate | 1 |

### Other (1 method)

#### Whole Cell Proteomics — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Unknown · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Transfected cells overexpressing C-terminal V5/eGFP-tagged RYK; PMA-stimulated ectodomain shedding followed by gamma-secretase cleavage generates membrane-anchored CTF and soluble ICD; GSI IX used to accumulate CTF | Established Cell Line | Moderate | 3 |

*Overexpression construct* — SP source: Unspecified · tag: C-terminal V5/eGFP. *(cites: a1_evi_19, a1_evi_20, a1_evi_21)*

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Human ovarian cancer tissue (malignant epithelium vs normal surface epithelium); increased RYK in malignant tumors | Patient Sample | IHC Protein | Moderate | 1 |
| Human glioblastoma primary specimens (41 patients); IHC for RYK alongside Wnt5a, Fzd2, Fzd6 | Patient Sample | IHC Protein | Moderate | 1 |
| Human glioblastoma tumor vs normal brain tissue; RYK mRNA significantly upregulated (RT-qPCR, p<0.0001) | Patient Sample | RNA | High | 1 |

**Contradicting evidence**

- *Isoform Conflict* (severity Low): An early 1993 cloning report (PMID:8390040) describes human RYK as having TWO potential transmembrane domains (607 aa), in contrast to the single-TM model supported by PMID:8386829, current UniProt annotation, and DeepTMHMM predictions. If a second TM helix were real, the topology of the extracellular WIF domain and the accessibility of the ectodomain to surface-targeting antibodies could differ substantially from the canonical single-pass model.
  - Likely explanation: Current consensus from UniProt, DeepTMHMM, and subsequent structural/functional studies firmly supports a single transmembrane helix. The two-TM prediction in the 1993 report likely reflects an artefact of early TM-prediction algorithms applied to a partial or mis-annotated sequence. The canonical single-pass topology is well-established and the discrepancy does not meaningfully challenge surface accessibility of the WIF-domain ECD.
- *Other* (severity Moderate): ADAM-family sheddases cleave RTK ectodomains at the extracellular juxtamembrane region, and this mechanism is described as applicable to RYK, meaning the WIF-domain ECD can be shed as a soluble fragment. Ectodomain shedding would reduce the surface-accessible pool of intact RYK and could confound antibody-based surface detection or targeting strategies that rely on the ECD.
  - Likely explanation: Ectodomain shedding is a dynamic, regulated process rather than a constitutive absence of surface expression. The specific ADAM sheddase responsible for RYK cleavage is not identified in this evidence, and the extent of shedding under basal conditions is unknown. Surface RYK is still present; shedding reduces but does not eliminate the accessible ECD pool, and the remaining membrane-tethered stub retains the transmembrane and intracellular domains.

## 4. Biological context

**Biological-context grade** · Rich

All four A2 axes are well-populated from independent sources. Expression is mapped across ≥10 tissues/cell types (brain, lung, liver, spinal cord, ovary, heart, peripheral nerve, endothelium, monocytes, breast) via Northern blot, ISH, IHC, RNA-seq, and scRNA-seq. Subcellular localization is pinned: plasma-membrane receptor confirmed in live-cell functional assays, with documented γ-secretase cleavage generating a nuclear ICD fragment and ligand-induced endocytosis via caveolin-1 pathways. Anatomical accessibility is evidenced across multiple human tissues. Accessibility modulation is rich: injury-induced upregulation (SCI, GBM), stem-cell-state enrichment, disease-state redistribution (ovarian cancer epithelial shift, HD nuclear ICD increase, pneumonitis stromal downregulation). Picture is coherent; state-dependent variation is biologically reconciled. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_07, a2_evi_08, +16)*

**Expression × cell type × disease context**

| Tissue | Cell type | Disease context | Level (protein) | Cell states |
|---|---|---|---|---|
| multiple adult tissues | — | Normal | High | — |
| ovary | surface epithelium | Normal | Absent | — |
| ovary | stromal cells | Tumor (benign and borderline ovarian tumor) | Low | — |
| ovary | epithelial cells | Tumor (malignant ovarian tumor) | High | — |
| brain | — | Normal | Low | — |
| brain | — | Tumor (glioblastoma multiforme) | High | — |
| brain | — | Tumor (glioma (WHO grade-stratified)) | High | — |
| brain | glioblastoma stem cells | Tumor (glioblastoma) | High | stem-like |
| spinal cord | astrocytes (GFAP+) | Other Disease (spinal cord injury) | High | reactive, injury-induced |
| spinal cord | astrocytes (GFAP+) | Other Disease (spinal cord injury) | High | reactive, injury-induced |
| lung | mesenchymal cells | Normal | Moderate | — |
| lung | epithelial cells | Normal | Moderate | — |
| lung | stromal cells | Other Disease (pneumonitis) | Low | — |
| liver | hepatocytes | Normal | Moderate | — |
| liver | hepatocytes | Other Disease (metabolic-associated steatohepatitis (MASH)) | Moderate | — |
| peripheral nerve | axons | Other Disease (nerve injury) | Moderate | — |
| brain | glutamatergic neurons (synaptic compartment) | Normal | Moderate | — |
| brain | neurons | Other Disease (Alzheimer's disease) | Moderate | — |
| brain (striatum) | neurons | Other Disease (Huntington's disease) | High | mutant huntingtin-expressing |
| coronary artery | endothelial cells | Normal | Moderate | — |
| heart | endothelial cells | Normal | Moderate | — |
| pleura | — | Tumor (mesothelioma) | Moderate | — |
| peripheral blood | monocytes / osteoclast progenitors | Normal | Moderate | RANKL-induced osteoclastogenesis |
| breast | — | Tumor (breast cancer (highly invasive)) | High | — |

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- Endosome · upon progranulin stimulation *(cites: a2_evi_20, a2_evi_21)*
- Nucleus · in mutant huntingtin-expressing neurons under HD pathology *(cites: a2_evi_22)*

**Membrane subdomains**: Caveolae

**Anatomical accessibility**

- glutamatergic synapses in adult brain — Synaptic · *Context Dependent*: Permeabilized IHC in mouse brain directly localizes RYK protein to glutamatergic synapses at 2, 4, and 6 months (a2_evi_15). Synaptic localization behind the blood-brain barrier restricts systemic binder access; local CNS delivery would be required.

**Accessibility modulation**

- *Disease State Induced*: normal ovarian surface epithelium → malignant ovarian carcinoma — RYK protein expression shifts from minimal/absent on normal ovarian surface epithelium to predominantly epithelial expression in malignant ovarian tumors (n=24); benign/borderline tumors show stromal-only expression. *(→ In Malignant Ovarian Tumors, RYK Becomes Accessible On The Epithelial Cell Surface, Creating A Tumor-Selective Surface Target Absent On Normal Ovarian Epithelium.)* *(cites: a2_evi_03)*
- *Cell State Induced* · trigger: Oncogenic Transformation: normal brain tissue → glioblastoma multiforme — RYK mRNA expression is significantly upregulated in glioblastoma multiforme tumor samples (n=77) compared to normal brain tissue (n=23), p<0.0001. *(→ Elevated RYK Expression In GBM Relative To Normal Brain Suggests Increased Surface Availability Of RYK On Tumor Cells, Potentially Enabling Tumor-Selective Targeting.)* *(cites: a2_evi_04)*
- *Cell State Induced* · trigger: Oncogenic Transformation: low-grade glioma tissue → high-grade glioma (GBM) tissue — RYK protein expression in human glioma tissues correlates positively with WHO histological grade, indicating progressive upregulation from low-grade to high-grade glioma. *(→ Higher-Grade Gliomas Express More RYK, Suggesting Progressively Greater Surface Accessibility Of RYK As Tumors Become More Malignant.)* *(cites: a2_evi_06, a2_evi_07)*
- *Disease State Induced*: uninjured spinal cord astrocytes → reactive astrocytes after spinal cord injury (1–7 days post-injury) — RYK expression is induced in astrocytes after spinal cord injury in both rodent and human spinal cord; immunoreactivity peaks at 1–7 days post-injury and begins to decrease by 14 days. *(→ Injury-Induced Upregulation Of RYK On Reactive Astrocytes Creates A Transiently Accessible Surface Target In The Acute Post-Injury Window That Is Absent In Uninjured Spinal Cord.)* *(cites: a2_evi_08, a2_evi_09)*
- *Disease State Induced*: healthy lung stromal cells → lung stromal cells in pneumonitis — RYK expression is down-regulated in stromal cells of pneumonitis patient lungs compared to healthy lung stromal tissue. *(→ Reduced RYK Surface Expression On Lung Stromal Cells During Pneumonitis Would Decrease Accessibility To RYK-Targeting Agents In This Inflammatory Disease Context.)* *(cites: a2_evi_11)*
- *Disease State Induced*: wild-type striatal neurons → mutant huntingtin-expressing striatal neurons (Huntington's disease) — RYK is upregulated in neurons expressing mutant huntingtin in multiple Huntington's disease models; additionally, γ-secretase cleavage generates a nuclear RYK-ICD fragment that accumulates in the nucleus of mutant HTT cells. *(→ In HD Neurons, Upregulated Full-Length RYK May Increase Surface Availability, But Concurrent γ-Secretase-Driven Cleavage And Nuclear ICD Accumulation Reduces The Surface Pool, Creating A Complex Net Effect On Extracellular Accessibility.)* *(cites: a2_evi_17, a2_evi_22)*
- *Post Translational Dependent*: wild-type striatal neurons (full-length RYK at plasma membrane) → mutant huntingtin striatal cells with elevated γ-secretase cleavage — In mutant huntingtin striatal cells, γ-secretase cleaves full-length RYK to generate an intracellular domain (Ryk-ICD) that translocates to the nucleus, shifting RYK from the plasma membrane to a nuclear fragment. *(→ γ-Secretase-Mediated Cleavage Removes The Extracellular/Transmembrane Portion Of RYK From The Cell Surface, Reducing Surface-Accessible RYK And Potentially Releasing An Ectodomain Fragment.)* *(cites: a2_evi_22)*
- *Dual Localization*: null → null — In mesothelioma cells, RYK colocalizes with progranulin in distinct intracellular vesicular compartments in addition to any plasma membrane pool, indicating a split between surface and endosomal/vesicular localization. *(→ A Fraction Of RYK Resides In Intracellular Vesicular Compartments Rather Than Exclusively At The Plasma Membrane, Potentially Limiting The Surface-Accessible Pool Available To Extracellular Binders.)* *(cites: a2_evi_20)*
- *Post Translational Dependent*: unstimulated mesothelioma cells → progranulin-stimulated mesothelioma cells — In mesothelioma cells, progranulin stimulation promotes RYK ubiquitination and endocytosis via caveolin-1-enriched pathways, reducing surface RYK levels and modulating RYK stability; downstream signaling is sensitive to endocytosis inhibitors. *(→ Ligand-Induced Ubiquitination And Caveolin-Mediated Endocytosis Dynamically Reduce Surface-Accessible RYK In Mesothelioma Cells; Endocytosis Inhibitors Could Restore Surface Availability.)* *(cites: a2_evi_21)*
- *Cell State Induced* · trigger: Oncogenic Transformation: low-invasiveness breast cancer cell lines → highly invasive breast cancer cell lines — RYK expression is higher in highly invasive breast cancer cell lines compared to less invasive lines; miR-7-5p targeting of RYK reduces its expression and downstream JNK phosphorylation. *(→ Higher RYK Expression In Invasive Breast Cancer Cells Suggests Greater Surface Availability Of RYK In Aggressive Tumor Phenotypes, Potentially Enabling Targeting In High-Invasiveness Breast Cancer.)* *(cites: a2_evi_24)*

**Restricted-subdomain distribution**

- present: true
- severity: Low
- evidence: Moderate
- domain: Synaptic
- rationale: RYK is documented at glutamatergic synapses in adult mouse brain at 2, 4, and 6 months (a1_evi_12, a2_evi_15), co-localizing with PCP components Celsr3 and Vangl2. However, RYK is also broadly expressed on astrocytes (a1_evi_08), axons (a1_evi_11), endothelial cells (a1_evi_15, a1_evi_16), and hepatocytes (a1_evi_14), indicating synaptic enrichment is cell-type-specific rather than an absolute restriction. Severity is low for systemic binder access.
- cites: a1_evi_12, a1_evi_15, a2_evi_15

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: RYK is a single-pass type I transmembrane receptor that traffics independently to the cell surface. Multiple studies demonstrate surface accessibility without any obligate partner: a cell-surface-displayed transmembrane protein library screen identified RYK on intact cells (a1_evi_14), and antibody blockade of RYK on intact cardiac endothelial cells and neurons confirms partner-independent surface residence (a1_evi_13, a1_evi_15). No chaperone or escort requirement is documented in the ledger.
- cites: a1_evi_13, a1_evi_14, a1_evi_15

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P34925 | ref | ref | 1 | 184 aa | 357 aa | 46 aa | Extracellular→Cytoplasmic | — |
| Isoform | P34925-2 | P34925-2 | 99.5% | 100.0% | 1 | 184 aa | 360 aa | 46 aa | Extracellular→Cytoplasmic | — |
| Mouse ortholog | Ryk | [Q01887](https://www.uniprot.org/uniprotkb/Q01887) | 93.1% | 96.0% | 1 | 184 aa | — | — | — | high (≥85%) |
| Cynomolgus ortholog | RYK | [A0A2K5VQA5](https://www.uniprot.org/uniprotkb/A0A2K5VQA5) | 99.0% | 98.3% | 1 | 184 aa | — | — | — | high (≥85%) |
| Paralog | ROS1 | [P08922](https://www.uniprot.org/uniprotkb/P08922) | 24.4% | 39.7% | — | — | — | — | — | low-risk |
| Paralog | FLT4 | [P35916](https://www.uniprot.org/uniprotkb/P35916) | 23.6% | 39.1% | — | — | — | — | — | low-risk |
| Paralog | ALK | [Q9UM73](https://www.uniprot.org/uniprotkb/Q9UM73) | 21.4% | 38.0% | — | — | — | — | — | low-risk |
| Paralog | RET | [P07949](https://www.uniprot.org/uniprotkb/P07949) | 20.1% | 38.0% | — | — | — | — | — | low-risk |
| Paralog | KDR | [P35968](https://www.uniprot.org/uniprotkb/P35968) | 23.4% | 37.5% | — | — | — | — | — | low-risk |
| Paralog | INSR | [P06213](https://www.uniprot.org/uniprotkb/P06213) | 23.4% | 37.5% | — | — | — | — | — | low-risk |
| Paralog | INSRR | [P14616](https://www.uniprot.org/uniprotkb/P14616) | 22.7% | 35.9% | — | — | — | — | — | low-risk |
| Paralog | CSF1R | [P07333](https://www.uniprot.org/uniprotkb/P07333) | 21.6% | 35.9% | — | — | — | — | — | low-risk |
| Paralog | MST1R | [Q04912](https://www.uniprot.org/uniprotkb/Q04912) | 25.4% | 35.3% | — | — | — | — | — | low-risk |
| Paralog | TIE1 | [P35590](https://www.uniprot.org/uniprotkb/P35590) | 23.9% | 34.8% | — | — | — | — | — | low-risk |
| Paralog | PDGFRB | [P09619](https://www.uniprot.org/uniprotkb/P09619) | 22.6% | 34.8% | — | — | — | — | — | low-risk |
| Paralog | EPHA2 | [P29317](https://www.uniprot.org/uniprotkb/P29317) | 21.7% | 34.8% | — | — | — | — | — | low-risk |
| Paralog | NTRK2 | [Q16620](https://www.uniprot.org/uniprotkb/Q16620) | 21.3% | 34.8% | — | — | — | — | — | low-risk |
| Paralog | IGF1R | [P08069](https://www.uniprot.org/uniprotkb/P08069) | 23.7% | 34.2% | — | — | — | — | — | low-risk |
| Paralog | FLT1 | [P17948](https://www.uniprot.org/uniprotkb/P17948) | 22.9% | 33.7% | — | — | — | — | — | low-risk |
| Paralog | EPHB1 | [P54762](https://www.uniprot.org/uniprotkb/P54762) | 21.6% | 33.7% | — | — | — | — | — | low-risk |
| Paralog | MET | [P08581](https://www.uniprot.org/uniprotkb/P08581) | 22.9% | 33.2% | — | — | — | — | — | low-risk |
| Paralog | EPHA1 | [P21709](https://www.uniprot.org/uniprotkb/P21709) | 21.1% | 32.6% | — | — | — | — | — | low-risk |
| Paralog | EPHA4 | [P54764](https://www.uniprot.org/uniprotkb/P54764) | 20.8% | 32.6% | — | — | — | — | — | low-risk |
| Paralog | EPHA8 | [P29322](https://www.uniprot.org/uniprotkb/P29322) | 22.2% | 32.1% | — | — | — | — | — | low-risk |
| Paralog | FGFR3 | [P22607](https://www.uniprot.org/uniprotkb/P22607) | 23.9% | 31.5% | — | — | — | — | — | low-risk |
| Paralog | TYRO3 | [Q06418](https://www.uniprot.org/uniprotkb/Q06418) | 23.2% | 31.5% | — | — | — | — | — | low-risk |
| Paralog | KIT | [P10721](https://www.uniprot.org/uniprotkb/P10721) | 22.6% | 31.5% | — | — | — | — | — | low-risk |
| Paralog | PDGFRA | [P16234](https://www.uniprot.org/uniprotkb/P16234) | 21.3% | 31.5% | — | — | — | — | — | low-risk |
| Paralog | ROR1 | [Q01973](https://www.uniprot.org/uniprotkb/Q01973) | 18.6% | 31.5% | — | — | — | — | — | low-risk |
| Paralog | ERBB3 | [P21860](https://www.uniprot.org/uniprotkb/P21860) | 18.1% | 31.5% | — | — | — | — | — | low-risk |
| Paralog | EPHB2 | [P29323](https://www.uniprot.org/uniprotkb/P29323) | 21.9% | 31.0% | — | — | — | — | — | low-risk |
| Paralog | NTRK1 | [P04629](https://www.uniprot.org/uniprotkb/P04629) | 21.3% | 31.0% | — | — | — | — | — | low-risk |
| Paralog | EGFR | [P00533](https://www.uniprot.org/uniprotkb/P00533) | 19.9% | 31.0% | — | — | — | — | — | low-risk |
| Paralog | FGFR1 | [P11362](https://www.uniprot.org/uniprotkb/P11362) | 24.7% | 30.4% | — | — | — | — | — | low-risk |
| Paralog | AXL | [P30530](https://www.uniprot.org/uniprotkb/P30530) | 23.9% | 30.4% | — | — | — | — | — | low-risk |
| Paralog | TEK | [Q02763](https://www.uniprot.org/uniprotkb/Q02763) | 21.4% | 30.4% | — | — | — | — | — | low-risk |
| Paralog | ERBB4 | [Q15303](https://www.uniprot.org/uniprotkb/Q15303) | 20.1% | 30.4% | — | — | — | — | — | low-risk |
| Paralog | FGFR2 | [P21802](https://www.uniprot.org/uniprotkb/P21802) | 23.9% | 29.9% | — | — | — | — | — | low-risk |
| Paralog | EPHA5 | [P54756](https://www.uniprot.org/uniprotkb/P54756) | 22.9% | 29.9% | — | — | — | — | — | low-risk |
| Paralog | EPHA3 | [P29320](https://www.uniprot.org/uniprotkb/P29320) | 22.2% | 29.9% | — | — | — | — | — | low-risk |
| Paralog | FLT3 | [P36888](https://www.uniprot.org/uniprotkb/P36888) | 20.1% | 29.9% | — | — | — | — | — | low-risk |
| Paralog | NTRK3 | [Q16288](https://www.uniprot.org/uniprotkb/Q16288) | 22.6% | 29.3% | — | — | — | — | — | low-risk |
| Paralog | EPHB3 | [P54753](https://www.uniprot.org/uniprotkb/P54753) | 22.4% | 29.3% | — | — | — | — | — | low-risk |
| Paralog | MERTK | [Q12866](https://www.uniprot.org/uniprotkb/Q12866) | 24.2% | 28.3% | — | — | — | — | — | low-risk |
| Paralog | EPHB4 | [P54760](https://www.uniprot.org/uniprotkb/P54760) | 22.1% | 28.3% | — | — | — | — | — | low-risk |
| Paralog | ERBB2 | [P04626](https://www.uniprot.org/uniprotkb/P04626) | 20.6% | 28.3% | — | — | — | — | — | low-risk |
| Paralog | EPHA10 | [Q5JZY3](https://www.uniprot.org/uniprotkb/Q5JZY3) | 19.4% | 28.3% | — | — | — | — | — | low-risk |
| Paralog | ROR2 | [Q01974](https://www.uniprot.org/uniprotkb/Q01974) | 18.9% | 27.7% | — | — | — | — | — | low-risk |
| Paralog | DDR2 | [Q16832](https://www.uniprot.org/uniprotkb/Q16832) | 23.7% | 26.6% | — | — | — | — | — | low-risk |
| Paralog | DDR1 | [Q08345](https://www.uniprot.org/uniprotkb/Q08345) | 22.2% | 26.6% | — | — | — | — | — | low-risk |
| Paralog | EPHA6 | [Q9UF33](https://www.uniprot.org/uniprotkb/Q9UF33) | 21.7% | 26.6% | — | — | — | — | — | low-risk |
| Paralog | MUSK | [O15146](https://www.uniprot.org/uniprotkb/O15146) | 20.6% | 26.1% | — | — | — | — | — | low-risk |
| Paralog | EPHA7 | [Q15375](https://www.uniprot.org/uniprotkb/Q15375) | 23.1% | 25.5% | — | — | — | — | — | low-risk |
| Paralog | FGFR4 | [P22455](https://www.uniprot.org/uniprotkb/P22455) | 22.6% | 23.4% | — | — | — | — | — | low-risk |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: true
- severity: Moderate
- evidence: Moderate
- mechanism: ADAM-Family Sheddase Cleaves The RYK Ectodomain At The Extracellular Juxtamembrane Region (Regulated Intramembrane Proteolysis, RIP); PMA-Stimulated Shedding Accumulates A Membrane-Anchored C-Terminal Fragment (CTF) Detectable By Western Blot After Gamma-Secretase Inhibition, Releasing The WIF-Domain ECD As A Soluble Fragment.
- sheddase: ADAM family (specific member for RYK not identified in ledger)
- rationale: RYK undergoes PMA-stimulated ADAM-family ectodomain shedding followed by gamma-secretase cleavage (RIP), documented by CTF accumulation upon GSI IX treatment in transfected cells (a1_evi_19, a1_evi_20, a1_evi_21). The WIF-domain ECD is released as a soluble fragment. Specific sheddase for RYK not named; ADAM10 validated for AXL in the same screen (a1_evi_21). No serum-level quantification or decoy competition data in ledger.
- cites: a1_evi_19, a1_evi_20, a1_evi_21

**Secreted form**

- present: true
- severity: Low
- evidence: Moderate
- source: Proteolytic
- rationale: The shed WIF-domain ectodomain of RYK is released as a soluble fragment via ADAM-family shedding (a1_evi_19, a1_evi_21). No serum/plasma quantification of free soluble RYK ECD is reported in the ledger, and no antibody-decoy competition assay is documented. Severity is low: soluble form is inferred from the shedding mechanism but circulating levels and decoy behavior are uncharacterized. No TM-less splice isoform is documented.
- cites: a1_evi_19, a1_evi_21

**ECD size assessment**

- ECD class: Moderate
- rationale: ECD length 184 residues (60-199) -> moderate; computed deterministically from DeepTMHMM topology.

**Epitope masking**

- severity: Low
- evidence: Moderate
- mechanism: Partner
- rationale: RYK associates with EphB2 and EphB3 via its extracellular domain in a constitutive complex (a1_evi_22), and complexes with EGFR in mesothelioma cells (a2_evi_21), potentially covering portions of the ECD. However, multiple studies demonstrate that antibodies and antagonists (WIF1) can access the RYK ECD on intact cells (a1_evi_13, a1_evi_15, a1_evi_16), indicating masking is partial and not constitutively occlusive. No homo-oligomerization is predicted (deterministic: is_homo_oligomer=false) and no ledger evidence supports it.
- cites: a1_evi_22, a2_evi_21, a1_evi_13, a1_evi_16

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P34925-F1](https://alphafold.ebi.ac.uk/entry/P34925) |
| AFDB version | v6 |
| ECD mean pLDDT | 77.4 |
| ECD disordered fraction | 25.0% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P34925) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P34925](https://alphafold.ebi.ac.uk/entry/P34925) | AlphaFold DB (AF-P34925-F1, v6) |
| Isoform P34925-2 | [P34925-2](https://alphafold.ebi.ac.uk/entry/P34925-2) | AlphaFold DB |
| Mouse ortholog (Ryk) | [Q01887](https://alphafold.ebi.ac.uk/entry/Q01887) | AlphaFold DB |
| Cynomolgus ortholog (RYK) | [A0A2K5VQA5](https://alphafold.ebi.ac.uk/entry/A0A2K5VQA5) | AlphaFold DB |
| Experimental (1 total) | [6TUA](https://www.rcsb.org/structure/6TUA) | RCSB PDB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

Tyrosine-protein kinase RYK · Receptors · Kinase · chain A · 1 scored site · 247 binder seeds (134 α-helix / 113 β-strand).

Anchor = patch-center residue; BSA = buried surface area (the contact footprint a binder would form on the patch); seed counts are docked binder backbones split by α-helix / β-strand.

**Reading the scores.** BSA vs the average antibody–antigen interface ≈ 1103 ± 244 Å² ([PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)): ≥1500 Å² comfortable · 850–1500 workable · <850 thin. Seed pool: ≥1000 comfortable design margin · ≥100 workable · <100 thin/specialized. SURFACE-Bind excludes transmembrane regions but not necessarily intracellular domains — cross-check the anchor residue against the topology string in §5/appendix (`O` = extracellular/antibody-accessible, `I` = intracellular).

| Site | Anchor residue | BSA (Å²) | α-helix seeds | β-strand seeds | Hydrophobicity |
|---|---|---|---|---|---|
| 0 | 98 | 5106.6 | 134 | 113 | 22.0 |

**Experimental structures** — 1 PDB entry for this protein (browse at [RCSB](https://www.rcsb.org/uniprot/P34925)).

## 9. Evidence ledger

50 entries · 38 primary · 12 secondary · 0 tertiary · 41 PMC OA.

- `a1_evi_01` · *Secondary* · Supports · Topology — Original cloning paper (1993) describes human RYK as a transmembrane protein with a cytoplasmic tyrosine kinase domain, establishing the single-pass receptor topology with an extracellular N-terminus and intracellular kinase domain. (https://pubmed.ncbi.nlm.nih.gov/8386829/)
  - *assay*: Human
  > "A cDNA encoding the human homologue of mouse RYK (related to receptor tyrosine kinases) has been cloned from an interleukin 1 (IL-1)-stimulated human hepatoma cDNA library by cross-species hybridization using the mouse RYK cDNA as a probe. The sequence of the 3067-bp cDNA clone encoding human RYK predicts a transmembrane protein with a cytoplasmic domain that contains the consensus sequences (subdomains I-XI) of the protein tyrosine kinase (PTK) family."
- `a1_evi_02` · *Secondary* · Ambiguous · Contradictory — A second 1993 cloning report describes human RYK as having TWO potential transmembrane domains (607 aa), in contrast to the single-TM model from PMID:8386829 and current UniProt annotation. This discrepancy in TM count between early reports is a potential topology conflict; current consensus (UniProt, DeepTMHMM) supports a single TM helix. (https://pubmed.ncbi.nlm.nih.gov/8390040/)
  - *assay*: Human
  > "The human ryk tyrosine kinase cDNA was originally identified as a PCR-amplified cDNA fragment (JTK5) from K562 leukemia cells and found to represent a ubiquitously expressed gene (Partanen et al., 1990). The open reading frame of human ryk, reported here, encodes a novel type of putative tyrosine kinase of 607 amino acid residues, having two potential transmembrane domains and homology to receptor tyrosine kinases, such as met (HGF/SF-R) and IGF-1R, in its catalytic domain. The gene maps to human chromosome 3q11-25."
- `a1_evi_03` · *Secondary* · Supports · Topology — RYK is classified as a single-pass transmembrane receptor tyrosine kinase co-receptor for WNTs, alongside ROR family RTKs, establishing its type I topology (extracellular WIF domain, single TM, intracellular pseudokinase domain). ([PMC8650758](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8650758/))
  - *assay*: Human
  > "WNTs play key roles in development and disease, signaling through Frizzled (FZD) seven-pass transmembrane receptors and numerous co-receptors including ROR and RYK family receptor tyrosine kinases (RTKs)."
- `a1_evi_04` · *Primary* · Supports · Topology — Crystal structures of extracellular regions from Drosophila RYK orthologs (Nrk, Drl-2) reveal WNT-binding through a FZD-related CRD and WIF domain respectively, directly characterizing the accessible extracellular topology of the RYK family ECD. ([PMC8650758](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8650758/))
  - *assay*: Other
  > "We describe crystal structures and WNT-binding characteristics of extracellular regions from the Drosophila ROR and RYK orthologs Nrk (neurospecific receptor tyrosine kinase) and Derailed-2 (Drl-2), which bind WNTs though a FZD-related cysteine-rich domain (CRD) and WNT-inhibitory factor (WIF) domain respectively."
- `a1_evi_05` · *Primary* · Supports · Topology — Crystal structure of Nrk ECR (Drosophila RYK ortholog) determined to 1.75 Å resolution, providing atomic-level detail of the extracellular domain architecture accessible at the cell surface. ([PMC8650758](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8650758/))
  - *assay*: Other
  > "We first determined the crystal structure of the Nrk ECR (sNrk) to 1.75 Å resolution ( Table 1 )."
- `a1_evi_06` · *Primary* · Supports · Topology — Crystal structure of the human RYK pseudokinase domain determined to 2.38 Å resolution (PDB: 6TUA), confirming the intracellular domain architecture and indirectly supporting the single-pass topology with cytoplasmic C-terminus. ([PMC7543951](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7543951/))
  - *assay*: Human
  > "We determined crystal structures of the PTK7 and RYK pseudokinase domains (to 1.95 Å and 2.38 Å respectively) plus that of ROR1 bound to a small molecule (described in a later section), as summarized in Table 1 ."
- `a1_evi_07` · *Secondary* · Supports · Topology — RYK undergoes gamma-secretase cleavage within its transmembrane region, releasing the intracellular domain (Ryk-ICD) which translocates to the nucleus — a regulated intramembrane proteolysis (RIP) event that presupposes prior ectodomain shedding and confirms the single-pass TM topology. ([PMC4068980](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4068980/))
  - *assay*: Mouse
  > "The Wnt receptor Ryk is an evolutionary-conserved protein important during neuronal differentiation through several mechanisms, including γ-secretase cleavage and nuclear translocation of its intracellular domain (Ryk-ICD)."
- `a1_evi_08` · *Primary* · Supports · Surface Expression — RYK is explicitly described as a cell-surface receptor that is induced in astrocytes after spinal cord injury in both rodent and human tissue, providing a direct surface-expression claim in native tissue context. ([PMC12012454](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12012454/))
  - *assay*: Human · astrocytes · fixed
  > "We show here that the expression of a cell-surface receptor, Ryk, is induced in astrocytes after injury in both rodent and human spinal cords."
- `a1_evi_09` · *Primary* · Supports · Methodological — IHC on mouse spinal cord tissue post-C5 dorsal column lesion using a polyclonal Ryk antibody (lab-generated) co-stained with GFAP (astrocyte marker) and fibronectin (fibroblast marker) at 1, 3, 7, and 14 days post-injury. Permeabilization status not specified for tissue sections; method is standard fixed-tissue IHC. ([PMC12012454](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12012454/))
  - *assay*: Mouse · astrocytes · fixed
  > "Mice were subjected to cervical 5 (C5) dorsal column lesion and costained with a polyclonal Ryk antibody previously made in the lab and an astrocyte marker, GFAP, or a fibroblast marker, fibronectin, 1 d, 3 d, 7 d, and 14 d after injury ( Fig. 1 A ) ( 2 , 13 )."
- `a1_evi_10` · *Primary* · Supports · Methodological — Antibody validation: Ryk immunoreactivity was abolished in astrocytes of conditional Ryk knockout mice (Ryk floxed × GFAPcre-ERT2), confirming specificity of the polyclonal Ryk antibody used for IHC. This genetic KO validation upgrades confidence in the IHC surface-expression claims. ([PMC12012454](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12012454/))
  - *assay*: Mouse · astrocytes · fixed
  > "Compared with WT animals, we found that most of the Ryk immunoreactivity was abolished in astrocytes in Ryk cKO mice ( Fig. 1 B ), confirming the specificity of the Ryk antibody and the effectiveness of the Ryk conditional knockout in astrocytes."
- `a1_evi_11` · *Primary* · Supports · Surface Expression — IHC on nerve injury conduit (NIC) tissue shows RYK protein expressed by axons traversing the NIC, while Wnt5a is expressed by Schwann cells — demonstrating RYK surface localization on axons in native peripheral nerve tissue. ([PMC8043392](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8043392/))
  - *assay*: Mouse · axons · fixed
  > "Immunohistochemistry showed that Schwann cells in the NIC and in the injured nerve are the source of Wnt5a, whereas the Wnt5a receptor Ryk is expressed by axons traversing the NIC."
- `a1_evi_12` · *Primary* · Supports · Surface Expression — Immunofluorescence/microscopy on adult mouse brain tissue shows RYK protein present at glutamatergic synapses at 2, 4, and 6 months of age, alongside PCP components Celsr3 and Vangl2, indicating stable surface localization at synaptic membranes. ([PMC8373119](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8373119/))
  - *assay*: Mouse · glutamatergic neurons · fixed
  > "We observed that the PCP components, Celsr3 and Vangl2, and the Wnt receptor, Ryk, are present in the adult glutamatergic synapses (at 2, 4, and 6 months of age)."
- `a1_evi_13` · *Primary* · Supports · Surface Expression — A function-blocking monoclonal Ryk antibody administered in the 5XFAD Alzheimer's mouse model protected synapses and preserved cognitive function, demonstrating that an antibody can engage RYK on intact cells in vivo — direct therapeutic surface-accessibility evidence. Conditional Ryk KO produced the same protective phenotype, validating antibody specificity. ([PMC8373119](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8373119/))
  - *assay*: Mouse · neurons · live · non-permeabilized
  > "In the 5XFAD mouse model of Alzheimer's disease, <i>Ryk</i> conditional knockout or a function-blocking monoclonal Ryk antibody protected synapses and preserved cognitive function."
- `a1_evi_14` · *Primary* · Supports · Surface Expression — Using an unbiased cell-surface-displayed transmembrane protein library screen, RYK was identified as a functional receptor for G-ECD (GDF15 ectodomain). Hepatocyte-specific Ryk ablation abolished G-ECD pathogenic effects. This screen directly demonstrates RYK surface accessibility on intact cells — the library format requires the protein to be displayed on the cell surface for detection. (https://pubmed.ncbi.nlm.nih.gov/41708863/)
  - *assay*: Mouse · hepatocytes · live · non-permeabilized
  > "Using an unbiased screen of a cell-surface-displayed transmembrane protein library, we identified related to receptor tyrosine kinase (RYK) as a functional receptor for G-ECD. Hepatocyte-specific Ryk ablation protected mice against MASH and abolished the pathogenic effects of G-ECD. Mechanistically, G-ECD binding to RYK activated ERK1/2 signaling, resulting in transcriptional activation of PPARγ-CD36 and SREBP1C pathways that promote hepatic lipid uptake and lipogenesis."
- `a1_evi_15` · *Primary* · Supports · Surface Expression — RYK receptor was phosphorylated after exposure of cardiac endothelial cells to HGF/IgG complexes (but not free HGF), and antibody blockade of RYK abolished the enhanced vascular protection — demonstrating that an antibody can access and block RYK on intact cardiac endothelial cells, confirming surface accessibility. ([PMC4565990](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4565990/))
  - *assay*: Human · cardiac endothelial cells · live · non-permeabilized
  > "Following reperfusion, preparations of HGF/IgG complexes provided greater vascular protection than free HGF with IgG. HGF/IgG complexes localized to blood vessels in vivo and increased HGF retention time after administration. In subsequent screens, we found that 'related to tyrosine kinase' (RYK) receptor was phosphorylated after exposure of cardiac endothelial cells to HGF/IgG complexes, but not to free HGF with IgG. The enhanced protection conferred by HGF/IgG complexes was lost after antibody blockade of RYK."
- `a1_evi_16` · *Primary* · Supports · Surface Expression — WIF1 antagonist, which specifically interferes with the WIF domain of Ryk receptors, prevented Wnt5A-induced actin polymerization and endothelial hyperpermeability in human coronary artery endothelial cells (HCAEC). Ryk silencing completely prevented Wnt5A-induced effects. This demonstrates that the WIF domain of RYK is accessible on intact endothelial cells for ligand and antagonist engagement. ([PMC5308226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5308226/))
  - *assay*: Human · HCAEC · live · non-permeabilized
  > "The antagonist Wnt inhibitory factor 1 (WIF1) that specifically interferes with the WIF domain of Ryk receptors prevented actin polymerization. Wnt5A disrupted β-catenin and VE-cadherin adherens junctions forming inter-endothelial gaps. Functional experiments targeting the endothelial monolayer integrity and live recording of trans-endothelial resistance revealed enhanced permeability of Wnt5A-treated HCAEC. Ryk silencing completely prevented Wnt5A-induced endothelial hyperpermeability. Wnt5A decreased wound healing capacity of HCAEC monolayers; this was restored by the ROCK inhibitor Y-27632."
- `a1_evi_17` · *Secondary* · Supports · Surface Expression — Progranulin directly interacts with RYK (ELISA Kd=0.67 nM) and co-localizes with RYK in mesothelioma cells in distinct vesicular compartments by immunofluorescence and proximity ligation assay. The vesicular co-localization suggests RYK is present at the cell surface and in endosomal compartments, consistent with surface expression followed by internalization. ([PMC10393324](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10393324/))
  - *assay*: Human · mesothelioma cell lines · fixed
  > "However, the molecular mechanism regulating the functional interaction among progranulin, EGFR, and RYK are not known. In this study, we demonstrated that progranulin directly interacted with RYK by specific enzyme-linked immunosorbent assay (ELISA) (K<i><sub>D</sub></i> = 0.67). Using immunofluorescence and proximity ligation assay, we further discovered that progranulin and RYK colocalized in mesothelioma cells in distinct vesicular compartments."
- `a1_evi_18` · *Secondary* · Ambiguous · Surface Expression — Progranulin promotes RYK ubiquitination and endocytosis preferentially through caveolin-1-enriched pathways, and downstream signaling is sensitive to endocytosis inhibitors. This indicates RYK is present at the plasma membrane and undergoes regulated internalization — consistent with surface expression dynamics but also indicating the dominant species may be internalized under progranulin stimulation. ([PMC10393324](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10393324/))
  - *assay*: Human · mesothelioma cell lines · live · non-permeabilized
  > "Notably, progranulin-dependent downstream signaling was sensitive to endocytosis inhibitors, suggesting that it could depend on RYK or EGFR internalization. We discovered that progranulin promoted RYK ubiquitination and endocytosis preferentially through caveolin-1-enriched pathways, and modulated RYK stability. Interestingly, we also showed that in mesothelioma cells, RYK complexes with the EGFR, contributing to the regulation of RYK stability."
- `a1_evi_19` · *Primary* · Ambiguous · Surface Expression — RYK undergoes regulated intramembrane proteolysis (RIP): ectodomain shedding by ADAM-family sheddases followed by gamma-secretase cleavage releases a soluble intracellular fragment (Ryk-ICD) with signaling activity. This shed-form mechanism means the RYK ectodomain may be released as a soluble form, reducing surface-accessible ECD under stimulated conditions. ([PMC5662267](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5662267/))
  - *assay*: Human · transfected cells · unspecified
  > "Receptor tyrosine kinases (RTKs) have been demonstrated to signal via regulated intramembrane proteolysis, in which ectodomain shedding and subsequent intramembrane cleavage by gamma-secretase leads to release of a soluble intracellular receptor fragment with functional activity."
- `a1_evi_20` · *Primary* · Ambiguous · Methodological — Screen methodology: GSI IX (gamma-secretase inhibitor) was used to accumulate the membrane-anchored C-terminal fragment (CTF) of RTKs after PMA-stimulated ectodomain shedding. Western blot detection of CTF in transfected cells with C-terminal epitope tags confirmed RYK undergoes PMA-stimulated shedding. This is the methodological basis for the shed-form claim — overexpression constructs with C-terminal V5/eGFP tags in transfected cells. ([PMC5662267](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5662267/))
  - *assay*: Human · transfected cells (C-terminal V5/eGFP tagged RYK) · unspecified
  > "The screen was based on the effect of a chemical gamma-secretase inhibitor IX (GSI IX) on accumulating the membrane-anchored carboxy-terminal fragment (CTF) of the RTK after PMA-stimulated shedding of the RTK ectodomain."
- `a1_evi_21` · *Secondary* · Refutes · Surface Expression — ADAM-family sheddases cleave the RTK ectodomain at the extracellular juxtamembrane region, generating a substrate for gamma-secretase. For RYK, this means the WIF-domain ECD can be shed as a soluble fragment, reducing surface-accessible ECD. Sheddase identity for RYK specifically is not named in this clip (ADAM10 validated for AXL in the same paper). ([PMC5662267](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5662267/))
  - *assay*: Human · transfected cells · unspecified
  > "The cleavage of the ectodomain within the extracellular juxtamembrane domain by members of the ADAM family of proteases (sheddases) generates a substrate for the activity of the gamma-secretase complex that subsequently cleaves the RTK within the cytosolic half of the transmembrane domain ( Figure 1A ; Ancot et al ., 2009 )."
- `a1_evi_22` · *Secondary* · Supports · Surface Expression — Human RYK associates with EphB2 and EphB3 via both its extracellular and cytoplasmic domains (not phosphorylated by Eph receptors). The requirement for the extracellular domain in this interaction confirms the ECD is accessible on the cell surface for protein-protein interactions. (https://pubmed.ncbi.nlm.nih.gov/11956217/)
  - *assay*: Human · unspecified · unspecified
  > "RYK is an atypical orphan receptor tyrosine kinase that lacks detectable kinase activity. Nevertheless, using a chimeric receptor approach, we previously found that RYK can signal via the mitogen-activated protein kinase pathway. Recently, it has been shown that murine Ryk can bind to and be phosphorylated by the ephrin receptors EphB2 and EphB3. In this study, we show that human RYK associates with EphB2 and EphB3 but is not phosphorylated by them. This association requires both the extracellular and cytoplasmic domains of RYK and is not dependent on activation of the Eph receptors."
- `a1_evi_23` · *Secondary* · Ambiguous · Tissue Expression — Polyclonal antisera raised against synthetic RYK peptides recognize a 100-kD protein in ovarian cancer cells and other cell lines by western blot. IHC on ovarian tissue shows minimal-to-absent RYK on normal surface epithelium but increased expression in malignant epithelium. This is whole-cell/tissue IHC without explicit membrane scoring or surface-specific fractionation. ([PMC2230112](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2230112/))
  - *assay*: Human · ovarian cancer cells · fixed
  > "There was minimal to absent expression of H-RYK on surface epithelium of ovaries. In benign (3) and borderline tumors of the ovary (5), there was expression in the stromal compartment. However, in malignant tumors (24) there was increased expression predominantly confined to the epithelium. Polyclonal antisera raised against synthetic peptides recognize a 100-kD protein in ovarian cancer cells and other cell lines."
- `a1_evi_24` · *Secondary* · Ambiguous · Tissue Expression — IHC on 41 primary glioblastoma specimens stained for Wnt5a, Fzd2, Fzd6, and RYK to assess influence on patient survival. This is whole-tissue IHC without explicit membrane scoring or surface-specific fractionation; feeds non-surface expression qualification. (https://pubmed.ncbi.nlm.nih.gov/23748645/)
  - *assay*: Human · glioblastoma · fixed
  > "The aim of this study was to determine the influence of Wnt5a and its receptors on the survival of glioblastoma patients and to determine reliable evaluation methods for immunohistochemistry. Diagnostic specimens from 41 histopathologically confirmed primary glioblastoma patients whose Gd-enhanced tumors had been totally removed were immunohistochemically stained for Wnt5a, Fzd2, Fzd6, and Ryk."
- `a1_evi_25` · *Secondary* · Ambiguous · Tissue Expression — RYK mRNA expression is significantly increased in glioblastoma tumors compared to normal tissue (RT-qPCR, p<0.0001), confirmed by Oncomine database. RNA-level upregulation without surface-specific validation; feeds non_surface_expression list. ([PMC5355113](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5355113/))
  - *assay*: Human · glioblastoma tumor tissue
  > "Expression of RYK mRNA was significantly increased in tumors compared to normal tissue ( p -value < 0.0001) (Figure 1A ), a trend confirmed by data obtained from the Oncomine database [ 18 ]( Supplementary Figure 1A )."
- `a1_evi_26` · *Primary* · Supports · Methodological — RYK siRNA knockdown in mesothelioma cells using ON-TARGETplus siRNA (Dharmacon L-003174-00-0005) at 50 nM. This genetic perturbation tool validates RYK as a functional target in mesothelioma and pairs with the progranulin/RYK surface-engagement claims from the same paper. ([PMC9720952](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9720952/))
  - *assay*: Human · mesothelioma cell lines
  > "Transient gene depletion was obtained by transfecting cells with ON-TARGET plus small interfering RNAs (siRNA) from Dharmacon (Lafayette, CO, USA) targeting GRN (progranulin) (L-009285–00-0005), EphA2 (L-003116–00-0005), PTK2 (FAK) (L-003164–00-0005), EphA7 (L-003119–00-0005), RYK (L-003174–00-0005) or non-targeting control siRNA (D-001810–10-05), using the Dharmafect transfection reagent according to the Manufacturer’s instruction. siRNAs targeting progranulin, PTK2 and EphA7 were used at the final concentration of 25 nM, siRNAs specific for EphA2 and RYK at 50 nM."
- `a2_evi_01` · *Primary* · Supports · Tissue Expression — RYK mRNA (3.4 kb transcript) is expressed in all human adult tissues examined, indicating ubiquitous baseline expression across the human body. (https://pubmed.ncbi.nlm.nih.gov/8390040/)
  - *assay*: Human · multiple adult human tissues · unspecified
  > "Expression of the 3.4 kb ryk mRNA was found in all human adult tissues examined."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — RYK transcript (3.0 kb) is expressed by Northern blot in heart, brain, lung, placenta, liver, skeletal muscle, kidney, and pancreas, with maximal expression in skeletal muscle. In situ hybridization further localizes RYK message to both epithelial and stromal compartments in brain, lung, colon, kidney, and breast. ([PMC2230112](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2230112/))
  - *assay*: Human · epithelial and stromal cells across multiple tissues · fixed
  > "A significant alteration in the catalytic domain is that the highly conserved "DFG" triplet in subdomain VII is altered to "DNA." The gene was mapped to chromosome 3q22. A single transcript of 3.0 kb is expressed in heart, brain, lung, placenta, liver, muscle, kidney, and pancreas by Northern analysis with maximal expression in skeletal muscle. In situ hybridization analysis on human tissues demonstrated localization of message in the epithelial and stromal compartment of tissues such as brain, lung, colon, kidney, and breast."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — RYK protein expression is minimal to absent on normal ovarian surface epithelium; in benign and borderline ovarian tumors expression is confined to the stromal compartment; in malignant ovarian tumors (n=24) expression shifts to predominantly epithelial compartment, indicating a disease-state-dependent redistribution of RYK between stromal and epithelial cell types. ([PMC2230112](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2230112/))
  - *assay*: Human · ovarian surface epithelium and stromal cells; ovarian tumor epithelium · fixed · permeabilized
  > "There was minimal to absent expression of H-RYK on surface epithelium of ovaries. In benign (3) and borderline tumors of the ovary (5), there was expression in the stromal compartment. However, in malignant tumors (24) there was increased expression predominantly confined to the epithelium. Polyclonal antisera raised against synthetic peptides recognize a 100-kD protein in ovarian cancer cells and other cell lines."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — RYK mRNA expression is significantly upregulated in glioblastoma multiforme (GBM) tumor samples (n=77) compared to normal brain tissue (n=23), with p<0.0001, indicating disease-state-induced overexpression in GBM. ([PMC5355113](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5355113/))
  - *assay*: Human · GBM tumor tissue vs normal brain · unspecified
  > "Expression of RYK mRNA was significantly increased in tumors compared to normal tissue ( p -value < 0.0001) (Figure 1A ), a trend confirmed by data obtained from the Oncomine database [ 18 ]( Supplementary Figure 1A )."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — RYK mRNA expression is higher in patient-derived glioblastoma stem cells (GSCs, n=6) compared to patient-derived GSCs induced to differentiate (n=6), indicating that RYK is preferentially expressed in the stem-like cell state within GBM. ([PMC5355113](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5355113/))
  - *assay*: Human · patient-derived glioblastoma stem cells (GSCs) vs differentiated GSCs · unspecified
  > "( B ) RYK's mRNA expression is greater in patient-derived GSCs ( n = 6) compared to patient-derived GSCs induced to differentiate ( n = 6)."
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — RYK protein expression in human glioma tissues (n=38) correlates positively with WHO histological grade, indicating progressive upregulation of RYK from low-grade to high-grade glioma. (https://pubmed.ncbi.nlm.nih.gov/24621529/)
  - *assay*: Human · glioma tumor tissue · fixed · permeabilized
  > "Furthermore, not only the expression of Wnt-5a but also that of Frizzled (Fz)-2 and Ryk was correlated with the WHO histological grade in 38 human glioma tissues. Taking these findings together, Fz-2 and Ryk could be therapeutic or pharmacological target molecules for the control of Wnt-5a-dependent invasion of human glioma in the near future."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — RYK protein is expressed in primary glioblastoma patient specimens (n=41 histopathologically confirmed cases), as assessed by immunohistochemistry on diagnostic tumor sections. (https://pubmed.ncbi.nlm.nih.gov/23748645/)
  - *assay*: Human · primary glioblastoma tumor specimens · fixed · permeabilized
  > "The aim of this study was to determine the influence of Wnt5a and its receptors on the survival of glioblastoma patients and to determine reliable evaluation methods for immunohistochemistry. Diagnostic specimens from 41 histopathologically confirmed primary glioblastoma patients whose Gd-enhanced tumors had been totally removed were immunohistochemically stained for Wnt5a, Fzd2, Fzd6, and Ryk."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — RYK expression is induced in astrocytes after spinal cord injury in both rodent and human spinal cord tissue, establishing RYK as an injury-upregulated cell-surface receptor in reactive astrocytes. ([PMC12012454](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12012454/))
  - *assay*: Human · reactive astrocytes in spinal cord · fixed · permeabilized
  > "We show here that the expression of a cell-surface receptor, Ryk, is induced in astrocytes after injury in both rodent and human spinal cords."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — In mouse spinal cord after injury, Ryk immunoreactivity is significantly increased at 1, 3, and 7 days post-injury and begins to decrease by 14 days, demonstrating a transient injury-induced upregulation of RYK in the lesion area. ([PMC12012454](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12012454/))
  - *assay*: Mouse · spinal cord lesion area (astrocytes and border region) · fixed · permeabilized
  > "Therefore, we examined Ryk expression in those areas and we found that Ryk was significantly increased 1 d, 3 d, and 7 d after spinal cord injury and started to decrease 14 d after injury ( Fig. 1 B )."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — RYK is expressed in lung mesenchymal tissues and functions as a WNT coreceptor acting as a cell survival and anti-inflammatory modulator; Ryk mutant mice exhibit lung hypoplasia, inflammation, and alveolar simplification, and mesenchyme-specific deletion recapitulates these phenotypes. ([PMC9214544](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9214544/))
  - *assay*: Mouse · lung mesenchymal cells · unspecified
  > "Here, starting with a forward genetic screen in mouse, we identify the WNT coreceptor Related to receptor tyrosine kinase (RYK) acting in mesenchymal tissues as a cell survival and antiinflammatory modulator. <i>Ryk</i> mutant mice exhibit lung hypoplasia and inflammation as well as alveolar simplification due to defective secondary septation, and deletion of <i>Ryk</i> specifically in mesenchymal cells also leads to these phenotypes."
- `a2_evi_11` · *Primary* · Supports · Tissue Expression — RYK expression is down-regulated in stromal cells of pneumonitis patient lungs compared to healthy lung tissue, indicating disease-state-dependent reduction of RYK in human lung stromal compartment during inflammatory disease. ([PMC9214544](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9214544/))
  - *assay*: Human · lung stromal cells · fixed · permeabilized
  > "Notably, RYK expression is down-regulated in the stromal cells of pneumonitis patient lungs."
- `a2_evi_12` · *Primary* · Supports · Tissue Expression — Epithelial-specific deletion of Ryk in mouse lung leads to goblet cell hyperplasia and mucus hypersecretion without lung inflammation, indicating that RYK is expressed and functionally required in lung epithelial cells for normal airway homeostasis. ([PMC9214544](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9214544/))
  - *assay*: Mouse · lung epithelial cells · unspecified
  > "Epithelial-specific deletion of Ryk leads to goblet cell hyperplasia and mucus hypersecretion without lung inflammation ( 14 )."
- `a2_evi_13` · *Primary* · Supports · Tissue Expression — RYK is identified as a functional receptor expressed on hepatocytes; hepatocyte-specific Ryk ablation protects mice against metabolic-associated steatohepatitis (MASH), establishing RYK as a hepatocyte-expressed surface receptor mediating ERK1/2 signaling in the context of liver metabolic disease. (https://pubmed.ncbi.nlm.nih.gov/41708863/)
  - *assay*: Mouse · hepatocytes · unspecified
  > "Using an unbiased screen of a cell-surface-displayed transmembrane protein library, we identified related to receptor tyrosine kinase (RYK) as a functional receptor for G-ECD. Hepatocyte-specific Ryk ablation protected mice against MASH and abolished the pathogenic effects of G-ECD. Mechanistically, G-ECD binding to RYK activated ERK1/2 signaling, resulting in transcriptional activation of PPARγ-CD36 and SREBP1C pathways that promote hepatic lipid uptake and lipogenesis."
- `a2_evi_14` · *Primary* · Supports · Tissue Expression — In nerve injury conduit (NIC) tissue from patients undergoing reconstructive surgery, RYK receptor is expressed by axons traversing the NIC, while Wnt5a is produced by Schwann cells, establishing a cell-type-specific expression pattern in peripheral nerve injury context. ([PMC8043392](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8043392/))
  - *assay*: Human · axons in nerve injury conduit · fixed · permeabilized
  > "Immunohistochemistry showed that Schwann cells in the NIC and in the injured nerve are the source of Wnt5a, whereas the Wnt5a receptor Ryk is expressed by axons traversing the NIC."
- `a2_evi_15` · *Primary* · Supports · Tissue Expression — RYK protein is present at adult glutamatergic synapses in mouse brain at 2, 4, and 6 months of age, co-localizing with PCP signaling components Celsr3 and Vangl2 at the synapse. ([PMC8373119](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8373119/))
  - *assay*: Mouse · glutamatergic synapses in adult brain · fixed · permeabilized
  > "We observed that the PCP components, Celsr3 and Vangl2, and the Wnt receptor, Ryk, are present in the adult glutamatergic synapses (at 2, 4, and 6 months of age)."
- `a2_evi_16` · *Primary* · Supports · Tissue Expression — RYK is required for amyloid-beta (Aβ)-induced synapse loss in Alzheimer's disease models; Ryk conditional knockout or function-blocking antibody protects synapses and preserves cognitive function in 5XFAD mice, indicating RYK is functionally active at synapses in the context of neurodegeneration. ([PMC8373119](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8373119/))
  - *assay*: Mouse · neurons in 5XFAD Alzheimer's disease model · unspecified
  > "Moreover, a Wnt receptor and regulator of PCP signaling, Ryk, is also required for Aβ-induced synapse loss."
- `a2_evi_17` · *Primary* · Supports · Tissue Expression — RYK is upregulated in neurons expressing mutant huntingtin (HTT) in multiple models of Huntington's disease (HD), indicating disease-state-induced overexpression of RYK in striatal neurons under HD pathology. ([PMC4068980](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4068980/))
  - *assay*: Mouse · striatal neurons expressing mutant huntingtin · unspecified
  > "We found that Ryk is up-regulated in neurons expressing mutant huntingtin (HTT) in several models of Huntington's disease (HD)."
- `a2_evi_18` · *Primary* · Supports · Tissue Expression — RYK is expressed on vascular endothelial cells (human coronary artery endothelial cells, HCAEC) and mediates Wnt5A-induced endothelial hyperpermeability through ROCK/LIMK2/CFL1 signaling; Ryk silencing completely prevents Wnt5A-induced permeability changes, establishing RYK as a functionally active surface receptor on vascular endothelium. ([PMC5308226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5308226/))
  - *assay*: Human · human coronary artery endothelial cells (HCAEC) · live · non-permeabilized
  > "Here we show that Wnt5A acts on the vascular endothelium causing enhanced permeability through Ryk interaction and downstream ROCK/LIMK2/CFL1 signaling. Wnt5A/Ryk signaling might provide novel therapeutic strategies to prevent capillary leakage in systemic inflammation and septic shock."
- `a2_evi_19` · *Primary* · Supports · Tissue Expression — RYK receptor is phosphorylated in cardiac endothelial cells upon exposure to HGF/IgG complexes (but not free HGF), and antibody blockade of RYK abolishes the enhanced vascular protection conferred by HGF/IgG complexes, demonstrating that RYK is a functionally accessible surface receptor on cardiac endothelial cells. ([PMC4565990](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4565990/))
  - *assay*: Human · cardiac endothelial cells · live · non-permeabilized
  > "Following reperfusion, preparations of HGF/IgG complexes provided greater vascular protection than free HGF with IgG. HGF/IgG complexes localized to blood vessels in vivo and increased HGF retention time after administration. In subsequent screens, we found that 'related to tyrosine kinase' (RYK) receptor was phosphorylated after exposure of cardiac endothelial cells to HGF/IgG complexes, but not to free HGF with IgG. The enhanced protection conferred by HGF/IgG complexes was lost after antibody blockade of RYK."
- `a2_evi_20` · *Primary* · Ambiguous · Surface Expression — In mesothelioma cells, RYK colocalizes with progranulin in distinct vesicular compartments as shown by immunofluorescence and proximity ligation assay, indicating that a fraction of RYK resides in intracellular vesicular/endosomal compartments rather than exclusively at the plasma membrane surface. ([PMC10393324](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10393324/))
  - *assay*: Human · mesothelioma cell lines · fixed · permeabilized
  > "However, the molecular mechanism regulating the functional interaction among progranulin, EGFR, and RYK are not known. In this study, we demonstrated that progranulin directly interacted with RYK by specific enzyme-linked immunosorbent assay (ELISA) (K<i><sub>D</sub></i> = 0.67). Using immunofluorescence and proximity ligation assay, we further discovered that progranulin and RYK colocalized in mesothelioma cells in distinct vesicular compartments."
- `a2_evi_21` · *Primary* · Supports · Surface Expression — In mesothelioma cells, progranulin promotes RYK ubiquitination and endocytosis preferentially through caveolin-1-enriched pathways, modulating RYK stability and surface availability; progranulin-dependent downstream signaling is sensitive to endocytosis inhibitors, indicating that RYK surface levels are dynamically regulated by ligand-induced internalization. ([PMC10393324](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10393324/))
  - *assay*: Human · mesothelioma cell lines · live · non-permeabilized
  > "Notably, progranulin-dependent downstream signaling was sensitive to endocytosis inhibitors, suggesting that it could depend on RYK or EGFR internalization. We discovered that progranulin promoted RYK ubiquitination and endocytosis preferentially through caveolin-1-enriched pathways, and modulated RYK stability. Interestingly, we also showed that in mesothelioma cells, RYK complexes with the EGFR, contributing to the regulation of RYK stability."
- `a2_evi_22` · *Primary* · Refutes · Surface Expression — In mutant huntingtin-expressing striatal cells, the RYK intracellular domain (Ryk-ICD) generated by γ-secretase cleavage is increased in the nucleus, and reducing γ-secretase PS1 levels compensates for full-length Ryk cytotoxicity, indicating that disease-state-induced γ-secretase cleavage shifts RYK from the plasma membrane to a nuclear ICD fragment in HD neurons. ([PMC4068980](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4068980/))
  - *assay*: Mouse · mutant huntingtin striatal cells · fixed · permeabilized
  > "Additionally, Ryk-ICD was increased in the nucleus of mutant htt cells, and reducing γ-secretase PS1 levels compensated for the cytotoxicity of full-length Ryk in these cells."
- `a2_evi_23` · *Primary* · Supports · Tissue Expression — Single-cell RNA sequencing and cell-cell communication analysis of RANKL-induced osteoclastogenesis reveals the WNT5a/RYK signaling axis as an extrinsic modulator of osteoclast progenitors derived from CD14+ CD16− monocytes, indicating RYK expression in monocyte/osteoclast progenitor populations. ([PMC10692129](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10692129/))
  - *assay*: Human · CD14+ CD16− monocytes / osteoclast progenitors from PBMCs · unspecified
  > "Furthermore, cell-cell communication analyses revealed extrinsic modulators of osteoclast progenitors including the IL7/IL7R and WNT5a/RYK axes."
- `a2_evi_24` · *Secondary* · Supports · Tissue Expression — In breast cancer cell lines, miR-7-5p targets RYK and reduces its expression, leading to reduced JNK phosphorylation; RYK expression is higher in highly invasive breast cancer cell lines, indicating RYK is expressed in breast cancer cells and its level correlates with invasive phenotype. ([PMC9549651](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9549651/))
  - *assay*: Human · breast cancer cell lines (high vs low invasiveness) · unspecified
  > "In terms of mechanism of action, miR-7-5p was found to target the RYK, leading to its reduced expression, which in turn caused a reduction in the phosphorylation level of the downstream factor JNK."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/RYK.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/RYK](https://surfaceome.deliverome.org/RYK)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/RYK.json](https://surfaceome.deliverome.org/data/surfaceome/RYK.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/RYK.md](https://surfaceome.deliverome.org/data/surfaceome/RYK.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P34925](https://alphafold.ebi.ac.uk/entry/P34925)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P34925](https://alphafold.ebi.ac.uk/api/prediction/P34925) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P34925](https://www.uniprot.org/uniprotkb/P34925)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-P34925-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-P34925-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-P34925-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-P34925-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-P34925-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-P34925-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*607 aa · `P34925` · embedded at build time*

```
   1  MRGAARLGRPGRSCLPGARGLRAPPPPPLLLLLALLPLLPAPGAAAAPAPRPPELQSASA
  61  GPSVSLYLSEDEVRRLIGLDAELYYVRNDLISHYALSFSLLVPSETNFLHFTWHAKSKVE
 121  YKLGFQVDNVLAMDMPQVNISVQGEVPRTLSVFRVELSCTGKVDSEVMILMQLNLTVNSS
 181  KNFTVLNFKRRKMCYKKLEEVKTSALDKNTSRTIYDPVHAAPTTSTRVFYISVGVCCAVI
 241  FLVAIILAVLHLHSMKRIELDDSISASSSSQGLSQPSTQTTQYLRADTPNNATPITSYPT
 301  LRIEKNDLRSVTLLEAKGKVKDIAISRERITLKDVLQEGTFGRIFHGILIDEKDPNKEKQ
 361  AFVKTVKDQASEIQVTMMLTESCKLRGLHHRNLLPITHVCIEEGEKPMVILPYMNWGNLK
 421  LFLRQCKLVEANNPQAISQQDLVHMAIQIACGMSYLARREVIHKDLAARNCVIDDTLQVK
 481  ITDNALSRDLFPMDYHCLGDNENRPVRWMALESLVNNEFSSASDVWAFGVTLWELMTLGQ
 541  TPYVDIDPFEMAAYLKDGYRIAQPINCPDELFAVMACCWALDPEERPKFQQLVQCLTEFH
 601  AALGAYV
```

### Alternative-isoform sequences

**P34925-2** (`P34925-2` · 610 aa)

```
   1  MRGAARLGRPGRSCLPGARGLRAPPPPPLLLLLALLPLLPAPGAAAAPAPRPPELQSASA
  61  GPSVSLYLSEDEVRRLIGLDAELYYVRNDLISHYALSFSLLVPSETNFLHFTWHAKSKVE
 121  YKLGFQVDNVLAMDMPQVNISVQGEVPRTLSVFRVELSCTGKVDSEVMILMQLNLTVNSS
 181  KNFTVLNFKRRKMCYKKLEEVKTSALDKNTSRTIYDPVHAAPTTSTRVFYISVGVCCAVI
 241  FLVAIILAVLHLHSMKRIELDDSISASSSSQGLSQPSTQTTQYLRADTPNNATPITSSLG
 301  YPTLRIEKNDLRSVTLLEAKGKVKDIAISRERITLKDVLQEGTFGRIFHGILIDEKDPNK
 361  EKQAFVKTVKDQASEIQVTMMLTESCKLRGLHHRNLLPITHVCIEEGEKPMVILPYMNWG
 421  NLKLFLRQCKLVEANNPQAISQQDLVHMAIQIACGMSYLARREVIHKDLAARNCVIDDTL
 481  QVKITDNALSRDLFPMDYHCLGDNENRPVRWMALESLVNNEFSSASDVWAFGVTLWELMT
 541  LGQTPYVDIDPFEMAAYLKDGYRIAQPINCPDELFAVMACCWALDPEERPKFQQLVQCLT
 601  EFHAALGAYV
```

### Canonical ortholog sequences

**Mouse — Ryk** (`Q01887` · 594 aa)

```
   1  MRAGRGGVPGSGGLRAPPPPLLLLLLAMLPAAAPRSPALAAAPAGPSVSLYLSEDEVRRL
  61  LGLDAELYYVRNDLISHYALSFNLLVPSETNFLHFTWHAKSKVEYKLGFQVDNFVAMGMP
 121  QVNISAQGEVPRTLSVFRVELSCTGKVDSEVMILMQLNLTVNSSKNFTVLNFKRRKMCYK
 181  KLEEVKTSALDKNTSRTIYDPVHAAPTTSTRVFYISVGVCCAVIFLVAIILAVLHLHSMK
 241  RIELDDSISASSSSQGLSQPSTQTTQYLRADTPNNATPITSSSGYPTLRIEKNDLRSVTL
 301  LEAKAKVKDIAISRERITLKDVLQEGTFGRIFHGILVDEKDPNKEKQTFVKTVKDQASEV
 361  QVTMMLTESCKLRGLHHRNLLPITHVCIEEGEKPMVVLPYMNWGNLKLFLRQCKLVEANN
 421  PQAISQQDLVHMAIQIACGMSYLARREVIHRDLAARNCVIDDTLQVKITDNALSRDLFPM
 481  DYHCLGDNENRPVRWMALESLVNNEFSSASDVWAFGVTLWELMTLGQTPYVDIDPFEMAA
 541  YLKDGYRIAQPINCPDELFAVMACCWALDPEERPKFQQLVQCLTEFHAALGAYV
```

**Cynomolgus — RYK** (`A0A2K5VQA5` · 610 aa)

```
   1  MRGAARLGRPGRSSLPGARGLRALPPPPPLLLLLALLPLLPAPGAAAPAPRPPELQSAAA
  61  GPSVSLYLSEDEVRRLIGLDAELYYVRNDLISHYALSFNLLVPSETNFLHFTWHAKSKVE
 121  YKLGFQVDNVLAMDMPQVNISVQGDVPRTLSVFRVELSCTGKVDSEVMILMQLNLTVNSS
 181  KNFTVLNFKRRKMCYKKLEEVKTSALDKNTSRTIYDPVHAAPTTSTRVFYISVGVCCAVI
 241  FLVAIILAVLHLHSMKRIELDDSISASSSSQGLSQPSTQTTQYLRADTPNNATPITSSLG
 301  YPTLRIEKNDLRSVTLLEAKAKVKDIAISRERITLKDVLQEGTFGRIFHGILIDEKDPNK
 361  EKQAFVKTVKDQASEIQVTMMLTESCKLRGLHHRNLLPITHVCIEEGEKPMVILPYMNWG
 421  NLKLFLRQCKLVEANNPQAISQQDLVHMAIQIACGMSYLARREVIHKDLAARNCVIDDTL
 481  QVKITDNALSRDLFPMDYHCLGDNENRPVRWMALESLVNNEFSSASDVWAFGVTLWELMT
 541  LGQTPYVDIDPFEMAAYLKDGYRIAQPINCPDELFAVMACCWALDPEERPKFQQLVQCLT
 601  EFHAALGAYV
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`P34925`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMM
 241  MMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIII
```

**P34925-2** (`P34925-2`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMM
 241  MMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIIIIII
```

**Mouse ortholog — Ryk** (`Q01887`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Cynomolgus ortholog — RYK** (`A0A2K5VQA5`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMM
 241  MMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence high — *
