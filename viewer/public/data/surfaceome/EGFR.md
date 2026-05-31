# EGFR — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-31T03:48:11.344709Z · model `claude-sonnet-4-6`*

> EGFR is a canonical Type I single-pass transmembrane receptor tyrosine kinase with a large (~620 aa) extracellular domain (ECD) constitutively accessible at the plasma membrane of epithelial and many tumor cell types. Multiple orthogonal methods — live-cell flow cytometry (up to 99% surface-positive), non-permeabilized IF, surface biotinylation MS (19 biotinylation sites), SILAC surfaceome, IHC membranous staining (97% of SIP tumors), and structural data — unanimously confirm high-confidence surface accessibility. FDA-approved antibodies (cetuximab, panitumumab) clinically validate the ECD as a therapeutic target. Shed ECD (via ADAM10/17) and ligand-induced internalization are documented but do not preclude effective targeting.

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
| Headline risks | Shed Form, Epitope Masked |

## 1. Executive summary

EGFR is a canonical Type I single-pass transmembrane receptor tyrosine kinase with a large (~620 aa) extracellular domain (ECD) constitutively accessible at the plasma membrane of epithelial and many tumor cell types. Multiple orthogonal methods — live-cell flow cytometry (up to 99% surface-positive), non-permeabilized IF, surface biotinylation MS (19 biotinylation sites), SILAC surfaceome, IHC membranous staining (97% of SIP tumors), and structural data — unanimously confirm high-confidence surface accessibility. FDA-approved antibodies (cetuximab, panitumumab) clinically validate the ECD as a therapeutic target. Shed ECD (via ADAM10/17) and ligand-induced internalization are documented but do not preclude effective targeting.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=High · subcategory=Single-pass type I · grade=Direct, multi-method · ecd=Large · density=High |
| Expression | level=High · breadth=Broad · specificity=Surface Dominant |
| Risks | shed=true · secreted=true · coreceptor=false · masking=true · subdomain=false |
| Cross-species | mouse=88.7% · cyno=98.7% |
| Paralogs | max %ECD identity = 48.5% |
| Topology | TM=1 · N-term-ECF=true · C-term-ECF=false |

## 3. Surface evidence

**Evidence grade** · Direct, multi-method

EGFR has overwhelming direct multi-method evidence for cell-surface accessibility. Live-cell non-permeabilized flow cytometry is demonstrated across multiple independent sources and cell types (glioma GSC83/U373vIII, pancreatic BxPC-3, epidermoid A431, breast MCF-7), with quantitative surface positivity data and EGF-competition specificity controls. Non-permeabilized immunofluorescence (paired with permeabilized controls) in GSC83 cells directly distinguishes surface from intracellular EGFR pools. Independent surface biotinylation assays (sulfo-NHS-biotin + WB and sBioSITe peptide-level MS) confirm EGFR at the plasma membrane in keratinocytes, prostate cancer, iPSC-derived neurons, and polarized MDCK cells across multiple laboratories. IHC membranous staining in 97% of primary human SIP tissue cases further corroborates surface localization. Structural data (crystal structures, cryo-EM) confirm the canonical type-I RTK topology with a large extracellular domain. No contradicting evidence exists. Grade: direct_multi_method.

### Live Cell Flow — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR-AF647 (AY13 · BioLegend · 352918 · AB_2650984) — Extracellular epitope; None validation

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| U373vIII glioma: 98% surface EGFR positive by live-cell flow cytometry | Established Cell Line | High | 1 |
| GSC83 glioma: 99% surface EGFR positive by live-cell flow cytometry | Established Cell Line | High | 1 |
| U373 glioma: 12% surface EGFR positive (low) by live-cell flow cytometry | Established Cell Line | Low | 1 |

### Nonpermeabilized IF — Supports Surface Localization

*Permeabilization: Nonpermeabilized · expression: Endogenous*

**Antibodies**

- anti-EGFR-AF647 (AY13 · BioLegend · 352918 · AB_2650984) — Extracellular epitope; None validation
- anti-CD9-FITC (HI9a · BioLegend · 312104 · AB_2075894) — Extracellular epitope; None validation

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GSC83 glioma adherent cells (fixed, non-permeabilized): EGFR antigen detected on cell surface, evenly decorating the cell | Established Cell Line | High | 2 |

### Permeabilized IF — Expression Only

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-EGFR-AF647 (AY13 · BioLegend · 352918 · AB_2650984) — Extracellular epitope; None validation
- anti-CD9-FITC (HI9a · BioLegend · 312104 · AB_2075894) — Extracellular epitope; None validation

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GSC83 glioma adherent cells (fixed, permeabilized with 0.1% Triton X-100): intracellular EGFR pool detected in addition to surface | Established Cell Line | High | 1 |

### Nonpermeabilized IF — Supports Surface Localization

*Permeabilization: Nonpermeabilized · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Unspecified cell line (nonpermeabilized, fixed): cell surface EGFR detected; significantly higher signal vs permeabilized arm (p<0.01, n=2 experiments) | Established Cell Line | Moderate | 1 |

### Permeabilized IF — Expression Only

*Permeabilization: Permeabilized · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Unspecified cell line (permeabilized): intracellular EGFR pool detected; lower signal than non-permeabilized surface arm (p<0.01) | Established Cell Line | Moderate | 1 |

### Surface Biotinylation — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-phosphotyrosine 4G10 (4G10) — Intracellular epitope; None validation; Pan-phosphotyrosine antibody used to probe ErbB kinases including EGFR after surface biotin pulldown; does not distinguish EGFR-specific signal from other ErbBs

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| DCDMLs: ErbB kinases including EGFR detected in streptavidin bead pulldown of sulfo-NHS-biotinylated surface proteins, probed by anti-pTyr 4G10 WB | Unknown | Moderate | 1 |

### Cell Surface Capture — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Prostate cancer cell lines: EGFR detected with 19 distinct surface-accessible biotinylation sites by sBioSITe peptide-level IP-MS | Established Cell Line | High | 1 |

### Cell Surface Capture — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| iPSC-derived sensory-like neurons from FD patients and controls: EGFR identified among 1,508 surface proteins consistently across 3 independent experiments by sulfo-NHS-SS-biotin + MS | IPSC Derived | Moderate | 1 |

### Cell Surface Capture — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Polarized MDCK epithelial cells (filter-grown): EGFR distributed ~40% apical / ~60% basolateral by quantitative SILAC surfaceome chemoproteomics | Established Cell Line | Moderate | 1 |

### Surface Biotinylation — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| NIKS keratinocytes (Wt16 HPV E7-expressing): modest upregulation of surface EGFR vs control by sulfo-NHS-biotin + streptavidin bead pulldown + WB | Established Cell Line | Moderate | 2 |
| SiHa (HPV16+) and HeLa (HPV18+) cervical cancer cells: surface EGFR detected by plasma membrane biotinylation + WB after E6/E7 knockdown | Established Cell Line | Moderate | 1 |

### IHC Membranous — Supports Surface Localization

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Sinonasal inverted papilloma (SIP) primary tumor tissue (n=32): EGFR positive plasma membrane staining in 31/32 cases (97%); criterion: moderate-to-strong membranous staining in >10% tumor cells | Primary Human Tissue | High | 1 |

### IHC Membranous — Supports Surface Localization

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-EGFR (EP38Y · Abcam · ab52894 · AB_869579) — Intracellular epitope; Strong validation; Immunogen is phospho-peptide around Tyr1068 (intracellular kinase domain); clone EP38Y detects total EGFR regardless of phosphorylation status. KO-validated: signal lost in EGFR-KO HeLa cells.

### Live Cell Flow — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| BxPC-3 and other pancreatic cancer cell lines: surface EGFR detected by live-cell flow cytometry (bispecific antibody characterization study) | Established Cell Line | High | 2 |

### Live Cell Flow — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| A431 epidermoid carcinoma (EGFR-overexpressing): surface EGFR ECD accessible; EGF (1 µM) competition blocks MNT1-AF488 affibody binding confirming EGFR-specificity | Established Cell Line | High | 2 |

### Live Cell Flow — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| MCF-7 breast cancer cells: surface EGFR ECD accessible; engaged by DNA-origami nanostructure bearing biotinylated anti-EGFR antibody conjugate on live cells | Established Cell Line | Moderate | 2 |

### Surface Biotinylation — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- streptavidin-HRP (BioLegend) — Unknown epitope; None validation; Detection reagent (1:2500) for biotinylated EGFR.Fc recovered from protein G bead pulldown after Z_EGFR:1907.BirA* proximity labeling
- anti-EGFR-HRP (Abcam) — Unknown epitope; Weak validation; Used at 1:5000 to confirm EGFR identity among biotinylated proteins pulled down; HRP-conjugated

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| EGFR.Fc recombinant protein: extracellular domain biotinylated by Z_EGFR:1907.BirA* affibody-biotin ligase fusion targeting EGFR ECD; biotinylated EGFR confirmed by WB under non-reducing conditions | Unknown | Moderate | 1 |

### IHC Membranous — Supports Surface Localization

*Permeabilization: Fixed Unknown · expression: Endogenous*

### Live Cell Flow — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| NCI-H1930 neuroendocrine carcinoma: live-cell flow cytometry confirms surface EGFR expression despite granular/diffuse (non-membranous) IHC pattern | Established Cell Line | Moderate | 1 |

### Cell Surface Capture — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| LUAD cell lines (vehicle control and gefitinib-treated): EGFR captured as surface protein by surfaceome MS profiling | Established Cell Line | Moderate | 1 |

### Cell Surface Capture — Supports Membrane Association

*Permeabilization: Live Cell · expression: Endogenous*

### Live Cell Flow — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-EGFR 528mAb (528 · CSIRO) — Extracellular epitope; None validation; Well-characterized anti-EGFR ECD monoclonal antibody clone 528; provided by CSIRO Recombinant Protein Production and Purification Facility

### Unknown — Weak Or Ambiguous

*Permeabilization: Unknown · expression: Unknown*

**Contradicting evidence**

- *Other* (severity Low): In NCI-H1930 cells, IHC showed a granular/diffuse pattern rather than sharp membranous staining, which could be misread as absence of surface EGFR. However, live-cell (non-permeabilized) flow cytometry confirmed genuine surface expression in the same cell line, revealing that IHC morphological scoring alone can underestimate or misclassify true surface accessibility.
  - Likely explanation: The discordance is methodological rather than biological: IHC staining pattern (granular/diffuse vs. sharp membranous) is an imperfect surrogate for surface presence. Live-cell flow cytometry directly detects accessible surface antigen without fixation or permeabilization artifacts, and it confirms EGFR is indeed surface-expressed. The 'contradiction' therefore reflects a limitation of IHC pattern interpretation, not an actual absence of surface EGFR.

## 4. Biological context

**Tissues × disease context**

| Tissue | Disease context | Level (protein) | Cell types | Cell states |
|---|---|---|---|---|
| iPSC-derived sensory-like neurons | Other Disease | Unknown | sensory-like neurons | — |
| bone metastasis (prostate cancer) | Tumor | Moderate | prostate cancer cells | — |
| multi-tumor (GBM, HNSC, LUSC, LUAD, PAAD, COAD, OV) | Tumor | Moderate | — | — |
| lung adenocarcinoma (EGFR-mutant) | Tumor | Unknown | lung adenocarcinoma cells | EGFR TKI-treated, EGFR TKI-untreated |
| skin | Normal | Moderate | epithelial cells | — |

**Primary subcellular compartment**: Plasma membrane

**Anatomical accessibility**

- polarized epithelial cells — Basolateral · *Favorable*: Mass-spec surfaceome shows EGFR distributed ~40:60 apical:basolateral in polarized epithelium, indicating a mild basolateral preference. The basolateral face is blood/interstitial-facing, making EGFR accessible to systemically delivered binders without tight-junction barrier.
- polarized epithelial cells (apical surface) — Apical · *Restricted*: ~40% of EGFR resides on the apical surface of polarized epithelial cells, which faces the lumen and is separated from systemic circulation by tight junctions, restricting access for IV-delivered binders to this fraction.

**Accessibility modulation**

- *Cell State Induced* · trigger: Other: EGFR-expressing cells at baseline (unstimulated, surface EGFR present) → EGF-stimulated cells undergoing ligand-induced internalization — EGF binding triggers EGFR internalization and lysosomal degradation, reducing the surface-accessible pool. Chloroquine inhibition of lysosomal function prevents degradation and alters steady-state surface levels.
- *Post Translational Dependent*: A431 squamous carcinoma cells with unoccupied surface EGFR → A431 cells pre-incubated with excess EGF ligand (ligand occupancy competition) — Pre-incubation with excess EGF blocks surface EGFR binding sites, reducing availability of unoccupied EGFR epitopes to targeting agents such as affibody-conjugates.
- *Polarization Dependent*: Non-polarized epithelial cells with uniform surface EGFR → Polarized epithelial cells with established apical-basolateral polarity — In polarized epithelial cells, EGFR distributes approximately 40:60 (apical:basolateral), showing a mild basolateral preference compared to uniform distribution in non-polarized cells.
- *Disease State Induced*: Healthy iPSC-derived sensory-like neurons → Familial Dysautonomia (FD) patient iPSC-derived sensory-like neurons — EGFR is one of the most significantly deregulated proteins (p<0.01) in the neuronal plasma membrane proteome of FD neurons vs. healthy controls, as detected by surface biotinylation mass spectrometry, indicating a shift in surface EGFR abundance.

## 5. Isoforms

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24*

| Isoform | UniProt | TM | N-term | Signal pep | ECD len | ICD len |
|---|---|---|---|---|---|---|
| **canonical** | P00533 | 1 | Extracellular | 24 aa | 621 aa | 543 aa |
| P00533-2 | P00533-2 | 0 | Extracellular | 24 aa | 381 aa | 0 aa |
| P00533-3 | P00533-3 | 0 | Extracellular | 24 aa | 681 aa | 0 aa |
| P00533-4 | P00533-4 | 0 | Extracellular | 24 aa | 604 aa | 0 aa |

## 6. Paralogs

*Compara Compara r112*

| Paralog | UniProt | ECD %id | Family |
|---|---|---|---|
| ERBB4 | [Q15303](https://www.uniprot.org/uniprotkb/Q15303) | 48.5% | Bilateria |
| ERBB3 | [P21860](https://www.uniprot.org/uniprotkb/P21860) | 45.7% | Bilateria |
| ERBB2 | [P04626](https://www.uniprot.org/uniprotkb/P04626) | 44.3% | Bilateria |
| INSR | [P06213](https://www.uniprot.org/uniprotkb/P06213) | 32.5% | Bilateria |
| ROS1 | [P08922](https://www.uniprot.org/uniprotkb/P08922) | 31.4% | Bilateria |
| IGF1R | [P08069](https://www.uniprot.org/uniprotkb/P08069) | 29.5% | Bilateria |
| INSRR | [P14616](https://www.uniprot.org/uniprotkb/P14616) | 29.5% | Bilateria |
| LTK | [P29376](https://www.uniprot.org/uniprotkb/P29376) | 28.8% | Bilateria |
| FGFR3 | [P22607](https://www.uniprot.org/uniprotkb/P22607) | 28.5% | Bilateria |
| FGFR4 | [P22455](https://www.uniprot.org/uniprotkb/P22455) | 28.4% | Bilateria |
| FGFR2 | [P21802](https://www.uniprot.org/uniprotkb/P21802) | 27.5% | Bilateria |
| NTRK2 | [Q16620](https://www.uniprot.org/uniprotkb/Q16620) | 27.1% | Bilateria |
| FGFR1 | [P11362](https://www.uniprot.org/uniprotkb/P11362) | 26.6% | Bilateria |
| NTRK3 | [Q16288](https://www.uniprot.org/uniprotkb/Q16288) | 26.4% | Bilateria |
| DDR2 | [Q16832](https://www.uniprot.org/uniprotkb/Q16832) | 26.3% | Bilateria |
| AXL | [P30530](https://www.uniprot.org/uniprotkb/P30530) | 26.0% | Bilateria |
| ALK | [Q9UM73](https://www.uniprot.org/uniprotkb/Q9UM73) | 25.9% | Bilateria |
| TYRO3 | [Q06418](https://www.uniprot.org/uniprotkb/Q06418) | 25.6% | Bilateria |
| ROR1 | [Q01973](https://www.uniprot.org/uniprotkb/Q01973) | 25.1% | Bilateria |
| NTRK1 | [P04629](https://www.uniprot.org/uniprotkb/P04629) | 25.0% | Bilateria |
| EPHB3 | [P54753](https://www.uniprot.org/uniprotkb/P54753) | 24.8% | Bilateria |
| TIE1 | [P35590](https://www.uniprot.org/uniprotkb/P35590) | 24.6% | Bilateria |
| EPHB2 | [P29323](https://www.uniprot.org/uniprotkb/P29323) | 24.2% | Bilateria |
| DDR1 | [Q08345](https://www.uniprot.org/uniprotkb/Q08345) | 24.2% | Bilateria |
| MET | [P08581](https://www.uniprot.org/uniprotkb/P08581) | 24.0% | Bilateria |
| EPHA5 | [P54756](https://www.uniprot.org/uniprotkb/P54756) | 23.9% | Bilateria |
| MERTK | [Q12866](https://www.uniprot.org/uniprotkb/Q12866) | 23.8% | Bilateria |
| MST1R | [Q04912](https://www.uniprot.org/uniprotkb/Q04912) | 23.8% | Bilateria |
| EPHB4 | [P54760](https://www.uniprot.org/uniprotkb/P54760) | 23.8% | Bilateria |
| FLT3 | [P36888](https://www.uniprot.org/uniprotkb/P36888) | 23.7% | Bilateria |
| ROR2 | [Q01974](https://www.uniprot.org/uniprotkb/Q01974) | 23.5% | Bilateria |
| TEK | [Q02763](https://www.uniprot.org/uniprotkb/Q02763) | 23.5% | Bilateria |
| EPHA4 | [P54764](https://www.uniprot.org/uniprotkb/P54764) | 23.4% | Bilateria |
| CSF1R | [P07333](https://www.uniprot.org/uniprotkb/P07333) | 22.8% | Bilateria |
| EPHA1 | [P21709](https://www.uniprot.org/uniprotkb/P21709) | 22.8% | Bilateria |
| FLT1 | [P17948](https://www.uniprot.org/uniprotkb/P17948) | 22.7% | Bilateria |
| FLT4 | [P35916](https://www.uniprot.org/uniprotkb/P35916) | 22.7% | Bilateria |
| PDGFRB | [P09619](https://www.uniprot.org/uniprotkb/P09619) | 22.4% | Bilateria |
| KIT | [P10721](https://www.uniprot.org/uniprotkb/P10721) | 22.4% | Bilateria |
| KDR | [P35968](https://www.uniprot.org/uniprotkb/P35968) | 22.4% | Bilateria |
| EPHA3 | [P29320](https://www.uniprot.org/uniprotkb/P29320) | 22.3% | Bilateria |
| PDGFRA | [P16234](https://www.uniprot.org/uniprotkb/P16234) | 22.2% | Bilateria |
| MUSK | [O15146](https://www.uniprot.org/uniprotkb/O15146) | 22.2% | Bilateria |
| EPHA2 | [P29317](https://www.uniprot.org/uniprotkb/P29317) | 22.1% | Bilateria |
| EPHA6 | [Q9UF33](https://www.uniprot.org/uniprotkb/Q9UF33) | 21.8% | Bilateria |
| EPHA10 | [Q5JZY3](https://www.uniprot.org/uniprotkb/Q5JZY3) | 21.8% | Bilateria |
| RET | [P07949](https://www.uniprot.org/uniprotkb/P07949) | 21.2% | Bilateria |
| EPHB1 | [P54762](https://www.uniprot.org/uniprotkb/P54762) | 20.8% | Bilateria |
| EPHA7 | [Q15375](https://www.uniprot.org/uniprotkb/Q15375) | 20.4% | Bilateria |
| EPHA8 | [P29322](https://www.uniprot.org/uniprotkb/P29322) | 20.2% | Bilateria |

*Per-antibody cross-reactivity behavior is captured per-clone under §3 (Surface evidence → antibodies). The LLM cross-reactivity verdict is deferred to v1.x.*

## 7. Orthologs

**Mouse**

| Canonical | Isoform | Symbol | UniProt | Type | Full-length %id | ECD %id | ECD %sim | ECD len | TM |
|---|---|---|---|---|---|---|---|---|---|
| ✓ | Q01279 | Egfr | [Q01279](https://www.uniprot.org/uniprotkb/Q01279) | One2one | 90.5% | 88.7% | 88.7% | 623 aa | 1 |

**Cynomolgus**

| Canonical | Isoform | Symbol | UniProt | Type | Full-length %id | ECD %id | ECD %sim | ECD len | TM |
|---|---|---|---|---|---|---|---|---|---|
| ✓ | A0A2K5WK39 | EGFR | [A0A2K5WK39](https://www.uniprot.org/uniprotkb/A0A2K5WK39) | One2one | 99.3% | 98.7% | 98.7% | 621 aa | 1 |

## 8. Accessibility risks

**Shed form**

- present: true
- severity: Moderate
- evidence: Moderate
- mechanism: ADAM10/ADAM17-Mediated Ectodomain Shedding Releases Soluble ECD; Shed Form Documented In Biological Contexts Including Pancreatic Acinar KRAS-Driven Tumorigenesis
- sheddase: ADAM17 (primary), ADAM10

**Secreted form**

- present: true
- severity: Low
- evidence: Weak
- source: Proteolytic

**Restricted subdomain**

- present: false
- severity: Low
- evidence: Strong
- domain: Unknown
- rationale: EGFR is broadly distributed across the plasma membrane. Quantitative SILAC surfaceome shows ~40:60 apical:basolateral distribution in polarized MDCK cells — both faces accessible — with no restriction to a single inaccessible subdomain. Live-cell flow cytometry across multiple tumor types (glioma, pancreatic, epidermoid, breast) confirms membrane-wide signal.

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: EGFR surface expression is intrinsic to its single-pass Type I transmembrane topology and does not require an obligate co-receptor or chaperone partner for plasma membrane delivery. Multiple independent surface biotinylation and flow cytometry studies confirm endogenous surface expression across diverse cell types without any co-receptor co-expression requirement.

**ECD size assessment**

- ECD class: Large
- rationale: ECD spans residues 25–645 (~620 aa), well above the 200-residue 'large' threshold. Multiple crystal structures (PDB: 1YY9, 3C09, 3NJP, 4UV7, 7OM4) and cryo-EM (PDB: 7SYD) confirm the full four-domain ECD architecture, accommodating many non-overlapping antibody footprints.

**Epitope masking**

- severity: Moderate
- evidence: Moderate
- mechanism: Glycan, Conformational
- rationale: EGFR has 12 N-glycosylation sites on the ECD that can partially occlude epitopes (glycan masking). EGF ligand occupancy competitively blocks the domain III binding site, as demonstrated by EGF competition on live A431 cells reducing affibody binding. Therapeutic antibodies (cetuximab domain III, matuzumab domain IV) show that accessible epitopes exist despite these constraints.

## 9. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P00533-F1](https://alphafold.ebi.ac.uk/entry/P00533) |
| AFDB version | v6 |
| ECD mean pLDDT | 91.0 |
| ECD disordered fraction | 3.2% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P00533) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

## 10. Evidence ledger

64 entries · 53 primary · 11 secondary · 0 tertiary · 64 PMC OA.

- `a1_evi_01` · *Primary* — Live-cell flow cytometry on intact (non-permeabilized) glioma cell lines (U373, U373vIII, GSC83) using anti-EGFR-Alexa Fluor647 conjugated antibody (BioLegend cat# 352918), analyzed on BD FACS Canto with FlowJo v10.7.1. No permeabilization step; measures cell-surface EGFR on live cells. Assay establishes method_family=flow_cytometry, method_subclass=live_cell_surface_staining, permeabilization=false. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
- `a1_evi_02` · *Primary* — Live-cell flow cytometry on intact glioma lines demonstrates endogenous EGFR/EGFRvIII at the cell surface: U373vIII 98% positive, GSC83 99% positive, U373 12% positive. Quantitative surface positivity data from non-permeabilized cells using BioLegend anti-EGFR-AF647 (cat# 352918). Strongly supports stable plasma membrane residence of endogenous EGFR. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
- `a1_evi_03` · *Primary* — Flow cytometry (live cells, non-permeabilized) and confocal IF (paired permeabilized vs intact) confirm endogenous EGFR antigen uniformly present on the surface of glioma cells (GSC83, U373vIII high expression; U373 low). Non-permeabilized confocal IF with anti-EGFR-AF647 (BioLegend 352918) and anti-CD9-FITC (BioLegend 312104) directly demonstrates cell-surface localization of EGFR protein. Paired permeabilized condition confirms intracellular EGFR is also present but surface form is the dominant detectable species by flow. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
- `a1_evi_04` · *Primary* — Confocal IF permeabilization protocol: cells fixed with 4% PFA for 10 min and optionally permeabilized with 0.1% Triton X-100 in PBS for 5 min. Permeabilized vs non-permeabilized arms of the same experiment allow direct comparison of surface vs intracellular EGFR signal; non-permeabilized arm = surface-specific readout. Anchors permeabilization=false for the surface-positive IF arm. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
- `a1_evi_05` · *Primary* — Antibody identifiers for surface vs intracellular confocal IF: anti-EGFR-Alexa Fluor647 (BioLegend 352918) and anti-CD9-FITC (BioLegend 312104) used on both permeabilized and non-permeabilized adherent cells. Provides MethodObservation.antibodies[] clone and catalogue number for the surface-positive non-permeabilized arm. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
- `a1_evi_06` · *Primary* — Endogenously expressed EGFR/EGFRvIII in GSC83 glioma cells is detectable principally on the cell surface, evenly decorating the cell, as shown by live-cell flow cytometry and confocal imaging on intact cells. Summarizes both assay results into a single surface-localization conclusion for endogenous EGFR. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
- `a1_evi_07` · *Primary* — Paired immunofluorescence on non-permeabilized vs permeabilized cells directly demonstrates cell-surface EGFR in intact cells and intracellular EGFR in permeabilized cells. Two independent experiments (mean ± SD, p<0.01 by multiple t-tests). Definitively distinguishes surface from intracellular EGFR pools using permeabilization as the differentiating variable. ([PMC9038772](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9038772/))
- `a1_evi_08` · *Primary* — Cell surface biotinylation (sulfo-NHS-biotin) applied to DCDMLs; plasma membrane proteins collected via streptavidin bead pulldown; ErbB kinases (including EGFR) probed by Western blot with 4G10 anti-phosphotyrosine antibody. Surface biotinylation + streptavidin pulldown + WB pipeline provides direct plasma membrane localization evidence for EGFR family members in intact cells. ([PMC10337807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10337807/))
- `a1_evi_09` · *Primary* — EGFR detected with 19 biotinylation sites in a surface biotinylation (sBioSITe) mass spectrometry study on prostate cancer cells; sBioSITe applies biotin to intact cell surfaces then enriches biotinylated peptides by immunoprecipitation for MS identification. 19 distinct surface-accessible peptide sites confirmed. This is the sBioSITe result clip; pairs with introduction clip for full method documentation. ([PMC10696767](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10696767/))
- `a1_evi_10` · *Primary* — sBioSITe (surface Biotinylation Site Identification Technology) method: biotin labeling of intact cell surfaces, followed by immunoprecipitation of biotinylated peptides for MS/MS identification. Adapted from BioSITe for cell-surface protein enrichment. Method_family=surface_biotinylation, method_subclass=peptide-level IP-MS, permeabilization=false. Paired with results clip identifying EGFR at 19 biotinylation sites. ([PMC10696767](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10696767/))
- `a1_evi_11` · *Primary* — Surface biotinylation method using sulfo-NHS-SS-biotin: intact cells washed with PBS, covered with sulfo-NHS-SS-biotin solution for 10 minutes at room temperature, labeling only extracellular-accessible lysines. Disulfide-cleavable linker (SS) allows selective elution of surface-labeled proteins. Method_family=surface_biotinylation, permeabilization=false. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
- `a1_evi_12` · *Primary* — Sulfo-NHS-SS-biotinylation followed by mass spectrometry of sensory-like neuron cultures identified 1,508 surface proteins including EGFR, consistently across three independent experiments. Provides mass-spec surfaceome confirmation of EGFR at the cell surface in iPSC-derived sensory neuron-like cells. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
- `a1_evi_13` · *Primary* — Surfaceome profiling by SILAC chemoproteomics on polarized MDCK epithelial cells (filter-grown) to map apicobasal surface protein distribution. Method_family=mass_spec_surfaceome; stable isotope labeling (SILAC) + cell-surface chemical labeling. Permeabilization=false (surface-specific capture). Establishes quantitative apicobasal ratio for surface proteins. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
- `a1_evi_14` · *Primary* — Quantitative surfaceome chemoproteomics (SILAC) on polarized MDCK cells shows EGFR is distributed relatively evenly across the apical and basolateral plasma membrane surfaces with an apicobasal ratio of approximately 40:60. Both EGF precursor and EGFR receptor are present at the surface. Confirms EGFR plasma membrane localization in polarized epithelial cells with quantitative apicobasal distribution. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
- `a1_evi_15` · *Primary* — Surface biotinylation (sulfo-NHS-biotin) followed by streptavidin bead recovery and Western blot in HPV E7-expressing NIKS keratinocytes shows higher total surface levels of EGFR (and other selected targets) on the cell surface in Wt16 E7-expressing cells vs control. Confirms EGFR is present and detectable at the plasma membrane by the biotinylation+WB pipeline. ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
- `a1_evi_16` · *Primary* — Surface biotinylation pipeline in SiHa (HPV16+) and HeLa (HPV18+) cells: plasma membrane proteins biotinylated on intact cells, labeled proteins purified, and then assessed by Western blotting including EGFR. Method_family=surface_biotinylation+western_blot paired. Permeabilization=false (surface-specific labeling step). ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
- `a1_evi_17` · *Primary* — Surface EGFR quantified from surface biotinylation assay (Fig. 2B) in HPV E7-expressing keratinocytes; modest upregulation of surface EGFR observed. Demonstrates that EGFR is a quantifiable plasma membrane protein by the biotinylation pipeline and confirms its endogenous surface expression in keratinocyte lines. ([PMC10958106](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10958106/))
- `a1_evi_18` · *Primary* — IHC with antibody staining shows EGFR positive plasma membrane staining in 31 of 32 sinonasal inverted papilloma (SIP) cases (97%). Membranous staining criterion: moderate to strong staining in >10% tumor cells. Provides IHC confirmation of EGFR at the plasma membrane in primary human tumor tissue. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
- `a1_evi_19` · *Secondary* — IHC scoring rubric for EGFR and p-EGFR membranous staining: positive = moderate to strong membranous staining in >10% tumor cells, based on Menendez M et al. Establishes that IHC readout targets plasma membrane localization specifically (membranous staining criterion). Pairs with results_04 and results_05 to anchor MethodObservation for IHC surface staining. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
- `a1_evi_20` · *Secondary* — Antibody reagent table identifies EGFR antibody clone ab52894 (Abcam) used for WB (1:5000) and IHC (1:100). Provides antibody clone/catalogue number for MethodObservation.antibodies[] slot. Enables downstream validation_strategy assessment for the WB+IHC method pairing. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
- `a1_evi_21` · *Primary* — Flow cytometry histograms of surface EGFR on intact pancreatic cancer cell lines (BxPC-3 and others); live-cell surface binding assay on non-permeabilized cells. Demonstrates endogenous EGFR accessible on the plasma membrane of multiple pancreatic cancer lines. Supports method_family=flow_cytometry, surface detection on intact cells. ([PMC13088391](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088391/))
- `a1_evi_22` · *Primary* — Cell-surface binding assessed by flow cytometry on live BxPC-3 pancreatic cancer cells for EGFR; demonstrates surface accessibility of EGFR ECD on intact (non-permeabilized) cells. Part of bispecific antibody characterization study confirming EGFR as a surface target on pancreatic cancer cells. ([PMC13088391](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088391/))
- `a1_evi_23` · *Primary* — Flow cytometry on live A431 epidermoid carcinoma cells used to study binding of MNT1 (affibody-based construct) to EGFR receptors at the cell surface. Intact (non-permeabilized) cells; measures surface-accessible EGFR ECD. A431 is a classic EGFR-overexpressing cell line; method_family=flow_cytometry, permeabilization=false. ([PMC10818351](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10818351/))
- `a1_evi_24` · *Primary* — EGF competition experiment on live A431 cells: pre-incubation with 1 µM EGF blocks binding of MNT1-AF488 affibody construct to cell-surface EGFR, confirming surface specificity. Demonstrates that EGFR ECD is accessible at the plasma membrane and that the binding site overlaps with the EGF binding region. EGF ligand competition = validation that the surface signal is EGFR-specific. ([PMC10818351](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10818351/))
- `a1_evi_25` · *Primary* — DNA-origami nanostructure (DON F) decorated with streptavidin binds biotinylated DNA-antibody conjugates targeting EGFR on the membrane of live MCF-7 breast cancer cells. Flow-based live-cell binding assay confirms EGFR surface accessibility on intact MCF-7 cells; the antibody-DNA conjugate specifically engages cell-surface EGFR ECD. ([PMC11472258](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11472258/))
- `a1_evi_26` · *Secondary* — Panitumumab (fully human anti-EGFR IgG2, KD = 5×10⁻¹¹ M) binds EGFR at the cell surface with picomolar affinity, blocking the EGF binding site. Referenced as a therapeutic antibody engaging the ECD of cell-surface EGFR. Clinical therapeutic engagement: panitumumab is an FDA-approved anti-EGFR antibody (Vectibix, Amgen) for metastatic colorectal cancer, engaging the extracellular domain of membrane-bound EGFR on tumor cells. Supports surface_expression and documents therapeutic engagement of the surface ECD. ([PMC11472258](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11472258/))
- `a1_evi_27` · *Primary* — X-ray crystal structures of cetuximab Fab and matuzumab Fab bound to the human EGFR extracellular domain (PDB: 1YY9 and 3C09 respectively) provide structural evidence that the EGFR ECD is accessible for antibody binding at the cell surface. Cetuximab (Erbitux, Eli Lilly/Merck KGaA) is FDA-approved for EGFR-positive colorectal and head-and-neck cancers; it engages domain III of the EGFR ECD on intact cells. Matuzumab (humanized anti-EGFR IgG1) also targets the ECD. Both therapeutic antibodies confirm the extracellular domain is surface-accessible and structurally characterized. ([PMC12827627](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12827627/))
- `a1_evi_28` · *Primary* — Crystal structure of the full EGFR ectodomain in ternary complex with EgB4 nanobody and EGF determined to 6.0 Å resolution (PDB: 7OM4). Confirms the complete extracellular domain architecture and ligand/antibody-binding surfaces of EGFR. Supports topology claim: large ECD exposed at the cell surface, accessible to nanobodies and growth factor ligands. ([PMC8887186](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8887186/))
- `a1_evi_29` · *Primary* — Cryo-EM reconstruction of EGFR receptor complex shows strongest density in the ectodomain region and weakest density in the transmembrane and intracellular domains. Consistent with all published RTK cryo-EM structures. Confirms ECD is structurally the most ordered and accessible domain; topology: ECD extracellular, single TM helix, ICD cytoplasmic. ([PMC10948148](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10948148/))
- `a1_evi_30` · *Primary* — Cryo-EM structures of liganded HER receptor dimers (including EGFR) show ectodomains adopting characteristic heart-shaped arrangement, consistent across X-ray and cryo-EM structures of EGFR dimers. Confirms the ECD dimerization architecture and its extracellular orientation; topology evidence for surface-exposed ECD in the active dimer state. ([PMC10948148](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10948148/))
- `a1_evi_31` · *Primary* — EGFR ectodomain crystal structure (PDB: 3NJP) used as starting structure for molecular dynamics simulations. Confirms ECD is crystallographically characterized as untethered full ectodomain; anchors topology of the extracellular domain as a structurally defined unit accessible from the extracellular face. ([PMC11965450](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11965450/))
- `a1_evi_32` · *Primary* — Crystal structure of EGFR ECD (PDB: 4UV7) superimposed on EGFR-Matuzumab complex (PDB: 3C09) for epitope mapping. Confirms complete EGFR ectodomain is structurally characterized in multiple crystal forms and directly accessible to therapeutic antibody engagement. Supports topology: large accessible ECD in extracellular space. ([PMC12827627](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12827627/))
- `a1_evi_33` · *Primary* — Complete EGFR ECD structure obtained from cryo-EM (PDB: 7SYD) used for modeling full-length antibody-EGFR complexes. Confirms cryo-EM characterization of the full extracellular domain; supports topology and structural accessibility of the EGFR ECD for IgG and IgM antibody binding. ([PMC12827627](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12827627/))
- `a1_evi_34` · *Primary* — Proximity-labeling biotinylation experiment: Z_EGFR:1907.BirA* affibody-biotin ligase fusion biotinylates EGFR.Fc protein specifically via affibody-mediated proximity; biotinylated EGFR detected by WB with streptavidin-HRP (1:2500) after protein G bead pulldown. Confirms that the EGFR ECD is accessible for affibody binding and proximity labeling from the extracellular face. Method: WB with streptavidin-HRP read-out, non-reducing conditions. ([PMC9890520](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9890520/))
- `a1_evi_35` · *Primary* — WB confirmation of biotinylated EGFR using streptavidin-HRP (BioLegend, 1:2500). Paired with proximity-labeling biotinylation assay. Provides antibody/reagent vendor and dilution for MethodObservation.antibodies[] slot. Anchors streptavidin-HRP reagent (BioLegend) for the WB+biotinylation paired method. ([PMC9890520](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9890520/))
- `a1_evi_36` · *Primary* — WB confirmation of EGFR in biotinylated protein pulldown using anti-EGFR-HRP (Abcam, 1:5000) and anti-HER2-HRP (Novus Biologicals) conjugates. Provides antibody identifiers (vendor Abcam, dilution 1:5000) for EGFR WB detection in the biotinylation assay. Paired WB step anchors MethodObservation for the proximity-labeling surface assay. ([PMC9890520](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9890520/))
- `a1_evi_37` · *Primary* — Construct design for proximity labeling: Z_EGFR:1907.BirA* affibody-biotin ligase fusion, where Z_EGFR:1907 recognizes EGFR ECD; BirA* fused at C-terminus. Sequence HVGSGSELGTGSENLYFQ serves as spacer and TEV cleavage site. Construct targets the extracellular domain of EGFR; validates that the biotinylation assay is directed at the ECD accessible from the extracellular face. ([PMC9890520](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9890520/))
- `a1_evi_38` · *Secondary* — IHC membrane staining scoring rubric: weak=1, complete moderate=2, complete strong=3. Specifically requires complete (circumferential) membrane staining to score 2 or 3, distinguishing membranous from cytoplasmic localization. Establishes the surface-staining criterion for paired IHC results; anchors MethodObservation.method_subclass=membranous_scoring for IHC assays. ([PMC13028177](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13028177/))
- `a1_evi_39` · *Primary* — In NCI-H1930 cells, IHC showed granular/diffuse pattern rather than sharp membranous staining, yet live-cell flow cytometry confirmed surface EGFR expression. Demonstrates discordance between IHC morphological pattern and actual surface expression: IHC membranous scoring may underestimate true surface presence. This represents a methodological caveat — IHC pattern alone is insufficient to conclude absence of surface EGFR. ([PMC13096901](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13096901/))
- `a1_evi_40` · *Secondary* — Surfaceome profiling (mass spectrometry-based surface capture) of LUAD cell lines treated with vehicle control or gefitinib (EGFR TKI). Schematic describes method: surface protein MS capture on LUAD cells. Documents that EGFR is a surface protein in LUAD cells as a starting premise for the surfaceome profiling experiment. Method_family=mass_spec_surfaceome. ([PMC12765945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12765945/))
- `a1_evi_41` · *Secondary* — Cell surface capture (CSC) method for enriching surface glycoproteins: periodate oxidation of glycans generates aldehydes that react with hydrazide beads; captured proteins released by PNGase F. Developed by Wollscheid/Aebersold. Method_family=mass_spec_surfaceome (glycoprotein capture), permeabilization=false (surface-only labeling). Provides method documentation for cell-surface-capture MS approach applicable to EGFR (a glycoprotein with 12 N-glycosylation sites). ([PMC12022999](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12022999/))
- `a1_evi_42` · *Secondary* — Anti-EGFR mouse 528mAb provided by CSIRO fermentation facility; used in subsequent SPR and cell-binding experiments. Provides antibody identifier (528mAb, mouse, anti-EGFR) for MethodObservation.antibodies[] slot. 528mAb is a well-characterized anti-EGFR antibody that binds the extracellular domain. ([PMC10245379](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10245379/))
- `a1_evi_43` · *Secondary* — Full-length EGFR (residues 1–1210) and ECD (residues 25–645) cloned into CMV-FLAG expression vector. Topology anchor: ECD spans residues 25–645 (after signal peptide cleavage at position 24); full-length protein is 1210 aa with single TM helix. Confirms EGFR topology: signal peptide (1–24), extracellular domain (25–645), TM, and intracellular domain (669–1210). ([PMC13010625](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13010625/))
- `a2_evi_01` · *Primary* — EGFR shows positive plasma membrane staining in 97% (31/32) of sinonasal inverted papilloma (SIP) tumor cases, indicating high surface expression in this upper respiratory tract tumor type. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
- `a2_evi_02` · *Primary* — Phosphorylated EGFR (p-EGFR) shows positive plasma membrane staining in 69% (22/32) of sinonasal inverted papilloma (SIP) tumor cases, indicating active EGFR signaling at the cell surface in the majority of this tumor type. ([PMC12674851](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12674851/))
- `a2_evi_03` · *Primary* — EGFR antigen is uniformly present on the surface of glioma cell lines with both high (GSC83, U373VIII) and low (U373) expression levels, as shown by flow cytometry on intact cells and confocal immunofluorescence in intact vs. permeabilized conditions. This establishes plasma membrane surface localization in glioblastoma/glioma cell types. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
- `a2_evi_04` · *Primary* — In GSC83 glioblastoma cells expressing endogenous EGFR/EGFRvIII, EGFR is detected principally on the cell surface, with the surface evenly decorated with EGFR antigen by flow cytometry and confocal imaging. This confirms EGFR surface-restricted localization in glioblastoma cells at endogenous expression levels. ([PMC13054837](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054837/))
- `a2_evi_05` · *Primary* — EGFR surface expression is detectable on pancreatic cancer cell lines (including BxPC-3), as assessed by flow cytometry on intact cells, supporting EGFR plasma membrane presence in pancreatic ductal adenocarcinoma cell models. ([PMC13088391](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088391/))
- `a2_evi_06` · *Primary* — HCT 116 colorectal cancer cells show minimal to absent EGFR surface staining by flow cytometry, consistent with very low RNA expression (log2[TPM+1] = 0.0), establishing HCT 116 as a EGFR-negative control in colorectal cancer. ([PMC13096901](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13096901/))
- `a2_evi_07` · *Primary* — NCI-H1930 cells demonstrate EGFR cell surface expression by flow cytometry, despite clinical specimens and this cell line showing a granular/diffuse rather than sharp membranous IHC staining pattern. This suggests that IHC pattern alone may underestimate surface accessibility in some contexts. ([PMC13096901](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13096901/))
- `a2_evi_08` · *Primary* — In polarized epithelial cells, EGFR is relatively evenly distributed between the apical and basolateral plasma membrane faces with an apicobasal ratio of approximately 40:60 (apical:basolateral). This indicates EGFR is accessible from both surfaces in polarized epithelium, with a mild basolateral preference. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
- `a2_evi_09` · *Primary* — EGFR, as a receptor tyrosine kinase mediating growth signaling, shows similar apical and basolateral surface abundance in polarized epithelial cells, in contrast to many of its interaction partners which are strongly polarized. This establishes EGFR as broadly accessible from both epithelial surfaces. ([PMC9788433](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9788433/))
- `a2_evi_10` · *Primary* — EGFR is identified as one of the most significantly deregulated proteins (p<0.01) in the neuronal plasma membrane proteome of sensory-like neurons derived from Familial Dysautonomia (FD) patients compared to healthy controls, detected by surface biotinylation followed by mass spectrometry. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
- `a2_evi_11` · *Primary* — EGFR mRNA expression was assessed by qPCR in iPSC-derived sensory-like neurons from Familial Dysautonomia (FD) patients and healthy controls to determine whether plasma membrane protein-level changes are mirrored at the transcript level. ([PMC11964241](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964241/))
- `a2_evi_12` · *Primary* — EGFR is detected as a known marker of prostate cancer dissemination to bone, identified with 19 biotinylation sites in a surface proteomics study, supporting EGFR surface expression in bone-metastatic prostate cancer. ([PMC10696767](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10696767/))
- `a2_evi_13` · *Primary* — EGFR surface expression was profiled across 85 PDX models spanning seven tumor types (GBM, HNSC, LUSC, LUAD, PAAD, COAD, and OV) using N-glycoproteomic enrichment, providing pan-cancer evidence for EGFR surface presence across diverse tumor types. ([PMC12923961](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12923961/))
- `a2_evi_14` · *Primary* — In pancreatic acinar cells, EGFR activation via ADAM17-mediated ligand shedding operates in a cell-autonomous manner in the context of KRAS-driven tumorigenesis. Genetic ablation of EGFR or ADAM17 in pancreatic parenchymal cells protects against acinar cell transdifferentiation, indicating functional EGFR surface expression is required in acinar cell disease-state transition. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
- `a2_evi_15` · *Primary* — Human pancreas scRNA-seq data shows EGFR ligand and pathway gene expression across distinct pancreatic cell clusters, providing single-cell resolution of EGFR pathway activity in human pancreatic tissue including acinar, ductal, immune, and other cell types. ([PMC12892050](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12892050/))
- `a2_evi_16` · *Primary* — EGFR inhibitor treatment remodels the surfaceome of EGFR-mutant lung adenocarcinoma (LUAD) cells, indicating that EGFR-driven cell state (TKI-treated vs. untreated) modulates the surface protein landscape in LUAD. This frames EGFR as the key driver of accessibility modulation in EGFR-mutant LUAD. ([PMC12765945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12765945/))
- `a2_evi_17` · *Secondary* — EGFR is expressed in the top 84% of proteins detected in the glans (penile tissue), highlighting relevant surface receptor expression in this anatomical compartment, in the context of HPV-associated disease. ([PMC10377392](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10377392/))
- `a2_evi_18` · *Secondary* — EGFR inhibition causes on-target, off-tumor skin rash, indicating that EGFR is expressed and functionally active at the surface of normal skin/epithelial cells, not just in tumors. ([PMC13196744](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13196744/))
- `a2_evi_19` · *Secondary* — Upon EGF stimulation, EGFR undergoes ligand-induced internalization and lysosomal degradation, representing a key accessibility modulation mechanism: baseline cell-surface EGFR levels are reduced following EGF-driven endocytosis. Inhibition of lysosomal function (e.g., chloroquine) prevents degradation and alters steady-state surface levels. ([PMC12702325](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12702325/))
- `a2_evi_20` · *Primary* — EGFR is present in the plasma membrane of live MCF-7 breast cancer cells, as demonstrated by binding of biotinylated DNA-antibody conjugates to EGFR on intact cells, supporting surface accessibility in breast cancer epithelial cells. ([PMC11472258](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11472258/))
- `a2_evi_21` · *Primary* — EGFR surface accessibility on A431 squamous carcinoma cells can be blocked by pre-incubation with excess EGF ligand, confirming EGFR-specific ligand binding at the cell surface and demonstrating that EGF competition reduces surface availability for targeting agents. This is a direct test of surface EGFR accessibility modulation by ligand occupancy. ([PMC10818351](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10818351/))

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

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence high — Confidence is high. EGFR surface accessibility is supported by the strongest possible evidence grade: multiple independent methods (live-cell flow cytometry, non-permeabilized IF with paired permeabilized controls, surface biotinylation Western blot, peptide-level MS with 19 biotinylation sites, SILAC quantitative surfaceome, IHC membranous staining in primary tumors, structural crystallography/cryo-EM) across more than ten independent research groups and cell contexts. There are no contradicting biological claims — the sole 'contradiction' (IHC pattern discordance in NCI-H1930) is a methodological artifact resolved by flow cytometry. FDA-approved therapeutic antibodies clinically validate the accessible ECD. The triage verdict and deep-dive are in complete agreement.*
