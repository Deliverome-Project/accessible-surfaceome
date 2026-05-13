# GPR75 — Surface Accessibility Brief

*Schema v1.0.0 · generated 2026-05-13T00:00:00Z · model `mock-placeholder`*

> GPR75 is an orphan class-A GPCR with a short ~41-aa extracellular N-terminal tail and three small extracellular loops. Surface presentation appears constitutive in adipocyte and vascular smooth-muscle contexts, but direct accessibility evidence on endogenously expressed GPR75 is sparse — most surface calls come from tagged overexpression. Headline risks: small ECD limits the accessible epitope footprint, and antibody validation is weak across the field.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:4526](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:4526) |
| UniProt | [O95800](https://www.uniprot.org/uniprotkb/O95800) |
| NCBI Gene | [10936](https://www.ncbi.nlm.nih.gov/gene/10936) |
| Ensembl | [ENSG00000119537](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000119537) |
| Subcategory | GPCR |
| Surface accessibility | Moderate |
| Confidence | Moderate |
| Evidence grade | Supportive but indirect |
| Triage signal | Likely accessible |
| Headline risks | Ecd Too Small, Antibody Validation Weak, Ligand Unknown |

## 1. Executive summary

GPR75 is an orphan class-A GPCR with a short ~41-aa extracellular N-terminal tail and three small extracellular loops. Surface presentation appears constitutive in adipocyte and vascular smooth-muscle contexts, but direct accessibility evidence on endogenously expressed GPR75 is sparse — most surface calls come from tagged overexpression. Headline risks: small ECD limits the accessible epitope footprint, and antibody validation is weak across the field.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=Moderate · conf=Moderate · subcategory=GPCR · grade=Supportive but indirect · ecd=Small · density=Low |
| Expression | level=Moderate · breadth=Restricted · specificity=Surface Dominant |
| Risks | shed=false · secreted=false · coreceptor=false · paralog=false · masking=false · subdomain=false |
| Cross-species | mouse=90.1% · cyno=98.4% |
| Topology | TM=7 · N-term-ECF=true · C-term-ECF=false |
| Quality | knowledge_gaps_max_impact=High |

## 3. Surface evidence

**Evidence grade** · Supportive but indirect

Surface-localization evidence comes primarily from tagged overexpression in HEK293T / CHO heterologous systems. Endogenous live-cell flow with a validated anti-ECD antibody is not in the public record. Recent obesity-axis work (Akbari et al. 2021) is consistent with plasma-membrane presentation but did not directly assay surface display on primary cells.

### Live Cell Flow — Supports Surface Localization

*Permeabilization: Live Cell · expression: Overexpression*

**Antibodies**

- anti-FLAG M2 (placeholder) (M2 · Sigma · F1804 · AB_262044) — Extracellular epitope; Moderate validation; Tag-based; reads N-terminal FLAG, not endogenous GPR75.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HEK293T transient transfection with N-terminal FLAG-GPR75 | Established Cell Line | High | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Human adipose tissue (GTEx, bulk RNA) | Primary Human Tissue | RNA | Moderate | 1 |

## 4. Biological context

**Tissues**

| Tissue | Present | Cell types | Cell states |
|---|---|---|---|
| adipose | ✓ | adipocyte | mature, differentiating |
| vasculature | ✓ | vascular smooth muscle | quiescent |
| blood | ✗ | — | — |

**Primary subcellular compartment**: Plasma membrane

**Anatomical accessibility**

- Adipocyte in subcutaneous adipose — Blood Interstitial Facing · *Favorable*: Mature adipocytes present their plasma membrane to the interstitial space and capillary plexus; small ECD is the limiting factor, not anatomy.

**Accessibility modulation**

- *Tissue Restricted Surface* · lineage: Endocrine: Most surveyed tissues → Adipocyte / vascular smooth-muscle lineage — Endogenous expression is concentrated in metabolically active tissues; pan-tissue surface presence is not supported.

## 5. Isoforms

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24*

| Isoform | UniProt | TM | N-term | Signal pep | ECD len | ICD len |
|---|---|---|---|---|---|---|
| **canonical** | O95800 | 7 | Extracellular | 0 aa | 89 aa | 296 aa |

## 6. Paralogs

*Compara Compara r112*

| Paralog | UniProt | ECD %id | Family |
|---|---|---|---|
| CCRL2 | [O00421](https://www.uniprot.org/uniprotkb/O00421) | 18.2% | ENSFM00390000965 |
| GPR15 | [P49685](https://www.uniprot.org/uniprotkb/P49685) | 16.8% | ENSFM00390000965 |

**LLM cross-binding assessment**

| Paralog | Cross-reactivity | Severity | Evidence | Rationale |
|---|---|---|---|---|
| CCRL2 | Negligible | Low | Inferred | Only ~18% ECD identity to GPR75. Cross-binding by an anti-GPR75 mAb against CCRL2 would require coincidental ECD-loop convergence; no empirical binders to validate either way. |

## 7. Orthologs

**Mouse**

| Canonical | Isoform | Symbol | UniProt | Type | ECD %id | ECD %sim | ECD len | TM |
|---|---|---|---|---|---|---|---|---|
| ✓ | Q8K4Y3-1 | Gpr75 | Q8K4Y3 | One2one | 90.1% | 95.5% | 89 aa | 7 |

**Rat**

| Canonical | Isoform | Symbol | UniProt | Type | ECD %id | ECD %sim | ECD len | TM |
|---|---|---|---|---|---|---|---|---|
| ✓ | F1LP90-1 | Gpr75 | F1LP90 | One2one | 89.4% | 95.1% | 89 aa | 7 |

**Cynomolgus**

| Canonical | Isoform | Symbol | UniProt | Type | ECD %id | ECD %sim | ECD len | TM |
|---|---|---|---|---|---|---|---|---|
| ✓ | XP_005553-1 | GPR75 | A0A2K5XAH3 | One2one | 98.4% | 99.2% | 89 aa | 7 |

## 8. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Inferred

**Secreted form**

- present: false
- severity: Low
- evidence: Inferred

**Restricted subdomain**

- present: false
- severity: Low
- evidence: Inferred
- domain: Unknown
- rationale: No subcellular polarization documented in non-epithelial tissues where GPR75 is expressed.

**Co-receptor requirements**

- dependency: Unknown
- evidence basis: Co Expression Only
- rationale: No partner-trafficking studies in the public record. Heterologous-expression flow data suggest GPR75 reaches the surface without an obligate partner, but this is an overexpression artifact-prone signal.

**ECD size assessment**

- ECD class: Small
- rationale: 41-aa N-terminal tail plus three short loops totaling ~48 aa across the three ECLs. Total accessible ECD ~89 aa — limits epitope footprint for a conventional mAb but is sufficient for nanobody / small-molecule modalities.

**Epitope masking**

- severity: None
- evidence: Inferred
- mechanism: None
- rationale: No known glycan shield or partner-mediated masking. N-tail predicted to be unstructured (pLDDT ~62 in the AFDB model) but solvent-accessible.

## 9. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-O95800-F1-model_v6](https://alphafold.ebi.ac.uk/entry/O95800) |
| AFDB version | v6 |
| ECD mean pLDDT | 62.4 |
| ECD disordered fraction | 38.0% |
| ECD solvent-accessible fraction | 71.0% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/O95800) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

## 10. Knowledge gaps

### Is there protein-level surface evidence on endogenously expressed GPR75 in primary adipocyte or vascular smooth-muscle samples?

*Impact: High · No literature*

All current surface-localization signal is from tagged overexpression in HEK293T / CHO. A live-cell flow run with a validated anti-ECD antibody on primary adipocytes would resolve this.

> Suggested next step: Generate or commission a validated anti-GPR75-ECD nanobody and run live-cell flow on primary human adipocytes.

### Is the orphan ligand status genuinely orphan, or has a recent screen identified an endogenous ligand?

*Impact: Moderate · Outside scope*

Ligand-binding context affects whether antibody and small-molecule modalities can be designed against the orthosteric pocket vs. an allosteric extracellular surface.

> Suggested next step: Targeted PubMed sweep with the past-12-month filter; if still orphan, cite the most recent confirmation paper.

## 11. Evidence ledger

5 entries · 2 primary · 2 secondary · 1 tertiary · 1 PMC OA.

- `evi_01` · *Secondary* — GPR75 is a class-A orphan GPCR. ([doi:10.1093/nar/gkac1052](https://doi.org/10.1093/nar/gkac1052) · [PMC9825594](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9825594/))
  > "GPR75 is an orphan class A G protein-coupled receptor."
- `evi_02` · *Primary* — Loss-of-function variants in GPR75 are associated with reduced obesity risk. ([doi:10.1126/science.abf8683](https://doi.org/10.1126/science.abf8683) · [PMID 34211177](https://pubmed.ncbi.nlm.nih.gov/34211177/))
  > "Heterozygous loss-of-function variants in GPR75 were associated with lower BMI."
- `evi_03` · *Secondary* — FLAG-tagged GPR75 traffics to the plasma membrane in HEK293T. (https://example.org/mock-source-evi_03)
  > "Anti-FLAG flow on live cells detected GPR75 at the plasma membrane."
- `evi_04` · *Tertiary* — GPR75 mRNA is detectable in human adipose tissue. (https://gtexportal.org/home/gene/GPR75)
  > "Median TPM across adipose subcutaneous samples > 1."
- `evi_05` · *Primary* — GPR75 is present in vascular smooth-muscle cells in mouse aorta. (https://example.org/mock-source-evi_05)
  > "GPR75 transcripts segregated to the smooth-muscle cluster."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/GPR75.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/GPR75](https://surfaceome.deliverome.org/GPR75)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/GPR75.json](https://surfaceome.deliverome.org/data/surfaceome/GPR75.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/GPR75.md](https://surfaceome.deliverome.org/data/surfaceome/GPR75.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/O95800](https://alphafold.ebi.ac.uk/entry/O95800)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/O95800](https://alphafold.ebi.ac.uk/api/prediction/O95800) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/O95800](https://www.uniprot.org/uniprotkb/O95800)

### Canonical UniProt sequence

*540 aa · fetched from AFDB API at build time*

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

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- Ensembl Compara orthologs & paralogs — Compara r112 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022; academic-use service)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence 0.55 — Mock placeholder record. Confidence held to moderate because the high-impact knowledge gap (no protein-level surface evidence on endogenous GPR75) caps the executive-summary confidence — the validator rule says any knowledge_gap with impact_on_confidence='high' bounds top-line confidence at ≤ moderate.*
