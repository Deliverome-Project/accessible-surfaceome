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
  EGFR — Surface Accessibility Brief
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
│   Overall accessibility:  HIGH       Subcategory: single-pass T1   │
│   Confidence:             0.86       Expression: high (epithelia)  │
│   Headline risks:         shed_form · paralog_cross_reactivity     │
└─────────────────────────────────────────────────────────────────────┘

┌─ FILTERS / TAGS  (catalog-facing, all closed enums) ───────────────┐
│                                                                     │
│  ACCESSIBILITY                                                      │
│    overall=HIGH · confidence=HIGH · subcategory=single_pass_T1     │
│    ecd_size_class=LARGE · evidence_density=HIGH                     │
│                                                                     │
│  EXPRESSION                                                         │
│    level=HIGH · breadth=BROAD · surface_specificity=MIXED          │
│                                                                     │
│  RISKS                                                              │
│    ✓ has_shed_form                  ✓ has_secreted_form             │
│    ✗ coreceptor_for_expression      • coreceptor_for_function       │
│    ✓ paralog_cross_reactivity       ✓ epitope_masking               │
│                                                                     │
│  CROSS-SPECIES                                                      │
│    mouse_efficacy · rat_PK · cyno_tox                               │
│                                                                     │
│  TOPOLOGY                                                           │
│    n_term_extracellular=TRUE                                        │
│                                                                     │
│  QUALITY                                                            │
│    has_knowledge_gaps=TRUE                                          │
│                                                                     │
│  (Catalog page renders each as a chip; click to filter the gene    │
│  list. Per-gene page surfaces these in the executive header above.) │
└─────────────────────────────────────────────────────────────────────┘

┌─ 1. SURFACE EVIDENCE ──────────────────────────────────────────────┐
│                                                                     │
│  What is the evidence for surface localization?                     │
│  ----------------------------------------------------------------   │
│  EGFR is one of the most thoroughly validated plasma-membrane       │
│  receptors; surface localization is confirmed across primary        │
│  cells, cancer cell lines, and reconstituted systems.               │
│                                                                     │
│  Cell lines observed (12 distinct citations)                        │
│  ----------------------------------------------------------------   │
│   • A431  (epidermoid carcinoma)        4 citations  [evi_02,07,…]  │
│   • A549  (lung adenocarcinoma)         3 citations  [evi_05,11]    │
│   • HeLa  (cervical carcinoma)          2 citations  [evi_09]       │
│   • MCF7  (breast)                      2 citations  [evi_14]       │
│   • Primary keratinocytes               1 citation   [evi_18]       │
│                                                                     │
│  Methods + antibodies  (3 panels: Flow · MS · IF)                   │
│  ----------------------------------------------------------------   │
│   • Flow cytometry  — anti-EGFR clone 528, ICR10      [evi_02,05]   │
│   • Mass spec       — surface biotinylation, label-free [evi_07]    │
│   • Immunofluorescence — cetuximab, panitumumab       [evi_11,14]   │
│                                                                     │
│  Expression levels                                                  │
│  ----------------------------------------------------------------   │
│   • Epithelial tumors        HIGH    (HPA, flow)        [evi_02]    │
│   • Normal skin              HIGH    (IHC)              [evi_18]    │
│   • Hematopoietic            ABSENT  (flow panels)      [evi_22]    │
│                                                                     │
│  Contradicting evidence                                             │
│  ----------------------------------------------------------------   │
│   • Mitochondrial pool reported in stressed cells       [evi_31]    │
│   • Nuclear-translocated fraction (ligand-induced)      [evi_27]    │
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
│   Membrane subdomains:                                              │
│      • lipid_raft (basal state, partial)                  [evi_18]  │
│      • basolateral in polarized epithelia                 [evi_22]  │
│   Exocytosis evidence:                                              │
│      • constitutive recycling from sorting endosomes      [evi_29]  │
└─────────────────────────────────────────────────────────────────────┘

┌─ 3. ISOFORMS  [deterministic — DeepTMHMM v1.0.24] ─────────────────┐
│                                                                     │
│   isoform     UniProt    TM count   N-term   ECD len   ICD len      │
│   ───────     ───────    ────────   ──────   ───────   ───────      │
│   canonical   P00533-1      1       extra      621       542        │
│   isoform-2   P00533-2      1       extra      621       430        │
│   isoform-3   P00533-3      0         —         88        0  ◀ sol  │
│   isoform-4   P00533-4      1       extra      490       542        │
│                                                                     │
│  LLM interpretation                                                 │
│  ----------------------------------------------------------------   │
│  Isoform-3 lacks the TM helix entirely (soluble decoy) — antibody   │
│  paratopes targeting the ECD will bind this isoform in solution.    │
│  Isoform-4 retains the ECD but with a truncated extracellular       │
│  subdomain IV; epitopes in that region may be lost.                 │
└─────────────────────────────────────────────────────────────────────┘

┌─ 4. ORTHOLOGS  [deterministic — Ensembl Compara r112] ─────────────┐
│                                                                     │
│   species        ortholog       type        ECD % id   ECD % sim    │
│   ─────────      ───────────    ─────────   ────────   ────────     │
│   mouse          Egfr (Q01279)  one2one        88.2%      94.1%     │
│   rat            Egfr (Q9QX70)  one2one        88.0%      94.3%     │
│   cynomolgus     EGFR           one2one        99.1%      99.6%     │
│                                                                     │
│  LLM interpretation                                                 │
│  ----------------------------------------------------------------   │
│  Mouse and rat ECDs are conserved enough for efficacy / PK PoC      │
│  studies but several human-specific surface loops (subdomain III)   │
│  may not be reproduced. Cyno ECD is nearly identical — good         │
│  toxicology surrogate.                                              │
└─────────────────────────────────────────────────────────────────────┘

┌─ 5. ACCESSIBILITY RISKS ───────────────────────────────────────────┐
│                                                                     │
│  • Co-receptor requirements (two independent axes)                  │
│      Surface-expression dependency:  NONE                           │
│        EGFR reaches the plasma membrane unassisted; no partner      │
│        is required for trafficking.                       [evi_46]  │
│      Function dependency:            MODULATORY                     │
│        EGFR autophosphorylates after ligand binding alone, but      │
│        HER2/3/4 heterodimerization tunes signaling output —         │
│        partners enhance but are not required.             [evi_47]  │
│      Partners: HER2, HER3, HER4                                     │
│      (TCR/CD3 would be REQUIRED on both axes; this captures both.) │
│  • Shed form?                  YES — ADAM17-mediated, soluble sEGFR │
│                                detectable in serum  [evi_33,34]     │
│  • Secreted form?              YES — isoform-3 is constitutively    │
│                                soluble (no TM helix)                │
│  • Similar paralogs:                                                │
│       paralog    ECD id    cross-reactivity risk                    │
│       HER2       45.1%     moderate                  [evi_41]       │
│       HER3       42.7%     moderate                  [evi_41]       │
│       HER4       43.0%     moderate                  [evi_41]       │
│  • ECD size assessment:        621 aa — LARGE, druggable by mAb,    │
│                                bispecifics, ADCs                    │
│  • Epitope masking?            Partial — heavy N-glycosylation on   │
│                                domain III; conformational gating    │
│                                by domain II tether                  [evi_45]
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
│  • Ensembl Compara orthologs — Apache 2.0 (EMBL-EBI)                │
│  • DeepTMHMM topology — GPL-3.0 (DTU Health Tech)                   │
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
| `Surface Accessibility Brief` | (viewer-static title) | — | — |
| `schema v1.0.0` | `schema_version` | `Literal["1.0.0"]` | D |
| `generated 2026-05-13` | `generated_at` | `datetime` | D |
| `model claude-opus-4-7` | `model_path` | `str` | D |

### Executive summary

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| "EGFR is a single-pass type I…" prose | `executive_summary.one_paragraph` | `str` (≤600) | L |
| `HIGH` (accessibility) | `executive_summary.overall_accessibility` | `Literal["high","moderate","low","uncertain"]` | L |
| `0.86` | `executive_summary.accessibility_score` | `float` [0.0–1.0] | L |
| `single-pass T1` | `executive_summary.subcategory` | `Literal["single_pass_T1","single_pass_T2","multi_pass","GPCR","GPI_anchored","tetraspanin","ion_channel","transporter","other"]` | L |
| `high (epithelia)` | `executive_summary.expression_summary` | `Literal["high","moderate","low","mixed","absent"]` | L |
| `shed_form · paralog_cross_reactivity` | `executive_summary.headline_risks` | `list[Literal["shed_form","secreted_form","co_receptor","paralog_cross_reactivity","ecd_too_small","epitope_masked","isoform_decoy","other"]]` (max 3) | L |
| (cite chips, not shown) | `executive_summary.cited_evidence_ids` | `list[str]` (→ `evidence[].evidence_id`) | L |

### Filters / tags card

Top-level `filters` block — every value is a closed enum, `bool`, or `list[enum]`. The catalog/index page reads these to render filter chips and faceted search; the per-gene executive header surfaces the same chips. Provenance column: **D** = derived by orchestrator from deeper fields (no extra LLM work), **L** = LLM emits directly (typically rolling-up judgment).

| Rendered chip | Schema path | Type | Prov | Derivation rule (D-source) |
|---|---|---|---|---|
| `overall=HIGH` | `filters.overall_accessibility` | `Literal["high","moderate","low","uncertain"]` | D | `executive_summary.overall_accessibility` |
| `confidence=HIGH` | `filters.accessibility_confidence` | `Literal["high","moderate","low"]` | D | bucketed from `confidence: float` (≥0.75/≥0.5/else) |
| `subcategory=single_pass_T1` | `filters.subcategory` | `Literal["single_pass_T1","single_pass_T2","multi_pass","GPCR","GPI_anchored","tetraspanin","ion_channel","transporter","other"]` | D | `executive_summary.subcategory` |
| `ecd_size_class=LARGE` | `filters.ecd_size_class` | `Literal["large","moderate","small","nano"]` | D | `accessibility_risks.ecd_size_assessment.druggability_class` |
| `evidence_density=HIGH` | `filters.evidence_density` | `Literal["low","moderate","high"]` | D | bucketed from `evidence_count` (≥30/≥10/else) |
| `level=HIGH` | `filters.expression_level` | `Literal["high","moderate","low","absent"]` | L | LLM rollup of `surface_evidence.expression_levels[]` |
| `breadth=BROAD` | `filters.expression_breadth` | `Literal["pan_tissue","broad","restricted","rare"]` | L | LLM judgment from `biological_context.tissues[]` |
| `surface_specificity=MIXED` | `filters.surface_specificity` | `Literal["surface_dominant","mixed","mostly_intracellular"]` | L | LLM rollup of `subcellular_localization.dual_localization[]` |
| `has_shed_form` (bool) | `filters.has_shed_form` | `bool` | D | `accessibility_risks.shed_form.present` |
| `has_secreted_form` (bool) | `filters.has_secreted_form` | `bool` | D | `accessibility_risks.secreted_form.present` |
| `coreceptor_for_expression` (bool) | `filters.requires_coreceptor_for_expression` | `bool` | D | `accessibility_risks.co_receptor_requirements.surface_expression_dependency == "required"` |
| `coreceptor_for_function` (bool) | `filters.requires_coreceptor_for_function` | `bool` | D | `accessibility_risks.co_receptor_requirements.function_dependency == "required"` |
| `paralog_cross_reactivity` (bool) | `filters.has_paralog_cross_reactivity_risk` | `bool` | D | any `accessibility_risks.similar_paralogs[].cross_reactivity_assessment ∈ {high, moderate}` |
| `epitope_masking` (bool) | `filters.has_epitope_masking` | `bool` | D | `accessibility_risks.epitope_masking.severity ∈ {high, moderate}` |
| `mouse_efficacy · cyno_tox …` | `filters.cross_species_useful_for` | `list[Literal["mouse_efficacy","mouse_tox","rat_PK","cyno_tox","cyno_efficacy","surrogate_needed","none"]]` | D | mirror of `ortholog_implications.cross_species_useful_for` |
| `n_term_extracellular` (bool) | `filters.n_term_extracellular` | `bool` | D | `deterministic_features.canonical_topology.n_terminal_orientation == "extracellular"` |
| `has_knowledge_gaps` (bool) | `filters.has_knowledge_gaps` | `bool` | D | `len(knowledge_gaps) > 0` |

**Filters-only rule (no duplication):** the three LLM-emitted dimensions (`expression_level`, `expression_breadth`, `surface_specificity`) live ONLY in `filters`. The deep `surface_evidence.expression_levels[]` list still carries per-context detail ("epithelial tumors HIGH; blood ABSENT") but the rolled-up filter values aren't repeated there. Zero drift risk.

**D1 indexing:** every filter is a top-level column on `deep_dive_run`, so queries like *"single_pass_T1 receptors with broad expression, no shed form, mouse_efficacy"* are an indexed scan, not JSON traversal.

### Section 1 — Surface evidence

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| "EGFR is one of the most thoroughly validated…" prose | `surface_evidence.evidence_summary` | `str` (≤800) | L |
| Each row in *Cell lines observed*: `A431 (epidermoid carcinoma) 4 citations` | `surface_evidence.cell_lines_observed: list[CellLineObservation]` | each: `{ cell_line: str, lineage: str, distinct_citation_count: int, cited_evidence_ids: list[str] }` | L |
| Each row in *Methods + antibodies*: `Flow cytometry — anti-EGFR clone 528, ICR10` | `surface_evidence.methods: list[MethodObservation]` | each: `{ method: Literal["flow","MS","IF"], antibodies: list[AntibodyRef], cited_evidence_ids: list[str] }` | L |
| (sub-field) `anti-EGFR clone 528` | `MethodObservation.antibodies[i]` | `AntibodyRef = { name: str, clone: str\|None, vendor: str\|None, catalog: str\|None }` | L |
| Each row in *Expression levels*: `Epithelial tumors HIGH (HPA, flow)` | `surface_evidence.expression_levels: list[ExpressionObservation]` | each: `{ context: str, level: Literal["high","moderate","low","absent"], quant_method: str\|None, cited_evidence_ids: list[str] }` | L |
| Each *Contradicting evidence* bullet | `surface_evidence.contradicting_evidence: list[Contradiction]` | each: `{ claim: str, cited_evidence_ids: list[str] }` | L |

### Section 2 — Biological context

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| `skin ✓ keratinocytes basal, suprabasal` (one row per tissue) | `biological_context.tissues: list[TissueContext]` | each: `{ tissue: str, present: bool, cell_types: list[str], cell_states: list[str], cited_evidence_ids: list[str] }` | L |
| (orthogonal pivot) cell types | `biological_context.cell_types: list[CellTypeContext]` | each: `{ cell_type: str, ontology_id: str\|None, present_in_tissues: list[str], cited_evidence_ids: list[str] }` | L |
| (orthogonal pivot) cell states | `biological_context.cell_states: list[StateContext]` | each: `{ state: str, descriptor: str, cited_evidence_ids: list[str] }` | L |
| `Primary compartment: plasma_membrane` | `biological_context.subcellular_localization.primary_compartment` | `Literal["plasma_membrane","endosome","lysosome","ER","Golgi","mitochondrion","nucleus","cytosol","secreted","other"]` | L |
| `endosome (post-internalization) ~25% under EGF` | `biological_context.subcellular_localization.dual_localization: list[DualLocalization]` | each: `{ compartment: str, fraction_estimate: float\|None, condition: str\|None, cited_evidence_ids: list[str] }` | L |
| `lipid_raft (basal state, partial)` | `biological_context.subcellular_localization.membrane_subdomains: list[MembraneSubdomain]` | each: `{ subdomain: Literal["lipid_raft","tight_junction","cilium","basolateral","apical","microvilli","filopodia","focal_adhesion","immunological_synapse","podosome","caveolae","other"], qualifier: str\|None, cited_evidence_ids: list[str] }` | L |
| `constitutive recycling from sorting endosomes` | `biological_context.subcellular_localization.exocytosis_evidence: list[ExocytosisEvidence]` | each: `{ stimulus: str\|None, mechanism: str\|None, cited_evidence_ids: list[str] }` | L |

### Section 3 — Isoforms (deterministic + LLM interpretation)

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| Table row `canonical P00533-1 1 extra 621 542` | `deterministic_features.isoform_topologies[i]` | `IsoformTopology = { isoform_id: str, uniprot_acc: str, tm_helix_count: int, n_terminal_orientation: Literal["extracellular","cytoplasmic"], signal_peptide_length: int, ecd_length_residues: int, icd_length_residues: int, per_residue_topology: str, tool_version: str, retrieved_at: datetime }` | D |
| `canonical_topology` (top-most row) | `deterministic_features.canonical_topology` | same `IsoformTopology` shape, single | D |
| "Isoform-3 lacks the TM helix entirely…" prose | `isoform_implications.summary` | `str` (≤800) | L |
| Per-isoform interpretation rows | `isoform_implications.per_isoform: list[IsoformAccessibility]` | each: `{ isoform_id: str, accessible: bool, rationale: str (≤300), dominant_in_tissues: list[str], cited_evidence_ids: list[str] }` | L |

### Section 4 — Orthologs + paralogs (deterministic + LLM interpretation)

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| Table row `mouse Egfr (Q01279) one2one 88.2% 94.1%` | `deterministic_features.orthologs.mouse` | `OrthologEntry \| None = { ensembl_id: str, ortholog_uniprot_acc: str, ortholog_symbol: str, type: Literal["one2one","one2many","many2many"], ecd_pct_identity: float, ecd_pct_similarity: float, compara_version: str, retrieved_at: datetime }` | D |
| Same shape for `rat`, `cynomolgus` | `deterministic_features.orthologs.{rat,cynomolgus}` | `OrthologEntry \| None` | D |
| (paralog table, also shown in §5) | `deterministic_features.paralogs: list[ParalogEntry]` | each: `{ paralog_symbol: str, paralog_uniprot_acc: str, ecd_pct_identity: float, family_id: str, compara_version: str }` | D |
| "Mouse and rat ECDs are conserved enough…" prose | `ortholog_implications.summary` | `str` (≤600) | L |
| `mouse_efficacy`, `cyno_tox` tags | `ortholog_implications.cross_species_useful_for` | `list[Literal["mouse_efficacy","mouse_tox","rat_PK","cyno_tox","cyno_efficacy","surrogate_needed","none"]]` | L |
| ECD conservation concerns bullets | `ortholog_implications.ecd_conservation_concerns: list[ConservationConcern]` | each: `{ species: Literal["mouse","rat","cynomolgus"], concern: str (≤300), cited_evidence_ids: list[str] }` | L |

### Section 5 — Accessibility risks

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| `Co-receptor requirements (two axes)…` | `accessibility_risks.co_receptor_requirements` | `{ surface_expression_dependency: Literal["required","modulatory","none","unknown"], function_dependency: Literal["required","modulatory","none","unknown"], partners: list[str], evidence_basis: Literal["co_expression_only","trafficking","signaling","binding","knockout","mixed"], rationale: str (≤400), cited_evidence_ids: list[str] }` | L |
| `Shed form? YES — ADAM17-mediated, soluble sEGFR…` | `accessibility_risks.shed_form` | `{ present: bool, mechanism: str\|None, sheddase_if_known: str\|None, cited_evidence_ids: list[str] }` | L |
| `Secreted form? YES — isoform-3 is constitutively soluble` | `accessibility_risks.secreted_form` | `{ present: bool, ratio_to_membrane: float\|None, source: Literal["alternative_splicing","proteolytic","both","unknown"]\|None, cited_evidence_ids: list[str] }` | L |
| Each paralog risk row `HER2 45.1% moderate` | `accessibility_risks.similar_paralogs: list[ParalogRisk]` | each: `{ paralog_symbol: str, ecd_similarity_pct_from_deterministic: float, cross_reactivity_assessment: Literal["high","moderate","low","negligible"], rationale: str (≤200), cited_evidence_ids: list[str] }` (orchestrator validates that `ecd_similarity_pct_from_deterministic` equals the matching `deterministic_features.paralogs[i].ecd_pct_identity`) | L→D |
| `ECD size assessment: 621 aa — LARGE, druggable…` | `accessibility_risks.ecd_size_assessment` | `{ length_residues_from_deterministic: int, druggability_class: Literal["large","moderate","small","nano"], rationale: str (≤300), cited_evidence_ids: list[str] }` (mirror-validated against `deterministic_features.canonical_topology.ecd_length_residues`) | L→D |
| `Epitope masking? Partial — heavy N-glycosylation…` | `accessibility_risks.epitope_masking` | `{ mechanism: Literal["glycan","partner","conformational","cleaved","none"], severity: Literal["high","moderate","low","none"], rationale: str (≤400), cited_evidence_ids: list[str] }` | L |

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
┌─ 6. WHAT WE COULDN'T DETERMINE ────────────────────────────────────┐
│                                                                     │
│  • Cell-state-dependent surface turnover in stressed epithelia     │
│      no_literature — no quantitative surface-flux data found       │
│  • Glycoform heterogeneity across tissues                          │
│      conflicting — tissue glycoproteomics datasets disagree        │
│      on the dominant N-glycan profile  [evi_43, evi_44]            │
│  • In-vivo shedding rate (vs. in-vitro ADAM17 assays)              │
│      outside_scope — would require kinetic patient-serum data      │
└─────────────────────────────────────────────────────────────────────┘
```

### Knowledge gaps — schema entry (added to the top-level shape)

| Rendered | Schema path | Type | Prov |
|---|---|---|---|
| Each bullet `• {question} — {why_unresolved}` | `knowledge_gaps: list[KnowledgeGap]` | each: `KnowledgeGap = { question: str (≤200), why_unresolved: Literal["no_literature","conflicting","outside_scope"], detail: str (≤300) \| None, cited_evidence_ids: list[str] }` | L |

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
│   ├── overall_accessibility                     # enum: high|moderate|low|uncertain
│   ├── accessibility_score                       # 0.0–1.0, calibrated
│   ├── subcategory                               # enum: single_pass_T1|GPCR|GPI|tetraspanin|...
│   ├── expression_summary                        # enum: high|moderate|low|mixed
│   ├── headline_risks: list[RiskTag]             # top-3 from accessibility_risks
│   └── cited_evidence_ids: list[str]
│
├── filters                                       [TOP-LEVEL — D1-indexed for catalog facets]
│   │                                             # Flat, closed-enum/bool/list rollups
│   │                                             # of the deep buckets. The catalog page
│   │                                             # renders one chip per field.
│   ├── overall_accessibility                     # D ← executive_summary.overall_accessibility
│   ├── accessibility_confidence                  # D ← bucketed from confidence: float
│   ├── subcategory                               # D ← executive_summary.subcategory
│   ├── ecd_size_class                            # D ← accessibility_risks.ecd_size_assessment
│   ├── evidence_density                          # D ← bucketed from evidence_count
│   ├── expression_level                          # L (rollup; lives ONLY here)
│   ├── expression_breadth                        # L (rollup; lives ONLY here)
│   ├── surface_specificity                       # L (rollup; lives ONLY here)
│   ├── has_shed_form                             # D ← accessibility_risks.shed_form.present
│   ├── has_secreted_form                         # D ← accessibility_risks.secreted_form.present
│   ├── requires_coreceptor_for_expression        # D ← co_receptor_requirements.surface_expression_dependency == "required"
│   ├── requires_coreceptor_for_function          # D ← co_receptor_requirements.function_dependency == "required"
│   ├── has_paralog_cross_reactivity_risk         # D ← any similar_paralogs[i] ≥ moderate
│   ├── has_epitope_masking                       # D ← epitope_masking.severity ≥ moderate
│   ├── cross_species_useful_for: list[enum]      # D ← ortholog_implications.cross_species_useful_for
│   ├── n_term_extracellular: bool                # D ← canonical_topology.n_terminal_orientation
│   └── has_knowledge_gaps: bool                  # D ← len(knowledge_gaps) > 0
│
├── surface_evidence                              [LLM — section 1 of viewer]
│   ├── evidence_summary                          # ≤800 char
│   ├── cell_lines_observed: list[CellLineObservation]
│   │   └── { cell_line, lineage, distinct_citation_count, cited_evidence_ids }
│   ├── methods: list[MethodObservation]
│   │   └── { method: flow|MS|IF, antibodies: list[AntibodyRef], cited_evidence_ids }
│   │       # closed enum — only the 3 core surface-evidence panels. MS subsumes
│   │       # surface biotinylation + LC-MS/MS, surfaceomics, glycoproteomics.
│   ├── expression_levels: list[ExpressionObservation]
│   │   └── { context, level: high|moderate|low|absent, quant_method, cited_evidence_ids }
│   └── contradicting_evidence: list[Contradiction]
│       └── { claim, cited_evidence_ids }
│
├── biological_context                            [LLM — section 2]
│   ├── tissues: list[TissueContext]              # presence / absence per tissue, with cell types + states
│   ├── cell_types: list[CellTypeContext]
│   ├── cell_states: list[StateContext]           # activated/resting, stressed, EMT, ...
│   └── subcellular_localization
│       ├── primary_compartment                   # enum: plasma_membrane|endosome|ER|...
│       ├── dual_localization: list[{ compartment, fraction_estimate, cited_evidence_ids }]
│       ├── membrane_subdomains: list[{ subdomain: lipid_raft|tight_junction|cilium|..., cited_evidence_ids }]
│       └── exocytosis_evidence: list[{ stimulus, cited_evidence_ids }]
│
├── deterministic_features                        [ORCHESTRATOR ONLY — sections 3, 4, appendix]
│   ├── canonical_topology                        # DeepTMHMM on canonical isoform
│   │   ├── tm_helix_count
│   │   ├── n_terminal_orientation                # extracellular|cytoplasmic
│   │   ├── signal_peptide_length
│   │   ├── ecd_length_residues
│   │   ├── icd_length_residues
│   │   ├── per_residue_topology                  # compressed 5-letter string
│   │   ├── tool_version                          # "deeptmhmm-1.0.24"
│   │   └── retrieved_at
│   ├── isoform_topologies: list[IsoformTopology] # DeepTMHMM per isoform
│   ├── orthologs                                 # Ensembl Compara one2one
│   │   ├── mouse: OrthologEntry | null
│   │   ├── rat: OrthologEntry | null
│   │   └── cynomolgus: OrthologEntry | null
│   │       └── { ensembl_id, ortholog_uniprot_acc, type, ecd_pct_identity, ecd_pct_similarity, compara_version }
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
├── isoform_implications                          [LLM interprets deterministic_features.isoform_topologies]
│   ├── summary
│   └── per_isoform: list[{ isoform_id, accessible: bool, rationale, dominant_in_tissues, cited_evidence_ids }]
│
├── ortholog_implications                         [LLM interprets deterministic_features.orthologs]
│   ├── cross_species_useful_for: list[enum]      # mouse_efficacy|cyno_tox|surrogate_needed|none
│   ├── ecd_conservation_concerns: list[{ species, concern, cited_evidence_ids }]
│   └── summary
│
├── accessibility_risks                           [LLM — section 5]
│   ├── shed_form: { present, mechanism, sheddase_if_known, cited_evidence_ids }
│   ├── secreted_form: { present, ratio_to_membrane, cited_evidence_ids }
│   ├── co_receptor_requirements:                 # TWO independent axes
│   │   ├── surface_expression_dependency         # enum: required|modulatory|none|unknown
│   │   │                                         #   (does partner need to be present
│   │   │                                         #    for the target to reach the surface?)
│   │   ├── function_dependency                   # enum: required|modulatory|none|unknown
│   │   │                                         #   (does partner need to be present
│   │   │                                         #    for the target to signal/function?)
│   │   ├── partners: list[str]                   # gene symbols
│   │   ├── evidence_basis                        # enum: co_expression_only|trafficking|
│   │   │                                         #   signaling|binding|knockout|mixed
│   │   ├── rationale                             # ≤400 char — names which axis the
│   │   │                                         #   evidence speaks to
│   │   └── cited_evidence_ids: list[str]
│   ├── similar_paralogs: list[ParalogRisk]       # cross-refs deterministic_features.paralogs
│   │   └── { paralog_symbol, ecd_similarity_pct_from_deterministic, cross_reactivity_assessment, cited_evidence_ids }
│   ├── ecd_size_assessment
│   │   └── { length_residues_from_deterministic, druggability_class: large|moderate|small|nano, cited_evidence_ids }
│   └── epitope_masking
│       └── { mechanism: glycan|partner|conformational|none, cited_evidence_ids }
│
├── knowledge_gaps: list[KnowledgeGap]            [LLM — section 6]
│   └── { question, why_unresolved: no_literature|conflicting|outside_scope, detail, cited_evidence_ids }
│
├── evidence: list[Evidence]                      [reuse current Evidence/SourceRef/EvidenceSpan]
├── search_log: list[SearchEntry]                 [reuse]
├── confidence: float
├── confidence_reasoning: str
└── contradiction_flag: bool
```

**Key invariants:**

- `deterministic_features.*` fields are written only by the orchestrator. The agent reads them in its task prompt but never emits them in its draft. Pydantic validator on `SurfaceomeRecordDraft` rejects any attempt by the agent to populate this region.
- `*_implications` sections and `accessibility_risks.*_from_deterministic` fields cross-reference deterministic numbers — the agent literally copies the number from `deterministic_features` into its risk assessment, and the orchestrator validates equality post-hoc. This gives readers an obvious bridge between tool output and LLM interpretation.
- **Evidence model unchanged.** Keep `EvidenceClaim` → `Evidence` → `SourceRef` with substring-validated quote spans. Every `cited_evidence_ids` list references `evidence[i].evidence_id`. This is the most rigorous part of the existing pipeline; the redesign preserves it.

### 3. Deterministic tool plumbing

Three new orchestrator-level fetchers (not agent tools). Each caches by `(uniprot_acc, tool_version)`:

| Module | What it does | Reuses |
|---|---|---|
| `src/accessible_surfaceome/agents/surface_annotator/fetchers/deeptmhmm_fetcher.py` | Runs DeepTMHMM on canonical + all isoforms; extracts TM count, terminal orientation, signal peptide, ECD/ICD lengths, per-residue topology | Existing M1 pipeline at [deeptmhmm.py](src/accessible_surfaceome/sources/deeptmhmm.py) — extract prediction-parsing into a shared helper |
| `src/accessible_surfaceome/agents/surface_annotator/fetchers/compara_fetcher.py` | Looks up Ensembl Compara one2one orthologs for mouse/rat/cynomolgus + within-species paralogs; computes ECD pct identity using topology-derived ECD boundaries | Existing Compara CSV path referenced in [deeptmhmm.py:369](src/accessible_surfaceome/sources/deeptmhmm.py:369); needs new direct-fetch path or new ingestion script if CSV is stale |
| `src/accessible_surfaceome/agents/surface_annotator/fetchers/alphafold_fetcher.py` | Fetches AlphaFold DB CIF + confidence JSON for canonical UniProt; computes ECD mean pLDDT, disordered fraction, SASA-derived epitope-accessibility proxy. **Stamps every output with `source="AlphaFold DB"`, `license="CC BY 4.0"`, `attribution="© DeepMind / EMBL-EBI"`, and the Jumper 2021 + Varadi 2024 DOIs** — these flow through to the record's `deterministic_features.structure` block and are rendered as an attribution line in both the viewer Structure card and the per-record Data Sources footer. | New — no current AlphaFold retrieval in the repo |

Caches under `data/external/agent_features/{uniprot_acc}/{tool}_{version}.json`. Orchestrator hits the cache first; misses trigger a fetch + write.

**License compliance.** AlphaFold DB is CC BY 4.0, which requires that attribution accompany every downstream use. The viewer's per-gene Structure card and the bottom-of-page Data Sources footer both render the attribution string from `deterministic_features.structure`. The same applies to UniProt (CC BY 4.0), Ensembl Compara (Apache 2.0 — attribution not legally required but included for parity), and DeepTMHMM (GPL-3.0 — academic-use attribution by convention). The Data Sources footer in the mockup is the canonical surface; the structured `source / license / attribution / citations` fields on each deterministic block are what make that footer mechanically constructible (no hand-maintained list).

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
       - every `*_from_deterministic` field matches the orchestrator's deterministic_features
       - promote evidence_claims → evidence via existing promote_claim() pipeline
  7. assemble SurfaceomeRecord, persist to data/annotations/{gene}.json + D1
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
- [src/accessible_surfaceome/agents/surface_annotator/orchestrator.py](src/accessible_surfaceome/agents/surface_annotator/orchestrator.py) — add deterministic-prefetch phase, validation of `*_from_deterministic` mirroring.
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
   - `accessibility_risks.ecd_size_assessment.length_residues_from_deterministic` equals `deterministic_features.canonical_topology.ecd_length_residues`
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
