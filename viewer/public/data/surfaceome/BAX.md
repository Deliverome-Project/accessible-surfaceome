# BAX — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-31T15:14:10.992681Z · model `claude-sonnet-4-6`*

> BAX is a BCL-2-family pro-apoptotic protein whose canonical localization is cytosolic in healthy cells, with stress-induced translocation to the mitochondrial outer membrane (OMM) to drive cytochrome-c release. No evidence from surface biotinylation, live-cell flow cytometry, or non-permeabilized immunofluorescence places BAX on the extracellular leaflet of the plasma membrane. The surfaceome capture database (Bausch-Fluck 2018) does not list BAX, and all direct assays confirm intracellular/mitochondrial localization. BAX is not a plasma-membrane surface target.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:959](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:959) |
| UniProt | [Q07812](https://www.uniprot.org/uniprotkb/Q07812) |
| NCBI Gene | [581](https://www.ncbi.nlm.nih.gov/gene/581) |
| Ensembl | [ENSG00000087088](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000087088) |
| Subcategory | Other |
| Surface accessibility | No |
| Confidence | High |
| Evidence grade | Weak |
| Triage signal | Unlikely |

## 1. Executive summary

BAX is a BCL-2-family pro-apoptotic protein whose canonical localization is cytosolic in healthy cells, with stress-induced translocation to the mitochondrial outer membrane (OMM) to drive cytochrome-c release. No evidence from surface biotinylation, live-cell flow cytometry, or non-permeabilized immunofluorescence places BAX on the extracellular leaflet of the plasma membrane. The surfaceome capture database (Bausch-Fluck 2018) does not list BAX, and all direct assays confirm intracellular/mitochondrial localization. BAX is not a plasma-membrane surface target.

**Family / classification** — UniProt family: Bcl-2 family · HGNC gene group(s): BCL2 family · functional class: Miscellaneous.

**Triage first-pass reasoning** — BAX is a BCL2-family pro-apoptotic protein that resides predominantly as a soluble cytoplasmic monomer under resting conditions. Upon apoptotic stimulation it undergoes conformational change, oligomerizes, and inserts into the outer mitochondrial membrane (OMM), not the plasma membrane. Its primary functional site is the OMM, where it permeabilizes the membrane to release cytochrome c. No credible surface biotinylation, flow cytometry on intact non-permeabilized cells, or surface proteomics data place BAX on the extracellular leaflet of the plasma membrane. Checking contextual buckets: cell_state_induced — stress/apoptosis recruits BAX to OMM, not PM outer leaflet; tissue_restricted_surface — no lineage-specific PM display documented; lysosomal_exocytosis — no evidence; dual_localization — PM pool not documented; stable_surface_attachment — not secreted and not wash-resistantly anchored to a PM partner. No therapeutic antibody/ADC/CAR-T targets BAX on the cell surface. Its only 'surface' is intramitochondrial, making it inaccessible from the extracellular face.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=No · conf=High · subcategory=Other · ecd=None |
| Classification | reason=Mitochondrial Internal · family=Miscellaneous · state-dependence=Low · induction-trigger=None |
| Expression | level=Moderate · breadth=Broad · specificity=Mostly Intracellular · low-endogenous=false · tumor-associated=false · orphan-receptor=false · OE-precedent=false |
| Risks | shed=false · secreted=true · co-receptor=None · masking=false · restricted-subdomain=false |
| Evidence | grade=Weak · density=Moderate · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=0 · N-term-ECF=false · C-term-ECF=false |

**Facet rationales**

- *Expression level*: BAX mRNA and protein are broadly detected in normal tissues and multiple tumor types including GBM and kidney disease (a2_evi_07, a2_evi_08, a2_evi_06), indicating moderate ubiquitous expression at the protein level.
- *Expression breadth*: BAX mRNA is present in multiple normal tissues and disease contexts including kidney and brain (a2_evi_06, a2_evi_07, a2_evi_08); consistent with pan-tissue apoptotic machinery, though IHC data in ledger are limited to two tissue types.
- *Surface specificity*: Entirely intracellular: cytosolic at rest, mitochondrial-outer-membrane upon apoptosis (a2_evi_01, a2_evi_02, a2_evi_03). Absent from surfaceome proteomics capture (a1_evi_03). No PM surface pool documented.
- *Known ligand*: BAX interacts with pro-survival BCL-2 family members (BCL-2, BCL-xL, MCL-1) as its primary binding partners; BCL-xL retrotranslocation interaction is directly evidenced (a2_evi_03, a2_evi_04). BH3-domain binding is well-established.
- *Low endogenous expression*: Derived from expression_level='moderate' (not low/absent → not flagged). BAX mRNA and protein are broadly detected in normal tissues and multiple tumor types including GBM and kidney disease (a2_evi_07, a2_evi_08, a2_evi_06), indicating moderate ubiquitous expression at the protein level.
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Weak

All three claims are tangential to a surface-accessibility call. a1_evi_01 is a WB antibody list with no surface assay; a1_evi_02 is permeabilized IF demonstrating mitochondrial co-localization (intracellular, not a direct surface refutation under the same conditions as any positive surface claim); a1_evi_03 is absence from a curated surfaceome DB, which is indirect/negative. There is no direct surface methodology (live flow, nonperm IF, surface biotinylation) in any direction. The evidence base is entirely indirect and negative, yielding a 'weak' grade — no direct surface assay supports or refutes plasma membrane exposure.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Low | WB antibody list in methods; no surface assay — describes intracellular detection context only. |
| a1_evi_02 | Tangential | Moderate | Permeabilized IF showing mitochondrial co-localization; confirms intracellular/mitochondrial biology, not a surface refutation per se. |
| a1_evi_03 | Tangential | Low | Absence from Surfaceome DB is indirect/negative evidence; no direct surface assay performed. |

### Immunofluorescence (1 method)

#### Permeabilized IF — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Cancer cell line treated with G-IrC8 nanoparticles plus laser; BAX co-localizes with MitoTracker Deep Red, confirming mitochondrial localization in fixed and live cells | Established Cell Line | Moderate | 1 |

### Surface mass spec (1 method)

#### Cell Surface Capture — Weak Or Ambiguous · Intracellular Pool

*Permeabilization: Unknown · expression: Unknown*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| BAX absent from Surfaceome database (Bausch-Fluck et al. 2018); not detected by cell-surface capture mass spectrometry across surveyed cell types | Unknown | Absent | 1 |

### Other (1 method)

#### Whole Cell Proteomics — Weak Or Ambiguous · Intracellular Pool

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-BAX (Cell Signaling Technology · 2772) — Intracellular epitope; Polyclonal; Moderate validation (SiRNA Knockdown); Rabbit polyclonal raised against N-terminal residues of human BAX; validated by knockdown per vendor/CiteAb.

**Contradicting evidence**

- *Intracellular Pool* (severity High): BAX co-localizes with MitoTracker Deep Red in both fixed and live cells, confirming its localization at the mitochondrial outer membrane rather than the plasma membrane surface. Western blot detection of BAX in whole-cell lysates using CST clone 2772 further situates it as a cytoplasmic/mitochondrial protein with no surface-specific fractionation reported. Together these data consistently place BAX intracellularly, contradicting the hypothesis that it is plasma membrane surface accessible.
  - Likely explanation: BAX is a well-established cytosolic and mitochondrial outer membrane protein that translocates to mitochondria upon apoptotic stimulation. The permeabilized IF and standard WB contexts capture this intracellular pool; any plasma membrane presence would be a minor or stress-induced event not representative of steady-state surface accessibility.
- *Proteomics Conflict* (severity High): BAX is absent from the Surfaceome database (Bausch-Fluck et al., 2018), a curated resource built from cell-surface capture mass spectrometry experiments. Its absence from this proteomics-based surfaceome dataset indicates it was not detected as a plasma membrane surface protein by biochemical cell-surface enrichment methods across multiple cell types.
  - Likely explanation: Cell-surface capture proteomics selectively biotinylates extracellular-facing glycoproteins; BAX lacks a canonical signal peptide and transmembrane domain oriented to the plasma membrane, so it would not be captured by this method, consistent with its established intracellular localization.

## 4. Biological context

*Accessibility context* — BAX is not surface-accessible; it resides in the cytosol at rest and translocates to the mitochondrial outer membrane upon apoptotic stimulation — never the extracellular leaflet of the plasma membrane.

**Cell types** *(orthogonal cell-type index)*

| Cell type | Ontology | Present in tissues | Species | Cites |
|---|---|---|---|---|
| renal tubular epithelial cells | — | kidney | Human | 1 |
| glomerular cells | — | kidney | Human | 1 |
| glioblastoma tumor cells | — | brain | Human | 2 |
| glial tumor cells | — | brain | Human | 1 |

**Cell states**

- *apoptotic* — Upon apoptotic stimulation, BAX translocates from the cytosol to the mitochondrial outer membrane, where it oligomerizes and permeabilizes the membrane; the BAX/BCL-2 ratio increases and BAX co-localizes with mitochondria. *(cites: a2_evi_01, a2_evi_05)*
- *resting* — In healthy, non-apoptotic cells, BCL-xL-driven retrotranslocation maintains BAX predominantly in the cytosol through continuous mitochondria-to-cytoplasm cycling. *(cites: a2_evi_02, a2_evi_03, a2_evi_04)*

**Primary subcellular compartment**: Cytosol

**Dual localization**

- Mitochondrial Outer Membrane · upon apoptotic stimulation *(cites: a2_evi_01, a2_evi_03, a2_evi_05)*
- Mitochondrion · basal cycling; retrotranslocated back to cytosol by pro-survival BCL-2 proteins *(cites: a2_evi_02, a2_evi_03, a2_evi_04)*

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Weak
- domain: Unknown
- rationale: No relevant data in the ledger regarding plasma-membrane subdomain restriction; the question does not arise because BAX has no documented PM surface presence.

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: BAX membrane association (OMM, not PM) is governed by its own conformational change and BCL-xL-mediated retrotranslocation cycling — no obligate plasma-membrane co-receptor is involved (a2_evi_03, a2_evi_04). The question is moot given no PM surface is documented.
- cites: a2_evi_03, a2_evi_04

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | Q07812 | ref | ref | 0 | 0 aa | 192 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q07812-2 | Q07812-2 | 87.0% | — | 0 | 0 aa | 218 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q07812-3 | Q07812-3 | 51.2% | — | 0 | 31 aa | 0 aa | 10 aa | Extracellular→Extracellular | — |
| Isoform | Q07812-4 | Q07812-4 | 100.0% | — | 0 | 0 aa | 143 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q07812-5 | Q07812-5 | 81.1% | — | 0 | 0 aa | 164 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q07812-6 | Q07812-6 | 100.0% | — | 0 | 0 aa | 114 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q07812-7 | Q07812-7 | 100.0% | — | 0 | 0 aa | 173 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | Q07812-8 | Q07812-8 | 100.0% | — | 0 | 0 aa | 179 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Mouse ortholog | Bax | [Q07813](https://www.uniprot.org/uniprotkb/Q07813) | 92.2% | — | 0 | 0 aa | — | — | — | high (≥85%) |
| Paralog | MCL1 | [Q07820](https://www.uniprot.org/uniprotkb/Q07820) | 24.5% | — | — | — | — | — | — | low-risk |
| Paralog | BCL2 | [P10415](https://www.uniprot.org/uniprotkb/P10415) | 23.4% | — | — | — | — | — | — | low-risk |
| Paralog | BCL2L1 | [Q07817](https://www.uniprot.org/uniprotkb/Q07817) | 21.9% | — | — | — | — | — | — | low-risk |
| Paralog | BAK1 | [Q16611](https://www.uniprot.org/uniprotkb/Q16611) | 20.8% | — | — | — | — | — | — | low-risk |
| Paralog | BOK | [Q9UMX3](https://www.uniprot.org/uniprotkb/Q9UMX3) | 20.8% | — | — | — | — | — | — | low-risk |
| Paralog | BCL2L10 | [Q9HD36](https://www.uniprot.org/uniprotkb/Q9HD36) | 20.3% | — | — | — | — | — | — | low-risk |
| Paralog | BCL2A1 | [Q16548](https://www.uniprot.org/uniprotkb/Q16548) | 20.3% | — | — | — | — | — | — | low-risk |
| Paralog | BCL2L2 | [Q92843](https://www.uniprot.org/uniprotkb/Q92843) | 18.8% | — | — | — | — | — | — | low-risk |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: false
- severity: Low
- evidence: Weak

**Secreted form**

- present: true
- severity: Low
- evidence: Weak
- source: Alternative Splicing

**ECD size assessment**

- ECD class: None
- rationale: BAX has no extracellular domain and no transmembrane segment oriented to the plasma-membrane outer leaflet. Its only membrane-associated state is OMM insertion (intracellular face), which is inaccessible to extracellular binders.
- cites: a2_evi_01, a1_evi_03

**Epitope masking**

- severity: None
- evidence: Inferred
- mechanism: None
- rationale: No extracellular epitope exists; masking is not applicable.

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-Q07812-F1](https://alphafold.ebi.ac.uk/entry/Q07812) |
| AFDB version | v6 |
| ECD mean pLDDT | 85.9 |
| ECD disordered fraction | 12.5% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/Q07812) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [Q07812](https://alphafold.ebi.ac.uk/entry/Q07812) | AlphaFold DB (AF-Q07812-F1, v6) |
| Isoform Q07812-2 | [Q07812-2](https://alphafold.ebi.ac.uk/entry/Q07812-2) | AlphaFold DB |
| Isoform Q07812-3 | [Q07812-3](https://alphafold.ebi.ac.uk/entry/Q07812-3) | AlphaFold DB |
| Isoform Q07812-4 | [Q07812-4](https://alphafold.ebi.ac.uk/entry/Q07812-4) | AlphaFold DB |
| Isoform Q07812-5 | [Q07812-5](https://alphafold.ebi.ac.uk/entry/Q07812-5) | AlphaFold DB |
| Isoform Q07812-6 | [Q07812-6](https://alphafold.ebi.ac.uk/entry/Q07812-6) | AlphaFold DB |
| Isoform Q07812-7 | [Q07812-7](https://alphafold.ebi.ac.uk/entry/Q07812-7) | AlphaFold DB |
| Isoform Q07812-8 | [Q07812-8](https://alphafold.ebi.ac.uk/entry/Q07812-8) | AlphaFold DB |
| Mouse ortholog (Bax) | [Q07813](https://alphafold.ebi.ac.uk/entry/Q07813) | AlphaFold DB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

12 entries · 8 primary · 4 secondary · 0 tertiary · 9 PMC OA.

- `a1_evi_01` · *Secondary* · Refutes · Methodological — Western blot antibody identifier for BAX: Cell Signaling Technology clone 2772 (rabbit anti-BAX), used in whole-cell lysate western blot assays alongside other BCL-2 family members. No fractionation or surface-specific step is described in this clip; the antibody is used in a standard intracellular WB context, consistent with BAX being detected as a cytoplasmic/mitochondrial protein rather than a plasma membrane surface protein. ([PMC12783235](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12783235/))
  - *assay*: Unspecified · unspecified · permeabilized
  > "The antibodies used were as follows: actin—Sigma A2066; BAX—Cell Signaling 2772; BCL-X L —Cell Signaling 2764; full length and cleaved caspase 7—Cell Signaling 9491; GAPDH—Cell Signaling 5174; MCL-1—Cell Signaling 94296; BCL-2—Cell Signaling 3492; BAK NT– Millipore 06-536; PUMA—Cell Signaling 98672; BIM—Cell Signaling 2933; Cleaved Caspase-3—Cell Signaling 9664; Anti-rabbit IgG (H1L) HRP conjugate—Thermo, 31460."
- `a1_evi_02` · *Secondary* · Refutes · Surface Expression — BAX/BCL-2 ratio measured as an intracellular apoptotic readout in cells treated with G-IrC8 nanoparticles plus laser; BAX co-localizes with MitoTracker Deep Red in fixed and live cells, confirming mitochondrial (not plasma membrane) localization. This is an intracellular signaling observation, consistent with BAX operating at the mitochondrial outer membrane rather than the plasma membrane surface. ([PMC12816584](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12816584/))
  - *assay*: Unspecified · fixed · permeabilized
  > "Heatmap on the right shows Bax/Bcl2 and cleaved-Caspase 3/Caspase 3 ratios, with significant increases in the G-IrC8 + Laser group compared to the Control group (p < 0.05). h Schematic illustrating the proposed mechanism of G-IrC8-induced apoptosis via mitochondrial targeting, fragmentation, ROS generation, and DNA damage
a Confocal microscopy showing G-IrC8 co-localized with mitochondria-specific dye MitoTracker Deep Red in fixed and live cells."
- `a1_evi_03` · *Secondary* · Refutes · Surface Expression — The Surfaceome database (Bausch-Fluck et al., 2018) was referenced as one of seven curated datasets used in a computational surface protein analysis pipeline. BAX is not listed as a surfaceome protein in this resource; its absence from the Surfaceome dataset corroborates that BAX is not recognized as a plasma membrane surface protein by cell-surface capture mass spectrometry approaches. ([PMC9751427](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9751427/))
  - *assay*: Unspecified
  > "The seven datasets used are included in Supplementary Table S3 : DrugBank ( Wishart et al., 2018 ), Human Protein Atlas ( Uhlén et al., 2015 ), STITCH ( Szklarczyk et al., 2016 ), Surfaceome ( Bausch-Fluck et al., 2018 ), Tumor Suppressor Gene Database v2.0 (TSGene) ( Zhao et al., 2016 ), pepBDB ( Wen et al., 2019 ), and Comparative Toxicogenomics Database ( Grondin et al., 2021 )."
- `a2_evi_01` · *Secondary* · Refutes · Surface Expression — BAX protein localizes primarily to the cytosol under resting conditions and translocates to the mitochondrial outer membrane upon apoptotic stimulation, where it oligomerizes and permeabilizes the membrane. This establishes BAX as an intracellular/mitochondrial protein, not a plasma membrane protein. ([PMC3070914](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3070914/))
  - *assay*: Unspecified · multiple cell types
  > "The Bcl-2 family member Bax translocates from the cytosol to mitochondria, where it oligomerizes and permeabilizes the mitochondrial outer membrane to promote apoptosis."
- `a2_evi_02` · *Primary* · Refutes · Surface Expression — In healthy, non-apoptotic cells, BAX undergoes constant retrotranslocation from mitochondria back into the cytoplasm (demonstrated by FLIP), maintaining a predominantly cytosolic pool. This dynamic mitochondria-to-cytoplasm cycling confirms BAX is not stably present at the plasma membrane surface. ([PMC3070914](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3070914/))
  - *assay*: Unspecified · healthy cells (unspecified line) · live
  > "Fluorescence loss in photobleaching (FLIP) reveals constant retrotranslocation of WT Bax, but not tethered Bax, from the mitochondria into the cytoplasm of healthy cells."
- `a2_evi_03` · *Primary* · Refutes · Surface Expression — BAX retrotranslocation from mitochondria to cytoplasm depends on pro-survival BCL-2 family proteins; when retrotranslocation is inhibited, BAX accumulates on the mitochondrial outer membrane (not plasma membrane). This reinforces BAX localization as cytosolic/mitochondrial rather than plasma membrane. ([PMC3070914](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3070914/))
  - *assay*: Unspecified · unspecified cell lines
  > "Bax retrotranslocation depends on prosurvival Bcl-2 family proteins, and inhibition of retrotranslocation correlates with Bax accumulation on the mitochondria."
- `a2_evi_04` · *Primary* · Refutes · Surface Expression — BCL-xL maintains BAX in the cytosol by continuous retrotranslocation of any mitochondrially-localized BAX back to the cytoplasm. The primary steady-state compartment of BAX is cytosolic, not the plasma membrane. ([PMC3070914](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3070914/))
  - *assay*: Unspecified · unspecified cell lines
  > "We propose that Bcl-x(L) inhibits and maintains Bax in the cytosol by constant retrotranslocation of mitochondrial Bax."
- `a2_evi_05` · *Primary* · Refutes · Surface Expression — Under apoptotic stress (G-IrC8 + laser photodynamic treatment), BAX/BCL-2 ratio increases and BAX co-localizes with mitochondria (MitoTracker), demonstrating stress-induced BAX translocation to the mitochondrial compartment, not the plasma membrane. Subcellular localization is intramitochondrial under apoptotic cell state. ([PMC12816584](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12816584/))
  - *assay*: Unspecified · unspecified cancer cells · fixed · permeabilized
  > "Heatmap on the right shows Bax/Bcl2 and cleaved-Caspase 3/Caspase 3 ratios, with significant increases in the G-IrC8 + Laser group compared to the Control group (p < 0.05). h Schematic illustrating the proposed mechanism of G-IrC8-induced apoptosis via mitochondrial targeting, fragmentation, ROS generation, and DNA damage
a Confocal microscopy showing G-IrC8 co-localized with mitochondria-specific dye MitoTracker Deep Red in fixed and live cells."
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — BAX protein expression was assessed by IHC scoring in renal tissue from kidney disease patients, including glomerulus, tubular epithelial cells (cytoplasm, membrane, and proximal), and areas of fibrosis. BAX is expressed in renal tissue in disease context (nephropathy/NRL), with scoring across multiple cellular compartments. This is not plasma membrane surface expression but general tissue expression in diseased kidney. ([PMC12291386](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12291386/))
  - *assay*: Human · renal tubular epithelial cells, glomerular cells · fixed · permeabilized
  > "IHC ISH ICIBs a Area of mononuclear inflammatory cell infiltration (scoring) b Other lesions Glomerulus lesion Area of desquamated basement membrane Area of renal fibrosis (scoring) b BCL2 (scoring) b BAX (scoring) b Cleaved caspase-3 (scoring) b 1 K014 NRL ++ C ( 2 ) - MPGN C, M − (0) C ( 1 ) − (0) − (0) - C 2 K025 NRL ++ C ( 1 ) - - C C (2.5) C, M, P ( 3 ) C, M ( 3 ) C ( 1 ) C, M,P C, M,P 3 K036 Mild irregular surface + C, M,P ( 2 ) Vacuolated cytoplasm of renal tubular epithelial cells - C, M,P C ( 0.7 ) C, M, P ( 3 ) C (2.7) C− (2) C, M,P C, M,P 4 K052 Mild irregular surface + C"
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — BAX protein expression was examined in 55 glioblastoma multiforme (GBM) patients, the most aggressive form of brain tumor. BAX is expressed in GBM tumor tissue, establishing a disease-context tissue expression profile in high-grade glioma. (https://pubmed.ncbi.nlm.nih.gov/11912183/)
  - *assay*: Human · glioblastoma multiforme tumor tissue · fixed · permeabilized
  > "Here, we have examined the expression of Bax in 55 patients with glioblastoma multiforme (GBM), the most common and aggressive form of brain tumors."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — Both BAX isoforms (Baxpsi and Baxalpha) are encoded by distinct mRNAs that are present in normal (non-tumor) tissues, establishing baseline BAX mRNA expression across normal human tissues. (https://pubmed.ncbi.nlm.nih.gov/11912183/)
  - *assay*: Human · normal tissues (unspecified panel)
  > "Baxpsi and the wild-type form, Baxalpha, are encoded by distinct mRNAs, both of which are present in normal tissues."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — In glial tumors, BAX isoform expression is exclusive: tumors express either Baxalpha or Baxpsi but not both, the result of exclusive transcription of the corresponding mRNAs. This isoform-specific tumor expression distinguishes glial tumor BAX expression from normal tissue and from non-glial tumor expression. (https://pubmed.ncbi.nlm.nih.gov/11912183/)
  - *assay*: Human · glial tumor cells
  > "Glial tumors express either Baxalpha or Baxpsi proteins, an apparent consequence of an exclusive transcription of the corresponding mRNAs."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/BAX.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/BAX](https://surfaceome.deliverome.org/BAX)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/BAX.json](https://surfaceome.deliverome.org/data/surfaceome/BAX.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/BAX.md](https://surfaceome.deliverome.org/data/surfaceome/BAX.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/Q07812](https://alphafold.ebi.ac.uk/entry/Q07812)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/Q07812](https://alphafold.ebi.ac.uk/api/prediction/Q07812) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/Q07812](https://www.uniprot.org/uniprotkb/Q07812)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-Q07812-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-Q07812-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-Q07812-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-Q07812-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-Q07812-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-Q07812-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*192 aa · `Q07812` · embedded at build time*

```
   1  MDGSGEQPRGGGPTSSEQIMKTGALLLQGFIQDRAGRMGGEAPELALDPVPQDASTKKLS
  61  ECLKRIGDELDSNMELQRMIAAVDTDSPREVFFRVAADMFSDGNFNWGRVVALFYFASKL
 121  VLKALCTKVPELIRTIMGWTLDFLRERLLGWIQDQGGWDGLLSYFGTPTWQTVTIFVAGV
 181  LTASLTIWKKMG
```

### Alternative-isoform sequences

**Q07812-2** (`Q07812-2` · 218 aa)

```
   1  MDGSGEQPRGGGPTSSEQIMKTGALLLQGFIQDRAGRMGGEAPELALDPVPQDASTKKLS
  61  ECLKRIGDELDSNMELQRMIAAVDTDSPREVFFRVAADMFSDGNFNWGRVVALFYFASKL
 121  VLKALCTKVPELIRTIMGWTLDFLRERLLGWIQDQGGWVRLLKPPHPHHRALTTAPAPPS
 181  LPPATPLGPWAFWSRSQWCPLPIFRSSDVVYNAFSLRV
```

**Q07812-3** (`Q07812-3` · 41 aa)

```
   1  MDGSGEQPRGGVSSRIEQGEWGGRHPSWPWTRCLRMRPPRS
```

**Q07812-4** (`Q07812-4` · 143 aa)

```
   1  MDGSGEQPRGGGPTSSEQIMKTGALLLQGMIAAVDTDSPREVFFRVAADMFSDGNFNWGR
  61  VVALFYFASKLVLKALCTKVPELIRTIMGWTLDFLRERLLGWIQDQGGWDGLLSYFGTPT
 121  WQTVTIFVAGVLTASLTIWKKMG
```

**Q07812-5** (`Q07812-5` · 164 aa)

```
   1  MDGSGEQPRGGGPTSSEQIMKTGALLLQGFIQDRAGRMGGEAPELALDPVPQDASTKKLS
  61  ECLKRIGDELDSNMELQRMIAAVDTDSPREVFFRVAADMFSDGNFNWGRVVALFYFASKL
 121  VLKAGVKWRDLGSLQPLPPGFKRFTCLSIPRSWDYRPCAPRCRN
```

**Q07812-6** (`Q07812-6` · 114 aa)

```
   1  MIAAVDTDSPREVFFRVAADMFSDGNFNWGRVVALFYFASKLVLKALCTKVPELIRTIMG
  61  WTLDFLRERLLGWIQDQGGWDGLLSYFGTPTWQTVTIFVAGVLTASLTIWKKMG
```

**Q07812-7** (`Q07812-7` · 173 aa)

```
   1  MKTGALLLQGFIQDRAGRMGGEAPELALDPVPQDASTKKLSECLKRIGDELDSNMELQRM
  61  IAAVDTDSPREVFFRVAADMFSDGNFNWGRVVALFYFASKLVLKALCTKVPELIRTIMGW
 121  TLDFLRERLLGWIQDQGGWDGLLSYFGTPTWQTVTIFVAGVLTASLTIWKKMG
```

**Q07812-8** (`Q07812-8` · 179 aa)

```
   1  MDGSGEQPRGGGPTSSEQIMKTGALLLQGFIQDRAGRMGGEAPELALDPVPQDASTKKLS
  61  ECLKRIGDELDSNMELQRMIAAVDTDSPREVFFRVAADMFSDGNFNWGRVVALFYFASKL
 121  VLKALCTKVPELIRTIMGWTLDFLRERLLGWIQDQGGWTVTIFVAGVLTASLTIWKKMG
```

### Canonical ortholog sequences

**Mouse — Bax** (`Q07813` · 192 aa)

```
   1  MDGSGEQLGSGGPTSSEQIMKTGAFLLQGFIQDRAGRMAGETPELTLEQPPQDASTKKLS
  61  ECLRRIGDELDSNMELQRMIADVDTDSPREVFFRVAADMFADGNFNWGRVVALFYFASKL
 121  VLKALCTKVPELIRTIMGWTLDFLRERLLVWIQDQGGWEGLLSYFGTPTWQTVTIFVAGV
 181  LTASLTIWKKMG
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`Q07812`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIII
```

**Q07812-2** (`Q07812-2`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Q07812-3** (`Q07812-3`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**Q07812-4** (`Q07812-4`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIII
```

**Q07812-5** (`Q07812-5`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Q07812-6** (`Q07812-6`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Q07812-7** (`Q07812-7`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Q07812-8** (`Q07812-8`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Mouse ortholog — Bax** (`Q07813`, projected onto human canonical)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence high — Confidence is high and aligned with the first-pass classifier. Multiple independent lines of evidence — FLIP-based live-cell microscopy, functional retrotranslocation assays, permeabilized immunofluorescence with MitoTracker co-localization, and absence from cell-surface capture proteomics (Bausch-Fluck 2018 surfaceome database) — all consistently place BAX in the cytosol and mitochondrial outer membrane, never on the extracellular leaflet of the plasma membrane. No credible counter-evidence for PM surface exposure exists in the literature or this ledger. Nothing in the reviewed evidence would change this call; BAX is not a surface target by any current experimental standard.*
