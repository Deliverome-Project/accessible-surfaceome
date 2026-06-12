# FN1 — Surface Accessibility Brief

*Schema v1.1.0 · generated 2026-05-31T15:21:51.367224Z · model `claude-sonnet-4-6`*

> FN1/fibronectin is a large secreted ECM glycoprotein with a well-documented surface-accessible pool in disease contexts: HCC, fibrotic intestine, cardiac failure, tumor stroma, and chondrogenic differentiation all show elevated surface/ECM-deposited FN1 by mass spectrometry and IHC. The dominant plasma fibronectin pool (hepatocyte-secreted, soluble) is a genuine decoy risk. Surface accessibility is high in tumor/fibrotic/diseased states but near-absent in normal liver, making this a contextual target best suited for disease-selective ECM- or stroma-directed strategies (e.g., EDB- or EDA-isoform antibodies). ECD is large, with the RGD-containing FN10 domain confirmed in crystal structure with integrin αVβ3.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:3778](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:3778) |
| UniProt | [P02751](https://www.uniprot.org/uniprotkb/P02751) |
| NCBI Gene | [2335](https://www.ncbi.nlm.nih.gov/gene/2335) |
| Ensembl | [ENSG00000115414](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000115414) |
| Subcategory | Other |
| Surface accessibility | High |
| Confidence | Moderate |
| Evidence grade | Direct, single method |
| Triage signal | Possibly Accessible |
| Headline risks | Secreted Form |

## 1. Executive summary

**Surface-accessible predominantly in diseased/tumor/fibrotic states — HCC, fibrotic intestine (Crohn's), heart failure, tumor stroma — where FN1 is markedly deposited in integrin-bound ECM and cell membranes; absent from normal liver membrane.**

FN1/fibronectin is a large secreted ECM glycoprotein with a well-documented surface-accessible pool in disease contexts: HCC, fibrotic intestine, cardiac failure, tumor stroma, and chondrogenic differentiation all show elevated surface/ECM-deposited FN1 by mass spectrometry and IHC. The dominant plasma fibronectin pool (hepatocyte-secreted, soluble) is a genuine decoy risk. Surface accessibility is high in tumor/fibrotic/diseased states but near-absent in normal liver, making this a contextual target best suited for disease-selective ECM- or stroma-directed strategies (e.g., EDB- or EDA-isoform antibodies). ECD is large, with the RGD-containing FN10 domain confirmed in crystal structure with integrin αVβ3.

**Family / classification** — HGNC gene group(s): Receptor ligands; Fibronectin type III domain containing · functional class: Miscellaneous.

**Triage first-pass reasoning** — FN1 encodes fibronectin, which exists in two major pools: (1) a soluble plasma/secreted dimeric form circulating in blood, and (2) a cell-surface and extracellular matrix multimeric form that is wash-resistantly deposited and bound to integrins and heparan sulfate proteoglycans on the outer leaflet of the plasma membrane. The cell-surface and matrix-associated forms are genuine surface-accessible proteins targeted by antibody programs (e.g., anti-ED-B fibronectin antibodies in ADC/radioligand contexts targeting the EDB splice isoform enriched in tumor neovasculature). However, the dominant circulating form is secreted and soluble, and the surface pool is particularly prominent in tumor stroma/angiogenesis contexts, making the call contextual rather than a stable constitutive surface protein. Cell-state-induced: EDB isoform is enriched in tumors/wound healing. Tissue-restricted: not restricted to a single lineage but overexpressed in specific contexts. Lysosomal exocytosis: not relevant. Dual localization: yes—secreted dominant pool plus a matrix/surface pool. Stable surface attachment: the ECM/integrin-bound fibronectin is wash-resistant, which fits stable_surface_attachment best.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=Moderate · subcategory=Other · ecd=Large |
| Classification | reason=Stable Surface Attachment · family=Miscellaneous · state-dependence=High · induction-trigger=Oncogenic |
| Expression | level=High · breadth=Broad · specificity=Mixed · low-endogenous=false · tumor-associated=true · orphan-receptor=false · OE-precedent=false |
| Risks | shed=false · secreted=true · co-receptor=None · masking=true · restricted-subdomain=false |
| Evidence | grade=Direct, single method · density=High · live-cell-surface=true · supporting(hi)=0 · contradicting(hi)=0 |
| Cross-species | mouse=92.2% · cyno=98.8% |
| Paralogs | max %ECD identity = 44.5% |
| Topology | TM=0 · N-term-ECF=true · C-term-ECF=true |

**Facet rationales**

- *Expression level*: FN1 protein is highly expressed in HCC tumor tissue (membranous and sinusoidal staining in ~53–91.5% of tumors) (a1_evi_09, a2_evi_03), fibrotic intestine (a2_evi_07, a2_evi_08), cardiac tissue under stress (a2_evi_05), and tumor stroma broadly (a2_evi_21). Plasma fibronectin is also constitutively high in blood (a2_evi_01).
- *Expression breadth*: FN1 is expressed across liver/blood (hepatocyte-secreted plasma form), intestinal stroma (fibrotic Crohn's), cardiac tissue, vascular tissue, tumor stroma across cancer types, and chondrogenic cells (a2_evi_01, a2_evi_07, a2_evi_04, a2_evi_11, a2_evi_21, a2_evi_19). Broad multi-tissue distribution, disease-enriched.
- *Surface specificity*: FN1 is primarily a secreted/ECM protein; plasma fibronectin is fully soluble (a2_evi_01). In tumor cells, surface IHC shows dual membranous + cytoplasmic signal (a2_evi_16); normal liver shows no membranous FN1 (a2_evi_02). Surface-capture MS confirms ECM/surface pool in chondrogenic (a1_evi_03) and cardiac tissue (a2_evi_23). Mixed surface/secreted/intracellular split.
- *Known ligand*: FN1 binds integrins (αVβ3, α5β1 via RGD domain confirmed by crystal structure PDB:4MMX) (a1_evi_15), as well as heparan sulfate proteoglycans, collagen, and fibrin. Multiple well-validated endogenous binding partners are documented.
- *Low endogenous expression*: Derived from expression_level='high' (not low/absent → not flagged). FN1 protein is highly expressed in HCC tumor tissue (membranous and sinusoidal staining in ~53–91.5% of tumors) (a1_evi_09, a2_evi_03), fibrotic intestine (a2_evi_07, a2_evi_08), cardiac tissue under stress (a2_evi_05), and tumor stroma broadly (a2_evi_21). Plasma fibronectin is also constitutively high in blood (a2_evi_01).
- *Overexpression surface localization*: No method observation pairs an overexpression/mixed expression system with a direct or supportive surface-accessibility readout.

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Direct, single method

The strongest direct surface evidence comes from a sialoglycoprotein-enrichment LC-MS/MS surfaceome study on live, non-permeabilized chondrogenic cells (a1_evi_03/04, moderate weight), which is a genuine surface-capture mass spectrometry approach. Supporting this are membranous IHC staining in HCC tumor tissue (a1_evi_09, moderate weight; permeabilized/fixed, so not nonperm-gold-standard), a crystal structure confirming ECD accessibility of FN10-RGD (a1_evi_15, moderate weight), and review/low-weight assertions for EV surface and PTEN-loss surfaceome. The absence of membranous staining in normal liver (a1_evi_10) represents cell-state/disease-dependent variation (normal vs tumor), not a logical contradiction. All direct surface evidence derives from a single primary method family (mass-spec surfaceome capture), so the grade is direct_single_method. The soluble plasma fibronectin pool is a noted caveat (secreted/shed form), but cell-surface/ECM-deposited FN1 is directly evidenced.

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Tangential | Moderate | Review noting dual soluble/ECM-insoluble pools; important context for secreted-form caveat, not a direct surface assay |
| a1_evi_02 | Supports Surface | Low | Review-level assertion of FN1 surface presence on EVs with functional consequence; no primary assay cited |
| a1_evi_03 | Supports Surface | Moderate | Sialoglycoprotein-enrichment LC-MS/MS surfaceome in live chondrogenic cells; direct surface-capture methodology |
| a1_evi_04 | Supports Surface | Moderate | Paired methods description for a1_evi_03; confirms live-cell, non-permeabilized surface enrichment protocol |
| a1_evi_05 | Tangential | Low | Generic methods description of live-cell surface capture; not linked to a specific FN1 detection result |
| a1_evi_06 | Tangential | Low | Sulfo-NHS-SS-biotin protocol detail; not linked to a specific FN1 surface detection result in the ledger |
| a1_evi_07 | Tangential | Low | Pulldown protocol detail; not linked to a specific FN1 detection result |
| a1_evi_08 | Tangential | Low | Cross-validation of trypsin shaving vs surface biotinylation overlap; general methodology, no FN1-specific call |
| a1_evi_09 | Supports Surface | Moderate | Membranous IHC staining in HCC tumor tissue (permeabilized/fixed); positive membranous signal in tumor context |
| a1_evi_10 | Tangential | Moderate | Absence of membranous staining in normal liver IHC — state/disease-dependent variation vs tumor, not a logical contradiction |
| a1_evi_11 | Supports Surface | Low | IHC listed as detection method for FN1 in stromal marker profiling; weak, no staining detail or nonperm specification |
| a1_evi_12 | Tangential | Moderate | Establishes FN1 as secreted ECM glycoprotein; topology-relevant context, not a direct surface assay |
| a1_evi_13 | Expression Only | Low | Elevated FN protein in OSCC/BC tumors vs normal; bulk protein/review assertion, no surface assay |
| a1_evi_15 | Supports Surface | Moderate | Crystal structure of FN10-RGD domain bound to integrin αVβ3 ectodomain confirms extracellular domain accessibility |
| a1_evi_16 | Supports Surface | Low | Secondary confirmation of PDB:4MMX structure; corroborates a1_evi_15 but same source |
| a1_evi_17 | Supports Surface | Low | FN1 detected in surfaceome/secretome MS in PTEN-loss context; ambiguous surface vs secreted partition |

### Immunohistochemistry (2 methods)

#### IHC Membranous — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Permeabilized · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human hepatocellular carcinoma / liver tumor tissue: negative membranous staining in 47.0% of tumor samples (n=255), implying positive membranous staining in ~53% of tumor tissue | Primary Human Tissue | Moderate | 1 |
| Human nonneoplastic liver tissue: strong cytoplasmic/sinusoidal or moderate-to-strong membranous staining not identified; membranous FN1 absent in normal liver | Primary Human Tissue | Absent | 1 |

#### IHC Membranous — Supports Surface Localization · Plasma Membrane Localized

*Permeabilization: Permeabilized · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human stromal tissue (unspecified), FN1/fibronectin detected by IHC as stromal marker | Primary Human Tissue | Moderate | 1 |

### Surface mass spec (3 methods)

#### Cell Surface Capture — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human chondrogenic micromass culture (differentiating chondrogenic cells, days 1–15), sialoglycoprotein enrichment via aminooxy-biotin conjugation + LC-MS/MS, n=3 biological replicates | Primary Human Cell | Moderate | 1 |

#### Cell Surface Capture — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Extracellular vesicles (EVs): FN1 identified as surface-associated EV protein via CSPA/SURFY surfaceome annotation mapped onto global EV protein profiles | Unknown | Moderate | 1 |

#### Cell Surface Capture — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Live Cell · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Human cancer cells with PTEN loss: FN1 identified as part of cellular surfaceome/secretome analysis; dual surface and secreted character noted | Unknown | Moderate | 1 |

### Surface biotinylation (2 methods)

#### Surface Biotinylation — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

#### Surface Biotinylation — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

### Other (1 method)

#### Whole Cell Proteomics — Weak Or Ambiguous · Secreted Or Shed

*Permeabilization: Unknown · expression: Endogenous*

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| FN1 soluble form in liver and blood (secreted by hepatocytes); insoluble ECM-deposited form from endothelial cells and fibroblasts; review-level assertion of dual secreted/ECM-associated character | Primary Human Tissue | High | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| OSCC and breast cancer tumor tissue vs normal counterparts — elevated FN protein levels | Primary Human Tissue | Bulk Protein | High | 1 |
| Stromal marker profiling — FN1 detected by scRNA-seq in stromal cells | Unknown | Single Cell RNA | Moderate | 1 |

**Contradicting evidence**

- *Alternative Localization* (severity Moderate): IHC of nonneoplastic liver tissue shows FN1 staining is predominantly cytoplasmic or sinusoidal rather than membranous, and moderate-to-strong membranous staining was not identified in normal liver at all. This indicates that surface/membranous FN1 presentation is a tumor-enriched phenomenon and is absent from normal hepatocytes, undermining the generalizability of FN1 surface accessibility across liver cell contexts.
  - Likely explanation: FN1 is a secreted extracellular matrix glycoprotein that can be retained intracellularly or deposited in the sinusoidal space in normal liver. Tumor cells may upregulate FN1 and present it at the cell surface via integrin binding or altered secretion, explaining the tumor-specific membranous pattern. The contradiction is tissue/disease-state specific rather than a fundamental barrier to surface targeting in tumor contexts.

## 4. Biological context

**Cell types** *(orthogonal cell-type index)*

| Cell type | Ontology | Present in tissues | Species | Cites |
|---|---|---|---|---|
| hepatocytes | — | liver, blood | Human | 1 |
| endothelial cells | — | extracellular matrix | Human | 1 |
| fibroblasts | — | extracellular matrix, intestine | Human | 2 |
| cardiomyocytes | — | heart, left ventricular myocardium | Human | 3 |
| intestinal fibroblasts | — | intestine | Mouse | 1 |
| vascular smooth muscle cells | — | arteriovenous fistula (vascular) | Human | 1 |
| tumor cells | — | tumor | Human | 1 |
| invasive carcinoma cells | — | tumor (invasive carcinoma) | Human | 1 |
| chondrogenic progenitor cells | — | — | Other | 2 |
| cancer-associated fibroblasts | — | tumor stroma | Human | 1 |

**Cell states**

- *fibrotic* — FN1 is the only ECM protein consistently and significantly enriched in fibrotic vs. normal intestinal tissue (ileum and colon) in Crohn's disease; fibroblast-derived FN1 is the principal structural scaffold of the fibrotic ECM. *(cites: a2_evi_07, a2_evi_08, a2_evi_09, a2_evi_10, a2_evi_15)*
- *hypoxic* — FN1 protein is significantly upregulated in cardiomyocytes under hypoxic/asphyxial stress, with expression graded by severity of oxygen deprivation across asphyxia subtypes. *(cites: a2_evi_04, a2_evi_05, a2_evi_06)*
- *tumor* — FN1 is markedly upregulated in HCC tumor tissue (cytoplasmic, sinusoidal, and membranous compartments) relative to normal liver, and shows membranous/surface staining in various carcinoma and tumor stromal contexts. *(cites: a2_evi_03, a2_evi_16, a2_evi_17, a2_evi_21)*
- *vascular disease* — EDA-containing FN1 isoform is specifically upregulated (isoform switch) in aneurysmal arteriovenous fistula tissue vs. non-aneurysmal AVF, and FN1 is broadly elevated in vascular pathologies including atherosclerosis. *(cites: a2_evi_11, a2_evi_12, a2_evi_13, a2_evi_22)*
- *synthetic VSMC phenotype* — EDA-FN isoform drives vascular smooth muscle cell phenotypic switching from contractile to synthetic state via ITGB1/FAK/Src/RUNX2 signaling, modulating FN1-integrin interactions during this cell-state transition. *(cites: a2_evi_14)*
- *chondrogenic differentiation* — FN1 is detected at the cell surface of embryonic chondrogenic progenitor cells by cell-surface capture mass spectrometry across key stages of chondrogenic differentiation (days 1–15). *(cites: a2_evi_19, a2_evi_20)*
- *heart failure* — FN1 surface-accessible protein was directly profiled by µCSC mass spectrometry in failing vs. non-failing human heart tissue, establishing disease-state-dependent surface/ECM FN1 in cardiac failure. *(cites: a2_evi_23)*

**Primary subcellular compartment**: Secreted

**Dual localization**

- Extracellular Matrix · deposited by fibroblasts, endothelial cells, and stromal cells as insoluble matrix *(cites: a2_evi_01, a2_evi_07, a2_evi_08, a2_evi_09, a2_evi_10, a2_evi_15)*
- Plasma Membrane / Cell Surface · surface-accessible in tumor cells, chondrogenic cells, and cardiac tissue *(cites: a2_evi_16, a2_evi_17, a2_evi_19, a2_evi_20, a2_evi_23)*
- Cytoplasm · intracellular pool detected in tumor cells and cardiomyocytes under stress *(cites: a2_evi_16, a2_evi_05, a2_evi_06)*
- Extracellular Vesicle Surface · surface-associated on EVs in tumor/stromal microenvironment *(cites: a2_evi_18)*
- Blood Plasma (Soluble) · hepatocyte-derived soluble dimeric form circulating in blood *(cites: a2_evi_01)*

**Anatomical accessibility**

- blood / plasma (hepatocyte-secreted soluble fibronectin) — Blood Interstitial Facing · *Favorable*: Hepatocyte-derived plasma fibronectin circulates freely in blood as a soluble dimer, making it directly accessible to systemically delivered binders without any tissue barrier.
- extracellular matrix — endothelial cells and fibroblasts (interstitial/stromal compartment) — Matrix Facing · *Context Dependent*: Cell-associated insoluble FN1 secreted into the ECM by endothelial cells and fibroblasts is embedded in the interstitial matrix. Systemic binders must extravasate and penetrate stromal tissue to reach it; accessibility depends on vascular permeability and tissue architecture.
- fibrotic intestinal ECM (Crohn's disease, ileum and colon) — Matrix Facing · *Context Dependent*: FN1 is the dominant structural scaffold of fibrotic intestinal ECM deposited by fibroblasts. Systemic binders must cross the intestinal vasculature and penetrate the submucosal/stromal matrix; fibrotic thickening may further impede diffusion.
- tumor stroma / cancer-associated fibroblasts (various cancers) — Matrix Facing · *Context Dependent*: FN1 is an established ECM glycoprotein marker of tumor stroma and CAFs. Access by systemic binders requires extravasation into the tumor interstitium; the dense stromal matrix can restrict penetration, though tumor vasculature is often leaky.
- arteriovenous fistula vascular wall (EDA-FN isoform, aneurysmal disease) — Matrix Facing · *Context Dependent*: EDA-FN isoform is deposited in the vascular wall ECM of aneurysmal AVF. Systemic binders circulating in blood are adjacent to the luminal surface but must penetrate the vessel wall to reach the EDA-FN–rich matrix; access is context-dependent on wall permeability.
- failing human heart tissue (surface-accessible cardiac ECM) — Matrix Facing · *Context Dependent*: µCSC mass spectrometry directly detected surface-accessible FN1 in cardiac tissue. Myocardial ECM FN1 is reachable only after extravasation from coronary vasculature; accessibility depends on capillary permeability and degree of fibrotic remodeling in heart failure.

**Accessibility modulation**

- *Disease State Induced* · trigger: Oncogenic Transformation: Nonneoplastic human liver tissue → Hepatocellular carcinoma (HCC) tumor tissue — In normal liver, membranous and sinusoidal FN1 staining is virtually absent. In HCC, strong sinusoidal staining appears in ~91.5% of tumors and membranous FN1 positivity in ~53% of tumors, representing a marked increase in surface/ECM-accessible FN1. *(→ HCC Cells And Sinusoids Present Substantially Elevated Surface-Accessible And Matrix-Deposited FN1, Making HCC Tissue A High-Accessibility Target For FN1-Directed Binders Compared To Normal Liver.)* *(cites: a2_evi_02, a2_evi_03)*
- *Stress Induced* · trigger: Hypoxia: Human left ventricular myocardium from traumatic (non-hypoxic) controls → Human left ventricular myocardium from asphyxial (hypoxic) deaths — FN1-positive cardiomyocyte fraction increases significantly under hypoxic/asphyxial stress (mean 11.7±3.6% overall; up to 46% in smothering/strangulation) compared to lower baseline in traumatic controls. *(→ Hypoxia-Driven Upregulation Of FN1 Deposition In Cardiomyocytes Increases Extracellular/Surface-Accessible FN1 In Ischemic Cardiac Tissue, Creating A Stress-Dependent Accessible Pool For Binders Targeting The Myocardium.)* *(cites: a2_evi_04, a2_evi_05, a2_evi_06)*
- *Disease State Induced*: Normal human intestinal tissue (ileum and colon) → Fibrotic human intestinal tissue (Crohn's disease, ileum and colon) — FN1 is the only ECM protein consistently and significantly enriched in fibrotic versus normal intestine across decellularized and native specimens, confirmed by mass spectrometry and immunofluorescence, establishing it as the principal structural scaffold of fibrotic ECM. *(→ Fibrotic Intestinal Tissue Presents Markedly Elevated FN1 In The Extracellular Matrix Accessible Space, Making Fibrotic Crohn'S Disease Intestine A High-Accessibility Environment For FN1-Targeting Binders Relative To Normal Gut.)* *(cites: a2_evi_07, a2_evi_08, a2_evi_09, a2_evi_15)*
- *Post Translational Dependent*: Non-aneurysmal arteriovenous fistula (AVF) vascular tissue → Aneurysmal arteriovenous fistula (AVFA) vascular tissue — EDA exon inclusion in FN1 transcript increases significantly in AVFA (elevated EDA-FN isoform, decreased WT-FN), without a change in total FN1 levels. The EDA-containing isoform is specifically deposited in the ECM of aneurysmal vascular tissue. *(→ The EDA-FN Isoform Presents A Disease-State-Specific Accessible Epitope In Aneurysmal Vascular ECM. Binders Targeting The EDA Domain Would Have Selective Accessibility In AVFA Over Normal Or Non-Aneurysmal Vascular Tissue.)* *(cites: a2_evi_11, a2_evi_12, a2_evi_13, a2_evi_14)*
- *Dual Localization*: Non-cancerous epithelial or stromal cells (low/absent membranous FN1) → Tumor cells (cancer tissue) — In tumor cells, FN1 shows both high-contrast membranous surface staining and strong cytoplasmic staining simultaneously. Invasive carcinoma cells additionally show weak membranous labeling in a limited fraction of cells. *(→ FN1 Is Present At The Cell Surface (Membranous) In Tumor Cells, Making It Accessible To Extracellular Binders, But Co-Existing Cytoplasmic Pool Means Surface Fraction Is Partial. Accessibility Varies By Tumor Cell Type.)* *(cites: a2_evi_16, a2_evi_17)*
- *Developmental Stage*: Undifferentiated embryonic limb bud mesenchymal progenitor cells → Chondrogenic cells at key differentiation stages (days 1–15 of chondrogenic differentiation) — FN1 is detected as a key surfaceome protein on the cell surface of embryonic chick limb bud chondrogenic cells during differentiation, as captured by cell-surface capture mass spectrometry on live, unpermeabilized cells. *(→ FN1 Surface Accessibility Is Gated By Chondrogenic Differentiation Stage; Binders Would Find FN1 Accessible On The Surface Of Differentiating Chondrogenic Cells During Specific Developmental Windows.)* *(cites: a2_evi_19, a2_evi_20)*
- *Disease State Induced*: Non-failing human heart tissue → Failing human heart tissue — Surface-accessible FN1 protein was directly profiled by cell-surface capture (µCSC) mass spectrometry in failing versus non-failing human cardiac tissue, establishing that the extracellular/surface-accessible FN1 pool is measurably present and differs between these disease states. *(→ The Surface-Accessible FN1 Pool In Failing Heart Is Directly Quantifiable And Distinct From Non-Failing Heart, Suggesting That Heart Failure Creates A Disease-State-Specific Surface Accessibility Profile For FN1-Directed Cardiac Targeting.)* *(cites: a2_evi_23)*

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Moderate
- domain: Unknown
- rationale: IHC staining in HCC shows both sinusoidal and membranous distribution across tumor cells; surface-capture MS in chondrogenic cells and failing heart tissue did not indicate subdomain restriction. No apical/junctional/ciliary restriction has been reported. Distribution appears membrane-wide in surface-positive contexts.
- cites: a1_evi_09, a2_evi_03, a2_evi_16, a2_evi_23

**Co-receptor requirements**

- dependency: None
- evidence basis: Co Expression Only
- rationale: FN1 is a secreted ECM glycoprotein that binds integrins and heparan sulfate proteoglycans post-secretion; its ECM deposition and surface tethering occur after secretion and do not require a specific obligate co-receptor for surface presence. Integrin binding modulates adhesion function but is not required for FN1 to be present in the ECM/surface.
- cites: a1_evi_01, a1_evi_12, a1_evi_15

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl ensembl_compara_2026_05_12. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | P02751 | ref | ref | 0 | 2451 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-1 | P02751-1 | 100.0% | 100.0% | 0 | 2360 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-10 | P02751-10 | 100.0% | 100.0% | 0 | 2150 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-11 | P02751-11 | 100.0% | 100.0% | 0 | 2360 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-12 | P02751-12 | 100.0% | 99.9% | 0 | 1982 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-13 | P02751-13 | 100.0% | 100.0% | 0 | 2241 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-14 | P02751-14 | 100.0% | 100.0% | 0 | 2239 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-16 | P02751-16 | 99.5% | 99.5% | 0 | 631 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-17 | P02751-17 | 100.0% | 100.0% | 0 | 2304 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-2 | P02751-2 | 99.2% | 99.2% | 0 | 616 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-3 | P02751-3 | 100.0% | 100.0% | 0 | 2329 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-4 | P02751-4 | 100.0% | 100.0% | 0 | 2005 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-5 | P02751-5 | 100.0% | 100.0% | 0 | 2185 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-6 | P02751-6 | 100.0% | 100.0% | 0 | 2158 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-7 | P02751-7 | 100.0% | 100.0% | 0 | 2420 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-8 | P02751-8 | 100.0% | 100.0% | 0 | 2270 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Isoform | P02751-9 | P02751-9 | 100.0% | 100.0% | 0 | 2214 aa | 0 aa | 26 aa | Extracellular→Extracellular | — |
| Mouse ortholog | Fn1 | [P11276](https://www.uniprot.org/uniprotkb/P11276) | 92.0% | 92.2% | 0 | 2450 aa | — | — | — | high (≥85%) |
| Cynomolgus ortholog | FN1 | [A0A2K5V0I5](https://www.uniprot.org/uniprotkb/A0A2K5V0I5) | 98.8% | 98.8% | 0 | 2451 aa | — | — | — | high (≥85%) |
| Paralog | FGL1 | [Q08830](https://www.uniprot.org/uniprotkb/Q08830) | 3.2% | 44.5% | — | — | — | — | — | low-risk |
| Paralog | MFAP4 | [P55083](https://www.uniprot.org/uniprotkb/P55083) | 2.9% | 44.3% | — | — | — | — | — | low-risk |
| Paralog | FCN1 | [O00602](https://www.uniprot.org/uniprotkb/O00602) | 3.9% | 44.1% | — | — | — | — | — | low-risk |
| Paralog | FCN3 | [O75636](https://www.uniprot.org/uniprotkb/O75636) | 3.4% | 42.0% | — | — | — | — | — | low-risk |
| Paralog | ANGPTL4 | [Q9BY76](https://www.uniprot.org/uniprotkb/Q9BY76) | 3.4% | 42.0% | — | — | — | — | — | low-risk |
| Paralog | FCN2 | [Q15485](https://www.uniprot.org/uniprotkb/Q15485) | 3.9% | 41.0% | — | — | — | — | — | low-risk |
| Paralog | ANGPTL5 | [Q86XS5](https://www.uniprot.org/uniprotkb/Q86XS5) | 3.2% | 39.7% | — | — | — | — | — | low-risk |
| Paralog | ANGPTL6 | [Q8NI99](https://www.uniprot.org/uniprotkb/Q8NI99) | 4.2% | 39.5% | — | — | — | — | — | low-risk |
| Paralog | FGG | [P02679](https://www.uniprot.org/uniprotkb/P02679) | 3.5% | 39.1% | — | — | — | — | — | low-risk |
| Paralog | ANGPTL2 | [Q9UKU9](https://www.uniprot.org/uniprotkb/Q9UKU9) | 4.4% | 39.1% | — | — | — | — | — | low-risk |
| Paralog | ANGPTL7 | [O43827](https://www.uniprot.org/uniprotkb/O43827) | 3.5% | 39.1% | — | — | — | — | — | low-risk |
| Paralog | FGB | [P02675](https://www.uniprot.org/uniprotkb/P02675) | 4.6% | 38.8% | — | — | — | — | — | low-risk |
| Paralog | FGL2 | [Q14314](https://www.uniprot.org/uniprotkb/Q14314) | 4.3% | 38.5% | — | — | — | — | — | low-risk |
| Paralog | FIBCD1 | [Q8N539](https://www.uniprot.org/uniprotkb/Q8N539) | 4.3% | 38.0% | — | — | — | — | — | low-risk |
| Paralog | ANGPTL3 | [Q9Y5C1](https://www.uniprot.org/uniprotkb/Q9Y5C1) | 3.3% | 37.2% | — | — | — | — | — | low-risk |
| Paralog | ANGPTL1 | [O95841](https://www.uniprot.org/uniprotkb/O95841) | 4.6% | 37.0% | — | — | — | — | — | low-risk |
| Paralog | ANGPT4 | [Q9Y264](https://www.uniprot.org/uniprotkb/Q9Y264) | 4.2% | 36.2% | — | — | — | — | — | low-risk |
| Paralog | FNDC7 | [Q5VTL7](https://www.uniprot.org/uniprotkb/Q5VTL7) | 4.5% | 35.5% | — | — | — | — | — | low-risk |
| Paralog | ANGPT1 | [Q15389](https://www.uniprot.org/uniprotkb/Q15389) | 4.9% | 35.3% | — | — | — | — | — | low-risk |
| Paralog | FGA | [P02671](https://www.uniprot.org/uniprotkb/P02671) | 2.4% | 34.1% | — | — | — | — | — | low-risk |
| Paralog | ANGPT2 | [O15123](https://www.uniprot.org/uniprotkb/O15123) | 4.6% | 34.1% | — | — | — | — | — | low-risk |
| Paralog | TNR | [Q92752](https://www.uniprot.org/uniprotkb/Q92752) | 12.2% | 33.5% | — | — | — | — | — | low-risk |
| Paralog | TNN | [Q9UQP3](https://www.uniprot.org/uniprotkb/Q9UQP3) | 10.1% | 32.1% | — | — | — | — | — | low-risk |
| Paralog | TNXB | [P22105](https://www.uniprot.org/uniprotkb/P22105) | 13.2% | 30.4% | — | — | — | — | — | low-risk |
| Paralog | TNC | [P24821](https://www.uniprot.org/uniprotkb/P24821) | 14.5% | 25.9% | — | — | — | — | — | low-risk |

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
- cites: a1_evi_01, a2_evi_01

**ECD size assessment**

- ECD class: Large
- rationale: FN1 is a large multidomain ECM glycoprotein (~2386 residues, multiple fibronectin type I, II, III repeats). The RGD-containing FN10 domain alone is confirmed extracellular by crystal structure (PDB:4MMX). The full extracellular sequence is many hundreds of residues, comfortably in the 'large' class (>>200 residues exposed).
- cites: a1_evi_15, a1_evi_16

**Epitope masking**

- severity: Moderate
- evidence: Inferred
- mechanism: Glycan, Partner
- rationale: FN1 is an extensively glycosylated ECM glycoprotein, and its RGD-containing cell-binding domain is occupied by integrin αVβ3 when surface-bound (PDB:4MMX). Glycan masking of epitopes and integrin-occupancy of the RGD site are expected but not directly measured as antibody-blocking events in this ledger. Moderate severity is inferred from ECM glycoprotein biology.
- cites: a1_evi_15, a1_evi_12

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-P02751-F1](https://alphafold.ebi.ac.uk/entry/P02751) |
| AFDB version | v6 |
| ECD mean pLDDT | 70.0 |
| ECD disordered fraction | 38.5% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/P02751) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [P02751](https://alphafold.ebi.ac.uk/entry/P02751) | AlphaFold DB (AF-P02751-F1, v6) |
| Isoform P02751-1 | [P02751-1](https://alphafold.ebi.ac.uk/entry/P02751-1) | AlphaFold DB |
| Isoform P02751-10 | [P02751-10](https://alphafold.ebi.ac.uk/entry/P02751-10) | AlphaFold DB |
| Isoform P02751-11 | [P02751-11](https://alphafold.ebi.ac.uk/entry/P02751-11) | AlphaFold DB |
| Isoform P02751-12 | [P02751-12](https://alphafold.ebi.ac.uk/entry/P02751-12) | AlphaFold DB |
| Isoform P02751-13 | [P02751-13](https://alphafold.ebi.ac.uk/entry/P02751-13) | AlphaFold DB |
| Isoform P02751-14 | [P02751-14](https://alphafold.ebi.ac.uk/entry/P02751-14) | AlphaFold DB |
| Isoform P02751-16 | [P02751-16](https://alphafold.ebi.ac.uk/entry/P02751-16) | AlphaFold DB |
| Isoform P02751-17 | [P02751-17](https://alphafold.ebi.ac.uk/entry/P02751-17) | AlphaFold DB |
| Isoform P02751-2 | [P02751-2](https://alphafold.ebi.ac.uk/entry/P02751-2) | AlphaFold DB |
| Isoform P02751-3 | [P02751-3](https://alphafold.ebi.ac.uk/entry/P02751-3) | AlphaFold DB |
| Isoform P02751-4 | [P02751-4](https://alphafold.ebi.ac.uk/entry/P02751-4) | AlphaFold DB |
| Isoform P02751-5 | [P02751-5](https://alphafold.ebi.ac.uk/entry/P02751-5) | AlphaFold DB |
| Isoform P02751-6 | [P02751-6](https://alphafold.ebi.ac.uk/entry/P02751-6) | AlphaFold DB |
| Isoform P02751-7 | [P02751-7](https://alphafold.ebi.ac.uk/entry/P02751-7) | AlphaFold DB |
| Isoform P02751-8 | [P02751-8](https://alphafold.ebi.ac.uk/entry/P02751-8) | AlphaFold DB |
| Isoform P02751-9 | [P02751-9](https://alphafold.ebi.ac.uk/entry/P02751-9) | AlphaFold DB |
| Mouse ortholog (Fn1) | [P11276](https://alphafold.ebi.ac.uk/entry/P11276) | AlphaFold DB |
| Cynomolgus ortholog (FN1) | [A0A2K5V0I5](https://alphafold.ebi.ac.uk/entry/A0A2K5V0I5) | AlphaFold DB |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

40 entries · 26 primary · 14 secondary · 0 tertiary · 37 PMC OA.

- `a1_evi_01` · *Secondary* · Ambiguous · Surface Expression — FN1/fibronectin exists in two major pools: a soluble form found in liver and blood (secreted by hepatocytes), and an insoluble secreted form deposited by endothelial cells and fibroblasts into the extracellular matrix. This dual nature — dominant circulating soluble form plus a cell-surface/ECM-associated insoluble form — is the central shed/secreted-form caveat for FN1 surface accessibility. The soluble plasma form is shed/secreted and not cell-surface-anchored, while the ECM-deposited insoluble form is matrix-associated and surface-accessible. Downstream risk builder should populate risks.secreted_form / risks.shed_form noting the dominant circulating pool is soluble. ([PMC8303147](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8303147/))
  - *assay*: Human
  > "It is found in a soluble form in liver and blood [ 9 ] and secreted by different cells such as endothelial cells and fibroblasts in insoluble form [ 10 ]."
- `a1_evi_02` · *Secondary* · Supports · Surface Expression — EV (extracellular vesicle) surface FN1 is documented to facilitate cellular migration through tissues, constituting a direct claim that FN1 is surface-presented on extracellular vesicles with functional consequence. This is a review/discussion-level assertion of FN1 surface localization on EVs (not plasma membrane of intact cells), supporting surface accessibility of the protein in an EV context. ([PMC8612312](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8612312/))
  - *assay*: Human · non-permeabilized
  > "Several surface‐associated proteins have been documented to dictate EV function; whereas EV surface ANXA1 promotes microcalcification (Rogers et al., 2020 ), FN1 facilitates cellular migration through tissues (Sung et al., 2015 ), TGFB1 triggers fibroblast differentiation (Ringuette Goulet et al., 2018 ) and MIF establishes pre‐metastatic niche in the liver (Costa‐Silva et al., 2015 )."
- `a1_evi_03` · *Primary* · Supports · Surface Expression — FN1 was identified in a surfaceome dataset from chondrogenic cells (micromass culture) profiled by sialoglycoprotein enrichment combined with high-resolution LC-MS/MS mass spectrometry-based surfaceome proteomics. This confirms FN1 was detected as a surface-accessible protein in this chondrogenic differentiation context at the protein level via cell-surface-capture mass spectrometry. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
  - *assay*: Human · chondrogenic micromass culture · live · non-permeabilized
  > "Key proteins in this group include AKT1, FN1, SOX5, NOTCH1, and ITGB1."
- `a1_evi_04` · *Primary* · Supports · Methodological — Surfaceome proteomics methods detail: temporal proteomic profiling of chondrogenic cells using sialoglycoprotein enrichment via aminooxy-biotin conjugation combined with high-resolution LC-MS/MS. This is the paired methodological description for the FN1 surfaceome detection result. Method family: mass_spec_surfaceome; surface enrichment via sialoglycoprotein capture (aminooxy-biotin + LC-MS/MS); n=3 biological replicates; no permeabilization step. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
  - *assay*: Human · chondrogenic micromass culture · live · non-permeabilized
  > "Temporal proteomic profiling was conducted at days 1, 3, 6, 10, and 15 of micromass culture corresponding to key histodifferentiation stages [ 17 , 18 ], combining sialoglycoprotein enrichment via aminooxy-biotin conjugation with high-resolution LC-MS/MS on 3 biological replicates ( n = 3)."
- `a1_evi_05` · *Secondary* · Supports · Methodological — Cell surface protein capture from live cells was performed (method described with modifications from prior protocols). This is a methodological description of a live-cell surface-capture assay — relevant to surface accessibility measurement of proteins including FN1. ([PMC12650875](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12650875/))
  - *assay*: Unspecified · live · non-permeabilized
  > "Cell surface protein capture from live cells was performed as described in [ 34 , 35 ] with some modifications."
- `a1_evi_06` · *Primary* · Supports · Methodological — Surface biotinylation protocol detail: cells washed with ice-cold PBS (pH 8.0), incubated with 0.5 mg/mL sulfo-NHS-SS-biotin (Thermo Fisher Scientific) in PBS (pH 8.0) for 1 hour at 4°C under gentle agitation. Sulfo-NHS-SS reagent is membrane-impermeant, labeling only extracellular lysines of surface-accessible proteins. This is the paired methodological description for a surface biotinylation assay with cleavable crosslinker. ([PMC13043088](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13043088/))
  - *assay*: Unspecified · live · non-permeabilized
  > "Cells were washed twice with ice-cold PBS (pH 8.0) and incubated with 0.5 mg/mL sulfo-NHS-SS-biotin (Thermo Fisher Scientific) in PBS (pH 8.0) for 1 hour at 4°C under gentle agitation."
- `a1_evi_07` · *Primary* · Supports · Methodological — Surface biotinylation pulldown protocol detail: surface biotinylated, avidin-bound proteins incubated with denaturing buffer (0.5% SDS, 0.4 M DTT) for elution and analysis. This paired methodological description confirms streptavidin/avidin pulldown followed by WB detection for the surface biotinylation workflow. ([PMC13043088](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13043088/))
  - *assay*: Unspecified · live · non-permeabilized
  > "Briefly, surface biotinylated and avidin-bound proteins or total protein extracts were incubated with a denaturing buffer (0.5% SDS and 0.4 M DTT) in a total reaction volume of 20 μL and incubated at 37°C for 10 minutes."
- `a1_evi_08` · *Primary* · Supports · Methodological — Two orthogonal surface-proteomics methodologies — trypsin shaving and surface biotinylation — were applied and showed 72% overlap (116/160 proteins), cross-validating surface accessibility identifications. This methodological observation supports the validity of combined surface-capture approaches for proteins like FN1 identified in surfaceome datasets. ([PMC7990945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7990945/))
  - *assay*: Unspecified · live · non-permeabilized
  > "Two orthogonal methodologies, trypsin shaving and surface biotinylation that have been used previously by our group to determine surface accessibility showed a 72% overlap (116/160 proteins), in part cross validating these identifications."
- `a1_evi_09` · *Primary* · Supports · Surface Expression — IHC of tumor tissue (likely liver tumor given context) shows negative cytoplasmic or membranous staining in only 54.5% and 47.0% of tumor tissue respectively, with positive membranous staining in a substantial proportion of tumor cells. This quantitative IHC analysis demonstrates FN1 protein is detectable at the cell membrane (membranous staining) in hepatocellular carcinoma or liver tumor tissue by IHC. ([PMC11907257](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11907257/))
  - *assay*: Human · fixed · permeabilized
  > "On the other hand, negative cytoplasmic or membranous staining was observed in a much smaller proportion of tumor tissue (n=296, 54.5% and n=255, 47.0%, respectively), with only 8.5% of tumors showing negative sinusoidal staining (n=46)."
- `a1_evi_10` · *Primary* · Refutes · Contradictory — IHC of nonneoplastic liver tissue shows FN1 staining is predominantly cytoplasmic or sinusoidal (not membranous) in normal liver; strong cytoplasmic/sinusoidal staining and moderate-to-strong membranous staining were not identified in nonneoplastic tissue. This constitutes a contradictory finding relative to tumor membranous positivity: normal liver lacks surface/membranous FN1 by IHC, indicating tumor-enriched surface presentation. ([PMC11907257](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11907257/))
  - *assay*: Human · fixed · permeabilized
  > "In nonneoplastic livers, moderate cytoplasmic or sinusoidal staining was rarely observed (n=3, 0.6% and n=4, 0.7%, respectively), while strong cytoplasmic/sinusoidal staining or moderate-to-strong membranous staining were not identified."
- `a1_evi_11` · *Secondary* · Supports · Surface Expression — FN1 (fibronectin, ECM glycoprotein) is detected by IHC and scRNA-seq in the context of stromal marker profiling, per a tabulated methods reference. This indicates IHC has been used to detect FN1 protein in tissue sections, supporting surface/tissue-level detection, while scRNA-seq provides RNA-level co-expression context. IHC is load-bearing for surface expression; scRNA-seq is non-surface-method RNA observation. ([PMC13005641](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13005641/))
  - *assay*: Human · fixed · permeabilized
  > "flow cytometry, scRNA-seq, mRNA sequencing [ 9 ] Transmembrane receptor PDGFRα/β Platelet-derived growth factor receptor IHC, flow cytometry, scRNA-seq [ 14 ] ECM glycoprotein Fibronectin 1(FN1) Fibronectin IHC, scRNA-seq [ 9 ] SPARC Secreted protein, acidic and rich in cysteine scRNA-seq, mRNA sequencing [ 27 ] THBS2 Platelet-derived growth factor receptor 2 mRNA sequencing [ 27 ] Cytoskeletal protein α-SMA α-smooth muscle actin IHC [ 9 ] Vimentin (VIM) Type III intermediate filament protein Immunofluorescence"
- `a1_evi_12` · *Secondary* · Supports · Topology — FN1 gene encodes an extracellular matrix glycoprotein, fibronectin (FN), identified as a common EMT gene across oral squamous cell carcinoma (OSCC) and breast cancer (BC). This establishes FN1's identity as an ECM glycoprotein in cancer contexts — topology-relevant (secreted ECM protein, no TM helix). ([PMC12897945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12897945/))
  - *assay*: Human
  > "Notably, the <i>FN1</i> gene coding for the extracellular matrix glycoprotein fibronectin (FN) emerged as the EMT gene common to either tumor types."
- `a1_evi_13` · *Secondary* · Ambiguous · Tissue Expression — FN protein levels were higher in OSCC and breast cancer tissues than in their normal counterparts, as assessed at the protein level in tumor tissue (method not specified in abstract — likely IHC or western blot of tissue lysate). This is a non-surface whole-tissue protein expression observation that qualifies but does not directly demonstrate surface accessibility. ([PMC12897945](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12897945/))
  - *assay*: Human
  > "In confirmation of this, FN protein levels were higher in OSCC and BC tissues than in their normal counterparts."
- `a1_evi_14` · *Secondary* · Supports · Methodological — EV surfaceome mapping was performed using experimentally verified cell-surface proteins from the Cell Surface Protein Atlas (CSPA) and the SURFY surfaceome predictor, combined with global EV protein profiles. This methodological approach establishes that FN1, which is present in the CSPA database, was identified as a surface protein via an orthogonal database-anchored surfaceome annotation approach applied to EVs. ([PMC8612312](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8612312/))
  - *assay*: Unspecified · live · non-permeabilized
  > "We mapped experimentally verified cell‐surface proteins (CSPA) (Bausch‐Fluck et al., 2015 ) and surfaceome proteins based on cell surfaceome predictor SURFY (Bausch‐Fluck et al., 2018 ) onto global EV protein profiles."
- `a1_evi_15` · *Primary* · Supports · Topology — Crystal structure of integrin αVβ3 ectodomain in complex with the FN type III 10th domain (FN10, the RGD-containing cell-binding domain of fibronectin) is available at PDB: 4MMX. This structure directly defines the extracellular domain interaction interface of FN1 with its integrin receptor, supporting the ECD accessibility of the fibronectin RGD-containing domain on the cell surface. ([PMC12609551](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12609551/))
  - *assay*: Human
  > "The crystal structure of the integrin ectodomain αV/β3 heterodimer in complex with FN10 (PDB: 4MMX) ( Figure 1 c), along with complexes involving other ectodomains ( Figure 1 d–f), exhibits a high degree of conservation at the interaction interfaces."
- `a1_evi_16` · *Secondary* · Supports · Topology — Crystal structure for integrin αVβ3 ectodomain bound to FN10 (PDB: 4MMX) was identified by sequence blasting, confirming structural data availability for the fibronectin cell-binding domain in complex with its integrin receptor. This methodological detail confirms the PDB entry for the FN1 ECD-integrin interaction structure. ([PMC12609551](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12609551/))
  - *assay*: Human
  > "Sequence blasting indicated that one crystal structure is available for integrin αVβ3 ectodomain bound to FN10 (ID: 4MMX) [ 35 ]."
- `a1_evi_17` · *Secondary* · Ambiguous · Surface Expression — Loss of PTEN produces abundance changes on the cellular surfaceome and secreted proteomes of affected tissues, partially detectable in serum. FN1 was identified as part of surfaceome/secretome analysis in this PTEN-loss context, supporting its dual membrane-surface and secreted character in cancer cell contexts. ([PMC9044739](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9044739/))
  - *assay*: Human · live · non-permeabilized
  > "It was shown in the past that the loss of PTEN produces abundance changes on the cellular surfaceome and secreted proteomes of the affected tissues and that these abundance changes are also partially detectable in serum [ 8 , 16 ]."
- `a2_evi_01` · *Secondary* · Supports · Tissue Expression — FN1 protein is present in a soluble (dimeric) form in liver and blood, and is secreted in insoluble form by endothelial cells and fibroblasts into the extracellular matrix. This establishes the two canonical tissue/cell-type pools: hepatocyte-derived plasma fibronectin (liver/blood) and cell-associated fibronectin from stromal/endothelial sources. ([PMC8303147](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8303147/))
  - *assay*: Human · hepatocytes, endothelial cells, fibroblasts
  > "It is found in a soluble form in liver and blood [ 9 ] and secreted by different cells such as endothelial cells and fibroblasts in insoluble form [ 10 ]."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — In nonneoplastic (normal) liver tissue, FN1 protein staining is largely absent: strong cytoplasmic/sinusoidal or moderate-to-strong membranous staining were not observed; only rare weak cytoplasmic or sinusoidal staining was seen (0.6–0.7% of cases). This indicates very low FN1 protein deposition in the parenchyma and membranes of normal liver. ([PMC11907257](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11907257/))
  - *assay*: Human · nonneoplastic liver tissue · fixed · permeabilized
  > "In nonneoplastic livers, moderate cytoplasmic or sinusoidal staining was rarely observed (n=3, 0.6% and n=4, 0.7%, respectively), while strong cytoplasmic/sinusoidal staining or moderate-to-strong membranous staining were not identified."
- `a2_evi_03` · *Primary* · Supports · Tissue Expression — In hepatocellular carcinoma (HCC) tumor tissue, FN1 protein staining is markedly upregulated relative to normal liver: only 54.5% of tumors showed negative cytoplasmic staining and 47.0% negative membranous staining (vs. near-universal negativity in normal liver). Sinusoidal staining was negative in only 8.5% of tumors, indicating widespread sinusoidal and membranous FN1 deposition in HCC. Disease-state-induced upregulation across cytoplasmic, sinusoidal, and membranous compartments in tumor tissue. ([PMC11907257](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11907257/))
  - *assay*: Human · hepatocellular carcinoma tumor tissue · fixed · permeabilized
  > "On the other hand, negative cytoplasmic or membranous staining was observed in a much smaller proportion of tumor tissue (n=296, 54.5% and n=255, 47.0%, respectively), with only 8.5% of tumors showing negative sinusoidal staining (n=46)."
- `a2_evi_04` · *Primary* · Supports · Tissue Expression — FN1 protein expression was investigated by IHC in left ventricular myocardium (cardiac tissue) from human autopsies, comparing asphyxial deaths to traumatic controls. This establishes cardiac myocardium as a tissue of interest for FN1 expression under hypoxic/stress conditions. (https://pubmed.ncbi.nlm.nih.gov/41785781/)
  - *assay*: Human · left ventricular myocardium (cardiomyocytes) · fixed · permeabilized
  > "We investigated its expression in cardiac tissue from asphyxial deaths compared with traumatic controls.<h4>Methods</h4>We retrospectively collected formalin-fixed, paraffin-embedded left ventricular myocardium from autopsies in Palermo and Genoa (2021-2025)."
- `a2_evi_05` · *Primary* · Supports · Tissue Expression — FN1 protein expression is significantly higher in cardiomyocytes from asphyxial deaths compared to traumatic controls (mean 11.7 ± 3.6% FN-positive cardiomyocytes in asphyxia group vs. lower baseline in controls), as quantified by IHC with a monoclonal antibody and dedicated image-analysis software. This represents disease-state-induced upregulation of FN1 in cardiac tissue under hypoxic stress. (https://pubmed.ncbi.nlm.nih.gov/41785781/)
  - *assay*: Human · cardiomyocytes, left ventricular myocardium · fixed · permeabilized
  > "We performed FN immunohistochemistry (IHC) with a monoclonal antibody and quantified FN-positive cardiomyocytes using dedicated image-analysis software.<h4>Results</h4>We found significantly higher FN expression in all asphyxial deaths compared with controls (mean 11.7 ± 3.6%)."
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — FN1 protein upregulation in cardiac myocardium under hypoxia is graded by asphyxia subtype: smothering (46.1 ± 7.2%) and strangulation (45.0 ± 8%) showed highest FN1-positive cardiomyocyte fractions, followed by chemical asphyxia (35.1 ± 9.8%), hanging (27.8 ± 6.6%), and drowning (21.4 ± 5.9%). Demonstrates FN1 is a hypoxia-sensitive ECM component in cardiac tissue with graded stress-dependent expression. (https://pubmed.ncbi.nlm.nih.gov/41785781/)
  - *assay*: Human · cardiomyocytes, left ventricular myocardium · fixed · permeabilized
  > "The highest intensities were observed in smothering (46.1 ± 7.2%) and strangulation (45.0 ± 8%), followed by chemical asphyxia (35.1 ± 9.8%), hanging (27.8 ± 6.6%), and drowning (21.4 ± 5.9%)."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — Matrisomic analysis of human ileal and colonic intestinal tissue (both decellularized and native) identified fibronectin (FN1) as the only ECM component consistently elevated in fibrotic versus normal gut tissue across all conditions tested, including clinical (human) and animal models. FN1 is a disease-state marker specifically enriched in fibrotic intestine. ([PMC13067841](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13067841/))
  - *assay*: Human · intestinal tissue (ileum and colon)
  > "In this study, we first performed matrisomic analysis on human (ileal/colonic) and animal (decellularized/native) intestines, identifying fibronectin as the only ECM component consistently elevated in fibrotic versus normal gut tissues across all conditions."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — Proteomic analysis demonstrated that fibronectin (FN1) was the only protein significantly enriched in fibrotic ileum and colon compared to normal tissue. This positions FN1 as a tissue-specific disease-state marker in fibrotic intestinal ECM. ([PMC13067841](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13067841/))
  - *assay*: Human · fibrotic ileum and colon tissue
  > "Results demonstrated that fibronectin was the only protein significantly enriched in fibrotic ileum and colon (Figure 1A,B )."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — Immunofluorescence co-staining identified fibronectin (FN1) as the principal structural scaffold of the fibrotic intestinal ECM in human Crohn's disease tissue. FN1 is the dominant ECM protein in the fibrotic intestinal microenvironment, consistent with a high-abundance, accessible matrix structure in diseased intestine. ([PMC13067841](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13067841/))
  - *assay*: Human · fibrotic intestinal ECM · fixed · permeabilized
  > "Subsequently, immunofluorescence co-staining identified fibronectin as the principal structural scaffold of the fibrotic intestinal ECM."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — Fibroblast-specific Fn1 genetic ablation ameliorated intestinal fibrosis in mouse models, demonstrating that fibroblast-derived FN1 is a key cell-type-specific driver of fibrotic ECM remodeling. Intestinal fibroblasts are the primary source of pathological fibronectin deposition in fibrotic intestine. ([PMC13067841](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13067841/))
  - *assay*: Mouse · intestinal fibroblasts
  > "Furthermore, fibroblast-specific Fn1 ablation ameliorates intestinal fibrosis and transforms refractory fibrotic thickening into reversible inflammatory thickening in both innate and adaptive immune-driven models."
- `a2_evi_11` · *Primary* · Supports · Tissue Expression — RNA-seq analysis of arteriovenous fistula (AVF) tissue detected a significant increase in EDA-containing FN1 transcript isoform in aneurysmal AVF (AVFA) compared to non-aneurysmal AVF (FDR < 0.05, |ΔPSI| > 0.1). This establishes disease-state-dependent alternative splicing of FN1 in vascular tissue, with EDA isoform specifically upregulated in the aneurysmal/diseased state. ([PMC12833886](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12833886/))
  - *assay*: Human · arteriovenous fistula vascular tissue
  > "After filtering ASEs based on the criteria (FDR < 0.05, |ΔPSI| > 0.1), we found the significant increase in the transcript isoform of EDA-FN in AVFA ( Figure 1A-B )."
- `a2_evi_12` · *Primary* · Supports · Tissue Expression — qPCR quantification confirmed increased EDA-FN isoform and decreased wild-type FN (WT-FN) in aneurysmal AVF (AVFA) tissue, with increased EDA inclusion ratio. This corroborates RNA-seq findings: disease-state-dependent isoform switch toward EDA-FN in vascular smooth muscle cell-containing arteriovenous fistula tissue under aneurysmal conditions. ([PMC12833886](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12833886/))
  - *assay*: Human · arteriovenous fistula vascular tissue
  > "For further quantitative analysis, we designed forward primers spanning the 32/33 or 32/34 sequences, with reverse primers located in exon 34, allowing specific amplification of either WT-FN or EDA-FN cDNA. qPCR results showed an increase in EDA-FN absolute quantification and a decrease in WT-FN in AVFA, with a concomitant rise in the inclusion ratio of EDA ( Figure 1D )."
- `a2_evi_13` · *Primary* · Supports · Tissue Expression — In clinical vascular tissue from AVF and AVFA specimens, increased EDA exon inclusion in FN1 (but not total FN levels) promoted aneurysmal formation and correlated with vessel diameters. This demonstrates that EDA-FN isoform deposition is specifically elevated in diseased vascular tissue and functionally drives vascular remodeling in the arteriovenous fistula context. ([PMC12833886](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12833886/))
  - *assay*: Human · arteriovenous fistula clinical tissue
  > "In clinical tissues, we found that increased inclusion of EDA in FN but not total FN promoted AVFA and that EDA-FN levels correlated with vessel diameters of AVF or AVFA, confirming the important role of FN variable splicing in AVFA formation Mechanistically, SRSF5 promotes EDA inclusion, increasing EDA-FN production."
- `a2_evi_14` · *Primary* · Supports · Tissue Expression — Increased EDA exon inclusion in FN1 triggers vascular smooth muscle cell (VSMC) phenotypic switching from contractile to synthetic state via the ITGB1/FAK/Src/RUNX2 signaling pathway in arteriovenous fistula tissue. Cell-state transition (contractile→synthetic VSMC) is driven by EDA-FN isoform, establishing cell-state-induced modulation of FN1-integrin interactions in the vascular compartment. ([PMC12833886](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12833886/))
  - *assay*: Human · vascular smooth muscle cells (VSMCs)
  > "Specifically, we demonstrate that increased inclusion of the EDA exon in FN within vascular smooth muscle cells triggers phenotypic switching to a synthetic state and extracellular matrix remodeling through the ITGB1/FAK/Src/RUNX2 pathway."
- `a2_evi_15` · *Primary* · Supports · Tissue Expression — Fibronectin enrichment in fibrotic intestinal tissue (ileum and colon) was confirmed in both decellularized and native fibrotic specimens from human Crohn's disease patients, with striking consistency between clinical matrisomic data and animal model data. This cross-validation reinforces FN1 as a robust marker of fibrotic intestinal ECM across experimental systems. ([PMC13067841](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13067841/))
  - *assay*: Human · fibrotic intestinal tissue (ileum and colon), decellularized and native
  > "Notably, fibronectin enrichment persisted in both decellularized and native fibrotic intestine tissues, showing striking consistency with clinical matrisomics (Figure 1E,F )."
- `a2_evi_16` · *Primary* · Supports · Surface Expression — FN1 protein shows dual compartment staining in tumor cells: high-contrast membranous staining alongside strong cytoplasmic staining, indicating that FN1 protein is present both at the cell membrane/surface and in the cytoplasm of tumor cells. This supports surface accessibility of FN1 in the tumor cell context, though cytoplasmic co-localization indicates not exclusively surface-restricted. ([PMC12647276](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12647276/))
  - *assay*: Human · tumor cells · fixed · permeabilized
  > "There was high-contrast membranous staining of the tumor cells, but also conspicuous strong cytoplasmic staining."
- `a2_evi_17` · *Primary* · Ambiguous · Surface Expression — Weak membranous labeling of FN1 protein was observed in a limited percentage of invasive carcinoma cells (on-site cohort, case 7). This indicates that FN1 surface/membranous localization is detectable but low-level in invasive carcinoma cells, suggesting restricted surface accessibility in this cancer cell population. ([PMC13094311](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13094311/))
  - *assay*: Human · invasive carcinoma cells · fixed · permeabilized
  > "Weak membranous labeling (blue arrows) in a limited percentage of invasive carcinoma cells (on-site cohort, case 7)."
- `a2_evi_18` · *Secondary* · Supports · Surface Expression — Extracellular vesicle (EV)-associated FN1 is a surface-associated protein that facilitates cellular migration through tissues. This review assertion identifies FN1 as a functional surface component of EVs, establishing a distinct surface/accessible pool of FN1 beyond integrin-bound matrix fibronectin—relevant to the biological context of FN1 surface accessibility in tumor/stromal settings. ([PMC8612312](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8612312/))
  - *assay*: Unspecified · extracellular vesicles
  > "Several surface‐associated proteins have been documented to dictate EV function; whereas EV surface ANXA1 promotes microcalcification (Rogers et al., 2020 ), FN1 facilitates cellular migration through tissues (Sung et al., 2015 ), TGFB1 triggers fibroblast differentiation (Ringuette Goulet et al., 2018 ) and MIF establishes pre‐metastatic niche in the liver (Costa‐Silva et al., 2015 )."
- `a2_evi_19` · *Primary* · Supports · Surface Expression — FN1 was identified as a key surfaceome protein in chondrogenic cells undergoing differentiation (embryonic chicken limb bud-derived chondrogenic cells), detected by cell-surface capture mass spectrometry. This places FN1 at the cell surface during chondrogenic differentiation, establishing surface accessibility in this cell-state context. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
  - *assay*: Other · embryonic chicken limb bud chondrogenic cells · live · non-permeabilized
  > "Key proteins in this group include AKT1, FN1, SOX5, NOTCH1, and ITGB1."
- `a2_evi_20` · *Secondary* · Supports · Surface Expression — A surfaceome study of embryonic chondrogenic cells employed cell-surface capture (CSC) mass spectrometry to profile the surfaceome across key stages of chondrogenic differentiation, providing the cell-state and methodological context for FN1 surface detection during differentiation transitions. ([PMC12777226](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12777226/))
  - *assay*: Other · embryonic chondrogenic cells · live · non-permeabilized
  > "This study employed a staged approach to define the surfaceome of embryonic chicken limb bud-derived chondrogenic cells at key stages of chondrogenic differentiation."
- `a2_evi_21` · *Secondary* · Supports · Tissue Expression — FN1 is described as an ECM glycoprotein (fibronectin) detectable by IHC and scRNA-seq in the context of tumor stroma characterization, alongside stromal markers PDGFRα/β, SPARC, THBS2, α-SMA, and vimentin. This establishes FN1 as a routinely used marker for tumor stroma/CAF characterization by tissue-level and single-cell methods. ([PMC13005641](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13005641/))
  - *assay*: Human · tumor stroma / cancer-associated fibroblasts · fixed · permeabilized
  > "flow cytometry, scRNA-seq, mRNA sequencing [ 9 ] Transmembrane receptor PDGFRα/β Platelet-derived growth factor receptor IHC, flow cytometry, scRNA-seq [ 14 ] ECM glycoprotein Fibronectin 1(FN1) Fibronectin IHC, scRNA-seq [ 9 ] SPARC Secreted protein, acidic and rich in cysteine scRNA-seq, mRNA sequencing [ 27 ] THBS2 Platelet-derived growth factor receptor 2 mRNA sequencing [ 27 ] Cytoskeletal protein α-SMA α-smooth muscle actin IHC [ 9 ] Vimentin (VIM) Type III intermediate filament protein Immunofluorescence"
- `a2_evi_22` · *Secondary* · Supports · Tissue Expression — FN1 is described as a key ECM glycoprotein that plays a critical role in vascular pathologies including aneurysms and atherosclerosis. This review-level assertion contextualizes FN1 as highly expressed in pathological vascular tissue across multiple disease states (aneurysm, atherosclerosis). ([PMC12833886](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12833886/))
  - *assay*: Human · vascular tissue
  > "FN, a key ECM glycoprotein, plays a critical role in vascular pathologies, including aneurysms and atherosclerosis [ 16 , 17 ]."
- `a2_evi_23` · *Primary* · Supports · Surface Expression — FN1 surface/ECM levels were measured by cell-surface capture (µCSC) mass spectrometry in failing versus non-failing human heart samples, alongside qRT-PCR and targeted MS analyses. This establishes that FN1 surface-accessible protein was directly profiled in human cardiac tissue in a disease-state comparison context (heart failure vs. normal). ([PMC10030153](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10030153/))
  - *assay*: Human · failing and non-failing heart tissue · live · non-permeabilized
  > "Samples used for µCSC, qRT–PCR and targeted MS analyses of failing and non-failing hearts are in Supplementary Table 13 ."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/FN1.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/FN1](https://surfaceome.deliverome.org/FN1)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/FN1.json](https://surfaceome.deliverome.org/data/surfaceome/FN1.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/FN1.md](https://surfaceome.deliverome.org/data/surfaceome/FN1.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/P02751](https://alphafold.ebi.ac.uk/entry/P02751)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/P02751](https://alphafold.ebi.ac.uk/api/prediction/P02751) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/P02751](https://www.uniprot.org/uniprotkb/P02751)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-P02751-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-P02751-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-P02751-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-P02751-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-P02751-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-P02751-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*2477 aa · `P02751` · embedded at build time*

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPEVPQLTDLSFVDITDSSIGLRWTPLNSSTIIGYRITVVAAGEGIPIFEDFVDSSV
1321  GYYTVTGLEPGIDYDISVITLINGGESAPTTLTQQTAVPPPTDLRFTNIGPDTMRVTWAP
1381  PPSIDLTNFLVRYSPVKNEEDVAELSISPSDNAVVLTNLLPGTEYVVSVSSVYEQHESTP
1441  LRGRQKTGLDSPTGIDFSDITANSFTVHWIAPRATITGYRIRHHPEHFSGRPREDRVPHS
1501  RNSITLTNLTPGTEYVVSIVALNGREESPLLIGQQSTVSDVPRDLEVVAATPTSLLISWD
1561  APAVTVRYYRITYGETGGNSPVQEFTVPGSKSTATISGLKPGVDYTITVYAVTGRGDSPA
1621  SSKPISINYRTEIDKPSQMQVTDVQDNSISVKWLPSSSPVTGYRVTTTPKNGPGPTKTKT
1681  AGPDQTEMTIEGLQPTVEYVVSVYAQNPSGESQPLVQTAVTNIDRPKGLAFTDVDVDSIK
1741  IAWESPQGQVSRYRVTYSSPEDGIHELFPAPDGEEDTAELQGLRPGSEYTVSVVALHDDM
1801  ESQPLIGTQSTAIPAPTDLKFTQVTPTSLSAQWTPPNVQLTGYRVRVTPKEKTGPMKEIN
1861  LAPDSSSVVVSGLMVATKYEVSVYALKDTLTSRPAQGVVTTLENVSPPRRARVTDATETT
1921  ITISWRTKTETITGFQVDAVPANGQTPIQRTIKPDVRSYTITGLQPGTDYKIYLYTLNDN
1981  ARSSPVVIDASTAIDAPSNLRFLATTPNSLLVSWQPPRARITGYIIKYEKPGSPPREVVP
2041  RPRPGVTEATITGLEPGTEYTIYVIALKNNQKSEPLIGRKKTDELPQLVTLPHPNLHGPE
2101  ILDVPSTVQKTPFVTHPGYDTGNGIQLPGTSGQQPSVGQQMIFEEHGFRRTTPPTTATPI
2161  RHRPRPYPPNVGEEIQIGHIPREDVDYHLYPHGPGLNPNASTGQEALSQTTISWAPFQDT
2221  SEYIISCHPVGTDEEPLQFRVPGTSTSATLTGLTRGATYNVIVEALKDQQRHKVREEVVT
2281  VGNSVNEGLNQPTDDSCFDPYTVSHYAVGDEWERMSESGFKLLCQCLGFGSGHFRCDSSR
2341  WCHDNGVNYKIGEKWDRQGENGQMMSCTCLGNGKGEFKCDPHEATCYDDGKTYHVGEQWQ
2401  KEYLGAICSCTCFGGQRGWRCDNCRRPGGEPSPEGTTGQSYNQYSQRYHQRTNTNVNCPI
2461  ECFMPLDVQADREDSRE
```

### Alternative-isoform sequences

**P02751-1** (`P02751-1` · 2386 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPAVPPPTDLRFTNIGPDTMRVTWAPPPSIDLTNFLVRYSPVKNEEDVAELSISPSD
1321  NAVVLTNLLPGTEYVVSVSSVYEQHESTPLRGRQKTGLDSPTGIDFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTNIDRPKGLAFTDVDVDSIKIAWESPQGQVSRYRVTYSSPEDGIHELFPAP
1681  DGEEDTAELQGLRPGSEYTVSVVALHDDMESQPLIGTQSTAIPAPTDLKFTQVTPTSLSA
1741  QWTPPNVQLTGYRVRVTPKEKTGPMKEINLAPDSSSVVVSGLMVATKYEVSVYALKDTLT
1801  SRPAQGVVTTLENVSPPRRARVTDATETTITISWRTKTETITGFQVDAVPANGQTPIQRT
1861  IKPDVRSYTITGLQPGTDYKIYLYTLNDNARSSPVVIDASTAIDAPSNLRFLATTPNSLL
1921  VSWQPPRARITGYIIKYEKPGSPPREVVPRPRPGVTEATITGLEPGTEYTIYVIALKNNQ
1981  KSEPLIGRKKTDELPQLVTLPHPNLHGPEILDVPSTVQKTPFVTHPGYDTGNGIQLPGTS
2041  GQQPSVGQQMIFEEHGFRRTTPPTTATPIRHRPRPYPPNVGEEIQIGHIPREDVDYHLYP
2101  HGPGLNPNASTGQEALSQTTISWAPFQDTSEYIISCHPVGTDEEPLQFRVPGTSTSATLT
2161  GLTRGATYNVIVEALKDQQRHKVREEVVTVGNSVNEGLNQPTDDSCFDPYTVSHYAVGDE
2221  WERMSESGFKLLCQCLGFGSGHFRCDSSRWCHDNGVNYKIGEKWDRQGENGQMMSCTCLG
2281  NGKGEFKCDPHEATCYDDGKTYHVGEQWQKEYLGAICSCTCFGGQRGWRCDNCRRPGGEP
2341  SPEGTTGQSYNQYSQRYHQRTNTNVNCPIECFMPLDVQADREDSRE
```

**P02751-10** (`P02751-10` · 2176 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPAVPPPTDLRFTNIGPDTMRVTWAPPPSIDLTNFLVRYSPVKNEEDVAELSISPSD
1321  NAVVLTNLLPGTEYVVSVSSVYEQHESTPLRGRQKTGLDSPTGIDFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTTIPAPTDLKFTQVTPTSLSAQWTPPNVQLTGYRVRVTPKEKTGPMKEINL
1681  APDSSSVVVSGLMVATKYEVSVYALKDTLTSRPAQGVVTTLENVSPPRRARVTDATETTI
1741  TISWRTKTETITGFQVDAVPANGQTPIQRTIKPDVRSYTITGLQPGTDYKIYLYTLNDNA
1801  RSSPVVIDASTAIDAPSNLRFLATTPNSLLVSWQPPRARITGYIIKYEKPGSPPREVVPR
1861  PRPGVTEATITGLEPGTEYTIYVIALKNNQKSEPLIGRKKTGQEALSQTTISWAPFQDTS
1921  EYIISCHPVGTDEEPLQFRVPGTSTSATLTGLTRGATYNVIVEALKDQQRHKVREEVVTV
1981  GNSVNEGLNQPTDDSCFDPYTVSHYAVGDEWERMSESGFKLLCQCLGFGSGHFRCDSSRW
2041  CHDNGVNYKIGEKWDRQGENGQMMSCTCLGNGKGEFKCDPHEATCYDDGKTYHVGEQWQK
2101  EYLGAICSCTCFGGQRGWRCDNCRRPGGEPSPEGTTGQSYNQYSQRYHQRTNTNVNCPIE
2161  CFMPLDVQADREDSRE
```

**P02751-11** (`P02751-11` · 2386 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPEVPQLTDLSFVDITDSSIGLRWTPLNSSTIIGYRITVVAAGEGIPIFEDFVDSSV
1321  GYYTVTGLEPGIDYDISVITLINGGESAPTTLTQQTAVPPPTDLRFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTNIDRPKGLAFTDVDVDSIKIAWESPQGQVSRYRVTYSSPEDGIHELFPAP
1681  DGEEDTAELQGLRPGSEYTVSVVALHDDMESQPLIGTQSTAIPAPTDLKFTQVTPTSLSA
1741  QWTPPNVQLTGYRVRVTPKEKTGPMKEINLAPDSSSVVVSGLMVATKYEVSVYALKDTLT
1801  SRPAQGVVTTLENVSPPRRARVTDATETTITISWRTKTETITGFQVDAVPANGQTPIQRT
1861  IKPDVRSYTITGLQPGTDYKIYLYTLNDNARSSPVVIDASTAIDAPSNLRFLATTPNSLL
1921  VSWQPPRARITGYIIKYEKPGSPPREVVPRPRPGVTEATITGLEPGTEYTIYVIALKNNQ
1981  KSEPLIGRKKTDELPQLVTLPHPNLHGPEILDVPSTVQKTPFVTHPGYDTGNGIQLPGTS
2041  GQQPSVGQQMIFEEHGFRRTTPPTTATPIRHRPRPYPPNVGEEIQIGHIPREDVDYHLYP
2101  HGPGLNPNASTGQEALSQTTISWAPFQDTSEYIISCHPVGTDEEPLQFRVPGTSTSATLT
2161  GLTRGATYNVIVEALKDQQRHKVREEVVTVGNSVNEGLNQPTDDSCFDPYTVSHYAVGDE
2221  WERMSESGFKLLCQCLGFGSGHFRCDSSRWCHDNGVNYKIGEKWDRQGENGQMMSCTCLG
2281  NGKGEFKCDPHEATCYDDGKTYHVGEQWQKEYLGAICSCTCFGGQRGWRCDNCRRPGGEP
2341  SPEGTTGQSYNQYSQRYHQRTNTNVNCPIECFMPLDVQADREDSRE
```

**P02751-12** (`P02751-12` · 2008 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKENSPVQ
1261  EFTVPGSKSTATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTD
1321  VQDNSISVKWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSV
1381  YAQNPSGESQPLVQTAVTTIPAPTDLKFTQVTPTSLSAQWTPPNVQLTGYRVRVTPKEKT
1441  GPMKEINLAPDSSSVVVSGLMVATKYEVSVYALKDTLTSRPAQGVVTTLENVSPPRRARV
1501  TDATETTITISWRTKTETITGFQVDAVPANGQTPIQRTIKPDVRSYTITGLQPGTDYKIY
1561  LYTLNDNARSSPVVIDASTAIDAPSNLRFLATTPNSLLVSWQPPRARITGYIIKYEKPGS
1621  PPREVVPRPRPGVTEATITGLEPGTEYTIYVIALKNNQKSEPLIGRKKTVQKTPFVTHPG
1681  YDTGNGIQLPGTSGQQPSVGQQMIFEEHGFRRTTPPTTATPIRHRPRPYPPNVGQEALSQ
1741  TTISWAPFQDTSEYIISCHPVGTDEEPLQFRVPGTSTSATLTGLTRGATYNVIVEALKDQ
1801  QRHKVREEVVTVGNSVNEGLNQPTDDSCFDPYTVSHYAVGDEWERMSESGFKLLCQCLGF
1861  GSGHFRCDSSRWCHDNGVNYKIGEKWDRQGENGQMMSCTCLGNGKGEFKCDPHEATCYDD
1921  GKTYHVGEQWQKEYLGAICSCTCFGGQRGWRCDNCRRPGGEPSPEGTTGQSYNQYSQRYH
1981  QRTNTNVNCPIECFMPLDVQADREDSRE
```

**P02751-13** (`P02751-13` · 2267 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPEVPQLTDLSFVDITDSSIGLRWTPLNSSTIIGYRITVVAAGEGIPIFEDFVDSSV
1321  GYYTVTGLEPGIDYDISVITLINGGESAPTTLTQQTAVPPPTDLRFTNIGPDTMRVTWAP
1381  PPSIDLTNFLVRYSPVKNEEDVAELSISPSDNAVVLTNLLPGTEYVVSVSSVYEQHESTP
1441  LRGRQKTGLDSPTGIDFSDITANSFTVHWIAPRATITGYRIRHHPEHFSGRPREDRVPHS
1501  RNSITLTNLTPGTEYVVSIVALNGREESPLLIGQQSTVSDVPRDLEVVAATPTSLLISWD
1561  APAVTVRYYRITYGETGGNSPVQEFTVPGSKSTATISGLKPGVDYTITVYAVTGRGDSPA
1621  SSKPISINYRTEIDKPSQMQVTDVQDNSISVKWLPSSSPVTGYRVTTTPKNGPGPTKTKT
1681  AGPDQTEMTIEGLQPTVEYVVSVYAQNPSGESQPLVQTAVTTIPAPTDLKFTQVTPTSLS
1741  AQWTPPNVQLTGYRVRVTPKEKTGPMKEINLAPDSSSVVVSGLMVATKYEVSVYALKDTL
1801  TSRPAQGVVTTLENVSPPRRARVTDATETTITISWRTKTETITGFQVDAVPANGQTPIQR
1861  TIKPDVRSYTITGLQPGTDYKIYLYTLNDNARSSPVVIDASTAIDAPSNLRFLATTPNSL
1921  LVSWQPPRARITGYIIKYEKPGSPPREVVPRPRPGVTEATITGLEPGTEYTIYVIALKNN
1981  QKSEPLIGRKKTGQEALSQTTISWAPFQDTSEYIISCHPVGTDEEPLQFRVPGTSTSATL
2041  TGLTRGATYNVIVEALKDQQRHKVREEVVTVGNSVNEGLNQPTDDSCFDPYTVSHYAVGD
2101  EWERMSESGFKLLCQCLGFGSGHFRCDSSRWCHDNGVNYKIGEKWDRQGENGQMMSCTCL
2161  GNGKGEFKCDPHEATCYDDGKTYHVGEQWQKEYLGAICSCTCFGGQRGWRCDNCRRPGGE
2221  PSPEGTTGQSYNQYSQRYHQRTNTNVNCPIECFMPLDVQADREDSRE
```

**P02751-14** (`P02751-14` · 2265 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPAVPPPTDLRFTNIGPDTMRVTWAPPPSIDLTNFLVRYSPVKNEEDVAELSISPSD
1321  NAVVLTNLLPGTEYVVSVSSVYEQHESTPLRGRQKTGLDSPTGIDFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTTIPAPTDLKFTQVTPTSLSAQWTPPNVQLTGYRVRVTPKEKTGPMKEINL
1681  APDSSSVVVSGLMVATKYEVSVYALKDTLTSRPAQGVVTTLENVSPPRRARVTDATETTI
1741  TISWRTKTETITGFQVDAVPANGQTPIQRTIKPDVRSYTITGLQPGTDYKIYLYTLNDNA
1801  RSSPVVIDASTAIDAPSNLRFLATTPNSLLVSWQPPRARITGYIIKYEKPGSPPREVVPR
1861  PRPGVTEATITGLEPGTEYTIYVIALKNNQKSEPLIGRKKTDELPQLVTLPHPNLHGPEI
1921  LDVPSTVQKTPFVTHPGYDTGNGIQLPGTSGQQPSVGQQMIFEEHGFRRTTPPTTATPIR
1981  HRPRPYPPNVGQEALSQTTISWAPFQDTSEYIISCHPVGTDEEPLQFRVPGTSTSATLTG
2041  LTRGATYNVIVEALKDQQRHKVREEVVTVGNSVNEGLNQPTDDSCFDPYTVSHYAVGDEW
2101  ERMSESGFKLLCQCLGFGSGHFRCDSSRWCHDNGVNYKIGEKWDRQGENGQMMSCTCLGN
2161  GKGEFKCDPHEATCYDDGKTYHVGEQWQKEYLGAICSCTCFGGQRGWRCDNCRRPGGEPS
2221  PEGTTGQSYNQYSQRYHQRTNTNVNCPIECFMPLDVQADREDSRE
```

**P02751-16** (`P02751-16` · 657 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPVSIPPRNLGY
```

**P02751-17** (`P02751-17` · 2330 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPAVPPPTDLRFTNIGPDTMRVTWAPPPSIDLTNFLVRYSPVKNEEDVAELSISPSD
1321  NAVVLTNLLPGTEYVVSVSSVYEQHESTPLRGRQKTGLDSPTGIDFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTNIDRPKGLAFTDVDVDSIKIAWESPQGQVSRYRVTYSSPEDGIHELFPAP
1681  DGEEDTAELQGLRPGSEYTVSVVALHDDMESQPLIGTQSTAIPAPTDLKFTQVTPTSLSA
1741  QWTPPNVQLTGYRVRVTPKEKTGPMKEINLAPDSSSVVVSGLMVATKYEVSVYALKDTLT
1801  SRPAQGVVTTLENVSPPRRARVTDATETTITISWRTKTETITGFQVDAVPANGQTPIQRT
1861  IKPDVRSYTITGLQPGTDYKIYLYTLNDNARSSPVVIDASTAIDAPSNLRFLATTPNSLL
1921  VSWQPPRARITGYIIKYEKPGSPPREVVPRPRPGVTEATITGLEPGTEYTIYVIALKNNQ
1981  KSEPLIGRKKTVQKTPFVTHPGYDTGNGIQLPGTSGQQPSVGQQMIFEEHGFRRTTPPTT
2041  ATPIRHRPRPYPPNVGQEALSQTTISWAPFQDTSEYIISCHPVGTDEEPLQFRVPGTSTS
2101  ATLTGLTRGATYNVIVEALKDQQRHKVREEVVTVGNSVNEGLNQPTDDSCFDPYTVSHYA
2161  VGDEWERMSESGFKLLCQCLGFGSGHFRCDSSRWCHDNGVNYKIGEKWDRQGENGQMMSC
2221  TCLGNGKGEFKCDPHEATCYDDGKTYHVGEQWQKEYLGAICSCTCFGGQRGWRCDNCRRP
2281  GGEPSPEGTTGQSYNQYSQRYHQRTNTNVNCPIECFMPLDVQADREDSRE
```

**P02751-2** (`P02751-2` · 642 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNDRTDSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALCHFPFLYNNHNYTDCT
 421  SEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRIGDQWDKQHDMGHMMR
 481  CTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHMLNCTCFGQGRGRWKC
 541  DPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQPLQTYPSSSGPVEVF
 601  ITETPSQPNSHPIQWNAPQPSHISKYILRWRPVSIPPRNLGY
```

**P02751-3** (`P02751-3` · 2355 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPAVPPPTDLRFTNIGPDTMRVTWAPPPSIDLTNFLVRYSPVKNEEDVAELSISPSD
1321  NAVVLTNLLPGTEYVVSVSSVYEQHESTPLRGRQKTGLDSPTGIDFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTNIDRPKGLAFTDVDVDSIKIAWESPQGQVSRYRVTYSSPEDGIHELFPAP
1681  DGEEDTAELQGLRPGSEYTVSVVALHDDMESQPLIGTQSTAIPAPTDLKFTQVTPTSLSA
1741  QWTPPNVQLTGYRVRVTPKEKTGPMKEINLAPDSSSVVVSGLMVATKYEVSVYALKDTLT
1801  SRPAQGVVTTLENVSPPRRARVTDATETTITISWRTKTETITGFQVDAVPANGQTPIQRT
1861  IKPDVRSYTITGLQPGTDYKIYLYTLNDNARSSPVVIDASTAIDAPSNLRFLATTPNSLL
1921  VSWQPPRARITGYIIKYEKPGSPPREVVPRPRPGVTEATITGLEPGTEYTIYVIALKNNQ
1981  KSEPLIGRKKTDELPQLVTLPHPNLHGPEILDVPSTVQKTPFVTHPGYDTGNGIQLPGTS
2041  GQQPSVGQQMIFEEHGFRRTTPPTTATPIRHRPRPYPPNVGQEALSQTTISWAPFQDTSE
2101  YIISCHPVGTDEEPLQFRVPGTSTSATLTGLTRGATYNVIVEALKDQQRHKVREEVVTVG
2161  NSVNEGLNQPTDDSCFDPYTVSHYAVGDEWERMSESGFKLLCQCLGFGSGHFRCDSSRWC
2221  HDNGVNYKIGEKWDRQGENGQMMSCTCLGNGKGEFKCDPHEATCYDDGKTYHVGEQWQKE
2281  YLGAICSCTCFGGQRGWRCDNCRRPGGEPSPEGTTGQSYNQYSQRYHQRTNTNVNCPIEC
2341  FMPLDVQADREDSRE
```

**P02751-4** (`P02751-4` · 2031 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPAVPPPTDLRFTNIGPDTMRVTWAPPPSIDLTNFLVRYSPVKNEEDVAELSISPSD
1321  NAVVLTNLLPGTEYVVSVSSVYEQHESTPLRGRQKTGLDSPTGIDFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTNIDRPKGLAFTDVDVDSIKIAWESPQGQVSRYRVTYSSPEDGIHELFPAP
1681  DGEEDTAELQGLRPGSEYTVSVVALHDDMESQPLIGTQSTAIPAPTDLKFTQVTPTSLSA
1741  QWTPPNVQLTGYRVRVTPKEKTGPMKEINLAPDSSSVVVSGLMVATKYEVSVYALKDTLT
1801  SRPAQGVVTTLENVSPPRRARVTDATETTITISWRTKTETITGFQVDAVPANGQTPIQRT
1861  IKPDVRSYTITGLQPGTDYKIYLYTLNDNARSSPVVIDASTAIDAPSNLRFLATTPNSLL
1921  VSWQPPRARITGYIIKYEKPGSPPREVVPRPRPGVTEATITGLEPGTEYTIYVIALKNNQ
1981  KSEPLIGRKKTGQEALSQTTISWAPFQDTSEYIISCHPVGTDEEPLQSTKA
```

**P02751-5** (`P02751-5` · 2211 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPAVPPPTDLRFTNIGPDTMRVTWAPPPSIDLTNFLVRYSPVKNEEDVAELSISPSD
1321  NAVVLTNLLPGTEYVVSVSSVYEQHESTPLRGRQKTGLDSPTGIDFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTNIDRPKGLAFTDVDVDSIKIAWESPQGQVSRYRVTYSSPEDGIHELFPAP
1681  DGEEDTAELQGLRPGSEYTVSVVALHDDMESQPLIGTQSTAIPAPTDLKFTQVTPTSLSA
1741  QWTPPNVQLTGYRVRVTPKEKTGPMKEINLAPDSSSVVVSGLMVATKYEVSVYALKDTLT
1801  SRPAQGVVTTLENVSPPRRARVTDATETTITISWRTKTETITGFQVDAVPANGQTPIQRT
1861  IKPDVRSYTITGLQPGTDYKIYLYTLNDNARSSPVVIDASTAIDAPSNLRFLATTPNSLL
1921  VSWQPPRARITGYIIKYEKPGSPPREVVPRPRPGVTEATITGLEPGTEYTIYVIALKNNQ
1981  KSEPLIGRKKTGQEALSQTTISWAPFQDTSEYIISCHPVGTDEEPLQFRVPGTSTSATLT
2041  GLTRGATYNVIVEALKDQQRHKVREEVVTVGNSRWCHDNGVNYKIGEKWDRQGENGQMMS
2101  CTCLGNGKGEFKCDPHEATCYDDGKTYHVGEQWQKEYLGAICSCTCFGGQRGWRCDNCRR
2161  PGGEPSPEGTTGQSYNQYSQRYHQRTNTNVNCPIECFMPLDVQADREDSRE
```

**P02751-6** (`P02751-6` · 2184 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPAVPPPTDLRFTNIGPDTMRVTWAPPPSIDLTNFLVRYSPVKNEEDVAELSISPSD
1321  NAVVLTNLLPGTEYVVSVSSVYEQHESTPLRGRQKTGLDSPTGIDFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTNIDRPKGLAFTDVDVDSIKIAWESPQGQVSRYRVTYSSPEDGIHELFPAP
1681  DGEEDTAELQGLRPGSEYTVSVVALHDDMESQPLIGTQSTAIPAPTDLKFTQVTPTSLSA
1741  QWTPPNVQLTGYRVRVTPKEKTGPMKEINLAPDSSSVVVSGLMVATKYEVSVYALKDTLT
1801  SRPAQGVVTTLENVSPPRRARVTDATETTITISWRTKTETITGFQVDAVPANGQTPIQRT
1861  IKPDVRSYTITGLQPGTDYKIYLYTLNDNARSSPVVIDASTAIDAPSNLRFLATTPNSLL
1921  VSWQPPRARITGYIIKYEKPGSPPREVVPRPRPGVTEATITGLEPGTEYTIYVIALKNNQ
1981  KSEPLIGRKKTVNEGLNQPTDDSCFDPYTVSHYAVGDEWERMSESGFKLLCQCLGFGSGH
2041  FRCDSSRWCHDNGVNYKIGEKWDRQGENGQMMSCTCLGNGKGEFKCDPHEATCYDDGKTY
2101  HVGEQWQKEYLGAICSCTCFGGQRGWRCDNCRRPGGEPSPEGTTGQSYNQYSQRYHQRTN
2161  TNVNCPIECFMPLDVQADREDSRE
```

**P02751-7** (`P02751-7` · 2446 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPEVPQLTDLSFVDITDSSIGLRWTPLNSSTIIGYRITVVAAGEGIPIFEDFVDSSV
1321  GYYTVTGLEPGIDYDISVITLINGGESAPTTLTQQTAVPPPTDLRFTNIGPDTMRVTWAP
1381  PPSIDLTNFLVRYSPVKNEEDVAELSISPSDNAVVLTNLLPGTEYVVSVSSVYEQHESTP
1441  LRGRQKTGLDSPTGIDFSDITANSFTVHWIAPRATITGYRIRHHPEHFSGRPREDRVPHS
1501  RNSITLTNLTPGTEYVVSIVALNGREESPLLIGQQSTVSDVPRDLEVVAATPTSLLISWD
1561  APAVTVRYYRITYGETGGNSPVQEFTVPGSKSTATISGLKPGVDYTITVYAVTGRGDSPA
1621  SSKPISINYRTEIDKPSQMQVTDVQDNSISVKWLPSSSPVTGYRVTTTPKNGPGPTKTKT
1681  AGPDQTEMTIEGLQPTVEYVVSVYAQNPSGESQPLVQTAVTNIDRPKGLAFTDVDVDSIK
1741  IAWESPQGQVSRYRVTYSSPEDGIHELFPAPDGEEDTAELQGLRPGSEYTVSVVALHDDM
1801  ESQPLIGTQSTAIPAPTDLKFTQVTPTSLSAQWTPPNVQLTGYRVRVTPKEKTGPMKEIN
1861  LAPDSSSVVVSGLMVATKYEVSVYALKDTLTSRPAQGVVTTLENVSPPRRARVTDATETT
1921  ITISWRTKTETITGFQVDAVPANGQTPIQRTIKPDVRSYTITGLQPGTDYKIYLYTLNDN
1981  ARSSPVVIDASTAIDAPSNLRFLATTPNSLLVSWQPPRARITGYIIKYEKPGSPPREVVP
2041  RPRPGVTEATITGLEPGTEYTIYVIALKNNQKSEPLIGRKKTDELPQLVTLPHPNLHGPE
2101  ILDVPSTVQKTPFVTHPGYDTGNGIQLPGTSGQQPSVGQQMIFEEHGFRRTTPPTTATPI
2161  RHRPRPYPPNVGQEALSQTTISWAPFQDTSEYIISCHPVGTDEEPLQFRVPGTSTSATLT
2221  GLTRGATYNVIVEALKDQQRHKVREEVVTVGNSVNEGLNQPTDDSCFDPYTVSHYAVGDE
2281  WERMSESGFKLLCQCLGFGSGHFRCDSSRWCHDNGVNYKIGEKWDRQGENGQMMSCTCLG
2341  NGKGEFKCDPHEATCYDDGKTYHVGEQWQKEYLGAICSCTCFGGQRGWRCDNCRRPGGEP
2401  SPEGTTGQSYNQYSQRYHQRTNTNVNCPIECFMPLDVQADREDSRE
```

**P02751-8** (`P02751-8` · 2296 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPAVPPPTDLRFTNIGPDTMRVTWAPPPSIDLTNFLVRYSPVKNEEDVAELSISPSD
1321  NAVVLTNLLPGTEYVVSVSSVYEQHESTPLRGRQKTGLDSPTGIDFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTTIPAPTDLKFTQVTPTSLSAQWTPPNVQLTGYRVRVTPKEKTGPMKEINL
1681  APDSSSVVVSGLMVATKYEVSVYALKDTLTSRPAQGVVTTLENVSPPRRARVTDATETTI
1741  TISWRTKTETITGFQVDAVPANGQTPIQRTIKPDVRSYTITGLQPGTDYKIYLYTLNDNA
1801  RSSPVVIDASTAIDAPSNLRFLATTPNSLLVSWQPPRARITGYIIKYEKPGSPPREVVPR
1861  PRPGVTEATITGLEPGTEYTIYVIALKNNQKSEPLIGRKKTDELPQLVTLPHPNLHGPEI
1921  LDVPSTVQKTPFVTHPGYDTGNGIQLPGTSGQQPSVGQQMIFEEHGFRRTTPPTTATPIR
1981  HRPRPYPPNVGEEIQIGHIPREDVDYHLYPHGPGLNPNASTGQEALSQTTISWAPFQDTS
2041  EYIISCHPVGTDEEPLQFRVPGTSTSATLTGLTRGATYNVIVEALKDQQRHKVREEVVTV
2101  GNSVNEGLNQPTDDSCFDPYTVSHYAVGDEWERMSESGFKLLCQCLGFGSGHFRCDSSRW
2161  CHDNGVNYKIGEKWDRQGENGQMMSCTCLGNGKGEFKCDPHEATCYDDGKTYHVGEQWQK
2221  EYLGAICSCTCFGGQRGWRCDNCRRPGGEPSPEGTTGQSYNQYSQRYHQRTNTNVNCPIE
2281  CFMPLDVQADREDSRE
```

**P02751-9** (`P02751-9` · 2240 aa)

```
   1  MLRGPGPGLLLLAVQCLGTAVPSTGASKSKRQAQQMVQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALVCTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTSVQTTSSGSGPFTDVRAAVYQPQPHP
 301  QPPPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVEVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHQEVTRFDFTTTSTSTPVTSNTVTGETTPFSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYQISEDGEQSLILSTSQTTAPDAPPDTTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVVIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVSHGRESKPLTAQQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RAQITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPASEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLEANPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGNSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPAVPPPTDLRFTNIGPDTMRVTWAPPPSIDLTNFLVRYSPVKNEEDVAELSISPSD
1321  NAVVLTNLLPGTEYVVSVSSVYEQHESTPLRGRQKTGLDSPTGIDFSDITANSFTVHWIA
1381  PRATITGYRIRHHPEHFSGRPREDRVPHSRNSITLTNLTPGTEYVVSIVALNGREESPLL
1441  IGQQSTVSDVPRDLEVVAATPTSLLISWDAPAVTVRYYRITYGETGGNSPVQEFTVPGSK
1501  STATISGLKPGVDYTITVYAVTGRGDSPASSKPISINYRTEIDKPSQMQVTDVQDNSISV
1561  KWLPSSSPVTGYRVTTTPKNGPGPTKTKTAGPDQTEMTIEGLQPTVEYVVSVYAQNPSGE
1621  SQPLVQTAVTTIPAPTDLKFTQVTPTSLSAQWTPPNVQLTGYRVRVTPKEKTGPMKEINL
1681  APDSSSVVVSGLMVATKYEVSVYALKDTLTSRPAQGVVTTLENVSPPRRARVTDATETTI
1741  TISWRTKTETITGFQVDAVPANGQTPIQRTIKPDVRSYTITGLQPGTDYKIYLYTLNDNA
1801  RSSPVVIDASTAIDAPSNLRFLATTPNSLLVSWQPPRARITGYIIKYEKPGSPPREVVPR
1861  PRPGVTEATITGLEPGTEYTIYVIALKNNQKSEPLIGRKKTVQKTPFVTHPGYDTGNGIQ
1921  LPGTSGQQPSVGQQMIFEEHGFRRTTPPTTATPIRHRPRPYPPNVGQEALSQTTISWAPF
1981  QDTSEYIISCHPVGTDEEPLQFRVPGTSTSATLTGLTRGATYNVIVEALKDQQRHKVREE
2041  VVTVGNSVNEGLNQPTDDSCFDPYTVSHYAVGDEWERMSESGFKLLCQCLGFGSGHFRCD
2101  SSRWCHDNGVNYKIGEKWDRQGENGQMMSCTCLGNGKGEFKCDPHEATCYDDGKTYHVGE
2161  QWQKEYLGAICSCTCFGGQRGWRCDNCRRPGGEPSPEGTTGQSYNQYSQRYHQRTNTNVN
2221  CPIECFMPLDVQADREDSRE
```

### Canonical ortholog sequences

**Mouse — Fn1** (`P11276` · 2477 aa)

```
   1  MLRGPGPGRLLLLAVLCLGTSVRCTEAGKSKRQAQQIVQPQSPVAVSQSKPGCFDNGKHY
  61  QINQQWERTYLGNALVCTCYGGSRGFNCESKPEPEETCFDKYTGNTYKVGDTYERPKDSM
 121  IWDCTCIGAGRGRISCTIANRCHEGGQSYKIGDKWRRPHETGGYMLECLCLGNGKGEWTC
 181  KPIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGNGRITCTSRNRCNDQDTRTS
 241  YRIGDTWSKKDNRGNLLQCVCTGNGRGEWKCERHALQSASAGSGSFTDVRTAIYQPQTHP
 301  QPAPYGHCVTDSGVVYSVGMQWLKSQGNKQMLCTCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHAVLVQTRGGNSNGALC
 421  HFPFLYNNRNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDLGHMMRCTCVGNGRGEWACIPYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPIDQCQDSETRTFYQIGDSWEKFVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPGTTGPVQVIITETPSQPNSHPIQWNAPEPSHITKYILRWRPKTSTGRWKEATIP
 661  GHLNSYTIKGLTPGVIYEGQLISIQQYGHREVTRFDFTTSASTPVTSNTVTGETAPYSPV
 721  VATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDLL
 781  PGRKYIVNVYQISEEGKQSLILSTSQTTAPDAPPDPTVDQVDDTSIVVRWSRPQAPITGY
 841  RIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIYAVEENQESTPVFIQQETTGT
 901  PRSDNVPPPTDLQFVELTDVKVTIMWTPPDSVVSGYRVEVLPVSLPGEHGQRLPVNRNTF
 961  AEITGLSPGVTYLFKVFAVHQGRESNPLTAQQTTKLDAPTNLQFVNETDRTVLVTWTPPR
1021  ARIAGYRLTAGLTRGGQPKQYNVGPLASKYPLRNLQPGSEYTVTLVAVKGNQQSPKATGV
1081  FTTLQPLRSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVVS
1141  GLTPGVEYTYTIQVLRDGQERDAPIVNRVVTPLSPPTNLHLEANPDTGVLTVSWERSTTP
1201  DITGYRITTTPTNGQQGTSLEEVVHADQSSCTFENLNPGLEYNVSVYTVKDDKESAPISD
1261  TVVPEVPQLTDLSFVDITDSSIGLRWTPLNSSTIIGYRITVVAAGEGIPIFEDFVDSSVG
1321  YYTVTGLEPGIDYDISVITLINGGESAPTTLTQQTAVPPPTDLRFTNIGPDTMRVTWAPP
1381  PSIELTNLLVRYSPVKNEEDVAELSISPSDNAVVLTNLLPGTEYLVSVSSVYEQHESIPL
1441  RGRQKTGLDSPTGFDSSDITANSFTVHWVAPRAPITGYIIRHHAEHSVGRPRQDRVPPSR
1501  NSITLTNLNPGTEYVVSIIAVNGREESPPLIGQQATVSDIPRDLEVIASTPTSLLISWEP
1561  PAVSVRYYRITYGETGGNSPVQEFTVPGSKSTATINNIKPGADYTITLYAVTGRGDSPAS
1621  SKPVSINYKTEIDKPSQMQVTDVQDNSISVRWLPSTSPVTGYRVTTTPKNGLGPSKTKTA
1681  SPDQTEMTIEGLQPTVEYVVSVYAQNRNGESQPLVQTAVTNIDRPKGLAFTDVDVDSIKI
1741  AWESPQGQVSRYRVTYSSPEDGIRELFPAPDGEDDTAELQGLRPGSEYTVSVVALHDDME
1801  SQPLIGIQSTAIPAPTNLKFSQVTPTSFTAQWIAPSVQLTGYRVRVNPKEKTGPMKEINL
1861  SPDSSSVIVSGLMVATKYEVSVYALKDTLTSRPAQGVITTLENVSPPRRARVTDATETTI
1921  TISWRTKTETITGFQVDAIPANGQTPVQRSISPDVRSYTITGLQPGTDYKIHLYTLNDNA
1981  RSSPVIIDASTAIDAPSNLRFLTTTPNSLLVSWQAPRARITGYIIKYEKPGSPPREVVPR
2041  PRPGVTEATITGLEPGTEYTIYVIALKNNQKSEPLIGRKKTDELPQLVTLPHPNLHGPEI
2101  LDVPSTVQKTPFITNPGYDTENGIQLPGTTHQQPSVGQQMIFEEHGFRRTTPPTAATPVR
2161  LRPRPYLPNVDEEVQIGHVPRGDVDYHLYPHVPGLNPNASTGQEALSQTTISWTPFQESS
2221  EYIISCQPVGTDEEPLQFQVPGTSTSATLTGLTRGVTYNIIVEALQNQRRHKVREEVVTV
2281  GNAVSEGLNQPTDDSCFDPYTVSHYAIGEEWERLSDAGFKLTCQCLGFGSGHFRCDSSKW
2341  CHDNGVNYKIGEKWDRQGENGQRMSCTCLGNGKGEFKCDPHEATCYDDGKTYHVGEQWQK
2401  EYLGAICSCTCFGGQRGWRCDNCRRPGAAEPSPDGTTGHTYNQYTQRYNQRTNTNVNCPI
2461  ECFMPLDVQADRDDSRE
```

**Cynomolgus — FN1** (`A0A2K5V0I5` · 2477 aa)

```
   1  MLRGPGPGLLLLAVLCLGTAVPSTGASKSKRQAQQMIQPQSPVAVSQSKPGCYDNGKHYQ
  61  INQQWERTYLGNALICTCYGGSRGFNCESKPEAEETCFDKYTGNTYRVGDTYERPKDSMI
 121  WDCTCIGAGRGRISCTIANRCHEGGQSYKIGDTWRRPHETGGYMLECVCLGNGKGEWTCK
 181  PIAEKCFDHAAGTSYVVGETWEKPYQGWMMVDCTCLGEGSGRITCTSRNRCNDQDTRTSY
 241  RIGDTWSKKDNRGNLLQCICTGNGRGEWKCERHTTVQTTSSGSGPFTDVREAVYQPQPHP
 301  QPAPYGHCVTDSGVVYSVGMQWLKTQGNKQMLCMCLGNGVSCQETAVTQTYGGNSNGEPC
 361  VLPFTYNGRTFYSCTTEGRQDGHLWCSTTSNYEQDQKYSFCTDHTVLVQTRGGNSNGALC
 421  HFPFLYNNHNYTDCTSEGRRDNMKWCGTTQNYDADQKFGFCPMAAHEEICTTNEGVMYRI
 481  GDQWDKQHDMGHMMRCTCVGNGRGEWTCIAYSQLRDQCIVDDITYNVNDTFHKRHEEGHM
 541  LNCTCFGQGRGRWKCDPVDQCQDSETGTFYQIGDSWEKYVHGVRYQCYCYGRGIGEWHCQ
 601  PLQTYPSSSGPVQVFITETPSQPNSHPIQWNAPQPSHISKYILRWRPKNSVGRWKEATIP
 661  GHLNSYTIKGLKPGVVYEGQLISIQQYGHREVTRFDFTTTSTSTPVTSNTVTGETTPLSP
 721  LVATSESVTEITASSFVVSWVSASDTVSGFRVEYELSEEGDEPQYLDLPSTATSVNIPDL
 781  LPGRKYIVNVYEISEDGEQSLILSTSQTTAPDAPPDPTVDQVDDTSIVVRWSRPQAPITG
 841  YRIVYSPSVEGSSTELNLPETANSVTLSDLQPGVQYNITIFAVEENQESTPVFIQQETTG
 901  TPRSDTVPSPRDLQFVEVTDVKVTIMWTPPESAVTGYRVDVIPVNLPGEHGQRLPISRNT
 961  FAEVTGLSPGVTYYFKVFAVNHGRESKPLTAEQTTKLDAPTNLQFVNETDSTVLVRWTPP
1021  RARITGYRLTVGLTRRGQPRQYNVGPSVSKYPLRNLQPGSEYTVSLVAIKGNQESPKATG
1081  VFTTLQPGSSIPPYNTEVTETTIVITWTPAPRIGFKLGVRPSQGGEAPREVTSDSGSIVV
1141  SGLTPGVEYVYTIQVLRDGQERDAPIVNKVVTPLSPPTNLHLETNPDTGVLTVSWERSTT
1201  PDITGYRITTTPTNGQQGYSLEEVVHADQSSCTFDNLSPGLEYNVSVYTVKDDKESVPIS
1261  DTIIPEVPQLTDLSFVDITDSSIGLRWTPLNSSTIIGYRITVVAAGEGIPIFEDFVDSSV
1321  GYYTVTGLEPGIDYDISVITLINGGESAPTTLTQQTAVPPPTDLRFTNIGPDTMRVTWAP
1381  PPSIDLTNFLVRYSPVKNEEDVAELSISPSDNAVVLTNLLPGTEYVVSVSSVYEQHESTP
1441  LRGRQKTGLDSPTGIDFSDITANSFTVHWIAPRATITGYRIRHHPEHMSGRPREDRVPPS
1501  RNSITLTNLTPGTEYVVSIVALNGREESPLLIGQQSTVSDVPRDLEVVAATPTSLLISWD
1561  APAVTVRYYRITYGETGGNSPVQEFTVPGSKSTATISGLKPGVDYTITVYAVTGRGDSPA
1621  SSKPISINYRTEIDKPSQMQVTDVQDNSISVKWLPSSSPVTGYRVTTTPKNGPGPTKTKT
1681  AGPDQTEMTIEGLQPTVEYVVSVFAQNPNGESQPLVQTAVTNIDRPKGLAFTDVDVDSIK
1741  IAWESPQGQVSRYRVTYSSPEDGIHELFPAPDGEEDTAELQGLRPGSEYTVSVVALHDDM
1801  ESQPLIGTQSTAIPAPTDLKFTQVTPTSLSAQWTPPNVQLTGYRVRVTPKEKTGPMKEIN
1861  LAPDSSSVVVSGLMVATKYEVSVYALKDTLTSRPAQGVVTTLENVSPPRRARVTDATETT
1921  ITISWRTKTETITGFQVDAVPANGQTPIQRTIKPDVRSYTITGLQPGTDYKIYLYTLNDN
1981  ARSSPVVIDASTAIDAPSNLRFLATTPNSLLVSWQPPRARITGYIIKYEKPGSSPREVVP
2041  RPRPGVTEATITGLEPGTEYTIYVIALKNNQKSEPLIGRKKTDELPQLVTLPHPNLHGPE
2101  ILDVPSTVQKTPFITHPGYDTGNGIQLPGTSGQQPTVGQQMIFEEHGFRRTTPPTTATPI
2161  RHRPRPYPPNVGEEIQIGHIPREDVDYHLYPHGLGLNPNASTGQEALSQTTISWAPFQDT
2221  SEYIISCHPVGTDEEPLQFRVPGTSTSATLTGLTRGATYNIIVEALKDQQRHKVREEVVT
2281  VGNSVNEGLNQPTDDSCFDPYTVSHYAVGDEWERMSESGFKLLCHCLGFGSGHFRCDSSR
2341  WCHDNGVNYKIGEKWDRQGENGQMMSCTCLGNGKGEFKCDPHEATCYDDGKTYHVGEQWQ
2401  KEYLGAICSCTCFGGQRGWRCDNCRRPGGEPSPEGTTGQSYNQYSQRYHQRTNTNVNCPI
2461  ECFMPLDVQADREDSRE
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`P02751`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2461  OOOOOOOOOOOOOOOOO
```

**P02751-1** (`P02751-1`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2341  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-10** (`P02751-10`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2161  OOOOOOOOOOOOOOOO
```

**P02751-11** (`P02751-11`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2341  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-12** (`P02751-12`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
1981  OOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-13** (`P02751-13`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2221  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-14** (`P02751-14`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2221  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-16** (`P02751-16`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-17** (`P02751-17`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2281  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-2** (`P02751-2`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 181  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 241  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 301  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 361  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 421  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 481  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 541  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 601  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-3** (`P02751-3`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2341  OOOOOOOOOOOOOOO
```

**P02751-4** (`P02751-4`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
1981  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-5** (`P02751-5`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2161  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-6** (`P02751-6`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2161  OOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-7** (`P02751-7`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2401  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
```

**P02751-8** (`P02751-8`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2281  OOOOOOOOOOOOOOOO
```

**P02751-9** (`P02751-9`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2221  OOOOOOOOOOOOOOOOOOOO
```

**Mouse ortholog — Fn1** (`P11276`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2461  OOOOOOOOOOOOOOOOO
```

**Cynomolgus ortholog — FN1** (`A0A2K5V0I5`, projected onto human canonical)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
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
2461  OOOOOOOOOOOOOOOOO
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — ensembl_compara_2026_05_12 · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence moderate — Confidence is moderate for two reasons. First, the direct surface-accessibility evidence comes from a single primary method (cell-surface capture mass spectrometry on chondrogenic cells, PMC12777226, and µCSC in cardiac tissue, PMC10030153); IHC data are from permeabilized/fixed tissue and cannot distinguish surface from intracellular FN1. Second, the dominant biological pool is the hepatocyte-secreted plasma fibronectin, which circulates freely in blood — a genuine high-severity decoy that complicates antibody-based targeting. Surface membranous FN1 is disease-state-enriched (tumor, fibrosis, cardiac failure) and absent in normal liver (PMC11907257), so confidence in a constitutive surface call is low; confidence in the disease-state surface call is moderate. To lift confidence, non-permeabilized live-cell flow cytometry or surface-capture MS in human tumor cell lines, combined with direct plasma/serum competition experiments, would be needed.*

## CellxGene RNA enrichment (CZI Census)

*Schema v2.1.5 · CZI Census 2025-11-08 · HPA-style 4× fold-change classification on log1p(CP10K) → linear means, plus Yanai et al. 2005 τ (specificity score ∈ [0, 1], computed over the eligible-entity set). Cell-class rollup walks the Cell Ontology graph (cl-basic.obo, OBO Foundry) — leaf CL → nearest compartment ancestor. CC-BY 4.0 (CZI Census).*

**Classification:**

- **Cell class (CL ontology graph, ~10 compartments):** enhanced · Stromal · 1.0× · τ=0.55
- **Cell type (leaf Cell Ontology terms, ~600):** enriched · cycling stromal cell · cell · embryonic fibroblast · 1.0× · τ=0.92
- **Tissue (UBERON terms, ~56):** enriched · vasculature · 4.4× · τ=0.98

**Top 5 cell types (leaf CL, pooled across tissues):**

| Cell type | CL ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| precursor cell | CL:0011115 | 3.793 | 31.57% | 179 / 567 |
| alternatively activated macrophage | CL:0000890 | 3.770 | 19.90% | 3,772 / 18,954 |
| trophoblast giant cell | CL:0002488 | 3.722 | 3.46% | 40 / 1,156 |
| endodermal cell | CL:0000223 | 3.546 | 49.85% | 4,273 / 8,571 |
| respiratory tract hillock cell | CL:4030023 | 3.347 | 1.96% | 108 / 5,515 |

**Top 5 tissues (UBERON, pooled across cell types):**

| Tissue | UBERON ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |
|---|---|---|---|---|
| paracolic gutter | UBERON:0035210 | 3.363 | 31.88% | 2,554 / 8,012 |
| pleura | UBERON:0000977 | 3.090 | 20.18% | 3,975 / 19,695 |
| omentum | UBERON:0003688 | 2.999 | 26.32% | 58,500 / 222,303 |
| chest wall | UBERON:0016435 | 2.990 | 25.84% | 5,205 / 20,144 |
| esophagus | UBERON:0001043 | 2.855 | 71.90% | 16,961 / 23,590 |

<!-- /cellxgene -->
