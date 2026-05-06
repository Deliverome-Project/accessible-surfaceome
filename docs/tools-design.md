# Custom tools for the surface-proteome Managed Agent

## Why this document exists

The agent needs to answer "is this protein on the cell surface, and how is it attached?" for each gene in our candidate universe. While investigating KAAG1 by hand, we burned ~1,200 lines of raw API output through the main context to surface ~250 lines of load-bearing fact — roughly a 5× token tax. Across 9,000 genes that tax is unaffordable, and a smaller (Haiku/Sonnet) model can't navigate it without choking.

This doc specifies the **custom tools the agent calls instead of doing raw API/file work itself.** Each tool returns pre-distilled, schema-validated structured output, so the agent reasons over high-signal inputs and the deterministic data wrangling lives in code.

## How custom tools work in Claude Managed Agents

Reference: [https://platform.claude.com/docs/en/managed-agents/tools](https://platform.claude.com/docs/en/managed-agents/tools), [https://platform.claude.com/docs/en/managed-agents/events-and-streaming](https://platform.claude.com/docs/en/managed-agents/events-and-streaming)

Custom tools are dispatched **outside** the Anthropic-hosted runtime. The protocol is event-driven, not endpoint-based:

1. We register the tool when creating the agent via `client.beta.agents.create(..., tools=[{type: "custom", name: ..., description: ..., input_schema: {...}}, ...])`. Registration only declares the contract; no executable code runs in Anthropic's environment.
2. During a session, when the model decides to call our tool, the agent emits an `agent.custom_tool_use` event carrying the tool name and input. The session pauses with `session.status_idle` and `stop_reason: requires_action`, listing the blocking event IDs.
3. Our orchestrator subscribes to the session event stream (`client.beta.sessions.events.stream(session_id)`), filters for that pause, dispatches to the corresponding Python function, and POSTs back a `user.custom_tool_result` event to `/sessions/{id}/events` with the matching `custom_tool_use_id` and the result content.
4. The session resumes once all blocking events are resolved.

Practical implications for our design:

- **Tool execution lives in our client.** The dispatcher is a Python table in `src/surface_proteome/agents/orchestrator.py` mapping tool name → handler function. We own all upstream API calls, retries, caching, and rate-limiting.
- **Results are text blocks, not native JSON.** The `content` field is `[{type: "text", text: "..."}]`. Until SDK auto-serialization is documented, we JSON-stringify Pydantic models inside the dispatcher (`model.model_dump_json(indent=2)`) and tell the agent in its system prompt that tool returns are JSON-shaped text.
- **No per-tool timeout/retry is documented.** We wrap every handler in `httpx` timeouts + retry logic ourselves; we do not rely on Anthropic-side semantics.
- **Tool result content size limits are not documented.** Treat ~10k tokens as a soft ceiling per tool return; chunk or paginate above that.
- **Tool descriptions are the primary lever on selection quality.** The official guidance is at least 3–4 sentences per description, explaining what the tool does, when to use it, when *not* to use it, parameter semantics, and caveats. We aim for ~150 words per tool.
- **Consolidate operations behind action parameters.** Fewer, more capable tools beat many single-action tools. Each of our tools below uses a `mode` parameter to expose related operations.
- **Use namespaced tool names.** Names are `gene_lookup`, `gene_literature`, `patent_lookup` — prefix communicates the resource scope.

## Built-in tools we keep, disable, or ignore

The agent toolset (`agent_toolset_20260401`) ships with bash, read, write, edit, glob, grep, web_fetch, web_search. For this agent:

- **Keep `read`, `grep`, `glob`** — useful for the agent to introspect cached corpus files in `data/corpus/{gene}/` if needed.
- **Keep `web_fetch`, `web_search`** — fallback for ad-hoc PDB/HPA pages, and for the <5% Serper-substitute path. Not the primary retrieval surface — that's `gene_literature`.
- **Disable `bash`, `write`, `edit`** — the agent should not run shell commands or write files. All persistence happens in our orchestrator after the agent emits its final structured response.

## The three custom tools

A fourth tool, `evidence_validate`, was considered and rejected: the deterministic validators (substring check, source_id-in-batch, char_offset present, retraction check) belong in the orchestrator's post-tool-call processing layer, not the agent's tool surface. Exposing them as a tool would invite the agent to "ask permission" for things that should run unconditionally on every Evidence record.

### 1. `gene_lookup`

**Purpose.** All identifier resolution, DB-vote panels, UniProt summary distillation, and "why did M1 miss this gene" diagnoses for a single gene. One tool with four modes; the agent picks the mode based on what it needs at each step.

**Description (for the registration payload, ~150 words).**

> Look up a single gene's identifiers, database votes, UniProt summary, or candidate-universe miss diagnosis. Use this tool first whenever you start work on a new gene — call `mode=resolve` with a symbol or accession to canonicalize the identifiers before any other tool call. Use `mode=db_panel` once per gene to get the structured per-source surface-vote panel from local processed data (SURFY, CSPA, UniProt query match, GO, HPA, DeepTMHMM, JensenLab COMPARTMENTS, patent-handle lane). Use `mode=uniprot_summary` to get distilled subcellular-location, topology features, PTMs, tissue specificity, and cross-references — do not call `web_fetch` against UniProt directly; this tool is faster, cached, and Pydantic-validated. Use `mode=miss_diagnosis` only when a gene is in the controls panel but absent from the candidate universe; it returns a structured per-source explanation of why each rule failed to fire.

**Input schema:**

```json
{
  "type": "object",
  "properties": {
    "mode": {"type": "string", "enum": ["resolve", "db_panel", "uniprot_summary", "miss_diagnosis"]},
    "symbol_or_acc": {"type": "string", "description": "HGNC symbol, UniProt accession, or Ensembl gene ID"}
  },
  "required": ["mode", "symbol_or_acc"]
}
```

**Returns (Pydantic-validated, JSON-stringified).** Per-mode shapes:

- `resolve` → `IdentifierBundle` with hgnc_symbol, hgnc_id, aliases, previous_symbols, uniprot_acc, uniprot_status (active/obsolete/merged_into:X), ncbi_gene_id, ensembl_gene, ensembl_canonical_protein, length_aa, isoform_count, alias_collision_risk (low/medium/high), open_targets_status, ncbi_summary. ~300 tokens.
- `db_panel` → `DBVotePanel` with one entry per source (surfy / cspa / uniprot_query / go / hpa / deeptmhmm / compartments / patent_handle), each carrying `vote: bool`, source-specific evidence (e.g., GO returns `[{go_id, evidence_code, term}]`; COMPARTMENTS returns `top3_terms` with stars), plus aggregate `n_sources_voting_surface`, `in_db_union`, `in_patent_handles`. ~400 tokens.
- `uniprot_summary` → `UniProtSummary` with subcellular_locations, topology_features (signal/TM/topo_dom/lipidation/GPI), PTMs, function_text, tissue_specificity_text, isoforms list, n_publications, top-N publications (PMID + title + year), key cross-refs (PDB, InterPro, Pfam, Antibodypedia). ~500 tokens.
- `miss_diagnosis` → `MissDiagnosis` per-source explanation: which rule fired/didn't, what features are missing, which lane(s) would have caught the gene. ~400 tokens.

**Implementation notes.** Calls UniProt REST, HGNC, NCBI Gene, Open Targets GraphQL in parallel for `resolve`; reads local processed Parquet/TSV for `db_panel` and `miss_diagnosis`; one UniProt JSON fetch for `uniprot_summary`. All three external-API modes share an SQLite cache with per-source TTL. **Haiku-safe** for all four modes — pure structured-data assembly, no judgment calls.

### 2. `gene_literature`

**Purpose.** All literature retrieval. Replaces the agent's instinct to call `web_search` 5× with different query phrasings. Operates as a small cascade: NCBI gene2pubmed first (high precision, ~5–20 PMIDs per gene), Europe PMC topic-anchored search second (recall fill), abstract fetch by PMID, and on-demand PMC OA full-text fetch.

**Description (~150 words).**

> Retrieve literature for a gene from NCBI, Europe PMC, and patent indices. Always start with `mode=gene2pubmed` — it returns NCBI's curated PMID list for the gene, which is far higher-precision than keyword search and the right starting point for any well-characterized gene. Use `mode=topic_search` only to fill recall when gene2pubmed returns fewer than 5 PMIDs or when you need surface-method-specific evidence (flow cytometry, surface biotinylation, IHC). Use `mode=fetch_abstract` to pull the abstract for a specific PMID with auto-tagged topic categories. Use `mode=fetch_fulltext` only for PMC-OA papers and only when an abstract is ambiguous and the paper is on the priority list — full text is large and rate-limited. Returned papers carry `topic_tags`, `is_review`, `is_retracted`, and `is_pmc_oa` so you can prioritize without re-reading.

**Input schema:**

```json
{
  "type": "object",
  "properties": {
    "mode": {"type": "string", "enum": ["gene2pubmed", "topic_search", "fetch_abstract", "fetch_fulltext"]},
    "uniprot_acc": {"type": "string"},
    "ncbi_gene_id": {"type": "integer"},
    "pmid": {"type": "integer"},
    "pmcid": {"type": "string"},
    "topic_anchors": {
      "type": "array",
      "items": {"type": "string", "enum": ["surface_expression", "topology", "ihc", "flow_cytometry", "surface_biotinylation", "mass_spec_surfaceome", "structure", "ptm", "shedding"]}
    },
    "max_results": {"type": "integer", "default": 25}
  }
}
```

**Returns.**
- `gene2pubmed` → `LiteraturePack` with ordered PMIDs and per-paper metadata: pmid, year, journal, title, abstract, is_review, is_retracted, publication_type, topic_tags, is_pmc_oa, pmc_id. Topic-tagging is rule-based (regex/keyword), done in the tool *before* tokens hit the agent.
- `topic_search` → same `LiteraturePack` shape; results dedup'd against gene2pubmed if both modes are used.
- `fetch_abstract` → single `Paper` record, ~200 tokens.
- `fetch_fulltext` → `Paper` with sections array (intro, methods, results, discussion, figure_legends), excludes references. **Cap at ~10k tokens**; if longer, sections are truncated and a `truncated_sections: list[str]` field flags which were trimmed.

**Implementation notes.** NCBI E-utils with API key + 10 qps semaphore; Europe PMC with 8 qps self-throttle. Retraction-Watch DB cross-ref runs at fetch time, sets `is_retracted` flag. Results cached by content hash (sha256) per the plan's anti-hallucination requirements. **Haiku-safe** for `gene2pubmed`, `topic_search`, `fetch_abstract`. `fetch_fulltext` is Sonnet-grade given the truncation logic.

### 3. `patent_lookup`

**Purpose.** Patent literature is where most of the "tumor surface ADC target" framing lives for under-DB-annotated genes (KAAG1 was the canonical case). The conventional sources cascade misses these systematically. This tool is the agent's hook into Google Patents / EPO OPS for delivery-handle provenance.

**Description (~120 words).**

> Look up a patent disclosure for delivery-target evidence. Use this whenever a gene appears in the patent-handle lane of the candidate universe (`db_panel.patent_handle.vote=True`) or when conventional sources return no surface evidence but a review article cites a patent. Returns the patent's title, priority date, applicant, claims summary, the cited gene list, and any figure-disclosed experimental evidence (IHC, flow cytometry, mAb characterization). Patent claims are *not* peer-reviewed primary evidence — the returned record carries `evidence_provenance: "patent"` and the agent must respect this when grading evidence tiers. Do not use this tool to look up scientific literature; use `gene_literature` for that.

**Input schema:**

```json
{
  "type": "object",
  "properties": {
    "wo_number": {"type": "string", "description": "WO/EP/US patent number, e.g. WO2024036333A2"}
  },
  "required": ["wo_number"]
}
```

**Returns.** `PatentSummary` with wo_number, title, applicant, priority_date, publication_date, claims_summary (top-N independent claims, condensed), cited_genes (list of HGNC symbols), experimental_evidence_figures (list of `{figure_id, modality, summary}`), evidence_provenance="patent". ~600 tokens.

**Implementation notes.** Google Patents JSON or EPO OPS API. Caching essential — patents don't change. **Sonnet-grade** because the claims-summary distillation may use a small LLM call internally (cheap, deterministic prompt).

## Tool surface summary

| Tool | Modes | Typical tokens returned | Smallest model that can use it | Replaces |
|---|---|---|---|---|
| `gene_lookup` | resolve, db_panel, uniprot_summary, miss_diagnosis | 300–500 | Haiku | direct curl/API to UniProt, HGNC, NCBI Gene, Open Targets; raw TSV grep |
| `gene_literature` | gene2pubmed, topic_search, fetch_abstract, fetch_fulltext | 200–10000 | Haiku (except fulltext: Sonnet) | EuropePMC keyword spam, NCBI efetch loops, web_search |
| `patent_lookup` | (single mode) | ~600 | Sonnet | manual Google Patents reading |

Net token compression vs raw API access on the KAAG1 walk-through: **roughly 4×** on the deterministic part of the pipeline, with no fidelity loss because distillation is done by code, not by the model.

## What lives outside the tool surface (orchestrator-internal)

These run in our Python pipeline before/after agent calls, *not* as agent tools:

- **Deterministic validators**: substring check on quotes, char_offset present, source_id ∈ batch, retraction cross-ref, content-hash verification. Run on every Evidence record the agent emits.
- **Claim-entailment audit**: a separate Sonnet call (not a tool from the agent's perspective). The orchestrator submits Evidence records and gets back entailment results; the audit results gate persistence.
- **Cascade routing**: deciding whether to escalate from Sonnet → Opus light → Opus heavy. Pure Python rules over the gene synthesis output.
- **Persistence**: writing `data/annotations/{gene}.json`, `data/audit/{gene}.jsonl`, the corpus bundle. Never the agent's responsibility.

## File layout

```
src/surface_proteome/
  agents/
    managed_agent.py          # creates the agent (tool registry + system prompt)
    orchestrator.py           # event-stream subscriber + custom-tool dispatcher
    tool_registry.py          # name → (handler, input_schema, description) table
  tools/
    gene_lookup.py            # 4 modes, returns Pydantic models
    gene_literature.py        # 4 modes
    patent_lookup.py
    _shared/
      cache.py                # SQLite-backed, per-source TTLs
      ratelimit.py            # asyncio.Semaphore per upstream API
      models.py               # Pydantic return shapes (IdentifierBundle, DBVotePanel, etc.)
  schemas.py                  # Evidence, GeneAnnotation (per the plan)
```

## Build order

1. Pydantic return models in `tools/_shared/models.py` — drives every other decision.
2. `gene_lookup` end-to-end with all four modes; smoke-test against KAAG1, CD19, ABCB9.
3. Orchestrator dispatcher + Managed Agent registration; one tool wired up; KAAG1 producing a `GeneAnnotation`.
4. `gene_literature` with all four modes; smoke-test against the same three genes.
5. `patent_lookup`; smoke-test against `WO2024036333A2` (the KAAG1 patent).
6. Run the full 6 worked-example genes (CD19, ABCB9, KRAS, MSLN, ST3GAL1, KAAG1) end-to-end; compare outputs against the hand-investigated ground truth.

## Open questions

- **SDK Pydantic auto-serialization.** Does `client.beta.sessions.events.create(..., content=PydanticModel)` serialize automatically, or do we need to JSON-stringify ourselves? Test on first integration; default to manual stringification until verified.
- **Tool-result size ceiling.** Not documented. Test `fetch_fulltext` with a 30k-token PMC paper and see what the platform does. Until we know, cap at 10k tokens with truncation flags.
- **Per-tool timeout/retry.** Not documented platform-side. We implement timeouts in the handler with `httpx`; retries are app-level.
- **Whether `evidence_validate` ever needs to be a tool.** Currently orchestrator-internal. Revisit if the agent ever wants to ask "is this quote substring valid?" before emitting it (probably never; the validator is a gate, not a query).
