# surfaceome_v2 process flow

End-to-end pipeline that takes a gene identifier and produces a v1.0.0
`SurfaceomeRecord`. Three logical phases (the original handoff scoping)
plus a B synthesizer + deterministic features rollup, all wired into
one `surfaceome_v2.annotate(gene)` entry point.

## Top-level flow

```mermaid
flowchart TB
    Start[("gene id<br/>(symbol / HGNC:N / UniProt acc)")] --> Resolve

    subgraph Resolve["identifier resolution (resolver v3)"]
        direction TB
        R1{"shape?"}
        R1 -->|UniProt acc| RUni["gene_lookup.resolve"]
        R1 -->|HGNC:N| RHgnc["resolve_by_hgnc_id"]
        R1 -->|bare symbol| RD1["D1 gene_identifier lookup<br/>→ HGNC:N → resolve_by_hgnc_id"]
        RUni --> RBundle[("IdentifierBundle<br/>(uniprot_acc, hgnc_id,<br/>ensembl_gene, ncbi_gene_id,<br/>aliases, prev_symbols, …)")]
        RHgnc --> RBundle
        RD1 --> RBundle
    end

    Resolve --> Phase1

    subgraph Phase1["Phase 1 · plan-trim-select dual (A1 then A2)"]
        direction TB
        P1A1["A1 leg<br/>(surface evidence focus)"] --> P1A2["A2 leg<br/>(biological context focus)"]
        P1A2 --> P1Ledger[("EvidenceClaim ledger<br/>A1: a1_evi_NN claims<br/>A2: a2_evi_NN claims<br/>100% verbatim-anchored by construction")]
    end

    Phase1 --> Phase2

    subgraph Phase2["Phase 2 · block builders (9 Sonnet calls)"]
        direction LR
        subgraph P2A1["A1-side (consume a1 ledger)"]
            direction TB
            BM["methods_builder<br/>→ list[MethodObservation]"]
            BT["therapeutic_engagement_builder<br/>→ TherapeuticEngagementContext | None"]
            BC["contradiction_builder<br/>→ list[Contradiction]"]
            BG["evidence_grade_builder<br/>→ EvidenceGrade + grade_rationale<br/>+ non_surface_expression[]"]
        end
        subgraph P2A2["A2-side (consume a2 ledger)"]
            direction TB
            BTi["tissues_builder<br/>→ list[TissueContext]"]
            BCt["cell_types_builder<br/>→ list[CellTypeContextV1]"]
            BSc["subcellular_localization_builder<br/>→ SubcellularLocalization"]
            BAn["anatomical_accessibility_builder<br/>→ list[AnatomicalAccessibilityObservation]"]
            BAm["accessibility_modulation_builder<br/>→ list[AccessibilityModulationObservation]<br/>(category-conditional validators)"]
        end
        P2A1 --> P2SE[/"SurfaceEvidence block"/]
        P2A2 --> P2BC[/"BiologicalContext block"/]
    end

    Phase2 --> Synth

    subgraph Synth["B · surfaceome_synthesizer (reused from v1)"]
        direction TB
        SB["run_synthesizer_with_drafts<br/>(reads both drafts in-memory)"]
        SB --> SBOut[/"ExecutiveSummary<br/>SynthesizerLLMFilters<br/>AccessibilityRisks<br/>Confidence + reasoning"/]
    end

    Synth --> Promote

    subgraph Promote["evidence promotion + deterministic + filters"]
        direction TB
        PP["promote_claim per claim<br/>(synthetic SourceTextStore from clip quotes)"]
        PP --> PE[/"list[Evidence] with substring-anchored spans[]"/]
        PD["_stub_deterministic_features (v1 helper)"]
        PD --> PDF[/"DeterministicFeatures (stub)"/]
        PF["_derive_filters (v1 helper, 17 fields)"]
        PF --> PFF[/"Filters block"/]
    end

    Promote --> Assemble

    subgraph Assemble["assemble v1.0.0 SurfaceomeRecord"]
        direction TB
        SR[("SurfaceomeRecord<br/>schema_version=1.0.0")]
    end

    Assemble --> Output[/"<br/>data/annotations/{gene}.json<br/>.runs/surfaceome_v2_{gene}.json<br/>HTML viewer (render_html.py)<br/>"/]

    classDef phase fill:#f3e2e8,stroke:#7a1d3f,color:#222
    classDef store fill:#fbeed1,stroke:#8a5a00,color:#222
    classDef llm fill:#e5dcf7,stroke:#4e3c8a,color:#222
    class Phase1,Phase2,Synth,Promote,Assemble,Resolve phase
    class P1Ledger,RBundle,P2SE,P2BC,SBOut,PE,PDF,PFF,SR,Output store
    class P2A1,P2A2,SB llm
```

## Phase 1 detail — plan-trim-select dual

Per agent (A1 surface evidence focus / A2 biological context focus).
Both legs use the same warmed `CachedHTTP` so the second leg hits the
disk cache on every fetch.

```mermaid
flowchart TB
    Start[("gene + IdentifierBundle")] --> Ctx["_build_gene_context<br/>(UniProt summary + HPA + DB votes)"]

    Ctx --> Plan["_run_planner (Sonnet)<br/>system: plan_system.md<br/>→ SearchPlan with N SearchRequests"]

    Plan --> Loop{{"iteration loop<br/>(MAX_PLAN_ITERATIONS=3)"}}

    Loop --> Exec

    subgraph Exec["_execute_plan"]
        direction TB
        ET1["evidence_retrieval per category<br/>(8 categories: ihc, if_intact,<br/>flow_cytometry, surface_biotinylation,<br/>mass_spec_surfaceome, western_blot_paired,<br/>structure_with_ecd, hpa_ihc)"]
        ET2["gene_literature per mode<br/>(gene2pubmed, topic_search,<br/>fetch_abstract, fetch_fulltext)"]
        ET2 --> FT["fetch_fulltext fallback chain<br/>1. NCBI E-utilities efetch<br/>2. EuropePMC fullTextXML<br/>3. abstract-only graceful degrade"]
    end

    Exec --> Pool[("clip pool<br/>EvidenceClaimDraft × N<br/>keyed by clip_id")]

    Pool --> Trim["_run_trim (Haiku per paper)<br/>system: a1_trim_system.md or a2_trim_system.md<br/>→ TrimResponse with kept clip_ids"]

    Trim --> Menu[("trimmed clip menu<br/>per-paper kept clips")]

    Menu --> Select["_run_selector (Sonnet)<br/>system: a1_select_system.md or a2_select_system.md<br/>→ SelectionResponse with clip_id picks + classifications"]

    Select --> Decide{"selector emitted<br/>needs_more_searches?"}
    Decide -->|yes, iters left| Loop
    Decide -->|no / cap reached| Promote["_promote_selections<br/>(stamp a1_evi_NN or a2_evi_NN)<br/>orchestrator copies verbatim quote<br/>from pool into EvidenceClaim.quote"]

    Promote --> Final[/"list[EvidenceClaim]<br/>100% anchored by construction"/]

    classDef llm fill:#e5dcf7,stroke:#4e3c8a,color:#222
    classDef tool fill:#d8e6f7,stroke:#1d4f8a,color:#222
    classDef store fill:#fbeed1,stroke:#8a5a00,color:#222
    class Plan,Trim,Select llm
    class Exec,FT tool
    class Pool,Menu,Final,Start store
```

## Phase 2 detail — block builder contract

Each builder is one Sonnet call with a closed-enum target schema. Shared
helper `call_builder` runs a Pydantic-repair loop (`MAX_REPAIRS=2`).

```mermaid
flowchart LR
    In[/"ledger slice<br/>(list[EvidenceClaim] + context)"/] --> Render["render_ledger_markdown<br/>(claims serialized with prose + ids)"]

    Render --> Prompt["builder system prompt<br/>(prompts/{builder}_system.md)<br/>+ target block JSON schema"]

    Prompt --> Sonnet["claude-sonnet-4-6"]

    Sonnet --> Raw[/"JSON output"/]

    Raw --> Validate{"Pydantic validate<br/>against target block class"}

    Validate -->|pass| Out[/"structured block"/]
    Validate -->|fail| Repair["repair loop<br/>(send validation error,<br/>ask for corrected JSON)"]
    Repair -->|attempt < 2| Sonnet
    Repair -->|exhausted| Fail[/"return safe default<br/>(empty list / None)"/]

    Out --> Cite{"cited_evidence_ids<br/>scrub against ledger ids"}
    Cite -->|all known| OK[/"block emitted"/]
    Cite -->|some unknown| Drop["drop unknown ids<br/>+ log warning"]
    Drop --> OK

    classDef llm fill:#e5dcf7,stroke:#4e3c8a,color:#222
    classDef gate fill:#fbeed1,stroke:#8a5a00,color:#222
    class Sonnet llm
    class Validate,Cite gate
```

## Data lineage — where each output field comes from

```mermaid
flowchart LR
    EC[("EvidenceClaim<br/>(a1_evi_NN / a2_evi_NN)<br/>+ verbatim quote pinned by orchestrator")] --> Promote["promote_claim<br/>(substring-anchor against synthetic source store)"]
    Promote --> Ev[("Evidence<br/>+ spans[] with quote, source, section")]

    EC -->|A1 ledger slice| BMethods[methods_builder]
    BMethods --> SEM[/"SurfaceEvidence.methods[]"/]

    EC -->|A1 drug-engagement claims| BTe[therapeutic_engagement_builder]
    BTe --> SETe[/"SurfaceEvidence.therapeutic_engagement"/]

    EC -->|A1 contradictory| BCon[contradiction_builder]
    BCon --> SECon[/"SurfaceEvidence.contradicting_evidence[]"/]

    EC -->|A1 full ledger| BGrade[evidence_grade_builder]
    BGrade --> SEG[/"SurfaceEvidence.evidence_grade<br/>+ grade_rationale<br/>+ non_surface_expression[]"/]

    EC -->|A2 tissue_expression| BTi[tissues_builder]
    BTi --> BCT[/"BiologicalContext.tissues[]"/]

    EC -->|A2 cell-type-flavored| BCt[cell_types_builder]
    BCt --> BCCt[/"BiologicalContext.cell_types[]"/]

    EC -->|A2 PM-subdomain| BSc[subcellular_localization_builder]
    BSc --> BCSc[/"BiologicalContext.subcellular_localization"/]

    EC -->|A2 orientation| BAn[anatomical_accessibility_builder]
    BAn --> BCAn[/"BiologicalContext.anatomical_accessibility[]"/]

    EC -->|A2 state-dependent| BAm[accessibility_modulation_builder]
    BAm --> BCAm[/"BiologicalContext.accessibility_modulation[]"/]

    SEM -. cites .-> EC
    SETe -. cites .-> EC
    SECon -. cites .-> EC
    SEG -. cites .-> EC
    BCT -. cites .-> EC
    BCCt -. cites .-> EC
    BCSc -. cites .-> EC
    BCAn -. cites .-> EC
    BCAm -. cites .-> EC

    SEM --> SED[/"SurfaceEvidenceDraft"/]
    SETe --> SED
    SECon --> SED
    SEG --> SED

    BCT --> BCD[/"BiologicalContextDraft"/]
    BCCt --> BCD
    BCSc --> BCD
    BCAn --> BCD
    BCAm --> BCD

    SED --> Synth[surfaceome_synthesizer<br/>run_synthesizer_with_drafts]
    BCD --> Synth
    Synth --> SOut[/"ExecutiveSummary<br/>filters_llm<br/>AccessibilityRisks<br/>Confidence"/]

    Ev --> SR[("SurfaceomeRecord<br/>v1.0.0")]
    SED --> SR
    BCD --> SR
    SOut --> SR
    Stub[("_stub_deterministic_features<br/>(DeepTMHMM/Compara/AlphaFold deferred)")] --> SR
    Filt[("_derive_filters<br/>17-field rollup")] --> SR

    classDef builder fill:#e5dcf7,stroke:#4e3c8a,color:#222
    classDef store fill:#fbeed1,stroke:#8a5a00,color:#222
    class BMethods,BTe,BCon,BGrade,BTi,BCt,BSc,BAn,BAm,Synth builder
    class EC,Ev,SED,BCD,SOut,Stub,Filt,SR store
```

## Notes

- **Resolver v3 boundary.** All gene-symbol input is routed through D1
  → HGNC ID → `resolve_by_hgnc_id` to avoid the symbol-collision
  silent-wrong-protein class (COX1 / WAS / etc.). The orchestrator
  refuses the legacy symbol-through-UniProt path.
- **HTTP cache shared across the dual run.** A2's leg fetches every
  paper A1 already hit via cache; the marginal cost is the
  A2-specialized trim + select model calls.
- **Fulltext fallback chain (post-2026-05-16):** NCBI E-utilities
  `efetch?db=pmc` first (authoritative source), EuropePMC
  `fullTextXML` second (catches EuropePMC-only OAI ingestions),
  abstract-only graceful degrade third. Promoted to NCBI-first after
  a GPR75 survey found EuropePMC 404'd on 58/58 fulltext attempts.
- **Verbatim anchoring is by construction.** Plan-trim-select never
  paraphrases — the selector picks `clip_id`s and the orchestrator
  copies the verbatim `quote` from the clip pool into
  `EvidenceClaim.quote` on promotion. The downstream `promote_claim`
  substring-check is bookkeeping that always passes.
- **Block-builder routing happens on prose, not enum.** `ClaimType`
  has only 5 values; the rich `BiologicalContext` /
  `SurfaceEvidence` structure (modulation categories, therapeutic
  engagement stage, antibody validation, etc.) is populated by the
  builders parsing the selector's `claim` text against the closed
  enums of each block schema.
