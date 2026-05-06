# Evidence + provenance architecture

> Drafted 2026-05-06. The agent currently emits `cited_evidence_ids: list[str]`
> as PMID strings — no verbatim quotes, no locations, no hash anchoring. This
> doc captures the design we're committing to for full claim-level
> provenance, oriented around two principles:
>
> 1. **Computationally tractable.** Every claim's substring, hashes, char
>    offset, retrieval timestamp, retraction status, and URL are derivable
>    from cached source data — no model calls needed for bookkeeping.
> 2. **Minimize agent context.** The agent emits the minimum necessary to
>    identify a claim (source_id + verbatim quote + claim metadata) and the
>    orchestrator constructs the full Evidence record from cached data the
>    agent already saw.

## Core split: agent emits claims, orchestrator builds records

The agent produces small, human-shaped statements. The orchestrator does
deterministic bookkeeping and validation.

```
Agent emits                              Orchestrator builds + persists
───────────────                          ────────────────────────────────
EvidenceClaim                            Evidence
  evidence_id: "evi_001"           →       evidence_id: "evi_001"
  claim                                    claim
  claim_type / direction                   claim_type / direction
  evidence_type / tier / confidence        evidence_type / tier / confidence
  assay_context                            assay_context
  source_id: "PMID:10601354"       ┐       spans: [EvidenceSpan]
  quote: "Short-term cultures..."  │         source: SourceRef
  section: "results"               │           source_id, url, title
  figure_or_table_id: "Fig 3"      │           retrieved_at, content_sha256
                                   │           publication_type, license
                                   │           is_retracted, retraction_checked_at
                                   │         section, figure_or_table_id
                                   │         quote, quote_sha256
                                   │         char_offset
                                   │         normalized_source_sha256
                                   │       entailment_verified
                                   │       validation_warnings
                                   ┘
```

The agent never emits hashes, char offsets, URLs, or retrieval timestamps.
Tokens stay low; the data is reconstructible from cached source bodies.

## Schema additions

### `EvidenceClaim` — what the agent emits

```python
class EvidenceClaim(BaseModel):
    evidence_id: str               # agent-assigned, e.g. "evi_001". Used for cross-references.
    claim: str
    claim_type: ClaimType          # surface_expression | topology | tissue_expression | methodological | contradictory
    direction: Direction           # supports | refutes | ambiguous
    evidence_type: EvidenceType    # flow_cytometry | surface_biotinylation | mass_spec_surfaceome | IHC | IF | crystal_structure | cryo_em | computational_prediction | orthology | review_assertion | db_annotation
    evidence_tier: EvidenceTier    # primary | secondary
    confidence: EvidenceConfidence # strong | moderate | weak
    assay_context: AssayContext    # species, cell_type, permeabilized, fixation, isoform
    source_id: str                 # "PMID:10601354" | "WO2024036333A2" | "UniProt:Q9UBP8" | "PDB:2ABC"
    quote: str                     # ≤200 chars verbatim
    section: PaperSection          # abstract | results | discussion | methods | figure_legend | …
    figure_or_table_id: str | None # "Figure 3A", "Table S1"
```

### `SearchEntry` — what we looked at (orchestrator-built from `events.jsonl`)

```python
class SearchEntry(BaseModel):
    tool: str                              # "gene_literature" | "patent_lookup" | "gene_lookup"
    mode: str | None                       # "gene2pubmed" | "topic_search" | "fetch_abstract" | …
    query: dict[str, Any]                  # e.g. {"uniprot_acc": "Q9UBP8"}
    n_results: int
    sources_seen: list[str]                # ["PMID:10601354", "PMID:14574404", …]
    retrieved_at: datetime
    contributed_evidence_ids: list[str]    # which Evidence cited these sources
```

Two payoffs for the search log:

1. **Comprehensiveness audit.** Did we check the shedding literature for KAAG1?
   Grep `search_log` for `topic_search` with `shedding` anchor; if absent, the
   gene is an audit-incomplete record.
2. **Re-run efficiency.** When re-annotating a gene under a newer schema, the
   orchestrator can show prior search log in the kickoff message: "Last run
   already covered gene2pubmed + patent_lookup + fetch_abstract on
   PMID:10601354. Skip these unless re-checking is warranted." Cuts redundant
   tool calls.

The agent never sees `search_log` during the run — it's reconstructed
post-hoc from `events.jsonl`.

### `Evidence` (refined) — what we persist

The existing `Evidence` model gains:

- `evidence_id: str` — carried over from `EvidenceClaim` so cross-references
  stay stable.
- `validation_warnings: list[str]` — populated when substring check passes
  with quirks (e.g. "matched after Greek-letter transliteration"), or when a
  precondition softly failed.
- `entailment_verified: bool` — `True` only if the substring check passed
  cleanly. `False` if the orchestrator could not anchor the quote.

### `SurfaceomeRecord` (refined)

Two new top-level fields:

- `evidence: list[Evidence]` — the centralized array.
- `search_log: list[SearchEntry]` — what we looked at.

Per-bucket `cited_evidence_ids: list[str]` on **load-bearing fields only**:

- `surface_biology.cited_evidence_ids` — for the surface_status / topology /
  anchor_type calls
- `targetability.cited_evidence_ids` — for tier + recommended_modalities
- `expression.cited_evidence_ids` — for tumor_indications + tumor_specificity
- `risk_flags[i].cited_evidence_ids` — each flag's severity/blocking call
- `therapeutic_landscape.approved_drugs[i].cited_evidence_ids` — FDA approval
  letter / label / clinical paper
- `therapeutic_landscape.clinical_trials[i].cited_evidence_ids` — NCT entry
- `therapeutic_landscape.patent_disclosures[i].cited_evidence_ids` — Google
  Patents URL (or just rely on `wo_number`; possibly redundant)
- `therapeutic_landscape.preclinical_evidence[i].cited_evidence_ids` — the
  paper(s) characterizing the modality

The existing top-level `cited_evidence_ids: list[str]` is removed (made
redundant by the per-bucket fields).

### `SurfaceomeRecordDraft` — the agent's emission shape

A separate Pydantic model for what the agent emits:

```python
class SurfaceomeRecordDraft(BaseModel):
    # all of SurfaceomeRecord's fields EXCEPT:
    #   - evidence (orchestrator builds)
    #   - search_log (orchestrator builds)
    # PLUS:
    evidence_claims: list[EvidenceClaim]
    # cited_evidence_ids fields use the agent-assigned evidence_id strings
```

The orchestrator parses agent JSON as `SurfaceomeRecordDraft`, validates
each `EvidenceClaim`, builds `Evidence` records, and emits the canonical
`SurfaceomeRecord` (with `evidence` populated, `evidence_claims` dropped).

## Validation pipeline

For each `EvidenceClaim` the agent emits:

1. **Look up cached source text.** The orchestrator maintains a small
   `source_id → cached body` map populated as `gene_literature` /
   `patent_lookup` / `gene_lookup` fetch during the session. Backed by the
   existing `CachedHTTP` SQLite cache; we expose a `SourceTextStore` over
   it.

2. **Normalize source + quote** the same way:
   - Unicode NFKC
   - Greek-letter transliteration both directions (α↔alpha, β↔beta, etc.)
   - HTML entity decoding (`&amp;`, `&#x2014;`, etc.)
   - Whitespace collapse (runs of `\s` → single space)
   - Lowercase (TBD: case-sensitive for chemical names; revisit)

3. **Substring check.** Assert normalized quote appears in normalized source.
   - On success: compute `char_offset` (position in *normalized* source),
     `quote_sha256`, `content_sha256`, `normalized_source_sha256`. Build the
     full `Evidence` + `EvidenceSpan` + `SourceRef` chain.
     `entailment_verified = True`.
   - On failure: persist the claim as an `Evidence` record with
     `entailment_verified = False` and a warning describing the failure
     ("substring not found in normalized PMID:10601354 text"). The claim
     is preserved for review; we don't reject.

4. **Retrieval metadata** (already in cached metadata): `retrieved_at`, `url`,
   `title`, `publication_type`, `license`. Filled in deterministically.

5. **Retraction check** (deferred to phase 2): Retraction-Watch cross-ref at
   fetch time. Phase 1 uses Europe PMC's `pubTypeList` "Retracted Publication"
   marker.

6. **Claim-entailment audit** (deferred — opt-in via `--audit` flag):
   separate Sonnet call asking `(quote, claim, direction) → entailed: bool`.
   Catches "right citation, wrong direction" — e.g. quote says "did not
   detect surface" but claim says `direction=supports`. Skip during
   iteration; turn on for gold-standard runs.

## Decisions made

1. **Centralized `evidence: list[Evidence]`** at the top level, with per-bucket
   `cited_evidence_ids` referencing by `evidence_id`. Deduplicates citations
   that support multiple buckets.
2. **Load-bearing fields only get evidence requirements.** Identity fields
   (`gene.hgnc_symbol`, etc.) don't need citations; HGNC is the authority
   by definition.
3. **Skip absence provenance.** "UniProt has no TM annotation" doesn't get
   an Evidence record — the search log captures the call we made and the
   cached UniProt entry's content_sha256, which is enough provenance for an
   absence.
4. **Persist with flags, never reject.** Failed substring checks produce
   `entailment_verified=False` records, not dropped data. Surfaces in the
   run summary so we can tune normalization or prompts; nothing gets lost.
5. **Substring check first; richer pipeline later.** Phase 1 is just the
   normalization + substring + char_offset. Retraction cross-ref + claim-
   entailment audit are phase 2.
6. **Skip the audit during iteration.** The Sonnet entailment call costs
   ~$0.05–0.15/gene; defer to gold-standard batches.
7. **No static site yet.** The user is designing it; build comes later.
   Phase 1 produces the JSON; render layer is downstream.

## Validation feedback loop

Open question pinned: **Option A** for first iteration (one-shot, no
agent retry on validation failure). The agent emits, the orchestrator
validates, anything that fails substring is persisted with
`entailment_verified=False` + warning. We measure the substring-failure
rate on the validated-target baselines; if it exceeds ~10%, we add
**Option B** (one round-trip with focused feedback to the agent on the
failed claims) as a follow-up.

## What stays implicit (no Evidence records needed)

- **Identity** — `gene.hgnc_symbol`, `uniprot_acc`, etc. HGNC is authoritative.
- **Database absences** — "UniProt records no signal peptide" / "all 8 M1
  sources vote false". Anchored in the search log + the cached source
  bodies.
- **Tool returns we cite implicitly** — when the agent says "per
  `gene_lookup mode='db_panel'` results", the search log entry IS the
  provenance. No need to extract a quote.

## Computational tractability checklist

For a record to be auditable, anyone with the same source corpus should be
able to:

- ✅ Re-fetch every `SourceRef.url` and confirm `content_sha256` matches.
- ✅ Re-normalize and confirm `normalized_source_sha256` matches.
- ✅ Locate the quote at the recorded `char_offset` in the normalized source.
- ✅ Verify `quote_sha256` matches.
- ✅ Re-run the retraction check at any time and compare against
  `retraction_checked_at`.
- ✅ For each search log entry, replay the tool call and confirm
  `sources_seen` matches.

Nothing in the validation requires re-running the model. The whole chain is
deterministic.

## Phased build

| Phase | Scope | Effort |
|---|---|---|
| **1. Schema migration** | `EvidenceClaim`, refine `Evidence`, `SearchEntry`, `SurfaceomeRecordDraft`, per-bucket `cited_evidence_ids`, top-level `evidence` + `search_log`, bump to v0.3.0. No orchestrator changes yet. | ~½ day |
| **2. Orchestrator: claim → evidence promotion** | Normalization helpers (NFKC + Greek + HTML + whitespace), `SourceTextStore` over `CachedHTTP`, substring check, build `Evidence` chain, populate `search_log` from `events.jsonl`. | ~1 day |
| **3. Source caching audit** | Make sure `gene_literature.{fetch_abstract,fetch_fulltext}`, `patent_lookup`, and `gene_lookup` returns expose canonical text + `content_sha256` so orchestrator can replay. | ~½ day |
| **4. System prompt rewrite** | Teach the agent the `EvidenceClaim` shape; drop instructions about `Evidence`/`SourceRef`/hashes (they go away from the agent's view). | ~½ day |
| **5. Smoke test on KAAG1** | Re-run, verify substring checks on the founding-paper quotes, verify `search_log` captures all 6 tool calls. | ~½ day |
| **6. Validated-target baselines** | Run the 11 with full provenance. First batch where every load-bearing claim is substring-anchored. | ~$1–3 |
| **7. Phase 2 (later)** | Retraction-Watch cross-ref, opt-in `--audit` for claim-entailment, `data/sources/` corpus persistence. | follow-up |

## Phase 2 schema refinements (2026-05-06)

The Phase 2 promotion pipeline forced one schema refinement, captured here so
future readers can audit why we bumped `SCHEMA_VERSION` to `v0.3.1`.

**Change:** `Evidence.spans` was `Field(..., min_length=1)`; it is now
`Field(default_factory=list)` (i.e. an empty list is legal). A new model
validator enforces that `entailment_verified=True` records still carry ≥1
span.

**Rationale.** When an `EvidenceClaim` cites a source we never fetched (or a
source where the verbatim quote can't be substring-anchored after
normalization), the orchestrator persists the claim with
`entailment_verified=False` and a `validation_warnings` entry. The original
schema required ≥1 `EvidenceSpan`, but a span requires a `SourceRef`
(`HttpUrl` URL, `content_sha256`, `retrieved_at`, etc.) — fields we don't have
when the source isn't in the session store. The cleanest options were:

1. Synthesize a placeholder `SourceRef` with sentinel values (dishonest:
   readers can't tell sentinel from real).
2. Use `char_offset=-1` as a sentinel (the rest of the chain still requires
   real `content_sha256` / `retrieved_at` we'd have to invent).
3. **Allow `spans=[]` for unverified evidence (chosen).** Verified evidence
   keeps the same shape as before; unverified evidence persists the claim
   text, classification, and warning without lying about the provenance
   chain. The validator pins the invariant so we can't accidentally ship a
   verified record without a span.

**Consequence for downstream readers.** `Evidence` consumers must check
`entailment_verified` before assuming `spans` is populated. The persisted
record's `evidence_count` still counts unverified records; downstream gates
that need anchored evidence should filter by `entailment_verified`.

## Things explicitly not in scope here

- **Static site / render layer** — the user is designing this separately.
- **Ontology-review agent** — wait for ~30 records.
- **Expression depth (HPA + Open Targets)** — moved behind provenance per
  user direction.
- **ChEMBL drug landscape** — same.
- **Memory stores for cross-session state** — we'd need them to make the
  search-log re-run optimization actually save tokens; defer.

## Open questions deferred

1. **Validator strictness once we measure substring-failure rate.** If <5%,
   keep one-shot. If higher, add agent round-trip on failed claims.
2. **Case-sensitivity of normalization.** Lowercase is safer for prose;
   case-sensitive is right for chemical names ("PD-L1" vs "pd-l1"). Probably
   case-insensitive substring matching with a flag in `validation_warnings`
   if the original case didn't match.
3. **How to cite tool returns** (e.g. "per UniProt, no TM features"). Either
   surface as Evidence with `source_id="UniProt:Q9UBP8"` and a quote like
   `"topology_features: []"`, or keep implicit via search log. Lean implicit
   for now.
4. **Identifier for cached UniProt body.** We need to give it a stable
   source_id so EvidenceClaim can reference it the same way as PMID-keyed
   papers. Probably `"UniProt:Q9UBP8"` keyed to the cached
   `https://rest.uniprot.org/uniprotkb/Q9UBP8.json` response.
