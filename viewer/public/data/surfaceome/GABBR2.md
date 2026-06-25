# GABBR2 — Surface Accessibility Brief

*Schema v2.13.0 · generated 2026-06-24T17:24:22.493916Z · model `claude-sonnet-4-6`*

> GABBR2 is constitutively surface-accessible as a pan-CNS class-C GPCR subunit forming an obligate heterodimer with GABBR1. Direct multi-method support: surface biotinylation of endogenous protein in rat cortical neurons quantifying ~50% of total GABBR2 at the plasma membrane (a1_evi_07), live-cell flow cytometry on hippocampal neurons confirming WT surface expression (a1_evi_14), and a CRISPR-KO genome-scale intact-cell mAb screen identifying GABBR2 at the human cell surface with KO-confirmed specificity (a1_evi_22, a1_evi_23). Surface levels are moderately state-modulated: upregulated in cAMP-stimulated pancreatic islets (a2_evi_25) and in melanoma (a2_evi_29), and downregulated in Alzheimer's disease cortex and epileptic hippocampus (a2_evi_06, a2_evi_07). Moderate epitope masking at the GABBR1/GABBR2 heterodimer interface is the principal binder-engineering caveat (a1_evi_04, a1_evi_20); synaptic subdomain restriction limits systemic antibody access in the CNS. No shed or secreted form is documented, ruling out decoy concerns.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:4507](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:4507) |
| UniProt | [O75899](https://www.uniprot.org/uniprotkb/O75899) |
| NCBI Gene | [9568](https://www.ncbi.nlm.nih.gov/gene/9568) |
| Ensembl | [ENSG00000136928](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000136928) |
| Subcategory | GPCR |
| Surface accessibility | High |
| Confidence | High |
| Evidence grade | Direct, multi-method |
| Triage signal | Likely accessible |
| Headline risks | Co Receptor, Epitope Masked |

## 1. Executive summary

**Constitutively surface-accessible at pre- and postsynaptic membranes throughout the CNS, and in peripheral tissues including airway smooth muscle, vascular smooth muscle, pancreatic islets, and melanoma cells; surface levels are moderately state-modulated by cAMP signaling, oncogenic transformation, and neurological disease states.**

GABBR2 is constitutively surface-accessible as a pan-CNS class-C GPCR subunit forming an obligate heterodimer with GABBR1. Direct multi-method support: surface biotinylation of endogenous protein in rat cortical neurons quantifying ~50% of total GABBR2 at the plasma membrane (a1_evi_07), live-cell flow cytometry on hippocampal neurons confirming WT surface expression (a1_evi_14), and a CRISPR-KO genome-scale intact-cell mAb screen identifying GABBR2 at the human cell surface with KO-confirmed specificity (a1_evi_22, a1_evi_23). Surface levels are moderately state-modulated: upregulated in cAMP-stimulated pancreatic islets (a2_evi_25) and in melanoma (a2_evi_29), and downregulated in Alzheimer's disease cortex and epileptic hippocampus (a2_evi_06, a2_evi_07). Moderate epitope masking at the GABBR1/GABBR2 heterodimer interface is the principal binder-engineering caveat (a1_evi_04, a1_evi_20); synaptic subdomain restriction limits systemic antibody access in the CNS. No shed or secreted form is documented, ruling out decoy concerns.

**Family / classification** — UniProt family: G protein-coupled receptor 3 family. GABA-B receptor subfamily · HGNC gene group(s): Gamma-aminobutyric acid type B receptor subunits · functional class: Receptor.

**Triage first-pass reasoning** — GABBR2 encodes the GABA-B receptor subunit 2 (GB2), a multi-pass transmembrane protein belonging to the class C GPCR (GPRC3) family. It contains seven transmembrane helices with extracellular loops accessible from the outer leaflet of the plasma membrane. GB2 forms an obligate heterodimer with GABBR1 (GB1); GB1 carries the ligand-binding Venus flytrap domain, while GB2 couples to G-proteins. The heterodimer is co-trafficked to the neuronal plasma membrane surface, where GB2's extracellular domains and loops are genuinely exposed. Surface expression is well-documented by electrophysiology, surface biotinylation, and immunostaining of non-permeabilized cells. As a GPCR, its extracellular loops are accessible to large and small molecule binders from the extracellular face. This is stable, constitutive surface expression under normal neuronal conditions.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=High · subcategory=GPCR · ecd=Large |
| Classification | reason=Classical Surface Receptor · family=Receptor · state-dependence=Moderate · induction-trigger=Oncogenic |
| Expression | level=High · breadth=Broad · specificity=Mixed · low-endogenous=false · tumor-associated=true · orphan-receptor=false · OE-precedent=true |
| Risks | shed=false · secreted=false · co-receptor=Required · masking=true · restricted-subdomain=true |
| Evidence | grade=Direct, multi-method · density=High · live-cell-surface=true · supporting(hi)=4 · contradicting(hi)=0 |
| Cross-species | mouse=97.6% · cyno=99.8% |
| Paralogs | max %ECD identity = 35.3% |
| Topology | TM=7 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: High expression across multiple CNS regions (cortex, hippocampus, thalamus, amygdala, cerebellum) by Northern blot and in situ hybridization (a2_evi_01), with surface biotinylation quantifying ~50% of total GABBR2 at the plasma membrane in cortical neurons (a1_evi_07).
- *Expression breadth*: Predominantly CNS-expressed (a2_evi_01, a2_evi_02) but also detected in airway smooth muscle (a2_evi_20), vascular smooth muscle (a2_evi_22), pancreatic islets (a2_evi_24), brain microvasculature (a2_evi_23), and melanoma (a2_evi_29); broad but not pan-tissue.
- *Surface specificity*: Surface biotinylation shows ~50% of GABBR2 at the plasma membrane and ~50% intracellular in neurons (a1_evi_07, a1_evi_09); constitutive internalization cycle and ER/endosomal pools documented (a2_evi_18, a2_evi_19), placing GABBR2 in a mixed surface/intracellular distribution.
- *Known ligand*: GABA is the validated endogenous agonist for the GABBR1/GABBR2 heterodimer; baclofen (GABA analog) activates the receptor with documented Gi coupling (a2_evi_21, a2_evi_25). GABBR1 carries the orthosteric binding site (a1_evi_03).
- *Low endogenous expression*: High expression across multiple CNS regions (cortex, hippocampus, thalamus, amygdala, cerebellum) by Northern blot and in situ hybridization (a2_evi_01), with surface biotinylation quantifying ~50% of total GABBR2 at the plasma membrane in cortical neurons (a1_evi_07).
- *Overexpression surface localization*: 4 method observation(s) pair an overexpression/mixed expression system with a surface-localization readout (cites a1_evi_10, a1_evi_15, a1_evi_16, a1_evi_20, a1_evi_21).

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Direct, multi-method

Multiple independent direct-surface method types support GABBR2 plasma membrane accessibility. (1) Surface biotinylation on endogenous GABBR2 in rat primary cortical neurons (15–20 DIV, live, non-permeabilized) quantified 49.6% of total GABBR2 protein at the PM under resting conditions (a1_evi_07), with the assay methodology described across a1_evi_06 and a1_evi_09 from a single source (PMC3945329). (2) Live-cell flow cytometry and confocal imaging on rat hippocampal neurons and HEK293T cells, using Flag-tagged GABBR2, demonstrated WT surface expression with variant-reduced surface signal as the comparator (a1_evi_14, a1_evi_15). (3) A CRISPR-KO genome-scale screen using mAb staining of intact (non-permeabilized) human cells identified GABBR2 at the cell surface, with KO-confirmed loss-of-signal validating specificity (a1_evi_22, a1_evi_23). (4) Non-permeabilized anti-Myc surface IF on HEK293T cells co-expressing Myc-GB2+GB1 confirmed surface localization (a1_evi_11, a1_evi_13), though with an exogenous SP. Cryo-EM topology (a1_evi_04, a1_evi_05) and crystal structure data (a1_evi_20, a1_evi_21) corroborate extracellular domain exposure. Three distinct direct method classes (surface biotinylation, live-cell flow cytometry, CRISPR-KO surface FACS) across multiple sources support direct_multi_method. Note: biotinylation and flow rows are rat-anchored; the CRISPR-KO FACS screen is human-anchored, satisfying the human-species requirement.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Moderate | Review-level topology description (7TM, N-term extracellular); confirms canonical architecture but not a direct surface assay. |
| a1_evi_02 | Tangential | Moderate | Review-level topology (VFTD + 7TM + C-term intracellular); contextualizes surface accessibility but not a direct assay. |
| a1_evi_03 | Tangential | Moderate | Review-level functional domain architecture; supports extracellular exposure of VFTD but not a direct surface assay. |
| a1_evi_04 | Tangential | High | Cryo-EM confirms 7TM topology with extracellular domains; structural evidence for topology, not a live-cell surface assay. |
| a1_evi_05 | Tangential | High | Cryo-EM confirms ECL2 surface-accessible; structural topology evidence, not a live-cell surface assay. |
| a1_evi_06 | Supports Surface | Moderate | Surface biotinylation on rat primary cortical neurons (15-20 DIV), endogenous GABBR2; single source, no KO control cited. |
| a1_evi_07 | Supports Surface | Moderate | Surface biotinylation quantifies 49.6% of endogenous GABBR2 at PM in rat cortical neurons; robust constitutive surface pool. |
| a1_evi_08 | Tangential | Low | Antibody reagent description for surface biotinylation study; methodological detail, not an independent surface claim. |
| a1_evi_09 | Supports Surface | Moderate | Surface biotinylation shows GABBR2 has proportionally more PM-resident protein than GABBR1 in rat cortical neurons. |
| a1_evi_10 | Tangential | Low | Methodological description of OE construct with exogenous SP; not an independent surface result. |
| a1_evi_11 | Supports Surface | Moderate | Non-permeabilized anti-Myc staining on live HEK293T cells co-expressing Myc-GB2+GB1; exogenous SP limits to secondary tier. |
| a1_evi_12 | Tangential | Low | Antibody reagent list for surface IF assay; methodological detail. |
| a1_evi_13 | Supports Surface | Moderate | Nonperm anti-Myc surface IF on HEK293T cells co-expressing GB2+GB1; exogenous SP, single source. |
| a1_evi_14 | Supports Surface | Moderate | Flow cytometry on rat hippocampal neurons and HEK293T; WT surface expression inferred from variant-reduced surface signal. |
| a1_evi_15 | Supports Surface | Moderate | Flow cytometry + confocal imaging surface assay methodology for GABBR2 variant characterization; Flag-tagged OE construct. |
| a1_evi_16 | Supports Surface | Moderate | SNAP-tag Lumi4-Tb surface fluorescence on transfected cells; exogenous HA SP, unspecified cell line, single source. |
| a1_evi_17 | Expression Only | Low | IHC of rat brainstem (PPT/LDT) sections, permeabilized; confirms expression but not surface accessibility. |
| a1_evi_18 | Tangential | Low | Antibody selection note for IHC; methodological detail. |
| a1_evi_19 | Expression Only | Low | RT-PCR, WB, IF, IHC in human aortic smooth muscle cells and LAD artery; permeabilization status unspecified, non-surface methods. |
| a1_evi_20 | Supports Surface | High | Crystal structure of human GABBR1/GABBR2 coiled-coil; GABBR2 masks ER retention signal enabling surface trafficking of both subunits. |
| a1_evi_21 | Supports Surface | High | Mutation of coiled-coil interface impairs GABBR1 surface expression; confirms GABBR2 coiled-coil is required for heterodimer surface delivery. |
| a1_evi_22 | Supports Surface | High | CRISPR-KO genome-scale screen with mAb staining of intact cells identifies GABBR2 surface-accessible; human cell line, live-cell FACS. |
| a1_evi_23 | Supports Surface | High | CRISPR-KO FACS methodology validates surface detection approach; loss-of-surface-signal upon KO confirms specificity. |
| a1_evi_24 | Supports Surface | Moderate | Review assertion: GABBR2 required for GABBR1 surface expression and heterodimer surface stability; corroborated by primary sources. |
| a1_evi_25 | Tangential | Moderate | GABBR2 variant p.Gly673Asp fails to reach surface; confirms WT surface expression is required for function, not a contradiction. |
| a1_evi_26 | Tangential | Moderate | Variant characterization showing reduced surface expression as LoF mechanism; confirms surface expression is a regulated parameter for WT. |
| a1_evi_27 | Expression Only | Low | Western blot of rat hippocampal DG slices (whole lysate); no surface fractionation. |
| a1_evi_28 | Tangential | Low | Antibody reagent description for WB; methodological detail. |

### Flow cytometry (2 methods)

#### Live Cell Flow — Supports Surface Localization · Surface Accessible

*Permeabilization: Live Cell · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Flag-tagged GABBR2 (WT) co-expressed with GABBR1 in HEK-293T cells; WT shows robust surface expression by flow cytometry; TM6 variants G693W, S695I, I705N reduce surface expression | Established Cell Line | High | 2 |

*Overexpression construct* — SP source: Unspecified · tag: C-terminal Flag · cell line: HEK-293T. *(cites: a1_evi_15)*

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Endogenous GABBR2 surface expression in rat hippocampal neurons; TM6 variants G693W, S695I, I705N reduce neuronal cell surface expression relative to WT | Primary Human Cell | High | 1 |

### Immunofluorescence (3 methods)

#### Nonpermeabilized IF — Supports Surface Localization · Surface Accessible

*Permeabilization: Nonpermeabilized · expression: Overexpression*

**Antibodies**

- anti-Myc (9E10 · Santa Cruz Biotechnology · sc-40 · AB_627268) — Extracellular epitope; Monoclonal; None validation (None); Detects Myc epitope tag (EQKLISEEDL) placed at N-terminus of GB2; extracellular when tag is on the extracellular N-terminal domain

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Myc-GB2 (mGluR5 SP, exogenous) co-expressed with GB1 in HEK293T cells; anti-Myc staining on live non-permeabilized cells reports surface fraction of GB2 WT and variants (S695I, A567T, I705N) | Established Cell Line | Moderate | 1 |

*Overexpression construct* — SP source: Exogenous · mGluR5 signal peptide · tag: N-terminal Myc · cell line: HEK293T. *(cites: a1_evi_10)*

#### Permeabilized IF — Expression Only · Plasma Membrane Localized

*Permeabilization: Permeabilized · expression: Overexpression*

**Antibodies**

- anti-GB2 (Synaptic Systems · 322205 · AB_2620061) — Unknown epitope; Polyclonal; None validation (None)
- anti-GB1 (2D7 · Abcam · ab55051 · AB_941703) — Unknown epitope; Monoclonal; None validation (None); Detects GABBR1, not GABBR2; used to confirm co-expression of GB1 partner subunit

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Post-permeabilization anti-GB2 staining of HEK293T cells co-expressing Myc-GB2 and GB1; reports total GB2 expression level used as denominator for surface/total ratio | Established Cell Line | Moderate | 1 |

*Overexpression construct* — SP source: Exogenous · mGluR5 signal peptide · tag: N-terminal Myc · cell line: HEK293T. *(cites: a1_evi_10)*

#### Permeabilized IF — Expression Only · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GABBR2 expression in human aortic smooth muscle cells (HASMCs) assessed by immunofluorescence; permeabilization condition not stated | Primary Human Cell | Moderate | 1 |

### Immunohistochemistry (2 methods)

#### IHC — Expression Only · Unclear

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-GABBR2 — Unknown epitope; Unknown; Moderate validation (Orthogonal Method); Selected over anti-GABBR1 antibody based on more robust labeling in initial trials; no KO validation reported

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GABBR2-immunoreactivity observed in a large number of cells and surrounding neuropil of rat brainstem PPT and LDT nuclei | Ex Vivo | High | 1 |

#### IHC — Expression Only · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GABBR2 localized by IHC in human left anterior descending (LAD) coronary artery sections | Primary Human Tissue | Moderate | 1 |

### Surface biotinylation (1 method)

#### Surface Biotinylation — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-GABBR2 (Chemicon International) — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Endogenous GABBR2 in rat cultured cortical neurons (15–20 DIV); 49.6% ± 1.19 of total GABBR2 protein is surface-expressed under resting conditions | Primary Human Cell | High | 1 |
| Endogenous GABBR2 in rat cortical neurons has proportionally more surface-resident protein than GABBR1 at steady state, indicating distinct trafficking pathways | Primary Human Cell | High | 1 |

### Functional surface assay (1 method)

#### Functional Surface Assay — Supports Surface Localization · Surface Accessible

*Permeabilization: Live Cell · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| SNAP-GB2 (influenza HA SP, exogenous) transfected alone or co-transfected with Halo-GB1; cell surface expression measured by Lumi4-Tb fluorescence emission on intact transfected cells; co-transfection with GB1 increases surface expression | Established Cell Line | Moderate | 1 |

*Overexpression construct* — SP source: Exogenous · influenza HA signal sequence · tag: SNAP-tag. *(cites: a1_evi_16)*

### Other (2 methods)

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-GABBR2 (N-terminus) (Santa Cruz Biotechnology) — Extracellular epitope; Unknown; None validation (None); N-terminus epitope antibody; GABBR2 N-terminus is extracellular

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GABBR2 subunit protein levels measured by western blot in rat hippocampal dentate gyrus slices; no surface fractionation; levels increase 10–90 days after TMT treatment | Ex Vivo | Moderate | 1 |

#### Other — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Unknown · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Crystal structure of intracellular coiled-coil heterodimer of human GABBR1/GABBR2; GABBR1–GABBR2 association masks ER retention signal in GABBR1 cytoplasmic region, facilitating surface expression of both subunits; disruption of coiled-coil interface impairs GABBR1 surface expression | Unknown | Moderate | 2 |

*Overexpression construct* — SP source: Native · endogenous signal peptide (full-length human GABBR1/GABBR2). *(cites: a1_evi_20, a1_evi_21)*

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Rat brainstem (PPT/LDT nuclei) neurons, permeabilized IHC sections | Ex Vivo | IHC Protein | Moderate | 2 |
| Human aortic smooth muscle cells (HASMCs) and human left anterior descending artery (LAD); RT-PCR, WB, IF, IHC — permeabilization status unspecified | Primary Human Cell | IHC Protein | Moderate | 1 |
| Rat hippocampal dentate gyrus slices, whole-lysate western blot | Ex Vivo | Bulk Protein | Moderate | 2 |

**Contradicting evidence**

- *Isoform Conflict* (severity Low): Certain GABBR2 variants (e.g., p.Gly673Asp in TMD3) fail to reach the cell surface, rendering the receptor completely inactive, and reduced surface expression is identified as one of three distinct loss-of-function mechanisms across multiple GABBR2 variants. This demonstrates that surface expression of GABBR2 is a variant-sensitive, regulatable parameter — some forms of the protein are retained intracellularly rather than trafficked to the plasma membrane.
  - Likely explanation: These findings concern pathogenic missense variants, not wild-type GABBR2. The wild-type receptor is well-established at the cell surface; the contradictory evidence reflects variant-specific trafficking defects (e.g., misfolding leading to ER retention) rather than any intrinsic absence of surface expression for the canonical protein. This is therefore an isoform/variant-level conflict, not a challenge to wild-type surface accessibility.

## 4. Biological context

**Biological-context grade** · Rich

All four A2 axes are well-populated: expression mapped across ≥8 tissues/cell types (CNS regions, brainstem nuclei, airway/vascular smooth muscle, pancreatic islets, brain endothelium, melanoma) from multiple independent primary sources; subcellular localization pinned to plasma membrane (pre- and postsynaptic, homodimer/heterodimer trafficking); anatomical accessibility established across CNS and peripheral tissues; modulation documented under stress, ethanol, cAMP, disease variants, and injury states. Picture is internally coherent—state-dependent variation is biologically plausible, not contradictory. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_07, a2_evi_08, +21)*

**Expression × cell type × disease context**

| Tissue | Cell type | Disease context | Level (protein) | Cell states |
|---|---|---|---|---|
| cortex | — | Normal | High | — |
| thalamus | — | Normal | High | — |
| hippocampus | — | Normal | High | — |
| amygdala | — | Normal | High | — |
| cerebellum | — | Normal | High | — |
| spinal cord | — | Normal | High | — |
| peripheral tissues | — | Normal | Absent | — |
| central nervous system | — | Normal | High | — |
| brainstem (PPN, LDT) | — | Normal | Moderate | — |
| brainstem (PPN, LDT) | cholinergic neurons | Normal | High | — |
| brainstem (PPN, LDT) | glutamatergic and GABAergic neurons | Normal | Moderate | — |
| middle temporal gyrus | — | Other Disease (Alzheimer's disease) | Low | — |
| hippocampus | — | Other Disease (temporal lobe epilepsy with Ammon's horn sclerosis) | Low | — |
| hippocampus | — | Other Disease (temporal lobe epilepsy) | Mixed | — |
| hippocampal dentate gyrus | — | Other Disease (trimethyltin neurotoxic injury) | High | — |
| hippocampal dentate gyrus | astrocytes (GFAP+) | Other Disease (trimethyltin neurotoxic injury) | Moderate | stress-induced |
| brain | neurons | Normal | High | — |
| airway smooth muscle | — | Normal | Moderate | — |
| aorta | vascular smooth muscle cells | Normal | Moderate | — |
| coronary artery | vascular smooth muscle cells | Normal | Moderate | — |
| brain microvasculature | endothelial cells | Normal | Moderate | — |
| pancreatic islet | beta cells | Normal | Moderate | — |
| pancreatic islet | beta cells | Normal | High | cAMP-stimulated |
| ventral tegmental area (VTA) | dopaminergic neurons | Normal | Moderate | acute restraint stress |
| skin | melanoma cells | Tumor (melanoma) | Moderate | — |

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- ER · GABBR1 homodimer context or disease variants *(cites: a2_evi_13, a2_evi_17, a2_evi_15)*
- Endosome · constitutive internalization cycle *(cites: a2_evi_18, a2_evi_19, a2_evi_28)*

**Membrane subdomains**: Other

**Anatomical accessibility**

- brain synapses (pre- and postsynaptic membranes) — Synaptic · *Context Dependent*: Ultrastructural analysis directly localizes GABBR2-containing receptors to presynaptic membranes in brain neurons (a2_evi_12); review confirms pre- and postsynaptic localization throughout the brain (a2_evi_11). Synaptic cleft orientation is behind the BBB, making systemic binder access context-dependent.

**Accessibility modulation**

- *Disease State Induced*: wild-type hippocampal neurons (rat) → hippocampal neurons expressing pathogenic GABBR2 variants G693W, S695I, or I705N (TM6 mutations) — Three pathogenic TM6 point mutations (G693W, S695I, I705N) impair neuronal cell surface expression of GABBR2-containing receptors, reducing surface levels and signalling efficacy. *(→ Reduced Surface Expression Of GABBR2 In Neurons Carrying These Variants Means Fewer Receptors Are Accessible To Extracellular Binders; Disease-Associated Variants Substantially Restrict Target Accessibility At The Neuronal Surface.)* *(cites: a2_evi_15)*
- *Disease State Induced*: wild-type GABBR2 expressed in HEK293T cells → HEK293T cells expressing GABBR2 variants A567T or I705N — GABBR2 variants A567T and I705N show slightly but significantly increased cell surface expression compared to wild-type GB2 in HEK293T cells; S695I surface expression is similar to wild-type. *(→ Certain Disease-Associated Variants (A567T, I705N) Modestly Increase Surface-Accessible GABBR2 In A Heterologous System, Potentially Enhancing Extracellular Binder Access, Though The Physiological Relevance In Neurons May Differ.)* *(cites: a2_evi_16)*
- *Disease State Induced*: wild-type GABBR2 in transfected cells → transfected cells expressing GABBR2 variant p.Gly673Asp (TMD3) — GABBR2 variant p.Gly673Asp renders the receptor completely inactive and causes intracellular retention, failing to reach the cell surface. *(→ Complete Loss Of Surface Expression For This Variant Means No Extracellular Binder Access; The Receptor Is Entirely Sequestered Intracellularly, Eliminating Surface Target Availability.)* *(cites: a2_evi_17)*
- *Dual Localization*: null → null — GABBR2 homodimers and GABBR1/GABBR2 heterodimers are present at the plasma membrane, while GABBR1 homodimers are retained in the ER/ERGIC. GABBR2 can reach the cell surface both as a homodimer and as part of the canonical heterodimer. *(→ GABBR2 Itself Is Surface-Accessible In Multiple Dimer Configurations; The ER-Retained Pool (GABBR1 Homodimers) Is Not Accessible. Surface GABBR2 Is Available For Extracellular Binders Regardless Of GABBR1 Pairing Status.)* *(cites: a2_evi_13)*
- *Cell State Induced* · trigger: Other: wild-type presynaptic neurons (mouse) → Ajap1-/- or Ajap1W183C/+ mice lacking functional AJAP1 — Ultrastructural analysis reveals significantly decreased presynaptic GABBR2-containing GBR levels at synapses in AJAP1 loss-of-function mice; AJAP1 trans-synaptically recruits GBRs to presynaptic sites. *(→ Loss Of AJAP1 Reduces Presynaptic Surface GABBR2, Diminishing The Accessible Pool At Synaptic Membranes. Binders Targeting Presynaptic GABBR2 Would Find Fewer Surface Receptors In AJAP1-Deficient Contexts.)* *(cites: a2_evi_12)*
- *Post Translational Dependent*: null → null — GABBR2 R2 subunit's C-terminal coiled-coil domain masks a dileucine internalization motif on GABBR1a, slowing receptor internalization and stabilizing surface expression of the heterodimer. Heterodimerization with R2 is critical for surface expression and determines internalization rate. *(→ The R2 Coiled-Coil Domain Post-Translationally Stabilizes Surface GABBR2-Containing Heterodimers By Suppressing Internalization; Disruption Of This Interaction Would Reduce Surface Receptor Availability And Binder Accessibility.)* *(cites: a2_evi_18, a2_evi_19)*
- *Post Translational Dependent*: null → null — IGF2R (mannose-6-phosphate receptor) directly interacts with GABBR2 in a mannose-6-phosphate-dependent manner, providing a mechanism for internalization and downregulation of GABBR2 surface levels. *(→ M6P-Dependent IGF2R Binding Drives GABBR2 Internalization, Reducing Surface-Accessible Receptor. Conditions That Elevate IGF2R Activity Or M6P Modification Of GABBR2 Would Decrease Extracellular Binder Access.)* *(cites: a2_evi_28)*
- *Cell State Induced* · trigger: Other: resting primary human islets (low GABBR2 expression) → cAMP-stimulated primary human islets — GABBR2 mRNA expression is strongly induced by cAMP signaling in primary human islets, while GABBR1 mRNA is constitutively expressed, suggesting state-dependent upregulation of GABBR2 surface availability. *(→ CAMP-Driven Induction Of GABBR2 In Islet Beta Cells Suggests Surface Receptor Levels Are Dynamically Regulated By Metabolic/Hormonal State; Binder Access To GABBR2 On Beta Cells Would Be Greater In CAMP-Elevated States.)* *(cites: a2_evi_25)*
- *Disease State Induced* · trigger: Oncogenic Transformation: null → null — TAp73α-induced derepression of GABBR2 expression in melanoma cells leads to upregulation of GABBR2, promoting EMT, invasiveness, and proliferation. GABBR2 is expressed and functionally active in melanoma. *(→ GABBR2 Is Upregulated And Functionally Active In Melanoma Cells, Suggesting Increased Surface Availability In This Tumor Context. This May Create A Disease-Selective Surface Target Opportunity In Melanoma.)* *(cites: a2_evi_29)*

**Restricted-subdomain distribution**

- present: true
- severity: Moderate
- evidence: Moderate
- domain: Synaptic
- rationale: GABBR2-containing receptors are expressed at pre- and postsynaptic membranes at most excitatory and inhibitory synapses (a2_evi_11). Ultrastructural analysis specifically localizes GABBR2 to presynaptic sites, with AJAP1 required for normal presynaptic GBR levels (a2_evi_12). Synaptic localization limits systemic antibody access to the receptor.
- cites: a2_evi_11, a2_evi_12

**Co-receptor requirements**

- dependency: Required
- evidence basis: Mixed
- partners: GABBR1
- rationale: GABBR1 contains an ER retention signal that is masked only upon coiled-coil heterodimerization with GABBR2; disrupting this interface abolishes GABBR1 surface expression (a1_evi_20, a1_evi_21). Conversely, GABBR2 homodimers can reach the surface independently (a2_evi_13), but the canonical functional receptor requires GABBR1 co-assembly. GABBR2 is the obligate trafficking chaperone for GABBR1 (a1_evi_24, a2_evi_14).
- cites: a1_evi_20, a1_evi_21, a1_evi_24, a2_evi_13, a2_evi_14

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | O75899 | ref | ref | 7 | 490 aa | 250 aa | 41 aa | Extracellular→Cytoplasmic | — |
| Mouse ortholog | Gabbr2 | [Q80T41](https://www.uniprot.org/uniprotkb/Q80T41) | 98.0% | 97.6% | 7 | 490 aa | — | — | — | high (≥85%) |
| Cynomolgus ortholog | GABBR2 | [A0A2K5VY83](https://www.uniprot.org/uniprotkb/A0A2K5VY83) | 99.5% | 99.8% | 7 | 489 aa | — | — | — | high (≥85%) |
| Paralog | GABBR1 | [Q9UBS5](https://www.uniprot.org/uniprotkb/Q9UBS5) | 30.6% | 35.3% | — | — | — | — | — | low-risk |
| Paralog | GPR156 | [Q8NFN8](https://www.uniprot.org/uniprotkb/Q8NFN8) | 13.4% | 28.0% | — | — | — | — | — | low-risk |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak
- rationale: No relevant data in the ledger documenting proteolytic shedding of the GABBR2 ectodomain by a sheddase or release of a soluble GABBR2 ectodomain into supernatant or serum.

**Secreted form**

- present: false
- severity: Low
- evidence: Weak
- rationale: No relevant data in the ledger for a free soluble GABBR2 species in serum/plasma or a TM-less splice isoform of GABBR2 that circulates. The ledger notes multiple splice variants of GABBR2 mRNA in airway smooth muscle (a2_evi_20) but provides no evidence of a secreted/soluble protein form.

**ECD size assessment**

- ECD class: Large
- rationale: ECD length 490 residues (>=200) -> large; computed deterministically from DeepTMHMM topology.

**Epitope masking**

- severity: Moderate
- evidence: Strong
- mechanism: Partner
- rationale: GABBR2 forms an obligate heterodimer with GABBR1; the extracellular VFTDs of both subunits interact at the heterodimer interface (a1_evi_01, a1_evi_04). The GABBR1 VFTD sits adjacent to GABBR2's extracellular domain in the complex, potentially occluding epitopes on GABBR2's ECD. The coiled-coil C-terminal interface further buries surfaces (a1_evi_20). Deterministic AF2 prior shows no homo-oligomer (is_homo_oligomer=false), so oligomerization mechanism is not added.
- cites: a1_evi_01, a1_evi_04, a1_evi_20

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-O75899-F1](https://alphafold.ebi.ac.uk/entry/O75899) |
| AFDB version | v6 |
| ECD mean pLDDT | 89.6 |
| ECD disordered fraction | 4.9% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/O75899) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [O75899](https://alphafold.ebi.ac.uk/entry/O75899) | AlphaFold DB (AF-O75899-F1, v6) |
| Mouse ortholog (Gabbr2) | [Q80T41](https://alphafold.ebi.ac.uk/entry/Q80T41) | AlphaFold DB |
| Cynomolgus ortholog (GABBR2) | [A0A2K5VY83](https://alphafold.ebi.ac.uk/entry/A0A2K5VY83) | AlphaFold DB |
| Experimental (26 total) | [4F11](https://www.rcsb.org/structure/4F11), [4F12](https://www.rcsb.org/structure/4F12), [4MQE](https://www.rcsb.org/structure/4MQE), [4MQF](https://www.rcsb.org/structure/4MQF), [4MR7](https://www.rcsb.org/structure/4MR7), … [all 26 →](https://www.rcsb.org/uniprot/O75899) | RCSB PDB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

Gamma-aminobutyric acid type B receptor subunit 2 · Receptors · GPCR · chain A · 1 scored site · 543 binder seeds (8 α-helix / 535 β-strand).

Anchor = patch-center residue; BSA = buried surface area (the contact footprint a binder would form on the patch); seed counts are docked binder backbones split by α-helix / β-strand.

**Reading the scores.** BSA vs the average antibody–antigen interface ≈ 1103 ± 244 Å² ([PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)): ≥1500 Å² comfortable · 850–1500 workable · <850 thin. Seed pool: ≥1000 comfortable design margin · ≥100 workable · <100 thin/specialized. SURFACE-Bind excludes transmembrane regions but not necessarily intracellular domains — cross-check the anchor residue against the topology string in §5/appendix (`O` = extracellular/antibody-accessible, `I` = intracellular).

| Site | Anchor residue | BSA (Å²) | α-helix seeds | β-strand seeds | Hydrophobicity |
|---|---|---|---|---|---|
| 0 | 802 | 1745.7 | 8 | 535 | 0.4 |

**Experimental structures** — 26 PDB entries for this protein (browse at [RCSB](https://www.rcsb.org/uniprot/O75899)).

## 9. Evidence ledger

57 entries · 42 primary · 15 secondary · 0 tertiary · 48 PMC OA.

- `a1_evi_01` · *Secondary* · Supports · Topology — GABBR2 (GB2) possesses an extracellular Venus flytrap domain connected to a canonical seven-transmembrane domain, establishing the 7TM topology with N-terminus extracellular and C-terminus cytoplasmic orientation as part of the obligate GABBR1/GABBR2 heterodimer. ([PMC8020835](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8020835/))
  - *assay*: Human
  > "Each subunit possesses an extracellular Venus flytrap domain, which is connected to a canonical seven-transmembrane domain."
- `a1_evi_02` · *Secondary* · Supports · Topology — Each GABBR subunit (including GABBR2/GB2) consists of an extracellular bi-lobed Venus flytrap domain (VFTD), a heptahelical transmembrane domain (TMD), and a C-terminal intracellular domain, confirming the 7TM topology with large extracellular N-terminal domain. ([PMC13103378](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13103378/))
  - *assay*: Human
  > "Each subunit consists of an extracellular bi-lobed Venus flytrap domain (VFTD), a heptahelical transmembrane domain (TMD), and a C-terminal intracellular domain 4 – 6 ."
- `a1_evi_03` · *Secondary* · Supports · Topology — Within the GABBR1/GABBR2 heterodimer, orthosteric ligands bind the VFTD of GB1, while the TMD of GB2 (GABBR2) is responsible for coupling with the G protein — defining the functional surface domain architecture of GABBR2. ([PMC13103378](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13103378/))
  - *assay*: Human
  > "Orthosteric ligands bind to a pocket located within the VFTD of GB1, while the TMD of GB2 is responsible for coupling with the G protein."
- `a1_evi_04` · *Primary* · Supports · Topology — Cryo-EM structural study confirms GABBR2 (GBR2) is an obligate heterodimeric GPCR subunit with extracellular, seven-helix transmembrane (7TM), and coiled-coil domains, establishing the canonical topology with extracellular N-terminus. (https://pubmed.ncbi.nlm.nih.gov/33058878/)
  - *assay*: Human
  > "The neurotransmitter γ-aminobutyric acid (GABA) activates the metabotropic GABA<sub>B</sub> receptor to generate slow, prolonged inhibitory signals that regulate the neural circuitry. The GABA<sub>B</sub> receptor is an obligate heterodimeric G protein-coupled receptor (GPCR) comprised of GBR1 and GBR2 subunits, each with extracellular, seven-helix transmembrane (7TM), and coiled-coil domains."
- `a1_evi_05` · *Primary* · Supports · Topology — Cryo-EM structures reveal that extracellular loop 2 (ECL2) of GABBR2 has an essential role in relaying structural transitions by ordering the linker connecting the extracellular ligand-binding domain to the transmembrane region, confirming ECL2 is surface-accessible. ([PMC7429364](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7429364/))
  - *assay*: Human
  > "Complemented by cellular signalling assays and atomistic simulations, these structures reveal that extracellular loop 2 (ECL2) of GABA<sub>B</sub> has an essential role in relaying structural transitions by ordering the linker that connects the extracellular ligand-binding domain to the transmembrane region."
- `a1_evi_06` · *Primary* · Supports · Methodological — Surface biotinylation assay performed on endogenous GABBR1/GABBR2 in cultured cortical neurons (15–20 DIV) to determine steady-state surface expression of both subunits; anti-GABBR2 antibody (Chemicon) used for detection. ([PMC3945329](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3945329/))
  - *assay*: Rat · cortical neurons · live · non-permeabilized
  > "The steady-state expression of endogenous GABA B1 /GABA B2 subunits in cultured cortical neurones (15–20 days in vitro ) was determined by surface biotinylation."
- `a1_evi_07` · *Primary* · Supports · Surface Expression — Surface biotinylation of endogenous GABBR2 in cultured cortical neurons shows that under resting conditions 49.6% ± 1.19 of GABBR2 protein is surface-expressed, demonstrating robust constitutive plasma membrane localization. ([PMC3945329](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3945329/))
  - *assay*: Rat · cortical neurons · live · non-permeabilized
  > "Under resting conditions 24.59% ± 2.45 of GABA B1 and 49.6% ± 1.19 of GABA B2 is surface-expressed ( Fig. 1 , A and B )."
- `a1_evi_08` · *Primary* · Supports · Methodological — Antibody reagents used for GABBR2 surface biotinylation and imaging: guinea pig anti-GABBR2 (Chemicon International, Temecula, CA); rabbit anti-GABBR1a,b (Santa Cruz Biotechnology) for WB; mouse monoclonal anti-β-actin (Sigma-Aldrich) as loading control. ([PMC3945329](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3945329/))
  - *assay*: Rat · cortical neurons · unspecified
  > "Primary antibodies used were as follows: rabbit anti-GABA B1a,b (Santa Cruz Biotechnology, for Western blotting), guinea pig anti-GABA B1a,b (for all imaging) and anti-GABA B2 (Chemicon, Intl., Temecula, CA), and mouse monoclonal anti-β-actin (Sigma-Aldrich)."
- `a1_evi_09` · *Primary* · Supports · Surface Expression — Surface biotinylation data indicate a larger intracellular pool of GABBR1 than GABBR2, suggesting the two subunits are regulated by distinct trafficking pathways; GABBR2 has proportionally more surface-resident protein than GABBR1 at steady state. ([PMC3945329](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3945329/))
  - *assay*: Rat · cortical neurons · live · non-permeabilized
  > "Consistent with previous reports ( 19 , 33 ), these results indicate that there is a larger pool of intracellular GABA B1 than GABA B2 and infer that the two subunits are regulated by distinct trafficking pathways."
- `a1_evi_10` · *Secondary* · Supports · Methodological — Overexpression construct for GABBR2 surface IF assay: mGluR5 signal peptide (exogenous SP) and N-terminal Myc-tag introduced into plasmids encoding human GB2 wild-type and variants (GB2-S695I, GB2-A567T, GB2-I705N) in HEK293T cells. SP source is exogenous (mGluR5), so surface localization evidence is capped at secondary tier. ([PMC13232046](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13232046/))
  - *assay*: Human · HEK293T · fixed · non-permeabilized
  > "The mGluR5 signal peptide and a Myc-tag were introduced into the plasmids encoding human GB2, GB2-S695I and GB2-A567T published previously. 21 The plasmid encoding GB2-I705N was generated from Myc-tagged GB2 through site-directed mutagenesis (Q5 Site-Directed Mutagenesis kit, New England Biolabs)."
- `a1_evi_11` · *Secondary* · Supports · Methodological — Surface IF protocol for GABBR2 OE assay: anti-Myc antibody applied for 1 h on live (non-permeabilized) HEK293T cells co-expressing Myc-GB2 and GB1, then fixed and permeabilized for total GB2 staining with anti-GB2 antibody. Non-permeabilized Myc staining = surface fraction; post-permeabilization GB2 staining = total. Ratio quantifies surface expression. ([PMC13232046](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13232046/))
  - *assay*: Human · HEK293T · fixed · non-permeabilized
  > "After 2 days, cells were incubated with anti-Myc antibody (1:1000) for 1 h, fixed, permeabilized and then treated overnight at 4°C with anti-GB2 antibody (1:1000)."
- `a1_evi_12` · *Secondary* · Supports · Methodological — Antibody identifiers for GABBR2 surface IF assay: anti-Myc (#sc-40, RRID:AB_627268, Santa Cruz Biotechnology); anti-GB2 (#322205, RRID:AB_2620061, Synaptic Systems); anti-GB1 (#ab55051, RRID:AB_941703, Abcam); secondary antibodies anti-mouse AF568 and anti-guinea pig AF488. ([PMC13232046](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13232046/))
  - *assay*: Human · HEK293T · fixed · non-permeabilized
  > "GB2(R), GB2(K) and serum responsive element-luciferase (sreLuc) plasmids were as reported. 36 , 37 The following antibodies were used: anti-Myc (#sc-40, RRID:AB_627268, Santa Cruz Biotechnology), anti-GB1 (#ab55051, RRID:AB_941703, Abcam), anti-GB2 (#322205, RRID:AB_2620061, Synaptic Systems), anti-mouse AF568 (#A-11004, Invitrogen) and anti-guinea pig AF488 (#A-11073, Invitrogen)."
- `a1_evi_13` · *Secondary* · Supports · Surface Expression — Myc-tagged GB2 (with exogenous mGluR5 SP) co-expressed with GB1 in HEK293T cells; cell surface expression assessed by anti-Myc staining on non-permeabilized cells and total expression by anti-GB2 after permeabilization using confocal IF. OE construct SP is exogenous. ([PMC13232046](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13232046/))
  - *assay*: Human · HEK293T · fixed · non-permeabilized
  > "The A567T variant in TM3 is situated in a region regulating constitutive receptor activity, whereas the S695I and I705N variants in TM6 are located in a region controlling receptor activation and allosteric modulation. 48 We co-expressed Myc-tagged GB2 variants along with GB1 in HEK293T cells and assessed GB2 cell surface and total expression levels before and after cell permeabilization, respectively, using anti-Myc and anti-GB2 antibodies ( Fig. 1B )."
- `a1_evi_14` · *Primary* · Supports · Surface Expression — Three GABBR2 point mutations (G693W, S695I, I705N) in TM6 impair neuronal cell surface expression of GABABRs, reducing signalling efficacy — assessed by confocal imaging and flow cytometry on HEK-293T cells and hippocampal neurons. This is direct surface-expression evidence for wild-type GABBR2 surface localization (variants reduce it). ([PMC11788220](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11788220/))
  - *assay*: Rat · hippocampal neurons / HEK-293T · live · non-permeabilized
  > "We report that all three point mutations impair neuronal cell surface expression of GABABRs, reducing signalling efficacy."
- `a1_evi_15` · *Primary* · Supports · Methodological — Surface-expression methods used for GABBR2 variant characterization include confocal imaging, flow cytometry, live-cell Ca2+ imaging of presynaptic terminals, whole-cell electrophysiology (HEK-293T and neurons), and two-electrode voltage clamping (Xenopus oocytes). Flag-tagged GABBR2 in pRK5 used as the overexpression construct. ([PMC11788220](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11788220/))
  - *assay*: Rat · HEK-293T / hippocampal neurons · live · non-permeabilized
  > "Using a range of confocal imaging, flow cytometry, structural modelling, biochemistry, live cell Ca2+ imaging of presynaptic terminals, whole-cell electrophysiology of human embryonic kidney (HEK)-293 T cells and neurons and two-electrode voltage clamping of Xenopus oocytes, we have probed the biophysical and molecular trafficking and functional profiles of G693W, S695I and I705N variants."
- `a1_evi_16` · *Secondary* · Supports · Surface Expression — Cell surface expression of SNAP-tagged GB2 (GABBR2) measured by Lumi4-Tb fluorescence emission on transfected cells, either alone or co-transfected with GB1. This is an OE surface assay using an influenza HA signal sequence (exogenous SP) on GB2 residues 42–821. ([PMC8020835](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8020835/))
  - *assay*: Human · transfected cells (unspecified line) · live · non-permeabilized
  > "Expression, characterization and purification of GABA B . a , b , Cell surface expression of Halo-GB1 ( a ) and SNAP-GB2 ( b ) transfected alone or co-transfected with the second subunit, measured by the fluorescence emission of the Lumi4-Tb bound to the Halo- ( a ) or SNAP-tag ( b )."
- `a1_evi_17` · *Primary* · Supports · Surface Expression — IHC of brainstem sections shows GABBR2-immunoreactivity (GABAB R2-ir) in a large number of cells and in the surrounding neuropil of the pedunculopontine tegmental (PPT) and laterodorsal tegmental (LDT) nuclei; R2 subunit antibody selected for more robust labeling over R1. ([PMC8741722](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8741722/))
  - *assay*: Rat · brainstem neurons · fixed · permeabilized
  > "Similarly, GABAAR γ2-immunoreactivity (GABAAR γ2-ir, Fig. 1 b, b’) and GABAB R2-ir (Fig. 1 c, c’) were also observed in a large number of cells and in the surrounding neuropil as well."
- `a1_evi_18` · *Primary* · Supports · Methodological — Antibody selection for GABBR2 IHC: initial trials with antibodies against both R1 and R2 subunits revealed more robust labeling with the R2 subunit antibody, which was selected for GABABR detection in brainstem sections. ([PMC8741722](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8741722/))
  - *assay*: Rat · brainstem neurons · fixed · permeabilized
  > "Initial trials using antibodies against the two subunits revealed a more robust labeling of the R2 subunit, which was, therefore, selected for GABABR detection."
- `a1_evi_19` · *Secondary* · Ambiguous · Tissue Expression — GABBR2 expression in human aortic smooth muscle cells (HASMCs) assessed by real-time PCR, western blot, and immunofluorescence; IHC used to localize GABBR2 in human left anterior descending artery (LAD). These are non-surface-specific methods (WB, IF without explicit non-permeabilized protocol, IHC on tissue sections). (https://pubmed.ncbi.nlm.nih.gov/24682435/)
  - *assay*: Human · human aortic smooth muscle cells / LAD artery · fixed
  > "The aim of this study was to investigate the expression of GABAB receptors, a subclass of receptors to the inhibitory neurotransmitter gamma-aminobutyric acid (GABAB), in human aortic smooth muscle cells (HASMCs), and to explore if altering receptor activation modified intracellular Ca(2+) concentration ([Ca(2+)]i) of HASMCs. Real-time PCR, western blots and immunofluorescence were used to determine the expression of GABABR1 and GABABR2 in cultured HASMCs. Immunohistochemistry was used to localize the two subunits in human left anterior descending artery (LAD)."
- `a1_evi_20` · *Primary* · Supports · Surface Expression — Crystal structure of the intracellular coiled-coil heterodimer of human GABBR1/GABBR2 shows that association between GBR1 and GBR2 masks an ER retention signal in the cytoplasmic region of GBR1, facilitating cell surface expression of both subunits — establishing GABBR2 as required for GABBR1 surface trafficking. ([PMC4024898](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4024898/))
  - *assay*: Human
  > "Metabotropic GABAB receptor is a G protein-coupled receptor that mediates inhibitory neurotransmission in the CNS. It functions as an obligatory heterodimer of GABAB receptor 1 (GBR1) and GABAB receptor 2 (GBR2) subunits. The association between GBR1 and GBR2 masks an endoplasmic reticulum (ER) retention signal in the cytoplasmic region of GBR1 and facilitates cell surface expression of both subunits. Here, we present, to our knowledge, the first crystal structure of an intracellular coiled-coil heterodimer of human GABAB receptor."
- `a1_evi_21` · *Primary* · Supports · Surface Expression — Disruption of the hydrophobic coiled-coil interface between GABBR1 and GABBR2 with single mutations in either subunit impairs surface expression of GBR1, confirming that the coiled-coil interaction is required to inactivate the adjacent ER retention signal. The coiled-coil assembly also buries an internalization motif of GBR1 at the heterodimer interface. ([PMC4024898](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4024898/))
  - *assay*: Human
  > "We found that polar interactions buried within the hydrophobic core determine the specificity of heterodimer pairing. Disruption of the hydrophobic coiled-coil interface with single mutations in either subunit impairs surface expression of GBR1, confirming that the coiled-coil interaction is required to inactivate the adjacent ER retention signal of GBR1. The coiled-coil assembly buries an internalization motif of GBR1 at the heterodimer interface."
- `a1_evi_22` · *Primary* · Supports · Surface Expression — CRISPR-KO genome-scale cell-based screen using mAb staining of intact cells identified IGF2R (insulin-like growth factor 2 receptor) as a direct binding partner for the R2 subunit (GABBR2) of GABA-B receptors at the cell surface; interaction is mannose-6-phosphate dependent. ([PMC6120632](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6120632/))
  - *assay*: Human · unspecified cell line · live · non-permeabilized
  > "Finally, we demonstrate the utility of the approach by identifying IGF2R (insulin like growth factor 2 receptor) as a binding partner for the R2 subunit of GABA<sub>B</sub> receptors."
- `a1_evi_23` · *Primary* · Supports · Methodological — CRISPR-KO surface-accessibility assay methodology: transduced cells losing antibody epitope at the cell surface were isolated by FACS; genes responsible for loss of binding identified by deep sequencing of gRNA PCR products. This validates the surface-detection approach used to identify GABBR2 binding partners. ([PMC6120632](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6120632/))
  - *assay*: Human · unspecified cell line · live · non-permeabilized
  > "Transduced cells that had lost the antibody epitope at the cell surface were isolated by FACS, and the genes responsible for this loss of binding were identified by comparing the relative abundance of the different gene-specific gRNAs present in the sorted cells compared with the total unsorted population using deep sequencing of gRNA PCR products and enrichment analysis ( Fig. 1 A; Li et al. 2014 )."
- `a1_evi_24` · *Secondary* · Supports · Surface Expression — GABBR2 is necessary for cell surface expression of GABBR1 and for ensuring cell surface stability of the GABBR1/GABBR2 heterodimer; oligomerization is indispensable for function. This establishes GABBR2 as the obligate trafficking chaperone for the heterodimer. ([PMC11788220](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11788220/))
  - *assay*: Human
  > "Oligomerization is indispensable for function as GABA B R1 contains the GABA binding site, whereas G-protein coupling occurs at GABA B R2. 9 , 10 In addition, GABA B R2 is necessary for cell surface expression of GABA B R1 11 and ensuring cell surface stability of the heterodimer. 12 Single nucleotide variants of the gene encoding for GABA B R2 ( GABBR2 ) are now implicated in a wide range of neurodevelopmental disorders 13 often sharing common symptoms, including: intellectual disability with developmental and epileptic encephalopathy and infantile seizures (e.g."
- `a1_evi_25` · *Primary* · Refutes · Contradictory — GABBR2 variant p.Gly673Asp in TMD3 renders the receptor completely inactive, consistent with failure of the receptor to reach the cell surface — direct evidence that wild-type GABBR2 surface expression is required for function, and that loss-of-surface-expression is a pathogenic mechanism. ([PMC9606381](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9606381/))
  - *assay*: Human · unspecified (in vitro functional characterization)
  > "GABA fails to efficiently activate the variant receptors, most likely leading to an increase in the excitation/inhibition balance in the central nervous system. Variant p.Gly673Asp in transmembrane domain 3 (TMD3) renders the receptor completely inactive, consistent with failure of the receptor to reach the cell surface. p.Glu368Asp is located near the orthosteric binding site and reduces GABA potency and efficacy at the receptor. GABA exhibits normal potency but decreased efficacy at the p.Ala397Val and p.Ala535Thr variants."
- `a1_evi_26` · *Primary* · Refutes · Contradictory — In vitro functional characterization of GABBR2 variants reveals reduced surface expression as one of three loss-of-function mechanisms, resulting in decreased GABA efficacy — confirming that surface expression level is a regulated, variant-sensitive parameter for GABBR2. ([PMC13103378](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13103378/))
  - *assay*: Human · unspecified (in vitro)
  > "In vitro functional characterization of these variants revealed a range of gain- and loss-of-function alterations: (i) increased constitutive activity, leading to a corresponding decrease in GABA efficacy; (ii) a significant reduction in GABA potency at the receptor; and (iii) reduced surface expression, resulting in decreased GABA efficacy."
- `a1_evi_27` · *Secondary* · Ambiguous · Tissue Expression — GABBR2 protein levels measured by western blot (immunoblotting) in dentate gyrus (DG) hippocampal slices; no surface fractionation step performed. This is a whole-cell WB without surface-specific isolation, qualifying as non-surface expression evidence. ([PMC11076641](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11076641/))
  - *assay*: Rat · hippocampal dentate gyrus · unspecified
  > "By contrast, both GABA B R1 and GABA B R2 subunit protein levels significantly and sustainably increased in the DG from 10 to 90 days after TMT."
- `a1_evi_28` · *Secondary* · Supports · Methodological — Antibody reagent for GABBR2 detection: N-terminus epitope antibody (Santa Cruz Biotechnology) used for immunoblotting of GABBR2 subunit; GAPDH antibody (Santa Cruz) used as loading control. ([PMC11076641](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11076641/))
  - *assay*: Rat · hippocampal slices · unspecified
  > "IgGs were purchased from companies below: calbindin and GFAP (Cell Signaling Technology Inc., Danvers, MA), glyceraldehyde 3-phosphate dehydrogenase (GAPDH) and N-terminus of GABA B receptor R2 (GABA B R2) subunit (Santa Cruz Biotechnology, Santa Cruz, CA)."
- `a2_evi_01` · *Primary* · Supports · Tissue Expression — GABBR2 (GPR51) mRNA is predominantly expressed in the CNS with highest abundance in cortex, thalamus, hippocampus, amygdala, cerebellum, and spinal cord; transcripts are almost undetectable in peripheral tissues. Evidence from Northern blot and in situ hybridization. (https://pubmed.ncbi.nlm.nih.gov/10087195/)
  - *assay*: Human · CNS tissue (cortex, thalamus, hippocampus, amygdala, cerebellum, spinal cord) · fixed
  > "GPR 51 expressed in COS-1 cells showed no specific binding for [3H](+)baclofen and when expressed in Xenopus oocyte and Xenopus melanophore functional assays showed no activity to GABA, (-)baclofen, and glutamic acid. Northern blot analysis and in situ hybridization revealed that GPR 51 transcripts were predominantly expressed in the central nervous system with highest abundance in the cortex, thalamus, hippocampus, amygdala, cerebellum, and spinal cord. In contrast, GPR 51 receptor transcripts were almost not detected in the peripheral tissues."
- `a2_evi_02` · *Secondary* · Supports · Tissue Expression — GABBR2-containing GABA(B) receptors are distributed throughout the mammalian central nervous system, consistent with broad CNS expression. ([PMC3374333](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3374333/))
  - *assay*: Unspecified · CNS tissue
  > "GABA B receptor is distributed throughout the mammalian central nervous system."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — GABBR2 (R2 subunit) is expressed in neurons of the pedunculopontine (PPN) and laterodorsal tegmental (LDT) brainstem nuclei; stereological quantification shows ~7310 non-cholinergic R2-positive cells in PPN and ~9170 in LDT. Neurochemical phenotyping performed by IHC. ([PMC8741722](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8741722/))
  - *assay*: Rat · PPN and LDT brainstem neurons · fixed · permeabilized
  > "Specifically, the total number of neurons expressing the GABAA receptor γ2 subunit (GABAAR γ2) and the GABAB receptor R2 subunit (GABAB R2) in PPN and LDT was estimated using stereological methods, and the neurochemical phenotype of cells expressing each subunit was also determined."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — In the PPN and LDT brainstem nuclei, 95–98% of cholinergic neurons co-express GABBR2 (R2 subunit), indicating near-universal expression in this neurochemical subpopulation. ([PMC8741722](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8741722/))
  - *assay*: Rat · cholinergic neurons, PPN and LDT · fixed · permeabilized
  > "In addition, all cholinergic neurons in both nuclei co-expressed GABAAR γ2 and 95-98% of them co-expressed GABAB R2."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — In PPN and LDT, approximately two-thirds of both glutamatergic and GABAergic neurons co-express GABBR2 (R2 subunit), with similar proportions in both nuclei. ([PMC8741722](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8741722/))
  - *assay*: Rat · glutamatergic and GABAergic neurons, PPN and LDT · fixed · permeabilized
  > "In contrast, a similar proportion (~2/3) of glutamatergic and GABAergic cells co-expressed GABAB R2 in both nuclei."
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — GABBR2 (GABA_B receptor 2 subunit) mRNA is transcriptionally downregulated in post-mortem human middle temporal gyrus in Alzheimer's disease, as measured by NanoString nCounter analysis. ([PMC7698927](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7698927/))
  - *assay*: Human · post-mortem middle temporal gyrus, Alzheimer's disease
  > "Utilizing NanoString nCounter analysis, we demonstrate here the transcriptional downregulation of several GABA signaling components in the post-mortem human middle temporal gyrus (MTG) in AD, including the GABA<sub>A</sub> receptor α<sub>1</sub>, α<sub>2</sub>, α<sub>3</sub>, α<sub>5</sub>, β<sub>1</sub>, β<sub>2</sub>, β<sub>3</sub>, δ, γ<sub>2</sub>, γ<sub>3</sub>, and θ subunits and the GABA<sub>B</sub> receptor 2 (GABA<sub>B</sub>R2) subunit."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — GABBR2 mRNA expression and receptor binding are significantly decreased in hippocampal subfields CA1 and CA3 and the dentate hilus in patients with temporal lobe epilepsy with Ammon's horn sclerosis, compared to post-mortem controls. (https://pubmed.ncbi.nlm.nih.gov/14625043/)
  - *assay*: Human · hippocampus (CA1, CA3, dentate hilus), temporal lobe epilepsy · fixed
  > "Malfunctioning of the GABA-ergic system has been postulated as a possible cause of epilepsy. We investigated changes in the mRNA expression of the GABA(B) receptor subtypes GABA(B)-R1 and GABA(B)-R2 and of GABA(B) receptor binding in the hippocampus of patients with temporal lobe epilepsy (TLE) compared with post-mortem controls. In patients with Ammon's horn sclerosis, significant decreases in [3H]CG54626A binding were observed in subfields CA1 and CA3 of the hippocampus proper and the dentate hilus."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — GABBR2 mRNA and receptor binding are enhanced (after correction for neuronal loss) in dentate granule cells, molecular layer, and subiculum in temporal lobe epilepsy patients with and without hippocampal sclerosis, indicating upregulation in surviving neurons. (https://pubmed.ncbi.nlm.nih.gov/14625043/)
  - *assay*: Human · dentate granule cells, molecular layer, subiculum · fixed
  > "On the other hand, both GABA(B) receptor mRNAs and receptor binding were enhanced after correction for neuronal loss in dentate granule cells and in the molecular layer, respectively, and the subiculum of patients with and without hippocampal sclerosis. These increases were even more pronounced when correcting the values for cell losses in the respective areas and indicated also increased expression of GABA(B)-R in the dentate hilus."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — GABBR2 protein levels are significantly and sustainably upregulated in the hippocampal dentate gyrus (DG) from 10 to 90 days after systemic trimethyltin (TMT) neurotoxic injury in mice, a disease-state-induced increase in a specific hippocampal subregion. ([PMC11076641](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11076641/))
  - *assay*: Mouse · hippocampal dentate gyrus, TMT injury model
  > "By contrast, both GABA B R1 and GABA B R2 subunit protein levels significantly and sustainably increased in the DG from 10 to 90 days after TMT."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — GABBR2 co-localizes with GFAP-positive astrocytes in the hippocampal dentate gyrus at 30 days post-TMT injury (by IHC), but this co-localization is lost by 90 days, suggesting a dynamic shift in the cell-type identity of GABBR2-expressing cells during recovery. ([PMC11076641](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11076641/))
  - *assay*: Mouse · hippocampal dentate gyrus astrocytes (GFAP+), TMT injury · fixed · permeabilized
  > "Although co-localization was invariably detected between GABA<sub>B</sub>R2 subunit and GFAP in the DG at 30 days on immunohistochemical analysis, GABA<sub>B</sub>R2-positive cells did not merge well with GFAP-positive cells in the DG at 90 days."
- `a2_evi_11` · *Secondary* · Supports · Surface Expression — GABBR2-containing GBRs are expressed at most excitatory and inhibitory synapses in the brain, where they inhibit neurotransmitter release and generate slow inhibitory postsynaptic potentials. This places GABBR2 at both pre- and postsynaptic membranes throughout the brain. ([PMC11235169](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11235169/))
  - *assay*: Unspecified · neurons, brain synapses
  > "GBRs are expressed at most excitatory and inhibitory synapses in the brain, where they inhibit neurotransmitter release and generate slow inhibitory postsynaptic potentials that decrease neuronal excitability ( 11 )."
- `a2_evi_12` · *Primary* · Supports · Surface Expression — Ultrastructural analysis reveals significantly decreased presynaptic GABBR2-containing GBR levels in Ajap1-/- and Ajap1W183C/+ mice, demonstrating that AJAP1 is required for normal presynaptic surface levels of GABBR2 at synapses. Baseline: wild-type presynaptic GBR levels. Modulating state: AJAP1 loss-of-function. Change: significant reduction in presynaptic GBR. Implication: AJAP1 trans-synaptically recruits GBRs to presynaptic sites. ([PMC11235169](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11235169/))
  - *assay*: Mouse · presynaptic neurons
  > "Ultrastructural analysis revealed significantly decreased presynaptic GBR levels in <i>Ajap1</i><sup>-/-</sup> and <i>Ajap1</i><sup>W183C/+</sup> mice."
- `a2_evi_13` · *Primary* · Supports · Surface Expression — GABBR2 homodimers and GABBR1/GABBR2 heterodimers are present at the plasma membrane, whereas GABBR1 homodimers are retained in the ER/ERGIC. This demonstrates that GABBR2 can reach the cell surface both as a homodimer and as part of the canonical heterodimer. ([PMC1186692](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1186692/))
  - *assay*: Unspecified · transfected cells · fixed · non-permeabilized
  > "Confocal microscopy indicates that, while GBR1/GBR1 homodimers are retained in the endoplasmic reticulum and endoplasmic reticulum-Golgi intermediate compartment, both GBR2/GBR2 homodimers and GBR1/GBR2 heterodimers are present at the plasma membrane. Although these observations shed new light on the assembly of GBR complexes, they raise questions about the potential functional roles of GBR1 and GBR2 homodimers."
- `a2_evi_14` · *Secondary* · Supports · Surface Expression — GABBR2 is required for GABBR1 to reach the cell surface; GABBR1 can only exit the ER and reach the plasma membrane after dimerizing with GABBR2. This establishes GABBR2 as the obligatory trafficking chaperone for surface delivery of the heterodimer. ([PMC13103378](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13103378/))
  - *assay*: Unspecified · neurons
  > "As a result, GB1 can only reach the cell surface after dimerizing with GB2."
- `a2_evi_15` · *Primary* · Refutes · Surface Expression — Three pathogenic GABBR2 point mutations (G693W, S695I, I705N in TM6) impair neuronal cell surface expression of GABBR2-containing receptors, reducing signalling efficacy. Baseline: wild-type neuronal surface expression. Modulating state: disease-associated variant. Change: reduced surface expression. Implication: variants reduce target accessibility at the neuronal surface. ([PMC11788220](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11788220/))
  - *assay*: Rat · hippocampal neurons · live · non-permeabilized
  > "We report that all three point mutations impair neuronal cell surface expression of GABABRs, reducing signalling efficacy."
- `a2_evi_16` · *Primary* · Supports · Surface Expression — In HEK293T cells, GABBR2 variants A567T and I705N show slightly but significantly increased cell surface expression compared to wild-type GB2, while S695I surface expression is similar to wild-type. This suggests variant-specific effects on surface trafficking. ([PMC13232046](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13232046/))
  - *assay*: Human · HEK293T cells · live · non-permeabilized
  > "While GB2-S695I cell surface expression was similar to that of wt GB2, surface expressions of GB2-A567T and GB2-I705N were slightly but significantly increased ( Fig. 1B )."
- `a2_evi_17` · *Primary* · Refutes · Surface Expression — GABBR2 variant p.Gly673Asp (in TMD3) renders the receptor completely inactive and fails to reach the cell surface, providing direct evidence that this variant causes intracellular retention rather than surface expression. ([PMC9606381](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9606381/))
  - *assay*: Unspecified · transfected cells
  > "GABA fails to efficiently activate the variant receptors, most likely leading to an increase in the excitation/inhibition balance in the central nervous system. Variant p.Gly673Asp in transmembrane domain 3 (TMD3) renders the receptor completely inactive, consistent with failure of the receptor to reach the cell surface. p.Glu368Asp is located near the orthosteric binding site and reduces GABA potency and efficacy at the receptor. GABA exhibits normal potency but decreased efficacy at the p.Ala397Val and p.Ala535Thr variants."
- `a2_evi_18` · *Primary* · Supports · Surface Expression — GABBR2 (R2 subunit) plays a dominant role in regulating internalization of GABA(B) receptors at the cell surface in live cells; heterodimerization between R1 and R2 is critical for cell surface expression and determines the rate and extent of receptor internalization. ([PMC3129212](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3129212/))
  - *assay*: Unspecified · live cells (transfected) · live · non-permeabilized
  > "γ-Aminobutyric acid type B (GABA(B)) receptors are important for slow synaptic inhibition in the CNS. The efficacy of inhibition is directly related to the stability of cell surface receptors. For GABA(B) receptors, heterodimerization between R1 and R2 subunits is critical for cell surface expression and signaling, but how this determines the rate and extent of receptor internalization is unknown. Here, we insert a high affinity α-bungarotoxin binding site into the N terminus of the R2 subunit and reveal its dominant role in regulating the internalization of GABA(B) receptors in live cells."
- `a2_evi_19` · *Primary* · Supports · Surface Expression — GABBR2 (R2) C-terminal coiled-coil domain masks a dileucine internalization motif on GABBR1 (R1a), slowing receptor internalization and stabilizing surface expression of the heterodimer. This is a novel role for GPCR heterodimerization in determining surface stability. ([PMC3129212](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3129212/))
  - *assay*: Unspecified · transfected cells · live · non-permeabilized
  > "The fast internalization rate of R1a, which has been engineered to exit the endoplasmic reticulum, was slowed to that of R2 by truncating the R1a C-terminal tail or by removing a dileucine motif in its coiled-coil domain. Slowing the rate of internalization by co-assembly with R2 represents a novel role for GPCR heterodimerization whereby R2 subunits, via their C terminus coiled-coil domain, mask a dileucine motif on R1a subunits to determine the surface stability of the GABA(B) receptor."
- `a2_evi_20` · *Primary* · Supports · Tissue Expression — GABBR2 mRNA (multiple splice variants) is expressed in native human airway smooth muscle and in cultured human airway smooth muscle (HASM) cells, extending GABBR2 expression beyond the CNS to peripheral airway tissue. (https://pubmed.ncbi.nlm.nih.gov/16829628/)
  - *assay*: Human · native and cultured human airway smooth muscle
  > "Although the GABA(B)R has been shown to function as a prejunctional inhibitory receptor on parasympathetic nerves in the lung, the expression and functional coupling of GABA(B) receptors to G(i) in airway smooth muscle itself have never been described. We detected the mRNA encoding multiple-splice variants of the GABA(B)R1 and GABA(B)R2 in total RNA isolated from native human and guinea pig airway smooth muscle and from RNA isolated from cultured human airway smooth muscle (HASM) cells."
- `a2_evi_21` · *Primary* · Supports · Tissue Expression — GABBR2 protein is detected by immunoblot in native and cultured human airway smooth muscle, and GABBR1 protein is immunohistochemically localized to airway smooth muscle in guinea pig trachea. Functional coupling to Gi confirmed by baclofen-stimulated GTPγS binding. (https://pubmed.ncbi.nlm.nih.gov/16829628/)
  - *assay*: Human · native and cultured human airway smooth muscle
  > "Immunoblots identified the GABA(B)R1 and GABA(B)R2 proteins in human native and cultured airway smooth muscle. The GABA(B)R1 protein was immunohistochemically localized to airway smooth muscle in guinea pig tracheal rings. Baclofen, a GABA(B)R agonist, elicited a concentration-dependent stimulation of [(35)S]GTPgammaS binding in HASM homogenates that was abrogated by the GABA(B)R antagonist CGP-35348. Baclofen also inhibited adenylyl cyclase activity and induced ERK phosphorylation in HASM."
- `a2_evi_22` · *Primary* · Supports · Tissue Expression — GABBR2 mRNA and protein are expressed in cultured human aortic smooth muscle cells (HASMCs) and GABBR2 antibody staining localizes to smooth muscle cells of the human left anterior descending (LAD) coronary artery, demonstrating vascular smooth muscle expression. (https://pubmed.ncbi.nlm.nih.gov/24682435/)
  - *assay*: Human · aortic smooth muscle cells, LAD coronary artery smooth muscle · fixed · permeabilized
  > "The effects of the GABAB receptor agonist baclofen on [Ca(2+)]i in cultured HASMCs were demonstrated using fluo-3. Both GABABR1 and GABABR2 mRNA and protein were identified in cultured HASMCs and antibody staining was also localized to smooth muscle cells of human LAD. 100 μM baclofen caused a transient increase of [Ca(2+)]i in cultured HASMCs regardless of whether Ca(2+) was added to the medium, and the effects were inhibited by pre-treatment with CGP46381 (selective GABAB receptor antagonist), pertussis toxin (a Gi/o protein inhibitor), and U73122 (a phospholipase C blocker)."
- `a2_evi_23` · *Primary* · Supports · Tissue Expression — GABBR2 is expressed in brain microvascular endothelial cells; inactivation of BACE2 causes downregulation of GABBR2 and p-AKT in this cell type, providing the first evidence of GABBR2 expression in the cerebrovascular endothelium. ([PMC12365451](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12365451/))
  - *assay*: Unspecified · brain microvascular endothelial cells
  > "We also provide the first evidence that in the microvascular endothelium, inactivation of BACE2 causes down-regulation of GABBR2 and p-AKT, and augments expression of TGF-β2, thereby resulting in enhanced release of powerful vasoconstrictor, prooxidant, and proinflammatory protein ET-1 ( Figure 3 )."
- `a2_evi_24` · *Primary* · Supports · Tissue Expression — Both GABBR1 and GABBR2 subunits are expressed in the human beta cell line ECN90 and in primary human islets, establishing GABBR2 expression in pancreatic beta cells. ([PMC7417582](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7417582/))
  - *assay*: Human · human beta cell line ECN90 and primary human islets
  > "This cell line, named ECN90 expresses both subunits (GABBR1 and GABBR2) of the metabotropic GABA<sub>B</sub> receptor compared to human islet."
- `a2_evi_25` · *Primary* · Supports · Tissue Expression — In primary human islets, GABBR2 mRNA expression is strongly induced under cAMP signaling (cell-state modulation), while GABBR1 mRNA is constitutively expressed. Baseline: resting human islets, low GABBR2. Modulating state: cAMP elevation. Change: strong GABBR2 mRNA induction. Implication: GABBR2 surface availability in islets is state-dependent. ([PMC7417582](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7417582/))
  - *assay*: Human · primary human islets
  > "We next demonstrated that in primary human islets, GABBR2 mRNA expression is strongly induced under cAMP signaling, while GABBR1 mRNA is constitutively expressed."
- `a2_evi_26` · *Primary* · Supports · Tissue Expression — Gabbr2 mRNA expression is upregulated in VTA dopaminergic neurons in Ogt conditional knockout mice and under acute restraint stress, with STAT3(Ser727) phosphorylation required for this upregulation. Baseline: resting VTA DAergic neurons. Modulating state: acute restraint stress or OGT loss. Change: Gabbr2 upregulation. Implication: stress-induced increase in GABBR2 in VTA dopaminergic neurons. ([PMC12533289](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12533289/))
  - *assay*: Mouse · VTA dopaminergic neurons
  > "Furthermore, Gabbr2 and Gabrb3 expression is upregulated in the VTA of Ogt cKO mice, whereas the phosphorylation of STAT3<sup>Ser727</sup> in the DAergic neurons is required for the upregulation of Gabbr2 and Gabrb3 induced by acute restraint stress."
- `a2_evi_27` · *Primary* · Supports · Tissue Expression — Acute ethanol exposure alters GABBR2-containing receptor expression and signalling in neurons, increasing dendritic calcium signaling. Baseline: untreated neurons. Modulating state: acute ethanol. Change: increased GABBR expression and dendritic Ca2+ signaling. Implication: ethanol modulates GABBR2 surface availability and function. ([PMC5052688](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5052688/))
  - *assay*: Mouse · neurons
  > "Ethanol, like rapid antidepressants, alters γ-aminobutyric acid type B receptor (GABA<sub>B</sub>R) expression and signalling, to increase dendritic calcium."
- `a2_evi_28` · *Primary* · Supports · Surface Expression — IGF2R (mannose-6-phosphate receptor) directly interacts with the GABBR2 (R2) subunit in a mannose-6-phosphate-dependent manner, providing a mechanism for internalization and regulation of GABBR2 surface levels. This is an accessibility modulation mechanism for GABBR2 at the cell surface. ([PMC6120632](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6120632/))
  - *assay*: Unspecified · transfected cells
  > "We show that this interaction is direct and is critically dependent on mannose-6-phosphate, providing a mechanism for the internalization and regulation of GABA<sub>B</sub> receptor signaling."
- `a2_evi_29` · *Primary* · Supports · Tissue Expression — TAp73α-induced derepression of GABBR2 expression in melanoma cells leads to upregulation of EMT markers, promotes cancer cell invasiveness and proliferation, and correlates with poor survival outcomes. This identifies GABBR2 as expressed and functionally active in melanoma in a disease-state-induced context. (https://pubmed.ncbi.nlm.nih.gov/40505831/)
  - *assay*: Human · melanoma cells
  > "TAp73α-induced derepression of GABBR2 expression leads to upregulation of EMT markers, promotes cancer cell invasiveness and proliferation, and correlates with poor survival outcomes. Our findings redefine the function of p73 in cancer pathogenesis and identify the TAp73α-HDAC2/REST-GABBR2 axis as a novel driver of melanoma progression. These insights could guide future strategies on melanoma treatment."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/GABBR2.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/GABBR2](https://surfaceome.deliverome.org/GABBR2)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/GABBR2.json](https://surfaceome.deliverome.org/data/surfaceome/GABBR2.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/GABBR2.md](https://surfaceome.deliverome.org/data/surfaceome/GABBR2.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/O75899](https://alphafold.ebi.ac.uk/entry/O75899)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/O75899](https://alphafold.ebi.ac.uk/api/prediction/O75899) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/O75899](https://www.uniprot.org/uniprotkb/O75899)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-O75899-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-O75899-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-O75899-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-O75899-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-O75899-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-O75899-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*941 aa · `O75899` · embedded at build time*

```
   1  MASPRSSGQPGPPPPPPPPPARLLLLLLLPLLLPLAPGAWGWARGAPRPPPSSPPLSIMG
  61  LMPLTKEVAKGSIGRGVLPAVELAIEQIRNESLLRPYFLDLRLYDTECDNAKGLKAFYDA
 121  IKYGPNHLMVFGGVCPSVTSIIAESLQGWNLVQLSFAATTPVLADKKKYPYFFRTVPSDN
 181  AVNPAILKLLKHYQWKRVGTLTQDVQRFSEVRNDLTGVLYGEDIEISDTESFSNDPCTSV
 241  KKLKGNDVRIILGQFDQNMAAKVFCCAYEENMYGSKYQWIIPGWYEPSWWEQVHTEANSS
 301  RCLRKNLLAAMEGYIGVDFEPLSSKQIKTISGKTPQQYEREYNNKRSGVGPSKFHGYAYD
 361  GIWVIAKTLQRAMETLHASSRHQRIQDFNYTDHTLGRIILNAMNETNFFGVTGQVVFRNG
 421  ERMGTIKFTQFQDSREVKVGEYNAVADTLEIINDTIRFQGSEPPKDKTIILEQLRKISLP
 481  LYSILSALTILGMIMASAFLFFNIKNRNQKLIKMSSPYMNNLIILGGMLSYASIFLFGLD
 541  GSFVSEKTFETLCTVRTWILTVGYTTAFGAMFAKTWRVHAIFKNVKMKKKIIKDQKLLVI
 601  VGGMLLIDLCILICWQAVDPLRRTVEKYSMEPDPAGRDISIRPLLEHCENTHMTIWLGIV
 661  YAYKGLLMLFGCFLAWETRNVSIPALNDSKYIGMSVYNVGIMCIIGAAVSFLTRDQPNVQ
 721  FCIVALVIIFCSTITLCLVFVPKLITLRTNPDAATQNRRFQFTQNQKKEDSKTSTSVTSV
 781  NQASTSRLEGLQSENHRLRMKITELDKDLEEVTMQLQDTPEKTTYIKQNHYQELNDILNL
 841  GNFTESTDGGKAILKNHLDQNPQLQWNTTEPSRTCKDPIEDINSPEHIQRRLSLQLPILH
 901  HAYLPSIGGVDASCVSPCVSPTASPRHRHVPPSFRVMVSGL
```

### Canonical ortholog sequences

**Mouse — Gabbr2** (`Q80T41` · 940 aa)

```
   1  MASPPSSGQPRPPPPPPPPARLLLPLLLSLLLSLAPGAWGWARGAPRPPPSSPPLSIMGL
  61  MPLTKEVAKGSIGRGVLPAVELAIEQIRNESLLRPYFLDLRLYDTECDNAKGLKAFYDAI
 121  KYGPNHLMVFGGVCPSVTSIIAESLQGWNLVQLSFAATTPVLADKKKYPYFFRTVPSDNA
 181  VNPAILKLLKHFRWRRVGTLTQDVQRFSEVRNDLTGVLYGEDIEISDTESFSNDPCTSVK
 241  KLKGNDVRIILGQFDQNMAAKVFCCAFEESMFGSKYQWIIPGWYEPAWWEQVHVEANSSR
 301  CLRRSLLAAMEGYIGVDFEPLSSKQIKTISGKTPQQYEREYNSKRSGVGPSKFHGYAYDG
 361  IWVIAKTLQRAMETLHASSRHQRIQDFNYTDHTLGRIILNAMNETNFFGVTGQVVFRNGE
 421  RMGTIKFTQFQDSREVKVGEYNAVADTLEIINDTIRFQGSEPPKDKTIILEQLRKISLPL
 481  YSILSALTILGMIMASAFLFFNIKNRNQKLIKMSSPYMNNLIILGGMLSYASIFLFGLDG
 541  SFVSEKTFETLCTVRTWILTVGYTTAFGAMFAKTWRVHAIFKNVKMKKKIIKDQKLLVIV
 601  GGMLLIDLCILICWQAVDPLRRTVERYSMEPDPAGRDISIRPLLEHCENTHMTIWLGIVY
 661  AYKGLLMLFGCFLAWETRNVSIPALNDSKYIGMSVYNVGIMCIIGAAVSFLTRDQPNVQF
 721  CIVALVIIFCSTITLCLVFVPKLITLRTNPDAATQNRRFQFTQNQKKEDSKTSTSVTSVN
 781  QASTSRLEGLQSENHRLRMKITELDKDLEEVTMQLQDTPEKTTYIKQNHYQELNDILSLG
 841  NFTESTDGGKAILKNHLDQNPQLQWNTTEPSRTCKDPIEDINSPEHIQRRLSLQLPILHH
 901  AYLPSIGGVDASCVSPCVSPTASPRHRHVPPSFRVMVSGL
```

**Cynomolgus — GABBR2** (`A0A2K5VY83` · 938 aa)

```
   1  MASRSSGPPGPPPPPPPPPARLLLLLLPLLLPLAPGAWGWARGAHPPPSSPPLSIMGLMP
  61  LTKEVAKGSIGRGVLPAVELAIEQIRNESLLRPYFLDLRLYDTECDNAKGLKAFYDAIKY
 121  GPNHLMVFGGVCPSVTSIIAESLQGWNLVQLSFAATTPVLADKKKYPYFFRTVPSDNAVN
 181  PAILKLLKHYQWKRVGTLTQDVQRFSEVRNDLTGVLYGEDIEISDTESFSNDPCTSVKKL
 241  KGNDVRIILGQFDQNMAAKVFCCAYEENMYGSKYQWIIPGWYEPSWWEQVHTEANSSRCL
 301  RKNLLAAMEGYIGVDFEPLSSKQIKTISGKTPQQYEREYNNKRSGVGPSKFHGYAYDGIW
 361  VIAKTLQRAMETLHASSRHQRIQDFNYTDHTLGRIILNAMNETNFFGVTGQVVFRNGERM
 421  GTIKFTQFQDSREVKVGEYNAVADTLEIINDTIRFQGSEPPKDKTIILEQLRKISLPLYS
 481  ILSALTILGMIMASAFLFFNIKNRNQKLIKMSSPYMNNLIILGGMLSYASIFLFGLDGSF
 541  VSEKTFETLCTVRTWILTVGYTTAFGAMFAKTWRVHAIFKNVKMKKKIIKDQKLLVIVGG
 601  MLLIDLCILICWQAVDPLRRTVEKYSMEPDPAGRDISIRPLLEHCENTHMTIWLGIVYAY
 661  KGLLMLFGCFLAWETRNVSIPALNDSKYIGMSVYNVGIMCIIGAAVSFLTRDQPNVQFCI
 721  VALVIIFCSTITLCLVFVPKLITLRTNPDAATQNRRFQFTQNQKKEDSKTSTSVTSVNQA
 781  STSRLEGLQSENHRLRMKITELDKDLEEVTMQLQDTPEKTTYIKQNHYQELNDILNLGNF
 841  TESTDGGKAILKNHLDQNPQLQWNTTEPSRTCKDPIEDINSPEHIQRRLSLQLPILHHAY
 901  LPSIGGVDASCVSPCVSPTASPRHRHVPPSFRVMVSGL
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`O75899`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMM
 481  MMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOO
 541  OOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIMMM
 601  MMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMM
 661  MMMMMMMMMMMMMMMMIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMMMOOOOMMM
 721  MMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 781  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 841  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 901  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Mouse ortholog — Gabbr2** (`Q80T41`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMM
 481  MMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOO
 541  OOOOOOOOOMMMMMMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIMMMM
 601  MMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMM
 661  MMMMMMMMMMMMMMMIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMMMOOOOMMMM
 721  MMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 781  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 841  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 901  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Cynomolgus ortholog — GABBR2** (`A0A2K5VY83`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMM
 481  MMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOOOO
 541  OOOOOOOMMMMMMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIMMMMMM
 601  MMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMM
 661  MMMMMMMMMMMMMIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMMMOOOOMMMMMM
 721  MMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 781  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 841  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 901  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence high — *
