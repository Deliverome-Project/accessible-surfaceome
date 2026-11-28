// Triage prior lookup, per-gene triage/internalization routes, and TSV export.

import { CACHE_TTL_LONG, CACHE_TTL_SHORT, badRequest, checkSymbol, isMissingTable, json, notFound, tsv, tsvCell } from "../lib/http.js";
import { collectSourceIds, fetchPaperMetadata } from "../lib/papers.js";
import { BENCH_MATRIX_MODELS, BENCH_MATRIX_VARIANTS, BENCH_RUN_ID, benchCellMajority } from "./benchmark.js";

export const TRIAGE_VERDICT_TO_SIGNAL = {
  yes: "likely_accessible",
  contextual: "possibly_accessible",
  no: "unlikely",
};

// Priority order for the Sonnet triage prior. MUST stay in sync with:
//   src/accessible_surfaceome/agents/surfaceome_v1/orchestrator.py
//     ::_D1_TRIAGE_PRIORITY
//   src/accessible_surfaceome/cloud/surface_annotation.py
//     ::_TRIAGE_COHERENCE_PRIORITY
// Walked in order; first hit wins. The bench-curated run is preferred
// over the genome-wide sweep — same logic the publish-time coherence
// guard uses. Public D1 currently carries only the ``_v2`` sweeps
// (verified 2026-06-07).
export const TRIAGE_PRIORITY = [
  ["mainbench_canonical_v2", "ncbi"],
  ["genome_full_sonnet_ncbi_v2", "ncbi"],
];

/**
 * Fetch the Sonnet triage row for `sym` honoring the priority order.
 * Returns `{verdict, reason, reasoning} | null`. Walks priorities one
 * by one — at most ~2 cheap point queries; the genome-wide sweep is the
 * tail case so most lookups resolve on the first query.
 *
 * The June-2026 bug: when the annotator's `_load_triage_record_from_d1`
 * failed silently (partial creds → empty token), records shipped with
 * `triage_signal=unknown` even though D1 carried the Sonnet verdict.
 * This overlay closes the loop: even if a record ships with `unknown`,
 * the Worker serves the live verdict that D1 actually has — no
 * re-annotation required.
 */
export async function fetchTriagePrior(env, sym) {
  for (const [runId, variant] of TRIAGE_PRIORITY) {
    const row = await env.DB.prepare(
      `SELECT predicted_verdict, predicted_reason, verdict_reasoning
         FROM triage_run_public
        WHERE gene_symbol = ? COLLATE NOCASE
          AND run_id = ?
          AND prompt_variant = ?
          AND model = 'claude-sonnet-4-6'
          AND predicted_verdict IS NOT NULL
        ORDER BY replicate ASC, created_at DESC
        LIMIT 1`
    ).bind(sym, runId, variant).first();
    if (row) {
      return {
        verdict: row.predicted_verdict,
        reason: row.predicted_reason,
        reasoning: row.verdict_reasoning,
      };
    }
  }
  return null;
}


export const EXPORT_COLUMNS = [
  "gene_symbol",
  "model",
  "prompt_variant",
  "replicate",
  "predicted_verdict",
  "predicted_reason",
  "predicted_confidence",
  "prompt_tokens",
  "completion_tokens",
  "cache_creation_tokens",
  "cache_read_tokens",
  "n_web_searches",
  "cost_usd",
  "latency_s",
  // Why a row has no verdict: "refusal" (the model's safety classifier
  // declined) or a runner error. Empty for a normal call. Last so existing
  // column positions are unchanged.
  "error",
];
export const DEFAULT_EXPORT_RUN_ID = BENCH_RUN_ID;
// The genome-wide Sonnet/NCBI triage sweep over the full protein-coding
// cohort (~19k genes). Used as the run_id for the genome-wide export and
// referenced by the /v1/meta/sizes estimator.
export const GENOME_RUN_ID = "genome_full_sonnet_ncbi_v2";

// The literature-rescue runs that make up stage two of the proteome-wide
// triage. Must equal RESCUE_RUNS in scripts/build_candidate_universe_v3.py,
// which builds the candidate universe the paper reports
// (tests/test_worker_catalog_rescue.py pins the two together). Order is the
// order a positive call is taken in when two lanes are both positive.
export const RESCUE_RUN_IDS = [
  "genome_full_sonnet_pubmed_ncbi_v1",
  "genome_intracellular_pubmed_ncbi_v1",
  "genome_1db_trim_pubmed_ncbi_v1",
  "genome_optcut_zerodb_pubmed_ncbi_v1",
];
// Reasoning columns appended to the triage export when `with_reasoning=1`.
// Default-off keeps the figure-input exports prose-free (see CLAUDE.md
// "Figure-input TSV conventions" — never ship full reasoning in those);
// opt-in gives the full genome-wide triage corpus with the agent's
// free-text verdict_reasoning for a bulk download.
export const REASONING_COLUMNS = ["predicted_key_uncertainty", "verdict_reasoning"];

// Self-describing endpoint catalog for the /v1 index. Kept in one place
// so an agent that lands on the API base discovers the whole surface
// (method + path template + summary) without scraping the docs page.

export async function handleTriageExport(env, url) {
  const runId = url.searchParams.get("run_id") || DEFAULT_EXPORT_RUN_ID;
  const replicate = url.searchParams.get("replicate");
  // Opt-in: append the agent's free-text reasoning columns. Off by
  // default so the figure-input export stays prose-free.
  const withReasoning = ["1", "true", "yes"].includes(
    (url.searchParams.get("with_reasoning") || "").toLowerCase()
  );
  const extraCols = withReasoning ? REASONING_COLUMNS : [];

  // Pin DB votes to the latest universe_version (same rule the
  // catalog handler uses).
  const releaseRow = await env.DB.prepare(
    `SELECT universe_version FROM candidate_universe_release
      ORDER BY loaded_at DESC LIMIT 1`
  ).first();
  const universeVersion = releaseRow?.universe_version ?? "";

  const sqlParts = [
    // uniprot_acc comes from the triage row's own resolution-stable value
    // (backfilled from gene_identifier via the HGNC-ID resolver), falling
    // back to the gene_identifier_public stable-ID cache by canonical
    // symbol. It is NO LONGER taken from candidate_universe_public by
    // gene_symbol — that symbol join misrouted the COX1/WAS-class genes
    // (e.g. COX1 must be MT-CO1/P00395, not PTGS1). The
    // candidate_universe_public join below stays, but only for the per-DB
    // surface-vote flags.
    `SELECT t.gene_symbol,`,
    `       COALESCE(t.uniprot_acc, gi.uniprot_acc) AS uniprot_acc,`,
    `       COALESCE(t.hgnc_id, gi.hgnc_id) AS hgnc_id,`,
    `       COALESCE(t.ensembl_gene, gi.ensembl_gene) AS ensembl_gene,`,
    // Recalibrated UniProt + CSPA, matching the catalog, the gene page and
    // the benchmark matrix. n_db_surface is recomputed rather than read
    // from n_sources_surface, which is the native count and would
    // contradict the flags in the same row.
    `       COALESCE(oc.uniprot_optimized, 0)   AS db_uniprot,`,
    `       COALESCE(c.go_surface_flag, 0)      AS db_go,`,
    `       COALESCE(c.surfy_surface_flag, 0)   AS db_surfy,`,
    `       COALESCE(oc.cspa_optimized, 0)      AS db_cspa,`,
    `       COALESCE(c.hpa_surface_flag, 0)     AS db_hpa,`,
    `       COALESCE(oc.uniprot_optimized, 0) + COALESCE(c.go_surface_flag, 0)`,
    `         + COALESCE(c.surfy_surface_flag, 0) + COALESCE(oc.cspa_optimized, 0)`,
    `         + COALESCE(c.hpa_surface_flag, 0)   AS n_db_surface,`,
    `       ${[...EXPORT_COLUMNS.slice(1), ...extraCols].map((c) => `t.${c}`).join(", ")}`,
    `  FROM triage_run_public t`,
    `  LEFT JOIN gene_identifier_public gi`,
    `         ON gi.hgnc_symbol = t.gene_symbol`,
    `  LEFT JOIN candidate_universe_public c`,
    `         ON c.gene_symbol = t.gene_symbol`,
    `  LEFT JOIN db_optimized_cutoff_public oc`,
    `         ON oc.accession = COALESCE(t.uniprot_acc, gi.uniprot_acc)`,
    `        AND c.universe_version = ?`,
    ` WHERE t.run_id = ?`,
  ];
  const params = [universeVersion, runId];
  if (replicate != null) {
    const r = parseInt(replicate, 10);
    if (Number.isNaN(r)) return badRequest("invalid_replicate");
    sqlParts.push(` AND t.replicate = ?`);
    params.push(r);
  }
  sqlParts.push(` ORDER BY t.model, t.prompt_variant, t.gene_symbol`);
  const rs = await env.DB.prepare(sqlParts.join("")).bind(...params).all();

  const cols = [
    "gene_symbol", "uniprot_acc", "hgnc_id", "ensembl_gene",
    "db_uniprot", "db_go", "db_surfy", "db_cspa", "db_hpa", "n_db_surface",
    ...EXPORT_COLUMNS.slice(1),
    ...extraCols,
  ];
  const headers = cols.join("\t");
  const body = rs.results
    .map((r) => cols.map((c) => tsvCell(r[c])).join("\t"))
    .join("\n");
  return tsv(`${headers}\n${body}\n`, { ttl: CACHE_TTL_LONG });
}


// Long-format TSV: one row per benchmark gene × model × variant cell, with
// curated truth labels and per-source DB votes joined in. Same cells as
// `/v1/benchmark/matrix`, flattened: predicted_* is the cell's majority
// over its replicates (benchCellMajority — the paper's per-cell numbers),
// `replicate` and the per-call telemetry columns describe the cell's
// representative replicate, and the trailing columns carry the majority's
// n_reps / agreement, the soft-credit is_match against truth, and the
// telemetry summed over all the cell's replicates (the `*_total` columns
// equal mainbench_canonical_v2.tsv's token / cost / latency columns). A
// cell whose replicates all refused keeps its row with an empty verdict,
// n_reps 0 and an empty is_match. Drives the
// triage-benchmark-with-reasoning Zenodo deposit file.
//
// Replaces an earlier truth-labels-only version of this endpoint —
// truth labels alone are still available as the truth_* columns here,
// or as the `/v1/benchmark[/{symbol}]` JSON endpoints.

export async function handleTriage(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  const rows = await env.DB.prepare(
    `SELECT created_at, model, prompt_variant, prompt_filename,
            schema_version, replicate, predicted_verdict, predicted_reason,
            predicted_confidence, predicted_key_uncertainty,
            verdict_reasoning, correct, latency_s, n_web_searches, error,
            cost_usd, prompt_tokens, completion_tokens,
            cache_creation_tokens, cache_read_tokens
       FROM triage_run_public
      WHERE gene_symbol = ? COLLATE NOCASE
      ORDER BY created_at DESC, model, prompt_variant, replicate`
  ).bind(sym).all();
  return json({
    gene_symbol: sym,
    count: rows.results.length,
    runs: rows.results,
  }, { ttl: CACHE_TTL_SHORT });
}

// Per-gene internalization record — the standalone internalization pass
// (surface_internalization). Serves the full InternalizationRecord JSON so the
// gene page's InternalizationCard renders the sequence-prior (+ literature,
// once present) tracks for ANY swept gene, not just the handful of committed
// static snapshots the card used to fall back to. One row per gene (publish
// drops stale schema_versions); the MAX(schema_version) guard is
// belt-and-suspenders. Returns `null` on a miss (short TTL so a later sweep
// surfaces without a day-long stale "no record" cache); the card treats null
// as "no record for {symbol} yet".
export async function handleInternalization(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  const rows = await env.DB.prepare(
    `SELECT record_json FROM surface_internalization
      WHERE gene_symbol = ? COLLATE NOCASE
      ORDER BY schema_version DESC LIMIT 1`
  ).bind(sym).all();
  const row = rows.results[0];
  if (!row) return json(null, { ttl: CACHE_TTL_SHORT });
  let record;
  try {
    record = JSON.parse(row.record_json);
  } catch {
    return json(null, { ttl: CACHE_TTL_SHORT });
  }
  const sources = Array.isArray(record?.literature?.sources) ? record.literature.sources : [];
  const papers = await fetchPaperMetadata(env, collectSourceIds(sources));
  return json({ ...record, papers }, { ttl: CACHE_TTL_LONG });
}

// Per-(gene, model, variant) replicate detail — backs the benchmark
// RationaleDrawer's "majority reason first, then all reps on scroll" view.
// Returns every replicate for the cell (so the drawer can show the
// per-rep spread), plus a computed `majority` block — the same majority
// the /benchmark/matrix cell carries (benchCellMajority), with the
// representative replicate's reasoning. Lazy-loaded by the drawer on open,
// so the matrix payload carries one reasoning string per cell.
export async function handleTriageCell(env, symbol, model, variant) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  // model/variant are closed enums — validate against the known sets to
  // avoid an unbounded WHERE and keep the query plan tight.
  if (!BENCH_MATRIX_MODELS.includes(model)) return badRequest("invalid_model");
  if (!BENCH_MATRIX_VARIANTS.includes(variant)) return badRequest("invalid_variant");
  // Scope to the canonical bench run — without this, a gene that also
  // appears in the whole-genome sweep (genome_full_sonnet_ncbi_v2, same
  // sonnet/ncbi cell) would have its rows collide with the bench reps.
  // One row per replicate number (latest by created_at) so a stray
  // duplicate-replicate row from a bad sync can't surface as two "Rep N".
  const rows = await env.DB.prepare(
    `WITH ranked AS (
       SELECT created_at, replicate, predicted_verdict, predicted_reason,
              predicted_confidence, predicted_key_uncertainty,
              verdict_reasoning, correct, latency_s, n_web_searches, error,
              cost_usd, prompt_tokens, completion_tokens,
              cache_creation_tokens, cache_read_tokens,
              ROW_NUMBER() OVER (
                PARTITION BY replicate ORDER BY created_at DESC
              ) AS rn
         FROM triage_run_public
        WHERE run_id = ? AND gene_symbol = ? COLLATE NOCASE AND model = ? AND prompt_variant = ?
     )
     SELECT created_at, replicate, predicted_verdict, predicted_reason,
            predicted_confidence, predicted_key_uncertainty,
            verdict_reasoning, correct, latency_s, n_web_searches, error,
            cost_usd, prompt_tokens, completion_tokens,
            cache_creation_tokens, cache_read_tokens
       FROM ranked WHERE rn = 1
      ORDER BY replicate`
  ).bind(BENCH_RUN_ID, sym, model, variant).all();
  const reps = rows.results;
  // The same majority the matrix serves for this cell (benchCellMajority):
  // binary surface vote over valid-verdict reps, then the modal verdict,
  // reason and confidence on the winning side, with the representative
  // replicate's free-text reasoning.
  const maj = benchCellMajority(reps);
  const majority = maj
    ? {
        verdict: maj.verdict,
        reason: maj.reason,
        reasoning: maj.rep.verdict_reasoning ?? null,
        confidence: maj.confidence,
        replicate: maj.rep.replicate,
        n_reps: maj.n_reps,
        agreement: maj.agreement,
      }
    : null;
  return json({
    gene_symbol: sym,
    model,
    prompt_variant: variant,
    majority,
    replicates: reps,
  }, { ttl: CACHE_TTL_SHORT });
}
