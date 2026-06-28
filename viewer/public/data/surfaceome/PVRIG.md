# PVRIG — Surface Accessibility Brief

*Schema v2.9.0 · generated 2026-06-08T20:48:27.517803Z · model `claude-sonnet-4-6`*

> PVRIG is constitutively surface-accessible as a Type I single-pass inhibitory immune checkpoint receptor on NK, NKT, γδ T, and CD8+ T cells. Direct multi-method support: live-cell flow cytometry on primary human lymphocytes (a1_evi_10, a1_evi_15, a1_evi_17) and functional surface-blockade assays with COM701 and a TIGIT×PVRIG bispecific antibody on intact T and NK cells (a1_evi_08, a1_evi_24), plus ER/Golgi trafficking assay confirming constitutive PM delivery (a1_evi_19). Surface levels are moderately state-modulated: upregulated on tumor-infiltrating and activated CD8+ T cells across multiple solid tumor types (a2_evi_12, a2_evi_14), downregulated on activated NK cells (a2_evi_25), and elevated in disease contexts such as MDS/AML bone marrow (a2_evi_11). No shed or secreted form, no co-receptor requirement, and no paralog cross-reactivity rules out decoy and selectivity concerns; ligand-trans engagement rather than constitutive cis masking means the epitope is freely accessible in the unbound state.

**Vitals**

| Field | Value |
|---|---|
| HGNC | [HGNC:32190](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:32190) |
| UniProt | [Q6DKI7](https://www.uniprot.org/uniprotkb/Q6DKI7) |
| NCBI Gene | [79037](https://www.ncbi.nlm.nih.gov/gene/79037) |
| Ensembl | [ENSG00000213413](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000213413) |
| Subcategory | Single-pass type I |
| Surface accessibility | High |
| Confidence | High |
| Evidence grade | Direct, multi-method |
| Triage signal | Likely accessible |

## 1. Executive summary

**Constitutively surface-accessible on circulating NK, NKT, γδ T, and CD8+ T cells; further upregulated on tumor-infiltrating lymphocytes across multiple solid tumors and in hematologic malignancies, with activation-induced downregulation on NK cells.**

PVRIG is constitutively surface-accessible as a Type I single-pass inhibitory immune checkpoint receptor on NK, NKT, γδ T, and CD8+ T cells. Direct multi-method support: live-cell flow cytometry on primary human lymphocytes (a1_evi_10, a1_evi_15, a1_evi_17) and functional surface-blockade assays with COM701 and a TIGIT×PVRIG bispecific antibody on intact T and NK cells (a1_evi_08, a1_evi_24), plus ER/Golgi trafficking assay confirming constitutive PM delivery (a1_evi_19). Surface levels are moderately state-modulated: upregulated on tumor-infiltrating and activated CD8+ T cells across multiple solid tumor types (a2_evi_12, a2_evi_14), downregulated on activated NK cells (a2_evi_25), and elevated in disease contexts such as MDS/AML bone marrow (a2_evi_11). No shed or secreted form, no co-receptor requirement, and no paralog cross-reactivity rules out decoy and selectivity concerns; ligand-trans engagement rather than constitutive cis masking means the epitope is freely accessible in the unbound state.

**Family / classification** — functional class: Receptor.

**Triage first-pass reasoning** — PVRIG (CD112R) is a type I single-pass transmembrane receptor expressed on T cells and NK cells. It contains an extracellular immunoglobulin domain that binds PVRL2 (Nectin-2/CD112) on tumor cells, acting as an inhibitory immune checkpoint receptor analogous to TIGIT. Flow cytometry on intact (non-permeabilized) lymphocytes and NK cells confirms cell-surface expression. Multiple therapeutic programs (antibodies targeting the extracellular domain in intact immune cells) are in clinical development (e.g., COM701). NCBI annotation explicitly states 'located in plasma membrane' with signaling receptor activity. The extracellular Ig domain is stably displayed on the outer leaflet under baseline conditions in T/NK cells.

## 2. Filters / catalog facets

| Group | Facets |
|---|---|
| Accessibility | overall=High · conf=High · subcategory=Single-pass type I · ecd=Moderate |
| Classification | reason=Classical Surface Receptor · family=Receptor · state-dependence=Moderate · induction-trigger=Oncogenic |
| Expression | level=Moderate · breadth=Restricted · specificity=Mixed · low-endogenous=true · tumor-associated=true · orphan-receptor=false · OE-precedent=true |
| Risks | shed=false · secreted=false · co-receptor=None · masking=false · restricted-subdomain=false |
| Evidence | grade=Direct, multi-method · density=High · live-cell-surface=true · supporting(hi)=9 · contradicting(hi)=0 |
| Cross-species | mouse=— · cyno=— |
| Paralogs | max %ECD identity = no Compara paralogs |
| Topology | TM=1 · N-term-ECF=true · C-term-ECF=false |

**Facet rationales**

- *Expression level*: High expression on NK and CD8+ T cell subsets in peripheral blood and tumor-infiltrating contexts (a1_evi_10, a1_evi_15, a2_evi_06); low-to-moderate on CD4+ T cells and Tregs (a2_evi_06, a2_evi_04); absent on B cells, monocytes, neutrophils (a2_evi_03).
- *Expression breadth*: Expression is confined to hematopoietic cytotoxic lymphocytes (NK, NKT, γδ T, CD8+ T cells) and absent on non-lymphoid immune cells and non-hematopoietic tissues under normal conditions (a2_evi_01, a2_evi_02, a2_evi_03).
- *Surface specificity*: Live-cell flow confirms surface PVRIG on NK and T cells (a1_evi_10, a1_evi_17), but permeabilized staining shows cytoplasmic pool exceeds surface pool especially on CD56bright NK cells (a1_evi_18, a2_evi_26); constitutive ER/Golgi trafficking maintains the surface fraction (a1_evi_19).
- *Known ligand*: PVRIG binds PVRL2 (Nectin-2/CD112) as its validated endogenous ligand; the 2.2 Å crystal structure of the PVRIG ECD–Nectin-2 complex defines the binding interface (a1_evi_21, a1_evi_22).
- *Low endogenous expression*: High expression on NK and CD8+ T cell subsets in peripheral blood and tumor-infiltrating contexts (a1_evi_10, a1_evi_15, a2_evi_06); low-to-moderate on CD4+ T cells and Tregs (a2_evi_06, a2_evi_04); absent on B cells, monocytes, neutrophils (a2_evi_03).
- *Overexpression surface localization*: 1 method observation(s) pair an overexpression/mixed expression system with a surface-localization readout (cites a1_evi_01, a1_evi_03).

**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 33170010](https://pubmed.ncbi.nlm.nih.gov/33170010/)).

## 3. Surface evidence

**Evidence grade** · Direct, multi-method

Multiple distinct direct-surface-accessibility method types support PVRIG surface expression on human immune cells. (1) Live-cell flow cytometry (non-permeabilized) with an explicit non-perm surface staining protocol (FcR block + viability dye exclusion) detected PVRIG on primary human NK cells (CD56dimCD16+ subset) in AML patient PBMCs and BMMCs (a1_evi_15, a1_evi_16), on resting primary human NK cells with activation-dependent downregulation (a1_evi_17), and on CD103+ T cell subsets in human bone marrow samples (a1_evi_25, a1_evi_26). (2) Functional surface-blockade assays: COM701 blocked PVRIG–PVRL2 interaction on intact primary T/NK cells (a1_evi_08); a bispecific antibody blocked PVRIG–CD112 on intact T and NK cells with functional T-cell and NK-cell enhancement (a1_evi_24); ER/Golgi trafficking to the cell surface confirmed by intracellular trafficking inhibitor assay in NK cells (a1_evi_19); anti-PVRIG antibody blockade enhanced NK killing of AML lines (a1_evi_20). The permeabilized-flow finding of a larger cytoplasmic pool than surface pool on CD56bright NK cells (a1_evi_18) describes pool distribution, not absence of surface expression, and is tangential (not contradictory) given the direct surface evidence. Graded direct_multi_method (live-cell flow + functional surface blockade across multiple independent human primary-cell studies).

**Claim stances** *(what the grade weighs)*

| Claim | Stance | Weight | Note |
|---|---|---|---|
| a1_evi_01 | Supports Surface | Moderate | CHO-huPVRIG stable OE line used for live-cell surface binding; confirms PVRIG traffics to PM in overexpression model |
| a1_evi_02 | Tangential | Low | Antibody provenance description; no direct surface assay readout |
| a1_evi_03 | Supports Surface | Moderate | Live-cell flow binding assay on CHO-huPVRIG, EC50=2.03 nM; direct surface readout in OE cells |
| a1_evi_04 | Supports Surface | Moderate | High-affinity ECD binding (Kd=0.53 nM) and PVRL2 blockade; therapeutic antibody ECD engagement |
| a1_evi_05 | Supports Surface | Moderate | COM701 generated against human PVRIG-Fc; functional surface blockade antibody production confirms ECD accessibility |
| a1_evi_06 | Tangential | Low | Clinical antibody format description; no independent surface readout |
| a1_evi_07 | Tangential | Low | Lentiviral OE methodology; no direct surface readout |
| a1_evi_08 | Supports Surface | High | COM701 blocks PVRIG-PVRL2 on intact immune cells; functional surface engagement confirmed in primary T/NK cells |
| a1_evi_09 | Tangential | Moderate | Review-level receptor topology description; confirms coinhibitory TM receptor with ECD, but no primary surface assay |
| a1_evi_10 | Supports Surface | High | Live flow cytometry surface detection of PVRIG on primary human NK, NKT, γδ, CD8+, CD4+ T cells |
| a1_evi_11 | Supports Surface | Moderate | Surface PVRIG on murine NK/NKT cells by flow; non-human but corroborates conserved surface expression |
| a1_evi_12 | Supports Surface | Moderate | Surface PVRIG protein on murine CD8+ T cells ex vivo and activated; non-human species |
| a1_evi_13 | Supports Surface | Moderate | Surface PVRIG on tumor-infiltrating CD8+ T cells in mouse tumor model; non-human, disease-relevant context |
| a1_evi_14 | Expression Only | Low | qPCR transcript levels in murine NK/NKT/T/B cells; RNA only, no surface assay |
| a1_evi_15 | Supports Surface | High | Live-cell flow surface phenotyping of PVRIG+ on CD56dimCD16+ NK cells in AML primary patient samples |
| a1_evi_16 | Supports Surface | High | Non-permeabilized surface staining protocol confirmed (FcR block + viability dye on unfixed PBMCs/BMMCs from AML) |
| a1_evi_17 | Supports Surface | High | Live-cell surface flow showing dynamic PVRIG downregulation upon NK activation in primary human NK cells |
| a1_evi_18 | Tangential | Moderate | Permeabilized flow shows larger cytoplasmic pool vs surface pool on CD56bright NK cells; quantifies distribution, doesn't refute surface presence |
| a1_evi_19 | Supports Surface | High | Functional assay: ER/Golgi-mediated continual trafficking to cell surface in resting and activated NK cells |
| a1_evi_20 | Supports Surface | High | Anti-PVRIG blockade enhances NK killing of AML lines; functional surface engagement on primary human NK cells |
| a1_evi_21 | Tangential | High | Crystal structure of PVRIG ECD in complex with Nectin-2; confirms folded extracellular Ig domain but not PM anchoring per se |
| a1_evi_22 | Tangential | High | 2.2Å crystal structure of CD112R ECD bound to CD112; topology confirmation, not direct surface-anchoring evidence |
| a1_evi_23 | Tangential | Moderate | Review-level receptor function description; supports topology but is secondary assertion |
| a1_evi_24 | Supports Surface | High | Bispecific Ab blocks PVRIG-CD112 on intact T and NK cells; functional surface engagement confirmed in primary human cells |
| a1_evi_25 | Supports Surface | Moderate | Multiparametric live-cell flow cytometry for PVRIG surface expression on bone marrow CD3+ T cells in clinical samples |
| a1_evi_26 | Supports Surface | High | Live flow: significantly increased PVRIG surface expression on CD103+ T cell subsets in bone marrow involvement, primary clinical samples |
| a1_evi_27 | Expression Only | Moderate | IHC on colorectal cancer TME; protein detected on CD8+ T cells but membrane scoring unspecified |
| a1_evi_28 | Expression Only | Low | IHC + RT-PCR on placental tissue; no membrane-specific scoring, surface accessibility unconfirmed |
| a1_evi_29 | Expression Only | Moderate | IHC on COAD tumor sections; immune cell PVRIG protein confirmed but no membrane scoring |

### Flow cytometry (6 methods)

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Overexpression*

**Antibodies**

- anti-PVRIG (IBI352g4a) (ch44G1 · Innovent Biologics) — Extracellular epitope; Monoclonal; None validation (None); Humanized IgG1 derived from murine clone ch44G1; targets human PVRIG ECD; specificity stated; no KO validation mentioned for flow panel.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| GS-CHO cells stably overexpressing human PVRIG (CHO-huPVRIG); cell binding assay EC50 = 2.03 nM confirming surface-accessible PVRIG | Established Cell Line | High | 1 |

*Overexpression construct* — SP source: Unspecified · cell line: GS-CHO. *(cites: a1_evi_01, a1_evi_03)*

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-PVRIG — Unknown epitope; Unknown; None validation (None); Antibody clone and vendor not specified in source; described as detecting PVRIG surface protein in primary human and murine lymphocytes.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Primary human circulating NK, NKT, γδ T, CD8+ T, and CD4+ T cells (PBMCs) under physiologic conditions; PVRIG detectable on surface, highest on NK/NKT | Primary Human Cell | Moderate | 1 |
| Murine NK and NKT cells constitutively express PVRIG at cell surface | Primary Human Cell | Moderate | 1 |
| Murine CD8+ T cells ex vivo (lower level than human); surface PVRIG upregulated upon activation | Ex Vivo | Low | 1 |
| Murine tumor-infiltrating CD8+ T cells in mouse tumor microenvironment; surface PVRIG detected | Ex Vivo | Moderate | 1 |

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-PVRIG — Unknown epitope; Unknown; None validation (None); Specific clone not identified in source; multiparametric panel included FcR blocking and viability dye exclusion confirming non-permeabilized surface staining.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| CD56dimCD16+ NK cell subset in AML patient peripheral blood and bone marrow mononuclear cells; PVRIG+ cells cluster on this subset by surface flow cytometry | Patient Sample | Moderate | 1 |

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-PVRIG (Compugen) — Extracellular epitope; Unknown; None validation (None); Anti-PVRIG blocking antibody provided by Compugen, USA Inc.; clone not specified in published methods; presumed to target PVRIG ECD given blocking activity.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Primary human NK cells (resting); surface PVRIG detectable; expression reduced upon IL-2/IL-12 activation | Primary Human Cell | Moderate | 1 |

#### Fixed Cell Flow — Expression Only · Intracellular Pool

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-PVRIG (Compugen) — Unknown epitope; Unknown; None validation (None); Anti-PVRIG antibody provided by Compugen; intracellular staining condition; clone not specified.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| CD56bright NK cells (resting and IL-2/IL-12 activated); cytoplasmic PVRIG levels exceed surface levels; cytoplasmic pool further increased on activation | Primary Human Cell | High | 1 |

#### Live Cell Flow — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-PVRIG — Unknown epitope; Unknown; None validation (None); Antibody clone and vendor not specified; used in multiparametric flow cytometry panel for exhaustion/checkpoint marker surface staining on CD3+ T cells.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| CD3+ T cells from bone marrow (bone marrow malignancy involvement vs. normal controls); multiparametric surface staining for PVRIG and co-checkpoint markers | Patient Sample | Moderate | 1 |
| CD103+ CD4+ and CD8+ T cells from bone marrow involvement patient samples; PVRIG expression and co-expression with TIGIT, KIR2DL5, CD39 significantly increased vs. controls | Patient Sample | High | 1 |

### Immunohistochemistry (3 methods)

#### Unknown — Expression Only · Unclear

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-CD112R (anti-PVRIG) — Unknown epitope; Unknown; None validation (None); Antibody clone and vendor not specified; used for spatial IHC scoring of CD112R on CD8+ T cells in colorectal cancer TMA; no membranous scoring reported.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| CD8+ T cells in colorectal cancer tumor microenvironment (T cell nests and invasive margin); CD112R expression elevated vs. other tumor compartments | Primary Human Tissue | High | 1 |

#### Unknown — Expression Only · Unclear

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-PVRIG — Unknown epitope; Unknown; None validation (None); Antibody clone and vendor not specified; used for IHC of placental tissue alongside RT-PCR; no membranous scoring reported.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Placental tissue from healthy controls, early-onset preeclampsia, and late-onset preeclampsia; PVRIG evaluated by IHC alongside RT-PCR | Primary Human Tissue | Moderate | 1 |

#### Unknown — Expression Only · Unclear

*Permeabilization: Permeabilized · expression: Endogenous*

**Antibodies**

- anti-PVRIG — Unknown epitope; Unknown; None validation (None); Antibody clone and vendor not specified; used for IHC on paraffin-embedded COAD patient sections; no membranous scoring reported.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Immune cells in colon adenocarcinoma (COAD) patient tumor sections; PVRIG expression confirmed on immune cells by IHC | Primary Human Tissue | Moderate | 1 |

### Functional surface assay (3 methods)

#### Unknown — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-PVRIG (COM701) (Compugen) — Extracellular epitope; Monoclonal; None validation (None); Humanized hinge-stabilized IgG4; generated vs. human PVRIG-Fc immunogen (ECD); fully blocks PVRIG-PVRL2 interaction; no KO validation cited for this functional assay.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Primary human T cells and NK cells (resting/activated); COM701 blocks PVRIG-PVRL2 interaction on intact live cells, confirming extracellular accessibility of PVRIG | Primary Human Cell | Moderate | 1 |

#### Unknown — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-PVRIG (Compugen) — Extracellular epitope; Unknown; None validation (None); Anti-PVRIG blocking antibody provided by Compugen; clone not specified; presumed ECD-targeting given ligand-blocking activity.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Primary human NK cells (resting and activated); PVRIG continually transported to cell surface via ER/Golgi; constitutive surface delivery documented | Primary Human Cell | Low | 1 |
| Primary human NK cells co-cultured with PVRL2+ AML cell lines; PVRIG blockade significantly enhanced NK cell killing and degranulation against primary AML blasts | Primary Human Cell | Moderate | 1 |

#### Unknown — Direct Surface Accessibility · Surface Accessible

*Permeabilization: Live Cell · expression: Endogenous*

**Antibodies**

- anti-PVRIG (BsAb nanobody arm) — Extracellular epitope; Monoclonal; None validation (None); Anti-PVRIG nanobody fused to anti-TIGIT IgG1; fully blocks PVRIG-CD112 interaction; no clone identifier provided for the nanobody arm.

**Observations**

| Context | Sample | Level | Cites |
|---|---|---|---|
| Primary human T cells and NK cells (activated); bispecific anti-TIGIT×PVRIG antibody blocks PVRIG-CD112 interaction, increasing T-cell activation 2.8-fold and NK-cell cytotoxicity 1.8-fold | Primary Human Cell | Moderate | 1 |

**Non-surface expression**

| Context | Sample | Measurement | Level | Cites |
|---|---|---|---|---|
| Murine NK, NKT, CD4+ T, CD8+ T, and B cells — steady-state transcript levels by qPCR | Primary Human Cell | RNA | High | 1 |
| CD8+ T cells in colorectal cancer tumor microenvironment — spatial IHC without membrane scoring | Primary Human Tissue | IHC Protein | Moderate | 1 |
| Placental tissue from preeclampsia and healthy controls — IHC and RT-PCR without membrane-specific scoring | Primary Human Tissue | IHC Protein | Moderate | 1 |
| Immune cells in COAD (colon adenocarcinoma) tumor sections — IHC without membrane scoring | Primary Human Tissue | IHC Protein | Moderate | 1 |

**Contradicting evidence**

- *Intracellular Pool* (severity Moderate): In human CD56bright NK cells, PVRIG protein is present at higher levels in the cytoplasm than on the cell surface, as measured by flow cytometry with permeabilization. This intracellular dominance is further amplified following IL-2/IL-12 activation, suggesting that the primary cellular pool of PVRIG in this NK cell subset is intracellular rather than surface-displayed.
  - Likely explanation: Permeabilized staining detects the total cellular pool (ER, Golgi, cytoplasmic vesicles, plus surface), so the cytoplasmic signal may reflect protein in transit or storage compartments. Surface PVRIG may still be functionally relevant even if numerically outnumbered by intracellular stores; the IL-2/IL-12-induced increase in cytoplasmic levels likely reflects upregulated synthesis or intracellular retention rather than loss of surface expression per se. The finding is cell-type-specific to CD56bright NK cells and may not generalize to other lymphocyte populations.

## 4. Biological context

**Biological-context grade** · Rich

All four A2 axes are well-populated from independent sources. Expression is mapped across ≥10 cell types and ≥15 tissues/cancer contexts (primary flow, IHC, RNA-seq, qPCR). Subcellular localization is pinned: cytoplasmic pool > surface, ER/Golgi trafficking documented. Anatomical accessibility spans peripheral blood, bone marrow, solid tumor TME, and placenta. Modulation is richly evidenced: activation upregulates PVRIG on CD8+ T cells but downregulates surface PVRIG on NK cells, with disease-state variation (AML, BoM, AS, cancer TME). The NK activation discrepancy is state-context variation, not contradiction. Coherent and multi-sourced across all axes. *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06, a2_evi_07, a2_evi_08, +22)*

**Expression × cell type × disease context**

| Tissue | Cell type | Disease context | Level (protein) | Cell states |
|---|---|---|---|---|
| peripheral blood | T cells | Normal | High | — |
| peripheral blood | CD8+ T cells | Normal | High | — |
| peripheral blood | NK cells | Normal | High | activated |
| peripheral blood | NKT cells | Normal | Moderate | — |
| peripheral blood | γδ T cells | Normal | Moderate | — |
| peripheral blood | CD4+ T cells | Normal | Low | — |
| peripheral blood | regulatory T cells (Tregs) | Normal | Low | — |
| peripheral blood | B cells | Normal | Absent | — |
| peripheral blood | monocytes | Normal | Absent | — |
| peripheral blood | neutrophils | Normal | Absent | — |
| peripheral blood | CD4+ T cells | Other Disease (ankylosing spondylitis) | Low | — |
| bone marrow | CD56dim CD16+ NK cells | Other Disease (acute myeloid leukemia (AML)) | Moderate | — |
| bone marrow | CD8+ T cells | Tumor (breast cancer, prostate cancer, NSCLC, multiple myeloma (bone marrow involvement)) | Moderate | — |
| bone marrow | cytotoxic NK cells | Tumor (breast cancer, prostate cancer, NSCLC, multiple myeloma (bone marrow involvement)) | Moderate | — |
| bone marrow | CD3+ T cells | Other Disease (monosomy 7 MDS/AML) | High | — |
| bone marrow | NK cells | Other Disease (monosomy 7 MDS/AML) | High | — |
| bone marrow | CD103+ CD4+ T cells | Tumor (bone metastasis) | High | — |
| bone marrow | CD103+ CD8+ T cells | Tumor (bone metastasis) | High | — |
| solid tumor (multiple types) | tumor-infiltrating T cells | Tumor (multiple solid tumor types) | High | — |
| colon adenocarcinoma | tumor-infiltrating immune cells | Tumor (colon adenocarcinoma) | Moderate | — |
| colorectal cancer | CD8+ T cells | Tumor (colorectal cancer) | High | proliferating, activated |
| colorectal cancer | tumor-infiltrating lymphocytes | Tumor (colorectal cancer) | Moderate | — |
| lung | tumor-infiltrating lymphocytes | Tumor (non-small cell lung cancer (NSCLC)) | Moderate | — |
| liver | — | Normal | Low | — |
| liver | — | Tumor (hepatocellular carcinoma) | High | — |
| stomach | — | Tumor (stomach adenocarcinoma (STAD)) | High | — |
| stomach | — | Tumor Adjacent (stomach adenocarcinoma (STAD) adjacent normal) | Unknown | — |
| kidney | — | Tumor (renal papillary cell carcinoma (KIRP) / clear-cell renal carcinoma (KIRC)) | High | — |
| kidney | — | Tumor Adjacent (renal carcinoma (KIRP/KIRC) adjacent normal) | Unknown | — |
| esophagus | — | Tumor (esophageal carcinoma (ESCA)) | High | — |
| esophagus | — | Tumor Adjacent (esophageal carcinoma (ESCA) adjacent normal) | Unknown | — |
| bladder | — | Tumor (bladder urothelial carcinoma (BLCA)) | Low | — |
| bladder | — | Tumor Adjacent (bladder urothelial carcinoma (BLCA) adjacent normal) | Unknown | — |
| colon | — | Tumor (colon adenocarcinoma (COAD)) | Low | — |
| colon | — | Tumor Adjacent (colon adenocarcinoma (COAD) adjacent normal) | Unknown | — |
| lung | — | Tumor (lung squamous cell carcinoma (LUSC)) | Low | — |
| lung | — | Tumor Adjacent (lung squamous cell carcinoma (LUSC) adjacent normal) | Unknown | — |
| thyroid | — | Tumor (thyroid carcinoma (THCA)) | Low | — |
| uterus | — | Tumor (uterine corpus endometrial carcinoma (UCEC)) | Low | — |
| lymph node / lymphoma | — | Tumor (diffuse large B-cell lymphoma (DLBC)) | High | — |
| head and neck | — | Tumor (head and neck squamous cell carcinoma (HNSC)) | High | — |
| skin | — | Tumor (skin cutaneous melanoma (SKCM)) | High | — |
| testis | — | Tumor (testicular germ cell tumor (TGCT)) | High | — |
| thymus | — | Tumor (thymoma (THYM)) | High | — |
| bone marrow / blood | — | Tumor (acute myeloid leukemia (LAML)) | High | — |
| placenta | — | Normal | Moderate | — |
| placenta | — | Other Disease (early-onset preeclampsia) | High | — |
| placenta | — | Other Disease (late-onset preeclampsia) | High | — |
| peripheral blood (mouse) | NK cells | Normal | High | — |
| peripheral blood (mouse) | NKT cells | Normal | High | — |
| peripheral blood (mouse) | CD4+ T cells | Normal | Low | — |
| peripheral blood (mouse) | CD8+ T cells | Normal | Low | — |
| peripheral blood (mouse) | B cells | Normal | Absent | — |
| peripheral blood (mouse) | CD8+ T cells | Normal | Moderate | in vitro activated |
| tumor microenvironment (mouse syngeneic) | CD8+ T cells | Tumor (syngeneic mouse tumor model) | Moderate | — |

**Primary subcellular compartment**: Plasma membrane

**Dual localization**

- Cytosol · dominant pool in CD56bright NK cells; further increased upon IL-2/IL-12 activation *(cites: a2_evi_26)*
- ER · transit compartment en route to plasma membrane *(cites: a2_evi_27)*
- Golgi · transit compartment en route to plasma membrane *(cites: a2_evi_27)*

**Membrane subdomains**: Immune Synapse

**Accessibility modulation**

- *Tissue Restricted Surface* · lineage: Hematopoietic: null → null — PVRIG surface expression is restricted to hematopoietic lymphocytes (NK cells, NKT cells, γδ T cells, CD8+ T cells, and to a lesser extent CD4+ T cells) in peripheral blood; absent on B cells, monocytes, and neutrophils. *(→ An Extracellular Binder Targeting PVRIG Will Only Engage Hematopoietic Cytotoxic Lymphocyte Subsets; Non-Lymphoid Immune Cells Are Non-Targets By Virtue Of Absent Surface Expression.)* *(cites: a2_evi_01, a2_evi_02, a2_evi_03, a2_evi_04, a2_evi_05, a2_evi_06)*
- *Activation Induced* · trigger: Immune Activation: resting mouse CD8+ T cells → in vitro activated mouse CD8+ T cells — Mouse CD8+ T cells upregulate Pvrig expression upon in vitro activation, though more slowly than Tigit. *(→ Activation Increases PVRIG Surface Availability On CD8+ T Cells, Making The Target More Accessible To Antibody Blockade In Effector States.)* *(cites: a2_evi_22)*
- *Activation Induced* · trigger: Immune Activation: resting human NK cells → activated human NK cells (tumor recognition, IL-2/IL-12, CD16/NKp46 crosslinking, or ADCC) — NK cell activation via multiple stimuli (tumor recognition, cytokines, receptor crosslinking, ADCC) consistently reduces PVRIG surface levels on human NK cells. *(→ Acutely Activated NK Cells Display Less Surface PVRIG, Reducing Antibody-Accessible Target Density Precisely When NK Cells Are Engaged In Cytotoxic Activity.)* *(cites: a2_evi_25, a2_evi_24)*
- *Dual Localization*: null → null — In human NK cells (especially CD56bright subset), PVRIG protein is present at higher levels in the cytoplasm than on the cell surface. After IL-2/IL-12 activation, cytoplasmic PVRIG further increases on CD56bright NK cells. PVRIG is constitutively trafficked to the surface via the ER-Golgi pathway. *(→ The Dominant Intracellular Pool Means Only A Fraction Of Total PVRIG Protein Is Surface-Exposed And Accessible To Extracellular Binders; Activation Further Skews The Balance Toward Intracellular In CD56bright NK Cells.)* *(cites: a2_evi_26, a2_evi_27)*
- *Disease State Induced* · trigger: Oncogenic Transformation: normal tissue T cells (multiple solid tumor types) → tumor-infiltrating T cells in human solid tumors — PVRIG expression on T cells is increased relative to normal tissue in human solid tumors, trending with TIGIT and PD-1 co-expression across multiple cancer types. *(→ Elevated PVRIG Surface Levels On TILs In The Tumor Microenvironment Enhance Target Accessibility For Therapeutic Antibodies In Solid Tumor Indications.)* *(cites: a2_evi_12, a2_evi_15)*
- *Disease State Induced* · trigger: Oncogenic Transformation: non-proliferating CD8+ T cells in colorectal cancer TME → proliferating CD8+ T cells in colorectal cancer TME — Proliferating CD8+ TILs show significantly higher CD112R (PVRIG) expression than non-proliferating CD8+ TILs across all tumor compartments (P<0.001); highest mean expression at the invasive margin. *(→ Actively Proliferating/Activated CD8+ TILs Carry More Surface PVRIG, Making Them Preferential Targets For Anti-PVRIG Therapy Within The Tumor.)* *(cites: a2_evi_14, a2_evi_29)*
- *Disease State Induced*: CD3+ T cells and NK cells in healthy/control bone marrow → CD3+ T cells and NK cells in bone marrow from monosomy 7 MDS/AML patients — PVRIG expression is significantly increased on CD3+ T cells and NK cells in monosomy 7 myeloid neoplasm (MDS/AML) patients vs controls, concomitant with decreased DNAM-1 expression. *(→ Disease-Driven Upregulation Of PVRIG On Immune Cells In The Leukemic Bone Marrow Enhances Target Accessibility For PVRIG-Directed Therapy In These Hematologic Malignancies.)* *(cites: a2_evi_11)*
- *Disease State Induced* · trigger: Oncogenic Transformation: CD103+ T cells in non-malignant bone marrow controls → CD103+ T cells (CD4+ and CD8+) in bone metastasis — PVRIG expression and co-expression with other inhibitory receptors is significantly increased on CD103+ tissue-resident T cells (both CD4+ and CD8+ compartments) in bone metastasis vs non-malignant bone marrow controls. *(→ Disease-Induced Upregulation On Tissue-Resident T Cells In Bone Metastasis Increases Surface PVRIG Availability For Therapeutic Targeting In Metastatic Disease.)* *(cites: a2_evi_30)*
- *Disease State Induced*: CD4+ T cells in healthy controls → CD4+ T cells in ankylosing spondylitis patients — PVRIG (CD112R) is significantly downregulated on CD4+ T cells in ankylosing spondylitis patients vs healthy controls by both transcriptomic analysis and flow cytometry. *(→ Reduced Surface PVRIG On CD4+ T Cells In AS Patients May Limit Target Accessibility For Anti-PVRIG Therapy In This Autoimmune Disease Context.)* *(cites: a2_evi_21)*
- *Disease State Induced*: placental tissue in healthy pregnancy → placental tissue in early-onset preeclampsia (EOP) — PVRIG protein expression (IHC H-score) and mRNA (twofold increase) are elevated in placental tissue in early-onset preeclampsia compared to healthy pregnancy controls. *(→ Elevated PVRIG In EOP Placenta Suggests Increased Surface Availability In This Disease Context; Relevance For Therapeutic Targeting Depends On The Cell Type Bearing PVRIG.)* *(cites: a2_evi_20)*
- *Disease State Induced*: NK cells in healthy donor bone marrow → NK cells in AML patient bone marrow — Despite PVRL2 expression on AML blasts, NK cell PVRIG expression levels in AML patient bone marrow are not increased compared to healthy donors, contradicting the upregulation pattern seen in solid tumors. *(→ Lack Of PVRIG Upregulation On NK Cells In AML Bone Marrow Means The Tumor Microenvironment Does Not Enhance Target Accessibility In This Hematologic Disease Context.)* *(cites: a2_evi_28)*

**Restricted-subdomain distribution**

- present: false
- severity: Low
- evidence: Moderate
- domain: Unknown
- rationale: PVRIG surface staining is detected broadly on circulating NK, NKT, γδ T, CD8+ and CD4+ T cells by flow cytometry (a1_evi_10, a2_evi_06) and on tumor-infiltrating lymphocytes across multiple tumor types (a1_evi_13, a2_evi_15). Antibody blockade works on intact primary cells with no polarized-epithelium or subdomain restriction reported. No ledger entry documents apical, junctional, ciliary, or other subdomain restriction.
- cites: a1_evi_10, a1_evi_13, a2_evi_06, a2_evi_15

**Co-receptor requirements**

- dependency: None
- evidence basis: Trafficking
- rationale: PVRIG traffics independently to the cell surface via ER/Golgi in both resting and activated NK cells (a1_evi_19, a2_evi_27). Multiple therapeutic antibodies (COM701, IBI352g4a, bispecific) bind the PVRIG ECD on intact primary lymphocytes and overexpressing CHO cells without any co-receptor requirement (a1_evi_03, a1_evi_08). No chaperone or obligate partner for surface delivery is documented in the ledger.
- cites: a1_evi_03, a1_evi_08, a1_evi_19, a2_evi_27

## 5. Isoforms, orthologs & paralogs

*Deterministic · UniProt + DeepTMHMM deeptmhmm-1.0.24 · Ensembl —. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*

| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |
|---|---|---|---|---|---|---|---|---|---|---|
| Isoform | **canonical** | Q6DKI7 | ref | ref | 1 | 132 aa | 134 aa | 39 aa | Extracellular→Cytoplasmic | — |

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

- ECD class: Moderate
- rationale: ECD length 132 residues (60-199) -> moderate; computed deterministically from DeepTMHMM topology.

**Epitope masking**

- severity: Low
- evidence: Moderate
- mechanism: Partner
- rationale: The PVRIG ECD binds its ligand PVRL2/Nectin-2 in trans (on opposing cells), not in cis on the same cell surface, so ligand engagement is an intermittent trans interaction rather than constitutive masking. The 2.2 Å crystal structure defines the ECD–Nectin-2 interface (a1_evi_22, a1_evi_21), and clinical antibodies (COM701, IBI352g4a) fully block this interaction, implying the epitope is accessible in the free receptor state (a1_evi_04, a1_evi_08). Homo-oligomerization is not predicted (is_homo_oligomer=false) and the ledger contains no homo-oligomer evidence. Severity is low because cis partner masking is not documented.
- cites: a1_evi_04, a1_evi_08, a1_evi_21, a1_evi_22

**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).

## 7. Structure summary

| Field | Value |
|---|---|
| AFDB ID | [AF-Q6DKI7-F1](https://alphafold.ebi.ac.uk/entry/Q6DKI7) |
| AFDB version | v6 |
| ECD mean pLDDT | 76.4 |
| ECD disordered fraction | 33.3% |

Structure data from [AlphaFold DB](https://alphafold.ebi.ac.uk/entry/Q6DKI7) · © DeepMind / EMBL-EBI · licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · cite `10.1038/s41586-021-03819-2`; `10.1093/nar/gkad1011`.

*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*

**Model variants & experimental structures**

| Structure | UniProt / PDB | Source |
|---|---|---|
| Canonical | [Q6DKI7](https://alphafold.ebi.ac.uk/entry/Q6DKI7) | AlphaFold DB (AF-Q6DKI7-F1, v6) |

## 8. SURFACE-Bind candidate sites

*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*

No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).

## 9. Evidence ledger

59 entries · 41 primary · 18 secondary · 0 tertiary · 39 PMC OA.

- `a1_evi_01` · *Secondary* · Supports · Methodological — GS-CHO stable cell lines overexpressing human PVRIG were generated using the Lonza GS Xceed system, providing the host system for surface-binding assays. This confirms a cell-based overexpression model with endogenous-sequence PVRIG (construct details: stable integration, full-length human PVRIG). OE construct SP source not specified in this clip. ([PMC10981589](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10981589/))
  - *assay*: Human · GS-CHO · live · non-permeabilized
  > "GS-CHO stable cell lines overexpressing human PVRIG or cynomolgus monkey PVRIG (cynoPVRIG) were generated according to the manufacturer’s instructions using the GS Xceed Expression System (Lonza) and cultured in CD CHO medium (Gibco, Grand Island, NY, USA) supplemented with 75 μM MSX (Sigma)."
- `a1_evi_02` · *Secondary* · Supports · Methodological — IBI352g4a is a humanized IgG1 antibody derived from murine clone ch44G1 that targets the human PVRIG extracellular domain. This is an anti-PVRIG therapeutic antibody with defined clone provenance (ch44G1 parent); relevant for antibody identity and ECD-targeting specificity in surface-method observations. ([PMC10981589](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10981589/))
  - *assay*: Human
  > "IBI352g4a, a humanized IgG1 PVRIG antibody derived from the murine clone ch44G1 by hybridoma fusion, targets the human PVRIG extracellular domain."
- `a1_evi_03` · *Secondary* · Supports · Surface Expression — Cell binding assay on CHO cells stably overexpressing human PVRIG (CHO-huPVRIG) confirmed high-affinity binding of IBI352g4a (EC50 = 2.03 nM), demonstrating that PVRIG traffics to the cell surface in the overexpression model. This is a direct cell-surface binding readout on intact OE cells. OE construct SP source not specified. ([PMC10981589](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10981589/))
  - *assay*: Human · CHO-huPVRIG · live · non-permeabilized
  > "This high binding affinity was further confirmed by a cell binding assay using a human PVRIG-overexpressing GS-CHO cell line (CHO-huPVRIG) with an EC50 of 2.03 nM (Fig. 1 b)."
- `a1_evi_04` · *Primary* · Supports · Surface Expression — IBI352g4a (humanized IgG1 anti-PVRIG) binds the extracellular domain of human PVRIG with high affinity (Kd = 0.53 nM) and fully blocks PVRIG–PVRL2 interaction, constituting therapeutic-antibody engagement of the surface-accessible ECD. This is direct surface-accessibility evidence from a clinical-stage antibody program. ([PMC10981589](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10981589/))
  - *assay*: Human · live · non-permeabilized
  > "IBI352g4a binds to the extracellular domain of human PVRIG with high affinity (Kd = 0.53 nM) and specificity, and fully blocks the interaction between PVRIG and its ligand PVRL2."
- `a1_evi_05` · *Secondary* · Supports · Methodological — Anti-PVRIG antibody COM701 was generated by immunizing mice with human PVRIG-Fc fusion protein and screening for clones that bind PVRIG and disrupt PVRIG–PVRL2 interaction (hybridoma technology). Antibody provenance: anti-PVRIG blocking antibody, generated against human PVRIG ECD (Fc fusion immunogen), screened by ligand-competition. ([PMC7001734](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7001734/))
  - *assay*: Human
  > "Anti-PVRIG was generated via hybridoma technology by immunizing mice with human PVRIG Fc and screening for antibodies that bind to human PVRIG and disrupt PVRIG–PVRL2 interactions."
- `a1_evi_06` · *Secondary* · Supports · Methodological — COM701 is a humanized anti-PVRIG hinge-stabilized IgG4 antibody (clinical-stage); this is the reference therapeutic binder to the PVRIG ECD. Its IgG4 hinge-stabilized format and humanization confirm it as a fully characterized clinical antibody targeting surface PVRIG. ([PMC7001734](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7001734/))
  - *assay*: Human
  > "COM701 is a humanized anti-PVRIG hinge-stabilized IgG4."
- `a1_evi_07` · *Secondary* · Supports · Methodological — Ectopic (overexpression) of human PVRIG was achieved by lentiviral transduction (Systems Biosciences) in the experimental cell system used for functional studies. This establishes a cell-based OE model that supports surface-localization validation experiments. ([PMC7001734](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7001734/))
  - *assay*: Human · lentivirus-transduced cells
  > "Ectopic expression of human PVRIG, human TIGIT, luciferase reporter gene, or a cell-surface anti-CD3 construct ( 23 ) was performed by lentivirus transduction (Systems Biosciences)."
- `a1_evi_08` · *Primary* · Supports · Surface Expression — COM701, a high-affinity humanized anti-PVRIG antibody, blocks the interaction of PVRIG with its ligand PVRL2 (see Fig. 1A). This therapeutic engagement of the PVRIG ECD on intact immune cells confirms surface accessibility of the extracellular domain for antibody binding and ligand competition. ([PMC7001734](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7001734/))
  - *assay*: Human · primary T/NK cells · live · non-permeabilized
  > "For PVRIG, we generated a high-affinity, humanized anti-PVRIG, COM701, which blocks the interaction of PVRIG with PVRL2 ( Fig. 1A ; Supplementary Fig."
- `a1_evi_09` · *Secondary* · Supports · Topology — PVRIG is described as a coinhibitory receptor of the DNAM/TIGIT/CD96 nectin family that binds PVRL2. This establishes PVRIG topology as a transmembrane coinhibitory receptor with a surface-accessible ECD that engages the nectin ligand family. ([PMC7001734](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7001734/))
  - *assay*: Human
  > "PVRIG is a coinhibitory receptor of the DNAM/TIGIT/CD96 nectin family that binds to PVRL2."
- `a1_evi_10` · *Primary* · Supports · Surface Expression — Human PVRIG is detectable at the surface of circulating NK, NKT, γδ T, CD8+, and to a lesser extent CD4+ T cells under physiologic conditions. This is a direct surface-detection statement in primary human lymphocytes (implied flow cytometry, established by the group describing PVRIG as CD112R). ([PMC7038785](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7038785/))
  - *assay*: Human · NK, NKT, γδ, CD8+ T, CD4+ T cells (PBMCs) · live · non-permeabilized
  > "In the physiologic setting, human Pvrig is detectable in circulating NK, NKT, γδ, CD8 + , and to a lesser extent in CD4 + T cells ( 10 )."
- `a1_evi_11` · *Primary* · Supports · Surface Expression — Murine NK and NKT cells constitutively express PVRIG at the cell surface, paralleling human expression. This demonstrates conserved surface expression across species in primary lymphocytes. ([PMC7038785](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7038785/))
  - *assay*: Mouse · NK and NKT cells · live · non-permeabilized
  > "As in humans, murine NK and NKT cells constitutively expressed PVRIG."
- `a1_evi_12` · *Primary* · Supports · Surface Expression — Surface PVRIG protein was detected on murine CD8+ T cells ex vivo (at lower levels than in humans), with upregulation upon activation. This provides species comparison data: surface protein confirmed in both resting and activated murine CD8+ T cells by flow cytometry. ([PMC7038785](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7038785/))
  - *assay*: Mouse · CD8+ T cells · live · non-permeabilized
  > "However, when compared with humans, less PVRIG transcript and surface protein was detected in murine CD8<sup>+</sup> T cells <i>ex vivo</i> However, activated CD8<sup>+</sup> T cells upregulated PVRIG expression."
- `a1_evi_13` · *Primary* · Supports · Surface Expression — In the mouse tumor microenvironment, infiltrating CD8+ T cells express PVRIG at the cell surface (tumor-infiltrating lymphocytes), mirroring human tumor expression patterns. This constitutes surface PVRIG detection in a disease-relevant in vivo context. ([PMC7038785](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7038785/))
  - *assay*: Mouse · tumor-infiltrating CD8+ T cells · live · non-permeabilized
  > "In the mouse tumor microenvironment, infiltrating CD8<sup>+</sup> T cells expressed PVRIG whereas its ligand, PVRL2, was detected predominantly on myeloid cells and tumor cells, mirroring the expression pattern in human tumors."
- `a1_evi_14` · *Secondary* · Ambiguous · Tissue Expression — PVRIG transcript is abundant in murine NK and NKT cells by quantitative PCR; barely detectable in CD4+ and CD8+ T cells; absent in B cells. This is RNA-level expression without a co-assayed surface-fractionation step, qualifying (but not confirming) the surface claim from the paired flow cytometry data. ([PMC7038785](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7038785/))
  - *assay*: Mouse · NK, NKT, CD4+ T, CD8+ T, B cells
  > "When we examined the steady-state expression profile in mouse cells by quantitative PCR, Pvrig transcripts were abundant in NK and NKT cells, barely detectable in CD4 + and CD8 + T cells, and absent in B cells ( Fig. 1A )."
- `a1_evi_15` · *Primary* · Supports · Surface Expression — PVRIG+ cells cluster on the CD56dimCD16+ NK cell subset in AML patients, as detected by multiparametric flow cytometry (surface phenotyping) on PB and BM mononuclear cells. This is direct surface staining evidence in a disease context (AML primary patient samples). ([PMC8657570](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8657570/))
  - *assay*: Human · CD56dimCD16+ NK cells (AML patients) · live · non-permeabilized
  > "Moreover, TIGIT<sup>+</sup> and PVRIG<sup>+</sup> cells cluster on the CD56<sup>dim</sup>CD16<sup>+</sup> subset whereas CD39<sup>+</sup> and CD38<sup>+</sup> cells do so on CD56<sup>bright</sup>CD16<sup>-</sup> NK cells in AML."
- `a1_evi_16` · *Secondary* · Supports · Methodological — Flow cytometry surface staining protocol: FcR blocking (Miltenyi FcR blocking reagent) followed by viability dye (Zombie NIR) exclusion of dead cells prior to antibody staining, performed on cryopreserved PBMCs and BMMCs from AML patients. This methodological detail confirms non-permeabilized surface staining protocol for PVRIG detection. ([PMC8657570](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8657570/))
  - *assay*: Human · PBMCs and BMMCs (AML) · live · non-permeabilized
  > "After FcR blocking (FcR Blocking Reagent, human, Miltenyi Biotec, Bergisch Gladbach, Germany) for 5 min in the dark, PBMCs and BMMCs were stained with the Zombie NIR ™ Fixable Viability Kit (BioLegend, San Diego, CA, USA) for exclusion of dead cells according to the manufacturer’s instructions."
- `a1_evi_17` · *Primary* · Supports · Surface Expression — PVRIG expression on the NK cell surface is reduced upon NK cell activation, as measured by surface phenotyping. This demonstrates dynamic regulation of surface PVRIG levels and confirms the protein is present at the cell surface in resting NK cells with quantifiable surface accessibility. (https://pubmed.ncbi.nlm.nih.gov/33147937/)
  - *assay*: Human · NK cells (resting and activated) · live · non-permeabilized
  > "To understand how PVRIG blockade might potentially be exploited therapeutically, we investigated the biology of PVRIG and revealed that NK cell activation resulted in reduced PVRIG expression on the cell surface."
- `a1_evi_18` · *Primary* · Refutes · Contradictory — PVRIG is present at higher levels in the cytoplasm than on the cell surface, particularly on CD56bright NK cells, with cytoplasmic levels further increased following IL-2/IL-12 activation. This constitutes an important contradictory/qualifying finding: the dominant cellular pool is intracellular, not surface-displayed, especially for CD56bright NK cells. (https://pubmed.ncbi.nlm.nih.gov/33147937/)
  - *assay*: Human · CD56bright NK cells · fixed · permeabilized
  > "PVRIG was present at higher levels in the cytoplasm than on the cell surface, particularly on CD56bright NK cells, which further increased cytoplasmic PVRIG levels following IL-2 and IL-12 activation."
- `a1_evi_19` · *Primary* · Supports · Surface Expression — PVRIG is continually transported to the cell surface via ER/Golgi trafficking in both unstimulated and activated NK cells, confirming active secretory pathway delivery to the plasma membrane. This mechanistic finding supports constitutive surface localization despite a larger cytoplasmic pool. (https://pubmed.ncbi.nlm.nih.gov/33147937/)
  - *assay*: Human · NK cells
  > "PVRIG was continually transported to the cell surface via the endoplasmic reticulum (ER) and Golgi in both unstimulated and activated NK cells."
- `a1_evi_20` · *Primary* · Supports · Surface Expression — PVRIG blockade by anti-PVRIG antibody (Compugen-provided) significantly enhanced NK cell killing of PVRL2+/PVRlo AML cell lines and increased NK cell activation/degranulation against primary AML blasts. This functional blockade of surface PVRIG constitutes therapeutic surface-engagement evidence in human primary NK cells. (https://pubmed.ncbi.nlm.nih.gov/33147937/)
  - *assay*: Human · primary NK cells + AML cell lines · live · non-permeabilized
  > "Furthermore, PVRIG blockade significantly enhanced NK cell killing of PVRL2+, poliovirus receptor (PVR)lo AML cell lines, and significantly increased NK cell activation and degranulation in the context of patient primary AML blasts."
- `a1_evi_21` · *Primary* · Supports · Topology — Crystal structure of PVRIG ECD in complex with Nectin-2 was determined, identifying a unique CC' loop in PVRIG that contributes to the double-lock-and-key binding mode and high-affinity recognition. This structural evidence confirms the extracellular Ig domain of PVRIG is accessible and forms the ligand-binding interface. (https://pubmed.ncbi.nlm.nih.gov/38626767/)
  - *assay*: Human
  > "Nectin and nectin-like (Necl) co-receptor axis, comprised of receptors DNAM-1, TIGIT, CD96, PVRIG, and nectin/Necl ligands, is gaining prominence in immuno-oncology. Within this axis, the inhibitory receptor PVRIG recognizes Nectin-2 with high affinity, but the underlying molecular basis remains unknown. By determining the crystal structure of PVRIG in complex with Nectin-2, we identified a unique CC' loop in PVRIG, which complements the double-lock-and-key binding mode and contributes to its high affinity for Nectin-2."
- `a1_evi_22` · *Primary* · Supports · Topology — A 2.2 Å crystal structure of CD112R (PVRIG) ECD bound to domain 1 of CD112 (Nectin-2) was determined, establishing the molecular determinants of CD112R–CD112 interactions. This high-resolution structural evidence confirms the PVRIG extracellular domain is a well-folded, surface-accessible immunoglobulin domain. ([PMC12368799](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12368799/))
  - *assay*: Human
  > "We determined the 2.2 Å-resolution structure of CD112R bound to D1 of CD112 to establish the molecular determinants of CD112R-CD112 interactions ( Figure 1C and Table S1 )."
- `a1_evi_23` · *Secondary* · Supports · Topology — PVRIG (CD112R) is defined as an immune checkpoint protein that suppresses T and NK cell activation upon binding tumor-expressed CD112 (Nectin-2). This is a receptor-function description confirming surface topology: extracellular domain engages tumor-expressed ligand, establishing the protein as a cell-surface receptor. ([PMC12368799](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12368799/))
  - *assay*: Human · T cells and NK cells
  > "The immune checkpoint protein, CD112 receptor (CD112R, also known as PVRIG), suppresses T and natural killer (NK) cell activation upon binding to tumor-expressed CD112 (Nectin-2) ligands."
- `a1_evi_24` · *Primary* · Supports · Surface Expression — A bispecific antibody (BsAb) co-targeting TIGIT and PVRIG blocked both receptors from binding their respective ligands (PVRIG–CD112 interaction blocked), leading to significant T-cell activation and NK-cell cytotoxicity enhancement. This bispecific therapeutic engagement confirms surface accessibility of the PVRIG ECD on intact T and NK cells. (https://pubmed.ncbi.nlm.nih.gov/39851063/)
  - *assay*: Human · T cells and NK cells · live · non-permeabilized
  > "The results showed that the BsAb effectively blocked TIGIT and PVRIG from binding their respective ligands, CD155 and CD112, leading to significant increases in T-cell activation (2.8-fold; P < 0.05) and NK-cell cytotoxicity (1.8-fold; P < 0.05). In vivo, the BsAb demonstrated potent antitumor activity, both as a monotherapy and in combination with anti-PD-1 or anti-PD-L1, in humanized peripheral blood mononuclear cell-reconstituted and transgenic mouse models."
- `a1_evi_25` · *Secondary* · Supports · Methodological — Multiparametric flow cytometry was used to assess PVRIG expression (as an exhaustion/checkpoint marker) on CD3+ T cells from bone marrow samples (bone marrow involvement vs. normal controls). This confirms surface staining of PVRIG by flow cytometry in a clinical primary-cell context. (https://pubmed.ncbi.nlm.nih.gov/41485718/)
  - *assay*: Human · CD3+ T cells (bone marrow) · live · non-permeabilized
  > "Age-matched bone marrow samples from individuals without malignancy (NMCs) were controls. Multiparametric flow cytometry (MFC) was utilized to assess the expression of CD103 and exhaustion markers (TIGIT, PVRIG, KIR2DL5, CD39) in CD3<sup>+</sup> cells.<h4>Results</h4>CD103⁺CD3<sup>+</sup> T cells are significantly elevated in BoM compared to NMC, driven by an increase in CD103⁺CD4⁺ cells, despite a relative decrease in frequency of CD103⁺CD8⁺ cells. Furthermore, CD103<sup>+</sup>CD4<sup>+</sup> cells from BoM displayed a significantly increased fraction of the central memory (CM) phenotype."
- `a1_evi_26` · *Primary* · Supports · Surface Expression — Flow cytometry demonstrated significantly increased PVRIG expression and coexpression with TIGIT, KIR2DL5, and CD39 on CD103+ CD4+ and CD8+ T cells in bone marrow involvement samples vs. controls. This quantitative surface phenotyping result confirms PVRIG surface detection across T cell subsets in primary clinical samples. (https://pubmed.ncbi.nlm.nih.gov/41485718/)
  - *assay*: Human · CD103+ CD4+ and CD8+ T cells (bone marrow) · live · non-permeabilized
  > "Expression and coexpression of TIGIT, PVRIG, KIR2DL5 and CD39 on CD103<sup>+</sup> cells both in the CD4 and CD8 compartment was significantly increased in BoM, compared within CD103<sup>-</sup> within BoM and CD103<sup>+</sup> in NMC.<h4>Conclusion</h4>In conclusion, BoM exhibit a distinct T-cell composition, highlighted by an increase in CD103⁺CD4⁺ cells displaying an increased CM phenotype. In BoM, cregulatory receptor expression is increased on CD103⁺ T cells, with distinct coexpression signatures in both CD4⁺ and CD8⁺ cells."
- `a1_evi_27` · *Secondary* · Ambiguous · Tissue Expression — Spatial IHC analysis of CD112R (PVRIG) expression on CD8+ T cells in colorectal cancer tissue microenvironment showed elevated CD112R levels on CD8+ T cells in T cell nests and at the invasive margin. This IHC-based quantitation provides tissue-level evidence of PVRIG protein expression, though not exclusively surface-restricted without membrane scoring confirmation. (https://pubmed.ncbi.nlm.nih.gov/36788088/)
  - *assay*: Human · CD8+ T cells (colorectal cancer TME) · fixed · permeabilized
  > "Spatial analysis of locally enriched CD8<sup>+</sup> T cell density and cell-to-cell contacts identified T cell nests in the tumor microenvironment of colorectal cancer. CD112R and PD-1 expressions on CD8<sup>+</sup> T cells located in T cell nests were found to be elevated compared with those on CD8<sup>+</sup> T cells in all other tumor compartments (P < .001 each). Although the highest mean CD112R expression on CD8<sup>+</sup> T cells was observed at the invasive margin, the PD-1 expression on CD8<sup>+</sup> T cells was elevated in the center of the tumor (P < .001 each)."
- `a1_evi_28` · *Secondary* · Ambiguous · Tissue Expression — IHC and RT-PCR were used in parallel to evaluate PVRIG expression in placental tissue from preeclampsia and healthy controls. The co-deployment of IHC (protein) and RT-PCR (mRNA) without membrane-specific scoring makes surface accessibility unconfirmed; this qualifies as non-surface protein expression evidence. (https://pubmed.ncbi.nlm.nih.gov/40425968/)
  - *assay*: Human · placental tissue · fixed · permeabilized
  > "In our study, the control group consisted of placentas from healthy pregnant women, the early onset preeclampsia group (EOP) consisted of patients diagnosed before the 34th week, and the late-onset preeclampsia group (LOP) consisted of placentas from patients diagnosed at or after the 34th week. TIGIT, PVRIG, CD155, and CD112 expression in placental materials was evaluated both immunohistochemically and by RT-PCR."
- `a1_evi_29` · *Secondary* · Ambiguous · Tissue Expression — PVRIG expression on immune cells was confirmed in COAD (colon adenocarcinoma) patient tumor sections by IHC (red arrows in Fig. 1b), consistent with prior reports of immune cell expression. This is whole-tissue IHC without membrane scoring; feeds non-surface expression bucket rather than direct surface-accessibility evidence. ([PMC8236157](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8236157/))
  - *assay*: Human · immune cells in colorectal adenocarcinoma · fixed · permeabilized
  > "PVRIG was reported to express on immune cells [ 24 ]; in our study, we also confirmed the expression of PVRIG on immune cells in COAD patients, as indicated by the red arrows (Fig. 1 b)."
- `a2_evi_01` · *Secondary* · Supports · Tissue Expression — PVRIG (CD112R) is preferentially expressed on human T cells, where it acts as an inhibitory receptor suppressing T cell receptor-mediated signals. This establishes T cells as the primary human immune cell type expressing PVRIG at baseline. ([PMC4749091](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4749091/))
  - *assay*: Human · T cells
  > "CD112R is preferentially expressed on T cells and inhibits T cell receptor-mediated signals."
- `a2_evi_02` · *Primary* · Supports · Tissue Expression — PVRIG was identified through a genome-wide search for genes preferentially expressed on human T cells that encode transmembrane proteins with a single IgV extracellular domain, confirming preferential T cell expression as the basis for target selection. ([PMC4749091](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4749091/))
  - *assay*: Human · T cells (genome-wide screen)
  > "We performed an extensive genome-wide search to look for genes that are both preferentially expressed on human T cells and encode transmembrane proteins with a single IgV extracellular domain."
- `a2_evi_03` · *Secondary* · Supports · Tissue Expression — In humans, PVRIG is expressed on T cells (predominantly CD8+ T cells) and natural killer (NK) cells, but is absent on B cells, monocytes, and neutrophils. This provides a clear cell-type restriction pattern for PVRIG surface expression in peripheral blood immune cells. (https://pubmed.ncbi.nlm.nih.gov/33147937/)
  - *assay*: Human · CD8+ T cells, NK cells, B cells, monocytes, neutrophils · live · non-permeabilized
  > "Poliovirus receptor-related immunoglobulin domain-containing (PVRIG) has https://doi.org/10.3324/haematol.2020.258574 recently been identified as an immune checkpoint molecule with potential for therapeutic development. 1 In humans, PVRIG is expressed on T cells (predominantly CD8 + T cells) and natural killer (NK) cells, but not on B cells, monocytes or neutrophils. 1 PVRIG binds to a single ligand, poliovirus receptor-related 2 (PVRL2, also Material published in Haematologica is covered by copyright."
- `a2_evi_04` · *Secondary* · Supports · Tissue Expression — Unlike TIGIT, PVRIG expression is restricted to activated NK cells and T cells, with particularly high expression on cytotoxic (CD8+) lymphocytes. Expression is low on regulatory T cells (Tregs). This distinguishes PVRIG's cell-type distribution from overlapping checkpoint receptors. ([PMC10981589](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10981589/))
  - *assay*: Human · CD8+ cytotoxic T cells, NK cells, Tregs · live · non-permeabilized
  > "Unlike TIGIT, PVRIG is expressed on only activated NK cells and T cells, especially on cytotoxic lymphocytes, while it is expressed at low levels on Treg cells."
- `a2_evi_05` · *Secondary* · Supports · Tissue Expression — PVRIG is a recently identified immune checkpoint receptor predominantly expressed on natural killer and CD8+ T cells. This consensus across the recent literature confirms the primary cell types for PVRIG expression. ([PMC11982253](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11982253/))
  - *assay*: Human · NK cells, CD8+ T cells · non-permeabilized
  > "The poliovirus receptor-related immunoglobulin domain-containing protein (PVRIG) is a recently identified immune checkpoint receptor predominantly expressed on natural killer and CD8 + T cells."
- `a2_evi_06` · *Primary* · Supports · Tissue Expression — In the physiologic setting, human PVRIG is detectable in circulating NK, NKT, γδ T cells, CD8+ T cells, and to a lesser extent in CD4+ T cells. This comprehensive flow cytometry survey of peripheral blood immune subsets establishes the baseline expression hierarchy across lymphocyte subpopulations. ([PMC7038785](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7038785/))
  - *assay*: Human · NK, NKT, γδ T cells, CD8+ T cells, CD4+ T cells (peripheral blood) · live · non-permeabilized
  > "In the physiologic setting, human Pvrig is detectable in circulating NK, NKT, γδ, CD8 + , and to a lesser extent in CD4 + T cells ( 10 )."
- `a2_evi_07` · *Primary* · Supports · Tissue Expression — In mouse cells at steady state (by qPCR), Pvrig transcripts are abundant in NK and NKT cells, barely detectable in CD4+ and CD8+ T cells, and absent in B cells. This species difference—mouse NK/NKT >> T cells, vs human where CD8+ T cells also express PVRIG—is important for model translation. ([PMC7038785](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7038785/))
  - *assay*: Mouse · NK, NKT, CD4+ T cells, CD8+ T cells, B cells
  > "When we examined the steady-state expression profile in mouse cells by quantitative PCR, Pvrig transcripts were abundant in NK and NKT cells, barely detectable in CD4 + and CD8 + T cells, and absent in B cells ( Fig. 1A )."
- `a2_evi_08` · *Primary* · Supports · Tissue Expression — In AML patients, PVRIG+ cells cluster on the CD56dimCD16+ NK cell subset (cytotoxic NK cells) rather than the CD56brightCD16- subset. This identifies the specific NK cell subpopulation bearing PVRIG expression in an AML disease context, mirroring the pattern seen in healthy donors. ([PMC8657570](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8657570/))
  - *assay*: Human · CD56dimCD16+ NK cells, CD56brightCD16- NK cells (AML bone marrow and peripheral blood) · live · non-permeabilized
  > "Moreover, TIGIT<sup>+</sup> and PVRIG<sup>+</sup> cells cluster on the CD56<sup>dim</sup>CD16<sup>+</sup> subset whereas CD39<sup>+</sup> and CD38<sup>+</sup> cells do so on CD56<sup>bright</sup>CD16<sup>-</sup> NK cells in AML."
- `a2_evi_09` · *Primary* · Supports · Tissue Expression — In bone marrow aspirates from patients with breast cancer, prostate cancer, NSCLC, and multiple myeloma, BM-derived CD8+ T cells aberrantly co-express TIGIT with PVRIG (or CD39), indicating PVRIG is present on CD8+ T cells infiltrating the bone marrow in solid tumor and hematologic malignancy disease states. ([PMC12022200](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12022200/))
  - *assay*: Human · CD8+ T cells (bone marrow, cancer patients) · live · non-permeabilized
  > "BM-derived CD8<sup>+</sup> T cells aberrantly co-expressed TIGIT with PVRIG or CD39."
- `a2_evi_10` · *Primary* · Supports · Tissue Expression — BM-derived cytotoxic NK cells from cancer patients (BC, PC, NSCLC, MM) co-express TIGIT and PVRIG, indicating that PVRIG is present on NK cells infiltrating the tumor-involved bone marrow compartment. ([PMC12022200](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12022200/))
  - *assay*: Human · cytotoxic NK cells (bone marrow, cancer patients) · live · non-permeabilized
  > "Similarly, BM-derived cytotoxic NK cells co-expressed TIGIT and PVRIG."
- `a2_evi_11` · *Primary* · Supports · Tissue Expression — In patients with monosomy 7 myeloid neoplasms (MDS/AML), PVRIG expression is significantly increased on CD3+ T cells and NK cells compared to controls, concomitant with decreased DNAM-1 (CD226) expression. This represents a disease-state-induced upregulation of PVRIG on immune cells driven by leukemic cell CD112 overexpression. ([PMC13161220](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13161220/))
  - *assay*: Human · CD3+ T cells, NK cells (bone marrow, monosomy 7 MDS/AML patients) · live · non-permeabilized
  > "Concomitant increased expression of the inhibitory TIGIT and PVRIG receptors, and decreased expression of the activating DNAM1 receptor, significantly emerged in CD3+, and natural killer (NK) cells from patients with -7."
- `a2_evi_12` · *Primary* · Supports · Tissue Expression — In human solid tumors, PVRIG expression on T cells is increased relative to normal tissue and trends with TIGIT and PD-1 expression, indicating tumor microenvironment-induced upregulation of PVRIG on tumor-infiltrating T cells across multiple cancer types. ([PMC7001734](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7001734/))
  - *assay*: Human · T cells (tumor-infiltrating, multiple solid tumors) · fixed · non-permeabilized
  > "In human tumors, PVRIG expression on T cells was increased relative to normal tissue and trended with TIGIT and PD-1 expression."
- `a2_evi_13` · *Primary* · Supports · Tissue Expression — PVRIG expression was confirmed on immune cells infiltrating colon adenocarcinoma (COAD) patient tumor tissue by IHC, consistent with PVRIG being present on tumor-infiltrating lymphocytes in colorectal cancer. ([PMC8236157](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8236157/))
  - *assay*: Human · tumor-infiltrating immune cells (colon adenocarcinoma) · fixed · permeabilized
  > "PVRIG was reported to express on immune cells [ 24 ]; in our study, we also confirmed the expression of PVRIG on immune cells in COAD patients, as indicated by the red arrows (Fig. 1 b)."
- `a2_evi_14` · *Primary* · Supports · Tissue Expression — Spatial analysis in colorectal cancer tumor microenvironment shows CD112R (PVRIG) expression on CD8+ T cells is elevated in T cell nests compared to other tumor compartments (P<0.001). The highest mean CD112R expression is observed at the invasive margin. Proliferating CD8+ T cells show higher CD112R expression than non-proliferating CD8+ T cells across all compartments (P<0.001), indicating activation-associated upregulation of PVRIG in tumor-infiltrating CD8+ T cells. (https://pubmed.ncbi.nlm.nih.gov/36788088/)
  - *assay*: Human · CD8+ tumor-infiltrating T cells (colorectal cancer tissue microarray) · fixed · permeabilized
  > "Spatial analysis of locally enriched CD8<sup>+</sup> T cell density and cell-to-cell contacts identified T cell nests in the tumor microenvironment of colorectal cancer. CD112R and PD-1 expressions on CD8<sup>+</sup> T cells located in T cell nests were found to be elevated compared with those on CD8<sup>+</sup> T cells in all other tumor compartments (P < .001 each). Although the highest mean CD112R expression on CD8<sup>+</sup> T cells was observed at the invasive margin, the PD-1 expression on CD8<sup>+</sup> T cells was elevated in the center of the tumor (P < .001 each)."
- `a2_evi_15` · *Primary* · Supports · Tissue Expression — PVRIG expression was assessed on tumor-infiltrating lymphocytes from patients with NSCLC (n=63) and colorectal cancer (n=26), confirming PVRIG presence on TILs in these two solid tumor indications. (https://pubmed.ncbi.nlm.nih.gov/39851063/)
  - *assay*: Human · tumor-infiltrating lymphocytes (NSCLC, colorectal cancer) · live · non-permeabilized
  > "Expression of TIGIT and PVRIG was assessed on tumor-infiltrating lymphocytes from patients with various cancers, including non-small cell lung cancer (n = 63) and colorectal cancer (n = 26). The BsAb was engineered by fusing anti-PVRIG nanobodies to the N terminus of anti-TIGIT antibodies. Functional characterization of the BsAb was performed in vitro and in vivo, including assessments of T- and NK-cell activation and cytotoxicity. Pharmacokinetics and safety profiles were evaluated in cynomolgus monkeys. Statistical analyses were conducted using the Student t test."
- `a2_evi_16` · *Primary* · Supports · Tissue Expression — In hepatocellular carcinoma (HCC), PVRIG mRNA expression is higher in tumor tissue than in normal liver. Expression is heterogeneous across tumors and is the only member of the TIGIT/DNAM-1 axis with independent prognostic value for better survival. PVRIG-high tumors show higher lymphocytic infiltrate and tertiary lymphoid structure signatures, linking high PVRIG expression to immune-active tumor contexts. ([PMC9856571](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9856571/))
  - *assay*: Human · hepatocellular carcinoma tumor vs normal liver (TCGA cohort)
  > "Among all members of the TIGIT/DNAM-1 axis, <i>PVRIG</i> expression was higher in tumors than in normal liver, was heterogeneous across tumors, and was the only member with independent prognostic value for better survival. <i>PVRIG</i> High tumors were characterized by a higher lymphocytic infiltrate and enriched for signatures associated with tertiary lymphoid structures and better anti-tumor immune response."
- `a2_evi_17` · *Primary* · Supports · Tissue Expression — Pan-cancer RNA-seq analysis (TCGA vs GTEx normals) shows significantly higher PVRIG mRNA in DLBC, ESCA, HNSC, KIRC, KIRP, LAML, SKCM, STAD, TGCT, and THYM tumors relative to normal tissues, while PVRIG is lower in UCS, UCEC, THCA, READ, OV, PRAD, KICH, LUSC, LGG, GBM, COAD, BLCA, and ACC. This establishes a cancer-type-specific pattern of PVRIG dysregulation. ([PMC11982253](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11982253/))
  - *assay*: Human · TCGA tumor cohorts vs GTEx normal tissues (pan-cancer)
  > "Comparing with normal tissues, significantly higher PVRIG mRNA expression levels were observed in DLBC, ESCA, HNSC, KIRC, KIRP, LAML, SKCM, STAD, TGCT, and THYM, while lower expression was found in UCS, UCEC, THCA, READ, OV, PRAD, KICH, LUSC, LGG, GBM, COAD, BLCA, and ACC (Fig. 1 A)."
- `a2_evi_18` · *Primary* · Supports · Tissue Expression — PVRIG mRNA is higher in STAD (stomach adenocarcinoma), KIRP, KIRC, and ESCA tumor tissues compared to matched adjacent normal tissues, confirming tumor-specific upregulation in these cancer types with within-patient paired analysis. ([PMC11982253](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11982253/))
  - *assay*: Human · STAD, KIRP, KIRC, ESCA tumor vs adjacent normal (TCGA)
  > "The PVRIG mRNA expression levels in the STAD, KIRP, KIRC, and ESCA tumor tissues were higher than those in adjacent normal tissues."
- `a2_evi_19` · *Primary* · Refutes · Tissue Expression — PVRIG mRNA is lower in BLCA, COAD, LUSC, THCA, and UCEC tumor samples compared to adjacent normal tissues, indicating that in these cancer types PVRIG is actually downregulated in the tumor versus the normal tissue context. ([PMC11982253](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11982253/))
  - *assay*: Human · BLCA, COAD, LUSC, THCA, UCEC tumor vs adjacent normal (TCGA)
  > "Conversely, the PVRIG mRNA expression levels in BLCA, COAD, LUSC, THCA, and UCEC tumor samples were lower than those in adjacent normal tissues (Fig. 1 B)."
- `a2_evi_20` · *Primary* · Supports · Tissue Expression — PVRIG expression was evaluated in placental tissue by immunohistochemistry and RT-PCR. PVRIG protein expression (H-score) is increased in early-onset preeclampsia (EOP) and late-onset preeclampsia (LOP) groups compared to healthy pregnant controls; at the mRNA level, PVRIG gene expression increases twofold in EOP but decreases to one-third in LOP. This establishes placenta as an expression site with disease-state-dependent modulation of PVRIG. (https://pubmed.ncbi.nlm.nih.gov/40425968/)
  - *assay*: Human · placental tissue (healthy, EOP, LOP) · fixed · permeabilized
  > "As a result of H scoring of immunohistochemical expression, it was observed that CD112 and CD155 expression decreased and PVRIG expression increased when the EOP and LOP groups were compared with the control group. In the early onset preeclampsia group, CD112, CD155, TIGIT, and PVRIG gene expression increased twofold compared to that in the control group. In the late-onset preeclampsia group, the expression of all the genes decreased to one-third. The results of our study revealed that these genes may serve as biomarkers for early- and late-onset preeclampsia."
- `a2_evi_21` · *Primary* · Supports · Tissue Expression — Bioinformatics analysis of two GEO datasets (GSE25101 and GSE73754) encompassing 68 ankylosing spondylitis (AS) cases and 36 healthy controls shows that CD112R (PVRIG) is significantly downregulated in AS patients. Flow cytometry confirms reduced frequency of CD112R-positive cells among CD4+ T cells in AS versus healthy controls, representing a disease-state-associated decrease in PVRIG expression on CD4+ T cells. ([PMC9234051](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9234051/))
  - *assay*: Human · CD4+ T cells (peripheral blood, ankylosing spondylitis patients vs healthy controls) · live · non-permeabilized
  > "Among the 9 picked IRs, CD112R and CD96 were significantly downregulated in AS patients ( Figure 1(b) )."
- `a2_evi_22` · *Primary* · Supports · Tissue Expression — Mouse CD8+ T cells upregulate Pvrig expression upon in vitro activation, though at a slower rate compared to Tigit. This activation-induced upregulation in CD8+ T cells mirrors the human biology and establishes activation state as a modulator of PVRIG surface levels. ([PMC7038785](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7038785/))
  - *assay*: Mouse · CD8+ T cells (in vitro activated)
  > "When activated in vitro , mouse CD8 + T cells upregulated Pvrig expression, although at a much slower rate compared with a related checkpoint, Tigit ( Fig. 1B )."
- `a2_evi_23` · *Primary* · Supports · Tissue Expression — In the mouse tumor microenvironment, infiltrating CD8+ T cells express PVRIG surface protein, while its ligand PVRL2 is detected predominantly on myeloid cells and tumor cells, mirroring the human tumor expression pattern. This positions PVRIG-expressing CD8+ T cells and PVRL2-expressing myeloid/tumor cells as the key interacting parties in the TME. ([PMC7038785](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7038785/))
  - *assay*: Mouse · CD8+ T cells, myeloid cells, tumor cells (tumor-infiltrating) · live · non-permeabilized
  > "In the mouse tumor microenvironment, infiltrating CD8<sup>+</sup> T cells expressed PVRIG whereas its ligand, PVRL2, was detected predominantly on myeloid cells and tumor cells, mirroring the expression pattern in human tumors."
- `a2_evi_24` · *Primary* · Supports · Surface Expression — CD112R (PVRIG) blockade, separately or together with TIGIT blockade, enhances trastuzumab-triggered antitumor response by human NK cells, indicating PVRIG is functionally expressed on NK cells and accessible to antibody blockade during NK cell activation. TIGIT is upregulated upon NK cell activation via ADCC, suggesting that activation further increases checkpoint receptor expression during tumor-directed killing. ([PMC5709220](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5709220/))
  - *assay*: Human · NK cells (peripheral blood, activated via ADCC) · live · non-permeabilized
  > "More importantly, TIGIT is upregulated upon NK cell activation via ADCC. Blockade of TIGIT or CD112R, separately or together, enhances trastuzumab-triggered antitumor response by human NK cells. Thus, our findings suggest that PVR-like receptors regulate NK cell functions and can be targeted for improving trastuzumab therapy for breast cancer."
- `a2_evi_25` · *Primary* · Supports · Surface Expression — NK cell activation (by tumor cell recognition, cytokines IL-2/IL-12, or receptor crosslinking via CD16/NKp46) results in reduced PVRIG expression on the cell surface. This is a consistent activation-induced downregulation of PVRIG surface levels across multiple activation stimuli, representing a key accessibility modulation event. Baseline: resting NK cells with moderate surface PVRIG. Modulating state: activated NK cells (any stimulus). Change: decreased surface PVRIG. Implication: PVRIG surface target is less accessible on acutely activated NK cells than on resting NK cells. (https://pubmed.ncbi.nlm.nih.gov/33147937/)
  - *assay*: Human · NK cells (peripheral blood, activated vs resting) · live · non-permeabilized
  > "To understand how PVRIG blockade might potentially be exploited therapeutically, we investigated the biology of PVRIG and revealed that NK cell activation resulted in reduced PVRIG expression on the cell surface."
- `a2_evi_26` · *Primary* · Ambiguous · Surface Expression — PVRIG protein is present at higher levels in the cytoplasm than on the cell surface, particularly on CD56bright NK cells. Following IL-2 and IL-12 activation, cytoplasmic PVRIG levels further increase on CD56bright NK cells. This subcellular distribution—cytoplasm > cell surface—places PVRIG primarily in an intracellular compartment, with surface expression being the minor pool, especially in CD56bright NK cells. (https://pubmed.ncbi.nlm.nih.gov/33147937/)
  - *assay*: Human · CD56bright NK cells vs CD56dim NK cells (peripheral blood) · fixed · permeabilized
  > "PVRIG was present at higher levels in the cytoplasm than on the cell surface, particularly on CD56bright NK cells, which further increased cytoplasmic PVRIG levels following IL-2 and IL-12 activation."
- `a2_evi_27` · *Primary* · Supports · Surface Expression — PVRIG is continually transported to the cell surface via the endoplasmic reticulum (ER) and Golgi pathway in both unstimulated and activated NK cells, indicating constitutive intracellular trafficking that maintains the surface pool. This places PVRIG in the secretory pathway en route to the plasma membrane rather than being exclusively surface-resident. (https://pubmed.ncbi.nlm.nih.gov/33147937/)
  - *assay*: Human · NK cells (peripheral blood, unstimulated and activated) · fixed · permeabilized
  > "PVRIG was continually transported to the cell surface via the endoplasmic reticulum (ER) and Golgi in both unstimulated and activated NK cells."
- `a2_evi_28` · *Primary* · Refutes · Contradictory — In AML patient bone marrow, NK cell PVRIG expression levels were NOT increased compared to normal, despite PVRL2 being expressed on AML blasts. This contradicts the expectation (from solid tumor data) that tumor context uniformly upregulates PVRIG on infiltrating NK cells, and represents a contradictory observation relative to PVRIG upregulation seen in other disease contexts. (https://pubmed.ncbi.nlm.nih.gov/33147937/)
  - *assay*: Human · NK cells (bone marrow, AML patients vs healthy donors) · live · non-permeabilized
  > "However, in AML patient bone marrow, NK cell PVRIG expression levels were not increased."
- `a2_evi_29` · *Primary* · Supports · Tissue Expression — Across all compartments in colorectal cancer tumor tissue, proliferating CD8+ T cells show significantly higher CD112R (PVRIG) expression than non-proliferating CD8+ T cells (P<0.001), indicating that cell proliferation/activation state is a positive modulator of PVRIG surface levels on CD8+ TILs. Baseline: non-proliferating CD8+ T cells, lower PVRIG. Modulating state: proliferating CD8+ T cells. Change: significantly higher PVRIG expression. Implication: PVRIG is more accessible on proliferating/activated effector CD8+ T cells in the tumor. (https://pubmed.ncbi.nlm.nih.gov/36788088/)
  - *assay*: Human · proliferating vs non-proliferating CD8+ T cells (colorectal cancer TME) · fixed · permeabilized
  > "Across all tissue compartments, proliferating CD8<sup>+</sup> T cells showed higher relative CD112R and PD-1 expressions than those shown by non-proliferating CD8<sup>+</sup> T cells (P < .001 each). Integration of all available spatial and immune checkpoint expression parameters revealed a superior predictive performance for overall survival (area under the curve, 0.65; 95% CI, 0.60-0.70) compared with the commonly used CD8<sup>+</sup> tumor-infiltrating lymphocyte density (area under the curve, 0.57; 95% CI, 0.53-0.61; P < .001)."
- `a2_evi_30` · *Primary* · Supports · Tissue Expression — In bone metastasis (BoM), expression and co-expression of PVRIG (along with TIGIT, KIR2DL5, CD39) is significantly increased on CD103+ T cells in both the CD4+ and CD8+ compartments, compared to CD103- T cells within BoM and compared to CD103+ T cells in non-malignant bone marrow controls. This demonstrates disease-state-induced upregulation of PVRIG on tissue-resident (CD103+) T cells in bone metastasis. (https://pubmed.ncbi.nlm.nih.gov/41485718/)
  - *assay*: Human · CD103+CD4+ and CD103+CD8+ T cells (bone marrow, bone metastasis vs non-malignant controls) · live · non-permeabilized
  > "Expression and coexpression of TIGIT, PVRIG, KIR2DL5 and CD39 on CD103<sup>+</sup> cells both in the CD4 and CD8 compartment was significantly increased in BoM, compared within CD103<sup>-</sup> within BoM and CD103<sup>+</sup> in NMC.<h4>Conclusion</h4>In conclusion, BoM exhibit a distinct T-cell composition, highlighted by an increase in CD103⁺CD4⁺ cells displaying an increased CM phenotype. In BoM, cregulatory receptor expression is increased on CD103⁺ T cells, with distinct coexpression signatures in both CD4⁺ and CD8⁺ cells."

## Appendix · Downloads & reproduction

This Markdown is generated from the canonical JSON record at `/data/surfaceome/PVRIG.json`. The JSON is the source of truth; this file is the human-readable mirror.

**Links**

- Viewer page: [https://surfaceome.deliverome.org/PVRIG](https://surfaceome.deliverome.org/PVRIG)
- Canonical JSON: [https://surfaceome.deliverome.org/data/surfaceome/PVRIG.json](https://surfaceome.deliverome.org/data/surfaceome/PVRIG.json)
- This Markdown: [https://surfaceome.deliverome.org/data/surfaceome/PVRIG.md](https://surfaceome.deliverome.org/data/surfaceome/PVRIG.md)
- AlphaFold DB entry: [https://alphafold.ebi.ac.uk/entry/Q6DKI7](https://alphafold.ebi.ac.uk/entry/Q6DKI7)
- AFDB prediction API: [https://alphafold.ebi.ac.uk/api/prediction/Q6DKI7](https://alphafold.ebi.ac.uk/api/prediction/Q6DKI7) (returns current `pdbUrl`, `cifUrl`, `uniprotSequence`, …)
- UniProt: [https://www.uniprot.org/uniprotkb/Q6DKI7](https://www.uniprot.org/uniprotkb/Q6DKI7)

**AlphaFold model downloads**

- mmCIF model: [https://alphafold.ebi.ac.uk/files/AF-Q6DKI7-F1-model_v6.cif](https://alphafold.ebi.ac.uk/files/AF-Q6DKI7-F1-model_v6.cif)
- PDB model: [https://alphafold.ebi.ac.uk/files/AF-Q6DKI7-F1-model_v6.pdb](https://alphafold.ebi.ac.uk/files/AF-Q6DKI7-F1-model_v6.pdb)
- PAE (predicted aligned error) JSON: [https://alphafold.ebi.ac.uk/files/AF-Q6DKI7-F1-predicted_aligned_error_v6.json](https://alphafold.ebi.ac.uk/files/AF-Q6DKI7-F1-predicted_aligned_error_v6.json)
- AFDB model version: 6

### Canonical UniProt sequence

*326 aa · `Q6DKI7` · embedded at build time*

```
   1  MRTEAQVPALQPPEPGLEGAMGHRTLVLPWVLLTLCVTAGTPEVWVQVRMEATELSSFTI
  61  RCGFLGSGSISLVTVSWGGPNGAGGTTLAVLHPERGIRQWAPARQARWETQSSISLILEG
 121  SGASSPCANTTFCCKFASFPEGSWEACGSLPPSSDPGLSAPPTPAPILRADLAGILGVSG
 181  VLLFGCVYLLHLLRRHKHRPAPRLQPSRTSPQAPRARAWAPSQASQAALHVPYATINTSC
 241  RPATLDTAHPHGGPSWWASLPTHAAHRPQGPAAWASTPIPARGSFVSVENGLYAQAGERP
 301  PHTGPGLTLFPDPRGPRAMEGPLGVR
```

### Per-residue DeepTMHMM topology

*Five-letter alphabet: `M` = TM helix, `O` = extracellular, `I` = intracellular, `S` = signal peptide, `B` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*

**canonical** (`Q6DKI7`, deeptmhmm-1.0.24)

```
   1  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOO
  61  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
 121  OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMM
 181  MMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 241  IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
 301  IIIIIIIIIIIIIIIIIIIIIIIIII
```

### Data sources

- AlphaFold DB structures — CC BY 4.0 (© DeepMind / EMBL-EBI)
- DeepTMHMM topology — deeptmhmm-1.0.24 · DTU Health Tech (Hallgren et al. 2022)
- Ensembl Compara orthologs & paralogs — — · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)
- UniProt — CC BY 4.0 (UniProt Consortium)

*Confidence high — *
