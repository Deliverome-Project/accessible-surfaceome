# Surface Proteome Annotation Project — Scoping Plan

> **Revision v2 (2026-04-16)** — incorporates Codex critical review. Major changes: alias-disambiguation hoisted to M0 pre-work, PDB added as 9th source, claim-entailment layer added to anti-hallucination, cost model recomputed with corrected token math + Batch API (50% off) + explicit pricing-verification step, audit sample size increased to n=300 stratified (was n=50; underpowered for 95% gate), Evidence schema extended with species/cell-type/isoform/assay context, licensing & redistribution section added, timeline extended from 3 weeks to 5–6 weeks.

## Context

**Goal.** Use Claude agents to produce a human surface-proteome annotation set that corrects known errors in SURFY/CSPA/UniProt/GO and adds evidence-grade topology calls with per-claim citations. Deliverable is an open blog post + public code + results table, acknowledging Anthropic's CC seats / API credits support.

**Why this is worth doing.** Becca has identified concrete false positives (e.g. `ABCB9` — a lysosomal protein listed in SURFY) and false negatives across existing DBs. No DB combines: (a) a graded evidence confidence scale (beyond binary yes/no), (b) topology discrimination, (c) per-claim literature citations. This project fills that gap for therapeutically-relevant target discovery, particularly as a lever for delivery-modality selection (ADC, CAR-T, mRNA-LNP, etc.).

**Near-term output (v0).** Per-gene annotation consisting of **two independent but related fields**:

- **`surface_status`** — "is this protein accessible from the extracellular side of an intact plasma membrane?" Graded: `strong_surface` / `moderate_surface` / `weak_surface` / `rare_surface` / `absent` / `contradictory`.
- **`topology`** — "how is this protein associated with the plasma membrane?" Enum: `transmembrane_single_pass` / `transmembrane_multi_pass` / `outer_leaflet_peripheral` / `gpi_anchored` / `inner_leaflet_peripheral` / `cytosolic_pm_adjacent` / `not_pm_associated`.

Note that these are **orthogonal**: `KRAS` has `topology=inner_leaflet_peripheral` *and* `surface_status=absent` (membrane-anchored but not extracellularly accessible — correctly flagged as a negative control for delivery-modality purposes). The two fields must both be reported; interpreting `topology` alone will produce the same false-positive pattern that SURFY exhibits.

- **Evidence pack**: per-claim citations (PMID / DOI / DB entry) with evidence type, assay context, and species. Full schema in Provenance section.
- **DB-comparison row**: SURFY / CSPA / UniProt / GO labels alongside ours, for disagreement analysis.

**Gene-level annotation is v0 scope.** Isoform-specific topology differences (real and well-documented for several surface families) are **flattened to the canonical UniProt isoform** for v0 and flagged with `isoform_flattened=True` where the gene has >1 reviewed isoform with differing signal-peptide/TM prediction. Isoform-level resolution is deferred to v1.

Internalization, tissue/cell-type-specific surface expression, and model-species conservation are explicitly **deferred** to v1.

---

## Prior art & design analogue — Lambert et al. 2018 ("The Human Transcription Factors")

The closest methodological precedent for what we're building is the Lambert et al. 2018 human TF census. They faced a structurally identical problem — multiple prior DBs (TFCat, TF Census, TFClass, CisBP, GO, PDB) disagreeing on what counts as a human transcription factor — and produced what is now *the* canonical list (1,639 TFs from 2,765 candidates) by being explicit about adjudication, grading, and provenance. We deliberately mirror their methodology where it transfers, and document where we diverge.

**Reference:** Lambert SA, Jolma A, Campitelli LF, Das PK, Yin Y, Albu M, Chen X, Taipale J, Hughes TR, Weirauch MT. *The Human Transcription Factors.* **Cell** 172(4):650–665 (2018-02-08). DOI: [10.1016/j.cell.2018.01.029](https://doi.org/10.1016/j.cell.2018.01.029). Public resource: [http://humantfs.ccbr.utoronto.ca/](http://humantfs.ccbr.utoronto.ca/).

### Mapping their choices onto ours

| Their move | Why it worked | Our analogue |
|---|---|---|
| **Union of 6 prior DBs → 2,765 candidates** | Recall-first; precision is for the adjudication step, not the universe | Union of SURFY + CSPA + UniProt + GO + HPA + ML → ~9k candidates (M1, recall-first by design) |
| **Two expert judges vote per candidate, disagreements resolved** | Single-judge calls are not credible at this scale; explicit disagreement resolution is the provenance | Sonnet extraction + claim-entailment audit + Opus cascade as "two-judge + arbiter"; Becca adjudicates the n=100 DB-disagreement spotlight (M6) |
| **Graded categories, not binary** (`known motif` / `homologous motif` / `likely` / `ssDNA-RNA-binding` / `unlikely`) | Binary calls hide real biology and force false positives | `surface_status ∈ {strong / moderate / weak / rare / absent / contradictory}` is intentionally the same shape |
| **Per-protein web page with full evidence trail** (NCBI summary, InterPro/Pfam, PDB, motif availability, "has this been tried on PBM / HT-SELEX") | The site, not the table, is what made the resource sticky and citable for 8+ years | v1 web explorer must mirror this: NCBI summary, UniProt/HGNC, PDB chains with TM/EC mapping, "has this been profiled by surface biotinylation / flow / MS surfaceome / IHC," DB-disagreement panel, per-claim citations |
| **Methods-comparison table** (Lambert et al. Fig 1B — PBM, B1H, SELEX-family, ChIP-seq, DamID-seq, EMSA, …) explaining what each assay can/can't resolve | Tells a reader *why* certain evidence is weighted more; doubles as the rubric for adjudication | Ship the equivalent for surface assays: flow cytometry, surface biotinylation, MS surfaceome, IHC, IF, cryo-EM/X-ray, computational. Columns: distinguishes surface from intracellular, permeabilization-dependent, isoform-resolving, quantitative for copy number, topology-resolving. Used both as a figure in the blog and as the weighting rubric the LLM applies. |
| **The "unlikely" category is load-bearing** (982/1,639) | Telling people what to *stop* chasing is as valuable as telling them what to chase | `surface_status=absent` and `contradictory` calls on genes that SURFY/CSPA flag positively (ABCB9, KRAS, mis-flagged solute carriers) are the headline, not a footnote |
| **Stable URL + persistent resource** | humantfs.ccbr.utoronto.ca is still live 8 years on; that's why it's still cited | Plan a permanent URL and DOI-citable per-release snapshots from day one — not a v1 concern |

### Where we deliberately diverge

- **Adjudication mechanism.** Lambert et al. used two human experts. We use Sonnet 4.6 extraction + a Sonnet entailment audit + an Opus 4.7 arbiter on the cascade, with human (Becca) adjudication confined to the n=100 DB-disagreement spotlight and the n=300 stratified citation audit. This swap is the single biggest methodological difference and must be argued for explicitly in the blog: the audit gates (≥95% citation fidelity with Wilson 95% LCB ≥92%, ≥97% claim-entailment on primary evidence) are what earn us the right to make the analogy.
- **Two orthogonal output fields, not one.** Lambert et al. shipped a single graded TF call. We ship `surface_status` *and* `topology` separately, because conflating them is exactly the SURFY failure mode (`KRAS` is membrane-anchored but not surface-accessible). The per-gene record carries both, and the disagreement analysis reports both.
- **Per-claim citations are first-class, not a supplementary table.** Lambert et al. cited the source DBs and key papers; we attach a verbatim quote + char offset + content hash to every claim, which is the layer SURFY/CSPA/UniProt don't have.

### What this gets us

If we ship v0 with the same methodological rigor — graded calls, two-judge + arbiter structure, published methods rubric, per-gene evidence pages, open code, stable URL, audited fidelity — we're positioned to become the cited canonical human surface proteome the way Lambert et al. became the cited canonical human TF list. The blog post should make this analogy explicit.

---

## M0 — Pre-work before M1 (~1 week)

Codex review flagged several issues that must be resolved **before** gene-universe assembly begins. None are optional.

1. **Alias-disambiguation strategy.** Query construction must resolve symbol collisions before retrieval runs. Rule: **UniProt primary accession is the canonical query key**; HGNC symbol + aliases are secondary filter terms only. For symbols that collide with common-word English (`CAT`, `TF`, `P53`, `BAD`, `TH`, `MAX`, `REST`, `FAT`, `TANK`), retrieval uses the accession + protein name combination, never the bare symbol. Validation: run test queries on a collision panel of 20 such symbols and confirm top-25 results are dominated by on-target hits. If <80% on-target at pilot, retrieval strategy has to be revised before M1.
2. **Opus 4.7 pricing verification.** Rates used in this plan ($15/M input, $75/M output) are estimates. Before committing M5's full-run spend, pull the live Anthropic rate card and recompute if delta >10%. The `$0.718/gene` Opus-heavy estimate is the most sensitive; a 2x pricing miss moves the all-in budget by ~$700.
3. **Batch API availability.** Confirm Sonnet 4.6 and Opus 4.7 are supported via Anthropic Batch API (asynchronous, 50% discount). Not all models are batch-eligible at all times. If eligible, batch is the default execution mode for the full run — this project is textbook batch work (latency-insensitive, high volume, structured outputs).
4. **Licensing & redistribution review.** Before publishing any cached corpus:
   - **Unpaywall / OA full text**: verify OA-license scope per source; some CC-BY-NC papers can't be redistributed.
   - **HPA**: Human Protein Atlas is CC-BY-4.0 (see https://www.proteinatlas.org/about/licence); commercial redistribution of derived tables requires attribution.
   - **Serper / Google results**: web-search snippets cannot be redistributed as a corpus. Use only as an internal retrieval signal; do not ship cached Serper payloads.
   - **PubMed abstracts**: NCBI permits redistribution with attribution; confirm for the specific use case.
   - **HGNC / UniProt / GO**: all CC-BY-4.0; clear.

   Deliverable: a short `LICENSING.md` at M6 that states per-source policy and which cached artifacts ship vs which are retained locally only. Start the legal conversation at M0 to avoid blocking at M6.
5. **Anthropic sync checkpoint scheduling.** Confirm monthly cadence. First sync should land at end of M3 (quality review on ~60-gene control set, before scaling).

---

## Gene universe

Target: **~8,000–10,000 candidate genes** — union of DB annotations + ML-flagged edge cases. Candidates are filtered (not classified) at this stage; LLM pipeline runs on all survivors.

### Posture: recall-first assembly

M1's job is to produce a **comprehensive union** of every protein that might plausibly be a human cell-surface target. The guiding rule for every per-source filter in this section is:

> *Include on any credible evidence; defer precision to M3–M5.*

Concretely:

- A protein enters the universe if **any one** source flags it under its own rule. Per-source rules are permissive by design.
- Per-source filters that appear "tightening" (the UniProt query, the GO evidence-code rule, the lone-organelle filter in step 7) are **targeted, not restrictive** — they sharpen what each source contributes, but the escape valve is always "include if any other source flags it." None of them reduce the universe to the intersection.
- Disagreement among sources is a *feature*: it is the signal the downstream LLM reconciliation pipeline (M3–M5) is designed to consume. Precision work — deciding whether a specific gene is a high-confidence therapeutic-delivery target — happens per-gene under the LLM, not here.
- False **negatives** at M1 (real surface proteins missing from the universe) are the costly error mode, because the downstream pipeline never sees them. False **positives** (non-surface proteins with one source's vote) are cheap — the LLM reads every source's evidence per gene and decides.

Read every "excluded," "filtered," or "tightened" phrase below in that light: the practical effect on universe membership is additive across sources, not subtractive.

**Assembly steps** (all pre-LLM, one-time):

1. **SURFY** — ingest current snapshot into `surfy_surfaceome_snapshot_rows` (pattern: [packages/schemas/src/drizzle/reference/surfy.ts](packages/schemas/src/drizzle/reference/surfy.ts)).
2. **CSPA** — download Wollscheid lab Table S3; normalize to UniProt + HGNC.
3. **UniProt** — **targeted-but-permissive query** that pulls plasma-membrane and extracellular-topology entries without demanding UniProt be the primary compartment call:
   ```
   organism_id:9606 AND reviewed:true AND (
     cc_scl_term_exact:"Cell membrane"
     OR cc_scl_term_exact:"Cell surface"
     OR cc_scl_term_exact:"Apical cell membrane"
     OR cc_scl_term_exact:"Basolateral cell membrane"
     OR cc_scl_term_exact:"GPI-anchor"
     OR ft_topo_dom:Extracellular
   )
   ```
   **Lone-organelle carve-out (union-preserving)**: proteins whose *only* UniProt subcellular-location call is an internal compartment — `Mitochondrion*`, `Nucleus*`, `Endoplasmic reticulum*`, `Golgi*`, `Lysosome*`, `Peroxisome*`, `Endosome*` — don't get a UniProt vote on their own, but they **remain in the universe** if any other DB or ML source flags them. This is a per-source permissiveness knob, not a universe-level exclusion. Evidence code filters: prefer `ECO:0000269` (experimental) and `ECO:0000314` (IDA) entries; flag `ECO:0000250` (by similarity) as lower-confidence but retain the vote.
4. **GO** — annotations for `GO:0009986` (cell surface), `GO:0009897` (external side of plasma membrane), and `GO:0005887` (integral component of plasma membrane), plus descendants via `is_a` + `part_of` closure. **Evidence rule (recall-preserving):** any non-`IEA` annotation to an included term counts as a GO vote — this covers experimental codes (`EXP|IDA|IPI|IMP|IGI|IEP|HDA|HMP|HEP|HTP|HGI|HMP`), curated/phylogenetic codes (`TAS|NAS|IC|IBA|IBD|IKR|IRD`), and sequence-based inference codes (`ISS|ISO|ISA|ISM|IGC|RCA`). Pure-`IEA` (electronic-only, un-curator-reviewed) rows are retained for provenance with a low-confidence flag but do **not** gate the GO vote. Rationale: requiring experimental-only evidence was considered and rejected as too aggressive for a recall-first step — it drops genuine surface proteins whose only non-IEA evidence is curated or orthology-based. The per-row evidence tier is carried through so the downstream LLM can down-weight weak-evidence votes without them causing missing proteins. *Note: `GO:0005886` (plasma membrane — too broad) and `GO:0031225` (obsolete in current GO) were previously in this set and have been dropped; the molecular-function terms `GO:0038023` and `GO:0004888` were also removed because they annotate receptor activity regardless of location (admits endosomal TLRs). See M1 accuracy critique resolution 2026-04-18.*
5. **ML edge cases** — run **DeepTMHMM** (primary) + **SignalP 6.0** + **PredGPI** across canonical UniProt isoforms for human reviewed entries. Union anything predicted to have (a) signal peptide + ≥1 TM helix, or (b) GPI signal, that isn't already in steps 1–4.

   **v0 scope (2026-04-16)**: M1 uses only the pre-existing DeepTMHMM run
   (2,360 unique human base accessions; 22.8% coverage of the 10,343-protein
   DB union). SignalP 6.0 and PredGPI are **deferred** for v0. Future work:
   extend DeepTMHMM to the full human reviewed proteome (~20,400 entries) so
   that ML-only edge cases — proteins with no DB evidence but predicted SP+TM
   or GPI — can actually enter the candidate universe. See
   `data/processed/deeptmhmm/deeptmhmm_build_summary.json` for current
   coverage.
6. **Negative controls** — explicit panel of known non-surface-accessible proteins wrongly annotated by at least one DB (`ABCB9`, `KRAS`, mitochondrial solute carriers mis-flagged in SURFY, nuclear receptors with TM-domain-like sequence). Target: 30 negative controls, each validated against primary literature before inclusion.
7. **Lone-organelle-lumen filter (union-preserving)** — proteins whose *only* annotation is an organelle-lumen UniProt subcellular-location call (no other DB or ML vote) are not admitted by UniProt alone. The `unless flagged by another DB or ML` escape valve is the rule, not the exception — this is a per-source permissiveness knob, not a universe-level drop. Counts of proteins admitted only via this escape are emitted to the M1 summary for auditability.

**Output**: `candidates.parquet` with columns:
```
hgnc_id, approved_symbol, previous_symbols, aliases,
uniprot_primary, uniprot_secondary, ensembl_gene_id, ensembl_canonical_transcript,
canonical_isoform_uniprot, isoform_count, isoform_flattened,
surfy_flag, cspa_flag, uniprot_subcell_terms, go_annotations,
ml_signal_peptide, ml_tm_count, ml_gpi, ml_tool_versions,
is_negative_control, is_positive_control, exclusion_reasons,
expected_db_disagreement
```

Reuse gene-ID normalization pattern from [packages/schemas/src/drizzle/reference/gene-resolutions.ts](packages/schemas/src/drizzle/reference/gene-resolutions.ts).

---

## Architecture

All code under new `analyses/surface-proteome/` as a standalone `uv` project. Pipeline runs independently (no Inngest / BFF / DB-RLS overhead).

```
analyses/surface-proteome/
  pyproject.toml                    # uv project: pydantic-ai, httpx, polars, sqlite-utils
  src/surface_proteome/ <!-- legacy path; not in current layout -->
    candidates/                     # M1 — gene universe
      build_surfy.py
      build_cspa.py
      build_uniprot.py              # tightened query (see Gene universe §3)
      build_go.py                   # evidence-code filtering
      build_ml_predictions.py       # DeepTMHMM + SignalP + PredGPI
      build_controls.py             # pos/neg control curation
      merge.py                      # → candidates.parquet
    retrieval/
      aliases.py                    # M0-validated disambiguation logic
      uniprot_pubs.py               # curator-tagged topic-filtered PMIDs
      europe_pmc.py                 # primary search + text-mining
      pubmed.py                     # MeSH-precision backup
      openalex.py                   # citation-graph + preprint tail
      unpaywall.py                  # DOI → OA fulltext resolver
      hpa.py                        # Human Protein Atlas pages → Evidence
      pdb.py                        # PDB structural evidence (NEW)
      retraction_check.py           # Retraction Watch + PubMed retracted status
      serper.py                     # web-search fallback (<5% genes)
      rank.py                       # adaptive top-K with priority tiers
      cache.py                      # SQLite-backed content store (sha256-keyed, TTL per source)
    agents/
      evidence_extractor.py         # Sonnet 4.6 — per-abstract/fulltext structured extraction
      gene_synthesizer.py           # Sonnet 4.6 — per-gene classification + topology
      claim_entailment.py           # Sonnet 4.6 — quote→claim entailment audit (NEW)
      edge_case_arbiter.py          # Opus 4.7 — light/heavy cascade paths
      validators.py                 # deterministic: source_id ∈ batch, quote substring (normalized), hash, entailment gate
      prompts/
        *.md                        # versioned system prompts
    schemas.py                      # Pydantic: SourceRef, EvidenceSpan, Evidence, GeneAnnotation
    pipeline/
      run_gene.py                   # single-gene workflow (idempotent)
      orchestrator.py               # async fan-out with bounded concurrency
      batch_runner.py               # Anthropic Batch API driver (50% discount path)
      checkpoint.py                 # resume-from-failure via per-gene JSONL
      cascade.py                    # Opus-routing decision logic
    cli.py                          # accessible-surfaceome {build,run,analyze,export,audit}
    reports/
      disagreement.py               # DB vs ours discrepancy tables
      blog_figures.py               # Plotly/matplotlib figures
      audit.py                      # stratified citation-integrity + entailment sampler (n=300)
  data/
    raw/                            # DB snapshots, gitignored
    candidates.parquet
    corpus/{gene}/
      sources.jsonl                 # every SourceRef seen
      raw/{source_id}.json          # cached API response (respecting per-source license policy)
    annotations/{gene}.json         # GeneAnnotation + Evidence[]
    audit/{gene}.jsonl              # retrieval → extraction → synthesis trace
    exports/                        # public CSV + parquet for blog
  LICENSING.md                      # per-source redistribution policy (M0 → M6)
  notebooks/                        # exploratory EDA
  README.md
```

**Why standalone, not integrated.** Open-source analysis, not a Coral product feature. Keeping it independent: (a) clean blog-post repo pointer, (b) no RLS / Inngest coupling, (c) Becca's team can run it without spinning up the full monorepo. Reuse *patterns* from `apps/workers/src/lib/retrieval/` and `apps/bff/src/bff/agents/`.

---

## Retrieval strategy

### Source cascade (per gene)

Nine sources. **Overlap is expected and desired** (triangulation); dedup is handled downstream by DOI→PMID→title-hash canonicalization. Each source earns its slot because of a unique coverage property, not because it's exclusive.

| # | Source | Role | Unique value | Typical hits/gene |
|---|---|---|---|---|
| 1 | **UniProt publications cross-ref** | Curator-pre-tagged baseline | Topic-tagged PMIDs (`subcellular location`, `topology`, `PTM`); zero-LLM curated prior | 5–50 |
| 2 | **Europe PMC** | Primary search engine | Superset of PubMed + PMC full-text + bioRxiv/medRxiv; text-mining entity annotations | 100–500 raw |
| 3 | **PubMed E-utils** | MeSH-precision backup | MeSH heading queries; authoritative retraction/PMID source | fills gaps |
| 4 | **OpenAlex** | Citation graph + preprint tail | Citation-count signal, concept expansion, chapters/preprints EPMC misses | tiebreaker |
| 5 | **Unpaywall** | OA full-text resolver | DOI → OA PDF/XML, invoked selectively for tier-B papers | ~1–2 |
| 6 | **Human Protein Atlas** | Curated antibody-validated evidence | Per-protein IHC + subcellular localization with antibody IDs | 1 page/gene |
| 7 | **PDB (NEW)** | Structural evidence for topology | Direct experimental structural evidence of extracellular/TM/inner-leaflet domains; first-class for topology calls, not secondary | 0–5 per gene |
| 8 | **Retraction Watch DB** | Negative filter | Cross-ref cited PMIDs for retracted status | — |
| 9 | **Serper (web search)** | Last-resort fallback | When cascade returns <5 candidates; **not redistributed** per licensing | <5% genes |

**PDB integration**: `pdb.py` queries for PDB entries citing the UniProt accession; for each entry, extract (a) method (X-ray / cryo-EM / NMR), (b) SEQRES regions matching signal-peptide / TM / extracellular / cytoplasmic annotations, (c) resolution. Emit `Evidence` records with `evidence_type=crystal_structure` and `source_type=pdb`, `source_id=PDB:xxxx`. Structural topology evidence outranks abstract-level topology claims in synthesis confidence.

Deliberately **not** using Google Scholar (no official API; scraping fragile; Europe PMC covers ~95% of Scholar's biomedical corpus).

### Query construction per gene

Built from **disambiguated identifiers** (per M0 validation) + topic anchors:

- **Primary key**: UniProt primary accession (always) + canonical protein name
- **Secondary terms**: HGNC approved symbol, previous symbols, Ensembl gene ID
- **Alias handling**: aliases added as filter terms, never as primary; colliding-symbol panel (`CAT`, `TF`, `P53`, etc.) uses accession + protein name only
- **Topic anchors**: `"cell surface" OR "plasma membrane" OR "surface expression" OR "surface biotinylation" OR "flow cytometry" OR "surfaceome" OR "transmembrane topology" OR "extracellular domain" OR "GPI-anchor" OR "immunohistochemistry"`
- **MeSH anchors** (PubMed only): `Cell Membrane[MeSH]`, `Membrane Proteins[MeSH]`, `Protein Transport[MeSH]`, `Flow Cytometry[MeSH]`

### Adaptive top-K selection

- **Cap**: 25 abstracts per gene (marginal returns drop after ~20)
- **Floor**: take all candidates if fewer than 25
- **Priority ordering**:
  1. UniProt-curator-tagged references (up to 10)
  2. PDB structural entries (up to 3 extra slots, not counted against 25 cap — topology is v0-critical)
  3. Method-keyword hits in title/abstract (flow cytometry, surface biotinylation, MS surfaceome, IHC, etc.)
  4. Review articles (PubMed `Publication Type = Review`)
  5. Citation-count (OpenAlex) tiebreaker
  6. Recency (last 10 years) 1.5× boost
  7. Retraction filter (drop outright)

Average after dedup lands near **~22 abstracts + ~1.5 PDB entries** per gene.

### Full-text policy (three tiers)

| Tier | Trigger | Content pulled | Avg per gene |
|---|---|---|---|
| **A — Abstract-only** | Default for every retrieved paper | Title + abstract (~400 tok) | ~22 |
| **B — Methods + results excerpt** | Abstract mentions surface method keyword AND tier-1 ranked AND abstract is ambiguous AND OA available | Methods + figure legends + results captions (~7.5k tok) | ~1.5 |
| **C — Full paper** | Opus HEAVY path only — evidence contradictory after tier-B review | Full sections excluding references (~20k tok) | ~2–3 × 10% of genes |

### Rate limits & throughput (honest numbers)

| API | Limit | Strategy |
|---|---|---|
| NCBI E-utils | 10 qps with API key | Shared `asyncio.Semaphore` |
| Europe PMC | ~10 qps (self-throttle to 8) | Primary |
| OpenAlex | 100k/day, 10 qps polite pool | Email in User-Agent |
| UniProt REST | 200 concurrent conn | Non-blocking |
| Unpaywall | ~100k/day | ~13.5k calls — fine |
| PDB | ~100 qps | Non-blocking |
| Serper | Plan quota | Fallback only, <5% of genes |

**Throughput correction**: earlier draft claimed "10–20 s/gene" and "~3–4 h for 9k genes" — those are inconsistent. Honest numbers:

- Per-gene wall-clock: ~15–30 s retrieval + ~5–10 s LLM (synchronous mode) = **~25–40 s/gene**
- At concurrency=32 sequentially: 9000 × 30 / 32 = **~2.3 h** retrieval-bound
- **With Batch API** (recommended): retrieval runs synchronously (~2.3 h), LLM extraction + synthesis submitted as batches, results ready in **~6–24 h total** (Anthropic Batch SLA is <24 h). Lower cost, slightly longer wall-clock.
- Opus cascade adds ~10–20 min synchronously or another batch turnaround if batched.

---

## Provenance & anti-hallucination

Every claim traces back to a specific span of a specific source at a specific retrieval timestamp, with content hashing so later audits are deterministic.

### Pydantic schemas (revised)

```python
class SourceRef(BaseModel):
    source_type: Literal["pubmed", "pmc", "europe_pmc", "openalex",
                         "uniprot", "biorxiv", "medrxiv", "hpa", "pdb", "web"]
    source_id: str                   # "PMID:12345678" / "DOI:10.xx/yy" / "UniProt:P12345" / "PDB:2ABC"
    pmc_id: str | None               # separate tracking for PubMed↔PMC linkage
    url: HttpUrl
    title: str
    retrieved_at: datetime
    content_sha256: str              # hash of fetched text at retrieval
    publication_type: Literal["primary_research", "review", "preprint",
                              "meta_analysis", "db_entry", "structure", "other"]
    is_retracted: bool
    retraction_checked_at: datetime  # TTL-bounded; rechecked at publish-time
    license: Literal["cc_by", "cc_by_nc", "cc_by_sa", "cc0", "closed", "unknown"]

class EvidenceSpan(BaseModel):
    source: SourceRef
    section: Literal["title", "abstract", "introduction", "results",
                     "discussion", "methods", "figure_legend", "table",
                     "structure_header", "other"]
    figure_or_table_id: str | None   # "Figure 3A", "Table S1", "Chain A"
    quote: str                       # ≤ 200 chars, ALWAYS verbatim
    quote_sha256: str                # tamper-detection
    char_offset: int                 # position in source; REQUIRED (no None) — if derived, record is rejected
    normalized_source_sha256: str    # hash of the normalized form used for substring check

class AssayContext(BaseModel):
    species: Literal["human", "mouse", "rat", "macaque", "dog", "other", "unspecified"]
    cell_type_or_line: str | None    # free text; "B cell", "HEK293", "primary hepatocyte", etc.
    permeabilized: bool | None       # critical: non-permeabilized = surface; permeabilized = ambiguous
    fixation: Literal["live", "fixed", "unspecified"] | None
    isoform: str | None              # UniProt isoform ID if specified

class Evidence(BaseModel):
    claim: str
    claim_type: Literal["surface_expression", "topology",
                        "tissue_expression", "methodological", "contradictory"]
    direction: Literal["supports", "refutes", "ambiguous"]
    evidence_type: Literal["flow_cytometry", "surface_biotinylation",
                           "mass_spec_surfaceome", "immunohistochemistry",
                           "immunofluorescence", "crystal_structure",
                           "cryo_em", "computational_prediction", "orthology",
                           "review_assertion", "db_annotation"]
    evidence_tier: Literal["primary", "secondary"]  # primary = experimental;
                                                    # secondary = review/db
    confidence: Literal["strong", "moderate", "weak"]
    assay_context: AssayContext
    spans: list[EvidenceSpan]        # ≥1
    entailment_verified: bool        # set by claim_entailment.py audit

class GeneAnnotation(BaseModel):
    gene: GeneIdentifier
    canonical_isoform: str           # UniProt isoform used
    isoform_flattened: bool          # flagged if gene has >1 reviewed isoform
    surface_status: SurfaceStatus    # orthogonal to topology
    topology: Topology               # orthogonal to surface_status
    confidence: Literal["high", "medium", "low"]
    confidence_reasoning: str        # required text explaining the confidence
    contradiction_flag: bool
    primary_evidence_count: int      # excludes review_assertion + db_annotation
    secondary_evidence_count: int
    evidence_count: int              # total
    db_comparison: DBComparison      # SURFY / CSPA / UniProt / GO side-by-side
    cited_evidence_ids: list[str]    # references into Evidence[] by quote_sha256
    rationale: str                   # ≤ 500 chars
    model_path: Literal["sonnet_only", "opus_light", "opus_heavy"]
```

### Anti-hallucination safeguards (deterministic checks + one probabilistic gate)

Codex review correctly flagged that earlier framing ("deterministic, not probabilistic") was overstated. Revised layered defenses:

**Deterministic Python checks (no LLM involvement):**

1. **Batch-level source_id binding**: Extractor sees batch of 8 abstracts, each tagged `[SOURCE: PMID:xxxxxx]`. Validator rejects any Evidence citing an out-of-batch `source_id`. Zero tolerance; one retry, then discard.
2. **Quote substring check with full normalization protocol**:
   - Unicode NFKC normalization
   - Greek-letter transliteration (α→alpha, β→beta, etc.) both directions
   - HTML entity decoding (`&amp;`, `&lt;`, etc.)
   - Whitespace collapse (runs of \s → single space)
   - Smart-quote → ASCII quote normalization
   - Zero-width character removal
   - Line-wrap hyphen repair (common in PDF extraction)
   - `str.find` on normalized source with normalized quote
   - Failure modes documented: `quote_match_failed` + raw vs normalized diff stored for audit
3. **`char_offset` is required, not optional** — any Evidence record missing it is rejected. Prevents paraphrased "evidence" from sneaking through.
4. **SHA-256 hashes** on source content + quote + normalized-source form; any mismatch at audit time triggers re-extraction.
5. **Retraction cross-ref** with 24h TTL; full rescan before publish.
6. **HPA flows through the same validator path as abstracts** — HPA pages are parsed into SourceRef + EvidenceSpan + Evidence with quote substrings from the page text. No HPA-specific bypass. Pre-formatted evidence (curator-assigned reliability scores) is still validated against the raw HPA page content.

**Probabilistic gate (one LLM call, audit-grade):**

7. **Claim-entailment audit** (`claim_entailment.py`): For every Evidence record, a second Sonnet 4.6 call takes `(quote, claim, direction)` and returns `entailed: bool` + `reasoning: str`. This catches:
   - Correct PMID + correct quote substring + **mis-represented claim direction** (e.g. quote says "did not detect surface" but Evidence says `direction=supports`).
   - Paraphrased-into-false-conclusion.
   - Cherry-picked supporting phrases with ignored qualifying context.

   Runs on **100% of primary evidence**, sample of 25% of secondary evidence. ~1k tokens per call × ~50k evidence records × $0.015/call = ~$750 (added to cost model).

**Synthesis-confidence upper bound (deterministic rule):**

8. Gene synthesis confidence is capped: `min(synthesis_confidence, max_evidence_confidence)`. If no Evidence has `confidence=strong`, synthesis cannot emit `confidence=high`. If >50% of evidence is `evidence_tier=secondary`, synthesis max confidence is `medium`. Prevents over-generalization from weak literature.

### Secondary-evidence policy

Reviews and database annotations (`review_assertion`, `db_annotation`) are first-class Evidence records but **tiered secondary**. A gene annotated as `strong_surface` with 100% secondary evidence is structurally impossible under rule 8 above. The per-gene output reports `primary_evidence_count` and `secondary_evidence_count` separately, so consumers can filter. Blog-post summary table will include a "primary-evidence %" column.

### On-disk bundle per gene (public-shippable, subject to LICENSING.md)

```
data/corpus/{gene}/
  sources.jsonl          # every SourceRef seen (seen set)
  raw/{source_id}.json   # cached response — only for redistributable licenses (not Serper)
data/annotations/{gene}.json       # GeneAnnotation + Evidence[]
data/audit/{gene}.jsonl            # retrieval → extraction → synthesis trace + entailment results
```

**Seen set vs cited set preserved separately** — lets reviewers detect selection bias and lets us swap extraction prompts without re-fetching.

---

## Agentic workflow (per gene)

```
                       ┌──────────────────────────┐
                       │  candidates.parquet row  │
                       └────────────┬─────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
 UniProt pubs + HPA           Europe PMC + PubMed         OpenAlex + Unpaywall + PDB
 (curator-tagged)             (search + rank)             (citation graph + structures)
       │                            │                            │
       └────────────────────────────┴────────────────────────────┘
                                    │
                                    ▼
                    ┌────────────────────────────────┐
                    │ adaptive top-K (~22 + PDB)     │
                    │ alias-disambiguated queries    │
                    │ retraction filter              │
                    │ sources.jsonl persisted        │
                    └──────────────┬─────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────────┐
                    │ evidence_extractor (Sonnet)    │  ← 3 batches × 8 abstracts
                    │ output_type = list[Evidence]   │    cached prefix (sys + gene hdr)
                    └──────────────┬─────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────────┐
                    │ deterministic validators       │  ← source_id ∈ batch?
                    │ (Python, not LLM)              │    quote substring (normalized)?
                    │                                │    char_offset present?
                    │                                │    retraction check?
                    └──────────────┬─────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────────┐
                    │ claim_entailment (Sonnet)      │  ← quote ⊨ claim?
                    │ 100% primary, 25% secondary    │    direction consistent?
                    └──────────────┬─────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────────┐
                    │ gene_synthesizer (Sonnet)      │
                    │ input: validated Evidence[]    │
                    │ output: GeneAnnotation         │
                    │ confidence cap rule applied    │
                    └──────────────┬─────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────────┐
                    │  cascade decision (Python)     │
                    └─┬──────────────────────────┬───┘
                      │ high-conf path           │ uncertain path
                      ▼                          ▼
                 persist + done          Opus LIGHT (re-synthesize)
                                                  │
                                                  ▼
                                          cascade decision
                                          ┌───────┴────────┐
                                          ▼                ▼
                                     persist + done   Opus HEAVY
                                                      (fetch 2–3 full
                                                       papers, re-extract
                                                       methods, re-synth)
                                                             │
                                                             ▼
                                                      persist + done
```

### Opus cascade — triggers (expanded; Codex flagged 10% as likely undercount)

**Route to Opus LIGHT** (re-synthesize with same Evidence records, no new retrieval):
- `confidence ∈ {medium, low}` **AND** DB disagreement (≥2 of SURFY/CSPA/UniProt/GO disagree with Sonnet's call), **OR**
- `contradiction_flag == True`, **OR**
- `primary_evidence_count < 3` **AND** DB annotations disagree, **OR**
- Negative-control panel (always — QC gate), **OR**
- Claim-entailment audit flagged ≥2 failed entailments on cited evidence

**Escalate to Opus HEAVY** (fetch 2–3 OA full papers via Unpaywall, re-extract methods+results, re-synthesize):
- Opus light emitted `confidence < high` OR `contradiction_flag == True`, **OR**
- `primary_evidence_count == 0` (dark gene or all-review annotation), **OR**
- DB disagreement AND no PDB structural evidence available

**Expected distribution (base scenario, revised up from 30% to 40% per Codex critique):**
- 60% → Sonnet only (high-confidence, DB-aligned, primary evidence)
- 30% → Opus light (~2,700 genes)
- 10% → Opus heavy (~900 genes)

---

## Token & cost estimate (recomputed)

### Assumptions (corrected)

- 9,000 candidate genes
- Sonnet 4.6: $3/M input, $15/M output, $3.75/M cache write, $0.30/M cache read
- Opus 4.7: $15/M input (est.), $75/M output (est.), $18.75/M cache write, $1.50/M cache read *(verify at M0)*
- **Batch API**: 50% discount on both input and output for async batch submissions
- Cache structure: two breakpoints per prompt — (1) ~2,500-tok system prompt shared across all calls in the run, (2) ~1,000-tok per-gene header shared across 3 extraction + 1 synthesis + entailment calls for a single gene
- Average 22 abstracts retrieved per gene, 3 extraction batches of ~8 abstracts each
- Evidence-record output: 1.5 records/abstract × 175 tok/record = ~262 tok/abstract; 8 abstracts/batch = **~2.1k output/batch**, **~6.3k output/gene** (Codex correctly flagged the earlier 9k as inconsistent)

### Sonnet per-gene cost (synchronous pricing; Batch API halves these)

| Phase | Non-cached input | Cached input (read) | Output | $ per gene |
|---|---|---|---|---|
| Extraction (3 calls × 8 abstracts) | 9.6k tok | 10.5k tok | 6.3k tok | $0.131 |
| Full-text methods (1.5 papers avg) | 11.25k tok | 5.25k tok | 3k tok | $0.081 |
| Claim-entailment audit (~20 Evidence × 1k tok each, 75% sampled) | 15k tok | 3.5k tok | 1.5k tok | $0.068 |
| Gene synthesis (1 call) | 7k tok | 3.5k tok | 1.5k tok | $0.045 |
| **Sonnet subtotal (synchronous)** | | | | **~$0.325** |

### Opus cascade cost (synchronous pricing)

| Path | Share | Non-cached in | Cached in | Output | $ per gene in path |
|---|---|---|---|---|---|
| Opus light (re-synthesize) | 30% | 7.5k | 3.5k | 3k | $0.343 |
| Opus heavy (+full papers) | 10% | 22.5k | 3.5k | 5k | $0.718 |

### Total projected cost — three scenarios × synchronous vs Batch API

**Synchronous pricing:**

| Scenario | Opus light | Opus heavy | Sonnet cost | Opus cost | Retrieval | Subtotal | +50% buffer | **All-in** |
|---|---|---|---|---|---|---|---|---|
| **Tight** (alias cleanup succeeds, 20% / 5%) | 1,800 | 450 | $2,925 | $940 | $75 | $3,940 | $1,970 | **~$5,910** |
| **Base** (recommended, 30% / 10%) | 2,700 | 900 | $2,925 | $1,572 | $75 | $4,572 | $2,286 | **~$6,860** |
| **Loose** (weak gating, 40% / 15%) | 3,600 | 1,350 | $2,925 | $2,203 | $75 | $5,203 | $2,602 | **~$7,800** |

**With Batch API (50% discount on both Sonnet + Opus):**

| Scenario | Subtotal (batched LLM) | +50% buffer | **All-in (batched)** |
|---|---|---|---|
| **Tight** | $2,008 | $1,004 | **~$3,010** |
| **Base** (recommended) | $2,324 | $1,162 | **~$3,486** |
| **Loose** | $2,639 | $1,320 | **~$3,960** |

**Pilot cost (M3/M4, 100 genes, synchronous): ~$70.** Iterate freely.

**Recommended execution: Batch API for the full 9k-gene run once M3/M4 converge on a stable prompt.** Buys back ~$3.3k on the base scenario.

**Buffer raised from 30% → 50%** per Codex critique. Covers prompt iteration, validator rejection re-runs, Becca's adjudication-driven re-runs, and verification-of-Opus-pricing margin.

### Token totals (base scenario, with Batch API)

**~500M input tokens, ~70M output tokens** across the full run. Within Anthropic API credit grants.

### Why revised higher than v1 ($4,500–$6,500 → $5,900–$7,800 sync / $3,000–$4,000 batched)

1. **Added claim-entailment audit** (~$750): necessary for the stated 95% citation-fidelity gate to be achievable.
2. **Opus cascade raised from 30% → 40%**: Codex is correct that DB-disagreement enrichment of the candidate universe makes uncertainty more common than initially modeled.
3. **Buffer raised from 30% → 50%**: first-pilot unknowns + pricing-verification margin.
4. **Added PDB retrieval + structural Evidence flow**: ~$0 net (PDB API is free; extraction tokens are marginal).

**Net offset**: Batch API (if eligible) cuts the recommended execution path roughly in half. **The budget ask to Anthropic should be framed around the synchronous scenario (~$7k base) to give headroom; actual spend with Batch API will be closer to $3.5k.**

### Cost-lever alternatives (documented, not selected)

**Haiku 4.5 for extraction + Sonnet for synthesis + Opus for edges**: cuts Sonnet extraction from $0.131 → ~$0.045/gene (saves $775 Sonnet path). All-in base with Batch: **~$2,800**. Not selected pending M3 quality review — if Haiku extraction passes citation-integrity audit at ≥95%, switch here for M5.

---

## Validation plan (statistically-powered, per Codex critique)

1. **Negative-control panel** (n=30) — must score `surface_status ∈ {absent, rare_surface}` AND topology consistent with known biology (e.g. KRAS → `inner_leaflet_peripheral`, ABCB9 → `not_pm_associated`). Target: ≥93% correct (28/30). **Regression QC, not publication-grade.**
2. **Positive-control panel** (n=50) — textbook surface proteins (CD19, CD20, EGFR, HER2, PD-L1, CD3ε, GPC3, FOLR1, CD33, CD38, CD138, ITGAX, …). Must score `strong_surface` with correct topology. Target: 100%.
3. **DB-disagreement spotlight** (n=100, up from 30 per Codex) — stratified random sample from genes where ≥2 DBs disagree. Becca adjudicates; compute agreement rate vs expert-ground-truth. **Wilson 95% CI on rate; publish CI in blog post.**
4. **Citation integrity audit** (n=300, up from 50 per Codex) — **stratified** sample: 100 from `confidence=high`, 100 from `medium`, 100 from `low`. For each:
   - (a) PMID/DOI exists in retrieved corpus (deterministic check);
   - (b) quote is verbatim in source (normalized substring, deterministic);
   - (c) quote entails the claim in the stated direction (manual review by Becca or designated reviewer).
   **Target: ≥95% overall fidelity.** At n=300, Wilson 95% lower bound on 95% point estimate is ~92.2% — enough to support the gate claim with honest CI. At ±3% precision (per Codex), this is the right sample size.
5. **Sensitivity analysis** — rerun the pipeline on the positive panel with (a) top-K=15 and (b) top-K=40; measure whether surface_status and topology change. Report robustness in blog.

---

## Milestones (revised; 5–6 weeks realistic)

| # | Milestone | Est. effort |
|---|---|---|
| **M0** | **Pre-work** — alias disambiguation validation (20-gene collision panel, ≥80% on-target), Opus pricing verification, Batch API eligibility confirmed, legal review started on LICENSING.md per-source policy | **~5 days** |
| M1 | **Recall-first candidate universe assembled** (union, not intersection): SURFY + CSPA + UniProt (targeted-but-permissive query) + GO (any non-IEA evidence) + HPA + COMPARTMENTS + ML (DeepTMHMM; SignalP + PredGPI deferred) + 30-gene negative-control panel. Parquet + counts + Venn diagram + recall audit against positive-control panel + sanity-check pass. Precision work deferred to M3–M5 per-gene LLM reconciliation. | 5–7 days |
| M2 | Retrieval layer (9 sources incl PDB) + SQLite cache with per-source TTL + Pydantic schemas + deterministic validators + claim-entailment audit layer + alias-disambiguation per M0 design | 4–5 days |
| M3 | Single-gene pipeline end-to-end on 30 neg + 50 pos controls; prompt iteration (expect 2–3 cycles); **first Anthropic sync checkpoint** with Becca quality review | 4–5 days |
| M4 | 500-gene pilot run (synchronous, for fast iteration); cost sanity-check vs M3 projection; stratified n=50 audit at pilot scale; prompt iteration (expect 1–2 cycles) | 3–5 days |
| M5 | Full ~9k-gene run via Batch API + Opus cascade; mid-run n=100 audit spot-check; **second Anthropic sync** | 2 days compute + 3–4 days review |
| M6 | Full n=300 stratified audit, n=100 disagreement adjudication with Becca, sensitivity analysis, disagreement analysis, blog figures, public repo README, CSV/parquet export, LICENSING.md finalized | 5–7 days |

**Total: ~5–6 weeks** focused work. Monthly Anthropic sync cadence aligned at M3 and M5.

---

## Critical files / patterns to reuse

- **PydanticAI structured-output pattern**: [apps/bff/src/bff/agents/question_generator.py:158](apps/bff/src/bff/agents/question_generator.py:158) — copy the `run_structured_output()` convention and `output_type=` usage.
- **NCBI E-utils throttling + retry**: `apps/workers/src/lib/retrieval/` — port concurrency + exp-backoff to Python (httpx + `asyncio.Semaphore`). Respect `RETRIEVAL_NCBI_MAX_CONCURRENCY`-style env vars.
- **Fan-out with checkpointing**: [apps/workers/src/inngest/question-run.ts:954](apps/workers/src/inngest/question-run.ts:954) — replicate the `mapWithConcurrency` + per-item durability pattern in Python using `asyncio.TaskGroup` + per-gene JSONL checkpoint for resume-from-failure.
- **Gene-ID normalization**: [packages/schemas/src/drizzle/reference/gene-resolutions.ts](packages/schemas/src/drizzle/reference/gene-resolutions.ts) — three-tier status model (`exact` / `normalized_alias` / `ambiguous`).
- **SURFY snapshot ingestion**: [packages/schemas/src/drizzle/reference/surfy.ts](packages/schemas/src/drizzle/reference/surfy.ts) — reuse column set for SURFY layer of `candidates.parquet`.

---

## Verification

**Local dry run (pilot):**
```bash
cd analyses/surface-proteome
uv sync
uv run accessible-surfaceome m0-validate                             # alias disambiguation test
uv run accessible-surfaceome build-candidates                        # → data/candidates.parquet
uv run accessible-surfaceome run --genes CD19,CD20,EGFR,ABCB9,KRAS   # 5-gene smoke test
uv run accessible-surfaceome run --limit 100 --seed 42               # 100-gene pilot
uv run accessible-surfaceome audit --sample 50 --stratified          # citation + entailment audit
uv run accessible-surfaceome analyze pilot                           # QC report
```

**Full run (Batch API path):**
```bash
uv run accessible-surfaceome run --all --batch-api --concurrency 32 --checkpoint
# ... Batch API polls until complete (typically <24 h) ...
uv run accessible-surfaceome audit --sample 300 --stratified          # final audit
uv run accessible-surfaceome export --format csv,parquet --out data/exports/
uv run accessible-surfaceome report blog                              # figures for post
```

**QC gates before declaring v0 done:**
- Negative-control pass rate ≥ 93% (28/30)
- Positive-control pass rate = 100%
- Stratified n=300 audit: overall fidelity ≥ 95% with Wilson 95% LCB ≥ 92%
- Claim-entailment pass rate ≥ 97% on primary evidence
- Cost per gene ≤ $0.45 average including cascade (Batch API, base scenario)
- Wall-clock ≤ 48 h end-to-end (includes Batch SLA)
- LICENSING.md finalized; no corpus artifacts shipped under unresolved licensing

---

## Licensing & redistribution

Per-source policy (finalized at M6, started at M0):

| Source | License | Cached raw shipped? | Notes |
|---|---|---|---|
| SURFY | CC-BY-4.0 | Yes | Attribute original paper |
| CSPA | Publication supplement | Derived only | Cite Bausch-Fluck et al. |
| UniProt | CC-BY-4.0 | Yes | Attribution required |
| GO / QuickGO | CC-BY-4.0 | Yes | Attribution required |
| HGNC | CC-BY-4.0 | Yes | Attribution required |
| PubMed abstracts | NIH permissive | Yes | Attribution + NIH disclaimer |
| Europe PMC OA subset | CC-BY / CC-BY-NC (per article) | **Per-article policy** | Filter NC before shipping |
| PMC OA subset | CC-BY / CC-BY-NC / CC0 | **Per-article policy** | Filter NC before shipping |
| Unpaywall | CC0 metadata | Metadata yes, OA content **per source license** | Must track per-item license |
| bioRxiv / medRxiv | CC-BY / CC-BY-NC / CC-BY-ND | **Per-preprint policy** | Filter before shipping |
| HPA | CC-BY-4.0 | Yes | Attribution required |
| PDB | CC0 | Yes | Cite structures |
| Retraction Watch | CC-BY-SA-4.0 | Derived only | Attribution |
| Serper / Google | Terms of Service | **NO** | Internal use only; never ship |

**Derived results table** (the final annotation CSV/parquet): released under **CC-BY-4.0**. HPA is CC-BY-4.0, so no share-alike encumbrance on HPA-derived columns. Legal review at M6.

---

## Out of scope for v0 (deferred to v1)

- Per-tissue / cell-type surface expression (HPA tissue atlas + scRNA cross-ref)
- Internalization rate / mechanism
- Model-species (mouse / NHP / rat) conservation
- Isoform-level topology resolution
- Interactive web explorer

---

## Open follow-ups (before M1 kickoff)

- **M0 tasks**: alias-disambiguation validation, Opus pricing verification, Batch API eligibility, legal review start.
- **Anthropic engagement**: schedule first sync at end of M3; share this v2 plan in advance.
- **HPA ingest cadence decision**: pull-at-runtime vs one-time bulk ingest. Recommendation: bulk ingest at M2 into SQLite (20k proteins fits easily, refresh quarterly).
- **Open question for Becca**: confirm the 30-gene negative-control panel composition — is `KRAS` the right flagship, or should we also include `HRAS`/`NRAS`/`RRAS` and solute-carrier false positives from SURFY?

---

## References

### Methodological precedent
- Lambert SA, Jolma A, Campitelli LF, Das PK, Yin Y, Albu M, Chen X, Taipale J, Hughes TR, Weirauch MT. *The Human Transcription Factors.* **Cell** 172(4):650–665 (2018-02-08). DOI: [10.1016/j.cell.2018.01.029](https://doi.org/10.1016/j.cell.2018.01.029). Resource: [http://humantfs.ccbr.utoronto.ca/](http://humantfs.ccbr.utoronto.ca/).

### Source databases (M1 candidate universe)
- Bausch-Fluck D, Goldmann U, Müller S, van Oostrum M, Müller M, Schubert OT, Wollscheid B. *The in silico human surfaceome.* **PNAS** 115(46):E10988–E10997 (2018). DOI: [10.1073/pnas.1808790115](https://doi.org/10.1073/pnas.1808790115). [SURFY]
- Bausch-Fluck D, Hofmann A, Bock T, Frei AP, Cerciello F, Jacobs A, Moest H, Omasits U, Gundry RL, Yoon C, Schiess R, Schmidt A, Mirkowska P, Härtlová A, Van Eyk JE, Bourquin J-P, Aebersold R, Boheler KR, Zandstra P, Wollscheid B. *A mass spectrometric-derived cell surface protein atlas.* **PLoS ONE** 10(4):e0121314 (2015). DOI: [10.1371/journal.pone.0121314](https://doi.org/10.1371/journal.pone.0121314). [CSPA]
- The UniProt Consortium. *UniProt: the Universal Protein Knowledgebase in 2023.* **Nucleic Acids Res** 51(D1):D523–D531 (2023). DOI: [10.1093/nar/gkac1052](https://doi.org/10.1093/nar/gkac1052).
- The Gene Ontology Consortium. *The Gene Ontology knowledgebase in 2023.* **Genetics** 224(1):iyad031 (2023). DOI: [10.1093/genetics/iyad031](https://doi.org/10.1093/genetics/iyad031).
- Uhlén M, Fagerberg L, Hallström BM, et al. *Tissue-based map of the human proteome.* **Science** 347(6220):1260419 (2015). DOI: [10.1126/science.1260419](https://doi.org/10.1126/science.1260419). [HPA]
- Berman HM, Westbrook J, Feng Z, Gilliland G, Bhat TN, Weissig H, Shindyalov IN, Bourne PE. *The Protein Data Bank.* **Nucleic Acids Res** 28(1):235–242 (2000). DOI: [10.1093/nar/28.1.235](https://doi.org/10.1093/nar/28.1.235). [PDB]
- Binder JX, Pletscher-Frankild S, Tsafou K, Stolte C, O'Donoghue SI, Schneider R, Jensen LJ. *COMPARTMENTS: unification and visualization of protein subcellular localization evidence.* **Database** 2014:bau012 (2014). DOI: [10.1093/database/bau012](https://doi.org/10.1093/database/bau012).
- Tweedie S, Braschi B, Gray K, Jones TEM, Seal RL, Yates B, Bruford EA. *Genenames.org: the HGNC and VGNC resources in 2021.* **Nucleic Acids Res** 49(D1):D939–D946 (2021). DOI: [10.1093/nar/gkaa980](https://doi.org/10.1093/nar/gkaa980). [HGNC]

### ML topology / signal-peptide / GPI predictors
- Hallgren J, Tsirigos KD, Pedersen MD, Almagro Armenteros JJ, Marcatili P, Nielsen H, Krogh A, Winther O. *DeepTMHMM predicts alpha and beta transmembrane proteins using deep neural networks.* bioRxiv (2022). DOI: [10.1101/2022.04.08.487609](https://doi.org/10.1101/2022.04.08.487609).
- Teufel F, Almagro Armenteros JJ, Johansen AR, Gíslason MH, Pihl SI, Tsirigos KD, Winther O, Brunak S, von Heijne G, Nielsen H. *SignalP 6.0 predicts all five types of signal peptides using protein language models.* **Nat Biotechnol** 40:1023–1025 (2022). DOI: [10.1038/s41587-021-01156-3](https://doi.org/10.1038/s41587-021-01156-3).
- Pierleoni A, Martelli PL, Casadio R. *PredGPI: a GPI-anchor predictor.* **BMC Bioinformatics** 9:392 (2008). DOI: [10.1186/1471-2105-9-392](https://doi.org/10.1186/1471-2105-9-392).

### Retrieval infrastructure
- Levchenko M, Gou Y, Graef F, Hamelers A, Huang Z, Ide-Smith M, et al. *Europe PMC in 2017.* **Nucleic Acids Res** 46(D1):D1254–D1260 (2018). DOI: [10.1093/nar/gkx1005](https://doi.org/10.1093/nar/gkx1005).
- Priem J, Piwowar H, Orr R. *OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts.* arXiv:2205.01833 (2022). [https://arxiv.org/abs/2205.01833](https://arxiv.org/abs/2205.01833).
- Piwowar H, Priem J, Larivière V, Alperin JP, Matthias L, Norlander B, Farley A, West J, Haustein S. *The state of OA: a large-scale analysis of the prevalence and impact of Open Access articles.* **PeerJ** 6:e4375 (2018). DOI: [10.7717/peerj.4375](https://doi.org/10.7717/peerj.4375). [Unpaywall]
- Retraction Watch Database. The Center for Scientific Integrity. [http://retractiondatabase.org/](http://retractiondatabase.org/).

### Therapeutic-modality framing
- Leung D, Wurst JM, Liu T, Martinez RM, Datta-Mannan A, Feng Y. *Antibody Conjugates — Recent Advances and Future Innovations.* **Antibodies** 9(1):2 (2020). DOI: [10.3390/antib9010002](https://doi.org/10.3390/antib9010002).
- MacKay M, Afshinnekoo E, Rub J, Hassan C, Khunte M, Baskaran N, Owens B, Liu L, Roboz GJ, Guzman ML, Melnick AM, Wu S, Mason CE. *The therapeutic landscape for cells engineered with chimeric antigen receptors.* **Nat Biotechnol** 38:233–244 (2020). DOI: [10.1038/s41587-019-0329-2](https://doi.org/10.1038/s41587-019-0329-2). [CAR-T]
