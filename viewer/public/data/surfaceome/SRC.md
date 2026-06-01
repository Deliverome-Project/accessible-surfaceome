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

**Family / classification** — functional class: Enzyme.

**Triage first-pass reasoning** — SRC (p60-Src) is a non-receptor tyrosine kinase that resides on the cytoplasmic face of the plasma membrane. It is myristoylated at Gly2 and further palmitoylated, anchoring it to the inner leaflet of the PM. The kinase domain, SH2, and SH3 domains all face the cytoplasm. There is no extracellular domain. Checking contextual buckets: (1) cell_state_induced — no evidence of stress/activation flipping SRC to outer leaflet; (2) tissue_restricted_surface — not applicable, inner-leaflet anchor; (3) lysosomal_exocytosis — not a lysosomal TM protein; (4) dual_localization — SRC cycles among PM inner leaflet, endosomes, and perinuclear membranes, all cytoplasmic-face; (5) stable_surface_attachment — no ectodomain or secreted form that anchors externally. No antibody/ADC/CAR-T programs target the SRC protein body on the cell surface. The protein body is entirely inaccessible from the extracellular space.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=Moderate · subcategory=Other · ecd=None |
| Classification | reason=Lysosomal Exocytosis · family=Enzyme · state-dependence=High · induction-trigger=— |
| Expression | level=Moderate · breadth=Broad · specificity=Mostly Intracellular · low-endogenous=false · tumor-associated=— · orphan-receptor=false · OE-precedent=false |
| Risks | shed=false · secreted=false · co-receptor=None · masking=true · restricted-subdomain=true |
| Evidence | grade=Direct, single method · density=Moderate · live-cell-surface=— · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=0 · N-term-ECF=false · C-term-ECF=false |

**Facet rationales**

- *Expression level*: SRC is broadly expressed across cancer cell lines and multiple normal cell types (keratinocytes, osteoblasts, thyroid epithelial, T cells) at moderate protein levels by WB; no high-expression context is established in the ledger.
- *Expression breadth*: SRC is detected across diverse tissue/cell contexts: cancer cell lines (multiple types), keratinocytes, osteoblast-like cells, thyroid epithelial cells, T lymphocytes, chondrocytes, and glioblastoma cells — spanning epithelial, immune, skeletal, and neural lineages.
- *Surface specificity*: In normal cells, SRC is exclusively inner-leaflet/cytoplasmic. Only in cancer cells does a fraction reach the outer surface via ALE. The dominant population across all cell types is intracellular; the surface-accessible eSrc pool is cancer-state-restricted.
- *Known ligand*: SRC is a non-receptor tyrosine kinase with well-documented interacting partners and substrates (e.g., FAK, EGFR, integrins, RANKL pathway). It is not an orphan; canonical SH2/SH3-mediated partner interactions are extensively characterised.
- *Low endogenous expression*: Derived from expression_level='moderate' (not low/absent → not flagged). SRC is broadly expressed across cancer cell lines and multiple normal cell types (keratinocytes, osteoblasts, thyroid epithelial, T cells) at moderate protein levels by WB; no high-expression context is established in the ledger.
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Direct, single method

The strongest evidence comes from PMID:41818370, a 2025 primary study reporting that Src undergoes ALE-mediated topological inversion onto the outer cell surface specifically in cancer cells (eSrc), with functional antibody-based tumor killing validated in xenograft models (a1_evi_01–04). These all derive from a single source, yielding direct_single_method. A companion paper (a1_evi_05) weakly corroborates at review level. Surfaceome MS detections (a1_evi_07, a1_evi_09) are low-weight ancillary signals. The canonical inner-leaflet topology (a1_evi_06) describes the baseline non-cancer state and is tangential — not contradictory — under the ALE state-dependent inversion mechanism. No second independent direct surface methodology (e.g. nonperm IF or surface biotinylation from a distinct group) is present, so the grade is direct_single_method rather than direct_multi_method.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Supports Surface | Moderate | Primary study: Src topologically inverted onto outer cancer cell surface in vitro and in vivo; single source, no KO control cited in abstract |
| a1_evi_02 | Supports Surface | Moderate | Topology-inversion claim from same primary source (PMID:41818370); ALE mechanism places Src body on extracellular face in cancer |
| a1_evi_03 | Supports Surface | Moderate | ALE-mediated trafficking to outer membrane surface; functional assay from same primary source |
| a1_evi_04 | Supports Surface | Moderate | Anti-Src antibody kills tumor cells in xenograft models; functional engagement at extracellular face; same primary source |
| a1_evi_05 | Supports Surface | Low | Companion review-level paper corroborating eSrc surface exposure; secondary/weak, no primary methodology |
| a1_evi_06 | Tangential | High | Canonical inner-leaflet topology — describes baseline normal-cell state; NOT contradictory given cancer-state ALE inversion mechanism |
| a1_evi_07 | Supports Surface | Low | Chick chondrogenic surfaceome CSC-MS; non-human system, possible co-purification, weak species/context transfer |
| a1_evi_08 | Tangential | Low | Methods detail for chondrogenic surfaceome study; informative but not a direct surface claim |
| a1_evi_09 | Supports Surface | Low | SRC in surfaceome cluster alongside ERBB2/CSF1R; discussion-level, co-enrichment possible, no methodology detail |
| a1_evi_10 | Tangential | Low | SRC in sEVs from cancer cell lines; shed/exosomal form, not plasma membrane surface accessibility |
| a1_evi_11 | Expression Only | Low | Whole-cell WB of SRC in HaCaT keratinocytes; no surface-accessibility information |
| a1_evi_12 | Tangential | Low | Antibody identifiers for WB/biotinylation study; methodological metadata only |
| a1_evi_13 | Tangential | Low | c-Src activates RANKL membrane redistribution in osteoblasts; Src stays inner-leaflet, no Src surface claim |
| a1_evi_14 | Tangential | Low | c-Src co-localizes with RANKL at cell periphery; consistent with canonical inner-leaflet association, no extracellular Src claim |

### Immunofluorescence (1 method)

#### Unknown — Weak Or Ambiguous · Plasma Membrane Localized

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-c-Src — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| MC3T3-E1 osteoblast-like cells after shear stimulation; c-Src co-localizes with RANKL at cell periphery — consistent with inner-leaflet plasma membrane association but does not establish extracellular accessibility | Established Cell Line | Moderate | 1 |

### Surface mass spec (3 methods)

#### Cell Surface Capture — Weak Or Ambiguous · Unclear

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Embryonic chicken limb bud-derived chondrogenic cells; sialoglycoprotein enrichment via aminooxy-biotin conjugation + LC-MS/MS; 3 biological replicates across 5 time points of micromass culture (days 1, 3, 6, 10, 15); SRC detected in surfaceome cluster 2 but lacks canonical signal peptide or glycosylation site — detection may reflect co-purification | Primary Human Cell | Low | 2 |

#### Cell Surface Capture — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Unspecified cell type from surfaceome proteomics study; SRC detected in a functional surfaceome cluster alongside ERBB2, CSF1R, PRKCD — noted as non-receptor kinase, presence may reflect co-enrichment | Unknown | Low | 1 |

#### Whole Cell Proteomics — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| High-invadopodia-activity cancer cell lines; SRC detected among proteins enriched in secreted extracellular vesicles (sEVs) alongside CTTN, CFL1, ITGA3, ITGB3 and MMP2, MMP14, BSG/CD147 — represents non-canonical extracellular/shed form in exosomes | Established Cell Line | Moderate | 1 |

### Functional surface assay (2 methods)

#### Unknown — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-Src (eSrc-targeting therapeutic antibody) — Extracellular epitope; Unknown; Moderate validation (Orthogonal Method); Antibody reported to mediate tumor cell killing in vitro and in vivo xenograft; epitope accessible on outer cell surface via non-canonical ALE exocytosis pathway

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Cancer cell lines (in vitro): Src noncanonically translocated and topologically inverted onto outer cell surface via autophagolysosomal exocytosis (ALE); anti-Src antibody-based therapies mediate tumor cell killing in cell culture | Established Cell Line | Moderate | 3 |
| Primary human tumors: extracellular membrane-associated Src (eSrc) detected in primary tumor specimens | Patient Sample | Moderate | 1 |
| Mouse xenograft models: anti-Src antibody-based therapies mediate tumor cell killing in vivo | Xenograft | Moderate | 1 |

#### Unknown — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-Src (eSrc-targeting therapeutic antibody) — Extracellular epitope; Unknown; None validation (None); Companion paper corroborating eSrc surface exposure concept; exocytosis exposes Src at outer surface of cancer cells

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Cancer cells (companion paper PMID:41818382): exocytosis exposes Src at the outer surface of cancer cells, cited as poised for therapeutic targeting | Established Cell Line | Moderate | 1 |

### Other (1 method)

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-SRC (60315-1-lg · Proteintech · 60315-1-lg) — Unknown epitope; Monoclonal; None validation (None)
- anti-phospho-SRC (Y416) (D49G4 · Cell Signaling Technology · #6943) — Intracellular epitope; Monoclonal; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HaCaT keratinocytes; whole-cell lysate western blot for total SRC and phospho-Y416 SRC; no membrane fractionation — expression evidence only, no surface-accessibility information | Established Cell Line | Moderate | 1 |

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

**Cell types** *(orthogonal cell-type index)*

| Cell type | Ontology | Present in tissues | Species | Cites |
|---|---|---|---|---|
| T lymphocytes | — | — | Unspecified | 1 |
| osteoblast-like cells | — | — | Mouse | 2 |
| thyroid epithelial cells | — | thyroid | Human | 1 |
| nasopharyngeal carcinoma cells | — | nasopharynx | Human | 1 |
| chondrocytes | — | cartilage | Other | 1 |
| glioblastoma cells | — | — | Human | 1 |

**Cell states**

- *tumor* — In cancer cells (but not normal cells), Src is noncanonically translocated via autophagolysosomal exocytosis (ALE) and topologically inverted onto the outer plasma membrane surface, both in vitro and in primary tumors in vivo. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_13)*
- *mechanical stress* — Fluid shear stress increases c-Src activation (Tyr416 phosphorylation) in osteoblast-like MC3T3-E1 cells, promoting redistribution of membrane-associated proteins toward the cell periphery and membrane fraction. *(cites: a2_evi_07, a2_evi_08)*
- *high invadopodia activity* — Glioblastoma cells with high invadopodia activity secrete small extracellular vesicles (sEVs) with enriched SRC abundance, implicating this invasive state in extracellular SRC compartmentalization. *(cites: a2_evi_12)*

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- Cytoplasmic Inner Leaflet Of Plasma Membrane · normal (non-cancer) cells *(cites: a2_evi_06)*
- Outer Cell Surface (Extracellular Face Of Plasma Membrane) · cancer cells, via autophagolysosomal exocytosis (ALE) *(cites: a2_evi_01, a2_evi_02, a2_evi_04, a2_evi_05)*
- Small Extracellular Vesicles (SEVs) / Secreted · glioblastoma cells with high invadopodia activity *(cites: a2_evi_12)*

**Membrane subdomains**: Inner Leaflet Of Plasma Membrane (Acyl-Anchored Via Myristoylation/Palmitoylation), Cell Periphery / Membrane Fraction (Shear-Stress-Induced Redistribution In Osteoblast-Like Cells)

**Anatomical accessibility**

- cancer cells (outer plasma membrane surface) — Blood Interstitial Facing · *Favorable*: In cancer, Src is noncanonically translocated via autophagolysosomal exocytosis and topologically inverted onto the outer cell surface (eSrc), making it accessible to systemically delivered antibodies. This surface exposure is cancer-restricted and not seen in normal cells where Src resides on the cytoplasmic inner leaflet.
- normal (non-cancer) cells — cytoplasmic inner leaflet of plasma membrane — Unknown · *Restricted*: In normal cells, Src is tethered via myristoylation/palmitoylation to the inner leaflet of the plasma membrane with all functional domains facing the cytoplasm. No extracellular domain exists, making Src inaccessible to systemically delivered binders in non-cancer tissue.

**Accessibility modulation**

- *Disease State Induced* · trigger: Oncogenic Transformation: Normal (non-cancer) cells where Src is exclusively anchored via N-myristoylation/palmitoylation to the inner leaflet of the plasma membrane with all functional domains facing the cytoplasm → Cancer cells (in vitro cell lines and primary tumor tissue in vivo) — Src undergoes noncanonical topological inversion and translocation onto the outer cell surface, exposing what is normally a cytoplasmic inner-leaflet kinase as an extracellular membrane-associated protein (eSrc). This occurs in multiple cancer types both in culture and in primary tumors. *(→ ESrc On The Outer Surface Of Cancer Cells Becomes Accessible To Antibodies And Extracellular Binders, Enabling Antibody-Based Therapeutic Targeting And Tumor Cell Killing. Normal Cells Lacking ESrc Provide A Tumor-Selective Therapeutic Window.)* *(cites: a2_evi_01, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06)*
- *Lysosomal Exocytosis* · trigger: Oncogenic Transformation: Non-cancer cells where autophagolysosomal exocytosis (ALE) is not prominently activated and Src remains intracellular → Cancer cell lines with activated autophagolysosomal exocytosis (ALE) pathway — ALE serves as the secretory mechanism that translocates Src to the outer cell surface in cancer cells, routing the cytoplasmic inner-leaflet kinase through autophagolysosomes that fuse with the plasma membrane and expose Src extracellularly. *(→ The ALE-Dependent Surface Delivery Mechanism Means Src Outer-Surface Accessibility Is Gated By Lysosomal Fusion Activity. Inhibiting ALE Could Suppress ESrc Surface Exposure; Conversely, Enhanced ALE In Cancer Amplifies The Accessible ESrc Pool For Therapeutic Targeting.)* *(cites: a2_evi_02, a2_evi_05)*
- *Stress Induced* · trigger: Mechanical Stress: Resting MC3T3-E1 osteoblast-like cells under static culture conditions → MC3T3-E1 osteoblast-like cells subjected to fluid shear stress — Fluid shear stress increases c-Src activation (Tyr416 phosphorylation) and promotes redistribution of RANKL toward the cell periphery and into the membrane fraction, reflecting a mechanical-stress-induced shift in Src activity and membrane-proximal protein organization. *(→ Mechanical Activation Of Src In Osteoblasts Alters The Membrane Distribution Of Associated Proteins (E.G., RANKL), Potentially Modulating Surface Accessibility Of Src-Regulated Targets. Constitutively Active Src (Y527F) Mimics This Effect Without Shear Stress.)* *(cites: a2_evi_07, a2_evi_08)*
- *Disease State Induced* · trigger: Oncogenic Transformation: Non-malignant cells where Src is not detected in small extracellular vesicles (sEVs) → Glioblastoma (GBM) cell lines with high invadopodia activity secreting sEVs — In aggressive GBM cells with high invadopodia activity, SRC is enriched in the proteome of secreted small extracellular vesicles (sEV Cluster 2), placing Src in the extracellular/secreted compartment alongside invadopodia regulators. *(→ SRC Present In SEVs From Invasive GBM Cells Is Extracellularly Accessible As A Secreted/Vesicle-Associated Form, Potentially Representing An Additional Disease-State-Specific Pool Of Src Outside The Cell That Could Be Detected Or Targeted In The Tumor Microenvironment.)* *(cites: a2_evi_12)*
- *Dual Localization*: Normal cells of any type where Src is canonical: myristoylated/palmitoylated, anchored to the inner leaflet of the plasma membrane with all domains facing the cytoplasm — no outer-surface exposure → Cancer cells where Src is present both as the canonical inner-leaflet cytoplasmic pool and as the eSrc outer-surface pool following ALE-mediated topological inversion — Cancer cells harbor two Src pools: the canonical cytoplasmic inner-leaflet form and the topologically inverted outer-surface eSrc form. The relative abundance of each pool depends on disease state and ALE activity. *(→ Only The Outer-Surface ESrc Pool Is Accessible To Extracellular Binders. The Co-Existing Cytoplasmic Pool Is Inaccessible Without Permeabilization. Assays Must Distinguish These Pools; Non-Permeabilized Staining Or Surface Biotinylation Specifically Interrogates The Accessible ESrc Fraction.)* *(cites: a2_evi_01, a2_evi_04, a2_evi_06)*

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Weak
- domain: Unknown
- rationale: The eSrc surface form is described as outer plasma membrane exposure broadly across cancer cell lines and primary tumors, with no evidence of restriction to a specific subdomain (apical, junctional, synaptic, etc.). The ALE-mediated exocytosis mechanism does not implicate a specific subdomain. No relevant subdomain-restriction data are present in the ledger.
- cites: a1_evi_01, a1_evi_04, a2_evi_01, a2_evi_03

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: SRC membrane anchoring in the canonical state is entirely myristoylation/palmitoylation-driven; no obligate co-receptor is required for membrane association. The cancer-state eSrc surface exposure is driven by the ALE autophagolysosomal exocytosis pathway intrinsic to cancer cells, not by a partner protein requirement.
- cites: a1_evi_06, a2_evi_06, a2_evi_02

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P12931 | ref | ref | 0 | 0 aa | 536 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | P12931-2 | P12931-2 | 100.0% | — | 0 | 0 aa | 542 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | P12931-3 | P12931-3 | 100.0% | — | 0 | 0 aa | 553 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Mouse ortholog | Src | [P05480](https://www.uniprot.org/uniprotkb/P05480) | 98.9% | — | 0 | 0 aa | — | — | — | high (≥85%) |
| Cynomolgus ortholog | SRC | [A0A7N9CC30](https://www.uniprot.org/uniprotkb/A0A7N9CC30) | 92.5% | — | 0 | 0 aa | — | — | — | high (≥85%) |
| Paralog | YES1 | [P07947](https://www.uniprot.org/uniprotkb/P07947) | 75.6% | — | — | — | — | — | — | caution |
| Paralog | FYN | [P06241](https://www.uniprot.org/uniprotkb/P06241) | 69.0% | — | — | — | — | — | — | caution |
| Paralog | FGR | [P09769](https://www.uniprot.org/uniprotkb/P09769) | 65.9% | — | — | — | — | — | — | caution |
| Paralog | HCK | [P08631](https://www.uniprot.org/uniprotkb/P08631) | 53.7% | — | — | — | — | — | — | low-risk |
| Paralog | BLK | [P51451](https://www.uniprot.org/uniprotkb/P51451) | 52.1% | — | — | — | — | — | — | low-risk |
| Paralog | LYN | [P07948](https://www.uniprot.org/uniprotkb/P07948) | 52.1% | — | — | — | — | — | — | low-risk |
| Paralog | LCK | [P06239](https://www.uniprot.org/uniprotkb/P06239) | 50.9% | — | — | — | — | — | — | low-risk |
| Paralog | FRK | [P42685](https://www.uniprot.org/uniprotkb/P42685) | 44.8% | — | — | — | — | — | — | low-risk |
| Paralog | ABL2 | [P42684](https://www.uniprot.org/uniprotkb/P42684) | 39.7% | — | — | — | — | — | — | low-risk |
| Paralog | ABL1 | [P00519](https://www.uniprot.org/uniprotkb/P00519) | 38.6% | — | — | — | — | — | — | low-risk |
| Paralog | PTK6 | [Q13882](https://www.uniprot.org/uniprotkb/Q13882) | 38.2% | — | — | — | — | — | — | low-risk |
| Paralog | SRMS | [Q9H3Y6](https://www.uniprot.org/uniprotkb/Q9H3Y6) | 37.1% | — | — | — | — | — | — | low-risk |
| Paralog | TEC | [P42680](https://www.uniprot.org/uniprotkb/P42680) | 34.7% | — | — | — | — | — | — | low-risk |
| Paralog | FER | [P16591](https://www.uniprot.org/uniprotkb/P16591) | 33.8% | — | — | — | — | — | — | low-risk |
| Paralog | BTK | [Q06187](https://www.uniprot.org/uniprotkb/Q06187) | 33.2% | — | — | — | — | — | — | low-risk |
| Paralog | TXK | [P42681](https://www.uniprot.org/uniprotkb/P42681) | 33.2% | — | — | — | — | — | — | low-risk |
| Paralog | CSK | [P41240](https://www.uniprot.org/uniprotkb/P41240) | 33.2% | — | — | — | — | — | — | low-risk |
| Paralog | FES | [P07332](https://www.uniprot.org/uniprotkb/P07332) | 32.3% | — | — | — | — | — | — | low-risk |
| Paralog | SYK | [P43405](https://www.uniprot.org/uniprotkb/P43405) | 32.1% | — | — | — | — | — | — | low-risk |
| Paralog | ITK | [Q08881](https://www.uniprot.org/uniprotkb/Q08881) | 31.5% | — | — | — | — | — | — | low-risk |
| Paralog | MATK | [P42679](https://www.uniprot.org/uniprotkb/P42679) | 31.2% | — | — | — | — | — | — | low-risk |
| Paralog | ZAP70 | [P43403](https://www.uniprot.org/uniprotkb/P43403) | 31.2% | — | — | — | — | — | — | low-risk |
| Paralog | PTK2 | [Q05397](https://www.uniprot.org/uniprotkb/Q05397) | 31.2% | — | — | — | — | — | — | low-risk |
| Paralog | PTK2B | [Q14289](https://www.uniprot.org/uniprotkb/Q14289) | 30.0% | — | — | — | — | — | — | low-risk |
| Paralog | BMX | [P51813](https://www.uniprot.org/uniprotkb/P51813) | 29.9% | — | — | — | — | — | — | low-risk |
| Paralog | JAK3 | [P52333](https://www.uniprot.org/uniprotkb/P52333) | 29.5% | — | — | — | — | — | — | low-risk |
| Paralog | JAK1 | [P23458](https://www.uniprot.org/uniprotkb/P23458) | 29.1% | — | — | — | — | — | — | low-risk |
| Paralog | TYK2 | [P29597](https://www.uniprot.org/uniprotkb/P29597) | 28.7% | — | — | — | — | — | — | low-risk |
| Paralog | JAK2 | [O60674](https://www.uniprot.org/uniprotkb/O60674) | 28.4% | — | — | — | — | — | — | low-risk |
| Paralog | TNK2 | [Q07912](https://www.uniprot.org/uniprotkb/Q07912) | 25.2% | — | — | — | — | — | — | low-risk |
| Paralog | TNK1 | [Q13470](https://www.uniprot.org/uniprotkb/Q13470) | 21.6% | — | — | — | — | — | — | low-risk |
| Paralog | STYK1 | [Q6J9G0](https://www.uniprot.org/uniprotkb/Q6J9G0) | 19.0% | — | — | — | — | — | — | low-risk |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak
- cites: a1_evi_03, a1_evi_04

**Secreted form**

- present: false
- severity: Low
- evidence: Weak

**ECD size assessment**

- ECD class: None
- rationale: SRC has no canonical extracellular domain — it is an inner-leaflet lipid-anchored kinase. The eSrc cancer-state surface form exposes what is normally the cytoplasmic protein body extracellularly via topological inversion. Antibody engagement targets this inverted cytoplasmic body; the deterministic ECD length is 0.
- cites: a1_evi_06, a2_evi_06

**Epitope masking**

- severity: Moderate
- evidence: Inferred
- mechanism: Conformational
- rationale: The eSrc surface form presents what is normally a cytoplasmic kinase domain, SH2, and SH3 on the extracellular face following topological inversion. The accessible epitopes are therefore non-glycosylated intracellular domains now extracellularly exposed. Conformational constraints from the inverted topology and possible membrane proximity effects are anticipated but not directly characterised in the ledger.
- cites: a1_evi_02, a2_evi_04

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P12931-F1](https://alphafold.ebi.ac.uk/entry/P12931) |
| AFDB version | v6 |
| ECD mean pLDDT | 83.4 |
| ECD disordered fraction | 19.4% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P12931) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P12931](https://alphafold.ebi.ac.uk/entry/P12931) | AlphaFold DB (AF-P12931-F1, v6) |
| Isoform P12931-2 | [P12931-2](https://alphafold.ebi.ac.uk/entry/P12931-2) | AlphaFold DB |
| Isoform P12931-3 | [P12931-3](https://alphafold.ebi.ac.uk/entry/P12931-3) | AlphaFold DB |
| Mouse ortholog (Src) | [P05480](https://alphafold.ebi.ac.uk/entry/P05480) | AlphaFold DB |
| Cynomolgus ortholog (SRC) | [A0A7N9CC30](https://alphafold.ebi.ac.uk/entry/A0A7N9CC30) | AlphaFold DB |
| Experimental (best) | [8JN8](https://www.rcsb.org/structure/8jn8) chain A | RCSB PDB · X-ray diffraction 1.902 Å · UniProt 1–536 |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

27 entries · 17 primary · 10 secondary · 0 tertiary · 17 PMC OA.

- `a1_evi_01` · *Primary* · Supports · Surface Expression — A 2025/2026 study reports that Src is noncanonically translocated and topologically inverted onto the outer cell surface in cancer cells, both in vitro and in vivo — a direct surface-expression claim contradicting the canonical inner-leaflet-only model. This is the central finding of the paper and establishes extracellular membrane-associated Src (eSrc) as a bona fide cancer cell surface antigen. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Unspecified · cancer cell lines (in vitro and in vivo) · unspecified · non-permeabilized
  > "In this work, we found that Src is noncanonically translocated and inverted onto the cell surface in cancer, both in vitro and in vivo."
- `a1_evi_02` · *Primary* · Supports · Topology — The 2025/2026 study demonstrates that intracellular N-myristoylated proteins, prototypically Src, can undergo topological inversion onto the outer cell surface in cancer — meaning the canonical cytoplasmic/inner-leaflet topology is inverted in this cancer-specific context, placing the Src protein body on the extracellular face. This is a topology-inversion claim that qualifies the standard DeepTMHMM/UniProt topology (all cytoplasmic, no ECD) by identifying a cancer-specific exceptional pathway. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Unspecified · cancer cell lines · unspecified · non-permeabilized
  > "Thus, intracellular <i>N</i>-myristoylated proteins, prototypically Src, can be topologically inverted onto the cell surface in cancer and targeted with antibody therapeutics."
- `a1_evi_03` · *Primary* · Supports · Surface Expression — Autophagolysosomal exocytosis (ALE) was identified as the secretory mechanism by which Src reaches the outer cell surface in cancer cell lines. This represents a non-classical (non-ER/Golgi) trafficking route that bypasses the signal-peptide requirement; the ALE pathway is prominent in cancer and delivers Src to the extracellular membrane face. Relevant to risks.shed_form and surface trafficking context. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Unspecified · cancer cell lines · unspecified
  > "We identified autophagolysosomal exocytosis (ALE) as a secretory mechanism prominent in cancer cell lines."
- `a1_evi_04` · *Primary* · Supports · Surface Expression — Extracellular membrane-associated Src (eSrc) was detected in primary tumors, and anti-Src antibody-based therapies mediated tumor cell killing in cell culture systems and in mouse xenograft models. This constitutes direct therapeutic engagement evidence: antibody therapeutics targeting the extracellular face of Src on the cancer cell surface demonstrate in vitro and in vivo preclinical proof-of-concept. No sponsor or clinical stage is named in the abstract; described as antibody-based therapy in preclinical (xenograft) models. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Human · primary tumors and xenograft models · unspecified · non-permeabilized
  > "Furthermore, this extracellular membrane-associated Src (eSrc) was found in primary tumors, and anti-Src antibody-based therapies mediated tumor cell killing in cell culture systems and in mouse xenograft models."
- `a1_evi_05` · *Secondary* · Supports · Surface Expression — A companion paper (PMID:41818382) provides a brief title-level assertion that exocytosis exposes Src at the outer surface of cancer cells, poised for therapeutic targeting — a secondary review-level corroboration of the surface-exposure claim, reinforcing the eSrc concept from a second publication in the same cluster. (https://pubmed.ncbi.nlm.nih.gov/41818382/)
  - *assay*: Unspecified · cancer cells · unspecified · non-permeabilized
  > "Exocytosis exposes Src at the outer surface of cancer cells, poised for therapeutic targeting."
- `a1_evi_06` · *Secondary* · Refutes · Topology — SRC-family kinases are canonically tethered via acyl groups (myristoylation/palmitoylation) to the inner leaflet of the plasma membrane, with all functional domains (SH2, SH3, kinase) facing the cytoplasm. This is the standard topology, with no extracellular domain. Directly refutes surface accessibility under canonical conditions. ([PMC11399299](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11399299/))
  - *assay*: Unspecified
  > "These motifs are phosphorylated by SRC-family tyrosine kinases, which are tethered via acyl groups to the inner leaflet of the plasma membrane."
- `a1_evi_07` · *Secondary* · Ambiguous · Surface Expression — SRC kinase was identified in surfaceome cluster 2 from a mass-spectrometry-based cell-surface capture (CSC) study of embryonic chicken limb bud-derived chondrogenic cells. The method used sialoglycoprotein enrichment via aminooxy-biotin conjugation + LC-MS/MS. SRC appears among bona fide cell-surface regulators of chondrocyte biology. However, this is a non-human (chicken/chondrogenic) system, and SRC lacks a signal peptide or glycosylation site that would normally anchor it to the CSC enrichment; its detection may reflect co-purification or unconventional surface presentation. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
  - *assay*: Other · embryonic chicken limb bud-derived chondrogenic cells · live · non-permeabilized
  > "Surfaceome cluster 2 harbors several cell-surface regulators of chondrocyte biology, including RECK (a membrane-anchored matrix metalloprotease inhibitor [ 45 ]), FGFR2 (fibroblast growth factor receptor 2; regulates chondrocyte proliferation/differentiation signaling [ 46 ]), multiple ephrin receptors (EPHA7, EPHB2, EPHB1, EPHB3 with potential roles in cartilage morphogenesis [ 47 ]), SRC kinase (chondrocyte phenotype control [ 48 ]), and GPC1 (glypical-1"
- `a1_evi_08` · *Secondary* · Supports · Methodological — The surfaceome study used sialoglycoprotein enrichment via aminooxy-biotin conjugation combined with high-resolution LC-MS/MS on 3 biological replicates (n=3) across 5 time points of chondrogenic differentiation. Method family: cell-surface glycoprotein capture (CSC-type). Permeabilization: not required by the chemistry (surface glycoproteins targeted). This methods detail anchors the MethodObservation for the SRC surfaceome detection in chondrogenic cells. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
  - *assay*: Other · embryonic chicken limb bud-derived chondrogenic cells · live · non-permeabilized
  > "Temporal proteomic profiling was conducted at days 1, 3, 6, 10, and 15 of micromass culture corresponding to key histodifferentiation stages [ 17 , 18 ], combining sialoglycoprotein enrichment via aminooxy-biotin conjugation with high-resolution LC-MS/MS on 3 biological replicates ( n = 3)."
- `a1_evi_09` · *Secondary* · Ambiguous · Surface Expression — SRC was identified within a functional surfaceome cluster (alongside ERBB2, CSF1R, PRKCD) in a surfaceome proteomics study. This is a discussion-level mention placing SRC among 'well-known receptor/non-receptor signaling kinases' detected in a surfaceome dataset. The context is a surfaceome study, but SRC is cited as a non-receptor kinase in a signaling cluster — presence may reflect co-enrichment rather than direct surface glycoprotein capture. ([PMC9237123](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9237123/))
  - *assay*: Unspecified · unspecified
  > "The ephrin/plexin group was part of a larger functional cluster with roles in chemokine signaling and increased chemotaxis 34 , 35 that included not just well-known receptor/non-receptor signaling kinases (e.g., ERBB2, CSF1R, SRC, PRKCD), but also proteins with functionally diverse activities (i.e., proteins with roles in immune response, cell adhesion cell-ECM binding molecules, and transport)."
- `a1_evi_10` · *Primary* · Ambiguous · Surface Expression — SRC was detected among proteins enriched in secreted extracellular vesicles (sEVs) from high-invadopodia-activity cancer cell lines, alongside CTTN, CFL1, ITGA3, ITGB3 (invadopodia regulators) and MMP2, MMP14, BSG/CD147. This constitutes evidence for a shed/secreted form of SRC in sEVs (exosomal form), representing a non-canonical route of extracellular SRC presence distinct from plasma-membrane surface presentation. Relevant to risks.shed_form. ([PMC10356899](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10356899/))
  - *assay*: Human · high-invadopodia activity cancer cell lines · unspecified
  > "Furthermore, these high invadopodia activity cell lines secreted sEVs with a greater abundance of proteins involved in the regulation of invadopodia formation (CTTN, CFL1, SRC, ITGA3, ITGB3 – Cluster 2) and proteolytic activity (MMP2, MMP14, BSG/CD147 – Cluster 2) (Fig. 3 D)."
- `a1_evi_11` · *Secondary* · Ambiguous · Tissue Expression — Western blot analyses of total SRC protein and its phosphorylated form (Y416) were performed in HaCaT keratinocyte cells (whole-cell lysate, no membrane fractionation). This is a non-surface whole-cell WB detection of SRC — provides tissue/cell-line expression evidence without surface-accessibility information. Relevant to non_surface_expression list. ([PMC8852774](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8852774/))
  - *assay*: Human · HaCaT keratinocytes · unspecified · permeabilized
  > "n = 2, representative pictures. b qRT-PCR analyses of CYP1A1 and AKR1C3 in HaCaT-shAHR and HaCaT-EV cells treated with 10 μM PP2 or 0.1 % DMSO for 24 h. n = 4. *, p ≤ 0.05 compared to EV DMSO, #, p ≤ 0.05 compared to EV B[a]P. c qRT-PCR analyses of CYP1A1 and AKR1C3 in HaCaT-shAHR and HaCaT-EV keratinocytes treated as indicated for 24 h. n = 4–7. *, p ≤ 0.05 compared to EV DMSO, #, p ≤ 0.05 compared to EV B[a]P. d NHEKs were treated with 20 ng/ml AREG for 24 h and AKR1C3 transcript level were analyzed by qRT-PCR. e Western blot analyses of SRC and its phosphorylated form (Y416)."
- `a1_evi_12` · *Secondary* · Supports · Methodological — Anti-SRC antibody identifiers used in a surface biotinylation / WB study: mouse monoclonal anti-SRC (clone 60315-1-lg, Proteintech, catalog 60315-1-lg) and rabbit anti-phospho Y416-SRC (clone D49G4, Cell Signaling Technology, catalog #6943). These antibody identifiers enable downstream AntibodyRef population for MethodObservation. ([PMC9659096](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9659096/))
  - *assay*: Unspecified
  > "mouse monoclonal anti-PCNA (NA03, Merck, Darmstadt, Germany); rabbit anti-GLUT1 (ab652; Abcam, Cambridge, UK); goat anti-GLUT1 (sc-1603; Santa Cruz Biotechnology, Santa Cruz, CA, USA); mouse monoclonal anti-RAC1 (05-389, Millipore, Burlington, MA, USA); mouse monoclonal anti-SRC antibody (60315-1-lg, Proteintech, Rosemont, IL, USA); rabbit anti-phospho Y416-SRC antibody D49G4 (#6943, Cell Signaling, Danvers, MA, USA); mouse monoclonal anti-VAV2 antibody (sc-271442, Santa Cruz Biotechnology, Santa Cruz, CA, USA)"
- `a1_evi_13` · *Secondary* · Ambiguous · Tissue Expression — Fluid shear stress increased c-Src activation (Tyr416 phosphorylation) and promoted redistribution of RANKL toward the cell periphery, with an increase of RANKL in the membrane fraction by subcellular fractionation in MC3T3-E1 osteoblast-like cells. This evidences c-Src's role in promoting membrane trafficking of RANKL — c-Src itself remains cytoplasmic/inner-leaflet but acts as a regulator of surface trafficking. No direct surface localization of Src is claimed. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
  - *assay*: Mouse · MC3T3-E1 osteoblast-like cells · unspecified
  > "Fluid shear stress increased c-Src activation (Tyr416 phosphorylation) and promoted redistribution of RANKL toward the cell periphery, accompanied by an increase of RANKL in the membrane fraction."
- `a1_evi_14` · *Secondary* · Refutes · Topology — Co-expression experiments showed spatial association of RANKL with c-Src at the cell periphery after shear stimulation in MC3T3-E1 cells. c-Src co-localizes with RANKL at the cell periphery — consistent with c-Src's known inner-leaflet plasma membrane association — but does not establish extracellular accessibility of Src itself. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
  - *assay*: Mouse · MC3T3-E1 osteoblast-like cells · unspecified
  > "Co-expression experiments showed spatial association of RANKL with c-Src at the cell periphery after shear stimulation."
- `a2_evi_01` · *Primary* · Supports · Surface Expression — Src is noncanonically translocated and topologically inverted onto the outer cell surface in cancer, both in cell culture (in vitro) and in primary tumors (in vivo). This represents a disease-state-induced surface exposure of an otherwise cytoplasmic inner-leaflet protein. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Human · cancer cell lines and primary tumor tissue · unspecified · non-permeabilized
  > "In this work, we found that Src is noncanonically translocated and inverted onto the cell surface in cancer, both in vitro and in vivo."
- `a2_evi_02` · *Primary* · Supports · Surface Expression — Autophagolysosomal exocytosis (ALE) is identified as the secretory mechanism by which Src is translocated to the outer cell surface in cancer cells. This cell-state-induced mechanism (ALE pathway activation) drives Src surface exposure in cancer. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Human · cancer cell lines · unspecified · non-permeabilized
  > "We identified autophagolysosomal exocytosis (ALE) as a secretory mechanism prominent in cancer cell lines."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — Extracellular membrane-associated Src (eSrc) is found in primary tumors but not (implicitly) in normal tissue. This establishes cancer-restricted anatomical accessibility of Src at the outer cell surface, and demonstrates that anti-Src antibody-based therapies can mediate tumor cell killing. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Human · primary tumor tissue; mouse xenograft models · unspecified · non-permeabilized
  > "Furthermore, this extracellular membrane-associated Src (eSrc) was found in primary tumors, and anti-Src antibody-based therapies mediated tumor cell killing in cell culture systems and in mouse xenograft models."
- `a2_evi_04` · *Primary* · Supports · Surface Expression — Intracellular N-myristoylated proteins, with Src as the prototype, can be topologically inverted onto the outer cell surface in cancer. This positions normally cytoplasmic Src as an accessible extracellular surface antigen specifically in cancer cells, enabling antibody-based therapeutic targeting. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Human · cancer cells · unspecified · non-permeabilized
  > "Thus, intracellular <i>N</i>-myristoylated proteins, prototypically Src, can be topologically inverted onto the cell surface in cancer and targeted with antibody therapeutics."
- `a2_evi_05` · *Primary* · Supports · Surface Expression — Exocytosis exposes Src at the outer surface of cancer cells, positioning it for therapeutic targeting. This is a cancer-cell-state-dependent surface accessibility event driven by exocytosis, distinct from normal cell biology where Src resides on the cytoplasmic inner leaflet. (https://pubmed.ncbi.nlm.nih.gov/41818382/)
  - *assay*: Human · cancer cells · unspecified · non-permeabilized
  > "Exocytosis exposes Src at the outer surface of cancer cells, poised for therapeutic targeting."
- `a2_evi_06` · *Secondary* · Refutes · Surface Expression — SRC-family kinases, including SRC itself, are tethered via acyl groups (myristoylation/palmitoylation) to the inner leaflet of the plasma membrane. All functional domains face the cytoplasm; there is no extracellular domain. This places Src at the cytoplasmic face of the plasma membrane in normal (non-cancer) cells. ([PMC11399299](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11399299/))
  - *assay*: Unspecified · T cells (context of discussion)
  > "These motifs are phosphorylated by SRC-family tyrosine kinases, which are tethered via acyl groups to the inner leaflet of the plasma membrane."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — In osteoblast-like MC3T3-E1 cells, fluid shear stress increases c-Src activation (Tyr416 phosphorylation) and promotes redistribution of RANKL toward the cell periphery and into the membrane fraction. This demonstrates a mechanical-stress-induced state change in osteoblast-like cells modulating Src activity. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
  - *assay*: Mouse · MC3T3-E1 osteoblast-like cells · unspecified
  > "Fluid shear stress increased c-Src activation (Tyr416 phosphorylation) and promoted redistribution of RANKL toward the cell periphery, accompanied by an increase of RANKL in the membrane fraction."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — Constitutively active c-Src (Y527F mutant) enhances peripheral/membrane localization of RANKL in osteoblast-like cells even in the absence of shear stress, demonstrating that Src activity state directly modulates membrane-proximal protein distribution in osteoblasts. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
  - *assay*: Mouse · MC3T3-E1 osteoblast-like cells · unspecified
  > "Moreover, constitutively active c-Src (Y527F) enhanced peripheral localization of RANKL even in the absence of shear stress."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — SRC is a key component of the SRC/RAC1/PAK1/PIP5K/EZRIN pathway that regulates NIS actin-cytoskeleton anchoring and retention at the plasma membrane in thyroid cells. SRC acts as an upstream regulator of PM surface retention for a transmembrane symporter, demonstrating SRC's role in modulating surface protein accessibility in thyroid epithelial cells. ([PMC9659096](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9659096/))
  - *assay*: Human · thyroid epithelial cells · unspecified
  > "Biochemical and functional analysis allowed us to establish the SRC/RAC1/PAK1/PIP5K/EZRIN pathway as a key regulator of NIS actin-cytoskeleton anchoring and retention at the PM [ 10 ]."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — SRC protein and its activated phospho-form (pSRC Y419) are expressed in nasopharyngeal carcinoma (NPC) cells (HK11.19 line), as shown by western blot. THY1 expression modulates SRC activation state in NPC cells — THY1 knockdown alters pSRC/SRC ratio, indicating cell-state-dependent SRC activity in NPC. ([PMC10093038](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10093038/))
  - *assay*: Human · HK11.19 nasopharyngeal carcinoma NPC cells · fixed · permeabilized
  > "Western blot analysis of pSRC (Y419), total SRC, and THY1 in ( A ) THY1-expressing NPC cells and ( B ) THY1-knockdown HK11.19 cells were shown."
- `a2_evi_11` · *Primary* · Ambiguous · Tissue Expression — SRC kinase is identified as a cell-surface regulator of chondrocyte biology involved in chondrocyte phenotype control, appearing in surfaceome cluster 2 of chondrogenic cells. This places SRC in the surfaceome context of cartilage/chondrocytes, though as an inner-leaflet kinase its surface exposure mechanism requires clarification. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
  - *assay*: Other · embryonic chondrogenic cells (chicken limb bud-derived) · live · non-permeabilized
  > "Surfaceome cluster 2 harbors several cell-surface regulators of chondrocyte biology, including RECK (a membrane-anchored matrix metalloprotease inhibitor [ 45 ]), FGFR2 (fibroblast growth factor receptor 2; regulates chondrocyte proliferation/differentiation signaling [ 46 ]), multiple ephrin receptors (EPHA7, EPHB2, EPHB1, EPHB3 with potential roles in cartilage morphogenesis [ 47 ]), SRC kinase (chondrocyte phenotype control [ 48 ]), and GPC1 (glypical-1"
- `a2_evi_12` · *Primary* · Supports · Tissue Expression — SRC protein is found in small extracellular vesicles (sEVs) secreted by glioblastoma (GBM) cell lines with high invadopodia activity (specifically in Cluster 2 of sEV proteome). This implicates SRC in the extracellular/secreted compartment of aggressive GBM cells. ([PMC10356899](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10356899/))
  - *assay*: Human · glioblastoma (GBM) cell lines with high invadopodia activity · unspecified · non-permeabilized
  > "Furthermore, these high invadopodia activity cell lines secreted sEVs with a greater abundance of proteins involved in the regulation of invadopodia formation (CTTN, CFL1, SRC, ITGA3, ITGB3 – Cluster 2) and proteolytic activity (MMP2, MMP14, BSG/CD147 – Cluster 2) (Fig. 3 D)."
- `a2_evi_13` · *Primary* · Supports · Tissue Expression — SRC is identified as a non-receptor signaling kinase within a disease-context functional cluster in the cancer surfaceome, co-clustering with receptor tyrosine kinases (ERBB2, CSF1R) in a chemokine signaling/chemotaxis network. This places SRC as part of an altered proteome in cancer with surfaceome-association context. ([PMC9237123](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9237123/))
  - *assay*: Human · cancer cell lines (surfaceome proteomics) · unspecified · non-permeabilized
  > "The ephrin/plexin group was part of a larger functional cluster with roles in chemokine signaling and increased chemotaxis 34 , 35 that included not just well-known receptor/non-receptor signaling kinases (e.g., ERBB2, CSF1R, SRC, PRKCD), but also proteins with functionally diverse activities (i.e., proteins with roles in immune response, cell adhesion cell-ECM binding molecules, and transport)."

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

### Experimental-structure sequence

**8JN8** chain A · X-ray diffraction, 1.902 Å · covers UniProt residues 1–536 (536 aa) · representative of 112 experimental structures. Residues sliced from the canonical sequence over the structure's SIFTS-mapped span; unresolved loops in the deposited coordinates are not removed here.

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

**Mouse ortholog — Src** (`P05480`, projected onto human canonical)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Cynomolgus ortholog — SRC** (`A0A7N9CC30`, projected onto human canonical)

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
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Experimental — 8JN8 chain A** (UniProt residues 1–536, projected from canonical)

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

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — Confidence is moderate because the cancer-cell outer-surface SRC story derives from a single recent research cluster — two 2025 papers (PMID:41818370 and PMID:41818382) that appear to originate from the same group. The canonical SRC topology — myristoylated, inner-leaflet, no extracellular domain — is established across decades of independent work (e.g., PMC:PMC11399299). The triage first-pass classified SRC as inner-leaflet-anchored with high confidence, a reasonable call given established biology. Lifting confidence to high would require an independent group to confirm cancer-state outer-leaflet eSrc exposure using orthogonal methodology (e.g., non-permeabilized flow cytometry, surface biotinylation mass spec, or cryo-EM structural evidence of the inverted topology) beyond the antibody-killing xenograft assays reported in PMID:41818370.*
