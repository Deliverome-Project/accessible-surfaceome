# LYN — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-31T15:31:28.680125Z · model `claude-sonnet-4-6`*

> LYN is a Src-family non-receptor tyrosine kinase anchored exclusively to the cytoplasmic (inner) leaflet of the plasma membrane via N-terminal myristoylation (Gly2) and palmitoylation (Cys3). It has zero transmembrane helices, no extracellular domain, and all catalytic domains (SH1/SH2/SH3) face the cytosol. The deep-dive evidence uniformly corroborates this topology: LYN-yPET serves as a standard inner-leaflet PM reference in BRET assays, and surface flow cytometry on LYN-deficient cells tested other antigens — not LYN itself. No ectopic-surface, cancer-state inversion, or outer-leaflet exposure has been documented for LYN in any lineage. Surface accessibility is absent.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:6735](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:6735) |
| UniProt | [P07948](https://www.uniprot.org/uniprotkb/P07948) |
| NCBI Gene | [4067](https://www.ncbi.nlm.nih.gov/gene/4067) |
| Ensembl | [ENSG00000254087](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000254087) |
| Subcategory | Other |
| Surface accessibility | No |
| Confidence | High |
| Evidence grade | Weak |
| Triage signal | Unlikely |

## 1. Executive summary

**LYN is constitutively anchored to the cytoplasmic face of the plasma membrane and is not surface-accessible in any documented cell state or disease context.**

LYN is a Src-family non-receptor tyrosine kinase anchored exclusively to the cytoplasmic (inner) leaflet of the plasma membrane via N-terminal myristoylation (Gly2) and palmitoylation (Cys3). It has zero transmembrane helices, no extracellular domain, and all catalytic domains (SH1/SH2/SH3) face the cytosol. The deep-dive evidence uniformly corroborates this topology: LYN-yPET serves as a standard inner-leaflet PM reference in BRET assays, and surface flow cytometry on LYN-deficient cells tested other antigens — not LYN itself. No ectopic-surface, cancer-state inversion, or outer-leaflet exposure has been documented for LYN in any lineage. Surface accessibility is absent.

**Family / classification** — UniProt family: protein kinase superfamily. Tyr protein kinase family. SRC subfamily · HGNC gene group(s): SH2 domain containing; Src family tyrosine kinases · functional class: Enzyme.

**Triage first-pass reasoning** — LYN is a Src-family non-receptor tyrosine kinase that resides on the cytoplasmic (inner) leaflet of the plasma membrane. It is anchored via dual N-terminal lipid modifications (myristoylation at Gly2 and palmitoylation at Cys3), placing it entirely on the cytosolic face of the PM. Its catalytic SH1, SH2, and SH3 domains are all cytoplasmic. There is no extracellular domain and no topology that would expose any part of the protein body to the extracellular space. Checking contextual buckets: (1) cell_state_induced — no documented stress/activation-induced surface flip; (2) tissue_restricted_surface — not applicable, no outer-leaflet display in any lineage; (3) lysosomal_exocytosis — LYN is not a lysosomal TM protein; (4) dual_localization — LYN cycles between inner PM leaflet and endomembranes, never the outer leaflet; (5) stable_surface_attachment — no documented wash-resistant anchoring to an extracellular-facing partner. No antibody, CAR-T, or surface-proteomics study targets LYN on the cell exterior. Verdict: cytoplasmic-face inner-leaflet anchored.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=No · conf=High · subcategory=Other · ecd=None |
| Classification | reason=Inner Leaflet Anchored · family=Enzyme · state-dependence=Low · induction-trigger=None |
| Expression | level=Moderate · breadth=Restricted · specificity=Mostly Intracellular · low-endogenous=false · tumor-associated=false · orphan-receptor=false · OE-precedent=false |
| Risks | shed=false · secreted=false · co-receptor=None · masking=false · restricted-subdomain=false |
| Evidence | grade=Weak · density=Moderate · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=0 · N-term-ECF=false · C-term-ECF=false |

**Facet rationales**

- *Expression level*: LYN is expressed in B cells, myeloid cells, microglia, AML blasts, and breast cancer cell lines (a2_evi_01, a2_evi_04, a2_evi_06). Expression is functionally significant in immune lineages but not pan-tissue high; moderate is the best-supported call.
- *Expression breadth*: Expression is concentrated in hematopoietic/immune lineages (B cells, myeloid cells, microglia) and select cancer contexts (AML, breast cancer) (a2_evi_01, a2_evi_03, a2_evi_04). Not detected broadly across non-immune tissues.
- *Surface specificity*: LYN is anchored exclusively to the cytoplasmic face of the PM via dual lipid modifications. Multiple independent observations confirm inner-leaflet topology with no outer-leaflet or surface exposure (a1_evi_01, a1_evi_04, a1_evi_05, a2_evi_08).
- *Known ligand*: LYN is a Src-family kinase; its substrates/interactors include BCR components (Igα/Igβ), CD22, FcγRIIB, and mesothelin (MSLN) in AML (a2_evi_04). Ligand/substrate identity is well-established even though LYN is cytoplasmic.
- *Low endogenous expression*: Derived from expression_level='moderate' (not low/absent → not flagged). LYN is expressed in B cells, myeloid cells, microglia, AML blasts, and breast cancer cell lines (a2_evi_01, a2_evi_04, a2_evi_06). Expression is functionally significant in immune lineages but not pan-tissue high; moderate is the best-supported call.
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Weak

All six claims are tangential to the question of surface accessibility. No claim uses a direct surface methodology (live-cell flow cytometry for LYN itself, non-permeabilized IF, surface biotinylation, or IHC membranous). The evidence uniformly describes LYN's canonical inner-leaflet, cytoplasmic-face topology via myristoylation/palmitoylation (a1_evi_01, a1_evi_02, a1_evi_06), its use as a cytoplasmic PM marker in BRET assays (a1_evi_04, a1_evi_05), and a surface flow experiment that measured other antigens on Lyn-KO microglia but never tested LYN surface exposure directly (a1_evi_03). The entirety of evidence is review-level, functional-assay-derived, or indirect topology inference — none constitutes a direct surface-accessibility assay for LYN. Grade: weak.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | High | Review-level assertion: SFKs including LYN are myristoylated and inner-leaflet anchored — describes canonical baseline topology |
| a1_evi_02 | Tangential | Moderate | N-terminal acetylated Gly2 consistent with post-myristoylation processing; confirms cytoplasmic-face anchoring indirectly |
| a1_evi_03 | Tangential | Low | Surface flow on Lyn-KO microglia measured other surface antigens, not LYN itself; LYN surface accessibility not tested |
| a1_evi_04 | Tangential | Moderate | LYN-yPET used as inner-leaflet PM marker in BRET assay; confirms cytoplasmic topology by functional usage, not direct surface assay |
| a1_evi_05 | Tangential | Moderate | LYN-yPET overexpression as PM reference in BRET; methodological detail supporting inner-leaflet topology, no surface accessibility assay |
| a1_evi_06 | Tangential | Low | Palmitoylation at Cys3 + myristoylation at Gly2 described; lipid-modification context, not a surface-accessibility assay |

### Flow cytometry (1 method)

#### Live Cell Flow — Weak Or Ambiguous · Intracellular Pool

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Lyn-deficient mouse microglia (dissociated whole brain tissue); surface phenotype panel — LYN itself not detected at surface, used as cytoplasmic kinase context | Ex Vivo | Absent | 1 |

### Functional surface assay (1 method)

#### Unknown — Weak Or Ambiguous · Intracellular Pool

*Permeabilization: Unknown · expression: Overexpression*

*Overexpression construct* — SP source: Unspecified · tag: C-terminal yPET. *(cites: a1_evi_05)*

### Other (1 method)

#### Unknown — Weak Or Ambiguous · Intracellular Pool

*Permeabilization: Unknown · expression: Endogenous*

**Contradicting evidence**

- *Alternative Localization* (severity High): LYN is a Src-family kinase that requires N-terminal myristoylation (at Gly2) and palmitoylation (at Cys3) for membrane association. These dual lipid modifications anchor LYN exclusively to the cytoplasmic face (inner leaflet) of the plasma membrane. DeepTMHMM confirms 0 transmembrane helices, and all functional domains (SH1, SH2, SH3) are cytoplasmic, meaning LYN has no extracellular domain and is not surface-accessible to antibodies on intact, non-permeabilized cells.
  - Likely explanation: LYN is a lipid-anchored, cytoplasmic-face kinase with no transmembrane segments or extracellular domain. Any apparent surface signal would require permeabilization or cell disruption to expose the cytoplasmic pool, and cannot represent genuine extracellular accessibility.
- *Alternative Localization* (severity High): LYN-yPET is routinely used as a reference marker for the inner leaflet of the plasma membrane in BRET-based internalization and trafficking assays, exploiting its N-terminal myristoylation/palmitoylation-driven cytoplasmic-face localization. This experimental use confirms that the field treats LYN as a cytoplasmic PM marker, not a surface-exposed protein, and that its topology places it inaccessible to extracellular reagents.
  - Likely explanation: The deliberate use of LYN as an inner-leaflet PM reference sensor in published assays reflects its established cytoplasmic topology; it is structurally incapable of presenting an extracellular epitope.
- *Intracellular Pool* (severity Moderate): DCAF10 regulates endogenous LYN levels by recognizing an N-terminally acetylated glycine residue (Gly2), consistent with post-myristoylation processing. Studies using siRNA knockdown, CRISPR/Cas9 knockout, and inducible LYN-GFP variants all treat LYN as an intracellular protein subject to cytoplasmic ubiquitin-proteasome regulation, further supporting inner-leaflet localization with no surface-accessible epitope.
  - Likely explanation: The N-terminal acetylated glycine is the degradation signal recognized by a cytoplasmic E3 ligase adaptor, confirming LYN's cytoplasmic face orientation; this is incompatible with extracellular exposure.
- *Intracellular Pool* (severity Low): Flow cytometry on intact (non-permeabilized) dissociated microglia from Lyn-deficient mice was used to examine 'microglial cell surface phenotype' without detecting LYN itself at the cell surface. The implicit assumption of this experimental design is that LYN is an intracellular kinase and would not appear in a live-cell surface staining panel.
  - Likely explanation: The study used surface flow cytometry to characterize downstream phenotypic markers on LYN-deficient microglia, not to detect LYN itself at the surface — consistent with LYN being cytoplasmic and not surface-accessible.

## 4. Biological context

**Cell types** *(orthogonal cell-type index)*

| Cell type | Ontology | Present in tissues | Species | Cites |
|---|---|---|---|---|
| B cells | — | peripheral blood / immune system | Human | 1 |
| myeloid cells | — | peripheral blood / immune system | Human | 1 |
| anergic B cells (Ars/A1) | — | peripheral lymphoid tissue | Mouse | 1 |
| microglia | — | brain | Mouse | 1 |
| acute myeloid leukemia (AML) blasts | — | — | Human | 2 |
| breast cancer epithelial cells | — | — | Human | 1 |
| autoreactive B cells | — | — | Mouse | 1 |

**Cell states**

- *anergic* — LYN is required in antigen-experienced anergic (Ars/A1) B cells to establish and maintain B cell unresponsiveness by restricting PI3K-dependent signaling. *(cites: a2_evi_02, a2_evi_09)*
- *disease state (autoimmune)* — Dysregulated LYN in autoreactive B cells impairs anergy induction, linking LYN activity to peripheral tolerance failure and autoimmune disease state. *(cites: a2_evi_09)*
- *disease state (AML)* — LYN is expressed and functionally active in AML blasts, forming a novel binding complex with mesothelin (MSLN) that drives oncogenic signaling and chemotherapy resistance. *(cites: a2_evi_04, a2_evi_05)*

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- Cytoplasmic Face Of Plasma Membrane (Inner Leaflet) · constitutive — LYN is myristoylated/palmitoylated and anchored to the cytoplasmic leaflet *(cites: a2_evi_08)*

**Membrane subdomains**: Inner Leaflet / Cytoplasmic Face Of Plasma Membrane

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Weak
- domain: Unknown
- rationale: No relevant data in the ledger addressing subdomain restriction. LYN is cytoplasmic-face and not surface-accessible at all; subdomain restriction of a surface epitope is not applicable.

**Co-receptor requirements**

- dependency: None
- evidence basis: Co Expression Only
- rationale: LYN membrane anchoring is entirely myristoylation/palmitoylation-driven at Gly2/Cys3. No obligate co-receptor or trafficking partner is required for its inner-leaflet PM association; the lipid modifications are sufficient and constitutive.
- cites: a1_evi_01, a1_evi_06

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P07948 | ref | ref | 0 | 0 aa | 512 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | P07948-2 | P07948-2 | 100.0% | — | 0 | 0 aa | 491 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Mouse ortholog | Lyn | [P25911](https://www.uniprot.org/uniprotkb/P25911) | 96.1% | — | 0 | 0 aa | — | — | — | high (≥85%) |
| Cynomolgus ortholog | LYN | [G7PBV3](https://www.uniprot.org/uniprotkb/G7PBV3) | 99.4% | — | 0 | 0 aa | — | — | — | high (≥85%) |
| Paralog | HCK | [P08631](https://www.uniprot.org/uniprotkb/P08631) | 69.9% | — | — | — | — | — | — | caution |
| Paralog | LCK | [P06239](https://www.uniprot.org/uniprotkb/P06239) | 63.1% | — | — | — | — | — | — | caution |
| Paralog | BLK | [P51451](https://www.uniprot.org/uniprotkb/P51451) | 59.6% | — | — | — | — | — | — | low-risk |
| Paralog | FYN | [P06241](https://www.uniprot.org/uniprotkb/P06241) | 57.8% | — | — | — | — | — | — | low-risk |
| Paralog | YES1 | [P07947](https://www.uniprot.org/uniprotkb/P07947) | 56.3% | — | — | — | — | — | — | low-risk |
| Paralog | FGR | [P09769](https://www.uniprot.org/uniprotkb/P09769) | 55.5% | — | — | — | — | — | — | low-risk |
| Paralog | SRC | [P12931](https://www.uniprot.org/uniprotkb/P12931) | 54.5% | — | — | — | — | — | — | low-risk |
| Paralog | FRK | [P42685](https://www.uniprot.org/uniprotkb/P42685) | 46.9% | — | — | — | — | — | — | low-risk |
| Paralog | ABL2 | [P42684](https://www.uniprot.org/uniprotkb/P42684) | 38.5% | — | — | — | — | — | — | low-risk |
| Paralog | ABL1 | [P00519](https://www.uniprot.org/uniprotkb/P00519) | 38.3% | — | — | — | — | — | — | low-risk |
| Paralog | SRMS | [Q9H3Y6](https://www.uniprot.org/uniprotkb/Q9H3Y6) | 35.9% | — | — | — | — | — | — | low-risk |
| Paralog | PTK6 | [Q13882](https://www.uniprot.org/uniprotkb/Q13882) | 35.0% | — | — | — | — | — | — | low-risk |
| Paralog | BTK | [Q06187](https://www.uniprot.org/uniprotkb/Q06187) | 34.8% | — | — | — | — | — | — | low-risk |
| Paralog | TXK | [P42681](https://www.uniprot.org/uniprotkb/P42681) | 34.8% | — | — | — | — | — | — | low-risk |
| Paralog | TYK2 | [P29597](https://www.uniprot.org/uniprotkb/P29597) | 34.4% | — | — | — | — | — | — | low-risk |
| Paralog | TEC | [P42680](https://www.uniprot.org/uniprotkb/P42680) | 34.2% | — | — | — | — | — | — | low-risk |
| Paralog | JAK2 | [O60674](https://www.uniprot.org/uniprotkb/O60674) | 34.0% | — | — | — | — | — | — | low-risk |
| Paralog | CSK | [P41240](https://www.uniprot.org/uniprotkb/P41240) | 33.8% | — | — | — | — | — | — | low-risk |
| Paralog | ITK | [Q08881](https://www.uniprot.org/uniprotkb/Q08881) | 33.2% | — | — | — | — | — | — | low-risk |
| Paralog | FER | [P16591](https://www.uniprot.org/uniprotkb/P16591) | 33.2% | — | — | — | — | — | — | low-risk |
| Paralog | SYK | [P43405](https://www.uniprot.org/uniprotkb/P43405) | 32.2% | — | — | — | — | — | — | low-risk |
| Paralog | PTK2 | [Q05397](https://www.uniprot.org/uniprotkb/Q05397) | 32.2% | — | — | — | — | — | — | low-risk |
| Paralog | FES | [P07332](https://www.uniprot.org/uniprotkb/P07332) | 32.2% | — | — | — | — | — | — | low-risk |
| Paralog | ZAP70 | [P43403](https://www.uniprot.org/uniprotkb/P43403) | 31.4% | — | — | — | — | — | — | low-risk |
| Paralog | JAK1 | [P23458](https://www.uniprot.org/uniprotkb/P23458) | 31.4% | — | — | — | — | — | — | low-risk |
| Paralog | BMX | [P51813](https://www.uniprot.org/uniprotkb/P51813) | 31.1% | — | — | — | — | — | — | low-risk |
| Paralog | JAK3 | [P52333](https://www.uniprot.org/uniprotkb/P52333) | 31.1% | — | — | — | — | — | — | low-risk |
| Paralog | MATK | [P42679](https://www.uniprot.org/uniprotkb/P42679) | 30.9% | — | — | — | — | — | — | low-risk |
| Paralog | PTK2B | [Q14289](https://www.uniprot.org/uniprotkb/Q14289) | 29.9% | — | — | — | — | — | — | low-risk |
| Paralog | TNK2 | [Q07912](https://www.uniprot.org/uniprotkb/Q07912) | 26.4% | — | — | — | — | — | — | low-risk |
| Paralog | TNK1 | [Q13470](https://www.uniprot.org/uniprotkb/Q13470) | 21.5% | — | — | — | — | — | — | low-risk |
| Paralog | STYK1 | [Q6J9G0](https://www.uniprot.org/uniprotkb/Q6J9G0) | 19.7% | — | — | — | — | — | — | low-risk |

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
- rationale: LYN has no extracellular domain. Zero TM helices confirmed by DeepTMHMM (a1_evi_01); all domains are cytoplasmic. ECD length = 0 residues; no antibody footprint possible on the cell exterior.
- cites: a1_evi_01, a1_evi_06

**Epitope masking**

- severity: None
- evidence: Inferred
- mechanism: None
- rationale: No extracellular domain exists, so epitope masking by glycan, partner, or conformation is not applicable. The entire protein body faces the cytoplasm.

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P07948-F1](https://alphafold.ebi.ac.uk/entry/P07948) |
| AFDB version | v6 |
| ECD mean pLDDT | 83.1 |
| ECD disordered fraction | 17.8% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P07948) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P07948](https://alphafold.ebi.ac.uk/entry/P07948) | AlphaFold DB (AF-P07948-F1, v6) |
| Isoform P07948-2 | [P07948-2](https://alphafold.ebi.ac.uk/entry/P07948-2) | AlphaFold DB |
| Mouse ortholog (Lyn) | [P25911](https://alphafold.ebi.ac.uk/entry/P25911) | AlphaFold DB |
| Cynomolgus ortholog (LYN) | [G7PBV3](https://alphafold.ebi.ac.uk/entry/G7PBV3) | AlphaFold DB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

15 entries · 8 primary · 7 secondary · 0 tertiary · 15 PMC OA.

- `a1_evi_01` · *Secondary* · Refutes · Topology — Src-family kinases (SFKs), including LYN, require N-terminal myristoylation for function. This establishes the topology mechanism by which LYN anchors to the cytoplasmic face of the plasma membrane inner leaflet via lipid modification, with no extracellular domain. DeepTMHMM confirms 0 TM helices; all domains (SH1, SH2, SH3) are cytoplasmic. This is a review/abstract-level assertion supporting inner-leaflet anchored topology. ([PMC12775124](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12775124/))
  - *assay*: Unspecified
  > "Src-family kinases (SFKs), signaling enzymes implicated in tumorigenesis, require N-terminal myristoylation for function."
- `a1_evi_02` · *Secondary* · Refutes · Methodological — DCAF10 regulates endogenous Lyn levels by recognizing an N-terminally acetylated glycine residue. The study uses siRNA-mediated knockdown and CRISPR/Cas9-mediated knockout of endogenous Lyn combined with inducible Lyn-GFP variants. This provides methodological detail confirming endogenous Lyn protein is the subject of study (not an overexpressed construct with foreign signal peptide), and the N-terminal glycine acetylation is consistent with post-myristoylation processing at residue Gly2, anchoring LYN to the inner leaflet of the plasma membrane rather than the cell surface. ([PMC12775124](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12775124/))
  - *assay*: Unspecified
  > "Combining siRNA-mediated knockdown and CRISPR/Cas9-mediated knockout of endogenous Lyn with inducible Lyn-GFP variants confirms that DCAF10 regulates SFK levels by recognizing an N-terminal acetylated glycine residue."
- `a1_evi_03` · *Secondary* · Refutes · Surface Expression — Flow cytometry on dissociated whole brain tissue was used to examine microglial cell surface phenotype in Lyn-deficient mice. This is a surface-method observation using intact (non-permeabilized) cells; however, the clip does not specify which surface antigens were measured or whether LYN itself was detected at the surface. LYN is a cytoplasmic kinase and would not be expected to appear in a live-cell surface flow panel. This clip is relevant as evidence that LYN-deficient cells were studied by surface flow cytometry, and the implicit assumption is LYN localizes intracellularly, not at the surface accessible to antibodies on intact cells. ([PMC10571795](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10571795/))
  - *assay*: Mouse · microglia · live · non-permeabilized
  > "To further characterize Lyn-deficient microglia, flow cytometry was conducted on dissociated whole brain tissue to examine microglial cell surface phenotype ( Figure 3 )."
- `a1_evi_04` · *Primary* · Refutes · Topology — In a study of bFFAR2 receptor internalization and trafficking, LYN was used as a sensor construct (not as the receptor target). LYN-yPET was employed as a plasma membrane marker to track internalization and trafficking events, exploiting LYN's known inner-leaflet plasma membrane localization via its N-terminal lipid anchors (myristoylation/palmitoylation). This confirms LYN is used as a cytoplasmic-face PM marker, not a surface-accessible protein, in BRET-based trafficking assays. ([PMC12405480](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12405480/))
  - *assay*: Unspecified
  > "Internalization and trafficking of bFFAR2 were assessed using two different sensors (LYN and FYVE)."
- `a1_evi_05` · *Secondary* · Refutes · Methodological — LYN was C-terminally fused with acceptor yPET and used in a BRET-based internalization assay at a 1:1 transfection ratio with bFFAR2. This methodological detail confirms LYN-yPET serves as an inner-leaflet plasma membrane reference marker in an overexpression system. The use of LYN as a cytoplasmic PM marker (not as a surface-exposed receptor) reflects its established topology: lipid-anchored at the cytoplasmic face with no extracellular exposure. ([PMC12405480](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12405480/))
  - *assay*: Unspecified
  > "LYN and FYVE were C-terminally fused with acceptor yPET, and transfection was performed at a 1:1 ratio with bFFAR2 (30 ng/well)."
- `a1_evi_06` · *Secondary* · Refutes · Topology — The study describes methods for detecting S-palmitoylated proteins including ABE, Acyl-RAC, and metabolic labelling. LYN is palmitoylated at Cys3 in addition to myristoylated at Gly2; these dual lipid modifications anchor it to the inner leaflet of the plasma membrane. This methodological context confirms that detection of LYN's membrane association relies on lipid-modification assays (not surface-accessibility assays), consistent with cytoplasmic-face topology. ([PMC12874130](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12874130/))
  - *assay*: Unspecified
  > "The detection of S-palmitoylated proteins and peptides includes the Acyl-Biotin Exchange (ABE) method, Acyl resin-assisted Capture (Acyl-RAC), metabolic labelling, and derivatives thereof."
- `a2_evi_01` · *Secondary* · Supports · Tissue Expression — LYN (Src family kinase) is expressed in B cells and myeloid cells, where it plays roles in B cell development, activation, and peripheral tolerance maintenance. This establishes B cells and myeloid cells as primary cell types expressing LYN. ([PMC13100191](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13100191/))
  - *assay*: Human · B cells, myeloid cells
  > "The Src family kinase Lyn is known to be involved in the induction and maintenance of peripheral B cell tolerance; however, mechanistic separation of tolerogenic functions from the role of Lyn in B cell and myeloid cell development and activation is challenging."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — LYN is required in anergic (Ars/A1) B cells — a specific cell state of antigen-experienced unresponsive B cells — to establish and maintain B cell unresponsiveness by restricting PI3K-dependent signaling. This identifies a cell-state-specific role for LYN in anergic versus non-anergic B cells. ([PMC13100191](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13100191/))
  - *assay*: Mouse · Ars/A1 anergic B cells
  > "Here we show that Ars/A1 B cells require Lyn to establish and maintain B cell unresponsiveness via restricting PI3K-dependent signaling pathways."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — LYN-deficient microglia were examined by flow cytometry on dissociated whole brain tissue, establishing that LYN is expressed in microglia (CNS-resident immune cells) and that its loss affects microglial cell surface phenotype. ([PMC10571795](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10571795/))
  - *assay*: Mouse · microglia (whole brain) · live · non-permeabilized
  > "To further characterize Lyn-deficient microglia, flow cytometry was conducted on dissociated whole brain tissue to examine microglial cell surface phenotype ( Figure 3 )."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — LYN (Src-family kinase) was identified as a novel binding partner of mesothelin (MSLN) in AML cells using an unbiased approach, establishing LYN expression in AML and its involvement in an oncogenic signaling axis. Pharmacological or genetic inhibition of LYN signaling restores chemotherapy sensitivity. ([PMC13098418](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13098418/))
  - *assay*: Human · NOMO-1 AML cell line
  > "Using an unbiased approach, we identify Src-family kinase member LYN, and guanine nucleotide-binding protein G(i) alpha subunit proteins, GNAI1, GNAI2, and GNAI3 as novel binding partners of MSLN in AML and show that pharmacological or genetic inhibition of LYN signaling restores NOMO-1 cell sensitivity to Ara-C."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — LYN was identified as one of three novel binding partners of mesothelin (MSLN) in AML, likely involved in oncogenic signaling, establishing LYN expression and functional activity in AML disease context. ([PMC13098418](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13098418/))
  - *assay*: Human · NOMO-1 AML cell line / AML001 PDX
  > "We identified three novel binding partners of MSLN; LYN, GNAI1, and GNAI2, which are likely involved in oncogenic signaling."
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — LYN (along with BLK and LCK, Src-family kinases) was detected by co-immunoprecipitation and mass spectrometry in MCF7 human breast cancer cells, establishing LYN expression in a breast cancer epithelial cell context. ([PMC9167300](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9167300/))
  - *assay*: Human · MCF7 · unspecified · permeabilized
  > "Within the same screen, we also identified peptides for BLK, LCK, and LYN, belonging to the Src family kinases, which were found in a similar size of ~60 kD band using co-immunoprecipitation (Co-IP) and MS assays in MCF7 cells (Fig."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — LYN was identified as part of a protein cluster enriched specifically in ST(3D) spatial transcriptomics data, associated with biological processes including homotypic cell-cell adhesion, regulation of leukocyte migration, and coagulation. This suggests LYN expression in a three-dimensional tissue context relevant to immune cell trafficking. ([PMC12329398](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12329398/))
  - *assay*: Human · ST(3D) tissue cluster · unspecified · permeabilized
  > "In contrast, Protein cluster enriched specifically in ST(3D) were implicated in protein folding in endoplasmic reticulum (CALR, CANX, DNAJC3, PDIA3), female pregnancy (ENDOU, HSD11B2, PSG3, SLC38A2, ACSL4, CALR, SLC2A1, STS), hormone biosynthetic process (CYP11A1, CYP19A1, DAB2, FDX1, POR), homotypic cell‐cell adhesion (CSRP1, FN1, HSPB1, LYN, PLPP3, STXBP1), regulation of leukocyte migration (CYP19A1, HMOX1, MPP1, ST3GAL4, CALR, DPP4, LGMN, LYN) and coagulation (ST3GAL4, TFPI, TFPI2, CSRP1, FN1, HSPB1, LYN, STXBP1)."
- `a2_evi_08` · *Secondary* · Refutes · Surface Expression — LYN was used as a plasma-membrane sensor in an internalization/trafficking assay to assess FFAR2 receptor endocytosis, exploiting LYN's known inner-leaflet plasma membrane anchoring. This is consistent with LYN residing at the cytoplasmic face of the plasma membrane, not at the cell surface. ([PMC12405480](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12405480/))
  - *assay*: Unspecified · transfected cell system
  > "Internalization and trafficking of bFFAR2 were assessed using two different sensors (LYN and FYVE)."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — Dysregulated LYN function in autoreactive B cells leads to failure of anergy induction and is associated with autoimmunity, suggesting that LYN activity in autoreactive B cell populations is critical for peripheral tolerance. This establishes a disease-state-specific role for LYN in autoimmune-associated B cells. ([PMC13100191](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13100191/))
  - *assay*: Mouse · autoreactive B cells
  > "Our findings thus suggest that a subset of autoreactive B cells requires Lyn to become anergic and that the autoimmunity associated with dysregulated Lyn function may, in part, be due to an inability of these autoreactive B cells to become tolerized."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/LYN.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/LYN](https://surfaceome.deliverome.org/LYN)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/LYN.json](https://surfaceome.deliverome.org/data/surfaceome/LYN.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/LYN.md](https://surfaceome.deliverome.org/data/surfaceome/LYN.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P07948](https://alphafold.ebi.ac.uk/entry/P07948)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P07948](https://alphafold.ebi.ac.uk/api/prediction/P07948) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P07948](https://www.uniprot.org/uniprotkb/P07948)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-P07948-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-P07948-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-P07948-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-P07948-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-P07948-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-P07948-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*512 aa · `P07948` · embedded at build time*

```
   1  MGCIKSKGKDSLSDDGVDLKTQPVRNTERTIYVRDPTSNKQQRPVPESQLLPGQRFQTKD
  61  PEEQGDIVVALYPYDGIHPDDLSFKKGEKMKVLEEHGEWWKAKSLLTKKEGFIPSNYVAK
 121  LNTLETEEWFFKDITRKDAERQLLAPGNSAGAFLIRESETLKGSFSLSVRDFDPVHGDVI
 181  KHYKIRSLDNGGYYISPRITFPCISDMIKHYQKQADGLCRRLEKACISPKPQKPWDKDAW
 241  EIPRESIKLVKRLGAGQFGEVWMGYYNNSTKVAVKTLKPGTMSVQAFLEEANLMKTLQHD
 301  KLVRLYAVVTREEPIYIITEYMAKGSLLDFLKSDEGGKVLLPKLIDFSAQIAEGMAYIER
 361  KNYIHRDLRAANVLVSESLMCKIADFGLARVIEDNEYTAREGAKFPIKWTAPEAINFGCF
 421  TIKSDVWSFGILLYEIVTYGKIPYPGRTNADVMTALSQGYRMPRVENCPDELYDIMKMCW
 481  KEKAEERPTFDYLQSVLDDFYTATEGQYQQQP
```

### Alternative-isoform sequences

**P07948-2** (`P07948-2` · 491 aa)

```
   1  MGCIKSKGKDSLSDDGVDLKTQPVPESQLLPGQRFQTKDPEEQGDIVVALYPYDGIHPDD
  61  LSFKKGEKMKVLEEHGEWWKAKSLLTKKEGFIPSNYVAKLNTLETEEWFFKDITRKDAER
 121  QLLAPGNSAGAFLIRESETLKGSFSLSVRDFDPVHGDVIKHYKIRSLDNGGYYISPRITF
 181  PCISDMIKHYQKQADGLCRRLEKACISPKPQKPWDKDAWEIPRESIKLVKRLGAGQFGEV
 241  WMGYYNNSTKVAVKTLKPGTMSVQAFLEEANLMKTLQHDKLVRLYAVVTREEPIYIITEY
 301  MAKGSLLDFLKSDEGGKVLLPKLIDFSAQIAEGMAYIERKNYIHRDLRAANVLVSESLMC
 361  KIADFGLARVIEDNEYTAREGAKFPIKWTAPEAINFGCFTIKSDVWSFGILLYEIVTYGK
 421  IPYPGRTNADVMTALSQGYRMPRVENCPDELYDIMKMCWKEKAEERPTFDYLQSVLDDFY
 481  TATEGQYQQQP
```

### Canonical ortholog sequences

**Mouse — Lyn** (`P25911` · 512 aa)

```
   1  MGCIKSKRKDNLNDDEVDSKTQPVRNTDRTIYVRDPTSNKQQRPVPEFHLLPGQRFQTKD
  61  PEEQGDIVVALYPYDGIHPDDLSFKKGEKMKVLEEHGEWWKAKSLSSKREGFIPSNYVAK
 121  VNTLETEEWFFKDITRKDAERQLLAPGNSAGAFLIRESETLKGSFSLSVRDYDPMHGDVI
 181  KHYKIRSLDNGGYYISPRITFPCISDMIKHYQKQSDGLCRRLEKACISPKPQKPWDKDAW
 241  EIPRESIKLVKKLGAGQFGEVWMGYYNNSTKVAVKTLKPGTMSVQAFLEEANLMKTLQHD
 301  KLVRLYAVVTKEEPIYIITEFMAKGSLLDFLKSDEGGKVLLPKLIDFSAQIAEGMAYIER
 361  KNYIHRDLRAANVLVSESLMCKIADFGLARVIEDNEYTAREGAKFPIKWTAPEAINFGCF
 421  TIKSDVWSFGILLYEIVTYGKIPYPGRTNADVMSALSQGYRMPRMENCPDELYDIMKMCW
 481  KEKAEERPTFDYLQSVLDDFYTATEGQYQQQP
```

**Cynomolgus — LYN** (`G7PBV3` · 622 aa)

```
   1  MQIRAPGSSWDLSTEPRDSQFLSRRAGPRCRSLPGRGASGPDALQPPARGKRGGRANPGP
  61  APAALAARPAFPASSLPYAGPAGPPRRAPCSELKSPWSSATPKLSPRAGNMGCIKSKGKD
 121  SLNDDGVDLKTQPVRNTERTIYVRDPTSNKQQRPVPESQLLPGQRFQAKDPEEQGDIVVA
 181  LYPYDGIHPDDLSFKKGEKMKVLEEHGEWWKAKSLLTKKEGFIPSNYVAKLNTLETEEWF
 241  FKDITRKDAERQLLAPGNSAGAFLIRESETLKGSFSLSVRDFDPVHGDVIKHYKIRSLDN
 301  GGYYISPRITFPCISDMIKHYQKQPDGLCRRLEKACISPKPQKPWDKDAWEIPRESIKLV
 361  KRLGAGQFGEVWMGYYNNSTKVAVKTLKPGTMSVQAFLEEANLMKTLQHDKLVRLYAVVT
 421  REEPIYIITEYMAKGSLLDFLKSDEGGKVLLPKLIDFSAQIAEGMAYIERKNYIHRDLRA
 481  ANVLVSESLMCKIADFGLARVIEDNEYTAREGAKFPIKWTAPEAINFGCFTIKSDVWSFG
 541  ILLYEIVTYGKIPYPGRTNADVMTALSQGYRMPRVENCPDELYDIMKMCWKEKAEERPTF
 601  DYLQSVLDDFYTATEGQYQQQP
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`P07948`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**P07948-2** (`P07948-2`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIII
```

**Mouse ortholog — Lyn** (`P25911`, projected onto human canonical)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 361  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 421  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 481  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Cynomolgus ortholog — LYN** (`G7PBV3`, projected onto human canonical)

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
 601  IIIIIIIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence high — Confidence is high because the canonical inner-leaflet topology of LYN is corroborated by multiple independent lines of evidence: review-level consensus on Src-family myristoylation, palmitoylation biochemistry at Gly2/Cys3, use as a validated inner-leaflet PM reference sensor in published BRET assays, and E3-ligase regulation of its N-terminally processed cytoplasmic form. No deep-dive evidence surfaced any ectopic outer-leaflet exposure, cancer-state topological inversion, or surface-proteomics detection of LYN on intact cells. The triage call of inner-leaflet-anchored is fully consistent with A1 and A2 findings; no override is required.*

## CellxGene RNA enrichment (CZI Census)

*Schema v2.1.4 · CZI Census 2025-11-08 · HPA-style 4× fold-change classification on log1p(CP10K) → linear means, plus Yanai et al. 2005 τ (specificity score ∈ [0, 1], computed over the eligible-entity set). Cell-class rollup walks the Cell Ontology graph (cl-basic.obo, OBO Foundry) — leaf CL → nearest compartment ancestor. CC-BY 4.0 (CZI Census).*

**Classification:**

- **Cell class (CL ontology graph, ~10 compartments):** enhanced · Immune · 4.6× · τ=0.78
- **Cell type (leaf Cell Ontology terms, ~600):** enhanced · neutrophil · 14.5× · τ=0.93
- **Tissue (UBERON terms, ~56):** enhanced · tongue · 20.2× · τ=0.95

**Top 5 cell types (leaf CL, pooled across tissues):**

| Cell type | CL ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| neutrophil | CL:0000775 | 2.829 | 52.98% | 97,180 / 183,432 |
| mucus secreting cell of tracheobronchial tree submucosal gland | CL:4033037 | 2.668 | 29.13% | 386 / 1,325 |
| chondrocyte | CL:0000138 | 2.638 | 3.98% | 1,276 / 32,083 |
| noradrenergic cell | CL:0000459 | 2.621 | 0.72% | 1 / 138 | (trace)
| dermis microvascular lymphatic vessel endothelial cell | CL:2000041 | 2.573 | 11.28% | 68 / 603 |

**Top 5 tissues (UBERON, pooled across cell types):**

| Tissue | UBERON ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| pleura | UBERON:0000977 | 2.438 | 2.17% | 428 / 19,695 |
| saliva | UBERON:0001836 | 2.260 | 45.16% | 6,549 / 14,502 |
| esophagus | UBERON:0001043 | 2.216 | 14.86% | 3,506 / 23,590 |
| chest | UBERON:0001443 | 2.200 | 11.32% | 1,745 / 15,413 |
| embryo | UBERON:0000922 | 2.200 | 86.18% | 12,276 / 14,244 |

<!-- /cellxgene -->
