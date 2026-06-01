# SRC — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-31T15:44:53.406494Z · model `claude-sonnet-4-6`*

> SRC (p60-Src) is a non-receptor tyrosine kinase canonically anchored to the inner leaflet of the plasma membrane via N-myristoylation and palmitoylation, with all functional domains facing the cytoplasm. Two 2025 publications (PMID:41818370, PMID:41818382) report that in cancer cells, autophagolysosomal exocytosis (ALE) drives topological inversion of Src onto the outer plasma membrane face, creating extracellular membrane-associated eSrc detectable in primary tumors and targetable by antibody-based therapies in xenograft models. Surface accessibility is therefore high in cancer but strictly state-gated; normal cells retain canonical inner-leaflet topology.

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

SRC (p60-Src) is a non-receptor tyrosine kinase canonically anchored to the inner leaflet of the plasma membrane via N-myristoylation and palmitoylation, with all functional domains facing the cytoplasm. Two 2025 publications (PMID:41818370, PMID:41818382) report that in cancer cells, autophagolysosomal exocytosis (ALE) drives topological inversion of Src onto the outer plasma membrane face, creating extracellular membrane-associated eSrc detectable in primary tumors and targetable by antibody-based therapies in xenograft models. Surface accessibility is therefore high in cancer but strictly state-gated; normal cells retain canonical inner-leaflet topology.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=Moderate · subcategory=Other · ecd=None |
| Classification | reason=Lysosomal Exocytosis · family=Enzyme · state-dependence=High · induction-trigger=Oncogenic |
| Expression | level=Moderate · breadth=Broad · specificity=Mostly Intracellular · low-endogenous=false · tumor-associated=true · orphan-receptor=false · OE-precedent=false |
| Risks | shed=false · secreted=false · co-receptor=None · masking=true · restricted-subdomain=false |
| Evidence | grade=Direct, single method · density=Moderate · live-cell-surface=true · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=0 · N-term-ECF=false · C-term-ECF=false |

## 3. Surface evidence

**Evidence grade** · Direct, single method

The primary surface evidence comes from two papers (PMID:41818370 and PMID:41818382) reporting ALE-mediated topological inversion of Src onto the outer surface of cancer cells (eSrc), corroborated by antibody-mediated tumor killing in xenografts — functional proof of extracellular face accessibility. These are moderate-weight supports from what appear to be review-level summaries of experimental work rather than primary direct-method papers with full methodology detail, and all derive from the same cancer-state ALE mechanism, limiting them to a single conceptual method type. A weak additional surfaceome MS hit exists in chondrocytes (a1_evi_07), but SRC lacks canonical glycosylation, reducing confidence. Claims describing canonical inner-leaflet topology (a1_evi_12, a1_evi_13) describe baseline/non-cancer states and are tangential, not contradictory. No definitive non-permeabilized IF or surface biotinylation result with KO controls from an independent method is documented. Grade: direct_single_method (ALE-exocytosis surface exposure methodology, cancer state, two independent sources but one mechanism type).

### Surface mass spec (1 method)

#### Cell Surface Capture — Supports Membrane Association

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Primary human chondrocytes in micromass culture (days 1-15), surfaceome cluster 2 hit by N-glycan/sialoglycoprotein cell-surface capture LC-MS/MS | Primary Human Cell | Low | 1 |

### Surface biotinylation (1 method)

#### Surface Biotinylation — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-SRC (60315-1-Ig · Proteintech · 60315-1-Ig) — Intracellular epitope; Weak validation; Clone 5E10C4; immunogen is full-length SRC (1-536 aa); used for WB detection after surface biotinylation pulldown, not direct surface staining.
- anti-phospho-Y416-SRC (D49G4 · Cell Signaling Technology · #6943) — Intracellular epitope; Weak validation; Rabbit recombinant monoclonal; targets pTyr416 activation loop (intracellular kinase domain); cross-reacts with Src family members (Fyn, Hck, Lck, Lyn, Yes) at the equivalent pTyr site.

### Membrane fractionation (1 method)

#### Whole Cell Proteomics — Weak Or Ambiguous

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| High-invadopodia-activity cancer cell lines; SRC detected in secreted extracellular vesicle (sEV) proteome fraction, cluster 2 with CTTN, CFL1, ITGA3, ITGB3 | Established Cell Line | Moderate | 1 |

### Functional surface assay (2 methods)

#### Unknown — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-Src (therapeutic) — Extracellular epitope; None validation; Antibody targets extracellular face of topologically inverted eSrc; specific clone and vendor not reported in the abstract-level claims.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Cancer cell lines (in vitro): anti-Src antibody-based therapy mediates tumor cell killing; eSrc detected via autophagolysosomal exocytosis (ALE)-dependent surface inversion | Established Cell Line | Moderate | 3 |
| Mouse xenograft tumor models: anti-Src antibody-based therapies mediate tumor cell killing in vivo; eSrc found in primary tumors | Xenograft | Moderate | 1 |

#### Unknown — Direct Surface Accessibility

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-Src (therapeutic) — Extracellular epitope; None validation; Antibody engages extracellular eSrc exposed by exocytosis; specific clone and vendor not reported in the abstract-level claim.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Cancer cells: exocytosis exposes Src at the outer cell surface, corroborating eSrc as a therapeutically accessible surface target (companion paper PMID:41818382) | Established Cell Line | Moderate | 1 |

### Other (1 method)

#### Whole Cell Proteomics — Weak Or Ambiguous

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-THY1 — Unknown epitope; None validation

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HONE1-VA, HONE1-THY1, and NP460 nasopharyngeal carcinoma cell lines; SRC co-immunoprecipitates with GPI-anchored surface protein THY1 (CD90) via anti-THY1 pulldown, consistent with inner-leaflet PM association | Established Cell Line | Moderate | 1 |

**Contradicting evidence**

- *Intracellular Pool* (severity Moderate): Fluid shear stress experiments in MC3T3-E1 osteoblast-like cells show that c-Src activation (Tyr416 phosphorylation) promotes redistribution of RANKL to the plasma membrane, but Src itself remains intracellular as the activating kinase. This functional assay documents Src as an intracellular signaling enzyme rather than a cell-surface–accessible protein, contradicting a surface-accessibility hypothesis for SRC.
  - Likely explanation: Src is a myristoylated, inner-leaflet peripheral membrane kinase; its activation at the plasma membrane does not render it extracellularly accessible. The assay measures kinase activity and downstream surface redistribution of RANKL, not SRC surface exposure, so the contradiction reflects canonical SRC topology rather than a novel finding.
- *Alternative Localization* (severity Moderate): Co-immunoprecipitation of SRC with THY1 (a GPI-anchored surface protein) in nasopharyngeal carcinoma cell lines demonstrates that SRC associates with the inner leaflet of the plasma membrane beneath a surface-exposed GPI-anchored protein, not with the extracellular face. This is consistent with canonical SRC inner-leaflet localization and contradicts the notion that SRC itself is extracellularly surface accessible.
  - Likely explanation: GPI-anchored proteins such as THY1 reside in the outer leaflet, while SRC is tethered to the inner leaflet via N-terminal myristoylation/palmitoylation. Co-IP simply reflects intracellular signaling complex formation at the cytoplasmic face of the membrane; SRC is not exposed on the extracellular surface.

## 4. Biological context

*Accessibility context* — Surface-accessible only on cancer cells, where autophagolysosomal exocytosis (ALE) drives topological inversion of inner-leaflet SRC onto the outer plasma membrane face (eSrc), enabling antibody-based tumor cell killing.

**Tissues × disease context**

| Tissue | Disease context | Level (protein) | Cell types | Cell states |
|---|---|---|---|---|
| primary tumor tissue | Tumor | High | tumor cells | cancer-state-induced surface Src |
| glioblastoma (small extracellular vesicle surfaceome) | Tumor | Moderate | glioblastoma cells | high invadopodia activity |

**Primary subcellular compartment**: Plasma membrane

**Accessibility modulation**

- *Disease State Induced* · trigger: Oncogenic Transformation: Normal (non-cancer) cells where Src is canonically anchored to the inner leaflet of the plasma membrane with all domains facing the cytoplasm → Cancer cells (in vitro cell lines and in vivo primary tumors) — Src is noncanonically translocated and inverted onto the outer cell surface; a pool of extracellular membrane-associated Src (eSrc) appears on the outer face of the plasma membrane, absent in normal cells.
- *Lysosomal Exocytosis* · trigger: Oncogenic Transformation: Normal (non-cancer) cells lacking autophagolysosomal exocytosis (ALE) activity sufficient to expose Src at the outer surface → Cancer cell lines with active autophagolysosomal exocytosis (ALE) — ALE drives secretory inversion of Src from the cytoplasmic inner leaflet to the extracellular face of the plasma membrane, creating the eSrc surface pool.

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Weak
- domain: Unknown
- rationale: No evidence in the ledger demonstrates restriction of eSrc to a specific membrane subdomain (apical, junctional, ciliary, etc.). The ALE-driven surface inversion data from cancer cell lines and primary tumors does not indicate subdomain restriction. No relevant subdomain-distribution IF or fractionation data in the ledger.

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: SRC membrane anchoring in canonical state is entirely myristoylation/palmitoylation-driven; no obligate co-receptor is required for inner-leaflet membrane association. In cancer, the ALE-driven surface inversion is an intrinsic cell-state mechanism, not dependent on a specific co-receptor partner for surface delivery.

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N-term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P12931 | ref | ref | 0 | 0 aa | 536 aa | 0 aa | Cytoplasmic | — |
| Isoform | P12931-2 | P12931-2 | 100.0% | — | 0 | 0 aa | 542 aa | 0 aa | Cytoplasmic | — |
| Isoform | P12931-3 | P12931-3 | 100.0% | — | 0 | 0 aa | 553 aa | 0 aa | Cytoplasmic | — |
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

**Secreted form**

- present: false
- severity: Low
- evidence: Weak

**ECD size assessment**

- ECD class: None
- rationale: SRC has no canonical extracellular domain — it is an inner-leaflet lipid-anchored kinase with all domains (SH3, SH2, kinase) facing the cytoplasm. The eSrc surface form arises by topological inversion via ALE, exposing domains that are structurally cytoplasmic in origin, not a conventional ECD.

**Epitope masking**

- severity: Moderate
- evidence: Weak
- mechanism: Conformational
- rationale: The eSrc surface form is generated by topological inversion of a normally cytoplasmic kinase; the exposed surface is an inverted cytoplasmic face whose epitope accessibility is not well characterized. Conformational masking by the membrane lipid bilayer or by lipid-anchored microdomain packing is plausible but undocumented. No specific epitope-masking evidence in the ledger.

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P12931-F1](https://alphafold.ebi.ac.uk/entry/P12931) |
| AFDB version | v6 |
| ECD mean pLDDT | 83.4 |
| ECD disordered fraction | 19.4% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P12931) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

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

26 entries · 13 primary · 13 secondary · 0 tertiary · 16 PMC OA.

- `a1_evi_01` · *Secondary* — A 2025 study (PMID:41818370) reports that intracellular N-myristoylated Src undergoes topological inversion onto the cell surface in cancer cells via autophagolysosomal exocytosis (ALE), resulting in extracellular membrane-associated Src (eSrc). This constitutes a non-canonical surface topology where the canonical inner-leaflet-anchored kinase is inverted, placing previously cytoplasmic domains accessible from the extracellular space. The topology claim is that N-myristoylated Src can be topologically inverted — contradicting the canonical expectation that N-myristoylated proteins are exclusively inner-leaflet anchored. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a1_evi_02` · *Secondary* — Src is noncanonically translocated and inverted onto the cell surface in cancer, both in vitro and in vivo. This is the core surface-expression finding of PMID:41818370 — a direct experimental observation establishing that Src (canonical inner-leaflet kinase) can achieve extracellular surface presence (eSrc) in cancer cells. Evidence derived from multiple experimental approaches in cancer cell lines and in vivo tumor models. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a1_evi_03` · *Secondary* — Extracellular membrane-associated Src (eSrc) was found in primary tumors. Anti-Src antibody-based therapies mediated tumor cell killing in cell culture systems and in mouse xenograft models. This constitutes therapeutic engagement evidence: antibody programs targeting the extracellular face of surface-inverted Src (eSrc) in cancer, demonstrating preclinical proof-of-concept for Src as an antibody-accessible surface target in oncology. The target form is the topologically inverted, membrane-associated eSrc. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a1_evi_04` · *Secondary* — Autophagolysosomal exocytosis (ALE) is identified as the secretory mechanism by which Src is delivered to the outer cell surface in cancer cell lines. This is the mechanistic basis for eSrc surface presentation — not canonical secretory pathway trafficking. The ALE mechanism is prominent in cancer cell lines, suggesting cancer-specific or cancer-enriched surface exposure. Relevant to shed/secreted form risk: ALE-delivered Src may also be released as a soluble extracellular form. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a1_evi_05` · *Secondary* — A companion publication (PMID:41818382) independently corroborates that exocytosis exposes Src at the outer surface of cancer cells, positioning eSrc for therapeutic targeting. This is a second-source confirmation of the surface-inverted Src concept and the antibody-therapeutic engagement angle, reinforcing the PMID:41818370 findings. (https://pubmed.ncbi.nlm.nih.gov/41818382/)
- `a1_evi_06` · *Secondary* — Src represents the prototypical example of a family of membrane-anchored (N-myristoylated) intracellular proteins that can be transported to the outer cell surface by ALE. This framing establishes that Src's N-myristoylation, normally responsible for inner-leaflet anchoring, does not preclude surface inversion in the cancer context — the protein reaches the outer leaflet via a non-canonical route. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a1_evi_07` · *Primary* — SRC kinase was identified in surfaceome cluster 2 in a mass spectrometry-based cell-surface capture (CSC) profiling study of chondrocytes, using sialoglycoprotein enrichment via aminooxy-biotin conjugation with LC-MS/MS. This constitutes a direct surfaceome MS detection of SRC in a primary chondrocyte context. The enrichment is glycoprotein-selective (N-glycan-dependent CSC), and SRC is not canonically glycosylated, raising the question of whether this detection reflects direct SRC surface presence or co-purification with a binding partner; nonetheless it is a reported surfaceome hit. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
- `a1_evi_08` · *Primary* — Surface-capture methodology for the chondrocyte surfaceome study (PMC12777226): sialoglycoprotein enrichment via aminooxy-biotin conjugation (cell-surface-capture chemistry targeting periodate-oxidized sialic acids on intact live cells) followed by high-resolution LC-MS/MS. This is a non-permeabilizing surface capture approach; only extracellular N-glycosylated/sialylated epitopes are accessible. Three biological replicates at multiple time points. This methodology detail is required to pair with the SRC surfaceome hit. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
- `a1_evi_09` · *Primary* — SRC was detected in secreted extracellular vesicles (sEVs) released by high-invadopodia-activity cancer cell lines, based on proteomic profiling of sEV fractions. SRC appears in a cluster of invadopodia-regulatory proteins (with CTTN, CFL1, ITGA3, ITGB3). This constitutes a shed/secreted-form observation: SRC can be released in sEVs from cancer cells, representing a pool outside the canonical inner-leaflet PM location. The soluble/vesicular form may confound surface-targeting strategies. ([PMC10356899](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10356899/))
- `a1_evi_10` · *Secondary* — A surfaceome proteomics study (PMC9237123) identified SRC in a functional cluster of non-receptor and receptor signaling kinases (alongside ERBB2, CSF1R, PRKCD) within a larger chemokine-signaling/immune-response cluster. While SRC is cited here in a discussion-level functional annotation context, its inclusion in a surfaceome-derived functional cluster implies co-detection in a surface-proteomics dataset — though this is secondary to the primary surfaceome result. Provides cross-study corroboration of SRC presence in surfaceome-associated datasets. ([PMC9237123](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9237123/))
- `a1_evi_11` · *Secondary* — Antibody reagent detail from PMC9659096: mouse monoclonal anti-SRC antibody clone 60315-1-lg (Proteintech, Rosemont, IL) and rabbit anti-phospho-Y416-SRC antibody clone D49G4 (#6943, Cell Signaling Technology). These antibodies are used in the surface biotinylation + Western blot workflow in this study. Clone and vendor identifiers are provided for downstream MethodObservation.antibodies[] population. ([PMC9659096](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9659096/))
- `a1_evi_12` · *Secondary* — Fluid shear stress increased c-Src activation (Tyr416 phosphorylation) and promoted redistribution of RANKL toward the cell periphery, accompanied by an increase of RANKL in the membrane fraction in osteoblast-like MC3T3-E1 cells. This is not a direct surface-localization assay for Src itself, but documents Src activation correlating with plasma-membrane redistribution of a surface protein (RANKL), assessed by subcellular fractionation. Src activity is measured here as a functional/kinase-activation readout, not a surface localization readout; Src remains intracellular as the activating kinase. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
- `a1_evi_13` · *Secondary* — Co-immunoprecipitation analysis showed interaction between SRC and THY1 (a GPI-anchored plasma membrane surface protein) in HONE1-VA, HONE1-THY1, and NP460 cells using anti-THY1 pulldown. SRC co-precipitates with a bona fide cell-surface protein (THY1/CD90), consistent with SRC associating with the inner leaflet of the PM beneath a surface-exposed GPI-anchored protein. This is indirect evidence of SRC's plasma membrane inner-leaflet localization (not extracellular surface), reflecting canonical SRC-surface-protein signaling interactions. ([PMC10093038](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10093038/))
- `a2_evi_01` · *Primary* — Src is noncanonically translocated and inverted onto the outer cell surface in cancer cells, both in vitro and in vivo, constituting a disease-state-induced surface exposure of a normally cytoplasmic inner-leaflet-anchored kinase. This represents a fundamentally contradictory localization relative to the canonical inner-leaflet anchor model. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a2_evi_02` · *Primary* — Autophagolysosomal exocytosis (ALE) is identified as the secretory mechanism driving extracellular surface exposure of Src in cancer cell lines, representing a lysosomal-exocytosis-based accessibility modulation pathway that inverts Src from the inner leaflet to the outer plasma membrane face. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a2_evi_03` · *Primary* — Extracellular membrane-associated Src (eSrc) is detected in primary tumors in vivo; anti-Src antibody-based therapies mediate tumor cell killing in culture and mouse xenograft models, confirming that cancer-state-induced surface Src is present on the outer face of primary tumor cells and is accessible to antibody-based targeting. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
- `a2_evi_04` · *Primary* — Exocytosis exposes Src at the outer surface of cancer cells, confirming that cancer cells undergo an exocytosis-driven accessibility modulation that places normally cytoplasmic Src on the extracellular face of the plasma membrane, where it is poised for therapeutic targeting. (https://pubmed.ncbi.nlm.nih.gov/41818382/)
- `a2_evi_05` · *Secondary* — SRC-family kinases, including SRC, are tethered via acyl groups (N-myristoylation and palmitoylation) to the inner leaflet of the plasma membrane; all kinase, SH2, and SH3 domains face the cytoplasm with no extracellular exposure under canonical non-cancer conditions. ([PMC11399299](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11399299/))
- `a2_evi_06` · *Primary* — In osteoblast-like MC3T3-E1 cells, fluid shear stress increases c-Src activation (Tyr416 phosphorylation) and promotes redistribution of RANKL toward the cell periphery with increased RANKL in the membrane fraction. This demonstrates that mechanical-stress-induced c-Src activation modulates surface availability of RANKL in osteoblast-lineage cells; c-Src itself localizes to the cell periphery under mechanical stimulation. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
- `a2_evi_07` · *Primary* — Constitutively active c-Src (Y527F mutant) enhances peripheral/membrane localization of RANKL even in the absence of mechanical shear stress in osteoblast-like cells, demonstrating that sustained c-Src activation is sufficient to drive membrane redistribution independent of the triggering stimulus. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
- `a2_evi_08` · *Primary* — SRC functions as a key regulator in the SRC/RAC1/PAK1/PIP5K/EZRIN pathway that governs NIS actin-cytoskeleton anchoring and retention at the plasma membrane in thyroid cells, indicating a functional role for inner-leaflet-anchored SRC in determining PM abundance of other surface proteins; SRC itself remains cytoplasmic-face-anchored in this context. ([PMC9659096](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9659096/))
- `a2_evi_09` · *Primary* — SRC protein expression and phosphorylation (pSRC Y419) are detectable by Western blot in NPC (nasopharyngeal carcinoma) cell lines including THY1-expressing cells and THY1-knockdown HK11.19 cells, confirming SRC protein presence in NPC cancer cell lines with differential cell states determined by THY1 status. ([PMC10093038](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10093038/))
- `a2_evi_10` · *Primary* — SRC protein is enriched in small extracellular vesicles (sEVs) secreted by high-invadopodia-activity glioblastoma (GBM) cell lines, indicating that GBM cells in an invasive/high-invadopodia state mobilize SRC into the extracellular vesicle compartment; SRC appears in the sEV surfaceome of these cancer cells. ([PMC10356899](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10356899/))
- `a2_evi_11` · *Primary* — SRC (proto-oncogene tyrosine-protein kinase Src) is identified as one of four key regulatory proteins in the NIS plasma membrane interaction subnetwork (together with RAC1, ARPC4, and EZRIN), anchoring its functional role at the inner face of the plasma membrane in thyroid biology; this positions SRC as a cytoplasmic-face PM-associated kinase in normal thyroid cells. ([PMC8582450](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8582450/))
- `a2_evi_12` · *Secondary* — SRC is identified alongside ERBB2, CSF1R, and PRKCD in a functional cluster associated with chemokine signaling, chemotaxis, receptor/non-receptor kinase signaling, immune response, and cell adhesion in a cancer context (disease-associated tissue expression); this review-level claim places SRC in a surface-signaling-adjacent functional network across cancer tissue types. ([PMC9237123](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9237123/))
- `a2_evi_13` · *Secondary* — In resting T cells, constitutive tyrosine phosphatase activity (CD45, CD148) suppresses TCR triggering; SRC-family kinases (including LCK/FYN, closely related to SRC) are retained in TCR-contact microdomains while large phosphatases are excluded. This describes SRC-family-kinase accessibility at the inner leaflet of T-cell plasma membranes in resting vs TCR-engaged states — SRC-kinases remain cytoplasmic-face-anchored throughout. ([PMC11399299](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11399299/))

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

*Confidence moderate — Confidence is moderate because the cancer-cell outer-surface SRC story derives from a single recent research cluster — two 2025 publications (PMID:41818370 and PMID:41818382) that appear to originate from the same group. The canonical SRC topology — myristoylated, inner-leaflet-anchored, no extracellular domain — is well-established across decades of independent work from multiple labs and cell contexts, and the triage prior correctly identified this as the baseline. Lifting confidence to high would require an independent group to confirm eSrc surface exposure using orthogonal methodology (e.g., non-permeabilized flow cytometry with validated anti-eSrc antibody + KO control, or cell-surface biotinylation with direct SRC WB confirmation) in a published primary study.*
