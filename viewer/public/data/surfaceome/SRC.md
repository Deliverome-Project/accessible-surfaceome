# SRC — Surface Accessibility Brief

*Schema v1.0.0 · generated 2026-05-17T13:05:27.108512Z · model `claude-sonnet-4-6`*

> SRC (P12931) is a non-receptor tyrosine kinase anchored exclusively to the cytoplasmic inner leaflet of the plasma membrane via N-myristoylation; it has no extracellular domain and no transmembrane segment. All evidence—biophysical inner-leaflet anchoring, membrane-fractionation MS, HPA IHC—demonstrates plasma-membrane association but not extracellular-face accessibility. SURFY/CSPA exclude SRC from the surfaceome. Approved drugs (dasatinib, bosutinib) act intracellularly. Surface accessibility is therefore low; any engagement strategy requires cell-permeable or intrabody-type binders.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:11283](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:11283) |
| UniProt | [P12931](https://www.uniprot.org/uniprotkb/P12931) |
| NCBI Gene | [6714](https://www.ncbi.nlm.nih.gov/gene/6714) |
| Ensembl | [ENSG00000197122](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000197122) |
| Subcategory | Other |
| Surface accessibility | Low |
| Confidence | Moderate |
| Evidence grade | Supportive but indirect |
| Triage signal | Unknown |
| Headline risks | Ecd Too Small, Restricted Subdomain, Other |

## 1. Executive summary

SRC (P12931) is a non-receptor tyrosine kinase anchored exclusively to the cytoplasmic inner leaflet of the plasma membrane via N-myristoylation; it has no extracellular domain and no transmembrane segment. All evidence—biophysical inner-leaflet anchoring, membrane-fractionation MS, HPA IHC—demonstrates plasma-membrane association but not extracellular-face accessibility. SURFY/CSPA exclude SRC from the surfaceome. Approved drugs (dasatinib, bosutinib) act intracellularly. Surface accessibility is therefore low; any engagement strategy requires cell-permeable or intrabody-type binders.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=Low · conf=Moderate · subcategory=Other · grade=Supportive but indirect · ecd=None · density=Moderate |
| Expression | level=Moderate · breadth=Pan Tissue · specificity=Mostly Intracellular |
| Risks | shed=false · secreted=false · coreceptor=false · masking=false · subdomain=true |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=0 · N-term-ECF=false · C-term-ECF=false |

## 3. Surface evidence

**Evidence grade** · Supportive but indirect

SRC (P12931) is a non-receptor tyrosine kinase anchored to the cytoplasmic inner leaflet of the plasma membrane via N-myristoylation at Gly-2, not a canonical surface-accessible protein with an extracellular domain. HPA IHC (supported reliability) detects SRC at plasma membrane and cell junctions; multiple membrane-fractionation and surfaceome MS studies co-isolate SRC with membrane-enriched fractions (SKBR3 membrane proteome, NIS-PM complex pull-down, chondrogenic surfaceome); and biophysical studies confirm lipid-bilayer anchoring via the myristoylated SH4 domain. However, no direct live-cell flow cytometry or cell-surface biotinylation study demonstrates extracellular-face accessibility of SRC. SURFY and CSPA databases do not vote SRC as a surface protein. The strongest evidence category is plasma membrane localization by IHC and membrane proteomics fractionation, both indirect for surface accessibility.

### IHC Membranous — Supports Membrane Association

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- HPA anti-SRC antibody panel (Human Protein Atlas) — Intracellular epitope; Moderate validation

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HPA IHC detects SRC at plasma membrane, cell junctions, and vesicles across multiple tissue types; reliability tier: supported | Primary Human Tissue | Moderate | 2 |

### Plasma Membrane Fractionation — Supports Membrane Association

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| SRC identified in cell-membrane proteome of SKBR3 HER2+ breast cancer cells by membrane-enrichment LC-MS/MS (Karcini & Lazar 2022) | Established Cell Line | Moderate | 2 |

### Cell Surface Capture — Supports Membrane Association

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| SRC kinase detected in surfaceome cluster 2 of chondrogenic cells by sialoglycoprotein-enrichment LC-MS/MS (Kovacs et al. 2025) | Unknown | Moderate | 2 |

### Plasma Membrane Fractionation — Supports Membrane Association

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| SRC co-isolated with NIS plasma membrane complexes using intact-cell labeling and immunoprecipitation in thyroid cancer cells (Faria et al. 2021) | Established Cell Line | Moderate | 2 |

### Unknown — Supports Membrane Association

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Biophysical studies confirm myristoylated Src anchors to lipid bilayer inner leaflet via SH4 domain and forms condensates (Mohammad et al. 2025) | Established Cell Line | High | 2 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| IHC in breast carcinoma cell lines shows activated c-Src predominantly in the cytoplasm, indicating a large intracellular pool (Ito et al. 2002) | Patient Sample | IHC Protein | Moderate | 1 |
| c-Src localizes to endosomal membranes in transformed cells and is encapsulated in secreted exosomes, revealing a non-plasma-membrane pool (Hikita et al. 2019) | Established Cell Line | Bulk Protein | Moderate | 1 |
| UniProt records multiple subcellular locations for SRC including cytoplasm, perinuclear region, nucleus, and mitochondrion inner membrane, confirming substantial intracellular pools | Unknown | Bulk Protein | High | 1 |

**Therapeutic engagement**

*Approved Drug*

Dasatinib (Sprycel) and bosutinib are FDA-approved BCR-ABL/SRC kinase inhibitors used in CML and ALL. These drugs bind intracellularly to the ATP-binding pocket of SRC's kinase domain and do not engage an extracellular epitope.

> Surface-form rationale: All approved SRC-targeting drugs act on the intracellular kinase domain. SRC has no extracellular domain; no antibody therapeutic targeting a surface-exposed SRC epitope is currently approved.

**Contradicting evidence**

- *Alternative Localization* (severity Moderate): SURFY and CSPA databases do not classify SRC as a cell-surface protein, consistent with its lack of a transmembrane domain and extracellular-facing epitopes.
  - Likely explanation: SRC is a peripheral membrane protein anchored to the cytoplasmic inner leaflet via N-myristoylation. It has no TM domain or ECD and is not accessible from the extracellular space. Surfaceome databases using impermeant-label strategies correctly exclude it.
- *Intracellular Pool* (severity Low): Immunofluorescence in breast carcinoma cell lines shows activated c-Src predominantly in the cytoplasm, not at the plasma membrane surface.
  - Likely explanation: SRC dynamically partitions between the inner leaflet of the plasma membrane and endomembranes. Cytoplasmic staining reflects physiological cycling rather than absence from the membrane.

## 4. Biological context

**Tissues × disease context**

| Tissue | Disease context | Level (protein) | Cell types | Cell states |
|---|---|---|---|---|
| kidney (clear cell renal cell carcinoma) | Tumor | High | renal carcinoma cells | high tumor stage, high grade |
| breast | Tumor | Mixed | breast carcinoma cells | low-grade tumor |
| breast | Normal | Absent | glandular epithelial cells, myoepithelial cells, stromal cells | — |
| cervix | Tumor | High | squamous carcinoma cells | carcinoma in situ, invasive carcinoma |
| cervix | Normal | Low | — | — |
| ubiquitous (multiple tissues) | Normal | Moderate | platelets, neurons, osteoclasts | — |
| skin | Normal | Moderate | — | — |
| cartilage / chondrogenic cells | Normal | Moderate | chondrocytes, chondroprogenitor cells | chondrogenic differentiation (day 6 peak) |
| breast (HER2+ cancer cell membrane) | Tumor | High | SKBR3 HER2+ cancer cells | — |
| thyroid | Normal | Moderate | thyroid follicular cells | — |

**Primary subcellular compartment**: Plasma membrane

**Anatomical accessibility**

- Systemic or intravascular access (blood vessels, tumors) — Blood Interstitial Facing · *Context Dependent*: SRC is a cytoplasmic-face peripheral membrane kinase anchored by N-myristoylation with no extracellular domain. Its kinase domain faces the cytoplasm, making it inaccessible to extracellular antibodies or ligands under normal membrane integrity; access requires delivery of cell-permeable or intrabody-type binders.

**Accessibility modulation**

- *Post Translational Dependent*: Quiescent cells; Src in closed/inactive conformation, distributed between cytosol and plasma membrane inner leaflet → Activating phosphorylation at Tyr419 (autocatalysis) or dephosphorylation of inhibitory Tyr530; loss of CSK-mediated suppression — Conformational opening of Src exposes kinase domain; membrane association increases via N-myristoylation and SH4 lysine cluster; lipid-driven condensates form at inner plasma membrane leaflet.
- *Stress Induced* · trigger: Mechanical Stress: Unstimulated osteoblast-like cells with low c-Src Tyr416 phosphorylation and cytoplasmic/peripheral Src distribution → Fluid shear stress applied to osteoblast-like MC3T3-E1 cells — Fluid shear stress increases c-Src activation (Tyr416 phosphorylation) and promotes co-localisation of Src with RANKL at the cell periphery and membrane fraction.
- *Activation Induced* · trigger: Cytokine Stimulation: Resting monocytes with basal Src membrane association → Sustained oxLDL or free cholesterol challenge (monocytes) — Membrane clustering of Src drives the Src-SYK-mTORC1-STAT3/5 signalling axis; inflammatory state persists even after stimulus withdrawal (immune memory-like phenotype). Fumagillin (myristoylation inhibitor) disrupts Src clustering and alleviates activation.
- *Disease State Induced* · trigger: Oncogenic Transformation: Normal epithelial or fibroblast cells with predominantly plasma-membrane-associated Src → Oncogenic transformation / c-Src overexpression in cancer cells — Activated c-Src redistributes to endosomal membranes, where it promotes ESCRT-mediated intraluminal vesicle formation and exosome secretion; plasma-membrane pool is supplemented by an endosomal pool.
- *Developmental Stage*: Early-stage or late-stage chondrogenic differentiation (days 1–3 or days 10–15 of micromass culture) → Mid-stage chondrogenic differentiation (day 6 micromass culture) — SRC kinase expression in the surfaceome peaks at day 6, the stage at which kinase activity, ephrin-receptor and FGF-signalling GO terms are most enriched; expression subsides thereafter.
- *Dual Localization*: Plasma membrane inner leaflet (primary compartment, N-myristoylation-anchored) → Transformed / cancer cells with high Src activity — c-Src distributes between plasma membrane and endosomal membrane; endosomal pool is activated and encapsulated in secreted exosomes.

## 5. Isoforms

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24*

| Isoform | UniProt | TM | N-term | Signal pep | ECD len | ICD len |
|---|---|---|---|---|---|---|
| **canonical** | P12931 | 0 | Cytoplasmic | 0 aa | 0 aa | 536 aa |

## 6. Paralogs

*Per-antibody cross-reactivity behavior is captured per-clone under §3 (Surface evidence → antibodies). The LLM cross-reactivity verdict is deferred to v1.x.*

## 7. Orthologs

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

- present: true
- severity: Moderate
- evidence: Moderate
- domain: Other
- rationale: SRC is restricted to the cytoplasmic (inner) leaflet of the plasma membrane; it is not accessible from the extracellular face. Within the inner leaflet it further concentrates in lipid-raft-like condensates, focal adhesions, and cell junctions depending on activation state, further limiting binder access strategies.

**Co-receptor requirements**

- dependency: None
- evidence basis: Co Expression Only
- rationale: SRC membrane anchoring is entirely myristoylation-driven (Gly2 N-myristoylation + SH4 lysine cluster); no obligate co-receptor is required for membrane association. The NIS/SRC interaction reflects a regulatory complex at the PM inner leaflet rather than a trafficking dependency.

**ECD size assessment**

- ECD class: None
- rationale: SRC is a peripheral membrane protein with no transmembrane domain and no extracellular domain; its entire kinase, SH2, and SH3 domains face the cytoplasm. Biophysical studies confirm exclusive inner-leaflet anchoring via the myristoylated SH4 domain. No extracellular epitope exists for antibody or biologics engagement.

**Epitope masking**

- severity: None
- evidence: Inferred
- mechanism: None
- rationale: Epitope masking is not applicable: SRC has no extracellular domain and therefore no extracellular epitope to be masked. All functional domains are intracellular and inaccessible to conventional biologics without cell penetration.

## 9. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P12931-F1-model_v4](https://alphafold.ebi.ac.uk/entry/P12931) |
| AFDB version | v4 |
| ECD mean pLDDT | 0.0 |
| ECD disordered fraction | 0.0% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P12931) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

## 10. Evidence ledger

27 entries · 13 primary · 14 secondary · 0 tertiary · 9 PMC OA.

- `a1_evi_01` · *Secondary* · entailment ✓ — HPA IHC with supported reliability detects SRC protein at the plasma membrane and cell junctions in human tissues. (https://www.proteinatlas.org/ENSG00000197122/cell)
- `a1_evi_02` · *Secondary* · entailment ✓ — HPA flags SRC as plasma-membrane accessible with supported reliability tier, indicating IHC staining at the plasma membrane passed reliability criteria. (https://www.proteinatlas.org/ENSG00000197122/cell)
- `a1_evi_03` · *Secondary* · entailment ✓ — SRC identified in the SKBR3 cell-membrane proteome among receptor/enzymatic-activity proteins in a plasma-membrane-enriched fraction by LC-MS/MS. ([PMC9237123](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9237123/))
- `a1_evi_04` · *Secondary* · entailment ✓ — The SKBR3 study performed cell-membrane proteome enrichment followed by LC-MS to identify ~2000 membrane-associated proteins, providing the methodological basis for SRC detection. ([PMC9237123](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9237123/))
- `a1_evi_05` · *Secondary* · entailment ✓ — SRC kinase was detected in surfaceome cluster 2 of chondrogenic cells by sialoglycoprotein-enrichment LC-MS/MS, a cell-surface capture approach. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
- `a1_evi_06` · *Secondary* · entailment ✓ — The chondrogenic surfaceome study used sialoglycoprotein enrichment via aminooxy-biotin conjugation with LC-MS/MS to profile the surfaceome across differentiation stages. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
- `a1_evi_07` · *Secondary* · entailment ✓ — SRC was co-isolated with NIS plasma membrane complexes using intact-cell labeling and immunoprecipitation from thyroid cells, placing SRC in the NIS-interacting PM subnetwork. ([PMC8582450](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8582450/))
- `a1_evi_08` · *Secondary* — Biochemical analysis established the SRC/RAC1/PAK1/PIP5K/EZRIN pathway as a key regulator of NIS anchoring and retention at the plasma membrane of thyroid cells.
- `a1_evi_09` · *Primary* — Active Src is anchored to the plasma membrane via N-myristoylation; biophysical lipid-bilayer experiments confirm inner-leaflet membrane association of full-length myristoylated Src.
- `a1_evi_10` · *Primary* — Myristoylated full-length Src forms micron-sized condensates on supported lipid bilayers, directly confirming inner-leaflet membrane anchoring via the N-terminal SH4 domain.
- `a1_evi_11` · *Secondary* · entailment ✓ — IHC of breast carcinoma cells shows activated c-Src predominantly in the cytoplasm, indicating a substantial intracellular pool rather than exclusive plasma membrane localization. (https://pubmed.ncbi.nlm.nih.gov/12462387/)
- `a1_evi_12` · *Secondary* — c-Src localizes to endosomal membranes in transformed cells and is encapsulated in secreted exosomes, revealing a significant non-plasma-membrane pool.
- `a1_evi_13` · *Secondary* — c-Src is activated under the plasma membrane in early carcinogenesis, consistent with its predominant inner-leaflet localization and membrane-proximal signaling role.
- `a1_evi_14` · *Secondary* · entailment ✓ — SURFY and CSPA databases do not vote SRC as a cell-surface protein, consistent with its classification as a peripheral non-receptor tyrosine kinase lacking a transmembrane domain or extracellular domain. (https://www.proteinatlas.org/ENSG00000197122/cell)
- `a2_evi_01` · *Primary* — Strong SRC protein expression by IHC in ccRCC tumors correlates with high tumor stage, high grade, and shorter patient survival, qualifying SRC as an independent prognostic biomarker in this tumor type.
- `a2_evi_02` · *Primary* · entailment ✓ — IHC scoring in the RCC study evaluated cytoplasmic staining intensity of SRC (negative/weak/moderate/strong), demonstrating that SRC localises primarily to cytoplasm in tumor cells rather than membrane in this context. ([PMC12012843](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12012843/))
- `a2_evi_03` · *Primary* · entailment ✓ — Activated c-Src (phospho-Src) is expressed in ~51% of human breast carcinoma tissues but is absent from normal glandular epithelial, myoepithelial, and stromal cells; expression is cytoplasmic and inversely correlated with aggressiveness markers. (https://pubmed.ncbi.nlm.nih.gov/12462387/)
- `a2_evi_04` · *Primary* — Phospho-Src expression in human cervical specimens increases from normal cervix to carcinoma in situ to invasive squamous cell carcinoma (CSCC), and is an independent predictor of recurrence-free survival by IHC.
- `a2_evi_05` · *Secondary* — SRC is ubiquitously expressed at the protein level, with platelets, neurons, and osteoclasts expressing 5–200-fold higher levels than most tissues; UniProt annotates subcellular localisation to cell membrane, mitochondrial inner membrane, nucleus, cytosol/perinuclear region, focal adhesions, and cell junctions; N-myristoylation at Gly2 is the primary membrane anchor.
- `a2_evi_06` · *Primary* · entailment ✓ — SRC kinase was identified in the surfaceome of chondrogenic cells (Cluster 2) peaking at differentiation day 6 by sialoglycoprotein-enrichment LC-MS/MS, indicating stage-specific surface association during chondrogenic differentiation. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
- `a2_evi_07` · *Primary* · entailment ✓ — SRC was detected in the cell-membrane proteome of HER2+ SKBR3 breast cancer cells by membrane enrichment and mass spectrometry; it was classified among receptor/enzymatic activity proteins mediating chemokine signalling and chemotaxis. ([PMC9237123](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9237123/))
- `a2_evi_08` · *Primary* · entailment ✓ — SRC was identified as a plasma-membrane interactor of the sodium-iodide symporter (NIS) in thyroid cells by intact-cell labelling/immunoprecipitation and mass spectrometry; the SRC/RAC1/PAK1/PIP5K/EZRIN pathway regulates NIS retention at the plasma membrane. ([PMC8582450](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8582450/))
- `a2_evi_09` · *Primary* — Membrane clustering of Src is responsible for sustained inflammatory activation in monocytes persistently challenged with oxLDL or free cholesterol; the Src-SYK-mTORC1-STAT3/5 axis drives a memory-like pro-inflammatory phenotype, and fumagillin (myristoylation inhibitor) disrupts Src clustering and alleviates monocyte activation.
- `a2_evi_10` · *Primary* — Fluid shear stress activates c-Src (Tyr416 phosphorylation) in osteoblast-like MC3T3-E1 cells and promotes membrane-proximal redistribution of Src; constitutively active Src (Y527F) mimics this peripheral localisation even without shear.
- `a2_evi_11` · *Primary* — In c-Src-transformed cells, activated c-Src localised to endosomal membranes promotes exosome secretion via ESCRT/Alix; a correlation between Src upregulation, endosomal Src pool, and malignant phenotype is reported in cancer cells.
- `a2_evi_12` · *Primary* — Src self-associates via a lysine cluster in its SH4 region through lipid-mediated interactions, forming micron-sized condensates anchored to the plasma membrane inner leaflet; this lipid-driven self-association is an additional regulatory mechanism that modulates Src membrane residence and transforming capacity.
- `a2_evi_13` · *Secondary* · entailment ✓ — HPA IHC (Supported reliability) localises SRC to plasma membrane, cell junctions, and vesicles in human tissue samples; HPA annotates SRC as plasma-membrane accessible with junctional localization. (https://www.proteinatlas.org/ENSG00000197122/cell)

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/SRC.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/SRC](https://surfaceome.deliverome.org/SRC)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/SRC.json](https://surfaceome.deliverome.org/data/surfaceome/SRC.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/SRC.md](https://surfaceome.deliverome.org/data/surfaceome/SRC.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P12931](https://alphafold.ebi.ac.uk/entry/P12931)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P12931](https://alphafold.ebi.ac.uk/api/prediction/P12931) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P12931](https://www.uniprot.org/uniprotkb/P12931)

### Canonical UniProt sequence

*536 aa · fetched from AFDB API at build time*

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

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- Ensembl Compara orthologs & paralogs — — · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022; academic-use service)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — A1 grades evidence as 'supportive_but_indirect' and this synthesis tracks that grade. The topology is unambiguous—inner-leaflet peripheral kinase, no ECD—supported by strong biophysical primary data (a1_evi_09, a1_evi_10, a2_evi_12) and consistent database exclusion from surfaceome calls (a1_evi_14). However, multiple membrane-fractionation MS studies superficially detect SRC in surface fractions, creating mild conflicting signal. State-dependence is moderate: PM association is modulated by activation state, oncogenic transformation (endosomal redistribution), and differentiation stage (chondrogenic day-6 peak). Confidence is 'moderate' rather than 'high' because the surface-fraction MS detections require careful interpretation and state-dependent variability is real.*
