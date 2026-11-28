// Health, gene list, self-describing /v1 index, and /v1/meta/sizes endpoints.

import { CACHE_TTL_SHORT, isMissingTable, json } from "../lib/http.js";
import { cacheEpoch } from "../lib/cache.js";
import { DEFAULT_EXPORT_RUN_ID, EXPORT_COLUMNS, GENOME_RUN_ID } from "./triage.js";

// --- handlers --------------------------------------------------------------

export async function handleHealth(env) {
  // Cheap query to confirm the DB binding works.
  const r = await env.DB.prepare(
    "SELECT count(*) AS n FROM surface_annotation"
  ).first();
  // ``cache_epoch`` is the deploy token every cache key is namespaced by.
  // The publish path reads it from here so it can still construct the exact
  // KV / caches.default keys to purge for a single republished gene — a
  // deploy invalidates everything by changing this, but a republish between
  // deploys still needs targeted eviction.
  return json({
    ok: true,
    n_annotations: r?.n ?? 0,
    cache_epoch: cacheEpoch(env),
  });
}

export async function handleGeneList(env) {
  // Return the latest (schema_version, prompt_corpus_version) row per
  // gene. Until the PK migration runbook in
  // docs/audit/r2_and_reproducibility_2026_06_08.md is executed, the PK
  // is still (gene_symbol, schema_version), so the COALESCE keeps
  // pre-prompt-corpus rows visible at a fallback '0.0.0' label rather
  // than appearing newer than they actually are.
  const rows = await env.DB.prepare(
    `SELECT gene_symbol, uniprot_acc, schema_version,
            COALESCE(prompt_corpus_version, '0.0.0') AS prompt_corpus_version,
            cohort_run_id, confidence,
            triage_signal, surface_status, annotated_at
       FROM surface_annotation
      ORDER BY gene_symbol`
  ).all();
  return json({ count: rows.results.length, genes: rows.results }, { ttl: CACHE_TTL_SHORT });
}

// Verdict (in triage_run_public) → triage_signal (in SurfaceomeRecord).
// MUST stay in sync with the Python side:
//   src/accessible_surfaceome/agents/surfaceome_v1/orchestrator.py
//     ::_TRIAGE_VERDICT_TO_SIGNAL
// Both sides feed the viewer's gene page; a drift here would silently
// recolor the triage chip.

export const V1_ENDPOINTS = [
  { group: "Contact sites", method: "GET", path: "/v1/contact-sites/releases/current", summary: "Current contact release, provenance, audited denominator and exclusions" },
  { group: "Contact sites", method: "GET", path: "/v1/contact-sites/releases/{release}/proteins/{uniprot}", summary: "Version-pinned ligand summaries and representative footprints; scope=extracellular (default) or all" },
  { group: "Contact sites", method: "GET", path: "/v1/contact-sites/releases/{release}/proteins/{uniprot}/ligands/{ligandId}/evidence", summary: "Original observations, paginated with next_cursor; omit ligands/{ligandId}/ to retrieve every observation including unnamed partners" },
  { group: "SurfaceBench", method: "GET", path: "/v1/benchmark", summary: "147 ground-truth labels for the current bench_version" },
  { group: "SurfaceBench", method: "GET", path: "/v1/benchmark/{symbol}", summary: "One gene's ground-truth label + rationale" },
  { group: "SurfaceBench", method: "GET", path: "/v1/benchmark/matrix", summary: "Full bench matrix: truth + 5 per-DB flags + verdicts[model][variant], each the 3-replicate majority" },
  { group: "SurfaceBench", method: "GET", path: "/v1/benchmark/export.tsv", summary: "Long-format TSV of the bench multi-model sweep, one majority row per cell" },
  { group: "Genome-wide", method: "GET", path: "/v1/catalog", summary: "Per-gene 5-DB surface-vote matrix + latest triage verdict + deep-dive flag (~19k genes)" },
  { group: "Genome-wide", method: "GET", path: "/v1/catalog/{symbol}", summary: "One gene's 5-DB surface-vote row (slim; for the per-gene page's DB-presence strip)" },
  { group: "Genome-wide", method: "GET", path: "/v1/triage/{symbol}", summary: "Every triage run for one gene, with the agent's verdict_reasoning" },
  { group: "Genome-wide", method: "GET", path: "/v1/triage/{symbol}/{model}/{variant}", summary: "Per-cell replicate detail + computed majority" },
  {
    group: "Genome-wide", method: "GET", path: "/v1/triage/export.tsv",
    summary: "Long-format TSV of all triage runs for a run_id; per-source DB votes + uniprot_acc joined server-side",
    params: {
      run_id: `default ${DEFAULT_EXPORT_RUN_ID}; pass ${GENOME_RUN_ID} for the full ~19k-gene Sonnet sweep`,
      replicate: "int (optional)",
      with_reasoning: "1 to append predicted_key_uncertainty + verdict_reasoning columns",
    },
  },
  { group: "Deep dive", method: "GET", path: "/v1/health", summary: "Liveness + n_annotations" },
  { group: "Deep dive", method: "GET", path: "/v1/genes", summary: "Index of genes with a deep-dive SurfaceomeRecord" },
  { group: "Deep dive", method: "GET", path: "/v1/genes/{symbol}", summary: "Full SurfaceomeRecord JSON (WITHOUT `evidence` — fetch that from /v1/genes/{symbol}/evidence)" },
  { group: "Deep dive", method: "GET", path: "/v1/genes/{symbol}/evidence", summary: "The gene's evidence ledger (quote+span items) split out of the record: { gene, evidence[], papers{} } — papers carries NCBI citation metadata (title, byline, journal, year) keyed by source_id" },
  { group: "Deep dive", method: "GET", path: "/v1/genes/{symbol}.md", summary: "Rich Markdown export (sequences, DeepTMHMM topology, AlphaFold links) — served from R2" },
  { group: "History", method: "GET", path: "/v1/genes/{symbol}/revisions", summary: "Every archived revision of this gene's served record (newest first), with the releases each belongs to" },
  { group: "History", method: "GET", path: "/v1/genes/{symbol}/revisions/{n}", summary: "Revision n of the record, byte-for-byte as served; also /evidence and .md" },
  { group: "History", method: "GET", path: "/v1/releases", summary: "Numbered data releases with their GitHub tag and Zenodo version DOI" },
  { group: "History", method: "GET", path: "/v1/releases/{version}", summary: "One release: metadata + the revision of every gene in it" },
  { group: "History", method: "GET", path: "/v1/releases/{version}/genes/{symbol}", summary: "A gene as it was in that release; also /evidence and .md" },
  { group: "Reproducibility", method: "GET", path: "/v1/replicates", summary: "Reproducibility replicates (NOT published records): each study with its replicate kinds and genes — e.g. deep_dive_concordance_v1, the 50-gene run-to-run study behind Supplementary Figure 16" },
  { group: "Reproducibility", method: "GET", path: "/v1/genes/{symbol}/replicates", summary: "The reproducibility replicates held for one gene (404 if none), with links to each" },
  { group: "Reproducibility", method: "GET", path: "/v1/genes/{symbol}/replicates/{study}/{kind}", summary: "One replicate SurfaceomeRecord in full (evidence included), wrapped with reproducibility_replicate: true; kind ∈ published_snapshot · full_rerun · fixed_evidence_replay" },
  { group: "Deep dive", method: "GET", path: "/v1/orthologs/{symbol}", summary: "Mouse + cyno orthologs from the latest Ensembl Compara release" },
  { group: "Internalization", method: "GET", path: "/v1/internalization/{symbol}", summary: "Full InternalizationRecord (schema 0.3.0): primary PMID/DOI-anchored literature track (per-mode basal/native_ligand/therapeutic/pathogen_entry grades, structured kinetics, verbatim quotes + joined papers) and secondary sequence-prior track; null outside cohort. Catalog rows carry `intern_lit_grade` (literature), `intern_lit`, `intl` (literature facets), and `intern` (sequence prior)" },
  { group: "Tag sites", method: "GET", path: "/v1/tag-sites/{symbol}", summary: "TaggedSitesFile: engineered epitope/tag insertion points (deterministic loop/disorder/terminal + literature-validated); empty-but-200 when the gene has none. isoform_pins ship static-only." },
  { group: "Tag sites", method: "GET", path: "/v1/l1-design/{symbol}", summary: "Deliverome L1 library design per member: rung, tag sites (current picks + alternatives; built / decided_not_built / no_tag / pending / alternative, with rationale, rejected alternative, source PR + commit and decided_by / implemented_by / reason), structures (native model per the payload, plus tagged-construct refolds) and contact sites (literature-agent and UniProt). Newest complete load; `load: null` when none is loaded." },
  { group: "Tag sites", method: "GET", path: "/v1/l1-design", summary: "Every L1 member in the newest load, one compact row each: rung, rule-based membrane class and the status of its current pick(s)" },
  { group: "Tag sites", method: "GET", path: "/v1/l1-design/{symbol}/{load_version}", summary: "The same, pinned to one content-addressed load (l1d-<16 hex>)" },
  { group: "Utility", method: "GET", path: "/v1/meta/sizes", summary: "Approximate per-endpoint response sizes, computed live from D1" },
  { group: "Utility", method: "GET", path: "/v1", summary: "This index" },
];

// Self-describing API index (HATEOAS-lite). Served at `/v1` and at the
// bare service root so an agent can discover every endpoint + the docs,
// the downloadable skill, llms.txt, the record schema, and the live
// dataset versions in one request. Version lookups are wrapped so a cold
// DB still returns the static catalog.
export async function handleV1Index(env) {
  let versions = null;
  try {
    const ann = await env.DB.prepare("SELECT COUNT(*) AS n FROM surface_annotation").first();
    const bench = await env.DB.prepare(
      `SELECT bench_version FROM benchmark_version
        WHERE truth_verdict IS NOT NULL AND truth_verdict != ''
        GROUP BY bench_version ORDER BY COUNT(*) DESC, MAX(created_at) DESC LIMIT 1`
    ).first();
    const uni = await env.DB.prepare(
      "SELECT universe_version FROM candidate_universe_release ORDER BY loaded_at DESC LIMIT 1"
    ).first();
    versions = {
      n_annotations: ann?.n ?? 0,
      bench_version: bench?.bench_version ?? null,
      universe_version: uni?.universe_version ?? null,
    };
  } catch {
    versions = null;
  }
  return json(
    {
      service: "surfaceome",
      description:
        "Public read-only API for the Deliverome surfaceome catalogue: deep-dive SurfaceomeRecords, genome-wide DB-vote + LLM triage verdicts, and the SurfaceBench eval. No auth; CORS open to all origins.",
      base_url: "https://api.deliverome.org/surfaceome/v1",
      docs: "https://surfaceome.deliverome.org/api",
      skill: "https://surfaceome.deliverome.org/surfaceome-api.skill.md",
      llms_txt: "https://surfaceome.deliverome.org/llms.txt",
      record_markdown_template: "https://api.deliverome.org/surfaceome/v1/genes/{symbol}.md",
      schema: {
        name: "SurfaceomeRecord",
        source: "src/accessible_surfaceome/tools/_shared/models.py",
        validates: "/v1/genes/{symbol}",
      },
      conventions: {
        stable_ids: "Key downstream lookups on hgnc_id / uniprot_acc / ensembl_gene, not the bare symbol.",
        verdict_values: ["yes", "contextual", "no"],
        missing_fields: "Absent fields are omitted on the wire; read with optional-chaining / ?? null.",
        caching: "List endpoints max-age=60; per-gene records / benchmark / orthologs max-age=86400.",
      },
      endpoints: V1_ENDPOINTS,
      versions,
      generated_at: new Date().toISOString(),
    },
    { ttl: CACHE_TTL_SHORT },
  );
}


// Approximate, D1-derived response size for every endpoint. The /api
// docs page renders these as live byte counts so they track the corpus
// as it grows instead of hand-maintained "~2 MB" strings. APPROXIMATE:
// variable-length text is summed exactly from D1 (LENGTH(...)); the
// fixed structural overhead of JSON (keys/quotes/commas/braces) and TSV
// (tabs/newlines) is added via the documented per-row constants below.
// Cheap aggregate queries only — no endpoint payload is materialized.
export async function handleMetaSizes(env) {
  // surface_annotation → /v1/genes, /v1/genes/{symbol}, /v1/health
  const sa = await env.DB.prepare(
    `SELECT COUNT(*) AS n,
            COALESCE(AVG(LENGTH(annotation_json)), 0) AS rec_avg,
            COALESCE(SUM(
              LENGTH(gene_symbol) + LENGTH(IFNULL(uniprot_acc,'')) +
              LENGTH(IFNULL(schema_version,'')) + LENGTH(IFNULL(confidence,'')) +
              LENGTH(IFNULL(triage_signal,'')) + LENGTH(IFNULL(surface_status,'')) +
              LENGTH(IFNULL(annotated_at,''))
            ), 0) AS list_chars
       FROM surface_annotation`
  ).first();

  // candidate_universe_public → /v1/catalog (pinned to latest universe)
  const rel = await env.DB.prepare(
    `SELECT universe_version FROM candidate_universe_release ORDER BY loaded_at DESC LIMIT 1`
  ).first();
  const cat = await env.DB.prepare(
    `SELECT COUNT(*) AS n FROM candidate_universe_public WHERE universe_version = ?`
  ).bind(rel?.universe_version ?? "").first();

  // triage_run_public grouped by the two export run_ids → export TSV sizes
  const trByRun = await env.DB.prepare(
    `SELECT run_id, COUNT(*) AS n,
            COALESCE(SUM(
              LENGTH(gene_symbol) + LENGTH(IFNULL(uniprot_acc,'')) +
              LENGTH(IFNULL(hgnc_id,'')) + LENGTH(IFNULL(ensembl_gene,'')) +
              LENGTH(IFNULL(model,'')) + LENGTH(IFNULL(prompt_variant,'')) +
              LENGTH(IFNULL(predicted_verdict,'')) + LENGTH(IFNULL(predicted_reason,'')) +
              LENGTH(IFNULL(predicted_confidence,'')) + 24
            ), 0) AS export_chars,
            COALESCE(SUM(
              LENGTH(IFNULL(verdict_reasoning,'')) + LENGTH(IFNULL(predicted_key_uncertainty,''))
            ), 0) AS reasoning_chars
       FROM triage_run_public
      WHERE run_id IN (?, ?)
      GROUP BY run_id`
  ).bind(DEFAULT_EXPORT_RUN_ID, GENOME_RUN_ID).all();
  const byRun = {};
  for (const r of trByRun.results) byRun[r.run_id] = r;
  const mainbench = byRun[DEFAULT_EXPORT_RUN_ID] || { n: 0, export_chars: 0, reasoning_chars: 0 };
  const genome = byRun[GENOME_RUN_ID] || { n: 0, export_chars: 0, reasoning_chars: 0 };

  // overall per-gene triage payload (all run_ids) → /v1/triage/{symbol}
  const trAll = await env.DB.prepare(
    `SELECT COUNT(*) AS n, COUNT(DISTINCT gene_symbol) AS g,
            COALESCE(SUM(
              LENGTH(IFNULL(verdict_reasoning,'')) + LENGTH(IFNULL(predicted_reason,'')) +
              LENGTH(IFNULL(predicted_key_uncertainty,'')) + 120
            ), 0) AS chars
       FROM triage_run_public`
  ).first();

  // benchmark_version → /v1/benchmark, /v1/benchmark/{symbol}, matrix/export
  const bv = await env.DB.prepare(
    `SELECT bench_version FROM benchmark_version ORDER BY bench_version DESC LIMIT 1`
  ).first();
  const bench = await env.DB.prepare(
    `SELECT COUNT(*) AS n,
            COALESCE(SUM(
              LENGTH(gene_symbol) + LENGTH(IFNULL(uniprot_acc,'')) + LENGTH(IFNULL(class,'')) +
              LENGTH(IFNULL(truth_verdict,'')) + LENGTH(IFNULL(truth_signal,'')) +
              LENGTH(IFNULL(truth_reason,'')) + LENGTH(IFNULL(rationale,''))
            ), 0) AS chars
       FROM benchmark_version WHERE bench_version = ?`
  ).bind(bv?.bench_version ?? "").first();

  // compara_ortholog → /v1/orthologs/{symbol} (avg rows per human gene)
  const orth = await env.DB.prepare(
    `SELECT COUNT(*) AS n, COUNT(DISTINCT human_gene_symbol) AS g
       FROM compara_ortholog
      WHERE release_version =
            (SELECT release_version FROM compara_release ORDER BY fetched_at DESC LIMIT 1)`
  ).first();

  // Per-row structural-overhead constants (documented approximations).
  const GENES_ROW = 95;    // JSON keys/quotes/commas per /v1/genes row
  const CATALOG_ROW = 230; // compact JSON per /v1/catalog row
  const BENCH_ROW = 110;   // JSON keys per /v1/benchmark row
  const ORTH_ROW = 180;    // JSON per ortholog row
  // Joined id/db columns added to the export beyond EXPORT_COLUMNS.
  const EXPORT_NCOLS = EXPORT_COLUMNS.length + 6;
  const r0 = (x) => Math.max(0, Math.round(x));

  const endpoints = {
    "/v1/health": {
      bytes: JSON.stringify({ ok: true, n_annotations: sa.n }).length,
      approx: false,
    },
    "/v1/genes": { bytes: r0(sa.list_chars + sa.n * GENES_ROW + 30), approx: true },
    "/v1/genes/{SYMBOL}": { bytes: r0(sa.rec_avg), approx: true, note: "average record" },
    "/v1/catalog": { bytes: r0(cat.n * CATALOG_ROW + 120), approx: true },
    "/v1/triage/{SYMBOL}": {
      bytes: trAll.g ? r0(trAll.chars / trAll.g + 400) : 0,
      approx: true,
      note: "average gene",
    },
    "/v1/triage/export.tsv": {
      bytes: r0(mainbench.export_chars + mainbench.n * EXPORT_NCOLS),
      approx: true,
      note: DEFAULT_EXPORT_RUN_ID,
    },
    [`/v1/triage/export.tsv?run_id=${GENOME_RUN_ID}`]: {
      bytes: r0(genome.export_chars + genome.n * EXPORT_NCOLS),
      approx: true,
      note: GENOME_RUN_ID,
    },
    [`/v1/triage/export.tsv?run_id=${GENOME_RUN_ID}&with_reasoning=1`]: {
      bytes: r0(genome.export_chars + genome.reasoning_chars + genome.n * (EXPORT_NCOLS + 2)),
      approx: true,
      note: `${GENOME_RUN_ID} + reasoning`,
    },
    "/v1/benchmark": { bytes: r0(bench.chars + bench.n * BENCH_ROW + 60), approx: true },
    "/v1/benchmark/{SYMBOL}": {
      bytes: bench.n ? r0(bench.chars / bench.n + BENCH_ROW) : 0,
      approx: true,
      note: "single label",
    },
    "/v1/benchmark/export.tsv": {
      bytes: r0(mainbench.export_chars + mainbench.reasoning_chars + mainbench.n * (EXPORT_NCOLS + 4)),
      approx: true,
    },
    "/v1/benchmark/matrix": {
      bytes: r0(bench.chars + mainbench.export_chars + mainbench.reasoning_chars + bench.n * 400),
      approx: true,
    },
    "/v1/orthologs/{SYMBOL}": {
      bytes: orth.g ? r0((orth.n / orth.g) * ORTH_ROW + 80) : 0,
      approx: true,
      note: "average gene",
    },
  };

  return json(
    {
      generated_at: new Date().toISOString(),
      bench_version: bv?.bench_version ?? null,
      universe_version: rel?.universe_version ?? null,
      endpoints,
    },
    { ttl: CACHE_TTL_SHORT },
  );
}
