# Surface-proteome annotator: status + roadmap

> Snapshot at 2026-05-06. The annotator is a working proof-of-concept that
> produces `SurfaceomeRecord v0.2.0` JSON for a single gene end-to-end. This
> doc captures what's filled today, what's sparse, and what we're building
> next.

## Status

The annotator ships:

- A reconciled per-protein record (`SurfaceomeRecord`) with seven buckets:
  `targetability`, `surface_biology`, `expression`, `adc_properties`,
  `therapeutic_landscape`, `risk_flags`, plus identity + provenance.
- Two custom tools registered with the Managed Agent: `gene_lookup` (four
  modes: resolve / db_panel / uniprot_summary / miss_diagnosis) and
  `patent_lookup` (Google Patents).
- Hybrid enums (closed list + `"other"` + required `*_other_label`) for
  ontology evolution. `schema_version` lets future records pin to a specific
  version of the ontology.
- An orchestrator that creates a session per gene, dispatches custom tools
  through the SSE event stream, and persists `data/annotations/{gene}.json`
  + a run log under `.runs/<timestamp>-<gene>-<session_id>/`.

End-to-end on KAAG1 (the canonical edge case): 5 tool calls, ~875 tokens of
output, correct call (`tier=edge_case`, `surface_status=absent`,
`anchor_type=mhc_presented_peptide`), patent surfaced with applicant + dates,
4 risk flags including one `other`-labelled novel category
(`antisense_orf_low_protein_evidence`).

## What each bucket has, today

| Bucket / field | Source | Status |
|---|---|---|
| `gene` identifiers | UniProt + HGNC + NCBI Gene | rich (approved name + alias_names + previous_names + previous_symbols) |
| `surface_biology.surface_status` / `topology` | M1 candidate-universe + UniProt features | rich; agent reasons over `db_panel` + `uniprot_summary` |
| `surface_biology.anchor_type` | UniProt topology features | rich |
| `surface_biology.extracellular_domain` | UniProt features | partial — domain names + size, not always full set |
| `surface_biology.glycosylation` / `shedding_documented` | UniProt features | sparse — UniProt has glycosylation features but shedding requires lit-mining |
| `surface_biology.db_comparison` | M1 candidate-universe + patent-handle controls panel | rich |
| `expression.tumor_indications` / `normal_tissue_top` | UniProt tissue prose + agent's trained knowledge | sparse — needs HPA / Open Targets |
| `expression.tumor_specificity` | agent inference | sparse without quantitative data |
| `adc_properties.internalization` / `copies_per_cell` | (none) | empty by design — needs `gene_literature` |
| `therapeutic_landscape.approved_drugs` / `clinical_trials` | agent's trained knowledge | partial — fine for the validated 11, sparse for novel candidates; needs ChEMBL |
| `therapeutic_landscape.patent_disclosures` | `patent_lookup` (Google Patents) | rich — title + applicant + dates + summary |
| `therapeutic_landscape.preclinical_evidence` | agent's trained knowledge | sparse — needs `gene_literature` |
| `risk_flags` | agent inference | rich — closed enum + `other` for novel risks |
| `evidence` records | (none) | empty by design — full Evidence-chain validation lands with `gene_literature` + claim-entailment audit (M3 plan) |

## Roadmap

Numbered roughly by priority × effort.

### 1. Validated-target baselines (small, immediate)

Annotate the 11 validated ADC targets — HER2, TROP2, Nectin-4, CD19, CD20,
CD22, CD30, CD33, CD79b, BCMA, FRα — under the current schema. Establishes
what `tier=validated_target` records look like so novel candidates have a
benchmark. ~$0.10–0.25 per gene at Opus 4.7. Outputs are immediately useful
for the eventual blog post comparison table.

### 2. `gene_literature` tool (highest ROI)

Already specced in [docs/tools-design.md](../tools-design.md). Modes:
`gene2pubmed`, `topic_search`, `fetch_abstract`, `fetch_fulltext` (with the
~10k-token truncation cap). NCBI E-utils + Europe PMC. Unblocks:

- `adc_properties.internalization` (lit-mining for "internalization",
  "endocytosis")
- `surface_biology.shedding_documented` (lit-mining for "shedding", "soluble
  form", BACE1/ADAM cleavage references)
- `therapeutic_landscape.preclinical_evidence` (mAb / ADC / CAR / TCR-mimic
  characterization papers — far richer than the agent's trained knowledge,
  especially for non-validated candidates)
- Real Evidence records with verbatim quotes + char_offset, enabling the
  deterministic-validator path from the M3 plan.

### 3. Expression depth (HPA + Open Targets)

The HPA cancer/tissue atlas data is already loaded for surface flag
purposes; we just don't expose it to the agent. Add a new
`gene_lookup mode="expression"` (or a sibling `expression_lookup` tool) that
returns:

- HPA tissue expression (top N normal tissues with levels)
- HPA cancer atlas (top N tumor types with prevalence)
- Open Targets disease-target associations (which indications has this been
  associated with, and at what evidence weight)

Open Targets uses GraphQL — slightly more lift than the REST clients we
have. The disease association data is the bigger payoff for therapeutic
context than the bare expression numbers.

### 4. ChEMBL drug-landscape integration

Approved drugs + clinical trials for `therapeutic_landscape`. Two paths:

1. **Static curated dump** for the validated 11 — quick, deterministic, no
   API dependency. Likely sufficient for the gold-standard baseline.
2. **Live ChEMBL API** for novel candidates — useful when we expand to the
   broader 47 patent-handle controls or beyond.

Start with (1); add (2) when we run more than ~20 novel candidates and the
agent's trained knowledge starts feeling stale.

### 5. Ontology-review agent

Once we have ~20–50 records, scan accumulated `*_other_label` entries and
propose new closed-enum categories or merges across the modality / risk-flag
ontologies. The hybrid-enum mechanism is already in place; the review agent
is its consumer. It would emit:

- New literal candidates ("anti_pmhc_bispecific_tcr_engager" → promote to
  closed `ModalityKind`)
- Duplicate detections ("low_density" vs "below_adc_threshold")
- Schema-version bumps (`v0.2.0` → `v0.3.0`) with migration notes

### 6. Validation pass (M3 plan deferred)

Per `docs/plans/2026-04-16-surface-proteome-annotation.md`, every Evidence
record needs:

- Substring check (verbatim quote present in normalized source text)
- `char_offset` non-null and matching the substring
- Source ID in batch (no out-of-batch citations)
- Retraction-Watch cross-reference at fetch time
- Claim-entailment audit (separate Sonnet call: does the quote actually
  support the claim direction?)

These are deterministic Python validators + one probabilistic gate. They
gate persistence — an Evidence record that fails any of them is rejected,
not "fixed up". Lands when `gene_literature` produces real Evidence records
to validate.

### 7. Quality-of-life

- `accessible-surfaceome agents view <run-dir>` — readable transcript
  renderer (we have a one-off script for this; promote to CLI).
- `accessible-surfaceome agents annotate --batch <file>` — batch annotation
  with per-gene parallelism.
- Lossless stream reconnect (per
  [shared/managed-agents-client-patterns.md](https://platform.claude.com/docs/en/managed-agents))
  — required before any unattended overnight batch.
- Cost tracking surfaced in the run summary; budget cap per run.
- Cleanup of orphaned remote agents / environments left by failed sync
  attempts.

## Open questions

- **Expression source priority**: HPA cancer atlas vs Open Targets vs
  TCGA/GTEx. HPA is what we already have loaded; the others have richer
  granularity. Pick one and surface the rest as fallback.
- **ChEMBL static vs live**: static dump is simpler but stale. Decide based
  on how often we re-annotate.
- **When does the ontology-review pay off?** Probably ~30 records. Our
  current corpus is 1.
- **Validation strictness**: should an Evidence record that fails the
  substring check be rejected silently (lose the citation) or surfaced as a
  contradiction the agent must resolve? M3 plan says rejected; revisit when
  we see real failure rates.
- **Memory stores**: do we need cross-session persistent memory (e.g. for
  the agent to remember its own prior calls on the same gene)? Not yet —
  stateless per-gene sessions work for v0. Revisit if/when we add multi-turn
  conversational use.
- **Cost budget per gene**: currently ~$0.05–0.25. Acceptable for the
  validated 11 + 47 patent-handle controls. For 9,000-gene full-universe
  runs (per the M3 plan), needs Batch API integration and tighter prompts.

## Build order I'd propose

For the next session: items 1 + 2 in parallel. The validated-11 baseline
runs in the background while `gene_literature` is built; when literature
lands, re-run the validated 11 to populate `preclinical_evidence` properly.
Items 3–4 follow once we know what the validated-11 records look like.
Items 5–6 wait for corpus + literature respectively.
