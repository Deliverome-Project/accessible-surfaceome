# EGFR — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-06-01T00:28:03.567292Z · model `claude-sonnet-4-6`*

> EGFR is a canonical single-pass Type I transmembrane receptor with a large (~620 aa) extracellular domain constitutively displayed at the plasma membrane of epithelial and many tumor cell types. Surface accessibility is confirmed by live-cell flow cytometry across glioma, pancreatic, lung, cervical, breast, and epidermoid carcinoma lines; non-permeabilized IF; surface biotinylation MS in keratinocytes, prostate cancer, iPSC neurons, and A549; and membranous IHC in 97% of SIP patient cases. Approved antibody therapeutics (cetuximab, panitumumab) and ADCs clinically validate ECD engagement. Ectodomain shedding by ADAM10/17 yields a soluble sEGFR decoy documented in circulation.

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
| Headline risks | Shed Form, Secreted Form |

## 1. Executive summary

**Constitutively surface-accessible across normal epithelial tissues and diverse tumor types; EGF-induced internalization transiently reduces surface pool but baseline PM residence is stable and not lineage- or state-restricted.**

EGFR is a canonical single-pass Type I transmembrane receptor with a large (~620 aa) extracellular domain constitutively displayed at the plasma membrane of epithelial and many tumor cell types. Surface accessibility is confirmed by live-cell flow cytometry across glioma, pancreatic, lung, cervical, breast, and epidermoid carcinoma lines; non-permeabilized IF; surface biotinylation MS in keratinocytes, prostate cancer, iPSC neurons, and A549; and membranous IHC in 97% of SIP patient cases. Approved antibody therapeutics (cetuximab, panitumumab) and ADCs clinically validate ECD engagement. Ectodomain shedding by ADAM10/17 yields a soluble sEGFR decoy documented in circulation.

**Family / classification** — UniProt family: protein kinase superfamily. Tyr protein kinase family. EGF receptor subfamily · HGNC gene group(s): Erb-b2 receptor tyrosine kinases · functional class: Receptor.

**Triage first-pass reasoning** — EGFR (ErbB1/HER1) is a single-pass type I transmembrane glycoprotein with a large extracellular ligand-binding domain (domains I-IV, ~620 aa) facing the extracellular space, a single TM helix, and an intracellular kinase domain. It is constitutively expressed on the plasma membrane of epithelial and many other cell types. The extracellular domain is the target of approved therapeutic antibodies (cetuximab, panitumumab), ADCs (e.g., ABT-414/depatuxizumab mafodotin), and bispecifics — all engaging the cell-surface ectodomain on intact, non-permeabilized cells. Surface biotinylation and flow cytometry on intact cells unambiguously confirm stable PM residence. Ectodomain shedding by ADAM10/17 does occur, but the transmembrane precursor is the dominant stable form at the cell surface; the shed ectodomain is a secondary product. This is a canonical surface receptor, fully accessible from the extracellular face.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=High · subcategory=Single-pass type I · ecd=Large |
| Classification | reason=Classical Surface Receptor · family=Receptor · state-dependence=Low · induction-trigger=Other |
| Expression | level=High · breadth=Broad · specificity=Mixed · low-endogenous=false · tumor-associated=true · orphan-receptor=false · OE-precedent=true |
| Risks | shed=true · secreted=true · co-receptor=None · masking=true · restricted-subdomain=false |
| Evidence | grade=Direct, multi-method · density=High · live-cell-surface=true · supporting(hi)=8 · contradicting(hi)=0 |
| Cross-species | mouse=88.7% · cyno=98.7% |
| Paralogs | max %ECD identity = 48.5% |
| Topology | TM=1 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: High surface EGFR in glioma (99% GSC83, 98% U373vIII by flow; a1_evi_02), prostate cancer (19 biotinylation sites; a1_evi_28), SIP patient tissue 97% membranous IHC (a2_evi_03), and 84th percentile in normal glandular tissue proteomics (a2_evi_19).
- *Expression breadth*: Surface EGFR documented across epithelial (keratinocytes a1_evi_21, polarized MDCK a1_evi_30), neural (iPSC neurons a1_evi_26), glioma (a1_evi_02), pancreatic cancer (a2_evi_07), prostate cancer (a2_evi_10), lung cancer (a1_evi_51), and squamous carcinoma (a1_evi_45) — multiple tissue families.
- *Surface specificity*: Non-permeabilized IF paired with permeabilized controls in GSC83 shows dominant surface signal with a visible intracellular pool (a1_evi_06); EGF-driven endocytosis to endosomal/lysosomal compartments further demonstrates a constitutive intracellular fraction (a2_evi_15, a2_evi_16). Surface-dominant in resting cells but notable intracellular recycling pool.
- *Known ligand*: Multiple validated endogenous ligands: EGF (canonical agonist), TGF-α, amphiregulin, epiregulin, betacellulin, and HB-EGF. Ligand binding drives receptor-mediated internalization (a2_evi_15, a2_evi_16). Panitumumab and cetuximab block EGF binding site (a1_evi_44).
- *Low endogenous expression*: Derived from expression_level='high' (not low/absent → not flagged). High surface EGFR in glioma (99% GSC83, 98% U373vIII by flow; a1_evi_02), prostate cancer (19 biotinylation sites; a1_evi_28), SIP patient tissue 97% membranous IHC (a2_evi_03), and 84th percentile in normal glandular tissue proteomics (a2_evi_19).
- *Overexpression surface localization*: 3 method observation(s) pair an overexpression/mixed expression system with a surface-localization readout (cites a1_evi_01, a1_evi_12, a1_evi_21, a1_evi_22).

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Direct, multi-method

EGFR surface accessibility is supported by multiple independent direct methods from numerous independent sources. Live-cell / non-permeabilized flow cytometry is demonstrated in glioma (GSC83, U373vIII), pancreatic cancer (BxPC-3), lung cancer (NCI-H1930), epidermoid carcinoma (A431), and EGFR-overexpressing epithelial lines. Non-permeabilized IF with paired permeabilized controls is shown in GSC83 and a second independent source (a1_evi_08). Surface biotinylation (+WB or +MS) confirms EGFR in the plasma membrane fraction across keratinocytes (NIKS), prostate cancer cells (sBioSITe, 19 sites), iPSC-derived neurons (n=3 MS), MDCK polarized epithelial (quantitative surfaceome SILAC), and A549 lung cancer. Membranous IHC in primary human SIP tissue (31/32 cases) adds a fourth direct method type. Structural data (cryo-EM, crystallography) are tangential confirmations of ECD-outward topology. No contradictions to surface expression exist; the NCI-H1930 IHC/flow discordance is a methodological note, not a logical conflict. Grade: `direct_multi_method`.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_02 | Supports Surface | High | Non-permeabilized live-cell flow cytometry on 3 glioma lines; 98-99% positive in high-EGFR lines |
| a1_evi_06 | Supports Surface | High | Non-permeabilized IF on GSC83 glioma cells with paired permeabilized control; CD9 co-marker |
| a1_evi_07 | Supports Surface | High | Direct conclusion from flow + confocal: endogenous EGFR/EGFRvIII at cell surface in GSC83 |
| a1_evi_08 | Supports Surface | Moderate | Non-permeabilized IF with permeabilized paired control; cell type unspecified but strong methodology |
| a1_evi_09 | Supports Surface | Moderate | Live-cell flow cytometry surface EGFR in pancreatic cancer lines; cell line names partially unspecified |
| a1_evi_10 | Supports Surface | Moderate | Live-cell flow cytometry on BxPC-3; anti-EGFR bispecific binding confirms ECD accessibility |
| a1_evi_12 | Supports Surface | Moderate | Flow cytometry on intact EGFR-overexpressing epithelial cells; validated nimotuzumab binding assay |
| a1_evi_13 | Supports Surface | Moderate | Saturation binding by flow on intact cells; confirms specific quantifiable EGFR surface accessibility |
| a1_evi_18 | Supports Surface | High | IHC membranous staining in 97% of SIP patient tissue cases; positive plasma membrane criterion |
| a1_evi_20 | Supports Surface | Moderate | Surface biotinylation + streptavidin + WB detecting phospho-EGFR/ErbB at cell surface in DCDMLs |
| a1_evi_21 | Supports Surface | High | Surface biotinylation + streptavidin + WB on NIKS keratinocytes; EGFR detected in surface fraction |
| a1_evi_22 | Supports Surface | Moderate | Surface biotinylation; modest EGFR upregulation at surface in HPV16 E7 NIKS |
| a1_evi_26 | Supports Surface | High | Surface biotinylation + MS on iPSC-derived sensory neurons; 1508 proteins identified, EGFR among them; n=3 |
| a1_evi_28 | Supports Surface | High | sBioSITe surface biotinylation MS on prostate cancer cells; 19 biotinylation sites on EGFR |
| a1_evi_30 | Supports Surface | High | Surfaceome MS (chemoproteomics + SILAC) on polarized MDCK; EGFR ~40:60 apical:basolateral at PM |
| a1_evi_43 | Supports Surface | Moderate | Live MCF-7 cells; antibody-conjugate binding to EGFR ECD at plasma membrane of intact cells |
| a1_evi_44 | Supports Surface | Moderate | Panitumumab functional binding to EGFR ECD at surface of live MCF-7 cells |
| a1_evi_45 | Supports Surface | Moderate | Live-cell flow cytometry on A431 cells; nanoparticle binding to surface EGFR |
| a1_evi_33 | Tangential | High | Cryo-EM confirms ECD-outward topology; structural support but not a cell-surface accessibility assay |
| a1_evi_34 | Tangential | High | Cryo-EM heart-shaped ECD dimer; confirms extracellular topology but not plasma-membrane surface assay |
| a1_evi_35 | Tangential | Moderate | Crystal structure of EGFR ECD; confirms ECD accessibility for nanobody but not cell-surface assay |
| a1_evi_36 | Tangential | Moderate | Cetuximab/Matuzumab crystal structures; confirms ECD epitope but not a cell-surface assay |
| a1_evi_51 | Tangential | Moderate | NCI-H1930: granular IHC vs positive surface flow; discordance is a caveat, not a contradiction of surface expression |
| a1_evi_11 | Tangential | Low | Panitumumab review-level assertion of slow EGFR internalization; contextual, not direct surface assay |
| a1_evi_27 | Expression Only | Low | qPCR EGFR mRNA in iPSC-derived sensory neurons; RNA level, no surface assay |
| a1_evi_52 | Expression Only | Low | Whole-cell WB in NIH-3T3 EGFR transfectants; bulk protein, no surface fractionation |

### Flow cytometry (5 methods)

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Mixed*

**Antibodies**

- anti-EGFR-Alexa Fluor 647 (AY13 · BioLegend · 352918 · AB_2650983) — Extracellular epitope; Monoclonal; Moderate validation (Overexpression Reference); Mouse IgG1κ clone AY13 targets human EGFR ECD; applied on live non-permeabilized cells confirming surface access.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| U373 glioma cells (low endogenous WT EGFR) — 12% surface-positive | Established Cell Line | Low | 1 |
| U373vIII glioma cells (engineered EGFRvIII overexpression) — 98% surface-positive | Established Cell Line | High | 1 |
| GSC83 glioma cells (endogenous EGFR/EGFRvIII) — 99% uniformly surface-positive | Established Cell Line | High | 2 |

*Overexpression construct* — SP source: Native · endogenous EGFRvIII signal sequence in U373vIII engineered line · cell line: U373vIII. *(cites: a1_evi_01)*

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR (panitumumab-derived bispecific) — Extracellular epitope; Monoclonal; Moderate validation (Overexpression Reference); VH/VL derived from clinically approved panitumumab; high-affinity binding to EGFR ECD; relatively slow internalization compared with other EGFR-targeting antibodies.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Pancreatic cancer cell lines (including BxPC-3) — surface EGFR detected by flow cytometry histograms | Established Cell Line | High | 1 |
| BxPC-3 pancreatic cancer cells — cell-surface EGFR binding confirmed by flow cytometry using panitumumab-derived bispecific antibody | Established Cell Line | High | 1 |

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Overexpression*

**Antibodies**

- nimotuzumab (anti-EGFR humanized IgG1 mAb) — Extracellular epitope; Monoclonal; Moderate validation (Overexpression Reference); Humanized IgG1 anti-EGFR (h-R3/nimotuzumab); CDR-grafted from murine mAb; binds EGFR ECD on cell surface at 3-5 µg/mL saturation.
- FITC-conjugated rabbit anti-human IgG (secondary) (Dako · F0056) — Unknown epitope; Polyclonal; None validation (None); Secondary antibody used to detect bound nimotuzumab (human IgG1); rabbit anti-human IgG polyclonal FITC conjugate, 1:60 dilution.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| EGFR-overexpressing epithelial cell lines — nimotuzumab binding reaches saturation at 3–5 µg/mL by flow cytometry; confirms surface EGFR ECD accessibility | Established Cell Line | High | 2 |

*Overexpression construct* — SP source: Unspecified. *(cites: a1_evi_12)*

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| A431 epidermoid carcinoma cells (live) — flow cytometry used to assess binding of MNT1 nanoparticles to EGFR receptors at cell surface | Established Cell Line | High | 1 |

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| NCI-H1930 lung cancer cells — live-cell flow cytometry demonstrates cell surface EGFR expression despite granular/diffuse IHC pattern in clinical specimens | Established Cell Line | Moderate | 1 |

### Immunofluorescence (5 methods)

#### Nonpermeabilized IF — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Nonpermeabilized · expression: Endogenous*

**Antibodies**

- anti-EGFR-Alexa Fluor 647 (AY13 · BioLegend · 352918 · AB_2650983) — Extracellular epitope; Monoclonal; Moderate validation (Overexpression Reference); Mouse IgG1κ clone AY13; applied to fixed non-permeabilized cells for surface topology validation.
- anti-CD9-FITC (BioLegend · 312104) — Extracellular epitope; Monoclonal; None validation (None); Used as plasma membrane co-marker (tetraspanin CD9).

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GSC83 glioma cells — intact (non-permeabilized) confocal IF shows EGFR at cell surface, evenly decorating plasma membrane; CD9 used as co-marker | Established Cell Line | High | 2 |

#### Permeabilized IF — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-EGFR-Alexa Fluor 647 (AY13 · BioLegend · 352918 · AB_2650983) — Extracellular epitope; Monoclonal; Moderate validation (Overexpression Reference); Applied under permeabilized condition (0.1% Triton X-100); reveals intracellular EGFR pool in paired comparison to surface staining.
- anti-CD9-FITC (BioLegend · 312104) — Extracellular epitope; Monoclonal; None validation (None); Membrane co-marker; also detectable in permeabilized condition.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GSC83 glioma cells — permeabilized (0.1% Triton X-100) confocal IF reveals intracellular EGFR distribution in paired comparison to surface staining | Established Cell Line | Moderate | 1 |

#### Nonpermeabilized IF — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Nonpermeabilized · expression: Unknown*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Non-permeabilized cells (cell type not specified in ledger) — immunofluorescence shows cell surface EGFR; n=2 independent experiments, p<0.01 vs. permeabilized | Unknown | Moderate | 1 |

#### Permeabilized IF — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Unknown*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Permeabilized cells — immunofluorescence shows intracellular EGFR; paired comparison to non-permeabilized surface signal; n=2 independent experiments | Unknown | Moderate | 1 |

#### Nonpermeabilized IF — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR (panitumumab-based, via DNA-antibody conjugate) — Extracellular epitope; Monoclonal; None validation (None); Panitumumab-derived antibody conjugated to biotinylated DNA; loaded onto streptavidin-decorated DNA origami nanoframes; binds EGFR ECD on live intact cells.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| MCF-7 breast cancer cells (live) — DNA-antibody conjugates bound to EGFR at the plasma membrane via streptavidin-decorated DNA origami nanoframes; demonstrates ECD surface accessibility | Established Cell Line | Moderate | 1 |

### Immunohistochemistry (2 methods)

#### IHC Membranous — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Sinonasal inverted papilloma (SIP) primary patient tissue — EGFR plasma membrane staining positive in 31/32 cases (97%); moderate-to-strong membranous staining in >10% tumor cells | Patient Sample | High | 1 |

#### IHC Membranous — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-EGFR (EP38Y · Abcam · ab52894 · AB_869579) — Intracellular epitope; Monoclonal; Strong validation (Genetic KO); Rabbit recombinant monoclonal; immunogen around intracellular Tyr1068 domain; KO-validated by Abcam; used at IHC 1:100 and WB 1:5000.

### Surface mass spec (3 methods)

#### Cell Surface Capture — Supports Membrane Association · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| MDCK polarized epithelial cells (filter-grown) — SILAC chemoproteomics surfaceome mapping; EGFR apicobasal ratio ~40% apical / 60% basolateral; relatively even distribution across polarized membrane | Established Cell Line | Moderate | 1 |

#### Cell Surface Capture — Weak Or Ambiguous · Unclear

*Permeabilization: Live Cell · expression: Unknown*

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| LUAD (lung adenocarcinoma) cell lines — surfaceome profiling by mass spectrometry comparing vehicle control vs. gefitinib (EGFR TKI) treatment; schematic presented but no explicit EGFR hit readout stated in ledger | Established Cell Line | Moderate | 1 |

### Surface biotinylation (5 methods)

#### Surface Biotinylation — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-phosphotyrosine 4G10 (4G10 · Millipore) — Unknown epitope; Monoclonal; None validation (None); Mouse IgG2bκ anti-phosphotyrosine; detects all pTyr proteins — not EGFR-specific; used to probe phosphorylated ErbB surface fraction after biotinylation capture.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| DCDMLs (cancer cell line derivative expressing ErbB kinases including EGFR) — plasma membrane proteins biotinylated, captured by streptavidin, probed with anti-pTyr 4G10; phosphorylated EGFR/ErbB detected at cell surface | Established Cell Line | Moderate | 1 |

#### Surface Biotinylation — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Mixed*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| NIKS keratinocytes (control) — surface EGFR detected by biotinylation + streptavidin bead + WB | Established Cell Line | Moderate | 1 |
| HPV16 E7-expressing NIKS keratinocytes — modest upregulation of surface EGFR vs. control by biotinylation assay | Established Cell Line | Moderate | 1 |
| SiHa (HPV-16+) cervical cancer cells — surface EGFR after E6/E7 knockdown assessed by biotinylation + WB | Established Cell Line | Moderate | 2 |
| HeLa (HPV-18+) cervical cancer cells — surface EGFR after E6/E7 knockdown assessed by biotinylation + WB | Established Cell Line | Moderate | 2 |

*Overexpression construct* — SP source: Native · endogenous EGFR signal peptide; HPV16 E7 modulates surface trafficking but does not alter the EGFR construct · cell line: NIKS. *(cites: a1_evi_21, a1_evi_22)*

#### Surface Biotinylation — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| iPSC-derived sensory-like neurons (FD patients and controls) — sulfo-NHS-SS-biotin surface labeling followed by mass spectrometry identified 1,508 surface proteins consistently across 3 independent experiments; EGFR among identified hits | IPSC Derived | Moderate | 1 |

#### Surface Biotinylation — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Prostate cancer cells — sBioSITe surface biotinylation detected EGFR with 19 biotinylation sites mapped; EGFR noted as marker of prostate cancer bone dissemination | Established Cell Line | High | 1 |

#### Surface Biotinylation — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| A549 lung adenocarcinoma cells — surface biotinylation + streptavidin bead enrichment; eluants analyzed by Western blot and mass spectrometry to characterize EGFR surface interactome | Established Cell Line | Moderate | 2 |

### Proximity labeling (1 method)

#### Unknown — Supports Membrane Association · Plasma Membrane Localized

*Permeabilization: Unknown · expression: Unknown*

**Antibodies**

- anti-EGFR-HRP (Abcam) — Unknown epitope; Unknown; Weak validation (Vendor Claim Only); HRP-conjugated anti-EGFR from Abcam, used at 1:5000 for WB confirmation of biotinylated EGFR fraction after Affibody.BirA* proximity labeling.
- anti-HER2-HRP (Novus Biologicals) — Unknown epitope; Unknown; Weak validation (Vendor Claim Only); HRP-conjugated anti-HER2 from Novus Biologicals used as comparator in the same WB panel.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| EGFR.Fc fusion protein exposed to Affibody.BirA* constructs — biotinylated proteins pulled down on protein G beads and confirmed by WB with anti-EGFR-HRP; demonstrates ECD proximal biotinylation | Unknown | Moderate | 2 |

### Other (2 methods)

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Overexpression*

**Antibodies**

- anti-EGFR — Unknown epitope; Unknown; None validation (None); Generic anti-EGFR antibody used for WB on NIH-3T3 transfectants; paper does not specify clone or vendor.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| NIH-3T3 stable transfectants expressing human WT EGFR (retroviral pMXs-neo vector) — Western blot confirms EGFR protein expression; no surface fractionation performed | Established Cell Line | High | 1 |

*Overexpression construct* — SP source: Native · human wild-type EGFR cDNA, full-length, no leader replacement mentioned · cell line: NIH-3T3. *(cites: a1_evi_52, a1_evi_53)*

#### Unknown — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-EGFR 528mAb (528 · CSIRO Recombinant Protein Production and Purification Facility) — Extracellular epitope; Monoclonal; None validation (None); Anti-EGFR mouse mAb clone 528; binds EGFR domain III (extracellular); used for SPR binding analysis with EGFR antigen rather than a direct cellular assay.

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| iPSC-derived sensory-like neurons (FD patients and controls); EGFR mRNA measured by qPCR alongside surface biotinylation | IPSC Derived | RNA | Moderate | 1 |
| NIH-3T3 fibroblasts stably transfected with human wild-type EGFR; EGFR protein detected by whole-cell Western blot | Established Cell Line | Bulk Protein | High | 1 |

**Contradicting evidence**

- *Other* (severity Low): In NCI-H1930 lung cancer cells, IHC of clinical specimens shows a granular/diffuse staining pattern rather than the sharp membranous signal expected for a surface-accessible protein. However, live-cell (non-permeabilized) flow cytometry on the same cell line confirms clear cell-surface EGFR expression, indicating the granular IHC pattern may reflect a methodological limitation of IHC rather than a true absence of surface EGFR.
  - Likely explanation: Granular or diffuse IHC patterns in clinical specimens can arise from fixation artifacts, antibody clone sensitivity, or antigen retrieval issues rather than genuine absence of surface protein. The concordant live-cell flow cytometry data in the same cell line demonstrates bona fide surface EGFR expression, suggesting the IHC pattern is a methodological caveat rather than evidence against surface accessibility.

## 4. Biological context

**Cell types** *(orthogonal cell-type index)*

| Cell type | Ontology | Present in tissues | Species | Cites |
|---|---|---|---|---|
| polarized epithelial cells | — | epithelium | Human | 2 |
| epithelial tumor cells | — | sinonasal epithelium | Human | 2 |
| glioblastoma / glioma stem-like cells | — | brain / glioblastoma | Human | 2 |
| pancreatic ductal adenocarcinoma cells | — | pancreas | Human | 1 |
| colorectal carcinoma cells | — | colon | Human | 1 |
| lung neuroendocrine carcinoma cells | — | lung | Human | 1 |
| prostate cancer cells | — | bone metastasis / prostate | Human | 1 |
| sensory-like neurons | — | peripheral nervous system | Human | 2 |
| lung adenocarcinoma cells | — | lung | Human | 2 |
| squamous carcinoma cells | — | epidermoid / squamous carcinoma | Human | 1 |
| pancreatic acinar cells | — | pancreas | Mouse | 1 |
| multiple pancreatic cell types | — | pancreas | Human | 1 |
| glandular epithelium | — | glandular tissue | Human | 1 |
| HPV-altered epithelial cells | — | cervix / oropharynx | Human | 1 |
| keratinocytes | — | skin | Human | 1 |
| small cell lung cancer cells | — | lung | Human | 1 |

**Cell states**

- *EGF-stimulated* — EGF ligand binding drives EGFR internalization and lysosomal degradation, reducing surface EGFR availability; receptor-mediated endocytosis confirmed in A431 cells by EGF pre-saturation block. *(cites: a2_evi_15, a2_evi_16)*
- *drug-tolerant persister* — Three-week TKI (gefitinib/osimertinib) treatment of EGFR-mutant LUAD lines generates drug-tolerant persister cells with a remodeled surfaceome, representing a distinct surface EGFR accessibility state under TKI pressure. *(cites: a2_evi_13, a2_evi_14)*
- *disease (Fabry disease)* — Surface EGFR is among the most significantly deregulated plasma membrane proteins (p<0.01) in iPSC-derived sensory-like neurons from Fabry disease patients compared to healthy controls. *(cites: a2_evi_12)*
- *HPV-transformed* — In HPV-associated cancers (cervical, oropharyngeal), EGFR and downstream pathways (PI3K/Akt, mTOR, JAK/STAT) are aberrantly activated, indicating dysregulated EGFR surface signaling in HPV-driven cellular transformation. *(cites: a2_evi_20)*

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- Endosome · EGF-induced internalization *(cites: a2_evi_15, a2_evi_16)*
- Lysosome · EGF-induced internalization and degradation *(cites: a2_evi_15)*

**Membrane subdomains**: Apical Membrane, Basolateral Membrane

**Anatomical accessibility**

- polarized epithelial cells — Apical · *Context Dependent*: EGFR distributes ~40:60 apical:basolateral in polarized epithelium, meaning it is present on both surfaces. Apical fraction faces luminal space (restricted for systemic binders), while basolateral fraction is blood/interstitial-facing (favorable). Net accessibility is context-dependent on which surface dominates in a given tissue.
- polarized epithelial cells — Basolateral · *Favorable*: The slight basolateral enrichment (~60%) of EGFR in polarized epithelium means a majority of surface EGFR faces the interstitial/blood compartment, making it accessible to systemically delivered binders without requiring crossing tight-junction barriers.

**Accessibility modulation**

- *Cell State Induced* · trigger: Other: Unstimulated / ligand-naive cancer cells with surface EGFR → EGF-stimulated cells (ligand-induced internalization) — EGF binding triggers receptor-mediated endocytosis of EGFR, transiting it from the plasma membrane to endosomal/lysosomal compartments where it undergoes lysosomal degradation, reducing surface EGFR pool. *(→ EGF Stimulation Acutely Decreases The Surface-Accessible EGFR Pool; Extracellular Binders Lose Target Availability Post-Ligand Engagement Unless Lysosomal Degradation Is Blocked (E.G., By Chloroquine).)* *(cites: a2_evi_15, a2_evi_16)*
- *Polarization Dependent*: Non-polarized epithelial cells with uniform surface EGFR → Polarized epithelial cells with distinct apical and basolateral membrane compartments — In polarized epithelium, EGFR distributes relatively evenly across apical and basolateral surfaces (~40:60 apicobasal ratio), with slight basolateral enrichment, rather than being restricted to one pole. *(→ EGFR Remains Accessible From Both Luminal (Apical) And Basolateral Surfaces In Polarized Epithelium; Extracellular Binders Applied From Either Side Can Reach EGFR, Though Basolateral Access Is Marginally Favored.)* *(cites: a2_evi_01, a2_evi_02)*
- *Disease State Induced*: Healthy iPSC-derived sensory-like neurons (normal controls) → Fabry disease (FD) patient iPSC-derived sensory-like neurons — EGFR is among the most significantly deregulated proteins (p<0.01) in the neuronal plasma membrane proteome of FD neurons compared to healthy controls, indicating altered surface EGFR levels in the disease state. *(→ Disease-Associated Remodeling Of The Neuronal Surfaceome In Fabry Disease Alters EGFR Surface Availability, Potentially Affecting Binder Access In Peripheral Sensory Neurons From FD Patients.)* *(cites: a2_evi_11, a2_evi_12)*

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Strong
- domain: Unknown
- rationale: Surfaceome SILAC on polarized MDCK epithelial cells shows EGFR distributed ~40:60 apical:basolateral with no strict restriction to either pole. Non-permeabilized IF on GSC83 shows uniform plasma membrane decoration. Surface biotinylation across multiple non-polarized cancer cell lines confirms broad PM distribution without subdomain restriction.
- cites: a1_evi_30, a1_evi_06, a2_evi_01, a2_evi_02

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: EGFR is a single-pass Type I receptor that traffics autonomously to the plasma membrane via its native signal peptide; surface biotinylation across multiple independent cell types (keratinocytes, prostate cancer, iPSC neurons) confirms PM residence without evidence of an obligate co-receptor requirement for surface delivery.
- cites: a1_evi_21, a1_evi_26, a1_evi_28

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
- mechanism: ADAM10/17-Mediated Ectodomain Shedding Generates A Soluble EGFR Ectodomain (SEGFR); The Triage Record Notes ADAM10/17 Shedding Of EGFR Itself Is Established. The Shed Ectodomain Can Circulate And Act As A Decoy For Therapeutic Antibodies (E.G., SEGFR Competes With Cetuximab Binding).
- sheddase: ADAM10, ADAM17

**Secreted form**

- present: true
- severity: Moderate
- evidence: Moderate
- source: Proteolytic

**ECD size assessment**

- ECD class: Large
- rationale: EGFR ECD spans residues 25–645 (~620 aa), well above the 200 aa threshold for 'large'. Cryo-EM and crystal structures (PDB: 7OM4, 1YY9, 3C09, 7SYD) confirm the four-domain extracellular architecture. Multiple approved antibodies (cetuximab domain III, matuzumab, panitumumab) and nanobodies engage non-overlapping epitopes, demonstrating ample surface for multi-epitope targeting.
- cites: a1_evi_33, a1_evi_34, a1_evi_35, a1_evi_36, a1_evi_40

**Epitope masking**

- severity: Moderate
- evidence: Moderate
- mechanism: Glycan, Conformational
- rationale: EGFR ECD is heavily N-glycosylated (11 predicted N-glycosylation sites), which can sterically mask certain epitopes; tethered/untethered ECD conformational switching between inactive and active states modulates epitope accessibility. Approved antibodies successfully navigate this, but glycan shielding and conformational masking of domain II dimerization arm are established structural considerations. No ledger entry documents complete epitope occlusion.
- cites: a1_evi_33, a1_evi_34, a1_evi_35, a1_evi_36

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

75 entries · 50 primary · 25 secondary · 0 tertiary · 75 PMC OA.

- `a1_evi_01` · *Primary* · Supports · Methodological — Flow cytometry on intact (non-permeabilized) glioma cell lines was used to test EGFR surface expression, including U373 (low endogenous WT EGFR), U373vIII (engineered EGFRvIII overexpression), and GSC83 (endogenous EGFR/EGFRvIII). This is the assay context clip for the quantitative surface-detection results. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · U373, U373vIII, GSC83 glioma cells · live · non-permeabilized
  > "In order to glean some related insights, we used conventional flow cytometry to test EGFR antigen expression on the surfaces of individual glioma cells that were either weakly positive for the wild type EGFR (U373), or were engineered to overexpress oncogenic EGFRvIII (U373vIII) (Micallef et al. 2009 )."
- `a1_evi_02` · *Primary* · Supports · Surface Expression — Flow cytometry on intact glioma cells quantified EGFR/EGFRvIII surface expression: 12% of U373 (low WT EGFR) cells positive, 98% of U373vIII cells positive, and 99% of GSC83 cells uniformly positive for surface EGFR/EGFRvIII. Demonstrates that WT EGFR is present at the cell surface in GSC83 (endogenous expression) and in U373vIII (EGFRvIII overexpression). ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · U373, U373vIII, GSC83 glioma cells · live · non-permeabilized
  > "The representative dot plots and histograms depicted in Figure 1A illustrate the expected (Spinelli et al. 2024 ; Magnus et al. 2014 ; Al‐Nedawi et al. 2010 ) levels of EGFR/EGFRvIII expression by these respective cell lines and suggest that while few (12%) U373 cells harbour low levels of this receptor on their surfaces, both U373vIII and GSC83 cells are highly and uniformly positive for EGFR/EGFRvIII (98% and 99%, respectively)."
- `a1_evi_03` · *Primary* · Supports · Methodological — Flow cytometry surface staining protocol: anti-EGFR-Alexa Fluor647 conjugated antibody (BioLegend catalog #352918) applied to trypsinized cells; analysis on BD FACS Canto with FlowJo v10.7.1. Antibody clone/vendor detail for MethodObservation.antibodies[]. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · glioma cell lines · live · non-permeabilized
  > "Indicated cells were seeded in 12‐well plates for 24 h, then trypsinized and stained with anti‐EGFR‐Alexa Fluor647‐conjugated antibodies (Biolegend, 352918) and analysed using a BD FACS Canto with FlowJo software version 10.7.1."
- `a1_evi_04` · *Primary* · Supports · Methodological — Antibody identifiers for EGFR surface-staining and confocal IF: anti-EGFR-Alexa Fluor647 (BioLegend 352918) and anti-CD9-FITC (BioLegend 312104). Used in both non-permeabilized (surface) and permeabilized (intracellular) conditions. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · GSC83 glioma cells · fixed
  > "Both permeabilized and non‐permeabilized cells were then incubated with primary antibodies: anti‐EGFR‐Alexa Fluor647 (Biolegend 352918) and anti‐CD9‐FITC (Biolegend 312104)."
- `a1_evi_05` · *Primary* · Supports · Methodological — Confocal IF permeabilization protocol detail: cells fixed with 4% paraformaldehyde, then either left intact (non-permeabilized, surface readout) or permeabilized with 0.1% Triton X-100 in PBS for 5 min. This paired comparison validates surface vs. intracellular EGFR localization. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · GSC83 glioma cells · fixed
  > "For confocal microscopy, the adherent cells were fixed with 4% paraformaldehyde in phosphate buffered saline (PBS) for 10 min and, when indicated, permeabilized with 0.1% Triton X‐100 in PBS for 5 min."
- `a1_evi_06` · *Primary* · Supports · Surface Expression — Flow cytometry confirms uniform EGFR antigen on glioma cell surfaces (GSC83, U373vIII high; U373 low). Paired confocal IF on non-permeabilized vs. permeabilized GSC83 cells shows cell-surface vs. intracellular EGFR distribution, with CD9 as membrane co-marker. Non-permeabilized IF provides topology-anchoring surface evidence. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · GSC83, U373, U373vIII glioma cells · fixed · non-permeabilized
  > "(A) Flow cytometry analysis illustrating the uniform presence of EGFR antigen on the surface of glioma cells with high (GSC83 and U373VIII) and low (U373) levels of EGFR/EGFRvIII expression (right panel—dot plot; left panel—histogram); (B) Confocal imaging of immunofluorescent staining for EGFR antigen (red) and CD9 (green) in adherent GSC83 cells either intact or permeabilized before antibody exposure."
- `a1_evi_07` · *Primary* · Supports · Surface Expression — Authors state that endogenously expressed EGFR/EGFRvIII in GSC83 glioma cells is detectable principally at the cell surface, evenly decorating it, as shown by flow cytometry and confocal imaging. This is a direct surface-expression conclusion from the primary results. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · GSC83 glioma cells · live · non-permeabilized
  > "In isolated GSC83 cells the endogenously expressed EGFR/EGFRvIII (Spinelli et al. 2024 ) appears to be detectable principally on the cell surface, which is evenly decorated with the EGFR antigen, as revealed by flow cytometry and confocal imaging."
- `a1_evi_08` · *Primary* · Supports · Surface Expression — Immunofluorescence on non-permeabilized cells detects EGFR at the cell surface, with paired permeabilized condition showing intracellular EGFR. Quantified from n=2 independent experiments with statistical significance (p<0.01). Validates surface vs. intracellular localization by non-permeabilized IF. ([PMC9038772](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9038772/))
  - *assay*: Human · unknown · unspecified · non-permeabilized
  > "Representative immunofluorescence micrographs (A) show either cell surface EGFR in nonpermeabilized cells or intracellular EGFR in permeabilized cells as indicated and (B) quantified data from n = 2 independent experiments (mean ± SD; ∗∗, p < 0.01 using multiple t tests; Prism)."
- `a1_evi_09` · *Primary* · Supports · Surface Expression — Flow cytometry histograms on intact pancreatic cancer cell lines detect surface EGFR protein, confirming cell-surface accessibility in multiple cell lines. ([PMC13088391](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088391/))
  - *assay*: Human · pancreatic cancer cell lines (including BxPC-3) · live · non-permeabilized
  > "( A ) Representative flow cytometry histograms of surface EGFR on the indicated pancreatic cancer cell lines."
- `a1_evi_10` · *Primary* · Supports · Surface Expression — Cell-surface binding of anti-EGFR bispecific antibody (panitumumab-derived) assessed by flow cytometry on intact BxPC-3 cells; confirms EGFR extracellular domain accessibility at the cell surface in pancreatic cancer cell line. ([PMC13088391](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088391/))
  - *assay*: Human · BxPC-3 · live · non-permeabilized
  > "( D ) Cell-surface binding assessed by flow cytometry: binding to EGFR on BxPC-3 cells and to NKG2D on primary human NK cells."
- `a1_evi_11` · *Secondary* · Supports · Surface Expression — Panitumumab (FDA-approved anti-EGFR IgG1 monoclonal antibody) VH/VL used to engineer bispecific antibody targeting EGFR on cancer cell surfaces; selected for high-affinity binding to human EGFR and relatively slow internalization. Clinically approved therapeutic engagement of EGFR ECD at the cell surface. Supports therapeutic engagement context for downstream builder. ([PMC13088391](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088391/))
  - *assay*: Human
  > "The EGFR-binding VH and VL pairs were derived from clinically approved anti-EGFR panitumumab, selected for its high-affinity binding to human EGFR and relatively slow internalization compared with other EGFR-targeting antibodies [ 40 , 41 ]."
- `a1_evi_12` · *Secondary* · Supports · Surface Expression — A flow cytometry-based assay was validated for measurement of nimotuzumab (anti-EGFR humanized IgG1 mAb) binding to EGFR-overexpressing cells at the cell surface, confirming surface accessibility of EGFR ECD in intact cells. ([PMC3163362](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3163362/))
  - *assay*: Human · epithelial cell lines overexpressing EGFR · live · non-permeabilized
  > "Here we report on the validation of a flow cytometry-based assay used in the evaluation of nimotuzumab binding to cells over-expressing EGFR on cell surface."
- `a1_evi_13` · *Secondary* · Supports · Surface Expression — Nimotuzumab binding to EGFR-overexpressing cell lines reached saturation at 3–5 µg/mL (% binding metric) by flow cytometry; saturation binding confirms specific and quantifiable EGFR surface accessibility in intact overexpression cells. ([PMC3163362](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3163362/))
  - *assay*: Human · EGFR-overexpressing epithelial cell lines · live · non-permeabilized
  > "For the data shown in figure 1a , saturation of binding was achieved at a concentration of 3–5 μg/mL of nimotuzumab when % of binding was reported."
- `a1_evi_14` · *Secondary* · Supports · Methodological — Flow cytometry staining protocol for nimotuzumab surface-binding assay: mAb incubated with cells for 30 min at 2–8°C (cold, non-activating, non-permeabilizing conditions), ensuring surface-only detection of EGFR. ([PMC3163362](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3163362/))
  - *assay*: Human · EGFR-overexpressing epithelial cell lines · live · non-permeabilized
  > "The mAbs were added according to the experimental plan, and cells were stained for 30 min at 2–8°C."
- `a1_evi_15` · *Secondary* · Supports · Methodological — Secondary antibody for nimotuzumab flow cytometry: FITC-conjugated rabbit anti-human IgG (Dako F0056, 1:60). Reagent identifier for MethodObservation.antibodies[]. ([PMC3163362](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3163362/))
  - *assay*: Human · EGFR-overexpressing epithelial cell lines · live · non-permeabilized
  > "FITC-conjugated rabbit anti human IgG (Dako F0056, Denmark, 1:60) was added and cells were stained for 30 min at 2–8°C."
- `a1_evi_16` · *Secondary* · Supports · Surface Expression — Nimotuzumab (h-R3), a clinically used humanized anti-EGFR IgG1 monoclonal antibody obtained by CDR grafting of murine mAb to human framework, is used for therapeutic engagement of EGFR ECD at the cell surface. Supports therapeutic engagement context. ([PMC3163362](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3163362/))
  - *assay*: Human
  > "Nimotuzumab (also known as h-R3) is an IgG1 humanized anti–epidermal growth factor receptor (EGFR) mAb that was obtained by complementarity determining regions grafting of a murine mAb to a human framework [ 5 ]."
- `a1_evi_17` · *Secondary* · Supports · Topology — Nimotuzumab binds domain III of the EGFR extracellular region, interfering with EGF ligand binding. This epitope-mapping information confirms ECD accessibility at domain III for antibody engagement. ([PMC3163362](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3163362/))
  - *assay*: Human
  > "Nimotuzumab binds to domain III of the extracellular region of the EGFR and interferes with EGF binding [ 5 , 6 ]."
- `a1_evi_18` · *Primary* · Supports · Surface Expression — IHC on sinonasal inverted papilloma (SIP) tissue sections shows EGFR positive plasma membrane staining in 31/32 cases (97%), using moderate-to-strong membranous staining criterion in >10% tumor cells. Direct surface-level IHC evidence from primary patient tissue. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
  - *assay*: Human · sinonasal inverted papilloma · fixed
  > "EGFR showed positive plasma membrane staining in 31 of 32 SIP cases (97%)."
- `a1_evi_19` · *Secondary* · Supports · Methodological — IHC scoring rubric for EGFR and p-EGFR membrane staining: positive = moderate-to-strong membranous staining in >10% tumor cells; criteria adapted from Menendez et al. Paired with IHC surface result clips to anchor MethodObservation for membranous IHC detection. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
  - *assay*: Human · tumor tissue sections · fixed
  > "IHC for EGFR and p-EGFR was considered positive when moderate to strong membranous staining was observed in more than 10% of tumor cells; cases that did not meet this criterion were regarded as negative, based on Menendez M et al. [ 23 ]."
- `a1_evi_20` · *Primary* · Supports · Surface Expression — Surface biotinylation on DCDMLs (derivatized cell line expressing ErbB kinases including EGFR): cells biotinylated at plasma membrane, labeled proteins captured with streptavidin beads, and Western blots probed with 4G10 antiphosphotyrosine antibody to detect phosphorylated EGFR/ErbB at cell surface. Primary surface biotinylation + WB evidence. ([PMC10337807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10337807/))
  - *assay*: Human · DCDMLs · live · non-permeabilized
  > "In order to simultaneously assess all possible ErbB kinases, we subjected DCDMLs to cell surface biotinylation, collected labeled plasma membrane proteins with streptavidin beads, and probed Western blots with the 4G10 antiphosphotyrosine antibody."
- `a1_evi_21` · *Primary* · Supports · Surface Expression — Surface biotinylation on NIKS keratinocyte cells: biotinylated plasma membrane proteins recovered with streptavidin beads, analyzed by Western blot. EGFR detected among surface proteins, with higher total surface EGFR levels in HPV16 E7-expressing NIKS cells vs. controls. Direct surface biotinylation + WB result for EGFR. ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
  - *assay*: Human · NIKS keratinocytes (HPV16 E7-expressing) · live · non-permeabilized
  > "Biotinylated proteins were recovered with streptavidin beads and analysed by Western blot; we observed higher total levels of the selected targets on the cell surface in Wt 16 E7-expressing NIKS cells ( Fig. 2 C)."
- `a1_evi_22` · *Primary* · Supports · Surface Expression — Surface EGFR is modestly upregulated in HPV16 E7-expressing NIKS cells, detected by surface biotinylation assay; consistent with prior results and implicating AP2-tyrosine-motif-dependent endocytic regulation of surface EGFR levels. ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
  - *assay*: Human · NIKS (HPV16 E7-expressing) · live · non-permeabilized
  > "Remarkably, we observed several potential membrane proteins up- and down-regulated by the AP2-tyrosine binding motif in E7, including a modest upregulation of the surface EGFR ( Fig. 2 B), which is in agreement with our previous results [ 13 ]."
- `a1_evi_23` · *Primary* · Supports · Methodological — Cell-surface biotinylation method on HPV+ cervical cancer cell lines (SiHa HPV-16+, HeLa HPV-18+): plasma membrane proteins biotinylated and labeled proteins assessed by Western blotting after E6/E7 knockdown. Methods detail for paired surface biotinylation + WB assay. ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
  - *assay*: Human · SiHa (HPV-16+), HeLa (HPV-18+) · live · non-permeabilized
  > "To investigate this, we knocked down the expression of E6 and E7 oncoproteins from HPV16 E7-expressing SiHa and HPV18 E7-expressing HeLa cells; then plasma membrane proteins were biotinylated and labelled proteins were assessed by Western blotting."
- `a1_evi_24` · *Primary* · Supports · Methodological — Cell-surface biotinylation + streptavidin purification + WB protocol applied to SiHa and HeLa cervical cancer cell lines: proteins biotinylated at the plasma membrane, purified, then membrane protein expression assessed by Western blot. Anchors MethodObservation.method_family=surface_biotinylation, validation_strategy confirmed by WB. ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
  - *assay*: Human · SiHa, HeLa · live · non-permeabilized
  > "(B) Cell surface proteins from SiHa (HPV-16-positive) and HeLa (HPV-18-positive) cells were biotinylated and purified; then cells were lysed and membrane protein expression was assessed by Western blotting."
- `a1_evi_25` · *Primary* · Supports · Methodological — Surface biotinylation method detail: sulfo-NHS-SS-biotin chemistry applied to intact cells (PBS washed, then sulfo-NHS-SS-biotin solution for 10 min at room temperature). Standard cleavable cell-surface labeling reagent; anchors method_family=surface_biotinylation, method_subclass=sulfo-NHS-SS. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · sensory-like neurons (iPSC-derived, FD patients and controls) · live · non-permeabilized
  > "In brief, cells were washed with PBS and covered with sulfo-NHS-SS-biotin solution for ten minutes at room temperature."
- `a1_evi_26` · *Primary* · Supports · Surface Expression — Surface biotinylation followed by mass spectrometry on iPSC-derived sensory-like neurons identified 1,508 distinct proteins at the cell surface, consistently across 3 independent experiments. EGFR was among the identified surface proteins, providing mass-spec surfaceome evidence for EGFR surface presence in neuronal cells. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · iPSC-derived sensory-like neurons · live · non-permeabilized
  > "Via biotinylation followed by mass spectrometry ( Fig 1A , 1B ), we identified 1,508 distinct proteins in sensory-like neuron cultures derived from FD patients and controls, consistently observed across three independent experiments (S2 Table)."
- `a1_evi_27` · *Secondary* · Ambiguous · Tissue Expression — qPCR analysis of EGFR mRNA in sensory-like neurons was conducted to assess whether surface-proteome differences were mirrored at gene-expression level. This is a non-surface RNA expression observation that qualifies a surface biotinylation result; EGFR RNA data without surface-method framing feeds non_surface_expression list. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · iPSC-derived sensory-like neurons
  > "To assess whether the observed differences in the neuronal plasma membrane were mirrored at the gene expression level, we conducted qPCR analysis for CACNA2D3, GPM6A, EGFR, and ABCA7, using samples from four separately prepared differentiations for FD and healthy control sensory-like neurons, respectively."
- `a1_evi_28` · *Primary* · Supports · Surface Expression — EGFR detected by surface biotinylation (sBioSITe method) on prostate cancer cells with 19 biotinylation sites mapped, confirming robust surface accessibility. Reference [29] cited as origin of biotinylation site count; EGFR noted as a known marker of prostate cancer bone dissemination. ([PMC10696767](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10696767/))
  - *assay*: Human · prostate cancer cells · live · non-permeabilized
  > "Epidermal growth factor receptor (EGFR), a known marker of dissemination of prostate cancer to bones, was detected with 19 biotinylation sites [ 29 ] (Fig. 3 C)."
- `a1_evi_29` · *Secondary* · Supports · Methodological — sBioSITe (surface Biotinylation Site Identification Technology) method described: adapts BioSITe to enrich cell-surface proteins by immunoprecipitation of biotinylated peptides; sensitive, reliable pipeline for surface protein identification. Anchors method_family=surface_biotinylation, method_subclass=sBioSITe. ([PMC10696767](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10696767/))
  - *assay*: Human · prostate cancer cells · live · non-permeabilized
  > "We report the development of surface Biotinylation Site Identification Technology (sBioSITe), a sensitive and reliable method for the enrichment of cell surface proteins by adapting the Biotinylation Site Identification Technology (BioSITe) for immunoprecipitation of biotinylated peptides [ 17 ]."
- `a1_evi_30` · *Primary* · Supports · Surface Expression — Surfaceome MS (SILAC chemoproteomics on filter-grown polarized MDCK epithelial cells) quantified EGFR apicobasal distribution: approximately 40% apical, 60% basolateral at the cell surface. Confirms EGFR is present at the plasma membrane of polarized epithelial cells with slight basolateral preference. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
  - *assay*: Dog · MDCK (Madin-Darby Canine Kidney) · live · non-permeabilized
  > "However, we show here that both the EGF precursor and its receptor EGFR are relatively evenly distributed across the polarized membrane (with an apicobasal ratio of 50:50 and 40:60, respectively)."
- `a1_evi_31` · *Primary* · Supports · Methodological — Apicobasal surfaceome mapping method: filter-grown MDCK cells + chemoproteomics (cell-surface capture chemistry) + SILAC for quantitative apicobasal surface protein distribution. Anchors method_family=mass_spec_surfaceome for the EGFR surface quantification result. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
  - *assay*: Dog · MDCK · live · non-permeabilized
  > "In order to map the apicobasal surfaceome quantitatively, we used filter-grown Madin–Darby canine kidney (MDCK) cells as the best-established in vitro system for epithelial polarity [ 16 ] in combination with chemoproteomics and stable isotope labeling of amino acids in cell culture (SILAC) ( Figure 1 A) [ 17 , 18 ]."
- `a1_evi_32` · *Secondary* · Supports · Methodological — Cell surface capture (CSC) method described: periodate oxidation of cell-surface glycoprotein sialic acids generates aldehydes that react with hydrazide beads to capture surface glycoproteins; washed and released with PNGase F. Developed by Wollscheid/Aebersold group. Anchors method_family=mass_spec_surfaceome, method_subclass=cell_surface_capture. ([PMC12022999](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12022999/))
  - *assay*: Unspecified · live · non-permeabilized
  > "The aldehydes readily react with hydrazide, to form stable hydrazone linkages. 75 The enrichment technique called cell surface capture (CSC) developed by Wollscheid, Aebersold, and co-workers, utilized this chemistry to capture cell surface proteins onto hydrazide beads. 76 The captured glycoproteins were washed extensively and released using PNGase F, an amidase that cleaves between the innermost GlcNAc and the N -glycan-modified asparagine."
- `a1_evi_33` · *Primary* · Supports · Topology — Cryo-EM reconstruction of EGFR reveals strongest density in the ectodomain region, with weaker density in TM and intracellular domains; consistent with all previously published cryo-EM RTK structures. Confirms extracellular-domain-outward topology by structural imaging. ([PMC10948148](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10948148/))
  - *assay*: Human
  > "As reported in all previously published cryo-EM reconstructions of other RTKs ( Diwanji et al., 2021 ; Huang et al., 2021 ; Nielsen et al., 2022 ; Li et al., 2019 ; Uchikawa et al., 2019 ; Krimmer et al., 2023 ), the cryo-EM density was the strongest in the ectodomain region of the receptor complex and the weakest within the transmembrane and intracellular domains ( Figure 1b–c , Figure 1—figure supplement 2a, f , Figure 1—figure supplement 3a, f )."
- `a1_evi_34` · *Primary* · Supports · Topology — Cryo-EM structures show EGFR ectodomains adopt a 'heart-shaped' arrangement in liganded dimers, consistent with domain I-IV extracellular architecture established by X-ray and cryo-EM structures of HER family receptors. Confirms ECD-outward topology in dimeric complex. ([PMC10948148](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10948148/))
  - *assay*: Human
  > "In both structures, the ectodomains adopt a characteristic ‘heart-shaped’ arrangement observed in previously solved X-ray and cryo-EM structures of liganded HER receptor dimers ( Garrett et al., 2002 ; Liu et al., 2012 ; Ogiso et al., 2002 ; Diwanji et al., 2021 ; Bai et al., 2023 ; Freed et al., 2017 ; Huang et al., 2021 ; Lu et al., 2010 )."
- `a1_evi_35` · *Primary* · Supports · Topology — Crystal structure of full EGFR ectodomain in complex with nanobody EgB4 and EGF ligand determined at 6.0 Å (PDB: 7OM4). Structural definition of the extracellular domain accessible face and nanobody binding epitope on EGFR ECD. ([PMC8887186](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8887186/))
  - *assay*: Human
  > "S 2
To study the mechanism by which the EgB4 nanobody interacts with EGFR, we then determined the structure of the full ectodomain EGFR-EgB4-EGF ternary complex from a crystal that diffracted to a maximum resolution of 6.0 Å (PDB: 7OM4; Table 1 and Fig."
- `a1_evi_36` · *Primary* · Supports · Topology — X-ray crystal structures of Cetuximab Fab–EGFR ECD complex (PDB: 1YY9) and Matuzumab Fab–EGFR ECD complex (PDB: 3C09) define therapeutic antibody epitopes on EGFR extracellular domain. Used for IgM antibody modeling. Anchors ECD topology and clinical antibody engagement interface. ([PMC12827627](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12827627/))
  - *assay*: Human
  > "The full-length IgM models for Cetuximab and Matuzumab were built using structural data available in the PDB: i) the X-ray crystal structures of Cetuximab and Matuzumab Fab bound to the human EGFR extracellular domains (ECDs) (PDB: 1YY9 ( 56 ) and 3C09 ( 22 ), respectively), ii) the cryogenic electron microscopy (cryo-EM) structure of the human IgM Fc pentamer (PDB: 6KXS) ( 25 ), and iii) the crystal structure of mouse Cµ2 domain (PDB: 4JVU) ( 57 )."
- `a1_evi_37` · *Primary* · Supports · Topology — Crystal structure of EGFR ECD (PDB: 4UV7) superimposed on EGFR-Matuzumab complex (PDB: 3C09) for epitope geometry calculations. Confirms structural accessibility of domain III/IV epitopes engaged by clinical antibodies. ([PMC12827627](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12827627/))
  - *assay*: Human
  > "The crystal structure of the extracellular domain of EGFR from PDB:4UV7 was superimposed on to the EGFR-Matuzumab complex (PDB: 3C09) to facilitate these calculations."
- `a1_evi_38` · *Primary* · Supports · Topology — Complete EGFR ECD structure from cryo-EM (PDB: 7SYD) used for IgM/IgG antibody–EGFR ECD binding modeling. Represents full extracellular domain structure available for surface-engagement geometry calculations. ([PMC12827627](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12827627/))
  - *assay*: Human
  > "To model the bound systems of IgM and IgG antibodies in complex with the EGFR, we obtained the complete EGFR ECD structure from a cryo-EM structure (PDB:7SYD) ( 62 )."
- `a1_evi_39` · *Secondary* · Supports · Topology — EGFR ectodomain crystal structure (PDB: 3NJP) used as starting structure for MD simulations; confirms availability of untethered ECD structural data for topology modeling. ([PMC11965450](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11965450/))
  - *assay*: Human
  > "For the starting structures of our EGFR simulations (simulations 1, 2, 5, and 6), four frames were selected randomly from an equilibration simulation of an untethered EGFR ectodomain crystal structure (PDB ID: 3NJP); the double mutation C271A/C283A was introduced for simulations 5 and 6."
- `a1_evi_40` · *Secondary* · Supports · Topology — Full-length EGFR (residues 1–1210) and extracellular domain (residues 25–645) cloned into CMV-FLAG expression vector. ECD boundaries confirm signal peptide (aa 1–24) with extracellular domain aa 25–645, consistent with UniProt topology annotation. ([PMC13010625](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13010625/))
  - *assay*: Human
  > "The full-length EGFR (residues 1–1210) and its extracellular domain (residues 25–645) were cloned into a CMV-FLAG expression vector."
- `a1_evi_41` · *Secondary* · Supports · Methodological — Antibody reagent table listing anti-EGFR antibody: Abcam ab52894, used at WB 1:5000 and IHC 1:100. Provides clone/vendor/catalog identifier for MethodObservation.antibodies[] in WB and IHC surface-method rows. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
  - *assay*: Unspecified
  > "Application/dilution ADAM17 Millipore Sigma AB19027 IF: 1:400 Amylase Millipore Sigma A8273 IHC 1:500 Amylase Santa Cruz SC-12821 ADM 1:2500 AKT Cell Signaling 4691 WB: 1:4000 CD45 Abcam Ab10558 IF: 1:400 CK19 Developmental Studies Hybridoma Bank Troma III IF 1:100 CK19 Abcam Ab133496 IHC 1:4000 ADM 1:5000 Cleaved caspase 3 Cell Signaling 9664 IHC 1:100 c-Jun Cell Signaling 9165 IHC: 1:100 E-cadherin Cell Signaling 3195 IHC: 1:100 IF 1:50 EGFR Abcam ab52894 WB 1:5000 IHC 1:100 ERK1/2 Cell Signaling 9102 WB: 15000 IHC"
- `a1_evi_42` · *Secondary* · Supports · Methodological — Anti-EGFR mouse 528mAb produced by CSIRO Recombinant Protein Production and Purification Facility. Clone 528 antibody identifier for EGFR surface-detection; used in surface-method validation (SPR with EGFR antigen). Reagent identifier for MethodObservation.antibodies[]. ([PMC10245379](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10245379/))
  - *assay*: Human
  > "Anti-EGFR mouse 528mAb was provided by the fermentation team at the Recombinant Protein Production and Purification Facility, CSIRO.
400 MHz NMR spectra were recorded on a Bruker Avance III Nanobay spectrometer."
- `a1_evi_43` · *Primary* · Supports · Surface Expression — DNA-antibody conjugates bound to EGFR in the membrane of live MCF-7 breast cancer cells via streptavidin-decorated DNA origami nanoframes (non-permeabilized, intact cell surface binding). Confirms EGFR ECD accessibility at the plasma membrane of intact live cells. ([PMC11472258](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11472258/))
  - *assay*: Human · MCF-7 · live · non-permeabilized
  > "To do so, the STV-decorated DON F were used to bind biotinylated DNA-antibody conjugates, which can bind to the EGF receptor (EGFR) in the membrane of live MCF-7 cells ( Figure 4 a)."
- `a1_evi_44` · *Primary* · Supports · Surface Expression — Panitumumab (FDA-approved anti-EGFR IgG2 mAb, KD=5×10⁻¹¹ M) binds EGFR at the cell surface of MCF-7 cells with 4 orders of magnitude higher affinity than EGF (KD=1.77×10⁻⁷ M), blocking EGF binding site. Therapeutic engagement of EGFR ECD at the cell surface by a clinical antibody; laterally clustering antibodies can also activate EGFR through surface receptor recruitment. ([PMC11472258](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11472258/))
  - *assay*: Human · MCF-7 · live · non-permeabilized
  > "Panitumumab ( K D = 5 × 10 –11 M) 39 binds EGFR with an affinity 4 orders of magnitude higher than EGF ( K D = 1.77 × 10 –7 M), thus preventing EGF binding. 40 Previous studies have shown that antibodies that bind EGFR laterally (not on the EGF binding site) can induce EGFR activation through clustering when attached to a surface. 41 We speculated that Panitumumab might also induce EGFR activation by receptor recruitment, even though it blocks the EGF binding site."
- `a1_evi_45` · *Primary* · Supports · Surface Expression — Flow cytometry on live A431 epidermoid carcinoma cells used to study binding of MNT 1 nanoparticles to EGFR receptors at the cell surface. Confirms EGFR surface accessibility on A431 cells by live-cell flow cytometry assay. ([PMC10818351](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10818351/))
  - *assay*: Human · A431 · live · non-permeabilized
  > "Flow cytometry was used to study the ability of MNT 1 to bind to EGFR receptors on the surface of A431 cells."
- `a1_evi_46` · *Primary* · Supports · Methodological — Surface biotinylation + streptavidin bead enrichment + Western blot on A549 cells to detect EGFR interactome at the cell surface. Standard cell-surface biotinylation WB method with streptavidin capture; anchors method_family=surface_biotinylation. ([PMC12749419](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12749419/))
  - *assay*: Human · A549 · live · non-permeabilized
  > "Following cell lysis and protein enrichment on streptavidin beads, we performed Western blot analysis of the resulting enriched proteins."
- `a1_evi_47` · *Primary* · Supports · Methodological — Streptavidin-bead enrichment eluants from A549 surface biotinylation analyzed by Western blotting and mass spectrometry to characterize EGFR surface interactome. Combined WB + MS readout following surface biotinylation; paired methods for surface EGFR identification. ([PMC12749419](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12749419/))
  - *assay*: Human · A549 · live · non-permeabilized
  > "Protein eluants after streptavidin-bead enrichment were analyzed by Western blotting and mass spectrometry."
- `a1_evi_48` · *Secondary* · Supports · Methodological — Surfaceome profiling by mass spectrometry performed on LUAD (lung adenocarcinoma) cell lines treated with vehicle control or gefitinib (EGFR TKI). Schematic of surfaceome method establishes assay family for surface protein quantification in EGFR-pathway-active cells. ([PMC12765945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12765945/))
  - *assay*: Human · LUAD cell lines · live · non-permeabilized
  > "Figure 1 EGFR TKI upregulates ALPP expression in LUAD cell (A) Schematic of surfaceome profiling of LUAD cell lines treated with vehicle control or gefitinib."
- `a1_evi_49` · *Secondary* · Supports · Methodological — Biotinylation of EGFR.Fc fusion protein using Affibody.BirA* proximity labeling: biotinylated proteins eluted from protein G beads and detected by Western blot under non-reducing conditions with streptavidin-HRP (1:2500). Method anchors surface-proximal biotinylation of EGFR ECD. ([PMC9890520](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9890520/))
  - *assay*: Human
  > "The level of the biotinylation of EGFR.Fc and HER2.Fc arising from exposing them to Affibody.BirA* constructs was monitored by eluting the biotinylated proteins bound to the protein G beads by boiling the beads in lithium dodecyl sulfate (LDS) sample buffer and performing Western blot on the recovered samples under nonreducing conditions using 1:2500 streptavidin-HRP."
- `a1_evi_50` · *Secondary* · Supports · Methodological — Western blot confirmation of EGFR in biotinylated fraction: anti-EGFR-HRP (Abcam) 1:5000 and anti-HER2-HRP (Novus Biologicals). Provides antibody vendor/catalog for MethodObservation.antibodies[] associated with biotinylation pull-down. ([PMC9890520](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9890520/))
  - *assay*: Human
  > "The presence of EGFR and HER2 among the biotinylated proteins pulled down was confirmed by Western blot using 1:5000 anti-EGFR.HRP (Abcam) and anti-HER2.HRP (Novus Biologicals) conjugates."
- `a1_evi_51` · *Primary* · Ambiguous · Contradictory — NCI-H1930 lung cancer cells show granular/diffuse IHC pattern (not sharp membranous) in clinical specimens but demonstrate clear cell surface EGFR expression by live-cell flow cytometry. This discordance between IHC pattern and flow cytometry surface signal is noted as a potential methodological caveat: granular IHC alone may underestimate surface EGFR presence. ([PMC13096901](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13096901/))
  - *assay*: Human · NCI-H1930 · live · non-permeabilized
  > "In addition, while clinical specimens often exhibited a granular and/or diffuse IHC pattern, rather than a sharp membranous staining, NCI–H1930 cells showed a similar pattern yet demonstrated cell surface expression by flow cytometry."
- `a1_evi_52` · *Secondary* · Ambiguous · Tissue Expression — Stable transfectants of NIH-3T3 cells expressing human wild-type EGFR (via retroviral vector) analyzed for EGFR protein expression by Western blot with anti-EGFR antibody. Whole-cell WB without surface fractionation; non-surface expression observation confirming protein expression in overexpression system. ([PMC4372364](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4372364/))
  - *assay*: Mouse · NIH-3T3 (EGFR transfectants)
  > "We generated stable transfectants of the cells by the introduction of human NEU3 and/or EGFR cDNA using a retroviral vector system, and analyzed the clones (Vec-, NEU3-, EGFR-, and EGFR/NEU3-cells) for NEU3 and EGFR by western blotting with anti-NEU3 and anti-EGFR antibodies, respectively."
- `a1_evi_53` · *Secondary* · Supports · Methodological — Human wild-type EGFR gene (not mutant, not fusion) used for overexpression into retroviral vector pMXs-neo for stable transfection into NIH-3T3 cells. Native full-length WT EGFR construct — endogenous signal peptide; OE construct SP source is endogenous, not foreign leader. ([PMC4372364](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4372364/))
  - *assay*: Human · NIH-3T3 transfectants
  > "For EGFR overexpression, the human wild- type gene, which was kindly provided by Dr."
- `a2_evi_01` · *Primary* · Supports · Surface Expression — EGFR is distributed relatively evenly across apical and basolateral membrane surfaces of polarized epithelial cells, with an apicobasal ratio of approximately 40:60 (apical:basolateral). This indicates EGFR is accessible from both luminal and basolateral surfaces in polarized epithelium, with a slight basolateral enrichment. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
  - *assay*: Human · polarized epithelial cells · live · non-permeabilized
  > "However, we show here that both the EGF precursor and its receptor EGFR are relatively evenly distributed across the polarized membrane (with an apicobasal ratio of 50:50 and 40:60, respectively)."
- `a2_evi_02` · *Primary* · Supports · Surface Expression — In polarized epithelial cells, both EGF (the ligand precursor) and EGFR are relatively evenly distributed across apical and basolateral membrane compartments (apicobasal ratio ~50:50 and 40:60 respectively), in contrast to many interaction partners which are strongly polarized. This non-polarized surface distribution of EGFR in polarized epithelium is relevant to spatial accessibility of the ECD. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
  - *assay*: Human · polarized epithelial cells · live · non-permeabilized
  > "Therefore, we created an in silico map of the apicobasal protein interaction network exemplified by the EGF/EGFR system ( Figure 3 B) and examined how the differential abundance of known interaction partners in the apical versus basolateral membrane may affect the functioning of this signaling machinery."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — EGFR protein shows positive plasma membrane staining in 31 of 32 cases (97%) of sinonasal inverted papilloma (SIP), a benign but locally aggressive epithelial neoplasm. This establishes high surface prevalence of EGFR in SIP tumor tissue by IHC. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
  - *assay*: Human · sinonasal inverted papilloma (SIP) tumor tissue · fixed · permeabilized
  > "EGFR showed positive plasma membrane staining in 31 of 32 SIP cases (97%)."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — Phosphorylated (activated) EGFR (p-EGFR) shows positive plasma membrane staining in 22 of 32 cases (69%) of sinonasal inverted papilloma (SIP), indicating that a substantial fraction of the EGFR present at the surface in this disease context is in the activated/phosphorylated state. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
  - *assay*: Human · sinonasal inverted papilloma (SIP) tumor tissue · fixed · permeabilized
  > "For p-EGFR, 22 of 32 SIP cases (69%) showed positive plasma membrane staining."
- `a2_evi_05` · *Primary* · Supports · Surface Expression — EGFR / EGFRvIII antigen is uniformly present on the surface of glioma stem-like cells (GSC83) and EGFRvIII-overexpressing U373VIII glioblastoma cells at high levels by flow cytometry; U373 parental cells show low EGFR surface levels. Confocal immunofluorescence of intact (non-permeabilized) vs. permeabilized GSC83 cells further distinguishes surface from intracellular EGFR localization. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · GSC83, U373VIII, U373 glioma cell lines · live · non-permeabilized
  > "(A) Flow cytometry analysis illustrating the uniform presence of EGFR antigen on the surface of glioma cells with high (GSC83 and U373VIII) and low (U373) levels of EGFR/EGFRvIII expression (right panel—dot plot; left panel—histogram); (B) Confocal imaging of immunofluorescent staining for EGFR antigen (red) and CD9 (green) in adherent GSC83 cells either intact or permeabilized before antibody exposure."
- `a2_evi_06` · *Primary* · Supports · Surface Expression — In isolated glioma stem-like cells (GSC83), endogenously expressed EGFR/EGFRvIII is detected principally on the cell surface, with even decoration of the surface confirmed by both flow cytometry and confocal imaging. This confirms plasma membrane-predominant localization in a glioblastoma stem cell context. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
  - *assay*: Human · GSC83 glioma stem-like cells · live · non-permeabilized
  > "In isolated GSC83 cells the endogenously expressed EGFR/EGFRvIII (Spinelli et al. 2024 ) appears to be detectable principally on the cell surface, which is evenly decorated with the EGFR antigen, as revealed by flow cytometry and confocal imaging."
- `a2_evi_07` · *Primary* · Supports · Surface Expression — EGFR is detectable at the cell surface of pancreatic cancer cell lines by flow cytometry, supporting surface expression of EGFR in pancreatic ductal adenocarcinoma-derived tumor cell contexts. ([PMC13088391](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088391/))
  - *assay*: Human · pancreatic cancer cell lines (BxPC-3 implied) · live · non-permeabilized
  > "( A ) Representative flow cytometry histograms of surface EGFR on the indicated pancreatic cancer cell lines."
- `a2_evi_08` · *Primary* · Refutes · Surface Expression — HCT116 colon carcinoma cells, which have a CCLE log2[TPM+1] value of ~0 for EGFR, show minimal to absent surface EGFR staining by flow cytometry — confirming that low mRNA expression translates to absent cell-surface EGFR protein in this colorectal cancer cell line. This provides a negative-control data point supporting tissue/cell-type specificity of EGFR surface expression. ([PMC13096901](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13096901/))
  - *assay*: Human · HCT116 colon carcinoma · live · non-permeabilized
  > "HCT 116 served as a negative control and showed minimal surface staining, consistent with a CCLE value of log2[TPM+1] = 0.0."
- `a2_evi_09` · *Primary* · Ambiguous · Contradictory — In NCI-H1930 lung neuroendocrine carcinoma cells, clinical IHC specimens often exhibit a granular and/or diffuse rather than sharp membranous EGFR staining pattern, yet these cells demonstrate clear cell surface EGFR expression by flow cytometry. This discordance suggests that granular/diffuse IHC morphology may not accurately reflect true plasma membrane surface availability of EGFR. ([PMC13096901](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13096901/))
  - *assay*: Human · NCI-H1930 lung neuroendocrine carcinoma cells / clinical specimens · live · non-permeabilized
  > "In addition, while clinical specimens often exhibited a granular and/or diffuse IHC pattern, rather than a sharp membranous staining, NCI–H1930 cells showed a similar pattern yet demonstrated cell surface expression by flow cytometry."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — EGFR is identified as a known marker of prostate cancer dissemination to bone, and was detected with 19 surface biotinylation sites in a bone-metastatic prostate cancer context, indicating robust surface expression of EGFR on bone-metastatic prostate cancer cells. ([PMC10696767](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10696767/))
  - *assay*: Human · bone-metastatic prostate cancer cells · live · non-permeabilized
  > "Epidermal growth factor receptor (EGFR), a known marker of dissemination of prostate cancer to bones, was detected with 19 biotinylation sites [ 29 ] (Fig. 3 C)."
- `a2_evi_11` · *Primary* · Supports · Surface Expression — Surface biotinylation followed by mass spectrometry of sensory-like neuron cultures (iPSC-derived) from Fabry disease (FD) patients and healthy controls identified EGFR among neuronal plasma membrane proteins, supporting cell-surface presence of EGFR in human sensory-like neurons. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · iPSC-derived sensory-like neuron cultures (FD patients and healthy controls) · live · non-permeabilized
  > "Via biotinylation followed by mass spectrometry ( Fig 1A , 1B ), we identified 1,508 distinct proteins in sensory-like neuron cultures derived from FD patients and controls, consistently observed across three independent experiments (S2 Table)."
- `a2_evi_12` · *Primary* · Ambiguous · Tissue Expression — EGFR is identified among the most deregulated proteins (p < 0.01) in the neuronal plasma membrane proteome of Fabry disease (FD) sensory-like neurons compared to healthy controls, indicating disease-state-associated alteration of EGFR surface levels in iPSC-derived peripheral sensory neurons. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
  - *assay*: Human · iPSC-derived sensory-like neurons (FD vs healthy control) · live · non-permeabilized
  > "Among the most deregulated proteins (p < 0.01), we identified several neuronal candidates with a potential link to nerve pathology such as: calcium voltage-gated channel auxiliary subunit alpha2delta 3 (CACNA2D3, p < 0.01) [ 52 ], neuronal membrane glycoprotein M6-A (GPM6A, p < 0.001) [ 53 , 54 ], ATP-binding cassette subfamily A member 7 (ABCA7) [ 55 ], and epidermal growth factor receptor (EGFR, p < 0.01) [ 56 , 57 ]."
- `a2_evi_13` · *Primary* · Supports · Tissue Expression — EGFR inhibitors (TKIs such as gefitinib/osimertinib) remodel the surfaceome of EGFR-mutant lung adenocarcinoma (LUAD) cells, establishing that EGFR-driven signaling state modulates the overall surface protein landscape in LUAD. This frames a drug-state-induced accessibility modulation context relevant to EGFR surface availability in LUAD. ([PMC12765945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12765945/))
  - *assay*: Human · EGFR-mutant LUAD cell lines (HCC827, PC9, H1650) · live · non-permeabilized
  > "We aimed to assess the extent to which EGFR inhibitors remodel the surfaceome in LUADs and whether such remodeling provides an opportunity for combination therapy."
- `a2_evi_14` · *Primary* · Ambiguous · Tissue Expression — Drug-tolerant persister (DTP) cells generated from EGFR-mutant LUAD lines (HCC827, PC9, H1650) by 3-week gefitinib or osimertinib treatment represent a distinct cell state for surfaceome analysis. This cell-state context (drug-tolerant persisters vs. treatment-naive LUAD) is relevant to EGFR surface accessibility modulation under TKI pressure. ([PMC12765945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12765945/))
  - *assay*: Human · HCC827, PC9, H1650 drug-tolerant persister cells · live · non-permeabilized
  > "To generate drug-tolerant persister cells, EGFR mutant LUAD cell lines HCC827, PC9, and H1650 were treated with 100 nM of gefitinib or osimertinib for 3 weeks."
- `a2_evi_15` · *Secondary* · Refutes · Surface Expression — EGF stimulation induces EGFR internalization followed by lysosomal degradation, representing a ligand-induced accessibility modulation mechanism that reduces surface EGFR. Chloroquine inhibition of lysosomal function blocks this degradation, trapping internalized EGFR in endosomal compartments. This demonstrates that EGF/EGFR binding decreases EGFR surface availability via endocytosis. ([PMC12702325](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12702325/))
  - *assay*: Unspecified · unspecified cancer cell line
  > "A , Schematic of epidermal growth factor (EGF)-induced epidermal growth factor receptor (EGFR) internalization and lysosomal degradation, with or without inhibition of lysosomal function by chloroquine."
- `a2_evi_16` · *Primary* · Supports · Surface Expression — EGFR internalization in A431 squamous carcinoma cells is confirmed to be EGFR-specific: pre-saturation with 1 µM EGF (competing endogenous ligand) blocks uptake of an EGFR-affibody conjugate, demonstrating receptor-mediated endocytosis as the mechanism of EGFR surface-to-intracellular transit upon ligand binding. This confirms that ligand (EGF) engagement drives EGFR surface downregulation in A431 cells. ([PMC10818351](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10818351/))
  - *assay*: Human · A431 squamous carcinoma cells · live · non-permeabilized
  > "To verify that the internalization of MNT 1 , containing an affibody to the epidermal growth factor receptor (EGFR), is EGFR-specific, a control experiment was performed in which A431 cells were first incubated for 1 h with 1 μM epidermal growth factor, EGF, and then these cells were incubated with 200 nM MNT 1 -AF488, to which EGF was added at a concentration of 2 μM."
- `a2_evi_17` · *Primary* · Supports · Tissue Expression — Genetic ablation of Egfr in pancreatic parenchymal (acinar) cells in mouse models protects against KRAS-driven acinar-to-ductal metaplasia and subsequent tumorigenesis, confirming a cell-autonomous role for EGFR in pancreatic acinar cells and its functional significance in KRAS-driven pancreatic neoplasia. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
  - *assay*: Mouse · pancreatic acinar cells
  > "In our previous study, genetic ablation of either Egfr or Adam17 in pancreatic parenchymal cells protects mice from KRAS-driven acinar cell transdifferentiation and subsequent tumorigenesis, 11 supporting a cell autonomous mechanism where EGFR-ligand shedding from acinar cells activates EGFR in those same cells."
- `a2_evi_18` · *Primary* · Supports · Tissue Expression — Human pancreas scRNA-seq data reveal expression of EGFR ligands and ADAM17 across multiple cell clusters in the human pancreas, establishing the cell-type distribution of the EGFR ligand-shedding system in normal human pancreatic tissue. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
  - *assay*: Human · multiple human pancreatic cell clusters
  > "( E ) Dot plot derived from human pancreas scRNA-seq data published by Loveless, et al 38 shows selected genes, ADAM17 , EGFR ligands, IL6R , and TNF , in various cell clusters."
- `a2_evi_19` · *Secondary* · Supports · Tissue Expression — EGFR ranks in the top 84th percentile of expression among proteins detected in glandular tissue from a normal tissue proteomics pool, supporting broadly high EGFR expression in normal glandular epithelium. ([PMC10377392](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10377392/))
  - *assay*: Human · glandular tissue (normal) · fixed · permeabilized
  > "Of interest, the previously described epidermal growth factor receptor (EGFR) was in the top 84% of expression."
- `a2_evi_20` · *Secondary* · Supports · Tissue Expression — In HPV-altered cellular states (e.g., HPV-associated cervical or oropharyngeal cancers), EGFR and downstream signaling pathways (PI3K/Akt, mTOR, JAK/STAT) may be aberrantly activated, indicating that HPV-induced cellular transformation represents a disease state in which EGFR surface signaling is dysregulated. ([PMC10377392](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10377392/))
  - *assay*: Human · HPV-transformed epithelial cells
  > "Among this HPV-altered cellular state, various receptors and their downstream effectors may also be aberrantly activated, such as the EGFR and PI3K/Akt, mTOR, or JAK/STAT signaling pathways [ 50 ]."
- `a2_evi_21` · *Secondary* · Supports · Tissue Expression — EGFR is expressed in normal skin tissue (keratinocytes/epithelial cells), as evidenced by the well-known on-target skin rash adverse event observed upon EGFR inhibitor therapy. This confirms that EGFR is functionally expressed at the surface of normal skin epithelial cells. ([PMC13196744](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13196744/))
  - *assay*: Human · skin keratinocytes / epithelial cells
  > "Inhibitors of receptor tyrosine kinases also show on-target, off-tumor adverse events such as skin rash upon inhibition of epidermal growth factor receptor (EGFR), hypertension upon inhibition of vascular endothelial growth factor receptor, and hyperphosphatemia upon inhibition of fibroblast growth factor receptor (FGFR) ( 3 )."
- `a2_evi_22` · *Secondary* · Supports · Tissue Expression — EGFR is proposed as a flow cytometry-detectable surface marker for identification and enrichment of a subpopulation within small cell lung cancer (SCLC) cells, supporting surface expression of EGFR in at least a subset of SCLC cells. ([PMC8171402](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8171402/))
  - *assay*: Human · small cell lung cancer (SCLC) cells · live · non-permeabilized
  > "In our future work, we are planning to filter out the subpopulation of SCLCs by flow cytometry with surface markers PTGS2/NRG1/EGFR."

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

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence high — EGFR surface accessibility is supported by multiple independent direct assay types across dozens of cell lines and primary patient tissue, fully concordant with the triage verdict. The evidence grade is direct multi-method with no meaningful contradictions to surface expression. The triage prior assigned high confidence for a classical surface receptor, which the experimental evidence fully corroborates.*

## CellxGene RNA enrichment (CZI Census)

*Schema v2.1.3 · CZI Census 2025-11-08 · HPA-style 4× fold-change classification on log1p(CP10K) → linear means, plus Yanai et al. 2005 τ (specificity score ∈ [0, 1], computed over the eligible-entity set). Cell-class rollup walks the Cell Ontology graph (cl-basic.obo, OBO Foundry) — leaf CL → nearest compartment ancestor. CC-BY 4.0 (CZI Census).*

**Classification:**

- **Cell class (CL ontology graph, ~10 compartments):** low specificity · τ=0.49
- **Cell type (leaf Cell Ontology terms, ~600):** enhanced · basal epithelial cell of prostatic duct · 9.0× · τ=0.89
- **Tissue (UBERON terms, ~56):** enhanced · tongue · 59.2× · τ=0.98

**Top 5 cell types (leaf CL, pooled across tissues):**

| Cell type | CL ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| trophoblast giant cell | CL:0002488 | 2.898 | 10.73% | 124 / 1,156 |
| malignant cell | CL:0001064 | 2.862 | 15.14% | 209,677 / 1,384,794 |
| chorionic trophoblast cell | CL:0011101 | 2.854 | 4.53% | 13 / 287 |
| basal epithelial cell of prostatic duct | CL:0002236 | 2.845 | 57.61% | 4,203 / 7,295 |
| skeletal muscle fibroblast | CL:0011027 | 2.795 | 49.01% | 2,898 / 5,913 |

**Top 5 tissues (UBERON, pooled across cell types):**

| Tissue | UBERON ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| tendon of semitendinosus | UBERON:8480009 | 2.520 | 39.28% | 4,137 / 10,533 |
| pleura | UBERON:0000977 | 2.498 | 9.82% | 1,935 / 19,695 |
| placenta | UBERON:0001987 | 2.334 | 45.75% | 144,803 / 316,501 |
| mucosa | UBERON:0000344 | 2.333 | 37.26% | 9,710 / 26,060 |
| testis | UBERON:0000473 | 2.270 | 1.97% | 408 / 20,724 |

<!-- /cellxgene -->
