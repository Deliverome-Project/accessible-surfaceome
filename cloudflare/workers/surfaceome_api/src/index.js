// Cloudflare Worker — public read-only Surfaceome API.
//
// Reads from the `surfaceome_public` D1 (bound as env.DB in wrangler.toml).
// No auth; aggressive Cache-Control headers carry the load on edge cache.
//
// Endpoints:
//   GET /v1/health
//   GET /v1/genes               — list of annotated genes
//   GET /v1/genes/:symbol       — full SurfaceomeRecord
//   GET /v1/orthologs/:symbol   — ortholog table for a gene
//   GET /v1/benchmark           — full benchmark truth labels (latest version)
//   GET /v1/benchmark/:symbol   — single gene's truth label
//   GET /v1/triage/:symbol      — model verdicts across runs (no costs)
//
// Schema: cloudflare/d1_public_schema.sql.

const CACHE_TTL_SHORT = 60;        // 1 min for list endpoints
const CACHE_TTL_LONG  = 86400;     // 1 day for per-gene records

const CORS_HEADERS = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function json(data, { status = 200, ttl = CACHE_TTL_SHORT } = {}) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": `public, max-age=${ttl}, s-maxage=${ttl}`,
      ...CORS_HEADERS,
    },
  });
}

function notFound(msg = "not_found") {
  return json({ error: msg }, { status: 404, ttl: 60 });
}

function badRequest(msg) {
  return json({ error: msg }, { status: 400, ttl: 0 });
}

// Light gene-symbol validation: alnum + dash + dot, ≤30 chars.
const SYMBOL_OK = /^[A-Za-z0-9][A-Za-z0-9._-]{0,29}$/;

function checkSymbol(sym) {
  if (!sym || !SYMBOL_OK.test(sym)) return null;
  return sym.toUpperCase();
}


// --- handlers --------------------------------------------------------------

async function handleHealth(env) {
  // Cheap query to confirm the DB binding works.
  const r = await env.DB.prepare(
    "SELECT count(*) AS n FROM surface_annotation"
  ).first();
  return json({ ok: true, n_annotations: r?.n ?? 0 });
}

async function handleGeneList(env) {
  const rows = await env.DB.prepare(
    `SELECT gene_symbol, uniprot_acc, schema_version, confidence,
            triage_signal, surface_status, annotated_at
       FROM surface_annotation
      ORDER BY gene_symbol`
  ).all();
  return json({ count: rows.results.length, genes: rows.results }, { ttl: CACHE_TTL_SHORT });
}

async function handleGene(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  // Latest schema_version wins (string ordering on v0.4.0 < v0.5.0 etc.).
  const row = await env.DB.prepare(
    `SELECT annotation_json, schema_version, annotated_at
       FROM surface_annotation
      WHERE gene_symbol = ?
      ORDER BY schema_version DESC
      LIMIT 1`
  ).bind(sym).first();
  if (!row) return notFound("gene_not_annotated");
  let record;
  try {
    record = JSON.parse(row.annotation_json);
  } catch (e) {
    return json({ error: "bad_record_json" }, { status: 500, ttl: 0 });
  }
  return json(record, { ttl: CACHE_TTL_LONG });
}

async function handleOrthologs(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  // Latest release_version wins for the same gene.
  const release = await env.DB.prepare(
    `SELECT release_version FROM compara_release ORDER BY fetched_at DESC LIMIT 1`
  ).first();
  if (!release) return json({ release_version: null, orthologs: [] }, { ttl: CACHE_TTL_LONG });
  const rows = await env.DB.prepare(
    `SELECT species, ortholog_uniprot_acc, ortholog_gene_symbol,
            ortholog_ensembl_gene, orthology_type, percent_identity,
            is_high_confidence
       FROM compara_ortholog
      WHERE release_version = ? AND human_gene_symbol = ?
      ORDER BY species`
  ).bind(release.release_version, sym).all();
  return json({
    release_version: release.release_version,
    gene_symbol: sym,
    orthologs: rows.results,
  }, { ttl: CACHE_TTL_LONG });
}

async function handleBenchmarkList(env) {
  // Latest bench_version wins.
  const v = await env.DB.prepare(
    `SELECT bench_version FROM benchmark_version ORDER BY bench_version DESC LIMIT 1`
  ).first();
  if (!v) return json({ bench_version: null, count: 0, entries: [] });
  const rows = await env.DB.prepare(
    `SELECT gene_symbol, uniprot_acc, class, truth_verdict, truth_signal,
            truth_reason, rationale
       FROM benchmark_version
      WHERE bench_version = ?
      ORDER BY gene_symbol`
  ).bind(v.bench_version).all();
  return json({
    bench_version: v.bench_version,
    count: rows.results.length,
    entries: rows.results,
  }, { ttl: CACHE_TTL_LONG });
}

async function handleBenchmarkOne(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  const row = await env.DB.prepare(
    `SELECT bench_version, gene_symbol, uniprot_acc, class,
            truth_verdict, truth_signal, truth_reason, rationale
       FROM benchmark_version
      WHERE gene_symbol = ?
      ORDER BY bench_version DESC
      LIMIT 1`
  ).bind(sym).first();
  if (!row) return notFound("not_in_benchmark");
  return json(row, { ttl: CACHE_TTL_LONG });
}

async function handleTriage(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  const rows = await env.DB.prepare(
    `SELECT created_at, model, prompt_variant, prompt_filename,
            schema_version, replicate, predicted_verdict, predicted_reason,
            predicted_confidence, predicted_key_uncertainty,
            verdict_reasoning, correct, latency_s, n_web_searches, error
       FROM triage_run_public
      WHERE gene_symbol = ?
      ORDER BY created_at DESC, model, prompt_variant, replicate`
  ).bind(sym).all();
  return json({
    gene_symbol: sym,
    count: rows.results.length,
    runs: rows.results,
  }, { ttl: CACHE_TTL_SHORT });
}


// --- entry ----------------------------------------------------------------

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }
    if (request.method !== "GET") {
      return json({ error: "method_not_allowed" }, { status: 405, ttl: 0 });
    }
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "");

    if (path === "/v1/health") return handleHealth(env);
    if (path === "/v1/genes") return handleGeneList(env);
    if (path === "/v1/benchmark") return handleBenchmarkList(env);

    let m;
    if ((m = path.match(/^\/v1\/genes\/([^/]+)$/))) return handleGene(env, m[1]);
    if ((m = path.match(/^\/v1\/orthologs\/([^/]+)$/))) return handleOrthologs(env, m[1]);
    if ((m = path.match(/^\/v1\/benchmark\/([^/]+)$/))) return handleBenchmarkOne(env, m[1]);
    if ((m = path.match(/^\/v1\/triage\/([^/]+)$/))) return handleTriage(env, m[1]);

    return notFound("route_not_found");
  },
};
