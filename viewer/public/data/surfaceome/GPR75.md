# GPR75 — Surface Accessibility Brief

*Schema v2.6.0 · generated 2026-06-07T02:42:21.474347Z · model `claude-sonnet-4-6`*

> GPR75 is a class A orphan GPCR with a canonical 7TM architecture and an extracellular N-terminus bearing N-glycosylation sites, conferring constitutive surface accessibility in neurons and vascular cells. Cryo-EM reveals a collapsed orthosteric pocket (moderate epitope-masking risk). Endogenous 3xFlag-knockin studies confirm ciliary plasma-membrane localization in hypothalamic neurons; VPS35-mediated retromer recycling supports hepatocyte surface residence in MASH. Surface accessibility is tissue- and disease-state-gated: absent in healthy liver, strongly upregulated in MASH hepatocytes, and ciliary-restricted in hypothalamic neurons. No shed or secreted decoy form identified.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:4526](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:4526) |
| UniProt | [O95800](https://www.uniprot.org/uniprotkb/O95800) |
| NCBI Gene | [10936](https://www.ncbi.nlm.nih.gov/gene/10936) |
| Ensembl | [ENSG00000119737](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000119737) |
| Subcategory | GPCR |
| Surface accessibility | High |
| Confidence | Moderate |
| Evidence grade | Supportive but indirect |
| Triage signal | Likely accessible |
| Headline risks | Epitope Masked |

## 1. Executive summary

**Constitutively surface-accessible on neurons and cerebrovascular cells; disease-state-induced surface expression in MASH hepatocytes and activated microglia; ciliary-restricted in hypothalamic neurons, limiting systemic binder access to that compartment.**

GPR75 is a class A orphan GPCR with a canonical 7TM architecture and an extracellular N-terminus bearing N-glycosylation sites, conferring constitutive surface accessibility in neurons and vascular cells. Cryo-EM reveals a collapsed orthosteric pocket (moderate epitope-masking risk). Endogenous 3xFlag-knockin studies confirm ciliary plasma-membrane localization in hypothalamic neurons; VPS35-mediated retromer recycling supports hepatocyte surface residence in MASH. Surface accessibility is tissue- and disease-state-gated: absent in healthy liver, strongly upregulated in MASH hepatocytes, and ciliary-restricted in hypothalamic neurons. No shed or secreted decoy form identified.

**Family / classification** — UniProt family: G-protein coupled receptor 1 family · HGNC gene group(s): G protein-coupled receptors, Class A orphans · functional class: Receptor.

**Triage first-pass reasoning** — GPR75 is a Class A orphan GPCR (UniProt O95800). GPCRs are seven-transmembrane proteins with extracellular loops and an extracellular N-terminus that are constitutively trafficked to the plasma membrane as their primary functional location. GPR75 has been detected at the cell surface in heterologous expression systems and is studied as a potential therapeutic target (notably linked to obesity protection in loss-of-function carriers). Its topology — multipass TM with exposed extracellular loops and N-terminus — places it firmly in the surface-accessible category without requiring any conditional stimulus.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=Moderate · subcategory=GPCR · ecd=Moderate |
| Classification | reason=Classical Surface Receptor · family=Receptor · state-dependence=Moderate · induction-trigger=Stress Hypoxia |
| Expression | level=Moderate · breadth=Restricted · specificity=Surface Dominant · low-endogenous=false · tumor-associated=true · orphan-receptor=false · OE-precedent=false |
| Risks | shed=false · secreted=false · co-receptor=Modulatory · masking=true · restricted-subdomain=true |
| Evidence | grade=Supportive but indirect · density=High · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=74.2% · cyno=98.9% |
| Paralogs | max %ECD identity = 35.7% |
| Topology | TM=7 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: High expression in brain neurons and cerebrovascular cells across multiple species (a2_evi_02, a2_evi_07, a2_evi_08); moderate in endothelial/vascular smooth muscle cells (a2_evi_11, a2_evi_13); absent in healthy liver and low in peripheral immune organs (a2_evi_09, a2_evi_22). Overall moderate given CNS-dominant but tissue-restricted profile.
- *Expression breadth*: GPR75 expression is concentrated in brain neurons and cerebrovascular cells, with disease-state induction in hepatocytes (MASH), renal macrophages (S-AKI), and microglia (TBI) (a2_evi_07, a2_evi_11, a2_evi_19, a2_evi_20, a2_evi_22); low in thymus/spleen and absent from astrocytes (a2_evi_09, a2_evi_12). Not pan-tissue.
- *Surface specificity*: Canonical 7TM GPCR; endogenous knockin confirms ciliary PM localization in neurons (a1_evi_12, a1_evi_14); photoaffinity crosslinking confirms membrane engagement in endothelial cells (a1_evi_08, a1_evi_09); retromer recycling confirms hepatocyte PM residence (a1_evi_11). Agonist-induced internalization is transient (a2_evi_18).
- *Low endogenous expression*: Derived from expression_level='moderate' (not low/absent → not flagged). High expression in brain neurons and cerebrovascular cells across multiple species (a2_evi_02, a2_evi_07, a2_evi_08); moderate in endothelial/vascular smooth muscle cells (a2_evi_11, a2_evi_13); absent in healthy liver and low in peripheral immune organs (a2_evi_09, a2_evi_22). Overall moderate given CNS-dominant but tissue-restricted profile.
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Supportive but indirect

GPR75 is a canonical class A GPCR with a well-established 7TM topology (extracellular N-terminus, 3 ECLs) confirmed by cryo-EM, computational prediction, and GPCRdb — topology itself is deterministic for surface ECD exposure. The strongest surface-supporting evidence comes from: (1) endogenous 3xFlag-GPR75 knockin mice showing ciliary PM localization in hypothalamic neurons by IF with an internal specificity control (L144P fails to localize); (2) photoaffinity crosslinking of a 20-HETE analogue on membrane fractions of human endothelial cells with competitive displacement control; (3) VPS35-mediated retromer recycling to the hepatocyte PM. However, none of these constitute a clean non-permeabilized surface staining or live-cell flow cytometry experiment with validated antibody and KO control. The IF studies do not specify permeabilization status, and the membrane-fraction photoaffinity assay is indirect fractionation-based. The sum is strong indirect evidence anchored by canonical topology — graded `supportive_but_indirect`.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Moderate | Computational 7TM topology prediction; establishes canonical GPCR architecture with extracellular N-terminus but not direct surface proof. |
| a1_evi_02 | Tangential | Low | Review-level topology description; confirms large extracellular N-terminus but no direct surface assay. |
| a1_evi_03 | Tangential | Low | Review assertion confirming N-glycosylation on extracellular N-terminus; topology-based, not direct surface accessibility proof. |
| a1_evi_04 | Tangential | Low | GPCRdb-derived topology diagram; database annotation confirming extracellular N-terminus and ECLs. |
| a1_evi_05 | Tangential | Moderate | Cryo-EM confirms 7TM with collapsed ECD; ambiguous for accessibility but confirms extracellular face exists. |
| a1_evi_06 | Supports Surface | Moderate | 3xFlag N-terminal knockin mouse; tag at extracellular N-terminus implies surface-accessible N-terminus in native context. |
| a1_evi_07 | Expression Only | Low | C-terminal antibody WB in endothelial cells; bulk protein detection, no surface fractionation. |
| a1_evi_08 | Supports Surface | Moderate | Photoaffinity crosslinking on membrane fractions of human endothelial cells; ligand engages membrane-localized GPR75. |
| a1_evi_09 | Supports Surface | Moderate | Selectivity competition control (20-HETE displaces, 12-HETE does not) strengthens membrane-engagement claim. |
| a1_evi_10 | Tangential | Low | Exogenous signal sequence construct; overexpression artifact risk noted; indirect/ambiguous for native routing. |
| a1_evi_11 | Supports Surface | Moderate | VPS35-mediated retromer recycling to hepatocyte plasma membrane; functional evidence of PM localization. |
| a1_evi_12 | Supports Surface | Moderate | Endogenous 3xFlag-GPR75 detected in primary cilia (plasma membrane subdomain) of hypothalamic neurons by IF. |
| a1_evi_13 | Supports Surface | Moderate | L144P mutant fails to localize to cilia; within-experiment specificity control validating WT ciliary surface signal. |
| a1_evi_14 | Supports Surface | Moderate | Endogenous knockin confirms ciliary PM localization in hypothalamic neurons; permeabilization status unstated but cilia are PM extensions. |
| a1_evi_15 | Expression Only | Moderate | WB of total brain tissue from knockin mice; confirms protein expression in brain but no surface fractionation. |
| a1_evi_16 | Expression Only | Low | Flow cytometry in SH-SY5Y; permeabilization status unspecified, cannot confirm surface accessibility. |
| a1_evi_17 | Expression Only | Low | WB of total lysate in rat cortical neurons and SH-SY5Y; bulk protein detection only. |
| a1_evi_18 | Expression Only | Low | IF on rat brain slices and cultured human cerebrovascular cells; permeabilization status not specified. |
| a1_evi_19 | Expression Only | Low | IF in rat cerebrovascular endothelial and smooth muscle cells; permeabilization not specified, no surface specificity. |
| a1_evi_20 | Expression Only | Low | WB and fluorescence microscopy in PC-3 prostate cancer cells; no membrane fractionation or nonperm protocol. |
| a1_evi_21 | Expression Only | Low | Gene expression and protein levels in CLD patient samples; unspecified methods, no surface assay. |
| a1_evi_22 | Expression Only | Low | RNAscope ISH for GPR75 mRNA in hippocampal neurons; RNA-level only. |

### Flow cytometry (1 method)

#### Unknown — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-GPR75 — Unknown epitope; Unknown; None validation (None); Antibody clone, vendor, permeabilization status, and isotype controls not specified in the source abstract.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| SH-SY5Y human neuroblastoma cells — flow cytometry confirms GPR75 expression; staining conditions (permeabilized vs non-permeabilized) not stated | Established Cell Line | Moderate | 1 |

### Immunofluorescence (4 methods)

#### Permeabilized IF — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Knock In Tag*

**Antibodies**

- anti-FLAG — Extracellular epitope; Unknown; Strong validation (Genetic KO); Detects 3xFlag tag inserted in-frame at N-terminus of endogenous GPR75 by CRISPR knockin; L144P mutant loss-of-cilia signal provides within-experiment specificity control.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Mouse hypothalamic neurons — wild-type 3xFlag-GPR75 localizes to primary cilia; L144P (Thinner) mutant fails to localize to cilia | Ex Vivo | Moderate | 2 |

#### Permeabilized IF — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Knock In Tag*

**Antibodies**

- anti-FLAG — Extracellular epitope; Unknown; Strong validation (Genetic KO); Detects 3xFlag tag at N-terminus of endogenous GPR75 (CRISPR knockin, PMC11444156). L144P and human obesity-protective variants fail to localize to cilia, confirming specificity of ciliary signal.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Mouse hypothalamic cells — endogenous 3xFlag-GPR75 localizes to primary cilia; Thinner mutation L144P and human GPR75 obesity-protective variants fail to localize to cilia | Ex Vivo | Moderate | 1 |

#### Permeabilized IF — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-GPR75 — Unknown epitope; Unknown; None validation (None); Antibody clone and vendor not specified in source abstract (PMC7499024); used for fluorescent immunostaining on brain tissue slices and cultured vascular cells.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Rat brain tissue slices (SD, Dahl SS, CYP4A1 transgenic) — fluorescent immunostaining; GPR75 expressed in endothelial cells, vascular smooth muscle cells, and glial limiting membrane of pial arteries and penetrating arterioles; absent from capillary endothelium | Ex Vivo | Moderate | 2 |
| Cultured human cerebral pericytes and cerebral vascular smooth muscle cells — fluorescent immunostaining | Primary Human Cell | Moderate | 1 |

#### Permeabilized IF — Expression Only · Unclear

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-GPR75 — Unknown epitope; Unknown; None validation (None); Antibody clone and vendor not specified in source abstract (PMC6957769); combined WB and fluorescence microscopy; no membrane-specific staining protocol described.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| PC-3 human androgen-insensitive prostate cancer cells — protein distribution assessed by fluorescence microscopy; no surface-specific protocol described | Established Cell Line | Moderate | 1 |

### Functional surface assay (2 methods)

#### Unknown — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human endothelial cells — photoaffinity crosslinking with 20-APheDa on membrane fractions yielded dominant band at 47–49 kDa; labeling competed by 20-HETE (100 µM) but not 12-HETE, confirming specific GPR75–ligand engagement at the plasma membrane | Primary Human Cell | Moderate | 2 |

#### Unknown — Supports Membrane Association · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human hepatocytes — VPS35-mediated retromer recycling returns GPR75 to the plasma membrane, reducing degradation during MASH progression; functional evidence of surface-resident receptor pool | Primary Human Cell | Moderate | 1 |

### Other (5 methods)

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-GPR75 (Santa Cruz Biotechnology · sc-164538) — Intracellular epitope; Polyclonal; None validation (None); Goat polyclonal raised against C-terminal peptide of human GPR75 (S-14); recognizes single band at 54–55 kDa. Discontinued product.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human endothelial cells — pull-down and western blot yielding single specific band at 54–55 kDa | Primary Human Cell | Moderate | 1 |

#### Whole Cell Proteomics — Expression Only · Unclear

*Permeabilization: Unknown · expression: Knock In Tag*

**Antibodies**

- anti-FLAG — Extracellular epitope; Unknown; Strong validation (Genetic KO); Detects 3xFlag tag at N-terminus of endogenous GPR75 by CRISPR knockin; protein exclusively detected in brain tissue.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Mouse brain tissue — 3xFlag-GPR75 knockin mice; endogenous protein exclusively expressed in brain with consistent expression across brain regions | Ex Vivo | Moderate | 1 |

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-GPR75 — Unknown epitope; Unknown; None validation (None); Antibody clone and vendor not specified in the source; detects ~59 kDa band in rat and human neural cells.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Rat cortical neurons — western blot of total cell lysate; immunoreactive band at ~59 kDa | Primary Human Cell | Moderate | 1 |
| Differentiated SH-SY5Y human neuroblastoma cells — western blot of total cell lysate; immunoreactive band at ~59 kDa | Established Cell Line | Moderate | 1 |

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human chronic liver disease / MASLD patient samples — protein level evaluation by unspecified method; increased expression observed during MASLD progression | Patient Sample | Moderate | 1 |

#### Unknown — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Overexpression*

*Overexpression construct* — SP source: Exogenous · cleavable signal sequence (common forward primer). *(cites: a1_evi_10)*

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Human endothelial cells — C-terminal antibody WB of total cell lysate | Primary Human Cell | Bulk Protein | Moderate | 1 |
| Mouse brain (multiple regions) — 3xFlag knockin, WB of total brain tissue | Ex Vivo | Bulk Protein | Moderate | 1 |
| SH-SY5Y human neuroblastoma cells — flow cytometry (permeabilization unspecified) and qPCR | Established Cell Line | Bulk Protein | Moderate | 1 |
| Rat cortical neurons and differentiated SH-SY5Y — WB of total cell lysate | Primary Human Cell | Bulk Protein | Moderate | 1 |
| Rat brain slices and cultured human cerebral pericytes / vascular smooth muscle cells — fluorescent immunostaining (permeabilization unspecified) | Ex Vivo | IHC Protein | Moderate | 2 |
| PC-3 androgen-insensitive prostate cancer cells — WB and fluorescence microscopy (surface specificity unspecified) | Established Cell Line | IHC Protein | Moderate | 1 |
| Human chronic liver disease / MASLD patient samples — unspecified gene expression and protein level assays | Patient Sample | Unknown | Moderate | 1 |
| Hippocampal neurons — RNAscope in situ hybridization for GPR75 mRNA | Unknown | Single Cell RNA | Moderate | 1 |

## 4. Biological context

**Biological-context grade** · Rich

All four A2 axes are well-populated from multiple independent sources. Expression is mapped across brain (neurons, vasculature), retina, liver, kidney, and prostate from primary tissue and cell lines. Subcellular localization is pinned to primary cilia (hypothalamic neurons) and plasma membrane (endothelial/vascular cells). Anatomical accessibility is characterized for cerebral vessels vs. capillaries vs. astrocytes. Modulation evidence covers ligand-induced downregulation, serum starvation upregulation, disease-state (TBI, MASH, DCD) induction, and mutation-driven ciliary mistargeting. Picture is internally coherent. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_07, a2_evi_08, +19)*

**Expression × cell type × disease context**

| Tissue | Cell type | Disease context | Level (protein) | Cell states |
|---|---|---|---|---|
| retina | retinal pigment epithelium | Normal | High | — |
| retina | perivascular cells surrounding retinal arterioles | Normal | Moderate | — |
| brain | — | Normal | High | — |
| cerebellum | — | Normal | High | — |
| cerebral cortex | — | Normal | High | — |
| cerebral cortex | cortical neurons | Normal | Moderate | — |
| hippocampus | neurons (NeuN+) | Normal | Moderate | — |
| brain | neurons | Normal | High | — |
| hypothalamus | neurons | Normal | High | — |
| thymus | — | Normal | Low | — |
| spleen | — | Normal | Low | — |
| heart | — | Normal | High | — |
| brain vasculature | endothelial cells | Normal | Moderate | — |
| brain vasculature | vascular smooth muscle cells | Normal | Moderate | — |
| brain vasculature | glial limiting membrane cells of pial arteries and penetrating arterioles | Normal | Moderate | — |
| brain | astrocytes | Normal | Absent | — |
| vasculature | microvascular endothelial cells | Normal | Moderate | — |
| vasculature | vascular smooth muscle cells | Normal | Moderate | — |
| prostate | prostate cancer cells | Tumor (prostate cancer) | Moderate | serum-starved, ligand-stimulated |
| brain | microglia | Other Disease (traumatic brain injury (immature brain)) | High | activated |
| kidney | macrophages | Other Disease (sepsis-associated acute kidney injury) | High | — |
| hippocampus | neurons | Other Disease (diabetic cognitive dysfunction / hyperglycemia) | High | stress-induced |
| liver | hepatocytes | Normal | Absent | — |
| liver | hepatocytes | Other Disease (metabolic dysfunction-associated steatohepatitis (MASH)) | High | — |
| vasculature | endothelial cells | Other Disease (methionine-induced hyperhomocysteinemia) | High | stress-induced |

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- Endosome · after 20-HETE ligand stimulation (agonist-induced internalization) *(cites: a2_evi_18)*

**Membrane subdomains**: Primary Cilium

**Anatomical accessibility**

- hypothalamic neurons (primary cilia) — Ciliary · *Restricted*: GPR75 accumulates in primary cilia of hypothalamic neurons, a membrane subdomain sequestered behind the blood-brain barrier and further compartmentalised within the ciliary pocket; systemically delivered binders face dual barriers (BBB + ciliary restriction).
- cerebral vasculature (endothelial cells and vascular smooth muscle cells of pial arteries and penetrating arterioles) — Blood Interstitial Facing · *Favorable*: GPR75 is expressed on endothelial cells and VSMCs of pial arteries and penetrating arterioles. Luminal endothelial surfaces of larger cerebral vessels are directly blood-facing, making GPR75 here accessible to circulating binders without requiring BBB penetration.
- hepatocytes (MASH liver) — Blood Interstitial Facing · *Context Dependent*: In MASH, GPR75 is recycled to the hepatocyte plasma membrane by VPS35. Hepatocytes are exposed to sinusoidal blood flow (fenestrated endothelium), making surface GPR75 potentially accessible to systemic binders, but only under disease conditions where expression is upregulated.

**Accessibility modulation**

- *Cell State Induced* · trigger: Nutrient Deprivation: PC-3 prostate cancer cells in complete medium → PC-3 prostate cancer cells after 24h serum starvation — GPR75 total protein abundance increases by ~91% after 24h serum starvation vs. complete medium in PC-3 prostate cancer cells, suggesting upregulation of receptor available for surface expression under nutrient-deprived conditions. *(→ Nutrient Deprivation Elevates GPR75 Protein Levels, Likely Increasing The Pool Available For Surface Display And Binder Engagement In Metabolically Stressed Cancer Cells.)* *(cites: a2_evi_17)*
- *Cell State Induced* · trigger: Other: PC-3 prostate cancer cells under basal conditions → PC-3 prostate cancer cells stimulated with 20-HETE (0.1 nM, 12h) — Ligand stimulation with 20-HETE reduces GPR75 protein abundance by ~78% in PC-3 cells (consistent with agonist-induced internalization/downregulation); antagonist AAA reverses this; antagonist alone increases GPR75 by 34%. *(→ Agonist-Driven Receptor Internalization Substantially Depletes The Surface-Accessible GPR75 Pool; Binder Access Would Be Reduced In The Presence Of Endogenous 20-HETE. Blocking Endogenous Ligand Can Increase Surface Availability.)* *(cites: a2_evi_18)*
- *Disease State Induced*: resting microglia in healthy immature rat brain → activated microglia after traumatic brain injury (TBI) in immature rat brain — GPR75 expression is upregulated in microglia following TBI in the immature brain, alongside elevated CYP4A and activation of Src/EGFR/NF-κB signaling. *(→ Disease-Induced Upregulation Of GPR75 In Activated Microglia After TBI Increases Receptor Density At The Microglial Surface, Potentially Expanding Binder Accessibility In The TBI Neuroinflammatory Milieu.)* *(cites: a2_evi_19)*
- *Disease State Induced*: healthy human liver / hepatocytes → hepatocytes in metabolic dysfunction-associated steatohepatitis (MASH) — GPR75 protein is nearly absent in healthy human liver but significantly increases in hepatocytes during MASH; VPS35-mediated retromer recycling stabilizes GPR75 by returning it to the hepatocyte plasma membrane in MASH. *(→ In MASH, Elevated GPR75 Is Actively Recycled To The Hepatocyte Plasma Membrane, Markedly Increasing Surface-Accessible Receptor. Binder Engagement Would Be Feasible In MASH But Not In Healthy Liver.)* *(cites: a2_evi_22, a2_evi_23)*
- *Disease State Induced*: hippocampal neurons under normoglycemic conditions → hippocampal neurons (HT22 cells) under hyperglycemia / diabetic cognitive dysfunction (DCD) — GPR75 is upregulated in hippocampal neurons in diabetic cognitive dysfunction, with co-localization with AMPK confirmed by immunofluorescence and co-IP in high-glucose-treated HT22 cells. *(→ GPR75 Upregulation In Hippocampal Neurons Under Diabetic/Hyperglycemic Conditions Increases Receptor Density; Elevated Surface Presence Could Support Targeting In The CNS Diabetic Disease Context.)* *(cites: a2_evi_21)*
- *Disease State Induced*: null → null — In sepsis-associated acute kidney injury (S-AKI) mice, GPR75 is highly expressed in renal macrophages; siRNA knockdown reduces oxidative stress and inflammatory cytokine secretion in macrophage/tubular epithelial coculture. *(→ GPR75 Is Upregulated In Renal Macrophages Specifically In The S-AKI Disease Context; If Surface-Expressed, It Represents An Accessible Target In The Inflamed Kidney During Sepsis.)* *(cites: a2_evi_20)*
- *Post Translational Dependent*: wild-type hypothalamic neurons (GPR75 traffics to primary cilia) → L144P (Thinner allele) mutant hypothalamic neurons (GPR75 fails ciliary targeting) — The L144P Thinner missense mutation abolishes GPR75 ciliary localization in hypothalamic neurons; mutant protein fails to traffic to the primary cilium surface, correlating with resistance to diet-induced fat accumulation. *(→ Loss Of Ciliary Targeting By The L144P Mutation Removes GPR75 From The Primary Cilium Membrane Subdomain; Binders Targeting The Ciliary Surface Pool Would Not Engage The Mutant Receptor, And Total Accessible Surface Receptor Is Reduced.)* *(cites: a2_evi_25, a2_evi_26)*
- *Tissue Restricted Surface* · lineage: Neural: null → null — GPR75 surface-level functional expression is documented in neural cells (cortical neurons, hippocampal neurons, hypothalamic neurons, neuroblastoma) and CNS-associated vascular cells (endothelium, vascular smooth muscle, glial limiting membrane of pial arteries), but not in capillary endothelium or astrocytes. *(→ GPR75 Surface Accessibility Is Restricted To Neurons And Select Large-Vessel Vascular Cells In The CNS; Capillary Endothelium And Astrocytes Are Not Accessible Targets, Limiting Systemic Binder Access.)* *(cites: a2_evi_04, a2_evi_05, a2_evi_11, a2_evi_12, a2_evi_13, a2_evi_14)*

**Restricted-subdomain distribution**

- present: true
- severity: Moderate
- evidence: Strong
- domain: Ciliary
- rationale: Endogenous 3xFlag-GPR75 (knockin) accumulates specifically in the primary cilia of hypothalamic neurons in mice (a1_evi_12, a1_evi_14, a2_evi_25). The Thinner allele (L144P) fails to localize to cilia (a1_evi_13, a2_evi_26). Ciliary membrane is a restricted subdomain inaccessible to most systemic binders in the CNS context, raising a real accessibility concern for hypothalamic neuronal GPR75. Non-neuronal cells (endothelium, hepatocytes) do not show ciliary restriction (a1_evi_11, a2_evi_13).
- cites: a1_evi_12, a1_evi_13, a1_evi_14, a2_evi_25, a2_evi_26

**Co-receptor requirements**

- dependency: Modulatory
- evidence basis: Trafficking
- partners: VPS35
- rationale: GPR75 is a canonical 7TM GPCR that traffics to the plasma membrane independently (a1_evi_01, a1_evi_11). VPS35/retromer recycles GPR75 back to the hepatocyte membrane and reduces its degradation during MASH, modulating surface abundance but not acting as an obligate partner for initial surface delivery (a1_evi_11, a2_evi_23). No obligate co-receptor or chaperone required for surface expression.
- cites: a1_evi_01, a1_evi_11, a2_evi_23

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | O95800 | ref | ref | 7 | 89 aa | 296 aa | 0 aa | Extracellular→Cytoplasmic | — |
| Isoform | O95800 | O95800 | — | — | 7 | 89 aa | 296 aa | 0 aa | Extracellular→Cytoplasmic | — |
| Isoform | O95800 | O95800 | — | — | 7 | 89 aa | 296 aa | 0 aa | Extracellular→Cytoplasmic | — |
| Mouse ortholog | Gpr75 | [Q6X632](https://www.uniprot.org/uniprotkb/Q6X632) | 88.0% | 74.2% | 7 | 89 aa | — | — | — | moderate |
| Cynomolgus ortholog | GPR75 | [A0A7N9DAV0](https://www.uniprot.org/uniprotkb/A0A7N9DAV0) | 99.1% | 98.9% | 7 | 89 aa | — | — | — | high (≥85%) |
| Paralog | OR9G1 | [Q8NH87](https://www.uniprot.org/uniprotkb/Q8NH87) | 12.0% | 35.7% | — | — | — | — | — | low-risk |
| Paralog | OR51F1 | [A6NGY5](https://www.uniprot.org/uniprotkb/A6NGY5) | 8.3% | 30.7% | — | — | — | — | — | low-risk |
| Paralog | GPR19 | [Q15760](https://www.uniprot.org/uniprotkb/Q15760) | 9.4% | 28.7% | — | — | — | — | — | low-risk |
| Paralog | OR11A1 | [Q9GZK7](https://www.uniprot.org/uniprotkb/Q9GZK7) | 10.7% | 26.5% | — | — | — | — | — | low-risk |
| Paralog | OR11G2 | [Q8NGC1](https://www.uniprot.org/uniprotkb/Q8NGC1) | 12.6% | 26.4% | — | — | — | — | — | low-risk |
| Paralog | NPY1R | [P25929](https://www.uniprot.org/uniprotkb/P25929) | 12.8% | 25.8% | — | — | — | — | — | low-risk |
| Paralog | TACR2 | [P21452](https://www.uniprot.org/uniprotkb/P21452) | 13.1% | 25.0% | — | — | — | — | — | low-risk |
| Paralog | NPY4R | [P50391](https://www.uniprot.org/uniprotkb/P50391) | 10.6% | 25.0% | — | — | — | — | — | low-risk |
| Paralog | NPY4R2 | [P0DQD5](https://www.uniprot.org/uniprotkb/P0DQD5) | 10.6% | 25.0% | — | — | — | — | — | low-risk |
| Paralog | PRLHR | [P49683](https://www.uniprot.org/uniprotkb/P49683) | 12.8% | 24.7% | — | — | — | — | — | low-risk |
| Paralog | OR11H2 | [Q8NH07](https://www.uniprot.org/uniprotkb/Q8NH07) | 12.0% | 24.7% | — | — | — | — | — | low-risk |
| Paralog | OR11H1 | [Q8NG94](https://www.uniprot.org/uniprotkb/Q8NG94) | 11.9% | 24.7% | — | — | — | — | — | low-risk |
| Paralog | PROKR1 | [Q8TCW9](https://www.uniprot.org/uniprotkb/Q8TCW9) | 11.5% | 23.6% | — | — | — | — | — | low-risk |
| Paralog | OR11H12 | [B2RN74](https://www.uniprot.org/uniprotkb/B2RN74) | 11.7% | 23.5% | — | — | — | — | — | low-risk |
| Paralog | GPR83 | [Q9NYM4](https://www.uniprot.org/uniprotkb/Q9NYM4) | 14.4% | 23.0% | — | — | — | — | — | low-risk |
| Paralog | TACR3 | [P29371](https://www.uniprot.org/uniprotkb/P29371) | 15.7% | 22.7% | — | — | — | — | — | low-risk |
| Paralog | NPY2R | [P49146](https://www.uniprot.org/uniprotkb/P49146) | 14.3% | 22.5% | — | — | — | — | — | low-risk |
| Paralog | OR9A4 | [Q8NGU2](https://www.uniprot.org/uniprotkb/Q8NGU2) | 11.1% | 22.4% | — | — | — | — | — | low-risk |
| Paralog | OR9A2 | [Q8NGT5](https://www.uniprot.org/uniprotkb/Q8NGT5) | 10.7% | 21.2% | — | — | — | — | — | low-risk |
| Paralog | MCHR1 | [Q99705](https://www.uniprot.org/uniprotkb/Q99705) | 11.1% | 20.7% | — | — | — | — | — | low-risk |
| Paralog | OR11H7 | [Q8NGC8](https://www.uniprot.org/uniprotkb/Q8NGC8) | 11.5% | 20.6% | — | — | — | — | — | low-risk |
| Paralog | PROKR2 | [Q8NFJ6](https://www.uniprot.org/uniprotkb/Q8NFJ6) | 11.7% | 20.2% | — | — | — | — | — | low-risk |
| Paralog | NPY5R | [Q15761](https://www.uniprot.org/uniprotkb/Q15761) | 11.3% | 20.2% | — | — | — | — | — | low-risk |
| Paralog | OR11H6 | [Q8NGC7](https://www.uniprot.org/uniprotkb/Q8NGC7) | 10.7% | 19.7% | — | — | — | — | — | low-risk |
| Paralog | OR10X1 | [Q8NGY0](https://www.uniprot.org/uniprotkb/Q8NGY0) | 10.7% | 19.0% | — | — | — | — | — | low-risk |
| Paralog | GPR88 | [Q9GZN0](https://www.uniprot.org/uniprotkb/Q9GZN0) | 10.4% | 18.6% | — | — | — | — | — | low-risk |
| Paralog | OR11H4 | [Q8NGC9](https://www.uniprot.org/uniprotkb/Q8NGC9) | 12.2% | 18.4% | — | — | — | — | — | low-risk |
| Paralog | MCHR2 | [Q969V1](https://www.uniprot.org/uniprotkb/Q969V1) | 10.2% | 17.5% | — | — | — | — | — | low-risk |
| Paralog | GPR50 | [Q13585](https://www.uniprot.org/uniprotkb/Q13585) | 11.5% | 15.6% | — | — | — | — | — | low-risk |
| Paralog | TACR1 | [P25103](https://www.uniprot.org/uniprotkb/P25103) | 14.6% | 15.2% | — | — | — | — | — | low-risk |
| Paralog | MTNR1A | [P48039](https://www.uniprot.org/uniprotkb/P48039) | 13.1% | 14.5% | — | — | — | — | — | low-risk |
| Paralog | MTNR1B | [P49286](https://www.uniprot.org/uniprotkb/P49286) | 12.4% | 12.5% | — | — | — | — | — | low-risk |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak

**Secreted form**

- present: false
- severity: Low
- evidence: Weak

**ECD size assessment**

- ECD class: Moderate
- rationale: ECD length 89 residues (60-199) -> moderate; computed deterministically from DeepTMHMM topology.

**Epitope masking**

- severity: Moderate
- evidence: Strong
- mechanism: Conformational
- rationale: Cryo-EM structures reveal a completely collapsed extracellular domain that eliminates the traditional orthosteric binding pocket; the HRL motif replaces DRY and a Lys134-Asp210 salt bridge locks an active-like conformation even without ligand (a1_evi_05). This structural collapse constitutively occludes the ECD surface accessible to binders targeting a conventional GPCR pocket. Deterministic AF2 prior indicates no homo-oligomer (is_homo_oligomer=false), so oligomerization is not invoked. No partner-complex masking evidence in the ledger.
- cites: a1_evi_05

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-O95800-F1](https://alphafold.ebi.ac.uk/entry/O95800) |
| AFDB version | v6 |
| ECD mean pLDDT | 65.4 |
| ECD disordered fraction | 57.3% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/O95800) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [O95800](https://alphafold.ebi.ac.uk/entry/O95800) | AlphaFold DB (AF-O95800-F1, v6) |
| Mouse ortholog (Gpr75) | [Q6X632](https://alphafold.ebi.ac.uk/entry/Q6X632) | AlphaFold DB |
| Cynomolgus ortholog (GPR75) | [A0A7N9DAV0](https://alphafold.ebi.ac.uk/entry/A0A7N9DAV0) | AlphaFold DB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

Scored, but no surface patch cleared the antibody-sized targetability threshold (`n_sites = 0`).

## 9. Evidence ledger

49 entries · 34 primary · 15 secondary · 0 tertiary · 39 PMC OA.

- `a1_evi_01` · *Primary* · Supports · Topology — Original cloning paper predicts 7TM topology for GPR75 (540 aa) by protein sequence analysis, establishing the canonical GPCR architecture with N-terminus extracellular. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
  - *assay*: Human
  > "We report the identification and characterisation of a novel human orphan G-protein-coupled receptor (GPR) which maps to chromosome 2p16. We have determined the full-length coding sequence and genomic structure of a gene corresponding to the anonymous expressed sequenced tag, WI-31133. This gene encodes a novel protein that is 540 amino acids in length. Protein sequence analysis predicts the presence of seven transmembrane domains, a characteristic feature of GPRs."
- `a1_evi_02` · *Secondary* · Supports · Topology — GPR75 has a structurally unique 7TM GPCR domain architecture: approximately 200 aa extracellular N-terminus, a third intracellular loop of 92 residues, and an unusually long C-terminal intracellular tail of 169 residues — defining accessible ECD surface area. ([PMC10119890](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10119890/))
  - *assay*: Human
  > "GPR75 is structurally unique among GPCRs, with about 200 amino acids, a putative third intracellular loop of 92 residues and an unusually long C-terminal tail of 169 residues."
- `a1_evi_03` · *Secondary* · Supports · Topology — GPR75 is a 540 aa Gαq-coupled 7TM GPCR with N-glycosylation sites in the N-terminus (extracellular) and serine/threonine phosphorylation sites in the C-terminus (intracellular), confirming N-terminal extracellular orientation with post-translational modifications on the surface face. ([PMC10330141](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10330141/))
  - *assay*: Human
  > "Originally listed in the orphan receptor family is the GPCR 75 (GPR75), a 540 amino acid member of the G αq class of GPCRs, which contains seven transmembrane spanning domains, N-glycosylation sites in the N-terminus, and numerous serine and threonine phosphorylation sites in the C-terminus."
- `a1_evi_04` · *Secondary* · Supports · Topology — GPR75 topology diagram from GPCRdb confirms 7TM architecture with 3 extracellular loops (ECL1-3) located outside the receptor and available for ligand binding, N-terminus extracellular, and C-terminus intracellular — anchoring the accessible surface face. ([PMC12071931](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12071931/))
  - *assay*: Human
  > "The transmembrane region of GPR75 consists of 7TM, including 3ECL located outside the receptor and involved in binding ligands; 3ICL located inside the receptor and involved in interacting with G proteins or other signaling molecules to transmit signals; and the N-terminal region, which is located outside the membrane, and the C-terminal region, located inside the cell ( https://gpcrdb.org/protein/gpr75_human , accessed on 12 February 2025)."
- `a1_evi_05` · *Primary* · Ambiguous · Topology — Cryo-EM structures of GPR75 (apo and G protein-complexed) reveal a completely collapsed extracellular domain that eliminates the traditional orthosteric binding pocket; the HRL motif replaces DRY and a Lys134-Asp210 salt bridge stabilizes active-like conformation without ligand. This ECD collapse is a major epitope-accessibility risk: antibodies or ligands targeting a conventional GPCR orthosteric ECD pocket may fail to engage GPR75 on intact cells. (https://pubmed.ncbi.nlm.nih.gov/41545757/)
  - *assay*: Human
  > "Our structures reveal unique architectural features: a completely collapsed extracellular domain eliminates the traditional orthosteric binding pocket, raising critical questions about previously reported small molecule ligands. GPR75 assumes active-like conformation in both apo and G protein complexed structures through unique molecular switches-the canonical DRY motif is replaced by HRL, abolishing the ionic lock, while a distinctive Lys134-Asp210 salt bridge stabilizes the active conformation without ligand binding."
- `a1_evi_06` · *Primary* · Supports · Methodological — 3xFlag-Gpr75 knockin (3xFlag-Gpr75) mice were generated using CRISPR/Cas9 with sgRNA targeting the Gpr75 locus and an oligo template inserting a 3xFlag tag in-frame at the N-terminus, immediately upstream of the endogenous start codon. This endogenous-tag knockin enables detection of GPR75 protein in native tissues without antibody cross-reactivity concerns; construct uses the native signal sequence. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
  - *assay*: Mouse
  > "Gpr75 -knockout ( Gpr75 –/– ) mice and 3xFlag tag Gpr75-knockin ( 3xFlag-Gpr75 ) mice were generated in our laboratory using the CRISPR/Cas9 system as described previously ( 41 ), with Gpr75 (5′-ATTGGGGACATTCTGAAGCG-3′) small base-pairing guide RNA (sgRNA) and the oligo template with the 3xFlag tag and flanking sequence: 5′-TGAGCTGAGATCCTGACTCTTTTCCTGCTGAATTTATTTTTTTGAGAACACAAGAAAGAGACACCTCTCTCTGAAGatggactacaaagaccatgacggtgattataaagat catgatatcgattacaaggatgacgatgacaagATGAACACAAGTGCCCCGCTTCAGAATGTCCCCAATGCCACCTTGCTAAACATGC-3′."
- `a1_evi_07` · *Primary* · Supports · Methodological — GPR75 protein detected by polyclonal anti-C-terminal antibody sc-164538 (Santa Cruz Biotechnology) in pull-down and WB experiments, yielding a single specific band at 54–55 kDa. Antibody is C-terminal (intracellular) directed; requires permeabilization for IF applications but suitable for WB validation. ([PMC5446268](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5446268/))
  - *assay*: Human · human endothelial cells
  > "Pull-down experiments and western blot analysis of GPR75 was performed using a polyclonal antibody against the c-terminal (sc-164538, Santa Cruz, Biotechnology, Dallas, TX) which recognized a single 54-55 KDa protein band."
- `a1_evi_08` · *Primary* · Supports · Surface Expression — Photoaffinity crosslinking with 20-APheDa (a 20-HETE analogue) on isolated membrane fractions from human endothelial cells, followed by click-chemistry fluorescent labeling, produced a dominant band at 47–49 kDa consistent with GPR75 molecular weight. This membrane-fraction assay demonstrates ligand engagement at the plasma membrane surface of intact endothelial cells. ([PMC5446268](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5446268/))
  - *assay*: Human · human endothelial cells · live · non-permeabilized
  > "Incubation of 10 nmol/L of 20-APheDa with membrane fractions of human endothelial cells (EC) (20μg) followed by 15 min of UV (365 nm) crosslinking and 1h of incubation with the click reagent (DBCO-IRdye 800CW, LiCor) (50 μmol/L) yielded several bands, including a dominant band located at 47–49 kDa were detected ( Fig. 1C )."
- `a1_evi_09` · *Primary* · Supports · Methodological — Competition of 20-APheDa membrane-fraction labeling by excess 20-HETE (agonist, 100 µM) but not 12-HETE (inactive control, 100 µM) confirms that the 47–49 kDa band represents specific GPR75–ligand engagement at the membrane. This selectivity control strengthens the surface-accessibility claim from the photoaffinity experiment. ([PMC5446268](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5446268/))
  - *assay*: Human · human endothelial cells · live · non-permeabilized
  > "This labeling profile of several bands is characteristic of many click-chemistry interactions whereby multiple proteins in close proximity to the binding site of the compound, in this case 20-APheda, are labeled. 30 Nevertheless, the labeling of these bands by 20-APheDa (0.1 nmol/L) was competed by excess amounts of 20-HETE (100 μmol/L), but not 12-HETE (100 μmol/L) ( Fig. 1D–E )."
- `a1_evi_10` · *Secondary* · Ambiguous · Methodological — GPR75 overexpression construct uses a cleavable exogenous signal sequence (common forward primer encoding a cleavable signal sequence), replacing the native N-terminal leader. This exogenous SP forces secretory-pathway trafficking regardless of native GPR75 routing; surface localization data from this construct should be interpreted as supportive-indirect evidence only. ([PMC8062009](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8062009/))
  - *assay*: Unspecified
  > "For each receptor the coding sequence was amplified with a common forward primer (corresponding to a cleavable signal sequence) and custom reverse primer (corresponding to the receptor C terminus) and ligated into a pRluc8-N1 cloning vector."
- `a1_evi_11` · *Primary* · Supports · Surface Expression — VPS35 stabilizes GPR75 by recycling it to the hepatocyte plasma membrane, reducing degradation during MASH progression. This retromer-mediated recycling pathway constitutes direct evidence that GPR75 resides at and returns to the cell surface of hepatocytes, supporting membrane-localized surface accessibility. (https://pubmed.ncbi.nlm.nih.gov/41632920/)
  - *assay*: Human · hepatocytes
  > "Mechanistically, VPS35 stabilized GPR75 by recycling it to the hepatocyte membrane, thereby decreasing its degradation during MASH progression.<h4>Conclusions</h4>This study demonstrates that GPR75 serves as a novel regulator of MASLD/MASH by modulating hepatic fatty acid metabolism. These findings suggest that GPR75 suppression may represent a potential therapeutic strategy for MASLD/MASH treatment."
- `a1_evi_12` · *Primary* · Supports · Surface Expression — 3xFlag-GPR75 (endogenous knockin tag) is expressed in the primary cilia of hypothalamic neurons in wild-type mice, as shown in a figure panel describing the construct and ciliary compartment localization. Primary cilia are plasma membrane extensions — this supports GPR75 surface accessibility in a specialized membrane subdomain. ([PMC11444157](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444157/))
  - *assay*: Mouse · hypothalamic neurons · fixed
  > "( A ) 3xFlag-GPR75 is expressed in primary cilia of hypothalamic neurons, and wild-type mice become obese when fed a HFD."
- `a1_evi_13` · *Primary* · Supports · Methodological — 3xFlag-GPR75-L144P (Thinner mutation) fails to localize to primary cilia in hypothalamic neurons, contrasting with wild-type GPR75 ciliary localization. This loss-of-ciliary-localization phenotype in a missense mutant provides within-experiment validation that the ciliary surface signal in wild-type is specific to the correctly folded receptor. ([PMC11444157](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444157/))
  - *assay*: Mouse · hypothalamic neurons · fixed
  > "( B ) The 3xFlag-GPR75-L144P mutant fails to localize to primary cilia, and mice carrying this mutation show resistance to weight gain."
- `a1_evi_14` · *Primary* · Ambiguous · Surface Expression — Endogenous GPR75 (detected via 3xFlag knockin) localizes to primary cilia of hypothalamic cells; the Thinner mutation L144P and human GPR75 obesity-protective variants fail to localize to cilia. Ciliary localization represents a restricted plasma-membrane subdomain — GPR75 surface accessibility may be compartmentalized to primary cilia in hypothalamic neurons, which could limit access for conventional antibody-based staining on non-ciliated cell surfaces. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
  - *assay*: Mouse · hypothalamic neurons · fixed
  > "Additionally, GPR75 was localized in the primary cilia of hypothalamic cells, whereas the Thinner mutation (L144P) and human GPR75 variants in individuals with a lower BMI failed to localize in the cilia."
- `a1_evi_15` · *Secondary* · Ambiguous · Tissue Expression — Endogenous GPR75 protein (detected via 3xFlag knockin) is exclusively expressed in the brains of knockin mice with consistent expression across different brain regions, confirmed by western blot of total brain tissue — whole-cell protein expression without surface fractionation. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
  - *assay*: Mouse
  > "The endogenous GPR75 protein was exclusively expressed in the brains of 3xFlag-tagged Gpr75-knockin (3xFlag-Gpr75) mice, with consistent expression across different brain regions."
- `a1_evi_16` · *Secondary* · Ambiguous · Tissue Expression — Both qPCR and flow cytometry show GPR75 expression in SH-SY5Y neuroblastoma cells. The flow cytometry result is mentioned but staining conditions (permeabilized vs non-permeabilized, antibody clone, isotype controls) are not specified in this abstract — surface accessibility cannot be confirmed from this result alone. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
  - *assay*: Human · SH-SY5Y · unspecified
  > "Both qPCR and flow cytometry show that these cells express GPR75 but do not express CCR5, CCR3 or CCR1 receptors."
- `a1_evi_17` · *Secondary* · Ambiguous · Tissue Expression — Anti-GPR75 antibody detects an immunoreactive band at ~59 kDa in rat cortical neurons and differentiated SH-SY5Y cells by western blot of total cell lysate — whole-cell protein expression without membrane fractionation; surface accessibility not addressed. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
  - *assay*: Rat · rat cortical neurons / SH-SY5Y
  > "The antibody against GPR75 detected an immunoreactive band with a molecular weight of approximately 59 kDa in rat cortical neurons and differentiated SH-SY5Y cells ( Fig. 1A )."
- `a1_evi_18` · *Secondary* · Ambiguous · Tissue Expression — GPR75 protein distribution examined by fluorescent immunostaining on brain tissue slices from multiple rat strains (SD, Dahl SS, CYP4A1 transgenic) and on cultured human cerebral pericytes and cerebral vascular smooth muscle cells. Immunostaining method described; permeabilization status not specified in abstract. ([PMC7499024](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7499024/))
  - *assay*: Rat · cerebral pericytes, vascular smooth muscle cells · fixed
  > "Brain tissue slices from Sprague Dawley (SD), Dahl Salt-Sensitive (SS) and CYP4A1 transgenic rat strains, as well as cultured human cerebral pericytes and cerebral vascular smooth muscle cells, were analyzed by fluorescent immunostaining."
- `a1_evi_19` · *Secondary* · Ambiguous · Tissue Expression — GPR75 detected by fluorescent immunostaining in endothelial cells, vascular smooth muscle cells, and the glial limiting membrane of pial arteries and penetrating arterioles, but absent from capillary endothelium in rat cerebral vasculature — establishes cell-type-specific expression pattern but permeabilization status unstated; surface accessibility not confirmed. ([PMC7499024](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7499024/))
  - *assay*: Rat · cerebrovascular cells · fixed
  > "In the cerebral vasculature, CYP4A and GPR75 were expressed in endothelial cells, vascular smooth muscle cells and the glial limiting membrane of pial arteries and penetrating arterioles but not in the endothelium of capillaries."
- `a1_evi_20` · *Secondary* · Ambiguous · Tissue Expression — GPR75 protein distribution assessed by western blot and/or fluorescence microscopy in androgen-insensitive prostate cancer cells (PC-3) — combined WB and microscopy methods described; no membrane fractionation or surface-specific staining protocol specified, so surface accessibility not directly confirmed. ([PMC6957769](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6957769/))
  - *assay*: Human · PC-3 · unspecified
  > "Thus, the aim of this study was to determine whether 20-HETE can affect the metastatic potential of androgen-insensitive prostate cancer cells, and the implication of the newly described 20-HETE receptor, GPR75, in mediating these effects.<h4>Methods</h4>The expression of GPR75, protein phosphorylation, actin polymerization and protein distribution were assessed by western blot and/or fluorescence microscopy."
- `a1_evi_21` · *Secondary* · Ambiguous · Tissue Expression — Gene expression and protein levels of GPR75 evaluated across chronic liver disease patient samples by unspecified methods (described as 'gene expression and protein levels'); no surface fractionation method described — expression evidence without surface accessibility confirmation. ([PMC11826315](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11826315/))
  - *assay*: Human
  > "Additionally, we evaluated gene expression and protein levels of GPR75, a high-affinity receptor for 20-HETE across CLD patient samples.<h4>Results</h4>We observed an increase in 20-HETE levels and synthesis during the progression of MASLD."
- `a1_evi_22` · *Secondary* · Ambiguous · Tissue Expression — RNAscope in situ hybridization identified GPR75 mRNA puncta in NeuN-positive hippocampal neurons, indicating neuronal mRNA expression without surface protein accessibility data — RNA-level evidence qualifying surface claims for neurons. ([PMC10330141](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10330141/))
  - *assay*: Unspecified · hippocampal neurons
  > "Using RNAscope® technology, we identified GPR75 puncta in several Rbfox3-/NeuN-positive cells in the hippocampus, suggesting that this receptor has a neuronal expression."
- `a2_evi_01` · *Primary* · Supports · Tissue Expression — In the original characterization study, GPR75 transcript was detected by in situ hybridization in human retinal pigment epithelium (RPE) and cells surrounding retinal arterioles; Northern blot showed a 7 kb transcript highly expressed in brain. In mouse retina the localization differed (photoreceptor inner segments and outer plexiform layer), indicating species-dependent expression pattern. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
  - *assay*: Human · retinal pigment epithelium; retinal arteriole perivascular cells · fixed
  > "In situ hybridisation to human retina and Northern blot analysis of human retinal pigment epithelium (RPE) showed localisation of this transcript to the RPE and cells surrounding retinal arterioles. In contrast, the transcript was localised to the photoreceptor inner segments and the outer plexiform layer in mouse sections. Northern blot analysis demonstrated a 7 kb transcript highly expressed in the brain. No mutations were identified during a screen of patients suffering from Doyne's honeycomb retinal dystrophy (DHRD), an inherited retinal degeneration which maps to chromosome 2p16."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — Northern blot analysis of human tissue showed GPR75 mRNA highly expressed in brain (7 kb transcript), establishing brain as the primary tissue of expression. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
  - *assay*: Human · brain tissue · unspecified
  > "In situ hybridisation to human retina and Northern blot analysis of human retinal pigment epithelium (RPE) showed localisation of this transcript to the RPE and cells surrounding retinal arterioles. In contrast, the transcript was localised to the photoreceptor inner segments and the outer plexiform layer in mouse sections. Northern blot analysis demonstrated a 7 kb transcript highly expressed in the brain. No mutations were identified during a screen of patients suffering from Doyne's honeycomb retinal dystrophy (DHRD), an inherited retinal degeneration which maps to chromosome 2p16."
- `a2_evi_03` · *Secondary* · Supports · Tissue Expression — GPR75 is most highly expressed in cerebellum and cerebral cortex among brain regions, correlating with the distribution of its proposed ligand CCL5. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
  - *assay*: Human · cerebellum; cerebral cortex · unspecified
  > "Indeed, CCL5 is highly abundant in the cerebellum and cerebral cortex ( Avdoshina et al . 2011 ), two areas that exhibit the highest GPR75 expression ( Sauer et al . 2001 )."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — Western blot detected GPR75 protein (~59 kDa immunoreactive band) in primary rat cortical neurons and in retinoic-acid-differentiated SH-SY5Y human neuroblastoma cells, confirming neuronal cell-type expression. GPR75 was not detected (or was much lower) in rat astrocytes based on the same blot series. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
  - *assay*: Rat · primary rat cortical neurons; differentiated SH-SY5Y cells · fixed · permeabilized
  > "The antibody against GPR75 detected an immunoreactive band with a molecular weight of approximately 59 kDa in rat cortical neurons and differentiated SH-SY5Y cells ( Fig. 1A )."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — Both qPCR and flow cytometry confirm that human neuroblastoma SH-SY5Y cells express GPR75 at the RNA and protein level; these cells do not express the related chemokine receptors CCR5, CCR3, or CCR1, making them a clean model for GPR75-specific studies. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
  - *assay*: Human · SH-SY5Y neuroblastoma cells · live · non-permeabilized
  > "Both qPCR and flow cytometry show that these cells express GPR75 but do not express CCR5, CCR3 or CCR1 receptors."
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — RNAscope in situ hybridization identified GPR75 transcript puncta in multiple NeuN-positive (neuronal) cells in the hippocampus of mice, establishing neuronal expression in this brain region. ([PMC10330141](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10330141/))
  - *assay*: Mouse · hippocampal neurons (NeuN+) · fixed · permeabilized
  > "Using RNAscope® technology, we identified GPR75 puncta in several Rbfox3-/NeuN-positive cells in the hippocampus, suggesting that this receptor has a neuronal expression."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — In 3xFlag-tagged Gpr75-knockin mice, endogenous GPR75 protein was detected exclusively in the brain, with consistent expression across multiple brain regions. This knockin approach provides high-specificity protein-level evidence for pan-brain expression. ([PMC11444156](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444156/))
  - *assay*: Mouse · brain (multiple regions) · fixed · permeabilized
  > "The endogenous GPR75 protein was exclusively expressed in the brains of 3xFlag-tagged Gpr75-knockin (3xFlag-Gpr75) mice, with consistent expression across different brain regions."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — Gpr75 is highly expressed in the brain, with particularly prominent expression across various neuron types including hypothalamic neurons, based on transcriptomic atlas data. ([PMC11805625](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11805625/))
  - *assay*: Mouse · hypothalamic neurons; brain neurons · unspecified
  > "(B) Gpr75 is highly expressed in the brain, particularly across various neurons, including the hypothalamus."
- `a2_evi_09` · *Primary* · Refutes · Tissue Expression — Western blot assessment of GPR75 in peripheral immune tissues (thymus and spleen) showed low or absent expression, establishing that GPR75 is not a prominently expressed receptor in classical immune organs. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
  - *assay*: Rat · thymus; spleen · fixed · permeabilized
  > "Lysates from the thymus and spleen were used to provide an assessment of the expression of GPR75 in peripheral tissues."
- `a2_evi_10` · *Secondary* · Supports · Tissue Expression — Published studies report high GPR75 expression in mouse brain and heart relative to spleen, indicating cardiac expression in addition to the well-established CNS expression. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
  - *assay*: Mouse · brain; heart; spleen · unspecified
  > "Other studies have indicated high expression of this receptor in the mouse brain and heart when compared to traditional immune organs such as spleen ( Ignatov et al . 2006 )."
- `a2_evi_11` · *Primary* · Supports · Tissue Expression — In rat brain, GPR75 protein was detected by fluorescent immunostaining in cerebral endothelial cells, vascular smooth muscle cells, and the glial limiting membrane of pial arteries and penetrating arterioles, but was absent from capillary endothelium. This establishes cell-type-specific vascular expression restricted to larger cerebral vessels. ([PMC7499024](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7499024/))
  - *assay*: Rat · cerebral endothelial cells; vascular smooth muscle cells; glial limiting membrane of pial arteries · fixed · permeabilized
  > "In the cerebral vasculature, CYP4A and GPR75 were expressed in endothelial cells, vascular smooth muscle cells and the glial limiting membrane of pial arteries and penetrating arterioles but not in the endothelium of capillaries."
- `a2_evi_12` · *Primary* · Refutes · Tissue Expression — GPR75 protein was NOT detected in astrocytes in rat brain sections, despite CYP4A expression in astrocytes. This negative finding distinguishes GPR75 from a fully pan-glial receptor. ([PMC7499024](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7499024/))
  - *assay*: Rat · astrocytes (brain) · fixed · permeabilized
  > "CYP4A, but not GPR75, was expressed in astrocytes."
- `a2_evi_13` · *Primary* · Supports · Tissue Expression — GPR75 is functionally expressed in cultured primary human microvascular endothelial cells, where 20-HETE binding activates Gαq/11 signaling, inositol phosphate accumulation, and downstream EGFR transactivation. ([PMC5446268](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5446268/))
  - *assay*: Human · primary human microvascular endothelial cells · live · non-permeabilized
  > "In cultured human endothelial cells, 20-HETE binding to GPR75 stimulated Gα<sub>q/11</sub> protein dissociation and increased inositol phosphate accumulation and GPCR-kinase interacting protein-1-GPR75 binding, which further facilitated the c-Src-mediated transactivation of epidermal growth factor receptor."
- `a2_evi_14` · *Primary* · Supports · Tissue Expression — GPR75 is functionally expressed in vascular smooth muscle cells (VSMCs), where 20-HETE/GPR75 signaling through Gαq/11 leads to protein kinase C-mediated phosphorylation of MaxiKβ, linking receptor activation to vasoconstriction. ([PMC5446268](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5446268/))
  - *assay*: Rat · rat aortic vascular smooth muscle cells (A7r5) · live · non-permeabilized
  > "In vascular smooth muscle cells, GPR75-20-HETE pairing is associated with Gα<sub>q/11</sub>- and GPCR-kinase interacting protein-1-mediated protein kinase C-stimulated phosphorylation of MaxiKβ, linking GPR75 activation to 20-HETE-mediated vasoconstriction."
- `a2_evi_15` · *Primary* · Supports · Tissue Expression — Knockdown of GPR75 in human endothelial cells abolished 20-HETE-stimulated intracellular Ca2+ signaling, confirming functional endogenous expression of GPR75 in human endothelial cells and its requirement for 20-HETE-mediated calcium mobilization. ([PMC10119890](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10119890/))
  - *assay*: Human · human endothelial cells · live · non-permeabilized
  > "Knockdown of GPR75 in human endothelial cells nullified 20-HETE-stimulated intracellular Ca<sup>2+</sup> ."
- `a2_evi_16` · *Primary* · Supports · Tissue Expression — GPR75 receptor protein was confirmed to be expressed in PC-3 human prostate cancer cells under standard culture conditions, establishing expression in a prostate cancer cell line. ([PMC6957769](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6957769/))
  - *assay*: Human · PC-3 prostate cancer cells · fixed · permeabilized
  > "The expression of GPR75 receptor protein was firstly confirmed in PC-3 cells cultured in complete or serum-deprived medium."
- `a2_evi_17` · *Primary* · Supports · Tissue Expression — In PC-3 prostate cancer cells, GPR75 protein abundance increases by ~91% after 24h serum starvation compared to cells in complete medium. This cell-state modulation (nutrient-deprived vs. nutrient-replete) demonstrates that receptor levels are dynamically regulated by metabolic context. ([PMC6957769](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6957769/))
  - *assay*: Human · PC-3 prostate cancer cells (serum-starved vs. complete medium) · fixed · permeabilized
  > "Although the receptor was detected in both conditions, 24 h serum starvation increased GPR75 protein abundance by 91% (p<0.05 vs. complete medium) ( Fig 1a )."
- `a2_evi_18` · *Primary* · Supports · Tissue Expression — In PC-3 prostate cancer cells, ligand stimulation with 20-HETE (0.1 nM, 12h) reduced GPR75 receptor abundance by 78%, consistent with ligand-induced receptor downregulation/internalization; this was reversed by the antagonist AAA. Antagonist alone increased GPR75 expression by 34%. This suggests agonist-driven surface depletion and constitutive ligand-mediated turnover as accessibility modulators. ([PMC6957769](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6957769/))
  - *assay*: Human · PC-3 prostate cancer cells · fixed · permeabilized
  > "Incubation with 20-HETE (0.1 nM, 12 h) decreased GPR75 receptor abundance in cell homogenates by 78% (p<0.0001 vs. control), an effect that was reversed by the 20-HETE receptor antagonist AAA (5 μM) (p<0.01 vs. 20-HETE alone)."
- `a2_evi_19` · *Primary* · Supports · Tissue Expression — After traumatic brain injury (TBI) in the immature brain, GPR75 expression levels are upregulated in activated microglia, alongside elevated CYP4A (20-HETE synthase), with concomitant activation of the Src/EGFR/NF-κB pathway. This establishes disease-state-induced upregulation of GPR75 specifically in microglial cells in the TBI context. (https://pubmed.ncbi.nlm.nih.gov/39541047/)
  - *assay*: Rat · microglia (immature brain TBI model) · fixed · permeabilized
  > "In contrast, overexpression of GPR75 had the opposite effect. In addition, after immature brain TBI, the 20-HETE and GPR75 expression levels were upregulated in microglia, with significant activation of the Src/EGFR/NF-κB pathway. Inhibition of 20-HETE synthesis with N-hydroxy-N'-(4-n-butyl-2-methylphenyl) formamidine (HET0016) produced the opposite effect. 20-HETE regulates the Src/EGFR/NF-κB signaling pathway via GPR75 to activate microglia, promoting immature brain TBI. These findings offer a novel target for promoting the brain injury effect of 20-HETE."
- `a2_evi_20` · *Primary* · Supports · Tissue Expression — Transcriptomic analysis of sepsis-associated acute kidney injury (S-AKI) mouse kidneys showed GPR75 is highly expressed in renal macrophages under disease conditions. Functional siRNA knockdown of GPR75 in a macrophage/tubular epithelial coculture system inhibited macrophage oxidative stress and inflammatory cytokine secretion. (https://pubmed.ncbi.nlm.nih.gov/41353881/)
  - *assay*: Mouse · renal macrophages (S-AKI model) · unspecified
  > "Transcriptomic analysis and further research revealed that WA promoted the expression of the antioxidant proteins HMOX1 and SOD2 and inhibited IL-1β, IL-6, and TNF-α secretion. G protein-coupled receptor 75 (GPR75), which was highly expressed in the renal macrophages of S-AKI mice, was subsequently identified as the direct target of WA. In the RAW264.7/mTEC coculture system, siGPR75 inhibited macrophage oxidative stress and restrained IL-1β, IL-6, and TNF-α secretion, thereby reducing mTEC injury, and overexpression of GPR75 resulted in the opposite effects."
- `a2_evi_21` · *Primary* · Supports · Tissue Expression — GPR75 is upregulated in hippocampal neurons in diabetic cognitive dysfunction (DCD), as shown by immunofluorescence co-localization and co-immunoprecipitation with AMPK in HT22 mouse hippocampal neuronal cells. This establishes disease-state-induced upregulation of GPR75 in hippocampal neurons under hyperglycemic/diabetic conditions. (https://pubmed.ncbi.nlm.nih.gov/41043317/)
  - *assay*: Mouse · HT22 hippocampal neuronal cells (high-glucose treated) · fixed · permeabilized
  > "Our investigations revealed upregulation of GPR75 in DCD. Furthermore, we demonstrated that knocking down GPR75 could mitigate the progression of DCD, with its protective effects associated with the inhibition of mitochondrial dysfunction in hippocampal neurons. AMP-activated protein kinase (AMPK), a regulator of mitochondrial function and cellular energy sensor, was identified as a novel target for GPR75. Immunofluorescence and co-immunoprecipitation (CO-IP) analyses confirmed the co-localization and interaction between GPR75 and AMPK in HT22 cells."
- `a2_evi_22` · *Primary* · Supports · Tissue Expression — GPR75 is not abundantly expressed in healthy human liver, but its protein levels significantly increase during metabolic dysfunction-associated steatohepatitis (MASH). This establishes a disease-state-induced upregulation in hepatocytes in MASH context vs. near-absence in normal liver. (https://pubmed.ncbi.nlm.nih.gov/41632920/)
  - *assay*: Human · liver / hepatocytes (healthy vs. MASH) · fixed · permeabilized
  > "<h4>Background and aims</h4>Metabolic dysfunction-associated steatotic liver disease (MASLD), including its more severe form, metabolic dysfunction-associated steatohepatitis (MASH), is increasingly recognized as a critical global health challenge. This study investigates the role of hepatic GPR75 in MASH progression.<h4>Approach and results</h4>Although GPR75 is not abundantly expressed in the liver in healthy individuals, its protein levels significantly increase during MASH."
- `a2_evi_23` · *Primary* · Supports · Surface Expression — VPS35 stabilizes GPR75 by recycling it back to the hepatocyte plasma membrane, thereby decreasing its degradation during MASH progression. This retromer-mediated membrane recycling constitutes an accessibility-modulation mechanism: in MASH, increased VPS35-driven membrane recycling elevates surface-available GPR75 in hepatocytes. (https://pubmed.ncbi.nlm.nih.gov/41632920/)
  - *assay*: Mouse · hepatocytes (MASH diet model) · unspecified
  > "Mechanistically, VPS35 stabilized GPR75 by recycling it to the hepatocyte membrane, thereby decreasing its degradation during MASH progression.<h4>Conclusions</h4>This study demonstrates that GPR75 serves as a novel regulator of MASLD/MASH by modulating hepatic fatty acid metabolism. These findings suggest that GPR75 suppression may represent a potential therapeutic strategy for MASLD/MASH treatment."
- `a2_evi_24` · *Primary* · Supports · Tissue Expression — Transcriptomic analysis in endothelial cells revealed methionine exposure induces upregulation of GPR75 mRNA, alongside CYP1A1. This represents a metabolic-state-induced transcriptional upregulation of GPR75 in vascular endothelial cells. ([PMC12249897](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12249897/))
  - *assay*: Human · EA.hy926 endothelial cells (methionine-treated) · unspecified
  > "Transcriptomic analysis revealed methionine-induced upregulation of AA pathway-associated genes <i>Cyp1a1</i> and <i>Gpr75</i>."
- `a2_evi_25` · *Primary* · Supports · Surface Expression — GPR75 protein accumulates in the primary cilia of hypothalamic neurons in mice, representing a specific subcellular localization at the ciliary membrane surface domain — a membrane subdomain with restricted accessibility. ([PMC11444157](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444157/))
  - *assay*: Mouse · hypothalamic neurons (primary cilia) · fixed · permeabilized
  > "GPR75 accumulated in the cilia of hypothalamic neurons."
- `a2_evi_26` · *Primary* · Refutes · Surface Expression — The Thinner allele (L144P missense mutation) of GPR75 shows defective ciliary localization in hypothalamic neurons: the mutant protein fails to traffic to the primary cilium surface, correlating with resistance to diet-induced fat accumulation. This represents an accessibility modulation — baseline: wild-type GPR75 at ciliary surface; modulating condition: L144P mutation abolishes ciliary surface targeting. ([PMC11444157](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11444157/))
  - *assay*: Mouse · hypothalamic neurons (Thinner/L144P mutant mice) · fixed · permeabilized
  > "However, mice with the Thinner allele showed defective ciliary localization with resistance to fat accumulation."
- `a2_evi_27` · *Secondary* · Ambiguous · Contradictory — Prior literature reports that GPR75 was proposed to be activated by CCL5/RANTES as a chemokine receptor originally characterized in the human retina. However, the functional role of CCL5 as a bona fide GPR75 ligand remains contested in the field — the receptor was initially identified as an orphan GPCR and the CCL5 pairing has not been independently replicated by all groups. ([PMC6198807](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6198807/))
  - *assay*: Human · retina · unspecified
  > "GPR75 has been considered an orphan receptor of the Gqα family of G proteins, which was originally characterized for its expression in the human retina ( Tarttelin et al . 1999 , Sauer et al . 2001 )."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/GPR75.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/GPR75](https://surfaceome.deliverome.org/GPR75)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/GPR75.json](https://surfaceome.deliverome.org/data/surfaceome/GPR75.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/GPR75.md](https://surfaceome.deliverome.org/data/surfaceome/GPR75.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/O95800](https://alphafold.ebi.ac.uk/entry/O95800)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/O95800](https://alphafold.ebi.ac.uk/api/prediction/O95800) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/O95800](https://www.uniprot.org/uniprotkb/O95800)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-O95800-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-O95800-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-O95800-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-O95800-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-O95800-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-O95800-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*540 aa · `O95800` · embedded at build time*

```
   1  MNSTGHLQDAPNATSLHVPHSQEGNSTSLQEGLQDLIHTATLVTCTFLLAVIFCLGSYGN
  61  FIVFLSFFDPAFRKFRTNFDFMILNLSFCDLFICGVTAPMFTFVLFFSSASSIPDAFCFT
 121  FHLTSSGFIIMSLKTVAVIALHRLRMVLGKQPNRTASFPCTVLLTLLLWATSFTLATLAT
 181  LKTSKSHLCLPMSSLIAGKGKAILSLYVVDFTFCVAVVSVSYIMIAQTLRKNAQVRKCPP
 241  VITVDASRPQPFMGVPVQGGGDPIQCAMPALYRNQNYNKLQHVQTRGYTKSPNQLVTPAA
 301  SRLQLVSAINLSTAKDSKAVVTCVIIVLSVLVCCLPLGISLVQVVLSSNGSFILYQFELF
 361  GFTLIFFKSGLNPFIYSRNSAGLRRKVLWCLQYIGLGFFCCKQKTRLRAMGKGNLEVNRN
 421  KSSHHETNSAYMLSPKPQKKFVDQACGPSHSKESMVSPKISAGHQHCGQSSSTPINTRIE
 481  PYYSIYNSSPSQEESSPCNLQPVNSFGFANSYIAMHYHTTNDLVQEYDSTSAKQIPVPSV
```

### Canonical ortholog sequences

**Mouse — Gpr75** (`Q6X632` · 540 aa)

```
   1  MNTSAPLQNVPNATLLNMPPLHGGNSTSLQEGLRDFIHTATLVTCTFLLAIIFCLGSYGN
  61  FIVFLSFFDPSFRKFRTNFDFMILNLSFCDLFICGVTAPMFTFVLFFSSASSIPDSFCFT
 121  FHLTSSGFVIMSLKMVAVIALHRLRMVMGKQPNCTASFSCILLLTLLLWATSFTLATLAT
 181  LRTNKSHLCLPMSSLMDGEGKAILSLYVVDFTFCVAVVSVSYIMIAQTLRKNAQVKKCPP
 241  VITVDASRPQPFMGASVKGNGDPIQCTMPALYRNQNYNKLQHSQTHGYTKNINQMPIPSA
 301  SRLQLVSAINFSTAKDSKAVVTCVVIVLSVLVCCLPLGISLVQMVLSDNGSFILYQFELF
 361  GFTLIFFKSGLNPFIYSRNSAGLRRKVLWCLRYTGLGFLCCKQKTRLRAMGKGNLEINRN
 421  KSSHHETNSAYMLSPKPQRKFVDQACGPSHSKESAASPKVSAGHQPCGQSSSTPINTRIE
 481  PYYSIYNSSPSQQESGPANLPPVNSFGFASSYIAMHYYTTNDLMQEYDSTSAKQIPIPSV
```

**Cynomolgus — GPR75** (`A0A7N9DAV0` · 540 aa)

```
   1  MNSTGHLQDAPNATSLHVPHSPEGNSTSLQEGLQDLIHTATLVTCTFLLAVIFCLGSYGN
  61  FIVFLSFFDPAFRKFRTNFDFMILNLSFCDLFICGVTAPMFTFVLFFSSASSIPDAFCFT
 121  FHLTSSGFIIMSLKTVAVIALHRLRMVLGKQPNRMASFPCTVLLTLLLWATSFTLATLAT
 181  LKTSKSHLCLPMSSLIAGKGKAILSLYVVDFTFCVAVVSVSYIMIAQTLRKNAQVRKCPP
 241  VITVDASRPQPFMGVPVQGGGDPIQCAMPALYRNQNYNKLQHVQTRGYTKSPNQLATPAA
 301  SRLQLVSAINLSTAKDSKAVVTCVIIVLSVLVCCLPLGISLVQVVLSSNGSFILYQFELF
 361  GFTLIFFKSGLNPFIYSRNSAGLRRKVLWCLQYIGLGFFCCKQKTRLRAMGKGNLEVNRN
 421  KSSHHETNSAYMLSPKPQKKFVDQACGPSHSKESVVSPKISAGHQHCGQSSSTPINTRIE
 481  PYYSIYNSSPSQEESSPCNLQPVNSFGFANSYIAMHYHTTNDLMQEYDSTSAKQIPVPSV
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`O95800`, deeptmhmm-1.0.24)

```
   1  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMM
  61  MMMMMIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOO
 121  MMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMM
 181  MOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOMMMM
 361  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**O95800** (`O95800`, deeptmhmm-1.0.24)

```
   1  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMM
  61  MMMMMIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOO
 121  MMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMM
 181  MOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOMMMM
 361  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**O95800** (`O95800`, deeptmhmm-1.0.24)

```
   1  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMM
  61  MMMMMIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOO
 121  MMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMM
 181  MOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOMMMM
 361  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Mouse ortholog — Gpr75** (`Q6X632`, projected onto human canonical)

```
   1  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMM
  61  MMMMMIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOO
 121  MMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMM
 181  MOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOMMMM
 361  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Cynomolgus ortholog — GPR75** (`A0A7N9DAV0`, projected onto human canonical)

```
   1  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMM
  61  MMMMMIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOO
 121  MMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMM
 181  MOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOMMMM
 361  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — Confidence is moderate for two reasons. First, the surface-accessibility evidence is indirect: the strongest data come from endogenous N-terminal 3xFlag-knockin immunofluorescence (validated by the L144P loss-of-localization control) and membrane-fraction photoaffinity crosslinking — robust but not a clean non-permeabilized live-cell flow or surface biotinylation experiment with a knockout comparator. Second, the 2025 cryo-EM structure (PMID:41545757) reveals a constitutively collapsed orthosteric ECD pocket, a moderate epitope-masking risk that could defeat conventional GPCR-targeting antibody strategies. Lifting confidence would require non-permeabilized live-cell surface staining or surface biotinylation in primary human cells with a GPR75-knockout control, plus structural mapping of ECL2/3 loop accessibility.*
