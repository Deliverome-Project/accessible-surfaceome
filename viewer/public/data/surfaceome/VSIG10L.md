# VSIG10L — Surface Accessibility Brief

*Schema v2.13.0 · generated 2026-06-24T16:22:42.269025Z · model `claude-sonnet-4-6`*

> VSIG10L has weak surface evidence as a tissue-restricted single-pass type I membrane protein in normal esophageal squamous epithelium. Supportive but indirect evidence: computational topology prediction of a signal peptide, large Ig-domain ECD, and single TM helix (a1_evi_01), corroborated by RNA-level expression in suprabasal squamous cells via RNAscope ISH (a1_evi_04) and qRT-PCR across 238 clinical samples (a1_evi_05); no live-cell flow, surface biotinylation, or non-permeabilized IF has been performed, and validated antibody reagents are absent (a1_evi_03). Surface presence is strictly tissue-restricted to suprabasal squamous esophageal epithelium and is markedly lost in Barrett esophagus-associated lesions, GERD-affected mucosa, and all neoplastic states (a2_evi_01, a2_evi_03, a2_evi_07). Moderate apical subdomain restriction in a stratified epithelium limits systemic binder access; no shed or secreted form is documented, ruling out decoy concerns.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:27111](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:27111) |
| UniProt | [Q86VR7](https://www.uniprot.org/uniprotkb/Q86VR7) |
| NCBI Gene | [147645](https://www.ncbi.nlm.nih.gov/gene/147645) |
| Ensembl | [ENSG00000186806](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000186806) |
| Subcategory | Single-pass type I |
| Surface accessibility | Low |
| Confidence | Low |
| Evidence grade | Weak |
| Triage signal | Unlikely |

## 1. Executive summary

**Surface-accessible only on suprabasal squamous epithelial cells of the normal esophagus; expression and inferred surface presence are lost in Barrett esophagus, GERD-affected mucosa, and esophageal adenocarcinoma.**

VSIG10L has weak surface evidence as a tissue-restricted single-pass type I membrane protein in normal esophageal squamous epithelium. Supportive but indirect evidence: computational topology prediction of a signal peptide, large Ig-domain ECD, and single TM helix (a1_evi_01), corroborated by RNA-level expression in suprabasal squamous cells via RNAscope ISH (a1_evi_04) and qRT-PCR across 238 clinical samples (a1_evi_05); no live-cell flow, surface biotinylation, or non-permeabilized IF has been performed, and validated antibody reagents are absent (a1_evi_03). Surface presence is strictly tissue-restricted to suprabasal squamous esophageal epithelium and is markedly lost in Barrett esophagus-associated lesions, GERD-affected mucosa, and all neoplastic states (a2_evi_01, a2_evi_03, a2_evi_07). Moderate apical subdomain restriction in a stratified epithelium limits systemic binder access; no shed or secreted form is documented, ruling out decoy concerns.

**Family / classification** — HGNC gene group(s): Immunoglobulin like domain containing · functional class: Miscellaneous.

**Triage first-pass reasoning** — VSIG10L (Q86VR7) is annotated as nucleoplasmic by Alliance of Genome Resources. Despite the 'V-set and immunoglobulin domain containing' name suggesting potential surface biology, the actual localization evidence points to nuclear/nucleoplasmic residence. Checking contextual buckets: (1) cell_state_induced — no published evidence of stress/activation-induced PM display; (2) tissue_restricted_surface — no flow cytometry or surface proteomics data showing surface display in any lineage; (3) lysosomal_exocytosis — no lysosomal TM topology reported; (4) dual_localization — no documented PM pool; (5) stable_surface_attachment — secreted/extracellular anchoring not reported. No therapeutic antibody/ADC/CAR-T program engaging cell-surface VSIG10L is known. The Ig-like domain naming reflects domain architecture not necessarily surface localization. Best classification: nuclear.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=Low · conf=Low · subcategory=Single-pass type I · ecd=Large |
| Classification | reason=Tissue Restricted Surface · family=Miscellaneous · state-dependence=High · induction-trigger=None |
| Expression | level=High · breadth=Rare · specificity=Mixed · low-endogenous=false · tumor-associated=false · orphan-receptor=true · OE-precedent=false |
| Risks | shed=false · secreted=false · co-receptor=None · masking=false · restricted-subdomain=true |
| Evidence | grade=Weak · density=Moderate · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=73.5% · cyno=— |
| Paralogs | max %ECD identity = 46.5% |
| Topology | TM=1 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: High RNA expression in normal esophageal suprabasal squamous cells by RNAscope ISH (a1_evi_04) and qRT-PCR across 238 clinical samples (a2_evi_03, a2_evi_04); expression is absent in Barrett lesions and reduced in GERD (a2_evi_06, a2_evi_07).
- *Expression breadth*: Expression is confined to suprabasal squamous epithelial cells of the esophagus; absent in basal cells (a2_evi_01) and lost in all non-squamous esophageal disease states (a2_evi_03, a2_evi_06); no evidence of expression in other tissues.
- *Surface specificity*: Canonical topology predicts a type I single-pass membrane protein with a large extracellular Ig-domain ECD (a1_evi_01), but no protein-level surface assay has been performed; surface vs. intracellular distribution is inferred from topology alone.
- *Known ligand*: No validated endogenous ligand or binding partner for VSIG10L is reported in the literature. The protein is functionally implicated in epithelial maturation and desmosome integrity (a2_evi_08), but no cognate receptor or natural agonist has been identified.
- *Low endogenous expression*: High RNA expression in normal esophageal suprabasal squamous cells by RNAscope ISH (a1_evi_04) and qRT-PCR across 238 clinical samples (a2_evi_03, a2_evi_04); expression is absent in Barrett lesions and reduced in GERD (a2_evi_06, a2_evi_07).
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Weak

The entire VSIG10L ledger contains zero direct surface-accessibility observations. The strongest topology claim is a computational prediction of a single-pass type I TM architecture with a large ECD (a1_evi_01), corroborated by a review-level assertion (a1_evi_02) — both are tangential to surface accessibility because neither uses a live-cell or nonperm assay. All remaining claims are RNA-level: RNAscope ISH in suprabasal squamous esophageal cells (a1_evi_04, a1_evi_07) and qRT-PCR across n=238 normal vs Barrett esophagus samples (a1_evi_05, a1_evi_06). A critical methodological note (a1_evi_03) explicitly documents the absence of validated VSIG10L antibodies, explaining why no protein-level or surface assay was attempted. No live-cell flow, nonperm IF, surface biotinylation, IHC membranous, or functional surface assay is present. With zero direct or indirect surface-method observations and only RNA-level expression data plus a computational topology prediction, the grade is weak.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Low | Computational topology prediction (single-pass type I TM); no experimental surface localization data. |
| a1_evi_02 | Tangential | Low | Review-level assertion of membrane-bound topology; no primary experimental surface evidence cited. |
| a1_evi_03 | Expression Only | Low | Methodological note: absence of validated VSIG10L antibodies; ISH used instead; no surface assay possible. |
| a1_evi_04 | Expression Only | Moderate | RNAscope ISH RNA-level only; suprabasal SQ esophagus; no protein or surface localization assessed. |
| a1_evi_05 | Expression Only | Moderate | RT-qPCR RNA expression in normal squamous esophagus vs Barrett lesions; no surface assay. |
| a1_evi_06 | Expression Only | Moderate | qRT-PCR quantification in n=238 samples; RNA-level only; no protein or surface assay performed. |
| a1_evi_07 | Expression Only | Moderate | ISH spatial RNA localization in normal esophageal squamous tissue; no protein surface localization assessed. |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Suprabasal squamous epithelial cells, human esophagus (normal tissue); RNAscope ISH showing selective suprabasal expression | Primary Human Tissue | Single Cell RNA | High | 2 |
| Normal squamous esophagus vs Barrett esophagus-associated lesions (metaplasia, dysplasia, adenocarcinoma); n=238 clinical samples; high in normal SQ, markedly lost in Barrett lesions | Patient Sample | RNA | High | 2 |
| EPC2 human esophageal squamous epithelial cell line grown as 3D-organotypes; ISH used due to lack of validated antibodies | Established Cell Line | Single Cell RNA | Moderate | 1 |

## 4. Biological context

**Biological-context grade** · Rich

Expression is mapped across multiple tissues/cell states (normal esophageal suprabasal vs basal, GERD, Barrett metaplasia/dysplasia/adenocarcinoma) via scRNA-seq, RT-qPCR, ISH, and RNA-seq from two independent sources. Subcellular localization is supported by sequence-predicted membrane topology with Ig-like ectodomain. Anatomical context is pinned to esophageal squamous epithelium. Modulation across disease states (GERD, Barrett, bile-acid stress in mouse) is well-documented. All axes cohere consistently. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_07, a2_evi_08, +5)*

**Expression × cell type × disease context**

| Tissue | Cell type | Disease context | Level (protein) | Cell states |
|---|---|---|---|---|
| esophagus | suprabasal squamous epithelial cells | Normal | High | — |
| esophagus | squamous epithelium | Normal | High | — |
| esophagus | squamous epithelium | Other Disease (Barrett esophagus-associated lesions (metaplasia, dysplasia, adenocarcinoma)) | Absent | — |
| esophagus | squamous epithelium | Other Disease (chronic gastroesophageal reflux disease (GERD)) | Low | — |
| esophagus | squamous epithelial cells | Other Disease (familial Barrett esophagus / esophageal adenocarcinoma predisposition (inherited VSIG10L mutation)) | Absent | — |
| squamous mucosa (forestomach equivalent) | squamous epithelial cells | Other Disease (Vsig10l germline mutation — loss of desmosomes and disrupted epithelial differentiation) | Unknown | — |
| forestomach | squamous epithelium | Other Disease (Barrett esophagus-like metaplasia (Vsig10l-mutant mice on bile acid diet)) | Absent | — |

**Primary subcellular compartment**: Plasma membrane

**Accessibility modulation**

- *Tissue Restricted Surface* · lineage: Epithelial: null → null — VSIG10L is a membrane-bound protein with extracellular Ig-like domains expressed selectively in suprabasal squamous epithelial cells of the esophagus, with no detectable expression in basal squamous cells, restricting surface presence to the suprabasal compartment. *(→ Surface Accessibility Of VSIG10L Is Confined To Suprabasal Squamous Epithelial Cells Of The Esophagus; Basal Cells And Non-Squamous Lineages Lack Surface-Accessible VSIG10L, Limiting Binder Access To The Suprabasal Epithelial Layer.)* *(cites: a2_evi_01, a2_evi_02, a2_evi_12, a2_evi_13)*
- *Disease State Induced*: normal squamous esophageal epithelium → Barrett esophagus-associated lesions (metaplasia, dysplasia, adenocarcinoma) — VSIG10L expression is high in normal squamous esophagus but is markedly lost in Barrett esophagus-associated lesions including metaplasia, dysplasia, and adenocarcinoma, as shown by RT-qPCR across 238 samples and in situ hybridization. *(→ Loss Of VSIG10L Surface Expression In Barrett Esophagus And Associated Neoplastic Lesions Means The Protein Is Not Accessible To Extracellular Binders In These Disease States; Therapeutic Or Diagnostic Targeting Would Be Limited To Residual Normal Squamous Epithelium.)* *(cites: a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_11)*
- *Disease State Induced*: normal esophageal squamous epithelium → chronic gastroesophageal reflux disease (GERD)-affected esophageal epithelium — VSIG10L expression is frequently lost in esophageal epithelium of patients with chronic GERD, a precursor state to Barrett esophagus, indicating disease-state-driven reduction of surface-expressed VSIG10L. *(→ Reduced VSIG10L Surface Expression In GERD-Affected Epithelium Diminishes The Accessible Target Pool In This At-Risk Patient Population, Potentially Before Overt Metaplastic Transformation Occurs.)* *(cites: a2_evi_07)*

**Restricted-subdomain distribution**

- present: true
- severity: Moderate
- evidence: Moderate
- domain: Apical
- rationale: VSIG10L RNA is selectively expressed in suprabasal squamous epithelial cells of the esophagus (a1_evi_04, a2_evi_01, a2_evi_02), a stratified epithelium where suprabasal cells face the luminal/apical surface. Expression is absent in basal cells (a2_evi_01). This cell-layer restriction implies the protein resides on the apical/luminal face of a polarized epithelium, potentially limiting systemic binder access.
- cites: a1_evi_04, a2_evi_01, a2_evi_02

**Co-receptor requirements**

- dependency: None
- evidence basis: Co Expression Only
- rationale: VSIG10L is annotated as a single-pass type I membrane protein with a signal peptide and large ECD (a1_evi_01). No ledger entry documents a chaperone, escort, or obligate trafficking partner required for surface expression. The membrane association is entirely topology-driven (signal peptide + TM helix); no co-receptor dependency is described.
- cites: a1_evi_01

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | Q86VR7 | ref | ref | 1 | 755 aa | 70 aa | 21 aa | Extracellular→Cytoplasmic | — |
| Isoform | Q86VR7-2 | Q86VR7-2 | 97.6% | 100.0% | 1 | 755 aa | 84 aa | 21 aa | Extracellular→Cytoplasmic | — |
| Mouse ortholog | Vsig10l | [D3YZF7](https://www.uniprot.org/uniprotkb/D3YZF7) | 69.2% | 73.5% | 1 | 742 aa | — | — | — | moderate |
| Paralog | HMCN2 | [Q8NDA2](https://www.uniprot.org/uniprotkb/Q8NDA2) | 17.9% | 46.5% | — | — | — | — | — | low-risk |
| Paralog | MXRA5 | [Q9NR99](https://www.uniprot.org/uniprotkb/Q9NR99) | 20.0% | 38.8% | — | — | — | — | — | low-risk |
| Paralog | ROBO4 | [Q8WZ75](https://www.uniprot.org/uniprotkb/Q8WZ75) | 15.9% | 34.2% | — | — | — | — | — | low-risk |
| Paralog | IGSF10 | [Q6WRI0](https://www.uniprot.org/uniprotkb/Q6WRI0) | 20.3% | 33.1% | — | — | — | — | — | low-risk |
| Paralog | SDK2 | [Q58EX2](https://www.uniprot.org/uniprotkb/Q58EX2) | 17.0% | 32.3% | — | — | — | — | — | low-risk |
| Paralog | PTPRQ | [Q9UMZ3](https://www.uniprot.org/uniprotkb/Q9UMZ3) | 13.8% | 31.7% | — | — | — | — | — | low-risk |
| Paralog | VSIG10 | [Q8N0Z9](https://www.uniprot.org/uniprotkb/Q8N0Z9) | 8.2% | 30.5% | — | — | — | — | — | low-risk |
| Paralog | CNTN5 | [O94779](https://www.uniprot.org/uniprotkb/O94779) | 16.8% | 30.5% | — | — | — | — | — | low-risk |
| Paralog | DSCAML1 | [Q8TD84](https://www.uniprot.org/uniprotkb/Q8TD84) | 14.6% | 30.5% | — | — | — | — | — | low-risk |
| Paralog | SDK1 | [Q7Z5N4](https://www.uniprot.org/uniprotkb/Q7Z5N4) | 16.7% | 28.7% | — | — | — | — | — | low-risk |
| Paralog | IGSF21 | [Q96ID5](https://www.uniprot.org/uniprotkb/Q96ID5) | 7.4% | 28.7% | — | — | — | — | — | low-risk |
| Paralog | IGDCC3 | [Q8IVU1](https://www.uniprot.org/uniprotkb/Q8IVU1) | 13.5% | 28.6% | — | — | — | — | — | low-risk |
| Paralog | CNTN2 | [Q02246](https://www.uniprot.org/uniprotkb/Q02246) | 17.2% | 28.5% | — | — | — | — | — | low-risk |
| Paralog | DSCAM | [O60469](https://www.uniprot.org/uniprotkb/O60469) | 14.3% | 28.5% | — | — | — | — | — | low-risk |
| Paralog | CHL1 | [O00533](https://www.uniprot.org/uniprotkb/O00533) | 14.0% | 28.2% | — | — | — | — | — | low-risk |
| Paralog | CNTN4 | [Q8IWV2](https://www.uniprot.org/uniprotkb/Q8IWV2) | 16.1% | 27.7% | — | — | — | — | — | low-risk |
| Paralog | ROBO3 | [Q96MS0](https://www.uniprot.org/uniprotkb/Q96MS0) | 17.1% | 27.3% | — | — | — | — | — | low-risk |
| Paralog | NFASC | [O94856](https://www.uniprot.org/uniprotkb/O94856) | 16.1% | 26.8% | — | — | — | — | — | low-risk |
| Paralog | IGSF9 | [Q9P2J2](https://www.uniprot.org/uniprotkb/Q9P2J2) | 14.8% | 26.7% | — | — | — | — | — | low-risk |
| Paralog | NEO1 | [Q92859](https://www.uniprot.org/uniprotkb/Q92859) | 15.2% | 26.2% | — | — | — | — | — | low-risk |
| Paralog | L1CAM | [P32004](https://www.uniprot.org/uniprotkb/P32004) | 16.1% | 26.1% | — | — | — | — | — | low-risk |
| Paralog | CDON | [Q4KMG0](https://www.uniprot.org/uniprotkb/Q4KMG0) | 13.4% | 26.0% | — | — | — | — | — | low-risk |
| Paralog | NRCAM | [Q92823](https://www.uniprot.org/uniprotkb/Q92823) | 16.8% | 25.8% | — | — | — | — | — | low-risk |
| Paralog | CNTN1 | [Q12860](https://www.uniprot.org/uniprotkb/Q12860) | 15.2% | 25.6% | — | — | — | — | — | low-risk |
| Paralog | ROBO1 | [Q9Y6N7](https://www.uniprot.org/uniprotkb/Q9Y6N7) | 16.8% | 25.0% | — | — | — | — | — | low-risk |
| Paralog | CNTN6 | [Q9UQ52](https://www.uniprot.org/uniprotkb/Q9UQ52) | 16.5% | 24.9% | — | — | — | — | — | low-risk |
| Paralog | ROBO2 | [Q9HCK4](https://www.uniprot.org/uniprotkb/Q9HCK4) | 16.5% | 24.9% | — | — | — | — | — | low-risk |
| Paralog | PRTG | [Q2VWP7](https://www.uniprot.org/uniprotkb/Q2VWP7) | 14.9% | 24.8% | — | — | — | — | — | low-risk |
| Paralog | DCC | [P43146](https://www.uniprot.org/uniprotkb/P43146) | 15.5% | 24.6% | — | — | — | — | — | low-risk |
| Paralog | CNTN3 | [Q9P232](https://www.uniprot.org/uniprotkb/Q9P232) | 17.6% | 24.1% | — | — | — | — | — | low-risk |
| Paralog | VCAM1 | [P19320](https://www.uniprot.org/uniprotkb/P19320) | 9.5% | 24.0% | — | — | — | — | — | low-risk |
| Paralog | NCAM1 | [P13591](https://www.uniprot.org/uniprotkb/P13591) | 14.8% | 23.7% | — | — | — | — | — | low-risk |
| Paralog | IGSF9B | [Q9UPX0](https://www.uniprot.org/uniprotkb/Q9UPX0) | 14.2% | 22.9% | — | — | — | — | — | low-risk |
| Paralog | IGDCC4 | [Q8TDY8](https://www.uniprot.org/uniprotkb/Q8TDY8) | 14.2% | 22.8% | — | — | — | — | — | low-risk |
| Paralog | NCAM2 | [O15394](https://www.uniprot.org/uniprotkb/O15394) | 15.1% | 22.0% | — | — | — | — | — | low-risk |
| Paralog | BOC | [Q9BWV1](https://www.uniprot.org/uniprotkb/Q9BWV1) | 13.8% | 21.9% | — | — | — | — | — | low-risk |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak
- rationale: No relevant data in the ledger. No ledger entry documents proteolytic release of the VSIG10L ectodomain, identification of a sheddase, or detection of soluble VSIG10L in supernatant or serum.

**Secreted form**

- present: false
- severity: Low
- evidence: Weak
- rationale: No relevant data in the ledger. No ledger entry documents a soluble splice isoform lacking the TM domain, nor any free soluble VSIG10L protein in serum or plasma. All expression evidence is RNA-level or topology-prediction; no secreted/soluble protein form is described.

**ECD size assessment**

- ECD class: Large
- rationale: ECD length 755 residues (>=200) -> large; computed deterministically from DeepTMHMM topology.

**Epitope masking**

- severity: None
- evidence: Weak
- mechanism: None
- rationale: No ledger entry documents homo-oligomerization burying extracellular epitopes, a hetero-complex partner covering the ECD, glycan shielding, or proteolytic removal of the ectodomain. The deterministic AF2 prior indicates is_homo_oligomer=false. With a large, Ig-domain-containing ECD and no documented masking, no epitope masking risk is supported by the ledger.

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-Q86VR7-F1](https://alphafold.ebi.ac.uk/entry/Q86VR7) |
| AFDB version | v6 |
| ECD mean pLDDT | 73.2 |
| ECD disordered fraction | 31.9% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/Q86VR7) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [Q86VR7](https://alphafold.ebi.ac.uk/entry/Q86VR7) | AlphaFold DB (AF-Q86VR7-F1, v6) |
| Isoform Q86VR7-2 | [Q86VR7-2](https://alphafold.ebi.ac.uk/entry/Q86VR7-2) | AlphaFold DB |
| Mouse ortholog (Vsig10l) | [D3YZF7](https://alphafold.ebi.ac.uk/entry/D3YZF7) | AlphaFold DB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

V-set and immunoglobulin domain-containing protein 10-like · Miscellaneous · StructuralAndAdhesion · chain A · 3 scored sites · 6,464 binder seeds (2,277 α-helix / 4,187 β-strand).

Anchor = patch-center residue; BSA = buried surface area (the contact footprint a binder would form on the patch); seed counts are docked binder backbones split by α-helix / β-strand.

**Reading the scores.** BSA vs the average antibody–antigen interface ≈ 1103 ± 244 Å² ([PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)): ≥1500 Å² comfortable · 850–1500 workable · <850 thin. Seed pool: ≥1000 comfortable design margin · ≥100 workable · <100 thin/specialized. SURFACE-Bind excludes transmembrane regions but not necessarily intracellular domains — cross-check the anchor residue against the topology string in §5/appendix (`O` = extracellular/antibody-accessible, `I` = intracellular).

| Site | Anchor residue | BSA (Å²) | α-helix seeds | β-strand seeds | Hydrophobicity |
|---|---|---|---|---|---|
| 0 | 223 | 1158.2 | 1,479 | 1,955 | 10.3 |
| 1 | 199 | 1767.0 | 45 | 168 | 30.0 |
| 2 | 735 | 2443.0 | 753 | 2,064 | 5.8 |

## 9. Evidence ledger

20 entries · 11 primary · 9 secondary · 0 tertiary · 20 PMC OA.

- `a1_evi_01` · *Secondary* · Supports · Topology — VSIG10L gene product is predicted to be a single-pass type I membrane-bound protein with 2 immunoglobulin (Ig)-like domains, 2 Ig-like folds, and a small cytoplasmic domain. This is the most detailed topology description available and is consistent with UniProt annotation (signal peptide aa1-27, large ECD aa28-776, single TM helix aa777-797, cytoplasmic tail aa798-867). ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human
  > "The predicted VSIG10L gene product is a membrane-bound protein with 2 immunoglobulin (Ig)-like domains, 2 Ig-like folds, and a small cytoplasmic domain ( Figure 4 )."
- `a1_evi_02` · *Secondary* · Supports · Topology — VSIG10L is described as a membrane-bound protein with immunoglobulin (Ig)-like domains, predominantly expressed in squamous (SQ) cells. This review-level assertion corroborates the single-pass TM topology but adds no new experimental surface localization data. ([PMC12960849](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12960849/))
  - *assay*: Human
  > "VSIG10L is predominantly expressed in SQ cells, and its gene product encodes a membrane-bound protein with immunoglobulin (Ig)-like domains 14 ."
- `a1_evi_03` · *Secondary* · Ambiguous · Methodological — Due to the lack of optimized VSIG10L antibodies, the authors developed custom RNAscope in situ hybridization probes to assess VSIG10L expression in human and porcine esophagus and in human SQ epithelial cells (EPC2) grown as 3D-organotypes. This methodological note documents the absence of validated antibody reagents for VSIG10L, which is a critical gap for surface protein validation. ([PMC12960849](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12960849/))
  - *assay*: Human · EPC2 / human esophagus tissue · fixed
  > "Given the lack of optimized VSIG10L antibodies, we developed custom RNAscope-in situ hybridization probes and subsequently assessed its expression in representative human and porcine esophagus, as well as in human SQ epithelial cells (EPC2) grown as 3D-organotypes 17 , 18 ."
- `a1_evi_04` · *Secondary* · Ambiguous · Tissue Expression — RNAscope in situ hybridization shows VSIG10L RNA is selectively and consistently expressed in suprabasal squamous cells of the esophagus, with no detectable expression in basal squamous cells. This is RNA-level evidence only; no protein surface localization was assessed. Feeds non_surface_expression as RNA-high with no surface validation. ([PMC12960849](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12960849/))
  - *assay*: Human · suprabasal SQ cells, human esophagus · fixed
  > "As shown in Fig. 1 , we found VSIG10L RNA to be selectively and consistently expressed in suprabasal SQ cells, with no detectable expression in basal squamous cells, suggesting a possible role of VSIG10L in epithelial maturation."
- `a1_evi_05` · *Secondary* · Ambiguous · Tissue Expression — VSIG10L exhibits high mRNA/RNA expression in normal squamous esophagus with marked loss of expression in Barrett-associated lesions (metaplasia, dysplasia, adenocarcinoma). This is RNA-level evidence from a clinical cohort study; no protein surface localization was assessed. Feeds non_surface_expression. ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human · normal squamous esophagus and Barrett lesions
  > "VSIG10L exhibited high expression in normal squamous esophagus with marked loss of expression in Barrett-associated lesions."
- `a1_evi_06` · *Secondary* · Ambiguous · Tissue Expression — qRT-PCR was used to quantify VSIG10L expression in n=238 normal squamous esophagus samples and stage-specific Barrett esophagus-associated lesions. This is the primary RNA quantification method for VSIG10L expression data in this study; no protein or surface assay was performed. ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human · normal squamous esophagus and BE lesions (n=238)
  > "We performed quantitative real-time polymerase chain reaction to determine VSIG10L expression in a random set of (n = 238) normal squamous esophagus and stage-specific BE-associated lesions ( Figure 3 )."
- `a1_evi_07` · *Secondary* · Ambiguous · Tissue Expression — In situ hybridization of VSIG10L transcript in normal esophageal squamous tissue confirmed and spatially localized mRNA expression. This is RNA-level spatial evidence only; no protein surface localization was assessed. Feeds non_surface_expression. ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human · normal esophageal squamous tissue · fixed
  > "In situ hybridization of VSIG10L transcript of normal esophagus squamous tissue confirmed and localized expression (see eFigure 3 in the Supplement )."
- `a2_evi_01` · *Primary* · Supports · Tissue Expression — VSIG10L RNA is selectively and consistently expressed in suprabasal squamous (SQ) cells of the esophageal epithelium, with no detectable expression in basal squamous cells, suggesting a role in epithelial maturation. This cell-state distinction (suprabasal vs basal) is a key expression boundary. ([PMC12960849](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12960849/))
  - *assay*: Human · suprabasal squamous epithelial cells, esophageal mucosa · unspecified
  > "As shown in Fig. 1 , we found VSIG10L RNA to be selectively and consistently expressed in suprabasal SQ cells, with no detectable expression in basal squamous cells, suggesting a possible role of VSIG10L in epithelial maturation."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — Using mammalian tissues and patient-derived organoids, VSIG10L is selectively expressed in suprabasal squamous cells of the esophageal mucosa and is essential for epithelial maturation and homeostasis. This confirms cell-type-restricted expression in normal esophageal squamous epithelium. ([PMC12960849](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12960849/))
  - *assay*: Human · suprabasal squamous epithelial cells, esophageal mucosa; patient-derived organoids · unspecified
  > "Using mammalian tissues and patient-derived organoids, we show VSIG10L is selectively expressed in the suprabasal squamous cells of the esophageal mucosa and is essential for epithelial maturation and homeostasis."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — VSIG10L exhibits high expression in normal squamous esophagus with marked loss of expression in Barrett esophagus-associated lesions (metaplasia, dysplasia, adenocarcinoma). This is the core disease-context expression contrast for VSIG10L. ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human · normal squamous esophagus and Barrett esophagus-associated lesions (n=238) · unspecified
  > "VSIG10L exhibited high expression in normal squamous esophagus with marked loss of expression in Barrett-associated lesions."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — Quantitative real-time PCR was used to measure VSIG10L expression across n=238 normal squamous esophagus samples and stage-specific Barrett esophagus-associated lesions, providing the quantitative basis for the high-normal / low-disease expression contrast. ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human · normal squamous esophagus and stage-specific BE-associated lesions (n=238) · unspecified
  > "We performed quantitative real-time polymerase chain reaction to determine VSIG10L expression in a random set of (n = 238) normal squamous esophagus and stage-specific BE-associated lesions ( Figure 3 )."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — In situ hybridization of VSIG10L transcript in normal esophageal squamous tissue confirmed and localized expression to the squamous epithelium, providing spatial transcript-level evidence for esophageal expression. ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human · normal esophageal squamous tissue · fixed · permeabilized
  > "In situ hybridization of VSIG10L transcript of normal esophagus squamous tissue confirmed and localized expression (see eFigure 3 in the Supplement )."
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — Loss of VSIG10L expression was found in sporadic Barrett esophagus-associated lesions, supporting a functional role for VSIG10L in disease beyond the familial context. Expression is absent or markedly reduced in BE metaplasia, dysplasia, and adenocarcinoma. ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human · Barrett esophagus-associated lesions (sporadic) · unspecified
  > "Moreover, we found loss of VSIG10L expression in BE-associated lesions supporting a functional role for this gene in sporadic disease."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — Loss of esophageal VSIG10L expression is observed frequently in patients with chronic gastroesophageal reflux disease (GERD), a known risk factor for Barrett esophagus. This represents a disease-state modulation: VSIG10L expression is reduced in GERD-affected esophageal epithelium relative to normal. ([PMC12960849](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12960849/))
  - *assay*: Human · esophageal mucosa from chronic GERD patients · unspecified
  > "Furthermore, loss of esophageal VSIG10L expression is observed frequently in patients with chronic gastroesophageal reflux disease, a known risk factor for BE."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — Mice carrying human-orthologous germline mutations in Vsig10l exhibit loss of desmosomes and disrupted epithelial differentiation in the squamous mucosa, demonstrating that VSIG10L function is required for normal squamous epithelial cell maturation in vivo. ([PMC12960849](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12960849/))
  - *assay*: Mouse · squamous mucosa, germline Vsig10l mutant mice · unspecified
  > "Mice carrying human-orthologous germline mutations in Vsig10l exhibit loss of desmosomes, concomitant with disrupted epithelial differentiation programs, in the squamous mucosa."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — Upon long-term exposure to a bile acid (deoxycholate)-supplemented diet, Vsig10l-mutant mice develop overt Barrett esophagus-like lesions in the forestomach, indicating that loss of VSIG10L combined with bile acid stress drives metaplastic transformation of squamous epithelium. ([PMC12960849](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12960849/))
  - *assay*: Mouse · forestomach squamous epithelium, Vsig10l-mutant mice on bile acid diet · unspecified
  > "Upon long-term exposure to a bile acid (deoxycholate) supplemented diet, Vsig10l-mutant mice develop overt BE-like lesions in the forestomach."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — Mutant VSIG10L impaired squamous cell maturation in an organotypic model and was associated with proton-pump inhibitor-refractory dilated intercellular spaces and reduced desmosome formation in an affected family member, supporting that inherited VSIG10L defects predispose to Barrett esophagus and/or esophageal adenocarcinoma. ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human · organotypic squamous epithelial model; affected family member esophageal biopsy · unspecified
  > "Mutant VSIG10L impaired squamous cell maturation in an organotypic model and was associated with proton-pump inhibitor refractory dilated intercellular spaces (DIS) and reduced desmosome formation in affected family member III-4, strongly supporting that the inherited defect in VSIG10L predisposes to BE and/or EAC in this family."
- `a2_evi_11` · *Secondary* · Supports · Tissue Expression — VSIG10L is highly expressed in normal esophagus and appears to play a role in epithelial maturation, as identified through genetic analysis of a large family with familial Barrett esophagus (FBE). This is a review-level summary of the primary expression finding. ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human · normal esophagus · unspecified
  > "Genetic analysis of a large family with FBE uncovered the previously uncharacterized gene VSIG10L that is highly expressed in normal esophagus and appears to play a role in epithelial maturation."
- `a2_evi_12` · *Primary* · Supports · Tissue Expression — VSIG10L is predominantly expressed in squamous (SQ) cells of the esophagus, and its gene product encodes a membrane-bound protein with immunoglobulin (Ig)-like domains. The membrane-bound topology is consistent with potential surface accessibility in squamous epithelial cells. ([PMC12960849](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12960849/))
  - *assay*: Human · squamous cells, esophageal epithelium · unspecified
  > "VSIG10L is predominantly expressed in SQ cells, and its gene product encodes a membrane-bound protein with immunoglobulin (Ig)-like domains 14 ."
- `a2_evi_13` · *Secondary* · Supports · Surface Expression — The predicted VSIG10L gene product is a membrane-bound protein with 2 immunoglobulin (Ig)-like domains, 2 Ig-like folds, and a small cytoplasmic domain. This computational/structural prediction places VSIG10L at the membrane with an extracellular Ig-domain-containing ectodomain, consistent with potential surface accessibility in esophageal squamous cells. ([PMC5063702](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5063702/))
  - *assay*: Human · predicted from sequence
  > "The predicted VSIG10L gene product is a membrane-bound protein with 2 immunoglobulin (Ig)-like domains, 2 Ig-like folds, and a small cytoplasmic domain ( Figure 4 )."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/VSIG10L.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/VSIG10L](https://surfaceome.deliverome.org/VSIG10L)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/VSIG10L.json](https://surfaceome.deliverome.org/data/surfaceome/VSIG10L.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/VSIG10L.md](https://surfaceome.deliverome.org/data/surfaceome/VSIG10L.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/Q86VR7](https://alphafold.ebi.ac.uk/entry/Q86VR7)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/Q86VR7](https://alphafold.ebi.ac.uk/api/prediction/Q86VR7) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/Q86VR7](https://www.uniprot.org/uniprotkb/Q86VR7)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-Q86VR7-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-Q86VR7-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-Q86VR7-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-Q86VR7-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-Q86VR7-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-Q86VR7-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*867 aa · `Q86VR7` · embedded at build time*

```
   1  MDNPQALPLFLLLASLVGILTLRASSGLQQTNFSSAFSSDSKSSSQGLGVEVPSIKPPSW
  61  KVPDQFLDSKASAGISDSSWFPEALSSNMSGSFWSNVSAEGQDLSPVSPFSETPGSEVFP
 121  DISDPQVPAKDPKPSFTVKTPASNISTQVSHTKLSVEAPDSKFSPDDMDLKLSAQSPESK
 181  FSAETHSAASFPQQVGGPLAVLVGTTIRLPLVPIPNPGPPTSLVVWRRGSKVLAAGGLGP
 241  GAPLISLDPAHRDHLRFDQARGVLELASAQLDDAGVYTAEVIRAGVSQQTHEFTVGVYEP
 301  LPQLSVQPKAPETEEGAAELRLRCLGWGPGRGELSWSRDGRALEAAESEGAETPRMRSEG
 361  DQLLIVRPVRSDHARYTCRVRSPFGHREAAADVSVFYGPDPPTITVSSDRDAAPARFVTA
 421  GSNVTLRCAAASRPPADITWSLADPAEAAVPAGSRLLLPAVGPGHAGTYACLAANPRTGR
 481  RRRSLLNLTVADLPPGAPQCSVEGGPGDRSLRFRCSWPGGAPAASLQFQGLPEGIRAGPV
 541  SSVLLAAVPAHPRLSGVPITCLARHLVATRTCTVTPEAPREVLLHPLVAETRLGEAEVAL
 601  EASGCPPPSRASWAREGRPLAPGGGSRLRLSQDGRKLHIGNFSLDWDLGNYSVLCSGALG
 661  AGGDQITLIGPSISSWRLQRARDAAVLTWDVERGALISSFEIQAWPDGPALGRTSTYRDW
 721  VSLLILGPQERSAVVPLPPRNPGTWTFRILPILGGQPGTPSQSRVYRAGPTLSHGAIAGI
 781  VLGSLLGLALLAVLLLLCICCLCRFRGKTPEKKKHPSTLVPVVTPSEKKMHSVTPVEISW
 841  PLDLKVPLEDHSSTRAYQAQTPVQLSL
```

### Alternative-isoform sequences

**Q86VR7-2** (`Q86VR7-2` · 881 aa)

```
   1  MDNPQALPLFLLLASLVGILTLRASSGLQQTNFSSAFSSDSKSSSQGLGVEVPSIKPPSW
  61  KVPDQFLDSKASAGISDSSWFPEALSSNMSGSFWSNVSAEGQDLSPVSPFSETPGSEVFP
 121  DISDPQVPAKDPKPSFTVKTPASNISTQVSHTKLSVEAPDSKFSPDDMDLKLSAQSPESK
 181  FSAETHSAASFPQQVGGPLAVLVGTTIRLPLVPIPNPGPPTSLVVWRRGSKVLAAGGLGP
 241  GAPLISLDPAHRDHLRFDQARGVLELASAQLDDAGVYTAEVIRAGVSQQTHEFTVGVYEP
 301  LPQLSVQPKAPETEEGAAELRLRCLGWGPGRGELSWSRDGRALEAAESEGAETPRMRSEG
 361  DQLLIVRPVRSDHARYTCRVRSPFGHREAAADVSVFYGPDPPTITVSSDRDAAPARFVTA
 421  GSNVTLRCAAASRPPADITWSLADPAEAAVPAGSRLLLPAVGPGHAGTYACLAANPRTGR
 481  RRRSLLNLTVADLPPGAPQCSVEGGPGDRSLRFRCSWPGGAPAASLQFQGLPEGIRAGPV
 541  SSVLLAAVPAHPRLSGVPITCLARHLVATRTCTVTPEAPREVLLHPLVAETRLGEAEVAL
 601  EASGCPPPSRASWAREGRPLAPGGGSRLRLSQDGRKLHIGNFSLDWDLGNYSVLCSGALG
 661  AGGDQITLIGPSISSWRLQRARDAAVLTWDVERGALISSFEIQAWPDGPALGRTSTYRDW
 721  VSLLILGPQERSAVVPLPPRNPGTWTFRILPILGGQPGTPSQSRVYRAGPTLSHGAIAGI
 781  VLGSLLGLALLAVLLLLCICCLCRFRGKTPEKKKHPSTLVPVVTPSEKKMHSVTPVEISW
 841  PLDLKVPLEDHSSTRAYQATDPSSVVSVGGGSKTVRAATQV
```

### Canonical ortholog sequences

**Mouse — Vsig10l** (`D3YZF7` · 868 aa)

```
   1  MGLSWALLPFLLLAFRAELLALQPALGSQPPSASSSHSMGSSRDFVSNVSSSQHPQPPGS
  61  EASAGIPDSNRFPQGLNSSHVPGLFRTNVSAEEQYLSPDVTSSETPPSRVSLDGLDSQDP
 121  DKDSGLPFLVKTPASQISVQTPDTKVPTKASGSKLSLEHHNLEPGSKISSEIYQAASFPQ
 181  QVGGPLAVLVGTTIRLPLTPVPSSSPPAPLVVWRRGSKVLAAGGLGSQAPLISLDPMHQA
 241  RLRFDQIRGGLELTSARLDDAGVYTVEVIRGGVSQQIREFVVGVFEPLPQLSVQPRAPET
 301  EEGAAELRLSCVGWNPGSGKLSWSRDGRALGTSDPEGAEPPRIRTERDQLLISRPVRSDH
 361  ARYTCQVRSPFGHTEAAADVSVFYGPDAPVIRVSSDRDASPALYVTAGSNVTLHCSAPSR
 421  PPADIAWSLADPTEAAVPAGPRLLLPAVGPGHGGAYACIAANPRTGHRRRSVFNLTVADL
 481  PPGAPQCSVEGGPVDRSLRFRCSWPGGVPAASLQFQGLPEGVRAGPVPSTLLVTVPARPE
 541  LSGVAVTCLARHLVATRTCTIIPEAPQEVLLQPIVEETQPGDVVVALEVTGCPPPSRASW
 601  ARQGRPLAPGGGGRLQLSQDGRKLLINNFSLDWDLGNYSVLCSSALGAGGNQITLTGPSI
 661  SSWRLQRAQEAAVLTWDVERGTLLTGFHIQAWTDSSEVDRVTMSRDWVSLLILGPQERSA
 721  IVPLPPRNPGTWAFRILPILGSLPGTPSQSRVYQAGSDLSPGAIAGIVLGSLLGLALLAG
 781  LLILCICCLRRYPGRASVKKQHSLTLAPVLTPPAKKIQSLTPVQTPRPLPIKTKMQSPHP
 841  AKAQQVISPSPTLCPGGSPWTVRAATQV
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`Q86VR7`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
 661  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 721  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMM
 781  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 841  IIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Q86VR7-2** (`Q86VR7-2`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
 661  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 721  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMM
 781  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 841  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Mouse ortholog — Vsig10l** (`D3YZF7`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
 661  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 721  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMM
 781  MMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 841  IIIIIIIIIIIIIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence low — Confidence is low because the entire evidence base is RNA-level: no live-cell flow cytometry, surface biotinylation, non-permeabilized immunofluorescence, or any direct protein surface assay has been performed for VSIG10L, and the authors explicitly note the absence of validated antibody reagents (PMC:PMC12960849). The surface call rests entirely on a computational single-pass type I topology prediction plus RNA expression in suprabasal esophageal squamous cells. The first-pass classifier flagged this as nuclear/intracellular — a reasonable call given the absence of experimental surface data; the present call of low surface accessibility with high state-dependence is justified by the predicted membrane topology and tissue-restricted RNA expression, but diverges from that initial assessment. Lifting confidence would require protein-level evidence: non-permeabilized immunofluorescence or flow cytometry on intact esophageal organoids or primary suprabasal cells, ideally with an orthogonally validated antibody or epitope-tagged construct.*
