// SurfaceBench truth labels, 147-gene matrix, and TSV export.

import { CACHE_TTL_LONG, CACHE_TTL_SHORT, badRequest, checkSymbol, json, notFound, tsv, tsvCell } from "../lib/http.js";

export async function handleBenchmarkList(env) {
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

export async function handleBenchmarkOne(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  const row = await env.DB.prepare(
    `SELECT bench_version, gene_symbol, uniprot_acc, class,
            truth_verdict, truth_signal, truth_reason, rationale
       FROM benchmark_version
      WHERE gene_symbol = ? COLLATE NOCASE
      ORDER BY bench_version DESC
      LIMIT 1`
  ).bind(sym).first();
  if (!row) return notFound("not_in_benchmark");
  return json(row, { ttl: CACHE_TTL_LONG });
}

// Slim per-row projection of SurfaceomeRecord.filters — only the fields
// the catalog UI offers as filter controls. Returns null on parse error
// or missing filters block so the caller can decide whether to omit
// the `ddf` field entirely (keeps wire size bounded — null entries
// would inflate every deep-dive-less row).
//
// Schema kept in sync with viewer/lib/surfaceome.ts `DeepDiveFilters`
// interface — both must list the same 21 keys. Continuous fields
// (max_paralog_ecd_pct_identity, ortholog identities) are deliberately
// excluded because the catalog filter UI doesn't expose them yet
// (range sliders are a UI-complexity bump for later). The
// `has_restricted_subdomain` boolean moved to the Biology card per
// the v1 schema split and is excluded here too.

// grid per the user request 2026-05-15). `headline_variant` is still
// returned for consumers that want to highlight one column.
export const BENCH_MATRIX_MODELS = [
  "claude-opus-4-8",
  "claude-sonnet-4-6",
  "claude-haiku-4-5",
  "claude-sonnet-5",
  "claude-opus-5",
  "claude-haiku-5-5",
  "claude-sonnet-5-5",
  "claude-opus-5-5",
];
// ncbi_effort_low = the ncbi prompt at output_config.effort="low" (Opus 5.5
// only, whose thinking cannot be disabled).
export const BENCH_MATRIX_VARIANTS = ["naive", "ncbi", "web_ncbi", "pubmed_ncbi", "ncbi_effort_low"];
export const BENCH_MATRIX_HEADLINE_VARIANT = "ncbi";
// The run that holds every SurfaceBench cell (all models x variants x 3
// replicates, scored against the bench truth). The bench genes are also
// in the genome-wide Sonnet sweeps and the PubMed rescue lanes, which
// write the same (gene, claude-sonnet-4-6, ncbi | pubmed_ncbi) cells with
// correct = 0 (those runs have no truth to score against) and a later
// created_at, so every benchmark query must pin to this run_id or the
// genome-run rows land in the bench cells.
export const BENCH_RUN_ID = "mainbench_canonical_v2";
// Five gating DBs — same five the homepage CatalogTable renders. The
// matrix used to expose two auxiliary signals (DeepTMHMM, COMPARTMENTS)
// but those were demoted from the M1 universe gate and only confused
// the side-by-side, so we drop them here too (2026-05-15).
export const BENCH_MATRIX_SOURCES = [
  "uniprot", "go", "surfy", "cspa", "hpa",
];

// --- SurfaceBench cell aggregation ----------------------------------------
// Every (gene, model, variant) cell of the bench run has three replicates.
// The paper and data/processed/triage_bench/mainbench_canonical_v2.tsv score
// each cell by its MAJORITY verdict, so the matrix, the export TSV and the
// per-cell drawer all do the same. This is a line-for-line port of
// `_collapse_to_majority` in scripts/tsv-export/export_mainbench_to_tsv.py;
// change both together (tests/test_worker_benchmark_majority.py replays the
// committed replicate TSV through this code and diffs it against the
// committed majority TSV).
//
//   - Only replicates with a yes / contextual / no verdict vote. A refused
//     or errored replicate (null verdict) is out of the vote and out of
//     n_reps, so a cell with one refusal is a majority of the other two.
//   - The binary surface vote decides the side (yes and contextual both
//     vote surface), then the most common raw verdict on that side is the
//     cell's verdict, then the most common reason and the most common
//     confidence among replicates carrying that verdict.
//   - Every tie goes to the value seen first in replicate order, which is
//     what Python's Counter.most_common does on the replicate-ordered rows.
//   - A cell with no valid replicate has no verdict and is not scored.
//   - `totals` sums telemetry over ALL the cell's replicates, refused ones
//     included, exactly like the TSV's token / cost / latency columns.
//
// The per-call fields (reasoning, latency, cost, tokens) describe one
// representative replicate: the lowest-numbered replicate carrying the
// majority verdict and reason, so the reasoning shown next to a verdict is
// a replicate that actually made that call.

export function benchSurfaceVote(verdict) {
  if (verdict === "yes" || verdict === "contextual") return true;
  if (verdict === "no") return false;
  return null;
}

// Most common value; ties go to the first one seen (Counter.most_common).
export function benchModeFirstSeen(values) {
  const tally = new Map();
  for (const v of values) tally.set(v, (tally.get(v) || 0) + 1);
  let best = null;
  let bestN = 0;
  for (const [v, n] of tally) {
    if (n > bestN) {
      best = v;
      bestN = n;
    }
  }
  return best;
}

// Soft credit, as in the figures' is_match: yes and contextual agree with
// each other, no agrees only with no.
export function benchSoftMatch(predicted, truth) {
  if (!predicted || !truth) return 0;
  if (predicted === truth) return 1;
  return benchSurfaceVote(predicted) === true && benchSurfaceVote(truth) === true ? 1 : 0;
}

// `reps` = one cell's replicates in ascending replicate order. Returns null
// when no replicate carries a verdict.
export function benchCellMajority(reps) {
  const valid = reps.filter((r) => benchSurfaceVote(r.predicted_verdict) !== null);
  if (!valid.length) return null;
  const winSide = benchModeFirstSeen(valid.map((r) => benchSurfaceVote(r.predicted_verdict)));
  const winReps = valid.filter((r) => benchSurfaceVote(r.predicted_verdict) === winSide);
  const verdict = benchModeFirstSeen(winReps.map((r) => r.predicted_verdict));
  const sameVerdict = winReps.filter((r) => r.predicted_verdict === verdict);
  const modal = (col) => {
    const vals = sameVerdict.map((r) => r[col]).filter((v) => v);
    return vals.length ? benchModeFirstSeen(vals) : null;
  };
  const reason = modal("predicted_reason");
  const confidence = modal("predicted_confidence");
  const rep = sameVerdict.find((r) => reason == null || r.predicted_reason === reason) ?? sameVerdict[0];
  return {
    verdict,
    reason,
    confidence,
    rep,
    n_reps: valid.length,
    agreement: Math.round((winReps.length / valid.length) * 1000) / 1000,
  };
}

export const BENCH_TOTAL_COLUMNS = [
  "prompt_tokens", "completion_tokens", "cache_creation_tokens",
  "cache_read_tokens", "n_web_searches", "cost_usd", "latency_s",
];

// Python 3.12+ sum() over floats is Neumaier-compensated, and the TSV's
// totals come from it; a naive loop lands one ulp away often enough to flip
// the sixth decimal of a cost. Same algorithm as CPython's builtin_sum.
export function benchFsum(rows, col) {
  let sum = 0;
  let c = 0;
  for (const r of rows) {
    const x = Number(r[col]) || 0;
    const t = sum + x;
    c += Math.abs(sum) >= Math.abs(x) ? (sum - t) + x : (x - t) + sum;
    sum = t;
  }
  return c && Number.isFinite(c) ? sum + c : sum;
}

export function benchCellTotals(reps) {
  const totals = {};
  for (const col of BENCH_TOTAL_COLUMNS) {
    const sum = benchFsum(reps, col);
    // toFixed rounds the exact binary value, as Python's round() does;
    // Math.round(sum * 1e6) would round the already-perturbed product.
    if (col === "cost_usd") totals[col] = Number(sum.toFixed(6));
    else if (col === "latency_s") totals[col] = Number(sum.toFixed(3));
    else totals[col] = Math.trunc(sum);
  }
  return totals;
}

// Read the bench run's replicates for the bench genes and aggregate them to
// one entry per cell: Map "gene\tmodel\tvariant" -> cell. A cell's `rep` is
// its representative replicate row (the latest replicate for a cell with no
// verdict, so its `error` says why). The light columns of all ~8k replicate
// rows come back in one query; the free-text fields are fetched in a second
// query for the representative replicates only, so the Worker never pulls
// three copies of every reasoning string out of D1.
export async function loadBenchCells(env, benchVersion, { withText = false } = {}) {
  const variantPlaceholders = BENCH_MATRIX_VARIANTS.map(() => "?").join(",");
  const modelPlaceholders = BENCH_MATRIX_MODELS.map(() => "?").join(",");
  const repRows = await env.DB.prepare(
    `SELECT t.id, t.gene_symbol, t.model, t.prompt_variant, t.replicate,
            t.predicted_verdict, t.predicted_reason, t.predicted_confidence,
            t.latency_s, t.n_web_searches, t.created_at, t.error,
            t.cost_usd, t.prompt_tokens, t.completion_tokens,
            t.cache_creation_tokens, t.cache_read_tokens
       FROM triage_run_public t
      WHERE t.run_id = ?
        AND t.gene_symbol IN (
              SELECT gene_symbol FROM benchmark_version WHERE bench_version = ?)
        AND t.prompt_variant IN (${variantPlaceholders})
        AND t.model IN (${modelPlaceholders})
      ORDER BY t.gene_symbol, t.model, t.prompt_variant, t.replicate,
               t.created_at DESC`
  ).bind(BENCH_RUN_ID, benchVersion, ...BENCH_MATRIX_VARIANTS, ...BENCH_MATRIX_MODELS).all();

  // Group by cell, keeping one row per replicate number (the latest), the
  // same guard handleTriageCell applies against a duplicate-replicate sync.
  const byCell = new Map();
  for (const r of repRows.results) {
    const key = `${r.gene_symbol}\t${r.model}\t${r.prompt_variant}`;
    let reps = byCell.get(key);
    if (!reps) {
      reps = [];
      byCell.set(key, reps);
    }
    const last = reps[reps.length - 1];
    if (last && last.replicate === r.replicate) continue;
    reps.push(r);
  }

  const cells = new Map();
  for (const [key, reps] of byCell) {
    const maj = benchCellMajority(reps);
    let rep = maj?.rep;
    if (!rep) {
      rep = reps[0];
      for (const r of reps) if ((r.created_at || "") > (rep.created_at || "")) rep = r;
    }
    cells.set(key, { reps, maj, rep, totals: benchCellTotals(reps) });
  }

  if (withText && cells.size) {
    const ids = [...cells.values()].map((c) => c.rep.id);
    const textRows = await env.DB.prepare(
      `SELECT id, predicted_key_uncertainty, verdict_reasoning
         FROM triage_run_public
        WHERE id IN (SELECT value FROM json_each(?))`
    ).bind(JSON.stringify(ids)).all();
    const textById = new Map(textRows.results.map((r) => [r.id, r]));
    for (const c of cells.values()) c.text = textById.get(c.rep.id) ?? null;
  }
  return cells;
}

export async function handleBenchmarkMatrix(env) {
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
      // SurfaceBench scores each database at its BEST — the recalibrated
      // cutoff — because that is what the accuracy figures compare the agent
      // against. Serving native flags here would have the benchmark table
      // disagree with the benchmark figures. Positive list: absent -> 0.
      `SELECT c.gene_symbol, c.uniprot_surface_flag, c.go_surface_flag,
              c.surfy_surface_flag, c.cspa_surface_flag, c.hpa_surface_flag,
              c.n_sources_surface,
              COALESCE(oc.uniprot_optimized, 0) AS uniprot_optimized,
              COALESCE(oc.cspa_optimized, 0) AS cspa_optimized
         FROM candidate_universe_public c
         LEFT JOIN db_optimized_cutoff_public oc ON oc.accession = c.uniprot_acc
        WHERE c.universe_version = ?`
    ).bind(universeVersion).all();
    for (const u of universeRows.results) {
      const upOpt = u.uniprot_optimized ? 1 : 0;
      const cspaOpt = u.cspa_optimized ? 1 : 0;
      const goFlag = u.go_surface_flag ? 1 : 0;
      const surfyFlag = u.surfy_surface_flag ? 1 : 0;
      const hpaFlag = u.hpa_surface_flag ? 1 : 0;
      dbByGene.set(u.gene_symbol, {
        uniprot: upOpt,
        go: goFlag,
        surfy: surfyFlag,
        cspa: cspaOpt,
        hpa: hpaFlag,
        n_sources_surface: upOpt + goFlag + surfyFlag + cspaOpt + hpaFlag,
      });
    }
  }

  // 4. The bench run's replicates, aggregated to one majority verdict per
  // (gene, model, variant) cell — the same per-cell numbers the paper and
  // mainbench_canonical_v2.tsv report (see benchCellMajority). The cell
  // used to be the single latest replicate, which put the page a few
  // genes off the paper on several models. Pinned to BENCH_RUN_ID: the
  // genome-wide Sonnet sweep and the PubMed rescue lanes write the same
  // (gene, claude-sonnet-4-6, ncbi | pubmed_ncbi) cells with no truth to
  // score against.
  const cells = await loadBenchCells(env, benchVersion, { withText: true });

  // 5. Stitch. Flat verdicts dict: model → variant → cell (or null when
  // no replicate is on file). `correct` is the soft-credit match of the
  // majority verdict against truth; a cell with no valid replicate keeps
  // its refusal / error marker but has verdict and correct null, so it is
  // never scored. `replicate` names the representative replicate whose
  // reasoning and per-call telemetry the cell carries; `totals` sums the
  // telemetry over all the cell's replicates.
  const rows = truthRows.results.map((t) => {
    const verdicts = {};
    for (const model of BENCH_MATRIX_MODELS) {
      const perVariant = {};
      for (const variant of BENCH_MATRIX_VARIANTS) {
        const c = cells.get(`${t.gene_symbol}\t${model}\t${variant}`);
        if (!c) {
          perVariant[variant] = null;
          continue;
        }
        const { maj, rep, text } = c;
        perVariant[variant] = {
          verdict: maj ? maj.verdict : null,
          reason: maj ? maj.reason : null,
          confidence: maj ? maj.confidence : null,
          key_uncertainty: maj ? (text?.predicted_key_uncertainty ?? null) : null,
          reasoning: maj ? (text?.verdict_reasoning ?? null) : null,
          correct: maj ? benchSoftMatch(maj.verdict, t.truth_verdict) : null,
          latency_s: rep.latency_s,
          n_web_searches: rep.n_web_searches,
          created_at: rep.created_at,
          error: rep.error,
          cost_usd: rep.cost_usd,
          prompt_tokens: rep.prompt_tokens,
          completion_tokens: rep.completion_tokens,
          cache_creation_tokens: rep.cache_creation_tokens,
          cache_read_tokens: rep.cache_read_tokens,
          replicate: rep.replicate,
          n_reps: maj ? maj.n_reps : 0,
          majority_agreement: maj ? maj.agreement : null,
          totals: c.totals,
        };
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
      // Each cell is the majority across the run's replicates (refused
      // replicates excluded), as in the paper — not one replicate.
      cell_aggregation: "majority_of_replicates",
      run_id: BENCH_RUN_ID,
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

export const BENCH_EXPORT_COLUMNS = [
  "gene_symbol", "uniprot_acc",
  "db_uniprot", "db_go", "db_surfy", "db_cspa", "db_hpa", "n_db_surface",
  "truth_verdict", "truth_signal", "truth_reason",
  "model", "prompt_variant", "replicate",
  "predicted_verdict", "predicted_reason", "predicted_confidence",
  "prompt_tokens", "completion_tokens",
  "cache_creation_tokens", "cache_read_tokens",
  "n_web_searches", "cost_usd", "latency_s",
  // Additive (appended so existing column positions are unchanged).
  "n_reps", "majority_agreement", "is_match",
  ...BENCH_TOTAL_COLUMNS.map((c) => `${c}_total`),
];

export async function handleBenchmarkExport(env) {
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

  // 2. Per-gene truth + DB votes in one round-trip. LEFT JOIN on
  // candidate_universe_public so bench rows without a current-universe
  // entry still appear (db columns come out 0).
  const releaseRow = await env.DB.prepare(
    `SELECT universe_version FROM candidate_universe_release
      ORDER BY loaded_at DESC LIMIT 1`
  ).first();
  const universeVersion = releaseRow?.universe_version ?? "";
  const genes = await env.DB.prepare(
    `SELECT bv.gene_symbol, bv.uniprot_acc,
            COALESCE(oc.uniprot_optimized, 0)   AS db_uniprot,
            COALESCE(c.go_surface_flag, 0)      AS db_go,
            COALESCE(c.surfy_surface_flag, 0)   AS db_surfy,
            COALESCE(oc.cspa_optimized, 0)      AS db_cspa,
            COALESCE(c.hpa_surface_flag, 0)     AS db_hpa,
            COALESCE(oc.uniprot_optimized, 0) + COALESCE(c.go_surface_flag, 0)
              + COALESCE(c.surfy_surface_flag, 0) + COALESCE(oc.cspa_optimized, 0)
              + COALESCE(c.hpa_surface_flag, 0)  AS n_db_surface,
            bv.truth_verdict, bv.truth_signal, bv.truth_reason
       FROM benchmark_version bv
       LEFT JOIN candidate_universe_public c
              ON c.gene_symbol = bv.gene_symbol AND c.universe_version = ?
       LEFT JOIN db_optimized_cutoff_public oc
              ON oc.accession = bv.uniprot_acc
      WHERE bv.bench_version = ?
      ORDER BY bv.gene_symbol`
  ).bind(universeVersion, benchVersion).all();

  // 3. The majority-aggregated cells, emitted gene → model → variant.
  const cells = await loadBenchCells(env, benchVersion);
  const models = [...BENCH_MATRIX_MODELS].sort();
  const variants = [...BENCH_MATRIX_VARIANTS].sort();
  const lines = [];
  for (const g of genes.results) {
    for (const model of models) {
      for (const variant of variants) {
        const c = cells.get(`${g.gene_symbol}\t${model}\t${variant}`);
        if (!c) continue;
        const { maj, rep, totals } = c;
        const row = {
          ...g,
          model,
          prompt_variant: variant,
          replicate: rep.replicate,
          predicted_verdict: maj?.verdict ?? null,
          predicted_reason: maj?.reason ?? null,
          predicted_confidence: maj?.confidence ?? null,
          prompt_tokens: rep.prompt_tokens,
          completion_tokens: rep.completion_tokens,
          cache_creation_tokens: rep.cache_creation_tokens,
          cache_read_tokens: rep.cache_read_tokens,
          n_web_searches: rep.n_web_searches,
          cost_usd: rep.cost_usd,
          latency_s: rep.latency_s,
          n_reps: maj ? maj.n_reps : 0,
          majority_agreement: maj ? maj.agreement : null,
          is_match: maj ? benchSoftMatch(maj.verdict, g.truth_verdict) : null,
        };
        for (const col of BENCH_TOTAL_COLUMNS) row[`${col}_total`] = totals[col];
        lines.push(BENCH_EXPORT_COLUMNS.map((col) => tsvCell(row[col])).join("\t"));
      }
    }
  }
  const headers = BENCH_EXPORT_COLUMNS.join("\t");
  return tsv(`${headers}\n${lines.join("\n")}\n`, { ttl: CACHE_TTL_LONG });
}
