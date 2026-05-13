# Plan: Redesign deep-dive agent around surface accessibility

## Context

The current `surface_annotator` "deep dive" agent ([orchestrator.py](src/accessible_surfaceome/agents/surface_annotator/orchestrator.py), schema [models.py](src/accessible_surfaceome/tools/_shared/models.py) v0.5.1) is heavily **translational** — it emits `targetability` tiers, ADC properties, therapeutic landscape (drugs/trials/patents), and modality recommendations. These bake in commercial assumptions and aren't the right output for early target-discovery work.

We want a redesigned agent whose single job is to answer: **"Is this candidate surface protein actually accessible, and what's the evidence?"** — the question a target-discovery scientist or pharma/biotech consultant asks before committing budget. Outputs must:

1. **Stay biological, not commercial.** No drug pipelines, no modality picks, no ADC math. Just: is it on the surface, in what cells/contexts, with what risks to accessibility.
2. **Lean on LLM for synthesis where it shines** — reading papers, reconciling conflicting cell-line evidence, extracting methods/antibodies, judging dual-localization or epitope masking.
3. **Use deterministic tools sparingly but rigorously** — AlphaFold DB, Ensembl Compara, DeepTMHMM are pre-fetched by the orchestrator before the LLM sees the gene. Their output lives in its own block, untouched by the model.
4. **Mark the determinism boundary structurally** in the schema, so a reader (and downstream audit) can tell at a glance which numbers came from a tool vs. the model.

Only a couple of mock runs exist on the current schema, so we're free to drop the existing D1 tables and ship a fresh v1.0.0 of the record under the existing `surface_annotator` / `SurfaceomeRecord` / `data/annotations/` / `deep_dive_run` naming — keep the straightforward existing names, replace the internals.

## Page mockup (scientific order)

This is what a reader sees in the viewer for a single gene. Section order mirrors the way a target-discovery scientist actually reads the question — headline first, surface claim second, biological context third, then the deterministic structural blocks, then the accessibility risks. Worked example uses **EGFR** placeholder content.

```
═══════════════════════════════════════════════════════════════════════
  EGFR — Surface Targetability Brief
  schema v1.0.0 · generated 2026-05-13 · model claude-opus-4-7
═══════════════════════════════════════════════════════════════════════

┌─ EXECUTIVE SUMMARY ────────────────────────────────────────────────┐
│ EGFR is a single-pass type I receptor with robust, multi-context   │
│ surface evidence — high expression in epithelial lineages,         │
│ extensively profiled by flow cytometry, mass spec, and IF. ECD is  │
│ large (~620 aa), well-folded (mean pLDDT 91), and highly conserved │
│ to mouse and cyno. Primary accessibility risks: regulated          │
│ shedding (sEGFR via ADAM17), endocytic turnover after ligand       │
│ binding, and paralog cross-reactivity (HER2/3/4 share ECD          │
│ subdomain folds).                                                  │
│                                                                     │
│   Surface targetability:  HIGH       Subcategory: single-pass T1   │
│   Evidence grade:         direct_multi_method                       │
│   Confidence:             HIGH       State dependence: MODERATE     │
│   Headline risks:         shed_form · paralog_cross_reactivity     │
│   ("Targetability" here = physical/biological reachability —        │
│    can a binder reach this protein. Not the commercial sense.)     │
└─────────────────────────────────────────────────────────────────────┘

┌─ FILTERS / TAGS  (catalog-facing, all closed enums) ───────────────┐
│                                                                     │
│  TARGETABILITY                                                      │
│    overall=HIGH · confidence=HIGH · subcategory=single_pass_T1     │
│    evidence_grade=direct_multi_method · ecd_accessibility=LARGE     │
│    evidence_density=HIGH                                            │
│                                                                     │
│  EXPRESSION                                                         │
│    level=HIGH · breadth=BROAD · surface_specificity=MIXED          │
│                                                                     │
│  RISKS                                                              │
│    ✓ has_shed_form                  ✓ has_secreted_form             │
│    ✗ coreceptor_for_expression                                       │
│    ✓ paralog_cross_reactivity       ✓ epitope_masking               │
│    ✗ has_restricted_subdomain                                       │
│                                                                     │
│  CROSS-SPECIES (deterministic — Compara ECD % identity)             │
│    mouse=88.2% · cyno=99.1% · rat=88.0%                             │
│                                                                     │
│  TOPOLOGY                                                           │
│    n_term_extracellular=TRUE · c_term_extracellular=FALSE          │
│                                                                     │
│  QUALITY                                                            │
│    knowledge_gaps_max_impact=HIGH                                   │
│                                                                     │
│  (Catalog page renders each as a chip; click to filter the gene    │
│  list. Per-gene page surfaces these in the executive header above.) │
└─────────────────────────────────────────────────────────────────────┘

┌─ 1. SURFACE ACCESSIBILITY EVIDENCE ────────────────────────────────┐
│                                                                     │
│  Evidence grade:  DIRECT_MULTI_METHOD                               │
│  ----------------------------------------------------------------   │
│  Live-cell flow with ECD antibody, surface biotinylation MS, and    │
│  non-permeabilized IF all confirm endogenous surface localization   │
│  in three independent epithelial lineages.                          │
│                                                                     │
│  Methods + antibodies  (each ties to its expression observations)  │
│  ----------------------------------------------------------------   │
│   • live_cell_flow / nonpermeabilized                               │
│     anti-EGFR clone 528 (ECD epitope), endogenous expression        │
│     accessibility: DIRECT_SURFACE_ACCESSIBILITY                     │
│     observed in:                                                    │
│        • A431 (cell_line · epidermoid carcinoma)  HIGH   [evi_02]   │
│        • Primary keratinocytes (primary_human_cell) HIGH [evi_18]   │
│        • Hematopoietic PBMCs (primary_human_cell) ABSENT [evi_22]   │
│                                                                     │
│   • surface_biotinylation / nonpermeabilized                        │
│     label-free LC-MS/MS, endogenous expression                      │
│     accessibility: DIRECT_SURFACE_ACCESSIBILITY                     │
│     observed in:                                                    │
│        • A431 (cell_line)                          HIGH   [evi_07]  │
│        • Normal lung biopsy (primary_human_tissue) HIGH   [evi_11]  │
│                                                                     │
│   • nonpermeabilized_IF                                             │
│     cetuximab + panitumumab (ECD epitopes), endogenous              │
│     accessibility: SUPPORTS_SURFACE_LOCALIZATION                    │
│     observed in:                                                    │
│        • Normal skin (primary_human_tissue) HIGH         [evi_18]   │
│        • Colon adenocarcinoma (patient_sample) HIGH      [evi_14]   │
│                                                                     │
│  (Cell lines and tissues are listed inline with the method that     │
│   measured them — single source of truth, primary human samples     │
│   shown first when present.)                                        │
│                                                                     │
│  Contradicting evidence  (typed + severity + interpretation)       │
│  ----------------------------------------------------------------   │
│   • Mitochondrial pool reported in stressed cells       [evi_31]    │
│     type=intracellular_pool · severity=LOW                          │
│     Minor stress-induced intracellular fraction does not negate     │
│     dominant plasma-membrane localization in baseline state.        │
│   • Nuclear-translocated fraction (ligand-induced)      [evi_27]    │
│     type=alternative_localization · severity=LOW                    │
│     Ligand-stim ~5% nuclear translocation; majority remains on      │
│     the surface — does not undermine accessibility claim.           │
└─────────────────────────────────────────────────────────────────────┘

┌─ 2. BIOLOGICAL CONTEXT ────────────────────────────────────────────┐
│                                                                     │
│  Tissues / cell types / cell states (expression yes/no)             │
│  ----------------------------------------------------------------   │
│   tissue          present  cell types               states          │
│   ────────────    ───────  ──────────────────────   ───────────     │
│   skin              ✓      keratinocytes            basal, suprabas │
│   lung              ✓      alveolar T2, club        normal, fibrotic│
│   colon             ✓      enterocytes              normal, EMT     │
│   blood             ✗      —                        —               │
│                                                                     │
│  Subcellular localization                                           │
│  ----------------------------------------------------------------   │
│   Primary compartment:       plasma_membrane                        │
│   Dual localization:                                                │
│      • endosome (post-internalization)    ~25% under EGF  [evi_27]  │
│      • nucleus  (ligand-stim, minor)      ~5%             [evi_27]  │
│                                                                     │
│  Anatomical accessibility  (where can a binder physically reach?)  │
│  ----------------------------------------------------------------   │
│   context              orientation      implication                 │
│   ───────────────      ─────────────    ──────────────              │
│   epithelial monolayer basolateral      RESTRICTED in polarized     │
│                                         tight-junction-intact       │
│                                         tissue  [evi_22]            │
│   carcinoma (EMT)      lateral/exposed  FAVORABLE — junction        │
│                                         disruption exposes ECD      │
│                                         [evi_36]                    │
│   resting keratinocyte basolateral      RESTRICTED  [evi_18]        │
│                                                                     │
│  Accessibility modulation  (disease / state relocalization)        │
│  Categories aligned with the triage agent's contextual taxonomy     │
│  (cell_state_induced, tissue_restricted, etc.) + expansions.       │
│  ----------------------------------------------------------------   │
│   • category=disease_state_induced                                  │
│     Normal: basolateral in polarized epithelium                     │
│     Disease: depolarized in invasive carcinoma — apical/lateral     │
│     surface exposure increases                            [evi_36]  │
│   • category=activation_induced                                     │
│     Resting: surface pool at steady-state                           │
│     Stimulated: post-EGF endocytosis depletes surface ~25% within   │
│     30 min — dwell time becomes assay-relevant            [evi_27]  │
│                                                                     │
│  Exocytosis / recycling evidence                                    │
│  ----------------------------------------------------------------   │
│      • constitutive recycling from sorting endosomes      [evi_29]  │
└─────────────────────────────────────────────────────────────────────┘

┌─ 3. ISOFORMS  [deterministic — UniProt/Ensembl + DeepTMHMM 1.0.24]─┐
│                                                                     │
│   isoform     UniProt    TM count   N-term   ECD len   ICD len      │
│   ───────     ───────    ────────   ──────   ───────   ───────      │
│   canonical   P00533-1      1       extra      621       542        │
│   isoform-2   P00533-2      1       extra      621       430        │
│   isoform-3   P00533-3      0         —         88        0  ◀ sol  │
│   isoform-4   P00533-4      1       extra      490       542        │
│                                                                     │
│  Canonical caveat: P00533-1 is the UniProt canonical AND the        │
│  dominant transcript in epithelial tissues — no tissue-specific     │
│  mismatch flagged.                                                  │
│                                                                     │
│  (Per-isoform LLM interpretation is intentionally deferred —        │
│   isoforms render as deterministic topology only in v1.0.0.         │
│   The executive summary carries any biological synthesis the LLM    │
│   wants to make about isoform implications.)                        │
└─────────────────────────────────────────────────────────────────────┘

┌─ 4. ORTHOLOGS  [deterministic — Compara r112 + DeepTMHMM 1.0.24] ──┐
│                                                                     │
│   species  isoform           UniProt    TM  ECD len   ECD %id   sim │
│   ───────  ─────────────     ────────   ──  ───────   ──────   ──── │
│   mouse    canonical (Egfr)  Q01279     1     616    88.2%   94.1% │
│   mouse    alt isoform-2     Q01279-2   1     614    87.8%   93.6% │
│   rat      canonical (Egfr)  Q9QX70     1     617    88.0%   94.3% │
│   cyno     canonical (EGFR)  XP_005553  1     621    99.1%   99.6% │
│   cyno     alt isoform-2     XP_005553… 1     621    99.1%   99.6% │
│                                                                     │
│  (Per-species LLM interpretation is intentionally deferred —       │
│   orthologs render as deterministic ECD-conservation numbers and   │
│   alternative-isoform topology only in v1.0.0. The executive       │
│   summary carries any biological synthesis the LLM wants to make   │
│   about cross-species relevance.)                                  │
└─────────────────────────────────────────────────────────────────────┘

┌─ 5. ACCESSIBILITY RISKS  (severity ≠ evidence strength) ───────────┐
│                                                                     │
│  • Partner required for surface expression?                         │
│      Surface-expression dependency:  NONE                           │
│        EGFR reaches the plasma membrane unassisted; no obligate     │
│        partner required for trafficking.                  [evi_46]  │
│      (TCR/CD3 would be REQUIRED — CD3 retains TCR in the ER         │
│       without it. Function-side dependency was considered but is    │
│       out of scope for v1.0.0; signaling biology lives elsewhere.) │
│                                                                     │
│  • Shed form              severity=MODERATE · evidence=STRONG       │
│      ADAM17-mediated, soluble sEGFR detectable in serum             │
│      Mature surface pool is the dominant pool; shedding is          │
│      detectable but not depleting.                     [evi_33,34]  │
│                                                                     │
│  • Secreted form          severity=LOW · evidence=STRONG            │
│      isoform-3 is predicted soluble (no TM helix), but biological   │
│      relevance is unconfirmed (transcript only) — risk gated on     │
│      protein-level expression evidence.                             │
│                                                                     │
│  • Restricted membrane subdomain  severity=MODERATE · evi=STRONG    │
│      basolateral in polarized normal epithelium                     │
│      Epithelial junctions limit luminal-side access in healthy      │
│      tissue; junction disruption in carcinoma relieves restriction. │
│                                                       [evi_22,36]   │
│                                                                     │
│  • Similar paralogs       severity=MODERATE · evidence=STRONG       │
│       paralog    ECD id    cross-reactivity risk                    │
│       HER2       45.1%     MODERATE                  [evi_41]       │
│       HER3       42.7%     MODERATE                  [evi_41]       │
│       HER4       43.0%     MODERATE                  [evi_41]       │
│      Domain folds are conserved; binder specificity should be       │
│      empirically tested against the full ERBB family.               │
│                                                                     │
│  • ECD accessibility size class:  LARGE                             │
│      621 aa extracellular region; multiple accessible epitopes      │
│      plausible, but actual exposure depends on folding,             │
│      glycosylation, complex state, and membrane subdomain.          │
│                                                                     │
│  • Epitope masking        severity=MODERATE · evidence=STRONG       │
│      Heavy N-glycosylation on domain III; conformational gating     │
│      by domain II tether.                                [evi_45]   │
└─────────────────────────────────────────────────────────────────────┘

┌─ APPENDIX — STRUCTURE [deterministic, AlphaFold DB] ───────────────┐
│   AFDB ID: AF-P00533-F1-model_v4                                    │
│   ECD mean pLDDT: 91.4   ECD disordered fraction: 3.1%              │
│   ECD solvent-accessible fraction (SASA proxy): 0.62                │
│                                                                     │
│   Structure data from AlphaFold DB · © DeepMind / EMBL-EBI ·        │
│   licensed CC BY 4.0 · cite Jumper et al., Nature 2021;             │
│   Varadi et al., NAR 2024                                           │
└─────────────────────────────────────────────────────────────────────┘

┌─ EVIDENCE LEDGER ──────────────────────────────────────────────────┐
│   45 evidence entries · 38 primary · 7 secondary · 31 PMC OA       │
│   [expandable list with substring-validated quotes + SourceRefs]   │
└─────────────────────────────────────────────────────────────────────┘

┌─ DATA SOURCES ─────────────────────────────────────────────────────┐
│  • AlphaFold DB structures — CC BY 4.0 (DeepMind / EMBL-EBI)        │
│  • Ensembl Compara orthologs — open data with citation              │
│    (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)              │
│  • DeepTMHMM topology — DTU Health Tech (Hallgren et al. 2022;      │
│    academic-use service)                                            │
│  • UniProt — CC BY 4.0 (UniProt Consortium)                         │
└─────────────────────────────────────────────────────────────────────┘
```

The mockup is also the contract for the viewer redesign: section order, headline-card layout, and the **deterministic banner** (`[deterministic — TOOL vN]`) on isoforms/orthologs/structure tell a reader at a glance which numbers came from a tool vs. the model.

## Schema-annotated mockup

Same mockup, each visible element labeled with its Pydantic field path + type so the page-to-record mapping is unambiguous. Provenance column: **D** = deterministic (orchestrator-populated), **L** = LLM (agent-emitted).

### Header card

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| `EGFR` | `gene.hgnc_symbol` | `str` | D |
| `Surface Targetability Brief` | (viewer-static title) | — | — |
| `schema v1.0.0` | `schema_version` | `Literal["1.0.0"]` | D |
| `generated 2026-05-13` | `generated_at` | `datetime` | D |
| `model claude-opus-4-7` | `model_path` | `str` | D |

### Executive summary

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| "EGFR is a single-pass type I…" prose | `executive_summary.one_paragraph` | `str` (≤600) | L |
| `HIGH` (targetability) | `executive_summary.surface_targetability` | `Literal["high","moderate","low","uncertain"]` | L |
| `direct_multi_method` | `executive_summary.evidence_grade_summary` | `Literal["direct_multi_method","direct_single_method","supportive_but_indirect","conflicting","weak"]` | L |
| `HIGH` (confidence) | `executive_summary.confidence` | `Literal["high","moderate","low"]` | L |
| `MODERATE` (state dependence) | `executive_summary.state_dependence` | `Literal["low","moderate","high","unclear"]` — how much does surface presence/exposure shift with cell state, tissue context, or disease state? Cross-checks against `biological_context.accessibility_modulation[]`. | L |
| `single-pass T1` | `executive_summary.subcategory` | `Literal["single_pass_T1","single_pass_T2","multi_pass","GPCR","GPI_anchored","tetraspanin","ion_channel","transporter","other"]` | L |
| `shed_form · paralog_cross_reactivity` | `executive_summary.headline_risks` | `list[Literal["shed_form","secreted_form","co_receptor","paralog_cross_reactivity","ecd_too_small","epitope_masked","isoform_decoy","restricted_subdomain","other"]]` (max 3) | L |
| (cite chips, not shown) | `executive_summary.cited_evidence_ids` | `list[str]` (→ `evidence[].evidence_id`) | L |

Two notes on the top-line summary:

- The numeric `accessibility_score: float` was dropped — categorical `surface_targetability` + categorical `confidence` carry the same information without implying a calibrated rubric we don't have.
- **"Targetability" is the biological/physical sense here** — *can a binder physically reach this protein on the cell surface?* It is intentionally NOT the commercial sense (worth pursuing as a drug target). The downstream sections still carry `accessibility`-named fields (`accessibility_risks`, `anatomical_accessibility`, `accessibility_modulation`, `accessibility_relevance`) — only the top-line summary and its filter chip use the `targetability` label so readers get a familiar headline word.

### Filters / tags card

Top-level `filters` block — every value is a closed enum, `bool`, or `list[enum]`. The catalog/index page reads these to render filter chips and faceted search; the per-gene executive header surfaces the same chips. Provenance column: **D** = derived by orchestrator from deeper fields (no extra LLM work), **L** = LLM emits directly (typically rolling-up judgment).

| Rendered chip | Schema path | Type | Prov | Derivation rule (D-source) |
|---|---|---|---|---|
| `overall=HIGH` | `filters.surface_targetability` | `Literal["high","moderate","low","uncertain"]` | D | `executive_summary.surface_targetability` |
| `confidence=HIGH` | `filters.confidence` | `Literal["high","moderate","low"]` | D | `executive_summary.confidence` |
| `subcategory=single_pass_T1` | `filters.subcategory` | `Literal["single_pass_T1","single_pass_T2","multi_pass","GPCR","GPI_anchored","tetraspanin","ion_channel","transporter","other"]` | D | `executive_summary.subcategory` |
| `evidence_grade=direct_multi_method` | `filters.evidence_grade` | `Literal["direct_multi_method","direct_single_method","supportive_but_indirect","conflicting","weak"]` | D | `surface_evidence.evidence_grade` |
| `ecd_accessibility=LARGE` | `filters.ecd_accessibility_class` | `Literal["large","moderate","small","minimal","none"]` | D | `accessibility_risks.ecd_size_assessment.ecd_accessibility_class` |
| `evidence_density=HIGH` | `filters.evidence_density` | `Literal["low","moderate","high"]` | D | bucketed from `evidence_count` (≥30/≥10/else) |
| `level=HIGH` | `filters.expression_level` | `Literal["high","moderate","low","absent"]` | L | LLM rollup of `surface_evidence.expression_levels[]` |
| `breadth=BROAD` | `filters.expression_breadth` | `Literal["pan_tissue","broad","restricted","rare"]` | L | LLM judgment from `biological_context.tissues[]` |
| `surface_specificity=MIXED` | `filters.surface_specificity` | `Literal["surface_dominant","mixed","mostly_intracellular"]` | L | LLM rollup of `subcellular_localization.dual_localization[]` |
| `has_shed_form` (bool) | `filters.has_shed_form` | `bool` | D | `accessibility_risks.shed_form.present` |
| `has_secreted_form` (bool) | `filters.has_secreted_form` | `bool` | D | `accessibility_risks.secreted_form.present` |
| `coreceptor_for_expression` (bool) | `filters.requires_coreceptor_for_expression` | `bool` | D | `accessibility_risks.co_receptor_requirements.surface_expression_dependency == "required"` |
| `paralog_cross_reactivity` (bool) | `filters.has_paralog_cross_reactivity_risk` | `bool` | D | any `accessibility_risks.paralog_cross_binding_risk[].cross_reactivity_assessment ∈ {high, moderate}` |
| `epitope_masking` (bool) | `filters.has_epitope_masking` | `bool` | D | `accessibility_risks.epitope_masking.severity ∈ {high, moderate}` |
| `restricted_subdomain` (bool) | `filters.has_restricted_subdomain` | `bool` | D | `accessibility_risks.restricted_subdomain.present == True` OR any `biological_context.anatomical_accessibility[].accessibility_implication == "restricted"` |
| `mouse=88.2% · cyno=99.1%` | `filters.mouse_ortholog_ecd_pct_identity` + `filters.cyno_ortholog_ecd_pct_identity` | `float [0.0–100.0]` each | D | `deterministic_features.orthologs.{species}[is_canonical].ecd_pct_identity_to_human_canonical` — pulled straight from Compara, no LLM rollup |
| `n_term_extracellular` (bool) | `filters.n_term_extracellular` | `bool` | D | `deterministic_features.canonical_topology.n_terminal_orientation == "extracellular"` |
| `c_term_extracellular` (bool) | `filters.c_term_extracellular` | `bool` | D | `deterministic_features.canonical_topology.c_terminal_orientation == "extracellular"` |
| `knowledge_gaps_max_impact=high` | `filters.knowledge_gaps_max_impact` | `Literal["high","moderate","low","none"]` | D | `max(g.impact_on_confidence for g in knowledge_gaps, default="none")` — replaces the earlier boolean `has_knowledge_gaps`, which was TRUE for almost every gene and carried no signal |

**Filters-only rule (no duplication):** the three LLM-emitted dimensions (`expression_level`, `expression_breadth`, `surface_specificity`) live ONLY in `filters`. The deep `surface_evidence.expression_levels[]` list still carries per-context detail ("epithelial tumors HIGH; blood ABSENT") but the rolled-up filter values aren't repeated there. Zero drift risk.

**D1 indexing:** every filter is a top-level column on `deep_dive_run`, so queries like *"single_pass_T1 receptors with broad expression, no shed form, mouse_efficacy"* are an indexed scan, not JSON traversal.

### Section 1 — Surface accessibility evidence

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| `DIRECT_MULTI_METHOD` banner | `surface_evidence.evidence_grade` | `Literal["direct_multi_method","direct_single_method","supportive_but_indirect","conflicting","weak"]` | L |
| Sentence under the banner | `surface_evidence.grade_rationale` | `str` (≤400) | L |
| Each row in *Methods + antibodies* | `surface_evidence.methods: list[MethodObservation]` | each: `{ method_family: Literal["flow_cytometry","immunofluorescence","immunohistochemistry","mass_spec","biotinylation","glycoproteomics","proximity_labeling","fractionation","other"], method_subclass: Literal["live_cell_flow","fixed_cell_flow","nonpermeabilized_IF","permeabilized_IF","IHC_membranous","surface_biotinylation","cell_surface_capture","N_glycoproteomics","plasma_membrane_fractionation","whole_cell_proteomics","unknown"], permeabilization: Literal["live_cell","nonpermeabilized","permeabilized","fixed_unknown","unknown"], expression_system: Literal["endogenous","overexpression","knock_in_tag","mixed","unknown"], antibodies: list[AntibodyRef], accessibility_relevance: Literal["direct_surface_accessibility","supports_surface_localization","supports_membrane_association","expression_only","weak_or_ambiguous"], surface_claim_type: Literal["surface_accessible","plasma_membrane_localized","membrane_fraction_enriched","cell_junction_localized","apical_or_luminal","secreted_or_shed","intracellular_pool","unclear"], expression_observations: list[ExpressionObservation], cited_evidence_ids: list[str] }` (the standalone `cell_lines_observed` list was dropped — sample context lives inline on each `expression_observations[]` entry below; primary human samples take precedence over established cell lines) | L |
| Antibody record `anti-EGFR clone 528 (ECD epitope)` | `MethodObservation.antibodies[i]` | `AntibodyRef = { name: str, clone: str\|None, vendor: str\|None, catalog: str\|None, antibody_epitope_region: Literal["extracellular","intracellular","conformational","isoform_specific","unknown"] }` | L |
| Per-observation `A431 (cell_line · epidermoid carcinoma) HIGH` rows inside each method card | `surface_evidence.methods[i].expression_observations: list[ExpressionObservation]` | each: `{ context: str, sample_type: Literal["primary_human_tissue","primary_human_cell","patient_sample","patient_derived_organoid","iPSC_derived","established_cell_line","xenograft","ex_vivo","unknown"], level: Literal["high","moderate","low","absent"], cited_evidence_ids: list[str] }`. **Nested inside `methods[i]` so each level is anchored to the measurement that produced it** — RNA / bulk-protein / IHC observations (which aren't tied to one of the 3 surface-evidence panels) live in `surface_evidence.non_surface_expression: list[NonSurfaceExpression]` instead. | L |
| Non-surface expression observations (RNA, IHC, bulk) | `surface_evidence.non_surface_expression: list[NonSurfaceExpression]` | each: `{ context: str, sample_type: ..., measurement_type: Literal["RNA","bulk_protein","IHC_protein","single_cell_RNA","unknown"], level: Literal["high","moderate","low","absent"], cited_evidence_ids: list[str] }` — for context that isn't surface-specific. | L |
| Each *Contradicting evidence* bullet | `surface_evidence.contradicting_evidence: list[Contradiction]` | each: `{ claim: str, contradiction_type: Literal["intracellular_pool","alternative_localization","secreted_only","cell_line_specific_absence","antibody_conflict","proteomics_conflict","isoform_conflict","other"], severity_for_surface_accessibility: Literal["high","moderate","low","unclear"], likely_explanation: str\|None, cited_evidence_ids: list[str] }` | L |

### Section 2 — Biological context

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| `skin ✓ keratinocytes basal, suprabasal` (one row per tissue) | `biological_context.tissues: list[TissueContext]` | each: `{ tissue: str, present: bool, cell_types: list[str], cell_states: list[str], cited_evidence_ids: list[str] }` | L |
| (orthogonal pivot) cell types | `biological_context.cell_types: list[CellTypeContext]` | each: `{ cell_type: str, ontology_id: str\|None, present_in_tissues: list[str], cited_evidence_ids: list[str] }` | L |
| (orthogonal pivot) cell states | `biological_context.cell_states: list[StateContext]` | each: `{ state: str, descriptor: str, cited_evidence_ids: list[str] }` | L |
| `Primary compartment: plasma_membrane` | `biological_context.subcellular_localization.primary_compartment` | `Literal["plasma_membrane","endosome","lysosome","ER","Golgi","mitochondrion","nucleus","cytosol","secreted","other"]` | L |
| `endosome (post-internalization) ~25% under EGF` | `biological_context.subcellular_localization.dual_localization: list[DualLocalization]` | each: `{ compartment: str, fraction_estimate: float\|None, condition: str\|None, cited_evidence_ids: list[str] }` | L |
| Anatomical accessibility table rows | `biological_context.anatomical_accessibility: list[AnatomicalAccessibilityObservation]` | each: `{ context: str, orientation: Literal["blood_interstitial_facing","luminal_facing","apical","basolateral","lateral","junction_restricted","ciliary","synaptic","matrix_facing","unknown"], accessibility_implication: Literal["favorable","restricted","context_dependent","unclear"], rationale: str (≤300), cited_evidence_ids: list[str] }` | L |
| Accessibility-modulation bullets (Normal → Disease shifts) | `biological_context.accessibility_modulation: list[AccessibilityModulationObservation]` | each: `{ category: Literal["cell_state_induced","tissue_restricted","activation_induced","stress_induced","disease_state_induced","polarization_dependent","post_translational_dependent","developmental_stage","none","unknown"], baseline_context: str, modulating_state: str, change: str (≤300), accessibility_implication: str (≤300), cited_evidence_ids: list[str] }`. **The `category` enum mirrors + expands the `surface_triage` agent's contextual `reason` taxonomy** (`cell_state_induced`, `tissue_restricted_surface`, `dual_localization`, `lysosomal_exocytosis`, `stable_surface_attachment`) so the two agents share vocabulary and a reader can cross-check a triage `contextual` verdict against the deep-dive evidence. | L |
| `constitutive recycling from sorting endosomes` | `biological_context.subcellular_localization.exocytosis_evidence: list[ExocytosisEvidence]` | each: `{ stimulus: str\|None, mechanism: str\|None, cited_evidence_ids: list[str] }` | L |

### Section 3 — Isoforms (deterministic + LLM interpretation)

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| Table row `canonical P00533-1 1 extra 621 542` | `deterministic_features.isoform_topologies[i]` | `IsoformTopology = { isoform_id: str, uniprot_acc: str, tm_helix_count: int, n_terminal_orientation: Literal["extracellular","cytoplasmic"], signal_peptide_length: int, ecd_length_residues: int, icd_length_residues: int, per_residue_topology: str, tool_version: str, retrieved_at: datetime }` | D |
| `canonical_topology` (top-most row) | `deterministic_features.canonical_topology` | same `IsoformTopology` shape, single | D |
| `Canonical caveat: P00533-1 is …` | `deterministic_features.canonical_topology.canonical_isoform_caveat` | `str \| None` (≤300) — LLM-emitted note when UniProt canonical isn't the tissue-dominant isoform | L |

**Per-isoform LLM interpretation is deferred** — v1.0.0 ships isoforms as deterministic topology only. Any biological reading of what an isoform implies for accessibility lives in `executive_summary.one_paragraph` if the LLM wants to surface it.

### Section 4 — Orthologs + paralogs (deterministic + LLM interpretation)

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| Per-species canonical + alternative isoforms (multi-row per species) | `deterministic_features.orthologs.{mouse,rat,cynomolgus}: list[OrthologEntry]` | each: `OrthologEntry = { is_canonical: bool, isoform_id: str, ensembl_id: str, ortholog_uniprot_acc: str, ortholog_symbol: str, type: Literal["one2one","one2many","many2many"], ecd_pct_identity_to_human_canonical: float, ecd_pct_similarity_to_human_canonical: float, ecd_length_residues: int, tm_helix_count: int, compara_version: str, retrieved_at: datetime }` (canonical first, then alternative isoforms — same shape, sorted) | D |
| (paralog table, also shown in §5) | `deterministic_features.paralogs: list[ParalogEntry]` | each: `{ paralog_symbol: str, paralog_uniprot_acc: str, ecd_pct_identity: float, family_id: str, compara_version: str }` | D |

**Per-species LLM interpretation is deferred** — v1.0.0 ships orthologs as deterministic ECD-conservation numbers + alternative-isoform topology only. Cross-species accessibility synthesis lives in `executive_summary.one_paragraph` if the LLM wants to make a call. (Earlier scratch fields `ortholog_implications.summary` / `cross_species_accessibility_relevance` / `species_caveats` are dropped.)

### Section 5 — Accessibility risks

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| `Partner required for surface expression?` | `accessibility_risks.co_receptor_requirements` | `{ surface_expression_dependency: Literal["required","modulatory","none","unknown"], partners: list[str], evidence_basis: Literal["co_expression_only","trafficking","knockout","mixed"], rationale: str (≤400), cited_evidence_ids: list[str] }` (function-side dependency dropped — out of scope for v1.0.0) | L |
| `Shed form … severity=MODERATE · evidence=STRONG` | `accessibility_risks.shed_form` | `{ present: bool, severity: Literal["high","moderate","low","unknown"], evidence_strength: Literal["strong","moderate","weak","inferred"], mechanism: str\|None, sheddase_if_known: str\|None, cited_evidence_ids: list[str] }` | L |
| `Secreted form … severity=LOW · evidence=STRONG` | `accessibility_risks.secreted_form` | `{ present: bool, severity: Literal["high","moderate","low","unknown"], evidence_strength: Literal["strong","moderate","weak","inferred"], ratio_to_membrane: float\|None, source: Literal["alternative_splicing","proteolytic","both","unknown"]\|None, cited_evidence_ids: list[str] }` | L |
| `Restricted membrane subdomain … severity=MODERATE` | `accessibility_risks.restricted_subdomain` | `{ present: bool, domain: Literal["apical","junctional","ciliary","synaptic","raft","basolateral","other","unknown"], severity: Literal["high","moderate","low","unknown"], evidence_strength: Literal["strong","moderate","weak","inferred"], rationale: str (≤300), cited_evidence_ids: list[str] }` | L |
| Each paralog risk row `HER2 45.1% MODERATE` | `accessibility_risks.paralog_cross_binding_risk: list[ParalogRisk]` | each: `{ paralog_symbol: str, deterministic_paralog_ref: str (FK → `deterministic_features.paralogs[i].family_id`), cross_reactivity_assessment: Literal["high","moderate","low","negligible"], severity: Literal["high","moderate","low","unknown"], evidence_strength: Literal["strong","moderate","weak","inferred"], rationale: str (≤200), cited_evidence_ids: list[str] }` (viewer/orchestrator look up `ecd_pct_identity` from the deterministic block; no mirrored field) | L→D-ref |
| `ECD accessibility size class: LARGE …` | `accessibility_risks.ecd_size_assessment` | `{ canonical_topology_ref: "canonical" (FK → `deterministic_features.canonical_topology`), ecd_accessibility_class: Literal["large","moderate","small","minimal","none"], rationale: str (≤300), cited_evidence_ids: list[str] }` (renamed from `druggability_class`; references rather than mirrors the deterministic length) | L→D-ref |
| `Epitope masking … severity=MODERATE · evidence=STRONG` | `accessibility_risks.epitope_masking` | `{ mechanism: Literal["glycan","partner","conformational","cleaved","none"], severity: Literal["high","moderate","low","none"], evidence_strength: Literal["strong","moderate","weak","inferred"], rationale: str (≤400), cited_evidence_ids: list[str] }` | L |

### Appendix — Structure

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| `AFDB ID: AF-P00533-F1-model_v4` | `deterministic_features.structure.afdb_id` | `str` | D |
| `ECD mean pLDDT: 91.4` | `deterministic_features.structure.ecd_mean_plddt` | `float` | D |
| `ECD disordered fraction: 3.1%` | `deterministic_features.structure.ecd_disordered_fraction` | `float` [0.0–1.0] | D |
| `ECD solvent-accessible fraction: 0.62` | `deterministic_features.structure.ecd_solvent_accessible_fraction` | `float` [0.0–1.0] | D |
| `Structure data from AlphaFold DB · © DeepMind / EMBL-EBI · licensed CC BY 4.0 · cite Jumper et al…` | `deterministic_features.structure.{source,attribution,license,citations}` | `source: str`, `attribution: str`, `license: str`, `citations: list[str]` (DOIs) | D |

### Evidence ledger

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| Counts row | `evidence_count`, `primary_evidence_count`, `secondary_evidence_count` (derived) | `int` | D |
| Each expandable evidence row | `evidence: list[Evidence]` | each: `Evidence = { evidence_id: str, claim: str, claim_type: enum, evidence_tier: Literal["primary","secondary","tertiary"], confidence: float, source: SourceRef, spans: list[EvidenceSpan], entailment_verified: bool }` (reused from current schema) | L→D |

### Data sources footer

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| Each `• {db} — {license} ({owner})` line | derived per-record from `deterministic_features.{canonical_topology,orthologs,structure}.{source,license,attribution}` | rendered by the viewer; no separate top-level field | D |

## Reviewer feedback applied (round 2)

After the initial plan, a second reviewer flagged that the schema was still drifting toward translational framing and underpowered on evidence quality / anatomical accessibility / uncertainty accounting. Applied changes:

| Area | Change |
|---|---|
| Executive summary | Dropped numeric `accessibility_score: float`; replaced with categorical `surface_targetability` (renamed from `surface_accessibility` for readability — the BD/discovery audience reads "targetability" instantly) + categorical `confidence` + `evidence_grade_summary` + `state_dependence` (renamed from `context_dependence`, which read as jargon — it answers "how much does surface presence shift with cell state / tissue / disease?"). Categorical-only avoids implying a calibrated rubric we don't have. The rename is **top-level only** — deeper sections keep `accessibility`-named fields (`accessibility_risks`, `anatomical_accessibility`, `accessibility_modulation`, `accessibility_relevance`). The plan now states explicitly that "targetability" here is the biological/physical sense (can a binder reach this protein), NOT the commercial sense (worth pursuing as a drug target). |
| Surface evidence | Added `evidence_grade: Literal["direct_multi_method","direct_single_method","supportive_but_indirect","conflicting","weak"]` + `grade_rationale` so the most important judgment in the section is explicit. |
| Method observations | Expanded from `Literal["flow","MS","IF"]` to a full `method_family` × `method_subclass` matrix (`live_cell_flow`, `surface_biotinylation`, `nonpermeabilized_IF`, etc.) plus `permeabilization`, `expression_system: endogenous\|overexpression\|...`, `antibody_epitope_region`, `accessibility_relevance`, `surface_claim_type`. Captures the difference between *live-cell flow with ECD antibody* (direct accessibility) and *whole-cell MS* (expression only). |
| Expression observations | Added closed `measurement_type: RNA\|bulk_protein\|IHC_protein\|surface_flow\|surface_proteomics\|single_cell_RNA\|unknown` + explicit `surface_specific: bool`. Prevents accidental conflation of expression with surface accessibility. |
| Contradictions | Restructured with `contradiction_type`, `severity_for_surface_accessibility`, `likely_explanation`. EGFR nuclear pool ≠ EGFR surface inaccessibility — the schema lets the LLM say so. |
| Anatomical accessibility | Promoted to first-class `biological_context.anatomical_accessibility` with closed `orientation` enum (apical/basolateral/junction_restricted/ciliary/luminal_facing/...) and `accessibility_implication`. |
| Disease / state relocalization | New `biological_context.accessibility_modulation` block — captures "basolateral in normal, depolarized in carcinoma" or "intracellular in resting, surface in activated". |
| Isoforms | Added `expression_support: protein_level\|transcript_level\|predicted_only\|conflicting\|unknown` and `biological_relevance` to `IsoformAccessibility`, plus `canonical_isoform_caveat` on `deterministic_features.canonical_topology`. Stops predicted-only isoforms from being overinterpreted as soluble decoys. |
| Orthologs | Replaced translational `cross_species_useful_for: list["mouse_efficacy", "cyno_tox", ...]` with `cross_species_accessibility_relevance: Literal["strongly_conserved","partially_conserved",...]` + per-species `species_caveats`. |
| Accessibility risks | Renamed `druggability_class` → `ecd_accessibility_class`. Added `severity` + `evidence_strength` to every risk. Added `restricted_subdomain` as a first-class risk. **Internalization/recycling is intentionally out of scope** for v1.0.0 — it is pro for some modalities (ADC delivery) and con for others (binder dwell time), so labeling it as a "risk" pre-judges; deferred until a separate dynamics block can frame it neutrally. |
| References instead of mirrors | Replaced the `*_from_deterministic` mirrored-value pattern with references — `ParalogRisk.deterministic_paralog_ref` and `ecd_size_assessment.canonical_topology_ref` FK into `deterministic_features`. Viewer/orchestrator do the lookup; no drift validation needed. |
| Knowledge gaps | Added `impact_on_confidence: high\|moderate\|low` and `suggested_resolution: str\|None` (the experiment that would resolve the gap). |
| Filters block | Added `evidence_grade` and `has_restricted_subdomain`. Replaced `cross_species_useful_for: list[enum]` with single-enum `cross_species_accessibility_relevance`. Top field renamed `filters.surface_accessibility` → `filters.surface_targetability`. (No `has_rapid_internalization` — internalization is out of scope, see Accessibility risks row.) |

Things the reviewer suggested but we pushed back on:

- **`final_accessibility_interpretation` bottom-of-page block** — duplicates `executive_summary`. One synthesis surface, not two that can drift.
- **Bulk renames** (`expression_summary` → `expression_context_summary`, etc.) — bikeshedding; the names that actually leaked translational framing (`druggability_class`, `cross_species_useful_for`) were renamed.
- **Bloating every `Evidence` entry** with `method_family` / `biological_context` / `surface_relevance` — keeps the ledger lean. Method metadata stays on the citing `MethodObservation`.
- **`normal_context_summary` block** — already covered by `biological_context.tissues[present=true]` + `surface_evidence.expression_levels[surface_specific=true]`.

## Optional additions — final decisions for v1.0.0

Six candidates were considered. **#1 (knowledge gaps) and #6 (filters block) land in v1.0.0.** The others are explicitly deferred so v1.0.0 ships lean.

| # | Feature | Decision | Notes |
|---|---|---|---|
| 1 | **Knowledge gaps** | **IN** | New top-level field `knowledge_gaps: list[KnowledgeGap]` where each entry is `{ question: str (≤200), why_unresolved: Literal["no_literature","conflicting","outside_scope"], cited_evidence_ids: list[str] }`. Rendered as a "What we couldn't determine" card between *Accessibility Risks* and the *Evidence Ledger*. The agent prompt instructs the model to enumerate questions it tried and couldn't resolve. |
| 6 | **Filters block (catalog-facing)** | **IN** | New top-level `filters` block — flat, closed-enum/bool/list rollups of the deep buckets. Powers chip filters + faceted search on the catalog/index page, and indexed D1 queries on `deep_dive_run`. Three rollup dimensions (`expression_level`, `expression_breadth`, `surface_specificity`) are LLM-emitted and live ONLY in `filters` (no duplication). The rest are orchestrator-derived from deeper fields. Co-receptor splits into two booleans: `requires_coreceptor_for_expression` (does the partner have to be present for the target to reach the surface?) and `requires_coreceptor_for_function` (does the partner have to be present for the target to signal?). |
| 2 | Glycosylation features | OUT (v1.0.0) | Defer to v1.1 — UniProt `ft_carbohyd` data is available; can land additively once the v1.0.0 surface is stable. For now, the LLM cites glycosylation from literature in `epitope_masking.mechanism`. |
| 3 | Surface-exposed epitope candidates | OUT (v1.0.0) | Defer. Needs SASA+DSSP integration in alphafold_fetcher + cutoff calibration against known-epitope proteins (EGFR domain III, PD-L1 IgV face). The LLM still discusses epitope masking from literature; we just don't have the structural-grounding numbers. |
| 4 | Per-section confidence | OUT (v1.0.0) | Defer. Top-level `confidence` + `confidence_reasoning` carry forward unchanged. |
| 5 | Run-level methodology block | OUT (v1.0.0) | Defer. `.runs/<timestamp>/summary.json` already captures this for reproducibility; surfacing it on the record itself can come later. |

### Knowledge gaps — placement in the mockup

Inserted as a card between *Accessibility Risks* and the *Evidence Ledger*:

```
┌─ 6. WHAT WE COULDN'T DETERMINE  (with impact + suggested resolve)──┐
│                                                                     │
│  • Cell-state-dependent surface turnover in stressed epithelia     │
│      why_unresolved: no_literature                                  │
│      impact_on_confidence: HIGH                                     │
│      suggested resolution: live-cell flow time-course on            │
│        stressed-vs-unstressed primary keratinocytes                 │
│                                                                     │
│  • Glycoform heterogeneity across tissues                          │
│      why_unresolved: conflicting  [evi_43, evi_44]                  │
│      impact_on_confidence: MODERATE                                 │
│      suggested resolution: tissue-specific N-glycoproteomics on     │
│        matched normal/tumor pairs                                   │
│                                                                     │
│  • In-vivo shedding rate (vs. in-vitro ADAM17 assays)              │
│      why_unresolved: outside_scope                                  │
│      impact_on_confidence: LOW                                      │
│      suggested resolution: serum sEGFR longitudinal cohort study    │
└─────────────────────────────────────────────────────────────────────┘
```

### Knowledge gaps — schema entry (added to the top-level shape)

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| Each bullet `• {question} — {why_unresolved} · impact=X · resolve: …` | `knowledge_gaps: list[KnowledgeGap]` | each: `KnowledgeGap = { question: str (≤200), why_unresolved: Literal["no_literature","conflicting","outside_scope"], detail: str (≤300) \| None, impact_on_confidence: Literal["high","moderate","low"], suggested_resolution: str (≤300) \| None, cited_evidence_ids: list[str] }` | L |

## Recommended approach

### 1. Keep naming, replace internals

Keep all existing names — they're descriptive enough and the rename buys us nothing:

| Stays the same |
|---|
| Agent dir: `src/accessible_surfaceome/agents/surface_annotator/` |
| Schema classes: `SurfaceomeRecord` / `SurfaceomeRecordDraft` |
| Persistence path: `data/annotations/{gene}.json` |
| D1 tables: `deep_dive_run` / `deep_dive_evidence` / `deep_dive_search_log` (+ NEW `deep_dive_features` for deterministic block) |
| CLI: `accessible-surfaceome agents annotate` |
| Viewer page route: `surfaceome.deliverome.org/{symbol}` |

The internals are a v1.0.0 rewrite — Pydantic schema, prompt, orchestrator flow, D1 columns. Old mock runs at `data/annotations/*.json` are discarded.

### 2. Top-level schema shape

`SurfaceomeRecord` v1.0.0 has **two structurally separated regions**: `deterministic_features` (verbatim tool output, populated by orchestrator) and `llm_synthesis` (the agent's work). Evidence + search log live at the top level and are referenced from both. Field order mirrors the mockup so JSON-reading humans see the same scientific flow.

```
SurfaceomeRecord (v1.0.0)
├── schema_version: "1.0.0"
├── gene: GeneIdentifier                          [reuse from current models.py]
│
├── executive_summary                             [LLM]
│   ├── one_paragraph                             # ≤600 char, consultant-readable
│   ├── surface_targetability                     # enum: high|moderate|low|uncertain
│   │                                             #   ("targetability" here = biological /
│   │                                             #    physical reachability, NOT commercial.
│   │                                             #    Top-line summary + filter chip only —
│   │                                             #    deeper sections keep `accessibility`.)
│   ├── evidence_grade_summary                    # enum: direct_multi_method|direct_single_method|
│   │                                             #   supportive_but_indirect|conflicting|weak
│   ├── confidence                                # enum: high|moderate|low (categorical only —
│   │                                             #   numeric `accessibility_score` was dropped)
│   ├── state_dependence                          # enum: low|moderate|high|unclear
│   │                                             #   how much does surface presence/exposure
│   │                                             #   shift with cell state / tissue / disease?
│   │                                             #   Cross-checks against accessibility_modulation[]
│   ├── subcategory                               # enum: single_pass_T1|GPCR|GPI|tetraspanin|...
│   ├── headline_risks: list[RiskTag]             # top-3 from accessibility_risks
│   └── cited_evidence_ids: list[str]
│
├── filters                                       [TOP-LEVEL — D1-indexed for catalog facets]
│   │                                             # Flat, closed-enum/bool/list rollups
│   │                                             # of the deep buckets. The catalog page
│   │                                             # renders one chip per field.
│   ├── surface_targetability                     # D ← executive_summary.surface_targetability
│   ├── confidence                                # D ← executive_summary.confidence
│   ├── subcategory                               # D ← executive_summary.subcategory
│   ├── evidence_grade                            # D ← surface_evidence.evidence_grade
│   ├── ecd_accessibility_class                   # D ← accessibility_risks.ecd_size_assessment
│   ├── evidence_density                          # D ← bucketed from evidence_count
│   ├── expression_level                          # L (rollup; lives ONLY here)
│   ├── expression_breadth                        # L (rollup; lives ONLY here)
│   ├── surface_specificity                       # L (rollup; lives ONLY here)
│   ├── has_shed_form                             # D ← accessibility_risks.shed_form.present
│   ├── has_secreted_form                         # D ← accessibility_risks.secreted_form.present
│   ├── requires_coreceptor_for_expression        # D ← co_receptor_requirements.surface_expression_dependency == "required"
│   ├── has_paralog_cross_reactivity_risk         # D ← any paralog_cross_binding_risk[i] ≥ moderate
│   ├── has_epitope_masking                       # D ← epitope_masking.severity ≥ moderate
│   ├── has_restricted_subdomain                  # D ← restricted_subdomain.present OR any
│   │                                             #     anatomical_accessibility[i].accessibility_implication == "restricted"
│   ├── mouse_ortholog_ecd_pct_identity           # D ← orthologs.mouse[is_canonical].ecd_pct_identity
│   ├── cyno_ortholog_ecd_pct_identity            # D ← orthologs.cynomolgus[is_canonical].ecd_pct_identity
│   ├── n_term_extracellular: bool                # D ← canonical_topology.n_terminal_orientation
│   ├── c_term_extracellular: bool                # D ← canonical_topology.c_terminal_orientation
│   └── knowledge_gaps_max_impact                 # enum: high|moderate|low|none
│                                                 #   D ← max(g.impact_on_confidence for g in
│                                                 #          knowledge_gaps, default="none")
│                                                 #   (replaces boolean has_knowledge_gaps —
│                                                 #    every gene has some gaps; severity is
│                                                 #    what actually filters)
│
├── surface_evidence                              [LLM — section 1 of viewer]
│   ├── evidence_grade                            # enum: direct_multi_method|direct_single_method|
│   │                                             #   supportive_but_indirect|conflicting|weak
│   ├── grade_rationale                           # ≤400 char — names the directness of evidence
│   ├── methods: list[MethodObservation]
│   │   └── { method_family: flow_cytometry|IF|IHC|mass_spec|biotinylation|glycoproteomics|...,
│   │         method_subclass: live_cell_flow|fixed_cell_flow|nonpermeabilized_IF|permeabilized_IF|
│   │           IHC_membranous|surface_biotinylation|cell_surface_capture|N_glycoproteomics|
│   │           plasma_membrane_fractionation|whole_cell_proteomics|unknown,
│   │         permeabilization: live_cell|nonpermeabilized|permeabilized|fixed_unknown|unknown,
│   │         expression_system: endogenous|overexpression|knock_in_tag|mixed|unknown,
│   │         antibodies: list[AntibodyRef],     # AntibodyRef now has antibody_epitope_region
│   │         accessibility_relevance: direct_surface_accessibility|supports_surface_localization|
│   │           supports_membrane_association|expression_only|weak_or_ambiguous,
│   │         surface_claim_type: surface_accessible|plasma_membrane_localized|
│   │           membrane_fraction_enriched|cell_junction_localized|apical_or_luminal|
│   │           secreted_or_shed|intracellular_pool|unclear,
│   │         expression_observations: list[ExpressionObservation],
│   │           # nested under the method so each level is anchored to its measurement
│   │           # each entry: { context, sample_type: primary_human_tissue|primary_human_cell|
│   │           #   patient_sample|patient_derived_organoid|iPSC_derived|established_cell_line|
│   │           #   xenograft|ex_vivo|unknown,
│   │           #   level: high|moderate|low|absent, cited_evidence_ids }
│   │           # primary human samples emphasized over established cell lines in the prompt
│   │         cited_evidence_ids }
│   ├── non_surface_expression: list[NonSurfaceExpression]
│   │   # RNA / IHC / bulk-protein levels that are NOT tied to one of the surface-evidence panels.
│   │   # Held separately so the report can't drift into treating RNA expression as accessibility.
│   │   └── { context, sample_type, measurement_type: RNA|bulk_protein|IHC_protein|
│   │           single_cell_RNA|unknown, level, cited_evidence_ids }
│   └── contradicting_evidence: list[Contradiction]
│       └── { claim,
│             contradiction_type: intracellular_pool|alternative_localization|secreted_only|
│               cell_line_specific_absence|antibody_conflict|proteomics_conflict|isoform_conflict|other,
│             severity_for_surface_accessibility: high|moderate|low|unclear,
│             likely_explanation,                # LLM-emitted — "does this contradiction matter?"
│             cited_evidence_ids }
│
├── biological_context                            [LLM — section 2]
│   ├── tissues: list[TissueContext]              # presence / absence per tissue, with cell types + states
│   ├── cell_types: list[CellTypeContext]
│   ├── cell_states: list[StateContext]           # activated/resting, stressed, EMT, ...
│   ├── subcellular_localization
│   │   ├── primary_compartment                   # enum: plasma_membrane|endosome|ER|...
│   │   ├── dual_localization: list[{ compartment, fraction_estimate, cited_evidence_ids }]
│   │   ├── membrane_subdomains: list[{ subdomain: lipid_raft|tight_junction|cilium|..., cited_evidence_ids }]
│   │   └── exocytosis_evidence: list[{ stimulus, cited_evidence_ids }]
│   ├── anatomical_accessibility: list[AnatomicalAccessibilityObservation]
│   │   └── { context, orientation: blood_interstitial_facing|luminal_facing|apical|basolateral|
│   │           lateral|junction_restricted|ciliary|synaptic|matrix_facing|unknown,
│   │         accessibility_implication: favorable|restricted|context_dependent|unclear,
│   │         rationale, cited_evidence_ids }
│   └── accessibility_modulation: list[AccessibilityModulationObservation]
│       └── { category: cell_state_induced|tissue_restricted|activation_induced|stress_induced|
│               disease_state_induced|polarization_dependent|post_translational_dependent|
│               developmental_stage|none|unknown,
│                                                 #   mirrors + expands surface_triage's contextual
│                                                 #   `reason` enum so the two agents share vocabulary
│             baseline_context, modulating_state, change, accessibility_implication,
│             cited_evidence_ids }
│
├── deterministic_features                        [ORCHESTRATOR ONLY — sections 3, 4, appendix]
│   ├── canonical_topology                        # DeepTMHMM on canonical isoform
│   │   ├── tm_helix_count
│   │   ├── n_terminal_orientation                # extracellular|cytoplasmic
│   │   ├── c_terminal_orientation                # extracellular|cytoplasmic
│   │   ├── signal_peptide_length
│   │   ├── ecd_length_residues
│   │   ├── icd_length_residues
│   │   ├── per_residue_topology                  # compressed 5-letter string
│   │   ├── canonical_isoform_caveat              # str | None — LLM-emitted note when
│   │   │                                         #   UniProt canonical ≠ tissue-dominant
│   │   ├── tool_version                          # "deeptmhmm-1.0.24"
│   │   └── retrieved_at
│   ├── isoform_topologies: list[IsoformTopology] # DeepTMHMM per isoform
│   ├── orthologs                                 # Ensembl Compara + DeepTMHMM
│   │   │                                         # Each species carries canonical + alt
│   │   │                                         # isoforms — same shape, sorted with
│   │   │                                         # canonical first. Alt isoforms let the
│   │   │                                         # reader spot species-specific isoform
│   │   │                                         # divergence that affects binder coverage.
│   │   ├── mouse: list[OrthologEntry]
│   │   ├── rat: list[OrthologEntry]
│   │   └── cynomolgus: list[OrthologEntry]
│   │       └── OrthologEntry = { is_canonical: bool, isoform_id, ensembl_id,
│   │             ortholog_uniprot_acc, ortholog_symbol,
│   │             type: one2one|one2many|many2many,
│   │             ecd_pct_identity_to_human_canonical,
│   │             ecd_pct_similarity_to_human_canonical,
│   │             ecd_length_residues, tm_helix_count,
│   │             compara_version, retrieved_at }
│   ├── paralogs: list[ParalogEntry]              # Compara within-species
│   │   └── { paralog_symbol, ecd_pct_identity, family_id }
│   └── structure                                 # AlphaFold DB
│       ├── afdb_id
│       ├── afdb_version
│       ├── ecd_mean_plddt
│       ├── ecd_disordered_fraction
│       ├── ecd_solvent_accessible_fraction
│       ├── source                                # fixed: "AlphaFold DB"
│       ├── license                               # fixed: "CC BY 4.0"
│       ├── attribution                           # fixed: "© DeepMind / EMBL-EBI"
│       └── citations                             # ["10.1038/s41586-021-03819-2",
│                                                  #  "10.1093/nar/gkad1011"]
│
│   # Per-isoform and per-species LLM interpretation blocks are
│   # intentionally OUT of v1.0.0. Isoforms and orthologs render
│   # as deterministic-only tables; any biological synthesis the
│   # LLM wants to make about them lives in executive_summary.one_paragraph.
│
├── accessibility_risks                           [LLM — section 5]
│   │                                             # Every risk now carries
│   │                                             # severity + evidence_strength so
│   │                                             # speculative-but-severe ≠ real-but-mild.
│   ├── shed_form: { present, severity, evidence_strength, mechanism,
│   │                sheddase_if_known, cited_evidence_ids }
│   ├── secreted_form: { present, severity, evidence_strength, ratio_to_membrane,
│   │                     source, cited_evidence_ids }
│   ├── restricted_subdomain:                      # NEW — apical/junctional/etc.
│   │   └── { present, domain: apical|junctional|ciliary|synaptic|raft|basolateral|other|unknown,
│   │         severity, evidence_strength, rationale, cited_evidence_ids }
│   ├── co_receptor_requirements:                 # surface-expression axis ONLY
│   │   ├── surface_expression_dependency         # enum: required|modulatory|none|unknown
│   │   │                                         #   (does partner need to be present
│   │   │                                         #    for the target to reach the surface?)
│   │   ├── partners: list[str]
│   │   ├── evidence_basis                        # enum: co_expression_only|trafficking|
│   │   │                                         #   knockout|mixed
│   │   ├── rationale
│   │   └── cited_evidence_ids: list[str]
│   │   # function-side dependency (does partner need to be present
│   │   # for signaling?) is out of scope for v1.0.0 — signaling
│   │   # biology lives elsewhere.
│   ├── paralog_cross_binding_risk: list[ParalogRisk]
│   │   └── { paralog_symbol,
│   │         deterministic_paralog_ref,         # FK → deterministic_features.paralogs[i].family_id
│   │         cross_reactivity_assessment: high|moderate|low|negligible,
│   │         severity, evidence_strength, rationale, cited_evidence_ids }
│   │       # references-instead-of-mirrors: viewer/orchestrator look up
│   │       # ecd_pct_identity from the deterministic block. No drift risk.
│   ├── ecd_size_assessment
│   │   └── { canonical_topology_ref,            # FK → deterministic_features.canonical_topology
│   │         ecd_accessibility_class: large|moderate|small|minimal|none,
│   │           # renamed from `druggability_class`; biological framing
│   │         rationale, cited_evidence_ids }
│   └── epitope_masking
│       └── { mechanism: glycan|partner|conformational|cleaved|none,
│             severity, evidence_strength, rationale, cited_evidence_ids }
│
├── knowledge_gaps: list[KnowledgeGap]            [LLM — section 6]
│   └── { question, why_unresolved: no_literature|conflicting|outside_scope, detail,
│         impact_on_confidence: high|moderate|low,
│         suggested_resolution: str|None,         # next experiment that would resolve the gap
│         cited_evidence_ids }
│
├── evidence: list[Evidence]                      [reuse current Evidence/SourceRef/EvidenceSpan]
├── search_log: list[SearchEntry]                 [reuse]
├── confidence: float
├── confidence_reasoning: str
└── contradiction_flag: bool
```

**Key invariants:**

- `deterministic_features.*` fields are written only by the orchestrator. The agent reads them in its task prompt but never emits them in its draft. Pydantic validator on `SurfaceomeRecordDraft` rejects any attempt by the agent to populate this region.
- `*_implications` sections and risk-assessment blocks **reference** deterministic numbers via foreign-key fields (`deterministic_paralog_ref`, `canonical_topology_ref`). The viewer / orchestrator resolve those refs into the deterministic block at render / serialization time. Avoids the duplicate-and-validate-for-drift pattern entirely.
- **Evidence model unchanged.** Keep `EvidenceClaim` → `Evidence` → `SourceRef` with substring-validated quote spans. Every `cited_evidence_ids` list references `evidence[i].evidence_id`. This is the most rigorous part of the existing pipeline; the redesign preserves it.

### 3. Deterministic tool plumbing

Three new orchestrator-level fetchers (not agent tools). Each caches by `(uniprot_acc, tool_version)`:

| Module | What it does | Reuses |
|---|---|---|
| `src/accessible_surfaceome/agents/surface_annotator/fetchers/deeptmhmm_fetcher.py` | Runs DeepTMHMM on canonical + all isoforms; extracts TM count, terminal orientation, signal peptide, ECD/ICD lengths, per-residue topology | Existing M1 pipeline at [deeptmhmm.py](src/accessible_surfaceome/sources/deeptmhmm.py) — extract prediction-parsing into a shared helper |
| `src/accessible_surfaceome/agents/surface_annotator/fetchers/compara_fetcher.py` | Looks up Ensembl Compara one2one orthologs for mouse/rat/cynomolgus + within-species paralogs; computes ECD pct identity using topology-derived ECD boundaries | Existing Compara CSV path referenced in [deeptmhmm.py:369](src/accessible_surfaceome/sources/deeptmhmm.py:369); needs new direct-fetch path or new ingestion script if CSV is stale |
| `src/accessible_surfaceome/agents/surface_annotator/fetchers/alphafold_fetcher.py` | Fetches AlphaFold DB CIF + confidence JSON for canonical UniProt; computes ECD mean pLDDT, disordered fraction, SASA-derived epitope-accessibility proxy. **Stamps every output with `source="AlphaFold DB"`, `license="CC BY 4.0"`, `attribution="© DeepMind / EMBL-EBI"`, and the Jumper 2021 + Varadi 2024 DOIs** — these flow through to the record's `deterministic_features.structure` block and are rendered as an attribution line in both the viewer Structure card and the per-record Data Sources footer. | New — no current AlphaFold retrieval in the repo |

Caches under `data/external/agent_features/{uniprot_acc}/{tool}_{version}.json`. Orchestrator hits the cache first; misses trigger a fetch + write.

**License compliance.** AlphaFold DB is CC BY 4.0, which requires that attribution accompany every downstream use. The viewer's per-gene Structure card and the bottom-of-page Data Sources footer both render the attribution string from `deterministic_features.structure`. The same applies to UniProt (CC BY 4.0).

**Ensembl Compara** data is freely redistributable with citation requested — Ensembl's policy is unrestricted use of data, no license-text required. (Apache 2.0 applies to their *code*, not the data tables we redistribute.) We cite Howe *et al.* 2024 (current Ensembl paper) and Vilella *et al.* 2009 (the Compara methodology paper).

**DeepTMHMM** is a DTU Health Tech service (Hallgren *et al.* 2022). Academic use of the service is free; we submit sequences and store the topology outputs as derived data, shipped with attribution. The model itself is not distributed under GPL or any other open-source license — commercial use of the model would require contacting DTU. Our redistribution of *outputs* is OK; we don't redistribute the model.

The Data Sources footer in the mockup is the canonical surface; the structured `source / license / attribution / citations` fields on each deterministic block are what make that footer mechanically constructible (no hand-maintained list).

### 4. Orchestrator flow

Modify [orchestrator.py](src/accessible_surfaceome/agents/surface_annotator/orchestrator.py):

```
annotate_gene(symbol):
  1. resolve gene → canonical UniProt + isoform list                   [reuse gene_lookup]
  2. prefetch deterministic_features in parallel:
       - deeptmhmm_fetcher(canonical + isoforms)
       - compara_fetcher(uniprot)
       - alphafold_fetcher(uniprot)
  3. build deterministic_features block + render as YAML for task prompt
  4. open Managed Agent session, send task with deterministic_features inline
  5. stream events, collect SurfaceomeRecordDraft from agent
  6. validate:
       - draft.deterministic_features is None (agent isn't allowed to write it)
       - every reference field (`deterministic_paralog_ref`, `canonical_topology_ref`)
         resolves to an entry in the orchestrator's deterministic_features
       - promote evidence_claims → evidence via existing promote_claim() pipeline
  7. derive filters block from deep buckets (orchestrator-derived rows)
  8. assemble SurfaceomeRecord, persist to data/annotations/{gene}.json + D1
```

### 5. Agent prompt

Rewrite `src/accessible_surfaceome/agents/surface_annotator/prompts/system.md` — drop the targetability/ADC/therapeutic-landscape framing entirely. Sections:

1. **Mission** — "assess whether {gene} is biologically accessible at the cell surface, for an early target-discovery scientist or pharma/biotech consultant"
2. **Inputs you'll receive** — a pre-computed `deterministic_features` block with explicit "do not contradict, do not rewrite" instruction
3. **What to produce** — schema walk-through following the mockup order: executive summary → surface evidence → biological context → isoform/ortholog implications → accessibility risks
4. **Citation discipline** — same load-bearing rules as today (quote ≤200 char, must appear verbatim in source, cite by PMID/DOI/PMC)
5. **Style** — biological, not commercial. No "billion-dollar market" phrases. Useful to a target-discovery scientist and a pharma consultant alike.

### 6. Agent toolkit

Keep `gene_lookup` and `gene_literature`. **Remove `patent_lookup`** (was for the dropped therapeutic_landscape). Do NOT add agent tools for AlphaFold / Compara / DeepTMHMM — those run pre-agent.

### 7. D1 + viewer

- D1: drop `deep_dive_run` / `deep_dive_evidence` / `deep_dive_search_log` (mock data only), recreate them for the v1.0.0 shape, add NEW `deep_dive_features` storing the deterministic block as JSON for fast filter-by-topology queries.
- Update [cloudflare/d1_schema.sql](cloudflare/d1_schema.sql) + [scripts/upload_triage_runs_to_d1.py](scripts/upload_triage_runs_to_d1.py).
- Viewer: [viewer/](viewer/) — replace the existing gene detail page with a layout that follows the mockup section order. Update `viewer/lib/surfaceome.ts` types to match new `SurfaceomeRecord` v1.0.0.

### 8. Critical files to modify or create

**New files**
- `src/accessible_surfaceome/agents/surface_annotator/fetchers/{deeptmhmm,compara,alphafold}_fetcher.py`
- New D1 table `deep_dive_features` in [cloudflare/d1_schema.sql](cloudflare/d1_schema.sql)

**Modified**
- [src/accessible_surfaceome/tools/_shared/models.py](src/accessible_surfaceome/tools/_shared/models.py) — replace `SurfaceomeRecord` / `SurfaceomeRecordDraft` + their nested classes (targetability, ADC, therapeutic_landscape) with the v1.0.0 shape. Keep shared primitives (`GeneIdentifier`, `Evidence`, `SourceRef`, `EvidenceSpan`, `EvidenceClaim`, `SearchEntry`).
- [src/accessible_surfaceome/agents/surface_annotator/orchestrator.py](src/accessible_surfaceome/agents/surface_annotator/orchestrator.py) — add deterministic-prefetch phase, validate reference-FK fields resolve to `deterministic_features`, derive the `filters` block.
- [src/accessible_surfaceome/agents/surface_annotator/agent.py](src/accessible_surfaceome/agents/surface_annotator/agent.py) — update agent definition (tools list, schema reference) so auto-sync pushes the new prompt to the Managed Agent.
- [src/accessible_surfaceome/agents/surface_annotator/prompts/system.md](src/accessible_surfaceome/agents/surface_annotator/prompts/system.md) — full rewrite.
- [scripts/upload_triage_runs_to_d1.py](scripts/upload_triage_runs_to_d1.py) — new payload shape, write to `deep_dive_features`.
- [viewer/lib/surfaceome.ts](viewer/lib/surfaceome.ts) + viewer page components.
- CLAUDE.md + AGENTS.md — update the "Managed Agents" + "Cloudflare D1" sections to reflect the new schema version + dropped patent_lookup tool.

**Deleted**
- The `patent_lookup` tool dir / its registration in `agent.py`.
- Mock runs at `data/annotations/*.json`.
- Old D1 rows in `deep_dive_*` tables (drop + recreate).

### 9. Verification

1. **Unit tests for fetchers** — given a UniProt acc with known answers (e.g. EGFR — single-pass TM, well-conserved across mouse/rat/cyno, high pLDDT ECD), each fetcher returns the expected fields. Pin tool versions.
2. **Schema round-trip test** — load a fixture `SurfaceomeRecord` v1.0.0 JSON, validate with Pydantic, re-serialize, verify byte equality.
3. **End-to-end smoke** — run `uv run accessible-surfaceome agents annotate EGFR`. Check:
   - `deterministic_features` populated for all 4 blocks (canonical_topology, isoform_topologies, orthologs/paralogs, structure)
   - `accessibility_risks.ecd_size_assessment.canonical_topology_ref` resolves to `deterministic_features.canonical_topology`, and viewer renders the ECD length from that ref (no mirrored field on the risk block)
   - Every claim in LLM sections resolves to an entry in `evidence` with `entailment_verified=True`
   - Persisted JSON validates against schema v1.0.0
4. **Manual read** — eyeball the EGFR output and a harder case (e.g. tetraspanin CD81 with small ECDs; shed receptor TNFR1) and verify the record reads as a useful accessibility brief for a consultant. The viewer page renders in the section order of the mockup.
5. **D1 + viewer** — confirm record uploads to `deep_dive_run` + `deep_dive_features`, viewer page renders without TypeScript errors against the new shape.
6. `bash scripts/check-py.sh` passes (ruff + ty + compile + pytest).

### 10. Out of scope (explicitly)

- Migrating old mock `data/annotations/*.json` records — they're discardable.
- A surrogate-target recommender — that's translational and belongs in a separate downstream layer.
- Multi-isoform tissue dominance from RNA-seq — too heavy for v1.0.0; the agent will summarize from literature with the deterministic topology side-by-side.
- AlphaFold-Multimer / partner complexes for `co_receptor_requirements` — single-chain AlphaFold only for v1.0.0.
- **Glycosylation features (#2)** — defer to v1.1. UniProt `ft_carbohyd` data is available; will land additively once v1.0.0 stabilizes.
- **Surface-exposed epitope candidates (#3)** — defer. Needs SASA+DSSP integration plus cutoff calibration against known-epitope proteins. The LLM still discusses epitope masking from literature.
- **Per-section confidence (#4)** — defer. Top-level `confidence` + `confidence_reasoning` carry forward unchanged.
- **Run-level methodology block (#5)** — defer. `.runs/<timestamp>/summary.json` already captures this for reproducibility; surfacing on the record can come later.
- **Internalization / surface dynamics** — defer. Rapid internalization is con for binder dwell time but pro for ADC delivery; the schema shouldn't pre-judge as a "risk." When this lands in v1.x it goes into a neutral `surface_dynamics` block under `biological_context`, not under `accessibility_risks`.
