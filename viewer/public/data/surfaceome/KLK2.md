# KLK2 — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-31T15:33:42.417728Z · model `claude-sonnet-4-6`*

> KLK2 (human kallikrein-2) is a canonical secreted serine protease with no transmembrane domain, but a 2025 preclinical study (PMC12580770) demonstrates surface accessibility on intact prostate cancer cells by live-cell FACS on VCaP and fresh mCRPC patient tumor cells, confocal IF, and functional engagement via three distinct therapeutic modalities. Surface expression is strictly prostate-lineage- and AR-state-restricted, absent in neuroendocrine/double-negative mCRPC variants. The primary risk is a large competing secreted pool (KLK2 is constitutively secreted into conditioned medium and seminal plasma), and the surface-docking mechanism remains uncharacterized.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:6363](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:6363) |
| UniProt | [P20151](https://www.uniprot.org/uniprotkb/P20151) |
| NCBI Gene | [3817](https://www.ncbi.nlm.nih.gov/gene/3817) |
| Ensembl | [ENSG00000167751](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000167751) |
| Subcategory | Other |
| Surface accessibility | Moderate |
| Confidence | Moderate |
| Evidence grade | Direct, multi-method |
| Triage signal | Unlikely |
| Headline risks | Secreted Form |

## 1. Executive summary

**Surface-accessible specifically on AR-positive prostate cancer cells (localized PCa through mCRPC); absent in neuroendocrine/double-negative variants and non-prostate tissues.**

KLK2 (human kallikrein-2) is a canonical secreted serine protease with no transmembrane domain, but a 2025 preclinical study (PMC12580770) demonstrates surface accessibility on intact prostate cancer cells by live-cell FACS on VCaP and fresh mCRPC patient tumor cells, confocal IF, and functional engagement via three distinct therapeutic modalities. Surface expression is strictly prostate-lineage- and AR-state-restricted, absent in neuroendocrine/double-negative mCRPC variants. The primary risk is a large competing secreted pool (KLK2 is constitutively secreted into conditioned medium and seminal plasma), and the surface-docking mechanism remains uncharacterized.

**Family / classification** — UniProt family: peptidase S1 family. Kallikrein subfamily · HGNC gene group(s): Kallikreins · functional class: Enzyme.

**Triage first-pass reasoning** — KLK2 encodes human kallikrein-2 (hK2), a secreted serine protease. It is synthesized as a preproenzyme, signal peptide is cleaved cotranslationally, and the mature/pro form is secreted into extracellular fluid (seminal plasma, blood). There is no transmembrane domain, no GPI anchor signal, and no documented stable association with a surface-anchored complex. Surface biotinylation and flow cytometry studies have not identified a cell-surface pool on intact non-permeabilized cells. Checking all contextual buckets: (1) cell-state-induced surface display — not documented; (2) tissue-restricted surface — no evidence of membrane anchoring in any lineage; (3) lysosomal exocytosis — not reported; (4) dual localization / TM precursor — no TM isoform exists; (5) stable surface attachment to TM partner — not documented. Therapeutic programs (e.g., anti-hK2 antibody-drug conjugates such as PSMA/hK2 bispecifics) target the secreted/shed protein or use hK2 as a prodrug activator in the extracellular milieu, not the protein body on the cell surface per se. KLK2 is therefore secreted-only.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=Moderate · conf=Moderate · subcategory=Other · ecd=Large |
| Classification | reason=Tissue Restricted Surface · family=Enzyme · state-dependence=High · induction-trigger=None |
| Expression | level=High · breadth=Rare · specificity=Mixed · low-endogenous=false · tumor-associated=false · orphan-receptor=false · OE-precedent=false |
| Risks | shed=false · secreted=true · co-receptor=Unknown · masking=false · restricted-subdomain=false |
| Evidence | grade=Direct, multi-method · density=High · live-cell-surface=true · supporting(hi)=3 · contradicting(hi)=0 |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=0 · N-term-ECF=true · C-term-ECF=true |

**Facet rationales**

- *Expression level*: High expression across localized PCa and mHSPC by IHC and RNA-seq; robustly and homogeneously expressed in AR+ prostate cancer (a2_evi_04, a2_evi_02). Expression becomes heterogeneous in visceral mCRPC lesions.
- *Expression breadth*: Essentially prostate-restricted: RNA-seq panel shows little-to-no expression outside prostate/prostate adenocarcinoma (a2_evi_02, a2_evi_03). Among the most prostate-specific antigens surveyed, narrower than PSMA/PSCA/STEAP1.
- *Surface specificity*: Live-cell FACS confirms surface pool on VCaP and patient mCRPC cells (a1_evi_02, a2_evi_14), but conditioned-medium WB documents a dominant secreted pool in LNCaP cells (a1_evi_14, a2_evi_11). Both pools coexist; surface fraction fraction unknown.
- *Known ligand*: KLK2 is a serine protease (trypsin-like) with documented substrates including semenogelins and pro-PSA (KLK3 precursor); substrate/inhibitor interactions are well characterized. Protease inhibitor MDPK67b targets KLK2 active site (a1_evi_17).
- *Low endogenous expression*: Derived from expression_level='high' (not low/absent → not flagged). High expression across localized PCa and mHSPC by IHC and RNA-seq; robustly and homogeneously expressed in AR+ prostate cancer (a2_evi_04, a2_evi_02). Expression becomes heterogeneous in visceral mCRPC lesions.
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Direct, multi-method

KLK2 surface accessibility is supported by multiple direct methods from a single primary source (PMC12580770). High-weight support: (1) live/non-permeabilized FACS on VCaP cells AND fresh mCRPC patient tumor cells (a1_evi_02, a1_evi_04); (2) functional surface engagement via three mechanistically distinct therapeutic modalities — bispecific T-cell redirector, alpha-radioligand, CAR-T cells — all requiring surface-accessible KLK2 (a1_evi_07). Moderate support: confocal IF surface imaging (a1_evi_03), live-cell antibody kinetics (a1_evi_10), and independent surface proteome MS (a1_evi_12, different source). The canonical secreted-protein topology (a1_evi_15, a1_evi_16) and secretion evidence (a1_evi_13, a1_evi_14) are tangential — they describe baseline biology and do not mechanistically preclude surface retention in prostate cancer. Two distinct direct method families (flow cytometry + immunofluorescence) are present, qualifying for `direct_multi_method`.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_02 | Supports Surface | High | Live/non-permeabilized FACS on VCaP cell line AND primary mCRPC patient tumor cells; two independent sample types in one study |
| a1_evi_03 | Supports Surface | Moderate | Confocal IF surface imaging on VCaP; permeabilization not explicitly stated but framed as surface expression |
| a1_evi_04 | Supports Surface | High | Methods explicitly state non-permeabilized live flow cytometry on fresh mCRPC patient tumor samples |
| a1_evi_07 | Supports Surface | High | Functional engagement at cell surface via bispecific T-cell redirector, alpha-radioligand, and CAR-T — three independent surface-targeting modalities |
| a1_evi_10 | Supports Surface | Moderate | Live-cell antibody kinetics showing plasma membrane binding at 60 min before internalization; direct surface accessibility evidence |
| a1_evi_12 | Supports Surface | Moderate | Surface proteome MS detection of KLK2 peptides; decreased abundance ambiguous but confirms surface-fraction presence |
| a1_evi_01 | Supports Surface | Moderate | Abstract-level summary from primary study; load-bearing conclusion statement but secondary tier |
| a1_evi_08 | Supports Surface | Low | Independent source review assertion co-citing KLK2 as a cell surface target; no primary methodology |
| a1_evi_11 | Tangential | Low | Acknowledges prior 'limited evidence' for surface expression — contextualizes novelty but does not refute the new data |
| a1_evi_13 | Tangential | Low | KLK2 described as secreted AR target; canonical biology context, not mechanistically incompatible with surface form in cancer state |
| a1_evi_14 | Tangential | Low | Conditioned medium WB showing secreted KLK2; documents secreted pool, does not refute surface-retained fraction |
| a1_evi_15 | Tangential | Low | KLKs described as canonical secreted proteases; baseline biology context, not a contradiction of surface retention in cancer cells |
| a1_evi_16 | Tangential | Moderate | No TM domain, signal peptide only — explains canonical secretion but not mechanistically incompatible with surface association/retention |
| a1_evi_17 | Tangential | Low | Protease inhibitor targeting secreted/surface-exposed KLK2 domain; indirect therapeutic relevance, no direct surface localization assay |

### Flow cytometry (1 method)

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-KLK2 (OT15D6 · OriGene · AB_2626200) — Extracellular epitope; Monoclonal; None validation (None); KLK2 shares 80% amino acid homology with KLK3 (PSA); cross-reactivity with KLK3 not explicitly ruled out in the paper.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| VCaP prostate cancer cell line, live intact cells, FACS | Established Cell Line | Moderate | 1 |
| Dissociated fresh mCRPC patient tumor cells, live intact cells, FACS | Patient Sample | Moderate | 2 |

### Immunofluorescence (2 methods)

#### Nonpermeabilized IF — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-KLK2 (OT15D6 · OriGene · AB_2626200) — Extracellular epitope; Monoclonal; None validation (None); KLK2 shares 80% amino acid homology with KLK3 (PSA); cross-reactivity with KLK3 not explicitly ruled out in the paper.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| VCaP prostate cancer cells, confocal imaging of KLK2 surface expression; antibody surface binding detected at 60 min before intracellular accumulation | Established Cell Line | Moderate | 2 |

#### Permeabilized IF — Expression Only · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-KLK2 (OT15D6 · OriGene · AB_2626200) — Extracellular epitope; Monoclonal; None validation (None); KLK2 shares 80% amino acid homology with KLK3 (PSA); cross-reactivity with KLK3 not explicitly ruled out in the paper.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Prostate cancer tissue, multiplex immunofluorescent staining confirming KLK2 expression and cell surface localization across prostate cancer stages | Primary Human Tissue | High | 1 |

### Immunohistochemistry (1 method)

#### IHC Membranous — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-KLK2 (OT15D6 · OriGene · AB_2626200) — Extracellular epitope; Monoclonal; None validation (None); KLK2 shares 80% amino acid homology with KLK3 (PSA); cross-reactivity with KLK3 not explicitly ruled out in the paper.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Prostate cancer tissue across disease stages (localized PCa, mHSPC, mCRPC) by IHC; KLK2 robustly and homogeneously expressed in localized PCa and mHSPC, some heterogeneity in visceral mCRPC lesions | Primary Human Tissue | High | 2 |

### Surface mass spec (1 method)

#### Cell Surface Capture — Supports Membrane Association · Membrane Fraction Enriched

*Permeabilization: Nonpermeabilized · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Unspecified cell type/line; KLK2 detected in surface proteome (surfaceome MS) with decreased abundance; grouped with coagulation/angiogenesis proteases (CTSB, MMP2) | Unknown | Low | 1 |

### Functional surface assay (2 methods)

#### Unknown — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| VCaP and mCRPC tumor cells; bispecific T-cell redirector (KLK2×CD3), targeted α-radioligand (225Ac-KLK2), and autologous CAR-T cells all engaging KLK2 at the cell surface; potent in vitro activity and robust in vivo tumor control in xenograft models | Established Cell Line | High | 1 |

#### Unknown — Weak Or Ambiguous · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Prostate cancer cell lines (unspecified), treated with recombinant protease inhibitor MDPK67b (ACT6.7 variant) targeting KLK2 and trypsin-like KLKs (KLK4, KLK14) in vitro; antitumor response assessed in charcoal-stripped media | Established Cell Line | Moderate | 1 |

### Other (1 method)

#### Whole Cell Proteomics — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| LNCaP prostate adenocarcinoma cells; KLK2 detected in conditioned medium (CM) by SDS-PAGE/western blot following androgen stimulation; secreted/shed pool | Established Cell Line | Moderate | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| KLK2 described as androgen-driven AR target gene encoding a secreted protein; prostate cancer screening/prognosis marker | Unknown | Bulk Protein | Moderate | 1 |
| LNCaP androgen-responsive prostate adenocarcinoma cells; KLK2 detected in conditioned medium by SDS-PAGE following androgen stimulation | Established Cell Line | Bulk Protein | Moderate | 1 |

**Contradicting evidence**

- *Secreted Only* (severity High): KLK2 is a canonical secreted serine protease with a signal peptide (aa 1-24) and no transmembrane domain, yielding a mature ~237 aa secreted protein with no intracellular domain. The entire KLK family is described as 'homologous secreted serine proteases' without membrane anchors. This structural topology argues against constitutive surface display and is consistent with a primarily secreted, extracellular-fluid-localized protein rather than a plasma-membrane-resident one.
  - Likely explanation: KLK2 may associate with the cell surface non-covalently through binding partners (e.g., via GPI-anchored proteins, integrins, or other receptors) rather than being a transmembrane protein. Recent studies have begun to document such surface retention in prostate cancer cells, reconciling the secreted topology with observed surface accessibility. The absence of a TM domain does not preclude membrane association but does mean surface localization requires a docking partner.
- *Secreted Only* (severity Moderate): Authors of a therapeutic-targeting study explicitly acknowledged that KLK2 was historically not recognized as a therapeutic target due to 'limited evidence of its cell surface expression', confirming that prior to recent work the prevailing view was that KLK2 lacked meaningful surface accessibility.
  - Likely explanation: This is a meta-level historical acknowledgment rather than a direct experimental refutation; it reflects the field's prior consensus that KLK2 is primarily a secreted enzyme. The same paper then presents new evidence for surface expression, suggesting the contradiction is being actively resolved rather than standing as a definitive refutation.

## 4. Biological context

**Cell types** *(orthogonal cell-type index)*

| Cell type | Ontology | Present in tissues | Species | Cites |
|---|---|---|---|---|
| prostate adenocarcinoma cells | — | prostate | Human | 2 |
| AR-positive prostate tumor cells | — | prostate | Human | 2 |
| neuroendocrine prostate cancer cells | — | prostate | Human | 2 |
| double-negative prostate cancer cells | — | prostate | Human | 2 |
| mCRPC tumor cells | — | prostate, prostate metastatic sites | Human | 4 |
| bone marrow-derived macrophages | — | — | Mouse | 1 |

**Cell states**

- *AR-active* — KLK2 expression is strictly AR-dependent; androgen stimulation drives KLK2 secretion in LNCaP cells, and AR genomic alterations / AR/FOXA1/HOXB13 enhancer activation correlate positively with KLK2 levels in prostate tumors. *(cites: a2_evi_05, a2_evi_06, a2_evi_08, a2_evi_09, a2_evi_11)*
- *neuroendocrine / AR-negative* — KLK2 expression is largely absent in neuroendocrine and double-negative prostate cancer phenotypes, which lack AR signaling, indicating loss of expression upon AR-negative cell-state transition. *(cites: a2_evi_05, a2_evi_08, a2_evi_09, a2_evi_10)*
- *castration-resistant (mCRPC)* — KLK2 expression becomes heterogeneous in visceral mCRPC lesions compared to robust homogeneous expression in hormone-sensitive disease; intra- and inter-tumoral variability is observed by IHC and scRNA-seq in this disease state. *(cites: a2_evi_04, a2_evi_07, a2_evi_13, a2_evi_14, a2_evi_15)*

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- Secreted · androgen-stimulated prostate cancer cells *(cites: a2_evi_11, a2_evi_13)*

**Accessibility modulation**

- *Tissue Restricted Surface* · lineage: Epithelial: non-prostate tissues (multi-tissue panel) → prostate epithelial cancer cells (LPC, mHSPC, mCRPC) — KLK2 surface expression is absent or minimal in non-prostate tissues but is confirmed on the plasma membrane of prostate cancer cells by live-cell FACS on VCaP cells and dissociated patient-derived mCRPC tumor cells. *(→ KLK2 Surface Accessibility Is Highly Restricted To Prostate-Lineage Tumor Cells, Making It A Selective Target For Extracellular Binders With Low Expected Off-Tumor Engagement In Non-Prostate Tissues.)* *(cites: a2_evi_02, a2_evi_03, a2_evi_13, a2_evi_14, a2_evi_15)*
- *Disease State Induced*: AR-negative / neuroendocrine or double-negative mCRPC tumor cells → AR-positive mCRPC tumor cells — KLK2 surface expression is high and homogeneous in AR+ prostate cancer cells but largely absent in neuroendocrine and double-negative mCRPC subtypes, driven by strict AR/FOXA1/HOXB13-dependent transcriptional and epigenomic activation. *(→ Surface-Accessible KLK2 Is Contingent On AR Pathway Activity; AR-Low Or Lineage-Switched Tumor Variants Will Lack Surface KLK2, Limiting Binder Efficacy In Those Disease States.)* *(cites: a2_evi_04, a2_evi_05, a2_evi_08, a2_evi_09, a2_evi_13, a2_evi_14)*

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Moderate
- domain: Unknown
- rationale: Live-cell FACS on VCaP and fresh mCRPC patient tumor cells shows broad plasma membrane signal without fractionation to a specific subdomain. No apical, junctional, or ciliary restriction is documented. The pan-membrane staining pattern in confocal IF (a1_evi_03) and the efficacy of three surface-targeting modalities (a1_evi_07) are consistent with broad membrane distribution.
- cites: a1_evi_02, a1_evi_03, a1_evi_07, a2_evi_14

**Co-receptor requirements**

- dependency: Unknown
- evidence basis: Co Expression Only
- rationale: KLK2 has no transmembrane domain and lacks a GPI signal, so surface retention must depend on a docking partner (e.g., GPI-anchored protein, integrin, or other receptor). The identity of this partner is undocumented in the ledger; surface expression is confirmed but the molecular anchor mechanism is uncharacterized.
- cites: a1_evi_15, a1_evi_16

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl —. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P20151 | ref | ref | 0 | 244 aa | 0 aa | 17 aa | Extracellular→Extracellular | — |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak

**Secreted form**

- present: true
- severity: High
- evidence: Strong
- source: Unknown
- cites: a1_evi_14, a1_evi_15, a1_evi_16, a2_evi_11

**ECD size assessment**

- ECD class: Large
- rationale: KLK2 is a secreted protease of ~237 residues (signal peptide-cleaved mature protein; a1_evi_16). The entire mature protein constitutes the extracellular-facing domain when surface-retained. At ≥200 aa this qualifies as 'large', accommodating numerous non-overlapping antibody footprints.
- cites: a1_evi_16

**Epitope masking**

- severity: Low
- evidence: Inferred
- mechanism: Conformational
- rationale: KLK2 is a serine protease with a well-defined catalytic domain; the active-site cleft may restrict access to some epitopes. Glycosylation of KLKs is documented in the literature but specific masking data for KLK2 surface form are not present in the ledger. No binding-blocking or masking study is reported. The therapeutic antibody OT15D6 binds surface KLK2 successfully (a1_evi_02), suggesting accessible epitopes exist.
- cites: a1_evi_02

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P20151-F1](https://alphafold.ebi.ac.uk/entry/P20151) |
| AFDB version | v6 |
| ECD mean pLDDT | 95.5 |
| ECD disordered fraction | 3.3% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P20151) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P20151](https://alphafold.ebi.ac.uk/entry/P20151) | AlphaFold DB (AF-P20151-F1, v6) |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

33 entries · 22 primary · 11 secondary · 0 tertiary · 25 PMC OA.

- `a1_evi_01` · *Secondary* · Supports · Surface Expression — Although KLK2 is traditionally described as a secreted protease, the authors demonstrate cell surface expression in both prostate cancer cell lines (VCaP) and patient-derived tumors, directly contradicting the secreted-only prior. This is the paper's primary conclusion and is the load-bearing surface-expression claim. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · VCaP; mCRPC patient-derived tumor cells · unspecified · non-permeabilized
  > "Although KLK2 is traditionally described as a secreted protease, our results demonstrated its cell surface expression in both prostate cancer cell lines and patient-derived tumors."
- `a1_evi_02` · *Primary* · Supports · Surface Expression — FACS of intact (non-permeabilized) VCaP cells and dissociated mCRPC tumor cells confirms KLK2 cell surface expression. This is a primary flow cytometry result on live/intact cells in both a prostate cancer cell line and patient-derived tumor samples, providing direct evidence of plasma membrane accessibility. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · VCaP; mCRPC dissociated tumor cells · live · non-permeabilized
  > "Cell surface expression of KLK2 was confirmed by FACS of VCaP cells ( Fig. 2A ) and dissociated mCRPC tumor cells ( Fig. 2B )."
- `a1_evi_03` · *Primary* · Supports · Surface Expression — Confocal immunofluorescence imaging of KLK2 surface expression in VCaP cells (PMC12580770). This is a direct surface-localization readout by IF microscopy supporting cell surface accessibility; permeabilization status must be inferred from context (surface-expression framing suggests non-permeabilized or membrane-targeted staining). ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · VCaP · unspecified · non-permeabilized
  > "C, Confocal imaging of KLK2 surface expression in VCaP cells."
- `a1_evi_04` · *Primary* · Supports · Methodological — Flow cytometry surface-expression assay: KLK2 cell surface expression in fresh mCRPC tumor samples assessed by flow cytometry using an anti-KLK2 antibody on intact (non-permeabilized) cells. Method family: flow cytometry; sample: primary patient tumor (mCRPC); non-permeabilized. Paired with results clip draft_PMC12580770_results_03. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · fresh mCRPC tumor cells · live · non-permeabilized
  > "KLK2 cell surface expression in fresh tumor samples of patients with mCRPC was assessed by flow cytometry using an anti-KLK2 antibody."
- `a1_evi_05` · *Primary* · Supports · Methodological — Antibody reagent detail: rabbit monoclonal anti-human KLK2 antibody clone OT15D6 (OriGene; RRID:AB_2626200) used for KLK2 IHC and surface staining experiments in PMC12580770. Paired antibody identifier and RRID for MethodObservation.antibodies[] population. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · fixed
  > "Rabbit monoclonal anti-human KLK2 antibody clone OT15D6 (OriGene; RRID:AB_2626200), anti-human CD4 antibody clone EPR6855 (Abcam; RRID:AB_2750883), anti-human CD8 antibody clone SP57 (Ventana; RRID:AB_2335985), and anti-human CK (AE1/AE3, Leica; RRID:AB_564123) were used for KLK2, CD4, and CD8 IHC."
- `a1_evi_06` · *Secondary* · Supports · Methodological — IHC and multiplex immunofluorescent staining were used to confirm KLK2 cell surface expression in prostate cancer. This abstract-level methodological statement establishes that the PMC12580770 study used paired IHC and multiplex IF to characterize KLK2 surface localization across prostate cancer stages. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · fixed
  > "In this study, we systematically characterized KLK2 expression in prostate cancer, confirmed its cell surface expression, and demonstrated the preclinical efficacy of three KLK2-targeting therapeutics with distinct MoA.<h4>Experimental design</h4>The KLK2 expression profile in different stages of prostate cancer and its cell surface expression were confirmed by IHC and multiplex immunofluorescent staining."
- `a1_evi_07` · *Primary* · Supports · Surface Expression — PMC12580770 establishes KLK2 as a prostate-specific cell surface target and demonstrates preclinical efficacy of three KLK2-targeting therapeutics with distinct mechanisms: bispecific T-cell redirector, targeted alpha-radioligand, and autologous CAR-T cells. All three modalities engage KLK2 at the cell surface of prostate cancer cells, providing strong therapeutic-engagement evidence for the surface-accessible form of KLK2. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · VCaP; mCRPC tumor cells · live · non-permeabilized
  > "Notably, targeting KLK2 with three different MoAs, including bispecific T-cell redirector, targeted α-radioligand, and autologous chimeric antigen receptor T cells, showed potent in vitro activity and robust in vivo tumor control.<h4>Conclusions</h4>Our study establishes KLK2 as a highly prostate-specific cell surface target."
- `a1_evi_08` · *Secondary* · Supports · Surface Expression — Review/abstract assertion that KLK2 is a cell surface target with relevance for prostate cancer therapy (co-cited alongside STEAP1). Secondary-level corroboration of surface accessibility claim from an independent source. (https://pubmed.ncbi.nlm.nih.gov/42189191/)
  - *assay*: Human
  > "KLK2 and STEAP1 are two cell surface targets with relevance for prostate cancer therapy."
- `a1_evi_09` · *Secondary* · Supports · Surface Expression — Figure legend heading 'Cell surface expression of KLK2' from PMC12580770 directly indexes a figure dedicated to KLK2 surface localization data; supports the overall claim that the paper presents primary cell-surface evidence. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · VCaP · unspecified · non-permeabilized
  > "Cell surface expression of KLK2."
- `a1_evi_10` · *Primary* · Supports · Surface Expression — Cell surface binding of the anti-KLK2 antibody detected at 60 minutes in the PMC12580770 kinetics experiment, with intracellular accumulation noted separately. This documents antibody engagement at the plasma membrane (surface-accessible epitope) at early timepoints before internalization, supporting cell surface accessibility. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · VCaP · live · non-permeabilized
  > "Cell surface binding of the anti-KLK2 antibody was detected at 60 minutes with intracellu…"
- `a1_evi_11` · *Secondary* · Refutes · Contradictory — The study authors explicitly note that KLK2 was not previously recognized as a therapeutic target due to 'limited evidence of its cell surface expression', establishing the historical context that this paper directly addresses and contradicts. This is a meta-level acknowledgment of the prior contradictory view (secreted-only, no surface evidence). ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human
  > "However, it was not recognized as a therapeutic target for prostate cancer in the past due to limited evidence of its cell surface expression."
- `a1_evi_12` · *Primary* · Ambiguous · Surface Expression — KLK2 identified in a cell surface mass spectrometry (surfaceome MS/surface proteome) study with decreased abundance in the surface proteome. This provides MS-level evidence that KLK2 peptides were detected in a surface-enriched fraction, though the decreased abundance finding is ambiguous regarding constitutive surface presence. ([PMC12161487](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12161487/))
  - *assay*: Human · unspecified · unspecified · non-permeabilized
  > "We also identified a decreased abundance of proteases that are involved in coagulation and angiogenesis (e.g., KLK2, CTSB, MMP2, Figure a)."
- `a1_evi_13` · *Secondary* · Ambiguous · Tissue Expression — KLK2 described as an androgen-driven AR target gene encoding a secreted protein, used as a marker for prostate cancer screening and prognosis. This is a non-surface expression observation (secretion context) — KLK2 is classified here as a secreted protein, qualifying surface claims as contested. Feeds non_surface_expression bucket. ([PMC11259169](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11259169/))
  - *assay*: Human
  > "Androgen-driven AR target genes include secreted proteins [kallikrein related peptidase 2 ( KLK2 ) and 3 ( KLK3 ); markers for prostate cancer screening and prognosis ( 30 , 31 )], proto-oncogenes { TMPRSS2 when fused with ERG ( 5 ) and growth factors [insulin-like growth factor 1 receptor ( 32 )]}, modulators of phosphatidylinositol 3-kinase (PI3K)/Akt and Notch signaling [ FKBP5 ( 33 ) and JAG1 ( 34 )], and transcription factors/tumor suppressors [NK3 Homeobox 1 ( NKX3.1 ) ( 35 , 36 ), ZBTB10 ( 37 ), and ZBTB16 ( 38 )]."
- `a1_evi_14` · *Secondary* · Ambiguous · Surface Expression — KLK2 is secreted by androgen-responsive LNCaP prostate adenocarcinoma cells following androgen stimulation, as evidenced by detection in conditioned medium (CM) by SDS-PAGE. This documents the secreted/shed form of KLK2 in the extracellular milieu; the soluble secreted pool is the dominant species detected here, feeding risks.secreted_form. The surface pool is not assessed in this assay. ([PMC9282638](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9282638/))
  - *assay*: Human · LNCaP
  > "LNCaP is an androgen-responsive human prostate adenocarcinoma cell line widely used to model key features of clinical disease, including secretion of KLK2 and KLK3 following androgen stimulation. 8 LNCaP CM was treated with different concentrations of 3 for 1 h, and proteins were separated by SDS–PAGE."
- `a1_evi_15` · *Secondary* · Refutes · Topology — KLK family members described as homologous secreted serine proteases with trypsin- or chymotrypsin-like activities and tissue-specific expression (15 members known). This is a topology/biology statement establishing that KLKs, including KLK2, are canonical secreted proteases without transmembrane domains — relevant context qualifying surface-expression claims. ([PMC12791160](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12791160/))
  - *assay*: Human
  > "To date, 15 KLKs that are homologous secreted serine proteases with trypsin‐ or chymotrypsin‐like activities with tissue‐specific expressions have been discovered [ 6 ]."
- `a1_evi_16` · *Secondary* · Refutes · Topology — KLK2 (human glandular kallikrein) gene encodes a preproprotein of 261 amino acids; signal peptide cleavage yields a mature ~237 aa protein. This establishes the topology: signal peptide present (aa 1-24 cleaved), no transmembrane domain, consistent with a secreted protein. ECD = 237 aa, ICD = 0, no TM helices. (https://pubmed.ncbi.nlm.nih.gov/2824146/)
  - *assay*: Human
  > "The gene encoded a unique preproprotein of 261 amino acids."
- `a1_evi_17` · *Secondary* · Supports · Surface Expression — Therapeutic engagement of KLK2: recombinant protease inhibitor MDPK67b (a variant of ACT6.7) targets KLK2 and other trypsin-like KLKs (KLK4, KLK14) in PCa cell lines in vitro. This is a preclinical inhibitor program targeting the surface-exposed/secreted protease domain of KLK2 for anti-tumor activity. Program stage: preclinical in vitro. Sponsor/developer: academic (inhibitor developed via phage display). ([PMC12791160](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12791160/))
  - *assay*: Human · PCa cell lines
  > "By inhibition with the recombinant protease inhibitor MDPK67b targeting KLK2 and other trypsin-like KLKs including KLK4 and KLK14, we investigated the antitumor response and the influence on AR downstream target genes with MDPK67b in PCa cell lines in vitro.<h4>Methods</h4>Human PCa cells were cultured in a charcoal-stripped media and treated with MDPK67b (0.75 mg/mL)."
- `a2_evi_01` · *Secondary* · Supports · Tissue Expression — KLK2 is a prostate-specific antigen expressed across the prostate cancer disease continuum, establishing strong tissue-restricted expression in prostate tissue and prostate cancer. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · prostate cancer tissue
  > "Human kallikrein 2 (KLK2) is a prostate-specific antigen expressed across the prostate cancer disease continuum."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — KLK2 expression is restricted to normal prostatic tissues and prostate adenocarcinoma with little-to-no expression in non-prostate tissues, confirming high prostate specificity across a multi-tissue expression panel. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · normal prostate and prostate adenocarcinoma
  > "Consistent with previous reports, KLK2 expression was restricted to normal prostatic tissues and prostate adenocarcinoma with little-to-no expression outside the prostate ( Fig. 1A )."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — KLK2 expression is highly prostate-specific in contrast to PSMA, PSCA, and STEAP1, which show broader tissue distribution; this specificity makes KLK2 a preferential prostate-restricted target. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · prostate cancer tissue vs multiple non-prostate tissues
  > "In contrast to the expression of well-established prostate cancer targets (PSMA, PSCA, and STEAP1), KLK2 expression is highly prostate-specific ( 21 , 22 )."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — KLK2 is robustly and homogeneously expressed in localized prostate cancer (LPC) and metastatic hormone-sensitive prostate cancer (mHSPC), but shows heterogeneity in visceral lesions of metastatic castration-resistant prostate cancer (mCRPC), establishing disease-state-dependent expression across the prostate cancer continuum. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · LPC, mHSPC, mCRPC tumor tissue
  > "The preclinical efficacy of three KLK2-targeting therapeutics was characterized using in vitro prostate cancer cell lines, patient-derived material, and in vivo xenograft mouse models.<h4>Results</h4>KLK2 was found to be robustly and homogeneously expressed in localized prostate cancer and metastatic hormone-sensitive prostate cancer, whereas some heterogeneity was observed in the visceral lesions of metastatic castration-resistant prostate cancer."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — KLK2 expression is strongly enriched in AR-positive prostate tumors and is largely absent in neuroendocrine and double-negative prostate cancer phenotypes (mCRPC), indicating AR-driven cell-state-dependent expression. (https://pubmed.ncbi.nlm.nih.gov/42189191/)
  - *assay*: Human · AR+ prostate tumor cells, neuroendocrine PCa cells, double-negative PCa cells
  > "The objective of this study was to characterize the expression landscape of KLK2 and STEAP1 in metastatic castration-resistant prostate cancer (mCRPC) and to define associated transcriptomic, genomic, and epigenomic features."
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — Within AR+ prostate tumors, KLK2 shows high co-expression with STEAP1 and PSMA; pairwise co-targeting any two of these antigens increases overall tumor coverage, implying KLK2 surface availability correlates with AR+ cell state. (https://pubmed.ncbi.nlm.nih.gov/42189191/)
  - *assay*: Human · AR+ prostate tumor cells
  > "Within AR+ tumors, pairwise comparisons revealed co-expression and high combined positivity rates for STEAP1, KLK2, and PSMA, suggesting that co-targeting any two of these antigens increases overall tumor coverage."
- `a2_evi_07` · *Primary* · Ambiguous · Tissue Expression — In a rapid autopsy mCRPC cohort, KLK2 shows comparable degrees of intra- and inter-tumoral expression heterogeneity to STEAP1, indicating spatial variability of KLK2 expression within metastatic disease. (https://pubmed.ncbi.nlm.nih.gov/42189191/)
  - *assay*: Human · mCRPC rapid autopsy tumor specimens · fixed
  > "Analysis of samples from a rapid autopsy cohort, which enabled assessment of intra- and inter-tumoral diversity, showed comparable degrees of expression heterogeneity for KLK2 and STEAP1."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — KLK2 antigen expression in prostate cancer correlates positively with AR genomic alterations and serum PSA levels, and negatively with RB1 and PTEN loss, indicating AR pathway activation state modulates KLK2 expression levels. (https://pubmed.ncbi.nlm.nih.gov/42189191/)
  - *assay*: Human · prostate cancer tumor tissue
  > "Antigen expression correlated positively with AR genomic alterations and serum PSA levels, and negatively with RB1 and PTEN loss."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — KLK2 expression exhibits strict AR dependence with coordinated AR/FOXA1/HOXB13 binding and enhancer activation, distinguishing it from STEAP1 which is only partially AR-dependent; this mechanistic basis underpins cell-state-driven modulation of KLK2 levels in prostate cancer. (https://pubmed.ncbi.nlm.nih.gov/42189191/)
  - *assay*: Human · prostate cancer tumor tissue
  > "Transcriptomic and epigenome analyses demonstrated distinct mechanisms governing antigen expression: KLK2 showed a strict AR dependence with coordinated AR/FOXA1/HOXB13 binding and enhancer activation, whereas STEAP1 was only partially AR-dependent and additionally regulated by locus-specific DNA methylation changes."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — A large single-cell transcriptomics atlas (~1 million cells, 213 patients) integrated with PDX models was used to systematically characterize KLK2 as a surfaceome target across the prostate cancer continuum including hormone-sensitive, castration-resistant, neuroendocrine, and double-negative subtypes. (https://pubmed.ncbi.nlm.nih.gov/42053993/)
  - *assay*: Human · prostate cancer cells across PCa subtypes
  > "We aimed to identify the most promising clinically relevant PCa targets using RNA and protein expression levels across the PCa continuum-hormone-sensitive, castration-resistant, neuroendocrine, and "double-negative" prostate cancer (DNPC).<h4>Experimental design</h4>We performed integration of a large single-cell transcriptomics atlas (JHU-PANORAMA, ~1 million cells and 213 patients) and PDX models for systematic investigation of clinically relevant surfaceome, followed by proteomic validation on patient samples and mechanistic investigations on PCa cell lines and patient"
- `a2_evi_11` · *Primary* · Supports · Tissue Expression — LNCaP prostate adenocarcinoma cells secrete KLK2 (and KLK3) following androgen stimulation, confirming androgen-regulated KLK2 expression in an AR-positive prostate cancer cell line model. ([PMC9282638](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9282638/))
  - *assay*: Human · LNCaP
  > "LNCaP is an androgen-responsive human prostate adenocarcinoma cell line widely used to model key features of clinical disease, including secretion of KLK2 and KLK3 following androgen stimulation. 8 LNCaP CM was treated with different concentrations of 3 for 1 h, and proteins were separated by SDS–PAGE."
- `a2_evi_12` · *Primary* · Supports · Tissue Expression — KLK2 protein is upregulated in cerebrospinal fluid of patients with leptomeningeal metastasis from leukemia compared to other pathologies, suggesting disease-state-dependent expression in a non-prostate tumor microenvironment context. ([PMC8773653](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8773653/))
  - *assay*: Human · cerebrospinal fluid from leptomeningeal metastasis patients
  > "This difference is mainly found in proteins functionally related to each pathology, for example: sCD44, HIF1A, ZMYM3 or PTPRC for CSF + LM in lymphoma and S100A9, TRAF3, KLK3, KLK2, PTPRC, among others, in the case of CSF + LM in leukemia ( Table S7 )."
- `a2_evi_13` · *Primary* · Supports · Surface Expression — Although KLK2 is traditionally described as a secreted protease, the study demonstrates its cell surface expression in both prostate cancer cell lines and patient-derived tumors, representing a key finding that challenges the secreted-only paradigm. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · prostate cancer cell lines and patient-derived mCRPC tumors · live · non-permeabilized
  > "Although KLK2 is traditionally described as a secreted protease, our results demonstrated its cell surface expression in both prostate cancer cell lines and patient-derived tumors."
- `a2_evi_14` · *Primary* · Supports · Surface Expression — Cell surface expression of KLK2 was confirmed by FACS on VCaP prostate cancer cells and on dissociated patient-derived mCRPC tumor cells, demonstrating plasma membrane-accessible KLK2 in both a cell line model and primary human tumor material. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · VCaP and mCRPC dissociated tumor cells · live · non-permeabilized
  > "Cell surface expression of KLK2 was confirmed by FACS of VCaP cells ( Fig. 2A ) and dissociated mCRPC tumor cells ( Fig. 2B )."
- `a2_evi_15` · *Primary* · Supports · Surface Expression — KLK2 cell surface expression in fresh mCRPC tumor samples from patients was assessed by flow cytometry, validating surface accessibility of KLK2 protein on intact non-permeabilized tumor cells in primary human patient material. ([PMC12580770](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12580770/))
  - *assay*: Human · fresh mCRPC tumor samples · live · non-permeabilized
  > "KLK2 cell surface expression in fresh tumor samples of patients with mCRPC was assessed by flow cytometry using an anti-KLK2 antibody."
- `a2_evi_16` · *Primary* · Supports · Surface Expression — KLK2 treatment of bone marrow-derived macrophages (BMDM) caused a significant reduction of IL-10R2 surface levels as detected by FACS, demonstrating that KLK2 as an exogenous protease can modulate surface receptor availability on macrophages in a condition-dependent manner. ([PMC11339918](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11339918/))
  - *assay*: Mouse · bone marrow-derived macrophages (BMDM) · live · non-permeabilized
  > "Compared to the control group, BMDM cells treated with KLK2 showed a significant reduction of IL-10R2 on the surface, as detected by flow cytometry (FACS analysis) ( Figure 2 ), indicating that KLK2 acts directly on IL-10R2."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/KLK2.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/KLK2](https://surfaceome.deliverome.org/KLK2)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/KLK2.json](https://surfaceome.deliverome.org/data/surfaceome/KLK2.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/KLK2.md](https://surfaceome.deliverome.org/data/surfaceome/KLK2.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P20151](https://alphafold.ebi.ac.uk/entry/P20151)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P20151](https://alphafold.ebi.ac.uk/api/prediction/P20151) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P20151](https://www.uniprot.org/uniprotkb/P20151)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-P20151-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-P20151-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-P20151-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-P20151-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-P20151-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-P20151-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*261 aa · `P20151` · embedded at build time*

```
   1  MWDLVLSIALSVGCTGAVPLIQSRIVGGWECEKHSQPWQVAVYSHGWAHCGGVLVHPQWV
  61  LTAAHCLKKNSQVWLGRHNLFEPEDTGQRVPVSHSFPHPLYNMSLLKHQSLRPDEDSSHD
 121  LMLLRLSEPAKITDVVKVLGLPTQEPALGTTCYASGWGSIEPEEFLRPRSLQCVSLHLLS
 181  NDMCARAYSEKVTEFMLCAGLWTGGKDTCGGDSGGPLVCNGVLQGITSWGPEPCALPEKP
 241  AVYTKVVHYRKWIKDTIAANP
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`P20151`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOO
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — — · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — Confidence is moderate for two reasons. First, the surface-expression evidence originates predominantly from a single 2025 research publication (PMC12580770); while that study used rigorous live-cell FACS on both VCaP cells and fresh patient mCRPC tumor specimens, and the surface activity is corroborated by three therapeutic modalities, independent replication by a second research group is not yet documented. Second, the molecular mechanism by which a signal-peptide-only secreted protease is retained at the plasma membrane remains uncharacterized — the docking partner is unknown — introducing uncertainty about the robustness and prevalence of the surface pool relative to the dominant secreted form. Confidence would increase with an independent group confirming live-cell surface staining in a different prostate cancer model, or with biochemical identification of the surface-retention partner.*

## CellxGene RNA enrichment (CZI Census)

*Schema v2.1.6 · CZI Census 2025-11-08 · τ-cutoff classification (Yanai 2005) on linear population mean (mean × pct, ≈ nTPM): τ≥0.85 enriched, 0.5–0.85 enhanced, <0.5 low specificity, no eligibles not detected. Cell ontology graph (cl-basic.obo) walked to ~150 cell-family terms; UBERON ontology walked to ~150 organ-level tissues. Cutoffs follow HPA's tissue-specificity nTPM convention. CC-BY 4.0 (CZI Census).*

**Classification:**

- **Cell class (CL ontology graph, ~10 compartments):** enriched · Epithelial · 47.4× · τ=0.98
- **Cell type (leaf Cell Ontology terms, ~600):** enriched · luminal cell of prostate epithelium · 3.1× · τ=0.93
- **Tissue (UBERON terms, ~56):** enriched · prostate gland · ∞×

**Top 5 cell types (leaf CL, pooled across tissues):**

| Cell type | CL ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| luminal cell of prostate epithelium | CL:0002340 | 3.684 | 53.19% | 17,072 / 32,099 |
| endocrine cell | CL:0000163 | 3.320 | 4.65% | 390 / 8,385 |
| epithelial cell of prostate | CL:0002231 | 3.261 | 26.21% | 2,032 / 7,752 |
| mesothelial fibroblast | CL:4023054 | 2.915 | 0.43% | 1 / 232 | (trace)
| prostate stromal cell | CL:0002622 | 2.900 | 1.59% | 1 / 63 | (trace)

**Top 5 tissues (UBERON, pooled across cell types):**

| Tissue | UBERON ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| prostate gland | UBERON:0002367 | 3.454 | 37.07% | 19,925 / 53,756 |
| urinary bladder | UBERON:0001255 | 2.577 | 0.04% | 6 / 15,201 | (trace)
| intestine | UBERON:0000160 | 2.187 | 0.00% | 1 / 49,900 | (trace)
| adrenal gland | UBERON:0002369 | 2.103 | 0.00% | 11 / 350,623 | (trace)
| pancreas | UBERON:0001264 | 2.071 | 0.01% | 20 / 162,373 | (trace)

<!-- /cellxgene -->
