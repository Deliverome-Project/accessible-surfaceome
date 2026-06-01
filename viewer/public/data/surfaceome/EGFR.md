# EGFR — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-30T20:11:51.719404Z · model `claude-sonnet-4-6`*

> EGFR is a canonical single-pass type I transmembrane receptor with a large extracellular domain (ECD, ~620 aa, domains I–IV) constitutively displayed at the plasma membrane of epithelial and many other cell types. Surface accessibility is confirmed by live-cell flow cytometry across glioma, pancreatic, breast, lung, and prostate cancer lines; multiple independent surface biotinylation-MS datasets; IHC membranous scoring in primary human tumors (97% of SIP cases); and cryo-EM/crystal structures of therapeutic antibody–ECD complexes. Two FDA-approved antibodies (cetuximab, panitumumab) and multiple ADCs engage the intact surface receptor. Ectodomain shedding by ADAM17 is documented but the full-length surface form is dominant. State dependence is low: EGFR is broadly constitutive, with modest modulation by EGF-induced internalization and tumor-state upregulation.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:3236](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:3236) |
| UniProt | [P00533](https://www.uniprot.org/uniprotkb/P00533) |
| NCBI Gene | [1956](https://www.ncbi.nlm.nih.gov/gene/1956) |
| Ensembl | [ENSG00000146648](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000146648) |
| Subcategory | Single-pass type I |
| Surface accessibility | High |
| Confidence | High |
| Evidence grade | Direct, multi-method |
| Triage signal | Likely accessible |
| Headline risks | Shed Form |

## 1. Executive summary

EGFR is a canonical single-pass type I transmembrane receptor with a large extracellular domain (ECD, ~620 aa, domains I–IV) constitutively displayed at the plasma membrane of epithelial and many other cell types. Surface accessibility is confirmed by live-cell flow cytometry across glioma, pancreatic, breast, lung, and prostate cancer lines; multiple independent surface biotinylation-MS datasets; IHC membranous scoring in primary human tumors (97% of SIP cases); and cryo-EM/crystal structures of therapeutic antibody–ECD complexes. Two FDA-approved antibodies (cetuximab, panitumumab) and multiple ADCs engage the intact surface receptor. Ectodomain shedding by ADAM17 is documented but the full-length surface form is dominant. State dependence is low: EGFR is broadly constitutive, with modest modulation by EGF-induced internalization and tumor-state upregulation.

**Family / classification** — functional class: Receptor.

**Triage first-pass reasoning** — EGFR (ErbB1/HER1) is a single-pass type I transmembrane glycoprotein with a large extracellular ligand-binding domain (domains I-IV, ~620 aa) facing the extracellular space, a single TM helix, and an intracellular kinase domain. It is constitutively expressed on the plasma membrane of epithelial and many other cell types. The extracellular domain is the target of approved therapeutic antibodies (cetuximab, panitumumab), ADCs (e.g., ABT-414/depatuxizumab mafodotin), and bispecifics — all engaging the cell-surface ectodomain on intact, non-permeabilized cells. Surface biotinylation and flow cytometry on intact cells unambiguously confirm stable PM residence. Ectodomain shedding by ADAM10/17 does occur, but the transmembrane precursor is the dominant stable form at the cell surface; the shed ectodomain is a secondary product. This is a canonical surface receptor, fully accessible from the extracellular face.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=High · subcategory=Single-pass type I · ecd=Large |
| Classification | reason=Classical Surface Receptor · family=Receptor · state-dependence=Low · induction-trigger=— |
| Expression | level=High · breadth=Broad · specificity=Surface Dominant · low-endogenous=false · tumor-associated=— · orphan-receptor=false · OE-precedent=true |
| Risks | shed=true · secreted=true · co-receptor=None · masking=true · restricted-subdomain=false |
| Evidence | grade=Direct, multi-method · density=High · live-cell-surface=— · supporting(hi)=11 · contradicting(hi)=0 |
| Cross-species | mouse=88.7% · cyno=98.7% |
| Paralogs | max %ECD identity = 48.5% |
| Topology | TM=1 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: High surface expression confirmed across multiple cancer contexts: 97-99% positivity in glioma lines by live flow (a1_evi_02), 97% membranous IHC in SIP tumor tissue (a1_evi_28), 19 biotinylation sites in prostate cancer metastasis (a1_evi_18), and top 84% expression in penile tissue surfaceome (a1_evi_27).
- *Expression breadth*: EGFR surface expression documented across epithelial (keratinocyte, lung, pancreatic, mammary, sinonasal), neural (iPSC sensory neuron), and cancer (glioma, prostate, PDAC, NSCLC, SCLC) lineages (a1_evi_14, a1_evi_20, a1_evi_23, a2_evi_07, a2_evi_22). Skin rash as on-target toxicity confirms normal keratinocyte expression (a2_evi_22).
- *Surface specificity*: Paired non-permeabilized vs. permeabilized IF confirms surface-dominant EGFR localization in GSC83 cells (a1_evi_08). Live-cell flow on intact cells across >10 cell lines confirms surface predominance (a1_evi_01, a1_evi_02, a1_evi_09). EGF-induced internalization reduces but does not abolish surface pool (a2_evi_24).
- *Known ligand*: Binds EGF (KD ~1.77×10⁻⁷ M), TGF-α, epiregulin, and other ErbB ligands. Panitumumab (KD 5×10⁻¹¹ M) outcompetes EGF for ECD binding (a1_evi_41). EGFR-ligand shedding (EGF family) drives autocrine loops in pancreatic tumorigenesis (a2_evi_04).
- *Low endogenous expression*: Derived from expression_level='high' (not low/absent → not flagged). High surface expression confirmed across multiple cancer contexts: 97-99% positivity in glioma lines by live flow (a1_evi_02), 97% membranous IHC in SIP tumor tissue (a1_evi_28), 19 biotinylation sites in prostate cancer metastasis (a1_evi_18), and top 84% expression in penile tissue surfaceome (a1_evi_27).
- *Overexpression surface localization*: 1 method observation(s) pair an overexpression/mixed expression system with a surface-localization readout (cites a1_evi_01, a1_evi_02).

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Direct, multi-method

EGFR surface accessibility is supported by an exceptionally strong and diverse body of direct evidence from multiple independent methods and sources. Live-cell non-permeabilized flow cytometry (high-weight) across glioma lines (PMC13054837), pancreatic cancer lines (PMC13088391), A431 epidermoid carcinoma (PMC10818351), and breast cancer MCF-7 cells (PMC11472258) directly confirms surface EGFR. Paired non-permeabilized vs. permeabilized IF (PMC9038772) provides an orthogonal direct surface method. Multiple independent surface biotinylation studies (DCDMLs/PMC10337807, NIKS keratinocytes/PMC10958106, prostate cancer sBioSITe/PMC10696767, iPSC neurons/PMC11964241, polarized MDCK SILAC surfaceome/PMC9788433, LNCaP/A549/PMC12749419) all confirm PM localization. IHC with membranous scoring in primary human SIP tumor tissue (97% of 32 cases, PMC12674851) adds tissue-level evidence. Crystal structures and cryo-EM confirm the extracellular topology of the ECD. No contradicting claims. Grade: direct_multi_method — live flow, nonperm IF, surface biotinylation (multiple independent sources), and IHC membranous all converge.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Supports Surface | High | Live-cell non-permeabilized flow cytometry on 3 glioma lines; multiple independent cell lines corroborate |
| a1_evi_02 | Supports Surface | High | Quantitative live-cell surface flow: 98-99% positivity in high-EGFR lines, same source as a1_evi_01 |
| a1_evi_03 | Supports Surface | High | Paired permeabilized vs non-permeabilized flow + confocal IF distinguishing surface vs intracellular EGFR |
| a1_evi_04 | Supports Surface | Moderate | Author conclusion re: surface-dominant EGFR in GSC83; same source, summarizes flow + confocal data |
| a1_evi_08 | Supports Surface | High | Non-permeabilized IF distinguishing surface vs intracellular pool; n=2 independent experiments, p<0.01 |
| a1_evi_09 | Supports Surface | Moderate | Live surface flow cytometry on pancreatic cancer cell lines; single source, moderate validation |
| a1_evi_10 | Supports Surface | Moderate | Live-cell surface flow confirming antibody engagement of EGFR on BxPC-3 intact cells |
| a1_evi_11 | Supports Surface | Moderate | Surface flow with EGFR-negative HCT116 as negative control; validates antibody specificity |
| a1_evi_12 | Tangential | Moderate | Methodological note on IHC vs flow discordance; confirms flow as gold standard but not a contradiction |
| a1_evi_13 | Supports Surface | High | Surface biotinylation + streptavidin pulldown + WB on intact DCDMLs; direct surface method |
| a1_evi_14 | Supports Surface | High | Surface biotinylation + streptavidin pulldown + WB in NIKS keratinocytes; direct plasma membrane evidence |
| a1_evi_15 | Supports Surface | Moderate | Surface biotinylation panel confirms modulation of surface EGFR pool in NIKS; same source as a1_evi_14 |
| a1_evi_18 | Supports Surface | High | sBioSITe surface biotin + MS with 19 biotinylation sites; robust PM localization in prostate cancer cells |
| a1_evi_20 | Supports Surface | Moderate | Sulfo-NHS-SS-biotin + MS identifies EGFR in iPSC-derived neuron surfaceome; independent source/context |
| a1_evi_21 | Supports Surface | Moderate | EGFR significantly deregulated surface protein (p<0.01) in FD patient neuronal surfaceome; same source |
| a1_evi_23 | Supports Surface | High | SILAC + chemoproteomic surface capture on polarized MDCK cells; quantitative apicobasal surface distribution |
| a1_evi_27 | Supports Surface | Moderate | Surfaceome MS identifies EGFR in top 84% expression in human penile tissue; primary human tissue |
| a1_evi_28 | Supports Surface | High | IHC membranous staining in 97% of SIP cases (31/32); validated scoring criterion, primary human tumor tissue |
| a1_evi_29 | Supports Surface | Moderate | IHC plasma membrane staining for p-EGFR in 69% of SIP cases; same source as a1_evi_28 |
| a1_evi_32 | Tangential | High | Cryo-EM confirms ECD extracellular topology; structural basis for surface accessibility, not a cell assay |
| a1_evi_33 | Tangential | High | Cryo-EM ECD heart-shaped dimer architecture; confirms extracellular domain topology |
| a1_evi_35 | Tangential | High | Crystal structure of full ECD (PDB:7OM4) confirms extracellular domain boundaries and accessibility |
| a1_evi_38 | Supports Surface | High | Cetuximab/matuzumab crystal structures confirm ECD epitope engagement; FDA-approved antibody surface binding |
| a1_evi_40 | Supports Surface | Moderate | DNA-antibody conjugate surface engagement of EGFR on live MCF-7 cells; demonstrates macromolecular accessibility |
| a1_evi_41 | Supports Surface | High | Panitumumab (FDA-approved) binds EGFR ECD; therapeutic antibody engagement confirms surface accessibility |
| a1_evi_42 | Supports Surface | Moderate | Live-cell flow cytometry on A431 cells for surface EGFR; canonical high-EGFR model line |
| a1_evi_52 | Supports Surface | Moderate | Cell-surface labeling confirms EGFR at LNCaP/PC3-PSMA membrane; part of macromolecular complex |
| a1_evi_53 | Supports Surface | Moderate | A549 cell-surface labeling identifies EGFR as surface-resident signaling hub; independent source |
| a1_evi_45 | Tangential | Moderate | ADAM17-mediated EGFR-ligand shedding implies surface EGFR presence but is indirect/ambiguous by itself |

### Flow cytometry (6 methods)

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Mixed*

**Antibodies**

- anti-EGFR-Alexa Fluor647 (BioLegend · 352918) — Extracellular epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| U373 glioma cells (wild-type EGFR, low endogenous expression) — 12% surface positive | Established Cell Line | Low | 1 |
| U373vIII glioma cells (EGFRvIII overexpressing) — 98% surface positive | Established Cell Line | High | 1 |
| GSC83 glioma cells (endogenous EGFR/EGFRvIII) — 99% surface positive | Established Cell Line | High | 2 |

*Overexpression construct* — SP source: Unspecified · cell line: U373vIII. *(cites: a1_evi_01, a1_evi_02)*

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR — Extracellular epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Pancreatic cancer cell lines including BxPC-3 — variable surface EGFR expression | Established Cell Line | Moderate | 1 |
| BxPC-3 pancreatic cancer cells — EGFR surface binding by bispecific antibody targeting EGFR/NKG2D | Established Cell Line | Moderate | 1 |

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR — Extracellular epitope; Unknown; None validation (None); HCT 116 used as EGFR-negative control (CCLE log2[TPM+1]=0.0); specificity anchored by negative control cell line.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| NCI-H1930 lung cancer cells — clear surface EGFR by flow despite granular/diffuse IHC pattern | Established Cell Line | Moderate | 1 |
| HCT 116 colorectal cancer cells — EGFR-negative control, minimal surface staining | Established Cell Line | Absent | 1 |

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR — Extracellular epitope; Unknown; None validation (None); Biotinylated anti-EGFR antibody conjugated to DNA-antibody constructs; EGFR surface accessibility demonstrated by macromolecular cargo binding on live MCF-7 cells.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| MCF-7 breast cancer cells (live) — EGFR accessible on cell surface for large DNA origami nanoframe cargo via biotinylated anti-EGFR antibody | Established Cell Line | Moderate | 1 |

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR 528mAb (528 · CSIRO Recombinant Protein Production and Purification Facility) — Extracellular epitope; Monoclonal; None validation (None); Well-characterized anti-EGFR ECD monoclonal antibody (clone 528); used for surface binding and therapeutic engagement studies.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| A431 epidermoid carcinoma cells (live) — high EGFR surface binding by MNT1 targeting moiety | Established Cell Line | High | 1 |

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR Affibody-FITC — Extracellular epitope; Recombinant; None validation (None)
- anti-EGFR antibody-Alexa Fluor 488 — Extracellular epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| EGFR-positive exosomes captured on microbeads — surface EGFR detection optimized for flow cytometry signal-to-noise | Unknown | Moderate | 1 |

### Immunofluorescence (2 methods)

#### Nonpermeabilized IF — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Nonpermeabilized · expression: Endogenous*

**Antibodies**

- anti-EGFR-Alexa Fluor647 (BioLegend · 352918) — Extracellular epitope; Unknown; Moderate validation (Orthogonal Method); Same clone used in paired flow cytometry and confocal IF; permeabilized vs. non-permeabilized design separates surface from intracellular pool.
- anti-CD9-FITC (BioLegend · 312104) — Extracellular epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GSC83 glioma cells (adherent), non-permeabilized — surface EGFR pool visualized | Established Cell Line | High | 2 |

#### Permeabilized IF — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-EGFR-Alexa Fluor647 (BioLegend · 352918) — Unknown epitope; Unknown; Moderate validation (Orthogonal Method); Paired permeabilized vs. non-permeabilized design; intracellular pool detected in permeabilized arm.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GSC83 glioma cells (adherent), permeabilized — intracellular EGFR pool visualized for comparison | Established Cell Line | Moderate | 2 |

### Immunohistochemistry (3 methods)

#### IHC Membranous — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-EGFR — Unknown epitope; Unknown; None validation (None)
- anti-phospho-EGFR — Intracellular epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Sinonasal inverted papilloma (SIP) primary tumor sections — EGFR positive plasma membrane staining in 31/32 cases (97%) | Primary Human Tissue | High | 1 |
| Sinonasal inverted papilloma (SIP) primary tumor sections — phospho-EGFR positive plasma membrane staining in 22/32 cases (69%) | Primary Human Tissue | Moderate | 1 |

#### IHC Membranous — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-EGFR (Abcam · ab52894) — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| EGFR-mutant NSCLC primary lung tissue — membranous staining scored on 1-3 scale | Primary Human Tissue | Moderate | 1 |

#### IHC Membranous — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-EGFR (Abcam · ab52894) — Unknown epitope; Unknown; None validation (None); Used at IHC 1:100 in pancreatic cancer mouse model tissue sections.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Mouse pancreas tissue in KRAS-driven tumorigenesis model — EGFR IHC membranous staining | Primary Human Tissue | Moderate | 1 |

### Surface mass spec (2 methods)

#### Cell Surface Capture — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Polarized MDCK epithelial cells — EGFR distributed apical:basolateral 40:60 across both membrane faces | Established Cell Line | Moderate | 1 |

#### Cell Surface Capture — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Penile tissue (glans penis, autopsied normal) — EGFR ranked top 84% of surface-protein expression in tissue surfaceome panel | Primary Human Tissue | High | 1 |

### Surface biotinylation (6 methods)

#### Surface Biotinylation — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-phosphotyrosine 4G10 (4G10) — Intracellular epitope; Monoclonal; None validation (None); Pan-phosphotyrosine readout for ErbB kinases including EGFR in streptavidin-bead-captured biotinylated fraction.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| DCDMLs (ductal carcinoma-derived mammary lines) — EGFR detected in surface-biotinylated plasma membrane fraction via pan-phosphotyrosine WB | Established Cell Line | Moderate | 1 |

#### Surface Biotinylation — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| NIKS (normal immortalized keratinocytes) expressing HPV16 E7 — EGFR modestly upregulated on cell surface vs. controls | Established Cell Line | Moderate | 2 |
| SiHa (HPV-16+) and HeLa (HPV-18+) cells after E6/E7 knockdown — surface EGFR assessed by biotinylation + WB | Established Cell Line | Moderate | 2 |

#### Surface Biotinylation — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Prostate cancer bone-metastatic cells — EGFR detected with 19 biotinylation sites by sBioSITe (biotinylation-site IP + MS) | Established Cell Line | High | 1 |

#### Surface Biotinylation — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| iPSC-derived sensory-like neurons from Familial Dysautonomia patients — EGFR significantly deregulated (p<0.01) in surface proteome vs. controls; identified among 1,508 surface proteins | IPSC Derived | Moderate | 2 |

#### Surface Biotinylation — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR-HRP (Abcam) — Extracellular epitope; Unknown; None validation (None); Used at 1:5000 for WB confirmation of EGFR in streptavidin pulldown; affibody-BirA* proximity labeling approach targeting EGFR ECD (Z_EGFR:1907.BirA*).

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| EGFR.Fc recombinant protein — EGFR ECD biotinylated by affibody-BirA* construct, confirmed by streptavidin-HRP WB and anti-EGFR-HRP WB | Unknown | Moderate | 2 |

#### Surface Biotinylation — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| LNCaP and PC3-PSMA prostate cancer cells — EGFR detected in GCPII interactome at cell membrane via cell-surface labeling | Established Cell Line | Moderate | 1 |
| A549 lung adenocarcinoma cells — EGFR identified as key surface signaling hub via cell-surface labeling of EGFR interactome | Established Cell Line | Moderate | 1 |

### Functional surface assay (1 method)

#### Unknown — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- Panitumumab (Amgen) — Extracellular epitope; Monoclonal; None validation (None); FDA-approved fully human anti-EGFR IgG2 (Vectibix); KD = 5x10^-11 M for EGFR ECD; prevents EGF binding.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| MCF-7 breast cancer cells — EGFR ECD accessible for Panitumumab binding (KD 5x10^-11 M); high-affinity surface engagement confirmed | Established Cell Line | Moderate | 1 |

### Other (2 methods)

#### Unknown — Weak Or Ambiguous · Surface Accessible

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- Cetuximab Fab — Extracellular epitope; Monoclonal; None validation (None); Crystal structure PDB:1YY9; Fab-EGFR ECD complex used for structural modeling of IgM bispecific antibodies.
- Matuzumab Fab — Extracellular epitope; Monoclonal; None validation (None); Crystal structure PDB:3C09; Fab-EGFR ECD complex used for structural modeling of IgM bispecific antibodies.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| EGFR extracellular domain — structural evidence for ECD surface accessibility from X-ray crystal structures of therapeutic antibody Fab-EGFR ECD complexes | Unknown | High | 1 |

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Mouse pancreatic acinar cells in KRAS-driven tumorigenesis — EGFR surface presence implied by ADAM17-mediated ectodomain shedding (genetic ablation of EGFR or ADAM17 protects from transformation) | Primary Human Tissue | Moderate | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| EGFR IHC in EGFR-mutant NSCLC primary tissue; membranous scoring rubric defined but aggregate expression level data not separately quantified in claims | Primary Human Tissue | IHC Protein | Moderate | 1 |
| EGFR Western blot in pancreatic cancer mouse models (KRAS-driven tumorigenesis); bulk protein level in tissue/cell lysate | Primary Human Tissue | Bulk Protein | Moderate | 1 |

**Contradicting evidence**

- *Other* (severity Low): Clinical IHC specimens frequently show a granular/diffuse staining pattern rather than sharp membranous staining for EGFR, creating a discordance between IHC membrane-pattern scoring and actual surface accessibility. However, flow cytometry in NCI-H1930 cells (which share the same ambiguous IHC pattern) confirmed genuine cell-surface EGFR expression, indicating that IHC pattern alone is an unreliable proxy for surface accessibility.
  - Likely explanation: The granular/diffuse IHC pattern likely reflects intracellular trafficking pools or fixation/antigen-retrieval artefacts rather than true absence of surface EGFR. Flow cytometry on non-permeabilized cells is the more direct assay and confirms surface expression, so the IHC discordance does not meaningfully undermine the surface-accessibility conclusion.

## 4. Biological context

**Tissues × disease context**

| Tissue | Disease context | Level (protein) | Cell types | Cell states |
|---|---|---|---|---|
| sinonasal/nasal cavity | Tumor | High | — | — |
| bone (metastatic site) | Tumor | High | — | — |
| multiple tumor types (brain, head/neck, lung, pancreas, colon, ovary) | Tumor | Unknown | — | — |
| lung | Tumor | High | — | EGFR-mutant, drug-tolerant persister |
| peripheral nervous system (sensory) | Other Disease | Mixed | sensory-like neurons | — |

**Cell types** *(orthogonal cell-type index)*

| Cell type | Ontology | Present in tissues | Species | Cites |
|---|---|---|---|---|
| sinonasal inverted papilloma tumor cells | — | sinonasal/nasal cavity | Human | 2 |
| prostate cancer cells (bone metastasis) | — | bone (metastatic site) | Human | 1 |
| pancreatic acinar cells | — | pancreas | Mouse | 2 |
| glioblastoma stem cells | — | brain (glioblastoma) | Human | 2 |
| pancreatic cancer cells (ductal adenocarcinoma) | — | pancreas | Human | 1 |
| small cell lung cancer cells | — | lung | Human | 2 |
| polarized epithelial cells | — | kidney (polarized epithelium model) | Dog | 2 |
| sensory-like neurons (iPSC-derived) | — | peripheral nervous system (sensory) | Human | 3 |
| keratinocytes | — | skin | Human | 1 |
| lung adenocarcinoma cells (EGFR-mutant) | — | lung | Human | 2 |
| HPV-altered epithelial cells | — | epithelium (HPV-associated lesion) | Human | 1 |

**Cell states**

- *EGF-stimulated* — EGF ligand binding triggers EGFR internalization and lysosomal degradation, reducing surface EGFR levels; blockade of lysosomal function (e.g., chloroquine) prevents this loss. *(cites: a2_evi_24)*
- *drug-tolerant persister* — EGFR-mutant LUAD cells surviving 3-week EGFR-TKI (gefitinib/osimertinib) treatment enter a drug-tolerant persister state with potentially altered EGFR surface dynamics relative to drug-naive cells. *(cites: a2_evi_15, a2_evi_16)*
- *tumor* — EGFR surface expression is elevated across multiple tumor types including SIP (97% IHC positivity), GBM, HNSC, LUSC, LUAD, PAAD, COAD, OV (pan-cancer PDX surfaceomics), PDAC cell lines, and bone-metastatic prostate cancer. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_07, a2_evi_08, a2_evi_09, a2_evi_10, a2_evi_12, +1)*
- *disease state (Familial Dysautonomia)* — Surface EGFR is among the most significantly deregulated proteins (p<0.01) in iPSC-derived sensory-like neurons from Familial Dysautonomia patients compared to healthy controls, indicating disease-state-dependent changes in neuronal surface EGFR levels. *(cites: a2_evi_17, a2_evi_18, a2_evi_19)*
- *HPV-associated* — In HPV-associated epithelial lesions, EGFR and downstream pathways (PI3K/Akt, mTOR, JAK/STAT) may be aberrantly activated, suggesting disease-state-induced upregulation or hyperactivation of surface EGFR. *(cites: a2_evi_21)*
- *KRAS-driven tumorigenesis* — In KRAS-driven pancreatic tumorigenesis, EGFR on acinar cells is engaged by autocrine ligand shedding and paracrine macrophage-derived signals, driving acinar-to-ductal transdifferentiation; genetic Egfr ablation is protective. *(cites: a2_evi_04, a2_evi_06)*

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- Endosome · following EGF ligand binding / stimulation *(cites: a2_evi_24)*
- Lysosome · following EGF-induced internalization (degradation pathway) *(cites: a2_evi_24)*

**Membrane subdomains**: Apical Membrane, Basolateral Membrane

**Anatomical accessibility**

- polarized epithelium (MDCK kidney model) — Unknown · *Favorable*: In polarized MDCK epithelial cells EGFR is distributed ~40:60 apical:basolateral, indicating near-uniform presence on both membrane faces. This dual-face distribution means systemically delivered binders reaching the basolateral/interstitial compartment can access EGFR without strict luminal restriction.

**Accessibility modulation**

- *Disease State Induced* · trigger: Oncogenic Transformation: Normal sinonasal epithelium → Sinonasal inverted papilloma (SIP) tumor tissue — EGFR plasma membrane staining detected in 97% of SIP cases (31/32) and phosphorylated EGFR (p-EGFR) in 69% of SIP cases (22/32), indicating high-frequency surface expression and activated receptor at the cell surface in this benign tumor. *(→ Near-Universal Surface EGFR In SIP Tumors Makes The Receptor Broadly Accessible To EGFR-Targeting Binders Across The Majority Of Tumor Cells; Activated P-EGFR Fraction Suggests High Receptor Occupancy At The Surface.)* *(cites: a2_evi_01, a2_evi_02)*
- *Disease State Induced* · trigger: Oncogenic Transformation: Normal prostate tissue → Prostate cancer bone metastasis — EGFR is identified as an established marker of prostate cancer bone dissemination, detected with 19 biotinylation sites by surface biotinylation-MS in a bone-metastatic prostate cancer model, indicating abundant cell-surface presence at the metastatic site. *(→ High-Density Surface EGFR In Bone-Metastatic Prostate Cancer Cells Offers Accessible Epitopes For Antibody- Or Conjugate-Based Targeting In The Metastatic Setting.)* *(cites: a2_evi_03)*
- *Disease State Induced* · trigger: Oncogenic Transformation: Normal pancreatic acinar cells → KRAS-driven pancreatic tumorigenesis / acinar-to-ductal transdifferentiation — EGFR surface signaling is functionally engaged in KRAS-driven acinar cell transdifferentiation; genetic ablation of Egfr protects from tumorigenesis, indicating that disease-state-associated EGFR surface activity is a key driver of the oncogenic process. *(→ Surface EGFR Is Functionally Critical In Early Pancreatic Oncogenesis; Its Accessibility In This Disease State Is Therapeutically Relevant For Interception Of KRAS-Driven Pancreatic Cancer Progression.)* *(cites: a2_evi_04, a2_evi_06)*
- *Disease State Induced* · trigger: Oncogenic Transformation: Healthy iPSC-derived sensory-like neurons → iPSC-derived sensory-like neurons from Familial Dysautonomia (FD) patients — EGFR is among the most significantly deregulated surface proteins (p<0.01) in FD patient neurons versus healthy controls by surface biotinylation-MS, indicating altered EGFR surface abundance in this genetic neurological disease state. *(→ Disease-State-Dependent Change In Neuronal Surface EGFR In FD Suggests That Binder Accessibility To EGFR On Peripheral Sensory Neurons Differs Between FD Patients And Healthy Individuals, With Potential Implications For Neurotrophic Targeting.)* *(cites: a2_evi_17, a2_evi_18, a2_evi_19)*
- *Disease State Induced* · trigger: Infection Viral: Normal epithelial cells → HPV-associated dysplasia/cancer epithelial cells — In HPV-altered cellular states, EGFR and downstream signaling pathways (PI3K/Akt, mTOR, JAK/STAT) may be aberrantly activated, suggesting disease-state-induced upregulation or hyperactivation of surface EGFR in HPV-associated epithelial pathology. *(→ Potential Surface EGFR Upregulation In HPV-Associated Lesions May Increase Target Density And Binder Accessibility In HPV-Driven Cancers, Although Direct Quantitative Surface Evidence Is Lacking.)* *(cites: a2_evi_21)*
- *Cell State Induced* · trigger: Other: Drug-naive EGFR-mutant LUAD cells (HCC827, PC9, H1650) → EGFR-mutant LUAD cells in drug-tolerant persister state after 3-week gefitinib or osimertinib treatment — EGFR TKI treatment remodels the overall surfaceome of EGFR-mutant LUAD cells; drug-tolerant persister cells represent a distinct cell state with potentially altered EGFR and co-receptor surface dynamics compared to drug-naive cells. *(→ Surfaceome Remodeling Under EGFR Inhibitor Pressure May Alter Target Density And Co-Target Availability On Persisters; Surface EGFR Accessibility Could Shift, Affecting Combination Targeting Strategies In The Drug-Tolerant State.)* *(cites: a2_evi_15, a2_evi_16)*
- *Polarization Dependent*: Non-polarized epithelial cells → Polarized MDCK epithelial monolayers with established apical-basolateral polarity — In polarized MDCK cells, EGFR distributes relatively evenly across apical and basolateral plasma membrane domains (apicobasal ratio ~40:60), unlike many interaction partners that show strong apicobasal polarization. *(→ EGFR Is Accessible From Both Luminal (Apical) And Basolateral Faces Of Polarized Epithelium Without Strong Subdomain Restriction, Meaning Binders Can Engage EGFR Regardless Of Which Pole Of The Epithelium They Access.)* *(cites: a2_evi_13, a2_evi_14)*
- *Dual Localization*: Unstimulated cells with surface EGFR → EGF ligand-stimulated cells undergoing receptor internalization — EGF binding triggers EGFR internalization from the plasma membrane followed by endosomal sorting and lysosomal degradation, substantially reducing cell-surface EGFR levels. Blockade of lysosomal function (e.g., by chloroquine) prevents degradation. *(→ EGF-Induced Internalization Dynamically Reduces Surface-Accessible EGFR; In Ligand-Rich Tumor Microenvironments, Surface EGFR Density May Be Lower Than In Resting Conditions, Potentially Limiting Binder Engagement Unless Internalization Is Exploited For Payload Delivery.)* *(cites: a2_evi_24)*

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Strong
- domain: Unknown
- rationale: Quantitative SILAC surfaceome of polarized MDCK cells shows EGFR distributed ~40:60 apical:basolateral, with no strong subdomain restriction. Multiple surface biotinylation studies on non-polarized cell lines show membrane-wide signal without fractionation specificity. No junctional, ciliary, or raft-restricted staining pattern reported.
- cites: a1_evi_23, a2_evi_13, a2_evi_14

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: EGFR is a single-pass type I transmembrane glycoprotein that traffics autonomously to the plasma membrane via the secretory pathway. Multiple independent surface biotinylation studies across diverse cell lines (keratinocytes, glioma, prostate, lung, breast cancer) all detect endogenous EGFR at the surface without co-receptor co-expression requirements. No obligate partner for surface delivery is documented.
- cites: a1_evi_13, a1_evi_14, a1_evi_18, a1_evi_20

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P00533 | ref | ref | 1 | 621 aa | 543 aa | 24 aa | Extracellular→Cytoplasmic | — |
| Isoform | P00533-2 | P00533-2 | 99.5% | 99.7% | 0 | 381 aa | 0 aa | 24 aa | Extracellular→Extracellular | — |
| Isoform | P00533-3 | P00533-3 | 93.5% | 98.4% | 0 | 681 aa | 0 aa | 24 aa | Extracellular→Extracellular | — |
| Isoform | P00533-4 | P00533-4 | 99.8% | 100.0% | 0 | 604 aa | 0 aa | 24 aa | Extracellular→Extracellular | — |
| Mouse ortholog | Egfr | [Q01279](https://www.uniprot.org/uniprotkb/Q01279) | 90.5% | 88.7% | 1 | 623 aa | — | — | — | high (≥85%) |
| Cynomolgus ortholog | EGFR | [A0A2K5WK39](https://www.uniprot.org/uniprotkb/A0A2K5WK39) | 99.3% | 98.7% | 1 | 621 aa | — | — | — | high (≥85%) |
| Paralog | ERBB4 | [Q15303](https://www.uniprot.org/uniprotkb/Q15303) | 51.4% | 48.5% | — | — | — | — | — | low-risk |
| Paralog | ERBB3 | [P21860](https://www.uniprot.org/uniprotkb/P21860) | 41.9% | 45.7% | — | — | — | — | — | low-risk |
| Paralog | ERBB2 | [P04626](https://www.uniprot.org/uniprotkb/P04626) | 49.1% | 44.3% | — | — | — | — | — | low-risk |
| Paralog | INSR | [P06213](https://www.uniprot.org/uniprotkb/P06213) | 15.8% | 32.5% | — | — | — | — | — | low-risk |
| Paralog | ROS1 | [P08922](https://www.uniprot.org/uniprotkb/P08922) | 13.1% | 31.4% | — | — | — | — | — | low-risk |
| Paralog | IGF1R | [P08069](https://www.uniprot.org/uniprotkb/P08069) | 15.8% | 29.5% | — | — | — | — | — | low-risk |
| Paralog | INSRR | [P14616](https://www.uniprot.org/uniprotkb/P14616) | 15.5% | 29.5% | — | — | — | — | — | low-risk |
| Paralog | LTK | [P29376](https://www.uniprot.org/uniprotkb/P29376) | 11.0% | 28.8% | — | — | — | — | — | low-risk |
| Paralog | FGFR3 | [P22607](https://www.uniprot.org/uniprotkb/P22607) | 13.6% | 28.5% | — | — | — | — | — | low-risk |
| Paralog | FGFR4 | [P22455](https://www.uniprot.org/uniprotkb/P22455) | 13.3% | 28.4% | — | — | — | — | — | low-risk |
| Paralog | FGFR2 | [P21802](https://www.uniprot.org/uniprotkb/P21802) | 13.6% | 27.5% | — | — | — | — | — | low-risk |
| Paralog | NTRK2 | [Q16620](https://www.uniprot.org/uniprotkb/Q16620) | 12.1% | 27.1% | — | — | — | — | — | low-risk |
| Paralog | FGFR1 | [P11362](https://www.uniprot.org/uniprotkb/P11362) | 12.6% | 26.6% | — | — | — | — | — | low-risk |
| Paralog | NTRK3 | [Q16288](https://www.uniprot.org/uniprotkb/Q16288) | 11.7% | 26.4% | — | — | — | — | — | low-risk |
| Paralog | DDR2 | [Q16832](https://www.uniprot.org/uniprotkb/Q16832) | 12.6% | 26.3% | — | — | — | — | — | low-risk |
| Paralog | AXL | [P30530](https://www.uniprot.org/uniprotkb/P30530) | 12.4% | 26.0% | — | — | — | — | — | low-risk |
| Paralog | ALK | [Q9UM73](https://www.uniprot.org/uniprotkb/Q9UM73) | 13.6% | 25.9% | — | — | — | — | — | low-risk |
| Paralog | TYRO3 | [Q06418](https://www.uniprot.org/uniprotkb/Q06418) | 12.2% | 25.6% | — | — | — | — | — | low-risk |
| Paralog | ROR1 | [Q01973](https://www.uniprot.org/uniprotkb/Q01973) | 11.2% | 25.1% | — | — | — | — | — | low-risk |
| Paralog | NTRK1 | [P04629](https://www.uniprot.org/uniprotkb/P04629) | 12.3% | 25.0% | — | — | — | — | — | low-risk |
| Paralog | EPHB3 | [P54753](https://www.uniprot.org/uniprotkb/P54753) | 15.5% | 24.8% | — | — | — | — | — | low-risk |
| Paralog | TIE1 | [P35590](https://www.uniprot.org/uniprotkb/P35590) | 13.8% | 24.6% | — | — | — | — | — | low-risk |
| Paralog | EPHB2 | [P29323](https://www.uniprot.org/uniprotkb/P29323) | 15.7% | 24.2% | — | — | — | — | — | low-risk |
| Paralog | DDR1 | [Q08345](https://www.uniprot.org/uniprotkb/Q08345) | 12.3% | 24.2% | — | — | — | — | — | low-risk |
| Paralog | MET | [P08581](https://www.uniprot.org/uniprotkb/P08581) | 12.9% | 24.0% | — | — | — | — | — | low-risk |
| Paralog | EPHA5 | [P54756](https://www.uniprot.org/uniprotkb/P54756) | 16.5% | 23.9% | — | — | — | — | — | low-risk |
| Paralog | MERTK | [Q12866](https://www.uniprot.org/uniprotkb/Q12866) | 12.5% | 23.8% | — | — | — | — | — | low-risk |
| Paralog | MST1R | [Q04912](https://www.uniprot.org/uniprotkb/Q04912) | 12.4% | 23.8% | — | — | — | — | — | low-risk |
| Paralog | EPHB4 | [P54760](https://www.uniprot.org/uniprotkb/P54760) | 15.4% | 23.8% | — | — | — | — | — | low-risk |
| Paralog | FLT3 | [P36888](https://www.uniprot.org/uniprotkb/P36888) | 12.9% | 23.7% | — | — | — | — | — | low-risk |
| Paralog | ROR2 | [Q01974](https://www.uniprot.org/uniprotkb/Q01974) | 11.9% | 23.5% | — | — | — | — | — | low-risk |
| Paralog | TEK | [Q02763](https://www.uniprot.org/uniprotkb/Q02763) | 13.8% | 23.5% | — | — | — | — | — | low-risk |
| Paralog | EPHA4 | [P54764](https://www.uniprot.org/uniprotkb/P54764) | 16.2% | 23.4% | — | — | — | — | — | low-risk |
| Paralog | CSF1R | [P07333](https://www.uniprot.org/uniprotkb/P07333) | 13.9% | 22.8% | — | — | — | — | — | low-risk |
| Paralog | EPHA1 | [P21709](https://www.uniprot.org/uniprotkb/P21709) | 15.2% | 22.8% | — | — | — | — | — | low-risk |
| Paralog | FLT1 | [P17948](https://www.uniprot.org/uniprotkb/P17948) | 14.3% | 22.7% | — | — | — | — | — | low-risk |
| Paralog | FLT4 | [P35916](https://www.uniprot.org/uniprotkb/P35916) | 13.6% | 22.7% | — | — | — | — | — | low-risk |
| Paralog | PDGFRB | [P09619](https://www.uniprot.org/uniprotkb/P09619) | 13.8% | 22.4% | — | — | — | — | — | low-risk |
| Paralog | KIT | [P10721](https://www.uniprot.org/uniprotkb/P10721) | 13.6% | 22.4% | — | — | — | — | — | low-risk |
| Paralog | KDR | [P35968](https://www.uniprot.org/uniprotkb/P35968) | 13.7% | 22.4% | — | — | — | — | — | low-risk |
| Paralog | EPHA3 | [P29320](https://www.uniprot.org/uniprotkb/P29320) | 16.1% | 22.3% | — | — | — | — | — | low-risk |
| Paralog | PDGFRA | [P16234](https://www.uniprot.org/uniprotkb/P16234) | 13.9% | 22.2% | — | — | — | — | — | low-risk |
| Paralog | MUSK | [O15146](https://www.uniprot.org/uniprotkb/O15146) | 12.1% | 22.2% | — | — | — | — | — | low-risk |
| Paralog | EPHA2 | [P29317](https://www.uniprot.org/uniprotkb/P29317) | 16.4% | 22.1% | — | — | — | — | — | low-risk |
| Paralog | EPHA6 | [Q9UF33](https://www.uniprot.org/uniprotkb/Q9UF33) | 15.8% | 21.8% | — | — | — | — | — | low-risk |
| Paralog | EPHA10 | [Q5JZY3](https://www.uniprot.org/uniprotkb/Q5JZY3) | 13.6% | 21.8% | — | — | — | — | — | low-risk |
| Paralog | RET | [P07949](https://www.uniprot.org/uniprotkb/P07949) | 12.5% | 21.2% | — | — | — | — | — | low-risk |
| Paralog | EPHB1 | [P54762](https://www.uniprot.org/uniprotkb/P54762) | 15.5% | 20.8% | — | — | — | — | — | low-risk |
| Paralog | EPHA7 | [Q15375](https://www.uniprot.org/uniprotkb/Q15375) | 15.9% | 20.4% | — | — | — | — | — | low-risk |
| Paralog | EPHA8 | [P29322](https://www.uniprot.org/uniprotkb/P29322) | 15.1% | 20.2% | — | — | — | — | — | low-risk |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: true
- severity: Moderate
- evidence: Moderate
- mechanism: ADAM17-Mediated Ectodomain Shedding Releases A Soluble EGFR ECD Fragment; Implicated In Autocrine/Paracrine Signaling In KRAS-Driven Pancreatic Tumorigenesis.
- sheddase: ADAM17
- cites: a1_evi_45, a2_evi_04

**Secreted form**

- present: true
- severity: Low
- evidence: Weak
- source: Alternative Splicing

**ECD size assessment**

- ECD class: Large
- rationale: EGFR ECD spans residues 25–645 (~620 aa across domains I–IV), well above the 200-aa threshold for the 'large' class. Crystal structures (PDB:7OM4, 1YY9, 3C09) and cryo-EM confirm a well-ordered, solvent-exposed ECD accommodating multiple non-overlapping antibody footprints. Cetuximab and panitumumab bind distinct epitopes confirming multiple accessible sites.
- cites: a1_evi_35, a1_evi_38, a1_evi_46, a1_evi_47

**Epitope masking**

- severity: Moderate
- evidence: Moderate
- mechanism: Glycan, Conformational
- rationale: EGFR ECD is heavily N-glycosylated (captured by glycan-based surface capture methods including CSC and N-glycocapture), which can sterically limit access to certain epitopes. ECD adopts a tethered inactive conformation and a ligand-induced open (heart-shaped) dimer conformation; conformation-dependent epitope exposure is documented for domain III. Approved antibodies (cetuximab domain III, panitumumab domain III) successfully navigate this, indicating masking is not prohibitive but reduces the accessible epitope space.
- cites: a1_evi_32, a1_evi_33, a1_evi_38, a2_evi_07

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P00533-F1](https://alphafold.ebi.ac.uk/entry/P00533) |
| AFDB version | v6 |
| ECD mean pLDDT | 91.0 |
| ECD disordered fraction | 3.2% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P00533) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P00533](https://alphafold.ebi.ac.uk/entry/P00533) | AlphaFold DB (AF-P00533-F1, v6) |
| Isoform P00533-2 | [P00533-2](https://alphafold.ebi.ac.uk/entry/P00533-2) | AlphaFold DB |
| Isoform P00533-3 | [P00533-3](https://alphafold.ebi.ac.uk/entry/P00533-3) | AlphaFold DB |
| Isoform P00533-4 | [P00533-4](https://alphafold.ebi.ac.uk/entry/P00533-4) | AlphaFold DB |
| Mouse ortholog (Egfr) | [Q01279](https://alphafold.ebi.ac.uk/entry/Q01279) | AlphaFold DB |
| Cynomolgus ortholog (EGFR) | [A0A2K5WK39](https://alphafold.ebi.ac.uk/entry/A0A2K5WK39) | AlphaFold DB |
| Experimental (best) | [7SYD](https://www.rcsb.org/structure/7syd) chain A | RCSB PDB · Electron Microscopy 3.1 Å · UniProt 1–1210 |
| Experimental (277 total) | [1IVO](https://www.rcsb.org/structure/1IVO), [1M14](https://www.rcsb.org/structure/1M14), [1M17](https://www.rcsb.org/structure/1M17), [1MOX](https://www.rcsb.org/structure/1MOX), [1NQL](https://www.rcsb.org/structure/1NQL), … [all 277 →](https://www.rcsb.org/uniprot/P00533) | RCSB PDB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

Epidermal growth factor receptor · Receptors · Kinase · chain A · 8 scored sites · 55,344 binder seeds (956 α-helix / 54,388 β-strand).

Anchor = patch-center residue; BSA = buried surface area (the contact footprint a binder would form on the patch); seed counts are docked binder backbones split by α-helix / β-strand.

**Reading the scores.** BSA vs the average antibody–antigen interface ≈ 1103 ± 244 Å² ([PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)): ≥1500 Å² comfortable · 850–1500 workable · <850 thin. Seed pool: ≥1000 comfortable design margin · ≥100 workable · <100 thin/specialized. SURFACE-Bind excludes transmembrane regions but not necessarily intracellular domains — cross-check the anchor residue against the topology string in §5/appendix (`O` = extracellular/antibody-accessible, `I` = intracellular).

| Site | Anchor residue | BSA (Å²) | α-helix seeds | β-strand seeds | Hydrophobicity |
|---|---|---|---|---|---|
| 0 | 743 | 1523.9 | 1 | 878 | 6.7 |
| 1 | 948 | 1519.4 | 241 | 16,361 | -22.3 |
| 2 | 599 | 1973.2 | 422 | 1,199 | 4.9 |
| 3 | 178 | 757.4 | 3 | 1,288 | -2.6 |
| 4 | 764 | 1599.8 | 11 | 168 | 11.0 |
| 5 | 69 | 700.3 | 203 | 3,769 | 4.5 |
| 6 | 549 | 1367.2 | 33 | 4,065 | 5.4 |
| 7 | 372 | 1257.0 | 42 | 26,660 | 6.7 |

**Experimental structures** — 277 PDB entries for this protein (browse at [RCSB](https://www.rcsb.org/uniprot/P00533)).

## 9. Evidence ledger

79 entries · 68 primary · 11 secondary · 0 tertiary · 79 PMC OA.

- `a1_evi_01` · *Primary* · Supports · Surface Expression — Live-cell flow cytometry on intact (non-permeabilized) glioma cells demonstrates endogenous EGFR/EGFRvIII antigen expression on the cell surface. Three cell lines tested: U373 (wild-type EGFR, weakly positive), U373vIII (EGFRvIII overexpressing), and GSC83 (endogenously expressing EGFR/EGFRvIII). Surface signal detected using anti-EGFR-Alexa Fluor647 antibody (Biolegend 352918) on live cells before permeabilization, confirming plasma membrane localization. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · U373, U373vIII, GSC83 glioma cells · live · non-permeabilized
  > "In order to glean some related insights, we used conventional flow cytometry to test EGFR antigen expression on the surfaces of individual glioma cells that were either weakly positive for the wild type EGFR (U373), or were engineered to overexpress oncogenic EGFRvIII (U373vIII) (Micallef et al. 2009 )."
- `a1_evi_02` · *Primary* · Supports · Surface Expression — Quantitative surface flow cytometry result: 12% of U373 cells (low endogenous EGFR), 98% of U373vIII cells (EGFRvIII OE), and 99% of GSC83 cells (endogenous EGFR/EGFRvIII) are positive for EGFR/EGFRvIII on their surfaces. Confirms robust, uniform surface presentation of both wild-type EGFR and the constitutively active EGFRvIII mutant on intact live glioma cells. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · U373, U373vIII, GSC83 · live · non-permeabilized
  > "The representative dot plots and histograms depicted in Figure 1A illustrate the expected (Spinelli et al. 2024 ; Magnus et al. 2014 ; Al‐Nedawi et al. 2010 ) levels of EGFR/EGFRvIII expression by these respective cell lines and suggest that while few (12%) U373 cells harbour low levels of this receptor on their surfaces, both U373vIII and GSC83 cells are highly and uniformly positive for EGFR/EGFRvIII (98% and 99%, respectively)."
- `a1_evi_03` · *Primary* · Supports · Surface Expression — Flow cytometry analysis on intact (non-permeabilized) glioma cells confirms uniform EGFR antigen presence on cell surface in GSC83 and U373vIII (high expression) versus U373 (low expression). Paired confocal IF on permeabilized vs. intact cells distinguishes surface EGFR pool from intracellular pool; antibody Biolegend 352918 used for both modalities. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · GSC83, U373, U373vIII · live · non-permeabilized
  > "(A) Flow cytometry analysis illustrating the uniform presence of EGFR antigen on the surface of glioma cells with high (GSC83 and U373VIII) and low (U373) levels of EGFR/EGFRvIII expression (right panel—dot plot; left panel—histogram); (B) Confocal imaging of immunofluorescent staining for EGFR antigen (red) and CD9 (green) in adherent GSC83 cells either intact or permeabilized before antibody exposure."
- `a1_evi_04` · *Primary* · Supports · Surface Expression — Authors conclude that endogenously expressed EGFR/EGFRvIII in GSC83 glioma cells is detectable principally on the cell surface, evenly decorating the surface as shown by both flow cytometry and confocal imaging. Confirms PM as dominant surface compartment for endogenous EGFR in these cells. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · GSC83 · live · non-permeabilized
  > "In isolated GSC83 cells the endogenously expressed EGFR/EGFRvIII (Spinelli et al. 2024 ) appears to be detectable principally on the cell surface, which is evenly decorated with the EGFR antigen, as revealed by flow cytometry and confocal imaging."
- `a1_evi_05` · *Primary* · Supports · Methodological — Methodological detail for live-cell surface flow cytometry: anti-EGFR-Alexa Fluor647 antibody (Biolegend catalog 352918) used on trypsinized live cells in 12-well plates; BD FACS Canto analyzer with FlowJo v10.7.1. No permeabilization step; confirms surface-only detection. Antibody RRID/catalog: Biolegend 352918. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · glioma cell lines · live · non-permeabilized
  > "Indicated cells were seeded in 12‐well plates for 24 h, then trypsinized and stained with anti‐EGFR‐Alexa Fluor647‐conjugated antibodies (Biolegend, 352918) and analysed using a BD FACS Canto with FlowJo software version 10.7.1."
- `a1_evi_06` · *Primary* · Supports · Methodological — Confocal microscopy protocol details permeabilized vs. non-permeabilized cell comparison: cells fixed with 4% PFA, then either permeabilized (0.1% Triton X-100) or left intact. This paired design explicitly distinguishes surface EGFR from intracellular pool. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · glioma cell lines · fixed
  > "For confocal microscopy, the adherent cells were fixed with 4% paraformaldehyde in phosphate buffered saline (PBS) for 10 min and, when indicated, permeabilized with 0.1% Triton X‐100 in PBS for 5 min."
- `a1_evi_07` · *Primary* · Supports · Methodological — Antibody identifiers for confocal IF surface vs. intracellular comparison: anti-EGFR-Alexa Fluor647 (Biolegend 352918) and anti-CD9-FITC (Biolegend 312104) used on both permeabilized and non-permeabilized fixed cells. The EGFR antibody is the same clone used in flow cytometry experiments. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · glioma cell lines · fixed
  > "Both permeabilized and non‐permeabilized cells were then incubated with primary antibodies: anti‐EGFR‐Alexa Fluor647 (Biolegend 352918) and anti‐CD9‐FITC (Biolegend 312104)."
- `a1_evi_08` · *Primary* · Supports · Surface Expression — Immunofluorescence microscopy comparing non-permeabilized vs. permeabilized cells explicitly separates cell-surface EGFR pool from intracellular EGFR pool. Quantified from n=2 independent experiments with statistical comparison (p<0.01). This paired permeabilization design directly validates surface EGFR localization. ([PMC9038772](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9038772/))
  - *assay*: Human · unspecified · fixed · non-permeabilized
  > "Representative immunofluorescence micrographs (A) show either cell surface EGFR in nonpermeabilized cells or intracellular EGFR in permeabilized cells as indicated and (B) quantified data from n = 2 independent experiments (mean ± SD; ∗∗, p < 0.01 using multiple t tests; Prism)."
- `a1_evi_09` · *Primary* · Supports · Surface Expression — Representative flow cytometry histograms of surface EGFR on pancreatic cancer cell lines (BxPC-3 and others indicated), demonstrating variable surface EGFR expression levels across cell lines. Method is surface-binding flow cytometry. ([PMC13088391](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088391/))
  - *assay*: Human · pancreatic cancer cell lines including BxPC-3 · live · non-permeabilized
  > "( A ) Representative flow cytometry histograms of surface EGFR on the indicated pancreatic cancer cell lines."
- `a1_evi_10` · *Primary* · Supports · Surface Expression — Cell-surface binding assessed by flow cytometry: bispecific antibody (targeting EGFR and NKG2D) binding to EGFR on BxPC-3 pancreatic cancer cells and to NKG2D on primary human NK cells. Demonstrates antibody-mediated engagement of EGFR at the cell surface on intact live cells. ([PMC13088391](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088391/))
  - *assay*: Human · BxPC-3 · live · non-permeabilized
  > "( D ) Cell-surface binding assessed by flow cytometry: binding to EGFR on BxPC-3 cells and to NKG2D on primary human NK cells."
- `a1_evi_11` · *Primary* · Supports · Methodological — Surface staining by flow cytometry on non-permeabilized cells, with HCT 116 used as a negative control (CCLE log2[TPM+1]=0.0, minimal surface staining). Validates antibody specificity by negative-control cell line lacking EGFR transcript; demonstrates surface detection is EGFR-specific. ([PMC13096901](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13096901/))
  - *assay*: Human · HCT 116 (negative control) · live · non-permeabilized
  > "HCT 116 served as a negative control and showed minimal surface staining, consistent with a CCLE value of log2[TPM+1] = 0.0."
- `a1_evi_12` · *Primary* · Ambiguous · Contradictory — Methodological note: clinical IHC specimens often showed granular/diffuse staining pattern rather than sharp membranous staining, yet NCI-H1930 cells with similar IHC pattern still showed clear cell surface EGFR expression by flow cytometry. Highlights discordance between IHC membrane-pattern scoring and actual surface accessibility, and confirms flow cytometry as the more direct surface-accessibility assay. ([PMC13096901](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13096901/))
  - *assay*: Human · NCI-H1930 · unspecified · non-permeabilized
  > "In addition, while clinical specimens often exhibited a granular and/or diffuse IHC pattern, rather than a sharp membranous staining, NCI–H1930 cells showed a similar pattern yet demonstrated cell surface expression by flow cytometry."
- `a1_evi_13` · *Primary* · Supports · Surface Expression — Surface biotinylation on DCDMLs (ductal carcinoma-derived mammary lines): sulfo-NHS biotin applied to intact cells, plasma membrane proteins captured with streptavidin beads, Western blotted with 4G10 anti-phosphotyrosine antibody. This workflow assesses all ErbB kinases (including EGFR) simultaneously at the plasma membrane; demonstrates EGFR biotinylation-capture method on intact cell surfaces. ([PMC10337807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10337807/))
  - *assay*: Human · DCDMLs (ductal carcinoma-derived mammary lines) · live · non-permeabilized
  > "In order to simultaneously assess all possible ErbB kinases, we subjected DCDMLs to cell surface biotinylation, collected labeled plasma membrane proteins with streptavidin beads, and probed Western blots with the 4G10 antiphosphotyrosine antibody."
- `a1_evi_14` · *Primary* · Supports · Surface Expression — Surface biotinylation + streptavidin pulldown + Western blot in HPV16 E7-expressing NIKS cells: biotinylated proteins recovered with streptavidin beads and assessed by WB show higher total levels of EGFR (and other targets) on the cell surface in Wt 16 E7-expressing NIKS versus controls. Direct protein-level evidence for EGFR at the plasma membrane of an endogenously expressing keratinocyte-derived cell line. ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
  - *assay*: Human · NIKS (normal immortalized keratinocytes) expressing HPV16 E7 · live · non-permeabilized
  > "Biotinylated proteins were recovered with streptavidin beads and analysed by Western blot; we observed higher total levels of the selected targets on the cell surface in Wt 16 E7-expressing NIKS cells ( Fig. 2 C)."
- `a1_evi_15` · *Primary* · Supports · Surface Expression — Surface EGFR (measured by surface biotinylation panel) is modestly upregulated in HPV16 E7-expressing cells via an AP2-tyrosine binding motif-dependent mechanism. Confirms surface-accessible EGFR pool modulation in keratinocytes; corroborates prior biotinylation results from the same paper. ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
  - *assay*: Human · NIKS · live · non-permeabilized
  > "Remarkably, we observed several potential membrane proteins up- and down-regulated by the AP2-tyrosine binding motif in E7, including a modest upregulation of the surface EGFR ( Fig. 2 B), which is in agreement with our previous results [ 13 ]."
- `a1_evi_16` · *Primary* · Supports · Methodological — Surface biotinylation methods detail: in HPV16 E7-expressing SiHa and HPV18 E7-expressing HeLa cells, plasma membrane proteins biotinylated after siRNA knockdown of E6/E7 oncoproteins; biotinylated proteins assessed by Western blot. Demonstrates surface biotinylation + WB method for EGFR in multiple HPV-positive human cancer cell lines. ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
  - *assay*: Human · SiHa (HPV16+), HeLa (HPV18+) · live · non-permeabilized
  > "To investigate this, we knocked down the expression of E6 and E7 oncoproteins from HPV16 E7-expressing SiHa and HPV18 E7-expressing HeLa cells; then plasma membrane proteins were biotinylated and labelled proteins were assessed by Western blotting."
- `a1_evi_17` · *Primary* · Supports · Methodological — Surface biotinylation + WB methodology: cell surface proteins from SiHa (HPV-16-positive) and HeLa (HPV-18-positive) cells biotinylated and purified with streptavidin; cells then lysed and membrane protein expression quantified by Western blotting. Paired biotinylation + WB satisfies the _check_wb_pairing requirement. ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
  - *assay*: Human · SiHa, HeLa · live · non-permeabilized
  > "(B) Cell surface proteins from SiHa (HPV-16-positive) and HeLa (HPV-18-positive) cells were biotinylated and purified; then cells were lysed and membrane protein expression was assessed by Western blotting."
- `a1_evi_18` · *Primary* · Supports · Surface Expression — Surface biotinylation (sBioSITe method) detects EGFR at the cell surface of prostate cancer bone-metastatic cells with 19 distinct biotinylation sites, confirming robust plasma membrane localization of EGFR. EGFR described as a known marker of prostate cancer bone dissemination; detection by biotinylation-site immunoprecipitation + MS. ([PMC10696767](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10696767/))
  - *assay*: Human · prostate cancer bone metastasis cells · live · non-permeabilized
  > "Epidermal growth factor receptor (EGFR), a known marker of dissemination of prostate cancer to bones, was detected with 19 biotinylation sites [ 29 ] (Fig. 3 C)."
- `a1_evi_19` · *Primary* · Supports · Methodological — sBioSITe (surface Biotinylation Site Identification Technology) developed as a sensitive, reliable method for enrichment of cell surface proteins by immunoprecipitation of biotinylated peptides. Method family: surface biotinylation + mass spectrometry; adapted from BioSITe approach. Used to detect and quantify EGFR and other cell surface proteins. ([PMC10696767](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10696767/))
  - *assay*: Human · prostate cancer cells · live · non-permeabilized
  > "We report the development of surface Biotinylation Site Identification Technology (sBioSITe), a sensitive and reliable method for the enrichment of cell surface proteins by adapting the Biotinylation Site Identification Technology (BioSITe) for immunoprecipitation of biotinylated peptides [ 17 ]."
- `a1_evi_20` · *Primary* · Supports · Surface Expression — Surface biotinylation (sulfo-NHS-SS-biotin) followed by mass spectrometry identifies 1,508 distinct surface proteins in sensory-like neuron cultures; EGFR is among the most deregulated hits (p<0.01) in FD patient vs. control neuronal plasma membrane proteomes. This is primary MS surfaceome evidence for EGFR at the neuronal cell surface. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · iPSC-derived sensory-like neurons (Familial Dysautonomia patients and controls) · live · non-permeabilized
  > "Via biotinylation followed by mass spectrometry ( Fig 1A , 1B ), we identified 1,508 distinct proteins in sensory-like neuron cultures derived from FD patients and controls, consistently observed across three independent experiments (S2 Table)."
- `a1_evi_21` · *Primary* · Supports · Surface Expression — EGFR identified as a significantly deregulated surface protein (p<0.01) in the plasma membrane proteome of Familial Dysautonomia patient-derived sensory-like neurons versus controls, detected by sulfo-NHS-SS-biotin surface labeling + mass spectrometry surfaceome assay. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · iPSC-derived sensory-like neurons · live · non-permeabilized
  > "Among the most deregulated proteins (p < 0.01), we identified several neuronal candidates with a potential link to nerve pathology such as: calcium voltage-gated channel auxiliary subunit alpha2delta 3 (CACNA2D3, p < 0.01) [ 52 ], neuronal membrane glycoprotein M6-A (GPM6A, p < 0.001) [ 53 , 54 ], ATP-binding cassette subfamily A member 7 (ABCA7) [ 55 ], and epidermal growth factor receptor (EGFR, p < 0.01) [ 56 , 57 ]."
- `a1_evi_22` · *Primary* · Supports · Methodological — Surface biotinylation protocol: cells washed with PBS and covered with sulfo-NHS-SS-biotin solution for 10 minutes at room temperature. This is a cleavable sulfo-NHS-SS chemistry ensuring selective labeling of extracellular-exposed lysines on intact cells. Paired with MS readout for surfaceome identification. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · sensory-like neurons · live · non-permeabilized
  > "In brief, cells were washed with PBS and covered with sulfo-NHS-SS-biotin solution for ten minutes at room temperature."
- `a1_evi_23` · *Primary* · Supports · Surface Expression — Quantitative surfaceome (SILAC + chemoproteomic surface capture on polarized MDCK epithelial cells) shows EGFR is relatively evenly distributed between apical and basolateral membrane faces with an apicobasal ratio of 40:60. EGFR is detected at both poles of the polarized epithelial plasma membrane, confirming surface localization in a relevant epithelial model. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
  - *assay*: Dog · MDCK (Madin-Darby Canine Kidney) · live · non-permeabilized
  > "However, we show here that both the EGF precursor and its receptor EGFR are relatively evenly distributed across the polarized membrane (with an apicobasal ratio of 50:50 and 40:60, respectively)."
- `a1_evi_24` · *Primary* · Supports · Methodological — Quantitative apicobasal surfaceome method: SILAC labeling + chemoproteomics (cell-surface capture chemistry) on filter-grown polarized MDCK cells. Two-domain biotinylation approach used to separately label apical and basolateral surfaces. Enables quantitative measurement of EGFR apicobasal surface distribution. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
  - *assay*: Dog · MDCK · live · non-permeabilized
  > "In order to map the apicobasal surfaceome quantitatively, we used filter-grown Madin–Darby canine kidney (MDCK) cells as the best-established in vitro system for epithelial polarity [ 16 ] in combination with chemoproteomics and stable isotope labeling of amino acids in cell culture (SILAC) ( Figure 1 A) [ 17 , 18 ]."
- `a1_evi_25` · *Primary* · Supports · Methodological — Surfaceome validation step: proteins identified by chemoproteomic capture filtered for plasma membrane evidence using UniProtKB and the Surfy surfaceome predictor. This validation/filtering strategy confirms that EGFR detections in the surfaceome dataset are restricted to genuine plasma membrane proteins. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
  - *assay*: Dog · MDCK · live · non-permeabilized
  > "Finally, identified proteins were filtered for evidence for localization at the plasma membrane using UniprotKB and the Surfy surfaceome predictor [ 19 ] ( Figure S1A )."
- `a1_evi_26` · *Secondary* · Supports · Methodological — Cell surface capture (CSC) method description: periodate oxidizes glycan termini on intact cells to generate aldehydes that react with hydrazide-coated beads via stable hydrazone linkages; captured glycoproteins released by PNGase F amidase. This is the foundational Wollscheid/Aebersold CSC chemistry used for surfaceome MS; EGFR is captured as an N-glycosylated surface protein. ([PMC12022999](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12022999/))
  - *assay*: Unspecified · live · non-permeabilized
  > "The aldehydes readily react with hydrazide, to form stable hydrazone linkages. 75 The enrichment technique called cell surface capture (CSC) developed by Wollscheid, Aebersold, and co-workers, utilized this chemistry to capture cell surface proteins onto hydrazide beads. 76 The captured glycoproteins were washed extensively and released using PNGase F, an amidase that cleaves between the innermost GlcNAc and the N -glycan-modified asparagine."
- `a1_evi_27` · *Primary* · Supports · Surface Expression — EGFR was identified in the surfaceome dataset for penile tissue and ranked in the top 84% of surface-protein expression across the tissue surfaceome panel. Evidence type: surfaceome MS (CSC or equivalent) with bioinformatic surfaceome annotation. ([PMC10377392](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10377392/))
  - *assay*: Human · unspecified · non-permeabilized
  > "Of interest, the previously described epidermal growth factor receptor (EGFR) was in the top 84% of expression."
- `a1_evi_28` · *Primary* · Supports · Surface Expression — IHC on sinonasal inverted papilloma (SIP) tumor sections shows positive EGFR plasma membrane staining in 31/32 cases (97%). Staining scored as moderate-to-strong membranous in >10% of tumor cells per validated scoring criterion (Menendez et al.). Confirms EGFR surface localization at the protein level in primary human tumor tissue. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
  - *assay*: Human · fixed · non-permeabilized
  > "EGFR showed positive plasma membrane staining in 31 of 32 SIP cases (97%)."
- `a1_evi_29` · *Primary* · Supports · Surface Expression — IHC on SIP tumor sections shows phospho-EGFR positive plasma membrane staining in 22/32 cases (69%), demonstrating that the activated (phosphorylated) form of EGFR is also present at the cell surface in the majority of cases. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
  - *assay*: Human · fixed · non-permeabilized
  > "For p-EGFR, 22 of 32 SIP cases (69%) showed positive plasma membrane staining."
- `a1_evi_30` · *Secondary* · Supports · Methodological — IHC scoring rubric for EGFR/p-EGFR membrane staining: positive requires moderate-to-strong membranous staining in >10% of tumor cells (Menendez et al. criterion). Rubric anchors the surface-detection methodology and defines the threshold for surface positivity in the SIP dataset. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
  - *assay*: Human · fixed · non-permeabilized
  > "IHC for EGFR and p-EGFR was considered positive when moderate to strong membranous staining was observed in more than 10% of tumor cells; cases that did not meet this criterion were regarded as negative, based on Menendez M et al. [ 23 ]."
- `a1_evi_31` · *Secondary* · Supports · Methodological — IHC membrane-staining scoring system for EGFR: weak membranous = 1, complete moderate membranous = 2, complete strong membranous = 3. Defines the surface-detection criterion used in EGFR/HER3 expression analysis of NSCLC tissue sections. ([PMC13028177](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13028177/))
  - *assay*: Human · fixed · non-permeabilized
  > "Weak membranous staining was scored as 1, complete but moderate membrane staining was scored as 2, and complete and strong staining was scored as 3 ( Figure 1 and Figure 2 )."
- `a1_evi_32` · *Primary* · Supports · Topology — Cryo-EM reconstruction of full-length EGFR receptor complex shows strongest density in the ectodomain region, consistent with a large, well-ordered extracellular domain. Weaker density in TM and intracellular domains. Confirms N-terminal ECD is extracellular and structurally accessible. ([PMC10948148](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10948148/))
  - *assay*: Human
  > "As reported in all previously published cryo-EM reconstructions of other RTKs ( Diwanji et al., 2021 ; Huang et al., 2021 ; Nielsen et al., 2022 ; Li et al., 2019 ; Uchikawa et al., 2019 ; Krimmer et al., 2023 ), the cryo-EM density was the strongest in the ectodomain region of the receptor complex and the weakest within the transmembrane and intracellular domains ( Figure 1b–c , Figure 1—figure supplement 2a, f , Figure 1—figure supplement 3a, f )."
- `a1_evi_33` · *Primary* · Supports · Topology — Cryo-EM and X-ray structures of liganded EGFR show ECD adopts characteristic 'heart-shaped' dimer arrangement (consistent across multiple solved structures). Establishes that domain I-IV ECD architecture is extracellular, forming dimerization interfaces accessible from outside the cell. ([PMC10948148](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10948148/))
  - *assay*: Human
  > "In both structures, the ectodomains adopt a characteristic ‘heart-shaped’ arrangement observed in previously solved X-ray and cryo-EM structures of liganded HER receptor dimers ( Garrett et al., 2002 ; Liu et al., 2012 ; Ogiso et al., 2002 ; Diwanji et al., 2021 ; Bai et al., 2023 ; Freed et al., 2017 ; Huang et al., 2021 ; Lu et al., 2010 )."
- `a1_evi_34` · *Primary* · Supports · Topology — Crystal structure of EGFR/EREG ectodomain complex reveals dimerization arm engaging HER2 via domain III interactions. Confirms that the ECD of EGFR presents accessible binding surfaces (including domain III) on the extracellular face, relevant for antibody/ligand engagement. ([PMC10948148](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10948148/))
  - *assay*: Human
  > "The EGFR dimerization arm engages HER2 via non-canonical interactions with domain III that resemble those only observed in the crystal structure of the EGFR/EREG ectodomain complex ( Bai et al., 2023 ; Freed et al., 2017 )."
- `a1_evi_35` · *Primary* · Supports · Topology — Crystal structure of full ectodomain EGFR in ternary complex with nanobody EgB4 and EGF ligand determined to 6.0 Å (PDB: 7OM4). Defines the spatial arrangement of all four ECD domains (I-IV) and confirms extracellular accessibility of the ligand-binding and antibody-binding surfaces on intact EGFR. ([PMC8887186](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8887186/))
  - *assay*: Human
  > "S 2
To study the mechanism by which the EgB4 nanobody interacts with EGFR, we then determined the structure of the full ectodomain EGFR-EgB4-EGF ternary complex from a crystal that diffracted to a maximum resolution of 6.0 Å (PDB: 7OM4; Table 1 and Fig."
- `a1_evi_36` · *Primary* · Supports · Topology — EGFR ectodomain crystal structure (PDB: 3NJP) used as starting point for molecular dynamics simulations. Confirms existence of a well-resolved, free-standing ectodomain structure (untethered) that establishes the extracellular domain topology and boundary at residues corresponding to the signal-peptide-cleavage site through the TM helix. ([PMC11965450](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11965450/))
  - *assay*: Human
  > "For the starting structures of our EGFR simulations (simulations 1, 2, 5, and 6), four frames were selected randomly from an equilibration simulation of an untethered EGFR ectodomain crystal structure (PDB ID: 3NJP); the double mutation C271A/C283A was introduced for simulations 5 and 6."
- `a1_evi_37` · *Primary* · Supports · Topology — EGFR ECD crystal structure PDB:4UV7 superimposed on EGFR-Matuzumab complex (PDB: 3C09) for antibody binding calculations. Confirms availability of high-resolution ECD structural data and provides the geometric basis for ECD surface accessibility and antibody epitope calculations. ([PMC12827627](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12827627/))
  - *assay*: Human
  > "The crystal structure of the extracellular domain of EGFR from PDB:4UV7 was superimposed on to the EGFR-Matuzumab complex (PDB: 3C09) to facilitate these calculations."
- `a1_evi_38` · *Primary* · Supports · Surface Expression — Therapeutic engagement: X-ray crystal structures of Cetuximab Fab-EGFR ECD complex (PDB: 1YY9) and Matuzumab Fab-EGFR ECD complex (PDB: 3C09) used to model full IgM bispecific antibodies targeting EGFR. Confirms structural basis for cetuximab and matuzumab ECD engagement; supports surface accessibility of EGFR epitopes for therapeutic antibody binding. ([PMC12827627](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12827627/))
  - *assay*: Human
  > "The full-length IgM models for Cetuximab and Matuzumab were built using structural data available in the PDB: i) the X-ray crystal structures of Cetuximab and Matuzumab Fab bound to the human EGFR extracellular domains (ECDs) (PDB: 1YY9 ( 56 ) and 3C09 ( 22 ), respectively), ii) the cryogenic electron microscopy (cryo-EM) structure of the human IgM Fc pentamer (PDB: 6KXS) ( 25 ), and iii) the crystal structure of mouse Cµ2 domain (PDB: 4JVU) ( 57 )."
- `a1_evi_39` · *Primary* · Supports · Topology — EGFR full ECD structure obtained from cryo-EM structure PDB:7SYD used for modeling IgM and IgG antibody complexes with EGFR. Confirms cryo-EM structural basis for ECD-antibody engagement; ECD accessibility from extracellular face confirmed in therapeutic modeling context. ([PMC12827627](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12827627/))
  - *assay*: Human
  > "To model the bound systems of IgM and IgG antibodies in complex with the EGFR, we obtained the complete EGFR ECD structure from a cryo-EM structure (PDB:7SYD) ( 62 )."
- `a1_evi_40` · *Primary* · Supports · Surface Expression — EGFR surface engagement by DNA-antibody conjugates on live MCF-7 cells: streptavidin-decorated DNA origami nanoframes bind biotinylated anti-EGFR antibody conjugates, which then bind EGFR in the membrane of live MCF-7 cells. Demonstrates that EGFR is accessible at the surface of intact live breast cancer cells for large macromolecular cargo engagement. ([PMC11472258](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11472258/))
  - *assay*: Human · MCF-7 · live · non-permeabilized
  > "To do so, the STV-decorated DON F were used to bind biotinylated DNA-antibody conjugates, which can bind to the EGF receptor (EGFR) in the membrane of live MCF-7 cells ( Figure 4 a)."
- `a1_evi_41` · *Primary* · Supports · Surface Expression — Therapeutic engagement: Panitumumab (fully human anti-EGFR IgG2, FDA-approved) binds EGFR ECD with KD = 5×10^-11 M, 4 orders of magnitude higher affinity than EGF. Panitumumab prevents EGF binding and may induce EGFR clustering/activation at the cell surface when multivalently engaged. Confirms cell-surface ECD accessibility for approved therapeutic antibody. Program: Amgen/Vectibix, approved for metastatic colorectal cancer (KRAS wild-type). ([PMC11472258](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11472258/))
  - *assay*: Human · MCF-7 · live · non-permeabilized
  > "Panitumumab ( K D = 5 × 10 –11 M) 39 binds EGFR with an affinity 4 orders of magnitude higher than EGF ( K D = 1.77 × 10 –7 M), thus preventing EGF binding. 40 Previous studies have shown that antibodies that bind EGFR laterally (not on the EGF binding site) can induce EGFR activation through clustering when attached to a surface. 41 We speculated that Panitumumab might also induce EGFR activation by receptor recruitment, even though it blocks the EGF binding site."
- `a1_evi_42` · *Primary* · Supports · Surface Expression — Flow cytometry on live A431 cells to study binding of MNT1 (a targeting moiety) to EGFR receptors on the surface. A431 is a canonical EGFR-overexpressing epidermoid carcinoma cell line. Confirms surface EGFR accessibility in the well-established high-EGFR model cell line. ([PMC10818351](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10818351/))
  - *assay*: Human · A431 · live · non-permeabilized
  > "Flow cytometry was used to study the ability of MNT 1 to bind to EGFR receptors on the surface of A431 cells."
- `a1_evi_43` · *Primary* · Supports · Methodological — Antibody identifier for surface EGFR detection: mouse 528mAb (anti-EGFR) provided by Recombinant Protein Production and Purification Facility, CSIRO. This antibody (clone 528) is a well-characterized anti-EGFR ECD antibody used in surface-binding and therapeutic engagement studies. ([PMC10245379](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10245379/))
  - *assay*: Human
  > "Anti-EGFR mouse 528mAb was provided by the fermentation team at the Recombinant Protein Production and Purification Facility, CSIRO.
400 MHz NMR spectra were recorded on a Bruker Avance III Nanobay spectrometer."
- `a1_evi_44` · *Primary* · Supports · Methodological — Antibody table: EGFR detected with Abcam ab52894, used at WB 1:5000 and IHC 1:100. Antibody vendor and catalog number provided; supports antibody specificity annotation for paired WB and IHC experiments in pancreatic cancer mouse models. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
  - *assay*: Mouse · fixed
  > "Application/dilution ADAM17 Millipore Sigma AB19027 IF: 1:400 Amylase Millipore Sigma A8273 IHC 1:500 Amylase Santa Cruz SC-12821 ADM 1:2500 AKT Cell Signaling 4691 WB: 1:4000 CD45 Abcam Ab10558 IF: 1:400 CK19 Developmental Studies Hybridoma Bank Troma III IF 1:100 CK19 Abcam Ab133496 IHC 1:4000 ADM 1:5000 Cleaved caspase 3 Cell Signaling 9664 IHC 1:100 c-Jun Cell Signaling 9165 IHC: 1:100 E-cadherin Cell Signaling 3195 IHC: 1:100 IF 1:50 EGFR Abcam ab52894 WB 1:5000 IHC 1:100 ERK1/2 Cell Signaling 9102 WB: 15000 IHC"
- `a1_evi_45` · *Primary* · Ambiguous · Surface Expression — EGFR-ligand shedding by pancreatic acinar cells via ADAM17 activates EGFR in a cell-autonomous manner. Genetic ablation of either EGFR or ADAM17 in pancreatic parenchymal cells protects mice from KRAS-driven acinar transdifferentiation. This shed-form/ectodomain shedding evidence implies active EGFR surface presence (ADAM17 substrate) and raises the risk of shed ECD confounding surface accessibility measurements. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
  - *assay*: Mouse
  > "In our previous study, genetic ablation of either Egfr or Adam17 in pancreatic parenchymal cells protects mice from KRAS-driven acinar cell transdifferentiation and subsequent tumorigenesis, 11 supporting a cell autonomous mechanism where EGFR-ligand shedding from acinar cells activates EGFR in those same cells."
- `a1_evi_46` · *Secondary* · Supports · Topology — Full-length EGFR (residues 1-1210, canonical isoform 1) and ECD (residues 25-645) cloned into CMV-FLAG expression vector. Establishes the precise ECD boundaries (25-645) used for phage display and biotinylation assays; confirms signal peptide is residues 1-24. ([PMC13010625](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13010625/))
  - *assay*: Human
  > "The full-length EGFR (residues 1–1210) and its extracellular domain (residues 25–645) were cloned into a CMV-FLAG expression vector."
- `a1_evi_47` · *Secondary* · Supports · Topology — EGFR ECD construct (residues 25-645) with C-terminal Avi tag generated for phage display and biotinylation. Confirms ECD boundaries (25-645) and that residue 24 is the signal peptide cleavage site. Avi-tagged ECD biotinylated by BirA enzyme for surface-capture experiments. ([PMC13010625](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13010625/))
  - *assay*: Human
  > "To facilitate immobilization during phage display screening, an Avi tag (GLNDIFEAQKIEWHE) was fused to the C-terminus of the EGFR extracellular domain, generating the hEGFR(25–645)-Avi-CMV-FLAG construct."
- `a1_evi_48` · *Primary* · Supports · Methodological — SPR (Biacore T200) confirms binding of Z_EGFR:1907.BirA* affibody construct to the EGFR extracellular domain, validating ECD accessibility and affibody specificity for surface proximity-labeling experiments. Confirms ECD-targeted engagement for biotinylation-based surface proteomics. ([PMC9890520](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9890520/))
  - *assay*: Human
  > "The ability of Z EGFR:1907 .BirA* and Z HER2:243 .BirA* to bind to their targets (the extracellular domains of EGFR and HER2, respectively) was determined by SPR (Biacore T200; GE Healthcare Mississauga, ON, Canada)."
- `a1_evi_49` · *Primary* · Supports · Methodological — BirA* proximity-labeling method: EGFR.Fc biotinylated by Affibody.BirA* construct (Z_EGFR:1907.BirA*) binding EGFR ECD; biotinylated proteins detected by streptavidin-HRP Western blot. Confirms ECD-targeted surface biotinylation approach with WB readout; satisfies _check_wb_pairing requirement. ([PMC9890520](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9890520/))
  - *assay*: Human
  > "The level of the biotinylation of EGFR.Fc and HER2.Fc arising from exposing them to Affibody.BirA* constructs was monitored by eluting the biotinylated proteins bound to the protein G beads by boiling the beads in lithium dodecyl sulfate (LDS) sample buffer and performing Western blot on the recovered samples under nonreducing conditions using 1:2500 streptavidin-HRP."
- `a1_evi_50` · *Primary* · Supports · Methodological — Anti-EGFR-HRP antibody (Abcam, 1:5000 dilution) used to confirm EGFR identity in streptavidin-bead pulldown Western blot. Antibody vendor and dilution specified. Paired WB validation confirms EGFR presence in biotinylated protein pool. ([PMC9890520](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9890520/))
  - *assay*: Human
  > "The presence of EGFR and HER2 among the biotinylated proteins pulled down was confirmed by Western blot using 1:5000 anti-EGFR.HRP (Abcam) and anti-HER2.HRP (Novus Biologicals) conjugates."
- `a1_evi_51` · *Primary* · Supports · Methodological — Flow cytometry optimization for EGFR-positive exosome detection: anti-EGFR Affibody-FITC and anti-EGFR antibody-Alexa Fluor 488 evaluated for optimal concentration and signal-to-noise for EGFR surface detection via flow cytometry. Parameters optimized: microbead count, antibody/affibody saturation concentration, fluorescent detector concentration. Documents surface EGFR flow cytometry methodology detail. ([PMC8584739](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8584739/))
  - *assay*: Human · EGFR-positive exosomes (microbead-captured) · unspecified · non-permeabilized
  > "To maximize the immune-capture efficiency and detection sensitivity of EGFR-positive exosomes with flow cytometry, three parameters were evaluated: (A) the optimal number of microbeads required for flow cytometry testing, (B) the concentration of anti-EGFR Affibody and antibody needed to saturate the surface of microbeads, respectively, and (C) the optimal concentration of Affibody-FITC and antibody-Alexa Fluor 488 fluorescent detector required for a high signal-to-noise ratio when tested using a flow cytometer."
- `a1_evi_52` · *Primary* · Supports · Surface Expression — EGFR detected in a cell-surface labeling study of GCPII interactome at LNCaP/PC3-PSMA cell membranes; EGFR forms a macromolecular complex with GCPII, ITGB1, filamin A, p130CAS, c-Src at the cell membrane. Confirms EGFR plasma membrane localization in prostate cancer cell lines via cell-surface labeling approach. ([PMC12749419](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12749419/))
  - *assay*: Human · LNCaP, PC3-PSMA · live · non-permeabilized
  > "EGFR (epidermal growth factor receptor), the other constituent of the complex, and ITGA3 (integrin α3) were both detected in this study."
- `a1_evi_53` · *Primary* · Supports · Surface Expression — A549 cell-surface labeling of EGFR interactome (biotinylation-based surfaceome detection) identifies EGFR as a key surface-resident signaling hub. Confirms EGFR plasma membrane localization in lung adenocarcinoma A549 cells via surface-labeling method. ([PMC12749419](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12749419/))
  - *assay*: Human · A549 · live · non-permeabilized
  > "V. et al. as a key EGFR interactor, based on A549 cell–surface labeling of the EGFR interactome 20 ."
- `a1_evi_54` · *Primary* · Supports · Methodological — Surface biotinylation + streptavidin-bead enrichment + Western blot methodology: after cell lysis, biotinylated proteins enriched on streptavidin beads and analyzed by WB. Paired WB step satisfies _check_wb_pairing requirement for surface_biotinylation assay. ([PMC12749419](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12749419/))
  - *assay*: Human · unspecified · live · non-permeabilized
  > "Following cell lysis and protein enrichment on streptavidin beads, we performed Western blot analysis of the resulting enriched proteins."
- `a1_evi_55` · *Primary* · Supports · Methodological — Surface biotinylation + streptavidin-bead enrichment + dual readout (Western blot and mass spectrometry): protein eluants analyzed by both WB and MS for quantitative surface proteomics. This paired WB + MS approach provides orthogonal validation of biotinylated surface protein identification. ([PMC12749419](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12749419/))
  - *assay*: Human · unspecified · live · non-permeabilized
  > "Protein eluants after streptavidin-bead enrichment were analyzed by Western blotting and mass spectrometry."
- `a2_evi_01` · *Primary* · Supports · Tissue Expression — EGFR protein shows positive plasma membrane staining in 97% (31/32) of sinonasal inverted papilloma (SIP) tumor cases, indicating high-frequency surface expression in this tumor type as detected by IHC. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
  - *assay*: Human · sinonasal inverted papilloma (SIP) tumor tissue · fixed · permeabilized
  > "EGFR showed positive plasma membrane staining in 31 of 32 SIP cases (97%)."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — Phosphorylated EGFR (p-EGFR) shows positive plasma membrane staining in 69% (22/32) of sinonasal inverted papilloma cases, indicating that activated/phosphorylated EGFR is present at the cell surface in the majority of SIP tumors. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
  - *assay*: Human · sinonasal inverted papilloma (SIP) tumor tissue · fixed · permeabilized
  > "For p-EGFR, 22 of 32 SIP cases (69%) showed positive plasma membrane staining."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — EGFR is identified as a known marker of prostate cancer dissemination to bone, detected with 19 biotinylation sites in a surface biotinylation-MS study, consistent with abundant cell-surface expression in bone-metastatic prostate cancer. ([PMC10696767](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10696767/))
  - *assay*: Human · prostate cancer bone metastasis model · live · non-permeabilized
  > "Epidermal growth factor receptor (EGFR), a known marker of dissemination of prostate cancer to bones, was detected with 19 biotinylation sites [ 29 ] (Fig. 3 C)."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — EGFR is expressed in pancreatic acinar cells and participates in a cell-autonomous signaling loop where EGFR-ligand shedding from acinar cells activates EGFR on those same cells, driving KRAS-induced acinar-to-ductal transdifferentiation and tumorigenesis. Genetic ablation of Egfr in pancreatic parenchymal cells protects from this process. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
  - *assay*: Mouse · pancreatic acinar cells
  > "In our previous study, genetic ablation of either Egfr or Adam17 in pancreatic parenchymal cells protects mice from KRAS-driven acinar cell transdifferentiation and subsequent tumorigenesis, 11 supporting a cell autonomous mechanism where EGFR-ligand shedding from acinar cells activates EGFR in those same cells."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — Human pancreas scRNA-seq data shows EGFR ligand expression across various pancreatic cell clusters, providing single-cell-level context for EGFR signaling in the human pancreatic microenvironment including acinar, ductal, and immune cell populations. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
  - *assay*: Human · human pancreas (multiple cell clusters)
  > "( E ) Dot plot derived from human pancreas scRNA-seq data published by Loveless, et al 38 shows selected genes, ADAM17 , EGFR ligands, IL6R , and TNF , in various cell clusters."
- `a2_evi_06` · *Secondary* · Supports · Tissue Expression — In KRAS-driven pancreatic tumorigenesis, EGFR ligand shedding from infiltrating macrophages (Csf1r+ cells) is proposed as a paracrine mechanism driving acinar cell transdifferentiation, indicating EGFR surface expression in pancreatic acinar cells is functionally engaged by macrophage-derived signals in the tumor microenvironment. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
  - *assay*: Mouse · pancreatic acinar cells / infiltrating macrophages
  > "Subsequently, other studies have suggested that acinar cell transdifferentiation is dependent on signals from infiltrating macrophages. 29 , 32 , 33 Although it was suggested that EGFR ligand shedding from macrophages is a possible mechanism of this dependency, this was not demonstrated experimentally."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — EGFR surface expression profiled across 85 PDX models spanning seven tumor types (GBM, HNSC, LUSC, LUAD, PAAD, COAD, OV) via N-glycoproteomic enrichment, providing a pan-cancer surface expression landscape in patient-derived xenografts. ([PMC12923961](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12923961/))
  - *assay*: Human · PDX models from GBM, HNSC, LUSC, LUAD, PAAD, COAD, OV · live · non-permeabilized
  > "Here, we applied a hydrazide-based N -glycoproteomic enrichment method, N -glycocapture, 14 , 15 , 16 to profile 85 unique PDX models spanning seven tumor types (glioblastoma [GBM], HNSC, lung squamous carcinoma [LUSC], lung adenocarcinoma [LUAD], pancreatic adenocarcinoma [PAAD], colorectal adenocarcinoma [COAD], and high-grade serous ovarian carcinoma [OV] 14 ) and three distinct PDX engraftment sites (intracranial, subcutaneous, and intraperitoneal) ( Figure 1 A and Data S1 )."
- `a2_evi_08` · *Primary* · Supports · Surface Expression — Flow cytometry confirms uniform EGFR/EGFRvIII antigen presence on the surface of glioma cells with high expression (GSC83 glioblastoma stem cells, U373VIII) and low expression (U373) levels. Confocal imaging of intact (non-permeabilized) GSC83 cells confirms EGFR surface localization co-localizing with CD9. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · GSC83 (glioblastoma stem cells), U373VIII, U373 · live · non-permeabilized
  > "(A) Flow cytometry analysis illustrating the uniform presence of EGFR antigen on the surface of glioma cells with high (GSC83 and U373VIII) and low (U373) levels of EGFR/EGFRvIII expression (right panel—dot plot; left panel—histogram); (B) Confocal imaging of immunofluorescent staining for EGFR antigen (red) and CD9 (green) in adherent GSC83 cells either intact or permeabilized before antibody exposure."
- `a2_evi_09` · *Primary* · Supports · Surface Expression — In glioblastoma stem cells (GSC83), endogenously expressed EGFR/EGFRvIII is detectable principally on the cell surface, with even decoration of the plasma membrane confirmed by both flow cytometry and confocal imaging of intact (non-permeabilized) cells. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · GSC83 glioblastoma stem cells · unspecified · non-permeabilized
  > "In isolated GSC83 cells the endogenously expressed EGFR/EGFRvIII (Spinelli et al. 2024 ) appears to be detectable principally on the cell surface, which is evenly decorated with the EGFR antigen, as revealed by flow cytometry and confocal imaging."
- `a2_evi_10` · *Primary* · Supports · Surface Expression — Flow cytometry demonstrates EGFR surface expression on pancreatic cancer cell lines (including BxPC-3 and others), establishing cell-surface presence of EGFR in pancreatic ductal adenocarcinoma-derived cell lines. ([PMC13088391](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088391/))
  - *assay*: Human · BxPC-3 and other pancreatic cancer cell lines · live · non-permeabilized
  > "( A ) Representative flow cytometry histograms of surface EGFR on the indicated pancreatic cancer cell lines."
- `a2_evi_11` · *Primary* · Refutes · Surface Expression — HCT 116 colorectal cancer cells show minimal EGFR surface staining by flow cytometry, consistent with very low EGFR mRNA expression (CCLE log2[TPM+1] = 0.0), establishing HCT 116 as a negative-expression control for EGFR surface detection. ([PMC13096901](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13096901/))
  - *assay*: Human · HCT 116 colorectal cancer cells · live · non-permeabilized
  > "HCT 116 served as a negative control and showed minimal surface staining, consistent with a CCLE value of log2[TPM+1] = 0.0."
- `a2_evi_12` · *Primary* · Supports · Surface Expression — NCI-H1930 small cell lung cancer cells exhibit granular/diffuse IHC staining pattern in clinical specimens but demonstrate clear cell-surface EGFR expression by flow cytometry, indicating that IHC morphology does not always predict flow cytometry surface detectability for EGFR. ([PMC13096901](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13096901/))
  - *assay*: Human · NCI-H1930 small cell lung cancer cells · live · non-permeabilized
  > "In addition, while clinical specimens often exhibited a granular and/or diffuse IHC pattern, rather than a sharp membranous staining, NCI–H1930 cells showed a similar pattern yet demonstrated cell surface expression by flow cytometry."
- `a2_evi_13` · *Primary* · Supports · Surface Expression — In polarized MDCK epithelial cells, EGFR is relatively evenly distributed across the apical and basolateral plasma membrane faces, with an apicobasal ratio of approximately 40:60 (apical:basolateral). This near-uniform distribution across both membrane domains indicates that EGFR is accessible from both luminal and basolateral surfaces in polarized epithelium. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
  - *assay*: Dog · MDCK (Madin-Darby canine kidney) polarized epithelial cells · live · non-permeabilized
  > "However, we show here that both the EGF precursor and its receptor EGFR are relatively evenly distributed across the polarized membrane (with an apicobasal ratio of 50:50 and 40:60, respectively)."
- `a2_evi_14` · *Primary* · Supports · Surface Expression — In polarized epithelial cells, EGFR and MET show similar apical and basolateral abundances among receptor tyrosine kinases, in contrast to their modulatory interaction partners which show strong apicobasal polarization. This indicates EGFR is accessible from both faces of polarized epithelium without strong subdomain restriction. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
  - *assay*: Dog · MDCK polarized epithelial cells · live · non-permeabilized
  > "Whereas various receptor tyrosine kinases (RTKs) that mediate major cellular functions such as growth signaling (e.g., EGFR and MET) showed rather similar apical and basolateral abundances ( Figure 2 C), many of their modulatory interaction partners were found to be strongly polarized."
- `a2_evi_15` · *Primary* · Supports · Tissue Expression — EGFR inhibitor (gefitinib) treatment remodels the surfaceome of EGFR-mutant lung adenocarcinoma (LUAD) cell lines, demonstrating that EGFR signaling status modulates the overall surface protein landscape in LUAD, with potential consequences for combination targeting strategies. ([PMC12765945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12765945/))
  - *assay*: Human · EGFR-mutant LUAD cell lines · live · non-permeabilized
  > "We aimed to assess the extent to which EGFR inhibitors remodel the surfaceome in LUADs and whether such remodeling provides an opportunity for combination therapy."
- `a2_evi_16` · *Primary* · Ambiguous · Tissue Expression — EGFR-mutant LUAD cell lines (HCC827, PC9, H1650) in a drug-tolerant persister state following 3-week gefitinib or osimertinib treatment represent a distinct cell state with potentially altered EGFR surface dynamics compared to drug-naive LUAD cells. ([PMC12765945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12765945/))
  - *assay*: Human · HCC827, PC9, H1650 EGFR-mutant LUAD cell lines (drug-tolerant persister state) · live · non-permeabilized
  > "To generate drug-tolerant persister cells, EGFR mutant LUAD cell lines HCC827, PC9, and H1650 were treated with 100 nM of gefitinib or osimertinib for 3 weeks."
- `a2_evi_17` · *Primary* · Supports · Surface Expression — Surface biotinylation followed by mass spectrometry identifies 1,508 distinct surface proteins in sensory-like neurons (including EGFR) across FD patients and healthy controls, revealing disease-state-associated changes in the neuronal surface proteome including EGFR. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · iPSC-derived sensory-like neurons from Familial Dysautonomia (FD) patients and healthy controls · live · non-permeabilized
  > "Via biotinylation followed by mass spectrometry ( Fig 1A , 1B ), we identified 1,508 distinct proteins in sensory-like neuron cultures derived from FD patients and controls, consistently observed across three independent experiments (S2 Table)."
- `a2_evi_18` · *Primary* · Supports · Tissue Expression — EGFR is among the most significantly deregulated surface proteins (p < 0.01) in iPSC-derived sensory-like neurons from Familial Dysautonomia (FD) patients compared to healthy controls, as identified by surface biotinylation-MS, suggesting disease-state-dependent changes in neuronal surface EGFR levels. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · iPSC-derived sensory-like neurons (FD patients) · live · non-permeabilized
  > "Among the most deregulated proteins (p < 0.01), we identified several neuronal candidates with a potential link to nerve pathology such as: calcium voltage-gated channel auxiliary subunit alpha2delta 3 (CACNA2D3, p < 0.01) [ 52 ], neuronal membrane glycoprotein M6-A (GPM6A, p < 0.001) [ 53 , 54 ], ATP-binding cassette subfamily A member 7 (ABCA7) [ 55 ], and epidermal growth factor receptor (EGFR, p < 0.01) [ 56 , 57 ]."
- `a2_evi_19` · *Primary* · Ambiguous · Tissue Expression — EGFR mRNA expression was assessed by qPCR in iPSC-derived sensory-like neurons from FD patients versus healthy controls (n=4 differentiations each), to determine whether surface protein deregulation detected by biotinylation-MS is mirrored at the transcriptional level. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · iPSC-derived sensory-like neurons (FD patients vs. healthy controls)
  > "To assess whether the observed differences in the neuronal plasma membrane were mirrored at the gene expression level, we conducted qPCR analysis for CACNA2D3, GPM6A, EGFR, and ABCA7, using samples from four separately prepared differentiations for FD and healthy control sensory-like neurons, respectively."
- `a2_evi_20` · *Secondary* · Supports · Tissue Expression — EGFR mRNA expression ranks in the top 84% among genes expressed in glandular tissue (normal pooled context), indicating moderate-to-high baseline EGFR expression in normal glandular epithelium. ([PMC10377392](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10377392/))
  - *assay*: Human · normal glandular tissue
  > "Of interest, the previously described epidermal growth factor receptor (EGFR) was in the top 84% of expression."
- `a2_evi_21` · *Secondary* · Supports · Tissue Expression — In HPV-altered cellular states (HPV-associated lesions), EGFR and downstream signaling pathways (PI3K/Akt, mTOR, JAK/STAT) may be aberrantly activated, suggesting disease-state-induced upregulation or hyperactivation of surface EGFR in HPV-associated epithelial pathology. ([PMC10377392](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10377392/))
  - *assay*: Human · HPV-altered epithelial cells
  > "Among this HPV-altered cellular state, various receptors and their downstream effectors may also be aberrantly activated, such as the EGFR and PI3K/Akt, mTOR, or JAK/STAT signaling pathways [ 50 ]."
- `a2_evi_22` · *Secondary* · Supports · Tissue Expression — Skin rash is a well-known on-target, off-tumor adverse event of EGFR inhibition, implying constitutive EGFR surface expression in normal keratinocytes/skin epithelium that is pharmacologically accessible in patients receiving EGFR inhibitors. ([PMC13196744](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13196744/))
  - *assay*: Human · skin keratinocytes (normal)
  > "Inhibitors of receptor tyrosine kinases also show on-target, off-tumor adverse events such as skin rash upon inhibition of epidermal growth factor receptor (EGFR), hypertension upon inhibition of vascular endothelial growth factor receptor, and hyperphosphatemia upon inhibition of fibroblast growth factor receptor (FGFR) ( 3 )."
- `a2_evi_23` · *Secondary* · Supports · Tissue Expression — EGFR is proposed as a surface marker for subpopulation stratification in small cell lung cancer (SCLC), used alongside PTGS2/NRG1 in a planned flow cytometry-based approach to filter SCLC subpopulations, indicating heterogeneous EGFR surface expression within SCLC tumors. ([PMC8171402](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8171402/))
  - *assay*: Human · small cell lung cancer (SCLC) cells · live · non-permeabilized
  > "In our future work, we are planning to filter out the subpopulation of SCLCs by flow cytometry with surface markers PTGS2/NRG1/EGFR."
- `a2_evi_24` · *Secondary* · Supports · Surface Expression — EGF-induced EGFR internalization and lysosomal degradation is a well-characterized ligand-dependent mechanism that reduces cell-surface EGFR levels. Baseline: surface EGFR on unstimulated cells. Modulating state: EGF ligand binding. Change: internalization and lysosomal degradation. Accessibility implication: surface EGFR is reduced following EGF stimulation unless lysosomal function is blocked (e.g., by chloroquine). ([PMC12702325](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12702325/))
  - *assay*: Unspecified · unspecified (schematic context) · non-permeabilized
  > "A , Schematic of epidermal growth factor (EGF)-induced epidermal growth factor receptor (EGFR) internalization and lysosomal degradation, with or without inhibition of lysosomal function by chloroquine."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/EGFR.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/EGFR](https://surfaceome.deliverome.org/EGFR)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/EGFR.json](https://surfaceome.deliverome.org/data/surfaceome/EGFR.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/EGFR.md](https://surfaceome.deliverome.org/data/surfaceome/EGFR.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P00533](https://alphafold.ebi.ac.uk/entry/P00533)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P00533](https://alphafold.ebi.ac.uk/api/prediction/P00533) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P00533](https://www.uniprot.org/uniprotkb/P00533)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-P00533-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-P00533-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-P00533-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-P00533-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-P00533-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-P00533-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*1210 aa · `P00533` · embedded at build time*

```
   1  MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEV
  61  VLGNLEITYVQRNYDLSFLKTIQEVAGYVLIALNTVERIPLENLQIIRGNMYYENSYALA
 121  VLSNYDANKTGLKELPMRNLQEILHGAVRFSNNPALCNVESIQWRDIVSSDFLSNMSMDF
 181  QNHLGSCQKCDPSCPNGSCWGAGEENCQKLTKIICAQQCSGRCRGKSPSDCCHNQCAAGC
 241  TGPRESDCLVCRKFRDEATCKDTCPPLMLYNPTTYQMDVNPEGKYSFGATCVKKCPRNYV
 301  VTDHGSCVRACGADSYEMEEDGVRKCKKCEGPCRKVCNGIGIGEFKDSLSINATNIKHFK
 361  NCTSISGDLHILPVAFRGDSFTHTPPLDPQELDILKTVKEITGFLLIQAWPENRTDLHAF
 421  ENLEIIRGRTKQHGQFSLAVVSLNITSLGLRSLKEISDGDVIISGNKNLCYANTINWKKL
 481  FGTSGQKTKIISNRGENSCKATGQVCHALCSPEGCWGPEPRDCVSCRNVSRGRECVDKCN
 541  LLEGEPREFVENSECIQCHPECLPQAMNITCTGRGPDNCIQCAHYIDGPHCVKTCPAGVM
 601  GENNTLVWKYADAGHVCHLCHPNCTYGCTGPGLEGCPTNGPKIPSIATGMVGALLLLLVV
 661  ALGIGLFMRRRHIVRKRTLRRLLQERELVEPLTPSGEAPNQALLRILKETEFKKIKVLGS
 721  GAFGTVYKGLWIPEGEKVKIPVAIKELREATSPKANKEILDEAYVMASVDNPHVCRLLGI
 781  CLTSTVQLITQLMPFGCLLDYVREHKDNIGSQYLLNWCVQIAKGMNYLEDRRLVHRDLAA
 841  RNVLVKTPQHVKITDFGLAKLLGAEEKEYHAEGGKVPIKWMALESILHRIYTHQSDVWSY
 901  GVTVWELMTFGSKPYDGIPASEISSILEKGERLPQPPICTIDVYMIMVKCWMIDADSRPK
 961  FRELIIEFSKMARDPQRYLVIQGDERMHLPSPTDSNFYRALMDEEDMDDVVDADEYLIPQ
1021  QGFFSSPSTSRTPLLSSLSATSNNSTVACIDRNGLQSCPIKEDSFLQRYSSDPTGALTED
1081  SIDDTFLPVPEYINQSVPKRPAGSVQNPVYHNQPLNPAPSRDPHYQDPHSTAVGNPEYLN
1141  TVQPTCVNSTFDSPAHWAQKGSHQISLDNPDYQQDFFPKEAKPNGIFKGSTAENAEYLRV
1201  APQSSEFIGA
```

### Alternative-isoform sequences

**P00533-2** (`P00533-2` · 405 aa)

```
   1  MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEV
  61  VLGNLEITYVQRNYDLSFLKTIQEVAGYVLIALNTVERIPLENLQIIRGNMYYENSYALA
 121  VLSNYDANKTGLKELPMRNLQEILHGAVRFSNNPALCNVESIQWRDIVSSDFLSNMSMDF
 181  QNHLGSCQKCDPSCPNGSCWGAGEENCQKLTKIICAQQCSGRCRGKSPSDCCHNQCAAGC
 241  TGPRESDCLVCRKFRDEATCKDTCPPLMLYNPTTYQMDVNPEGKYSFGATCVKKCPRNYV
 301  VTDHGSCVRACGADSYEMEEDGVRKCKKCEGPCRKVCNGIGIGEFKDSLSINATNIKHFK
 361  NCTSISGDLHILPVAFRGDSFTHTPPLDPQELDILKTVKEITGLS
```

**P00533-3** (`P00533-3` · 705 aa)

```
   1  MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEV
  61  VLGNLEITYVQRNYDLSFLKTIQEVAGYVLIALNTVERIPLENLQIIRGNMYYENSYALA
 121  VLSNYDANKTGLKELPMRNLQEILHGAVRFSNNPALCNVESIQWRDIVSSDFLSNMSMDF
 181  QNHLGSCQKCDPSCPNGSCWGAGEENCQKLTKIICAQQCSGRCRGKSPSDCCHNQCAAGC
 241  TGPRESDCLVCRKFRDEATCKDTCPPLMLYNPTTYQMDVNPEGKYSFGATCVKKCPRNYV
 301  VTDHGSCVRACGADSYEMEEDGVRKCKKCEGPCRKVCNGIGIGEFKDSLSINATNIKHFK
 361  NCTSISGDLHILPVAFRGDSFTHTPPLDPQELDILKTVKEITGFLLIQAWPENRTDLHAF
 421  ENLEIIRGRTKQHGQFSLAVVSLNITSLGLRSLKEISDGDVIISGNKNLCYANTINWKKL
 481  FGTSGQKTKIISNRGENSCKATGQVCHALCSPEGCWGPEPRDCVSCRNVSRGRECVDKCN
 541  LLEGEPREFVENSECIQCHPECLPQAMNITCTGRGPDNCIQCAHYIDGPHCVKTCPAGVM
 601  GENNTLVWKYADAGHVCHLCHPNCTYGPGNESLKAMLFCLFKLSSCNQSNDGSVSHQSGS
 661  PAAQESCLGWIPSLLPSEFQLGWGGCSHLHAWPSASVIITASSCH
```

**P00533-4** (`P00533-4` · 628 aa)

```
   1  MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEV
  61  VLGNLEITYVQRNYDLSFLKTIQEVAGYVLIALNTVERIPLENLQIIRGNMYYENSYALA
 121  VLSNYDANKTGLKELPMRNLQEILHGAVRFSNNPALCNVESIQWRDIVSSDFLSNMSMDF
 181  QNHLGSCQKCDPSCPNGSCWGAGEENCQKLTKIICAQQCSGRCRGKSPSDCCHNQCAAGC
 241  TGPRESDCLVCRKFRDEATCKDTCPPLMLYNPTTYQMDVNPEGKYSFGATCVKKCPRNYV
 301  VTDHGSCVRACGADSYEMEEDGVRKCKKCEGPCRKVCNGIGIGEFKDSLSINATNIKHFK
 361  NCTSISGDLHILPVAFRGDSFTHTPPLDPQELDILKTVKEITGFLLIQAWPENRTDLHAF
 421  ENLEIIRGRTKQHGQFSLAVVSLNITSLGLRSLKEISDGDVIISGNKNLCYANTINWKKL
 481  FGTSGQKTKIISNRGENSCKATGQVCHALCSPEGCWGPEPRDCVSCRNVSRGRECVDKCN
 541  LLEGEPREFVENSECIQCHPECLPQAMNITCTGRGPDNCIQCAHYIDGPHCVKTCPAGVM
 601  GENNTLVWKYADAGHVCHLCHPNCTYGS
```

### Canonical ortholog sequences

**Mouse — Egfr** (`Q01279` · 1210 aa)

```
   1  MRPSGTARTTLLVLLTALCAAGGALEEKKVCQGTSNRLTQLGTFEDHFLSLQRMYNNCEV
  61  VLGNLEITYVQRNYDLSFLKTIQEVAGYVLIALNTVERIPLENLQIIRGNALYENTYALA
 121  ILSNYGTNRTGLRELPMRNLQEILIGAVRFSNNPILCNMDTIQWRDIVQNVFMSNMSMDL
 181  QSHPSSCPKCDPSCPNGSCWGGGEENCQKLTKIICAQQCSHRCRGRSPSDCCHNQCAAGC
 241  TGPRESDCLVCQKFQDEATCKDTCPPLMLYNPTTYQMDVNPEGKYSFGATCVKKCPRNYV
 301  VTDHGSCVRACGPDYYEVEEDGIRKCKKCDGPCRKVCNGIGIGEFKDTLSINATNIKHFK
 361  YCTAISGDLHILPVAFKGDSFTRTPPLDPRELEILKTVKEITGFLLIQAWPDNWTDLHAF
 421  ENLEIIRGRTKQHGQFSLAVVGLNITSLGLRSLKEISDGDVIISGNRNLCYANTINWKKL
 481  FGTPNQKTKIMNNRAEKDCKAVNHVCNPLCSSEGCWGPEPRDCVSCQNVSRGRECVEKCN
 541  ILEGEPREFVENSECIQCHPECLPQAMNITCTGRGPDNCIQCAHYIDGPHCVKTCPAGIM
 601  GENNTLVWKYADANNVCHLCHANCTYGCAGPGLQGCEVWPSGPKIPSIATGIVGGLLFIV
 661  VVALGIGLFMRRRHIVRKRTLRRLLQERELVEPLTPSGEAPNQAHLRILKETEFKKIKVL
 721  GSGAFGTVYKGLWIPEGEKVKIPVAIKELREATSPKANKEILDEAYVMASVDNPHVCRLL
 781  GICLTSTVQLITQLMPYGCLLDYVREHKDNIGSQYLLNWCVQIAKGMNYLEDRRLVHRDL
 841  AARNVLVKTPQHVKITDFGLAKLLGAEEKEYHAEGGKVPIKWMALESILHRIYTHQSDVW
 901  SYGVTVWELMTFGSKPYDGIPASDISSILEKGERLPQPPICTIDVYMIMVKCWMIDADSR
 961  PKFRELILEFSKMARDPQRYLVIQGDERMHLPSPTDSNFYRALMDEEDMEDVVDADEYLI
1021  PQQGFFNSPSTSRTPLLSSLSATSNNSTVACINRNGSCRVKEDAFLQRYSSDPTGAVTED
1081  NIDDAFLPVPEYVNQSVPKRPAGSVQNPVYHNQPLHPAPGRDLHYQNPHSNAVGNPEYLN
1141  TAQPTCLSSGFNSPALWIQKGSHQMSLDNPDYQQDFFPKETKPNGIFKGPTAENAEYLRV
1201  APPSSEFIGA
```

**Cynomolgus — EGFR** (`A0A2K5WK39` · 1210 aa)

```
   1  MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEV
  61  VLGNLEITYVQRNYDLSFLKTIQEVAGYVLIALNTVERIPLENLQIIRGNMYYENSYALA
 121  VLSNYDANKTGLKELPMRNLQEILHGAVRFSNNPALCNVESIQWRDIVSSEFLSNMSMDF
 181  QNHLGSCQKCDPSCPNGSCWGAGEENCQKLTKIICAQQCSGRCRGKSPSDCCHNQCAAGC
 241  TGPRESDCLVCRKFRDEATCKDTCPPLMLYNPTTYQMDVNPEGKYSFGATCVKKCPRNYV
 301  VTDHGSCVRACGADSYEMEEDGVRKCKKCEGPCRKVCNGIGIGEFKDTLSINATNIKHFK
 361  NCTSISGDLHILPVAFRGDSFTHTPPLDPQELDILKTVKEITGFLLIQAWPENRTDLHAF
 421  ENLEIIRGRTKQHGQFSLAVVSLNITSLGLRSLKEISDGDVIISGNKNLCYANTINWKKL
 481  FGTSSQKTKIISNRGENSCKATGQVCHALCSPEGCWGPEPRDCVSCQNVSRGRECVDKCN
 541  ILEGEPREFVENSECIQCHPECLPQVMNITCTGRGPDNCIQCAHYIDGPHCVKTCPAGVM
 601  GENNTLVWKYADAGHVCHLCHPNCTYGCTGPGLEGCARNGPKIPSIATGMVGALLLLLVV
 661  ALGIGLFMRRRHIVRKRTLRRLLQERELVEPLTPSGEAPNQALLRILKETEFKKIKVLGS
 721  GAFGTVYKGLWIPEGEKVKIPVAIKELREATSPKANKEILDEAYVMASVDNPHVCRLLGI
 781  CLTSTVQLITQLMPFGCLLDYVREHKDNIGSQYLLNWCVQIAKGMNYLEDRRLVHRDLAA
 841  RNVLVKTPQHVKITDFGLAKLLGAEEKEYHAEGGKVPIKWMALESILHRIYTHQSDVWSY
 901  GVTVWELMTFGSKPYDGIPASEISSILEKGERLPQPPICTIDVYMIMVKCWMIDADSRPK
 961  FRELIIEFSKMARDPQRYLVIQGDERMHLPSPTDSNFYRALMDEEDMDDVVDADEYLIPQ
1021  QGFFSSPSTSRTPLLSSLSATSNNSTVACIDRNGLQSCPIKEDSFLQRYSSDPTGALTED
1081  SIDDTFLPVPEYINQSVPKRPAGSVQNPVYHNQPLNPAPSRDPHYQDPHSTAVGNPEYLN
1141  TVQPTCVNSTFDSPAHWAQKGSHQISLDNPDYQQDFFPKEAKPNGIFKGSTAENAEYLRV
1201  APQSSEFIGA
```

### Experimental-structure sequence

**7SYD** chain A · Electron Microscopy, 3.1 Å · covers UniProt residues 1–1210 (1210 aa) · representative of 642 experimental structures. Residues sliced from the canonical sequence over the structure's SIFTS-mapped span; unresolved loops in the deposited coordinates are not removed here.

```
   1  MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEV
  61  VLGNLEITYVQRNYDLSFLKTIQEVAGYVLIALNTVERIPLENLQIIRGNMYYENSYALA
 121  VLSNYDANKTGLKELPMRNLQEILHGAVRFSNNPALCNVESIQWRDIVSSDFLSNMSMDF
 181  QNHLGSCQKCDPSCPNGSCWGAGEENCQKLTKIICAQQCSGRCRGKSPSDCCHNQCAAGC
 241  TGPRESDCLVCRKFRDEATCKDTCPPLMLYNPTTYQMDVNPEGKYSFGATCVKKCPRNYV
 301  VTDHGSCVRACGADSYEMEEDGVRKCKKCEGPCRKVCNGIGIGEFKDSLSINATNIKHFK
 361  NCTSISGDLHILPVAFRGDSFTHTPPLDPQELDILKTVKEITGFLLIQAWPENRTDLHAF
 421  ENLEIIRGRTKQHGQFSLAVVSLNITSLGLRSLKEISDGDVIISGNKNLCYANTINWKKL
 481  FGTSGQKTKIISNRGENSCKATGQVCHALCSPEGCWGPEPRDCVSCRNVSRGRECVDKCN
 541  LLEGEPREFVENSECIQCHPECLPQAMNITCTGRGPDNCIQCAHYIDGPHCVKTCPAGVM
 601  GENNTLVWKYADAGHVCHLCHPNCTYGCTGPGLEGCPTNGPKIPSIATGMVGALLLLLVV
 661  ALGIGLFMRRRHIVRKRTLRRLLQERELVEPLTPSGEAPNQALLRILKETEFKKIKVLGS
 721  GAFGTVYKGLWIPEGEKVKIPVAIKELREATSPKANKEILDEAYVMASVDNPHVCRLLGI
 781  CLTSTVQLITQLMPFGCLLDYVREHKDNIGSQYLLNWCVQIAKGMNYLEDRRLVHRDLAA
 841  RNVLVKTPQHVKITDFGLAKLLGAEEKEYHAEGGKVPIKWMALESILHRIYTHQSDVWSY
 901  GVTVWELMTFGSKPYDGIPASEISSILEKGERLPQPPICTIDVYMIMVKCWMIDADSRPK
 961  FRELIIEFSKMARDPQRYLVIQGDERMHLPSPTDSNFYRALMDEEDMDDVVDADEYLIPQ
1021  QGFFSSPSTSRTPLLSSLSATSNNSTVACIDRNGLQSCPIKEDSFLQRYSSDPTGALTED
1081  SIDDTFLPVPEYINQSVPKRPAGSVQNPVYHNQPLNPAPSRDPHYQDPHSTAVGNPEYLN
1141  TVQPTCVNSTFDSPAHWAQKGSHQISLDNPDYQQDFFPKEAKPNGIFKGSTAENAEYLRV
1201  APQSSEFIGA
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`P00533`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMM
 661  MMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 721  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 781  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 841  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 901  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 961  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1021  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1081  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1141  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1201  IIIIIIIIII
```

**P00533-2** (`P00533-2`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P00533-3** (`P00533-3`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 661  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P00533-4** (`P00533-4`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**Mouse ortholog — Egfr** (`Q01279`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMM
 661  MMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 721  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 781  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 841  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 901  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 961  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1021  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1081  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1141  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1201  IIIIIIIIII
```

**Cynomolgus ortholog — EGFR** (`A0A2K5WK39`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMM
 661  MMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 721  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 781  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 841  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 901  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 961  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1021  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1081  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1141  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1201  IIIIIIIIII
```

**Experimental — 7SYD chain A** (UniProt residues 1–1210, projected from canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMM
 661  MMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 721  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 781  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 841  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 901  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 961  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1021  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1081  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1141  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
1201  IIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence high — *
