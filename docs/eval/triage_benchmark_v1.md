# Triage benchmark v1 — controls

Total: **104 proteins** (39 `yes`, 14 `maybe`, 51 `no`)

**DBs/5** column: how many of the 5 retained M1 surface databases (UniProt subcellular query, GO cellular component, HPA, SURFY, CSPA) flagged the protein as surface-expressed. *DeepTMHMM and JensenLab COMPARTMENTS are excluded from the triage stack.* `—` means the protein is not in the M1 candidate universe (failed every M1 source rule).

## Yes — surface accessible

Surface-accessible: a binder could in principle reach the protein from the extracellular face. Includes validated targets, disagreement-rich positives (real targets that the M1 consensus stack misses), and GPCRs whose extracellular pocket is engaged by small molecules.

| Gene | UniProt | Class | DBs/5 | Localization / rationale |
|---|---|---|---|---|
| **CCR8** | P51685 | `disagreement_rich_positive` | **3/5** (surfy,uniprot,go) | clinical mAb: Multiple anti-CCR8 mAb programs (Treg depletion) |
| **CD74** | P04233 | `disagreement_rich_positive` | **4/5** (surfy,cspa,uniprot,go) | Invariant chain on B/dendritic cell surface; clinical-stage Milatuzumab ADC |
| **CLDN6** | P56747 | `disagreement_rich_positive` | **2/5** (surfy,uniprot) | CAR-T + ADC + bispecific: BNT211 CAR-T (BioNTech), AMG794 bispecific, multiple ADCs. Tight-junction claudin |
| **DLL3** | Q9NYJ7 | `disagreement_rich_positive` | **3/5** (surfy,uniprot,hpa) | approved bispecific: Tarlatamab/Imdelltra approved 2024 SCLC |
| **EFNA4** | P52798 | `disagreement_rich_positive` | **2/5** (surfy,cspa) | clinical ADC: PF-06647263 ADC |
| **EPHB4** | P54760 | `disagreement_rich_positive` | **3/5** (surfy,cspa,uniprot) | clinical mAb: Soluble EphB4 fusion programs |
| **EREG** | O14944 | `disagreement_rich_positive` | **2/5** (surfy,uniprot) | clinical mAb: Anti-EREG programs (epiregulin) |
| **FLT3** | P36888 | `disagreement_rich_positive` | **3/5** (surfy,cspa,uniprot) | clinical ADC + CAR-T: AMG553 CAR-T, FLT3xCD3 bispecifics |
| **FZD10** | Q9ULW2 | `disagreement_rich_positive` | **3/5** (surfy,uniprot,go) | clinical mAb: OTSA101-DTPA (radioimmunoconjugate) |
| **FZD7** | O75084 | `disagreement_rich_positive` | **2/5** (surfy,uniprot) | clinical mAb: Vantictumab (OMP-18R5, Ipsen/OncoMed); 7TM Wnt receptor |
| **GFRA1** | P56159 | `disagreement_rich_positive` | **3/5** (surfy,cspa,go) | clinical ADC: Multiple GFRalpha-1 ADC programs |
| **GPNMB** | Q14956 | `disagreement_rich_positive` | **3/5** (surfy,cspa,uniprot) | clinical ADC: Glembatumumab vedotin (Celldex) |
| **GPRC5D** | Q9NZD1 | `disagreement_rich_positive` | **2/5** (surfy,uniprot) | approved bispecific + CAR-T: Talquetamab approved 2023 (multiple myeloma); orphan GPCR |
| **GUCY2C** | P25092 | `disagreement_rich_positive` | **2/5** (surfy,uniprot) | approved bispecific + ADC: M9140 ADC; multiple approved/clinical programs |
| **KLK2** | P20151 | `disagreement_rich_positive` | — | clinical ADC: Multiple programs; secreted+membrane prostate antigen |
| **LGR5** | O75473 | `disagreement_rich_positive` | **2/5** (surfy,uniprot) | clinical ADC: Multiple Wnt-receptor ADC programs |
| **LRRC15** | Q8TF66 | `disagreement_rich_positive` | **5/5** (surfy,cspa,uniprot,go,hpa) | Mesenchymal/stromal surface receptor; clinical-stage ABBV-085 ADC |
| **MUC1** | P15941 | `disagreement_rich_positive` | **4/5** (surfy,uniprot,go,hpa) | TROP-2-adjacent validated tumor antigen; large mucin ECD; multiple antibody programs |
| **PSCA** | O43653 | `disagreement_rich_positive` | **2/5** (surfy,hpa) | clinical CAR-T + ADC: Multiple PSCA programs; GPI-anchored |
| **ROR1** | Q01973 | `disagreement_rich_positive` | **3/5** (surfy,cspa,uniprot) | clinical CAR-T + ADC: Cirmtuzumab, Zilovertamab vedotin, Lyell CAR-T |
| **ROR2** | Q01974 | `disagreement_rich_positive` | **3/5** (surfy,cspa,uniprot) | clinical ADC: BA3021 conditionally-active ADC (BioAtla) |
| **ROS1** | P08922 | `disagreement_rich_positive` | **2/5** (surfy,uniprot) | approved TKI + clinical ADC: Crizotinib/lorlatinib approved (small molecule); ADC programs in development |
| **SEZ6** | Q53EL9 | `disagreement_rich_positive` | **2/5** (surfy,uniprot) | clinical ADC: ABBV-011 ADC (AbbVie SCLC) |
| **SLC34A2** | O95436 | `disagreement_rich_positive` | **4/5** (surfy,uniprot,go,hpa) | Apical phosphate transporter; clinical Lifastuzumab vedotin ADC |
| **STEAP1** | Q9UHE8 | `disagreement_rich_positive` | — | TCR-T + bispecific: GSK4427296 TCR-T + AMG509 bispecific. 6-pass TM with small ECLs — also tests minimal_ectoloops case |
| **ADORA3** | P0DMS8 | `gpcr_extracellular_pocket` | **1/5** (uniprot) | clinical small molecule: Adenosine A3 receptor; multiple clinical programs |
| **AVPR1A** | P37288 | `gpcr_extracellular_pocket` | **2/5** (surfy,uniprot) | clinical small molecule: Vasopressin V1A receptor; conivaptan family |
| **BDKRB1** | P46663 | `gpcr_extracellular_pocket` | **2/5** (surfy,uniprot) | clinical small molecule: Bradykinin B1 receptor; multiple programs |
| **GCGR** | P47871 | `gpcr_extracellular_pocket` | **2/5** (surfy,uniprot) | clinical peptide drug: Multiple glucagon receptor programs |
| **GIPR** | P48546 | `gpcr_extracellular_pocket` | **2/5** (surfy,uniprot) | approved peptide drug: Tirzepatide (GIP/GLP-1 dual agonist) approved |
| **GPBAR1** | Q8TDU6 | `gpcr_extracellular_pocket` | **2/5** (surfy,uniprot) | clinical small molecule: Bile acid receptor TGR5; multiple programs |
| **GRM4** | Q14833 | `gpcr_extracellular_pocket` | **2/5** (surfy,uniprot) | clinical small molecule: Metabotropic glutamate receptor 4; CNS programs |
| **HRH2** | P25021 | `gpcr_extracellular_pocket` | **2/5** (surfy,uniprot) | approved small molecule: H2 receptor (ranitidine/famotidine class) |
| **HTR2C** | P28335 | `gpcr_extracellular_pocket` | **2/5** (surfy,uniprot) | approved small molecule: Lorcaserin (was approved); 7TM serotonin receptor |
| **MC1R** | Q01726 | `gpcr_extracellular_pocket` | **2/5** (surfy,uniprot) | approved peptide: Afamelanotide (Scenesse) approved; melanocortin |
| **NPY5R** | Q15761 | `gpcr_extracellular_pocket` | **2/5** (surfy,uniprot) | clinical small molecule: Neuropeptide Y receptor 5; obesity programs |
| **CD19** | P15391 | `validated_positive` | **4/5** (surfy,cspa,uniprot,go) | Approved CAR-T + ADC; classical B-cell surface marker |
| **ERBB2** | P04626 | `validated_positive` | **5/5** (surfy,cspa,uniprot,go,hpa) | Approved ADC; classical surface receptor with large ECD |
| **FOLR1** | P15328 | `validated_positive` | **4/5** (surfy,cspa,uniprot,go) | Approved Mirvetuximab (ELAHERE); GPI-anchored on outer leaflet |

## Maybe — borderline / conditional / unusual mechanism

Borderline accessibility: pMHC peptides (the protein is intracellular but its peptide is MHC-presented), induced/conditional surfacers (cell-state-, stress-, or exocytosis-driven surfacing), mixed-mechanism cases, and proteins canonically in non-PM compartments that have documented (but not dominant) surface forms — e.g. GARP-tethered TGF-β1, plasma-membrane VDAC1, ecto-Src on tumor cells, surface B4GALT1 on sperm.

| Gene | UniProt | Class | DBs/5 | Localization / rationale |
|---|---|---|---|---|
| **B4GALT1** | P15291 | `induced_borderline` | **2/5** (uniprot,go) | β-1,4-galactosyltransferase 1; primarily Golgi-resident, but **a cell-surface form on sperm mediates zona pellucida adhesion**; also reported on tumor cells. Conditional/cell-type-restricted surfacing. |
| **CALR** | P27797 | `induced_borderline` | **3/5** (cspa,uniprot,go) | ER-resident at baseline; reaches outer leaflet during immunogenic cell death |
| **HSPA1A** | P0DMV8 | `induced_borderline` | — | Cytoplasmic at baseline; tumor-stress-induced surface presentation |
| **HSPA5** | P11021 | `induced_borderline` | **1/5** (uniprot) | ER chaperone at baseline; ER-stress/oncogenic-state translocation to outer leaflet |
| **LAMP1** | P11279 | `induced_borderline` | **2/5** (surfy,cspa) | Classical lysosomal membrane glycoprotein; reaches plasma membrane via lysosomal exocytosis (CD107a degranulation marker on NK / cytotoxic T cells, surface staining on metastatic tumor cells). Conditional surfacing puts it in the maybe class. |
| **STIM1** | Q13586 | `induced_borderline` | **4/5** (surfy,cspa,uniprot,go) | ER calcium sensor; canonically ER-resident, but **clusters at ER-PM junctions during store-operated calcium entry (SOCE)**; some PM staining reports. Borderline due to ER-PM junction localization. |
| **VDAC1** | P21796 | `induced_borderline` | **1/5** (cspa) | Mitochondrial outer-membrane porin; **plasma-membrane VDAC1 (pl-VDAC) is well-documented** in B cells, neurons, sperm, cancer cells, erythrocytes. Anti-VDAC1 antibodies in development. Borderline due to dual-localization. |
| **PMEL** | P40967 | `mixed_mechanism_borderline` | **2/5** (surfy,cspa) | Primarily melanosomal (lysosome-related organelle); pMHC presentation is the dominant accessibility mechanism (Tebentafusp targets gp100 peptide-MHC, not PMEL on the surface). Borderline like other pMHC cases. |
| **CTAG1B** | P78358 | `pmhc_borderline` | — | HLA-A*02-restricted cancer-testis antigen (NY-ESO-1); clinical TCR-T programs |
| **KAAG1** | Q9UBP8 | `pmhc_borderline` | — | HLA-B7-restricted CTL peptide; protein not directly accessible but its peptide is pMHC-presented |
| **PRAME** | P78395 | `pmhc_borderline` | **1/5** (hpa) | HLA-A*02-restricted; clinical T-cell engagers (brenetafusp/IMC-F106C) |
| **C3** | P01024 | `secreted_borderline` | **2/5** (cspa,uniprot) | Complement C3 secreted plasma protein; cleavage fragment **C3b is covalently deposited on cell surfaces during opsonization**. Borderline because C3 itself is soluble but its activation product is surface-anchored. |
| **TGFB1** | P01137 | `secreted_borderline` | **3/5** (cspa,go,hpa) | TGF-β1 secreted as latent complex; **GARP/LRRC32-tethered to Treg surface** as latent TGF-β; integrin αvβ6/αvβ8-mediated activation extracellularly. Clinical anti-GARP-TGF-β programs (Treg targeting). |
| **SRC** | P12931 | `wrong_side_borderline` | **2/5** (go,hpa) | Proto-oncogene tyrosine kinase; canonically myristoylated/palmitoylated to inner leaflet (cytoplasmic face). Ecto-SRC has been reported on cancer cell surfaces (melanoma, other tumors) — borderline conditional/pathological surfacing. M1 votes 3/6. |

## No — not surface accessible

Not accessible from outside the cell. Adversarial negatives: wrong-side (cytoplasmic-face anchored), wrong-compartment (lysosomal/Golgi/ER/mitochondrial/nuclear-envelope membrane-resident), secreted-only proteins, and approved-drug intracellular targets (kinases, nuclear receptors) that test the 'approved drug ⇒ surface' trap.

| Gene | UniProt | Class | DBs/5 | Localization / rationale |
|---|---|---|---|---|
| **AKT2** | P31751 | `approved_drug_intracellular_negative` | **1/5** (go) | AKT2 serine/threonine kinase; cytoplasmic. Capivasertib clinical/approved. |
| **BRAF** | P15056 | `approved_drug_intracellular_negative` | **1/5** (hpa) | B-Raf serine/threonine kinase; cytoplasmic. **Vemurafenib/dabrafenib approved**. Tests "approved drug ⇒ surface" trap. |
| **BTK** | Q06187 | `approved_drug_intracellular_negative` | **1/5** (hpa) | Bruton's tyrosine kinase; cytoplasmic. **Ibrutinib approved**. |
| **HDAC6** | Q9UBN7 | `approved_drug_intracellular_negative` | **1/5** (go) | Histone deacetylase 6; cytoplasmic/perinuclear. Multiple clinical inhibitors. |
| **IKBKB** | O14920 | `approved_drug_intracellular_negative` | **1/5** (go) | IKK-β; cytoplasmic. Multiple clinical NF-κB-pathway programs. |
| **JAK1** | P23458 | `approved_drug_intracellular_negative` | **1/5** (go) | JAK1 tyrosine kinase; cytoplasmic. Multiple approved JAK inhibitors. |
| **JAK2** | O60674 | `approved_drug_intracellular_negative` | **1/5** (go) | JAK2 tyrosine kinase; cytoplasmic. **Ruxolitinib approved** (myelofibrosis). |
| **JAK3** | P52333 | `approved_drug_intracellular_negative` | **2/5** (go,hpa) | JAK3 tyrosine kinase; cytoplasmic (associates with γc of cytokine receptors). Tofacitinib target. |
| **LRRK2** | Q5S007 | `approved_drug_intracellular_negative` | **1/5** (go) | LRRK2 kinase; cytoplasmic/peripheral. **Parkinson's clinical programs**. |
| **MAP2K1** | Q02750 | `approved_drug_intracellular_negative` | **1/5** (hpa) | MEK1 kinase; cytoplasmic. **Cobimetinib/trametinib approved**. |
| **MAP2K2** | P36507 | `approved_drug_intracellular_negative` | **1/5** (go) | MEK2 kinase; cytoplasmic. |
| **SYK** | P43405 | `approved_drug_intracellular_negative` | **2/5** (go,hpa) | Spleen tyrosine kinase; cytoplasmic. Fostamatinib target. |
| **TYK2** | P29597 | `approved_drug_intracellular_negative` | **1/5** (go) | TYK2 tyrosine kinase; cytoplasmic. Deucravacitinib approved (psoriasis). |
| **APPL1** | Q9UKG1 | `opencell_vesicle_negative` | **1/5** (hpa) | Imaged-confirmed signaling endosome; M1 false positive |
| **A2M** | P01023 | `secreted_negative` | **1/5** (cspa) | α2-macroglobulin; secreted plasma protease inhibitor. |
| **APOB** | P04114 | `secreted_negative` | **1/5** (cspa) | Apolipoprotein B-100; secreted on lipoprotein particles. |
| **F2** | P00734 | `secreted_negative` | **2/5** (cspa,go) | Prothrombin; secreted coagulation zymogen. |
| **FN1** | P02751 | `secreted_negative` | **1/5** (cspa) | Fibronectin; secreted ECM glycoprotein. |
| **IGF1** | P05019 | `secreted_negative` | **1/5** (go) | Insulin-like growth factor 1; secreted hormone. |
| **IL6** | P05231 | `secreted_negative` | **1/5** (go) | Interleukin-6; secreted cytokine. |
| **MUC5AC** | P98088 | `secreted_negative` | — | Fully secreted gel-forming mucin; no membrane tether |
| **TF** | P02787 | `secreted_negative` | **2/5** (cspa,go) | Transferrin; secreted iron-transport plasma protein. |
| **VEGFA** | P15692 | `secreted_negative` | **1/5** (go) | Vascular endothelial growth factor A; secreted angiogenic factor. |
| **ABCB9** | Q9NP78 | `wrong_compartment_negative` | **1/5** (surfy) | Polytopic TM but lysosomal; TM topology does not imply PM accessibility |
| **ATG9A** | Q7Z3C6 | `wrong_compartment_negative` | **2/5** (surfy,cspa) | Cycles between Golgi/endosomes/autophagosomal precursors; multi-pass TM but never PM in steady state |
| **BAX** | Q07812 | `wrong_compartment_negative` | **1/5** (hpa) | Pro-apoptotic Bcl-2 family; translocates to mitochondrial outer membrane. |
| **GALNT1** | Q10472 | `wrong_compartment_negative` | **1/5** (cspa) | N-acetylgalactosaminyltransferase 1; Golgi glycosyltransferase. |
| **GORASP2** | Q9H8Y8 | `wrong_compartment_negative` | — | Peripheral on Golgi cytosolic face; tests inner-leaflet/cytosolic-Golgi confusion |
| **ITPR1** | Q14643 | `wrong_compartment_negative` | **1/5** (cspa) | IP3 receptor type 1; ER membrane calcium channel. |
| **ITPR3** | Q14573 | `wrong_compartment_negative` | **2/5** (cspa,uniprot) | IP3 receptor type 3; ER membrane calcium channel. |
| **NUP210** | Q8TEM1 | `wrong_compartment_negative` | **2/5** (surfy,cspa) | Nuclear pore complex transmembrane component; nuclear envelope. |
| **RPN1** | P04843 | `wrong_compartment_negative` | **2/5** (surfy,cspa) | Ribophorin 1; ER membrane subunit of OST glycosylation complex. |
| **RPN2** | P04844 | `wrong_compartment_negative` | **1/5** (cspa) | Ribophorin 2; ER membrane subunit of OST. |
| **SCAP** | Q12770 | `wrong_compartment_negative` | **2/5** (surfy,cspa) | SREBP cleavage-activating protein; ER cholesterol sensor. |
| **SEC61G** | P60059 | `wrong_compartment_negative` | **1/5** (uniprot) | Sec61 translocon γ subunit; ER protein-translocation channel. |
| **STING1** | Q86WV6 | `wrong_compartment_negative` | — | ER signaling adaptor (TMEM173); TM-rich but never on PM |
| **SUN1** | O94901 | `wrong_compartment_negative` | **1/5** (cspa) | SUN domain protein 1; inner nuclear membrane (LINC complex). |
| **SUN2** | Q9UH99 | `wrong_compartment_negative` | **1/5** (cspa) | SUN domain protein 2; inner nuclear membrane. |
| **SYNE1** | Q8NF91 | `wrong_compartment_negative` | **1/5** (go) | Nesprin-1; outer nuclear membrane (LINC complex), cytoskeleton-coupled. |
| **SYNE2** | Q8WXH0 | `wrong_compartment_negative` | **1/5** (go) | Nesprin-2; outer nuclear membrane. |
| **TGOLN2** | O43493 | `wrong_compartment_negative` | **2/5** (surfy,uniprot) | Trans-Golgi network resident; TM + small luminal domain |
| **TMED10** | P49755 | `wrong_compartment_negative` | **1/5** (go) | TMED10 cargo receptor; ER-Golgi cycling. |
| **TMED9** | Q9BVK6 | `wrong_compartment_negative` | **1/5** (cspa) | TMED9 cargo receptor; cycles ER↔Golgi but Golgi-residence dominant. |
| **GNAQ** | P50148 | `wrong_side_negative` | **2/5** (go,hpa) | Heterotrimeric G-alpha-q; lipidated cytoplasmic-side anchor. |
| **GNB1** | P62873 | `wrong_side_negative` | **2/5** (go,hpa) | G-protein beta-1 subunit; peripheral on inner leaflet via Gγ prenylation. |
| **HCK** | P08631 | `wrong_side_negative` | **2/5** (go,hpa) | Hematopoietic cell kinase (Src family); inner-leaflet lipid-anchored. |
| **KRAS** | P01116 | `wrong_side_negative` | **1/5** (go) | Membrane-anchored on the cytoplasmic face; tests "membrane = surface" trap |
| **LYN** | P07948 | `wrong_side_negative` | **2/5** (go,hpa) | Src-family kinase; myristoylated/palmitoylated inner-leaflet anchor. |
| **NRAS** | P01111 | `wrong_side_negative` | **1/5** (hpa) | Ras GTPase; lipidated inner leaflet (same family as KRAS in benchmark). |
| **RAC1** | P63000 | `wrong_side_negative` | **1/5** (go) | Rac1 GTPase; geranylgeranylated to inner leaflet. |
| **RHOA** | P61586 | `wrong_side_negative` | **2/5** (go,hpa) | Rho GTPase; geranylgeranylated to inner leaflet. Cytoplasmic signaling. |

## Class composition

| Class | Verdict | Count |
|---|---|---:|
| `approved_drug_intracellular_negative` | `no` | 13 |
| `disagreement_rich_positive` | `yes` | 25 |
| `gpcr_extracellular_pocket` | `yes` | 11 |
| `induced_borderline` | `maybe` | 7 |
| `mixed_mechanism_borderline` | `maybe` | 1 |
| `opencell_vesicle_negative` | `no` | 1 |
| `pmhc_borderline` | `maybe` | 3 |
| `secreted_borderline` | `maybe` | 2 |
| `secreted_negative` | `no` | 9 |
| `validated_positive` | `yes` | 3 |
| `wrong_compartment_negative` | `no` | 20 |
| `wrong_side_borderline` | `maybe` | 1 |
| `wrong_side_negative` | `no` | 8 |

## DB-vote distribution by verdict (n / 5)

How well do the 5 retained M1 surface databases (UniProt, GO, HPA, SURFY, CSPA) collectively rank the benchmark? `—` = not in M1 (treated as 0).

| Verdict | 0/5 (or not-in-M1) | 1/5 | 2/5 | 3/5 | 4/5 | 5/5 |
|---|---:|---:|---:|---:|---:|---:|
| `yes` | 2 | 1 | 20 | 9 | 5 | 2 |
| `maybe` | 3 | 3 | 5 | 2 | 1 | 0 |
| `no` | 3 | 33 | 15 | 0 | 0 | 0 |
