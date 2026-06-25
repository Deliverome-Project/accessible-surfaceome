# SRC — Surface Accessibility Brief

*Schema v2.12.0 · generated 2026-06-09T01:43:58.622412Z · model `claude-sonnet-4-6`*

> SRC is state-dependently surface-accessible in cancer cells — a canonical inner-leaflet kinase with a cancer-specific outer-surface form. Direct surface evidence is single-method: antibody-mediated tumor cell killing against extracellular-facing eSrc in cancer cell lines and xenograft models demonstrates outer-leaflet engagement (a1_evi_01, a1_evi_02). Surface presence is strictly state-gated, requiring cancer-state autophagolysosomal exocytosis (ALE) to invert the N-myristoylated kinase onto the outer leaflet; normal cells retain exclusively inner-leaflet, cytoplasmic-face localization cycling between plasma membrane and late endosomes (a2_evi_04). The principal binder-engineering caveat is moderate restricted-subdomain access — outer-surface SRC is absent in normal tissue and confined to cancer cells with active ALE (a2_evi_01, a2_evi_03); the absence of a shed or secreted form and no co-receptor requirement rule out decoy and escort concerns.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:11283](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:11283) |
| UniProt | [P12931](https://www.uniprot.org/uniprotkb/P12931) |
| NCBI Gene | [6714](https://www.ncbi.nlm.nih.gov/gene/6714) |
| Ensembl | [ENSG00000197122](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000197122) |
| Subcategory | Other |
| Surface accessibility | Moderate |
| Confidence | Low |
| Evidence grade | Direct, single method |
| Triage signal | Unlikely |

## 1. Executive summary

**Surface-accessible only on cancer cells where ALE-driven topological inversion exposes the kinase domain on the outer plasma membrane face; absent on normal cells where SRC is exclusively inner-leaflet.**

SRC is state-dependently surface-accessible in cancer cells — a canonical inner-leaflet kinase with a cancer-specific outer-surface form. Direct surface evidence is single-method: antibody-mediated tumor cell killing against extracellular-facing eSrc in cancer cell lines and xenograft models demonstrates outer-leaflet engagement (a1_evi_01, a1_evi_02). Surface presence is strictly state-gated, requiring cancer-state autophagolysosomal exocytosis (ALE) to invert the N-myristoylated kinase onto the outer leaflet; normal cells retain exclusively inner-leaflet, cytoplasmic-face localization cycling between plasma membrane and late endosomes (a2_evi_04). The principal binder-engineering caveat is moderate restricted-subdomain access — outer-surface SRC is absent in normal tissue and confined to cancer cells with active ALE (a2_evi_01, a2_evi_03); the absence of a shed or secreted form and no co-receptor requirement rule out decoy and escort concerns.

**Family / classification** — UniProt family: protein kinase superfamily. Tyr protein kinase family. SRC subfamily · HGNC gene group(s): SH2 domain containing; Src family tyrosine kinases · functional class: Enzyme.

**Triage first-pass reasoning** — SRC (p60-Src) is a non-receptor tyrosine kinase anchored to the cytoplasmic face of the plasma membrane via N-terminal myristoylation and palmitoylation. Its kinase domain, SH2, and SH3 domains all face the cytoplasm. No extracellular domain exists. Checking contextual buckets: (1) cell_state_induced — no evidence of stress-induced extracellular display; (2) tissue_restricted_surface — not applicable, inner-leaflet anchor throughout; (3) lysosomal_exocytosis — no lysosomal biology documented for SRC; (4) dual_localization — SRC cycles between cytoplasmic face of PM and endomembranes, but never the outer leaflet; (5) stable_surface_attachment — SRC is not secreted and not documented as wash-resistantly attached to any extracellular surface protein. No antibody/ADC/CAR-T programs target extracellular SRC; all therapeutic programs (dasatinib, bosutinib, etc.) are intracellular small-molecule inhibitors. Surface biotinylation and flow cytometry on intact cells do not detect SRC on the outer leaflet. Verdict: inner-leaflet-anchored, not accessible from extracellular face.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=Moderate · conf=Low · subcategory=Other · ecd=None |
| Classification | reason=Lysosomal Exocytosis · family=Enzyme · state-dependence=High · induction-trigger=Oncogenic |
| Expression | level=Moderate · breadth=Broad · specificity=Mostly Intracellular · low-endogenous=false · tumor-associated=true · orphan-receptor=true · OE-precedent=false |
| Risks | shed=false · secreted=false · co-receptor=None · masking=false · restricted-subdomain=true |
| Evidence | grade=Direct, single method · density=High · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=0 · N-term-ECF=false · C-term-ECF=false |

**Facet rationales**

- *Expression level*: SRC protein is detected at moderate levels across skin keratinocytes (a2_evi_08), osteocytes (a2_evi_12), monocytes (a2_evi_17), and multiple cancer cell lines including MPM (a2_evi_10), OSCC (a2_evi_15), and NPC (a2_evi_19); no high-level pan-tissue baseline is documented.
- *Expression breadth*: SRC expression is documented in at least six tissue/cell contexts — skin, bone (osteocytes, osteoblasts), blood (monocytes), pleura (MPM), oral mucosa (OSCC), and nasopharynx (NPC) — spanning normal and tumor settings (a2_evi_08, a2_evi_12, a2_evi_10, a2_evi_14, a2_evi_17, a2_evi_19).
- *Surface specificity*: Under normal conditions SRC is exclusively inner-leaflet (cytoplasmic-face PM and late endosomes); outer-surface eSrc is documented only in cancer cells via ALE (a1_evi_01, a2_evi_01, a2_evi_04), making surface exposure a minority, state-restricted fraction.
- *Known ligand*: SRC is a non-receptor tyrosine kinase; it has no canonical extracellular ligand-binding domain. The validated interactions (NMDAR via ND2/PSD-95, focal adhesion substrates) are intracellular and substrate-level, not extracellular ligand-receptor pairs. All therapeutic programs are intracellular small-molecule inhibitors or antibodies targeting the unconventional eSrc form.
- *Low endogenous expression*: SRC protein is detected at moderate levels across skin keratinocytes (a2_evi_08), osteocytes (a2_evi_12), monocytes (a2_evi_17), and multiple cancer cell lines including MPM (a2_evi_10), OSCC (a2_evi_15), and NPC (a2_evi_19); no high-level pan-tissue baseline is documented.
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Direct, single method

The key surface-positive evidence comes from a single source (PMID:41818370), which reports that SRC is non-canonically translocated to the outer cell surface in cancer cells via autophagolysosomal exocytosis (ALE), resulting in a topologically inverted extracellular membrane-associated form (eSrc) (a1_evi_01). The same source reports detection of eSrc in primary human tumors and demonstrates anti-Src antibody-mediated tumor cell killing in xenograft models — a functional surface assay classified as direct_surface_accessibility by the methods builder (a1_evi_02). Both claims are from a single paper with moderate confidence (no independent replication). The canonical inner-leaflet topology (a1_evi_03, a1_evi_04, a1_evi_16) describes the baseline biology and is not mechanistically incompatible with cancer-state ALE inversion — these are tangential (different state). The IHC membranous signal in human skin (a1_evi_07) and PSD fractionation in mouse brain (a1_evi_08) are expression-only. Antibody cross-reactivity with Fyn/Yes (a1_evi_09, a1_evi_10) is a caveat. One direct method class (functional surface assay / antibody-mediated tumor killing), single source → direct_single_method with low confidence and high state_dependence (cancer-state-only).

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Supports Surface | Moderate | Cancer-state ALE-mediated topological inversion; single source (PMID:41818370); in vitro + in vivo |
| a1_evi_02 | Supports Surface | Moderate | eSrc in primary human tumors; anti-Src antibody tumor killing in xenografts; single source (PMID:41818370) |
| a1_evi_03 | Tangential | High | Canonical inner-leaflet topology — describes baseline state, not incompatible with cancer-state ALE inversion |
| a1_evi_04 | Tangential | High | N-myristoylation requirement for SFK function — canonical baseline biology, not a refutation of induced surface form |
| a1_evi_05 | Tangential | Moderate | Fumagillin blocks Src membrane clustering in monocytes — cytoplasmic-face biology, describes baseline state |
| a1_evi_06 | Tangential | Moderate | NMT1 myristoylates Src in OSCC — biochemical anchoring mechanism, canonical topology context |
| a1_evi_07 | Expression Only | Low | Phospho-IHC in human skin epidermis, PM-associated pattern but permeabilization unspecified; IHC_membranous graded weak_or_ambiguous |
| a1_evi_08 | Expression Only | Low | PSD fractionation in mouse brain; cytoplasmic-face localization, no outer-leaflet accessibility |
| a1_evi_09 | Tangential | Moderate | Antibody cross-reactivity caveat (anti-pSrc cross-reacts with Fyn/Yes) — methodological note, not surface evidence |
| a1_evi_10 | Tangential | Moderate | Paralog cross-reactivity confirmed for CST #2105/#6943 — specificity caveat for SRC surface claims using these clones |
| a1_evi_11 | Tangential | Low | Antibody catalog listing — methodological, no surface accessibility information |
| a1_evi_12 | Tangential | Low | Antibody RRID listing for mouse fractionation study — methodological, no outer-leaflet accessibility claim |
| a1_evi_13 | Tangential | Low | Surface biotinylation reagent listed but used to assay N-cadherin surface levels, not SRC itself |
| a1_evi_14 | Tangential | Low | Antibody catalog listing in prostate cancer lines — methodological, no surface accessibility information |
| a1_evi_15 | Tangential | Low | Antibody catalog listing in endothelial cells — methodological, no surface accessibility information |
| a1_evi_16 | Tangential | Moderate | Fumagillin blocks cytoplasmic-face Src clustering in monocytes — describes baseline inner-leaflet biology, not incompatible with cancer-state ALE inversion (different state/context) |

### Immunohistochemistry (1 method)

#### IHC Membranous — Weak Or Ambiguous · Intracellular Pool

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-c-Src pY419 — Intracellular epitope; Unknown; None validation (None); Phospho-specific antibody targeting pY419 activating autophosphorylation site; potential cross-reactivity with other SFK members at equivalent phospho-residues.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| c-Src pY419 plasma membrane-associated staining in basal and spinous keratinocytes of human skin epidermis by phospho-specific IHC; inner-leaflet anchored — not extracellularly accessible. | Primary Human Tissue | Moderate | 1 |

### Membrane fractionation (1 method)

#### Plasma Membrane Fractionation — Weak Or Ambiguous · Intracellular Pool

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-SRC (H-12 · Santa Cruz Biotechnology · sc-5266 · AB_627308) — Intracellular epitope; Monoclonal; None validation (None); Mouse monoclonal IgG2a raised against aa 1-30 at N-terminus of human c-Src (intracellular myristoylation domain). Broad species reactivity (mouse, rat, human, avian).

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| SRC levels in PSD-enriched fractions from mouse brain are reduced 38% ± 5% in Posh-cKO mice versus controls; cytoplasmic/inner-leaflet localization at postsynaptic density — not extracellularly accessible. | Ex Vivo | Moderate | 1 |

### Functional surface assay (1 method)

#### Functional Surface Assay — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-Src (therapeutic/functional) — Extracellular epitope; Unknown; None validation (None); Anti-Src antibody used for antibody-based therapeutic tumor cell killing; epitope identity and clone not specified in the source. Engages extracellular-facing (eSrc) kinase domain exposed by ALE-mediated topological inversion.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Extracellular membrane-associated Src (eSrc) detected in cancer cell lines (in vitro) via non-canonical ALE-mediated surface translocation with topological inversion; anti-Src antibody-mediated tumor cell killing demonstrated. | Established Cell Line | Moderate | 1 |
| eSrc detected in primary human tumor tissue by non-canonical ALE-mediated topological inversion; anti-Src antibody-based therapies mediated tumor cell killing in mouse xenograft models. | Xenograft | Moderate | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Human skin epidermis, basal and spinous keratinocytes — phospho-Src(pY419) plasma membrane-associated signal by IHC | Primary Human Tissue | IHC Protein | Moderate | 1 |
| Mouse brain postsynaptic density-enriched fractions from cortical neurons — SRC levels by subcellular fractionation Western blot | Ex Vivo | Bulk Protein | Moderate | 1 |

**Contradicting evidence**

- *Alternative Localization* (severity High): SRC is a canonical inner-leaflet peripheral membrane protein anchored exclusively via N-terminal myristoylation and a polybasic cluster, with all functional domains (SH3, SH2, catalytic) facing the cytoplasm and no extracellular domain. Multiple independent review-level and experimental sources confirm this topology, directly refuting any hypothesis that SRC presents an accessible extracellular surface for antibody or ligand engagement from outside the cell.
  - Likely explanation: SRC is a bona fide cytoplasmic-face membrane kinase; any apparent 'surface' signal would require an unconventional mechanism such as ALE-mediated membrane inversion, ectopic secretion, or artefactual permeabilization in the assay. The canonical topology is overwhelmingly supported and should be treated as the default.

## 4. Biological context

**Biological-context grade** · Rich

All four A2 axes are well-populated across multiple independent sources. Expression is mapped in cancer cell lines, primary tumors (MPM, OSCC, NPC), skin, bone, and monocytes. Subcellular localization is pinned (inner-leaflet PM, focal adhesions, perinuclear, late endosomes). Anatomical context spans ≥6 tissue/cell types. Accessibility modulation is richly documented: cancer-specific ALE-driven outer-surface translocation (eSrc), mechano-stress redistribution in osteocytes/osteoblasts, chemical irritant activation in skin, and lipid-induced clustering in monocytes. The cancer vs. normal distinction is internally consistent, not contradictory. Picture is coherent and multi-axis. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_07, a2_evi_08, +12)*

**Expression × cell type × disease context**

| Tissue | Cell type | Disease context | Level (protein) | Cell states |
|---|---|---|---|---|
| skin | keratinocytes (basal/spinous) | Normal | Moderate | — |
| skin | keratinocytes | Other Disease (lactic acid irritant stress) | Moderate | stress-induced, irritant-activated |
| pleura | — | Tumor (malignant pleural mesothelioma) | Moderate | — |
| bone | osteocytes | Normal | Moderate | — |
| bone | osteocytes | Normal | Moderate | fluid shear stress-stimulated |
| oral mucosa | — | Tumor (oral squamous cell carcinoma) | High | — |
| blood | monocytes | Other Disease (lipid-induced inflammatory state (oxLDL challenge)) | Moderate | chronically activated, lipid-challenged |
| skeletal muscle | — | Other Disease (sepsis (CLP model)) | Moderate | — |
| nasopharynx | — | Tumor (nasopharyngeal carcinoma) | High | EMT-associated |
| bone | osteoblasts | Normal | Moderate | fluid shear stress-stimulated |
| primary tumor (multiple types) | — | Tumor (cancer (multiple types)) | Moderate | — |

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- Late Endosome/Lysosome · normal, non-cancer cells *(cites: a2_evi_04)*
- Outer Plasma Membrane Surface · cancer cells with active ALE pathway *(cites: a2_evi_01, a2_evi_02, a2_evi_03)*
- Cytoplasm/Perinuclear Region · in OSCC cancer cells *(cites: a2_evi_16)*
- Peri-Nuclear/Nuclear Region · fluid shear stress in osteocytes *(cites: a2_evi_13)*

**Membrane subdomains**: Focal Adhesion

**Accessibility modulation**

- *Lysosomal Exocytosis* · trigger: Oncogenic Transformation: normal (non-cancer) cells → cancer cells with ALE pathway activity — SRC undergoes topological inversion via autophagolysosomal exocytosis (ALE), translocating from the inner leaflet of the plasma membrane to the outer extracellular surface as 'eSrc'. This is absent in normal cells. *(→ Cancer-Specific Surface Exposure Of The N-Myristoylated SRC N-Terminus Creates An Extracellular Epitope Targetable By Antibody Therapeutics; Absent In Normal Cells, Providing A Tumor-Selective Therapeutic Window.)* *(cites: a2_evi_01, a2_evi_03)*
- *Disease State Induced* · trigger: Oncogenic Transformation: normal (non-cancer) cells → primary tumor tissue (multiple cancer types) — Extracellular membrane-associated Src (eSrc) is present on the outer surface of primary tumor tissue in vivo, validated by antibody-mediated tumor cell killing in xenograft models, confirming cancer-specific outer-surface SRC accessibility. *(→ ESrc On The Outer Plasma Membrane Of Primary Tumor Cells Is Accessible To Extracellular Antibody Therapeutics, Enabling Tumor-Selective Targeting Not Achievable In Normal Tissue.)* *(cites: a2_evi_02)*
- *Dual Localization*: null → null — In normal (non-cancer) cells, c-Src rapidly cycles between the inner leaflet of the plasma membrane and intracellular late endosomes/lysosomes via cytosolic release. No outer-surface exposure occurs under these conditions. *(→ Under Normal Physiological Conditions, SRC Is Restricted To Cytoplasmic-Face And Intracellular Compartments; No Extracellular Epitope Is Accessible To Binders In The Absence Of Cancer-State ALE Pathway Activation.)* *(cites: a2_evi_04)*
- *Stress Induced* · trigger: Mechanical Stress: resting MLO-Y4 osteocytes → fluid shear stress-stimulated MLO-Y4 osteocytes — Mechanical stimulation by fluid flow induces redistribution of Src-Pyk2 complexes away from focal adhesions (plasma membrane periphery) toward the peri-nuclear/nuclear region, consistent with mechanosome translocation. *(→ Mechanical Stress-Induced Redistribution Of Src Toward The Nucleus Further Reduces Any Inner-Leaflet Plasma Membrane Association; No Gain Of Outer-Surface Accessibility Occurs, So Mechanoresponsive States Do Not Enhance Therapeutic Targeting.)* *(cites: a2_evi_12, a2_evi_13)*
- *Cell State Induced* · trigger: Immune Activation: resting monocytes → chronically oxLDL-challenged monocytes (lipid-induced inflammatory activation) — In monocytes challenged with oxLDL, myristoylation-dependent Src membrane clustering at the inner leaflet increases, driving intracellular stress signaling and sustained activation. Disruption of this clustering alleviates the inflammatory phenotype. *(→ Enhanced Inner-Leaflet Membrane Clustering Of SRC In Activated Monocytes Does Not Expose An Extracellular Epitope; Therapeutic Relevance Is Limited To Intracellular Or Indirect Targeting Strategies In This Inflammatory Context.)* *(cites: a2_evi_17)*
- *Disease State Induced* · trigger: Infection Bacterial: sham-operated rat skeletal muscle → sepsis (CLP model) rat skeletal muscle plasma membrane fraction — In sepsis, active tyrosine-phosphorylated c-Src (Tyr416) is significantly increased in plasma membrane fractions of skeletal muscle, forming a complex with the creatine transporter (CreaT) at the membrane. *(→ Increased Active Src At The Inner Leaflet Of The Plasma Membrane During Sepsis-Induced Muscle Pathology Could Modulate Transporter Function, But This Cytoplasmic-Face Enrichment Does Not Confer Extracellular Accessibility.)* *(cites: a2_evi_18)*

**Restricted-subdomain distribution**

- present: true
- severity: Moderate
- evidence: Moderate
- domain: Other
- rationale: Under normal conditions SRC is confined to the cytoplasmic face (inner leaflet) of the plasma membrane and focal adhesions — not the outer surface accessible to circulating binders (a2_evi_04, a2_evi_06). Cancer-specific ALE exocytosis is required to expose eSrc on the outer surface (a1_evi_01, a2_evi_01, a2_evi_03); this outer-surface form is absent in normal cells, restricting antibody-accessible SRC to cancer tissue.
- cites: a2_evi_04, a2_evi_06, a1_evi_01, a2_evi_01, a2_evi_03

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: SRC is a cytoplasmic-face, N-myristoylated kinase that traffics to the inner leaflet of the plasma membrane independently via lipid modification, with no obligate escort or co-receptor required for membrane association (a1_evi_03, a1_evi_04, a2_evi_04). In cancer, ALE-mediated topological inversion places eSrc on the outer surface autonomously (a1_evi_01, a2_evi_01) — still no partner required for surface delivery.
- cites: a1_evi_03, a1_evi_04, a2_evi_04, a1_evi_01, a2_evi_01

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P12931 | ref | ref | 0 | 0 aa | 536 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | P12931-2 | P12931-2 | 98.9% | — | 0 | 0 aa | 542 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Isoform | P12931-3 | P12931-3 | 96.9% | — | 0 | 0 aa | 553 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
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
- rationale: No relevant data in the ledger. SRC lacks a canonical ectodomain; no sheddase cleavage of SRC itself, no soluble SRC ectodomain detected in supernatant or serum, and no proteolytic release of the SRC protein body is documented in any ledger entry.

**Secreted form**

- present: false
- severity: Low
- evidence: Weak
- rationale: No relevant data in the ledger. SRC has no TM domain and no annotated soluble splice isoform; its membrane association is entirely via N-myristoylation. No serum/plasma soluble SRC protein, no TM-less isoform, and no antibody-decoy competition data are documented in any ledger entry.

**ECD size assessment**

- ECD class: None
- rationale: ECD length 0 residues (==0) -> none; computed deterministically from DeepTMHMM topology.

**Epitope masking**

- severity: None
- evidence: Weak
- mechanism: None
- rationale: SRC has no canonical extracellular domain, so classical epitope masking (glycan, partner occlusion, oligomerization) is not applicable to the conventional topology. The cancer-specific eSrc outer-surface form exposes the kinase domain extracellularly (a1_evi_02, a2_evi_02); no ledger evidence documents masking of this form. Deterministic prior indicates no homo-oligomer (is_homo_oligomer=false), and no ledger evidence supports oligomerization-based epitope burial.
- cites: a1_evi_02, a2_evi_02

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P12931-F1](https://alphafold.ebi.ac.uk/entry/P12931) |
| AFDB version | v6 |
| ECD mean pLDDT | 83.4 |
| ECD disordered fraction | 19.4% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P12931) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P12931](https://alphafold.ebi.ac.uk/entry/P12931) | AlphaFold DB (AF-P12931-F1, v6) |
| Isoform P12931-2 | [P12931-2](https://alphafold.ebi.ac.uk/entry/P12931-2) | AlphaFold DB |
| Isoform P12931-3 | [P12931-3](https://alphafold.ebi.ac.uk/entry/P12931-3) | AlphaFold DB |
| Mouse ortholog (Src) | [P05480](https://alphafold.ebi.ac.uk/entry/P05480) | AlphaFold DB |
| Cynomolgus ortholog (SRC) | [A0A7N9CC30](https://alphafold.ebi.ac.uk/entry/A0A7N9CC30) | AlphaFold DB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

36 entries · 19 primary · 17 secondary · 0 tertiary · 24 PMC OA.

- `a1_evi_01` · *Secondary* · Supports · Surface Expression — Src is non-canonically translocated and topologically inverted onto the outer cell surface in cancer cells (in vitro and in vivo) via autophagolysosomal exocytosis (ALE), a secretory mechanism prominent in cancer cell lines. This is a direct surface_expression claim that directly contradicts the canonical inner-leaflet-only topology. Src is described as the prototypical example of membrane-anchored proteins transported by ALE to the outer surface. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Human · cancer cell lines (unspecified) · unspecified
  > "Overexpression of the proto-oncogene Src is common to a wide variety of cancers. In this work, we found that Src is noncanonically translocated and inverted onto the cell surface in cancer, both in vitro and in vivo. We identified autophagolysosomal exocytosis (ALE) as a secretory mechanism prominent in cancer cell lines. Src represents the prototypical example of a family of membrane-anchored proteins that are transported by this process."
- `a1_evi_02` · *Secondary* · Supports · Surface Expression — Extracellular membrane-associated Src (eSrc), formed by topological inversion via ALE, was detected in primary human tumors. Anti-Src antibody-based therapies mediated tumor cell killing in cell culture and mouse xenograft models, demonstrating therapeutic engagement of the extracellular-facing Src. The protein retains its N-myristoylation yet is oriented with its kinase domain accessible from outside the cell in this non-canonical configuration. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Human · primary tumor tissue; xenograft · unspecified
  > "Furthermore, this extracellular membrane-associated Src (eSrc) was found in primary tumors, and anti-Src antibody-based therapies mediated tumor cell killing in cell culture systems and in mouse xenograft models. Thus, intracellular <i>N</i>-myristoylated proteins, prototypically Src, can be topologically inverted onto the cell surface in cancer and targeted with antibody therapeutics."
- `a1_evi_03` · *Secondary* · Refutes · Topology — SRC topology: SRC family kinases share a conserved N-terminal myristoylation motif and polybasic cluster that anchor the kinase to the cytoplasmic face of the plasma membrane, with SH3, SH2, and catalytic domains all facing the cytoplasm. No extracellular domain exists. This canonical topology is the reference against which the non-canonical ALE-mediated surface inversion must be evaluated. ([PMC13122706](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13122706/))
  - *assay*: Human
  > "SRC family kinases (SFKs), with SRC being the prototypical member, modulate NMDAR activity by phosphorylating tyrosine residues within the C-terminal tails of GluN2A and GluN2B. 12 , 13 , 14 , 15 SRC binds the NMDAR complex via interactions with ND2 (NADH dehydrogenase subunit 2) 16 , 17 and PSD-95. 18 , 19 SFKs share a conserved architecture in which an N-terminal myristoylation motif 20 , 21 , 22 and polybasic cluster anchor the kinase to the membrane, 23 while the SH3, SH2, and catalytic domains orchestrate conformational switching."
- `a1_evi_04` · *Secondary* · Refutes · Topology — SRC-family kinases require N-terminal myristoylation for function, confirming the lipid-anchor topology mechanism. This is the canonical membrane-anchoring mechanism placing SRC on the cytoplasmic face of the plasma membrane rather than presenting an extracellular domain. ([PMC12775124](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12775124/))
  - *assay*: Human
  > "Src-family kinases (SFKs), signaling enzymes implicated in tumorigenesis, require N-terminal myristoylation for function."
- `a1_evi_05` · *Secondary* · Refutes · Topology — SRC is described as a key myristoylated innate sensor requiring membrane clustering for activation; fumagillin (a myristoylation inhibitor) blocks Src membrane clustering. This confirms N-myristoylation as the primary membrane-anchoring mechanism placing SRC on the cytoplasmic leaflet, and demonstrates that disrupting myristoylation displaces SRC from the membrane. ([PMC12929915](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12929915/))
  - *assay*: Human · monocytes · unspecified
  > "To block the membrane clustering of key myristoylated innate sensors and kinases such as Src that may initiate and sustain low-grade inflammation, we tested the effects of fumagillin, a well-characterized myristoylation inhibitor originally developed as an antimicrobial agent against microsporidia and Nosema infections. 20–23 In addition, we tested the effects of Docosahexaenoic acid (DHA), a long-chain omega-3 polyunsaturated fatty acid with known beneficial effec…"
- `a1_evi_06` · *Secondary* · Refutes · Topology — NMT1 myristoylates Src; NMT1 is overexpressed in oral squamous cell carcinoma. This confirms the biochemical mechanism of Src membrane anchoring via N-myristoylation by NMT1, consistent with canonical inner-leaflet localization. ([PMC12764184](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12764184/))
  - *assay*: Human · OSCC cell lines · unspecified
  > "<h4>Background aim</h4>N-myristoyltransferase 1 (NMT1), which myristoylates Src, is highly expressed in oral squamous cell carcinoma (OSCC)."
- `a1_evi_07` · *Secondary* · Ambiguous · Tissue Expression — Phospho-specific IHC in human skin epidermis (basal/spinous cells) shows c-Src(pY419) is plasma membrane-associated. This is not extracellular-face accessibility but demonstrates SRC localizes to the plasma membrane compartment in skin tissue, consistent with inner-leaflet anchoring. The membrane pattern scoring supports the topology claim. ([PMC10946902](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10946902/))
  - *assay*: Human · basal/spinous epidermal cells · fixed
  > "Specific phosphorylation of c-Src<sup>Y419</sup> was confirmed by immunoblotting and was plasma membrane-associated in basal/spinous cells by phospho-specific immunohistochemistry."
- `a1_evi_08` · *Secondary* · Ambiguous · Tissue Expression — Subcellular fractionation of mouse brain tissue with PSD-enriched fractions shows SRC levels are reduced 38% in Posh-cKO mice. This demonstrates SRC is enriched in postsynaptic density fractions by biochemical fractionation, confirming intracellular (cytoplasmic face) localization at synapses. Not surface biotinylation; no outer-leaflet accessibility claim. ([PMC13122706](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13122706/))
  - *assay*: Mouse · mouse brain PSD fraction · unspecified
  > "Subcellular fractionation revealed a 38% ± 5% reduction in SRC levels in PSD-enriched fractions from Posh -cKO mice, whereas minimal effects were observed in total homogenate lysates ( Figure 1 C)."
- `a1_evi_09` · *Secondary* · Ambiguous · Methodological — Anti-phospho-Src antibodies (anti-Y530P-Src CST #2105; anti-Y416P-Src CST #6943) are documented with species-specific epitope mapping: Y530 human / Y527 chicken for the inhibitory site, Y419 human / Y416 chicken for the activating autophosphorylation site. Both antibodies cross-react with Fyn and may also cross-react with other SFKs (Yes). This is a critical specificity caveat for all WB-based SRC surface or localization data using these clones. ([PMC12681528](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12681528/))
  - *assay*: Human · unspecified
  > "Regarding antibodies for phosphorylated Src, anti-Y530P-Src and anti-Y416P-Src antibodies recognize the Src phosphorylated at the C-terminal region (Tyr535 in mouse Src [isoform 1]; corresponding to Tyr530 in human and Tyr527 in chicken) and the activated Src with autophosphorylation (Tyr424 in mouse Src [isoform 1]; corresponding to Tyr419 in human and Tyr416 in chicken), respectively."
- `a1_evi_10` · *Secondary* · Ambiguous · Methodological — Both anti-Y530P-Src and anti-Y416P-Src antibodies (CST #2105 and #6943) cross-react with Fyn (confirmed by supplementary data) and may cross-react with Yes and other SFKs per manufacturer datasheet. This paralog cross-reactivity must be considered when interpreting any SRC-specific localization or surface result obtained with these antibodies. ([PMC12681528](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12681528/))
  - *assay*: Human · unspecified
  > "Both anti-Y530P-Src and anti-Y416P-Src antibodies crossreact with Fyn ( Fig."
- `a1_evi_11` · *Secondary* · Ambiguous · Methodological — Antibody reagents used for Src detection: anti-total-Src (Abcam ab231081; CST #2123); anti-Y530P-Src (CST #2105); anti-Y416P-Src (CST #6943); anti-Csk (BD #610079). These clone/catalog numbers are load-bearing for MethodObservation.antibodies[] population by the block builder. ([PMC12681528](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12681528/))
  - *assay*: Human · unspecified
  > "Primary antibodies used in this study were anti-Csk (610079; BD Biosciences), anti-Y530P-Src (2105; Cell Signaling Technology), anti-Y416P-Src (6943; Cell Signaling Technology), anti-total-Src (ab231081; abcam [ Fig."
- `a1_evi_12` · *Secondary* · Ambiguous · Methodological — Antibody reagents for SRC detection with RRIDs: mouse anti-SRC (Santa Cruz sc-5266, RRID:AB_627308); rabbit anti-SRC pY461/p461 (CST #6943, RRID not fully shown). These RRID-tracked antibody identifiers are load-bearing for validation_strategy and MethodObservation.antibodies[]. ([PMC13122706](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13122706/))
  - *assay*: Mouse · unspecified
  > "REAGENT or RESOURCE SOURCE IDENTIFIER Antibodies Rabbit anti-GluN2A Cell Signaling Technology Cat#4205 RRID: AB_211229 Mouse anti-PSD-95 Thermo Fisher Scientific Cat#MA1-046 RRID: AB_2092361 Mouse anti-SRC Santa Cruz Cat#sc-5266 RRID: AB_627308 Rabbit anti-SYN Cell Signaling Technology Cat#4179 RRID: AB_1904156 Anti-GluA1 Cell Signaling Technology Cat#13185 RRID: AB_2732897 Rabbit anti-POSH Proteintech Cat#14649-1-AP RRID: AB_2187290 Rabbit anti-GluA1 p831 Cell Signaling Technology Cat#75574 RRID: AB_2799873 Rabbit anti-SRC p461 Cell Signaling Technology Cat#6943 RRID"
- `a1_evi_13` · *Secondary* · Ambiguous · Methodological — EZ-Link Sulfo-NHS-Biotin (Thermo Fisher #21217) is listed as a purchased reagent in a study examining SRC-family kinase effects on N-cadherin cell surface levels, indicating surface biotinylation was employed as a surface-accessibility assay method in this paper. ([PMC12681528](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12681528/))
  - *assay*: Mouse · mouse cortical neurons · live · non-permeabilized
  > "EZ-Link Sulfo-NHS–Biotin was purchased from Thermo Fisher Scientific (21217)."
- `a1_evi_14` · *Secondary* · Ambiguous · Methodological — Antibody reagents for SRC detection: anti-SRC (CST #2109) and anti-phospho-SRC Tyr416 (CST #6943) used in prostate cancer cell line experiments. These catalog numbers populate MethodObservation.antibodies[] for the block builder. ([PMC13034504](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13034504/))
  - *assay*: Human · prostate cancer cell lines
  > "Anti-ERK1/2 (cat. no. 9102), anti-phospho-ERK1/2 (T202/Y204) (cat. no. 4370), anti-SRC (cat. no. 2109), anti-phospho-SRC (Tyr416; cat. no. 6943), anti-JNK (cat. no. 9252), anti-phospho-JNK (T183/Y185; cat. no. 4668), anti-p38 MAPK (cat. no. 8690) and anti-phospho-p38 MAPK (T180/Y182; cat. no. 4511) antibodies were purchased from Cell Signaling Technology, Inc."
- `a1_evi_15` · *Secondary* · Ambiguous · Methodological — Antibody reagents for SRC detection in endothelial cell studies: c-Src pY416 (CST #2101); anti-c-Src (CST #2109). These catalog numbers are load-bearing for MethodObservation.antibodies[] by the block builder. ([PMC12925215](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12925215/))
  - *assay*: Human · endothelial cells
  > "In this study, the following antibodies were used: mouse anti–PAR1 WEDE (Beckman Coulter, #IM2584), anti-Cav1 (CST, #3267S and BD, #610060), anti-Cav1 Y14 phospho antibody (CST, #3251), anti-βarr2 (Abcam, #ab54790), GAPDH (GeneTex, #GT239), c-Src Y416 (CST, #2101), anti-c-Src (CST, #2109), GRK5 (Santa Cruz, #sc-518005), GRK5 polyclonal antibody (Invitrogen, #PA5-96262) anti-GRK4-6 (Millipore, #05-466), anti-HA (CST, #3724S), anti-rabbit IgG (CST, #2729), anti-β-Tubulin (CST, #86298), anti–early endosome antigen-1 (BD Biosciences, #610457), anti-Vinculin (Sigma, #V9131)"
- `a1_evi_16` · *Primary* · Refutes · Contradictory — Src membrane clustering (via N-myristoylation) drives intracellular stress signaling and sustained monocyte activation; fumagillin (selective myristoylation inhibitor) blocks Src membrane clustering and alleviates monocyte activation. This is a contradictory/refuting finding relative to outer-surface accessibility: it demonstrates SRC surface engagement occurs on the cytoplasmic face via myristoylation-dependent clustering, not via an extracellular domain. ([PMC12929915](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12929915/))
  - *assay*: Human · human monocytes · live · non-permeabilized
  > "Mechanistically, we defined the membrane clustering of Src is responsible for the generation of intra-cellular stress signaling and sustained monocyte activation, which can be alleviated by the administration of fumagillin, a selective inhibitor of protein myristoylation and Src membrane clustering."
- `a2_evi_01` · *Primary* · Supports · Surface Expression — SRC undergoes noncanonical surface translocation onto the outer cell surface in cancer cells, mediated by autophagolysosomal exocytosis (ALE). This inverted 'eSrc' form exposes the N-myristoylated protein on the extracellular face — a cancer-specific accessibility modulation absent in normal cells. Baseline: normal cells show inner-leaflet SRC only. Modulating state: cancer overexpression + ALE pathway. Change: SRC appears on outer plasma membrane surface. Implication: extracellular Src is targetable by antibody therapeutics in cancer contexts. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Human · cancer cell lines (multiple) and mouse xenograft models · live · non-permeabilized
  > "Overexpression of the proto-oncogene Src is common to a wide variety of cancers. In this work, we found that Src is noncanonically translocated and inverted onto the cell surface in cancer, both in vitro and in vivo. We identified autophagolysosomal exocytosis (ALE) as a secretory mechanism prominent in cancer cell lines. Src represents the prototypical example of a family of membrane-anchored proteins that are transported by this process."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — Extracellular membrane-associated Src (eSrc) is present in primary tumor tissue in vivo, confirming that cancer-specific surface translocation of SRC is not merely a cell-line artifact. Anti-Src antibody-based therapies mediate tumor cell killing in xenograft models, validating eSrc as an accessible surface target in cancer primary tissue. (https://pubmed.ncbi.nlm.nih.gov/41818370/)
  - *assay*: Human · primary tumor tissue and mouse xenograft · unspecified · non-permeabilized
  > "Furthermore, this extracellular membrane-associated Src (eSrc) was found in primary tumors, and anti-Src antibody-based therapies mediated tumor cell killing in cell culture systems and in mouse xenograft models. Thus, intracellular <i>N</i>-myristoylated proteins, prototypically Src, can be topologically inverted onto the cell surface in cancer and targeted with antibody therapeutics."
- `a2_evi_03` · *Primary* · Supports · Surface Expression — Exocytosis exposes Src at the outer surface of cancer cells, positioning it for therapeutic targeting. This represents a disease-state-induced gain of extracellular accessibility for an otherwise intracellular kinase. (https://pubmed.ncbi.nlm.nih.gov/41818382/)
  - *assay*: Human · cancer cell lines · live · non-permeabilized
  > "Exocytosis exposes Src at the outer surface of cancer cells, poised for therapeutic targeting."
- `a2_evi_04` · *Primary* · Refutes · Surface Expression — c-Src is a non-palmitoylated SFK that rapidly exchanges between the plasma membrane (cytoplasmic face) and intracellular late endosomes/lysosomes via cytosolic release. Unlike palmitoylated Lyn which traffics via Golgi exocytosis, c-Src cycles between PM and late endosomal/lysosomal compartments. Under normal (non-cancer) conditions, c-Src is restricted to the inner leaflet of the plasma membrane and intracellular organelles — it is NOT on the outer cell surface. (https://pubmed.ncbi.nlm.nih.gov/17537435/)
  - *assay*: Unspecified · cell lines (unspecified) · live · permeabilized
  > "Here, we show by time-lapse monitoring combined with photobleaching techniques that c-Src, a non-palmitoylated SFK, is rapidly exchanged between the plasma membrane and intracellular organelles representing late endosomes/lysosomes possibly through its cytosolic release. Although Lyn, a palmitoylated SFK, is exocytosed to the plasma membrane via the Golgi apparatus along the secretory pathway, lack of palmitoylation directs Lyn away from the exocytotic transport to the c-Src-type trafficking between the plasma membrane and late endosomes/lysosomes."
- `a2_evi_05` · *Primary* · Refutes · Surface Expression — c-Src and a non-palmitoylated Lyn mutant are recruited and immobilized at focal adhesions when their SH2 domains mediate protein-protein interactions. This reveals a cytoplasmic-face localization at focal adhesion subdomains, distinct from outer surface presence. Palmitoylation inhibits focal adhesion recruitment. Two distinct trafficking pathways for SFKs underlie their functional specificity. (https://pubmed.ncbi.nlm.nih.gov/17537435/)
  - *assay*: Unspecified · cell lines (unspecified) · live · permeabilized
  > "Intriguingly, c-Src and a non-palmitoylated Lyn mutant are efficiently delivered and immobilized to focal adhesions when their SH2 domains are able to mediate protein-protein interactions in place of intramolecular bindings. However, palmitoylation of Lyn inhibits its recruitment to focal adhesions. These results suggest that palmitoylation of SFKs is critical for SFK localization and trafficking and implicate that two distinct trafficking pathways for SFKs may be involved in SFKs' specific functions."
- `a2_evi_06` · *Primary* · Refutes · Surface Expression — The majority of activated Src molecules localize at focal adhesions (cytoplasmic face). Src is activated at the cell membrane (inner leaflet) and translocates to focal adhesions. Myristoylation is required for cell membrane targeting, which is essential for focal adhesion recruitment. This confirms SRC localization at the cytoplasmic face of the plasma membrane and focal adhesions — not at the extracellular surface under normal conditions. (https://pubmed.ncbi.nlm.nih.gov/28543306/)
  - *assay*: Unspecified · live cell imaging (cell line unspecified) · live · non-permeabilized
  > "The role of myristoylation in the localization and catalytic activity of Src at focal adhesions was investigated by live-cell imaging and site-directed mutagenesis. Although the majority of activated Src molecules are localized at focal adhesions, it is unclear how activated Src molecules are recruited to focal adhesions. Because Src is activated at the cell membrane, translocation of Src to cell membranes is considered to be essential for its recruitment to focal adhesions."
- `a2_evi_07` · *Primary* · Refutes · Surface Expression — A membrane-targeting-deficient Src mutant (SrcG2A, lacking myristoylation) can still localize at focal adhesions via direct cytosol-to-focal-adhesion recruitment, indicating Src's focal adhesion localization is partially membrane-independent. These directly recruited Src molecules enhance paxillin dynamics. This demonstrates that SRC biology is cytoplasmic-face and intracellular, with no outer surface presence. (https://pubmed.ncbi.nlm.nih.gov/28543306/)
  - *assay*: Unspecified · cell line (unspecified) · live · non-permeabilized
  > "Membrane-targeting-deficient Src mutant SrcG2A localizes at focal adhesions, indicating direct recruitment of Src from cytosol to focal adhesions. Furthermore, directly recruited Src molecules are shown to enhance paxillin dynamics at focal adhesions. These results reveal that the regulation of Src activation and translocation is more complex than previously suggested."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — In human skin equivalent (HSE) tissue, phospho-c-Src Y419 is plasma membrane-associated in basal and spinous keratinocytes, as demonstrated by phospho-specific immunohistochemistry. This places active Src at the inner leaflet of the PM in skin epithelial cells, with enrichment in proliferative basal cells. ([PMC10946902](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10946902/))
  - *assay*: Human · basal and spinous keratinocytes, human skin equivalent (HSE) · fixed · permeabilized
  > "Specific phosphorylation of c-Src<sup>Y419</sup> was confirmed by immunoblotting and was plasma membrane-associated in basal/spinous cells by phospho-specific immunohistochemistry."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — In human skin equivalent (HSE), phospho-c-Src Y419 is dramatically and significantly increased in protein extracts when the skin irritant lactic acid is applied topically for 15 minutes, compared to non-irritant controls. This demonstrates stress-induced activation of SRC in skin epithelial tissue in response to chemical irritants. ([PMC10946902](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10946902/))
  - *assay*: Human · human skin equivalent (HSE), keratinocytes · fixed · permeabilized
  > "Phosphokinase array analysis of HSE protein extracts showed a dramatic and significant increased abundance of phospho‐c‐Src Y419 when the known skin irritant, lactic acid (LA), was topically applied to HSE for 15 minutes, in comparison to the non‐irritants methylparaben (MP) and cocamide diethanolamine (Co‐DEA), or water applied as carrier control (Figure 1 )."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — c-Src is expressed (total and activated forms) in all four malignant pleural mesothelioma (MPM) cell lines tested, establishing SRC expression in MPM as a disease context. (https://pubmed.ncbi.nlm.nih.gov/17620427/)
  - *assay*: Human · MPM cell lines (4 lines) · fixed · permeabilized
  > "Malignant pleural mesothelioma (MPM) is a deadly disease with few systemic treatment options. One potential therapeutic target, the non-receptor tyrosine kinase c-Src, causes changes in proliferation, motility, invasion, survival, and angiogenesis in cancer cells and may be a valid therapeutic target in MPM. To test this hypothesis, we determined the effects of c-Src inhibition in MPM cell lines and examined c-Src expression and activation in tissue samples. We analyzed four MPM cell lines and found that all expressed total and activated c-Src."
- `a2_evi_11` · *Primary* · Supports · Tissue Expression — In malignant pleural mesothelioma (MPM) tumor tissue samples, activated Src (phospho-Src Y419) shows membrane distribution (as well as cytoplasmic) that is elevated in advanced-stage disease and correlates with metastasis. Lower membrane expression of inactive c-Src (p-Src Y530) correlates with advanced N stage. This IHC study of human MPM tissue demonstrates that in cancer tissue, activated Src distributes to the tumor cell membrane (inner leaflet) with disease-stage-dependent modulation. (https://pubmed.ncbi.nlm.nih.gov/17620427/)
  - *assay*: Human · MPM primary tumor tissue · fixed · permeabilized
  > "However, expression of activated Src (p-Src Y419) on the tumor cell membrane was higher in patients with advanced-stage disease; the presence of metastasis correlated with higher membrane (P = 0.03) and cytoplasmic (P = 0.04) expression of p-Src Y419. Lower levels of membrane expression of inactive c-Src (p-Src Y530) correlated with advanced N stage (P = 0.02). Activated c-Src may play a role in survival, metastasis, and invasion of MPM, and targeting c-Src may be an important therapeutic strategy."
- `a2_evi_12` · *Primary* · Refutes · Surface Expression — In MLO-Y4 osteocytes, Src-Pyk2 protein complexes concentrate at the periphery of focal adhesions and the peri-nuclear region, as determined by co-localization studies. This establishes SRC subcellular localization at focal adhesion subdomains and peri-nuclear regions (cytoplasmic face) in osteocytes. ([PMC8699642](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8699642/))
  - *assay*: Mouse · MLO-Y4 osteocytes · fixed · permeabilized
  > "Src-Pyk2 complexes were concentrated at the periphery of focal adhesions and the peri-nuclear region."
- `a2_evi_13` · *Primary* · Refutes · Surface Expression — Mechanical stimulation by fluid flow induces apparent accumulation of Src-Pyk2 protein complexes in the peri-nuclear/nuclear region in osteocytes, consistent with mechanosome behavior. This represents stress-induced redistribution of Src from focal adhesions toward the nucleus — a cell-state-induced subcellular relocalization away from the plasma membrane in osteocytes. ([PMC8699642](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8699642/))
  - *assay*: Mouse · MLO-Y4 osteocytes · fixed · permeabilized
  > "Finally, mechanical stimulation by fluid flow induced apparent accumulation of Src-Pyk2 protein complexes in the peri-nuclear/nuclear region, consistent with the proposed behavior of a mechanosome in response to a mechanical stimulus."
- `a2_evi_14` · *Primary* · Supports · Tissue Expression — NMT1 (N-myristoyltransferase 1), which myristoylates Src, is highly expressed in oral squamous cell carcinoma (OSCC), establishing OSCC as a disease context where Src myristoylation-dependent membrane anchoring is active. ([PMC12764184](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12764184/))
  - *assay*: Human · oral squamous cell carcinoma (OSCC) tissue · fixed · permeabilized
  > "<h4>Background aim</h4>N-myristoyltransferase 1 (NMT1), which myristoylates Src, is highly expressed in oral squamous cell carcinoma (OSCC)."
- `a2_evi_15` · *Secondary* · Supports · Tissue Expression — SRC protein expression is detected in all OSCC-derived cell lines tested (HSC-2, HSC-3, WK2, WK3F), confirming ubiquitous SRC expression in oral squamous cell carcinoma cell lines including both well-differentiated and poorly-differentiated tongue carcinoma cells. ([PMC12764184](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12764184/))
  - *assay*: Human · HSC-2, HSC-3, SAS, WK2, WK3F (OSCC cell lines) · fixed · permeabilized
  > "HSC-2, HSC-3, WK2, and WK3F derived from human OSCC <i>in vitro</i> were also used to confirm malignancy by siRNA of siNMT1 in OSCC cell lines.<h4>Results</h4>NMT1 and Src expression was detected in all OSCC cell lines."
- `a2_evi_16` · *Primary* · Ambiguous · Surface Expression — In OSCC cells, myristoylated proteins (including Src, as the target of NMT1) accumulate primarily in the cytoplasm with pronounced perinuclear localization, not at the plasma membrane surface. NMT1 itself localizes primarily in the cytoplasm. This suggests that despite myristoylation enabling membrane anchoring, a significant fraction of Src-related myristoylated proteins pool in cytoplasmic/perinuclear compartments in OSCC. ([PMC12764184](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12764184/))
  - *assay*: Human · OSCC cell lines · fixed · permeabilized
  > "Compared with the control, NMT1 was localized primarily in the cytoplasm, whereas myristoylated proteins were observed in the cytoplasm, with pronounced accumulation around the nucleus."
- `a2_evi_17` · *Primary* · Supports · Tissue Expression — In monocytes, membrane clustering of Src (driven by myristoylation) is responsible for generating intracellular stress signaling and sustained monocyte activation. Fumagillin, a selective inhibitor of protein myristoylation, disrupts Src membrane clustering and alleviates the chronic inflammatory phenotype. This establishes Src membrane clustering at the inner leaflet as a cell-state modulator in monocytes under lipid-induced inflammatory conditions. ([PMC12929915](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12929915/))
  - *assay*: Human · monocytes (oxLDL-challenged) · unspecified · non-permeabilized
  > "Mechanistically, we defined the membrane clustering of Src is responsible for the generation of intra-cellular stress signaling and sustained monocyte activation, which can be alleviated by the administration of fumagillin, a selective inhibitor of protein myristoylation and Src membrane clustering."
- `a2_evi_18` · *Primary* · Supports · Tissue Expression — In skeletal muscle (gastrocnemius) during sepsis, tyrosine-phosphorylated c-Src (Tyr416, active form) is detected in both total homogenates and plasma membrane fractions, forming a complex with creatine transporter (CreaT). This demonstrates active c-Src presence at the plasma membrane fraction of skeletal muscle under sepsis disease state. (https://pubmed.ncbi.nlm.nih.gov/11934669/)
  - *assay*: Rat · gastrocnemius skeletal muscle, plasma membrane fraction · fixed · permeabilized
  > "Western blotting of the immunoprecipitated CreaT with an anti-phosphotyrosine or anti-phospho-c-Src (Y-416) antibody revealed that tyrosine phosphorylation of the CreaT and tyrosine-phosphorylated c-Src (Tyr(416)) expression in the CreaT-c-Src complex were significantly increased after CLP compared with sham operation. These changes were observed in homogenates and plasma membrane fractions of gastrocnemius muscles."
- `a2_evi_19` · *Secondary* · Supports · Tissue Expression — High levels of SRC activity in nasopharyngeal carcinoma (NPC) are associated with epithelial-to-mesenchymal transition (EMT) and poor prognosis, establishing SRC as an active signaling molecule in NPC tumor disease context. ([PMC10093038](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10093038/))
  - *assay*: Human · nasopharyngeal carcinoma (NPC) tumor cells · unspecified · permeabilized
  > "Previous studies by others have found that high levels of SRC activity in NPCs are associated with EMT and a poor prognosis."
- `a2_evi_20` · *Primary* · Supports · Tissue Expression — In osteoblastic lineage cells (MC3T3-E1), fluid shear stress increases c-Src activation (Tyr416 phosphorylation) and promotes redistribution of RANKL toward the cell periphery/membrane fraction. Constitutively active c-Src (Y527F) enhances RANKL peripheral localization even without shear stress, showing that c-Src activation state modulates downstream membrane protein trafficking in osteoblasts. This places SRC activation (inner leaflet) as a mechanoresponsive modulator in bone tissue. ([PMC13054614](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13054614/))
  - *assay*: Mouse · MC3T3-E1 osteoblastic cells · fixed · permeabilized
  > "Fluid shear stress increased c-Src activation (Tyr416 phosphorylation) and promoted redistribution of RANKL toward the cell periphery, accompanied by an increase of RANKL in the membrane fraction."

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

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence low — Confidence is low for two compounding reasons. First, the only direct evidence for outer-surface SRC accessibility comes from a single research paper (PMID:41818370) reporting the ALE-mediated topological inversion mechanism; no independent group has yet replicated this finding with a different methodology or in a different cancer model. Second, the canonical literature — spanning decades of independent biochemical, imaging, and pharmacological work — firmly establishes SRC as an inner-leaflet peripheral kinase with no extracellular domain, constituting a high-severity contradicting baseline. Lifting confidence to moderate would require at least one independent group to confirm eSrc outer-surface exposure (e.g., via non-permeabilized flow cytometry or surface biotinylation specifically detecting SRC) in additional cancer types, ideally without reliance on the same functional antibody-killing readout used in the original report.*
