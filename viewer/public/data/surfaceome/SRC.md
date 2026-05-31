# SRC — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-30T15:53:59.643534Z · model `claude-sonnet-4-6`*

> SRC is canonically an inner-leaflet myristoylated/palmitoylated non-receptor tyrosine kinase with no extracellular domain. A 2025 primary study (PMID:41818370) reports that in cancer cells, SRC undergoes topological inversion onto the outer plasma membrane surface via autophagolysosomal exocytosis (ALE), creating extracellular membrane-associated Src (eSrc). Anti-eSrc antibodies mediate tumor killing in xenograft models and eSrc is detected in primary tumors. Surface accessibility is therefore high in the cancer state but strictly state-gated — normal cells retain inner-leaflet-only topology.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:11283](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:11283) |
| UniProt | [P12931](https://www.uniprot.org/uniprotkb/P12931) |
| NCBI Gene | [6714](https://www.ncbi.nlm.nih.gov/gene/6714) |
| Ensembl | [ENSG00000197122](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000197122) |
| Subcategory | Other |
| Surface accessibility | High |
| Confidence | Moderate |
| Evidence grade | Direct, single method |
| Triage signal | Unlikely |

## 1. Executive summary

SRC is canonically an inner-leaflet myristoylated/palmitoylated non-receptor tyrosine kinase with no extracellular domain. A 2025 primary study (PMID:41818370) reports that in cancer cells, SRC undergoes topological inversion onto the outer plasma membrane surface via autophagolysosomal exocytosis (ALE), creating extracellular membrane-associated Src (eSrc). Anti-eSrc antibodies mediate tumor killing in xenograft models and eSrc is detected in primary tumors. Surface accessibility is therefore high in the cancer state but strictly state-gated — normal cells retain inner-leaflet-only topology.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=Moderate · subcategory=Other · grade=Direct, single method · ecd=None · density=Moderate |
| Expression | level=Moderate · breadth=Broad · specificity=Mostly Intracellular |
| Risks | shed=false · secreted=false · coreceptor=false · masking=true · subdomain=true |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=0 · N-term-ECF=false · C-term-ECF=false |

## 3. Surface evidence

**Evidence grade** · Direct, single method

The strongest evidence comes from PMID:41818370, a 2025 primary study reporting that Src undergoes ALE-mediated topological inversion onto the outer cell surface specifically in cancer cells (eSrc), with functional antibody-based tumor killing validated in xenograft models (a1_evi_01–04). These all derive from a single source, yielding direct_single_method. A companion paper (a1_evi_05) weakly corroborates at review level. Surfaceome MS detections (a1_evi_07, a1_evi_09) are low-weight ancillary signals. The canonical inner-leaflet topology (a1_evi_06) describes the baseline non-cancer state and is tangential — not contradictory — under the ALE state-dependent inversion mechanism. No second independent direct surface methodology (e.g. nonperm IF or surface biotinylation from a distinct group) is present, so the grade is direct_single_method rather than direct_multi_method.

### Cell Surface Capture — Weak Or Ambiguous

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Embryonic chicken limb bud-derived chondrogenic cells; sialoglycoprotein enrichment via aminooxy-biotin conjugation + LC-MS/MS; 3 biological replicates across 5 time points of micromass culture (days 1, 3, 6, 10, 15); SRC detected in surfaceome cluster 2 but lacks canonical signal peptide or glycosylation site — detection may reflect co-purification | Primary Human Cell | Low | 2 |

### Cell Surface Capture — Weak Or Ambiguous

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Unspecified cell type from surfaceome proteomics study; SRC detected in a functional surfaceome cluster alongside ERBB2, CSF1R, PRKCD — noted as non-receptor kinase, presence may reflect co-enrichment | Unknown | Low | 1 |

### Whole Cell Proteomics — Weak Or Ambiguous

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| High-invadopodia-activity cancer cell lines; SRC detected among proteins enriched in secreted extracellular vesicles (sEVs) alongside CTTN, CFL1, ITGA3, ITGB3 and MMP2, MMP14, BSG/CD147 — represents non-canonical extracellular/shed form in exosomes | Established Cell Line | Moderate | 1 |

### Whole Cell Proteomics — Weak Or Ambiguous

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-SRC (60315-1-lg · Proteintech · 60315-1-lg) — Unknown epitope; None validation
- anti-phospho-SRC (Y416) (D49G4 · Cell Signaling Technology · #6943) — Intracellular epitope; None validation

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HaCaT keratinocytes; whole-cell lysate western blot for total SRC and phospho-Y416 SRC; no membrane fractionation — expression evidence only, no surface-accessibility information | Established Cell Line | Moderate | 1 |

### Unknown — Weak Or Ambiguous

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-c-Src — Unknown epitope; None validation

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| MC3T3-E1 osteoblast-like cells after shear stimulation; c-Src co-localizes with RANKL at cell periphery — consistent with inner-leaflet plasma membrane association but does not establish extracellular accessibility | Established Cell Line | Moderate | 1 |

### Unknown — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-Src (eSrc-targeting therapeutic antibody) — Extracellular epitope; Moderate validation; Antibody reported to mediate tumor cell killing in vitro and in vivo xenograft; epitope accessible on outer cell surface via non-canonical ALE exocytosis pathway

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Cancer cell lines (in vitro): Src noncanonically translocated and topologically inverted onto outer cell surface via autophagolysosomal exocytosis (ALE); anti-Src antibody-based therapies mediate tumor cell killing in cell culture | Established Cell Line | Moderate | 3 |
| Primary human tumors: extracellular membrane-associated Src (eSrc) detected in primary tumor specimens | Patient Sample | Moderate | 1 |
| Mouse xenograft models: anti-Src antibody-based therapies mediate tumor cell killing in vivo | Xenograft | Moderate | 1 |

### Unknown — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-Src (eSrc-targeting therapeutic antibody) — Extracellular epitope; None validation; Companion paper corroborating eSrc surface exposure concept; exocytosis exposes Src at outer surface of cancer cells

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Cancer cells (companion paper PMID:41818382): exocytosis exposes Src at the outer surface of cancer cells, cited as poised for therapeutic targeting | Established Cell Line | Moderate | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| HaCaT keratinocyte cell line — whole-cell western blot of total SRC and pY416-SRC | Established Cell Line | Bulk Protein | Moderate | 1 |

**Contradicting evidence**

- *Alternative Localization* (severity High): SRC-family kinases are anchored via myristoylation/palmitoylation to the inner leaflet of the plasma membrane, with all functional domains (SH2, SH3, kinase) facing the cytoplasm. There is no extracellular domain in the canonical topology, directly refuting surface accessibility. Co-localization of c-Src with RANKL at the cell periphery in MC3T3-E1 osteoblasts is consistent with this inner-leaflet association and does not establish extracellular exposure of Src.
  - Likely explanation: SRC is a peripheral membrane protein attached to the cytoplasmic face via lipid modifications; any plasma membrane signal in imaging experiments reflects inner-leaflet localization, not extracellular accessibility. Claims of surface SRC would require unconventional secretion, exosomal display, or an atypical isoform lacking the myristoylation signal.

## 4. Biological context

**Tissues × disease context**

| Tissue | Disease context | Level (protein) | Cell types | Cell states |
|---|---|---|---|---|
| primary tumor (unspecified) | Tumor | Unknown | — | — |
| bone / osteoblast | Normal | Unknown | osteoblast-like cells | fluid shear stress-stimulated, constitutively active Src (Y527F) |
| thyroid | Normal | Unknown | thyroid epithelial cells | — |
| nasopharynx | Tumor | Moderate | nasopharyngeal carcinoma cells | — |
| cartilage | Normal | Unknown | chondrocytes | — |
| brain / glioblastoma | Tumor | Unknown | glioblastoma cells | high invadopodia activity |
| cancer cell lines (unspecified) | Tumor | Unknown | — | — |

**Primary subcellular compartment**: Plasma membrane

**Anatomical accessibility**

- cancer cells (outer plasma membrane surface) — Blood Interstitial Facing · *Favorable*: In cancer, Src is noncanonically translocated via autophagolysosomal exocytosis and topologically inverted onto the outer cell surface (eSrc), making it accessible to systemically delivered antibodies. This surface exposure is cancer-restricted and not seen in normal cells where Src resides on the cytoplasmic inner leaflet.
- normal (non-cancer) cells — cytoplasmic inner leaflet of plasma membrane — Unknown · *Restricted*: In normal cells, Src is tethered via myristoylation/palmitoylation to the inner leaflet of the plasma membrane with all functional domains facing the cytoplasm. No extracellular domain exists, making Src inaccessible to systemically delivered binders in non-cancer tissue.

**Accessibility modulation**

- *Disease State Induced* · trigger: Oncogenic Transformation: Normal (non-cancer) cells where Src is exclusively anchored via N-myristoylation/palmitoylation to the inner leaflet of the plasma membrane with all functional domains facing the cytoplasm → Cancer cells (in vitro cell lines and primary tumor tissue in vivo) — Src undergoes noncanonical topological inversion and translocation onto the outer cell surface, exposing what is normally a cytoplasmic inner-leaflet kinase as an extracellular membrane-associated protein (eSrc). This occurs in multiple cancer types both in culture and in primary tumors.
- *Lysosomal Exocytosis* · trigger: Oncogenic Transformation: Non-cancer cells where autophagolysosomal exocytosis (ALE) is not prominently activated and Src remains intracellular → Cancer cell lines with activated autophagolysosomal exocytosis (ALE) pathway — ALE serves as the secretory mechanism that translocates Src to the outer cell surface in cancer cells, routing the cytoplasmic inner-leaflet kinase through autophagolysosomes that fuse with the plasma membrane and expose Src extracellularly.
- *Stress Induced* · trigger: Mechanical Stress: Resting MC3T3-E1 osteoblast-like cells under static culture conditions → MC3T3-E1 osteoblast-like cells subjected to fluid shear stress — Fluid shear stress increases c-Src activation (Tyr416 phosphorylation) and promotes redistribution of RANKL toward the cell periphery and into the membrane fraction, reflecting a mechanical-stress-induced shift in Src activity and membrane-proximal protein organization.
- *Disease State Induced* · trigger: Oncogenic Transformation: Non-malignant cells where Src is not detected in small extracellular vesicles (sEVs) → Glioblastoma (GBM) cell lines with high invadopodia activity secreting sEVs — In aggressive GBM cells with high invadopodia activity, SRC is enriched in the proteome of secreted small extracellular vesicles (sEV Cluster 2), placing Src in the extracellular/secreted compartment alongside invadopodia regulators.
- *Dual Localization*: Normal cells of any type where Src is canonical: myristoylated/palmitoylated, anchored to the inner leaflet of the plasma membrane with all domains facing the cytoplasm — no outer-surface exposure → Cancer cells where Src is present both as the canonical inner-leaflet cytoplasmic pool and as the eSrc outer-surface pool following ALE-mediated topological inversion — Cancer cells harbor two Src pools: the canonical cytoplasmic inner-leaflet form and the topologically inverted outer-surface eSrc form. The relative abundance of each pool depends on disease state and ALE activity.

## 5. Isoforms

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24*

| Isoform | UniProt | TM | N-term | Signal pep | ECD len | ICD len |
|---|---|---|---|---|---|---|
| **canonical** | P12931 | 0 | Cytoplasmic | 0 aa | 0 aa | 536 aa |
| P12931-2 | P12931-2 | 0 | Cytoplasmic | 0 aa | 0 aa | 542 aa |
| P12931-3 | P12931-3 | 0 | Cytoplasmic | 0 aa | 0 aa | 553 aa |

## 6. Paralogs

*Compara Compara r112*

| Paralog | UniProt | ECD %id | Family |
|---|---|---|---|
| YES1 | [P07947](https://www.uniprot.org/uniprotkb/P07947) | — | Bilateria |
| FYN | [P06241](https://www.uniprot.org/uniprotkb/P06241) | — | Bilateria |
| FGR | [P09769](https://www.uniprot.org/uniprotkb/P09769) | — | Bilateria |
| HCK | [P08631](https://www.uniprot.org/uniprotkb/P08631) | — | Bilateria |
| BLK | [P51451](https://www.uniprot.org/uniprotkb/P51451) | — | Bilateria |
| LYN | [P07948](https://www.uniprot.org/uniprotkb/P07948) | — | Bilateria |
| LCK | [P06239](https://www.uniprot.org/uniprotkb/P06239) | — | Bilateria |
| FRK | [P42685](https://www.uniprot.org/uniprotkb/P42685) | — | Bilateria |
| ABL2 | [P42684](https://www.uniprot.org/uniprotkb/P42684) | — | Bilateria |
| ABL1 | [P00519](https://www.uniprot.org/uniprotkb/P00519) | — | Bilateria |
| PTK6 | [Q13882](https://www.uniprot.org/uniprotkb/Q13882) | — | Bilateria |
| SRMS | [Q9H3Y6](https://www.uniprot.org/uniprotkb/Q9H3Y6) | — | Bilateria |
| TEC | [P42680](https://www.uniprot.org/uniprotkb/P42680) | — | Bilateria |
| FER | [P16591](https://www.uniprot.org/uniprotkb/P16591) | — | Bilateria |
| BTK | [Q06187](https://www.uniprot.org/uniprotkb/Q06187) | — | Bilateria |
| TXK | [P42681](https://www.uniprot.org/uniprotkb/P42681) | — | Bilateria |
| CSK | [P41240](https://www.uniprot.org/uniprotkb/P41240) | — | Bilateria |
| FES | [P07332](https://www.uniprot.org/uniprotkb/P07332) | — | Bilateria |
| SYK | [P43405](https://www.uniprot.org/uniprotkb/P43405) | — | Bilateria |
| ITK | [Q08881](https://www.uniprot.org/uniprotkb/Q08881) | — | Bilateria |
| MATK | [P42679](https://www.uniprot.org/uniprotkb/P42679) | — | Bilateria |
| ZAP70 | [P43403](https://www.uniprot.org/uniprotkb/P43403) | — | Bilateria |
| PTK2 | [Q05397](https://www.uniprot.org/uniprotkb/Q05397) | — | Bilateria |
| PTK2B | [Q14289](https://www.uniprot.org/uniprotkb/Q14289) | — | Bilateria |
| BMX | [P51813](https://www.uniprot.org/uniprotkb/P51813) | — | Bilateria |
| JAK3 | [P52333](https://www.uniprot.org/uniprotkb/P52333) | — | Bilateria |
| JAK1 | [P23458](https://www.uniprot.org/uniprotkb/P23458) | — | Bilateria |
| TYK2 | [P29597](https://www.uniprot.org/uniprotkb/P29597) | — | Bilateria |
| JAK2 | [O60674](https://www.uniprot.org/uniprotkb/O60674) | — | Bilateria |
| TNK2 | [Q07912](https://www.uniprot.org/uniprotkb/Q07912) | — | Bilateria |
| TNK1 | [Q13470](https://www.uniprot.org/uniprotkb/Q13470) | — | Bilateria |
| STYK1 | [Q6J9G0](https://www.uniprot.org/uniprotkb/Q6J9G0) | — | Bilateria |

*Per-antibody cross-reactivity behavior is captured per-clone under §3 (Surface evidence → antibodies). The LLM cross-reactivity verdict is deferred to v1.x.*

## 7. Orthologs

**Mouse**

| Canonical | Isoform | Symbol | UniProt | Type | Full-length %id | ECD %id | ECD %sim | ECD len | TM |
|---|---|---|---|---|---|---|---|---|---|
| ✓ | P05480 | Src | [P05480](https://www.uniprot.org/uniprotkb/P05480) | One2one | 98.9% | — | — | 0 aa | 0 |

**Cynomolgus**

| Canonical | Isoform | Symbol | UniProt | Type | Full-length %id | ECD %id | ECD %sim | ECD len | TM |
|---|---|---|---|---|---|---|---|---|---|
| ✓ | A0A7N9CC30 | SRC | [A0A7N9CC30](https://www.uniprot.org/uniprotkb/A0A7N9CC30) | One2one | 92.5% | — | — | 0 aa | 0 |

## 8. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak

**Secreted form**

- present: false
- severity: Low
- evidence: Weak

**Restricted subdomain**

- present: false
- severity: Low
- evidence: Weak
- domain: Unknown
- rationale: The eSrc surface form is described as outer plasma membrane exposure broadly across cancer cell lines and primary tumors, with no evidence of restriction to a specific subdomain (apical, junctional, synaptic, etc.). The ALE-mediated exocytosis mechanism does not implicate a specific subdomain. No relevant subdomain-restriction data are present in the ledger.

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: SRC membrane anchoring in the canonical state is entirely myristoylation/palmitoylation-driven; no obligate co-receptor is required for membrane association. The cancer-state eSrc surface exposure is driven by the ALE autophagolysosomal exocytosis pathway intrinsic to cancer cells, not by a partner protein requirement.

**ECD size assessment**

- ECD class: None
- rationale: SRC has no canonical extracellular domain — it is an inner-leaflet lipid-anchored kinase. The eSrc cancer-state surface form exposes what is normally the cytoplasmic protein body extracellularly via topological inversion. Antibody engagement targets this inverted cytoplasmic body; the deterministic ECD length is 0.

**Epitope masking**

- severity: Moderate
- evidence: Inferred
- mechanism: Conformational
- rationale: The eSrc surface form presents what is normally a cytoplasmic kinase domain, SH2, and SH3 on the extracellular face following topological inversion. The accessible epitopes are therefore non-glycosylated intracellular domains now extracellularly exposed. Conformational constraints from the inverted topology and possible membrane proximity effects are anticipated but not directly characterised in the ledger.

## 9. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P12931-F1](https://alphafold.ebi.ac.uk/entry/P12931) |
| AFDB version | v6 |
| ECD mean pLDDT | 83.4 |
| ECD disordered fraction | 19.4% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P12931) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

## 10. Evidence ledger

27 entries · 17 primary · 10 secondary · 0 tertiary · 17 PMC OA.

- `a1_evi_01` · *Primary* — A 2025/2026 study reports that Src is noncanonically translocated and topologically inverted onto the outer cell surface in cancer cells, both in vitro and in vivo — a direct surface-expression claim contradicting the canonical inner-leaflet-only model. This is the central finding of the paper and establishes extracellular membrane-associated Src (eSrc) as a bona fide cancer cell surface antigen. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a1_evi_02` · *Primary* — The 2025/2026 study demonstrates that intracellular N-myristoylated proteins, prototypically Src, can undergo topological inversion onto the outer cell surface in cancer — meaning the canonical cytoplasmic/inner-leaflet topology is inverted in this cancer-specific context, placing the Src protein body on the extracellular face. This is a topology-inversion claim that qualifies the standard DeepTMHMM/UniProt topology (all cytoplasmic, no ECD) by identifying a cancer-specific exceptional pathway. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a1_evi_03` · *Primary* — Autophagolysosomal exocytosis (ALE) was identified as the secretory mechanism by which Src reaches the outer cell surface in cancer cell lines. This represents a non-classical (non-ER/Golgi) trafficking route that bypasses the signal-peptide requirement; the ALE pathway is prominent in cancer and delivers Src to the extracellular membrane face. Relevant to risks.shed_form and surface trafficking context. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a1_evi_04` · *Primary* — Extracellular membrane-associated Src (eSrc) was detected in primary tumors, and anti-Src antibody-based therapies mediated tumor cell killing in cell culture systems and in mouse xenograft models. This constitutes direct therapeutic engagement evidence: antibody therapeutics targeting the extracellular face of Src on the cancer cell surface demonstrate in vitro and in vivo preclinical proof-of-concept. No sponsor or clinical stage is named in the abstract; described as antibody-based therapy in preclinical (xenograft) models. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a1_evi_05` · *Secondary* — A companion paper (PMID:41818382) provides a brief title-level assertion that exocytosis exposes Src at the outer surface of cancer cells, poised for therapeutic targeting — a secondary review-level corroboration of the surface-exposure claim, reinforcing the eSrc concept from a second publication in the same cluster. (https://pubmed.ncbi.nlm.nih.gov/41818382/)
- `a1_evi_06` · *Secondary* — SRC-family kinases are canonically tethered via acyl groups (myristoylation/palmitoylation) to the inner leaflet of the plasma membrane, with all functional domains (SH2, SH3, kinase) facing the cytoplasm. This is the standard topology, with no extracellular domain. Directly refutes surface accessibility under canonical conditions. ([PMC11399299](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11399299/))
- `a1_evi_07` · *Secondary* — SRC kinase was identified in surfaceome cluster 2 from a mass-spectrometry-based cell-surface capture (CSC) study of embryonic chicken limb bud-derived chondrogenic cells. The method used sialoglycoprotein enrichment via aminooxy-biotin conjugation + LC-MS/MS. SRC appears among bona fide cell-surface regulators of chondrocyte biology. However, this is a non-human (chicken/chondrogenic) system, and SRC lacks a signal peptide or glycosylation site that would normally anchor it to the CSC enrichment; its detection may reflect co-purification or unconventional surface presentation. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
- `a1_evi_08` · *Secondary* — The surfaceome study used sialoglycoprotein enrichment via aminooxy-biotin conjugation combined with high-resolution LC-MS/MS on 3 biological replicates (n=3) across 5 time points of chondrogenic differentiation. Method family: cell-surface glycoprotein capture (CSC-type). Permeabilization: not required by the chemistry (surface glycoproteins targeted). This methods detail anchors the MethodObservation for the SRC surfaceome detection in chondrogenic cells. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
- `a1_evi_09` · *Secondary* — SRC was identified within a functional surfaceome cluster (alongside ERBB2, CSF1R, PRKCD) in a surfaceome proteomics study. This is a discussion-level mention placing SRC among 'well-known receptor/non-receptor signaling kinases' detected in a surfaceome dataset. The context is a surfaceome study, but SRC is cited as a non-receptor kinase in a signaling cluster — presence may reflect co-enrichment rather than direct surface glycoprotein capture. ([PMC9237123](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9237123/))
- `a1_evi_10` · *Primary* — SRC was detected among proteins enriched in secreted extracellular vesicles (sEVs) from high-invadopodia-activity cancer cell lines, alongside CTTN, CFL1, ITGA3, ITGB3 (invadopodia regulators) and MMP2, MMP14, BSG/CD147. This constitutes evidence for a shed/secreted form of SRC in sEVs (exosomal form), representing a non-canonical route of extracellular SRC presence distinct from plasma-membrane surface presentation. Relevant to risks.shed_form. ([PMC10356899](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10356899/))
- `a1_evi_11` · *Secondary* — Western blot analyses of total SRC protein and its phosphorylated form (Y416) were performed in HaCaT keratinocyte cells (whole-cell lysate, no membrane fractionation). This is a non-surface whole-cell WB detection of SRC — provides tissue/cell-line expression evidence without surface-accessibility information. Relevant to non_surface_expression list. ([PMC8852774](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8852774/))
- `a1_evi_12` · *Secondary* — Anti-SRC antibody identifiers used in a surface biotinylation / WB study: mouse monoclonal anti-SRC (clone 60315-1-lg, Proteintech, catalog 60315-1-lg) and rabbit anti-phospho Y416-SRC (clone D49G4, Cell Signaling Technology, catalog #6943). These antibody identifiers enable downstream AntibodyRef population for MethodObservation. ([PMC9659096](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9659096/))
- `a1_evi_13` · *Secondary* — Fluid shear stress increased c-Src activation (Tyr416 phosphorylation) and promoted redistribution of RANKL toward the cell periphery, with an increase of RANKL in the membrane fraction by subcellular fractionation in MC3T3-E1 osteoblast-like cells. This evidences c-Src's role in promoting membrane trafficking of RANKL — c-Src itself remains cytoplasmic/inner-leaflet but acts as a regulator of surface trafficking. No direct surface localization of Src is claimed. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
- `a1_evi_14` · *Secondary* — Co-expression experiments showed spatial association of RANKL with c-Src at the cell periphery after shear stimulation in MC3T3-E1 cells. c-Src co-localizes with RANKL at the cell periphery — consistent with c-Src's known inner-leaflet plasma membrane association — but does not establish extracellular accessibility of Src itself. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
- `a2_evi_01` · *Primary* — Src is noncanonically translocated and topologically inverted onto the outer cell surface in cancer, both in cell culture (in vitro) and in primary tumors (in vivo). This represents a disease-state-induced surface exposure of an otherwise cytoplasmic inner-leaflet protein. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a2_evi_02` · *Primary* — Autophagolysosomal exocytosis (ALE) is identified as the secretory mechanism by which Src is translocated to the outer cell surface in cancer cells. This cell-state-induced mechanism (ALE pathway activation) drives Src surface exposure in cancer. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a2_evi_03` · *Primary* — Extracellular membrane-associated Src (eSrc) is found in primary tumors but not (implicitly) in normal tissue. This establishes cancer-restricted anatomical accessibility of Src at the outer cell surface, and demonstrates that anti-Src antibody-based therapies can mediate tumor cell killing. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a2_evi_04` · *Primary* — Intracellular N-myristoylated proteins, with Src as the prototype, can be topologically inverted onto the outer cell surface in cancer. This positions normally cytoplasmic Src as an accessible extracellular surface antigen specifically in cancer cells, enabling antibody-based therapeutic targeting. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a2_evi_05` · *Primary* — Exocytosis exposes Src at the outer surface of cancer cells, positioning it for therapeutic targeting. This is a cancer-cell-state-dependent surface accessibility event driven by exocytosis, distinct from normal cell biology where Src resides on the cytoplasmic inner leaflet. (https://pubmed.ncbi.nlm.nih.gov/41818382/)
- `a2_evi_06` · *Secondary* — SRC-family kinases, including SRC itself, are tethered via acyl groups (myristoylation/palmitoylation) to the inner leaflet of the plasma membrane. All functional domains face the cytoplasm; there is no extracellular domain. This places Src at the cytoplasmic face of the plasma membrane in normal (non-cancer) cells. ([PMC11399299](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11399299/))
- `a2_evi_07` · *Primary* — In osteoblast-like MC3T3-E1 cells, fluid shear stress increases c-Src activation (Tyr416 phosphorylation) and promotes redistribution of RANKL toward the cell periphery and into the membrane fraction. This demonstrates a mechanical-stress-induced state change in osteoblast-like cells modulating Src activity. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
- `a2_evi_08` · *Primary* — Constitutively active c-Src (Y527F mutant) enhances peripheral/membrane localization of RANKL in osteoblast-like cells even in the absence of shear stress, demonstrating that Src activity state directly modulates membrane-proximal protein distribution in osteoblasts. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
- `a2_evi_09` · *Primary* — SRC is a key component of the SRC/RAC1/PAK1/PIP5K/EZRIN pathway that regulates NIS actin-cytoskeleton anchoring and retention at the plasma membrane in thyroid cells. SRC acts as an upstream regulator of PM surface retention for a transmembrane symporter, demonstrating SRC's role in modulating surface protein accessibility in thyroid epithelial cells. ([PMC9659096](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9659096/))
- `a2_evi_10` · *Primary* — SRC protein and its activated phospho-form (pSRC Y419) are expressed in nasopharyngeal carcinoma (NPC) cells (HK11.19 line), as shown by western blot. THY1 expression modulates SRC activation state in NPC cells — THY1 knockdown alters pSRC/SRC ratio, indicating cell-state-dependent SRC activity in NPC. ([PMC10093038](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10093038/))
- `a2_evi_11` · *Primary* — SRC kinase is identified as a cell-surface regulator of chondrocyte biology involved in chondrocyte phenotype control, appearing in surfaceome cluster 2 of chondrogenic cells. This places SRC in the surfaceome context of cartilage/chondrocytes, though as an inner-leaflet kinase its surface exposure mechanism requires clarification. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
- `a2_evi_12` · *Primary* — SRC protein is found in small extracellular vesicles (sEVs) secreted by glioblastoma (GBM) cell lines with high invadopodia activity (specifically in Cluster 2 of sEV proteome). This implicates SRC in the extracellular/secreted compartment of aggressive GBM cells. ([PMC10356899](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10356899/))
- `a2_evi_13` · *Primary* — SRC is identified as a non-receptor signaling kinase within a disease-context functional cluster in the cancer surfaceome, co-clustering with receptor tyrosine kinases (ERBB2, CSF1R) in a chemokine signaling/chemotaxis network. This places SRC as part of an altered proteome in cancer with surfaceome-association context. ([PMC9237123](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9237123/))

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/SRC.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/SRC](https://surfaceome.deliverome.org/SRC)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/SRC.json](https://surfaceome.deliverome.org/data/surfaceome/SRC.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/SRC.md](https://surfaceome.deliverome.org/data/surfaceome/SRC.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P12931](https://alphafold.ebi.ac.uk/entry/P12931)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P12931](https://alphafold.ebi.ac.uk/api/prediction/P12931) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P12931](https://www.uniprot.org/uniprotkb/P12931)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-P12931-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-P12931-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-P12931-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-P12931-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-P12931-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-P12931-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*536 aa · `P12931` · embedded at build time*

```
   1  MGSNKSKPKDASQRRRSLEPAENVHGAGGGAFPASQTPSKPASADGHRGPSAAFAPAAAE
  61  PKLFGGFNSSDTVTSPQRAGPLAGGVTTFVALYDYESRTETDLSFKKGERLQIVNNTEGD
 121  WWLAHSLSTGQTGYIPSNYVAPSDSIQAEEWYFGKITRRESERLLLNAENPRGTFLVRES
 181  ETTKGAYCLSVSDFDNAKGLNVKHYKIRKLDSGGFYITSRTQFNSLQQLVAYYSKHADGL
 241  CHRLTTVCPTSKPQTQGLAKDAWEIPRESLRLEVKLGQGCFGEVWMGTWNGTTRVAIKTL
 301  KPGTMSPEAFLQEAQVMKKLRHEKLVQLYAVVSEEPIYIVTEYMSKGSLLDFLKGETGKY
 361  LRLPQLVDMAAQIASGMAYVERMNYVHRDLRAANILVGENLVCKVADFGLARLIEDNEYT
 421  ARQGAKFPIKWTAPEAALYGRFTIKSDVWSFGILLTELTTKGRVPYPGMVNREVLDQVER
 481  GYRMPCPPECPESLHDLMCQCWRKEPEERPTFEYLQAFLEDYFTSTEPQYQPGENL
```

### Alternative-isoform sequences

**P12931-2** (`P12931-2` · 542 aa)

```
   1  MGSNKSKPKDASQRRRSLEPAENVHGAGGGAFPASQTPSKPASADGHRGPSAAFAPAAAE
  61  PKLFGGFNSSDTVTSPQRAGPLAGGVTTFVALYDYESRTETDLSFKKGERLQIVNNTRKV
 121  DVREGDWWLAHSLSTGQTGYIPSNYVAPSDSIQAEEWYFGKITRRESERLLLNAENPRGT
 181  FLVRESETTKGAYCLSVSDFDNAKGLNVKHYKIRKLDSGGFYITSRTQFNSLQQLVAYYS
 241  KHADGLCHRLTTVCPTSKPQTQGLAKDAWEIPRESLRLEVKLGQGCFGEVWMGTWNGTTR
 301  VAIKTLKPGTMSPEAFLQEAQVMKKLRHEKLVQLYAVVSEEPIYIVTEYMSKGSLLDFLK
 361  GETGKYLRLPQLVDMAAQIASGMAYVERMNYVHRDLRAANILVGENLVCKVADFGLARLI
 421  EDNEYTARQGAKFPIKWTAPEAALYGRFTIKSDVWSFGILLTELTTKGRVPYPGMVNREV
 481  LDQVERGYRMPCPPECPESLHDLMCQCWRKEPEERPTFEYLQAFLEDYFTSTEPQYQPGE
 541  NL
```

**P12931-3** (`P12931-3` · 553 aa)

```
   1  MGSNKSKPKDASQRRRSLEPAENVHGAGGGAFPASQTPSKPASADGHRGPSAAFAPAAAE
  61  PKLFGGFNSSDTVTSPQRAGPLAGGVTTFVALYDYESRTETDLSFKKGERLQIVNNTRKV
 121  DVSQTWFTFRWLQREGDWWLAHSLSTGQTGYIPSNYVAPSDSIQAEEWYFGKITRRESER
 181  LLLNAENPRGTFLVRESETTKGAYCLSVSDFDNAKGLNVKHYKIRKLDSGGFYITSRTQF
 241  NSLQQLVAYYSKHADGLCHRLTTVCPTSKPQTQGLAKDAWEIPRESLRLEVKLGQGCFGE
 301  VWMGTWNGTTRVAIKTLKPGTMSPEAFLQEAQVMKKLRHEKLVQLYAVVSEEPIYIVTEY
 361  MSKGSLLDFLKGETGKYLRLPQLVDMAAQIASGMAYVERMNYVHRDLRAANILVGENLVC
 421  KVADFGLARLIEDNEYTARQGAKFPIKWTAPEAALYGRFTIKSDVWSFGILLTELTTKGR
 481  VPYPGMVNREVLDQVERGYRMPCPPECPESLHDLMCQCWRKEPEERPTFEYLQAFLEDYF
 541  TSTEPQYQPGENL
```

### Canonical ortholog sequences

**Mouse — Src** (`P05480` · 535 aa)

```
   1  MGSNKSKPKDASQRRRSLEPSENVHGAGGAFPASQTPSKPASADGHRGPSAAFVPPAAEP
  61  KLFGGFNSSDTVTSPQRAGPLAGGVTTFVALYDYESRTETDLSFKKGERLQIVNNTEGDW
 121  WLAHSLSTGQTGYIPSNYVAPSDSIQAEEWYFGKITRRESERLLLNAENPRGTFLVRESE
 181  TTKGAYCLSVSDFDNAKGLNVKHYKIRKLDSGGFYITSRTQFNSLQQLVAYYSKHADGLC
 241  HRLTTVCPTSKPQTQGLAKDAWEIPRESLRLEVKLGQGCFGEVWMGTWNGTTRVAIKTLK
 301  PGTMSPEAFLQEAQVMKKLRHEKLVQLYAVVSEEPIYIVTEYMNKGSLLDFLKGETGKYL
 361  RLPQLVDMSAQIASGMAYVERMNYVHRDLRAANILVGENLVCKVADFGLARLIEDNEYTA
 421  RQGAKFPIKWTAPEAALYGRFTIKSDVWSFGILLTELTTKGRVPYPGMVNREVLDQVERG
 481  YRMPCPPECPESLHDLMCQCWRKEPEERPTFEYLQAFLEDYFTSTEPQYQPGENL
```

**Cynomolgus — SRC** (`A0A7N9CC30` · 634 aa)

```
   1  MDSDWRVDAIGISLSNDILKTVLRCLLYPCFADEDTEAQRGEVTCLGTHSGERWRRASSS
  61  RPLTSHLVFVPRLQAASQVLRDSPCLLPARTMGSNKSKPKDASQRRRSLEPAENAHGAGG
 121  ALSPPPDPQQASLGRRPPRPQRGLPPRASLLGHRHLPQRAGPLAGGVTTFVALYDYESRT
 181  ETDLSFKKGERLQIVNNTRKVDVSQTWFTFRWLQREGDWWLAHSLSTGQTGYIPSNYVAP
 241  SDSIQAEEWYFGKITRRESERLLLNAENPRGTFLVRESETTKGAYCLSVSDFDNAKGLNV
 301  KHYKIRKLDSGGFYITSRTQFNSLQQLVAYYSKHADGLCHRLTTVCPTSKPQTQGLAKDA
 361  WEIPRESLRLEVKLGQGCFGEVWMGTWNGTTRVAIKTLKPGTMSPEAFLQEAQVMKKLRH
 421  EKLVQLYAVVSEEPIYIVTEYMSKGSLLDFLKGETGKYLRLPQLVDMAAQIASGMAYVER
 481  MNYVHRDLRAANILVGENLVCKVADFGLARLIEDNEYTARQGAKFPIKWTAPEAALYGRF
 541  TIKSDVWSFGILLTELTTKGRVPYPGMVNREVLDQVERGYRMPCPPECPESLHDLMCQCW
 601  RKEPEERPTFEYLQAFLEDYFTSTEPQYQPGENL
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`P12931`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**P12931-2** (`P12931-2`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  II
```

**P12931-3** (`P12931-3`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — Confidence is moderate because the cancer-cell outer-surface SRC story derives from a single recent research cluster — two 2025 papers (PMID:41818370 and PMID:41818382) that appear to originate from the same group. The canonical SRC topology — myristoylated, inner-leaflet, no extracellular domain — is established across decades of independent work (e.g., PMC:PMC11399299). The triage first-pass classified SRC as inner-leaflet-anchored with high confidence, a reasonable call given established biology. Lifting confidence to high would require an independent group to confirm cancer-state outer-leaflet eSrc exposure using orthogonal methodology (e.g., non-permeabilized flow cytometry, surface biotinylation mass spec, or cryo-EM structural evidence of the inverted topology) beyond the antibody-killing xenograft assays reported in PMID:41818370.*
