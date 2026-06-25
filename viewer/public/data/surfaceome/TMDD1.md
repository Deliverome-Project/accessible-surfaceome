# TMDD1 — Surface Accessibility Brief

*Schema v2.13.0 · generated 2026-06-24T17:17:41.621156Z · model `claude-sonnet-4-6`*

> TMDD1 has weak surface evidence; topology suggests a single-pass Type I membrane protein with a 194-residue extracellular domain, but direct surface readouts are absent. The sole evidence (a1_evi_01) is an abstract-level assertion from a functional study in LUAD cells describing TMDD1 as a membrane protein whose cytoplasmic domain mediates intracellular signaling — no live-cell flow, surface biotinylation, or non-permeabilized IF was reported. State-dependence is unclear: expression context is limited to LUAD tumor cells (a2_evi_01), with no modulation data across other cell states or tissues. No binder-engineering caveats emerged — no shed or secreted form, no co-receptor requirement, no epitope masking, and no paralogs rule out decoy and cross-reactivity concerns.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:53646](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:53646) |
| UniProt | [P0DPE3](https://www.uniprot.org/uniprotkb/P0DPE3) |
| NCBI Gene | [112163659](https://www.ncbi.nlm.nih.gov/gene/112163659) |
| Ensembl | [ENSG00000284730](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000284730) |
| Subcategory | Single-pass type I |
| Surface accessibility | Low |
| Confidence | Low |
| Evidence grade | Weak |
| Triage signal | Possibly Accessible |

## 1. Executive summary

**Topology predicts extracellular exposure in membrane-expressing cells, but surface accessibility has not been experimentally confirmed; the only documented context is LUAD tumor cells (a2_evi_01).**

TMDD1 has weak surface evidence; topology suggests a single-pass Type I membrane protein with a 194-residue extracellular domain, but direct surface readouts are absent. The sole evidence (a1_evi_01) is an abstract-level assertion from a functional study in LUAD cells describing TMDD1 as a membrane protein whose cytoplasmic domain mediates intracellular signaling — no live-cell flow, surface biotinylation, or non-permeabilized IF was reported. State-dependence is unclear: expression context is limited to LUAD tumor cells (a2_evi_01), with no modulation data across other cell states or tissues. No binder-engineering caveats emerged — no shed or secreted form, no co-receptor requirement, no epitope masking, and no paralogs rule out decoy and cross-reactivity concerns.

**Family / classification** — functional class: Miscellaneous.

**Triage first-pass reasoning** — TMDD1 (C12orf81) encodes a protein named 'transmembrane and death domain 1,' implying a single-pass or multi-pass TM domain plus an intracellular death domain. UniProt P0DPE3 is annotated as membrane-located. With a TM domain, the protein would be inserted into the PM with at least short extracellular loops or an ectodomain accessible from outside. However, experimental surface evidence (flow cytometry, surface biotinylation) is absent from the literature for this poorly characterized gene. Checking contextual buckets: cell_state_induced — possible but no specific data; tissue_restricted_surface — expression pattern unknown; lysosomal_exocytosis — no evidence; dual_localization — plausible if predominantly intracellular membrane; stable_surface_attachment — no data. Given the TM annotation and 'death domain' motif (typically cytoplasmic signaling), the extracellular-facing portion may be minimal or absent, but a TM protein does present loops at the outer face. Calling contextual/dual_localization given uncertainty about whether PM pool is dominant vs. endomembrane resident.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=Low · conf=Low · subcategory=Single-pass type I · ecd=Moderate |
| Classification | reason=Other · family=Miscellaneous · state-dependence=Unclear · induction-trigger=None |
| Expression | level=Low · breadth=Rare · specificity=Mixed · low-endogenous=true · tumor-associated=true · orphan-receptor=true · OE-precedent=false |
| Risks | shed=false · secreted=false · co-receptor=None · masking=false · restricted-subdomain=false |
| Evidence | grade=Weak · density=Low · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=1 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: Only a single abstract-level report places TMDD1 in LUAD tumor cells (a2_evi_01); no quantitative expression data (RNA-seq, proteomics) are available in the ledger.
- *Expression breadth*: Expression context is limited to lung adenocarcinoma tumor cells in one study (a2_evi_01); no pan-tissue or multi-tissue expression data are present in the ledger.
- *Surface specificity*: Canonical topology predicts a plasma membrane single-pass protein, but the only functional evidence highlights cytoplasmic-domain intracellular signaling (a1_evi_01), leaving the surface vs. intracellular distribution unresolved.
- *Known ligand*: No validated endogenous binding partner is reported in the ledger. TMDD1 is a poorly characterized protein with no deorphanized ligand; the sole evidence (a1_evi_01) describes intracellular cytoplasmic-domain interactions, not an extracellular receptor-ligand pairing.
- *Low endogenous expression*: Only a single abstract-level report places TMDD1 in LUAD tumor cells (a2_evi_01); no quantitative expression data (RNA-seq, proteomics) are available in the ledger.
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Weak

The single ledger claim (a1_evi_01) is an abstract-level review assertion from a functional study of Hinokitiol in LUAD cells. It describes TMDD1 as a membrane protein with a functionally important cytoplasmic domain mediating intracellular EP300-KLF15/ZNF384 interactions, but reports no direct surface-localization assay (no live-cell flow, nonperm IF, surface biotinylation, or IHC membranous staining). The claim is classified as `review_assertion` at secondary evidence tier with weak confidence. There are zero direct-surface-methodology observations in the ledger. The topology description is consistent with a single-pass TM protein but does not establish extracellular exposure or PM surface accessibility. Graded `weak` — assertion-only, no surface method evidence.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Low | Abstract-level assertion of membrane protein topology; no surface assay; cytoplasmic domain focus; review_assertion tier. |

## 4. Biological context

**Biological-context grade** · Sparse

Single secondary source, abstract-level only. One axis (tissue expression in LUAD) is partially covered; subcellular localization, anatomical accessibility, and modulation axes are absent. No quantitative data or direct surface localization evidence. *(cites: a2_evi_01)*

**Expression × cell type × disease context**

| Tissue | Cell type | Disease context | Level (protein) | Cell states |
|---|---|---|---|---|
| lung | lung adenocarcinoma cells | Tumor (lung adenocarcinoma (LUAD), including metastatic stage IV) | Unknown | — |

**Primary subcellular compartment**: Plasma membrane

**Restricted-subdomain distribution**

- present: false
- severity: Unknown
- evidence: Weak
- domain: Unknown
- rationale: No relevant data in the ledger. Neither a1_evi_01 nor a2_evi_01 reports subcellular membrane localization (apical/basolateral/junctional/ciliary staining or polarized-epithelium fractionation) for TMDD1. Domain restriction cannot be assessed.

**Co-receptor requirements**

- dependency: None
- evidence basis: Co Expression Only
- rationale: The ledger describes TMDD1 as a single-pass membrane protein whose cytoplasmic domain mediates intracellular interactions (a1_evi_01, a2_evi_01). No co-receptor or trafficking partner requirement for surface expression is mentioned. Single-pass transmembrane proteins typically traffic independently; no obligate escort is documented.
- cites: a1_evi_01, a2_evi_01

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl —. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P0DPE3 | ref | ref | 1 | 194 aa | 73 aa | 24 aa | Extracellular→Cytoplasmic | — |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak
- rationale: No relevant data in the ledger. Neither ledger entry (a1_evi_01, a2_evi_01) documents proteolytic shedding of the TMDD1 ectodomain, identifies a sheddase, or reports a soluble TMDD1 form in supernatant or serum.

**Secreted form**

- present: false
- severity: Low
- evidence: Weak
- rationale: No relevant data in the ledger. The ledger contains no evidence of a soluble splice isoform or free circulating TMDD1 ectodomain. Both entries describe TMDD1 solely as a membrane-anchored protein acting via its cytoplasmic domain (a1_evi_01, a2_evi_01).

**ECD size assessment**

- ECD class: Moderate
- rationale: ECD length 194 residues (60-199) -> moderate; computed deterministically from DeepTMHMM topology.

**Epitope masking**

- severity: None
- evidence: Weak
- mechanism: None
- rationale: No masking mechanism is documented in the ledger. The ledger entries (a1_evi_01, a2_evi_01) focus on the cytoplasmic domain's intracellular interactions; no extracellular complex, glycan shielding, or conformational occlusion of the ECD is described. Deterministic prior shows is_homo_oligomer=false, providing no corroborating oligomerization signal.

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P0DPE3-F1](https://alphafold.ebi.ac.uk/entry/P0DPE3) |
| AFDB version | v6 |
| ECD mean pLDDT | 69.8 |
| ECD disordered fraction | 46.4% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P0DPE3) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P0DPE3](https://alphafold.ebi.ac.uk/entry/P0DPE3) | AlphaFold DB (AF-P0DPE3-F1, v6) |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

2 entries · 0 primary · 2 secondary · 0 tertiary · 0 PMC OA.

- `a1_evi_01` · *Secondary* · Supports · Topology — TMDD1 is described as a membrane protein with a functionally important cytoplasmic domain, consistent with a single-pass transmembrane topology where the C-terminus is intracellular. The cytoplasmic domain mediates interaction with EP300-KLF15/ZNF384 complexes in the context of Hinokitiol anti-tumor activity. No direct surface-localization assay is reported; this is an abstract-level assertion from a functional study. (https://pubmed.ncbi.nlm.nih.gov/40975161/)
  - *assay*: Human · LUAD cell lines
  > "The natural monoterpenoid Hinokitiol inhibits LUAD growth by disrupting EP300-KLF15/ZNF384 interactions, suppressing ISC biogenesis gene expression and inducing ferroptosis. Mechanistically, the membrane protein TMDD1, particularly its cytoplasmic domain, promotes Hinokitiol's anti-tumor effects by facilitating EP300-KLF15/ZNF384 dissociation and inhibiting ISC biogenesis. Remarkably, Hinokitiol exhibits stage-dependent efficacy, with superior suppression of metastatic (stage IV) tumors linked to heightened ferroptosis sensitivity."
- `a2_evi_01` · *Secondary* · Supports · Tissue Expression — TMDD1 is described as a membrane protein expressed in lung adenocarcinoma (LUAD) tumor cells, where its cytoplasmic domain facilitates EP300-KLF15/ZNF384 dissociation and promotes ferroptosis sensitivity, particularly in metastatic (stage IV) LUAD. This abstract-level assertion places TMDD1 in the LUAD tumor context but does not provide quantitative expression data or direct surface localization evidence. (https://pubmed.ncbi.nlm.nih.gov/40975161/)
  - *assay*: Human · lung adenocarcinoma (LUAD) tumor cells
  > "The natural monoterpenoid Hinokitiol inhibits LUAD growth by disrupting EP300-KLF15/ZNF384 interactions, suppressing ISC biogenesis gene expression and inducing ferroptosis. Mechanistically, the membrane protein TMDD1, particularly its cytoplasmic domain, promotes Hinokitiol's anti-tumor effects by facilitating EP300-KLF15/ZNF384 dissociation and inhibiting ISC biogenesis. Remarkably, Hinokitiol exhibits stage-dependent efficacy, with superior suppression of metastatic (stage IV) tumors linked to heightened ferroptosis sensitivity."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/TMDD1.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/TMDD1](https://surfaceome.deliverome.org/TMDD1)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/TMDD1.json](https://surfaceome.deliverome.org/data/surfaceome/TMDD1.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/TMDD1.md](https://surfaceome.deliverome.org/data/surfaceome/TMDD1.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P0DPE3](https://alphafold.ebi.ac.uk/entry/P0DPE3)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P0DPE3](https://alphafold.ebi.ac.uk/api/prediction/P0DPE3) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P0DPE3](https://www.uniprot.org/uniprotkb/P0DPE3)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-P0DPE3-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-P0DPE3-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-P0DPE3-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-P0DPE3-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-P0DPE3-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-P0DPE3-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*317 aa · `P0DPE3` · embedded at build time*

```
   1  MAARTLASALVLTLWVWALAPAGAVDAMGPHAAVRLAELLTPEECGHFRSLLEAPEPDVE
  61  AELSRLSEDRLARPEPLNTTSGSPSRRRRREAAEDPAGRVAGPGEVSDGCREALAAWLAP
 121  QAASLSWDRLARALRRSGRPDVARELGKNLHQQATLQLRKFGQRFLPRPGAAARVPFAPA
 181  PRPRRAAVPAPDWDALQLIVERLPQPLYERSPMGWAGPLALGLLTGFVGALGTGALVVLL
 241  TLWITGGDGDRASPGSPGPLATVQGWWETKLLLPKERRAPPGAWAADGPDSPSPHSALAL
 301  SCKMGAQSWGSGALDGL
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`P0DPE3`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMM
 241  MMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — — · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence low — Confidence is low because the entire evidence base for TMDD1 surface accessibility rests on a single abstract-level assertion from one study (PMID:40975161) describing the protein as a membrane protein in LUAD cells — no direct surface-localization method (live-cell flow cytometry, surface biotinylation, non-permeabilized immunofluorescence) has been reported by any group. The canonical single-pass Type I topology predicts an extracellular domain of 194 residues, but topology prediction alone does not establish plasma membrane accessibility. No mouse or cynomolgus ortholog data exist, and no paralogs are present to triangulate function. Lifting confidence would require at least one independent study using a direct surface-detection method — ideally live-cell flow cytometry or surface biotinylation in a defined cell line — to confirm that the predicted extracellular domain is accessible at the plasma membrane.*
