# GPR75 — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-31T04:28:23.884488Z · model `claude-sonnet-4-6`*

> GPR75 is an orphan Class A GPCR (7TM, Gαq-coupled) constitutively resident at the plasma membrane across multiple peripheral tissues — pancreatic beta cells, vascular and pulmonary smooth muscle, adipocytes — and highly expressed in CNS neurons (BBB-restricted). Surface residence is supported by a BRET plasma-membrane trafficking assay in live HEK293 cells and functional calcium/cAMP assays in primary beta cells and VSMCs responding to exogenous CCL5/20-HETE. Evidence grade is supportive_but_indirect: no live-cell flow or surface biotinylation data exist, and the BRET construct used an exogenous signal peptide.

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

## 1. Executive summary

**Constitutively surface-accessible in peripheral tissues (pancreatic islets, VSMCs, adipocytes); CNS neuronal GPR75 is expression-confirmed but largely inaccessible to systemic large-molecule binders due to the blood-brain barrier.**

GPR75 is an orphan Class A GPCR (7TM, Gαq-coupled) constitutively resident at the plasma membrane across multiple peripheral tissues — pancreatic beta cells, vascular and pulmonary smooth muscle, adipocytes — and highly expressed in CNS neurons (BBB-restricted). Surface residence is supported by a BRET plasma-membrane trafficking assay in live HEK293 cells and functional calcium/cAMP assays in primary beta cells and VSMCs responding to exogenous CCL5/20-HETE. Evidence grade is supportive_but_indirect: no live-cell flow or surface biotinylation data exist, and the BRET construct used an exogenous signal peptide.

**Family / classification** — UniProt family: G-protein coupled receptor 1 family · HGNC gene group(s): G protein-coupled receptors, Class A orphans · functional class: Receptor.

**Triage first-pass reasoning** — GPR75 is a Class A orphan GPCR. All GPCRs are seven-transmembrane (heptahelical) receptors that reside at the plasma membrane with extracellular N-terminus and three extracellular loops accessible from outside the cell. GPR75 (UniProt O95800) is annotated as a GPCR family member and is expressed at the cell surface, consistent with the canonical topology of its class. Its extracellular loops and N-terminal domain are accessible to extracellular binders. No evidence places it exclusively in intracellular compartments; the NCBI summary explicitly states it is a 'cell surface receptor.'

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=Moderate · subcategory=GPCR · ecd=Small |
| Classification | reason=Classical Surface Receptor · family=Receptor · state-dependence=Low · induction-trigger=None |
| Expression | level=Moderate · breadth=Broad · specificity=Surface Dominant · low-endogenous=false · tumor-associated=false · orphan-receptor=true · OE-precedent=true |
| Risks | shed=false · secreted=false · co-receptor=None · masking=false · restricted-subdomain=false |
| Evidence | grade=Supportive but indirect · density=High · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=74.2% · cyno=98.9% |
| Paralogs | max %ECD identity = 35.7% |
| Topology | TM=7 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: High mRNA in CNS (Northern blot, RT-PCR: a2_evi_03, a2_evi_08); moderate protein in pancreatic islets by WB/IHC (a1_evi_08, a2_evi_04); functional expression in VSMCs and adipocytes (a2_evi_23, a2_evi_19). Overall peripheral expression is moderate.
- *Expression breadth*: Documented across CNS (brain, spinal cord: a2_evi_08, a2_evi_09), retina (a2_evi_01), pancreatic islets (a2_evi_04), adipose (a2_evi_19), vascular smooth muscle (a2_evi_23), and pulmonary artery (a2_evi_22) — multiple organ systems.
- *Surface specificity*: As a canonical 7TM GPCR, GPR75 is integral to the plasma membrane with no intracellular retention or dual-localization reported. BRET PM-marker assay confirms efficient surface trafficking (a1_evi_05); functional assays in beta cells and VSMCs confirm surface-accessible receptor (a2_evi_06, a2_evi_23).
- *Known ligand*: GPR75 is classified as an orphan GPCR with no validated endogenous agonist. CCL5 and 20-HETE have been proposed as ligands (a2_evi_06, a2_evi_23) but GPR75 is not formally deorphanized — the receptor is described as orphan in multiple sources (a1_evi_04, a2_evi_15).
- *Low endogenous expression*: Derived from expression_level='moderate' (not low/absent → not flagged). High mRNA in CNS (Northern blot, RT-PCR: a2_evi_03, a2_evi_08); moderate protein in pancreatic islets by WB/IHC (a1_evi_08, a2_evi_04); functional expression in VSMCs and adipocytes (a2_evi_23, a2_evi_19). Overall peripheral expression is moderate.
- *Overexpression surface localization*: 1 method observation(s) pair an overexpression/mixed expression system with a surface-localization readout (cites a1_evi_05, a1_evi_06, a1_evi_07).

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Supportive but indirect

The strongest surface-localization evidence for GPR75 comes from a BRET-based plasma-membrane trafficking assay in live, non-permeabilized HEK293 cells (a1_evi_05, a1_evi_07), which is a proximity-based functional readout consistent with surface residence. However, the construct used an exogenous cleavable signal peptide rather than the native GPR75 sequence, capping confidence to secondary tier. No classical direct surface methods (live-cell flow cytometry with nonperm antibody staining, surface biotinylation, or nonperm IHC) are present in the ledger. The remaining claims are either topology/classification assertions (tangential, low weight) or RNA/bulk-protein expression observations (expression_only). Because the only surface-positive evidence is a single functional proximity assay (BRET) with a chimeric construct in an overexpression system, and no orthogonal direct surface methodology is available, the grade is supportive_but_indirect.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Low | Computational 7TM topology prediction from discovery paper; no direct surface assay |
| a1_evi_02 | Tangential | Low | Review-level topology description with N-glycosylation sites implying extracellular N-terminus; no direct surface assay |
| a1_evi_03 | Tangential | Low | Structural annotation of protein size/genomic locus; no surface evidence |
| a1_evi_04 | Tangential | Low | Gαq-class GPCR classification implies PM residence but no direct surface assay |
| a1_evi_05 | Supports Surface | Moderate | BRET PM-marker assay in live HEK293 cells; proximity-based readout, not classical surface staining; exogenous signal peptide used |
| a1_evi_06 | Tangential | Low | Methodological note: exogenous signal peptide used in construct; caps confidence but does not contradict surface localization |
| a1_evi_07 | Supports Surface | Low | Overexpression BRET trafficking in G-protein null HEK293; exogenous signal peptide; secondary tier |
| a1_evi_08 | Expression Only | Low | WB + IHC on fixed pancreatic islets; whole-cell/bulk protein, no surface fractionation or nonperm staining |
| a1_evi_09 | Tangential | Low | KO-validated RT-PCR specificity control for mRNA expression; no surface assay |
| a1_evi_10 | Expression Only | Low | RT-PCR mRNA in mouse hippocampal neurons; RNA-level only |
| a1_evi_11 | Expression Only | Low | RT-PCR mRNA across mouse CNS regions; RNA-level only |
| a1_evi_12 | Expression Only | Low | RT-PCR mRNA CNS vs peripheral tissues with HPA corroboration; RNA-level only |

### Immunohistochemistry (1 method)

#### IHC Membranous — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-GPR75 — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human pancreatic islets — GPR75 detected by immunohistochemistry on fixed tissue | Primary Human Tissue | Moderate | 1 |

### Proximity labeling (1 method)

#### Unknown — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HEK 293 cells overexpressing GPR75-Rluc8 fusion — BRET to plasma membrane marker substantially higher than to ER marker, indicating efficient surface trafficking | Established Cell Line | High | 2 |
| Genome-edited G-protein-null HEK 293 cells coexpressing GPR75-Rluc8 with Gα and Venus-Gβγ — BRET-based PM trafficking assay in clean G-protein background | Established Cell Line | High | 1 |

*Overexpression construct* — SP source: Exogenous · cleavable signal sequence (common forward primer, not native GPR75 SP) · tag: C-terminal Rluc8 fusion · cell line: HEK 293. *(cites: a1_evi_05, a1_evi_06, a1_evi_07)*

### Other (1 method)

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-GPR75 — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human pancreatic islets — GPR75 detected by western blot (whole-cell lysate, no fractionation) | Primary Human Tissue | Moderate | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Human pancreatic islets (beta cells) — western blot and IHC on fixed tissue | Primary Human Tissue | Bulk Protein | Moderate | 1 |
| Mouse hippocampal neurons — RT-PCR mRNA (prior publication referenced) | Primary Human Cell | RNA | High | 1 |
| Mouse CNS multiple regions (brain and spinal cord) — RT-PCR mRNA with KO validation | Ex Vivo | RNA | Moderate | 2 |
| Mouse CNS vs peripheral tissues (spleen, kidney, heart) — RT-PCR mRNA; CNS-enriched pattern corroborated by Human Protein Atlas | Ex Vivo | RNA | High | 1 |

## 4. Biological context

**Cell types** *(orthogonal cell-type index)*

| Cell type | Ontology | Present in tissues | Species | Cites |
|---|---|---|---|---|
| retinal pigment epithelial cells | — | retina | Human | 1 |
| perivascular cells | — | retina | Human | 1 |
| photoreceptors | — | retina | Mouse | 1 |
| outer plexiform layer neurons | — | retina | Mouse | 1 |
| pancreatic islet cells | — | pancreatic islet | Human | 2 |
| pancreatic beta cells | — | pancreatic islet | Mouse | 4 |
| GABAergic neurons | — | brain, cerebellum | Mouse | 2 |
| glutamatergic neurons | — | brain, cerebellum | Mouse | 2 |
| monoaminergic neurons | — | substantia nigra, ventral tegmental area, locus coeruleus, raphe nucleus | Mouse | 1 |
| hippocampal neurons | — | hippocampus | Mouse | 1 |
| hypothalamic neurons | — | hypothalamus | Rat | 2 |
| adipocytes | — | adipose tissue | Mouse | 2 |
| pulmonary artery smooth muscle cells | — | pulmonary artery | Unspecified | 1 |
| vascular smooth muscle cells | — | vasculature | Unspecified | 1 |
| neurons | — | brain | Unspecified | 1 |

**Cell states**

- *GLP-1R agonist stimulation* — Treatment of NIT-1 pancreatic beta cells with 10 nM liraglutide for 60 min significantly upregulates GPR75 mRNA, suggesting GLP-1R signaling increases receptor transcript levels in beta cells. *(cites: a2_evi_24)*
- *high-fat diet-induced obesity* — GPR75 in adipocytes is functionally engaged under HFD conditions in a sex-dependent manner; female adipo-Gpr75-/- mice show 50% reduced weight gain, while male knockouts are unaffected. Hypothalamic Ccl5 is upregulated in Gpr75 KO rats on HFD, implicating central GPR75 activity during diet-induced obesity. *(cites: a2_evi_17, a2_evi_19, a2_evi_20)*
- *hyperglycaemia/insulin resistance* — CCL5 stimulates insulin secretion and improves glucose tolerance via GPR75 in ob/ob mice (hyperglycaemia/insulin resistance model), indicating functional surface GPR75 in pancreatic islets under this metabolic disease state. *(cites: a2_evi_07)*

**Primary subcellular compartment**: Plasma membrane

**Anatomical accessibility**

- vascular smooth muscle cells (VSMCs) in systemic vasculature — Blood Interstitial Facing · *Favorable*: GPR75 is functionally active at the surface of VSMCs, responding to circulating/interstitial ligands (20-HETE) via Gαq signaling. VSMCs are embedded in vessel walls and bathed by interstitial fluid accessible from the bloodstream, making GPR75 reachable by systemically delivered binders.
- pulmonary artery smooth muscle cells (PASMCs) — Blood Interstitial Facing · *Favorable*: GPR75 on PASMCs responds to CCL5 via Gαi signaling to modulate cAMP and induce contraction. PASMCs face the interstitial/adventitial compartment accessible from pulmonary circulation, suggesting systemic binders could reach GPR75 here.
- CNS neurons (brain and spinal cord) — Unknown · *Restricted*: GPR75 is highly expressed in CNS neurons (hippocampus, hypothalamus, substantia nigra, cerebellum). The blood-brain barrier (BBB) prevents most systemically delivered large-molecule binders from accessing CNS neuronal GPR75, severely restricting accessibility from the periphery.
- pancreatic islet beta cells — Blood Interstitial Facing · *Favorable*: GPR75 is functionally active at the beta cell surface, responding to exogenous CCL5 to elevate intracellular calcium. Pancreatic islets are richly vascularized without tight-junction barriers equivalent to BBB, so systemically delivered binders can access islet GPR75.
- adipocytes (adipose tissue) — Blood Interstitial Facing · *Favorable*: Adipocyte-specific GPR75 deletion modulates diet-induced obesity, implying functional surface GPR75 in adipocytes. Adipose tissue is well-perfused without restrictive epithelial barriers, making adipocyte GPR75 accessible to systemically delivered binders.
- retinal pigment epithelium (RPE) and perivascular retinal cells — Unknown · *Restricted*: GPR75 is expressed in RPE and perivascular cells of the retina. The blood-retina barrier (tight junctions in RPE and retinal endothelium) restricts systemic access to retinal GPR75, similar to the BBB, limiting accessibility for large-molecule binders delivered systemically.

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Weak
- domain: Unknown
- rationale: No evidence in the ledger documents restriction to a specific membrane subdomain (apical, junctional, synaptic, etc.). The BRET PM-marker assay shows broad plasma-membrane localization, and functional assays in beta cells and VSMCs are consistent with membrane-wide distribution. No relevant subdomain-fractionation or polarization data exist in the ledger.
- cites: a1_evi_05, a2_evi_06, a2_evi_23

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: GPR75 traffics efficiently to the plasma membrane in G-protein-null HEK293 cells lacking endogenous Gs/olf, Gq/11, and G12/13, demonstrating that surface residence does not require G-protein co-expression. No obligate co-receptor or chaperone for membrane targeting has been reported.
- cites: a1_evi_07

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | O95800 | ref | ref | 7 | 89 aa | 296 aa | 0 aa | Extracellular→Cytoplasmic | — |
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

- ECD class: Small
- rationale: GPR75 is a 7TM GPCR with a short N-terminal extracellular domain and three extracellular loops. Canonical class A GPCR ECDs (N-terminus + ECL1/2/3) typically sum to 30–60 accessible residues outside the membrane plane, placing GPR75 in the small class. Three N-glycosylation sites on the N-terminus are documented, which may assist folding but also limit accessible epitope surface.
- cites: a1_evi_02

**Epitope masking**

- severity: Low
- evidence: Inferred
- mechanism: Glycan
- rationale: Three N-glycosylation sites at N2, N12, and N25 of the extracellular N-terminus are annotated. Glycan shielding of the short N-terminal extracellular domain is a common concern for class A GPCRs, but no direct epitope-blocking or glycan-dependency experiment has been reported for GPR75 in the ledger. Risk is inferred from topology annotation.
- cites: a1_evi_02

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

37 entries · 22 primary · 15 secondary · 0 tertiary · 28 PMC OA.

- `a1_evi_01` · *Primary* · Supports · Topology — The original 1999 cloning paper (Tarttelin et al.) used protein sequence analysis to predict seven transmembrane domains for GPR75, establishing it as a GPCR with canonical 7TM topology. This is the primary source topology prediction from the discovery paper. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
  - *assay*: Human
  > "Protein sequence analysis predicts the presence of seven transmembrane domains, a characteristic feature of GPRs."
- `a1_evi_02` · *Secondary* · Supports · Topology — GPR75 contains the characteristic seven transmembrane spanning domains with N-glycosylation sites in the N-terminus (extracellular) and serine/threonine phosphorylation sites in the C-terminus (cytoplasmic). This supports the canonical class A GPCR topology: extracellular N-terminus, cytoplasmic C-terminus, 7TM architecture. Three N-glycosylation sites at N2, N12, and N25 (per UniProt) on the extracellular N-terminal domain are consistent with surface accessibility. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Human
  > "GPR75 contains the characteristic seven transmembrane spanning domains, N‐glycosylation sites in the N‐terminus and several serine and threonine phosphorylation sites in the C‐terminus (Tarttelin et al. 1999 )."
- `a1_evi_03` · *Secondary* · Supports · Topology — GPR75 is a 540-amino-acid protein encoded by 2 exons on chromosome 2p16. This structural annotation anchors the full-length protein used in surface-expression studies and confirms the protein size expected in WB experiments. ([PMC10495892](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10495892/))
  - *assay*: Human
  > "GPR75, first identified by Tarttelin et al. in 1999, is a 540-amino-acid protein with only two exons located on human chromosome 2p16."
- `a1_evi_04` · *Secondary* · Supports · Topology — GPR75 is described as a 540 amino acid member of the Gαq class of GPCRs with no homology to other classic GPCRs. As a Gαq-coupled receptor, it is expected to reside at the plasma membrane. This secondary review assertion supports the surface-expression classification for GPR75 but does not provide direct experimental surface evidence. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Human
  > "G-protein coupled receptor (GPCR) 75 (GPR75) is a 540 amino acid member of the G<sub>αq</sub> class of GPCRs, with no homology with other classic GPCRs."
- `a1_evi_05` · *Primary* · Supports · Surface Expression — In a BRET-based trafficking assay, GPR75 (along with most tested receptors) showed substantial BRET to a plasma membrane (PM) marker and less BRET to an ER marker, indicating efficient trafficking to the cell surface in HEK 293 cells. This is a direct functional surface-localization readout using a proximity-based PM marker assay without permeabilization. ([PMC8062009](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8062009/))
  - *assay*: Human · HEK 293 · live · non-permeabilized
  > "Most receptors showed substantial BRET to the PM marker, and less BRET to the ER marker, indicating efficient trafficking to the cell surface."
- `a1_evi_06` · *Secondary* · Ambiguous · Methodological — In the BRET surface-trafficking study, each receptor coding sequence was amplified with a common forward primer corresponding to a cleavable signal sequence and ligated into a pRluc8-N1 vector. The construct uses an exogenous cleavable signal sequence (not the native GPR75 signal), meaning the trafficking data represents OE with a foreign/chimeric signal peptide. This caps surface evidence confidence as supportive_indirect (evidence_tier=secondary per overexpression SP rules). The Rluc8 fusion is at the receptor C-terminus, which is cytoplasmic — consistent with intact-cell PM-marker BRET being a genuine surface readout. ([PMC8062009](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8062009/))
  - *assay*: Human · HEK 293 · live · non-permeabilized
  > "For each receptor the coding sequence was amplified with a common forward primer (corresponding to a cleavable signal sequence) and custom reverse primer (corresponding to the receptor C terminus) and ligated into a pRluc8-N1 cloning vector."
- `a1_evi_07` · *Secondary* · Supports · Surface Expression — GPR75 was coexpressed together with Gα subunit and Venus-Gβγ in genome-edited HEK 293 cells lacking endogenous Gs/olf, Gq/11, and G12/13 proteins. This overexpression system with G-protein-null HEK 293 cells provides a clean background for measuring receptor surface trafficking and G-protein coupling via BRET. OE construct used an exogenous cleavable signal sequence (per methods clip); evidence tier capped at secondary. ([PMC8062009](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8062009/))
  - *assay*: Human · HEK 293 (genome-edited, G-protein null) · live · non-permeabilized
  > "Receptors were coexpressed together with a Gα subunit and Venus-Gβγ in genome-edited HEK 293 cells lacking endogenous G s/olf , G q/11 and G 12/13 proteins [ 19 ]."
- `a1_evi_08` · *Secondary* · Ambiguous · Tissue Expression — GPR75 expression in pancreatic islets was measured by quantitative RT-PCR (mRNA) and GPR75 was detected by western blotting and immunohistochemistry — neither fractionation nor surface-specific biotinylation was performed. The western blot is whole-cell and the IHC is on fixed tissue, so these do not directly confirm cell-surface localization. These constitute non-surface expression observations qualifying the surface claim: GPR75 protein is present in islets but surface accessibility is not directly demonstrated by these methods. Antibody identity and validation controls are not described in this abstract clip. (https://pubmed.ncbi.nlm.nih.gov/23979485/)
  - *assay*: Human · pancreatic islets · fixed
  > "GPR75 is coupled to Gq to elevate intracellular calcium, so we investigated whether islets express this receptor and whether its activation by CCL5 increases beta cell calcium levels and insulin secretion.<h4>Methods</h4>Islet CCL5 receptor mRNA expression was measured by quantitative RT-PCR and GPR75 was detected in islets by western blotting and immunohistochemistry."
- `a1_evi_09` · *Primary* · Supports · Methodological — RT-PCR validation in GPR75 knockout (KO) mice confirmed specificity of the GPR75 amplicon: the expected 234-bp band was present in wild-type tissue and absent in GPR75 KO samples. This KO-validated RT-PCR specificity control supports the reliability of GPR75 expression measurements in the CNS study and provides a genetic loss-of-function validation anchor. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · CNS tissue (wild-type vs GPR75 KO)
  > "We observed the expected 234‐bp size of the GPR75 amplicon in WT tissue samples, and no band was detected in the GPR75 KO sample (Figure 1A )."
- `a1_evi_10` · *Secondary* · Ambiguous · Tissue Expression — GPR75 mRNA is reported as abundant in neurons of the mouse hippocampus (prior publication referenced in this 2026 paper). This is an RNA-level observation in CNS neurons without surface-method validation; it qualifies as a non-surface expression observation feeding the non_surface_expression list. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · hippocampal neurons
  > "We have previously established that GPR75 mRNA is abundant in neurons of the mouse hippocampus (Speidell et al. 2023 )."
- `a1_evi_11` · *Secondary* · Ambiguous · Tissue Expression — GPR75 mRNA is expressed in all analysed mouse CNS areas with regional variation — higher in brain regions than spinal cord. This RT-PCR mRNA-level observation lacks surface-method validation and feeds the non_surface_expression list as a qualifier indicating widespread CNS RNA presence without direct surface accessibility evidence. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · CNS tissue (multiple regions)
  > "All analysed CNS areas express GPR75 mRNA; however, there are clear fluctuations in the amount of expression, especially when comparing between brain areas and spinal cord (Figure 1B )."
- `a1_evi_12` · *Secondary* · Ambiguous · Tissue Expression — GPR75 mRNA expression is significantly higher in CNS tissues compared to peripheral tissues (spleen, kidney, heart), following patterns similar to the Human Protein Atlas. This is a comparative RNA-level tissue expression observation without surface-method validation, feeding the non_surface_expression list. The reference to Human Protein Atlas convergence provides secondary database corroboration. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · CNS vs peripheral tissues
  > "Further, GPR75 mRNA expression is significantly higher in the CNS when compared to peripheral tissues, such as spleen, kidney and heart (Figure 1C ), and follows a pattern similar to that previously described in the Human Protein Atlas."
- `a2_evi_01` · *Primary* · Supports · Tissue Expression — GPR75 transcript was localized by in situ hybridization to the retinal pigment epithelium (RPE) and to perivascular cells surrounding retinal arterioles in human retina sections; Northern blot of human RPE confirmed transcript presence. This establishes GPR75 expression in human retinal tissue, specifically in RPE cells and perivascular/arteriolar cells in the ganglion cell/nerve fiber layer. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
  - *assay*: Human · retinal pigment epithelium (RPE); perivascular cells surrounding retinal arterioles · fixed
  > "In situ hybridisation to human retina and Northern blot analysis of human retinal pigment epithelium (RPE) showed localisation of this transcript to the RPE and cells surrounding retinal arterioles."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — In mouse retina, GPR75 transcript was localized by in situ hybridization to photoreceptor inner segments and the outer plexiform layer — a distinct localization pattern from human retina where expression is in the RPE and perivascular cells. This constitutes a species difference in retinal cell-type distribution. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
  - *assay*: Mouse · photoreceptor inner segments; outer plexiform layer cells · fixed
  > "In contrast, the transcript was localised to the photoreceptor inner segments and the outer plexiform layer in mouse sections."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — Northern blot analysis of human tissues detected a 7 kb GPR75 transcript highly expressed in brain, establishing brain as the primary tissue of GPR75 expression at the RNA level. (https://pubmed.ncbi.nlm.nih.gov/10381362/)
  - *assay*: Human · brain tissue panel
  > "Northern blot analysis demonstrated a 7 kb transcript highly expressed in the brain."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — Both mouse and human pancreatic islets express GPR75 protein (detected by Western blot and IHC) and its ligand CCL5, confirming GPR75 protein-level presence in islet cells of both species. This places GPR75 in the context of pancreatic endocrine tissue. (https://pubmed.ncbi.nlm.nih.gov/23979485/)
  - *assay*: Human · pancreatic islets (mouse and human)
  > "Glucose homeostasis in lean and obese mice was determined by measuring glucose and insulin tolerance, and insulin secretion in vivo.<h4>Results</h4>Mouse and human islets express GPR75 and its ligand CCL5."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — GPR75 protein was detected in pancreatic islets by Western blotting and immunohistochemistry (IHC). Beta cells were confirmed as the relevant islet cell type through functional studies with CCL5-stimulated calcium elevation. This is primary protein-level evidence for GPR75 expression in pancreatic beta cells. (https://pubmed.ncbi.nlm.nih.gov/23979485/)
  - *assay*: Mouse · pancreatic islets; beta cells · fixed · permeabilized
  > "GPR75 is coupled to Gq to elevate intracellular calcium, so we investigated whether islets express this receptor and whether its activation by CCL5 increases beta cell calcium levels and insulin secretion.<h4>Methods</h4>Islet CCL5 receptor mRNA expression was measured by quantitative RT-PCR and GPR75 was detected in islets by western blotting and immunohistochemistry."
- `a2_evi_06` · *Primary* · Supports · Surface Expression — Exogenous CCL5 reversibly increased intracellular calcium in pancreatic beta cells via GPR75 activation (dependent on phospholipase C and calcium influx), demonstrating functional surface-accessible GPR75 in the beta cell plasma membrane. This constitutes a functional assay confirming surface availability of GPR75 in the pancreatic beta cell context. (https://pubmed.ncbi.nlm.nih.gov/23979485/)
  - *assay*: Mouse · pancreatic beta cells · live · non-permeabilized
  > "Exogenous CCL5 reversibly increased intracellular calcium in beta cells via GPR75, this phenomenon being dependent on phospholipase C activation and calcium influx."
- `a2_evi_07` · *Primary* · Supports · Surface Expression — CCL5 stimulated insulin secretion from mouse and human pancreatic islets in vitro and improved glucose tolerance in lean mice and in ob/ob (hyperglycaemia/insulin-resistance) mice via GPR75, indicating that GPR75 is functionally surface-accessible in pancreatic islets under both normal and obese/hyperglycaemic disease conditions. This supports accessibility in a metabolic disease context. (https://pubmed.ncbi.nlm.nih.gov/23979485/)
  - *assay*: Mouse · pancreatic islets (mouse and human) · live · non-permeabilized
  > "CCL5 also stimulated insulin secretion from mouse and human islets in vitro, and improved glucose tolerance in lean mice and in a mouse model of hyperglycaemia and insulin resistance (ob/ob)."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — GPR75 mRNA expression is abundant in the central nervous system (CNS) and significantly higher than in peripheral tissues (spleen, kidney, heart), consistent with the Human Protein Atlas distribution pattern. This establishes the CNS as the primary tissue compartment for GPR75 expression. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · CNS vs. spleen, kidney, heart
  > "GPR75 expression is abundant in the central nervous system (CNS) more so than in the peripheral tissues; however, much remains unknown about the distribution and role of this receptor throughout the CNS."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — GPR75 mRNA is expressed across all analyzed CNS regions with clear fluctuations, with higher expression in brain areas compared to spinal cord. This heterogeneous distribution across CNS subregions establishes differential CNS regional expression. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · CNS regions including brain and spinal cord
  > "All analysed CNS areas express GPR75 mRNA; however, there are clear fluctuations in the amount of expression, especially when comparing between brain areas and spinal cord (Figure 1B )."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — GPR75 mRNA expression is significantly higher in the CNS (brain and spinal cord) compared to peripheral tissues (spleen, kidney, heart), confirming CNS-enriched expression and aligning with Human Protein Atlas data. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · CNS vs. peripheral tissue panel
  > "Further, GPR75 mRNA expression is significantly higher in the CNS when compared to peripheral tissues, such as spleen, kidney and heart (Figure 1C ), and follows a pattern similar to that previously described in the Human Protein Atlas."
- `a2_evi_11` · *Secondary* · Supports · Tissue Expression — GPR75 mRNA is abundant in neurons of the mouse hippocampus, as previously established by Speidell et al. 2023. This provides cell-type-level resolution of CNS expression, placing GPR75 in hippocampal neurons specifically. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · hippocampal neurons
  > "We have previously established that GPR75 mRNA is abundant in neurons of the mouse hippocampus (Speidell et al. 2023 )."
- `a2_evi_12` · *Primary* · Supports · Tissue Expression — Single-cell or neuronal subtype analysis reveals GPR75 mRNA expression in multiple neuronal populations including GABAergic and glutamatergic neurons across the CNS. This establishes that GPR75 is not restricted to a single neurotransmitter-defined neuronal subtype. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · GABAergic neurons; glutamatergic neurons · fixed
  > "Our results show that GPR75 mRNA expression occurs in several neuronal populations including GABAergic and glutamatergic neurons."
- `a2_evi_13` · *Primary* · Supports · Tissue Expression — GPR75 mRNA is highly expressed in monoaminergic neurons in select brain areas: substantia nigra/ventral tegmental area (dopaminergic neurons), locus coeruleus (noradrenergic neurons), and raphe nucleus (serotonergic neurons). This places GPR75 in discrete monoaminergic neuron populations with functional implications for reward, stress, and arousal circuits. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · monoaminergic neurons (dopaminergic, noradrenergic, serotonergic) · fixed
  > "In select areas, such as the substantia nigra/ventral tegmental area, locus coeruleus and raphe nucleus, GPR75 mRNA is also highly expressed in monoaminergic neurons."
- `a2_evi_14` · *Primary* · Supports · Tissue Expression — GPR75 mRNA is highly expressed in both GABAergic and glutamatergic neurons of the cerebellum, suggesting a potential role in motor and equilibrium circuitry. This extends the CNS cell-type distribution to cerebellar neurons. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Mouse · cerebellar GABAergic and glutamatergic neurons · fixed
  > "Moreover, we found high expression of GPR75 mRNA in the cerebellum, in both GABAergic and glutamatergic neurons, suggesting a potential role for this receptor in motor/equilibrium activity."
- `a2_evi_15` · *Secondary* · Supports · Tissue Expression — GPR75 was originally characterized for its expression in the human retina (Tarttelin et al. 1999; Sauer et al. 2001), establishing retinal expression as one of the earliest documented tissue contexts for this receptor. ([PMC12920073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12920073/))
  - *assay*: Human · retina
  > "One GPCR that is considered an orphan receptor is GPCR 75 (GPR75), a 540 amino acid member of the G αq class of GPCRs, originally characterized for its expression in the human retina (Tarttelin et al. 1999 ; Sauer et al. 2001 )."
- `a2_evi_16` · *Primary* · Supports · Tissue Expression — Gpr75 mRNA is highly expressed in rat brain, including several hypothalamic nuclei, in both sexes. This constitutes primary evidence for GPR75 enrichment in hypothalamic neurons, relevant to energy balance regulation. ([PMC12702673](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12702673/))
  - *assay*: Rat · hypothalamic nuclei neurons · fixed
  > "Gpr75 was highly expressed in the brain, including several hypothalamic nuclei, in rats of both sexes."
- `a2_evi_17` · *Primary* · Supports · Tissue Expression — Hypothalamic Ccl5 expression is significantly upregulated in Gpr75 KO male rats on high-fat diet (HFD) compared to wild-type, suggesting that in the normal (WT) state GPR75 is functionally active at the surface of hypothalamic neurons and modulates CCL5 signaling during HFD-induced hyperphagia. Baseline: WT hypothalamic neurons under HFD. Modulating state: Gpr75 knockout. Change: increased Ccl5 expression. Implication: GPR75 surface activity in hypothalamus is engaged under diet-induced obese state. ([PMC12702673](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12702673/))
  - *assay*: Rat · hypothalamic tissue
  > "Notably, hypothalamic Ccl5 (encoding C-C motif chemokine ligand 5 [CCL5]) expression was significantly higher in Gpr75 KO male rats than in wild-type rats, suggesting that Gpr75 KO may prevent HFD-induced hyperphagia via central CCL5 signaling in rats."
- `a2_evi_18` · *Primary* · Supports · Tissue Expression — Loss-of-function GPR75 variants in humans are associated with leanness (genetic association), and Gpr75 null mice are protected from diet-induced obesity, establishing GPR75 as a functionally relevant receptor in adipose/metabolic tissue contexts and validating mouse KO as a model. ([PMC12916076](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12916076/))
  - *assay*: Human · human population cohort; adipose tissue (mouse KO model)
  > "Loss of function G-protein coupled receptor 75 (GPR75) variants in humans are associated with leanness, and Gpr75 null mice are protected from diet-induced obesity (DIO)."
- `a2_evi_19` · *Primary* · Supports · Tissue Expression — Adipocyte-specific Gpr75 deletion in mice was investigated for its contribution to diet-induced obesity, directly implicating adipocyte-expressed GPR75 as a tissue-relevant isoform in fat tissue. This establishes adipocytes as a cell type expressing functional GPR75. ([PMC12916076](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12916076/))
  - *assay*: Mouse · adipocytes (adipo-Gpr75-/- model)
  > "Here, we investigated the contribution of adipocyte-derived Gpr75 to DIO."
- `a2_evi_20` · *Primary* · Supports · Tissue Expression — Female adipo-Gpr75-/- mice showed 50% reduction in weight gain and adiposity on HFD vs WT, while male knockouts gained weight similarly to WT. This sex-dependent modulation indicates that GPR75 in adipocytes is functionally engaged in a sex-dependent and diet-state-dependent manner, with greater surface/functional relevance in female adipocytes under HFD conditions. ([PMC12916076](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12916076/))
  - *assay*: Mouse · adipocytes (female vs male adipo-Gpr75-/- mice)
  > "Female adipo-Gpr75<sup>-/-</sup> mice displayed a 50% (p < 0.001) decrease in weight gain and adiposity compared to WT, whereas male adipo-Gpr75<sup>-/-</sup> gained weight like WT mice."
- `a2_evi_21` · *Secondary* · Supports · Tissue Expression — Review-level assertion that GPR75 has been identified across various tissues and organs, where it contributes to biological regulation and disease progression. This is a general statement from a review without primary data but corroborates broad multi-tissue distribution. ([PMC12071931](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12071931/))
  - *assay*: Human · multiple tissues and organs
  > "G protein-coupled receptor 75 (GPR75), a novel member of the rhodopsin-like G protein-coupled receptor (GPCR) family, has been identified across various tissues and organs, where it contributes to biological regulation and disease progression."
- `a2_evi_22` · *Secondary* · Supports · Tissue Expression — GPR75 is expressed and functionally active in pulmonary artery smooth muscle cells (PASMCs), where CCL5 binding activates Gαi signaling to decrease cAMP and induce contraction. This establishes GPR75 cell-surface expression and functionality in vascular smooth muscle of the pulmonary circulation. ([PMC12071931](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12071931/))
  - *assay*: Unspecified · pulmonary artery smooth muscle cells (PASMCs) · live · non-permeabilized
  > "Additionally, in pulmonary artery smooth muscle cells (PASMCs), CCL5 decreases cAMP levels via Gα i signaling, thereby inducing contraction."
- `a2_evi_23` · *Secondary* · Supports · Surface Expression — GPR75 is expressed and functionally active in vascular smooth muscle cells (VSMCs), where 20-HETE binding activates Gαq/PLC signaling to increase IP3 and Ca2+ and induce contraction. This places GPR75 at the surface of systemic VSMCs and implicates it in vascular tone regulation. ([PMC12071931](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12071931/))
  - *assay*: Unspecified · vascular smooth muscle cells (VSMCs) · live · non-permeabilized
  > "In contrast, 20-HETE, a high-affinity ligand for GPR75, induces contraction in vascular smooth muscle cells (VSMCs) by activating the Gα q /PLC pathway, leading to increased IP 3 and Ca 2+ levels."
- `a2_evi_24` · *Primary* · Supports · Tissue Expression — In NIT-1 mouse pancreatic beta cells, GPR75 mRNA levels were significantly increased at 60 min with 10 nM liraglutide treatment (GLP-1 receptor agonist), while no time- or dose-dependent pattern was observed at other concentrations/timepoints. Baseline: untreated NIT-1 beta cells. Modulating state: 60 min 10 nM liraglutide. Change: statistically significant GPR75 mRNA upregulation. Implication: GLP-1R agonist signaling upregulates GPR75 transcript in beta cells, potentially increasing surface receptor availability. ([PMC12058015](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12058015/))
  - *assay*: Mouse · NIT-1 pancreatic beta cells
  > "We did not detect any time- and dose-dependent changes in all investigated genes, instead we found a statistically significant increase in mRNA levels of GPR75, GPR56, M3R and CB1R genes at 60 min with 10nM liraglutide and a slight and statistically significant decrease in GLP1R mRNA levels in response to 1000nM liraglutide treatment compared to 10nM and 100nM concentrations at all tested time points, as shown in the figure ."
- `a2_evi_25` · *Secondary* · Supports · Tissue Expression — GPR75 is expressed in neuronal cells where the CCL5/GPR75 axis activates DAG/PKC → AKT/MAPK signaling to inhibit Aβ-induced neuronal apoptosis and confer neuroprotection. This functional context implies surface-accessible GPR75 on neurons relevant to Alzheimer's disease. ([PMC12071931](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12071931/))
  - *assay*: Unspecified · neurons · live · non-permeabilized
  > "The CCL5/GPR75 axis also stimulates the DAG/PKC pathway, leading to the activation of AKT and MAPK signaling, which inhibits Aβ-induced neuronal apoptosis and confers neuroprotection."

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

*Confidence moderate — Confidence is moderate because direct surface-localization evidence is limited to a single BRET proximity assay using an overexpression construct with an exogenous signal peptide (PMC:PMC8062009) — no live-cell flow cytometry, surface biotinylation, or non-permeabilized antibody staining with an endogenous construct is in the literature. The functional assays in pancreatic beta cells and vascular smooth muscle (PMID:23979485) provide strong indirect support but do not directly image or quantify surface GPR75. Lifting confidence to high would require at least one direct surface-localization experiment on endogenous GPR75 — for example, live-cell immunostaining with a validated extracellular-epitope antibody, or surface biotinylation mass spectrometry in a GPR75-expressing primary cell type.*

## CellxGene RNA enrichment (CZI Census)

*Schema v2.1.11 · CZI Census 2025-11-08 · τ-cutoff classification (Yanai 2005, PMID 15388519) on linear population mean (mean × pct, ≈ nTPM) over the full measured universe with a 1e-3 noise floor: τ≥0.85 enriched, 0.5–0.85 enhanced, <0.5 low specificity, no eligibles not detected. Cutoffs from Kryuchkova-Mostacci & Robinson-Rechavi 2017 (PMID 26891983) + Lüleci & Yılmaz 2022. Cell ontology graph (cl-basic.obo) walked to ~150 cell-family terms; UBERON ontology walked to ~150 organ-level tissues. CC-BY 4.0 (CZI Census).*

**Classification:**

- **Cell class (CL ontology graph, ~10 compartments):** not detected
- **Cell type (leaf Cell Ontology terms, ~600):** not detected · τ=0.99
- **Tissue (UBERON terms, ~56):** not detected · τ=0.99

**Top 5 cell types (leaf CL, pooled across tissues):**

| Cell type | CL ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| kidney loop of Henle ascending limb epithelial cell | CL:1001016 | 1.756 | 1.92% | 202 / 10,531 |
| visceromotor neuron | CL:0005025 | 2.343 | 0.49% | 3 / 610 | (trace)
| dermis microvascular lymphatic vessel endothelial cell | CL:2000041 | 2.078 | 0.33% | 2 / 603 | (trace)
| mature neutrophil | CL:0000096 | 2.272 | 0.11% | 1 / 906 | (trace)
| IgA plasmablast | CL:0000984 | 2.141 | 0.10% | 1 / 956 | (trace)

**Top 5 tissues (UBERON, pooled across cell types):**

| Tissue | UBERON ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| eye | UBERON:0000970 | 1.671 | 15.30% | 3,455 / 22,576 |
| brain | UBERON:0000955 | 1.878 | 2.12% | 5,393 / 254,285 |
| heart | UBERON:0000948 | 1.767 | 0.77% | 70 / 9,037 | (trace)
| adipose tissue | UBERON:0001013 | 1.759 | 0.65% | 39 / 6,041 | (trace)
| small intestine | UBERON:0002108 | 1.624 | 0.39% | 19 / 4,915 | (trace)

<!-- /cellxgene -->
