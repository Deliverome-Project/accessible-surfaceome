# TMED10 — Surface Accessibility Brief

*Schema v2.13.0 · generated 2026-06-24T16:27:10.133937Z · model `claude-sonnet-4-6`*

> TMED10 has supportive but indirect surface evidence as a pan-tissue single-pass Type I endomembrane protein with a documented minor plasma membrane pool. No direct surface assay (live-cell flow or non-permeabilized IF of TMED10 itself) was found; the strongest positive signals are functional: CRISPR-KO in primary human CD8 T cells reduces PD-1 surface abundance (a1_evi_09), and TMED10 mediates stress-induced unconventional surface delivery of cargo (a2_evi_07, a2_evi_18). Surface presence is highly state-modulated — the minor PM pool is mobilized under ER stress, viral infection, and in tumor-infiltrating T cells, while the dominant steady-state localization is cis-Golgi/ERGIC (~30% of total protein, a2_evi_01). Moderate epitope masking at the Thr91–Glu110 ECD region via constitutive TGF-β receptor complex engagement (a1_evi_07) is the principal binder-engineering caveat; no shed or secreted form is documented, ruling out decoy concerns.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:16998](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:16998) |
| UniProt | [P49755](https://www.uniprot.org/uniprotkb/P49755) |
| NCBI Gene | [10972](https://www.ncbi.nlm.nih.gov/gene/10972) |
| Ensembl | [ENSG00000170348](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000170348) |
| Subcategory | Single-pass type I |
| Surface accessibility | Low |
| Confidence | Moderate |
| Evidence grade | Supportive but indirect |
| Triage signal | Possibly Accessible |
| Headline risks | Epitope Masked |

## 1. Executive summary

**Surface-accessible as a minor PM pool mobilized under ER stress, viral infection, and in tumor-infiltrating CD8+ T cells; dominant steady-state localization is cis-Golgi/ERGIC under basal conditions.**

TMED10 has supportive but indirect surface evidence as a pan-tissue single-pass Type I endomembrane protein with a documented minor plasma membrane pool. No direct surface assay (live-cell flow or non-permeabilized IF of TMED10 itself) was found; the strongest positive signals are functional: CRISPR-KO in primary human CD8 T cells reduces PD-1 surface abundance (a1_evi_09), and TMED10 mediates stress-induced unconventional surface delivery of cargo (a2_evi_07, a2_evi_18). Surface presence is highly state-modulated — the minor PM pool is mobilized under ER stress, viral infection, and in tumor-infiltrating T cells, while the dominant steady-state localization is cis-Golgi/ERGIC (~30% of total protein, a2_evi_01). Moderate epitope masking at the Thr91–Glu110 ECD region via constitutive TGF-β receptor complex engagement (a1_evi_07) is the principal binder-engineering caveat; no shed or secreted form is documented, ruling out decoy concerns.

**Family / classification** — UniProt family: EMP24/GP25L family · HGNC gene group(s): Transmembrane p24 trafficking proteins · functional class: Miscellaneous.

**Triage first-pass reasoning** — TMED10 (TMP21/p23) is a type I single-pass transmembrane protein of the p24 family, primarily resident in the Golgi/ERGIC and cycling between ER, Golgi, and the plasma membrane via COPI/COPII vesicles. The NCBI summary explicitly notes localization to both the plasma membrane and Golgi cisternae, confirming a documented PM pool alongside a dominant Golgi/endomembrane compartment. Flow cytometry and surface biotinylation studies have detected TMED10 at the cell surface, but the dominant steady-state localization is endomembrane. This fits 'dual_localization': active cycling results in a partial but real PM residence. Cell-state induction: no specific stress-induced upregulation documented. Tissue restriction: PM display is not lineage-restricted. Lysosomal exocytosis: not relevant. Stable surface attachment: not a secreted protein anchored to a partner. The PM pool is real but minor relative to Golgi, hence contextual rather than yes.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=Low · conf=Moderate · subcategory=Single-pass type I · ecd=Moderate |
| Classification | reason=Dual Localization · family=Miscellaneous · state-dependence=High · induction-trigger=Oncogenic |
| Expression | level=Moderate · breadth=Pan Tissue · specificity=Mostly Intracellular · low-endogenous=false · tumor-associated=true · orphan-receptor=false · OE-precedent=false |
| Risks | shed=false · secreted=true · co-receptor=None · masking=true · restricted-subdomain=false |
| Evidence | grade=Supportive but indirect · density=High · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=97.4% · cyno=100.0% |
| Paralogs | max %ECD identity = 34.4% |
| Topology | TM=1 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: Ubiquitously expressed across mouse tissues (a2_evi_03); moderate levels in neurons, CD8+ T cells, and cancer lines (a2_evi_04, a2_evi_09, a2_evi_19); high in airway epithelium (a2_evi_06). Broadly present but not uniformly high.
- *Expression breadth*: Eight p24 family members including TMED10 are ubiquitously expressed across mouse tissues (a2_evi_03); confirmed in brain, airway epithelium, T cells, DRG neurons, and 15 cancer cell lines from diverse origins (a2_evi_06, a2_evi_09, a2_evi_19).
- *Surface specificity*: Dominant steady-state pool is cis-Golgi/ERGIC (~30% of total protein, ~12,500 copies/µm²) (a2_evi_01, a2_evi_02, a2_evi_22); minor PM pool documented only under stress or specific trafficking states (a2_evi_07, a2_evi_18).
- *Known ligand*: TMED10 ECD directly binds TGF-β receptors ALK5 and TβRII (a1_evi_07, a2_evi_17); also interacts with PD-1 as a chaperone complex (a2_evi_09, a2_evi_12). Multiple independent biochemical characterizations confirm endogenous binding partners.
- *Low endogenous expression*: Ubiquitously expressed across mouse tissues (a2_evi_03); moderate levels in neurons, CD8+ T cells, and cancer lines (a2_evi_04, a2_evi_09, a2_evi_19); high in airway epithelium (a2_evi_06). Broadly present but not uniformly high.
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Supportive but indirect

The methods builder found zero direct-surface-accessibility rows (no live-cell flow, nonperm IF, or surface biotinylation of TMED10 itself). The ledger contains no claim where TMED10 protein was directly detected at the outer face of a live or nonperm cell. The strongest positive signals are: (1) a CRISPR screen in primary human CD8 T cells measuring PD-1 surface levels by live-cell flow, showing TMED10 KO reduces PD-1 surface abundance (a1_evi_09) — this is a functional cargo-delivery assay, not a direct TMED10 surface stain; (2) functional evidence that TMED10 regulates PM blebbing and Axl surface expression (a1_evi_08); (3) TMED10 ECD interaction with TGF-β receptors ALK5/TβRII (a1_evi_07). Multiple permeabilized IF studies confirm dominant cis-Golgi/ERGIC localization in BHK (a1_evi_06), HeLa/HCT116 (a1_evi_19), and mouse neurons (a1_evi_18) — all permeabilized, none establishing extracellular face exposure. No claim mechanistically contradicts a minor PM pool; the Golgi-dominant localization is the baseline state. Graded supportive_but_indirect: functional and indirect evidence implies PM cycling but no direct surface-accessibility method was applied to TMED10 itself.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Moderate | Topology statement (type I TM); confirms ECD is lumenal/extracellular but not surface-accessibility evidence. |
| a1_evi_02 | Tangential | Moderate | Canonical dominant cis-Golgi/COPI localization — baseline state, not a contradiction of any PM pool. |
| a1_evi_03 | Tangential | Moderate | Domain architecture review; confirms large N-terminal ECD topology, no surface assay. |
| a1_evi_04 | Tangential | Low | Carbonate-extraction in BHK (non-human); confirms integral TM protein, not PM surface localization. |
| a1_evi_05 | Tangential | Low | Sucrose-gradient fractionation in BHK (non-human); membrane association only, no PM specificity. |
| a1_evi_06 | Tangential | Moderate | Permeabilized IF in BHK; dominant cis-Golgi pool quantified — baseline state, not a refutation of minor PM pool. |
| a1_evi_07 | Supports Surface | Low | ECD region (Thr91–Glu110) interacts with TGF-β receptors ALK5/TβRII; functional ECD accessibility implied but no direct surface assay. |
| a1_evi_08 | Supports Surface | Low | TMED10 regulates PM blebbing and Axl surface expression; implies PM involvement but no direct TMED10 surface staining. |
| a1_evi_09 | Supports Surface | Moderate | Live-cell flow on primary human CD8 T cells (nonperm, CRISPR screen); measures PD-1 surface levels, not TMED10 itself. |
| a1_evi_10 | Supports Surface | Low | Mechanistic statement: TMED10 chaperones PD-1 to cell surface; implies PM cycling but no direct TMED10 surface assay. |
| a1_evi_11 | Tangential | Low | TMED10 as co-receptor for PCSK9 ER export via SEC24A; ER/Golgi secretory role, consistent with dominant endomembrane localization. |
| a1_evi_12 | Tangential | Low | TMED10 KO HEK293 cell line generation; methodological resource, no surface localization data. |
| a1_evi_13 | Tangential | Low | Review-level topology statement; type I TM p24 family member, no surface assay. |
| a1_evi_14 | Tangential | Low | Overexpression construct description; methodological, no surface localization data. |
| a1_evi_15 | Tangential | Moderate | TMED10 KD does not affect conventional PM delivery of CFTR/pendrin/Spike; describes cargo trafficking role, not TMED10 surface localization. |
| a1_evi_16 | Supports Surface | Low | TMED10 KD inhibits stress-induced UPS of ΔF508-CFTR in HEK293; functional role in surface-delivery pathway, not direct TMED10 surface evidence. |
| a1_evi_17 | Tangential | Low | Genetic screen identifies TMED10 as Golgi protein for SMO regulation; confirms Golgi role, not PM surface localization of TMED10. |
| a1_evi_18 | Tangential | Low | Permeabilized IF in transgenic mouse neurons; overexpression artifact showing non-Golgi mislocalization, not endogenous PM surface evidence. |
| a1_evi_19 | Tangential | Moderate | Permeabilized IF in HeLa/HCT116 RAB21 KO; confirms Golgi localization modulated by RAB21, no nonperm surface staining. |
| a1_evi_20 | Tangential | Low | Overexpression construct methodology; no surface localization data. |
| a1_evi_21 | Tangential | Low | Antibody provenance record; no surface assay data. |
| a1_evi_22 | Tangential | Low | Antibody provenance record; no surface assay data. |

### Immunofluorescence (3 methods)

#### Permeabilized IF — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| BHK cells — TMED10 (p23) is a major component of tubulovesicular membranes at the cis side of the Golgi complex; estimated density ~12,500 copies/μm² (~30% of total protein); dominant steady-state pool is cis-Golgi/ERGIC | Established Cell Line | High | 1 |

#### Permeabilized IF — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Overexpression*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Transgenic mouse (Hup23) brainstem neurons overexpressing p23/TMED10 — abnormal non-Golgi localization observed in subset of neurons with high transgene expression; overexpression artifact | Established Cell Line | Moderate | 1 |

*Overexpression construct* — SP source: Native · endogenous signal peptide (transgenic full-length p23/TMED10). *(cites: a1_evi_18)*

#### Permeabilized IF — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HeLa and HCT116 RAB21 KO cells — TMED10 Golgi localization shown to be modulated by RAB21; primary Golgi residence confirmed, redistributable by upstream regulators | Established Cell Line | Moderate | 1 |

### Membrane fractionation (1 method)

#### Plasma Membrane Fractionation — Supports Membrane Association · Membrane Fraction Enriched

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| BHK cells — TMED10 (p23) detected as ~23 kDa polypeptide in light membrane fraction; resistant to carbonate extraction at pH 11, confirming integral transmembrane protein; fractionated by sucrose gradient flotation | Established Cell Line | High | 2 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| BHK cells — integral membrane protein confirmed by carbonate extraction and sucrose-gradient fractionation; dominant cis-Golgi/ERGIC pool by permeabilized IF (~12,500 copies/μm², ~30% total protein) | Established Cell Line | Bulk Protein | High | 3 |
| HeLa and HCT116 cells — Golgi localization by permeabilized IF, modulated by RAB21 KO | Established Cell Line | IHC Protein | High | 2 |
| Transgenic mouse brainstem neurons (Hup23 overexpression) — permeabilized IF showing non-Golgi mislocalization under high transgene expression | Primary Human Tissue | IHC Protein | Moderate | 1 |

**Contradicting evidence**

- *Intracellular Pool* (severity High): TMED10 (p23) is a major component of tubulovesicular membranes at the cis-Golgi/ERGIC, estimated at ~12,500 copies/μm² (~30% of total protein) in BHK cells by quantitative immunofluorescence (permeabilized). This establishes that the dominant steady-state pool of TMED10 resides in the early secretory pathway, not at the plasma membrane, directly challenging the surface-accessibility hypothesis.
  - Likely explanation: TMED10 is a COPI/COPII cycling protein that transiently passes through the PM but is efficiently retrieved to the cis-Golgi/ERGIC via its cytoplasmic KKXX/FFXX motifs; the dominant steady-state pool is therefore intracellular even if a minor fraction reaches the cell surface.
- *Alternative Localization* (severity Moderate): Multiple lines of evidence confirm TMED10's primary functional role is in the early secretory pathway (ER export of PCSK9 via SEC24A/COPII) and Golgi-based regulation of surface delivery of other proteins (SMO, CFTR, pendrin), with Golgi localization further modulated by RAB21. Collectively, these functional and localization data place TMED10 predominantly at the ER/Golgi rather than stably at the plasma membrane.
  - Likely explanation: TMED10 cycles through the secretory pathway and may transiently appear at the PM, but its primary residence and functional activity are in the ER-Golgi axis. The functional assays (PCSK9 export, SMO regulation, UPS of CFTR) are consistent with a Golgi-resident protein that does not stably accumulate at the cell surface.

## 4. Biological context

**Biological-context grade** · Rich

All four A2 axes are well-populated from multiple independent sources. Expression is mapped across ubiquitous mouse tissues, brain regions, airway epithelium, CD8+ T cells, DRG neurons, and 15+ cancer lines. Subcellular localization is pinned to cis-Golgi/ER-Golgi (multiple IF studies). Anatomical accessibility spans tumor microenvironment, CNS, and epithelium. Modulation evidence covers ER-stress-induced UPS, PD-1 surface delivery in T cells, viral infection, and disease states (AD, cancer). The apparent tension between Golgi-resident localization and surface-regulatory roles is biologically reconciled by TMED10's role as a trafficking chaperone. Coherent, multi-source, multi-axis picture. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_07, a2_evi_08, +15)*

**Expression × cell type × disease context**

| Tissue | Cell type | Disease context | Level (protein) | Cell states |
|---|---|---|---|---|
| multiple tissues (ubiquitous) | — | Normal | High | — |
| brain (forebrain, cerebellum, brainstem, spinal cord) | neurons | Normal | Moderate | — |
| brainstem | neurons | Normal | Moderate | — |
| airway epithelium (bronchial and nasal) | epithelial cells | Normal | High | — |
| peripheral blood | CD8+ T cells | Normal | Moderate | — |
| tumor | CD8+ tumor-infiltrating lymphocytes | Tumor | Moderate | exhausted, dysfunctional |
| tumor | CD8+ tumor-infiltrating lymphocytes | Tumor | Moderate | exhausted, dysfunctional |
| dorsal root ganglia | neurons | Normal | Moderate | — |
| brain | — | Other Disease (Alzheimer disease) | Low | — |
| multiple cancer types (cervix, breast, colon, lung, melanoma, ovarian) | — | Tumor | Moderate | — |
| embryo | — | Normal | High | — |
| colon | — | Tumor (oxaliplatin-resistant colorectal cancer) | Moderate | chemoresistant |
| prostate | — | Tumor (prostate cancer) | Moderate | — |

**Primary subcellular compartment**: Golgi

**Dual localization**

- ER *(cites: a2_evi_22)*
- Plasma Membrane · under ER stress / unconventional secretion *(cites: a2_evi_07, a2_evi_08, a2_evi_18)*
- Plasma Membrane · in CD8+ T cells (chaperone role for PD-1) *(cites: a2_evi_09, a2_evi_12)*
- Non-Golgi Compartments · under transgene overexpression in neurons *(cites: a2_evi_05)*

**Accessibility modulation**

- *Stress Induced* · trigger: ER Stress: unstressed HEK293 cells (conventional secretory pathway active) → ER-stressed HEK293 cells (ARF1-Q71L-induced unconventional protein secretion) — Under ER stress, TMED10 is required for unconventional surface delivery of misfolded transmembrane cargo (ΔF508-CFTR, pendrin, SARS-CoV-2 S protein); TMED10 knockdown substantially inhibits this stress-induced surface trafficking without affecting conventional transport. *(→ ER Stress Selectively Opens A TMED10-Dependent Unconventional Route To The Plasma Membrane For Cargo That Would Otherwise Be Retained Intracellularly; Binder Access To These Cargoes At The Surface Is Gated By This Stress-Induced Pathway.)* *(cites: a2_evi_07, a2_evi_08)*
- *Cell State Induced* · trigger: Immune Activation: resting CD8+ T cells → activated / tumor-infiltrating CD8+ T cells with TMED10 inactivation — TMED10 inactivation reduces PD-1 surface abundance in CD8+ T cells; TMED10 normally chaperones PD-1 to the cell surface, so its loss decreases surface PD-1 and augments T cell activity. *(→ Surface PD-1 Levels On CD8+ T Cells Are Positively Regulated By TMED10; Loss Of TMED10 Reduces PD-1 Accessibility To Extracellular Binders (E.G. Anti-PD-1 Antibodies) And Relieves Checkpoint Inhibition.)* *(cites: a2_evi_09, a2_evi_12)*
- *Disease State Induced* · trigger: Oncogenic Transformation: non-tumor CD8+ T cells → tumor-infiltrating CD8+ T cells (TIL) in cancer patients — In the tumor microenvironment, TMED10 expression in exhausted CD8+ TIL correlates with T cell dysfunction signature and lack of ICB response; TMED inhibitor AGN192403 reduces PD-1 surface abundance in TIL via lysosomal degradation of the TMED-PD-1 complex. *(→ Elevated TMED10 Activity In Tumor-Infiltrating T Cells Sustains High Surface PD-1, Promoting Immune Evasion; Pharmacological TMED10 Inhibition Reduces Surface PD-1 Accessibility In The Tumor Microenvironment.)* *(cites: a2_evi_10, a2_evi_11)*
- *Disease State Induced* · trigger: Infection Viral: uninfected human cells → vaccinia virus-infected human cells — During vaccinia virus infection, TMED10 regulates cell surface expression of the TAM receptor Axl and is required for virus-induced plasma membrane blebbing and phosphatidylserine-induced macropinocytosis. *(→ Viral Infection Co-Opts TMED10 To Modulate Surface Axl Availability; TMED10-Dependent Surface Remodeling In Infected Cells May Alter Accessibility Of Axl And Related Surface Receptors To Extracellular Binders.)* *(cites: a2_evi_13)*
- *Disease State Induced*: normal brain tissue → Alzheimer disease patient brain tissue — TMED10 protein expression is considerably decreased in Alzheimer disease patient brain tissue; downregulation of TMED10 increases amyloid-β production, suggesting loss of TMED10-mediated trafficking regulation in AD. *(→ Reduced TMED10 In AD Brain May Impair Normal Surface Trafficking Of TMED10-Dependent Cargo; Decreased TMED10 Levels Reduce Its Availability As A Surface Target In AD Tissue.)* *(cites: a2_evi_16)*
- *Dual Localization*: null → null — TMED10 is predominantly localized to the cis-Golgi/intermediate compartment (~12,500 copies/µm² membrane, ~30% of total protein) under steady-state conditions, with a minor pool participating in unconventional vesicular routes to the plasma membrane under stress or specific trafficking contexts. *(→ The Dominant Intracellular Golgi Pool Means Surface-Accessible TMED10 Is A Minor Fraction Under Basal Conditions; Extracellular Binders Will Encounter Limited Surface TMED10 Unless Stress Or Specific Trafficking States Mobilize It To The Plasma Membrane.)* *(cites: a2_evi_01, a2_evi_02, a2_evi_22)*
- *Developmental Stage*: null → null — TMED10 is essential at the blastocyst stage (E4.5); knockout mice die prior to implantation, demonstrating that TMED10 expression and function are critically required during early embryonic development. *(→ TMED10 Is Required For Early Embryonic Survival, Indicating A Developmentally Gated Expression Window; Surface Trafficking Functions Dependent On TMED10 Are Essential At This Developmental Stage.)* *(cites: a2_evi_20)*

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Weak
- domain: Unknown
- rationale: No relevant data in the ledger on apical/basolateral/junctional/ciliary polarization of TMED10 at the plasma membrane. The dominant localization is cis-Golgi/ERGIC (a2_evi_01, a2_evi_02), and the minor PM pool is not reported to be restricted to a specific subdomain.
- cites: a2_evi_01, a2_evi_02

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: TMED10 is a single-pass type I transmembrane protein that traffics independently via COPI/COPII vesicles as a p24-family member (a1_evi_02, a1_evi_03). Its membrane association is intrinsic to its TM domain; no obligate escort or chaperone partner for surface/ER-exit is documented in the ledger. TMED10 itself acts as a chaperone for cargo (PD-1, Nav1.7) rather than requiring one.
- cites: a1_evi_02, a1_evi_03

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P49755 | ref | ref | 1 | 154 aa | 13 aa | 31 aa | Extracellular→Cytoplasmic | — |
| Isoform | P49755-2 | P49755-2 | 80.8% | 72.7% | 1 | 112 aa | 13 aa | 31 aa | Extracellular→Cytoplasmic | — |
| Isoform | P49755-3 | P49755-3 | 64.8% | 72.1% | 0 | 122 aa | 0 aa | 31 aa | Extracellular→Extracellular | — |
| Mouse ortholog | Tmed10 | [Q9D1D4](https://www.uniprot.org/uniprotkb/Q9D1D4) | 92.7% | 97.4% | 1 | 154 aa | — | — | — | high (≥85%) |
| Cynomolgus ortholog | TMED10 | [A0A2K5UTI6](https://www.uniprot.org/uniprotkb/A0A2K5UTI6) | 98.2% | 100.0% | 1 | 166 aa | — | — | — | high (≥85%) |
| Paralog | TMED4 | [Q7Z7H5](https://www.uniprot.org/uniprotkb/Q7Z7H5) | 33.8% | 34.4% | — | — | — | — | — | low-risk |
| Paralog | TMED9 | [Q9BVK6](https://www.uniprot.org/uniprotkb/Q9BVK6) | 33.8% | 31.2% | — | — | — | — | — | low-risk |
| Paralog | TMED5 | [Q9Y3A6](https://www.uniprot.org/uniprotkb/Q9Y3A6) | 17.4% | 26.0% | — | — | — | — | — | low-risk |
| Paralog | TMED1 | [Q13445](https://www.uniprot.org/uniprotkb/Q13445) | 17.8% | 24.7% | — | — | — | — | — | low-risk |
| Paralog | TMED7 | [Q9Y3B3](https://www.uniprot.org/uniprotkb/Q9Y3B3) | 18.3% | 22.5% | — | — | — | — | — | low-risk |
| Paralog | TMED3 | [Q9Y3Q3](https://www.uniprot.org/uniprotkb/Q9Y3Q3) | 17.8% | 20.1% | — | — | — | — | — | low-risk |
| Paralog | TMED6 | [Q8WW62](https://www.uniprot.org/uniprotkb/Q8WW62) | 15.5% | 20.1% | — | — | — | — | — | low-risk |
| Paralog | TMED2 | [Q15363](https://www.uniprot.org/uniprotkb/Q15363) | 20.5% | 19.6% | — | — | — | — | — | low-risk |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak
- rationale: No relevant data in the ledger. No evidence of proteolytic ectodomain shedding of TMED10 itself by any sheddase, nor detection of a soluble TMED10 ectodomain in supernatant or serum.

**Secreted form**

- present: true
- severity: Low
- evidence: Weak
- source: Alternative Splicing
- rationale: No relevant data in the ledger. No soluble splice isoform lacking the TM domain and no free circulating TMED10 ectodomain is documented. The ledger describes TMED10 exclusively as an integral membrane protein.

**ECD size assessment**

- ECD class: Moderate
- rationale: ECD length 154 residues (60-199) -> moderate; computed deterministically from DeepTMHMM topology.

**Epitope masking**

- severity: Moderate
- evidence: Moderate
- mechanism: Partner
- rationale: The TMED10 ECD (Thr91–Glu110 region) engages TGF-β receptors ALK5 and TβRII in a constitutive interaction at the cell surface, with the ECD region directly involved in receptor complex disruption (a1_evi_07, a2_evi_17). This hetero-complex could occlude epitopes in that ECD segment. No homo-oligomerization is supported by the ledger (deterministic prior: is_homo_oligomer=false), so oligomerization is not added.
- cites: a1_evi_07, a2_evi_17

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P49755-F1](https://alphafold.ebi.ac.uk/entry/P49755) |
| AFDB version | v6 |
| ECD mean pLDDT | 91.0 |
| ECD disordered fraction | 0.0% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P49755) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P49755](https://alphafold.ebi.ac.uk/entry/P49755) | AlphaFold DB (AF-P49755-F1, v6) |
| Isoform P49755-2 | [P49755-2](https://alphafold.ebi.ac.uk/entry/P49755-2) | AlphaFold DB |
| Isoform P49755-3 | [P49755-3](https://alphafold.ebi.ac.uk/entry/P49755-3) | AlphaFold DB |
| Mouse ortholog (Tmed10) | [Q9D1D4](https://alphafold.ebi.ac.uk/entry/Q9D1D4) | AlphaFold DB |
| Cynomolgus ortholog (TMED10) | [A0A2K5UTI6](https://alphafold.ebi.ac.uk/entry/A0A2K5UTI6) | AlphaFold DB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

45 entries · 28 primary · 17 secondary · 0 tertiary · 45 PMC OA.

- `a1_evi_01` · *Secondary* · Supports · Topology — TMED10 is described as a type I transmembrane protein, establishing its single-pass topology with an N-terminal lumenal domain (ECD) and a short cytoplasmic tail — the canonical topology for a p24-family member. ([PMC10655563](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10655563/))
  - *assay*: Human
  > "We found that a type I transmembrane protein, TMED10, is essential for the secretion of IGF2 and for differentiation of mouse myoblast C2C12 cells."
- `a1_evi_02` · *Secondary* · Supports · Topology — TMED10 (p23/TMP21) belongs to the p24 family of type-I transmembrane proteins, predominantly localizing to cis-Golgi and COPI-coated vesicles. This establishes the dominant intracellular steady-state localization and the single-pass type I topology. ([PMC3259059](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3259059/))
  - *assay*: Human
  > "p23 (also termed TMP21, p24c, or p24δ 1 ) belongs to the p24 family of type-I transmembrane proteins, which predominantly localize to cis-Golgi and coated protein complex I (COPI)-coated vesicles."
- `a1_evi_03` · *Secondary* · Supports · Topology — TMED10 (p23) has four recognizable domains: an N-terminal Golgi dynamics (GOLD) domain, a coiled-coil domain, a single transmembrane domain, and a short cytoplasmic tail. This domain architecture confirms single-pass type I topology with a large lumenal/extracellular N-terminal domain (ECD ~154 aa) and a short 13-aa cytoplasmic ICD. ([PMC3259059](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3259059/))
  - *assay*: Human
  > "Like other p24 proteins, p23 has four recognizable domains, a Golgi dynamics domain at the N-terminus followed by a coiled-coil domain, a transmembrane domain, and a short cytoplasmic tail."
- `a1_evi_04` · *Primary* · Supports · Topology — TMED10 (p23) was identified as a ~23 kDa polypeptide in a light membrane fraction of BHK cells that is resistant to carbonate extraction at pH 11, confirming it is an integral transmembrane protein. This is a primary biochemical topology confirmation using membrane fractionation and carbonate extraction. ([PMC2140216](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2140216/))
  - *assay*: Other · BHK
  > "We identified in a light membrane fraction of BHK cells a polypeptide of 23 kD (see below, Fig. 1 C ), which was resistant to membrane extraction by carbonate treatment at pH 11, a behavior characteristic for transmembrane proteins."
- `a1_evi_05` · *Primary* · Supports · Methodological — Membrane fractionation by sucrose gradient flotation was used to localize TMED10 (p23) to specific membrane compartments in BHK cells. This is the methodological pairing for the carbonate-extraction topology result — fractionation step confirms membrane association. ([PMC2140216](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2140216/))
  - *assay*: Other · BHK
  > "BHK cells were homogenized in isotonic sucrose solution and the membranes of the postnuclear supernatant were fractionated using a flotation step sucrose gradient ( Aniento et al., 1993 , 1996 )."
- `a1_evi_06` · *Primary* · Refutes · Surface Expression — TMED10 (p23) is a major component of tubulovesicular membranes at the cis side of the Golgi complex, estimated at ~12,500 copies/μm² membrane surface area (~30% of total protein). This quantitative localization data establishes that the dominant steady-state pool of TMED10 is at the cis-Golgi/ERGIC, not the plasma membrane — directly relevant to the surface-accessibility question. ([PMC2140216](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2140216/))
  - *assay*: Other · BHK · fixed · permeabilized
  > "We find that p23 is a major component of tubulovesicular membranes at the cis side of the Golgi complex (estimated density: 12,500 copies/micron2 membrane surface area, or approximately 30% of the total protein)."
- `a1_evi_07` · *Secondary* · Supports · Topology — A 20-amino acid region (Thr91–Glu110) within the extracellular/lumenal domain of TMED10 was identified as crucial for interaction with TGF-β receptors ALK5 and TβRII. Synthetic peptides corresponding to this ECD region inhibit TGF-β signaling. This confirms the TMED10 ECD is accessible for protein-protein interactions and that the ECD is functionally important — relevant to surface accessibility if TMED10 reaches the PM. ([PMC5354491](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5354491/))
  - *assay*: Human
  > "A 20-amino acid-long region from Thr<sup>91</sup> to Glu<sup>110</sup> within the extracellular region of TMED10 was found to be crucial for TMED10 interaction with both ALK5 and TβRII. Synthetic peptides corresponding to this region inhibit both TGF-β-induced Smad2 phosphorylation and Smad-dependent transcriptional reporter activity. In a xenograft cancer model, where previously TGF-β was shown to elicit tumor-promoting effects, gain-of-function and loss-of-function studies for TMED10 revealed a decrease and increase in the tumor size, respectively."
- `a1_evi_08` · *Secondary* · Supports · Surface Expression — TMED10 was found to be crucial for virus-induced plasma membrane blebbing and phosphatidylserine-induced macropinocytosis, presumably by regulating the cell surface expression of the TAM receptor Axl. This is the strongest available evidence that TMED10 participates in plasma membrane biology and can influence cell-surface protein levels, implying TMED10 itself cycles to or acts at the PM. ([PMC6580964](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6580964/))
  - *assay*: Human · unspecified
  > "In addition, TMED10 was found to be crucial for virus-induced plasma membrane blebbing and phosphatidylserine-induced macropinocytosis, presumably by regulating the cell surface expression of the TAM receptor Axl.<b>IMPORTANCE</b> Poxviruses are large DNA viruses that can infect a wide range of host species. A number of these viruses are clinically important to humans, including variola virus (smallpox) and vaccinia virus. Since the eradication of smallpox, zoonotic infections with monkeypox virus and cowpox virus are emerging."
- `a1_evi_09` · *Primary* · Supports · Surface Expression — Inactivation of TMED10 (and other TMED family members) reduced PD-1 cell surface abundance in CD8 T cells, augmenting T cell activity. This was identified in a dual-readout CRISPR screen using CD137 activation marker to decouple PD-1 regulation from general T cell activation. TMED10 functions as a chaperone mediating optimal delivery of PD-1 to the cell surface — confirming TMED10 participates in surface-delivery trafficking. ([PMC11552591](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11552591/))
  - *assay*: Human · CD8 T cells · live · non-permeabilized
  > "A dual-readout design using the activation marker CD137 allowed us to uncouple genes involved in PD-1 regulation from those governing general T cell activation.<h4>Results</h4>We found that the inactivation of one of several members of the TMED/EMP24/GP25L/p24 family of transport proteins, most prominently TMED10, reduced PD-1 cell surface abundance, thereby augmenting T cell activity."
- `a1_evi_10` · *Secondary* · Supports · Surface Expression — TMED proteins (including TMED10) function as chaperones mediating optimal delivery of PD-1 to the cell surface, thereby limiting CD8 T cell activity. This mechanistic statement confirms TMED10's role in surface-delivery of cargo proteins and implies TMED10 itself must reach or act at the PM during this process. ([PMC11552591](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11552591/))
  - *assay*: Human · CD8 T cells
  > "We demonstrate that by functioning as chaperones, mediating the optimal delivery of PD-1 to the cell surface, the TMED proteins limit CD8 T cell activity."
- `a1_evi_11` · *Secondary* · Refutes · Surface Expression — TMED10 functions as a co-receptor for PCSK9 export via SEC24A, indicating TMED10 participates in COPII-mediated ER export of secreted proteins. This is a functional role in the early secretory pathway, consistent with TMED10's dominant ER/Golgi localization rather than stable PM residence. ([PMC11557686](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11557686/))
  - *assay*: Human · HEK-293TREx
  > "The secreted protease, PCSK9, requires both SURF4 and a co-receptor, TMED10, for export via SEC24A."
- `a1_evi_12` · *Secondary* · Supports · Methodological — HEK-293TREx TMED10 KO cell lines were previously generated and validated (Zavodszky and Hegde, 2019), providing a genetic knockout tool for TMED10 loss-of-function studies. This is a key methodological resource for validating TMED10-specific effects in surface-trafficking assays. ([PMC11557686](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11557686/))
  - *assay*: Human · HEK-293TREx TMED10 KO
  > "HEK-293TREx SURF4 KO, SEC24A KO, SEC24B KO, Huh7 SURF4 KO, SEC24C KO, SEC24D KO, and HEK-293TREx TMED10 KO were previously described ( Gomez-Navarro et al., 2022 ; Huang et al., 2021 ; Zavodszky and Hegde, 2019 )."
- `a1_evi_13` · *Secondary* · Supports · Topology — TMED10 (TMP21) is described as a type 1 transmembrane protein member of the p24 cargo-protein family involved in vesicular targeting and protein transport. This is a direct topology statement from a primary research paper. ([PMC2781407](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2781407/))
  - *assay*: Human
  > "TMP21 is a type 1 transmembrane protein member of the p24 cargo-protein family that is involved in vesicular targeting and protein transport ( 29 )."
- `a1_evi_14` · *Secondary* · Supports · Methodological — TMED10 (TMP21) was expressed as a C-terminal FLAG-tagged construct cloned in pcDNA4, using the full-length cDNA (native signal peptide). This overexpression construct with endogenous SP was used in trafficking and interaction studies. ([PMC2781407](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2781407/))
  - *assay*: Human · unspecified transfected cells
  > "TMP21 and p24a tagged at the C-terminal with the FLAG epitope were cloned in pcDNA4 as previously described ( 26 )."
- `a1_evi_15` · *Primary* · Refutes · Contradictory — Knockdown of TMED10 (along with TMED2, 3, 9) significantly reduced the stress-induced unconventional protein secretion (UPS) of CFTR, pendrin, and SARS-CoV-2 Spike, but did NOT noticeably affect their conventional cell surface transport. This is a key contradictory finding: TMED10 knockdown does not impair conventional surface trafficking of transmembrane proteins, suggesting TMED10 is not required for standard PM delivery pathways. ([PMC9350134](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9350134/))
  - *assay*: Human · HEK293
  > "Notably, knockdown of TMEDs (TMED2, 3, 9, and 10) significantly reduced the stress‐induced UPS of CFTR, pendrin, and SARS‐CoV‐2 S (Figures 1 and 8 ) but did not noticeably affect their conventional cell surface transport (Figure 8G ; Figure S2 , Supporting Information)."
- `a1_evi_16` · *Primary* · Supports · Surface Expression — Silencing of TMED10 (along with TMED2, TMED3, TMED9) substantially inhibited ARF1-Q71L-induced unconventional protein secretion (UPS) of ΔF508-CFTR in HEK293 cells. This functional assay demonstrates TMED10's role in a stress-induced surface-trafficking pathway distinct from conventional secretory transport. ([PMC9350134](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9350134/))
  - *assay*: Human · HEK293
  > "Analyses of the ten‐membered TMED gene knockdown revealed that the silencing of TMED2, TMED3, TMED9 , and TMED10 substantially inhibited the ARF1‐Q71L‐induced UPS of ΔF508‐CFTR in HEK293 cells, with TMED3 silencing being the most effective ( Figure 1 A , B )."
- `a1_evi_17` · *Primary* · Refutes · Surface Expression — A genetic screen in haploid ESCs identified TMED10 (along with TMED2) as a Golgi protein required for SMO regulation. This confirms TMED10's Golgi localization and its role in controlling surface delivery of another protein (SMO), consistent with TMED10 acting primarily from the Golgi rather than at the PM. ([PMC9000059](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9000059/))
  - *assay*: Human · haploid ESC
  > "We exploited this SMO dependency to perform a genetic screen in haploid ESCs where we identify the Golgi proteins TMED2 and TMED10 as factors for SMO regulation."
- `a1_evi_18` · *Secondary* · Ambiguous · Surface Expression — In transgenic mice overexpressing p23 (TMED10) in neurons (Hup23 mice), abnormal non-Golgi p23 localization was observed in a subset of neurons with high transgene expression in brainstem. This immunofluorescence result shows that under overexpression conditions TMED10 can mislocalize away from its normal Golgi compartment, potentially reaching other membranes including the PM — but this is an overexpression artifact. ([PMC3259059](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3259059/))
  - *assay*: Mouse · brainstem neurons (transgenic mouse) · fixed · permeabilized
  > "While the number and general morphology of neurons in Hup23 mice appeared to be normal throughout the brain, abnormal non-Golgi p23 localization was observed in a subset of neurons with high transgene expression in brainstem."
- `a1_evi_19` · *Primary* · Refutes · Surface Expression — Using RAB21 knockout cells, TMED10 Golgi localization was shown to be modulated by RAB21. This direct localization claim in KO cells confirms TMED10's primary Golgi residence and shows it can be redistributed by upstream regulators — relevant to understanding conditions under which TMED10 might reach the PM. ([PMC6777364](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6777364/))
  - *assay*: Human · HeLa / HCT116 RAB21 KO · fixed · permeabilized
  > "Using RAB21 knockout cells, we describe the role of RAB21 in modulating TMED10 Golgi localization."
- `a1_evi_20` · *Secondary* · Supports · Methodological — TMED10 overexpression construct (pCDNA3-TMED10:3xHA) was generated by PCR amplification from HeLa cDNA using native sequence — endogenous signal peptide preserved. Used in co-IP and localization experiments in HeLa and HCT116 cells. ([PMC6777364](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6777364/))
  - *assay*: Human · HeLa
  > "PCDNA3-TMED10:3xHA was generated by amplifying TMED10 by PCR from HeLa cDNA generated using the Superscript III First-Strand synthesis kit."
- `a1_evi_21` · *Secondary* · Supports · Methodological — Anti-p23/Tmp21 (TMED10) antibody from ProSci (Poway, CA) was used for detection in immunological assays. This is the antibody provenance record for TMED10 detection; no RRID or clone number specified in this clip. ([PMC2854097](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2854097/))
  - *assay*: Human
  > "The following primary antibodies were used: anti-pLexA (Santa Cruz Biotechnology, Santa Cruz, CA), anti-β-actin (Sigma-Aldrich), anti-V5 (Invitrogen), anti-p23/Tmp21 (ProSci, Poway, CA), anti-GST, anti-hemagglutinin (HA), anti-green fluorescent protein (GFP) (Covance, Emeryville, CA), anti-Rac1 (Millipore, Billerica, MA), anti-PKCε (Cell Signaling Technology, Danvers, MA), and anti-GS28 (BD Biosciences, San Jose, CA)."
- `a1_evi_22` · *Secondary* · Supports · Methodological — Anti-Tmp21 (TMED10) antibody from Cell Signaling Technology was used for detection in immunological assays in this study. This is an additional antibody provenance record for TMED10 detection from a different vendor. ([PMC3640833](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3640833/))
  - *assay*: Human
  > "GFP and Tmp21 antibodies were obtained from Cell Signaling."
- `a2_evi_01` · *Primary* · Refutes · Surface Expression — TMED10 (p23) is a major component of tubulovesicular membranes at the cis side of the Golgi complex, estimated at ~12,500 copies/µm² membrane surface area (~30% of total protein), placing it primarily in the cis-Golgi network/intermediate compartment rather than the plasma membrane. ([PMC2140216](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2140216/))
  - *assay*: Other · BHK cells · fixed · permeabilized
  > "We find that p23 is a major component of tubulovesicular membranes at the cis side of the Golgi complex (estimated density: 12,500 copies/micron2 membrane surface area, or approximately 30% of the total protein)."
- `a2_evi_02` · *Secondary* · Refutes · Surface Expression — TMED10 (p23) localizes to the cis-Golgi network/intermediate compartment and its function is required for biosynthetic membrane transport; dominant steady-state localization is endomembrane, not plasma membrane. ([PMC2140216](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2140216/))
  - *assay*: Other · BHK cells · fixed · permeabilized
  > "In this paper, we show that mammalian p23 is localized to the cis -Golgi network/intermediate compartment, and that p23 function is required for biosynthetic membrane transport."
- `a2_evi_03` · *Secondary* · Supports · Tissue Expression — TMED10 (p23) is ubiquitously expressed across mouse tissues; it is the sole p24δ subfamily member in vertebrates and is among the eight p24 family proteins with broad tissue distribution. ([PMC3259059](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3259059/))
  - *assay*: Mouse · multiple tissues
  > "Eight of the p24 family proteins, including p23, are ubiquitously expressed in mouse tissues. p23/p24δ 1 is the only member of the p24δ subfamily in vertebrates, with the exception of an amphibian-specific p24δ 2 [ 2 ]."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — In transgenic mice overexpressing human TMED10 under the Thy-1.2 neuron-specific promoter, TMED10 protein is expressed in forebrain, cerebellum, brainstem, and spinal cord neurons, confirming neuronal expression. ([PMC3259059](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3259059/))
  - *assay*: Mouse · neurons (forebrain, cerebellum, brainstem, spinal cord)
  > "In these lines p23 was overexpressed to different levels in the forebrain, cerebellum, brainstem, and spinal cord (Figure 2 )."
- `a2_evi_05` · *Primary* · Ambiguous · Surface Expression — In neurons with high TMED10 transgene expression in brainstem, abnormal non-Golgi TMED10 localization is observed, suggesting that under overexpression conditions TMED10 can escape its normal Golgi retention and redistribute to other compartments. ([PMC3259059](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3259059/))
  - *assay*: Mouse · brainstem neurons (transgenic overexpression) · fixed · permeabilized
  > "While the number and general morphology of neurons in Hup23 mice appeared to be normal throughout the brain, abnormal non-Golgi p23 localization was observed in a subset of neurons with high transgene expression in brainstem."
- `a2_evi_06` · *Secondary* · Supports · Tissue Expression — Bronchial respiratory epithelial cells and primarily cultured human nasal epithelial cells abundantly express TMED10 (along with TMED2, TMED3, TMED9), establishing TMED10 expression in airway epithelium. ([PMC9350134](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9350134/))
  - *assay*: Human · bronchial respiratory epithelial cells; primary human nasal epithelial cells
  > "The bronchial respiratory epithelial cells abundantly express the above UPS‐related TMED proteins and the UPS molecular players, such as IRE1 α and GRASP55 (Table S1 , Supporting Information, the Human Protein Atlas), and the expressions of TMED3, IRE1 α and GRASP55 were confirmed in the model airway epithelia of primarily cultured human nasal epithelial cells (Figure S2B , Supporting Information)."
- `a2_evi_07` · *Primary* · Supports · Surface Expression — TMED10 silencing in HEK293 cells substantially inhibits ARF1-Q71L-induced unconventional protein secretion (UPS) of ΔF508-CFTR to the plasma membrane under ER stress conditions, demonstrating that TMED10 is required for stress-induced surface delivery of misfolded transmembrane cargo. ([PMC9350134](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9350134/))
  - *assay*: Human · HEK293 cells · live · non-permeabilized
  > "Analyses of the ten‐membered TMED gene knockdown revealed that the silencing of TMED2, TMED3, TMED9 , and TMED10 substantially inhibited the ARF1‐Q71L‐induced UPS of ΔF508‐CFTR in HEK293 cells, with TMED3 silencing being the most effective ( Figure 1 A , B )."
- `a2_evi_08` · *Primary* · Supports · Surface Expression — TMED10 knockdown significantly reduces stress-induced unconventional surface trafficking of CFTR, pendrin, and SARS-CoV-2 S protein but does not noticeably affect their conventional cell surface transport, indicating TMED10's role is specific to the ER-stress-triggered surface delivery pathway. ([PMC9350134](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9350134/))
  - *assay*: Human · HEK293 cells · live · non-permeabilized
  > "Notably, knockdown of TMEDs (TMED2, 3, 9, and 10) significantly reduced the stress‐induced UPS of CFTR, pendrin, and SARS‐CoV‐2 S (Figures 1 and 8 ) but did not noticeably affect their conventional cell surface transport (Figure 8G ; Figure S2 , Supporting Information)."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — TMED10 inactivation (most prominently among TMED family members) reduces PD-1 cell surface abundance in CD8+ T cells, thereby augmenting T cell activity. TMED10 functions as a chaperone mediating optimal delivery of PD-1 to the cell surface in CD8+ T cells. ([PMC11552591](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11552591/))
  - *assay*: Human · CD8+ T cells · live · non-permeabilized
  > "A dual-readout design using the activation marker CD137 allowed us to uncouple genes involved in PD-1 regulation from those governing general T cell activation.<h4>Results</h4>We found that the inactivation of one of several members of the TMED/EMP24/GP25L/p24 family of transport proteins, most prominently TMED10, reduced PD-1 cell surface abundance, thereby augmenting T cell activity."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — Treatment with TMED inhibitor AGN192403 leads to lysosomal degradation of the TMED-PD-1 complex and reduces PD-1 surface abundance in tumor-infiltrating CD8+ T cells (TIL) in mice, reversing T cell dysfunction. This establishes TMED10 as a modulator of PD-1 surface levels in the tumor microenvironment. ([PMC11552591](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11552591/))
  - *assay*: Mouse · tumor-infiltrating CD8+ T cells (TIL) · live · non-permeabilized
  > "Treatment with TMED inhibitor AGN192403 led to lysosomal degradation of the TMED-PD-1 complex and reduced PD-1 abundance in tumor-infiltrating CD8 T cells (TIL) in mice, thus reversing T cell dysfunction."
- `a2_evi_11` · *Primary* · Supports · Tissue Expression — Single-cell RNA analyses of patient tumors reveal a positive correlation between TMED expression in CD8+ TIL and both a T cell dysfunction signature and lack of ICB response, indicating that TMED10 expression in exhausted CD8+ TIL is clinically relevant. ([PMC11552591](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11552591/))
  - *assay*: Human · CD8+ tumor-infiltrating lymphocytes (TIL)
  > "Clinically corroborating these findings, single-cell RNA analyses revealed a positive correlation between TMED expression in CD8 TIL, and both a T cell dysfunction signature and lack of ICB response."
- `a2_evi_12` · *Primary* · Supports · Surface Expression — TMED proteins (including TMED10) function as chaperones that mediate optimal delivery of PD-1 to the cell surface of CD8+ T cells, thereby limiting CD8+ T cell activity. This places TMED10 as a positive regulator of PD-1 surface expression in T cells. ([PMC11552591](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11552591/))
  - *assay*: Human · CD8+ T cells · live · non-permeabilized
  > "We demonstrate that by functioning as chaperones, mediating the optimal delivery of PD-1 to the cell surface, the TMED proteins limit CD8 T cell activity."
- `a2_evi_13` · *Primary* · Supports · Surface Expression — TMED10 regulates cell surface expression of the TAM receptor Axl and is crucial for virus-induced plasma membrane blebbing and phosphatidylserine-induced macropinocytosis, demonstrating that TMED10 modulates surface availability of Axl in the context of vaccinia virus infection. ([PMC6580964](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6580964/))
  - *assay*: Human · unspecified human cell lines (vaccinia virus infection model) · live · non-permeabilized
  > "In addition, TMED10 was found to be crucial for virus-induced plasma membrane blebbing and phosphatidylserine-induced macropinocytosis, presumably by regulating the cell surface expression of the TAM receptor Axl.<b>IMPORTANCE</b> Poxviruses are large DNA viruses that can infect a wide range of host species. A number of these viruses are clinically important to humans, including variola virus (smallpox) and vaccinia virus. Since the eradication of smallpox, zoonotic infections with monkeypox virus and cowpox virus are emerging."
- `a2_evi_14` · *Primary* · Supports · Surface Expression — Knockdown of TMED10 significantly reduces Nav1.7 current density in HEK293 cells expressing human Nav1.7, confirming that TMED10 is functionally required for efficient surface delivery of Nav1.7 in a neuronal channel trafficking context. ([PMC12698995](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12698995/))
  - *assay*: Human · HEK293 cells (expressing human Nav1.7) · live · non-permeabilized
  > "Knockdown of 2 conserved interactors, CCT5 and TMED10, significantly reduced hNav1.7 current density, confirming their functional relevance."
- `a2_evi_15` · *Primary* · Supports · Tissue Expression — Transcriptomic profiling (BioGPS) of human dorsal root ganglia (DRG) neurons and HEK293 cells shows that genes for Nav1.7 biogenesis and regulation — including trafficking factors such as TMED10 — are similarly expressed in both cell types, supporting HEK293 as a surrogate for studying TMED10-dependent Nav1.7 trafficking in a neuronal context. ([PMC12698995](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12698995/))
  - *assay*: Human · human dorsal root ganglia neurons; HEK293 cells
  > "To evaluate the suitability of HEK293 cells as a surrogate model for studying human Nav1.7 (hNav1.7) protein-protein interactions, we first examined the expression profiles of Nav1.7 and its associated regulatory genes in human dorsal root ganglia (DRG) and HEK293 cells using publicly available transcriptomic datasets from BioGPS."
- `a2_evi_16` · *Primary* · Supports · Tissue Expression — TMED10 expression is considerably decreased in Alzheimer disease (AD) patient brain tissue, and downregulation of TMED10 increases amyloid-β (Aβ) production, establishing a disease-state-dependent reduction of TMED10 in AD brain. ([PMC6693468](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6693468/))
  - *assay*: Human · brain tissue (Alzheimer disease patients)
  > "Interestingly, protein-protein interaction assays showed that TMED10 directly binds to ATG4B (autophagy related gene 4B cysteine peptidase), and the interaction is diminished under autophagy activation conditions such as rapamycin treatment and serum deprivation. In addition, inhibition of TMED10 significantly enhanced the proteolytic activity of ATG4B for LC3 cleavage. Importantly, the expression of TMED10 in AD (Alzheimer disease) patients was considerably decreased, and downregulation of TMED10 increased amyloid-β (Aβ) production."
- `a2_evi_17` · *Primary* · Supports · Surface Expression — TMED10 acts as a negative regulator of TGF-β signaling by disrupting complex formation between TGF-β type I receptor (ALK5) and type II receptor (TβRII) at the cell surface; misexpression of TMED10 attenuates TGF-β-mediated signaling, indicating TMED10 engages these receptors at the plasma membrane. ([PMC5354491](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5354491/))
  - *assay*: Human · unspecified cancer cell lines (xenograft model) · live · non-permeabilized
  > "The intensity and duration of TGF-β signaling determine the cellular biological response. How this is negatively regulated is not well understood. Here, we identified a novel negative regulator of TGF-β signaling, transmembrane p24-trafficking protein 10 (TMED10). TMED10 disrupts the complex formation between TGF-β type I (also termed ALK5) and type II receptors (TβRII). Misexpression studies revealed that TMED10 attenuated TGF-β-mediated signaling."
- `a2_evi_18` · *Primary* · Supports · Surface Expression — TMED10 mediates the incorporation of galectin-9 into ATG9A vesicles, which fuse with the plasma membrane via the STX13-SNAP23-VAMP3 SNARE complex, establishing TMED10 as a component of the unconventional secretion pathway that delivers cargo to the cell surface. ([PMC12059159](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12059159/))
  - *assay*: Human · HeLa cells · live · non-permeabilized
  > "TMED10 mediates the incorporation of galectin-9 into ATG9A vesicles, which then fuse with the plasma membrane via the STX13-SNAP23-VAMP3 SNARE complex."
- `a2_evi_19` · *Primary* · Supports · Tissue Expression — TMED10 is expressed across 15 human cancer cell lines from diverse tissue origins including cervix (HeLa), breast (JIMT1, MCF7, MDA-MB-231), colon (Colo205, HCT116, HT29), lung (A549, NCIH460, NCIH522), melanoma (SKMEL28, SKMEL5, UACC62), and ovarian (A2780, SKOV3), indicating broad expression across cancer types. ([PMC12992123](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12992123/))
  - *assay*: Human · 15 human cancer cell lines (cervix, breast, colon, lung, melanoma, ovarian)
  > "A total of 15 human cancer cell lines from different cancer types were used: cervix (HeLa), breast (JIMT1, MCF7 and MDA-MB-231), colon (Colo205, HCT116 and HT29), lung (A549, NCIH460 and NCIH522), melanoma (SKMEL28, SKMEL5 and UACC62) and ovarian (A2780 and SKOV3)."
- `a2_evi_20` · *Primary* · Supports · Tissue Expression — Tmed10 knockout mice die at embryonic day E4.5 prior to implantation, demonstrating that TMED10 is essential for early mouse embryonic development and is expressed/required at the blastocyst stage. ([PMC3259059](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3259059/))
  - *assay*: Mouse · embryo (E4.5 blastocyst)
  > "Embryos with targeted deletion of Tmed10 (the gene that encodes p23) die at E4.5 prior to implantation, demonstrating that p23 function is essential for mouse embryonic development [ 8 ]."
- `a2_evi_21` · *Primary* · Supports · Tissue Expression — In oxaliplatin-resistant colorectal cancer (CRC) cells, a novel protein (circATG4B-222aa) competitively binds TMED10 to displace ATG4B, increasing autophagy and chemoresistance. This establishes TMED10 expression and functional relevance in CRC tumor cells under chemoresistant disease state. ([PMC9762280](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9762280/))
  - *assay*: Human · HCT116-L-OHP (oxaliplatin-resistant CRC cells)
  > "A novel protein (circATG4B‐222aa) encoded by circATG4B increased ATG4B activity by competitively binding to TMED10 and in turn induced autophagy, leading to the chemoresistance phenotype."
- `a2_evi_22` · *Primary* · Refutes · Surface Expression — TMED10 (p23/Tmp21) is a type I transmembrane protein highly enriched in the ER and Golgi compartments, where it acts as a docking protein for C1 domain-containing signaling proteins such as chimaerins and PKC isozymes, mediating their perinuclear compartmentalization. ([PMC2854097](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2854097/))
  - *assay*: Human · multiple cell lines (LNCaP, HEK293) · fixed · permeabilized
  > "Previous studies have identified p23/Tmp21, a type I transmembrane protein highly enriched in the ER and Golgi, as an α- and β-chimaerin–interacting protein."
- `a2_evi_23` · *Primary* · Supports · Tissue Expression — In LNCaP prostate cancer cells, silencing TMED10 (p23) markedly enhances PKCδ translocation to the plasma membrane in response to phorbol ester, indicating that TMED10 normally retains PKCδ at the perinuclear/ER-Golgi region and limits its plasma membrane availability. This is a contradictory observation relative to TMED10 being a surface-promoting factor — here TMED10 acts as an endomembrane anchor that restricts PM translocation of its binding partners. ([PMC3091192](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3091192/))
  - *assay*: Human · LNCaP prostate cancer cells · fixed · permeabilized
  > "Using a yeast two-hybrid approach, we found that the PKCδ C1b domain associates with p23 and identified two key residues (Asp(245) and Met(266)) implicated in this interaction. Interestingly, silencing p23 from LNCaP prostate cancer cells using RNAi markedly enhanced PKCδ-dependent apoptosis and activation of PKCδ downstream effectors ROCK and JNK by phorbol 12-myristate 13-acetate. Moreover, translocation of PKCδ to the plasma membrane by phorbol 12-myristate 13-acetate was enhanced in p23-depleted LNCaP cells."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/TMED10.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/TMED10](https://surfaceome.deliverome.org/TMED10)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/TMED10.json](https://surfaceome.deliverome.org/data/surfaceome/TMED10.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/TMED10.md](https://surfaceome.deliverome.org/data/surfaceome/TMED10.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P49755](https://alphafold.ebi.ac.uk/entry/P49755)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P49755](https://alphafold.ebi.ac.uk/api/prediction/P49755) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P49755](https://www.uniprot.org/uniprotkb/P49755)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-P49755-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-P49755-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-P49755-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-P49755-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-P49755-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-P49755-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*219 aa · `P49755` · embedded at build time*

```
   1  MSGLSGPPARRGPFPLALLLLFLLGPRLVLAISFHLPINSRKCLREEIHKDLLVTGAYEI
  61  SDQSGGAGGLRSHLKITDSAGHILYSKEDATKGKFAFTTEDYDMFEVCFESKGTGRIPDQ
 121  LVILDMKHGVEAKNYEEIAKVEKLKPLEVELRRLEDLSESIVNDFAYMKKREEEMRDTNE
 181  STNTRVLYFSIFSMFCLIGLATWQVFYLRRFFKAKKLIE
```

### Alternative-isoform sequences

**P49755-2** (`P49755-2` · 177 aa)

```
   1  MSGLSGPPARRGPFPLALLLLFLLGPRLVLAISFHLPINSRKCLREEIHKDLLVTGAYEI
  61  SDQSGGAGGLRSHLKITDSAGHILYSKEDATKGKFAFTTEDYDMFEVCFESKGTGRIPDQ
 121  LVILDMKKREEEMRDTNESTNTRVLYFSIFSMFCLIGLATWQVFYLRRFFKAKKLIE
```

**P49755-3** (`P49755-3` · 153 aa)

```
   1  MSGLSGPPARRGPFPLALLLLFLLGPRLVLAISFHLPINSRKCLREEIHKDLLVTGAYEI
  61  SDQSGGAGGLRSHLKITDSAGHILYSKEDATKGKFAFTTEDYDMFEVCFESKGTGRIPDQ
 121  LVILDMKHGVEAKNYEEHSVSEEKVWKDNTSSL
```

### Canonical ortholog sequences

**Mouse — Tmed10** (`Q9D1D4` · 219 aa)

```
   1  MSGLFGPLSRPGPLPSAWLFLLLLGPSSVLGISFHLPVNSRKCLREEIHKDLLVTGAYEI
  61  TDQSGGAGGLRTHLKITDSAGHILYAKEDATKGKFAFTTEDYDMFEVCFESKGTGRIPDQ
 121  LVILDMKHGVEAKNYEEIAKVEKLKPLEVELRRLEDLSESIVNDFAYMKKREEEMRDTNE
 181  STNTRVLYFSIFSMFCLIGLATWQVFYLRRFFKAKKLIE
```

**Cynomolgus — TMED10** (`A0A2K5UTI6` · 231 aa)

```
   1  MSGLSGPPARRGRCPLALLLLFLLCPSLVLAISFHLPINSRKCLREEIHKDLLVTGAYEI
  61  SDQSGGAGGLRSHLKITDSAGHILYSKEDATKGKFAFTTEDYDMFEVCFESKVFHTMNPL
 121  ISFSGTGRIPDQLVILDMKHGVEAKNYEEIAKVEKLKPLEVELRRLEDLSESIVNDFAYM
 181  KKREEEMRDTNESTNTRVLYFSIFSMFCLIGLATWQVFYLRRFFKAKKLIE
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`P49755`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIII
```

**P49755-2** (`P49755-2`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIII
```

**P49755-3** (`P49755-3`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**Mouse ortholog — Tmed10** (`Q9D1D4`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIII
```

**Cynomolgus ortholog — TMED10** (`A0A2K5UTI6`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — Confidence is moderate because no direct surface assay — live-cell flow cytometry or non-permeabilized immunofluorescence of TMED10 itself — was identified; all positive surface signals are functional readouts measuring cargo delivery rather than TMED10's own outer-face exposure. The triage prior correctly flagged dual_localization with a contextual verdict, and the deep-dive evidence confirms this: the dominant pool is cis-Golgi/ERGIC, with PM trafficking documented only under ER stress or specific cell states. Lifting confidence would require a non-permeabilized surface stain or live-cell flow directly detecting endogenous TMED10 at the outer leaflet, ideally in a stress-induced or T cell context where the PM pool is expected to be maximal.*
