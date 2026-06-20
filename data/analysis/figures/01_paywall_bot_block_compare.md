# Production vs OpenAlex — body-fetch reachability

Two-bar comparison of how literature reachability changes when the v2
deep-dive's production search strategy is swapped for an OpenAlex-backed
retrieval surface with **matched 21-axis parity**. Same 100 random genes
× 10 random papers each for direct comparability.

## What the two strategies are

**Production** — `build_a1_kickoff()` from the deep-dive pipeline.
**21 search calls per gene**:
- 10 EuropePMC method-category searches (`evidence_retrieval` × ihc, IF,
  flow_cytometry, surface_biotinylation, mass_spec_surfaceome, shedding,
  overexpression, western_blot_paired, structure_with_ecd, other)
- 1 NCBI ELink `gene2pubmed` (PMIDs → EuropePMC bulk)
- 1 PubTator `@GENE_<SYMBOL>` date-desc sweep (`recent_corpus`)
- 9 EuropePMC `topic_search` axes (surface_method, structure_topology,
  shedding_ptm + 6 standing axes)

**OpenAlex** — broader retrieval surface via OpenAlex's REST API.
**21 search calls per gene** (1:1 axis mapping to production):
- 1 broad gene-name search (analog of `gene2pubmed`)
- 1 broad gene-name + date-desc sort (analog of `recent_corpus`)
- 10 method-keyword conjunctions (analogs of the 10 EuropePMC
  evidence_retrieval categories)
- 3 topic-keyword conjunctions (surface_method, structure_topology,
  shedding_ptm)
- 6 standing-axis keyword conjunctions (normal_tissue_expression,
  surface_reachability, partner_dependency, membrane_subdomain,
  epitope_masking, cell_state_modulation)

Coverage difference: OpenAlex indexes preprints (bioRxiv, medRxiv,
ChemRxiv, Research Square), non-PubMed journals, and grey literature
that EuropePMC + PubMed don't comprehensively index. At identical 21-axis
parity, OpenAlex surfaces ~3.6× more papers per gene than production
(829 vs 228) — that's the broader recall in action.

## Methodology — same classifier for both

Every paper is run through the **production fetch chain**
(`_fetch_body_drafts` → PMC JATS → Unpaywall PDF → fallback abstract).
When the prod fetch fails, the secondary Unpaywall lookup distinguishes:

| Bucket | Meaning |
|---|---|
| **PMC** | Production fetched the full body via PMC JATS |
| **Unpaywall** | Production fetched via Unpaywall's OA PDF |
| **Bot-blocked** | Unpaywall says is_oa=true, but the only OA paths route through publishers that 403 our polite UA (Wiley, Elsevier ScienceDirect, ASH/Blood, MDPI, OUP/Academic Oxford, bioRxiv, medRxiv, JBC, Cell Press, AHA, JCS, IIAR — empirically HEAD-tested 2026-06-07) |
| **OA repo, DataCite** | The DOI is registered with a non-Crossref agency (DataCite, JaLC, ISTIC) — typically arXiv (`10.48550`), Zenodo (`10.5281`), figshare (`10.6084`), or an institutional thesis repo. Sliced out of the "No OA" pile via the free `doi.org/doiRA` registration-agency endpoint. **Partial fetch-chain coverage:** the production chain now adds a DataCite landing → `<meta name="citation_pdf_url">` step that recovers arXiv + Zenodo (verified end-to-end, 8 drafts each). figshare, HeiDOK, LMU edoc, UNSW Sydney, ESSR, ResearchGate, and similar institutional / society repos still miss because their landing pages don't emit the Highwire `citation_pdf_url` meta tag the resolver scrapes. |
| **No OA** | Unpaywall returns is_oa=false (paywalled) OR has no record, and the DOI is Crossref-registered (so we'd have expected Unpaywall to surface an OA copy if one existed). |

## Headline results

| Strategy | Sample size | Avg pre-sample papers/gene | PMC | Unpaywall | Bot-blocked | OA repo, DataCite | No OA | Reachable (Crossref) | Functionally OA |
|---|---|---|---|---|---|---|---|---|---|
| **Production** (21 axes) | 1,000 papers / 100 genes | 228 | 88% | 0.5% | 0.6% | 0.1% | 10% | **88%** | **89%** |
| **OpenAlex** (21 axes) | 989 papers / 100 genes | 829 | 44% | 4% | 11% | 2.7% | 38% | **48%** | **51%** |

*Reachable (Crossref)* = PMC + Unpaywall (what the original chain fetches).
*Functionally OA* = Reachable + OA repo, DataCite (everything that's
freely available — the DataCite landing-page resolver in
`abstract_triage._fetch_body_via_datacite_landing` now reaches the arXiv
+ Zenodo subset; the rest of the OA-repo bucket sits behind landing
pages that don't emit `citation_pdf_url`).

**The story.** With matched 21-axis search complexity, production
surfaces a smaller pool per gene (~228 papers) but **88% are
reachable**. OpenAlex's broader recall surface returns **3.6× more
papers per gene** (~829) but only **48% are reachable** — the
additional pool is dominated by:
- Preprints whose only OA path bot-blocks (bioRxiv/medRxiv/Research Square)
- Paywalled non-PMC-archived journal articles (Cell/Nature non-OA, Wiley journals)
- Grey literature (conference proceedings, dissertations)
- **OA repository content registered with DataCite** (arXiv, Zenodo,
  figshare, institutional theses) — these are *not* paywalled, they're
  just outside Unpaywall's Crossref-indexed world. The lavender bucket
  carves them out by registration agency; the DataCite landing →
  `citation_pdf_url` resolver fetches the arXiv + Zenodo subset.

**Net reachable papers per gene**: production ~200 (228 × 88%),
OpenAlex ~398 (829 × 48%). OpenAlex genuinely surfaces about 2× the
reachable corpus when measured this way — but with much higher noise
(see next section: most of those additional papers are off-topic).

## Are OpenAlex's incremental "unpaywall" hits useful?

We inspected all 20 OpenAlex-only Unpaywall hits in an earlier
partial run. **~4 of 20 (20%)** were genuinely on-topic to the gene
(TSPAN10 surface biology, PDE6B photoreceptor, TNFRSF4/OX40, TREML2
microglial). **~16 of 20 (80%)** were gene-name-in-passing matches that
production's PubTator NER + topic-focused keywords correctly excluded.

OpenAlex's broader text search returns papers that mention the gene
symbol anywhere in title/abstract — including supplementary gene panels
and incidental mentions. The production search is well-calibrated;
adding OpenAlex would dilute precision more than it adds signal.

## Run

```bash
uv run https://gist.githubusercontent.com/beccajcarlson/cbc950dad1c3a6595fd5018cdb6b030d/raw/make_paywall_bot_block_compare.py
```

PEP 723 inline-deps script reads the per-paper TSV from
`raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/paywall_bot_block/paywall_bot_block_compare.tsv`
(one row per source × gene × paper).

## Data sources

| File | Contents |
|---|---|
| `data/processed/paywall_bot_block/paywall_bot_block_compare.tsv` | Tidy long-form figure input: source × gene × paper × bucket. 1,989 rows. LFS-exempted so raw.githubusercontent.com serves it as text. |
| `probe_results/cohort100x10_production.jsonl` | Per-gene production-strategy probe results (live JSONL, 100/100 genes done) |
| `probe_results/cohort100x10_openalex.jsonl` | Per-gene OpenAlex-strategy probe results, 21-axis run with API key (100/100 genes done) |
| Probe script | `scripts/probe_oa_buckets.py --source {production,openalex} --n-genes 100 --papers-per-gene 10 --workers 8` — resume-capable, JSONL-per-gene incremental writer, 8-wide parallelism |
| Figure script | `scripts/paywall_bot_block_compare.py` — canonical generator |

## Cohort definition

`candidate_universe_v2.tsv` (6,521 genes; Sonnet yes/contextual ∪
≥1 DB-vote). 100 random genes sampled with seed=2024.
