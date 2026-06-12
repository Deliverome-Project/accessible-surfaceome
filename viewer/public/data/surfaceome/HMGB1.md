# HMGB1 — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-31T20:15:43.094500Z · model `claude-sonnet-4-6`*

> HMGB1 is a nuclear chromatin-binding protein with no transmembrane domain that becomes extracellularly accessible only upon cell activation, stress, or death. The entire ledger lacks a qualifying direct surface assay of HMGB1 on viable cells (live-cell flow, non-perm IF, or surface biotinylation with HMGB1 as a confirmed hit). Evidence shows HMGB1 in cell supernatants (pyroptosis, senescence SASP), on EV exteriors (proteinase-K confirmed, EV-shielded), and in solution binding TREM-1/RAGE, but none of these constitute plasma-membrane surface detection. Surface accessibility is therefore 'no' by the direct-assay gate.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:4983](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:4983) |
| UniProt | [P09429](https://www.uniprot.org/uniprotkb/P09429) |
| NCBI Gene | [3146](https://www.ncbi.nlm.nih.gov/gene/3146) |
| Ensembl | [ENSG00000189403](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000189403) |
| Subcategory | Other |
| Surface accessibility | No |
| Confidence | Moderate |
| Evidence grade | Weak |
| Triage signal | Possibly Accessible |
| Headline risks | Secreted Form |

## 1. Executive summary

**HMGB1 has no validated plasma-membrane surface presence; it is released as a soluble DAMP into extracellular fluid upon inflammation, necrosis, ferroptosis, senescence, or chemotherapy stress, and appears on EV exteriors in arthritic disease state.**

HMGB1 is a nuclear chromatin-binding protein with no transmembrane domain that becomes extracellularly accessible only upon cell activation, stress, or death. The entire ledger lacks a qualifying direct surface assay of HMGB1 on viable cells (live-cell flow, non-perm IF, or surface biotinylation with HMGB1 as a confirmed hit). Evidence shows HMGB1 in cell supernatants (pyroptosis, senescence SASP), on EV exteriors (proteinase-K confirmed, EV-shielded), and in solution binding TREM-1/RAGE, but none of these constitute plasma-membrane surface detection. Surface accessibility is therefore 'no' by the direct-assay gate.

**Family / classification** — UniProt family: HMGB family · HGNC gene group(s): Canonical high mobility group · functional class: Miscellaneous.

**Triage first-pass reasoning** — HMGB1 is primarily a nuclear chromatin-binding protein and also resides in the cytoplasm, but it is actively secreted extracellularly via two distinct pathways: (1) active, non-classical secretion from immune/activated cells (acetylation-triggered translocation to cytoplasm then secretion); and (2) passive release from necrotic/dying cells. Once extracellular, HMGB1 binds cell-surface receptors (RAGE, TLR2, TLR4) and this interaction has been exploited therapeutically — multiple anti-HMGB1 antibody programs and RAGE-targeting strategies exist. Surface biotinylation on intact cells and flow cytometry data show HMGB1 can associate with the outer leaflet of the PM bound to surface RAGE. This is cell-state-induced (inflammation, DAMPs, cell death), not constitutive. Checking contextual buckets: cell_state_induced — YES, display under inflammatory activation/necrosis; tissue_restricted — no, broad; lysosomal_exocytosis — no documented lysosomal route; dual_localization — nuclear dominant; stable_surface_attachment — binds RAGE wash-resistantly on surface. Best fit is cell_state_induced surface display.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=No · conf=Moderate · subcategory=Other · ecd=None |
| Classification | reason=Secreted Only · family=Miscellaneous · state-dependence=High · induction-trigger=Immune |
| Expression | level=High · breadth=Pan Tissue · specificity=Mostly Intracellular · low-endogenous=false · tumor-associated=false · orphan-receptor=false · OE-precedent=false |
| Risks | shed=false · secreted=true · co-receptor=None · masking=true · restricted-subdomain=false |
| Evidence | grade=Weak · density=High · live-cell-surface=false · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=0 · N-term-ECF=false · C-term-ECF=false |

**Facet rationales**

- *Expression level*: IHC in primary gastric adenocarcinoma shows 81.76% positivity (a2_evi_01, a2_evi_02); intracellular HMGB1 is abundant in tumor cells by permeabilized flow (a1_evi_14); broad nuclear expression is well established across cell types.
- *Expression breadth*: HMGB1 is a ubiquitous nuclear chromatin-binding protein expressed broadly across immune cells, epithelial tumors, neurons, and senescent cells (a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_07, a2_evi_12); breadth is pan-tissue.
- *Surface specificity*: Primary compartment is nucleus/cytoplasm (a1_evi_14, a2_evi_09); extracellular form is soluble/secreted or EV-associated (a1_evi_15, a1_evi_16, a2_evi_10, a2_evi_11), not plasma-membrane-anchored. No direct surface staining of HMGB1 on viable cells exists in the ledger.
- *Known ligand*: HMGB1 binds RAGE and TLR4 on neutrophils and macrophages as a DAMP ligand (a2_evi_05), and also binds TREM-1 ectodomain in solution (a1_evi_18); multiple validated receptor interactions are documented.
- *Low endogenous expression*: Derived from expression_level='high' (not low/absent → not flagged). IHC in primary gastric adenocarcinoma shows 81.76% positivity (a2_evi_01, a2_evi_02); intracellular HMGB1 is abundant in tumor cells by permeabilized flow (a1_evi_14); broad nuclear expression is well established across cell types.
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Weak

No claim in this ledger places HMGB1 on the viable-cell plasma membrane via a direct surface method (live/non-perm flow, non-perm IF, surface biotinylation with HMGB1 as a confirmed hit, or membranous IHC). The strongest surface-topology evidence (a1_evi_08, a1_evi_09) uses proteinase-K protection on exosome vesicles — this confirms HMGB1 on the EV exterior, not the plasma membrane of living cells (shed/secreted_or_EV form per the grading rules). Remaining claims are: methodology descriptions where HMGB1 is not a reported hit (a1_evi_01–05), receptor-surface flow assays where HMGB1 is the stimulus not the target (a1_evi_11–12), intracellular permeabilized flow (a1_evi_14), supernatant/ELISA soluble detection (a1_evi_15–17), and review/functional assertions (a1_evi_07, a1_evi_10, a1_evi_17–18). The overall grade is therefore `weak`.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Low | Methodology anchor for CSC/surface-biotinylation in study, but HMGB1 not confirmed as a detected hit in this assay. |
| a1_evi_02 | Tangential | Low | APEX2 surface-biotin + MS methodology description; HMGB1 not reported as a detected hit. |
| a1_evi_03 | Tangential | Low | WB validation of APEX2 assay specificity; HMGB1 not the target measured. |
| a1_evi_04 | Tangential | Low | High non-specific background caveat for the APEX2-MS step; HMGB1 not a confirmed hit. |
| a1_evi_05 | Tangential | Moderate | Surfaceome MS on chondrogenic cultures; HMGB1 not explicitly confirmed as a detected hit in the quote. |
| a1_evi_06 | Tangential | Low | Antibody reagent list entry; no surface assay result for HMGB1 itself. |
| a1_evi_07 | Tangential | Low | Review-level redox/topology note; cysteines described as 'cell surface' but review assertion only, no direct assay. |
| a1_evi_08 | Tangential | Moderate | HMGB1 on exosome exterior — shed/EV form, not viable-cell plasma membrane surface. |
| a1_evi_09 | Tangential | Moderate | Proteinase-K protection on intact exosomes confirms EV-exterior HMGB1; not viable-cell PM surface exposure. |
| a1_evi_10 | Tangential | Low | Neutralizing anti-HMGB1 blocks complement; extracellular soluble form, not cell-surface plasma membrane. |
| a1_evi_11 | Tangential | Low | Non-perm flow on mast cells measures HMGB1 receptors (Dectin-1, TLR2), not HMGB1 itself on cell surface. |
| a1_evi_12 | Tangential | Low | Non-perm flow/confocal confirms receptor surface levels; HMGB1 is stimulus, not the measured target. |
| a1_evi_13 | Tangential | Low | Live-cell flow methodology anchor; HMGB1 not confirmed as measured target. |
| a1_evi_14 | Tangential | Moderate | Flow detects intracellular HMGB1 (permeabilized/fixed); consistent with predominantly intracellular localization. |
| a1_evi_15 | Tangential | Moderate | HMGB1 in supernatant of pyroptotic cells; shed/secreted form, not stable plasma-membrane surface. |
| a1_evi_16 | Tangential | Moderate | ELISA of conditioned medium; soluble secreted HMGB1, not cell-surface assay. |
| a1_evi_17 | Tangential | Low | Review assertion: HMGB1 released as soluble DAMP in senescence; not a surface assay. |
| a1_evi_18 | Tangential | Low | sTREM-1 pulldown shows extracellular HMGB1 ligand activity in solution; not a viable-cell surface assay. |
| a1_evi_19 | Tangential | Low | Surface biotinylation for NHE3, not HMGB1; HMGB1 not a detected hit in this assay. |

### Flow cytometry (3 methods)

#### Live Cell Flow — Weak Or Ambiguous · Unclear

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Mast cells (MCs) stained non-permeabilized for Dectin-1, Dectin-2, TLR2 surface expression after HMGB1 stimulation; HMGB1 is the stimulus not the detected target | Primary Human Cell | Moderate | 2 |

#### Live Cell Flow — Weak Or Ambiguous · Unclear

*Permeabilization: Live Cell · expression: Unknown*

#### Fixed Cell Flow — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| PyMT-B6 mouse breast cancer cells 24 h post-taxane chemotherapy; intracellular HMGB1 detected by fixed/permeabilized flow cytometry | Established Cell Line | Moderate | 1 |

### Surface biotinylation (2 methods)

#### Cell Surface Capture — Weak Or Ambiguous · Unclear

*Permeabilization: Live Cell · expression: Unknown*

#### Surface Biotinylation — Weak Or Ambiguous · Unclear

*Permeabilization: Live Cell · expression: Unknown*

### Glycoproteomics (1 method)

#### N Glycoproteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Chondrogenic micromass cultures at days 1, 3, 6, 10, 15 of differentiation; sialoglycoprotein-enriched surface proteome by aminooxy-biotin + LC-MS/MS | Primary Human Cell | Moderate | 1 |

### Proximity labeling (1 method)

#### Surface Biotinylation — Weak Or Ambiguous · Unclear

*Permeabilization: Live Cell · expression: Unknown*

### Functional surface assay (2 methods)

#### Unknown — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-HMGB1 neutralizing (2G7) — Intracellular epitope; Monoclonal; None validation (None); Mouse IgG2b; epitope = HMGB1 A-box aa 53–63 (nuclear/intracellular domain when cell-resident; exposed on surface of secreted/exosome-displayed form). Non-commercial; originally from Critical Therapeutics / Kevin Tracey lab.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HMGB1 displayed on exterior of exosomes from MIA-injured mouse knee tissue; proteinase-K protection assay confirmed exterior localization; 2G7 neutralization abrogated exosome-induced neuronal NF-κB/senescence effects | Ex Vivo | Moderate | 2 |

#### Unknown — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Unknown · expression: Unknown*

**Antibodies**

- anti-HMGB1 neutralizing — Unknown epitope; Unknown; None validation (None)

### Other (4 methods)

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-HMGB1 (1D12A6 · Proteintech · 66525-1-Ig) — Intracellular epitope; Monoclonal; Weak validation (Vendor Claim Only); Mouse monoclonal raised against full-length human HMGB1; primarily validated for WB/IHC. No surface-accessibility or HMGB2/3 cross-reactivity data reported.

#### Whole Cell Proteomics — Weak Or Ambiguous · Unclear

*Permeabilization: Unknown · expression: Unknown*

**Antibodies**

- anti-HMGB1 — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HMGB1 pulled down by sTREM-1-Sepharose resin, resolved by SDS-PAGE + WB; demonstrates extracellular HMGB1–TREM-1 ectodomain binding in solution | Unknown | Moderate | 1 |

#### Whole Cell Proteomics — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| HMGB1 quantified in supernatant of VSV-S-infected HN12 and CAL27 head-and-neck cancer cell lines by ELISA (n=6); elevated alongside LDH and IL-1β indicating pyroptosis-associated release | Established Cell Line | High | 2 |

#### Whole Cell Proteomics — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Unknown · expression: Unknown*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Review-level citation: HMGB1 released into extracellular milieu as DAMP during cellular senescence (SASP context) | Unknown | Moderate | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Senescent cells — HMGB1 released as DAMP into extracellular milieu (SASP marker), review assertion | Unknown | Bulk Protein | Moderate | 1 |
| HN12 and CAL27 head-and-neck cancer cells undergoing VSV-S-induced pyroptosis — HMGB1 detected in supernatant by ELISA | Established Cell Line | Bulk Protein | High | 2 |
| PyMT-B6 breast cancer cells 24h post-taxane — intracellular HMGB1 detected by permeabilized flow cytometry | Established Cell Line | Bulk Protein | Moderate | 1 |

**Contradicting evidence**

- *Intracellular Pool* (severity Moderate): Flow cytometry on permeabilized, fixed PyMT-B6 breast cancer cells detects HMGB1 as an intracellular pool 24 hours after taxane chemotherapy treatment. The assay explicitly measures intracellular HMGB1, not surface-localized protein, indicating that the dominant detectable signal in this context is inside the cell rather than on its surface.
  - Likely explanation: Permeabilization of cells in this assay allows antibody access to the nuclear/cytoplasmic HMGB1 reservoir, which far exceeds any transient surface pool. Taxane treatment may trigger active secretion, but the intracellular stock remains large and dominates the flow cytometry signal. Surface HMGB1 could still exist transiently but would not be captured by this assay design.
- *Secreted Only* (severity Moderate): HMGB1 is detected in cell culture supernatants of pyroptotic HN12 and CAL27 head-and-neck cancer cells following VSV-S infection, quantified by ELISA in conditioned medium. This passive release during membrane pore formation (pyroptosis) represents HMGB1 as a shed/secreted soluble DAMP rather than a stably membrane-anchored surface protein. Similarly, review literature cites HMGB1 secretion into the extracellular milieu as a canonical marker of the senescence-associated secretory phenotype (SASP), reinforcing the view that the predominant extracellular form is soluble rather than surface-tethered.
  - Likely explanation: HMGB1 lacks a classical transmembrane domain and signal peptide; its extracellular appearance is driven by unconventional secretion (active acetylation-dependent secretion, pyroptotic pore release, or necrotic leakage). Soluble HMGB1 in the supernatant does not preclude transient or low-level surface association, but the dominant extracellular form appears to be freely secreted, which would complicate strategies requiring stable surface accessibility for therapeutic targeting.
- *Other* (severity Low): Flow cytometry and confocal microscopy on non-permeabilized mast cells confirm surface expression of HMGB1 receptors (Dectin-2, TLR2) but show no significant change in receptor levels following HMGB1 stimulation. This is ambiguous for the surface-accessibility hypothesis: while it confirms HMGB1 can engage cell surfaces via receptors, it provides no direct evidence of HMGB1 itself being stably surface-displayed, and the lack of receptor upregulation suggests receptor-mediated surface engagement of HMGB1 may be limited or saturable.
  - Likely explanation: This evidence pertains to HMGB1 receptor surface levels rather than HMGB1 surface localization per se. The absence of receptor upregulation after HMGB1 treatment may reflect constitutive expression levels being sufficient for ligand engagement, or that HMGB1 functions predominantly in a soluble paracrine mode rather than through stable surface-to-surface contact.

## 4. Biological context

**Cell types** *(orthogonal cell-type index)*

| Cell type | Ontology | Present in tissues | Species | Cites |
|---|---|---|---|---|
| macrophages | — | — | Unspecified | 2 |
| neutrophils | — | — | Unspecified | 1 |
| senescent cells | — | — | Unspecified | 1 |
| glioma cells | — | — | Human | 2 |
| mammary tumor cells (PyMT-B6) | — | — | Mouse | 1 |
| neurons | — | brain | Unspecified | 2 |
| T cells | — | — | Human | 1 |
| mast cells | — | — | Unspecified | 1 |

**Cell states**

- *senescent* — Senescent cells release HMGB1 into the extracellular milieu as a SASP/DAMP factor, representing a nuclear-to-extracellular shift in localization upon senescence induction. *(cites: a2_evi_06)*
- *ferroptotic* — Ferroptosis in glioma cells upregulates HMGB1 mRNA and drives secretion of acetylated HMGB1 into the extracellular compartment, increasing extracellular HMGB1 availability. *(cites: a2_evi_07, a2_evi_08)*
- *chemotherapy-stressed* — Taxane chemotherapy treatment of mammary tumor cells induces TLR4-dependent active secretion of HMGB1, shifting it from intracellular compartments toward extracellular release. *(cites: a2_evi_09)*
- *inflammatory* — Infection/inflammatory stimuli induce HMGB1 release from activated immune cells (macrophages) and damaged/necrotic cells, increasing extracellular HMGB1 as a DAMP in sepsis and inflammatory contexts. *(cites: a2_evi_04, a2_evi_05)*
- *tumor* — Gastric adenocarcinoma tissue shows markedly upregulated HMGB1 expression (81.76% IHC positivity) versus normal mucosa, with levels correlating with tumor size, invasion depth, and clinical stage. *(cites: a2_evi_01, a2_evi_02, a2_evi_03)*
- *arthritis (joint injury)* — MIA-induced joint injury drives surface display of HMGB1 on the exterior of joint-derived exosomes, enabling long-range DAMP signaling to the brain and inducing neuronal NF-κB activation and senescence. *(cites: a2_evi_10, a2_evi_11)*
- *activated* — T cell activation induces changes in cysteine oxidation state at HMGB1 surface residues C23, C45, and C106, modulating its anti-inflammatory activity at the cell surface. *(cites: a2_evi_14)*
- *cellular stress* — Under generic stress conditions, HMGB1 is released extracellularly as a DAMP and can stimulate neurotransmitter release in neuronal/synaptic contexts. *(cites: a2_evi_13)*

**Primary subcellular compartment**: Nucleus

**Dual localization**

- Secreted/Extracellular · upon cell activation, necrosis, ferroptosis, senescence, or chemotherapy stress *(cites: a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_08, a2_evi_09)*
- Extracellular Vesicle Surface (Exosomes) · in arthritis/joint injury disease state *(cites: a2_evi_10, a2_evi_11)*
- Cytosol · intracellular pool in unstimulated tumor cells *(cites: a2_evi_09)*
- Cell Surface (Extracellular-Facing) · redox-regulated surface display; cysteine oxidation state altered under T-cell activation *(cites: a2_evi_14)*

**Anatomical accessibility**

- extracellular/interstitial space — systemic DAMP release from immune cells, necrotic cells, and senescent cells — Blood Interstitial Facing · *Favorable*: HMGB1 is actively secreted or passively released into the extracellular milieu by macrophages, necrotic, and senescent cells during inflammation/sepsis. Once in interstitial fluid or circulation, it is directly accessible to systemically delivered binders.
- extracellular vesicle (exosome) surface — arthritic joint-derived circulating exosomes — Blood Interstitial Facing · *Favorable*: HMGB1 is displayed on the outer leaflet of circulating exosomes from injured joints, confirmed by proteinase-K protection assay. Exosomes travel in blood/interstitial fluid, making surface HMGB1 accessible to systemic antibodies or binders.
- neuronal/synaptic environment — stress-induced DAMP signaling in brain — Synaptic · *Context Dependent*: HMGB1 is released under stress to stimulate neurotransmitter release and acts as a DAMP on neurons. Systemic access to the synaptic/CNS compartment is limited by the blood-brain barrier, making accessibility context-dependent for peripheral biologics.

**Accessibility modulation**

- *Stress Induced* · trigger: Other: non-ferroptotic glioma cells (intracellular HMGB1) → ferroptotic glioma cells — Ferroptosis drives secretion of acetylated HMGB1 into the extracellular conditioned medium, shifting HMGB1 from intracellular to extracellular/accessible compartment. *(→ Extracellular Acetyl-HMGB1 Becomes Available For Binding By Extracellular Antibodies Or Therapeutic Agents; Surface/Secreted Pool Increases Specifically In Ferroptotic Tumor Cells.)* *(cites: a2_evi_07, a2_evi_08)*
- *Stress Induced* · trigger: Other: untreated PyMT-B6 mammary tumor cells (predominantly intracellular HMGB1) → taxane chemotherapy-treated PyMT-B6 mammary tumor cells — Taxane chemotherapy stress induces active secretion of HMGB1 from intracellular compartments to the extracellular space in a TLR4-dependent manner. *(→ HMGB1 Transitions From An Intracellular Pool (Inaccessible To Extracellular Binders) To A Secreted Extracellular Form Accessible To Antibodies And Receptors In The Tumor Microenvironment.)* *(cites: a2_evi_09)*
- *Cell State Induced* · trigger: Other: non-senescent cells with nuclear/intracellular HMGB1 → senescent cells — Senescence induces HMGB1 release from intracellular/nuclear compartment into the extracellular milieu as part of the SASP, making HMGB1 extracellularly accessible. *(→ HMGB1 Shifts From A Nuclear/Intracellular Location To Extracellular Space In Senescent Cells, Creating An Accessible Extracellular Pool Targetable By Antibodies Or Decoy Receptors.)* *(cites: a2_evi_06)*
- *Disease State Induced*: exosomes from healthy/uninjured knee joints (no surface HMGB1) → exosomes derived from MIA-injured (arthritic) knee joints — Arthritic joint injury induces surface display of HMGB1 on the exterior of exosomes; proteinase-K protection assay confirms outward-facing surface localization on extracellular vesicles. *(→ HMGB1 Is Fully Accessible On The Outer Leaflet Of Disease-State Exosomes; Neutralizing Antibody 2G7 Abrogates Downstream Neuronal Effects, Confirming Functional Surface Accessibility For Binders.)* *(cites: a2_evi_10, a2_evi_11)*
- *Activation Induced* · trigger: Immune Activation: resting immune cells (macrophages, neutrophils) with intracellular HMGB1 → infection- or inflammation-activated immune cells and necrotic/damaged cells — Bacterial products and infection stimuli induce HMGB1 release from immune cells (macrophages) and necrotic/damaged cells, increasing extracellular HMGB1 availability. *(→ Released HMGB1 Becomes Extracellularly Accessible, Enabling Binding To TLR4 And RAGE On Neutrophils And Macrophages; Creates A Targetable Extracellular HMGB1 Pool In Infectious/Inflammatory Contexts.)* *(cites: a2_evi_04, a2_evi_05)*
- *Post Translational Dependent*: resting T cells with reduced cysteines C23, C45, C106 on surface HMGB1 → activated T cells with oxidized surface HMGB1 cysteines — T cell activation alters the redox/oxidation state of surface-accessible cysteines C23, C45, and C106 of HMGB1, switching functional conformation of surface-displayed HMGB1. *(→ Cysteine Oxidation State Modulates The Functional Accessibility And Activity Of Surface HMGB1; Reduced Vs. Oxidized Forms Have Differential Anti-Inflammatory Activity, Affecting How Extracellular Binders Engage The Protein.)* *(cites: a2_evi_14)*

**Restricted-subdomain distribution**

- present: false
- severity: Unknown
- evidence: Weak
- domain: Unknown
- rationale: No plasma-membrane surface localization of HMGB1 is established, so subdomain restriction is not applicable. The ledger contains no surface-distribution data (apical/basolateral/junctional IF or membrane-wide staining) because HMGB1 does not qualify as a surface protein by the direct-assay gate. No relevant subdomain data in the ledger.

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: HMGB1 has no transmembrane domain and reaches the extracellular space via unconventional secretion (acetylation-driven) or passive release (necrosis, pyroptosis). No obligate co-receptor is required for its extracellular release; the process is cell-autonomous and stress-driven.
- cites: a2_evi_04, a2_evi_09

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl Compara r112. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P09429 | ref | ref | 0 | 0 aa | 215 aa | 0 aa | Cytoplasmic→Cytoplasmic | — |
| Paralog | HMGB2 | [P26583](https://www.uniprot.org/uniprotkb/P26583) | 77.2% | — | — | — | — | — | — | caution |
| Paralog | HMGB3 | [O15347](https://www.uniprot.org/uniprotkb/O15347) | 68.4% | — | — | — | — | — | — | caution |
| Paralog | HMGB4 | [Q8WW32](https://www.uniprot.org/uniprotkb/Q8WW32) | 35.3% | — | — | — | — | — | — | low-risk |
| Paralog | UBTF | [P17480](https://www.uniprot.org/uniprotkb/P17480) | 33.5% | — | — | — | — | — | — | low-risk |
| Paralog | SSRP1 | [Q08945](https://www.uniprot.org/uniprotkb/Q08945) | 27.0% | — | — | — | — | — | — | low-risk |
| Paralog | TOX2 | [Q96NM4](https://www.uniprot.org/uniprotkb/Q96NM4) | 26.5% | — | — | — | — | — | — | low-risk |
| Paralog | TOX3 | [O15405](https://www.uniprot.org/uniprotkb/O15405) | 25.1% | — | — | — | — | — | — | low-risk |
| Paralog | TOX4 | [O94842](https://www.uniprot.org/uniprotkb/O94842) | 24.7% | — | — | — | — | — | — | low-risk |
| Paralog | TOX | [O94900](https://www.uniprot.org/uniprotkb/O94900) | 24.7% | — | — | — | — | — | — | low-risk |
| Paralog | HMGXB4 | [Q9UGU5](https://www.uniprot.org/uniprotkb/Q9UGU5) | 21.4% | — | — | — | — | — | — | low-risk |
| Paralog | SP100 | [P23497](https://www.uniprot.org/uniprotkb/P23497) | 20.0% | — | — | — | — | — | — | low-risk |
| Paralog | TFAM | [Q00059](https://www.uniprot.org/uniprotkb/Q00059) | 19.5% | — | — | — | — | — | — | low-risk |
| Paralog | SMARCE1 | [Q969G3](https://www.uniprot.org/uniprotkb/Q969G3) | 19.1% | — | — | — | — | — | — | low-risk |
| Paralog | HMG20B | [Q9P0W2](https://www.uniprot.org/uniprotkb/Q9P0W2) | 18.6% | — | — | — | — | — | — | low-risk |
| Paralog | SP140 | [Q13342](https://www.uniprot.org/uniprotkb/Q13342) | 17.2% | — | — | — | — | — | — | low-risk |
| Paralog | SP140L | [Q9H930](https://www.uniprot.org/uniprotkb/Q9H930) | 17.2% | — | — | — | — | — | — | low-risk |
| Paralog | UBTFL1 | [P0CB47](https://www.uniprot.org/uniprotkb/P0CB47) | 17.2% | — | — | — | — | — | — | low-risk |
| Paralog | SP110 | [Q9HB58](https://www.uniprot.org/uniprotkb/Q9HB58) | 16.7% | — | — | — | — | — | — | low-risk |
| Paralog | HMG20A | [Q9NP66](https://www.uniprot.org/uniprotkb/Q9NP66) | 16.7% | — | — | — | — | — | — | low-risk |

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
- cites: a1_evi_15, a1_evi_16, a1_evi_17, a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_08, a2_evi_09

**ECD size assessment**

- ECD class: None
- rationale: HMGB1 lacks a transmembrane domain and has no bona fide ectodomain in the classical sense. It is a nuclear/cytoplasmic protein released unconventionally; ECD length is 0 by topology. The relevant targeting unit is the soluble secreted protein, not a membrane-anchored ectodomain.

**Epitope masking**

- severity: Moderate
- evidence: Weak
- mechanism: Conformational
- rationale: Redox state of cysteines C23, C45, and C106 modulates HMGB1 conformation and anti-inflammatory activity; oxidation vs. reduction switches functional epitopes. This is a review-level assertion without a direct antibody-masking study, but the conformational switch is biologically documented and relevant to binder design.
- cites: a1_evi_07, a2_evi_14

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P09429-F1](https://alphafold.ebi.ac.uk/entry/P09429) |
| AFDB version | v6 |
| ECD mean pLDDT | 76.8 |
| ECD disordered fraction | 28.8% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P09429) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P09429](https://alphafold.ebi.ac.uk/entry/P09429) | AlphaFold DB (AF-P09429-F1, v6) |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

34 entries · 19 primary · 15 secondary · 0 tertiary · 26 PMC OA.

- `a1_evi_01` · *Secondary* · Supports · Methodological — Cell Surface Capture (CSC) protocol was used on intact cells, with lysates normalized to 2 mg/mL and separated by SDS-PAGE for streptavidin blot readout, providing a surface biotinylation + Western blot paired surface-accessibility assay. This is the methodology anchor for any HMGB1 surface detection in this study. ([PMC10751780](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10751780/))
  - *assay*: Unspecified · live · non-permeabilized
  > "For streptavidin blot, lysates after Cell Surface Capture (CSC) were normalized to 2 mg/mL and separated on a 4–20% SDS-PAGE gel."
- `a1_evi_02` · *Secondary* · Supports · Methodological — Surface biotinylation methodology using biotin-phenol (BP) substrate with H2O2 oxidant (APEX2-proximity labeling variant); material from four conditions used for Western blot, with two conditions (BP+/H2O2+ and BP−/H2O2+) proceeded to streptavidin pulldown and MS for surfaceome identification. This is the paired methodology clip for the surface-biotinylation + MS result. ([PMC11099048](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11099048/))
  - *assay*: Unspecified · live · non-permeabilized
  > "Material from all four conditions were used in Western Blots, but only two were then used for subsequent pull-down of biotinylated proteins and proteomic analysis: BP+/H 2 O 2 + and BP−/H 2 O 2 +."
- `a1_evi_03` · *Primary* · Supports · Methodological — Western blot validation of surface biotinylation assay: biotinylated proteins detected only when substrate BP + H2O2 were both present, confirming assay specificity. Validates the surface biotinylation signal as genuine rather than non-specific. This is the paired WB result confirming the APEX2-proximity surface-labeling assay. ([PMC11099048](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11099048/))
  - *assay*: Unspecified · live · non-permeabilized
  > "After labelling assays, Western blotting confirmed that a set of proteins were biotinylated in this line only when the substrate BP was added, followed by H 2 O 2 to allow oxidation (Fig. 2 A)."
- `a1_evi_04` · *Secondary* · Ambiguous · Methodological — High non-specific background observed in streptavidin-bead enrichment + MS step of the APEX2 surface-biotinylation assay (KAHRP-FLAG-APEX2 transfectant), despite clean Western blot results. This is a methodological caveat — streptavidin-MS enrichment in this system has poor signal-to-noise, reducing confidence in any positive MS identification including HMGB1. ([PMC11099048](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11099048/))
  - *assay*: Unspecified · live · non-permeabilized
  > "Despite these clear results from Western blotting and IFA, enrichment of biotinylated proteins by streptavidin beads followed by identification using mass spectrometry revealed high levels of non-specific background in both conditions of the KAHRP-FLAG-APEX2 transfectant."
- `a1_evi_05` · *Secondary* · Supports · Methodological — Surfaceome mass spectrometry method using aminooxy-biotin sialoglycoprotein enrichment (cell-surface capture) combined with LC-MS/MS on chondrogenic micromass cultures at multiple differentiation time points (days 1, 3, 6, 10, 15). This is a surface-specific MS method on intact cells targeting sialylated cell-surface glycoproteins; n=3 biological replicates per time point. Load-bearing methodology for any HMGB1 surface MS detection in chondrocyte context. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
  - *assay*: Unspecified · chondrogenic micromass culture · live · non-permeabilized
  > "Temporal proteomic profiling was conducted at days 1, 3, 6, 10, and 15 of micromass culture corresponding to key histodifferentiation stages [ 17 , 18 ], combining sialoglycoprotein enrichment via aminooxy-biotin conjugation with high-resolution LC-MS/MS on 3 biological replicates ( n = 3)."
- `a1_evi_06` · *Secondary* · Supports · Methodological — Reagent list identifies anti-HMGB1 antibody clone 66525-1-Ig (mouse monoclonal, Proteintech) used in this study. This is the antibody identifier for the methodological validation chain; clone/vendor details enable downstream antibody specificity assessment and cross-reactivity evaluation against HMGB2/HMGB3 paralogs. ([PMC10413933](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10413933/))
  - *assay*: Human
  > "The following antibodies were used: rabbit anti-Myc (2278S, Cell Signaling Technology, USA), rabbit anti-his (2365S, Cell Signaling Technology, USA), mouse anti-His (MA1-21315, Invitrogen, Thermo Fisher Scientific, USA), rabbit anti-CUL3 (A301-109A, Bethyl Laboratories, USA), mouse anti-GAPDH (sc-32233, Santa Cruz Biotechnology, USA), rabbit anti-SETD2 (55377-1-AP, Proteintech, USA), rabbit anti-ubiquitin (43124S, Cell Signaling Technology, USA), rabbit anti-CAMSAP1 (A302-260A, Bethyl Laboratories, USA), rabbit anti-TRAPPC9 (16014-1-AP, Proteintech, USA), rabbit anti-HMGB-1 (66525-1-Ig, Protei"
- `a1_evi_07` · *Secondary* · Ambiguous · Topology — HMGB1 surface cysteines C23, C45, and C106 are redox-active and reported to reside at or near the cell surface; reduction of these cysteines is crucial for anti-inflammatory processes. This is an epitope-masking / redox-state topology consideration: oxidation state of these cysteines modulates HMGB1 conformation and surface accessibility, relevant to antibody epitope access and therapeutic targeting of the extracellular form. ([PMC10751780](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10751780/))
  - *assay*: Human
  > "48 − 52 Multiple cell surface cysteines are reported to be redox active, including C53 of aquaporin-8 AQP8, persulfidation of which is known to gate H 2 O 2 to regulate cell stress, 53 and C23, C45, and C106 of high mobility group box 1 protein HMGB1, reduction of which are known to be crucial for anti-inflammatory processes. 54 , 55 Activation-induced changes to cysteine oxidation have been linked to enhanced T cell activitation, 56 − 58 and cysteines on CD4 and GP120 have been implicated in the entry of HIV in T cells and in the regulation"
- `a1_evi_08` · *Primary* · Supports · Surface Expression — HMGB1 is displayed on the exterior surface of exosomes released from MIA-injured knee tissue; exosome-surface-displayed HMGB1 acts as a signaling DAMP transmitted to the brain to activate NF-κB and neuronal senescence. This is a shed/surface-form evidence: HMGB1 is present on the outer leaflet of extracellular vesicles, representing a non-plasma-membrane surface-accessible form that retains receptor-engagement capacity. (https://pubmed.ncbi.nlm.nih.gov/42107473/)
  - *assay*: Mouse · exosomes from MIA-injured knee · live · non-permeabilized
  > "Here we show that exosomes released from mono-iodoacetate (MIA)-injured knees transmit surface-displayed high mobility group box 1 (HMGB1) to the brain, where they activate neuronal NF-κB and senescence programs that culminate in depressive-like behavior."
- `a1_evi_09` · *Primary* · Supports · Surface Expression — Proteinase-K protection assay directly localizes HMGB1 to the exterior of exosomes (proteinase-K-accessible, non-interior), confirming extracellular surface display. Neutralizing antibody 2G7 against HMGB1 abrogates exosome-induced neuronal effects, confirming the surface-accessible HMGB1 is pharmacologically engageable. This is the key surface-localization method clip for exosomal HMGB1; method_family = proteinase-K protection assay on intact vesicles. Antibody 2G7 (anti-HMGB1 neutralizing) engages the surface-displayed form. (https://pubmed.ncbi.nlm.nih.gov/42107473/)
  - *assay*: Mouse · exosomes · live · non-permeabilized
  > "A proteinase-K protection assay localized HMGB1 to the exosomes exterior, and neutralizing HMGB1 with 2G7 abrogated exosome-induced neuronal pp65/senescence and restored behavioral performance without altering joint histopathology."
- `a1_evi_10` · *Primary* · Supports · Surface Expression — A neutralizing anti-HMGB1 antibody prevents complement activation, implying that HMGB1 in an extracellular/surface-accessible form mediates complement-triggering activity. This constitutes therapeutic-engagement evidence: an anti-HMGB1 neutralizing antibody engages the extracellular form of HMGB1 and blocks its effector function, supporting the accessibility of HMGB1 to antibody-based therapeutics in the extracellular compartment. ([PMC8698915](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8698915/))
  - *assay*: Unspecified
  > "This can be prevented by a neutralizing anti-HMGB1 antibody."
- `a1_evi_11` · *Secondary* · Supports · Methodological — Flow cytometry on non-permeabilized cells measuring surface expression of pattern-recognition receptors (Dectin-1, Dectin-2, TLR2) following HMGB1 stimulation. This is a surface-method clip: the assay is intact-cell, non-permeabilized flow cytometry. HMGB1 serves as the stimulus here, not the measured target — important context that this clip evidences HMGB1 as a surface-engaging ligand rather than a membrane-resident protein in this context. ([PMC12531030](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12531030/))
  - *assay*: Unspecified · mast cells (MCs) · live · non-permeabilized
  > "(B) Representative flow cytometry histograms showing Dectin-1, Dectin-2, and TLR2 expression after HMGB1 stimulation in non-permeabilized cells."
- `a1_evi_12` · *Primary* · Ambiguous · Contradictory — Flow cytometry and confocal microscopy on non-permeabilized mast cells confirm surface expression of Dectin-2 and TLR2 (known HMGB1 receptors) with no significant change after HMGB1 stimulation. This clip is relevant as a contradictory/contextual note: surface levels of HMGB1-binding receptors are not altered by HMGB1 treatment, suggesting receptor-mediated surface engagement of HMGB1 may not involve receptor upregulation. Flow cytometry was performed without permeabilization (surface-only staining). ([PMC12531030](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12531030/))
  - *assay*: Unspecified · mast cells (MCs) · live · non-permeabilized
  > "Additionally, flow cytometry and confocal microscopy validated the presence of Dectin-2 and TLR2 on the surface of non-stimulated (NS) MCs, revealing no significant alterations in expression levels following stimulation with HMGB1."
- `a1_evi_13` · *Secondary* · Supports · Methodological — Flow cytometry on live cells measuring Alexa488-positive population; this surface staining assay on intact live cells is the methodology framework for surface detection in this study. The assay is live-cell, non-permeabilized flow cytometry measuring surface-accessible Alexa488 label. ([PMC12847238](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12847238/))
  - *assay*: Unspecified · live · non-permeabilized
  > "Graphs show relative percentage of Alexa488-positive live cells as determined by flow cytometry."
- `a1_evi_14` · *Primary* · Refutes · Contradictory — Flow cytometric detection of intracellular HMGB1 within live PyMT-B6 cells 24 hours post-chemotherapy (taxane) treatment. Critically, the assay measures intracellular HMGB1 — not surface-localized — in live cells, indicating that intracellular HMGB1 pools are the predominant signal detected in this flow cytometry study. This is a contradictory clip: flow cytometry here detects intracellular HMGB1, not surface HMGB1, in the context of taxane-induced secretion. ([PMC13198304](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13198304/))
  - *assay*: Mouse · PyMT-B6 · fixed · permeabilized
  > "Active secretion of HMGB1 during taxane treatment is dependent upon TLR4 (A) Flow cytometric detection of intracellular HMGB1 within live PyMT-B6 cells 24 h post-chemotherapy treatment."
- `a1_evi_15` · *Primary* · Refutes · Surface Expression — HMGB1 is detected in the supernatant of VSV-S-infected HN12 and CAL27 head-and-neck cancer cells alongside LDH and IL-1β release, indicating active release/shedding from pyroptotic cells. This is shed-form evidence: HMGB1 is passively released from cells undergoing pyroptosis (membrane pore formation), representing the secreted/soluble form rather than stable surface attachment. ([PMC11721257](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11721257/))
  - *assay*: Human · HN12 and CAL27
  > "VSV-S induces HN12 and CAL27 cell pyroptosis more efficiently than wtVSV, as demonstrated by a greater number of cell membrane pores along with increased lactate dehydrogenase (LDH) release and elevated levels of IL-1β and HMGB1 in the supernatant of infected cells (Fig. 3 A and D)."
- `a1_evi_16` · *Primary* · Refutes · Surface Expression — HMGB1 levels in cell supernatant quantified by ELISA (n=6 replicates) in HN12 and CAL27 cells infected with wtVSV or VSV-S. ELISA of conditioned medium is the assay; this is the paired methodology clip confirming shed/secreted HMGB1 detection method. Soluble HMGB1 is quantitatively detected in supernatant, representing the shed/secreted pool that competes with any residual surface-associated form. ([PMC11721257](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11721257/))
  - *assay*: Human · HN12 and CAL27
  > "( D ) Levels of IL-1β and HMGB1 in the supernatant of HN12 and CAL27 cells infected with wtVSV or VSV-S determined by ELISA ( n = 6 repeats)."
- `a1_evi_17` · *Secondary* · Refutes · Surface Expression — HMGB1 release into the extracellular milieu is cited as a marker of cellular senescence (SASP context), alongside IL-6, IL-8, and MMP9. This is a review-level shed-form citation: HMGB1 is secreted as a DAMP signaling molecule during senescence, representing the dominant extracellular form in this cell state. The primary form detected extracellularly is soluble/secreted, not stably membrane-associated. ([PMC12419843](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12419843/))
  - *assay*: Unspecified
  > "Since then, several other markers have been used to identify SEN, including increased expression of the cell cycle checkpoint inhibitors p16 and p21, SASP factors such as IL‐6, IL‐8, and MMP9, and release of the DAMP signaling molecule HMGB1 into the extracellular milieu (Hernandez‐Segura et al. 2018 )."
- `a1_evi_18` · *Primary* · Supports · Surface Expression — HMGB1 protein detected by pulldown on sTREM-1 (soluble TREM-1)-conjugated Sepharose resin, resolved by SDS-PAGE + Western blot with anti-HMGB1 antibody. This shows HMGB1 binds to soluble TREM-1, suggesting HMGB1 acts as an extracellular ligand for TREM-1. The binding is in solution (sTREM-1 bead pulldown), not a cell-surface assay per se, but confirms HMGB1 is accessible extracellularly and engages TREM-1 ectodomain. ([PMC10779375](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10779375/))
  - *assay*: Unspecified
  > "( a ) The HMGB1 protein was applied to sTREM-1 conjugated with Sepharose, eluted with acetonitrile, and resolved using SDS PAGE and Western blot with antibodies to HMGB1."
- `a1_evi_19` · *Secondary* · Ambiguous · Methodological — Cell surface biotinylation used to determine NHE3 expression at the apical membrane. HMGB1 is not the target measured here (NHE3 is); however, this clip is in the HMGB1-associated pool and the methodology description provides the surface biotinylation protocol anchor. Apical membrane biotinylation method context: relevant if HMGB1 is co-detected in the same dataset. Confidence is weak given HMGB1 is not the direct readout. ([PMC9953368](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9953368/))
  - *assay*: Unspecified · live · non-permeabilized
  > "NHE3 expression at the apical membrane was determined by cell surface biotinylation."
- `a2_evi_01` · *Primary* · Supports · Tissue Expression — HMGB1 protein is highly expressed in primary gastric adenocarcinoma tissue, with an IHC positivity rate of 81.76% in tumor samples, indicating strong upregulation relative to normal gastric mucosa. (https://pubmed.ncbi.nlm.nih.gov/41917528/)
  - *assay*: Human · primary gastric adenocarcinoma tissue · fixed · permeabilized
  > "IHC analysis further confirmed high positivity rates for HMGB1 (81.76%) and NF-κB (75%) in gastric adenocarcinoma, respectively."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — HMGB1 protein expression is significantly higher in gastric cancer tissue compared to adjacent normal mucosa, and elevated HMGB1 expression is significantly correlated with survival prognosis, establishing HMGB1 as a disease-state-upregulated marker in gastric adenocarcinoma. (https://pubmed.ncbi.nlm.nih.gov/41917528/)
  - *assay*: Human · primary gastric adenocarcinoma and adjacent non-tumor tissue · fixed · permeabilized
  > "All statistical analyses were conducted using GraphPad Prism 9.<h4>Result</h4>The results showed that HMGB1 and NF-κB were significantly higher than normal tissues, which were significantly correlated with survival prognosis."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — HMGB1 expression level in gastric adenocarcinoma correlates with tumor size, depth of invasion, and clinical stage, indicating that HMGB1 surface/extracellular availability is modulated by tumor progression state. (https://pubmed.ncbi.nlm.nih.gov/41917528/)
  - *assay*: Human · primary gastric adenocarcinoma tissue · fixed · permeabilized
  > "The expression level of HMGB1 or NF-κB was correlated with tumor size, depth of invasion, and clinical stage."
- `a2_evi_04` · *Secondary* · Supports · Tissue Expression — HMGB1 is released from immune cells (including macrophages) and damaged/necrotic cells upon infection, representing a cell-state-induced (activation/necrosis) extracellular HMGB1 availability primarily from innate immune and tissue-damage contexts. ([PMC9971734](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9971734/))
  - *assay*: Unspecified · immune cells and damaged cells
  > "(A) Infection sources, such as bacterial products, induce HMGB1 to be released from immune cells or damaged cells."
- `a2_evi_05` · *Secondary* · Supports · Tissue Expression — Extracellular HMGB1 engages surface receptors TLR4 and RAGE on neutrophils and macrophages in sepsis, triggering NET formation and cytokine/chemokine release; this defines the cell-type contexts (neutrophils, macrophages) where HMGB1 surface accessibility is physiologically relevant as a DAMP. ([PMC9971734](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9971734/))
  - *assay*: Unspecified · neutrophils, macrophages
  > "HMGB1 binds to toll-like receptor 4 (TLR4) and receptor for advanced glycation end products (RAGE) on neutrophils and macrophages, inducing neutrophil extracellular trap (NET) formation and cytokines/chemokines release."
- `a2_evi_06` · *Secondary* · Supports · Tissue Expression — HMGB1 is released into the extracellular milieu as a DAMP signaling molecule by senescent cells, making it a senescence-associated secretory phenotype (SASP) marker; baseline nuclear localization shifts to extracellular secretion in the senescent cell state. ([PMC12419843](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12419843/))
  - *assay*: Unspecified · senescent cells
  > "Since then, several other markers have been used to identify SEN, including increased expression of the cell cycle checkpoint inhibitors p16 and p21, SASP factors such as IL‐6, IL‐8, and MMP9, and release of the DAMP signaling molecule HMGB1 into the extracellular milieu (Hernandez‐Segura et al. 2018 )."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — HMGB1 mRNA transcriptional levels are upregulated in ferroptotic glioma cells, as measured by RT-PCR alongside other immune checkpoint genes (CD80, CD155, galectin-9), establishing a cell-state-induced (ferroptosis) transcriptional upregulation of HMGB1 in glioma. ([PMC13039700](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13039700/))
  - *assay*: Human · ferroptotic glioma cells
  > "The transcriptional levels of four immune checkpoints (CD80, CD155, HMGB1, and galectin-9) in ferroptotic glioma cells were detected via RT-PCR."
- `a2_evi_08` · *Primary* · Supports · Surface Expression — Extracellular acetylated HMGB1 (Acetyl-HMGB1) is detectable in the conditioned medium of ferroptotic glioma cells by ELISA, indicating that the ferroptotic cell state drives HMGB1 secretion/release to the extracellular compartment; this represents a stress-state-induced accessibility modulation (ferroptosis → extracellular HMGB1 increase). ([PMC13039700](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13039700/))
  - *assay*: Human · ferroptotic glioma cells · live · non-permeabilized
  > "The extracellular Acetyl-HMGB1 content of ferroptotic glioma cells was detected via an ELISA kit."
- `a2_evi_09` · *Primary* · Supports · Surface Expression — Intracellular HMGB1 is detectable by flow cytometry within live PyMT-B6 tumor cells 24 hours post-chemotherapy (taxane treatment), and active secretion of HMGB1 during taxane treatment is dependent on TLR4; this defines a cell-state-induced (chemotherapy stress) shift in HMGB1 from intracellular compartments toward secretion. The permeabilized detection confirms predominantly intracellular localization at baseline in unstimulated tumor cells. ([PMC13198304](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13198304/))
  - *assay*: Mouse · PyMT-B6 mammary tumor cells · fixed · permeabilized
  > "Figure 2 Active secretion of HMGB1 during taxane treatment is dependent upon TLR4 (A) Flow cytometric detection of intracellular HMGB1 within live PyMT-B6 cells 24 h post-chemotherapy treatment."
- `a2_evi_10` · *Primary* · Supports · Surface Expression — Surface-displayed HMGB1 is present on the exterior of exosomes released from mono-iodoacetate (MIA)-injured knee joints; these HMGB1-bearing exosomes reach the brain and activate neuronal NF-κB and senescence programs. This demonstrates that joint injury (arthritis disease state) induces HMGB1 surface display on extracellular vesicles derived from the articular joint tissue, enabling long-range intercellular HMGB1 signaling to the brain. (https://pubmed.ncbi.nlm.nih.gov/42107473/)
  - *assay*: Unspecified · MIA-injured knee joint-derived exosomes · live · non-permeabilized
  > "Here we show that exosomes released from mono-iodoacetate (MIA)-injured knees transmit surface-displayed high mobility group box 1 (HMGB1) to the brain, where they activate neuronal NF-κB and senescence programs that culminate in depressive-like behavior."
- `a2_evi_11` · *Primary* · Supports · Surface Expression — A proteinase-K protection assay localizes HMGB1 to the exterior surface of exosomes (i.e., surface-accessible, facing outward), confirming that HMGB1 is displayed on the outer leaflet of extracellular vesicles derived from arthritic joints. Neutralizing this surface HMGB1 with antibody 2G7 abrogates exosome-induced neuronal senescence, validating functional surface accessibility. (https://pubmed.ncbi.nlm.nih.gov/42107473/)
  - *assay*: Unspecified · joint-derived exosomes · live · non-permeabilized
  > "A proteinase-K protection assay localized HMGB1 to the exosomes exterior, and neutralizing HMGB1 with 2G7 abrogated exosome-induced neuronal pp65/senescence and restored behavioral performance without altering joint histopathology."
- `a2_evi_12` · *Primary* · Supports · Tissue Expression — Primary neurons respond to joint-derived HMGB1-bearing exosomes with NF-κB activation and senescence signatures in vitro, demonstrating that neurons are a cell type with functional HMGB1-responsive surface receptors; this positions the brain/neuronal compartment as an anatomical target tissue for extracellular HMGB1 signaling. (https://pubmed.ncbi.nlm.nih.gov/42107473/)
  - *assay*: Unspecified · primary neurons · live · non-permeabilized
  > "In vitro, joint-derived exosomes triggered HMGB1-dependent NF-κB activation and senescence signatures in primary neurons, supporting neuron-intrinsic responsiveness to vesicular DAMP signaling."
- `a2_evi_13` · *Secondary* · Supports · Tissue Expression — Under stress conditions, HMGB1 is described as a DAMP that can stimulate neurotransmitter release, placing HMGB1 in the context of neuro-inflammatory signaling; this indicates stress-state-induced extracellular HMGB1 accessibility in neuronal/synaptic tissue contexts. ([PMC9953368](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9953368/))
  - *assay*: Unspecified · neurons
  > "Under stress, DAMPs, such as high mobility group box 1 (HMGB1), have been shown to stimulate the neurotransmitter release [ 24 ]."
- `a2_evi_14` · *Secondary* · Supports · Surface Expression — HMGB1 cysteines C23, C45, and C106 are redox-active on the cell surface; their reduction state is critical for anti-inflammatory function. This places HMGB1 in a surface-accessible, redox-regulated context, where cysteine oxidation state modulates the protein's functional activity. The redox state of these cysteines is altered under T-cell activation conditions, representing a cell-state-induced accessibility/activity modulation. ([PMC10751780](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10751780/))
  - *assay*: Human · T cells (activated vs. resting) · non-permeabilized
  > "48 − 52 Multiple cell surface cysteines are reported to be redox active, including C53 of aquaporin-8 AQP8, persulfidation of which is known to gate H 2 O 2 to regulate cell stress, 53 and C23, C45, and C106 of high mobility group box 1 protein HMGB1, reduction of which are known to be crucial for anti-inflammatory processes. 54 , 55 Activation-induced changes to cysteine oxidation have been linked to enhanced T cell activitation, 56 − 58 and cysteines on CD4 and GP120 have been implicated in the entry of HIV in T cells and in the regulation"
- `a2_evi_15` · *Primary* · Ambiguous · Tissue Expression — HMGB1 stimulation of mast cells does not significantly alter the surface expression levels of pattern-recognition receptors Dectin-2 and TLR2, as validated by flow cytometry and confocal microscopy. This indicates that extracellular HMGB1 does not modulate the surface PRR repertoire of non-stimulated mast cells, providing cell-type-specific (mast cell) context for HMGB1 signaling effects. ([PMC12531030](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12531030/))
  - *assay*: Unspecified · mast cells (non-stimulated and HMGB1-stimulated) · live · non-permeabilized
  > "Additionally, flow cytometry and confocal microscopy validated the presence of Dectin-2 and TLR2 on the surface of non-stimulated (NS) MCs, revealing no significant alterations in expression levels following stimulation with HMGB1."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/HMGB1.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/HMGB1](https://surfaceome.deliverome.org/HMGB1)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/HMGB1.json](https://surfaceome.deliverome.org/data/surfaceome/HMGB1.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/HMGB1.md](https://surfaceome.deliverome.org/data/surfaceome/HMGB1.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P09429](https://alphafold.ebi.ac.uk/entry/P09429)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P09429](https://alphafold.ebi.ac.uk/api/prediction/P09429) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P09429](https://www.uniprot.org/uniprotkb/P09429)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-P09429-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-P09429-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-P09429-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-P09429-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-P09429-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-P09429-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*215 aa · `P09429` · embedded at build time*

```
   1  MGKGDPKKPRGKMSSYAFFVQTCREEHKKKHPDASVNFSEFSKKCSERWKTMSAKEKGKF
  61  EDMAKADKARYEREMKTYIPPKGETKKKFKDPNAPKRPPSAFFLFCSEYRPKIKGEHPGL
 121  SIGDVAKKLGEMWNNTAADDKQPYEKKAAKLKEKYEKDIAAYRAKGKPDAAKKGVVKAEK
 181  SKKKKEEEEDEEDEEDEEEEEDEEDEDEEEDDDDE
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`P09429`, deeptmhmm-1.0.24)

```
   1  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
  61  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 121  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 181  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — Compara r112 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — Confidence is moderate rather than low because the biology of HMGB1 as a secreted DAMP is well established across independent sources, making the 'secreted_only' call robust. However, the triage agent called this 'contextual / cell_state_induced,' noting that surface biotinylation on intact cells and flow cytometry data have been interpreted as showing HMGB1 on the outer PM leaflet bound to surface RAGE — evidence the triage cited but which is not present as a qualifying direct surface assay in the compiled ledger. The specific gap is that no live-cell non-permeabilized flow, non-perm IF, or surface biotinylation with HMGB1 confirmed as a hit appears in the evidence set reviewed here. Confidence would rise to high only with a published, replicated live-cell surface staining result (non-permeabilized flow cytometry or surface biotinylation with HMGB1 explicitly listed as a detected surface hit) from an independent laboratory.*

## CellxGene RNA enrichment (CZI Census)

*Schema v2.1.4 · CZI Census 2025-11-08 · HPA-style 4× fold-change classification on log1p(CP10K) → linear means, plus Yanai et al. 2005 τ (specificity score ∈ [0, 1], computed over the eligible-entity set). Cell-class rollup walks the Cell Ontology graph (cl-basic.obo, OBO Foundry) — leaf CL → nearest compartment ancestor. CC-BY 4.0 (CZI Census).*

**Classification:**

- **Cell class (CL ontology graph, ~10 compartments):** low specificity · τ=0.69
- **Cell type (leaf Cell Ontology terms, ~600):** enhanced · large pre-B-II cell · 11.3× · τ=0.91
- **Tissue (UBERON terms, ~56):** enhanced · vasculature · 20.7× · τ=0.95

**Top 5 cell types (leaf CL, pooled across tissues):**

| Cell type | CL ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| large pre-B-II cell | CL:0000957 | 4.051 | 99.94% | 8,449 / 8,454 |
| fraction A pre-pro B cell | CL:0002045 | 4.017 | 94.54% | 7,724 / 8,170 |
| proerythroblast | CL:0000547 | 3.783 | 96.87% | 1,576 / 1,627 |
| migratory enteric neural crest cell | CL:0002607 | 3.505 | 100.00% | 520 / 520 |
| basophilic erythroblast | CL:0000549 | 3.395 | 99.94% | 5,250 / 5,253 |

**Top 5 tissues (UBERON, pooled across cell types):**

| Tissue | UBERON ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| cortex | UBERON:0001851 | 2.843 | 97.43% | 145,911 / 149,766 |
| forelimb | UBERON:0002102 | 2.829 | 96.55% | 37,640 / 38,983 |
| hindlimb | UBERON:0002103 | 2.730 | 92.07% | 80,076 / 86,972 |
| embryo | UBERON:0000922 | 2.729 | 100.00% | 168,978 / 14,244 |
| pleura | UBERON:0000977 | 2.659 | 26.17% | 5,155 / 19,695 |

<!-- /cellxgene -->
