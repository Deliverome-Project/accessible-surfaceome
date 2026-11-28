// Genome-wide catalog (/v1/catalog) and single-gene catalog row (/v1/catalog/:symbol).
import { CACHE_TTL_LONG, CACHE_TTL_SHORT, badRequest, checkSymbol, json, notFound } from "../lib/http.js";
import { isArchiveBypass } from "../lib/crypto.js";
import { cacheEpoch } from "../lib/cache.js";
import { majorityVerdictAndReason, surfaceMethodsSql } from "../lib/catalog_projection.js";
import { GENOME_RUN_ID, RESCUE_RUN_IDS } from "./triage.js";
import { BENCH_RUN_ID } from "./benchmark.js";
import { buildCatalogRows } from "./catalog_rows.js";

export async function handleCatalog(env, request) {
  // Self-managed edge cache, keyed on the request URL. CF's HTTP cache
  // already does this via Cache-Control, but the in-Worker cache lets
  // us serve a stored Response without entering the join/format code
  // at all on warm hits — that's the difference between 1ms and 100ms
  // of CPU when the edge cache lottery loses. TTL still governed by
  // the response's Cache-Control header (set in `json` to 1 min for
  // /v1/catalog), so a re-deploy or universe-version bump surfaces on
  // the next miss.
  const cache = caches.default;
  const cacheKey = new Request(
    new URL(`/${cacheEpoch(env)}/v1/catalog`, "https://catalog.cache").href,
    { method: "GET" },
  );
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

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

  // ONE consolidated query: universe rows + deep-dive flag + SURFACE-Bind
  // site count. Previously this was 3 separate D1 round-trips and 3 JS
  // Map builds; pushing the joins into SQLite drops ~20k Map ops and
  // 2 round-trips. n_sources_surface in the table is already the count
  // over the 5 gating flags (uniprot/go/surfy/cspa/hpa); DeepTMHMM /
  // COMPARTMENTS are auxiliary signals and not in the catalog response.
  //
  // LEFT JOIN on surface_annotation via a DISTINCT subquery so a gene
  // with multiple schema_version rows in the table still emits one
  // deep_dive=1 row (and surface_annotation grows slowly, so the
  // subquery is cheap).
  //
  // LEFT JOIN on surface_bind_protein via uniprot_acc; the n_sites
  // column carries the SURFACE-Bind three-state value the viewer's
  // filter chip group reads (null = not in SURFACE-Bind, 0 = scored
  // no patches, N>0 = scored with patches).
  //
  // Also LEFT JOIN the LATEST surface_annotation row (by schema_version
  // desc) so we can pull `annotation_json` and project a slimmed-down
  // `filters` block onto the catalog row. The subquery picks one row
  // per gene_symbol — the highest schema_version, matching the
  // `/v1/genes/{symbol}` lookup logic. surface_annotation grows
  // slowly (~6k rows today, all deep-dived genes), so the subquery
  // is cheap.
  // uniprot_acc is COALESCEd onto the gene_identifier_public stable-ID
  // cache (resolver canonical) first, then candidate_universe_public's own
  // value. This (a) corrects the handful of candidates where
  // candidate_universe picked a non-canonical Swiss-Prot entry
  // (multi_xref_canonical_pick_disagrees — GNAS, MYO18A, NRXN2, TRA, TRB),
  // and (b) fills uniprot for non-candidate rows (n_sources_surface = 0),
  // which candidate_universe leaves NULL by design. The SURFACE-Bind join
  // below deliberately stays on u.uniprot_acc — that's the key SURFACE-Bind
  // was scored against.
  // Deep-dive projection strategy: rather than pulling the full
  // ~120 KB `annotation_json` per row and JSON.parsing it in JS to
  // pluck 6 sub-blocks, ask SQLite to `json_extract` just those
  // sub-blocks server-side. Total per-row payload drops from ~120 KB
  // to ~4 KB — 30× headroom under D1's per-query isolate memory cap.
  // See `projectDeepDiveFiltersFromParts` for the read-side contract.
  //
  // Path list must stay in sync with `projectDeepDiveFiltersFromParts`
  // — that function reads exactly these 6 sub-paths and nothing else.
  const enrichedRows = await env.DB.prepare(
    `SELECT u.gene_symbol,
            COALESCE(gi.uniprot_acc, u.uniprot_acc) AS uniprot_acc,
            u.n_sources_surface,
            u.uniprot_surface_flag, u.go_surface_flag, u.surfy_surface_flag,
            u.cspa_surface_flag, u.hpa_surface_flag,
            COALESCE(oc.uniprot_optimized, 0) AS uniprot_optimized,
            COALESCE(oc.cspa_optimized, 0) AS cspa_optimized,
            sb.n_sites AS sb_n_sites,
            sa.ddf_filters AS sa_ddf_filters,
            sa.ddf_evidence_grade_summary AS sa_ddf_evidence_grade_summary,
            sa.ddf_primary_compartment AS sa_ddf_primary_compartment,
            sa.ddf_restricted_subdomain AS sa_ddf_restricted_subdomain,
            sa.ddf_secreted_form AS sa_ddf_secreted_form,
            sa.ddf_surface_bind AS sa_ddf_surface_bind,
            sa.ddf_homo_oligomerization AS sa_ddf_homo_oligomerization,
            sa.ddf_topo_tm_helix_count AS sa_ddf_topo_tm_helix_count,
            sa.ddf_topo_signal_peptide_length AS sa_ddf_topo_signal_peptide_length,
            sa.ddf_surface_methods AS sa_ddf_surface_methods,
            si.intern_grade AS intern_grade,
            si.intern_has_lit AS intern_has_lit,
            si.intern_lit_grade AS intern_lit_grade,
            si.intern_lit_conf AS intern_lit_conf,
            si.intern_lit_basal AS intern_lit_basal,
            si.intern_lit_native AS intern_lit_native,
            si.intern_lit_therapeutic AS intern_lit_therapeutic,
            si.intern_lit_pathogen AS intern_lit_pathogen,
            si.intern_lit_fate AS intern_lit_fate,
            si.intern_lit_primary AS intern_lit_primary,
            si.intern_lit_quant AS intern_lit_quant,
            si.intern_lit_fitted AS intern_lit_fitted,
            si.intern_lit_binders AS intern_lit_binders,
            si.intern_lit_mechs AS intern_lit_mechs,
            CASE WHEN sa.gene_symbol IS NOT NULL THEN 1 ELSE 0 END AS has_deep_dive
       FROM candidate_universe_public u
       LEFT JOIN gene_identifier_public gi ON gi.hgnc_symbol = u.gene_symbol
       LEFT JOIN surface_bind_protein sb ON sb.uniprot_acc = u.uniprot_acc
       -- SurfaceBench-recalibrated DB cutoffs. A POSITIVE LIST: no row means
       -- (0, 0), never "fall back to the native flag" -- a fallback
       -- resurrects the low-confidence CSPA-only proteins the tightening
       -- drops. Hence the COALESCE to 0 above, and hence the table must be
       -- loaded before this Worker deploys.
       LEFT JOIN db_optimized_cutoff_public oc
         ON oc.accession = COALESCE(gi.uniprot_acc, u.uniprot_acc)
       -- Internalization sequence-prior grade (separate standalone pass;
       -- scalar grade columns only — never record_json, which carries the
       -- per-residue topology string that would blow D1's isolate memory
       -- cap at catalog scale, same rationale as the canonical_topology
       -- scalars above). One row per gene (publish drops stale schema
       -- versions); the MAX(schema_version) guard is belt-and-suspenders.
       LEFT JOIN (
         SELECT gene_symbol,
                seq_canonical_grade AS intern_grade,
                has_literature AS intern_has_lit,
                lit_overall_grade AS intern_lit_grade,
                lit_overall_confidence AS intern_lit_conf,
                lit_basal_grade AS intern_lit_basal,
                lit_native_ligand_grade AS intern_lit_native,
                lit_therapeutic_grade AS intern_lit_therapeutic,
                lit_pathogen_entry_grade AS intern_lit_pathogen,
                lit_predominant_fate AS intern_lit_fate,
                lit_has_primary_or_invivo AS intern_lit_primary,
                lit_has_quant AS intern_lit_quant,
                lit_has_fitted_kinetics AS intern_lit_fitted,
                lit_binder_types AS intern_lit_binders,
                lit_mechanisms AS intern_lit_mechs
           FROM surface_internalization sii1
          WHERE schema_version = (
            SELECT MAX(schema_version) FROM surface_internalization sii2
             WHERE sii2.gene_symbol = sii1.gene_symbol
          )
       ) si ON si.gene_symbol = u.gene_symbol
       LEFT JOIN (
         -- One row per gene: the latest (schema_version, prompt_corpus_version)
         -- combo. The schema_version match is load-bearing today (the
         -- PK is still (gene_symbol, schema_version) until the
         -- migration runbook is applied); prompt_corpus is a secondary
         -- tie-break that only matters when two rows share schema_version.
         SELECT gene_symbol,
                json_extract(annotation_json, '$.filters') AS ddf_filters,
                json_extract(annotation_json, '$.executive_summary.evidence_grade_summary') AS ddf_evidence_grade_summary,
                json_extract(annotation_json, '$.biological_context.subcellular_localization.primary_compartment') AS ddf_primary_compartment,
                json_extract(annotation_json, '$.accessibility_risks.restricted_subdomain') AS ddf_restricted_subdomain,
                json_extract(annotation_json, '$.accessibility_risks.secreted_form') AS ddf_secreted_form,
                json_extract(annotation_json, '$.deterministic_features.surface_bind') AS ddf_surface_bind,
                json_extract(annotation_json, '$.deterministic_features.homo_oligomerization') AS ddf_homo_oligomerization,
                -- Canonical-topology SCALARS only — never the full
                -- canonical_topology object (it carries per_residue_topology,
                -- a ~protein-length string that would blow D1's per-query
                -- isolate memory across ~1.2k catalog rows).
                json_extract(annotation_json, '$.deterministic_features.canonical_topology.tm_helix_count') AS ddf_topo_tm_helix_count,
                json_extract(annotation_json, '$.deterministic_features.canonical_topology.signal_peptide_length') AS ddf_topo_signal_peptide_length,
                ${surfaceMethodsSql("sa1")} AS ddf_surface_methods
           FROM surface_annotation sa1
          WHERE schema_version = (
            SELECT MAX(schema_version) FROM surface_annotation sa2
             WHERE sa2.gene_symbol = sa1.gene_symbol
          )
            AND COALESCE(prompt_corpus_version, '0.0.0') = (
              SELECT MAX(COALESCE(prompt_corpus_version, '0.0.0'))
                FROM surface_annotation sa3
               WHERE sa3.gene_symbol = sa1.gene_symbol
                 AND sa3.schema_version = sa1.schema_version
            )
       ) sa ON sa.gene_symbol = u.gene_symbol
      WHERE u.universe_version = ?
      ORDER BY u.gene_symbol`
  ).bind(universe).all();

  // Per-model NCBI-variant verdict for each gene. The page renders
  // three columns (Haiku / Sonnet / Opus); each cell shows that
  // model's ncbi-variant call. Only `prompt_variant='ncbi'` because
  // that's the variant with cross-model coverage and the one the
  // published figures use as headline.
  //
  // Aggregation: majority verdict across replicates per (gene, model),
  // then most common reason within the winning verdict, both tiebroken
  // on most recent `created_at` (see majorityVerdictAndReason).
  //
  // Coverage today:
  //   - Sonnet/ncbi: full ~19k genome (genome_full_sonnet_ncbi_v2)
  //   - Haiku/ncbi: 147 SurfaceBench genes only (mainbench_canonical_v2)
  //   - Opus/ncbi: 147 SurfaceBench genes only (mainbench_canonical_v2)
  // So most rows will show only the Sonnet column populated.
  //
  // The Sonnet slot is the paper's two-stage triage verdict, so its stage
  // one is the GENOME run alone. The 147 SurfaceBench genes also carry
  // three benchmark replicates of the same (model, variant); letting those
  // vote turned a 2:2 tie into "contextual" for a gene the genome run
  // called "no". Benchmark replicates are used only for a gene the genome
  // run does not cover.
  const CATALOG_MODELS = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"];
  const SONNET = "claude-sonnet-4-6";
  const triageByGene = new Map();
  const triageRows = await env.DB.prepare(
    `SELECT gene_symbol, model, run_id, predicted_verdict, predicted_reason, created_at
       FROM triage_run_public
      WHERE prompt_variant = 'ncbi'
        AND model IN ('claude-haiku-4-5','claude-sonnet-4-6','claude-opus-4-8')
        AND predicted_verdict IS NOT NULL`
  ).all();
  // Group replicates by (gene, model).
  const triageReplicates = new Map();
  for (const r of triageRows.results) {
    const key = `${r.gene_symbol}\t${r.model}`;
    let lst = triageReplicates.get(key);
    if (!lst) { lst = []; triageReplicates.set(key, lst); }
    lst.push(r);
  }
  for (const [key, reps] of triageReplicates) {
    const [gene_symbol, model] = key.split("\t");
    let cell = reps;
    if (model === SONNET) {
      const genome = reps.filter((r) => r.run_id === GENOME_RUN_ID);
      if (genome.length) cell = genome;
    }
    let perModel = triageByGene.get(gene_symbol);
    if (!perModel) { perModel = {}; triageByGene.set(gene_symbol, perModel); }
    perModel[model] = majorityVerdictAndReason(cell);
  }

  // Stage two (literature rescue): a gene the genome run called "no" takes
  // the verdict of any rescue run that called it yes/contextual. A rescue
  // "no" never overrides a positive call, since it adds no evidence of
  // absence.
  //
  // Rows are selected by RUN ID, not by prompt_variant, to match
  // scripts/build_candidate_universe_v3.py (RESCUE_RUNS), which builds the
  // candidate universe and every count in the paper:
  //   - A rescue cell falls back to the `naive` variant when its PubMed
  //     fetch fails. It is still that gene's second look; filtering on
  //     `pubmed_ncbi` dropped it and left a rescued gene showing "no".
  //   - SurfaceBench genes carry `pubmed_ncbi` rows from the benchmark,
  //     which are not a proteome-wide second look; treating them as one
  //     rescued genes the paper's triage calls "no".
  // A gene re-run in more than one lane is rescued if ANY lane is positive.
  const rescueRows = await env.DB.prepare(
    `SELECT gene_symbol, run_id, predicted_verdict, predicted_reason, created_at
       FROM triage_run_public
      WHERE run_id IN (${RESCUE_RUN_IDS.map(() => "?").join(", ")})
        AND model = 'claude-sonnet-4-6'
        AND predicted_verdict IS NOT NULL`
  ).bind(...RESCUE_RUN_IDS).all();
  const rescueByGene = new Map();
  for (const r of rescueRows.results) {
    let byRun = rescueByGene.get(r.gene_symbol);
    if (!byRun) { byRun = new Map(); rescueByGene.set(r.gene_symbol, byRun); }
    let lst = byRun.get(r.run_id);
    if (!lst) { lst = []; byRun.set(r.run_id, lst); }
    lst.push(r);
  }
  for (const [gene_symbol, byRun] of rescueByGene) {
    const stageOne = triageByGene.get(gene_symbol)?.[SONNET];
    if (!stageOne || stageOne.verdict !== "no") continue;
    const positive = RESCUE_RUN_IDS
      .filter((id) => byRun.has(id))
      .map((id) => majorityVerdictAndReason(byRun.get(id)))
      .filter((c) => c.verdict === "yes" || c.verdict === "contextual");
    if (!positive.length) continue;
    triageByGene.get(gene_symbol)[SONNET] =
      positive.find((c) => c.verdict === "yes") || positive[0];
  }

  // Track which genes we've emitted so we can append deep-dive-only
  // genes (e.g. HSPA1A — conditional surface, doesn't pass the
  // universe gate) at the bottom. Also collect the deep-dive gene set
  // from the join so we can spot the gap without an extra SELECT.
  const covered = new Set();
  const deepSet = new Set();
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
  // How many library members (l1+l2) have a DeepTMHMM v1 topology for their EXACT
  // designed sequence. One aggregate query for the whole cohort, not per row.
  // Deliberately a count and not a boolean: a gene can contribute several members
  // (library_reference plus isoform and ortholog arms), and "2 of this gene's
  // members are covered" is the thing a reviewer needs to see. Genes with none are
  // absent from the map and get no field — never a 0, which would be
  // indistinguishable from "not a library gene" in the UI.
  const libTopoByGene = new Map();
  {
    const r = await env.DB.prepare(
      `SELECT gene_symbol, COUNT(*) AS n
         FROM library_topology_public
        WHERE gene_symbol IS NOT NULL
        GROUP BY gene_symbol`
    )
      .all()
      .catch(() => null);
    for (const row of r?.results ?? []) {
      libTopoByGene.set(row.gene_symbol, Number(row.n));
    }
  }

  const { rows, psCutoffs } = await buildCatalogRows(env, {
    enrichedRows,
    covered,
    deepSet,
    packTriage,
    libTopoByGene,
  });

  const response = json(
    {
      universe_version: universe,
      bench_version: benchVersion,
      models: CATALOG_MODELS,
      n_rows: rows.length,
      n_with_triage: rows.filter((r) => r.tr).length,
      n_with_deep_dive: deepSet.size,
      // Schema version of the row encoding. Bumped when the shape
      // changes; viewer/lib/surfaceome.ts checks this and decodes
      // accordingly.
      //   v3 = per-model ncbi `tr` array replaces single `triage`.
      //   v4 = optional `sb` (SURFACE-Bind site count) added.
      //   v5 = optional `ddf` (slimmed deep-dive Filters projection)
      //        added — present only when has_deep_dive=true and the
      //        record_json parsed. Carries the catalog-filterable
      //        subset of SurfaceomeRecord.filters; see
      //        projectDeepDiveFiltersFromParts() above.
      //   v6 = adds `ddf.n_papers_selected`, `ddf.n_papers_found`
      //        (raw counts), `ddf.n_papers_selected_band` (the
      //        cohort-percentile-banded value the filter UI keys off,
      //        when ≥3 records carry the count); the cutoffs that
      //        produced the bands travel as the top-level
      //        `n_papers_selected_cutoffs` field so the viewer can
      //        display them in the filter tooltip.
      //   v7 = adds deterministic transmembrane-topology facets derived
      //        from deterministic_features.canonical_topology (DeepTMHMM):
      //        `ddf.has_tm` and `ddf.tm_count_band` (none/single/multi).
      //   v8 = adds top-level `intern` (internalization sequence-prior
      //        SeqGrade: very_high|high|moderate|low|very_low|unknown) from
      //        surface_internalization, present only for the internalization
      //        cohort; plus optional `intern_lit`=1 when a literature grade
      //        also exists. A SEPARATE catalog facet, independent of `ddf` /
      //        deep-dive coverage. Older viewers ignore unknown fields.
      //   v9 = adds optional top-level `intern_lit_grade` (literature-track
      //        overall Grade: high|moderate|low|no|unknown), distinct from the
      //        seq-prior `intern`, so the catalog can show a SEPARATE
      //        internalization-literature column + filter. Present only once a
      //        gene has a literature run; `intern_lit`=1 stays as the has-lit
      //        flag for back-compat. Older viewers ignore the new field.
      //   v10 = adds `ddf.surface_method_direct` / `ddf.surface_method_supporting`
      //        (sorted method-category lists from surface_evidence.methods;
      //        a method with a direct row is not repeated as supporting) and
      //        `ddf.has_native_direct_surface_evidence` (a direct row in an
      //        endogenous / mixed / knock-in system), and re-derives
      //        `ddf.has_live_cell_surface_evidence` from the methods rows
      //        (live cells, native expression, not a functional assay).
      //        See projectSurfaceMethods.
      //   v11 = adds optional top-level `libtopo` — the number of library
      //        members (l1+l2) whose EXACT designed sequence has a DeepTMHMM v1
      //        topology, from library_topology_public. Present only for genes
      //        with at least one. Distinct from `ddf.has_tm` / `tm_count_band`,
      //        which are derived from the gene's CANONICAL topology: a library
      //        member's ORF is an Ensembl-transcript product and for a
      //        substantial minority is a different protein from the canonical,
      //        so the two can legitimately disagree. The per-member strings
      //        travel on the gene record as
      //        `deterministic_features.library_designed_topology`, not here.
      //        Older viewers ignore the new field.
      //   v12 = adds optional top-level `intl` — slim projection of the schema
      //        0.3.0 literature internalization facets from flat scalar columns
      //        on surface_internalization (conf, per-mode basal/native/
      //        therapeutic/pathogen grades, predominant fate, primary/in vivo
      //        flag, quant/fitted kinetics flags, distinct binder_types and
      //        mechanisms). Unknown/empty/false keys omitted. Older viewers
      //        ignore the new field.
      row_schema: 12,
      n_papers_selected_cutoffs: psCutoffs,
      // Names for the bits in each row's `db` 5-bit field (LSB → MSB).
      // Self-describing for external reanalysts: decode with
      //   const flags = db_keys.map((_, i) => (row.db >> i) & 1);
      // Matches the encoding above + viewer/lib/surfaceome.ts.
      db_keys: ["uniprot", "go", "surfy", "cspa", "hpa"],
      rows,
    },
    { ttl: CACHE_TTL_SHORT },
  );

  // Stash in the Worker-managed cache. `.clone()` because Response
  // bodies are streams — once consumed they can't be re-read. The
  // ``ctx.waitUntil`` would let this run after the response sends,
  // but the handler signature here doesn't expose `ctx`; the await
  // adds <5ms to the cold response, well within budget.
  await cache.put(cacheKey, response.clone());
  return response;
}

// Models + prompt variants surfaced in the benchmark matrix. All 4
// variants render as their own columns on the /benchmark/ page (the
// old "headline + 3 alts behind an expand" UX collapsed into a flat

// --- entry ----------------------------------------------------------------

// Slim single-gene catalog row — the 5 source-DB surface flags (+ n_sources,
// deep-dive flag, SURFACE-Bind site count) for ONE gene, so the per-gene page
// can render the DB-presence strip without pulling the ~5 MB genome-wide
// /v1/catalog. Mirrors handleCatalog's per-row projection, filtered to the
// latest universe_version and one gene. `deep_dive` is just presence in
// surface_annotation (the strip only reads `db`, but the row is returned in
// the same CatalogRow shape the catalog table uses).
export async function handleCatalogOne(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return notFound("gene_not_found");
  const release = await env.DB.prepare(
    `SELECT universe_version FROM candidate_universe_release
      ORDER BY loaded_at DESC LIMIT 1`
  ).first();
  if (!release?.universe_version) return notFound("no_universe");
  const r = await env.DB.prepare(
    `SELECT u.gene_symbol,
            COALESCE(gi.uniprot_acc, u.uniprot_acc) AS uniprot_acc,
            u.n_sources_surface,
            u.uniprot_surface_flag, u.go_surface_flag, u.surfy_surface_flag,
            u.cspa_surface_flag, u.hpa_surface_flag,
            COALESCE(oc.uniprot_optimized, 0) AS uniprot_optimized,
            COALESCE(oc.cspa_optimized, 0) AS cspa_optimized,
            sb.n_sites AS sb_n_sites,
            CASE WHEN sa.gene_symbol IS NOT NULL THEN 1 ELSE 0 END AS has_deep_dive
       FROM candidate_universe_public u
       LEFT JOIN gene_identifier_public gi ON gi.hgnc_symbol = u.gene_symbol
       LEFT JOIN surface_bind_protein sb ON sb.uniprot_acc = u.uniprot_acc
       -- Recalibrated UniProt + CSPA membership, matching handleCatalog.
       -- Positive list: absent -> 0, never a native fallback.
       LEFT JOIN db_optimized_cutoff_public oc
              ON oc.accession = COALESCE(gi.uniprot_acc, u.uniprot_acc)
       LEFT JOIN (SELECT DISTINCT gene_symbol FROM surface_annotation) sa
              ON sa.gene_symbol = u.gene_symbol
      WHERE u.gene_symbol = ? COLLATE NOCASE
        AND u.universe_version = ?
      LIMIT 1`
  ).bind(sym, release.universe_version).first();
  if (!r) return notFound("gene_not_in_universe");
  const flag = (v) => (v ? 1 : 0);
  const upOpt = flag(r.uniprot_optimized);
  const cspaOpt = flag(r.cspa_optimized);
  const goFlag = flag(r.go_surface_flag);
  const surfyFlag = flag(r.surfy_surface_flag);
  const hpaFlag = flag(r.hpa_surface_flag);
  return json({
    symbol: r.gene_symbol,
    uniprot: r.uniprot_acc ?? "",
    // Recomputed from the recalibrated flags, not the table's native count.
    n_sources: upOpt + goFlag + surfyFlag + cspaOpt + hpaFlag,
    db: {
      uniprot: upOpt,
      go: goFlag,
      surfy: surfyFlag,
      cspa: cspaOpt,
      hpa: hpaFlag,
    },
    deep_dive: r.has_deep_dive === 1,
    surface_bind_sites:
      typeof r.sb_n_sites === "number" ? r.sb_n_sites : undefined,
  });
}

// L1 library design overlay: per-member tag sites (current picks + alternatives, with
// the rationale for each), folded structures (native model per the structure payload,
// plus tagged-construct refolds) and contact sites, from the l1_*_public tables
// (cloudflare/migrations/l1_design_v1.sql, loaded by
// scripts/cloud/build_l1_design_tables.py). Additive: no existing route or table is
// read differently.
//
// Loads are content-addressed and INSERT-only. The newest load that has a row in
// l1_design_load_public is served; the loader writes that row last, so a
// half-applied load is invisible. `/v1/l1-design/{symbol}/{load_version}` pins an
// older load for auditability (immutable, so edge-cached). The unpinned routes skip
// the edge/KV cache and carry a 30 s browser TTL: a new load goes live within a
// minute with no purge. Missing tables (Worker deployed before the migration) and
// empty tables degrade to `load: null`; transient D1/runtime errors fail closed
// with 503 `{ error: "l1_design_unavailable" }` and `Cache-Control: no-store`.
