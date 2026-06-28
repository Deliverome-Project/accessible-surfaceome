# ABCB9 — Surface Accessibility Brief

*Schema v2.9.0 · generated 2026-06-08T21:22:09.672189Z · model `claude-sonnet-4-6`*

> ABCB9 (TAPL) has low surface accessibility as a canonical lysosomal multi-pass ABC transporter; its full-length form is not meaningfully present at the plasma membrane under any documented normal or disease state. The evidence is consistent and multi-method: permeabilized fluorescence microscopy showed TAPL-GFP co-localizing exclusively with LysoTracker in CHO-K1 cells (a1_evi_13), Percoll-gradient fractionation co-sedimented TAPL-GFP with cathepsin D rather than PM markers (a1_evi_14), and stable-expression studies in mammalian cells confirmed lysosomal sorting with no PM signal for the full-length protein (a1_evi_17). Surface presence is constitutively intracellular — state-modulation (DC differentiation, TME Tregs) upregulates ABCB9 expression within the lysosomal compartment, not at the cell surface (a2_evi_01, a2_evi_06). The principal binder-engineering caveat is the lysosomal subdomain restriction (high severity); moderate homodimer-mediated epitope masking at the TMD0 interface is an additional concern, while the absence of a shed or secreted form rules out decoy competition.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:50](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:50) |
| UniProt | [Q9NP78](https://www.uniprot.org/uniprotkb/Q9NP78) |
| NCBI Gene | [23457](https://www.ncbi.nlm.nih.gov/gene/23457) |
| Ensembl | [ENSG00000150967](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000150967) |
| Subcategory | Multi-pass |
| Surface accessibility | No |
| Confidence | High |
| Evidence grade | Weak |
| Triage signal | Possibly Accessible |
| Headline risks | Epitope Masked |

## 1. Executive summary

**ABCB9 localizes constitutively to the lysosomal limiting membrane across all documented cell types and states; no plasma membrane pool has been demonstrated for the full-length protein.**

ABCB9 (TAPL) has low surface accessibility as a canonical lysosomal multi-pass ABC transporter; its full-length form is not meaningfully present at the plasma membrane under any documented normal or disease state. The evidence is consistent and multi-method: permeabilized fluorescence microscopy showed TAPL-GFP co-localizing exclusively with LysoTracker in CHO-K1 cells (a1_evi_13), Percoll-gradient fractionation co-sedimented TAPL-GFP with cathepsin D rather than PM markers (a1_evi_14), and stable-expression studies in mammalian cells confirmed lysosomal sorting with no PM signal for the full-length protein (a1_evi_17). Surface presence is constitutively intracellular — state-modulation (DC differentiation, TME Tregs) upregulates ABCB9 expression within the lysosomal compartment, not at the cell surface (a2_evi_01, a2_evi_06). The principal binder-engineering caveat is the lysosomal subdomain restriction (high severity); moderate homodimer-mediated epitope masking at the TMD0 interface is an additional concern, while the absence of a shed or secreted form rules out decoy competition.

**Family / classification** — UniProt family: ABC transporter superfamily. ABCB family. MHC peptide exporter (TC 3.A.1.209) subfamily · HGNC gene group(s): ATP binding cassette subfamily B · functional class: Transporter.

**Triage first-pass reasoning** — ABCB9 (TAPL) is a multi-pass ABC transporter that resides primarily on lysosomal/late-endosomal membranes, where it translocates peptides from the cytosol into the lysosomal lumen. Its dominant steady-state localization is lysosomal, not the plasma membrane. However, lysosomal membrane proteins can reach the plasma membrane transiently via lysosomal exocytosis — a documented pathway for LAMP1, LAMP2, and other lysosomal TM proteins. No strong gene-specific flow cytometry or surface biotinylation data confirm a stable PM pool for ABCB9 itself. Checking contextual buckets: cell_state_induced — not specifically documented; tissue_restricted — ubiquitous expression, not tissue-restricted; lysosomal_exocytosis — plausible given lysosomal TM topology; dual_localization — possible minor PM cycling; stable_surface_attachment — not applicable (no evidence of secreted form). Given the lysosomal_exocytosis pathway applies to this class of proteins and 'contextual beats no', lysosomal_exocytosis is the best fit.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=No · conf=High · subcategory=Multi-pass · ecd=Moderate |
| Classification | reason=Endomembrane Resident · family=Transporter · state-dependence=Unclear · induction-trigger=Immune |
| Expression | level=Moderate · breadth=Broad · specificity=Mostly Intracellular · low-endogenous=false · tumor-associated=true · orphan-receptor=false · OE-precedent=true |
| Risks | shed=false · secreted=false · co-receptor=Modulatory · masking=true · restricted-subdomain=true |
| Evidence | grade=Weak · density=High · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=9 |
| Cross-species | mouse=96.4% · cyno=100.0% |
| Paralogs | max %ECD identity = 31.8% |
| Topology | TM=10 · N-term-ECF=false · C-term-ECF=false |

**Facet rationales**

- *Expression level*: High expression in monocyte-derived DCs, macrophages, and testicular Sertoli cells (a2_evi_01, a2_evi_02); moderate in TME Tregs and tumor cells (a2_evi_06); low in brain microvessels (a2_evi_05). Overall: moderate across relevant cell types.
- *Expression breadth*: Expressed across immune (DCs, macrophages, Tregs), reproductive (testis), vascular (brain microvessels), and tumor compartments (a2_evi_01, a2_evi_02, a2_evi_04, a2_evi_05, a2_evi_06); not pan-tissue but spans multiple distinct lineages.
- *Surface specificity*: All direct localization studies place full-length ABCB9 on the lysosomal limiting membrane; no PM pool documented (a1_evi_13, a1_evi_14, a1_evi_17, a2_evi_08, a2_evi_09). Only TMD0-deleted truncations reach the PM.
- *Known ligand*: ABCB9/TAPL translocates oligo- and polypeptides (6–59 amino acids) from the cytosol into the lysosomal lumen in an ATP-dependent manner; cytosolic peptides are its validated endogenous substrates/cargo (a1_evi_08).
- *Low endogenous expression*: High expression in monocyte-derived DCs, macrophages, and testicular Sertoli cells (a2_evi_01, a2_evi_02); moderate in TME Tregs and tumor cells (a2_evi_06); low in brain microvessels (a2_evi_05). Overall: moderate across relevant cell types.
- *Overexpression surface localization*: 1 method observation(s) pair an overexpression/mixed expression system with a surface-localization readout (cites a1_evi_16).

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Weak

The ledger contains zero direct-surface-accessibility observations (no live-cell flow, non-permeabilized IF, or surface biotinylation). The methods builder found no `direct_surface_accessibility` rows, so the grade cannot reach `direct_*` or `supportive_but_indirect`. Multiple high-weight claims converge on strict lysosomal localization: (1) NMR structural analysis confirmed a four-TM lysosomal-loop topology for TMD0 with no exposed extracellular domain (a1_evi_02, a1_evi_03); (2) permeabilized fluorescence microscopy of TAPL-GFP in CHO-K1 cells showed co-localization with LysoTracker but no PM signal (a1_evi_13); (3) Percoll density-gradient fractionation of CHO-K1 cells co-sedimented TAPL-GFP with cathepsin D, not PM markers (a1_evi_14); (4) stable OE in mammalian cells showed full-length TAPL-GFP sorted exclusively to lysosomes (a1_evi_17); (5) multiple reviews corroborate lysosomal targeting via LAMP-1/LAMP-2 interaction mediated by TMD0 (a1_evi_01, a1_evi_05, a1_evi_06, a1_evi_08). The single indirect 'supports' signal (a1_evi_16) actually reinforces the lysosomal model: only the TMD0-deleted core reaches the PM, while the full-length protein does not. No lysosomal-exocytosis PM pool has been demonstrated. Graded `weak`.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Contradicts Surface | High | Review: TMD0 mediates lysosomal targeting via LAMP-1/LAMP-2 interaction; canonical lysosomal destination |
| a1_evi_02 | Contradicts Surface | High | NMR structure of TMD0 confirms four-TM lysosomal-loop topology; no extracellular domain exposed at PM |
| a1_evi_03 | Contradicts Surface | High | Paramagnetic relaxation enhancement NMR validates four-TM topology of lysosomal-targeting domain |
| a1_evi_04 | Tangential | Low | TMD0 dimerization biology; no surface-accessibility information |
| a1_evi_05 | Contradicts Surface | High | Review: homodimeric half-transporter with cytosolic NBD, no large ECD; canonical lysosomal topology |
| a1_evi_06 | Contradicts Surface | High | Review: TMD0 four-TM helices essential for lysosomal targeting/LAMP interaction; not PM-directed |
| a1_evi_07 | Tangential | Low | Antibody provenance note (immunoblot reagent); no localization data |
| a1_evi_08 | Contradicts Surface | High | Review: homodimeric translocon delivers cargo to lysosomal lumen; confirms intracellular orientation |
| a1_evi_09 | Tangential | Low | Membrane-fraction detection in Drosophila S2 OE; non-human, does not distinguish lysosome vs PM |
| a1_evi_10 | Tangential | Low | Method detail for S2-cell fractionation; non-human, no surface specificity |
| a1_evi_11 | Contradicts Surface | Moderate | Drosophila S2 OE: TAPL distributes primarily to intracellular membranes even under overexpression |
| a1_evi_12 | Tangential | Low | Construct description for TAPL-GFP in CHO-K1; methodological context only |
| a1_evi_13 | Contradicts Surface | High | Permeabilized IF in CHO-K1: TAPL-GFP colocalizes with LysoTracker, not at PM; lysosomal localization |
| a1_evi_14 | Contradicts Surface | High | Percoll gradient fractionation in CHO-K1: TAPL-GFP co-sediments with cathepsin D (lysosomal marker) |
| a1_evi_15 | Contradicts Surface | Moderate | Lipid-raft association with flotillin-1 on sucrose gradient in CHO-K1; consistent with lysosomal membrane |
| a1_evi_16 | Tangential | Moderate | Core-TAPL (TMD0-deleted) reaches PM in OE; full-length protein does NOT — confirms full-length is lysosomal |
| a1_evi_17 | Contradicts Surface | High | Fluorescence microscopy of stable OE: full-length TAPL-GFP sorted to lysosomes; no PM signal noted |
| a1_evi_18 | Tangential | Low | shRNA reagent identifier; no localization data |
| a1_evi_19 | Expression Only | Low | RT-qPCR + whole-cell Western after shRNA knockdown; no surface-specificity |
| a1_evi_20 | Expression Only | Low | Label-free whole-tissue proteomics of mouse brain microvessels; no membrane fractionation or surface capture |

### Immunofluorescence (3 methods)

#### Permeabilized IF — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| CHO-K1 cells stably expressing TAPL-GFP: GFP signal co-localizes with LysoTracker but not MitoTracker, indicating lysosomal localization | Established Cell Line | Moderate | 1 |

*Overexpression construct* — SP source: Native · full-length TAPL, native signal sequence implied; no heterologous leader mentioned · tag: C-terminal GFP · cell line: CHO-K1. *(cites: a1_evi_12, a1_evi_13)*

#### Unknown — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Unknown · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Mammalian cells (unspecified line) stably overexpressing core-TAPL (six TM helices + NBD, lacking TMD0): preferentially targeted to plasma membrane; full-length TAPL targets lysosomes in the same system | Established Cell Line | Moderate | 1 |

*Overexpression construct* — SP source: Native · truncated core-TAPL construct (Arg141-Ala766, lacking TMD0); full-length and truncated constructs use native sequence; no heterologous leader mentioned. *(cites: a1_evi_16)*

#### Unknown — Expression Only · Intracellular Pool

*Permeabilization: Unknown · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Unspecified mammalian cells stably expressing full-length TAPL-GFP or N-terminal domain (Met1-Arg141): sorted to lysosomal membranes; core domain (Arg141-Ala766) broadly distributed in intracellular membranes but not lysosomes specifically; no plasma membrane signal for full-length TAPL | Established Cell Line | Moderate | 1 |

*Overexpression construct* — SP source: Native · full-length TAPL-GFP and N-terminal domain (Met1-Arg141) constructs; native sequence implied; no heterologous leader mentioned · tag: C-terminal GFP (full-length construct). *(cites: a1_evi_17)*

### Surface mass spec (1 method)

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Isolated mouse brain microvessels (BBB tissue): Abcb9 quantified by label-free proteomics (MaxQuant analysis); whole-tissue proteomics without surface-specific capture or fractionation | Ex Vivo | Low | 1 |

### Membrane fractionation (2 methods)

#### Plasma Membrane Fractionation — Supports Membrane Association · Intracellular Pool

*Permeabilization: Unknown · expression: Overexpression*

**Antibodies**

- anti-polyHistidine (HIS-1 · Sigma-Aldrich) — Unknown epitope; Monoclonal; None validation (None); Detects His6-tag on overexpressed TAPL constructs; not a native ABCB9 epitope antibody. Tag-directed.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Drosophila S2 cells overexpressing hTAPL and rTAPL (His-tagged): both detected exclusively in membrane fraction, not soluble fraction; noted to reside on intracellular membranes | Established Cell Line | Moderate | 3 |

*Overexpression construct* — SP source: Unspecified · tag: C-terminal His6 · cell line: S2. *(cites: a1_evi_09, a1_evi_10)*

#### Plasma Membrane Fractionation — Supports Membrane Association · Intracellular Pool

*Permeabilization: Unknown · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| CHO-K1 cells stably expressing TAPL-GFP: co-sedimented with lysosomal marker cathepsin D on Percoll density gradient; also co-sedimented with flotillin-1 on sucrose density gradient, suggesting lysosomal lipid raft association | Established Cell Line | Moderate | 2 |

*Overexpression construct* — SP source: Native · full-length TAPL, native signal sequence implied; no heterologous leader mentioned · tag: C-terminal GFP · cell line: CHO-K1. *(cites: a1_evi_12, a1_evi_14, a1_evi_15)*

### Other (2 methods)

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-TAPL — Unknown epitope; Polyclonal; None validation (None); Rabbit polyclonal anti-TAPL cited as 'ref. 12' in PMC6695453; no catalog number or RRID provided; epitope region unspecified.

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Unspecified human cells with stable shRNA knockdown of ABCB9 (sc-60115-SH, Santa Cruz Biotechnology): ABCB9 protein assessed by Western blot after 10 days of shRNA selection; whole-cell lysate, no fractionation | Established Cell Line | Moderate | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Unspecified human cells (stably transduced), shRNA knockdown validation by RT-qPCR and whole-cell Western blot | Established Cell Line | Bulk Protein | Moderate | 2 |
| Mouse brain microvessels (BBB tissue), isolated primary tissue, label-free whole-tissue proteomics | Ex Vivo | Bulk Protein | Low | 1 |

**Contradicting evidence**

- *Alternative Localization* (severity High): Multiple structural and functional studies establish that ABCB9/TAPL is a lysosomal membrane protein, not a plasma membrane protein. The TMD0 domain is solely responsible for lysosomal targeting via interaction with LAMP-1 and LAMP-2, and NMR analysis confirms a four-transmembrane helix topology with a lysosomal loop. The nucleotide-binding domain (NBD) is cytoplasmic, and there is no large extracellular domain — making surface accessibility at the plasma membrane structurally implausible.
  - Likely explanation: ABCB9/TAPL is a canonical lysosomal ABC half-transporter; its TMD0 contains a lysosomal targeting signal that directs the entire protein to the lysosomal membrane. Any plasma membrane detection would likely represent a minor mistargeted fraction or an artifact of overexpression systems.
- *Alternative Localization* (severity High): Direct cell-biological experiments consistently show ABCB9/TAPL localizing to lysosomal membranes rather than the plasma membrane. In CHO-K1 cells, TAPL-GFP co-localizes with LysoTracker (not MitoTracker) by fluorescence microscopy, co-sediments with the lysosomal marker cathepsin D on Percoll gradients, and associates with lipid raft microdomains of lysosomal membranes (co-sedimentation with flotillin-1). In mammalian stable-expression systems, full-length TAPL-GFP sorted specifically to lysosomal membranes with no plasma membrane signal reported.
  - Likely explanation: These orthogonal localization experiments (fluorescence microscopy, subcellular fractionation, detergent-resistance profiling) all converge on the lysosomal membrane as the primary residence of full-length ABCB9, consistent with the lysosomal targeting signal in TMD0. Surface expression at the plasma membrane is not supported by these data.
- *Intracellular Pool* (severity Moderate): In a Drosophila S2 overexpression system, significant amounts of TAPL were expressed on intracellular membranes rather than the cell surface, even under conditions designed to drive high protein levels. This non-mammalian overexpression context reinforces the conclusion that ABCB9 preferentially localizes to intracellular membranes.
  - Likely explanation: The S2 insect cell system lacks the precise mammalian lysosomal targeting machinery but still routes TAPL to intracellular membranes, consistent with an intrinsic intracellular retention/targeting signal. The non-mammalian context slightly reduces the severity compared to mammalian-cell data.

## 4. Biological context

**Biological-context grade** · Rich

All four A2 axes are well-populated: expression mapped across ≥5 tissues/cell types (monocytes/DCs/macrophages, testis, placenta, brain microvessels, Tregs) from multiple independent sources; subcellular localization to lysosomal limiting membrane is pinned by multiple primary IF/biochemical studies; anatomical context spans immune, reproductive, vascular, and CNS compartments; modulation evidence covers DC differentiation-state induction, disease-state downregulation (malaria/placenta), and pharmacological upregulation (NPt/Tregs). Picture is internally consistent—all roads lead to lysosomal membrane. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_07, a2_evi_08, +7)*

**Expression × cell type × disease context**

| Tissue | Cell type | Disease context | Level (protein) | Cell states |
|---|---|---|---|---|
| immune compartment (in vitro) | monocytes | Normal | Absent | resting |
| immune compartment (in vitro) | monocyte-derived dendritic cells | Normal | High | differentiated (monocyte→DC) |
| immune compartment (in vitro) | monocyte-derived macrophages | Normal | High | differentiated (monocyte→macrophage) |
| testis | Sertoli cells | Normal | High | — |
| placenta | — | Other Disease (malaria-in-pregnancy (Plasmodium berghei ANKA)) | Low | — |
| brain microvessels | — | Normal | Moderate | — |
| brain microvessels | — | Normal | Low | — |
| lung | — | Normal | Unknown | — |
| liver | — | Normal | Unknown | — |
| spleen | — | Normal | Unknown | — |
| tumor microenvironment | regulatory T cells (Tregs) | Tumor | Moderate | — |
| tumor microenvironment | tumor cells | Tumor | Moderate | — |

**Primary subcellular compartment**: Lysosome

**Dual localization**

- Endosome · retained on limiting membrane by LAMP proteins *(cites: a2_evi_10)*
- Plasma membrane · only when TMD0 is absent (core-TAPL truncation) *(cites: a2_evi_09, a2_evi_12)*

**Membrane subdomains**: Lipid Raft

**Accessibility modulation**

- *Activation Induced* · trigger: Immune Activation: resting peripheral blood monocytes → monocyte-derived dendritic cells or macrophages — ABCB9 (TAPL) expression is absent/low in resting monocytes and is strongly induced upon differentiation to dendritic cells or macrophages, where it localizes to the lysosomal compartment (co-localizes with LAMP-2). *(→ ABCB9 Is Not Surface-Accessible In Resting Monocytes; Upon DC/Macrophage Differentiation It Becomes Present On Lysosomal Membranes — Not The Plasma Membrane — So It Remains Inaccessible To Extracellular Binders Even In The Induced State.)* *(cites: a2_evi_01, a2_evi_07)*
- *Post Translational Dependent*: cells expressing truncated core-TAPL (lacking TMD0) → cells expressing full-length TAPL (with TMD0) — Core-TAPL (without TMD0) localizes preferentially to the plasma membrane; full-length TAPL with TMD0 is directed exclusively to lysosomal membranes. TMD0 is the structural determinant routing the protein away from the cell surface. *(→ Full-Length ABCB9 Is Inaccessible To Extracellular Binders Under Normal Conditions Because TMD0 Enforces Lysosomal Targeting. Only Truncated Forms Lacking TMD0 Reach The Plasma Membrane.)* *(cites: a2_evi_09, a2_evi_12, a2_evi_13)*
- *Disease State Induced* · trigger: Infection Bacterial: placenta of uninfected pregnant mice → placenta of Plasmodium berghei ANKA-infected pregnant mice (malaria-in-pregnancy) — Placental Abcb9 mRNA/protein is decreased in malaria-in-pregnancy compared to uninfected controls. *(→ Reduced ABCB9 In Malaria-Infected Placenta; As ABCB9 Is A Lysosomal Membrane Protein, Reduced Expression Further Limits Any Potential Accessibility. Impact On Extracellular Binder Access Is Minimal Since Protein Is Intracellular Regardless.)* *(cites: a2_evi_03)*
- *Cell State Induced* · trigger: Unknown: null → null — In the tumor microenvironment, ABCB9 participates in lysosomal metabolic programs in both tumor cells and human Tregs; suppression of ABCB9 impairs GARP/TGF-β1 production and Treg immunosuppression, indicating functional relevance of ABCB9 lysosomal expression in this state. *(→ ABCB9 Operates On The Lysosomal Membrane Of Tregs In The Tumor Microenvironment. This Intracellular Localization Means It Is Not Accessible To Conventional Extracellular Binders, Though Its Functional Importance In TME Tregs Is Noted.)* *(cites: a2_evi_06, a2_evi_15)*

**Restricted-subdomain distribution**

- present: true
- severity: High
- evidence: Strong
- domain: Other
- rationale: ABCB9 localises exclusively to the lysosomal limiting membrane, not the plasma membrane, as demonstrated by LysoTracker co-localisation and cathepsin D co-sedimentation (a1_evi_13, a1_evi_14, a2_evi_08). Full-length TAPL-GFP shows no plasma membrane signal in multiple stable-expression systems (a1_evi_17, a2_evi_09). This intracellular compartment is inaccessible to circulating antibodies.
- cites: a1_evi_13, a1_evi_14, a1_evi_17, a2_evi_08, a2_evi_09

**Co-receptor requirements**

- dependency: Modulatory
- evidence basis: Knockout
- partners: LAMP-1, LAMP-2B
- rationale: ABCB9 traffics to lysosomal membrane independently via TMD0 (a1_evi_06), but LAMP-1/LAMP-2B interaction stabilises it on the limiting membrane and prevents ILV sorting (a2_evi_10). LAMP KO reduces TAPL stability ~5-fold without fully abolishing membrane integration, so LAMPs are modulatory stabilisers, not obligate trafficking chaperones for initial surface/membrane targeting.
- cites: a1_evi_06, a2_evi_10

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | Q9NP78 | ref | ref | 10 | 84 aa | 482 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q9NP78-2 | Q9NP78-2 | 94.4% | 93.1% | 8 | 74 aa | 484 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q9NP78-3 | Q9NP78-3 | 76.8% | 98.9% | 10 | 83 aa | 317 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q9NP78-5 | Q9NP78-5 | 89.0% | 98.9% | 10 | 83 aa | 401 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q9NP78-6 | Q9NP78-6 | 88.9% | 98.9% | 10 | 83 aa | 399 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q9NP78-7 | Q9NP78-7 | 91.8% | 100.0% | 10 | 84 aa | 429 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Mouse ortholog | Abcb9 | [Q9JJ59](https://www.uniprot.org/uniprotkb/Q9JJ59) | 93.7% | 96.4% | 10 | 84 aa | — | — | — | high (≥85%) |
| Cynomolgus ortholog | ABCB9 | [G8F535](https://www.uniprot.org/uniprotkb/G8F535) | 99.0% | 100.0% | 10 | 84 aa | — | — | — | high (≥85%) |
| Paralog | TAP1 | [Q03518](https://www.uniprot.org/uniprotkb/Q03518) | 34.6% | 31.8% | — | — | — | — | — | low-risk |
| Paralog | ABCB11 | [O95342](https://www.uniprot.org/uniprotkb/O95342) | 30.0% | 28.6% | — | — | — | — | — | low-risk |
| Paralog | ABCB7 | [O75027](https://www.uniprot.org/uniprotkb/O75027) | 21.9% | 24.4% | — | — | — | — | — | low-risk |
| Paralog | ABCB4 | [P21439](https://www.uniprot.org/uniprotkb/P21439) | 30.0% | 24.2% | — | — | — | — | — | low-risk |
| Paralog | ABCB5 | [Q2M3G0](https://www.uniprot.org/uniprotkb/Q2M3G0) | 28.2% | 24.1% | — | — | — | — | — | low-risk |
| Paralog | TAP2 | [Q03519](https://www.uniprot.org/uniprotkb/Q03519) | 36.3% | 24.1% | — | — | — | — | — | low-risk |
| Paralog | ABCB10 | [Q9NRK6](https://www.uniprot.org/uniprotkb/Q9NRK6) | 30.8% | 20.0% | — | — | — | — | — | low-risk |
| Paralog | ABCB1 | [P08183](https://www.uniprot.org/uniprotkb/P08183) | 31.5% | 18.9% | — | — | — | — | — | low-risk |
| Paralog | ABCB8 | [Q9NUT2](https://www.uniprot.org/uniprotkb/Q9NUT2) | 29.5% | 17.8% | — | — | — | — | — | low-risk |
| Paralog | ABCB6 | [Q9NP58](https://www.uniprot.org/uniprotkb/Q9NP58) | 22.6% | 10.2% | — | — | — | — | — | low-risk |

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
- rationale: ECD length 84 residues (60-199) -> moderate; computed deterministically from DeepTMHMM topology.

**Epitope masking**

- severity: Moderate
- evidence: Moderate
- mechanism: Oligomerization, Partner
- rationale: TMD0 forms homodimers (assigned by PELDOR and static light scattering) (a1_evi_04), consistent with the deterministic homodimer prior (stoichiometry=2); dimer interface may bury extracellular-facing loop epitopes. Additionally, LAMP-1/LAMP-2B physically interact with TMD0 (a1_evi_01, a1_evi_06), and in LAMP-positive compartments this hetero-partner may occlude TMD0-facing epitopes. Both mechanisms operate in the lysosomal membrane context.
- cites: a1_evi_04, a1_evi_01, a1_evi_06

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-Q9NP78-F1](https://alphafold.ebi.ac.uk/entry/Q9NP78) |
| AFDB version | v6 |
| ECD mean pLDDT | 83.3 |
| ECD disordered fraction | 13.1% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/Q9NP78) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [Q9NP78](https://alphafold.ebi.ac.uk/entry/Q9NP78) | AlphaFold DB (AF-Q9NP78-F1, v6) |
| Isoform Q9NP78-2 | [Q9NP78-2](https://alphafold.ebi.ac.uk/entry/Q9NP78-2) | AlphaFold DB |
| Isoform Q9NP78-3 | [Q9NP78-3](https://alphafold.ebi.ac.uk/entry/Q9NP78-3) | AlphaFold DB |
| Isoform Q9NP78-5 | [Q9NP78-5](https://alphafold.ebi.ac.uk/entry/Q9NP78-5) | AlphaFold DB |
| Isoform Q9NP78-6 | [Q9NP78-6](https://alphafold.ebi.ac.uk/entry/Q9NP78-6) | AlphaFold DB |
| Isoform Q9NP78-7 | [Q9NP78-7](https://alphafold.ebi.ac.uk/entry/Q9NP78-7) | AlphaFold DB |
| Mouse ortholog (Abcb9) | [Q9JJ59](https://alphafold.ebi.ac.uk/entry/Q9JJ59) | AlphaFold DB |
| Cynomolgus ortholog (ABCB9) | [G8F535](https://alphafold.ebi.ac.uk/entry/G8F535) | AlphaFold DB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

ABC-type oligopeptide transporter ABCB9 · Transporters · Active_transporters · chain A · 2 scored sites · 3,604 binder seeds (1,130 α-helix / 2,474 β-strand).

Anchor = patch-center residue; BSA = buried surface area (the contact footprint a binder would form on the patch); seed counts are docked binder backbones split by α-helix / β-strand.

**Reading the scores.** BSA vs the average antibody–antigen interface ≈ 1103 ± 244 Å² ([PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)): ≥1500 Å² comfortable · 850–1500 workable · <850 thin. Seed pool: ≥1000 comfortable design margin · ≥100 workable · <100 thin/specialized. SURFACE-Bind excludes transmembrane regions but not necessarily intracellular domains — cross-check the anchor residue against the topology string in §5/appendix (`O` = extracellular/antibody-accessible, `I` = intracellular).

| Site | Anchor residue | BSA (Å²) | α-helix seeds | β-strand seeds | Hydrophobicity |
|---|---|---|---|---|---|
| 0 | 301 | 1355.2 | 1,127 | 2,330 | 35.4 |
| 1 | 398 | 2365.7 | 3 | 144 | 6.3 |

## 9. Evidence ledger

35 entries · 22 primary · 13 secondary · 0 tertiary · 14 PMC OA.

- `a1_evi_01` · *Secondary* · Refutes · Topology — ABCB9/TAPL is functionally divided into coreTAPL (peptide translocation) and the N-terminal transmembrane domain TMD0. TMD0 is solely responsible for lysosomal targeting and mediates interaction with LAMP-1 and LAMP-2, establishing that the protein's intracellular destination is the lysosomal membrane, not the plasma membrane. ([PMC6199259](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6199259/))
  - *assay*: Human
  > "TAPL can be divided into two functional units: coreTAPL, active in ATP-dependent peptide translocation, and the N-terminal membrane spanning domain, TMD0, responsible for cellular localization and interaction with the lysosomal associated membrane proteins LAMP-1 and LAMP-2."
- `a1_evi_02` · *Primary* · Refutes · Topology — TMD0 of ABCB9/TAPL has a four transmembrane helix topology with a short helical segment in a lysosomal loop, established by NMR structural analysis. This four-TM architecture, combined with the lysosomal loop, confirms intracellular (luminal/cytoplasmic) orientation rather than extracellular exposure at the plasma membrane. ([PMC6199259](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6199259/))
  - *assay*: Human
  > "Accordingly, TMD0 has a four transmembrane helix topology with a short helical segment in a lysosomal loop."
- `a1_evi_03` · *Primary* · Refutes · Topology — The four-TM topology of ABCB9/TAPL TMD0 was confirmed by paramagnetic relaxation enhancement using paramagnetic stearic acid and nuclear Overhauser effects with c6-DHPC and water cross-peaks — direct NMR structural validation of the membrane orientation of the lysosomal-targeting domain. ([PMC6199259](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6199259/))
  - *assay*: Human
  > "The topology of TMD0 was confirmed by paramagnetic relaxation enhancement with paramagnetic stearic acid as well as by nuclear Overhauser effects with c6-DHPC and cross-peaks with water."
- `a1_evi_04` · *Primary* · Ambiguous · Surface Expression — TMD0 of ABCB9/TAPL forms oligomers assigned as dimers by PELDOR spectroscopy and static light scattering, both in-cell and cell-free expressed. Homodimerization at the TMD0 interface may partially bury epitopes, posing a risk of epitope masking for antibodies targeting this domain. ([PMC6199259](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6199259/))
  - *assay*: Human
  > "In cell as well as cell-free expressed TMD0 forms oligomers, which were assigned as dimers by PELDOR spectroscopy and static light scattering."
- `a1_evi_05` · *Secondary* · Refutes · Topology — ABCB9/TAPL is a homodimeric half-transporter composed of one transmembrane domain (TMD), one cytoplasmic nucleotide-binding domain (NBD), and an N-terminal TMD0 — confirming the multi-pass membrane topology with cytosolic NBD orientation and the absence of a large extracellular domain. ([PMC9532399](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9532399/))
  - *assay*: Human
  > "TAPL is a homodimeric half-transporter composed of a transmembrane domain (TMD) and a cytoplasmic nucleotide-binding domain (NBD) with an N-terminal TMD (TMD0) 3 , 4 ."
- `a1_evi_06` · *Secondary* · Refutes · Topology — TMD0 of ABCB9/TAPL comprises four transmembrane alpha-helices; it is dispensable for peptide transport but essential for lysosomal targeting and long-term stabilization by interacting with LAMP-1 and LAMP-2B. This interaction with lysosomal markers anchors ABCB9 in the lysosomal membrane, not the plasma membrane. ([PMC9532399](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9532399/))
  - *assay*: Human
  > "TMD0 is made up of four transmembrane α-helices; it is dispensable for peptide transport but is essential for lysosomal targeting and long-term stabilization by interacting with the lysosome-associated membrane proteins, LAMP-1 and LAMP-2B 5 , 6 ."
- `a1_evi_07` · *Secondary* · Ambiguous · Methodological — Antibody identifiers for TAPL/ABCB9 detection in the referenced study: rabbit anti-TAPL (ref. 12, polyclonal) used for immunoblotting, with HRP-conjugated goat anti-rabbit secondary (BD Pharmingen). No RRID or clone number provided. This clip provides the antibody provenance needed for downstream method validation assessment. ([PMC6695453](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6695453/))
  - *assay*: Human
  > "For detection by immunoblotting the following antibodies were used: rabbit anti-TAPL 12 and mouse anti-His (monoclonal, HIS-1; Sigma-Aldrich now Merck); horseradish peroxidase-conjugated goat anti-rabbit (polyclonal; BD Pharmingen) and goat anti-mouse (polyclonal A2554; Sigma-Aldrich now Merck)."
- `a1_evi_08` · *Secondary* · Refutes · Topology — TAPL/ABCB9 forms a homodimeric transport complex that translocates oligo- and polypeptides into the lysosomal lumen driven by ATP hydrolysis. Homodimerization establishes the quaternary structure relevant to epitope accessibility; the cargo destination (lysosomal lumen) confirms intracellular rather than extracellular orientation. ([PMC6695453](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6695453/))
  - *assay*: Human
  > "TAPL forms a homodimeric transport complex, which translocates oligo- and polypeptides into the lumen of lysosomes driven by ATP hydrolysis."
- `a1_evi_09` · *Secondary* · Supports · Methodological — In Drosophila S2 cells overexpressing human TAPL (hTAPL) and rat TAPL (rTAPL) constructs (His-tagged), membrane/soluble fractionation followed by Western blot with anti-His6 antibodies detected both TAPL proteins exclusively in the membrane fraction and not in the soluble fraction. This confirms stable membrane integration of overexpressed TAPL but does not distinguish lysosomal from plasma membrane. Construct SP source: unspecified (full-length constructs implied but leader sequence not described). (https://pubmed.ncbi.nlm.nih.gov/18175933/)
  - *assay*: Other · Drosophila S2
  > "The recombinant hTAPL and rTAPL were detected in the membrane fraction but not in the soluble fraction (Fig. 1A)."
- `a1_evi_10` · *Secondary* · Supports · Methodological — Methodology detail for membrane/soluble fractionation of S2 cells overexpressing hTAPL and rTAPL: membranes prepared from expressing and mock-transfected cells, 20 µg protein aliquots analyzed by SDS-PAGE (7.5%) + Western blot with anti-His6 antibodies. This is the paired method detail for the membrane-fraction result clip. (https://pubmed.ncbi.nlm.nih.gov/18175933/)
  - *assay*: Other · Drosophila S2
  > "Membrane (lanes 1—3) and soluble (lanes 4—6) fractions were prepared from hTAPL-expressing (lanes 1, 4), rTAPLexpressing (lanes 2, 5), and mock-transfected (lanes 3, 6) cells, and then aliquots (20 m g protein) were analyzed by means of Western blotting using anti-His6 antibodies after SDS-polyacrylamide gel (7.5%) electrophoresis. [B] Membranes were prepared from S2 cells expressing rTAPL."
- `a1_evi_11` · *Primary* · Refutes · Surface Expression — The study notes that significant amounts of both TAPL proteins were expressed on intracellular membranes in the S2 overexpression system — establishing that even under OE conditions the protein distributes primarily to intracellular membranes rather than the cell surface. (https://pubmed.ncbi.nlm.nih.gov/18175933/)
  - *assay*: Other · Drosophila S2
  > "Significant amounts of both TAPL proteins were expressed on the intracellular membranes."
- `a1_evi_12` · *Secondary* · Ambiguous · Methodological — ABCB9/TAPL-GFP fusion construct (C-terminal GFP tag) was stably expressed in CHO-K1 cells. SP source: full-length TAPL implies native signal sequence; no heterologous leader mentioned. This is the OE construct description enabling tier assignment for downstream localization results. (https://pubmed.ncbi.nlm.nih.gov/21212514/)
  - *assay*: Human · CHO-K1
  > "The carboxyl terminus of a human ATP-binding cassette (ABC) transporter, transporter associated with antigen processing (TAP)-like (TAPL), was tagged with green fluorescence protein (GFP), and the resulting fusion protein (TAPL-GFP) was stably expressed in Chinese hamster ovary (CHO)-K1 cells."
- `a1_evi_13` · *Primary* · Refutes · Surface Expression — Fluorescence microscopy of TAPL-GFP stably expressed in CHO-K1 cells showed GFP signal co-localizing with LysoTracker but not MitoTracker. This directly demonstrates lysosomal (not mitochondrial or plasma membrane) localization of overexpressed full-length ABCB9, consistent with intracellular rather than surface localization. (https://pubmed.ncbi.nlm.nih.gov/21212514/)
  - *assay*: Human · CHO-K1 · fixed · permeabilized
  > "The GFP signal was co-localized with that of LysoTracker but not that of MitoTracker, as visualized under a microscope."
- `a1_evi_14` · *Primary* · Refutes · Surface Expression — Subcellular fractionation on Percoll density gradient of CHO-K1 cells expressing TAPL-GFP: the fusion protein co-sedimented with the lysosomal marker cathepsin D, confirming lysosomal membrane residence. This paired fractionation result is required alongside the WB/IF result to satisfy the surface-assay pairing rule. (https://pubmed.ncbi.nlm.nih.gov/21212514/)
  - *assay*: Human · CHO-K1
  > "TAPL-GFP was co-sedimented with lysosomal marker cathepsin D on Percoll density gradient centrifugation."
- `a1_evi_15` · *Primary* · Refutes · Surface Expression — TAPL-GFP in CHO-K1 cells was not completely solubilized by non-ionic detergent under ice-cold conditions and co-sedimented with flotillin-1 on sucrose density gradient, indicating association with lipid raft microdomains of lysosomal membranes — consistent with intracellular (lysosomal) membrane residency. (https://pubmed.ncbi.nlm.nih.gov/21212514/)
  - *assay*: Human · CHO-K1
  > "It was not solubilized completely with a non-ionic detergent under ice-cold conditions, and was co-sedimented with flotillin-1 on sucrose density gradient centrifugation."
- `a1_evi_16` · *Primary* · Ambiguous · Surface Expression — OE surface-localization precedent: core-TAPL construct (six predicted TM helices + NBD, lacking TMD0) overexpressed in mammalian cells is sufficient for peptide transport AND is preferentially targeted to the plasma membrane, in striking contrast to full-length TAPL which goes to lysosomes. TMD0 alone traffics to lysosomes. This is direct evidence that the core translocon domain CAN reach the PM when the lysosomal-targeting TMD0 is removed — but the full-length protein does not. SP source: full-length and truncated constructs, native sequence implied; no heterologous leader mentioned. (https://pubmed.ncbi.nlm.nih.gov/20377823/)
  - *assay*: Human · mammalian cells (OE, unspecified line) · unspecified
  > "The core-TAPL complex, composed of six predicted transmembrane helices and a nucleotide-binding domain, is sufficient for peptide transport, showing that the core transport complex is correctly targeted to and assembled in the membrane. Strikingly, in contrast to the full-length transporter, the core translocation complex is targeted preferentially to the plasma membrane. However, TMD0 alone, comprising a putative four transmembrane helix bundle, traffics to lysosomes."
- `a1_evi_17` · *Primary* · Refutes · Surface Expression — Full-length TAPL-GFP and the N-terminal domain (Met1-Arg141) both sorted to lysosomal membranes upon stable expression as visualized by fluorescence microscopy; the core domain (Arg141-Ala766) was broadly distributed in intracellular membranes but not specifically lysosomes. No plasma membrane signal was noted for full-length TAPL. This directly establishes lysosomal rather than plasma-membrane localization of full-length ABCB9. (https://pubmed.ncbi.nlm.nih.gov/18952056/)
  - *assay*: Human · unspecified mammalian cells (stable OE) · unspecified
  > "The amino-terminal domain (Met(1)-Arg(141)) as well as the full-length transporter fused with fluorescent protein GFP was sorted to lysosomal membranes upon their stable expression, as visualized by means of fluorescent microscopy, while the core domain (Arg(141)-Ala(766)) was broadly distributed in the intra-cellular membranes. These results suggest that the sorting signal for lysosomes is present within the amino-terminal transmembrane domain (Met(1)-Arg(141)) of the TAPL molecule."
- `a1_evi_18` · *Secondary* · Ambiguous · Methodological — shRNA construct for stable knockdown of human ABCB9 (sc-60115-SH, Santa Cruz Biotechnology) was used in the referenced study. This provides the knockdown reagent identifier enabling downstream assessment of antibody-validation strategy (siRNA/shRNA knockdown control). ([PMC10828454](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10828454/))
  - *assay*: Human · unspecified human cells
  > "Four hours later, transfection with jetPRIME (Polyplus transfection) was carried out following the manufacturer’s instructions.
shRNAs constructs for the stable knockdown of human ABCB6 (sc-94721-SH) and ABCB9 (sc-60115-SH) were obtained from Santa Cruz Biotechnology."
- `a1_evi_19` · *Secondary* · Ambiguous · Tissue Expression — ABCB9 mRNA expression was assessed by RT-qPCR and protein expression by Western blot after 10 days of shRNA selection in the referenced study. No membrane fractionation step is mentioned; this is a whole-cell protein detection readout without surface specificity. ([PMC10828454](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10828454/))
  - *assay*: Human · unspecified human cells (shRNA knockdown)
  > "After 10 days of selection, ABCB6 and ABCB9 mRNA and protein expression were assessed using reverse transcription-quantitative polymerase chain reaction and Western blot."
- `a1_evi_20` · *Secondary* · Ambiguous · Tissue Expression — Label-free proteomics of isolated brain microvessels (BBB tissue) quantified Abcb9 protein using MaxQuant analysis in rodent. This is a whole-tissue proteomics result without membrane fractionation or surface-specific capture, so it confirms ABCB9 protein expression in vascular tissue but provides no information on plasma membrane accessibility. (https://pubmed.ncbi.nlm.nih.gov/29675872/)
  - *assay*: Mouse · brain microvessels (isolated)
  > "Label-free proteomics was used to identify nearly 2000 proteins and quantify 1276 proteins in isolated microvessels. A combination of targeted and global proteomics was adopted to measure protein abundance of 6 ATP-binding cassette and 27 solute carrier transporters. Data analysis using proprietary Progenesis and open access MaxQuant software showed overall agreement; however, Abcb9 and Slc22a8 were quantified only by MaxQuant, whereas Abcc9 and Abcd3 were quantified only by Progenesis."
- `a2_evi_01` · *Primary* · Supports · Tissue Expression — ABCB9 (TAPL) expression is strongly induced during differentiation of monocytes to dendritic cells and to macrophages; it is not expressed in resting monocytes. In these antigen-presenting cell lineages, TAPL localizes to the lysosomal compartment, co-localizing with LAMP-2 as demonstrated by quantitative immunofluorescence and subcellular fractionation. (https://pubmed.ncbi.nlm.nih.gov/17977821/)
  - *assay*: Human · monocytes, monocyte-derived dendritic cells, monocyte-derived macrophages · fixed · permeabilized
  > "Remarkably, TAPL expression is strongly induced during differentiation of monocytes to dendritic cells and to macrophages. TAPL does not, however, restore MHC class I surface expression in TAP-deficient cells, demonstrating that TAPL alone or in combination with single TAP subunits does not form a functional transport complex required for peptide loading of MHC I in the endoplasmic reticulum. In fact, by using quantitative immunofluorescence and subcellular fractionation, TAPL was detected in the lysosomal compartment co-localizing with the lysosome-associated membrane protein LAMP-2."
- `a2_evi_02` · *Secondary* · Supports · Tissue Expression — ABCB9 (TAPL) is expressed at high levels in testicular Sertoli cells, which are known for lysosomal-mediated phagocytosis; this is a key tissue with enriched ABCB9 expression. ([PMC9532399](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9532399/))
  - *assay*: Human · testicular Sertoli cells
  > "Despite its high sequence homology to the TAP complex, TAPL is not involved in the MHC class I-dependent pathway of antigen presentation 14 , and high levels are found in testicular Sertoli cells, which function in lysosomal-mediated phagocytosis 7 ."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — Placental Abcb9 mRNA/protein expression is decreased in pregnant mice with malaria-in-pregnancy (Plasmodium berghei ANKA infection) compared to uninfected controls, indicating disease-state-dependent downregulation of ABCB9 in placental tissue. ([PMC6685947](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6685947/))
  - *assay*: Mouse · placenta
  > "Additionally, a decrease in placental Abca1 (ABCA1), Abcb1b (P-glycoprotein), Abcb9 and Abcg2 (BCRP) expression was observed in MiP mice."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — ABCB9 (Abcb9) protein was quantified by label-free proteomics in isolated rat blood-brain barrier microvessels, establishing its presence at the protein level in this specialized brain vascular compartment. (https://pubmed.ncbi.nlm.nih.gov/29675872/)
  - *assay*: Rat · brain microvessels / blood-brain barrier
  > "Label-free proteomics was used to identify nearly 2000 proteins and quantify 1276 proteins in isolated microvessels. A combination of targeted and global proteomics was adopted to measure protein abundance of 6 ATP-binding cassette and 27 solute carrier transporters. Data analysis using proprietary Progenesis and open access MaxQuant software showed overall agreement; however, Abcb9 and Slc22a8 were quantified only by MaxQuant, whereas Abcc9 and Abcd3 were quantified only by Progenesis."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — ABC transporter gene expression patterns in human brain microvessels versus peripheral tissues (lung, liver, spleen) and lung vessels were systematically profiled by RNA-seq across human, mouse, and rat; most ABC transporters including ABCB9 are enriched in peripheral tissues compared to brain microvessels in humans. ([PMC10221359](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10221359/))
  - *assay*: Human · brain microvessels, lung, liver, spleen
  > "The expression patterns/enrichment of <i>ABC</i> transporter genes in brain microvessels compared to peripheral vessels and tissues are largely uncharacterized.<h4>Methods</h4>In this study, the expression patterns of <i>ABC</i> transporter genes in brain microvessels, peripheral tissues (lung, liver and spleen) and lung vessels were investigated using RNA-seq and Wes<sup>TM</sup> analyses in three species: human, mouse and rat.<h4>Results</h4>The study demonstrated that <i>ABC</i> drug efflux transporter genes (including <i>ABCB1</i>, <i>ABCG2</i>"
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — ABCB9 is expressed in regulatory T cells (Tregs) and localizes to the lysosomal membrane within these cells. In the tumor microenvironment, ABCB9 participates in lysosomal metabolic programs in both tumor cells and human Tregs. Suppression of ABCB9 impairs GARP/TGF-β1 production, indicating a functional role in Treg immunosuppression. (https://pubmed.ncbi.nlm.nih.gov/38698265/)
  - *assay*: Human · regulatory T cells (Tregs), tumor cells
  > "Here, we demonstrated that tumour necrosis factor receptor-associated factor 3 interacting protein 3 (TRAF3IP3) in the Treg lysosome is involved in this activation mechanism. Using a novel naphthalenelactam-platinum-based anticancer drug (NPt), we developed a new synergistic effect by suppressing ATP-binding cassette subfamily B member 9 (ABCB9) and TRAF3IP3-mediated divergent lysosomal metabolic programs in tumors and human Tregs to block the production of active GARP/TGF-β1 for remodeling the tumor microenvironment."
- `a2_evi_07` · *Secondary* · Supports · Tissue Expression — ABCB9 (TAPL) expression is induced upon dendritic cell differentiation, consistent with a cell-state-dependent upregulation in professional antigen-presenting cells. This represents an accessibility modulation: baseline (resting monocytes) = absent/low; differentiated state (DCs) = induced. (https://pubmed.ncbi.nlm.nih.gov/21212514/)
  - *assay*: Human · monocytes / dendritic cells
  > "Although the physiological roles of TAPL have not been determined, expression of TAPL is induced upon dendritic cell differentiation. 12) Peptide transport into lysosomes could be enhanced under such conditions."
- `a2_evi_08` · *Primary* · Refutes · Surface Expression — Full-length ABCB9 (TAPL-GFP) co-localizes with the lysosomal marker LysoTracker in mammalian cells, while free GFP does not, confirming lysosomal membrane as the primary subcellular compartment. TAPL does not localize to ER or endosomes. (https://pubmed.ncbi.nlm.nih.gov/21212514/)
  - *assay*: Human · transfected mammalian cells · fixed · permeabilized
  > "The merged image (right) showed the good co-localization of the signals of hTAPL-GFP and LysoTracker, while the signal of free GFP did not overlap with that of LysoTracker (Fig. 1A, lower)."
- `a2_evi_09` · *Primary* · Refutes · Surface Expression — The core-TAPL complex (six-TM + NBD, lacking TMD0) localizes preferentially to the plasma membrane when expressed alone, demonstrating that TMD0 is the determinant of lysosomal vs plasma membrane targeting. Full-length TAPL with TMD0 is directed to lysosomes. This establishes that the full-length protein is a lysosomal membrane protein, not a cell-surface protein under normal conditions. (https://pubmed.ncbi.nlm.nih.gov/20377823/)
  - *assay*: Human · transfected mammalian cells · fixed · permeabilized
  > "The core-TAPL complex, composed of six predicted transmembrane helices and a nucleotide-binding domain, is sufficient for peptide transport, showing that the core transport complex is correctly targeted to and assembled in the membrane. Strikingly, in contrast to the full-length transporter, the core translocation complex is targeted preferentially to the plasma membrane. However, TMD0 alone, comprising a putative four transmembrane helix bundle, traffics to lysosomes."
- `a2_evi_10` · *Primary* · Refutes · Surface Expression — In LAMP-deficient cells, ABCB9 (TAPL) stability is markedly reduced (half-life decreased ~5-fold) due to increased lysosomal degradation. LAMP proteins normally retain TAPL on the limiting membrane of endosomes/lysosomes and prevent its sorting to intraluminal vesicles (ILVs). This LAMP interaction is a critical determinant of ABCB9's subcellular compartment positioning on the lysosomal limiting membrane rather than ILVs. (https://pubmed.ncbi.nlm.nih.gov/22641697/)
  - *assay*: Human · LAMP-deficient cells
  > "Reduced stability of TAPL is caused by increased lysosomal degradation, indicating that LAMP proteins retain TAPL on the limiting membrane of endosomes and prevent its sorting to intraluminal vesicles."
- `a2_evi_11` · *Primary* · Refutes · Surface Expression — Full-length ABCB9 (TAPL) subcellular localization depends solely on its N-terminal TMD0 domain (which lacks conventional lysosomal targeting sequences). The intracellular trafficking route to lysosomes is direct; conserved charged residues in TMD0 transmembrane helices are essential for lysosomal targeting steps. ([PMC6509505](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6509505/))
  - *assay*: Human · transfected cells · fixed · permeabilized
  > "The human lysosomal polypeptide ABC transporter TAPL (ABC subfamily B member 9, ABCB9) transports 6-59-amino-acid-long polypeptides from the cytosol into lysosomes. The subcellular localization of TAPL depends solely on its N-terminal transmembrane domain, TMD0, which lacks conventional targeting sequences. However, the intracellular route and the molecular mechanisms that control TAPL localization remain unclear. Here, we delineated the route of TAPL to lysosomes and investigated the determinants of single trafficking steps."
- `a2_evi_12` · *Primary* · Refutes · Surface Expression — An N-terminal truncation of TAPL (M1-G75, TAPL-S-GFP) distributes over all cellular membranes including the plasma membrane, whereas full-length TAPL localizes to intracellular membranes. This indicates that the M1-S275 region is essential for restricting TAPL to intracellular membranes and away from the cell surface. (https://pubmed.ncbi.nlm.nih.gov/15577206/)
  - *assay*: Human · transfected mammalian cells · fixed · permeabilized
  > "However, the fluorescence of TAPL-S-GFP (M1-G75) was distributed over all the cellular membranes including plasma membrane, indicating that the amino terminal region of TAPL (M1-S275) is essential for its localization to the intracellular membranes. A co-expression study demonstrated that TAPL-S-GFP was co-localized with TAPL-DR (DsRed-tagged TAPL) or TAP1-DR, suggesting that TAPL is able to interact with not only itself but also with TAP1 through the M1-G75 region of TAPL."
- `a2_evi_13` · *Primary* · Refutes · Surface Expression — The full-length ABCB9 (TAPL) protein fused to GFP localizes to lysosomal membranes upon stable expression. The N-terminal domain (Met1-Arg141) is sufficient for lysosomal targeting, while the core domain (Arg141-Ala766) distributes broadly to intracellular membranes. The lysosomal sorting signal resides within TMD0. (https://pubmed.ncbi.nlm.nih.gov/18952056/)
  - *assay*: Human · stably transfected mammalian cells · fixed · permeabilized
  > "The amino-terminal domain (Met(1)-Arg(141)) as well as the full-length transporter fused with fluorescent protein GFP was sorted to lysosomal membranes upon their stable expression, as visualized by means of fluorescent microscopy, while the core domain (Arg(141)-Ala(766)) was broadly distributed in the intra-cellular membranes. These results suggest that the sorting signal for lysosomes is present within the amino-terminal transmembrane domain (Met(1)-Arg(141)) of the TAPL molecule."
- `a2_evi_14` · *Primary* · Refutes · Surface Expression — ABCB9 (TAPL) may be localized to lipid raft microdomains (cholesterol-enriched regions) of lysosomal membranes, as suggested by co-sedimentation with lysosomal marker cathepsin D and detergent-resistant membrane fractionation. (https://pubmed.ncbi.nlm.nih.gov/21212514/)
  - *assay*: Human · transfected mammalian cells · permeabilized
  > "These results suggest that TAPL may be localized to the microdomains (lipid rafts) of lysosomal membranes enriched in cholesterol."
- `a2_evi_15` · *Primary* · Supports · Surface Expression — In regulatory T cells (Tregs), ABCB9 protein expression in the lysosomal membrane is promoted by the anticancer drug NPt, which increases ABCB9 levels and thereby inhibits SARA/p-SMAD2/3 signaling. This represents a cell-state/pharmacological modulation of ABCB9 lysosomal expression in Tregs. (https://pubmed.ncbi.nlm.nih.gov/38698265/)
  - *assay*: Human · regulatory T cells (Tregs)
  > "Mechanistically, NPt is stored in Treg lysosome to inhibit TRAF3IP3-meditated GARP/TGF-β1 complex activation to specifically deplete Tregs. In addition, by promoting the expression of ABCB9 in lysosome membrane, NPt inhibits SARA/p-SMAD2/3 through CHRD-induced TGF-β1 signaling pathway."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/ABCB9.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/ABCB9](https://surfaceome.deliverome.org/ABCB9)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/ABCB9.json](https://surfaceome.deliverome.org/data/surfaceome/ABCB9.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/ABCB9.md](https://surfaceome.deliverome.org/data/surfaceome/ABCB9.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/Q9NP78](https://alphafold.ebi.ac.uk/entry/Q9NP78)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/Q9NP78](https://alphafold.ebi.ac.uk/api/prediction/Q9NP78) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/Q9NP78](https://www.uniprot.org/uniprotkb/Q9NP78)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-Q9NP78-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-Q9NP78-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-Q9NP78-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-Q9NP78-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-Q9NP78-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-Q9NP78-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*766 aa · `Q9NP78` · embedded at build time*

```
   1  MRLWKAVVVTLAFMSVDICVTTAIYVFSHLDRSLLEDIRHFNIFDSVLDLWAACLYRSCL
  61  LLGATIGVAKNSALGPRRLRASWLVITLVCLFVGIYAMVKLLLFSEVRRPIRDPWFWALF
 121  VWTYISLGASFLLWWLLSTVRPGTQALEPGAATEAEGFPGSGRPPPEQASGATLQKLLSY
 181  TKPDVAFLVAASFFLIVAALGETFLPYYTGRAIDGIVIQKSMDQFSTAVVIVCLLAIGSS
 241  FAAGIRGGIFTLIFARLNIRLRNCLFRSLVSQETSFFDENRTGDLISRLTSDTTMVSDLV
 301  SQNINVFLRNTVKVTGVVVFMFSLSWQLSLVTFMGFPIIMMVSNIYGKYYKRLSKEVQNA
 361  LARASNTAEETISAMKTVRSFANEEEEAEVYLRKLQQVYKLNRKEAAAYMYYVWGSGLTL
 421  LVVQVSILYYGGHLVISGQMTSGNLIAFIIYEFVLGDCMESVGSVYSGLMQGVGAAEKVF
 481  EFIDRQPTMVHDGSLAPDHLEGRVDFENVTFTYRTRPHTQVLQNVSFSLSPGKVTALVGP
 541  SGSGKSSCVNILENFYPLEGGRVLLDGKPISAYDHKYLHRVISLVSQEPVLFARSITDNI
 601  SYGLPTVPFEMVVEAAQKANAHGFIMELQDGYSTETGEKGAQLSGGQKQRVAMARALVRN
 661  PPVLILDEATSALDAESEYLIQQAIHGNLQKHTVLIIAHRLSTVEHAHLIVVLDKGRVVQ
 721  QGTHQQLLAQGGLYAKLVQRQMLGLQPAADFTAGHNEPVANGSHKA
```

### Alternative-isoform sequences

**Q9NP78-2** (`Q9NP78-2` · 723 aa)

```
   1  MRLWKAVVVTLAFMSVDICVTTAIYVFSHLDRSLLEDIRHFNIFDSVLDLWAACLYRSCL
  61  LLGATIGVAKNSALGPRRLRASWLVITLVCLFVGIYAMVKLLLFSEVRRPIRDPWFWALF
 121  VWTYISLGASFLLWWLLSTVRPGTQALEPGAATEAEGFPGSGRPPPEQASGATLQKLLSY
 181  TKPDVAFLVAASFFLIVAALGETFLPYYTGRAIDGIVIQKSMDQFSTAVVIVCLLAIGSS
 241  FAAGIRGGIFTLIFARLNIRLRNCLFRSLVSQETSFFDENRTGDLISRLTSDTTMVSDLV
 301  SQNINVFLRNTVKVTGVVVFMFSLSWQLSLVTFMGFPIIMMVSNIYGKYYKRLSKEVQNA
 361  LARASNTAEETISAMKTVRSFANEEEEAEVYLRKLQQVYKLNRKEAAAYMYYVWGSGSVG
 421  SVYSGLMQGVGAAEKVFEFIDRQPTMVHDGSLAPDHLEGRVDFENVTFTYRTRPHTQVLQ
 481  NVSFSLSPGKVTALVGPSGSGKSSCVNILENFYPLEGGRVLLDGKPISAYDHKYLHRVIS
 541  LVSQEPVLFARSITDNISYGLPTVPFEMVVEAAQKANAHGFIMELQDGYSTETGEKGAQL
 601  SGGQKQRVAMARALVRNPPVLILDEATSALDAESEYLIQQAIHGNLQKHTVLIIAHRLST
 661  VEHAHLIVVLDKGRVVQQGTHQQLLAQGGLYAKLVQRQMLGLQPAADFTAGHNEPVANGS
 721  HKA
```

**Q9NP78-3** (`Q9NP78-3` · 596 aa)

```
   1  MRLWKAVVVTLAFMSVDICVTTAIYVFSHLDRSLLEDIRHFNIFDSVLDLWAACLYRSCL
  61  LLGATIGVAKNSALGPRRLRASWLVITLVCLFVGIYAMVKLLLFSEVRRPIRDPWFWALF
 121  VWTYISLGASFLLWWLLSTVRPGTQALEPGAATEAEGFPGSGRPPPEQASGATLQKLLSY
 181  TKPDVAFLVAASFFLIVAALGETFLPYYTGRAIDGIVIQKSMDQFSTAVVIVCLLAIGSS
 241  FAAGIRGGIFTLIFARLNIRLRNCLFRSLVSQETSFFDENRTGDLISRLTSDTTMVSDLV
 301  SQNINVFLRNTVKVTGVVVFMFSLSWQLSLVTFMGFPIIMMVSNIYGKYYKRLSKEVQNA
 361  LARASNTAEETISAMKTVRSFANEEEEAEVYLRKLQQVYKLNRKEAAAYMYYVWGSGLTL
 421  LVVQVSILYYGGHLVISGQMTSGNLIAFIIYEFVLGDCMESVGSVYSGLMQGVGAAEKVF
 481  EFIDRQPTMVHDGSLAPDHLEGRVDFENVTFTYRTRPHTQVLQNVSFSLSPGKVTALVGP
 541  SGSGKSSCVNILENFYPLEGGRVLLDGKPISAYDHKYLHRVVCARAWATLLRPFCI
```

**Q9NP78-5** (`Q9NP78-5` · 683 aa)

```
   1  MRLWKAVVVTLAFMSVDICVTTAIYVFSHLDRSLLEDIRHFNIFDSVLDLWAACLYRSCL
  61  LLGATIGVAKNSALGPRRLRASWLVITLVCLFVGIYAMVKLLLFSEVRRPIRDPWFWALF
 121  VWTYISLGASFLLWWLLSTVRPGTQALEPGAATEAEGFPGSGRPPPEQASGATLQKLLSY
 181  TKPDVAFLVAASFFLIVAALGETFLPYYTGRAIDGIVIQKSMDQFSTAVVIVCLLAIGSS
 241  FAAGIRGGIFTLIFARLNIRLRNCLFRSLVSQETSFFDENRTGDLISRLTSDTTMVSDLV
 301  SQNINVFLRNTVKVTGVVVFMFSLSWQLSLVTFMGFPIIMMVSNIYGKYYKRLSKEVQNA
 361  LARASNTAEETISAMKTVRSFANEEEEAEVYLRKLQQVYKLNRKEAAAYMYYVWGSGLTL
 421  LVVQVSILYYGGHLVISGQMTSGNLIAFIIYEFVLGDCMESVGSVYSGLMQGVGAAEKVF
 481  EFIDRQPTMVHDGSLAPDHLEGRVDFENVTFTYRTRPHTQVLQNVSFSLSPGKVTALVGP
 541  SGSGKSSCVNILENFYPLEGGRVLLDGKPISAYDHKYLHRVISLVSQEPVLFARSITDNI
 601  SYGLPTVPFEMVVEAAQKANAHGFIMELQDGYSTETGEKGAQLSGGQKQRVAMARALVRN
 661  PPVLILDEATSALDAESEYLCAG
```

**Q9NP78-6** (`Q9NP78-6` · 681 aa)

```
   1  MRLWKAVVVTLAFMSVDICVTTAIYVFSHLDRSLLEDIRHFNIFDSVLDLWAACLYRSCL
  61  LLGATIGVAKNSALGPRRLRASWLVITLVCLFVGIYAMVKLLLFSEVRRPIRDPWFWALF
 121  VWTYISLGASFLLWWLLSTVRPGTQALEPGAATEAEGFPGSGRPPPEQASGATLQKLLSY
 181  TKPDVAFLVAASFFLIVAALGETFLPYYTGRAIDGIVIQKSMDQFSTAVVIVCLLAIGSS
 241  FAAGIRGGIFTLIFARLNIRLRNCLFRSLVSQETSFFDENRTGDLISRLTSDTTMVSDLV
 301  SQNINVFLRNTVKVTGVVVFMFSLSWQLSLVTFMGFPIIMMVSNIYGKYYKRLSKEVQNA
 361  LARASNTAEETISAMKTVRSFANEEEEAEVYLRKLQQVYKLNRKEAAAYMYYVWGSGLTL
 421  LVVQVSILYYGGHLVISGQMTSGNLIAFIIYEFVLGDCMESVGSVYSGLMQGVGAAEKVF
 481  EFIDRQPTMVHDGSLAPDHLEGRVDFENVTFTYRTRPHTQVLQNVSFSLSPGKVTALVGP
 541  SGSGKSSCVNILENFYPLEGGRVLLDGKPISAYDHKYLHRVISLVSQEPVLFARSITDNI
 601  SYGLPTVPFEMVVEAAQKANAHGFIMELQDGYSTETGEKGAQLSGGQKQRVAMARALVRN
 661  PPVLILDEATSALDAESEYLI
```

**Q9NP78-7** (`Q9NP78-7` · 703 aa)

```
   1  MRLWKAVVVTLAFMSVDICVTTAIYVFSHLDRSLLEDIRHFNIFDSVLDLWAACLYRSCL
  61  LLGATIGVAKNSALGPRRLRASWLVITLVCLFVGIYAMVKLLLFSEVRRPIRDPWFWALF
 121  VWTYISLGASFLLWWLLSTVRPGTQALEPGAATEAEGFPGSGRPPPEQASGATLQKLLSY
 181  TKPDVAFLVAASFFLIVAALGETFLPYYTGRAIDGIVIQKSMDQFSTAVVIVCLLAIGSS
 241  FAAGIRGGIFTLIFARLNIRLRNCLFRSLVSQETSFFDENRTGDLISRLTSDTTMVSDLV
 301  SQNINVFLRNTVKVTGVVVFMFSLSWQLSLVTFMGFPIIMMVSNIYGKYYKRLSKEVQNA
 361  LARASNTAEETISAMKTVRSFANEEEEAEVYLRKLQQVYKLNRKEAAAYMYYVWGSGLTL
 421  LVVQVSILYYGGHLVISGQMTSGNLIAFIIYEFVLGDCMENVSFSLSPGKVTALVGPSGS
 481  GKSSCVNILENFYPLEGGRVLLDGKPISAYDHKYLHRVISLVSQEPVLFARSITDNISYG
 541  LPTVPFEMVVEAAQKANAHGFIMELQDGYSTETGEKGAQLSGGQKQRVAMARALVRNPPV
 601  LILDEATSALDAESEYLIQQAIHGNLQKHTVLIIAHRLSTVEHAHLIVVLDKGRVVQQGT
 661  HQQLLAQGGLYAKLVQRQMLGLQPAADFTAGHNEPVANGSHKA
```

### Canonical ortholog sequences

**Mouse — Abcb9** (`Q9JJ59` · 762 aa)

```
   1  MRLWKAVVVTLAFVSTDVGVTTAIYAFSHLDRSLLEDIRHFNIFDSVLDLWAACLYRSCL
  61  LLGATIGVAKNSALGPRRLRASWLVITLVCLFVGIYAMAKLLLFSEVRRPIRDPWFWALF
 121  VWTYISLAASFLLWGLLATVRPDAEALEPGNEGFHGEGGAPAEQASGATLQKLLSYTKPD
 181  VAFLVAASFFLIVAALGETFLPYYTGRAIDSIVIQKSMDQFTTAVVVVCLLAIGSSLAAG
 241  IRGGIFTLVFARLNIRLRNCLFRSLVSQETSFFDENRTGDLISRLTSDTTMVSDLVSQNI
 301  NIFLRNTVKVTGVVVFMFSLSWQLSLVTFMGFPIIMMVSNIYGKYYKRLSKEVQSALARA
 361  STTAEETISAMKTVRSFANEEEEAEVFLRKLQQVYKLNRKEAAAYMSYVWGSGLTLLVVQ
 421  VSILYYGGHLVISGQMSSGNLIAFIIYEFVLGDCMESVGSVYSGLMQGVGAAEKVFEFID
 481  RQPTMVHDGSLAPDHLEGRVDFENVTFTYRTRPHTQVLQNVSFSLSPGKVTALVGPSGSG
 541  KSSCVNILENFYPLQGGRVLLDGKPIGAYDHKYLHRVISLVSQEPVLFARSITDNISYGL
 601  PTVPFEMVVEAAQKANAHGFIMELQDGYSTETGEKGAQLSGGQKQRVAMARALVRNPPVL
 661  ILDEATSALDAESEYLIQQAIHGNLQRHTVLIIAHRLSTVERAHLIVVLDKGRVVQQGTH
 721  QQLLAQGGLYAKLVQRQMLGLEHPLDYTASHKEPPSNTEHKA
```

**Cynomolgus — ABCB9** (`G8F535` · 766 aa)

```
   1  MRLWKAVVVTLAFMSVDICVTTAIYVFSHLDRSLLEDIRHFNIFDSVLDLWAACLYRSCL
  61  LLGATIGVAKNSALGPRRLRASWLVITLVCLFVGIYAMVKLLLFSEVRRPIRDPWFWALF
 121  VWTYISLGASFLLWWLLSTVRPSTQALEPGAATEAEGFPGSGLPPPEQASGATLQKLLSY
 181  TKPDVAFLVAASFFLIVAALGETFLPYYTGRAIDGIVIQKSMDQFSTAVTIVCLLAIGSS
 241  FAAGIRGGIFTLIFARLNIRLRNCLFRSLVSQETSFFDENRTGDLISRLTSDTTMVSDLV
 301  SQNINVFLRNTVKVTGVVVFMFSLSWQLSLVTFMGFPIIMMVSNIYGKYYKRLSKEVQNA
 361  LARASNTAEETISAMKTVRSFANEEEEAEVYLRKLQQVYKLNRKEAAAYMYYVWGSGLTL
 421  LVVQVSILYYGGHLVISGQMTSGNLIAFIIYEFVLGDCMESVGSVYSGLMQGVGAAEKVF
 481  EFIDRQPTMVHDGSLAPDHLEGRVDFENVTFTYRTRPHTQVLQNVSFSLCPGKVTALVGP
 541  SGSGKSSCVNILENFYPLEGGRVLLDGKPISAYDHKYLHRVISLVSQEPVLFARSITDNI
 601  SYGLPTVPFEMVVEAAQKANAHGFIMELQDGYSTETGEKGAQLSGGQKQRVAMARALVRN
 661  PPVLILDEATSALDAESEYLIQQAIHGNLQKHTVLIIAHRLSTVEHAHLIVVLDKGRVVQ
 721  QGTHQQLLAQGGLYAKLVQRQMLGLEPAVDFTAGHKEPAANGSHKA
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`Q9NP78`, deeptmhmm-1.0.24)

```
   1  IIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMM
  61  MMMMMMMMIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOMMMMM
 121  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMM
 241  MMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIM
 301  MMMMMMMMMMMMMMMMMMMMOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIMMM
 421  MMMMMMMMOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 661  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 721  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Q9NP78-2** (`Q9NP78-2`, deeptmhmm-1.0.24)

```
   1  IIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMM
  61  MMMMMMMMIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOMMMMM
 121  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMM
 241  MMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIM
 301  MMMMMMMMMMMMMMMMMMMMOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 661  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 721  III
```

**Q9NP78-3** (`Q9NP78-3`, deeptmhmm-1.0.24)

```
   1  IIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMM
  61  MMMMMMMMIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOMMMMM
 121  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMM
 241  MMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIM
 301  MMMMMMMMMMMMMMMMMMMMOOOOOOOOOMMMMMMMMMMMMMMMMMMIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIM
 421  MMMMMMMMMOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Q9NP78-5** (`Q9NP78-5`, deeptmhmm-1.0.24)

```
   1  IIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMM
  61  MMMMMMMMIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOMMMMM
 121  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMM
 241  MMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIM
 301  MMMMMMMMMMMMMMMMMMMMOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIM
 421  MMMMMMMMMOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 661  IIIIIIIIIIIIIIIIIIIIIII
```

**Q9NP78-6** (`Q9NP78-6`, deeptmhmm-1.0.24)

```
   1  IIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMM
  61  MMMMMMMMIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOMMMMM
 121  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMM
 241  MMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIM
 301  MMMMMMMMMMMMMMMMMMMMOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIM
 421  MMMMMMMMMOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 661  IIIIIIIIIIIIIIIIIIIII
```

**Q9NP78-7** (`Q9NP78-7`, deeptmhmm-1.0.24)

```
   1  IIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMM
  61  MMMMMMMMIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOMMMMM
 121  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMM
 241  MMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIM
 301  MMMMMMMMMMMMMMMMMMMMOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIMMM
 421  MMMMMMMMOOOOOOOOOOOOOOOOMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 661  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Mouse ortholog — Abcb9** (`Q9JJ59`, projected onto human canonical)

```
   1  IIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMM
  61  MMMMMMMMIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOMMMMM
 121  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  MMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMM
 241  MMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIMMMMM
 301  MMMMMMMMMMMMMMMMOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIMMMMMMM
 421  MMMMOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 661  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 721  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Cynomolgus ortholog — ABCB9** (`G8F535`, projected onto human canonical)

```
   1  IIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMM
  61  MMMMMMMMIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOMMMMM
 121  MMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMM
 241  MMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIM
 301  MMMMMMMMMMMMMMMMMMMMOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIMMM
 421  MMMMMMMMOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 541  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 601  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 661  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 721  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence high — Confidence is high for the low/endomembrane call because the evidence is internally consistent, multi-method, and from multiple independent groups: NMR structural analysis, LysoTracker co-localization, Percoll-gradient fractionation, and stable-expression fluorescence microscopy all converge on strict lysosomal localization with no plasma membrane signal for the full-length protein. The triage verdict (contextual via lysosomal exocytosis) is overridden here because no gene-specific evidence for a PM pool via lysosomal exocytosis exists — this is class-level extrapolation, not ABCB9-specific data. The restricted_subdomain risk (high severity, strong evidence) further reinforces that the lysosomal compartment is inaccessible to extracellular binders. No contradictions exist; state-modulation (DC differentiation, TME) increases lysosomal expression, not PM exposure.*
