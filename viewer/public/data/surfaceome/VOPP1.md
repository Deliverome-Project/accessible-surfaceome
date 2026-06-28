# VOPP1 — Surface Accessibility Brief

*Schema v2.13.0 · generated 2026-06-24T17:18:50.227048Z · model `claude-sonnet-4-6`*

> VOPP1 has weak surface evidence; topology suggests a type I single-pass architecture but direct surface readouts are absent. The sole experimental primary evidence (a1_evi_04) is a permeabilized immunofluorescence study showing an intracellular vesicular localization pattern with partial co-localization with perinuclear lysosomes, and a conditioned-media immunoblot confirming the protein is not secreted. Computational topology predictions (a1_evi_01, a1_evi_02) establish a type I TM architecture with an extracellular N-terminus, but no live-cell, non-permeabilized, or surface-biotinylation assay has been reported. Surface presence is not documented in any state; no accessibility modulation data exist, and the protein is consistently described as endomembrane-resident across all cancer contexts examined (a2_evi_03). The principal binder-engineering caveat is intracellular sequestration in endolysosomal vesicles (high-severity restricted subdomain); no shed or secreted form is present, and the absence of paralogs rules out cross-reactivity concerns.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:34518](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:34518) |
| UniProt | [Q96AW1](https://www.uniprot.org/uniprotkb/Q96AW1) |
| NCBI Gene | [81552](https://www.ncbi.nlm.nih.gov/gene/81552) |
| Ensembl | [ENSG00000154978](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000154978) |
| Subcategory | Single-pass type I |
| Surface accessibility | No |
| Confidence | Moderate |
| Evidence grade | Weak |
| Triage signal | Unlikely |

## 1. Executive summary

**VOPP1 is not surface-accessible in any documented state; it resides in intracellular endolysosomal vesicles across all cancer cell contexts examined, with no plasma membrane trafficking reported.**

VOPP1 has weak surface evidence; topology suggests a type I single-pass architecture but direct surface readouts are absent. The sole experimental primary evidence (a1_evi_04) is a permeabilized immunofluorescence study showing an intracellular vesicular localization pattern with partial co-localization with perinuclear lysosomes, and a conditioned-media immunoblot confirming the protein is not secreted. Computational topology predictions (a1_evi_01, a1_evi_02) establish a type I TM architecture with an extracellular N-terminus, but no live-cell, non-permeabilized, or surface-biotinylation assay has been reported. Surface presence is not documented in any state; no accessibility modulation data exist, and the protein is consistently described as endomembrane-resident across all cancer contexts examined (a2_evi_03). The principal binder-engineering caveat is intracellular sequestration in endolysosomal vesicles (high-severity restricted subdomain); no shed or secreted form is present, and the absence of paralogs rules out cross-reactivity concerns.

**Family / classification** — UniProt family: VOPP1/ECOP family · HGNC gene group(s): WBP1/VOPP1 family · functional class: Miscellaneous.

**Triage first-pass reasoning** — VOPP1 (ECop/GASP) is annotated as resident in cytoplasmic vesicle membranes, late endosomes, and lysosomes — all intracellular endomembrane compartments. No isoform has a documented extracellular domain or GPI anchor; it is an intracellular membrane protein. Checking contextual buckets: (1) cell_state_induced — no reported stress/activation-induced PM translocation; (2) tissue_restricted_surface — no tissue-specific surface display documented; (3) lysosomal_exocytosis — lysosomal exocytosis of VOPP1 to the PM surface has not been reported; (4) dual_localization — no evidence of a stable PM pool alongside the endolysosomal pool; (5) stable_surface_attachment — it is not a secreted protein and no wash-resistant PM anchoring has been described. No antibody/ADC/CAR-T therapeutic program targeting VOPP1 at the cell surface is known. The protein functions intracellularly in vesicular trafficking/ubiquitin pathway; endomembrane compartment localization is well-supported.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=No · conf=Moderate · subcategory=Single-pass type I · ecd=Small |
| Classification | reason=Endomembrane Resident · family=Miscellaneous · state-dependence=Unclear · induction-trigger=None |
| Expression | level=High · breadth=Restricted · specificity=Mostly Intracellular · low-endogenous=false · tumor-associated=true · orphan-receptor=true · OE-precedent=false |
| Risks | shed=false · secreted=false · co-receptor=None · masking=false · restricted-subdomain=true |
| Evidence | grade=Weak · density=Low · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=1 |
| Cross-species | mouse=100.0% · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=1 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: VOPP1 transcript is highly expressed across multiple cancer types including GBM, HNSCC, breast carcinoma, pancreatic carcinoma, and lymphoma by microarray profiling (a2_evi_01, a2_evi_02).
- *Expression breadth*: Expression data are confined to tumor contexts (GBM, HNSCC, breast, pancreatic, lymphoma); no normal-tissue breadth data are available in the evidence (a2_evi_01, a2_evi_02).
- *Surface specificity*: Permeabilized IF and conditioned-media immunoblot consistently place VOPP1 in intracellular endolysosomal vesicles with no plasma membrane signal detected (a1_evi_04, a2_evi_03).
- *Known ligand*: No validated endogenous binding partner or ligand is reported for VOPP1. The protein functions in vesicular trafficking/ubiquitin pathways intracellularly; no cognate receptor or natural agonist has been characterized.
- *Low endogenous expression*: VOPP1 transcript is highly expressed across multiple cancer types including GBM, HNSCC, breast carcinoma, pancreatic carcinoma, and lymphoma by microarray profiling (a2_evi_01, a2_evi_02).
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Weak

The ledger contains zero direct surface-accessibility observations. The only experimental primary evidence (a1_evi_04) is a permeabilized immunofluorescence study in human cell lines showing VOPP1 in an intracellular vesicular pattern with partial co-localization with perinuclear lysosomes; a conditioned-media immunoblot confirmed the protein is not secreted. This directly contradicts plasma membrane surface accessibility. The remaining three claims (a1_evi_01, a1_evi_02, a1_evi_03) are computational topology predictions and ER-bound mRNA microarray data — they establish a type I TM architecture synthesized into the ER but provide no evidence of PM delivery. No live-cell flow, non-permeabilized IF, surface biotinylation, or functional surface assay is present. The methods builder emitted only one row (permeabilized IF, expression_only). Grade: weak.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Low | Computational topology prediction (type I TM, extracellular N-terminus) — no experimental surface assay. |
| a1_evi_02 | Tangential | Low | Computational prediction of cytoplasmic C-terminus / extracellular N-terminus — no experimental surface assay. |
| a1_evi_03 | Tangential | Low | Sequence-based topology + ER-bound mRNA microarray; supports ER synthesis but not PM residence. |
| a1_evi_04 | Contradicts Surface | High | Permeabilized IF + conditioned-media immunoblot: intracellular vesicular/lysosomal localization, not secreted, not PM. |

### Immunofluorescence (1 method)

#### Permeabilized IF — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Mixed*

**Antibodies**

- anti-VOPP1 — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human cell lines expressing recombinant and native VOPP1; intracellular vesicular localization with partial co-localization with perinuclear lysosomes; not secreted into conditioned media | Established Cell Line | Moderate | 1 |

*Overexpression construct* — SP source: Unspecified · tag: fluorescence reporter. *(cites: a1_evi_04)*

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Human cancer cell lines — VOPP1 mRNA highly expressed in breast carcinoma, pancreatic carcinoma, lymphoma (Oncomine microarray); ER-bound mRNA microarray consistent with ER synthesis | Established Cell Line | RNA | High | 1 |
| Human cell lines — permeabilized IF showing intracellular vesicular/lysosomal localization; conditioned-media immunoblot confirming no secretion | Established Cell Line | Bulk Protein | Moderate | 1 |

**Contradicting evidence**

- *Alternative Localization* (severity High): Immunoblot of conditioned media confirms VOPP1 is not secreted and is retained intracellularly. Fluorescence reporter-tagged and antibody-visualized VOPP1 (both recombinant and native) display an intracellular vesicular localization pattern with partial co-localization with perinuclear lysosomes but not mitochondria or peroxisomes. This directly contradicts plasma membrane surface accessibility, placing the protein in an intracellular vesicular compartment.
  - Likely explanation: VOPP1 appears to reside predominantly in intracellular vesicles (partially lysosomal), with no evidence of plasma membrane trafficking. The permeabilized fixation used in the IF assay would detect all intracellular pools; the absence of any surface signal and the confirmed non-secreted status together strongly argue against meaningful surface accessibility under basal conditions.

## 4. Biological context

**Biological-context grade** · Moderate

Expression mapped across ≥5 cancer types (GBM, HNSCC, breast, pancreatic, lymphoma) from two sources. Subcellular localization is well-pinned (intracellular vesicular/endolysosomal, not PM) by IF and immunoblot. Topology prediction adds structural support. Anatomical/modulation axes are absent. Single publication dominates; no normal-tissue or state-modulation data. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04)*

**Expression × cell type × disease context**

| Tissue | Cell type | Disease context | Level (protein) | Cell states |
|---|---|---|---|---|
| brain | — | Tumor (glioblastoma multiforme) | High | — |
| head and neck | — | Tumor (squamous cell carcinoma) | High | — |
| breast | — | Tumor (breast carcinoma) | High | — |
| pancreas | — | Tumor (pancreatic carcinoma) | High | — |
| lymphoid tissue | — | Tumor (lymphoma) | High | — |

**Primary subcellular compartment**: Endosome

**Dual localization**

- Lysosome · partial co-localization, perinuclear pool *(cites: a2_evi_03)*
- ER · during biosynthesis / transit *(cites: a2_evi_02)*

**Restricted-subdomain distribution**

- present: true
- severity: High
- evidence: Strong
- domain: Other
- rationale: VOPP1 localizes to intracellular vesicles (endolysosomal compartment) with partial co-localization with perinuclear lysosomes, not the plasma membrane (a1_evi_04, a2_evi_03). Topology predictions confirm endomembrane orientation (a2_evi_04). Surface accessibility to a systemic binder is severely compromised.
- cites: a1_evi_04, a2_evi_03, a2_evi_04

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: VOPP1 is a single-pass type I TM protein that traffics independently through the ER secretory pathway (a1_evi_03, a2_evi_02). No obligate escort or chaperone partner is documented. The protein reaches endomembranes without a named co-receptor (a1_evi_04, a2_evi_03).
- cites: a1_evi_03, a1_evi_04, a2_evi_02, a2_evi_03

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | Q96AW1 | ref | ref | 1 | 38 aa | 91 aa | 22 aa | Extracellular→Cytoplasmic | — |
| Isoform | Q96AW1-2 | Q96AW1-2 | 91.9% | 74.0% | 1 | 50 aa | 99 aa | 0 aa | Extracellular→Cytoplasmic | — |
| Isoform | Q96AW1-3 | Q96AW1-3 | 91.9% | 97.4% | 1 | 37 aa | 99 aa | 19 aa | Extracellular→Cytoplasmic | — |
| Isoform | Q96AW1-4 | Q96AW1-4 | 90.1% | 88.1% | 1 | 42 aa | 99 aa | 0 aa | Extracellular→Cytoplasmic | — |
| Mouse ortholog | Vopp1 | [Q8R1C3](https://www.uniprot.org/uniprotkb/Q8R1C3) | 89.5% | 100.0% | 1 | 38 aa | — | — | — | high (≥85%) |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak
- rationale: No relevant data in the ledger. Immunoblot of conditioned media confirms VOPP1 is not secreted (a1_evi_04, a2_evi_03); no sheddase cleavage of the VOPP1 ectodomain is documented.
- cites: a1_evi_04, a2_evi_03

**Secreted form**

- present: false
- severity: Low
- evidence: Strong
- rationale: Immunoblot of cell culture conditioned media explicitly confirms VOPP1 protein is not secreted and is retained intracellularly (a1_evi_04, a2_evi_03). No soluble splice isoform or shed ectodomain is documented in the ledger.
- cites: a1_evi_04, a2_evi_03

**ECD size assessment**

- ECD class: Small
- rationale: ECD length 38 residues (30-59) -> small; computed deterministically from DeepTMHMM topology.

**Epitope masking**

- severity: None
- evidence: Weak
- mechanism: None
- rationale: No epitope masking by partner, glycan, or oligomerization is documented in the ledger. The deterministic AF2 prior indicates no homo-oligomer (is_homo_oligomer=false). The primary accessibility concern is intracellular sequestration (a1_evi_04, a2_evi_03), not epitope masking per se. The small ECD (38 aa) limits epitope surface but no masking mechanism is evidenced.

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-Q96AW1-F1](https://alphafold.ebi.ac.uk/entry/Q96AW1) |
| AFDB version | v6 |
| ECD mean pLDDT | 82.0 |
| ECD disordered fraction | 10.5% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/Q96AW1) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [Q96AW1](https://alphafold.ebi.ac.uk/entry/Q96AW1) | AlphaFold DB (AF-Q96AW1-F1, v6) |
| Isoform Q96AW1-2 | [Q96AW1-2](https://alphafold.ebi.ac.uk/entry/Q96AW1-2) | AlphaFold DB |
| Isoform Q96AW1-3 | [Q96AW1-3](https://alphafold.ebi.ac.uk/entry/Q96AW1-3) | AlphaFold DB |
| Isoform Q96AW1-4 | [Q96AW1-4](https://alphafold.ebi.ac.uk/entry/Q96AW1-4) | AlphaFold DB |
| Mouse ortholog (Vopp1) | [Q8R1C3](https://alphafold.ebi.ac.uk/entry/Q8R1C3) | AlphaFold DB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

8 entries · 2 primary · 6 secondary · 0 tertiary · 3 PMC OA.

- `a1_evi_01` · *Secondary* · Supports · Topology — The GASP/WBP1/VOPP1 family proteins share a domain architecture comprising a predicted signal peptide, an N-terminal cysteine-rich domain with eight conserved cysteines, a single predicted transmembrane segment, and a proline-rich C-terminal cytosolic region — establishing VOPP1 as a single-pass type I transmembrane protein with a short extracellular N-terminus. ([PMC3295595](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3295595/))
  - *assay*: Human
  > "For Shisa proteins from subfamilies 1–5, several cysteines residues are present near the C-termini of their predicted TMs ( Figure 2 ), possibly providing sites for lipid modifications such as palmitoylation to facilitate their localization to specific membrane microdomains [ 41 ]."
- `a1_evi_02` · *Secondary* · Supports · Topology — VOPP1 family members are predicted to be type I transmembrane proteins with their proline-rich, mostly disordered C-terminal regions residing in the cytosol, confirming cytoplasmic C-terminus and extracellular N-terminus orientation. ([PMC3295595](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3295595/))
  - *assay*: Human
  > "They are predicted to be type I transmembrane proteins with their proline-rich, mostly disordered C-terminal regions residing in the cytosol."
- `a1_evi_03` · *Secondary* · Supports · Topology — Sequence analysis of VOPP1 identifies both a signal sequence and a transmembrane domain; microarray data for ER-bound mRNA transcripts is consistent with VOPP1 being synthesized into the ER, supporting a type I TM topology but not plasma membrane residence. (https://pubmed.ncbi.nlm.nih.gov/20571887/)
  - *assay*: Human
  > "A query of a public database of gene expression profiling data (Oncomine) shows that the VOPP1 transcript is also highly expressed in several other common human cancers, including breast carcinoma, pancreatic carcinoma, and lymphoma. Analysis of VOPP1 sequence structure shows both a signal sequence and a transmembrane domain, and examination of a public microarray dataset for endoplasmic reticulum (ER)-bound mRNA transcripts is consistent with the VOPP1 protein product being synthesized into the ER."
- `a1_evi_04` · *Primary* · Refutes · Contradictory — Immunoblot analysis of cell culture conditioned media confirms VOPP1 protein is NOT secreted and is retained intracellularly. Fluorescence reporter-tagged VOPP1 and antibody-mediated visualization of both recombinant and native VOPP1 reveal an intracellular vesicular localization pattern with partial co-localization with perinuclear lysosomes but not mitochondria or peroxisomes — directly contradicting plasma membrane surface accessibility. (https://pubmed.ncbi.nlm.nih.gov/20571887/)
  - *assay*: Human · fixed · permeabilized
  > "Immunoblot analysis of cell culture and conditioned media confirms that the protein product is not secreted and is retained intracellularly. VOPP1 protein tagged with a fluorescence reporter, as well as antibody-mediated visualization of recombinant and native forms of the protein reveals an intracellular vesicular pattern of localization. Co-localization experiments reveal that VOPP1 vesicles do not co-localize with mitochondria or peroxisomes, but show partial co-localization with perinuclear lysosomes."
- `a2_evi_01` · *Secondary* · Supports · Tissue Expression — VOPP1 mRNA/protein is overexpressed in human glioblastoma multiforme and squamous cell carcinoma relative to normal tissue, conferring a prosurvival phenotype. Disease context: high-grade brain tumor and head/neck squamous carcinoma. (https://pubmed.ncbi.nlm.nih.gov/20571887/)
  - *assay*: Human · glioblastoma multiforme tumor tissue; squamous cell carcinoma tumor tissue
  > "Vesicular Over-expressed in cancer Prosurvival Protein 1 (VOPP1), also known as Glioblastoma Amplified and Secreted Protein and EGFR-Coamplified and Over-expressed Protein has been previously shown to be over-expressed in human glioblastoma multiforme and squamous cell carcinoma. Additionally, previous experimental work suggests that it confers a prosurvival cellular phenotype."
- `a2_evi_02` · *Secondary* · Supports · Tissue Expression — VOPP1 transcript is highly expressed in breast carcinoma, pancreatic carcinoma, and lymphoma based on public gene expression profiling data (Oncomine microarray). The protein has a signal sequence and transmembrane domain and is consistent with ER-bound synthesis, suggesting it enters the secretory pathway but is retained intracellularly rather than reaching the plasma membrane. (https://pubmed.ncbi.nlm.nih.gov/20571887/)
  - *assay*: Human · breast carcinoma; pancreatic carcinoma; lymphoma tumor samples
  > "A query of a public database of gene expression profiling data (Oncomine) shows that the VOPP1 transcript is also highly expressed in several other common human cancers, including breast carcinoma, pancreatic carcinoma, and lymphoma. Analysis of VOPP1 sequence structure shows both a signal sequence and a transmembrane domain, and examination of a public microarray dataset for endoplasmic reticulum (ER)-bound mRNA transcripts is consistent with the VOPP1 protein product being synthesized into the ER."
- `a2_evi_03` · *Primary* · Refutes · Surface Expression — VOPP1 protein is not secreted and is retained intracellularly; fluorescence reporter and antibody-based visualization reveal an intracellular vesicular localization pattern with partial co-localization with perinuclear lysosomes but not mitochondria or peroxisomes. This directly refutes plasma membrane surface presence: the protein localizes to endolysosomal vesicles, not the cell surface. (https://pubmed.ncbi.nlm.nih.gov/20571887/)
  - *assay*: Human · cell culture (cancer cell lines, unspecified) · fixed · permeabilized
  > "Immunoblot analysis of cell culture and conditioned media confirms that the protein product is not secreted and is retained intracellularly. VOPP1 protein tagged with a fluorescence reporter, as well as antibody-mediated visualization of recombinant and native forms of the protein reveals an intracellular vesicular pattern of localization. Co-localization experiments reveal that VOPP1 vesicles do not co-localize with mitochondria or peroxisomes, but show partial co-localization with perinuclear lysosomes."
- `a2_evi_04` · *Secondary* · Ambiguous · Surface Expression — VOPP1 family members (WBP1/VOPP1 superfamily) are predicted to be type I transmembrane proteins with their proline-rich C-terminal regions residing in the cytosol, placing the short N-terminal domain extracellularly. This topology is consistent with endomembrane (endosomal/lysosomal) orientation rather than plasma membrane surface display. ([PMC3295595](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3295595/))
  - *assay*: Human
  > "They are predicted to be type I transmembrane proteins with their proline-rich, mostly disordered C-terminal regions residing in the cytosol."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/VOPP1.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/VOPP1](https://surfaceome.deliverome.org/VOPP1)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/VOPP1.json](https://surfaceome.deliverome.org/data/surfaceome/VOPP1.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/VOPP1.md](https://surfaceome.deliverome.org/data/surfaceome/VOPP1.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/Q96AW1](https://alphafold.ebi.ac.uk/entry/Q96AW1)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/Q96AW1](https://alphafold.ebi.ac.uk/api/prediction/Q96AW1) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/Q96AW1](https://www.uniprot.org/uniprotkb/Q96AW1)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-Q96AW1-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-Q96AW1-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-Q96AW1-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-Q96AW1-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-Q96AW1-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-Q96AW1-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*172 aa · `Q96AW1` · embedded at build time*

```
   1  MRRQPAKVAALLLGLLLECTEAKKHCWYFEGLYPTYYICRSYEDCCGSRCCVRALSIQRL
  61  WYFWFLLMMGVLFCCGAGFFIRRRMYPPPLIEEPAFNVSYTRQPPNPGPGAQQPGPPYYT
 121  DPGGPGMNPVGNSMAMAFQVPPNSPQGSVACPPPPAYCNTPPPPYEQVVKAK
```

### Alternative-isoform sequences

**Q96AW1-2** (`Q96AW1-2` · 163 aa)

```
   1  MRRTGSHAQCTEAKKHCWYFEGLYPTYYICRSYEDCCGSRCCVRALSIQRLWYFWFLLMM
  61  GVLFCCGAGFFIRRRMYPPPLIEEPAFNVSYTRQPPNPGPGAQQPGPPYYTDPGGPGMNP
 121  VGNSMAMAFQVPPNSPQGSVACPPPPAYCNTPPPPYEQVVKAK
```

**Q96AW1-3** (`Q96AW1-3` · 169 aa)

```
   1  MLSETLGYLSSVLLQCTEAKKHCWYFEGLYPTYYICRSYEDCCGSRCCVRALSIQRLWYF
  61  WFLLMMGVLFCCGAGFFIRRRMYPPPLIEEPAFNVSYTRQPPNPGPGAQQPGPPYYTDPG
 121  GPGMNPVGNSMAMAFQVPPNSPQGSVACPPPPAYCNTPPPPYEQVVKAK
```

**Q96AW1-4** (`Q96AW1-4` · 155 aa)

```
   1  MCTEAKKHCWYFEGLYPTYYICRSYEDCCGSRCCVRALSIQRLWYFWFLLMMGVLFCCGA
  61  GFFIRRRMYPPPLIEEPAFNVSYTRQPPNPGPGAQQPGPPYYTDPGGPGMNPVGNSMAMA
 121  FQVPPNSPQGSVACPPPPAYCNTPPPPYEQVVKAK
```

### Canonical ortholog sequences

**Mouse — Vopp1** (`Q8R1C3` · 172 aa)

```
   1  MGRRLGRVAALLLGLLVECTEAKKHCWYFEGLYPTYYICRSYEDCCGSRCCVRALSIQRL
  61  WYFWFLLMMGVLFCCGAGFFIRRRMYPPPLIEEPTFNVSYTRQPPNPAPGAQQMGPPYYT
 121  DPGGPGMNPVGNTMAMAFQVQPNSPHGGTTYPPPPSYCNTPPPPYEQVVKDK
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`Q96AW1`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  MMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Q96AW1-2** (`Q96AW1-2`, deeptmhmm-1.0.24)

```
   1  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMM
  61  MMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Q96AW1-3** (`Q96AW1-3`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMM
  61  MMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Q96AW1-4** (`Q96AW1-4`, deeptmhmm-1.0.24)

```
   1  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Mouse ortholog — Vopp1** (`Q8R1C3`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  MMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — Confidence is moderate rather than low because the intracellular localization call is well-supported by direct experimental evidence — permeabilized immunofluorescence and conditioned-media immunoblot from PMID:20571887 consistently place VOPP1 in endolysosomal vesicles with no plasma membrane signal. However, the entire experimental record derives from a single publication and research group; independent corroboration using orthogonal methods (live-cell non-permeabilized staining, surface biotinylation, or cell-surface proteomics) has not been reported. The first-pass classifier's endomembrane-resident verdict aligns with this conclusion. Lifting confidence to high would require a second independent group to confirm the intracellular-only localization, ideally with a non-permeabilized assay that explicitly rules out any plasma membrane pool.*
