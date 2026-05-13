# Triage benchmark v1 — controls

Total: **147 proteins** (71 `yes`, 27 `contextual`, 49 `no`).

The benchmark uses the schema vocabulary directly — `ground_truth_verdict` is one of `yes` / `contextual` / `no` matching `TriageVerdict` in `src/accessible_surfaceome/tools/_shared/models.py`, and `ground_truth_reason` is one of the literals in `TriageReason`. Every row roundtrips through `TriageRecordDraft` — see `tests/test_triage_benchmark_schema.py`.

## Yes — surface accessible (71)

Stably surface by the protein's own mechanism: TM domain, GPI, outer-leaflet lipidation, direct outer-leaflet lipid binding, pore assembly, or stable complex-partner co-trafficking.

| Gene | UniProt | Class | Reason | Localization / rationale |
|---|---|---|---|---|
| **CD19** | P15391 | `validated_positive` | `classical_surface_receptor` | Approved CAR-T + ADC; classical B-cell surface marker |
| **FOLR1** | P15328 | `validated_positive` | `gpi_anchored` | Approved Mirvetuximab (ELAHERE); GPI-anchored on outer leaflet |
| **MUC1** | P15941 | `disagreement_rich_positive` | `classical_surface_receptor` | Single-pass TM with large mucin ECD |
| **CD74** | P04233 | `disagreement_rich_positive` | `classical_surface_receptor` | Invariant chain on B/dendritic cell surface; Milatuzumab ADC |
| **SLC34A2** | O95436 | `disagreement_rich_positive` | `multipass_with_exposed_loops` | Apical phosphate transporter; Lifastuzumab vedotin ADC |
| **STEAP1** | Q9UHE8 | `disagreement_rich_positive` | `multipass_with_exposed_loops` | 6-pass TM with small ECLs; TCR-T + bispecific |
| **KLK2** | P20151 | `disagreement_rich_positive` | `extracellular_face_protein` | Secreted+membrane prostate antigen |
| **CLDN6** | P56747 | `disagreement_rich_positive` | `multipass_with_exposed_loops` | Tight-junction claudin |
| **GPRC5D** | Q9NZD1 | `disagreement_rich_positive` | `multipass_with_exposed_loops` | Approved bispecific + CAR-T (talquetamab) |
| **GUCY2C** | P25092 | `disagreement_rich_positive` | `classical_surface_receptor` | Approved bispecific + ADC (M9140) |
| **PSCA** | O43653 | `disagreement_rich_positive` | `gpi_anchored` | Clinical CAR-T + ADC |
| **SEZ6** | Q53EL9 | `disagreement_rich_positive` | `classical_surface_receptor` | Clinical ADC (ABBV-011) |
| **FZD7** | O75084 | `disagreement_rich_positive` | `multipass_with_exposed_loops` | Vantictumab; 7TM Wnt receptor |
| **LGR5** | O75473 | `disagreement_rich_positive` | `multipass_with_exposed_loops` | Wnt-receptor ADC programs |
| **EFNA4** | P52798 | `disagreement_rich_positive` | `gpi_anchored` | PF-06647263 ADC |
| **EREG** | O14944 | `disagreement_rich_positive` | `classical_surface_receptor` | Anti-EREG mAb programs |
| **ROS1** | P08922 | `disagreement_rich_positive` | `classical_surface_receptor` | Approved TKI + clinical ADC |
| **DLL3** | Q9NYJ7 | `disagreement_rich_positive` | `classical_surface_receptor` | Approved bispecific (tarlatamab) |
| **ROR1** | Q01973 | `disagreement_rich_positive` | `classical_surface_receptor` | Clinical CAR-T + ADC |
| **ROR2** | Q01974 | `disagreement_rich_positive` | `classical_surface_receptor` | BA3021 conditionally-active ADC |
| **CCR8** | P51685 | `disagreement_rich_positive` | `multipass_with_exposed_loops` | Anti-CCR8 mAb (Treg depletion) |
| **EPHB4** | P54760 | `disagreement_rich_positive` | `classical_surface_receptor` | Soluble EphB4 fusion programs |
| **FLT3** | P36888 | `disagreement_rich_positive` | `classical_surface_receptor` | AMG553 CAR-T, FLT3×CD3 bispecifics |
| **GFRA1** | P56159 | `disagreement_rich_positive` | `gpi_anchored` | GFRalpha-1 ADC programs |
| **GPNMB** | Q14956 | `disagreement_rich_positive` | `classical_surface_receptor` | Glembatumumab vedotin |
| **FZD10** | Q9ULW2 | `disagreement_rich_positive` | `multipass_with_exposed_loops` | OTSA101-DTPA radioimmunoconjugate |
| **TFRC** | P02786 | `disagreement_rich_positive` | `classical_surface_receptor` | Transferrin receptor 1 (CD71) |
| **LRRC32** | Q14392 | `disagreement_rich_positive` | `classical_surface_receptor` | GARP on Tregs; livmoniplimab |
| **OR1A1** | Q9P1Q5 | `disagreement_rich_positive` | `multipass_with_exposed_loops` | Olfactory receptor 1A1; 7TM GPCR |
| **DSG3** | P32926 | `disagreement_rich_positive` | `classical_surface_receptor` | Desmoglein 3; pemphigus autoantigen |
| **GYPA** | P02724 | `disagreement_rich_positive` | `classical_surface_receptor` | Glycophorin A; RBC marker |
| **DSG4** | Q86SJ6 | `disagreement_rich_positive` | `classical_surface_receptor` | Desmoglein 4; hair-follicle restricted |
| **NRROS** | Q86YC3 | `disagreement_rich_positive` | `classical_surface_receptor` | Legacy alias LRRC33; myeloid-cell analog of GARP |
| **ADORA3** | P0DMS8 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | Adenosine A3 receptor |
| **GIPR** | P48546 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | Tirzepatide approved |
| **GCGR** | P47871 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | Glucagon receptor |
| **HTR2C** | P28335 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | 7TM serotonin receptor |
| **MC1R** | Q01726 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | Afamelanotide approved |
| **GPBAR1** | Q8TDU6 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | Bile-acid receptor TGR5 |
| **BDKRB1** | P46663 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | Bradykinin B1 receptor |
| **HRH2** | P25021 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | H2 receptor (famotidine class) |
| **NPY5R** | Q15761 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | NPY5R obesity programs |
| **GRM4** | Q14833 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | Metabotropic glutamate receptor 4 |
| **AVPR1A** | P37288 | `gpcr_extracellular_pocket` | `multipass_with_exposed_loops` | Vasopressin V1A receptor |
| **B2M** | P61769 | `stable_complex_positive` | `stable_complex_partner` | β2-microglobulin — co-trafficked with MHC-I |
| **PRNP** | P04156 | `gpi_anchored_positive` | `gpi_anchored` | Cellular prion protein |
| **MSLN** | Q13421 | `gpi_anchored_positive` | `gpi_anchored` | Mesothelin |
| **CEACAM5** | P06731 | `gpi_anchored_positive` | `gpi_anchored` | CEA |
| **CD24** | P25063 | `gpi_anchored_positive` | `gpi_anchored` | CD24 |
| **BST2** | Q10589 | `gpi_anchored_positive` | `gpi_anchored` | Tetherin (dual TM + GPI architecture) |
| **DPEP1** | P16444 | `gpi_anchored_positive` | `gpi_anchored` | Renal dipeptidase |

## Contextual — conditional / borderline (27)

Conditional, induced, cycling, dual-localized, or stably (wash-resistantly) attached cases. Surface presence is real but state- or condition-dependent. **pMHC presentation alone does not qualify** — see the "No" section.

| Gene | UniProt | Class | Reason | Localization / rationale |
|---|---|---|---|---|
| **CALR** | P27797 | `induced_borderline` | `cell_state_induced` | ER-resident at baseline; outer leaflet during ICD |
| **HSPA1A** | P0DMV8 | `induced_borderline` | `cell_state_induced` | Cytoplasmic; tumor-stress-induced surface |
| **HSPA5** | P11021 | `induced_borderline` | `cell_state_induced` | ER chaperone (GRP78/BiP); ER-stress translocation |
| **LAMP1** | P11279 | `induced_borderline` | `lysosomal_exocytosis` | CD107a; lysosomal → PM via exocytosis |
| **LAMP2** | P13473 | `induced_borderline` | `lysosomal_exocytosis` | CD107b; same exocytosis mechanism as LAMP1 |
| **TGOLN2** | O43493 | `induced_borderline` | `dual_localization` | TGN46; continuous TGN ↔ PM recycling |
| **B4GALT1** | P15291 | `induced_borderline` | `tissue_restricted_surface` | Sperm-specific cell-surface form (ZP adhesion) |
| **VDAC1** | P21796 | `induced_borderline` | `dual_localization` | pl-VDAC on B cells, sperm, cancer cells |
| **BAX** | Q07812 | `induced_borderline` | `cell_state_induced` | Surface BAX as apoptotic-cell marker |
| **STIM1** | Q13586 | `induced_borderline` | `dual_localization` | ER-PM junctions during SOCE |
| **IZUMO1** | Q8IYV9 | `induced_borderline` | `cell_state_induced` | Acrosomal cap; PM-exposed after acrosome reaction |
| **IZUMO4** | Q1ZYL8 | `induced_borderline` | `cell_state_induced` | Same acrosomal-cap → PM biology as IZUMO1 |
| **SRC** | P12931 | `wrong_side_borderline` | `cell_state_induced` | Inner-leaflet Src family; ecto-SRC in cancer |
| **LYN** | P07948 | `wrong_side_borderline` | `cell_state_induced` | Inner-leaflet Src-family; cell-surface LYN reported |
| **HSPD1** | P10809 | `dual_localization_borderline` | `dual_localization` | HSP60; surface-reported DAMP / tumor marker |
| **ATP5F1B** | P06576 | `dual_localization_borderline` | `dual_localization` | Mitochondrial matrix + ecto-F1-ATPase |
| **LAMP3** | Q9UQV4 | `lysosomal_exocytosis_borderline` | `lysosomal_exocytosis` | DC-LAMP; PM via exocytosis on mature DCs |
| **CD63** | P08962 | `lysosomal_exocytosis_borderline` | `lysosomal_exocytosis` | Tetraspanin TSPAN30; exosomal-surface marker |
| **CD68** | P34810 | `lysosomal_exocytosis_borderline` | `lysosomal_exocytosis` | Macrosialin; macrophage exocytosis |
| **SCARB2** | Q14108 | `lysosomal_exocytosis_borderline` | `lysosomal_exocytosis` | LIMP-2; lysosomal + EV71 entry receptor |
| **TGFB1** | P01137 | `surface_attachment_borderline` | `stable_surface_attachment` | Latent TGF-β1 disulfide-tethered to GARP |
| **C3** | P01024 | `surface_attachment_borderline` | `stable_surface_attachment` | C3b thioester-deposited on opsonized cells |
| **CRISP1** | P54107 | `surface_attachment_borderline` | `stable_surface_attachment` | Epididymal CRISP1 stably attached to sperm PM |

## No — not surface accessible (49)

Cytoplasmic, nuclear, mitochondrial-internal, endomembrane-resident, nuclear-envelope, inner-leaflet-anchored, secreted-only, or pMHC-only-intracellular.

| Gene | UniProt | Class | Reason | Localization / rationale |
|---|---|---|---|---|
| **PMEL** | P40967 | `pmhc_only_negative` | `pmhc_only_intracellular` | Melanosomal; Tebentafusp targets gp100·HLA, not PMEL on the cell surface |
| **PRAME** | P78395 | `pmhc_only_negative` | `pmhc_only_intracellular` | Cancer-testis; brenetafusp / IMC-F106C target the pMHC |
| **AKT2** | P31751 | `approved_drug_intracellular_negative` | `cytoplasmic` | Cytoplasmic; capivasertib target |
| **BRAF** | P15056 | `approved_drug_intracellular_negative` | `cytoplasmic` | Cytoplasmic; vemurafenib/dabrafenib approved |
| **BTK** | Q06187 | `approved_drug_intracellular_negative` | `cytoplasmic` | Cytoplasmic; ibrutinib approved |
| **HDAC6** | Q9UBN7 | `approved_drug_intracellular_negative` | `cytoplasmic` | Cytoplasmic/perinuclear |
| **IKBKB** | O14920 | `approved_drug_intracellular_negative` | `cytoplasmic` | IKK-β |
| **JAK1** | P23458 | `approved_drug_intracellular_negative` | `cytoplasmic` | Cytoplasmic JAK1 |
| **JAK2** | O60674 | `approved_drug_intracellular_negative` | `cytoplasmic` | Cytoplasmic; ruxolitinib approved |
| **JAK3** | P52333 | `approved_drug_intracellular_negative` | `cytoplasmic` | Cytoplasmic; tofacitinib target |
| **LRRK2** | Q5S007 | `approved_drug_intracellular_negative` | `cytoplasmic` | Cytoplasmic/peripheral |
| **MAP2K1** | Q02750 | `approved_drug_intracellular_negative` | `cytoplasmic` | MEK1 |
| **MAP2K2** | P36507 | `approved_drug_intracellular_negative` | `cytoplasmic` | MEK2 |
| **SYK** | P43405 | `approved_drug_intracellular_negative` | `cytoplasmic` | Spleen TK |
| **TYK2** | P29597 | `approved_drug_intracellular_negative` | `cytoplasmic` | Cytoplasmic; deucravacitinib approved |
| **APPL1** | Q9UKG1 | `opencell_vesicle_negative` | `endomembrane_resident` | Signaling endosome; M1 false positive |
| **A2M** | P01023 | `secreted_negative` | `secreted_only` | α2-macroglobulin |
| **APOB** | P04114 | `secreted_negative` | `secreted_only` | Apolipoprotein B-100 |
| **F2** | P00734 | `secreted_negative` | `secreted_only` | Prothrombin; Ca²⁺-dependent reversible Gla-PS recruitment |
| **FN1** | P02751 | `secreted_negative` | `secreted_only` | Fibronectin ECM glycoprotein |
| **IGF1** | P05019 | `secreted_negative` | `secreted_only` | IGF-1 hormone |
| **IL6** | P05231 | `secreted_negative` | `secreted_only` | IL-6 cytokine |
| **TF** | P02787 | `secreted_negative` | `secreted_only` | Transferrin |
| **VEGFA** | P15692 | `secreted_negative` | `secreted_only` | VEGF-A |
| **ZP3** | P21754 | `secreted_negative` | `secreted_only` | Zona pellucida 3; matrix-deposited |
| **ABCB9** | Q9NP78 | `wrong_compartment_negative` | `endomembrane_resident` | Polytopic TM but lysosomal |
| **ATG9A** | Q7Z3C6 | `wrong_compartment_negative` | `endomembrane_resident` | Cycles Golgi/endosomes/autophagosomes; never PM |
| **GALNT1** | Q10472 | `wrong_compartment_negative` | `endomembrane_resident` | Golgi glycosyltransferase |
| **ITPR1** | Q14643 | `wrong_compartment_negative` | `endomembrane_resident` | IP3R-1; ER Ca²⁺ channel |
| **ITPR3** | Q14573 | `wrong_compartment_negative` | `endomembrane_resident` | IP3R-3; ER Ca²⁺ channel |
| **NUP210** | Q8TEM1 | `wrong_compartment_negative` | `nuclear_envelope` | Nuclear pore TM |
| **RPN1** | P04843 | `wrong_compartment_negative` | `endomembrane_resident` | Ribophorin 1; ER OST |
| **RPN2** | P04844 | `wrong_compartment_negative` | `endomembrane_resident` | Ribophorin 2; ER OST |
| **SCAP** | Q12770 | `wrong_compartment_negative` | `endomembrane_resident` | SREBP cleavage-activating; ER cholesterol sensor |
| **SEC61G** | P60059 | `wrong_compartment_negative` | `endomembrane_resident` | Sec61 translocon γ; ER |
| **SUN1** | O94901 | `wrong_compartment_negative` | `nuclear_envelope` | SUN1; inner nuclear membrane (LINC) |
| **SUN2** | Q9UH99 | `wrong_compartment_negative` | `nuclear_envelope` | SUN2; inner nuclear membrane |
| **SYNE1** | Q8NF91 | `wrong_compartment_negative` | `nuclear_envelope` | Nesprin-1; outer nuclear membrane |
| **SYNE2** | Q8WXH0 | `wrong_compartment_negative` | `nuclear_envelope` | Nesprin-2; outer nuclear membrane |
| **TMED9** | Q9BVK6 | `wrong_compartment_negative` | `endomembrane_resident` | p24 cargo receptor; ER-Golgi cycling |
| **TMED10** | P49755 | `wrong_compartment_negative` | `endomembrane_resident` | p24 cargo receptor; ER-Golgi cycling |
| **HMGB1** | P09429 | `nuclear_negative` | `nuclear` | Chromatin / nucleoplasmic; released as soluble DAMP |
| **HNRNPK** | P61978 | `nuclear_negative` | `nuclear` | Nucleoplasmic RNA-binding protein |
| **GNAQ** | P50148 | `wrong_side_negative` | `inner_leaflet_anchored` | Heterotrimeric Gα-q |
| **GNB1** | P62873 | `wrong_side_negative` | `inner_leaflet_anchored` | Gβ-1 |
| **HCK** | P08631 | `wrong_side_negative` | `inner_leaflet_anchored` | Src-family kinase |
| **KRAS** | P01116 | `wrong_side_negative` | `inner_leaflet_anchored` | Inner-leaflet farnesylated |
| **NRAS** | P01111 | `wrong_side_negative` | `inner_leaflet_anchored` | Inner-leaflet Ras |
| **RAC1** | P63000 | `wrong_side_negative` | `inner_leaflet_anchored` | Inner-leaflet Rac |
| **RHOA** | P61586 | `wrong_side_negative` | `inner_leaflet_anchored` | Inner-leaflet Rho |

## Class composition

| Class | Verdict | Count |
|---|---|---:|
| `validated_positive` | `yes` | 5 |
| `disagreement_rich_positive` | `yes` | 43 |
| `gpcr_extracellular_pocket` | `yes` | 12 |
| `stable_complex_positive` | `yes` | 1 |
| `gpi_anchored_positive` | `yes` | 12 |
| `induced_borderline` | `contextual` | 12 |
| `wrong_side_borderline` | `contextual` | 2 |
| `dual_localization_borderline` | `contextual` | 4 |
| `lysosomal_exocytosis_borderline` | `contextual` | 4 |
| `surface_attachment_borderline` | `contextual` | 3 |
| `approved_drug_intracellular_negative` | `no` | 13 |
| `opencell_vesicle_negative` | `no` | 1 |
| `secreted_negative` | `no` | 9 |
| `wrong_compartment_negative` | `no` | 15 |
| `nuclear_negative` | `no` | 2 |
| `wrong_side_negative` | `no` | 7 |
| `pmhc_only_negative` | `no` | 2 |

**Totals:** 71 yes + 27 contextual + 49 no = **147**.

## Recent revisions

- **Added LY6K + LYPD3** (both 2/5 — SFY, CSPA only) — LY6/PLAUR-family GPI-anchored cancer-testis / tumor antigens. Same architectural pattern as LYPD1 / CD24; tests recognition of GPI architecture from family-membership when UP / GO / HPA all miss it.
- **Added 3 more low-DB-cover candidates** (AMHR2 2/5, TM4SF1 2/5, ALPPL2 0/5 M1-escape) — all bona-fide surface (TGFβ-receptor-family TM, tetraspanin, GPI-anchored phosphatase respectively); high-leverage agent-rescue test cases. ALPPL2 sits with STEAP2 as the second M1-escape entry.
- **Added 18 candidate-surface entries** for tumor-antigen / surfaceome coverage: EPCAM, MCSP (CSPG4), TACSTD2, CD276, CEACAM6, MUC16, PTK7, CLDN18 (CLDN18.2), FOLH1 (PSMA), GPC3, NECTIN4, CA9, DLK1, GPC2, LYPD1, SSTR2, STEAP2 (all `yes` across the 5/5 → 0/5 DB-coverage range), plus TYRP1 as `contextual / dual_localization` (melanosomal-dominant with documented melanoma-surface fraction — same biology family as PMEL but cleaner surface evidence). Three approved-drug anchors added to `validated_positive`: TACSTD2 (Trodelvy / Dato-DXd), FOLH1 (Pluvicto), NECTIN4 (Padcev). STEAP2 is a deliberate 0/5 M1-escape test case (not in pipeline; tests family-extrapolation from STEAP1).
- EREG relabeled `yes → contextual` / `classical_surface_receptor → dual_localization`: dominant detected biologically active form is the soluble shed ligand; TM precursor transits PM transiently before ADAM/MMP shedding.
- **pMHC excluded from triage.** Schema dropped `pmhc_presented_peptide` from `_CONTEXTUAL_REASONS` and added `pmhc_only_intracellular` to `_NO_REASONS`. The retained pMHC entries (PMEL, PRAME) moved from `contextual` (`pmhc_borderline`) → `no` (`pmhc_only_negative`); KAAG1, CTAG1B, MAGEA4, WT1, AFP, SSX2 were removed from the benchmark. Rationale: every intracellular protein has potentially MHC-presentable peptides, so pMHC presentation alone is not a discriminating signal for surface accessibility of the *protein body* — TCR / TCR-mimic / bispecific programs are tracked downstream as a separate axis.
- Added `ground_truth_reason` column populated against the schema's `TriageReason` enum. Every row roundtrips through `TriageRecordDraft` (`tests/test_triage_benchmark_schema.py`).
- Reason renamed: `covalent_surface_attachment` → `stable_surface_attachment` to match the loosened scope (covalent *or* wash-resistant non-covalent post-translational anchoring). Schema version bumped `v0.7.0 → v0.8.0`.
- Migrated `ground_truth_verdict` vocabulary `maybe → contextual` to match the schema literal. Also fixed a silent scoring bug: `scoring.py` / `database_baselines.py` / `triage_bench_db_barplot.py` previously compared against `"maybe"` only, treating the agent's `"contextual"` outputs as `no`.
- Relabel batch: PRNP `contextual → yes` (`gpi_anchored`); LRRC33 `contextual → yes` (`classical_surface_receptor`); TMED9, TMED10 `contextual → no` (`endomembrane_resident`); ZP3 `yes → no` (`secreted_only` — matrix-deposited); IZUMO1, IZUMO4 `yes → contextual` (`cell_state_induced` — acrosome-reaction-dependent); ATP5F1B `no → contextual` (`dual_localization` — documented ecto-F1-ATPase); CRISP1 `yes → contextual` (`stable_surface_attachment` under loosened wash-resistant definition).
- Removed: TGFB2, TGFB3 (β2/β3 GARP/LRRC33 surface tethering not well-established); KAAG1, CTAG1B, MAGEA4, WT1, AFP, SSX2 (pure pMHC cases redundant with PMEL+PRAME under the new policy).
- Class renames: `covalent_attachment_borderline` → `surface_attachment_borderline`; `secreted_borderline` folded in; `pmhc_borderline` → `pmhc_only_negative` (under the new pMHC-excluded policy); `tissue_restricted_positive` deleted (members redistributed); `mitochondrial_internal_negative` deleted (sole member moved to `dual_localization_borderline`).
