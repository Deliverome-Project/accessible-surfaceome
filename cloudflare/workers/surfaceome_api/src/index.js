// Cloudflare Worker — public read-only Surfaceome API.
//
// Reads from the `surfaceome_public` D1 (bound as env.DB in wrangler.toml).
// No auth; aggressive Cache-Control headers carry the load on edge cache.
//
// Endpoints:
//   GET /v1/health
//   GET /v1/genes               — list of annotated genes
//   GET /v1/genes/:symbol       — full SurfaceomeRecord
//   GET /v1/catalog             — genome-wide candidate-universe table
//                                  (DB votes + latest triage + deep-dive flag)
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

async function handleCatalog(env) {
  // Pull the latest universe_version pointer. If no universe has been
  // loaded yet (cold DB), bail with an empty payload — the viewer
  // falls back to its committed snapshot in that case.
  const releaseRow = await env.DB.prepare(
    `SELECT universe_version, n_rows, loaded_at
       FROM candidate_universe_release
       ORDER BY loaded_at DESC LIMIT 1`
  ).first();
  if (!releaseRow) {
    return json(
      { universe_version: null, n_rows: 0, n_with_triage: 0, n_with_deep_dive: 0, rows: [] },
      { ttl: CACHE_TTL_SHORT },
    );
  }
  const universe = releaseRow.universe_version;

  // (Bench version surfaced for response metadata only — the triage
  // lookup below no longer FILTERS by latest bench_version. Older
  // verdicts still represent the project's freshest read on each
  // gene; hiding them just because the bench_version label rolled
  // forward leaves the catalog mostly empty.)
  const benchRow = await env.DB.prepare(
    `SELECT bench_version FROM benchmark_version
      ORDER BY bench_version DESC LIMIT 1`
  ).first();
  const benchVersion = benchRow?.bench_version ?? null;

  // Universe rows are the spine of the catalog: one per gene. We only
  // SELECT the 5 gating DBs (uniprot, go, surfy, cspa, hpa) — DeepTMHMM
  // and COMPARTMENTS are stored in the table for fidelity but are
  // auxiliary signals (demoted from the M1 universe gate; see
  // src/accessible_surfaceome/merge/__init__.py). n_sources_surface in
  // the table is already the count over those 5 flags only.
  const universeRows = await env.DB.prepare(
    `SELECT gene_symbol, uniprot_acc, n_sources_surface,
            uniprot_surface_flag, go_surface_flag, surfy_surface_flag,
            cspa_surface_flag, hpa_surface_flag
       FROM candidate_universe_public
      WHERE universe_version = ?
      ORDER BY gene_symbol`
  ).bind(universe).all();

  // Latest triage verdict per gene, regardless of bench_version. The
  // earlier query strict-filtered to the latest bench, which left the
  // catalog mostly empty: most triage runs are genome-wide sweeps
  // (~19k genes) that aren't anchored to a benchmark at all, so
  // their bench_version is either NULL or whatever was current
  // months ago — not useful as a "freshness" filter. Take
  // max(created_at) across all benches; surface `bench_version`
  // (possibly null) + `created_at` per row so consumers can tell
  // *which* run each verdict came from.
  const triageMap = new Map();
  const triageRows = await env.DB.prepare(
    `SELECT gene_symbol, predicted_verdict, predicted_reason,
            bench_version, created_at
       FROM triage_run_public t
      WHERE created_at = (
        SELECT MAX(created_at) FROM triage_run_public
         WHERE gene_symbol = t.gene_symbol
      )`
  ).all();
  for (const r of triageRows.results) {
    if (!triageMap.has(r.gene_symbol)) {
      triageMap.set(r.gene_symbol, {
        verdict: r.predicted_verdict,
        reason: r.predicted_reason,
        bench_version: r.bench_version,
        created_at: r.created_at,
      });
    }
  }

  // Genes with a published deep-dive SurfaceomeRecord (whatever schema_version).
  const deepRows = await env.DB.prepare(
    `SELECT DISTINCT gene_symbol FROM surface_annotation`
  ).all();
  const deepSet = new Set(deepRows.results.map((r) => r.gene_symbol));

  // Track which genes we've emitted so we can append deep-dive-only
  // genes (e.g. HSPA1A — conditional surface, doesn't pass the
  // universe gate) at the bottom.
  const covered = new Set();
  // Encode the 5 surface flags as a single 5-bit integer to keep the
  // response under Next.js's 2 MB data-cache ceiling. Bit layout
  // (LSB → MSB) matches the order the viewer renders columns in:
  //   bit 0 = uniprot, 1 = go, 2 = surfy, 3 = cspa, 4 = hpa.
  // Decoded in viewer/lib/surfaceome.ts; see DB_BIT_KEYS there.
  const rows = universeRows.results.map((u) => {
    covered.add(u.gene_symbol);
    const db =
      (u.uniprot_surface_flag ? 1 : 0) |
      (u.go_surface_flag ? 2 : 0) |
      (u.surfy_surface_flag ? 4 : 0) |
      (u.cspa_surface_flag ? 8 : 0) |
      (u.hpa_surface_flag ? 16 : 0);
    const row = {
      symbol: u.gene_symbol,
      n_sources: u.n_sources_surface,
      db,
    };
    // Drop empty / falsy fields to compact the wire payload further —
    // most rows have no uniprot accession and no triage / deep-dive
    // flag.
    if (u.uniprot_acc) row.uniprot = u.uniprot_acc;
    const t = triageMap.get(u.gene_symbol);
    if (t) row.triage = t;
    if (deepSet.has(u.gene_symbol)) row.deep_dive = true;
    return row;
  });

  // Append deep-dive-only genes (missing from the universe row set).
  // Without this the index page loses these records entirely; they're
  // the strongest accessibility data we have.
  for (const sym of deepSet) {
    if (covered.has(sym)) continue;
    const row = { symbol: sym, n_sources: 0, db: 0, deep_dive: true };
    const t = triageMap.get(sym);
    if (t) row.triage = t;
    rows.push(row);
  }

  // Stable sort: deep-dive first, then DB-vote desc, then symbol asc.
  // (deep_dive is now optional — undefined sorts AFTER true.)
  rows.sort((a, b) => {
    const da = a.deep_dive ? 1 : 0;
    const db = b.deep_dive ? 1 : 0;
    if (da !== db) return db - da;
    if (a.n_sources !== b.n_sources) return b.n_sources - a.n_sources;
    return a.symbol < b.symbol ? -1 : a.symbol > b.symbol ? 1 : 0;
  });

  return json(
    {
      universe_version: universe,
      bench_version: benchVersion,
      n_rows: rows.length,
      n_with_triage: rows.filter((r) => r.triage).length,
      n_with_deep_dive: rows.filter((r) => r.deep_dive).length,
      // Schema version of the row encoding. Bumped when the shape
      // changes; viewer/lib/surfaceome.ts checks this and decodes
      // accordingly.
      row_schema: 2,
      rows,
    },
    { ttl: CACHE_TTL_SHORT },
  );
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
    // Strip the `/surfaceome` route prefix when present so the
    // same router handles both production
    // (`api.deliverome.org/surfaceome/v1/...`) and the workers.dev
    // fallback (`surfaceome-api.<sub>.workers.dev/v1/...`). Trailing
    // slashes are normalized so `/v1/health/` and `/v1/health` both
    // resolve.
    let path = url.pathname.replace(/\/+$/, "");
    if (path.startsWith("/surfaceome/")) {
      path = path.slice("/surfaceome".length);
    } else if (path === "/surfaceome") {
      path = "";
    }

    if (path === "/v1/health") return handleHealth(env);
    if (path === "/v1/genes") return handleGeneList(env);
    if (path === "/v1/catalog") return handleCatalog(env);
    if (path === "/v1/benchmark") return handleBenchmarkList(env);

    let m;
    if ((m = path.match(/^\/v1\/genes\/([^/]+)$/))) return handleGene(env, m[1]);
    if ((m = path.match(/^\/v1\/orthologs\/([^/]+)$/))) return handleOrthologs(env, m[1]);
    if ((m = path.match(/^\/v1\/benchmark\/([^/]+)$/))) return handleBenchmarkOne(env, m[1]);
    if ((m = path.match(/^\/v1\/triage\/([^/]+)$/))) return handleTriage(env, m[1]);

    return notFound("route_not_found");
  },
};
