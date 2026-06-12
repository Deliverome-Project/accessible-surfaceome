# IZUMO4 — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-31T15:24:58.797948Z · model `claude-sonnet-4-6`*

> IZUMO4 is a soluble, secreted member of the IZUMO immunoglobulin-like family that lacks a transmembrane domain, distinguishing it sharply from its paralogs IZUMO1/2/3. Multiple convergent review and computational sources (a1_evi_01, a1_evi_02, a1_evi_03) describe it as constitutively secreted rather than membrane-anchored, with expression detected in testis round spermatids at the RNA level (a1_evi_05). There is no experimental surface-display evidence and no documented plasma membrane anchor. IZUMO4 is not a viable surface-targeting candidate under current evidence.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:26950](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:26950) |
| UniProt | [Q1ZYL8](https://www.uniprot.org/uniprotkb/Q1ZYL8) |
| NCBI Gene | [113177](https://www.ncbi.nlm.nih.gov/gene/113177) |
| Ensembl | [ENSG00000099840](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000099840) |
| Subcategory | Other |
| Surface accessibility | No |
| Confidence | Moderate |
| Evidence grade | Weak |
| Triage signal | Unlikely |
| Headline risks | Secreted Form |

## 1. Executive summary

**IZUMO4 is a constitutively secreted soluble protein with no membrane anchor; no surface-accessible state has been documented in any tissue or cell type.**

IZUMO4 is a soluble, secreted member of the IZUMO immunoglobulin-like family that lacks a transmembrane domain, distinguishing it sharply from its paralogs IZUMO1/2/3. Multiple convergent review and computational sources (a1_evi_01, a1_evi_02, a1_evi_03) describe it as constitutively secreted rather than membrane-anchored, with expression detected in testis round spermatids at the RNA level (a1_evi_05). There is no experimental surface-display evidence and no documented plasma membrane anchor. IZUMO4 is not a viable surface-targeting candidate under current evidence.

**Family / classification** — UniProt family: Izumo family · HGNC gene group(s): IZUMO family · functional class: Miscellaneous.

**Triage first-pass reasoning** — IZUMO4 (Q1ZYL8) is an IZUMO family member but diverges sharply from its paralogs IZUMO1/2/3 in localization. The NCBI/Alliance annotation explicitly places it in the nucleus. Unlike IZUMO1, which is a classic single-pass TM protein on sperm, IZUMO4 lacks a predicted TM domain and signal peptide consistent with surface display; structural bioinformatics and the available literature describe it as a nuclear-localized protein. Checking contextual buckets: (1) cell_state_induced — no evidence of stress/ICD-induced surface translocation; (2) tissue_restricted_surface — no sperm-surface or other surface display documented even in restricted lineages; (3) lysosomal_exocytosis — no lysosomal/endosomal TM topology reported; (4) dual_localization — no PM pool described; (5) stable_surface_attachment — it is not a secreted protein captured at the surface. No antibody/ADC/CAR-T surface-targeting program is documented. The dominant evidence points to a nuclear-resident protein with no membrane anchor.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=No · conf=Moderate · subcategory=Other · ecd=None |
| Classification | reason=Secreted Only · family=Miscellaneous · state-dependence=Low · induction-trigger=None |
| Expression | level=Low · breadth=Rare · specificity=Mostly Intracellular · low-endogenous=true · tumor-associated=false · orphan-receptor=true · OE-precedent=false |
| Risks | shed=false · secreted=true · co-receptor=None · masking=false · restricted-subdomain=false |
| Evidence | grade=Weak · density=Low · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=0 · N-term-ECF=false · C-term-ECF=false |

**Facet rationales**

- *Expression level*: Expression detected by scRNA-seq as a round spermatid marker in testis (a1_evi_05); no broad or high-level expression data in the ledger. Restricted germ-cell RNA signal; protein-level evidence absent.
- *Expression breadth*: Ledger evidence localizes IZUMO4 expression to testis, specifically round spermatids (a1_evi_05); review text notes testis and other tissues broadly (a1_evi_03) but without quantitative data. Overall breadth appears rare/restricted.
- *Surface specificity*: IZUMO4 is a secreted soluble protein with no TM domain (a1_evi_01, a1_evi_02, a1_evi_03); it is not plasma-membrane resident. The dominant compartment is extracellular/secreted, and no PM pool has been described.
- *Known ligand*: IZUMO4 is a poorly characterized secreted IZUMO family member; no validated endogenous receptor or binding partner has been reported in the literature surveyed. Functional interaction context is limited to computational sperm-egg fusion network studies (a1_evi_04).
- *Low endogenous expression*: Derived from expression_level='low' (∈ {low, absent} → flagged). Expression detected by scRNA-seq as a round spermatid marker in testis (a1_evi_05); no broad or high-level expression data in the ledger. Restricted germ-cell RNA signal; protein-level evidence absent.
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Weak

No direct surface assay (live flow cytometry, nonperm IF, surface biotinylation, or IHC-membranous) exists for IZUMO4 in this ledger. All topology claims are review-level or computational: three moderate-weight claims (a1_evi_01, 02, 03) consistently characterize IZUMO4 as a secreted/soluble protein lacking a transmembrane domain, directly contradicting stable plasma membrane surface display. One computational interaction study (a1_evi_04) is tangential, and one scRNA-seq observation (a1_evi_05) is expression-only. The absence of any direct surface methodology and the convergent evidence for a soluble topology yields a grade of 'weak' — the evidence is consistent but rests entirely on review assertions and computational predictions rather than experimental surface assays.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Contradicts Surface | Moderate | Review assertion: IZUMO4 lacks TM domain unlike IZUMO1/2/3; consistent across family topology description |
| a1_evi_02 | Contradicts Surface | Moderate | Computational prediction classifies IZUMO4 as secreted; no direct assay but corroborates a1_evi_01 |
| a1_evi_03 | Contradicts Surface | Moderate | Review-level characterization as soluble protein lacking TM anchor; no direct surface assay |
| a1_evi_04 | Tangential | Low | Structural region definition (C18-H232) used in computational interaction study; no surface assay |
| a1_evi_05 | Expression Only | Low | scRNA-seq marker in buffalo round spermatids; RNA-level only, no surface assay |

### Other (1 method)

#### Unknown — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Unknown · expression: Unknown*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Testis and other tissues; IZUMO4 described as constitutively soluble protein lacking a TM domain | Primary Human Tissue | Moderate | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Buffalo testis round spermatids (DNAH14+/IZUMO4+/NKAPL+) | Primary Human Cell | Single Cell RNA | Moderate | 1 |

**Contradicting evidence**

- *Secreted Only* (severity High): IZUMO4 lacks a transmembrane domain and is computationally predicted to be a secreted protein, in contrast to the other IZUMO family members (IZUMO1/2/3) which are single-pass membrane proteins. Multiple sources consistently describe IZUMO4 as a constitutively soluble protein expressed in testis and other tissues, with no evidence of a membrane-anchored precursor or sheddase-mediated release. This strongly refutes stable plasma membrane surface display for IZUMO4.
  - Likely explanation: IZUMO4 appears to be an evolutionarily diverged family member that retained the IZUMO immunoglobulin-like fold but lost the transmembrane segment, rendering it constitutively soluble/secreted. Any apparent 'surface' signal would likely reflect transient association of extracellular soluble protein with the cell surface rather than bona fide membrane anchoring.

## 4. Biological context

**Primary subcellular compartment**: Plasma membrane

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Weak
- domain: Unknown
- rationale: No surface membrane subdomain localization is reported; the protein is secreted and not membrane-anchored, making subdomain restriction a non-applicable concern. No relevant distribution data in the ledger.

**Co-receptor requirements**

- dependency: None
- evidence basis: Co Expression Only
- rationale: IZUMO4 is constitutively secreted and lacks a TM domain; it does not reach the plasma membrane and therefore has no surface-expression co-receptor dependency. The question is moot given the secreted topology.
- cites: a1_evi_01, a1_evi_02

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM placeholder-no-d1-row · Ensembl —. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | Q1ZYL8 | ref | ref | 0 | 0 aa | 0 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak

**Secreted form**

- present: true
- severity: High
- evidence: Moderate
- source: Unknown
- cites: a1_evi_01, a1_evi_02, a1_evi_03

**ECD size assessment**

- ECD class: None
- rationale: IZUMO4 lacks a transmembrane domain (a1_evi_01, a1_evi_02) and is constitutively secreted; there is no membrane-tethered extracellular domain by definition. ECD size as an antibody-engagement metric does not apply.
- cites: a1_evi_01, a1_evi_02

**Epitope masking**

- severity: None
- evidence: Weak
- mechanism: None
- rationale: No surface-displayed form exists on which to assess epitope masking. The protein is entirely soluble/secreted. Not applicable.

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-Q1ZYL8-F1](https://alphafold.ebi.ac.uk/entry/Q1ZYL8) |
| AFDB version | v6 |
| ECD mean pLDDT | 81.4 |
| ECD disordered fraction | 23.3% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/Q1ZYL8) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [Q1ZYL8](https://alphafold.ebi.ac.uk/entry/Q1ZYL8) | AlphaFold DB (AF-Q1ZYL8-F1, v6) |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

5 entries · 0 primary · 5 secondary · 0 tertiary · 5 PMC OA.

- `a1_evi_01` · *Secondary* · Refutes · Topology — IZUMO4 lacks a transmembrane domain, distinguishing it from the other IZUMO family members (IZUMO1/2/3) that are single-pass membrane proteins. This topology finding directly refutes canonical plasma membrane anchoring for IZUMO4 and supports a secreted/soluble rather than membrane-anchored surface model. ([PMC8999778](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8999778/))
  - *assay*: Human
  > "Notably, IZUMO4 lacks a transmembrane domain [ 39 ]."
- `a1_evi_02` · *Secondary* · Refutes · Topology — Computational prediction classifies IZUMO4 as a secreted protein, in contrast to IZUMO1/2/3 which are predicted single-pass membrane proteins. This supports IZUMO4 being a soluble/secreted form rather than a plasma-membrane-anchored surface protein, directly refuting stable surface display. ([PMC9482655](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9482655/))
  - *assay*: Human
  > "IZUMO2 and IZUMO3 are predicted to be single-pass membrane proteins like IZUMO1, whereas IZUMO4 appears to be secreted."
- `a1_evi_03` · *Secondary* · Refutes · Surface Expression — IZUMO4 is described as a soluble protein expressed in the testis and other tissues, indicating it is not membrane-anchored. This refutes plasma membrane surface accessibility and flags IZUMO4 as a secreted/soluble form; the soluble form is the dominant species. No sheddase is implicated — the protein appears constitutively soluble by virtue of lacking a TM domain rather than being shed from a membrane-anchored precursor. ([PMC8999778](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8999778/))
  - *assay*: Human
  > "IZUMO4 is a soluble protein expressed in the testis and other tissues."
- `a1_evi_04` · *Secondary* · Ambiguous · Topology — In a deep-learning structural study of the sperm-egg fusion synapse, the IZUMO4 region used for binary interaction predictions is defined as C18-H232 (UniProt Q1ZYL8). This region definition is consistent with the entire protein being extracellular/secreted (no intracellular domain segment specified), supporting the interpretation that IZUMO4's folded domain is fully outside the membrane, though the protein itself lacks a TM anchor. ([PMC11052572](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11052572/))
  - *assay*: Human
  > "The human protein regions used for the binary interaction predictions whose network is shown in Figure 4 were CD9 P2-V228 (UniProt P21926 ); CD81 M1-Y236 ( P60033 ); DCST1 M1-G706 ( Q5T197 ); DCST2 M1-K773 ( Q5T1A1 ); FIMP A22-S77 (Q96LL3-2); JUNO G20-S228 ( A6ND01 ); IZUMO1 C22-Q284 ( Q8IYV9 ); IZUMO2 C21-P183 ( Q6UXV1 ); IZUMO3 C21-D166 ( Q5VZ72 ); IZUMO4 C18-H232 ( Q1ZYL8 ); MAIA Q16-L580 ( Q96P31 ); SOF1 S29-H122 ( Q96L11 ); SPACA6 C27-T291 ( W5XKT8 ); TMEM81 I31-P218 ( Q6P7N7 ); TMEM95 C17-D140 ( Q3KNT9 )."
- `a1_evi_05` · *Secondary* · Ambiguous · Tissue Expression — Single-cell RNA-seq of buffalo testis identifies IZUMO4 as a marker gene for the round spermatid stage of spermatogenesis (DNAH14+/IZUMO4+/NKAPL+). This is an RNA-level expression observation in germ cells with no accompanying surface-method validation; it qualifies IZUMO4 as expressed in round spermatids but does not establish plasma membrane accessibility. ([PMC9793287](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9793287/))
  - *assay*: Other · round spermatid
  > "PTPRC + / NKG7 + / KLRF1 + / CD94 + ), undifferentiated spermatogonia (Undiff SPG, SALL4 + / ZBTB16 + / ELAVL2 + ), spermatogonia (SPG, NR6A1 + / FGFR3 + / FMR1 + ), early-stage primary spermatocyte (from preleptotene to zygotene) (Early SPC, TEX12 + / SMCHD1 + / PRSS50 + ), late-stage spermatocyte (from pachytene to secondary spermatocyte) (Late SPC, SYCE2 + / BOLL + / MLH1 + ), round spermatid (RS, DNAH14 + / IZUMO4 + / NKAPL + ), elongating/elongated spermatid (ES, TEX29 + / FBXO24 + / ACRV1 + ), and spermatozoa (Sperm, ODF1 + / ODF2 + / OAZ3 + / AKAP4 + ) ( Figures 1 E, S1 C, and S1D)."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/IZUMO4.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/IZUMO4](https://surfaceome.deliverome.org/IZUMO4)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/IZUMO4.json](https://surfaceome.deliverome.org/data/surfaceome/IZUMO4.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/IZUMO4.md](https://surfaceome.deliverome.org/data/surfaceome/IZUMO4.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/Q1ZYL8](https://alphafold.ebi.ac.uk/entry/Q1ZYL8)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/Q1ZYL8](https://alphafold.ebi.ac.uk/api/prediction/Q1ZYL8) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/Q1ZYL8](https://www.uniprot.org/uniprotkb/Q1ZYL8)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-Q1ZYL8-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-Q1ZYL8-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-Q1ZYL8-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-Q1ZYL8-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-Q1ZYL8-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-Q1ZYL8-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*232 aa · `Q1ZYL8` · embedded at build time*

```
   1  MALLLCLVCLTAALAHGCLHCHSNFSKKFSFYRHHVNFKSWWVGDIPVSGALLTDWSDDT
  61  MKELHLAIPAKITREKLDQVATAVYQMMDQLYQGKMYFPGYFPNELRNIFREQVHLIQNA
 121  IIESRIDCQHRCGIFQYETISCNNCTDSHVACFGYNCESSAQWKSAVQGLLNYINNWHKQ
 181  DTSMRPRSSAFSWPGTHRATPAFLVSPALRCLEPPHLANLTLEDAAECLKQH
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`Q1ZYL8`, placeholder-no-d1-row)

```

```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — placeholder-no-d1-row · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — — · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — Confidence is moderate rather than low because multiple independent sources converge on the same conclusion — IZUMO4 lacks a transmembrane domain and is constitutively secreted — but these sources are all review assertions or computational predictions rather than direct experimental assays (e.g. western blot of conditioned medium, live-cell surface biotinylation, or flow cytometry). The triage verdict of 'nuclear' is partially at odds with the ledger, which describes secreted rather than nuclear localization; both agree there is no plasma membrane surface display. Confidence would rise to high if a direct surface-proteomics or conditioned-medium mass spectrometry study confirmed the secreted topology and ruled out any membrane-anchored isoform, particularly in sperm or testicular cell lines.*

## CellxGene RNA enrichment (CZI Census)

*Schema v2.1.5 · CZI Census 2025-11-08 · HPA-style 4× fold-change classification on log1p(CP10K) → linear means, plus Yanai et al. 2005 τ (specificity score ∈ [0, 1], computed over the eligible-entity set). Cell-class rollup walks the Cell Ontology graph (cl-basic.obo, OBO Foundry) — leaf CL → nearest compartment ancestor. CC-BY 4.0 (CZI Census).*

**Classification:**

- **Cell class (CL ontology graph, ~10 compartments):** enriched · Reproductive · 23.9× · τ=0.97
- **Cell type (leaf Cell Ontology terms, ~600):** enriched · spermatocyte · 2.1× · τ=0.98
- **Tissue (UBERON terms, ~56):** enriched · eye · testis · 1.5× · τ=0.86

**Top 5 cell types (leaf CL, pooled across tissues):**

| Cell type | CL ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| spermatocyte | CL:0000017 | 2.599 | 85.21% | 2,616 / 3,070 |
| epithelial cell of sweat gland | CL:1000448 | 2.555 | 0.33% | 1 / 301 | (trace)
| inhibitory motor neuron | CL:0008015 | 2.537 | 0.13% | 1 / 745 | (trace)
| visceromotor neuron | CL:0005025 | 2.437 | 0.16% | 1 / 610 | (trace)
| natural T-regulatory cell | CL:0000903 | 2.281 | 1.60% | 114 / 7,117 |

**Top 5 tissues (UBERON, pooled across cell types):**

| Tissue | UBERON ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| pleura | UBERON:0000977 | 2.319 | 0.13% | 26 / 19,695 | (trace)
| testis | UBERON:0000473 | 2.257 | 28.41% | 5,888 / 20,724 |
| scalp | UBERON:0000403 | 2.221 | 0.10% | 3 / 3,029 | (trace)
| esophagus | UBERON:0001043 | 2.201 | 3.71% | 875 / 23,590 |
| pancreas | UBERON:0001264 | 2.162 | 0.61% | 1,506 / 246,237 | (trace)

<!-- /cellxgene -->
