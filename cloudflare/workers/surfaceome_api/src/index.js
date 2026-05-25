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
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
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

  // SURFACE-Bind per-UniProt site counts (Marchand 2026 PNAS).
  // Three-state value semantics — see viewer/lib/surfaceome.ts:
  //   `null` (omitted from row entirely) — UniProt not in surface_bind_protein
  //     (filtered out at SURFACE-Bind's structural QC step)
  //   `0` — scored but no surface patches cleared the MaSIF
  //     targetability threshold
  //   `N > 0` — number of scored targetable patches
  // The filter chip group in the catalog page reads this directly.
  // ``surface_bind_protein`` is mirrored from
  // ``scripts/sync_surface_bind_to_d1.py``; the join is keyed on
  // UniProt acc so the lookup is O(1) per row.
  const sbByAcc = new Map();
  try {
    // Column name in the D1 mirror is ``uniprot_acc`` (matches the
    // pydantic field), NOT ``acc`` (which is the source CSV's name).
    const sbRows = await env.DB.prepare(
      `SELECT uniprot_acc, n_sites FROM surface_bind_protein`
    ).all();
    for (const r of sbRows.results) {
      if (r.uniprot_acc) sbByAcc.set(r.uniprot_acc, r.n_sites ?? 0);
    }
  } catch (e) {
    // Table doesn't exist yet (D1 mirror hasn't synced) — degrade
    // gracefully; rows just won't carry the ``sb`` field.
    console.warn("surface_bind_protein lookup failed:", e?.message ?? e);
  }

  // HGNC ID lookup keyed on the authoritative hgnc_symbol. Lets us
  // attach hgnc_id to every catalog row so external reanalysts can
  // cross-reference any other HGNC-keyed table without re-resolving
  // from the (fragile) gene symbol — see CLAUDE.md "Gene identifier
  // resolution". ~190 KB on the wire for 19k rows; small relative to
  // the catalog's 5 MB payload.
  const hgncByGene = new Map();
  const hgncRows = await env.DB.prepare(
    `SELECT hgnc_symbol, hgnc_id FROM gene_identifier_public
      WHERE hgnc_id IS NOT NULL AND hgnc_id != ''`
  ).all();
  for (const r of hgncRows.results) {
    if (r.hgnc_symbol && r.hgnc_id) {
      hgncByGene.set(r.hgnc_symbol, r.hgnc_id);
    }
  }

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
    const hgnc = hgncByGene.get(u.gene_symbol);
    if (hgnc) row.hgnc_id = hgnc;
    const t = packTriage(u.gene_symbol);
    if (t) row.tr = t;
    if (deepSet.has(u.gene_symbol)) row.deep_dive = true;
    if (u.uniprot_acc && sbByAcc.has(u.uniprot_acc)) {
      row.sb = sbByAcc.get(u.uniprot_acc);
    }
    return row;
  });

  // Append deep-dive-only genes (missing from the universe row set).
  for (const sym of deepSet) {
    if (covered.has(sym)) continue;
    const row = { symbol: sym, n_sources: 0, db: 0, deep_dive: true };
    const hgnc = hgncByGene.get(sym);
    if (hgnc) row.hgnc_id = hgnc;
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
      // accordingly.
      //   v3 = per-model ncbi `tr` array replaces single `triage`.
      //   v4 = optional `sb` (SURFACE-Bind site count) added.
      row_schema: 4,
      // Names for the bits in each row's `db` 5-bit field (LSB → MSB).
      // Self-describing for external reanalysts: decode with
      //   const flags = db_keys.map((_, i) => (row.db >> i) & 1);
      // Matches the encoding above + viewer/lib/surfaceome.ts.
      db_keys: ["uniprot", "go", "surfy", "cspa", "hpa"],
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


// === Feedback flow helpers ================================================
// All functions in this block support the three /v1/feedback/* endpoints
// added below. They never leak PII or unsanitized HTML across the
// public/private boundary.

// Hex-encode an ArrayBuffer or Uint8Array.
function toHex(buf) {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Base64url (no padding) — safe to put in a URL.
function toBase64Url(buf) {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// HMAC-SHA256(secret, message) → base64url.
async function hmacSign(secret, message) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return toBase64Url(sig);
}

// Constant-time compare for base64url-or-hex strings of equal length.
function timingSafeEqualStr(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}

// SHA-256(text) → hex.
async function sha256Hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return toHex(buf);
}

// Strip HTML tags and normalize whitespace. Comments render as plaintext
// in the viewer (no dangerouslySetInnerHTML), so this is defense-in-depth.
function sanitizeComment(s) {
  return String(s ?? "")
    .replace(/<[^>]*>/g, "")
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .trim()
    .slice(0, 4000);
}

// Cheap email-shape check. Real validation lives at the auth layer
// (we never auto-trust the address); this is just "does it look like
// an email at all".
function looksLikeEmail(s) {
  return typeof s === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
}

// HTML-escape a string for safe embedding in the moderate-confirmation
// page and the Resend email body.
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Verify a Cloudflare Turnstile token against the siteverify endpoint.
// Returns true on success, false on failure (does NOT throw — caller
// decides response code).
async function verifyTurnstile(token, secret, remoteIp) {
  if (!token || !secret) return false;
  const body = new URLSearchParams({ secret, response: token });
  if (remoteIp) body.set("remoteip", remoteIp);
  try {
    const r = await fetch(
      "https://challenges.cloudflare.com/turnstile/v0/siteverify",
      { method: "POST", body },
    );
    const j = await r.json();
    return !!j.success;
  } catch {
    return false;
  }
}

// Rate-limit per IP-hash. Returns true if under the limit, false if over.
// Window: 1 hour, max: 5 submissions. KV is eventually consistent — that
// is acceptable here (bursts of 6-10 once an hour aren't a real DoS).
async function checkRateLimit(kv, ipHash) {
  const key = `rl:${ipHash}:${Math.floor(Date.now() / 3600_000)}`; // hour bucket
  const v = await kv.get(key);
  const n = v ? parseInt(v, 10) : 0;
  if (n >= 5) return false;
  await kv.put(key, String(n + 1), { expirationTtl: 3600 });
  return true;
}

// Send the feedback notification email via Resend. Returns true on
// success, false on failure (the caller still 200's the submission —
// we don't lose the row just because email is slow).
async function sendFeedbackEmail({ apiKey, from, to, replyTo, subject, html }) {
  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from,
        to: [to],
        reply_to: replyTo ? [replyTo] : undefined,
        subject,
        html,
      }),
    });
    if (!r.ok) {
      console.error("Resend send failed:", r.status, await r.text());
      return false;
    }
    return true;
  } catch (err) {
    console.error("Resend send error:", err);
    return false;
  }
}

// Compose the email body sent to the maintainer.
function feedbackEmailHtml({ rec, base, approvePublicUrl, discardUrl }) {
  const additional = `
    <p><strong>Additional information</strong></p>
    <ul style="line-height: 1.5">
      <li>Referred from: <code>${escapeHtml(rec.referrer || "—")}</code></li>
      <li>User browser: <code>${escapeHtml(rec.user_agent || "—")}</code></li>
      <li>Website version: <code>${escapeHtml(rec.site_version || "—")}</code></li>
    </ul>
  `;
  const publicBtn = rec.public_requested
    ? `<a href="${approvePublicUrl}"
          style="background:#922038;color:#fff;padding:0.7em 1.2em;
                 border-radius:999px;text-decoration:none;
                 display:inline-block;margin-right:0.6em;">
         Approve as public
       </a>`
    : "";
  return `
    <div style="font-family:system-ui,sans-serif;color:#1f1718;
                max-width:640px;margin:0 auto;line-height:1.55">
      <h2 style="margin-top:0">New feedback for ${escapeHtml(rec.gene_symbol)}</h2>
      <p style="color:#6f5d5a;margin:0 0 1em">
        From <strong>${escapeHtml(rec.submitter_name)}</strong>
        &lt;${escapeHtml(rec.submitter_email)}&gt;
      </p>
      <p><strong>Subject:</strong> ${escapeHtml(rec.subject)}</p>
      <p style="white-space:pre-wrap;border-left:3px solid #e5ded3;
                padding-left:1em;color:#1f1718">
        ${escapeHtml(rec.comment)}
      </p>
      ${additional}
      <p style="margin-top:2em">
        ${publicBtn}
        <a href="${discardUrl}"
           style="color:#6f5d5a;text-decoration:underline;
                  display:inline-block;padding:0.7em 0">
          Discard
        </a>
      </p>
      <p style="color:#80706a;font-size:0.85em;margin-top:2em">
        Reply directly to this e-mail to respond to the submitter
        (their address is set as Reply-To).
      </p>
    </div>
  `;
}

async function handleFeedbackSubmit(request, env, url) {
  // Parse + validate body.
  let body;
  try {
    body = await request.json();
  } catch {
    return badRequest("invalid_json");
  }
  const gene = String(body.gene ?? "").trim();
  if (!/^[A-Z0-9-]{1,30}$/.test(gene)) return badRequest("invalid_gene");
  const name = String(body.name ?? "").trim();
  if (name.length < 1 || name.length > 80) return badRequest("invalid_name");
  const email = String(body.email ?? "").trim();
  if (!looksLikeEmail(email)) return badRequest("invalid_email");
  const subject = String(body.subject ?? "").trim();
  if (subject.length < 1 || subject.length > 200) return badRequest("invalid_subject");
  const comment = String(body.comment ?? "").trim();
  if (comment.length < 1 || comment.length > 4000) return badRequest("invalid_comment");

  // Turnstile.
  const tToken = String(body.turnstile_token ?? "");
  const remoteIp = request.headers.get("CF-Connecting-IP") ?? null;
  const ok = await verifyTurnstile(tToken, env.TURNSTILE_SECRET_KEY, remoteIp);
  if (!ok) return badRequest("turnstile_failed");

  // Rate-limit by IP-hash (per day salt = today's UTC date).
  const day = new Date().toISOString().slice(0, 10);
  const ipHash = await sha256Hex(`${remoteIp ?? "0"}|${day}`);
  const under = await checkRateLimit(env.FEEDBACK_RATELIMIT, ipHash);
  if (!under) {
    return json({ error: "rate_limited" }, { status: 429, ttl: 0 });
  }

  // Insert.
  const id = crypto.randomUUID();
  const approveToken = await hmacSign(env.MAGIC_LINK_SECRET, id);
  const publicRequested = body.public_requested ? 1 : 0;
  await env.FEEDBACK_DB.prepare(
    `INSERT INTO feedback (
       id, gene_symbol, uniprot_acc, submitter_name, submitter_email,
       subject, comment, public_requested, referrer, user_agent,
       site_version, ip_hash, approve_token
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).bind(
    id, gene,
    String(body.uniprot_acc ?? "") || null,
    name, email, subject, comment, publicRequested,
    String(body.referrer ?? "") || null,
    String(body.user_agent ?? "") || null,
    String(body.site_version ?? "") || null,
    ipHash, approveToken,
  ).run();

  // Email notify maintainer.
  const base = `${url.protocol}//${url.host}`;
  const approvePublicUrl =
    `${base}/v1/feedback/moderate?id=${encodeURIComponent(id)}` +
    `&action=public&t=${encodeURIComponent(await hmacSign(env.MAGIC_LINK_SECRET, id + ":public"))}`;
  const discardUrl =
    `${base}/v1/feedback/moderate?id=${encodeURIComponent(id)}` +
    `&action=discard&t=${encodeURIComponent(await hmacSign(env.MAGIC_LINK_SECRET, id + ":discard"))}`;

  await sendFeedbackEmail({
    apiKey: env.RESEND_API_KEY,
    from: env.MAINTAINER_EMAIL,
    to: env.MAINTAINER_EMAIL,
    replyTo: email,
    subject,
    html: feedbackEmailHtml({
      rec: {
        gene_symbol: gene, submitter_name: name, submitter_email: email,
        subject, comment, public_requested: publicRequested,
        referrer: String(body.referrer ?? ""),
        user_agent: String(body.user_agent ?? ""),
        site_version: String(body.site_version ?? ""),
      },
      base, approvePublicUrl, discardUrl,
    }),
  });

  return json({ ok: true, id }, { status: 200, ttl: 0 });
}

// HTML confirmation page (no JS — just shows the outcome).
function moderateHtmlPage({ title, message, accent = "#922038" }) {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><title>${escapeHtml(title)}</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:560px;margin:6em auto;
       padding:0 1em;color:#1f1718;line-height:1.55}
  h1{font-size:1.4rem;color:${accent};margin-bottom:0.3em}
  p{color:#6f5d5a}
  .hint{font-size:0.85em;color:#80706a;margin-top:2em}
</style></head>
<body>
  <h1>${escapeHtml(title)}</h1>
  <p>${escapeHtml(message)}</p>
  <p class="hint">You can close this tab.</p>
</body></html>`;
}

function htmlResponse(content, { status = 200 } = {}) {
  return new Response(content, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      ...CORS_HEADERS,
    },
  });
}

async function handleFeedbackModerate(env, url) {
  const id = url.searchParams.get("id");
  const action = url.searchParams.get("action");
  const t = url.searchParams.get("t");
  if (!id || !action || !t) {
    return htmlResponse(
      moderateHtmlPage({
        title: "Invalid link",
        message: "This moderation link is missing required parameters.",
      }),
      { status: 400 },
    );
  }
  if (action !== "public" && action !== "discard") {
    return htmlResponse(
      moderateHtmlPage({
        title: "Invalid link",
        message: "Unknown action.",
      }),
      { status: 400 },
    );
  }
  const expected = await hmacSign(env.MAGIC_LINK_SECRET, `${id}:${action}`);
  if (!timingSafeEqualStr(expected, t)) {
    return htmlResponse(
      moderateHtmlPage({
        title: "Invalid link",
        message: "This link is invalid or has been tampered with.",
      }),
      { status: 403 },
    );
  }

  const row = await env.FEEDBACK_DB.prepare(
    "SELECT id, gene_symbol, submitter_name, comment, status FROM feedback WHERE id = ?",
  ).bind(id).first();
  if (!row) {
    return htmlResponse(
      moderateHtmlPage({
        title: "Not found",
        message: "We couldn't find that submission.",
      }),
      { status: 404 },
    );
  }
  if (row.status !== "pending") {
    return htmlResponse(
      moderateHtmlPage({
        title: "Already handled",
        message: `This submission was already marked "${row.status}".`,
      }),
    );
  }

  if (action === "discard") {
    await env.FEEDBACK_DB.prepare(
      "UPDATE feedback SET status = 'discarded', moderated_at = datetime('now') WHERE id = ?",
    ).bind(id).run();
    return htmlResponse(
      moderateHtmlPage({
        title: "Discarded",
        message: `The submission about ${row.gene_symbol} from ${row.submitter_name} has been discarded.`,
        accent: "#6f5d5a",
      }),
    );
  }

  // action === 'public' — copy sanitized subset to public DB, then mark approved.
  const sanitized = sanitizeComment(row.comment);
  await env.DB.prepare(
    `INSERT OR IGNORE INTO feedback_public (id, gene_symbol, submitter_name, comment)
     VALUES (?, ?, ?, ?)`,
  ).bind(row.id, row.gene_symbol, row.submitter_name, sanitized).run();
  await env.FEEDBACK_DB.prepare(
    "UPDATE feedback SET status = 'approved_public', moderated_at = datetime('now') WHERE id = ?",
  ).bind(id).run();
  return htmlResponse(
    moderateHtmlPage({
      title: "Approved & published",
      message: `${row.submitter_name}'s note on ${row.gene_symbol} is now visible on the gene page.`,
    }),
  );
}

async function handleFeedbackPublic(env, url) {
  const gene = url.searchParams.get("gene");
  if (!gene || !/^[A-Z0-9-]{1,30}$/.test(gene)) {
    return badRequest("invalid_gene");
  }
  const rows = await env.DB.prepare(
    `SELECT id, submitter_name, comment, approved_at
     FROM feedback_public
     WHERE gene_symbol = ?
     ORDER BY approved_at DESC
     LIMIT 50`,
  ).bind(gene).all();
  return json({ gene, notes: rows.results }, { ttl: CACHE_TTL_SHORT });
}

// --- entry ----------------------------------------------------------------

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          ...CORS_HEADERS,
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        },
      });
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

    // POST is allowed ONLY on the feedback submit endpoint.
    if (request.method === "POST") {
      if (path === "/v1/feedback/submit") {
        return handleFeedbackSubmit(request, env, url);
      }
      return json({ error: "method_not_allowed" }, { status: 405, ttl: 0 });
    }
    if (request.method !== "GET") {
      return json({ error: "method_not_allowed" }, { status: 405, ttl: 0 });
    }

    if (path === "/v1/health") return handleHealth(env);
    if (path === "/v1/genes") return handleGeneList(env);
    if (path === "/v1/catalog") return handleCatalog(env);
    if (path === "/v1/benchmark") return handleBenchmarkList(env);
    if (path === "/v1/benchmark/matrix") return handleBenchmarkMatrix(env);
    if (path === "/v1/benchmark/export.tsv") return handleBenchmarkExport(env);
    if (path === "/v1/triage/export.tsv") return handleTriageExport(env, url);
    if (path === "/v1/feedback/moderate") return handleFeedbackModerate(env, url);
    if (path === "/v1/feedback/public") return handleFeedbackPublic(env, url);

    let m;
    if ((m = path.match(/^\/v1\/genes\/([^/]+)$/))) return handleGene(env, m[1]);
    if ((m = path.match(/^\/v1\/orthologs\/([^/]+)$/))) return handleOrthologs(env, m[1]);
    if ((m = path.match(/^\/v1\/benchmark\/([^/]+)$/))) return handleBenchmarkOne(env, m[1]);
    if ((m = path.match(/^\/v1\/triage\/([^/]+)$/))) return handleTriage(env, m[1]);

    return notFound("route_not_found");
  },
};
