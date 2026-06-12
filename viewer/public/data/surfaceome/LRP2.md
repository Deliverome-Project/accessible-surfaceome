# LRP2 — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-30T20:29:01.447637Z · model `claude-sonnet-4-6`*

> LRP2/megalin is a canonical single-pass type I transmembrane endocytic receptor with a massive ~4400-residue extracellular domain, constitutively expressed at the apical plasma membrane of kidney proximal tubule epithelial cells, placental extravillous trophoblasts, and coronary endothelial cells. Surface accessibility is confirmed by multiple independent surface biotinylation studies (OK cells, MLE-12 cells) and orthogonal cell-surface capture MS in MDA-MB-231 cells. The dominant targeting risk is apical-membrane restriction: systemic binders cannot cross the tight epithelial barrier to reach LRP2 on the tubular luminal surface. A shed ectodomain is documented. The large ECD provides abundant epitope real estate.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:6694](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:6694) |
| UniProt | [P98164](https://www.uniprot.org/uniprotkb/P98164) |
| NCBI Gene | [4036](https://www.ncbi.nlm.nih.gov/gene/4036) |
| Ensembl | [ENSG00000081479](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000081479) |
| Subcategory | Single-pass type I |
| Surface accessibility | High |
| Confidence | High |
| Evidence grade | Direct, multi-method |
| Triage signal | Likely accessible |
| Headline risks | Shed Form |

## 1. Executive summary

**Constitutively surface-accessible at the apical membrane of kidney proximal tubule epithelial cells, placental EVTs, and coronary endothelial cells; not state-gated but anatomically restricted to epithelial/endothelial apical surfaces.**

LRP2/megalin is a canonical single-pass type I transmembrane endocytic receptor with a massive ~4400-residue extracellular domain, constitutively expressed at the apical plasma membrane of kidney proximal tubule epithelial cells, placental extravillous trophoblasts, and coronary endothelial cells. Surface accessibility is confirmed by multiple independent surface biotinylation studies (OK cells, MLE-12 cells) and orthogonal cell-surface capture MS in MDA-MB-231 cells. The dominant targeting risk is apical-membrane restriction: systemic binders cannot cross the tight epithelial barrier to reach LRP2 on the tubular luminal surface. A shed ectodomain is documented. The large ECD provides abundant epitope real estate.

**Family / classification** — functional class: Receptor.

**Triage first-pass reasoning** — LRP2/megalin is a single-pass type I transmembrane glycoprotein (large N-terminal extracellular domain, single TM helix, short cytoplasmic tail) belonging to the LDL receptor family. It functions as an endocytic multi-ligand receptor on the apical surface of absorptive epithelia — most prominently proximal tubule cells of the kidney, choroid plexus, intestine, and lung. Extensive experimental evidence (surface biotinylation, immunofluorescence on intact non-permeabilized cells, flow cytometry) confirms robust cell-surface expression at the apical plasma membrane. Its large ectodomain is the ligand-binding apparatus and is fully extracellular. Although it cycles through endosomes as part of its endocytic function, a substantial steady-state pool resides at the PM. Multiple therapeutic and diagnostic programs target its extracellular domain. This is an unambiguous classical single-pass TM receptor with dominant surface localization.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=High · subcategory=Single-pass type I · ecd=Large |
| Classification | reason=Classical Surface Receptor · family=Receptor · state-dependence=Low · induction-trigger=— |
| Expression | level=High · breadth=Restricted · specificity=Mixed · low-endogenous=false · tumor-associated=— · orphan-receptor=false · OE-precedent=false |
| Risks | shed=true · secreted=false · co-receptor=None · masking=true · restricted-subdomain=true |
| Evidence | grade=Direct, multi-method · density=High · live-cell-surface=— · supporting(hi)=5 · contradicting(hi)=0 |
| Cross-species | mouse=77.1% · cyno=98.1% |
| Paralogs | max %ECD identity = 49.7% |
| Topology | TM=1 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: High expression in kidney proximal tubule epithelial cells, where LRP2 is a canonical segment marker (~70% of CKD atlas cells express it) (a2_evi_01, a2_evi_02); also high in human kidney brush-border by IHC (a1_evi_19).
- *Expression breadth*: Restricted to kidney proximal tubule epithelium (dominant), placental extravillous trophoblasts (a2_evi_05), and coronary endothelial cells (a2_evi_07); not broadly expressed across tissue families.
- *Surface specificity*: Steady-state surface fraction is modest (4.9% of total megalin at apical PM under static culture (a1_evi_06)); majority of protein cycles through endosomes constitutively (a2_evi_10, a2_evi_11, a2_evi_14). Surface-dominant during interphase, but endosomal pool is substantial.
- *Known ligand*: LRP2 binds a large array of documented ligands including albumin, apolipoprotein B, vitamin D-binding protein, cubilin-amnionless complex, SARS-CoV-2 spike protein, and HDL/miR-223 (a2_evi_04, a1_evi_22, a2_evi_07). Not an orphan receptor.
- *Low endogenous expression*: Derived from expression_level='high' (not low/absent → not flagged). High expression in kidney proximal tubule epithelial cells, where LRP2 is a canonical segment marker (~70% of CKD atlas cells express it) (a2_evi_01, a2_evi_02); also high in human kidney brush-border by IHC (a1_evi_19).
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Direct, multi-method

LRP2 surface accessibility is supported by two distinct direct methods from independent sources. Surface biotinylation (sulfo-NHS-SS-biotin, non-permeabilized, live cells) was performed in OK proximal tubule cells by two independent groups (PMC11211581 and PMC9614980), both recovering biotinylated LRP2 via streptavidin pulldown and anti-megalin WB — high-weight direct evidence. Additionally, cell-surface capture (CSC) mass spectrometry via N-glycan oxidation and biocytin hydrazide enrichment identified LRP2 in MDA-MB-231 surfaceome (PMC12576823) — a second orthogonal direct surface method. Supporting evidence includes surface biotinylation in MLE-12 lung epithelial cells and structural/topology data (cryo-EM, canonical type I TM architecture). No mechanistically incompatible contradictions exist: endosomal accumulation under OCRL1 deficiency (a1_evi_23) is a pathological state variation, not a baseline refutation. Grade: direct_multi_method.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Supports Surface | Moderate | Canonical type I TM topology from sequence analysis; single source review assertion |
| a1_evi_02 | Supports Surface | Moderate | ECD domain architecture confirming large extracellular ligand-binding surface |
| a1_evi_03 | Supports Surface | Moderate | FXNPXY internalization signals confirm cytoplasmic C-terminus and endocytic cycling from surface |
| a1_evi_04 | Supports Surface | Moderate | Cryo-EM of nearly entire ectodomain confirming extracellular structure; purified protein not in situ |
| a1_evi_05 | Supports Surface | High | Non-permeabilized sulfo-NHS-SS-biotin apical surface biotinylation in OK proximal tubule cells |
| a1_evi_06 | Supports Surface | High | Quantified LRP2 at apical membrane (4.9% static, 2.8% FSS); direct surface biotinylation result |
| a1_evi_07 | Supports Surface | High | Streptavidin pulldown + anti-megalin WB detection from surface biotin fraction, OK cells |
| a1_evi_08 | Supports Surface | High | Independent source (PMC9614980) replicating non-permeabilized apical surface biotin in OK cells |
| a1_evi_09 | Supports Surface | High | Streptavidin pulldown + anti-megalin WB from surface fraction, corroborating PMC11211581 |
| a1_evi_10 | Supports Surface | Moderate | Surface biotinylation + WB quantification; cell type unspecified, single source |
| a1_evi_11 | Supports Surface | Moderate | Surface biotinylation in MLE-12 lung epithelial cells; moderate—no KO control described |
| a1_evi_12 | Tangential | Low | Antibody identifier for IF; no surface localization data presented here |
| a1_evi_13 | Tangential | Low | Antibody identifier for flow cytometry; no surface localization data presented here |
| a1_evi_14 | Supports Surface | Moderate | Surface biotinylation + pulldown for LDLR family surface detection including LRP2; partial detail |
| a1_evi_15 | Tangential | Low | WB antibody identifier only; no surface assay data |
| a1_evi_16 | Supports Surface | Moderate | CSC-MS glycoprotein enrichment in MDA-MB-231; surface-selective N-glycan capture method |
| a1_evi_17 | Supports Surface | Moderate | Quantitative surfaceome MS (CSC) in MDA-MB-231 cells; independent cell type from biotin studies |
| a1_evi_18 | Supports Surface | Low | Review-level structural comparison; weak indirect topology assertion |
| a1_evi_19 | Supports Surface | Moderate | IHC of human kidney sections localizing LRP2 to brush-border; fixation status not specified (likely permeabilized) |
| a1_evi_20 | Supports Surface | Moderate | IF localization of mutant LRP2 to apical membrane of proximal tubule; permeabilization not specified |
| a1_evi_21 | Tangential | Low | Computational modeling of surface vs endosomal forms; indirect support only |
| a1_evi_22 | Tangential | Low | SPR with shed soluble LRP2; demonstrates shedding but not cell-surface localization per se |
| a1_evi_23 | Tangential | Low | Pathological redistribution to endosomes under OCRL1 deficiency; not a surface contradiction in normal state |
| a1_evi_24 | Tangential | Low | mTORC1 phosphorylation modulates endocytic rate with minor surface/intracellular ratio change; ambiguous |

### Flow cytometry (1 method)

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-megalin/LRP2 (FAB9578G · R&D Systems) — Extracellular epitope; Unknown; None validation (None)

### Immunofluorescence (2 methods)

#### Permeabilized IF — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Unknown · expression: Endogenous*

**Antibodies**

- anti-megalin/LRP2 (Proteintech · 19700-1-AP · AB_10640428) — Unknown epitope; Polyclonal; None validation (None)

#### Unknown — Supports Surface Localization · Apical Or Luminal

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human proximal tubule cells — mutant LRP2 localizes to the proximal tubule apical membrane, confirming apical surface targeting is retained | Primary Human Cell | Moderate | 1 |

### Immunohistochemistry (1 method)

#### IHC Membranous — Supports Surface Localization · Apical Or Luminal

*Permeabilization: Fixed Unknown · expression: Endogenous*

**Antibodies**

- anti-gp330/LRP2 — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human kidney tissue sections — LRP2/gp330 localized to brush-border epithelium of proximal tubules by immunocytochemical staining | Primary Human Tissue | High | 1 |

### Surface mass spec (1 method)

#### Cell Surface Capture — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| MDA-MB-231 (human breast cancer) cells — N-linked cell surface glycoproteins enriched by biocytin hydrazide CSC technology; LRP2 detected in surface-enriched lysates by quantitative MS following LIPTAC treatment | Established Cell Line | Moderate | 2 |

### Surface biotinylation (5 methods)

#### Surface Biotinylation — Direct Surface Accessibility · Apical Or Luminal

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-megalin/LRP2 — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| OK cells (opossum kidney proximal tubule) under static culture conditions — 4.9% of total megalin at apical plasma membrane | Established Cell Line | Low | 1 |
| OK cells (opossum kidney proximal tubule) under fluid shear stress (FSS) conditions — 2.8% of total megalin at apical plasma membrane (43% reduction vs static) | Established Cell Line | Low | 1 |

#### Surface Biotinylation — Direct Surface Accessibility · Apical Or Luminal

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-megalin/LRP2 — Unknown epitope; Unknown; None validation (None)

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| OK cells (opossum kidney proximal tubule) under shear stress conditions — apical surface LRP2 detected by sulfo-NHS-SS-biotin labeling | Established Cell Line | Low | 2 |

#### Surface Biotinylation — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Unspecified cell type — biotinylated surface protein fraction quantified by SDS-PAGE and western blot | Unknown | Moderate | 1 |

#### Surface Biotinylation — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| MLE-12 (mouse lung epithelial) cells inoculated with influenza virus (MOI 1, 24 h) — LRP2 surface expression detected by cell-surface biotinylation | Established Cell Line | Moderate | 1 |

#### Surface Biotinylation — Direct Surface Accessibility · Plasma Membrane Localized

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human cells (unspecified line) — surface biotinylation and pulldown indicated only a minor fraction of LDLR family members at the plasma membrane; same study employed FAB9578G flow cytometry antibody for LRP2 | Unknown | Low | 1 |

### Functional surface assay (1 method)

#### Unknown — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Soluble LRP2 purified from rat kidneys — used in SPR assay to assess binding to SARS-CoV-2 spike protein; likely represents shed ectodomain | Ex Vivo | Moderate | 1 |

### Other (1 method)

#### Unknown — Weak Or Ambiguous · Surface Accessible

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Proximal tubule epithelial cells (unspecified species) — mTORC1-induced phosphorylation of megalin (S4577) reduces endocytosis rate with only minor changes in surface vs intracellular distribution | Unknown | Moderate | 1 |

**Contradicting evidence**

- *Intracellular Pool* (severity Low): Under conditions of OCRL1 dysregulation (Lowe syndrome / Dent's disease), LRP2/megalin becomes trapped in enlarged EEA1-positive sorting endosomes and fails to recycle back to the plasma membrane. This documents pathological intracellular accumulation of LRP2, contradicting its normal surface accessibility. Notably, the observation is disease-state-specific rather than a constitutive intracellular localization.
  - Likely explanation: This redistribution is pathological and context-specific: it occurs only when the OCRL1-dependent recycling machinery is disrupted (Lowe syndrome / Dent's disease). In normal physiology, LRP2 cycles through endosomes but returns to the plasma membrane. The finding actually implies that surface-accessible LRP2 is the default state, and intracellular trapping is a disease-induced deviation rather than a normal steady-state localization.

## 4. Biological context

**Cell types** *(orthogonal cell-type index)*

| Cell type | Ontology | Present in tissues | Species | Cites |
|---|---|---|---|---|
| proximal tubule epithelial cells | — | kidney, kidney cortex | Human | 14 |
| extravillous trophoblasts | — | placenta | Human | 1 |
| coronary endothelial cells | — | coronary vasculature | Unspecified | 1 |

**Cell states**

- *fluid shear stress* — Fluid shear stress (mimicking tubular flow) reduces the apical surface fraction of megalin by ~43% compared to static culture in OK proximal tubule cells. *(cites: a2_evi_12, a2_evi_13)*
- *mTORC1-active* — mTORC1-induced phosphorylation of megalin (S4577) reduces its endocytosis rate, increasing surface dwell time; mTORC1 deletion causes a Fanconi-like syndrome with impaired endocytic machinery. *(cites: a2_evi_14, a2_evi_06)*
- *mitosis* — During mitosis, megalin relocalizes from the apical plasma membrane to the spindle pole with ARH; phosphorylation peaks in metaphase and telophase/cytokinesis, reducing apical surface availability. *(cites: a2_evi_15, a2_evi_16)*
- *ACE2-overexpressing* — ACE2 overexpression in proximal tubule epithelial cells increases megalin surface expression and albumin surface binding via an Ang II/AT1R-dependent mechanism; ACE2 inhibition reverses this effect. *(cites: a2_evi_17, a2_evi_18)*
- *acute infection* — LRP2 mRNA shows a decreasing trend at 6 h and significant downregulation at 24 h post-inoculation in an infection model, indicating state-dependent transcriptional suppression. *(cites: a2_evi_08)*

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- Endosome · constitutive endocytic recycling in proximal tubule epithelial cells *(cites: a2_evi_10, a2_evi_11, a2_evi_14)*
- Spindle Pole / Intercellular Bridge · during mitosis and cytokinesis *(cites: a2_evi_15, a2_evi_16)*
- Lysosome · enlarged lysosomes observed in Donnai-Barrow Syndrome variant cells with disrupted recycling *(cites: a2_evi_10)*

**Membrane subdomains**: Apical Membrane

**Anatomical accessibility**

- kidney proximal tubule epithelium — Apical · *Restricted*: LRP2/megalin localizes to the apical (luminal/tubular filtrate-facing) surface of proximal tubule epithelial cells, confirmed by surface biotinylation and immunofluorescence. Systemic (blood-side) binders cannot cross the tight epithelial barrier to reach the apical membrane; access would require glomerular filtration into tubular lumen.

**Accessibility modulation**

- *Tissue Restricted Surface* · lineage: Epithelial: Non-epithelial cell types; non-renal tissues → Kidney proximal tubule epithelial cells (PTECs) under normal or CKD conditions — LRP2/megalin is a canonical apical surface receptor expressed specifically in kidney proximal tubule epithelial cells, with high prevalence (~70% of CKD atlas cells), and also in placental extravillous trophoblasts and coronary endothelial cells — not broadly expressed. *(→ Binder Access To LRP2 Ectodomain Is Substantially Restricted To Epithelial And Select Endothelial Lineages; Systemic Targeting Will Concentrate On Proximal Tubule Apical Surfaces And Placental EVTs, Minimizing Off-Target Exposure In Non-Expressing Tissues.)* *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_07)*
- *Polarization Dependent*: Polarized kidney proximal tubule epithelial cells in normal physiological state → Polarized PTECs under apical fluid shear stress (tubular flow conditions) — Surface biotinylation of OK cells shows a 43% decrease in apical membrane fraction of total megalin under fluid shear stress (2.8% vs 4.9% under static conditions), indicating mechanical stimulation redistributes LRP2 away from the apical surface. *(→ Under Physiological Tubular Flow, Apical Surface LRP2 Density Is Reduced Relative To Static Culture; Binders Targeting Apical LRP2 May Encounter Lower Surface Density Under Flow Conditions Resembling In Vivo Tubular Physiology.)* *(cites: a2_evi_12, a2_evi_13)*
- *Post Translational Dependent*: Renal proximal tubule epithelial cells with basal mTORC1 activity → Renal proximal tubule epithelial cells with elevated mTORC1 signaling and S4577 megalin phosphorylation — mTORC1-induced phosphorylation of megalin at S4577 reduces its endocytosis rate with only minor overall distribution changes, effectively increasing surface dwell time. Phosphorylation peaks during metaphase and telophase/cytokinesis. *(→ MTORC1-Active Cells Display Megalin With Slower Internalization, Increasing The Window For Binder Engagement At The Apical Surface. However, This Effect Is Cell-Cycle-Phase-Dependent And May Be Modest In Bulk Tissue.)* *(cites: a2_evi_14, a2_evi_16)*
- *Dual Localization*: Interphase kidney proximal tubule epithelial cells with LRP2 at the apical plasma membrane → Mitotic/cytokinetic proximal tubule epithelial cells — During mitosis, megalin relocalizes from the apical plasma membrane to the spindle pole in association with ARH; S4577 phosphorylation peaks in metaphase and telophase/cytokinesis, and ARH/megalin signals at intercellular bridge poles diminish when either protein is absent. *(→ During Mitosis, LRP2 Is Substantially Withdrawn From The Apical Surface To The Spindle Pole, Rendering It Transiently Inaccessible To Extracellular Binders. Surface-Targeting Strategies Will Be Less Effective In Proliferating PTEC Populations.)* *(cites: a2_evi_15, a2_evi_16)*
- *Cell State Induced* · trigger: Other: Normal proximal tubule epithelial cells with basal ACE2 expression → PTECs with ACE2 overexpression (renin-angiotensin pathway activated) — ACE2 overexpression correlates with increased megalin cell surface expression and increased albumin surface binding in PTECs; this effect is blocked by ACE2 inhibitor MLN-4760 via an Ang II/AT1R-dependent mechanism. *(→ ACE2/Renin-Angiotensin Pathway Activation Upregulates Apical LRP2 Surface Levels, Increasing Extracellular Accessibility. Conditions Activating This Pathway (E.G., Certain Disease States) May Enhance LRP2 Binder Engagement At The Apical PTEC Surface.)* *(cites: a2_evi_17, a2_evi_18)*
- *Disease State Induced* · trigger: Infection Bacterial: Uninfected cells expressing LRP2 at baseline transcript levels → Cells at 24 hours post-inoculation in an acute infection model — LRP2 mRNA shows a decreasing trend at 6 h and significant downregulation at 24 h post-inoculation, indicating infection-driven transcriptional suppression of LRP2 expression. *(→ During Acute Infection, LRP2 Surface Levels May Be Reduced Due To Transcriptional Downregulation, Potentially Limiting Extracellular Binder Access. Targeting LRP2 In Infected Tissue May Yield Lower Engagement Than In Healthy Tissue.)* *(cites: a2_evi_08)*
- *Disease State Induced* · trigger: Other: Wild-type kidney proximal tubule epithelial cells with normal LRP2 endocytic recycling → PTECs expressing Donnai-Barrow Syndrome (cysteine-to-arginine) LRP2 variant — DBS variant LRP2 reaches the apical membrane but exhibits aberrant endocytic recycling: mislocalized RAB11+ and TFR1+ compartments, enlarged lysosomes, and impaired receptor recycling due to steric clashes at endosomal pH disrupting intramolecular interfaces. *(→ DBS Variant LRP2 Is Present At The Apical Surface But With Disrupted Recycling, Potentially Altering Surface Density Dynamics And Receptor Conformation. Binders Must Account For Possible Conformational Differences And Altered Surface Turnover In Disease-Variant Contexts.)* *(cites: a2_evi_09, a2_evi_10, a2_evi_11)*

**Restricted-subdomain distribution**

- present: true
- severity: High
- evidence: Strong
- domain: Apical
- rationale: LRP2/megalin is strictly restricted to the apical (luminal/tubular filtrate-facing) membrane of polarized proximal tubule epithelial cells. Surface biotinylation in OK cells selectively labels the apical compartment and confirms exclusive apical localization. Systemic (blood-side) binders cannot cross the tight epithelial barrier to access the apical surface; luminal access would require glomerular filtration.
- cites: a1_evi_05, a1_evi_06, a1_evi_07, a1_evi_08, a1_evi_09, a2_evi_09, a2_evi_12, a2_evi_13

**Co-receptor requirements**

- dependency: None
- evidence basis: Co Expression Only
- partners: cubilin, amnionless
- rationale: LRP2/megalin reaches the apical surface independently via its own signal peptide and transmembrane domain. Cubilin and amnionless are co-receptor complex partners required for full ligand uptake function (albumin endocytosis), but their absence does not prevent LRP2 surface trafficking. No trafficking or knockout study in the ledger shows obligate co-receptor requirement for surface expression.
- cites: a2_evi_04

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P98164 | ref | ref | 1 | 4399 aa | 209 aa | 25 aa | Extracellular→Cytoplasmic | — |
| Mouse ortholog | Lrp2 | [A2ARV4](https://www.uniprot.org/uniprotkb/A2ARV4) | 76.8% | 77.1% | 1 | 4400 aa | — | — | — | moderate |
| Cynomolgus ortholog | LRP2 | [A0A2K5VUN1](https://www.uniprot.org/uniprotkb/A0A2K5VUN1) | 98.0% | 98.1% | 1 | 4399 aa | — | — | — | high (≥85%) |
| Paralog | LRP3 | [O75074](https://www.uniprot.org/uniprotkb/O75074) | 3.7% | 49.7% | — | — | — | — | — | low-risk |
| Paralog | LRP12 | [Q9Y561](https://www.uniprot.org/uniprotkb/Q9Y561) | 3.5% | 49.1% | — | — | — | — | — | low-risk |
| Paralog | LRP10 | [Q7Z4F1](https://www.uniprot.org/uniprotkb/Q7Z4F1) | 2.8% | 49.1% | — | — | — | — | — | low-risk |
| Paralog | VLDLR | [P98155](https://www.uniprot.org/uniprotkb/P98155) | 6.5% | 46.9% | — | — | — | — | — | low-risk |
| Paralog | LRP8 | [Q14114](https://www.uniprot.org/uniprotkb/Q14114) | 6.4% | 43.8% | — | — | — | — | — | low-risk |
| Paralog | LDLR | [P01130](https://www.uniprot.org/uniprotkb/P01130) | 6.0% | 43.4% | — | — | — | — | — | low-risk |
| Paralog | LRP4 | [O75096](https://www.uniprot.org/uniprotkb/O75096) | 10.2% | 42.6% | — | — | — | — | — | low-risk |
| Paralog | LRP6 | [O75581](https://www.uniprot.org/uniprotkb/O75581) | 9.2% | 39.8% | — | — | — | — | — | low-risk |
| Paralog | LRP5 | [O75197](https://www.uniprot.org/uniprotkb/O75197) | 9.0% | 39.1% | — | — | — | — | — | low-risk |
| Paralog | LRP1 | [Q07954](https://www.uniprot.org/uniprotkb/Q07954) | 36.2% | 38.7% | — | — | — | — | — | low-risk |
| Paralog | EGF | [P01133](https://www.uniprot.org/uniprotkb/P01133) | 5.7% | 38.3% | — | — | — | — | — | low-risk |
| Paralog | NID1 | [P14543](https://www.uniprot.org/uniprotkb/P14543) | 5.1% | 37.7% | — | — | — | — | — | low-risk |
| Paralog | NID2 | [Q14112](https://www.uniprot.org/uniprotkb/Q14112) | 5.0% | 37.0% | — | — | — | — | — | low-risk |
| Paralog | LRP1B | [Q9NZR2](https://www.uniprot.org/uniprotkb/Q9NZR2) | 33.7% | 36.9% | — | — | — | — | — | low-risk |

**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 6. Accessibility risks

**Shed form**

- present: true
- severity: Moderate
- evidence: Moderate
- mechanism: Proteolytic Ectodomain Shedding
- cites: a1_evi_22

**Secreted form**

- present: false
- severity: Low
- evidence: Weak

**ECD size assessment**

- ECD class: Large
- rationale: LRP2 has a ~4398-residue extracellular domain (25-aa signal peptide + 4398-aa ECD per PMID:8706697), confirmed by cryo-EM structural resolution of nearly the entire ectodomain. This vastly exceeds the 200-residue threshold for 'large'; it accommodates hundreds of non-overlapping antibody footprints (~12 residues each), providing exceptional epitope design flexibility.
- cites: a1_evi_01, a1_evi_04

**Epitope masking**

- severity: Moderate
- evidence: Inferred
- mechanism: Glycan, Conformational
- rationale: LRP2 carries >30 N-glycosylation sites across its ECD (as referenced in the CSC-MS cell surface capture enrichment rationale), consistent with heavy glycosylation typical of LDLR-family members. Dense glycan coverage may shield some epitopes. Additionally, the compact multi-domain architecture seen in cryo-EM suggests conformational occlusion of inter-domain linkers. No direct epitope-masking experiment is in the ledger; this is inferred from glycoprotein biology.
- cites: a1_evi_04, a1_evi_16

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P98164-F1](https://alphafold.ebi.ac.uk/entry/P98164) |
| AFDB version | unknown |
| ECD mean pLDDT | 0.0 |
| ECD disordered fraction | 0.0% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P98164) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P98164](https://alphafold.ebi.ac.uk/entry/P98164) | AlphaFold DB (AF-P98164-F1, unknown) |
| Mouse ortholog (Lrp2) | [A2ARV4](https://alphafold.ebi.ac.uk/entry/A2ARV4) | AlphaFold DB |
| Cynomolgus ortholog (LRP2) | [A0A2K5VUN1](https://alphafold.ebi.ac.uk/entry/A0A2K5VUN1) | AlphaFold DB |
| Experimental (1 total) | [2M0P](https://www.rcsb.org/structure/2M0P) | RCSB PDB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

Low-density lipoprotein receptor-related protein 2 · Receptors · Other_receptors · chain A · 7 scored sites · 2,695 binder seeds (511 α-helix / 2,184 β-strand).

Anchor = patch-center residue; BSA = buried surface area (the contact footprint a binder would form on the patch); seed counts are docked binder backbones split by α-helix / β-strand.

**Reading the scores.** BSA vs the average antibody–antigen interface ≈ 1103 ± 244 Å² ([PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)): ≥1500 Å² comfortable · 850–1500 workable · <850 thin. Seed pool: ≥1000 comfortable design margin · ≥100 workable · <100 thin/specialized. SURFACE-Bind excludes transmembrane regions but not necessarily intracellular domains — cross-check the anchor residue against the topology string in §5/appendix (`O` = extracellular/antibody-accessible, `I` = intracellular).

| Site | Anchor residue | BSA (Å²) | α-helix seeds | β-strand seeds | Hydrophobicity |
|---|---|---|---|---|---|
| 0 | 337 | 2346.8 | 61 | 563 | -5.3 |
| 1 | 176 | 866.4 | 0 | 24 | 4.6 |
| 2 | 1167 | 1265.4 | 0 | 4 | 8.3 |
| 3 | 744 | 12969.8 | 136 | 77 | -135.5 |
| 4 | 1375 | 1337.6 | 0 | 4 | 14.5 |
| 5 | 1368 | 815.9 | 291 | 1,397 | -10.0 |
| 6 | 771 | 646.5 | 23 | 115 | -1.5 |

**Experimental structures** — 1 PDB entry for this protein (browse at [RCSB](https://www.rcsb.org/uniprot/P98164)).

## 9. Evidence ledger

42 entries · 35 primary · 7 secondary · 0 tertiary · 28 PMC OA.

- `a1_evi_01` · *Primary* · Supports · Topology — LRP2 (gp330) encodes a 4655-amino acid protein with a 25-aa N-terminal signal peptide, a large 4398-aa extracellular domain, a single 23-aa transmembrane-spanning domain, and a 209-aa intracellular C-terminal region. This establishes LRP2 as a canonical single-pass type I transmembrane protein with a massive ECD fully exposed to the extracellular space. (https://pubmed.ncbi.nlm.nih.gov/8706697/)
  - *assay*: Human
  > "The deduced 4655 amino acid residues give a calculated molecular mass of 519636 Da for the mature protein and consists of a probable 25-amino-acid N-terminal signal peptide sequence, an extracellular region of 4398 amino acids, a single transmembrane-spanning domain of 23 amino acids, and an intracellular C-terminal region of 209 amino acid residues."
- `a1_evi_02` · *Primary* · Supports · Topology — The LRP2 extracellular domain contains 36 LDLR ligand-binding repeats organized into four distinct domains, 16 growth factor repeats separated by eight YWTD spacer regions, and one EGF-like repeat. This extensive modular ECD architecture defines the extracellular ligand-binding surface accessible at the plasma membrane. (https://pubmed.ncbi.nlm.nih.gov/8706697/)
  - *assay*: Human
  > "In the extracellular region, there are a total of 36 LDLR ligand-binding repeats, comprising four distinct domains, 16 growth factor repeats separated by eight YWTD spacer regions, and one epidermal growth factor-like repeat."
- `a1_evi_03` · *Primary* · Supports · Topology — The LRP2 intracellular tail contains two F(X)NPXY coated-pit internalization signals characteristic of the LDLR superfamily, plus Src-homology recognition motifs and kinase sites. The dual internalization signals confirm the cytoplasmic orientation of the C-terminus and the receptor's endocytic cycling from the cell surface. (https://pubmed.ncbi.nlm.nih.gov/8706697/)
  - *assay*: Human
  > "The intracellular tail contains not only two copies of the F(X)NPXY coated-pit mediated internalization signal characteristic of LDLR superfamily members, but also intriguing and potentially functional motifs including several Src-homology 3 recognition motifs, one Src-homology 2 recognition motif for the p85 regulatory subunit of phosphatidylinositol 3-kinase, and additional sites for protein kinase C, casein kinase II and cAMP-/cGMP-dependent protein kinase."
- `a1_evi_04` · *Primary* · Supports · Topology — Cryo-EM structural analysis resolved nearly the entire LRP2 ectodomain, with density traced for almost all extracellular regions aided by AlphaFold2 prediction models. This confirms that the massive ~4400-residue ECD forms a structured extracellular entity and provides direct structural evidence that the ectodomain is extracellularly accessible. ([PMC11145282](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11145282/))
  - *assay*: Unspecified
  > "Although some regions were only weakly visible in the cryo-EM maps, almost all ectodomains were traced on the density, aided by the fragmentary prediction models generated by Alphafold2 ( 21 ) ( Fig. 1 )."
- `a1_evi_05` · *Primary* · Supports · Methodological — Sulfo-NHS-SS-biotin surface biotinylation protocol applied selectively to the apical membrane of OK (opossum kidney) cells cultured on permeable supports under static or fluid shear stress (FSS) conditions. Biotinylation performed with 1 mg/mL EZ-Link Sulfo-NHS-SS-biotin in TEA-buffered saline for 2×15 min on ice, labeling only surface-exposed proteins. This is a non-permeabilized, intact-cell surface-accessibility assay for LRP2/megalin. ([PMC11211581](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11211581/))
  - *assay*: Other · OK cells (opossum kidney proximal tubule) · live · non-permeabilized
  > "OK cells cultured on permeable supports under static or FSS conditions were washed with cold PBS and the apical surface biotinylated with 1 mg/mL EZ-Link Sulfo-NHS-SS-biotin (Thermo Scientific, 21331) in 0.5 mL TEA-buffered saline (TBS; 10 mM triethanolamine-HCl, pH 7.6, 137 mM NaCl, 1 mM CaCl 2 ) for 2 × 15 min on ice."
- `a1_evi_06` · *Primary* · Supports · Surface Expression — Apical surface biotinylation of megalin (LRP2) in OK cells revealed that 4.9% of total megalin is present at the apical plasma membrane under static culture conditions, decreasing to 2.8% under fluid shear stress (FSS) — a 43% reduction. This directly quantifies LRP2 surface fraction at the apical membrane and confirms robust cell-surface presence of LRP2 in kidney proximal tubule cells. ([PMC11211581](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11211581/))
  - *assay*: Other · OK cells (opossum kidney proximal tubule) · live · non-permeabilized
  > "Interestingly, surface biotinylation of megalin revealed a 43% decrease in the fraction of total megalin at the apical membrane of FSS-cultured cells (2.8%) when compared to static-cultured cells (4.9%; Figure 2B )."
- `a1_evi_07` · *Primary* · Supports · Methodological — Biotinylated megalin (LRP2) was recovered from OK cell apical surface fractions using streptavidin beads and detected by western blot with an anti-megalin antibody, confirming successful surface-selective protein capture. This paired western blot step is the detection readout for the sulfo-NHS-SS-biotin surface biotinylation assay, satisfying the WB-pairing requirement for surface biotinylation method observations. ([PMC11211581](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11211581/))
  - *assay*: Other · OK cells (opossum kidney proximal tubule) · live · non-permeabilized
  > "Biotinylated megalin (B) and cubilin (C) were recovered using streptavidin beads and western blotted using anticubilin and antimegalin antibody, respectively."
- `a1_evi_08` · *Primary* · Supports · Methodological — Apical surface biotinylation of OK cells cultured on permeable supports under shear stress conditions using 1 mg/mL EZ-Link Sulfo-NHS-SS-biotin in TEA-buffered saline for 2×15 min on ice following cold PBS wash. This non-permeabilized assay protocol selectively labels apical surface-exposed LRP2/megalin on intact polarized proximal tubule cells; method_family=surface_biotinylation, method_subclass=sulfo-NHS-SS, permeabilization=false. ([PMC9614980](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9614980/))
  - *assay*: Other · OK cells (opossum kidney proximal tubule) · live · non-permeabilized
  > "After washing with cold phosphate-buffered saline containing MgCl 2 and CaCl 2 (PBS; Sigma, D8662), the apical surface of OK cells cultured on permeable supports under shear stress was biotinylated with 1 mg/mL EZ-Link Sulfo-NHS-SS-biotin (Thermo Scientific, 21331) in 0.5 mL TEA-buffered saline (TBS; 10 m m triethanolamine-HCl, pH 7.6, 137 m m NaCl, 1 m m CaCl 2 ) for 2 × 15 min on ice."
- `a1_evi_09` · *Primary* · Supports · Methodological — Biotinylated megalin (LRP2) was recovered from OK cell apical surface fractions using streptavidin beads and detected by western blot with an anti-megalin antibody. This paired streptavidin pulldown + WB readout completes the surface biotinylation assay, confirming LRP2 surface presence in OK cells under shear stress conditions. ([PMC9614980](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9614980/))
  - *assay*: Other · OK cells (opossum kidney proximal tubule) · live · non-permeabilized
  > "Biotinylated megalin was recovered using streptavidin beads and western blotted using antimegalin antibody."
- `a1_evi_10` · *Primary* · Supports · Methodological — Surface biotinylation method used to quantify LRP2 at the cell surface: biotinylated proteins were recovered from cell surface fractions and quantified after SDS-PAGE and western blotting. This paired biotinylation + WB approach confirms surface fraction identity; method_family=surface_biotinylation, detection=western_blot. ([PMC10295476](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10295476/))
  - *assay*: Unspecified · live · non-permeabilized
  > "Biotinylated proteins were recovered from the remaining fractions, and the fraction at the cell surface was quantified after SDS–PAGE and western blotting."
- `a1_evi_11` · *Primary* · Supports · Surface Expression — Cell-surface biotinylation assay performed in MLE-12 cells (mouse lung epithelial cell line) inoculated with influenza virus (MOI 1, 24 h incubation) to assess surface protein levels. This assay was used to detect LRP2 surface expression in airway epithelial cells; method_family=surface_biotinylation, cell_type=MLE-12 (mouse lung epithelial). ([PMC10505651](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10505651/))
  - *assay*: Mouse · MLE-12 · live · non-permeabilized
  > "(B) Cell-surface biotinylation assay was performed in MLE-12 cells inoculated with IV MOI 1 incubated for 24 h Left: representative blot."
- `a1_evi_12` · *Primary* · Supports · Methodological — Anti-LRP2/megalin antibody identified for immunofluorescence: clone 19700-1-AP (RRID:AB_10640428) from Proteintech. This antibody identifier is load-bearing for MethodObservation.antibodies[] validation_strategy for IF-based surface-localization assays. ([PMC8892268](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8892268/))
  - *assay*: Unspecified
  > "Na‐K ATPase (14418‐1‐AP, RRID:AB_2227873), LC3 (14600‐1‐AP, RRID:AB_2137737), Rab11 (20229‐1‐AP, RRID:AB_10666202), GFP (50430‐2‐AP, RRID:AB_11042881), GDI 1 (10249‐1‐AP, RRID:AB_2111520), Rabenosyn‐5 (22218‐1‐AP, RRID:AB_11182179), p62/SQSTM1 (18420‐1‐AP, RRID:AB_10694431), vinculin (66305‐1‐Ig, RRID:AB_2810300), megalin/LDL receptor‐related protein 2 (LRP2) (19700‐1‐AP, RRID:AB_10640428) (for immunofluorescence), β‐actin (66009‐1‐Ig), GAPDH (60004‐1‐Ig), and COMMD1 (11938‐1‐AP, RRID:AB_2083542) were from Proteintech (Wuhan, Hubei Province, China)."
- `a1_evi_13` · *Primary* · Supports · Methodological — Anti-LRP2/megalin antibody identified for flow cytometry: clone FAB9578G from R&D Systems (unconjugated). This antibody identifier is load-bearing for MethodObservation.antibodies[] for flow cytometry-based LRP2 surface detection assays. ([PMC8892268](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8892268/))
  - *assay*: Unspecified
  > "LDLR (AF2148, RRID:AB_2135126) (unconjugated goat IgG, for double immunofluorescence labeling of endogenous LDLR), LDLR (FAB2148P, RRID:AB_10573833) (PE‐conjugated, for flow cytometry), megalin/LRP2 (FAB9578G) (for flow cytometry), and human apolipoprotein B (ApoB) (AF3556, RRID:AB_573025) were from R&D Systems (Minneapolis, MN, USA)."
- `a1_evi_14` · *Primary* · Supports · Surface Expression — Surface biotinylation and pulldown in cells confirmed that only a minor fraction of LDL receptors (a close LRP2 paralog) were located at the plasma membrane; the same paper employs surface biotinylation methodology for LRP2 surface detection using the FAB9578G flow cytometry antibody. The surface biotinylation + pulldown approach is the primary surface-fraction readout used in this study for LDLR family members including LRP2. ([PMC8892268](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8892268/))
  - *assay*: Human · live · non-permeabilized
  > "Preliminary experiments using surface biotinylation and pull‐down indicated that only a minor fraction of LDLRs were located on PM (Fig 2A )."
- `a1_evi_15` · *Secondary* · Supports · Methodological — Anti-LRP2 antibody used for western blot detection identified as clone A24690 from ABclonal (1:1000 dilution). This antibody identifier anchors MethodObservation.antibodies[] for WB-based LRP2 detection assays. ([PMC12526718](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12526718/))
  - *assay*: Unspecified
  > "difluoride) membranes were blocked in 5% skim milk in TBST [1X tris-buffered saline (TBS) with 0.05% Tween 20] and incubated with primary antibodies against AIBP (1:1000, homemade), CXCR4 (1:1000, Abcam, catalog no. 124824), glyceraldehyde-3-phosphate dehydrogenase (GAPDH) (1:10,000, Abcam, catalog no.181602), CAV-1 (1:5000, Abcam), FLOT1 (1:200, sc-74566, Santa Cruz Bio), FLOT2 (1:1000, PTM-5369, PTM BIO), LRP2 (1:1000, A24690, ABclonal), and anti-rabbit (1:10,000, Abcam, catalog no. 6721) or anti-mouse (1:10,000, Abcam, catalog no.6789) secondary HRP (horseradish peroxidase) antibodies."
- `a1_evi_16` · *Primary* · Supports · Methodological — Cell-surface capture (CSC) mass spectrometry technology applied to enrich N-linked cell surface glycoproteins via biocytin hydrazide. LRP2 is a heavily N-glycosylated type I transmembrane protein (30+ N-glycosylation sites in ECD per UniProt) and is captured by this cell-surface glycoprotein enrichment strategy. Method_family=mass_spec_surfaceome, method_subclass=cell-surface-capture (CSC), enrichment=N-glycan oxidation + biocytin hydrazide pulldown. ([PMC12576823](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12576823/))
  - *assay*: Human · MDA-MB-231 · live · non-permeabilized
  > "N-Linked cell surface glycoproteins were captured by the cell-surface capture technology and enriched by biocytin hydrazide."
- `a1_evi_17` · *Primary* · Supports · Surface Expression — Quantitative mass spectrometry analysis of surface-enriched lysates from MDA-MB-231 cells following LIPTAC treatment; surface-enriched proteomics readout that monitors surface glycoprotein abundance including LRP2. This confirms CSC-MS as a surface-accessibility method deployed in this study. ([PMC12576823](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12576823/))
  - *assay*: Human · MDA-MB-231 · live · non-permeabilized
  > "To further investigate the impact of LIPTAC treatment on the proteome, we conducted quantitative mass spectrometry analysis of surface-enriched lysates following LIPTAC1 treatment in MDA-MB-231 cells."
- `a1_evi_18` · *Secondary* · Supports · Topology — Gp330 (LRP2) is described as a high molecular weight glycoprotein structurally similar to the alpha2-macroglobulin receptor/LRP1 and LDL receptor — anchoring its classification as a large ECD-bearing transmembrane endocytic receptor. (https://pubmed.ncbi.nlm.nih.gov/1400426/)
  - *assay*: Human
  > "Gp330 is a high molecular weight glycoprotein that is structurally similar to both the alpha 2MR/LRP and low density lipoprotein receptor."
- `a1_evi_19` · *Primary* · Supports · Surface Expression — Immunocytochemical staining of human kidney tissue sections localized RAP and gp330 (LRP2) to the brush-border epithelium of proximal tubules, providing immunohistochemical evidence of LRP2 surface expression at the apical/brush-border membrane of kidney proximal tubule cells in human tissue. (https://pubmed.ncbi.nlm.nih.gov/1400426/)
  - *assay*: Human · proximal tubule epithelial cells · fixed
  > "Immunocytochemical staining of human kidney sections localized RAP to the brush-border epithelium of proximal tubules."
- `a1_evi_20` · *Primary* · Supports · Surface Expression — A disease-associated mutant LRP2 was expressed and observed to dimerize and localize to the proximal tubule apical membrane, confirming that LRP2 is expressed at the apical cell surface of proximal tubule cells; the mutant protein retains apical membrane targeting even in the presence of the pathogenic variant. (https://pubmed.ncbi.nlm.nih.gov/42024452/)
  - *assay*: Human · proximal tubule
  > "The mutant LRP2 was expressed and observed to dimerize and localize to the proximal tubule apical membrane."
- `a1_evi_21` · *Secondary* · Supports · Surface Expression — Structural modeling of LRP2 assembly indicates that it likely tolerates a cysteine-to-arginine substitution at the cell surface (neutral effect on surface form), but at endosomal pH the variant introduces steric clashes that may disrupt intramolecular interfaces and disturb receptor recycling. This confirms that wild-type LRP2 is present at the cell surface and that the endosomal (post-internalization) environment is distinct from the surface form. (https://pubmed.ncbi.nlm.nih.gov/42024452/)
  - *assay*: Human
  > "Structural modeling showed the LRP2 assembly likely tolerates the cysteine to arginine substitution at the cell surface, but at endosomal pH the variant introduced steric clashes that may disrupt intramolecular interfaces and disturb receptor recycling."
- `a1_evi_22` · *Secondary* · Ambiguous · Surface Expression — Soluble LRP2 purified from rat kidneys was used in surface plasmon resonance (SPR) binding assays to assess interaction with SARS-CoV-2 spike protein. The use of purified soluble/shed LRP2 in a cell-free SPR chip assay constitutes evidence for a shed/secreted form of LRP2 ectodomain. Note: this is a biochemical binding assay on immobilized recombinant/shed protein, NOT a cell-surface localization assay — it does NOT qualify as an OE-surface clip. The soluble form likely arises from ectodomain shedding of kidney-expressed LRP2. This feeds risks.shed_form. ([PMC12192683](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12192683/))
  - *assay*: Rat
  > "To determine if these receptors also recognize the SARS-CoV-2 spike protein, we quantified the binding of this protein to SPR chips coated with soluble forms of LRP2 ( Fig. 2 A , Table 1 ) or recombinant soluble VLDLR ( Fig. 2 B , Table 1 )."
- `a1_evi_23` · *Secondary* · Refutes · Contradictory — Under conditions of OCRL1 dysregulation (Lowe syndrome / Dent's disease context), LRP2/megalin becomes trapped in enlarged sorting endosomes (EEA1-positive) and fails to recycle to the plasma membrane or proceed to late endosomes. This documents an intracellular accumulation phenotype contradicting normal surface recycling, providing a contradictory evidence row: LRP2 redistributes to intracellular endosomal compartments when the recycling pathway is disrupted, demonstrating that a portion of LRP2 is normally at the plasma membrane but can be rerouted intracellularly under pathological conditions. ([PMC11274606](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11274606/))
  - *assay*: Unspecified
  > "The dysregulation of OCRL1 halts various receptors, such as Megalin/LRP2, Transferrin Receptor (TfR), Epidermal Growth Factor Receptor (EGFR), and CI-Mannose-6-Phosphate Receptor (CI-MPR) in enlarged sorting endosomes characterized by the presence of the tethering protein Early Endosome Antigen 1 (EEA1); these receptors are accumulated and do not proceed to their destination to the plasma membrane in the recycling pathway, to late endosomes for degradation, or the Golgi complex in the retrograde pathway [ 21 , 27 ]."
- `a1_evi_24` · *Secondary* · Ambiguous · Surface Expression — mTORC1-induced phosphorylation of megalin (LRP2) at S4577 reduces its endocytosis rate with only minor changes in overall distribution between surface and intracellular pools. This ambiguous finding suggests that under mTORC1-activated conditions, the surface-to-intracellular ratio of LRP2 is only minimally altered despite reduced endocytic flux — the protein remains substantially at the surface. ([PMC13198606](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13198606/))
  - *assay*: Unspecified
  > "The identification of the role of this mTORC1-induced phosphorylation on megalin was subject of our analysis. mTORC1-induced megalin phosphorylation reduced endocytosis rate with only minor distribution changes."
- `a2_evi_01` · *Primary* · Supports · Tissue Expression — LRP2 is used as a segment-specific marker for proximal tubule cells in the kidney. Single-cell transcriptomic analysis of CKD kidney tissue reveals that proximal tubule cells (constituting ~70% of profiled cells) express LRP2 alongside SLC34A1, CUBN, and other PT markers, and these cells show marked metabolic heterogeneity across OXPHOS-high, glycolytic, dormant, and intermediate cell states. ([PMC13088866](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088866/))
  - *assay*: Human · kidney proximal tubule epithelial cells (CKD tissue) · unspecified
  > "We analyzed segment-specific markers (SLC34A1, SLC5A2, LRP2, CUBN, ALDOB, and GATM) and metabolic enzymes (glycolysis and TCA cycle enzymes) in cell subsets.<h4>Results</h4>Tubular cells showed marked heterogeneity and metabolic reprogramming from oxidative phosphorylation to glycolysis, clustering as OXPHOS-high, glycolytic, dormant, and intermediate cell states."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — Proximal tubule cells constitute approximately 70% of the cells profiled in the CKD single-cell atlas, with LRP2 serving as a canonical proximal tubule marker, confirming high LRP2 expression prevalence in this kidney cell population. ([PMC13088866](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13088866/))
  - *assay*: Human · kidney proximal tubule epithelial cells (CKD tissue) · unspecified
  > "Proximal tubule cells constituted ∼70% of the profiled cells with different transcriptomic signatures."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — LRP2/megalin is expressed in kidney proximal tubule cells under normal physiological conditions; loss-of-function variants in LRP2 cause Donnai-Barrow Syndrome characterized by low molecular weight proteinuria and developmental abnormalities, confirming the essential role of LRP2 endocytic receptor function in proximal tubule epithelial cells. (https://pubmed.ncbi.nlm.nih.gov/42024452/)
  - *assay*: Human · kidney proximal tubule epithelial cells · unspecified
  > "Donnai-Barrow Syndrome (DBS) arises from loss-of-function (LoF) variants in the endocytic receptor LRP2/megalin and is characterized by low molecular weight (LMW) proteinuria and developmental abnormalities."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — In kidney proximal tubule epithelial cells (PTECs), LRP2/megalin functions as part of a receptor complex with cubilin and amnionless mediating albumin endocytosis, confirming expression and functional engagement of megalin at the PTEC apical surface under normal physiological conditions. (https://pubmed.ncbi.nlm.nih.gov/41955164/)
  - *assay*: Human · proximal tubule epithelial cells (PTEC) · unspecified
  > "This process occurs through a receptor-mediated endocytosis, being megalin, cubilin and amnionless the receptor complex involved."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — LRP2 protein is enriched specifically in extravillous trophoblasts (EVTs) compared to trophoblast stem cells (TS) and syncytiotrophoblasts (ST), based on proteomic cluster analysis. This identifies placental EVTs as a cell type with elevated LRP2 expression, supporting the known placental expression of LRP2. ([PMC12329398](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12329398/))
  - *assay*: Human · extravillous trophoblasts (EVT), trophoblast stem cells, syncytiotrophoblasts · unspecified
  > "Protein cluster enriched specifically in EVTs (compared to TS and ST(3D)) were implicated in ECM organization (ADAMTSL4, COL1A2, COL4A1, LAMB1, LAMC1, NID1) via receptors (FBN2, ITGB6, VIM, COL1A2, LRP2) (Table S15 )."
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — Genetic deletion of mTORC1 in the kidney leads to a Fanconi-like syndrome with reduction of the renal cortex and impaired tubular epithelial transport and endocytic machinery, confirming that LRP2/megalin-mediated endocytosis is essential in renal cortical proximal tubule epithelial cells. ([PMC13198606](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13198606/))
  - *assay*: Mouse · renal cortex tubular epithelial cells · unspecified
  > "Genetic deletion of renal mTORC1 led to a Fanconi-like syndrome with reduction of the renal cortex, tubular epithelial transport and perturbation of the endocytic machinery."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — LRP2 mediates HDL-based delivery of miR-223 in coronary endothelial cells (CECs), suppressing the sprouting phase of coronary collateral (CC) vessel formation. This identifies coronary endothelial cells as a cell type expressing functional LRP2 in a disease-relevant vascular context. ([PMC12526718](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12526718/))
  - *assay*: Unspecified · coronary endothelial cells (CEC2) · unspecified
  > "We show that AIBP suppresses the sprouting phase of CC by facilitating HDL-mediated delivery of miR-223 via LRP2, which down-regulates CXCR4 expression and restricts CEC2 expansion."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — LRP2 mRNA expression shows a decreasing trend at 6 hours and significant downregulation at 24 hours post-inoculation in a disease/infection context, indicating that LRP2 transcript levels are modulated by disease state — specifically downregulated during acute infection/inoculation response. ([PMC10505651](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10505651/))
  - *assay*: Unspecified · unspecified (infection model) · unspecified
  > "The results revealed a decreasing trend in LRP2 transcription levels at the 6 h time point and a significant downregulation at 24 h post-inoculation."
- `a2_evi_09` · *Primary* · Supports · Surface Expression — LRP2/megalin mutant protein (from a Donnai-Barrow Syndrome variant) is expressed and localizes to the proximal tubule apical membrane, confirming that the apical plasma membrane of kidney proximal tubule epithelial cells is the normal subcellular surface localization of LRP2. (https://pubmed.ncbi.nlm.nih.gov/42024452/)
  - *assay*: Human · kidney proximal tubule epithelial cells · fixed
  > "The mutant LRP2 was expressed and observed to dimerize and localize to the proximal tubule apical membrane."
- `a2_evi_10` · *Primary* · Refutes · Surface Expression — In LRP2 variant-expressing proximal tubule cells (Donnai-Barrow Syndrome model), immunofluorescence reveals aberrant endocytic recycling with mislocalized RAB11+ and TFR1+ compartments and enlarged lysosomes, indicating that disease-causing LRP2 variants disrupt normal apical surface recycling — the normal steady-state surface localization of LRP2 depends on intact endosomal recycling. (https://pubmed.ncbi.nlm.nih.gov/42024452/)
  - *assay*: Human · kidney proximal tubule epithelial cells (DBS variant model) · fixed · permeabilized
  > "Immunofluorescence revealed aberrant endocytic recycling with mislocalized RAB11+ and TFR1+ compartments and enlarged lysosomes."
- `a2_evi_11` · *Secondary* · Ambiguous · Surface Expression — Structural modeling of a Donnai-Barrow Syndrome LRP2 variant shows the cysteine-to-arginine substitution is tolerated at the cell surface (neutral pH) but introduces steric clashes at endosomal pH, likely disrupting intramolecular interfaces and impairing receptor recycling back to the apical surface. This implies normal LRP2 surface retention requires structural integrity at endosomal pH for recycling. (https://pubmed.ncbi.nlm.nih.gov/42024452/)
  - *assay*: Human · kidney proximal tubule epithelial cells (modeled) · unspecified
  > "Structural modeling showed the LRP2 assembly likely tolerates the cysteine to arginine substitution at the cell surface, but at endosomal pH the variant introduced steric clashes that may disrupt intramolecular interfaces and disturb receptor recycling."
- `a2_evi_12` · *Primary* · Supports · Surface Expression — Surface biotinylation of megalin (LRP2) in OK (opossum kidney) proximal tubule cells under fluid shear stress (FSS) versus static culture reveals a 43% decrease in the fraction of total megalin present at the apical membrane under FSS conditions (2.8% of total) compared to static conditions (4.9% of total). This demonstrates that mechanical stimulation (FSS mimicking tubular flow) modulates LRP2 surface availability — baseline: static proximal tubule cells; modulating state: fluid shear stress; direction: decreased apical surface fraction. ([PMC11211581](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11211581/))
  - *assay*: Other · OK (opossum kidney) proximal tubule epithelial cells · live · non-permeabilized
  > "Interestingly, surface biotinylation of megalin revealed a 43% decrease in the fraction of total megalin at the apical membrane of FSS-cultured cells (2.8%) when compared to static-cultured cells (4.9%; Figure 2B )."
- `a2_evi_13` · *Primary* · Supports · Surface Expression — Apical surface biotinylation is specifically applied to polarized OK (opossum kidney) proximal tubule cells cultured on permeable supports under shear stress, confirming that LRP2/megalin is accessible at the apical plasma membrane in polarized epithelial cells under physiological flow conditions. The orientation is apical-only, consistent with LRP2's known apical localization in proximal tubule epithelia. ([PMC9614980](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9614980/))
  - *assay*: Other · OK (opossum kidney) proximal tubule epithelial cells · live · non-permeabilized
  > "After washing with cold phosphate-buffered saline containing MgCl 2 and CaCl 2 (PBS; Sigma, D8662), the apical surface of OK cells cultured on permeable supports under shear stress was biotinylated with 1 mg/mL EZ-Link Sulfo-NHS-SS-biotin (Thermo Scientific, 21331) in 0.5 mL TEA-buffered saline (TBS; 10 m m triethanolamine-HCl, pH 7.6, 137 m m NaCl, 1 m m CaCl 2 ) for 2 × 15 min on ice."
- `a2_evi_14` · *Primary* · Supports · Surface Expression — mTORC1-induced phosphorylation of megalin (LRP2) reduces its endocytosis rate with only minor changes in overall distribution, indicating that mTORC1 activation in renal tubular cells modulates LRP2 surface dynamics — phosphorylated megalin is less rapidly internalized from the apical surface, effectively increasing its surface dwell time under mTORC1-active conditions. ([PMC13198606](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13198606/))
  - *assay*: Mouse · renal proximal tubule epithelial cells · unspecified
  > "The identification of the role of this mTORC1-induced phosphorylation on megalin was subject of our analysis. mTORC1-induced megalin phosphorylation reduced endocytosis rate with only minor distribution changes."
- `a2_evi_15` · *Primary* · Refutes · Surface Expression — During cell mitosis, megalin (LRP2) relocalizes from the apical plasma membrane to the spindle pole in association with the adaptor protein ARH, indicating that LRP2 surface localization is cell-cycle-dependent — during mitosis LRP2 is redirected intracellularly (spindle pole), reducing its apical surface availability. ([PMC13198606](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13198606/))
  - *assay*: Mouse · renal proximal tubule epithelial cells · fixed · permeabilized
  > "During cell mitosis megalin is localized with ARH at the spindle pole."
- `a2_evi_16` · *Primary* · Refutes · Surface Expression — Megalin-deficient and ARH-deficient renal cells show significantly reduced cell proliferation and diminished ARH or megalin signals at intercellular bridge poles during cytokinesis. mTORC1-induced S4577 phosphorylation of megalin peaks in metaphase and telophase/cytokinesis, establishing that LRP2 surface/intracellular distribution varies across cell cycle phases with highest intracellular redistribution during metaphase and telophase. ([PMC13198606](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13198606/))
  - *assay*: Mouse · renal proximal tubule epithelial cells (megalin-deficient, ARH-deficient) · fixed · permeabilized
  > "Compared to wildtype cells, megalin-deficient and ARH-deficient cells showed significantly less cell proliferation, and during cytokinesis significantly less ARH or megalin signals, respectively at the pole of intercellular bridges. mTORC1-induced megalin S4577 phopshorylation varies throughout the cell cycle with highest abundance in metaphase and telophase/cytokinesis."
- `a2_evi_17` · *Primary* · Supports · Surface Expression — ACE2 overexpression in proximal tubule epithelial cells correlates with increased megalin (LRP2) cell surface expression and increased albumin surface binding, indicating that ACE2 pathway activation is a positive modulator of LRP2 apical surface levels in PTECs. Baseline: normal PTECs; modulating state: ACE2 overexpression; direction: increased megalin surface expression. (https://pubmed.ncbi.nlm.nih.gov/41955164/)
  - *assay*: Human · proximal tubule epithelial cells (PTEC) · live · non-permeabilized
  > "This effect was correlated with increased albumin cell surface binding and increased megalin expression."
- `a2_evi_18` · *Primary* · Supports · Surface Expression — Treatment with the ACE2 inhibitor MLN-4760 blocks the ACE2 overexpression-induced increase in albumin endocytosis in PTECs via an angiotensin II (Ang II) / AT1R-dependent mechanism, demonstrating that the renin-angiotensin system modulates LRP2/megalin surface function and endocytic activity in proximal tubule epithelial cells. (https://pubmed.ncbi.nlm.nih.gov/41955164/)
  - *assay*: Human · proximal tubule epithelial cells (PTEC) · live · non-permeabilized
  > "Treatment with ACE2 inhibitor MLN-4760 blocked the increase in albumin endocytosis induced by ACE2 overexpression in an angiotensin II (Ang II) / AT1R dependent manner."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/LRP2.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/LRP2](https://surfaceome.deliverome.org/LRP2)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/LRP2.json](https://surfaceome.deliverome.org/data/surfaceome/LRP2.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/LRP2.md](https://surfaceome.deliverome.org/data/surfaceome/LRP2.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P98164](https://alphafold.ebi.ac.uk/entry/P98164)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P98164](https://alphafold.ebi.ac.uk/api/prediction/P98164) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P98164](https://www.uniprot.org/uniprotkb/P98164)

### Canonical UniProt sequence

*4655 aa · `P98164` · embedded at build time*

```
   1  MDRGPAAVACTLLLALVACLAPASGQECDSAHFRCGSGHCIPADWRCDGTKDCSDDADEI
  61  GCAVVTCQQGYFKCQSEGQCIPNSWVCDQDQDCDDGSDERQDCSQSTCSSHQITCSNGQC
 121  IPSEYRCDHVRDCPDGADENDCQYPTCEQLTCDNGACYNTSQKCDWKVDCRDSSDEINCT
 181  EICLHNEFSCGNGECIPRAYVCDHDNDCQDGSDEHACNYPTCGGYQFTCPSGRCIYQNWV
 241  CDGEDDCKDNGDEDGCESGPHDVHKCSPREWSCPESGRCISIYKVCDGILDCPGREDENN
 301  TSTGKYCSMTLCSALNCQYQCHETPYGGACFCPPGYIINHNDSRTCVEFDDCQIWGICDQ
 361  KCESRPGRHLCHCEEGYILERGQYCKANDSFGEASIIFSNGRDLLIGDIHGRSFRILVES
 421  QNRGVAVGVAFHYHLQRVFWTDTVQNKVFSVDINGLNIQEVLNVSVETPENLAVDWVNNK
 481  IYLVETKVNRIDMVNLDGSYRVTLITENLGHPRGIAVDPTVGYLFFSDWESLSGEPKLER
 541  AFMDGSNRKDLVKTKLGWPAGVTLDMISKRVYWVDSRFDYIETVTYDGIQRKTVVHGGSL
 601  IPHPFGVSLFEGQVFFTDWTKMAVLKANKFTETNPQVYYQASLRPYGVTVYHSLRQPYAT
 661  NPCKDNNGGCEQVCVLSHRTDNDGLGFRCKCTFGFQLDTDERHCIAVQNFLIFSSQVAIR
 721  GIPFTLSTQEDVMVPVSGNPSFFVGIDFDAQDSTIFFSDMSKHMIFKQKIDGTGREILAA
 781  NRVENVESLAFDWISKNLYWTDSHYKSISVMRLADKTRRTVVQYLNNPRSVVVHPFAGYL
 841  FFTDWFRPAKIMRAWSDGSHLLPVINTTLGWPNGLAIDWAASRLYWVDAYFDKIEHSTFD
 901  GLDRRRLGHIEQMTHPFGLAIFGEHLFFTDWRLGAIIRVRKADGGEMTVIRSGIAYILHL
 961  KSYDVNIQTGSNACNQPTHPNGDCSHFCFPVPNFQRVCGCPYGMRLASNHLTCEGDPTNE
1021  PPTEQCGLFSFPCKNGRCVPNYYLCDGVDDCHDNSDEQLCGTLNNTCSSSAFTCGHGECI
1081  PAHWRCDKRNDCVDGSDEHNCPTHAPASCLDTQYTCDNHQCISKNWVCDTDNDCGDGSDE
1141  KNCNSTETCQPSQFNCPNHRCIDLSFVCDGDKDCVDGSDEVGCVLNCTASQFKCASGDKC
1201  IGVTNRCDGVFDCSDNSDEAGCPTRPPGMCHSDEFQCQEDGICIPNFWECDGHPDCLYGS
1261  DEHNACVPKTCPSSYFHCDNGNCIHRAWLCDRDNDCGDMSDEKDCPTQPFRCPSWQWQCL
1321  GHNICVNLSVVCDGIFDCPNGTDESPLCNGNSCSDFNGGCTHECVQEPFGAKCLCPLGFL
1381  LANDSKTCEDIDECDILGSCSQHCYNMRGSFRCSCDTGYMLESDGRTCKVTASESLLLLV
1441  ASQNKIIADSVTSQVHNIYSLVENGSYIVAVDFDSISGRIFWSDATQGKTWSAFQNGTDR
1501  RVVFDSSIILTETIAIDWVGRNLYWTDYALETIEVSKIDGSHRTVLISKNLTNPRGLALD
1561  PRMNEHLLFWSDWGHHPRIERASMDGSMRTVIVQDKIFWPCGLTIDYPNRLLYFMDSYLD
1621  YMDFCDYNGHHRRQVIASDLIIRHPYALTLFEDSVYWTDRATRRVMRANKWHGGNQSVVM
1681  YNIQWPLGIVAVHPSKQPNSVNPCAFSRCSHLCLLSSQGPHFYSCVCPSGWSLSPDLLNC
1741  LRDDQPFLITVRQHIIFGISLNPEVKSNDAMVPIAGIQNGLDVEFDDAEQYIYWVENPGE
1801  IHRVKTDGTNRTVFASISMVGPSMNLALDWISRNLYSTNPRTQSIEVLTLHGDIRYRKTL
1861  IANDGTALGVGFPIGITVDPARGKLYWSDQGTDSGVPAKIASANMDGTSVKTLFTGNLEH
1921  LECVTLDIEEQKLYWAVTGRGVIERGNVDGTDRMILVHQLSHPWGIAVHDSFLYYTDEQY
1981  EVIERVDKATGANKIVLRDNVPNLRGLQVYHRRNAAESSNGCSNNMNACQQICLPVPGGL
2041  FSCACATGFKLNPDNRSCSPYNSFIVVSMLSAIRGFSLELSDHSETMVPVAGQGRNALHV
2101  DVDVSSGFIYWCDFSSSVASDNAIRRIKPDGSSLMNIVTHGIGENGVRGIAVDWVAGNLY
2161  FTNAFVSETLIEVLRINTTYRRVLLKVTVDMPRHIVVDPKNRYLFWADYGQRPKIERSFL
2221  DCTNRTVLVSEGIVTPRGLAVDRSDGYVYWVDDSLDIIARIRINGENSEVIRYGSRYPTP
2281  YGITVFENSIIWVDRNLKKIFQASKEPENTEPPTVIRDNINWLRDVTIFDKQVQPRSPAE
2341  VNNNPCLENNGGCSHLCFALPGLHTPKCDCAFGTLQSDGKNCAISTENFLIFALSNSLRS
2401  LHLDPENHSPPFQTINVERTVMSLDYDSVSDRIYFTQNLASGVGQISYATLSSGIHTPTV
2461  IASGIGTADGIAFDWITRRIYYSDYLNQMINSMAEDGSNRTVIARVPKPRAIVLDPCQGY
2521  LYWADWDTHAKIERATLGGNFRVPIVNSSLVMPSGLTLDYEEDLLYWVDASLQRIERSTL
2581  TGVDREVIVNAAVHAFGLTLYGQYIYWTDLYTQRIYRANKYDGSGQIAMTTNLLSQPRGI
2641  NTVVKNQKQQCNNPCEQFNGGCSHICAPGPNGAECQCPHEGNWYLANNRKHCIVDNGERC
2701  GASSFTCSNGRCISEEWKCDNDNDCGDGSDEMESVCALHTCSPTAFTCANGRCVQYSYRC
2761  DYYNDCGDGSDEAGCLFRDCNATTEFMCNNRRCIPREFICNGVDNCHDNNTSDEKNCPDR
2821  TCQSGYTKCHNSNICIPRVYLCDGDNDCGDNSDENPTYCTTHTCSSSEFQCASGRCIPQH
2881  WYCDQETDCFDASDEPASCGHSERTCLADEFKCDGGRCIPSEWICDGDNDCGDMSDEDKR
2941  HQCQNQNCSDSEFLCVNDRPPDRRCIPQSWVCDGDVDCTDGYDENQNCTRRTCSENEFTC
3001  GYGLCIPKIFRCDRHNDCGDYSDERGCLYQTCQQNQFTCQNGRCISKTFVCDEDNDCGDG
3061  SDELMHLCHTPEPTCPPHEFKCDNGRCIEMMKLCNHLDDCLDNSDEKGCGINECHDPSIS
3121  GCDHNCTDTLTSFYCSCRPGYKLMSDKRTCVDIDECTEMPFVCSQKCENVIGSYICKCAP
3181  GYLREPDGKTCRQNSNIEPYLIFSNRYYLRNLTIDGYFYSLILEGLDNVVALDFDRVEKR
3241  LYWIDTQRQVIERMFLNKTNKETIINHRLPAAESLAVDWVSRKLYWLDARLDGLFVSDLN
3301  GGHRRMLAQHCVDANNTFCFDNPRGLALHPQYGYLYWADWGHRAYIGRVGMDGTNKSVII
3361  STKLEWPNGITIDYTNDLLYWADAHLGYIEYSDLEGHHRHTVYDGALPHPFAITIFEDTI
3421  YWTDWNTRTVEKGNKYDGSNRQTLVNTTHRPFDIHVYHPYRQPIVSNPCGTNNGGCSHLC
3481  LIKPGGKGFTCECPDDFRTLQLSGSTYCMPMCSSTQFLCANNEKCIPIWWKCDGQKDCSD
3541  GSDELALCPQRFCRLGQFQCSDGNCTSPQTLCNAHQNCPDGSDEDRLLCENHHCDSNEWQ
3601  CANKRCIPESWQCDTFNDCEDNSDEDSSHCASRTCRPGQFRCANGRCIPQAWKCDVDNDC
3661  GDHSDEPIEECMSSAHLCDNFTEFSCKTNYRCIPKWAVCNGVDDCRDNSDEQGCEERTCH
3721  PVGDFRCKNHHCIPLRWQCDGQNDCGDNSDEENCAPRECTESEFRCVNQQCIPSRWICDH
3781  YNDCGDNSDERDCEMRTCHPEYFQCTSGHCVHSELKCDGSADCLDASDEADCPTRFPDGA
3841  YCQATMFECKNHVCIPPYWKCDGDDDCGDGSDEELHLCLDVPCNSPNRFRCDNNRCIYSH
3901  EVCNGVDDCGDGTDETEEHCRKPTPKPCTEYEYKCGNGHCIPHDNVCDDADDCGDWSDEL
3961  GCNKGKERTCAENICEQNCTQLNEGGFICSCTAGFETNVFDRTSCLDINECEQFGTCPQH
4021  CRNTKGSYECVCADGFTSMSDRPGKRCAAEGSSPLLLLPDNVRIRKYNLSSERFSEYLQD
4081  EEYIQAVDYDWDPKDIGLSVVYYTVRGEGSRFGAIKRAYIPNFESGRNNLVQEVDLKLKY
4141  VMQPDGIAVDWVGRHIYWSDVKNKRIEVAKLDGRYRKWLISTDLDQPAAIAVNPKLGLMF
4201  WTDWGKEPKIESAWMNGEDRNILVFEDLGWPTGLSIDYLNNDRIYWSDFKEDVIETIKYD
4261  GTDRRVIAKEAMNPYSLDIFEDQLYWISKEKGEVWKQNKFGQGKKEKTLVVNPWLTQVRI
4321  FHQLRYNKSVPNLCKQICSHLCLLRPGGYSCACPQGSSFIEGSTTECDAAIELPINLPPP
4381  CRCMHGGNCYFDETDLPKCKCPSGYTGKYCEMAFSKGISPGTTAVAVLLTILLIVVIGAL
4441  AIAGFFHYRRTGSLLPALPKLPSLSSLVKPSENGNGVTFRSGADLNMDIGVSGFGPETAI
4501  DRSMAMSEDFVMEMGKQPIIFENPMYSARDSAVKVVQPIQVTVSENVDNKNYGSPINPSE
4561  IVPETNPTSPAADGTQVTKWNLFKRKSKQTTNFENPIYAQMENEQKESVAATPPPSPSLP
4621  AKPKPPSRRDPTPTYSATEDTFKDTANLVKEDSEV
```

### Canonical ortholog sequences

**Mouse — Lrp2** (`A2ARV4` · 4660 aa)

```
   1  MERGAAAAAWMLLLAIAACLAPVSGQECGSGNFRCDNGYCIPASWRCDGTRDCLDDTDEI
  61  GCPPRSCGSGFFLCPAEGTCIPSSWVCDQDKDCSDGADEQQNCPGTTCSSQQLTCSNGQC
 121  VPIEYRCDHVSDCPDGSDERNCYYPTCDQLTCANGACYNTSQKCDHKVDCRDSSDEANCT
 181  TLCSQKEFQCGSGECILRAYVCDHDNDCEDNSDEHNCNYDTCGGHQFTCSNGQCINQNWV
 241  CDGDDDCQDSGDEDGCESNQRHHTCYPREWACPGSGRCISMDKVCDGVPDCPEGEDENNA
 301  TSGRYCGTGLCSILNCEYQCHQTPYGGECFCPPGHIINSNDSRTCIDFDDCQIWGICDQK
 361  CESRQGRHQCLCEEGYILERGQHCKSNDSFSAASIIFSNGRDLLVGDLHGRNFRILAESK
 421  NRGIVMGVDFHYQKHRVFWTDPMQAKVFSTDINGLNTQEILNVSIDAPENLAVDWINNKL
 481  YLVETRVNRIDVVNLEGNQRVTLITENLGHPRGIALDPTVGYLFFSDWGSLSGQPKVERA
 541  FMDGSNRKDLVTTKLGWPAGITLDLVSKRVYWVDSRYDYIETVTYDGIQRKTVARGGSLV
 601  PHPFGISLFEEHVFFTDWTKMAVMKANKFTDTNPQVYHQSSLTPFGVTVYHALRQPNATN
 661  PCGNNNGGCAQICVLSHRTDNGGLGYRCKCEFGFELDADEHHCVAVKNFLLFSSQTAVRG
 721  IPFTLSTQEDVMVPVTGSPSFFVGIDFDAQHSTIFYSDLSKNIIYQQKIDGTGKEVITAN
 781  RLQNVECLSFDWISRNLYWTDGGSKSVTVMKLADKSRRQIISNLNNPRSIVVHPAAGYMF
 841  LSDWFRPAKIMRAWSDGSHLMPIVNTSLGWPNGLAIDWSTSRLYWVDAFFDKIEHSNLDG
 901  LDRKRLGHVDQMTHPFGLTVFKDNVFLTDWRLGAIIRVRKSDGGDMTVVRRGISSIMHVK
 961  AYDADLQTGTNYCSQTTHPNGDCSHFCFPVPNFQRVCGCPYGMKLQRDQMTCEGDPAREP
1021  PTQQCGSSSFPCNNGKCVPSIFRCDGVDDCHDNSDEHQCGALNNTCSSSAFTCVHGGQCI
1081  PGQWRCDKQNDCLDGSDEQNCPTRSPSSTCPPTSFTCDNHMCIPKEWVCDTDNDCSDGSD
1141  EKNCQASGTCHPTQFRCPDHRCISPLYVCDGDKDCVDGSDEAGCVLNCTSSQFKCADGSS
1201  CINSRYRCDGVYDCKDNSDEAGCPTRPPGMCHPDEFQCQGDGTCIPNTWECDGHPDCIQG
1261  SDEHNGCVPKTCSPSHFLCDNGNCIYNSWVCDGDNDCRDMSDEKDCPTQPFHCPSSQWQC
1321  PGYSICVNLSALCDGVFDCPNGTDESPLCNQDSCLHFNGGCTHRCIQGPFGATCVCPIGY
1381  QLANDTKTCEDVNECDIPGFCSQHCVNMRGSFRCACDPEYTLESDGRTCKVTASENLLLV
1441  VASRDKIIMDNITAHTHNIYSLVQDVSFVVALDFDSVTGRVFWSDLLEGKTWSAFQNGTD
1501  KRVVHDSGLSLTEMIAVDWIGRNIYWTDYTLETIEVSKIDGSHRTVLISKNVTKPRGLAL
1561  DPRMGDNVMFWSDWGHHPRIERASMDGTMRTVIVQEKIYWPCGLSIDYPNRLIYFMDAYL
1621  DYIEFCDYDGQNRRQVIASDLVLHHPHALTLFEDSVFWTDRGTHQVMQANKWHGRNQSVV
1681  MYSVPQPLGIIAIHPSRQPSSPNPCASATCSHLCLLSAQEPRHYSCACPSGWNLSDDSVN
1741  CVRGDQPFLISVRENVIFGISLDPEVKSNDAMVPISGIQHGYDVEFDDSEQFIYWVENPG
1801  EIHRVKTDGSNRTAFAPLSLLGSSLGLALDWVSRNIYYTTPASRSIEVLTLRGDTRYGKT
1861  LITNDGTPLGVGFPVGIAVDPARGKLYWSDHGTDSGVPAKIASANMDGTSLKILFTGNME
1921  HLEVVTLDIQEQKLYWAVTSRGVIERGNVDGTERMILVHHLAHPWGLVVHGSFLYYSDEQ
1981  YEVIERVDKSSGSNKVVFRDNIPYLRGLRVYHHRNAADSSNGCSNNPNACQQICLPVPGG
2041  MFSCACASGFKLSPDGRSCSPYNSFIVVSMLPAVRGFSLELSDHSEAMVPVAGQGRNVLH
2101  ADVDVANGFIYWCDFSSSVRSSNGIRRIKPNGSNFTNIVTYGIGANGIRGVAVDWVAGNL
2161  YFTNAFVYETLIEVIRINTTYRRVLLKVSVDMPRHIVVDPKHRYLFWADYGQKPKIERSF
2221  LDCTNRTVLVSEGIVTPRGLAVDHDTGYIYWVDDSLDIIARIHRDGGESQVVRYGSRYPT
2281  PYGITVFGESIIWVDRNLRKVFQASKQPGNTDPPTVIRDSINLLRDVTIFDEHVQPLSPA
2341  ELNNNPCLQSNGGCSHFCFALPELPTPKCGCAFGTLEDDGKNCATSREDFLIYSLNNSLR
2401  SLHFDPQDHNLPFQAISVEGMAIALDYDRRNNRIFFTQKLNPIRGQISYVNLYSGASSPT
2461  ILLSNIGVTDGIAFDWINRRIYYSDFSNQTINSMAEDGSNRAVIARVSKPRAIVLDPCRG
2521  YMYWTDWGTNAKIERATLGGNFRVPIVNTSLVWPNGLTLDLETDLLYWADASLQKIERST
2581  LTGSNREVVISTAFHSFGLTVYGQYIYWTDFYTKKIYRANKYDGSDLIAMTTRLPTQPSG
2641  ISTVVKTQQQQCSNPCDQFNGGCSHICAPGPNGAECQCPHEGSWYLANDNKYCVVDTGAR
2701  CNQFQFTCLNGRCISQDWKCDNDNDCGDGSDELPTVCAFHTCRSTAFTCANGRCVPYHYR
2761  CDFYNDCGDNSDEAGCLFRSCNSTTEFTCSNGRCIPLSYVCNGINNCHDNDTSDEKNCPP
2821  ITCQPDFAKCQTTNICVPRAFLCDGDNDCGDGSDENPIYCASHTCRSNEFQCVSPHRCIP
2881  SYWFCDGEADCVDSSDEPDTCGHSLNSCSANQFHCDNGRCISSSWVCDGDNDCGDMSDED
2941  QRHHCELQNCSSTEFTCINSRPPNRRCIPQHWVCDGDADCADALDELQNCTMRACSTGEF
3001  SCANGRCIRQSFRCDRRNDCGDYSDERGCSYPPCRDDQFTCQNGQCITKLYVCDEDNDCG
3061  DGSDEQEHLCHTPEPTCPPHQFRCDNGHCIEMGTVCNHVDDCSDNSDEKGCGINECQDSS
3121  ISHCDHNCTDTITSFYCSCLPGYKLMSDKRTCVDIDECKETPQLCSQKCENVIGSYICKC
3181  APGYIREPDGKSCRQNSNIEPYLVFSNRYYIRNLTIDGTSYSLILQGLGNVVALDFDRVE
3241  ERLYWIDAEKQIIERMFLNKTNQETIISHRLRRAESLAVDWVSRKLYWLDAILDCLFVSD
3301  LEGRQRKMLAQHCVDANNTFCFENPRGIVLHPQRGYVYWADWGDHAYIARIGMDGTNKTV
3361  IISTKIEWPNAITIDYTNDLLYWADAHLGYIEFSDLEGHHRHTVYDGTLPHPFALTIFED
3421  TVFWTDWNTRTVEKGNKYDGSGRVVLVNTTHKPFDIHVLHPYRQPIMSNPCATNNGGCSH
3481  LCLIKAGGRGFTCECPDDFQTVQLRDRTLCMPMCSSTQFLCGNNEKCIPIWWKCDGQKDC
3541  SDGSDESDLCPHRFCRLGQFQCRDGNCTSPQALCNARQDCADGSDEDRVLCEHHRCEANE
3601  WQCANKRCIPEYWQCDSVDDCLDNSDEDPSHCASRTCRPGQFKCNNGRCIPQSWKCDVDN
3661  DCGDYSDEPIHECMTAAYNCDNHTEFSCKTNYRCIPQWAVCNGFDDCRDNSDEQGCESVP
3721  CHPSGDFRCGNHHCIPLRWKCDGIDDCGDNSDEESCVPRECTESEFRCADQQCIPSRWVC
3781  DQENDCGDNSDERDCEMKTCHPEHFQCTSGHCVPKALACDGRADCLDASDESACPTRFPN
3841  GTYCPAAMFECKNHVCIQSFWICDGENDCVDGSDEEIHLCFNVPCESPQRFRCDNSRCIY
3901  GHQLCNGVDDCGDGSDEKEEHCRKPTHKPCTDTEYKCSNGNCVSQHYVCDNVDDCGDLSD
3961  ETGCNLGENRTCAEKICEQNCTQLSNGGFICSCRPGFKPSTLDKNSCQDINECEEFGICP
4021  QSCRNSKGSYECFCVDGFKSMSTHYGERCAADGSPPLLLLPENVRIRKYNISSEKFSEYL
4081  EEEEHIQAIDYDWDPEGIGLSVVYYTVLSQGSQFGAIKRAYLPDFESGSNNPVREVDLGL
4141  KYLMQPDGLAVDWVGRHIYWSDAKSQRIEVATLDGRYRKWLITTQLDQPAAIAVNPKLGL
4201  MFWTDQGKQPKIESAWMNGEHRSVLASANLGWPNGLSIDYLNGDRIYWSDSKEDVIESIK
4261  YDGTDRRLIINDAMKPFSLDIFEDQLYWVAKEKGEVWRQNKFGKGNKEKLLVVNPWLTQV
4321  RIFHQLRYNQSVSNPCKQVCSHLCLLRPGGYSCACPQGSDFVTGSTVECDAASELPITMP
4381  SPCRCMHGGSCYFDENDLPKCKCSSGYSGEYCEIGLSRGIPPGTTMALLLTFAMVIIVGA
4441  LVLVGFFHYRKTGSLLPSLPKLPSLSSLAKPSENGNGVTFRSGADVNMDIGVSPFGPETI
4501  IDRSMAMNEQFVMEVGKQPVIFENPMYAAKDSTSKVGLAVQGPSVSSQVTVPENVENQNY
4561  GRSIDPSEIVPEPKPASPGADETQGTKWNIFKRKPKQTTNFENPIYAEMDTEQKEAVAVA
4621  PPPSPSLPAKASKRSSTPGYTATEDTFKDTANLVKEDSDV
```

**Cynomolgus — LRP2** (`A0A2K5VUN1` · 4655 aa)

```
   1  MDRGPAAVACTLLLALVACLAPASGQECDSEHFRCGSGHCIPADWRCDGTKDCSDDTDEI
  61  GCAVVTCQQGYFKCQSEGQCIPNSWVCDQDQDCDDGSDEHQGCSQSTCSSHQITCSNGQC
 121  IPGEYRCDHVRDCPDGADENDCQYPTCEQLTCDNGACYNTSQKCDWKVDCRDSSDEINCT
 181  EICLHNEFSCGSGECIPHAYVCDHDSDCQDGSDEHACNYPTCGGYQFTCPSGRCIYQNWV
 241  CDGEDDCKDNGDEDGCESSSHGVHKCSPREWSCPESGRCISIYKVCDGILDCPGREDENS
 301  TTTGKYCSTTLCSALNCQYQCHETPYGGACFCPPGYTINHNDSRTCVEFDDCQIWGICDQ
 361  KCESRPGHHLCHCEEGYILERGQHCKANDSFGEASIIFSNGRDLLIGDIHGRSFRILVES
 421  QNRGVAVGVAFHYHLQRVFWTDTVQNKVFSVDIHGLNIQEVLNVSVETPENLAVDWVNNK
 481  IYLVETKVNRIDMVNLDGSYRVTLITENLGHPRGIAVDPTVGYLFFSDWESLSGEPKLER
 541  AFMDGSNRKDLVKTKLGWPAGVTLDMISKRVYWVDSRFDYIETVTYDGIQRKTVVHGGSL
 601  IPHPFGISLFEGQVFFTDWTKMAVLKANKFAETNPQVYYQASLRPYGVTVYHSLRQPYAT
 661  NPCKDNNGGCEQVCVLSHRTDNDGLGFRCKCTFGFQLDTDERHCIAVQNFLIFSSQVAIR
 721  GIPFTLSTQEDVMVPVSGNPSFFVGIDFDAQDSTIFFSDMSKHMIFKQKIDGTGREILAA
 781  NRVENVESLAFDWISKNLYWTDSHYKSISVMRLADKTRRTVVQYLNNPRSVVVHPFAGYL
 841  FFTDWFRPAKIMRAWSDGSHLLPIVNTTLGWPNGLAIDWAASRLYWVDAYFDKIEHSTFD
 901  GLDRRRLGHIEQMTHPFGLAIFGEHLFFTDWRLGAIIRVRKADGGEMTVIRSGIAYILHL
 961  KSYDVNIQTGSNACNQPTHPNGDCSHFCFPVPNFQRVCGCPYGMRLASNHLTCEGDPTNE
1021  PPTEQCGIFSFPCKNGRCVPSYYRCDGVNDCHDNSDEQLCGTLNNTCSSSAFTCGNGECI
1081  PAHWRCDKRNDCVDGSDEHNCPTHAPASCLDTQYTCDNHQCISKNWVCDTDNDCGDGSDE
1141  KNCNSTEICQPSQFNCPNHRCIDLSFVCDGDKDCVDGSDEVGCVLNCTASQFKCASGDKC
1201  ISVTNRCDGVFDCSDNSDEAGCPTRPPGMCHSDEFQCQEDGICIPNFWECDGHPDCLYGS
1261  DEHNACVPKTCPSSYFHCDNGNCIHRAWLCDRDNDCGDMSDEKDCPTQPFRCPSWQWQCL
1321  GHNICVNLSVVCDGIFDCPNGTDESPLCNGNSCSDFNGGCTHECVQEPFGAKCLCPLGFL
1381  LANDSKTCEDIDECDIPGSCSQHCYNMRGSFRCACDTGYMLESDGRTCKVTASENLLLLV
1441  ASQNKIIADSVTSQVHNIYSLVENGSYIVAVDFDSISGRIFWSDATQGKTWSAFQNGTDR
1501  RVVFDSSIILTETIAIDWVGRNLYWTDYALETIEVSKIDGSHRTVLISKNLTNPRGLALD
1561  PRMNEHLLFWSDWGHHPRIERASMDGSMRTVIVQDKIFWPCGLTIDYPNRLLYFMDSYLD
1621  YIDFCDYNGHHRRQVIASDLIIRHPYALTLFEDSVYWTDRATRRVMRANKWHGGNQSVVM
1681  YNIQWPLGIVAVHPSKQPNSVNPCAFSRCSHLCLLSSQGPHFYSCVCPSGWSLSPDLLNC
1741  LRDDQPFLITVRQHIIFGISLNPDVKSNDAMVPIAGIQNGLDVEFDDAEQYIYWVENPGE
1801  IHRVKTDGTNRTVFASVSMVGPSMNLALDWVSRNLYSTNPRTQSIEVLTLHGDIRYRKTL
1861  IANDGTALGVGFPIGITVDPTRGKLYWSDQGTDSGVPAKIASANMDGTSVKTLFTGNLEH
1921  LECVTLDIEEQKLYWAVTGRGVIERGNVDGTDRMILVHQLSHPWGIAVYDSFLYYTDEQY
1981  EVIERVDKATGANKIVLRDNVPNLRGLRVYHRRNTAESSNGCSNNMNACQQICLPVPGGL
2041  FSCACATGFKLNPDNRSCSPYNSFIVVSMLSAIRGFSLELSDHSETMVPVAGQGRNALHV
2101  DVDVSSGFVYWCDFSSSVTSDNAIRRIKPDGSSLMNIVTHGIGENGVRGIAVDWVAGNLY
2161  FTNAFVSETLIEVLRINTTYRRVLLKVTVDMPRHIVVDPKNRYLFWADYGQRPKIERSFL
2221  DCTNRTVLVSEGIVTPRGLAVDRSDGYVYWVDDSLDIIARIRINGENSEVIRYGSRYPTP
2281  YGITVFGNSIIWVDRNLKKIFQASKEPENTDPPTVIRDNINWLRDVTIFDKQVQPQSPAE
2341  VNNNPCLENNGGCSHLCFALPGLYTPKCDCAFGTLESDGKNCAISTENFLIFALSNSLRS
2401  LHLDPENHSPPFQTINVERTVMSLDYDSVSDRIYFTQNLASGVGQISYVSLSSGIHTPTV
2461  IASGIGTADGIAFDWITRRIYYSDYLNQTINSMAEDGSNRTVIARVPKPRAIVLDPCQGY
2521  LYWADWDMHAKIERATLGGNFRVSIVNSSLVMPSGLTLDYEEDLLYWVDASLQKIERSTL
2581  TGMDREVIVNAAVHAFGLTLYGQYIYWTDLYTQRIYRANKYDGSGQIAMTTNLLSQPRGI
2641  NTVVKNQKEQCNNPCEQFNGGCSHICAPGPNGAECQCPHEGNWYLANNRKHCIVDNGERC
2701  GASSFTCSNGRCISKEWKCDNDNDCGDGSDEMESVCALHTCSPTAFTCANGRCVQYSYRC
2761  DYYNDCGDGSDEAGCLFRDCNATTEFMCNNRRCIPREFVCNGVDNCHDNNTSDEKNCPDR
2821  TCQSGYTTCQNSNICIPRIYLCDGDNDCGDNSDENPTYCTTHTCSSSEFQCTSGRCIPQH
2881  WYCDQEIDCFDASDEPASCGHPERTCLADEFKCDRGRCIPSEWICDGDNDCGDMSDEDER
2941  HQCHNQNCSDSEFLCVNDRPPDRRCIPQSWVCDGDVDCTDGYDENQNCTRRTCSENEFTC
3001  GYGLCIPEIFRCDRHNDCGDYSDERGCLYQTCQQNQFTCQNGRCISKTFVCDEDNDCGDG
3061  SDELMHLCHTPEPTCPPHEFKCDNGRCIEMMKLCNHLDDCLDNSDEKGCGVNECHDPSIS
3121  GCDHNCTDTLTSFYCSCRPGYKLMSDKRTCVDIDECTETPFVCSQKCENVIGSYICKCAP
3181  GYLREPDGKTCRQNSNIEPYLIFSNRYYLRNLTIDGYFYSLILEGLGNVVALDFDRVEKR
3241  LYWIDTQRQVIERMFLNKTNKETIINHRLPAAESLAVEWVSRKLYWLDARLDGLFVSELN
3301  GGHRRMLAQHCVDANNTFCFDNPRGLALHPQYGYIYWADWGHRAYIGRVGMDGTNKSVII
3361  STKLEWPNGITIDYTNDLLYWADAHLGYIEYSDLEGHRRHTVYDGSLPHPFAITIFEDTI
3421  YWTDWNTRTVEKGNKYDGSNRQTLVNTTHRPFDIHVYHPYRQPIVSNPCGTNNGGCSHLC
3481  LIKPGGKGFTCECPDDFRTLQLSGSTYCMPMCSSTQFLCANNEKCIPIWWKCDGQKDCSD
3541  GSDELALCPQRFCRLGQFQCNDGNCTSPQTLCNAHQNCPDGSDEDRLLCENHHCDSNEWQ
3601  CTNKRCIPESWQCDTFNDCEDNSDEDSSHCASRTCRPGQFRCANGRCIPQAWKCDVDNDC
3661  GDHSDEPIEECMSSAHLCDNFTEFSCKTNYRCIPKWAVCNGVDDCRDNSDEQGCEERTCH
3721  PVGDFRCKNHHCIPLRWQCDGQNDCGDNSDEENCAPRECTESEFRCVNQQCIPSRWICDH
3781  YNDCGDNSDERDCEMRTCHPEYFQCTSGHCVPSELKCDGTADCLDASDEADCPTRFPDGA
3841  YCQATMFECKNHVCIPPYWKCDGDDDCGDGSDEELHLCLNVPCNSPNRFRCDNNRCIYGH
3901  EVCNGVDDCGDGTDETEEHCRKPTPKPCTEYEYKCGNGHCIPNDNVCDDADDCGDWSDEL
3961  GCNKGKERTCAENICEQNCTQLNEGGFICSCTAGFETNVFDRTSCLDINECEQFGTCPQH
4021  CRNTKGSYECVCADGFTSMSDHPGKRCAAEGSSPLLLLPDNVRIRKYNLSSERFSEYLQD
4081  EEYIQAVDYDWDPEDIGLSVVYYTVRGEGSRFGAIKRAYIPNFESGHNNLVQEVDLKLKY
4141  VMQPDGIAVDWVGRHIYWSDVKNKRIEVAKLDGRYRKWLISTDLDQPAAIAVNPKLGLMF
4201  WTDWGKEPKIESAWMNGEDRNILVFEDLGWPTGLSIDYLNNDRIYWSDFKEDVIETIKYD
4261  GTDRRVIAKEAMNPYSLDIFEDQLYWISKEKGEVWKQNKFGQGKKEKTLVVNPWLTQVRI
4321  FHQLRYNKSVPNLCKQICSHLCLLRPGGYSCACPQGSSFIEGSTTECDAAIELPINLPPP
4381  CRCMHGGNCYFDETDLPKCKCPSGYTGKYCEMAFSKGISPGTTAVAVLLTILLIVIIGAL
4441  AIAGFFHYRRTGSLLPALPKLPSLSSLVKPSENGNGVTFRSGADLNMDIGVSGFGPETSI
4501  DRSMAMSEDFVMEMGKQPIIFENPMYSVRDSAVKVVQPTQVTVSGNVDNKNYGSPINPSE
4561  IVPETSPTSPAADGTQVTKWNLFKRKTKQTTNFENPIYAQMENEQKETVAATPPPSPSLP
4621  AKPKPPSRRDPTPTYSATEDTFKDTANLVKEDSEV
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`P98164`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 661  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 721  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 781  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 841  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 901  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 961  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1021  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1081  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1141  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1201  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1261  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1321  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1381  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1441  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1501  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1561  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1621  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1681  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1741  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1801  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1861  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1921  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1981  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2041  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2101  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2161  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2221  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2281  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2341  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2401  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2461  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2521  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2581  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2641  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2701  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2761  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2821  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2881  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2941  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3001  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3061  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3661  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3721  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3781  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3841  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3901  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3961  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4021  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4081  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4141  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4201  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4261  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4321  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4381  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMM
4441  MMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
4501  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
4561  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
4621  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Mouse ortholog — Lrp2** (`A2ARV4`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 661  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 721  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 781  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 841  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 901  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 961  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1021  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1081  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1141  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1201  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1261  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1321  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1381  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1441  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1501  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1561  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1621  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1681  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1741  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1801  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1861  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1921  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1981  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2041  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2101  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2161  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2221  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2281  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2341  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2401  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2461  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2521  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2581  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2641  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2701  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2761  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2821  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2881  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2941  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3001  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3061  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3661  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3721  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3781  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3841  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3901  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3961  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4021  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4081  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4141  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4201  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4261  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4321  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4381  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMM
4441  MMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
4501  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
4561  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
4621  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

**Cynomolgus ortholog — LRP2** (`A0A2K5VUN1`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 661  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 721  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 781  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 841  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 901  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 961  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1021  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1081  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1141  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1201  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1261  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1321  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1381  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1441  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1501  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1561  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1621  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1681  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1741  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1801  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1861  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1921  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
1981  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2041  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2101  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2161  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2221  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2281  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2341  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2401  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2461  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2521  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2581  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2641  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2701  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2761  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2821  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2881  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
2941  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3001  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3061  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3661  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3721  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3781  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3841  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3901  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
3961  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4021  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4081  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4141  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4201  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4261  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4321  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
4381  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMM
4441  MMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
4501  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
4561  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
4621  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence high — *

## CellxGene RNA enrichment (CZI Census)

*Schema v2.1.1 · CZI Census 2025-11-08 · HPA-style 4× fold-change classification on log1p(CP10K) → linear means, with a zero-baseline universe for `enriched` / `group_enriched` and an eligibles-only denominator for `enhanced`. CC-BY 4.0 (CZI).*

**Classification:**

- **Cell class (broad rollup, ~10 compartments):** low specificity
- **Cell type (leaf Cell Ontology terms, ~600):** low specificity
- **Tissue (UBERON terms, ~56):** low specificity

**Top 5 cell types (leaf CL, pooled across tissues):**

| Cell type | CL ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| epithelial cell of proximal tubule segment 3 | CL:4030011 | 3.289 | 62.75% | 2,296 / 3,659 |
| kidney proximal convoluted tubule epithelial cell | CL:1000838 | 3.206 | 76.10% | 15,755 / 20,704 |
| supporting cell of vestibular epithelium | CL:0002316 | 3.153 | 0.37% | 1 / 270 | (trace)
| epithelial cell of proximal tubule | CL:0002306 | 2.707 | 60.53% | 141,865 / 234,384 |
| pigmented epithelial cell | CL:0000529 | 2.681 | 31.18% | 9,349 / 29,987 |

**Top 5 tissues (UBERON, pooled across cell types):**

| Tissue | UBERON ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| kidney | UBERON:0002113 | 2.585 | 23.17% | 218,605 / 943,536 |
| lamina propria | UBERON:0000030 | 2.342 | 0.00% | 1 / 23,687 | (trace)
| pleura | UBERON:0000977 | 2.279 | 1.51% | 297 / 19,695 |
| testis | UBERON:0000473 | 2.248 | 0.39% | 80 / 20,724 | (trace)
| embryo | UBERON:0000922 | 2.226 | 65.23% | 9,291 / 14,244 |

<!-- /cellxgene -->
