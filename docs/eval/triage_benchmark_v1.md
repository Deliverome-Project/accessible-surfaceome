# Triage benchmark v1 — controls

Total: **55 proteins** (39 `yes`, 8 `maybe`, 8 `no`)

## Yes — surface accessible

Surface-accessible: a binder could in principle reach the protein from the extracellular face. Includes validated targets, disagreement-rich positives (real targets that the M1 consensus stack misses), and GPCRs whose extracellular pocket is engaged by small molecules.

| Gene | UniProt | Class | Description |
|---|---|---|---|
| **CCR8** | P51685 | `disagreement_rich_positive` | Chemokine receptor 8; tumor Treg-restricted; multiple anti-CCR8 mAb depletion programs. |
| **CD74** | P04233 | `disagreement_rich_positive` | MHC II invariant chain; transient PM presence with MHC II; Milatuzumab clinical ADC. |
| **CLDN6** | P56747 | `disagreement_rich_positive` | Tight-junction claudin; tumor-restricted; BNT211 CAR-T, AMG794 bispecific, multiple ADCs. |
| **DLL3** | Q9NYJ7 | `disagreement_rich_positive` | Notch ligand; SCLC neuroendocrine; **Tarlatamab/Imdelltra approved 2024 bispecific**. |
| **EFNA4** | P52798 | `disagreement_rich_positive` | Ephrin-A4; PF-06647263 clinical ADC. |
| **EPHB4** | P54760 | `disagreement_rich_positive` | Eph receptor B4; soluble EphB4 fusion clinical programs. |
| **EREG** | O14944 | `disagreement_rich_positive` | Epiregulin (EGFR family ligand); clinical mAb programs. |
| **FLT3** | P36888 | `disagreement_rich_positive` | FMS-like tyrosine kinase 3; AML; AMG553 CAR-T, FLT3×CD3 bispecifics. |
| **FZD10** | Q9ULW2 | `disagreement_rich_positive` | 7TM Wnt receptor; OTSA101-DTPA clinical radioimmunoconjugate. |
| **FZD7** | O75084 | `disagreement_rich_positive` | 7TM Wnt receptor; Vantictumab clinical mAb (Ipsen/OncoMed). |
| **GFRA1** | P56159 | `disagreement_rich_positive` | GDNF family receptor α-1; multiple clinical ADCs. |
| **GPNMB** | Q14956 | `disagreement_rich_positive` | Glycoprotein nmb; melanoma/breast; Glembatumumab vedotin clinical ADC. |
| **GPRC5D** | Q9NZD1 | `disagreement_rich_positive` | Orphan GPCR; multiple myeloma; **Talquetamab approved 2023 bispecific**. |
| **GUCY2C** | P25092 | `disagreement_rich_positive` | Guanylyl cyclase C; intestinal/CRC; clinical bispecifics + ADCs (M9140). |
| **KLK2** | P20151 | `disagreement_rich_positive` | Kallikrein-related peptidase 2; secreted+membrane prostate antigen; clinical ADC programs. |
| **LGR5** | O75473 | `disagreement_rich_positive` | 7TM Wnt-pathway receptor; multiple clinical ADC programs. |
| **LRRC15** | Q8TF66 | `disagreement_rich_positive` | Mesenchymal/stromal surface receptor; ABBV-085 clinical ADC. |
| **MUC1** | P15941 | `disagreement_rich_positive` | Tethered tumor mucin; large extracellular tandem-repeat ECD; multiple ADC/bispecific programs. |
| **PSCA** | O43653 | `disagreement_rich_positive` | Prostate stem cell antigen; GPI-anchored; clinical CAR-T + ADC programs. |
| **ROR1** | Q01973 | `disagreement_rich_positive` | Receptor tyrosine kinase orphan; CLL/solid tumor; Cirmtuzumab, Zilovertamab vedotin, Lyell CAR-T. |
| **ROR2** | Q01974 | `disagreement_rich_positive` | Wnt5a coreceptor; BA3021 conditionally-active clinical ADC. |
| **ROS1** | P08922 | `disagreement_rich_positive` | Receptor tyrosine kinase; lung cancer fusions; **crizotinib/lorlatinib approved (small mol)**; clinical ADCs. |
| **SEZ6** | Q53EL9 | `disagreement_rich_positive` | Seizure-related 6; SCLC; ABBV-011 clinical ADC. |
| **SLC34A2** | O95436 | `disagreement_rich_positive` | NaPi2b multipass apical phosphate transporter; Lifastuzumab vedotin clinical ADC. |
| **STEAP1** | Q9UHE8 | `disagreement_rich_positive` | 6-pass TM prostate antigen with small ECLs; GSK4427296 TCR-T + AMG509 bispecific. **In Tier 1: not in M1 panel.** |
| **ADORA3** | P0DMS8 | `gpcr_extracellular_pocket` | Adenosine A3 receptor (GPCR); multiple clinical small-molecule programs. |
| **AVPR1A** | P37288 | `gpcr_extracellular_pocket` | Vasopressin V1A receptor (GPCR); conivaptan-class clinical small molecules. |
| **BDKRB1** | P46663 | `gpcr_extracellular_pocket` | Bradykinin B1 receptor (GPCR); clinical small-molecule programs. |
| **GCGR** | P47871 | `gpcr_extracellular_pocket` | Glucagon receptor (GPCR); clinical peptide-drug programs. |
| **GIPR** | P48546 | `gpcr_extracellular_pocket` | GIP receptor (GPCR); **Tirzepatide approved (GIP/GLP-1 dual agonist peptide drug)**. |
| **GPBAR1** | Q8TDU6 | `gpcr_extracellular_pocket` | TGR5 bile acid receptor (GPCR); clinical small-molecule programs. |
| **GRM4** | Q14833 | `gpcr_extracellular_pocket` | Metabotropic glutamate receptor 4 (GPCR); CNS clinical small molecules. |
| **HRH2** | P25021 | `gpcr_extracellular_pocket` | Histamine H2 receptor (GPCR); ranitidine/famotidine class small molecules. |
| **HTR2C** | P28335 | `gpcr_extracellular_pocket` | 5-HT2C serotonin receptor (GPCR); lorcaserin small-molecule (formerly approved). |
| **MC1R** | Q01726 | `gpcr_extracellular_pocket` | Melanocortin-1 receptor (GPCR); **Afamelanotide (Scenesse) approved peptide**. |
| **NPY5R** | Q15761 | `gpcr_extracellular_pocket` | Neuropeptide Y5 receptor (GPCR); obesity small-molecule programs. |
| **CD19** | P15391 | `validated_positive` | B-cell coreceptor; classical CAR-T + ADC target (Kymriah, Loncastuximab tesirine). |
| **ERBB2** | P04626 | `validated_positive` | HER2 — single-pass receptor tyrosine kinase; canonical ADC target (T-DM1, Enhertu). |
| **FOLR1** | P15328 | `validated_positive` | Folate receptor α; GPI-anchored ovarian cancer target; Mirvetuximab (ELAHERE). |

## Maybe — borderline / conditional / unusual mechanism

Borderline accessibility: pMHC peptides (the protein is intracellular but its peptide is MHC-presented), induced/conditional surfacers (cell-state-, stress-, or exocytosis-driven surfacing), and mixed-mechanism cases.

| Gene | UniProt | Class | Description |
|---|---|---|---|
| **CALR** | P27797 | `induced_borderline` | Calreticulin; ER-resident at baseline; reaches outer leaflet during immunogenic cell death. |
| **HSPA1A** | P0DMV8 | `induced_borderline` | HSP70; cytoplasmic at baseline; tumor-stress-induced surface presentation. |
| **HSPA5** | P11021 | `induced_borderline` | GRP78/BiP; ER chaperone; ER-stress/oncogenic-state translocation to outer leaflet. |
| **LAMP1** | P11279 | `induced_borderline` | Lysosomal membrane glycoprotein; reaches PM via lysosomal exocytosis (CD107a degranulation marker). |
| **PMEL** | P40967 | `mixed_mechanism_borderline` | gp100 melanoma antigen; primarily melanosomal; pMHC presentation is dominant accessibility mechanism (Tebentafusp). |
| **CTAG1B** | P78358 | `pmhc_borderline` | NY-ESO-1 cancer-testis antigen; HLA-A*02-restricted; clinical TCR-T (e.g. afami-cel). |
| **KAAG1** | Q9UBP8 | `pmhc_borderline` | Kidney-associated antigen 1 (RU2AS); HLA-B7-presented CTL peptide; protein itself intracellular. |
| **PRAME** | P78395 | `pmhc_borderline` | PRAME cancer-testis antigen; HLA-A*02-restricted; brenetafusp/IMC-F106C T-cell engagers. |

## No — not surface accessible

Not accessible from outside the cell. Adversarial negatives: wrong-side (cytoplasmic-face anchored), wrong-compartment (lysosomal/Golgi/ER membrane-resident), and secreted-only proteins. Cytoplasmic and ribosomal proteins are deliberately excluded as too easy.

| Gene | UniProt | Class | Description |
|---|---|---|---|
| **APPL1** | Q9UKG1 | `opencell_vesicle_negative` | Imaged-confirmed signaling endosome (OpenCell grade-3); intracellular. |
| **MUC5AC** | P98088 | `secreted_negative` | Secreted gel-forming airway/gastric mucin; no membrane tether. |
| **ABCB9** | Q9NP78 | `wrong_compartment_negative` | Lysosomal ABC transporter (TAPL); polytopic TM but lysosomal — not PM-accessible. |
| **ATG9A** | Q7Z3C6 | `wrong_compartment_negative` | Autophagy machinery; cycles between Golgi/endosomes/autophagosomal precursors; never PM in steady state. |
| **GORASP2** | Q9H8Y8 | `wrong_compartment_negative` | Golgi reassembly stacking protein 2; peripheral on Golgi cytosolic face. |
| **STING1** | Q86WV6 | `wrong_compartment_negative` | TMEM173 ER signaling adaptor; TM-rich but never on PM. |
| **TGOLN2** | O43493 | `wrong_compartment_negative` | TGN46 trans-Golgi network resident; TM + small luminal domain — Golgi-resident. |
| **KRAS** | P01116 | `wrong_side_negative` | Membrane-anchored on the cytoplasmic face (inner leaflet, lipidated); tests the wrong-side trap. |

## Class composition

| Class | Verdict | Count |
|---|---|---:|
| `disagreement_rich_positive` | `yes` | 25 |
| `gpcr_extracellular_pocket` | `yes` | 11 |
| `induced_borderline` | `maybe` | 4 |
| `mixed_mechanism_borderline` | `maybe` | 1 |
| `opencell_vesicle_negative` | `no` | 1 |
| `pmhc_borderline` | `maybe` | 3 |
| `secreted_negative` | `no` | 1 |
| `validated_positive` | `yes` | 3 |
| `wrong_compartment_negative` | `no` | 5 |
| `wrong_side_negative` | `no` | 1 |
