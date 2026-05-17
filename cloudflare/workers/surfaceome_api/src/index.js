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
//   GET /v1/benchmark/matrix    — 147-gene matrix: truth + per-DB flags +
//                                  per-model headline & alt LLM verdicts
//   GET /v1/benchmark/export.tsv — 7-column TSV of curated truth labels,
//                                  mirrors `data/eval/triage_benchmark_v1.tsv`
//                                  shape (gene/uniprot/class/verdict/
//                                  signal/reason/rationale). Figure scripts
//                                  load truth labels from here.
//   GET /v1/benchmark/:symbol   — single gene's truth label
//   GET /v1/triage/:symbol      — model verdicts across runs (with costs)
//   GET /v1/triage/export.tsv   — long-format TSV of all triage runs for a
//                                  given run_id (default mainbench_canonical_v1).
//                                  Single source of truth for final-figure
//                                  predictions data; carries cost_usd + token
//                                  counts.
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

// TSV response — same cache/CORS posture as `json` but text/tsv.
// Used by /v1/triage/export.tsv so reproducibility scripts can `pd.read_csv(url, sep="\t")`
// straight from the API.
function tsv(content, { status = 200, ttl = CACHE_TTL_SHORT } = {}) {
  return new Response(content, {
    status,
    headers: {
      "Content-Type": "text/tab-separated-values; charset=utf-8",
      "Cache-Control": `public, max-age=${ttl}, s-maxage=${ttl}`,
      ...CORS_HEADERS,
    },
  });
}

// Minimal TSV escaping: tabs/CR/LF in a cell would break the row,
// so collapse them to a single space. Don't quote — TSV doesn't.
function tsvCell(v) {
  if (v == null) return "";
  return String(v).replace(/[\t\r\n]+/g, " ");
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

  // Latest per-model NCBI-variant verdict for each gene. The page
  // renders three columns (Haiku / Sonnet / Opus); each cell shows
  // that model's ncbi-variant call. Only `prompt_variant='ncbi'`
  // because that's the variant with cross-model coverage and the one
  // the published figures use as headline.
  //
  // Coverage today:
  //   - Sonnet/ncbi: full ~19k genome (genome_full_sonnet_ncbi_v1)
  //   - Haiku/ncbi: 147 SurfaceBench genes only (mainbench_canonical_v1)
  //   - Opus/ncbi: 147 SurfaceBench genes only (mainbench_canonical_v1)
  // So most rows will show only the Sonnet column populated.
  const CATALOG_MODELS = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"];
  const triageByGene = new Map();
  const triageRows = await env.DB.prepare(
    `WITH ranked AS (
       SELECT gene_symbol, model, predicted_verdict, predicted_reason,
              created_at,
              ROW_NUMBER() OVER (
                PARTITION BY gene_symbol, model
                ORDER BY created_at DESC
              ) AS rn
         FROM triage_run_public
        WHERE prompt_variant = 'ncbi'
          AND model IN ('claude-haiku-4-5','claude-sonnet-4-6','claude-opus-4-7')
     )
     SELECT gene_symbol, model, predicted_verdict, predicted_reason, created_at
       FROM ranked WHERE rn = 1`
  ).all();
  for (const r of triageRows.results) {
    let perModel = triageByGene.get(r.gene_symbol);
    if (!perModel) {
      perModel = {};
      triageByGene.set(r.gene_symbol, perModel);
    }
    perModel[r.model] = {
      verdict: r.predicted_verdict,
      reason: r.predicted_reason,
      created_at: r.created_at,
    };
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
  //
  // Per-model NCBI verdict: `tr` is a 3-slot array
  // [haiku, sonnet, opus]. Each slot is null or [verdict, reason].
  // Compact wire form because we have ~19k rows; the verdict strings
  // are short and ~95% of slots are null (Haiku/Opus only cover the
  // 147 SurfaceBench genes today).
  function packTriage(sym) {
    const per = triageByGene.get(sym);
    if (!per) return undefined;
    const out = CATALOG_MODELS.map((m) => {
      const t = per[m];
      if (!t?.verdict) return null;
      return [t.verdict, t.reason ?? null];
    });
    return out.some((x) => x) ? out : undefined;
  }
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
    if (u.uniprot_acc) row.uniprot = u.uniprot_acc;
    const t = packTriage(u.gene_symbol);
    if (t) row.tr = t;
    if (deepSet.has(u.gene_symbol)) row.deep_dive = true;
    return row;
  });

  // Append deep-dive-only genes (missing from the universe row set).
  for (const sym of deepSet) {
    if (covered.has(sym)) continue;
    const row = { symbol: sym, n_sources: 0, db: 0, deep_dive: true };
    const t = packTriage(sym);
    if (t) row.tr = t;
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
      models: CATALOG_MODELS,
      n_rows: rows.length,
      n_with_triage: rows.filter((r) => r.tr).length,
      n_with_deep_dive: rows.filter((r) => r.deep_dive).length,
      // Schema version of the row encoding. Bumped when the shape
      // changes; viewer/lib/surfaceome.ts checks this and decodes
      // accordingly. v3 = per-model ncbi `tr` array replaces the
      // single `triage` object.
      row_schema: 3,
      rows,
    },
    { ttl: CACHE_TTL_SHORT },
  );
}

// Models + prompt variants surfaced in the benchmark matrix. All 4
// variants render as their own columns on the /benchmark/ page (the
// old "headline + 3 alts behind an expand" UX collapsed into a flat
// grid per the user request 2026-05-15). `headline_variant` is still
// returned for consumers that want to highlight one column.
const BENCH_MATRIX_MODELS = [
  "claude-opus-4-7",
  "claude-sonnet-4-6",
  "claude-haiku-4-5",
];
const BENCH_MATRIX_VARIANTS = ["naive", "ncbi", "web_ncbi", "pubmed_ncbi"];
const BENCH_MATRIX_HEADLINE_VARIANT = "ncbi";
// Five gating DBs — same five the homepage CatalogTable renders. The
// matrix used to expose two auxiliary signals (DeepTMHMM, COMPARTMENTS)
// but those were demoted from the M1 universe gate and only confused
// the side-by-side, so we drop them here too (2026-05-15).
const BENCH_MATRIX_SOURCES = [
  "uniprot", "go", "surfy", "cspa", "hpa",
];

async function handleBenchmarkMatrix(env) {
  // 1. Pick the canonical curated benchmark — the bench_version with
  // the most rows carrying a non-empty truth_verdict, breaking ties by
  // most recent created_at. The unlabeled gene-set snapshots (19k+
  // rows, blank truth columns) and the small ad-hoc benches (2-9 rows)
  // are interned with their own bench_version SHA, so a plain
  // `ORDER BY bench_version DESC` is essentially random — bench_version
  // is a content hash, not a timestamp. Filtering on labeled rows is
  // robust to both the unlabeled inputs and the stub uploads.
  const benchRow = await env.DB.prepare(
    `SELECT bench_version, COUNT(*) AS n_labeled, MAX(created_at) AS latest
       FROM benchmark_version
      WHERE truth_verdict IS NOT NULL AND truth_verdict != ''
      GROUP BY bench_version
      ORDER BY n_labeled DESC, latest DESC
      LIMIT 1`
  ).first();
  if (!benchRow) {
    return json(
      { bench_version: null, universe_version: null, n_genes: 0, rows: [] },
      { ttl: CACHE_TTL_SHORT },
    );
  }
  const benchVersion = benchRow.bench_version;

  // 2. Truth labels for that bench_version.
  const truthRows = await env.DB.prepare(
    `SELECT gene_symbol, uniprot_acc, class, truth_verdict, truth_signal,
            truth_reason, rationale
       FROM benchmark_version
      WHERE bench_version = ?
      ORDER BY gene_symbol`
  ).bind(benchVersion).all();

  // 3. Latest universe_version + per-DB flags. Five gating DBs only —
  // matches the homepage CatalogTable so the SurfaceBench and Catalog
  // surfaces are side-by-side comparable.
  const releaseRow = await env.DB.prepare(
    `SELECT universe_version FROM candidate_universe_release
      ORDER BY loaded_at DESC LIMIT 1`
  ).first();
  const universeVersion = releaseRow?.universe_version ?? null;
  const dbByGene = new Map();
  if (universeVersion) {
    const universeRows = await env.DB.prepare(
      `SELECT gene_symbol, uniprot_surface_flag, go_surface_flag,
              surfy_surface_flag, cspa_surface_flag, hpa_surface_flag,
              n_sources_surface
         FROM candidate_universe_public
        WHERE universe_version = ?`
    ).bind(universeVersion).all();
    for (const u of universeRows.results) {
      dbByGene.set(u.gene_symbol, {
        uniprot: u.uniprot_surface_flag ? 1 : 0,
        go: u.go_surface_flag ? 1 : 0,
        surfy: u.surfy_surface_flag ? 1 : 0,
        cspa: u.cspa_surface_flag ? 1 : 0,
        hpa: u.hpa_surface_flag ? 1 : 0,
        n_sources_surface: u.n_sources_surface ?? 0,
      });
    }
  }

  // 4. Triage runs for the model/variant grid we care about. The
  // partition-and-rank used to scan the whole ~19k-row genome-wide
  // sweep (~228k cells across all model×variant combinations) and
  // then JS-filter down to the 147 benchmark genes — that's a hot
  // ROW_NUMBER() window over D1 that exceeded Cloudflare's Worker
  // CPU budget (HTTP 503, cf-error 1102). Joining inside the SQL
  // against the benchmark_version table (just 1 bound parameter for
  // bench_version) shrinks the partition-and-rank working set to
  // 147 genes × 3 models × 4 variants ≈ 1.7k rows — well inside the
  // CPU budget. Runs tagged against any bench_version still count
  // (we don't filter triage_run_public by bench_version, only by
  // gene_symbol membership in the current bench) so the matrix
  // keeps full Opus/Haiku coverage from earlier sweeps.
  const wantedVariants = BENCH_MATRIX_VARIANTS;
  const variantPlaceholders = wantedVariants.map(() => "?").join(",");
  const modelPlaceholders = BENCH_MATRIX_MODELS.map(() => "?").join(",");
  const triageRows = await env.DB.prepare(
    `WITH bench_genes AS (
       SELECT DISTINCT gene_symbol
         FROM benchmark_version
        WHERE bench_version = ?
     ),
     ranked AS (
       SELECT t.gene_symbol, t.model, t.prompt_variant, t.predicted_verdict,
              t.predicted_reason, t.predicted_confidence, t.predicted_key_uncertainty,
              t.verdict_reasoning,
              t.correct, t.latency_s, t.n_web_searches, t.created_at, t.error,
              t.cost_usd, t.prompt_tokens, t.completion_tokens,
              t.cache_creation_tokens, t.cache_read_tokens,
              ROW_NUMBER() OVER (
                PARTITION BY t.gene_symbol, t.model, t.prompt_variant
                ORDER BY t.created_at DESC
              ) AS rn
         FROM triage_run_public t
         INNER JOIN bench_genes b ON t.gene_symbol = b.gene_symbol
        WHERE t.prompt_variant IN (${variantPlaceholders})
          AND t.model IN (${modelPlaceholders})
     )
     SELECT gene_symbol, model, prompt_variant, predicted_verdict,
            predicted_reason, predicted_confidence, predicted_key_uncertainty,
            verdict_reasoning,
            correct, latency_s, n_web_searches, created_at, error,
            cost_usd, prompt_tokens, completion_tokens,
            cache_creation_tokens, cache_read_tokens
       FROM ranked
      WHERE rn = 1`
  ).bind(benchVersion, ...wantedVariants, ...BENCH_MATRIX_MODELS).all();

  // Build a nested map: gene → model → variant → run. The SQL JOIN
  // above already restricts to benchmark genes, so no JS-side
  // membership check is needed.
  const runMap = new Map();
  for (const r of triageRows.results) {
    let byModel = runMap.get(r.gene_symbol);
    if (!byModel) {
      byModel = new Map();
      runMap.set(r.gene_symbol, byModel);
    }
    let byVariant = byModel.get(r.model);
    if (!byVariant) {
      byVariant = new Map();
      byModel.set(r.model, byVariant);
    }
    byVariant.set(r.prompt_variant, {
      verdict: r.predicted_verdict,
      reason: r.predicted_reason,
      confidence: r.predicted_confidence,
      key_uncertainty: r.predicted_key_uncertainty,
      reasoning: r.verdict_reasoning,
      correct: r.correct,
      latency_s: r.latency_s,
      n_web_searches: r.n_web_searches,
      created_at: r.created_at,
      error: r.error,
      cost_usd: r.cost_usd,
      prompt_tokens: r.prompt_tokens,
      completion_tokens: r.completion_tokens,
      cache_creation_tokens: r.cache_creation_tokens,
      cache_read_tokens: r.cache_read_tokens,
    });
  }

  // 5. Stitch. Flat verdicts dict: model → variant → run (or null when
  // we have no data for that cell). Replaces the prior headline+alts
  // split; the page renders all 4 variants per model as their own
  // columns and shows each cell's verdict_reasoning on row-expand.
  const rows = truthRows.results.map((t) => {
    const byModel = runMap.get(t.gene_symbol);
    const verdicts = {};
    for (const model of BENCH_MATRIX_MODELS) {
      const byVariant = byModel?.get(model);
      const perVariant = {};
      for (const variant of BENCH_MATRIX_VARIANTS) {
        perVariant[variant] = byVariant?.get(variant) ?? null;
      }
      verdicts[model] = perVariant;
    }
    const db = dbByGene.get(t.gene_symbol) ?? null;
    const row = {
      gene_symbol: t.gene_symbol,
      uniprot_acc: t.uniprot_acc,
      class: t.class,
      truth_verdict: t.truth_verdict,
      truth_signal: t.truth_signal,
      truth_reason: t.truth_reason,
      db: db
        ? {
            uniprot: db.uniprot, go: db.go, surfy: db.surfy,
            cspa: db.cspa, hpa: db.hpa,
          }
        : null,
      n_db_surface: db?.n_sources_surface ?? 0,
      verdicts,
    };
    return row;
  });

  return json(
    {
      bench_version: benchVersion,
      universe_version: universeVersion,
      generated_at: new Date().toISOString(),
      sources: BENCH_MATRIX_SOURCES,
      models: BENCH_MATRIX_MODELS,
      variants: BENCH_MATRIX_VARIANTS,
      headline_variant: BENCH_MATRIX_HEADLINE_VARIANT,
      n_genes: rows.length,
      rows,
    },
    { ttl: CACHE_TTL_LONG },
  );
}


// Long-format TSV export — the single source of truth for figure
// reproduction and the triage-with-reasoning Zenodo deposit file.
// One row per (gene × model × variant × replicate) for a given run_id,
// with per-source DB votes and uniprot_acc joined in server-side from
// the latest candidate-universe snapshot.
//
// Columns: gene_symbol / uniprot_acc / db_uniprot / db_go / db_surfy /
// db_cspa / db_hpa / n_db_surface / model / prompt_variant / replicate
// / predicted_verdict / predicted_reason / predicted_confidence /
// prompt_tokens / completion_tokens / cache_creation_tokens /
// cache_read_tokens / n_web_searches / cost_usd / latency_s.
//
// LEFT JOIN preserves triage rows even for genes that aren't in the
// current universe snapshot (db columns come out blank for those).
const EXPORT_COLUMNS = [
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
];
const DEFAULT_EXPORT_RUN_ID = "mainbench_canonical_v1";

async function handleTriageExport(env, url) {
  const runId = url.searchParams.get("run_id") || DEFAULT_EXPORT_RUN_ID;
  const replicate = url.searchParams.get("replicate");

  // Pin DB votes to the latest universe_version (same rule the
  // catalog handler uses).
  const releaseRow = await env.DB.prepare(
    `SELECT universe_version FROM candidate_universe_release
      ORDER BY loaded_at DESC LIMIT 1`
  ).first();
  const universeVersion = releaseRow?.universe_version ?? "";

  const sqlParts = [
    `SELECT t.gene_symbol, c.uniprot_acc,`,
    `       COALESCE(c.uniprot_surface_flag, 0) AS db_uniprot,`,
    `       COALESCE(c.go_surface_flag, 0)      AS db_go,`,
    `       COALESCE(c.surfy_surface_flag, 0)   AS db_surfy,`,
    `       COALESCE(c.cspa_surface_flag, 0)    AS db_cspa,`,
    `       COALESCE(c.hpa_surface_flag, 0)     AS db_hpa,`,
    `       COALESCE(c.n_sources_surface, 0)    AS n_db_surface,`,
    `       ${EXPORT_COLUMNS.slice(1).map((c) => `t.${c}`).join(", ")}`,
    `  FROM triage_run_public t`,
    `  LEFT JOIN candidate_universe_public c`,
    `         ON c.gene_symbol = t.gene_symbol`,
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
    "gene_symbol", "uniprot_acc",
    "db_uniprot", "db_go", "db_surfy", "db_cspa", "db_hpa", "n_db_surface",
    ...EXPORT_COLUMNS.slice(1),
  ];
  const headers = cols.join("\t");
  const body = rs.results
    .map((r) => cols.map((c) => tsvCell(r[c])).join("\t"))
    .join("\n");
  return tsv(`${headers}\n${body}\n`, { ttl: CACHE_TTL_LONG });
}


// Long-format TSV: every benchmark gene × every model × every variant
// (latest replicate per cell), with curated truth labels and per-
// source DB votes joined in. Same data as `/v1/benchmark/matrix` but
// reshaped from wide nested JSON to long flat TSV. Drives the
// triage-benchmark-with-reasoning Zenodo deposit file.
//
// Replaces an earlier truth-labels-only version of this endpoint —
// truth labels alone are still available as the truth_* columns here,
// or as the `/v1/benchmark[/{symbol}]` JSON endpoints.
async function handleBenchmarkExport(env) {
  // 1. Canonical curated bench_version (same rule as the matrix
  // handler — most labeled rows wins).
  const benchRow = await env.DB.prepare(
    `SELECT bench_version FROM benchmark_version
      WHERE truth_verdict IS NOT NULL AND truth_verdict != ''
      GROUP BY bench_version
      ORDER BY COUNT(*) DESC, MAX(created_at) DESC
      LIMIT 1`
  ).first();
  if (!benchRow) {
    return tsv("gene_symbol\n", { ttl: CACHE_TTL_LONG });
  }
  const benchVersion = benchRow.bench_version;

  // 2. Truth + DB + model output, joined inside SQL so a single round-
  // trip returns everything. LEFT JOIN on candidate_universe_public
  // so bench rows without a current-universe entry still appear (db
  // columns come out 0).
  const releaseRow = await env.DB.prepare(
    `SELECT universe_version FROM candidate_universe_release
      ORDER BY loaded_at DESC LIMIT 1`
  ).first();
  const universeVersion = releaseRow?.universe_version ?? "";

  const variantPlaceholders = BENCH_MATRIX_VARIANTS.map(() => "?").join(",");
  const modelPlaceholders = BENCH_MATRIX_MODELS.map(() => "?").join(",");
  const rs = await env.DB.prepare(
    `WITH ranked AS (
       SELECT t.gene_symbol, t.model, t.prompt_variant, t.replicate,
              t.predicted_verdict, t.predicted_reason, t.predicted_confidence,
              t.prompt_tokens, t.completion_tokens,
              t.cache_creation_tokens, t.cache_read_tokens,
              t.n_web_searches, t.cost_usd, t.latency_s,
              ROW_NUMBER() OVER (
                PARTITION BY t.gene_symbol, t.model, t.prompt_variant
                ORDER BY t.created_at DESC
              ) AS rn
         FROM triage_run_public t
         INNER JOIN benchmark_version bv ON bv.gene_symbol = t.gene_symbol
        WHERE bv.bench_version = ?
          AND t.prompt_variant IN (${variantPlaceholders})
          AND t.model IN (${modelPlaceholders})
     )
     SELECT r.gene_symbol, bv.uniprot_acc,
            COALESCE(c.uniprot_surface_flag, 0) AS db_uniprot,
            COALESCE(c.go_surface_flag, 0)      AS db_go,
            COALESCE(c.surfy_surface_flag, 0)   AS db_surfy,
            COALESCE(c.cspa_surface_flag, 0)    AS db_cspa,
            COALESCE(c.hpa_surface_flag, 0)     AS db_hpa,
            COALESCE(c.n_sources_surface, 0)    AS n_db_surface,
            bv.truth_verdict, bv.truth_signal, bv.truth_reason,
            r.model, r.prompt_variant, r.replicate,
            r.predicted_verdict, r.predicted_reason, r.predicted_confidence,
            r.prompt_tokens, r.completion_tokens,
            r.cache_creation_tokens, r.cache_read_tokens,
            r.n_web_searches, r.cost_usd, r.latency_s
       FROM ranked r
       INNER JOIN benchmark_version bv
               ON bv.gene_symbol = r.gene_symbol AND bv.bench_version = ?
       LEFT  JOIN candidate_universe_public c
               ON c.gene_symbol = r.gene_symbol AND c.universe_version = ?
      WHERE r.rn = 1
      ORDER BY r.gene_symbol, r.model, r.prompt_variant`
  ).bind(
    benchVersion,
    ...BENCH_MATRIX_VARIANTS, ...BENCH_MATRIX_MODELS,
    benchVersion, universeVersion,
  ).all();

  const cols = [
    "gene_symbol", "uniprot_acc",
    "db_uniprot", "db_go", "db_surfy", "db_cspa", "db_hpa", "n_db_surface",
    "truth_verdict", "truth_signal", "truth_reason",
    "model", "prompt_variant", "replicate",
    "predicted_verdict", "predicted_reason", "predicted_confidence",
    "prompt_tokens", "completion_tokens",
    "cache_creation_tokens", "cache_read_tokens",
    "n_web_searches", "cost_usd", "latency_s",
  ];
  const headers = cols.join("\t");
  const body = rs.results
    .map((r) => cols.map((c) => tsvCell(r[c])).join("\t"))
    .join("\n");
  return tsv(`${headers}\n${body}\n`, { ttl: CACHE_TTL_LONG });
}


async function handleTriage(env, symbol) {
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
    if (path === "/v1/benchmark/matrix") return handleBenchmarkMatrix(env);
    if (path === "/v1/benchmark/export.tsv") return handleBenchmarkExport(env);
    if (path === "/v1/triage/export.tsv") return handleTriageExport(env, url);

    let m;
    if ((m = path.match(/^\/v1\/genes\/([^/]+)$/))) return handleGene(env, m[1]);
    if ((m = path.match(/^\/v1\/orthologs\/([^/]+)$/))) return handleOrthologs(env, m[1]);
    if ((m = path.match(/^\/v1\/benchmark\/([^/]+)$/))) return handleBenchmarkOne(env, m[1]);
    if ((m = path.match(/^\/v1\/triage\/([^/]+)$/))) return handleTriage(env, m[1]);

    return notFound("route_not_found");
  },
};
