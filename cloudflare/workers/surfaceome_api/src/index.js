// Cloudflare Worker — public read-only Surfaceome API.
//
// Reads from the `surfaceome_public` D1 (bound as env.DB in wrangler.toml).
// No auth; aggressive Cache-Control headers carry the load on edge cache.
//
// Endpoints:
//   GET /v1                     — self-describing index: endpoint catalog +
//                                  docs/skill/llms.txt links + dataset versions
//                                  (also served at the bare service root)
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
//   GET /v1/triage/:symbol/:model/:variant — per-cell replicate detail:
//                                  every replicate + computed majority
//                                  (backs the benchmark RationaleDrawer)
//   GET /v1/triage/export.tsv   — long-format TSV of all triage runs for a
//                                  given run_id (default mainbench_canonical_v2).
//                                  Single source of truth for final-figure
//                                  predictions data; carries cost_usd + token
//                                  counts. Pass with_reasoning=1 to append the
//                                  agent's verdict_reasoning + key-uncertainty
//                                  columns (e.g. the full genome-wide sweep).
//   GET /v1/meta/sizes          — approximate per-endpoint response sizes,
//                                  computed live from D1 row counts + LENGTH
//                                  sums (drives the /api docs page badges).
//
// Schema: cloudflare/d1_public_schema.sql.

const CACHE_TTL_SHORT = 60;        // 1 min for list endpoints
const CACHE_TTL_LONG  = 86400;     // 1 day for per-gene records
const CACHE_SWR       = 86400;     // serve-stale window (revalidate / on-error)

// Build the Cache-Control header. On cacheable responses (ttl > 0) we add
// `stale-while-revalidate` so the edge serves the stale copy instantly on a
// miss while refreshing in the background, and `stale-if-error` so it keeps
// serving the stale copy when the Worker/origin errors — that's what absorbs
// the catalog handler's historical CPU-budget 503s (cf-error 1102) instead
// of surfacing them to readers. Freshness after a republish is handled by
// purge-on-publish (cloud/surface_annotation.publish_record), so the long
// TTL + serve-stale window costs nothing in staleness. ttl === 0 (e.g. a 400
// on bad input) opts out — a non-cacheable error must not be served stale.
function cacheControl(ttl) {
  const base = `public, max-age=${ttl}, s-maxage=${ttl}`;
  if (ttl <= 0) return base;
  return `${base}, stale-while-revalidate=${CACHE_SWR}, stale-if-error=${CACHE_SWR}`;
}

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
      "Cache-Control": cacheControl(ttl),
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
      "Cache-Control": cacheControl(ttl),
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
  // NOTE: this uppercases, but most per-symbol D1 lookups compare the
  // stored `gene_symbol` COLLATE NOCASE. That's load-bearing: a minority
  // of HGNC symbols are stored MIXED-CASE (the `Cxorf` class, e.g.
  // `C11orf24`, lowercase "orf"), so an uppercased `= ?` match silently
  // misses them and the record endpoint 404s while `/v1/genes` still
  // lists them. Keep new per-symbol WHERE clauses `COLLATE NOCASE`.
  return sym.toUpperCase();
}

// Per-IP rate limiting via the native Workers Rate Limiting binding
// (configured in wrangler.toml). In-colo + in-memory — NOT KV, so there's
// no per-request storage read/write and no storage cost. The data is
// publish-intended, so the point is to bound cost/CPU under abuse, not to
// gate access — the limits are generous.
//
// Returns a 429 Response when the caller is over its limit, or null to
// proceed. The binding is OPTIONAL: an older wrangler or a local
// `wrangler dev` without it simply skips the check (never crashes). The
// CPU-heavy endpoints (/v1/catalog + the *.tsv exports) use the tighter
// RATE_LIMITER_HEAVY; everything else uses RATE_LIMITER. /v1/health is
// never limited so uptime probes always succeed. Counting is per-colo, so
// a distributed attacker gets N×limit total — fine here; Cloudflare's
// always-on L7 DDoS protection covers the volumetric case underneath.
async function checkRate(env, request, path) {
  if (path === "/v1/health") return null;
  const heavy = path === "/v1/catalog" || path.endsWith(".tsv");
  const limiter = heavy ? env.RATE_LIMITER_HEAVY : env.RATE_LIMITER;
  if (!limiter) return null;
  const ip = request.headers.get("CF-Connecting-IP") || "anon";
  const { success } = await limiter.limit({ key: ip });
  if (success) return null;
  return new Response(JSON.stringify({ error: "rate_limited" }), {
    status: 429,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Retry-After": "60",
      "Cache-Control": "no-store",
      ...CORS_HEADERS,
    },
  });
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
const TRIAGE_VERDICT_TO_SIGNAL = {
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
const TRIAGE_PRIORITY = [
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
async function fetchTriagePrior(env, sym) {
  for (const [runId, variant] of TRIAGE_PRIORITY) {
    const row = await env.DB.prepare(
      `SELECT predicted_verdict, predicted_reason, verdict_reasoning
         FROM triage_run_public
        WHERE gene_symbol = ? COLLATE NOCASE
          AND run_id = ?
          AND prompt_variant = ?
          AND model LIKE '%sonnet%'
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

async function handleGene(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  // Latest (schema_version, prompt_corpus_version) row wins. The
  // ``COALESCE(prompt_corpus_version, '0.0.0')`` keeps pre-corpus rows
  // ordering deterministically below any row that carries the column —
  // matches the behavior at handleGeneList. Until the PK migration in
  // docs/audit/r2_and_reproducibility_2026_06_08.md is executed on
  // prod D1, the PK is still (gene_symbol, schema_version) so the
  // schema_version DESC tie-break is the load-bearing ordering;
  // prompt_corpus is a secondary disambiguator that only matters when
  // two rows accidentally share a schema_version.
  const row = await env.DB.prepare(
    `SELECT annotation_json, schema_version, annotated_at,
            COALESCE(prompt_corpus_version, '0.0.0') AS prompt_corpus_version,
            cohort_run_id
       FROM surface_annotation
      WHERE gene_symbol = ? COLLATE NOCASE
      ORDER BY schema_version DESC,
               COALESCE(prompt_corpus_version, '0.0.0') DESC
      LIMIT 1`
  ).bind(sym).first();
  if (!row) return notFound("gene_not_annotated");
  let record;
  try {
    record = JSON.parse(row.annotation_json);
  } catch (e) {
    return json({ error: "bad_record_json" }, { status: 500, ttl: 0 });
  }
  // Enrich with Schweke 2024 homo-oligomer prediction at serve time.
  // The annotator already bakes ``deterministic_features.homo_oligomerization``
  // into newly-annotated records (consistent with how the other deterministic
  // blocks — topology, paralogs, orthologs, structure, surface_bind — are
  // populated at annotation time). This LEFT JOIN is the back-compat hatch
  // for records annotated BEFORE the schweke_homomer wiring landed: any
  // record whose homo_oligomerization block is missing OR carries
  // is_homo_oligomer=false despite the gene appearing in
  // schweke_homomer_public gets the row injected. Records that already
  // carry a positive Schweke entry from the annotator are left alone
  // (annotator's bake wins; ensures the data the LLM saw at annotation
  // time matches what the viewer renders).
  const uniprot = record?.gene?.uniprot_acc;
  if (uniprot) {
    const existing = record?.deterministic_features?.homo_oligomerization;
    const needsEnrichment = !existing || existing.is_homo_oligomer === false;
    if (needsEnrichment) {
      const schwekeRow = await env.DB.prepare(
        `SELECT stoichiometry, af_model_num, is_ecd_only,
                has_higher_order_complex, dimer_pdb_filename,
                complex_pdb_filename
           FROM schweke_homomer_public
          WHERE uniprot_acc = ?
          ORDER BY universe_version DESC
          LIMIT 1`
      ).bind(uniprot).first().catch(() => null);
      if (schwekeRow) {
        if (!record.deterministic_features) record.deterministic_features = {};
        record.deterministic_features.homo_oligomerization = {
          is_homo_oligomer: true,
          stoichiometry: schwekeRow.stoichiometry ?? null,
          af_model_num: schwekeRow.af_model_num ?? null,
          is_ecd_only: !!schwekeRow.is_ecd_only,
          has_higher_order_complex: !!schwekeRow.has_higher_order_complex,
          dimer_pdb_filename: schwekeRow.dimer_pdb_filename ?? null,
          complex_pdb_filename: schwekeRow.complex_pdb_filename ?? null,
          source: "Schweke 2024 (PMID 38325366)",
          citation: "10.1016/j.cell.2024.01.022",
        };
        // Cat 3 mitigation — also derive
        // ``accessibility_risks.homo_oligomerization_prediction`` from the
        // injected block. This field is normally populated at annotation
        // time by the orchestrator's ``_attach_homo_oligomerization_prediction``
        // post-pass (see ``agents/surfaceome_v2/orchestrator.py``); the
        // Worker mirrors the same derivation so old records served before
        // re-annotation also carry the structured risk chip the viewer
        // renders next to ``epitope_masking``. Severity bands MUST match
        // the Python implementation's ``_homo_oligomerization_severity``
        // helper — keep them in sync (≤2 → low, 3..7 → moderate, 8..24 →
        // high, None → unknown). Annotator-populated risk chips win: only
        // inject when the served record doesn't already carry one (mirrors
        // the same "annotator-bake wins" convention as every other
        // serve-time enrichment in handleGene).
        const existingRisk =
          record?.accessibility_risks?.homo_oligomerization_prediction;
        if (!existingRisk) {
          const n = schwekeRow.stoichiometry;
          let severity = "unknown";
          if (typeof n === "number") {
            if (n <= 2) severity = "low";
            else if (n <= 7) severity = "moderate";
            else if (n <= 24) severity = "high";
          }
          if (!record.accessibility_risks) record.accessibility_risks = {};
          record.accessibility_risks.homo_oligomerization_prediction = {
            present: true,
            stoichiometry: n ?? null,
            severity,
            is_ecd_only: !!schwekeRow.is_ecd_only,
            source: "Schweke 2024 (PMID 38325366)",
            cited_evidence_ids: [],
          };
        }
      }
    }
  }
  // Defense-in-depth dedup for the three enrichment queries below. Each one
  // selects from a topology_public / compara_paralog / compara_ortholog
  // table that carries the same accession at MULTIPLE topology / release
  // versions. The query filters by a single version, so the happy path
  // returns ≤ 1 row per accession. But when the version-resolution lookup
  // hiccups (a topology_release row is missing / NULL / older than the data
  // it points at), the filter degrades and we get one row per (accession ×
  // version) → the duplication TGOLN2 showed: 11 isoform_topologies for a
  // gene that has 5 alternative isoforms (5 × 2 topology_versions + the
  // canonical row leaking in). Drop duplicates by primary accession so the
  // shape returned to the viewer is correct even when version resolution
  // misbehaves. Picks the first-occurring row (D1's order-by puts the
  // alphabetically-earliest accession first; later versions overwrite when
  // they sort later — close enough for a safety net, and the annotator
  // path is the authoritative source either way).
  function dedupeByKey(rows, keyFn) {
    if (!Array.isArray(rows) || rows.length === 0) return rows;
    const seen = new Set();
    const out = [];
    for (const r of rows) {
      const k = keyFn(r);
      if (k == null || seen.has(k)) continue;
      seen.add(k);
      out.push(r);
    }
    return out;
  }
  // Enrich with canonical + isoform topology, paralogs, and orthologs at
  // serve time. Same back-compat rationale as the Schweke block above: the
  // annotator already bakes these into newly-annotated records (see
  // src/accessible_surfaceome/agents/surfaceome_v1/d1_deterministic.py
  // _fetch_canonical_topology / _fetch_isoform_topologies / _fetch_paralogs
  // / _fetch_orthologs). These LEFT JOINs are the back-compat hatch for
  // records annotated BEFORE each feature's wiring landed. Annotator-baked
  // positives ALWAYS win — the "needsEnrichment" gate only fires when the
  // record's field is missing, carries the explicit placeholder, OR is
  // empty without a "checked, none found" sentinel (see
  // DeterministicFeatures.{paralogs,isoform_topologies}_checked and
  // OrthologSet.checked — those are the annotator's "we looked and there's
  // genuinely nothing" signal, and we leave that alone).
  if (uniprot) {
    // Resolve the active per-table versions in parallel. Each defaults to
    // null on a missing release row or D1 hiccup; the per-feature blocks
    // below skip enrichment when their version is absent.
    const [topoCanonRow, topoIsoRow, paralogRelRow, orthoEcdRelRow] = await Promise.all([
      env.DB.prepare(
        `SELECT topology_version FROM topology_release
            WHERE topology_version IN (
              SELECT DISTINCT topology_version FROM topology_public WHERE cohort = 'human_canonical'
            )
            ORDER BY loaded_at DESC LIMIT 1`
      ).first().catch(() => null),
      env.DB.prepare(
        `SELECT topology_version FROM topology_release
            WHERE topology_version IN (
              SELECT DISTINCT topology_version FROM topology_public WHERE cohort = 'human_isoforms'
            )
            ORDER BY loaded_at DESC LIMIT 1`
      ).first().catch(() => null),
      env.DB.prepare(
        `SELECT paralog_version FROM compara_paralog_release
            ORDER BY fetched_at DESC LIMIT 1`
      ).first().catch(() => null),
      env.DB.prepare(
        `SELECT ortholog_ecd_version FROM compara_ortholog_ecd_release
            ORDER BY computed_at DESC LIMIT 1`
      ).first().catch(() => null),
    ]);
    const canonicalTopoVersion = topoCanonRow?.topology_version ?? null;
    const isoformTopoVersion = topoIsoRow?.topology_version ?? null;
    const paralogVersion = paralogRelRow?.paralog_version ?? null;
    const orthologEcdVersion = orthoEcdRelRow?.ortholog_ecd_version ?? null;

    // ----- canonical_topology -----
    // Mirror _fetch_canonical_topology. Enrich when the record's
    // canonical_topology is missing OR carries the
    // ``tool_version='placeholder-no-d1-row'`` stub the Python annotator
    // emits when no D1 row was available at annotation time. Annotator
    // records with a real DeepTMHMM row are left alone.
    const existingCanonTopo = record?.deterministic_features?.canonical_topology;
    const canonTopoIsPlaceholder = existingCanonTopo?.tool_version === "placeholder-no-d1-row";
    const canonTopoNeedsEnrich = !existingCanonTopo || canonTopoIsPlaceholder;
    if (canonTopoNeedsEnrich && canonicalTopoVersion) {
      const tr = await env.DB.prepare(
        `SELECT uniprot_acc_full, isoform_id, tm_helix_count,
                n_terminal_orientation, c_terminal_orientation,
                signal_peptide_length, ecd_length_residues, icd_length_residues,
                per_residue_topology, sequence, tool_version, retrieved_at
           FROM topology_public
          WHERE uniprot_acc = ? AND cohort = 'human_canonical'
            AND topology_version = ?
          LIMIT 1`
      ).bind(uniprot, canonicalTopoVersion).first().catch(() => null);
      if (tr) {
        if (!record.deterministic_features) record.deterministic_features = {};
        record.deterministic_features.canonical_topology = {
          isoform_id: tr.isoform_id || `${uniprot}-1`,
          uniprot_acc: tr.uniprot_acc_full || uniprot,
          tm_helix_count: Number(tr.tm_helix_count || 0),
          n_terminal_orientation: tr.n_terminal_orientation === "extracellular" ? "extracellular" : "cytoplasmic",
          c_terminal_orientation: tr.c_terminal_orientation === "extracellular" ? "extracellular" : "cytoplasmic",
          signal_peptide_length: Number(tr.signal_peptide_length || 0),
          ecd_length_residues: Number(tr.ecd_length_residues || 0),
          icd_length_residues: Number(tr.icd_length_residues || 0),
          per_residue_topology: tr.per_residue_topology || "",
          sequence: tr.sequence ?? null,
          tool_version: tr.tool_version || "deeptmhmm-1.0.24",
          retrieved_at: tr.retrieved_at || new Date().toISOString(),
        };
      }
    }

    // ----- isoform_topologies -----
    // Mirror _fetch_isoform_topologies. Enrich when the field is missing
    // OR (the array is empty AND ``isoform_topologies_checked`` is not
    // True). The latter sentinel is the annotator's "we ran the isoforms
    // cohort and this gene genuinely has no alternative isoforms" signal;
    // we honor it. The Worker does NOT compute %identity to canonical
    // (BLOSUM62 alignment is too heavy for the request hot path); identity
    // fields are emitted as null. Records that need real %identity values
    // get them via re-annotation, not at serve time.
    const existingIsoTopo = record?.deterministic_features?.isoform_topologies;
    const isoTopoChecked = record?.deterministic_features?.isoform_topologies_checked === true;
    const isoTopoNeedsEnrich = !Array.isArray(existingIsoTopo)
      || (existingIsoTopo.length === 0 && !isoTopoChecked);
    if (isoTopoNeedsEnrich && isoformTopoVersion) {
      const isoRows = await env.DB.prepare(
        `SELECT uniprot_acc_full, isoform_id, tm_helix_count,
                n_terminal_orientation, c_terminal_orientation,
                signal_peptide_length, ecd_length_residues, icd_length_residues,
                per_residue_topology, sequence, tool_version, retrieved_at
           FROM topology_public
          WHERE uniprot_acc = ? AND cohort = 'human_isoforms'
            AND topology_version = ?
          ORDER BY uniprot_acc_full ASC`
      ).bind(uniprot, isoformTopoVersion).all().catch(() => null);
      // Belt-and-suspenders dedup: even though the query filters by
      // topology_version, a stale topology_release row would let multiple
      // versions slip through and produce duplicate isoform rows (one per
      // version). Also drop any row whose uniprot_acc_full matches the
      // canonical accession — those belong to the human_canonical cohort
      // and shouldn't be inside human_isoforms.
      const rawIsoResults = isoRows?.results ?? [];
      const results = dedupeByKey(
        rawIsoResults.filter((r) => r.uniprot_acc_full && r.uniprot_acc_full !== uniprot),
        (r) => r.uniprot_acc_full,
      );
      if (results.length > 0) {
        if (!record.deterministic_features) record.deterministic_features = {};
        record.deterministic_features.isoform_topologies = results.map((r) => ({
          isoform_id: r.isoform_id || r.uniprot_acc_full,
          uniprot_acc: r.uniprot_acc_full || uniprot,
          tm_helix_count: Number(r.tm_helix_count || 0),
          n_terminal_orientation: r.n_terminal_orientation === "extracellular" ? "extracellular" : "cytoplasmic",
          c_terminal_orientation: r.c_terminal_orientation === "extracellular" ? "extracellular" : "cytoplasmic",
          signal_peptide_length: Number(r.signal_peptide_length || 0),
          ecd_length_residues: Number(r.ecd_length_residues || 0),
          icd_length_residues: Number(r.icd_length_residues || 0),
          per_residue_topology: r.per_residue_topology || "",
          sequence: r.sequence ?? null,
          tool_version: r.tool_version || "deeptmhmm-1.0.24",
          retrieved_at: r.retrieved_at || new Date().toISOString(),
          // %identity to canonical not computed at serve time (BLOSUM62
          // alignment is too heavy here). Re-annotation fills these in.
          full_length_pct_identity_to_canonical: null,
          ecd_pct_identity_to_canonical: null,
          ecd_pct_similarity_to_canonical: null,
        }));
      }
    }

    // ----- paralogs -----
    // Mirror _fetch_paralogs. Enrich when the field is missing OR (the
    // array is empty AND ``paralogs_checked`` is not True). Close paralogs
    // (>=80% full-length identity, the CLOSE_PARALOG_THRESHOLD constant in
    // d1_deterministic.py) get their DeepTMHMM topology + sequence threaded
    // on via LEFT JOIN against topology_public; far/ECD-less paralogs stay
    // chip-only. PARALOG_TOP_N is 50 in the Python annotator — same cap here.
    const existingParalogs = record?.deterministic_features?.paralogs;
    const paralogsChecked = record?.deterministic_features?.paralogs_checked === true;
    const paralogsNeedEnrich = !Array.isArray(existingParalogs)
      || (existingParalogs.length === 0 && !paralogsChecked);
    if (paralogsNeedEnrich && paralogVersion) {
      const paralogRows = await env.DB.prepare(
        `SELECT cp.paralog_gene_symbol, cp.paralog_uniprot_acc, cp.ecd_pct_identity,
                cp.ecd_pct_similarity, cp.biomart_percent_identity, cp.family_id,
                cp.compara_version, cp.rank_by_ecd_identity,
                tp.per_residue_topology, tp.deeptmhmm_label, tp.tm_helix_count,
                tp.ecd_length_residues, tp.icd_length_residues,
                tp.n_terminal_orientation, tp.c_terminal_orientation,
                tp.signal_peptide_length, tp.sequence
           FROM compara_paralog cp
           LEFT JOIN topology_public tp
             ON tp.uniprot_acc = cp.paralog_uniprot_acc
            AND tp.cohort = 'human_canonical' AND tp.topology_version = ?
          WHERE cp.human_uniprot_acc = ? AND cp.paralog_version = ?
            AND cp.paralog_gene_symbol IS NOT NULL
            AND cp.paralog_uniprot_acc IS NOT NULL
          ORDER BY cp.rank_by_ecd_identity ASC NULLS LAST LIMIT 50`
      ).bind(canonicalTopoVersion ?? "", uniprot, paralogVersion).all().catch(() => null);
      // Belt-and-suspenders dedup: the LEFT JOIN against topology_public
      // is keyed on (uniprot_acc, cohort, topology_version); a stale
      // topology_release would let multiple cohort/version rows survive
      // per paralog and double-count entries here.
      const presults = dedupeByKey(
        paralogRows?.results ?? [],
        (r) => r.paralog_uniprot_acc,
      );
      if (presults.length > 0) {
        if (!record.deterministic_features) record.deterministic_features = {};
        const CLOSE_PARALOG_THRESHOLD = 80.0;
        record.deterministic_features.paralogs = presults.map((r) => {
          const fullId = r.biomart_percent_identity != null ? Number(r.biomart_percent_identity) : null;
          const ecdId = r.ecd_pct_identity != null ? Number(r.ecd_pct_identity) : null;
          const isClose = fullId !== null && fullId >= CLOSE_PARALOG_THRESHOLD;
          // Topology + sequence surfaced only for close paralogs (same gate
          // as the Python annotator). Far/ECD-less paralogs stay chip-only.
          let topo = null, tmc = null, ecdl = null, seq = null;
          if (isClose && r.per_residue_topology) {
            topo = r.per_residue_topology;
            seq = r.sequence ?? null;
            tmc = r.tm_helix_count != null ? Number(r.tm_helix_count) : null;
            ecdl = r.ecd_length_residues != null ? Number(r.ecd_length_residues) : null;
          }
          return {
            paralog_symbol: r.paralog_gene_symbol,
            paralog_uniprot_acc: r.paralog_uniprot_acc,
            ecd_pct_identity: ecdId,
            full_length_pct_identity: fullId,
            family_id: r.family_id || "",
            compara_version: r.compara_version || "",
            per_residue_topology: topo,
            tm_helix_count: tmc,
            ecd_length_residues: ecdl,
            sequence: seq,
          };
        });
      }
    }

    // ----- orthologs (mouse + cynomolgus) -----
    // Mirror _fetch_orthologs. Enrich when the field is missing OR (both
    // species lists are empty AND ``checked`` is not True). The Python
    // annotator projects the human canonical topology onto each ortholog
    // (via merge.ortholog_topology_projection) — that's a global alignment
    // not feasible in a Worker, so we ship the RAW DeepTMHMM-on-ortholog
    // topology (cohort='mouse_ortholog' / 'cyno_ortholog') with
    // topology_projection_source=null. Records that need the projected
    // topology get it via re-annotation, not at serve time. Higher-order
    // (one-to-many) ortholog rows are emitted as-is, same as the Python
    // path — there's no is_canonical filter on compara_ortholog_ecd.
    const existingOrthologs = record?.deterministic_features?.orthologs;
    const orthologsChecked = existingOrthologs?.checked === true;
    const orthologsEmpty = !existingOrthologs
      || ((existingOrthologs.mouse?.length ?? 0) === 0
          && (existingOrthologs.cynomolgus?.length ?? 0) === 0);
    const orthologsNeedEnrich = orthologsEmpty && !orthologsChecked;
    if (orthologsNeedEnrich && orthologEcdVersion) {
      // Pick the topology_version that has ortholog cohorts. The Python
      // annotator resolves mouse_topo_version specifically; in practice
      // mouse_ortholog + cyno_ortholog share a version. Default to the
      // canonical topology_version if no mouse-cohort row exists.
      const mouseTopoRow = await env.DB.prepare(
        `SELECT topology_version FROM topology_release
            WHERE topology_version IN (
              SELECT DISTINCT topology_version FROM topology_public WHERE cohort = 'mouse_ortholog'
            )
            ORDER BY loaded_at DESC LIMIT 1`
      ).first().catch(() => null);
      const orthoTopoVersion = mouseTopoRow?.topology_version ?? canonicalTopoVersion ?? "";
      const orthologRows = await env.DB.prepare(
        `SELECT eo.species, eo.ortholog_uniprot_acc, eo.ortholog_ensembl_gene,
                eo.ortholog_gene_symbol, eo.ecd_pct_identity,
                co.percent_identity AS full_length_pct_identity,
                tp.tm_helix_count, tp.ecd_length_residues,
                tp.per_residue_topology, tp.deeptmhmm_label,
                tp.sequence AS ortholog_sequence,
                eo.compara_release
           FROM compara_ortholog_ecd eo
           LEFT JOIN topology_public tp
             ON tp.uniprot_acc = eo.ortholog_uniprot_acc
            AND tp.topology_version = ?
            AND (
              (eo.species = 'mouse' AND tp.cohort = 'mouse_ortholog') OR
              (eo.species IN ('cynomolgus','cyno') AND tp.cohort = 'cyno_ortholog')
            )
           LEFT JOIN compara_ortholog co
             ON co.release_version = eo.compara_release
            AND co.human_ensembl_gene = eo.human_ensembl_gene
            AND co.species = eo.species
            AND co.ortholog_ensembl_gene = eo.ortholog_ensembl_gene
          WHERE eo.human_uniprot_acc = ?
            AND eo.ortholog_ecd_version = ?
          ORDER BY eo.species ASC`
      ).bind(orthoTopoVersion, uniprot, orthologEcdVersion).all().catch(() => null);
      // Belt-and-suspenders dedup: the LEFT JOIN against topology_public is
      // gated on topology_version; a stale topology_release lets multiple
      // versions slip through and produce two rows per (species, ortholog).
      // Key by (species, ortholog_uniprot_acc) — same gene's mouse + cyno
      // rows are legitimately distinct.
      const oresults = dedupeByKey(
        orthologRows?.results ?? [],
        (r) => `${r.species}::${r.ortholog_uniprot_acc}`,
      );
      const mouse = [];
      const cyno = [];
      const nowIso = new Date().toISOString();
      for (const r of oresults) {
        const species = String(r.species || "").toLowerCase();
        const ecdPct = r.ecd_pct_identity != null ? Number(r.ecd_pct_identity) : null;
        const fullPct = r.full_length_pct_identity != null ? Number(r.full_length_pct_identity) : null;
        const entry = {
          is_canonical: true,
          isoform_id: r.ortholog_uniprot_acc || "",
          ensembl_id: r.ortholog_ensembl_gene || "",
          ortholog_uniprot_acc: r.ortholog_uniprot_acc || "",
          ortholog_symbol: r.ortholog_gene_symbol || "",
          type: "one2one",
          ecd_pct_identity_to_human_canonical: ecdPct,
          // Similarity not yet wired in the underlying table; mirror identity.
          ecd_pct_similarity_to_human_canonical: ecdPct,
          full_length_pct_identity_to_human_canonical: fullPct,
          ecd_length_residues: Number(r.ecd_length_residues || 0),
          tm_helix_count: Number(r.tm_helix_count || 0),
          compara_version: r.compara_release || "",
          retrieved_at: nowIso,
          // Raw DeepTMHMM-on-ortholog values; the Python annotator's
          // projection is skipped at serve time (no alignment library in
          // the Worker). projection_source=null signals "raw values".
          per_residue_topology: r.per_residue_topology ?? null,
          deeptmhmm_label: r.deeptmhmm_label != null ? String(r.deeptmhmm_label) : null,
          topology_projection_source: null,
          tm_absent_from_model: false,
          n_tm_regions_absent: 0,
          sequence: r.ortholog_sequence ?? null,
        };
        if (species === "mouse") {
          mouse.push(entry);
        } else if (species === "cynomolgus" || species === "cyno") {
          cyno.push(entry);
        }
      }
      if (mouse.length > 0 || cyno.length > 0) {
        if (!record.deterministic_features) record.deterministic_features = {};
        record.deterministic_features.orthologs = {
          mouse,
          cynomolgus: cyno,
          checked: true,
        };
      }
    }

    // ----- surface_bind -----
    // Mirror tools.surface_bind.lookup (D1-first). SURFACE-Bind's
    // ``surface_bind_protein`` table is keyed PRIMARY KEY on uniprot_acc
    // (one row per acc), and ``surface_bind_site`` is keyed (uniprot_acc,
    // site_id). There's no separate release table; the version is the
    // per-row ``surfacebind_version`` column. ORDER BY surfacebind_version
    // DESC LIMIT 1 is defensive — today the PK guarantees uniqueness, so
    // the ORDER BY is a no-op, but it keeps the query future-proof if the
    // schema ever allows multi-version coexistence (e.g. v1 + v2 atlases).
    //
    // Enrich when the record's surface_bind is missing OR carries
    // ``has_data=false`` despite a row existing in D1. Annotator-baked
    // positives win — a v2-orchestrator record with a real
    // SurfaceBindFeatures block is left alone so the data the LLM saw at
    // annotation time matches what the viewer renders.
    const existingSurfaceBind = record?.deterministic_features?.surface_bind;
    const sbNeedsEnrichment = !existingSurfaceBind
      || existingSurfaceBind.has_data === false;
    if (sbNeedsEnrichment) {
      const sbProteinRow = await env.DB.prepare(
        `SELECT chain, main_class, sub_class, protein_name, n_sites,
                n_seeds_alpha, n_seeds_beta, n_seeds_total, pdbs
           FROM surface_bind_protein
          WHERE uniprot_acc = ?
          ORDER BY surfacebind_version DESC
          LIMIT 1`
      ).bind(uniprot).first().catch(() => null);
      if (sbProteinRow) {
        const sbSiteRows = await env.DB.prepare(
          `SELECT site_id, anchor_residue, area_a2, n_seeds_alpha,
                  n_seeds_beta, hydrophobicity
             FROM surface_bind_site
            WHERE uniprot_acc = ?
            ORDER BY site_id`
        ).bind(uniprot).all().catch(() => null);
        // ``pdbs`` is stored as a JSON-encoded array string (see
        // scripts/sync_surface_bind_to_d1.py: ``json.dumps(entry.get("pdbs",
        // []))``). Defensively accept a real array (forward-compat), an
        // empty / null cell, or a comma-separated string (legacy snapshots).
        let pdbs = [];
        const rawPdbs = sbProteinRow.pdbs;
        if (Array.isArray(rawPdbs)) {
          pdbs = rawPdbs.map((x) => String(x)).filter(Boolean);
        } else if (typeof rawPdbs === "string" && rawPdbs.trim()) {
          const trimmed = rawPdbs.trim();
          if (trimmed.startsWith("[")) {
            try {
              const decoded = JSON.parse(trimmed);
              if (Array.isArray(decoded)) {
                pdbs = decoded.map((x) => String(x)).filter(Boolean);
              }
            } catch {
              // Fall through to comma-split below.
            }
          }
          if (pdbs.length === 0) {
            pdbs = trimmed.split(",").map((x) => x.trim()).filter(Boolean);
          }
        }
        const sites = (sbSiteRows?.results ?? []).map((s) => ({
          site_id: Number(s.site_id),
          anchor_residue: Number(s.anchor_residue),
          area_a2: Number(s.area_a2),
          n_seeds_alpha: Number(s.n_seeds_alpha),
          n_seeds_beta: Number(s.n_seeds_beta),
          hydrophobicity: Number(s.hydrophobicity),
        }));
        if (!record.deterministic_features) record.deterministic_features = {};
        record.deterministic_features.surface_bind = {
          has_data: true,
          n_sites: Number(sbProteinRow.n_sites ?? 0),
          n_seeds_alpha: Number(sbProteinRow.n_seeds_alpha ?? 0),
          n_seeds_beta: Number(sbProteinRow.n_seeds_beta ?? 0),
          n_seeds_total: Number(sbProteinRow.n_seeds_total ?? 0),
          chain: sbProteinRow.chain ?? null,
          sites,
          main_class: sbProteinRow.main_class ?? null,
          sub_class: sbProteinRow.sub_class ?? null,
          protein_name: sbProteinRow.protein_name ?? null,
          pdbs,
          // ``representative_structure`` is sourced from PDBe SIFTS at
          // annotation time (PR #54), not from the SURFACE-Bind tables.
          // Preserve whatever the record carried (often null) rather than
          // dropping it — the structure ranker isn't wired to the Worker.
          representative_structure:
            existingSurfaceBind?.representative_structure ?? null,
          source: "SURFACE-Bind v1 (Balbi 2026 PNAS)",
          attribution: "© Balbi et al., Correia lab — EPFL / Inria / Novo Nordisk",
          citation: "10.1073/pnas.2506269123",
        };
      }
    }
  }
  // Triage-signal overlay — the load-bearing freshness fix for the
  // June-2026 silent-failure bug. The annotator bakes `triage_signal` +
  // `triage_reasoning` at deep-dive time by reading
  // `triage_run_public`; when that read silently failed (partial creds /
  // priority-list drift / stale run_ids), the record shipped with
  // `triage_signal=unknown` despite D1 carrying the Sonnet verdict.
  // Overlaying live closes the loop: even a corrupted/stale record
  // serves the verdict D1 actually has, no re-annotation required.
  //
  // Posture matches the other enrich steps: fail-open on a D1 hiccup
  // (don't break the per-gene endpoint), and don't overwrite a
  // populated record with null (a brand-new gene the triage sweep
  // hasn't covered yet leaves the annotator's call intact).
  try {
    const triagePrior = await fetchTriagePrior(env, sym);
    if (triagePrior) {
      record.triage_signal =
        TRIAGE_VERDICT_TO_SIGNAL[triagePrior.verdict] ?? "unknown";
      if (triagePrior.reasoning && triagePrior.reasoning.trim()) {
        record.triage_reasoning = triagePrior.reasoning;
      }
    }
  } catch (e) {
    // Best-effort — never break the endpoint over a triage miss.
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
      WHERE release_version = ? AND human_gene_symbol = ? COLLATE NOCASE
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
const DDF_KEYS = [
  "surface_accessibility",
  "confidence",
  "state_dependence",
  "surface_call_reason",
  "subcategory",
  "llm_family",
  "evidence_grade",
  "evidence_density",
  // schema 2.14.0 — unique-paper count behind the evidence list
  // (= length of the distinct span.source.source_id set across the
  // evidence rows). The filterable understudied-vs-well-studied
  // signal; populated on records annotated under schema 2.14+ or
  // backfilled via scripts/backfill_n_papers_selected.py. Banded
  // into low/moderate/high below in handleCatalog using cohort
  // percentile cutoffs (so the band auto-adjusts as the cohort
  // grows).
  "n_papers_selected",
  // schema 2.14.0 — TRUE pre-trim discovery corpus size sourced from
  // dual.a{1,2}.n_papers_discovered (= len of cumulative_discovered
  // in the plan_trim_select runner, which is the EuropePMC +
  // PubTator NER + gene2pubmed union before any clip selection).
  // Display-only on the viewer; gives readers context for whether a
  // low-n_papers_selected value reflects an understudied gene or
  // aggressive agent filtering. Null on records annotated before
  // the field existed; honest backfill requires a discover-only
  // rerun (no LLM, around 30 seconds per gene).
  "n_papers_found",
  "ecd_accessibility_class",
  "expression_level",
  "expression_breadth",
  "surface_specificity",
  "co_receptor_dependency",
  "has_known_ligand",
  "low_endogenous_expression",
  "overexpression_surface_localization_observed",
  "has_shed_form",
  "has_secreted_form",
  "has_epitope_masking",
  "has_restricted_subdomain",
  "n_term_extracellular",
  "c_term_extracellular",
  "tumor_associated",
  "induction_trigger",
  "has_live_cell_surface_evidence",
];

// Bin an ECD %-identity into a coarse band. Keep in sync with
// viewer/lib/deep-dive-fields.ts:ecdBand. `null` (no ortholog/paralog in
// Compara) → "none".
function ecdBand(pct, hi, mid) {
  if (pct == null) return "none";
  if (pct >= hi) return "high";
  if (pct >= mid) return "moderate";
  return "low";
}

const ECD_BAND_SOURCES = [
  ["cyno_ortholog_ecd", "cyno_ortholog_ecd_pct_identity", 90, 70],
  ["mouse_ortholog_ecd", "mouse_ortholog_ecd_pct_identity", 90, 70],
  ["max_paralog_ecd", "max_paralog_ecd_pct_identity", 70, 40],
];

// Try JSON.parse and return the result, or null on failure / falsy input.
// Also passes through pre-parsed objects — SQLite `json_extract` on an
// object path returns a JSON string, but D1's client-side handling can
// vary, so accepting either shape keeps the caller compact.
function safeJsonParse(s) {
  if (s == null) return null;
  if (typeof s === "object") return s;
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

// Read-time DDF projection from a set of pre-extracted sub-blocks
// rather than the full ~120 KB record JSON.
//
// Historical shape: this function took the entire `annotation_json`
// string, JSON.parsed it, and walked half a dozen sub-paths. At scale
// (~1.2k deep-dive records × ~120 KB each) that meant handleCatalog
// pulled ~145 MB of JSON through one D1 query and blew D1's per-query
// isolate-memory cap (see runbook + wrangler tail on 2026-07-01 —
// "D1_ERROR: D1 DB's isolate exceeded its memory limit and was reset").
//
// New shape: the two catalog queries `json_extract` just the 6
// sub-paths this projection reads — `$.filters`,
// `$....primary_compartment`, `$....restricted_subdomain`,
// `$....secreted_form`, `$....surface_bind`,
// `$....homo_oligomerization` — total ~4 KB per row instead of ~120 KB.
// Same public output; ~30× headroom under D1's cap.
//
// `parts` fields (all null-safe):
//   * `filters`             — parsed `$.filters` object (or null)
//   * `primary_compartment` — scalar string (or null)
//   * `restricted_subdomain`, `secreted_form`,
//     `surface_bind`, `homo_oligomerization` — parsed objects (or null)
function projectDeepDiveFiltersFromParts(parts) {
  const f = parts.filters;
  if (!f || typeof f !== "object") return null;
  const out = {};
  let any = false;
  for (const k of DDF_KEYS) {
    if (f[k] !== undefined && f[k] !== null) {
      out[k] = f[k];
      any = true;
    }
  }
  // Derived ECD bands — the numeric source is present (number or null) when
  // the record carries it; "none" is a real facet (no ortholog/paralog).
  for (const [key, src, hi, mid] of ECD_BAND_SOURCES) {
    if (src in f) {
      out[key] = ecdBand(f[src], hi, mid);
      any = true;
    }
  }
  // Primary subcellular compartment lives in biological_context, not the
  // top-level `filters` block. Keep in sync with viewer/lib/deep-dive-fields.ts
  // `pickDeepDiveFilters`. Powers the "Primary localization" facet on the
  // catalog filter panel + compare tool.
  if (typeof parts.primary_compartment === "string") {
    out.primary_compartment = parts.primary_compartment;
    any = true;
  }
  // Restricted subdomain kind — sourced from accessibility_risks, but
  // ONLY when present === true. The schema requires `domain` to always
  // be set with "unknown" as the not-applicable sentinel; projecting
  // unconditionally would pile every non-restricted gene into the
  // "unknown" bucket and drown the signal. Keep in sync with the
  // viewer's `pickDeepDiveFilters`.
  const rs = parts.restricted_subdomain;
  if (rs && rs.present === true && typeof rs.domain === "string") {
    out.restricted_subdomain_kind = rs.domain;
    any = true;
  }
  // Same project-when-present contract for secreted_form.source — only
  // surface the source when a secreted form actually exists.
  const sf = parts.secreted_form;
  if (sf && sf.present === true && typeof sf.source === "string") {
    out.secreted_form_source = sf.source;
    any = true;
  }
  // SURFACE-Bind facets (Balbi 2026, PMID 41604262) — sourced from
  // deterministic_features.surface_bind. Keep in sync with the
  // viewer's pickDeepDiveFilters. The 4-way bucket mirrors the
  // existing catalog quick-filter (any / ≥1 / ≥3 / not_in).
  const sb = parts.surface_bind;
  if (sb) {
    const hasData = sb.has_data === true;
    const nSites = typeof sb.n_sites === "number" ? sb.n_sites : 0;
    let bucket = "not_scored";
    if (hasData) {
      if (nSites >= 3) bucket = "high";
      else if (nSites >= 1) bucket = "moderate";
      else bucket = "none";
    }
    out.surface_bind_targetability = bucket;
    any = true;
    if (hasData && typeof sb.main_class === "string") {
      out.surface_bind_main_class = sb.main_class;
    }
  }
  // Schweke 2024 (PMID 38325366) — sourced from
  // deterministic_features.homo_oligomerization.is_homo_oligomer.
  // Schweke is positives-only; an absent/empty block (pre-Schweke
  // annotation) means "not in the predicted homomer refset". Coerce to
  // `false` for absent/false so the catalog has a consistent value to
  // filter on.
  const ho = parts.homo_oligomerization;
  out.is_homo_oligomer = ho?.is_homo_oligomer === true;
  any = true;
  // Transmembrane-topology facets — sourced from
  // deterministic_features.canonical_topology (DeepTMHMM v1.0.24 +
  // UniProt curated topology). SCALAR fields only (json_extracted in
  // handleCatalog); the full per_residue_topology string is never
  // pulled at catalog scale. Keep in sync with the viewer's
  // pickDeepDiveFilters. `has_tm` / `tm_count_band` derive from the
  // TM-helix count; `is_gpi_anchored` passes through when the record
  // carries it (records/topology rows predating the GPI field leave it
  // absent — the filter simply won't populate for those genes).
  const tmc = parts.topo_tm_helix_count;
  if (typeof tmc === "number") {
    out.has_tm = tmc > 0;
    out.tm_count_band = tmc === 0 ? "none" : tmc === 1 ? "single" : "multi";
    any = true;
  }
  const gpi = parts.topo_is_gpi_anchored;
  if (gpi === true || gpi === 1) {
    out.is_gpi_anchored = true;
    any = true;
  } else if (gpi === false || gpi === 0) {
    out.is_gpi_anchored = false;
    any = true;
  }
  return any ? out : null;
}

// Build a DDF-parts bag from the `sa_ddf_*` (or `ddf_*`) columns
// emitted by handleCatalog's json_extract queries. `filters` is the
// only value guaranteed to be present when the row has a deep dive;
// the others are null when the annotator didn't populate that block.
function ddfPartsFromRow(row, prefix) {
  return {
    filters: safeJsonParse(row[`${prefix}filters`]),
    primary_compartment:
      typeof row[`${prefix}primary_compartment`] === "string"
        ? row[`${prefix}primary_compartment`]
        : null,
    restricted_subdomain: safeJsonParse(row[`${prefix}restricted_subdomain`]),
    secreted_form: safeJsonParse(row[`${prefix}secreted_form`]),
    surface_bind: safeJsonParse(row[`${prefix}surface_bind`]),
    homo_oligomerization: safeJsonParse(row[`${prefix}homo_oligomerization`]),
    // Canonical-topology scalars only. The catalog query json_extracts the
    // three SCALAR paths — NEVER the whole canonical_topology object, which
    // carries per_residue_topology (a ~protein-length string) that would
    // blow D1's per-query isolate memory across ~1.2k catalog rows. See the
    // json_extract paths in handleCatalog.
    topo_tm_helix_count:
      typeof row[`${prefix}topo_tm_helix_count`] === "number"
        ? row[`${prefix}topo_tm_helix_count`]
        : null,
    topo_is_gpi_anchored: row[`${prefix}topo_is_gpi_anchored`] ?? null,
    topo_signal_peptide_length:
      typeof row[`${prefix}topo_signal_peptide_length`] === "number"
        ? row[`${prefix}topo_signal_peptide_length`]
        : null,
  };
}

// CPU budget on this handler is tight — the catalog response is ~4.5MB
// across 19k+ rows, and Cloudflare Workers cap at 30ms CPU (50ms with
// Bundled). Pre-2026-05-25 the handler ran 6 separate D1 queries +
// 5 JS-side Map builds + 19k×4 per-row Map.gets, which routinely blew
// the cap and surfaced as 503 / CF error 1102 to readers. The current
// shape uses a single LEFT JOIN to fold the universe + deep-dive +
// SURFACE-Bind lookups into one round-trip (SQLite does the join work),
// drops the HGNC-id-per-row backfill (the viewer doesn't read it; the
// TSV export endpoints do hgnc_id via a separate join), and wraps the
// whole handler in caches.default so the cold-start CPU cost is paid
// once per universe_version, not per request.
async function handleCatalog(env, request) {
  // Self-managed edge cache, keyed on the request URL. CF's HTTP cache
  // already does this via Cache-Control, but the in-Worker cache lets
  // us serve a stored Response without entering the join/format code
  // at all on warm hits — that's the difference between 1ms and 100ms
  // of CPU when the edge cache lottery loses. TTL still governed by
  // the response's Cache-Control header (set in `json` to 1 min for
  // /v1/catalog), so a re-deploy or universe-version bump surfaces on
  // the next miss.
  const cache = caches.default;
  const cacheKey = new Request(new URL("/v1/catalog", "https://catalog.cache").href, {
    method: "GET",
  });
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
            sb.n_sites AS sb_n_sites,
            sa.ddf_filters AS sa_ddf_filters,
            sa.ddf_primary_compartment AS sa_ddf_primary_compartment,
            sa.ddf_restricted_subdomain AS sa_ddf_restricted_subdomain,
            sa.ddf_secreted_form AS sa_ddf_secreted_form,
            sa.ddf_surface_bind AS sa_ddf_surface_bind,
            sa.ddf_homo_oligomerization AS sa_ddf_homo_oligomerization,
            sa.ddf_topo_tm_helix_count AS sa_ddf_topo_tm_helix_count,
            sa.ddf_topo_is_gpi_anchored AS sa_ddf_topo_is_gpi_anchored,
            sa.ddf_topo_signal_peptide_length AS sa_ddf_topo_signal_peptide_length,
            CASE WHEN sa.gene_symbol IS NOT NULL THEN 1 ELSE 0 END AS has_deep_dive
       FROM candidate_universe_public u
       LEFT JOIN gene_identifier_public gi ON gi.hgnc_symbol = u.gene_symbol
       LEFT JOIN surface_bind_protein sb ON sb.uniprot_acc = u.uniprot_acc
       LEFT JOIN (
         -- One row per gene: the latest (schema_version, prompt_corpus_version)
         -- combo. The schema_version match is load-bearing today (the
         -- PK is still (gene_symbol, schema_version) until the
         -- migration runbook is applied); prompt_corpus is a secondary
         -- tie-break that only matters when two rows share schema_version.
         SELECT gene_symbol,
                json_extract(annotation_json, '$.filters') AS ddf_filters,
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
                json_extract(annotation_json, '$.deterministic_features.canonical_topology.is_gpi_anchored') AS ddf_topo_is_gpi_anchored,
                json_extract(annotation_json, '$.deterministic_features.canonical_topology.signal_peptide_length') AS ddf_topo_signal_peptide_length
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
  // then most common reason within the winning verdict. Tiebreak on
  // most recent `created_at` (matches the single-replicate behavior
  // when there's only one row). For 1-rep cells the majority degenerates
  // to that single verdict — backward-compatible with the pre-2/3-rep
  // catalog. The matching per-cell majority logic for the benchmark
  // drawer lives in `handleTriageCell` below; this is the catalog-tier
  // mirror so the genome-wide summary surfaces consensus the same way.
  //
  // Coverage today:
  //   - Sonnet/ncbi: full ~19k genome (genome_full_sonnet_ncbi_v2,
  //                  with multi-rep on the ambiguous-no zero-DB slice
  //                  to expose 2/3 consensus).
  //   - Haiku/ncbi: 147 SurfaceBench genes only (mainbench_canonical_v2)
  //   - Opus/ncbi: 147 SurfaceBench genes only (mainbench_canonical_v2)
  // So most rows will show only the Sonnet column populated.
  const CATALOG_MODELS = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"];
  const triageByGene = new Map();
  const triageRows = await env.DB.prepare(
    `SELECT gene_symbol, model, predicted_verdict, predicted_reason, created_at
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
  // For each cell, take the most common verdict, then the most common
  // reason within that verdict. Both tiebreak on max(created_at).
  for (const [key, reps] of triageReplicates) {
    const [gene_symbol, model] = key.split("\t");
    const vTally = new Map();
    const vMax = new Map();
    for (const r of reps) {
      vTally.set(r.predicted_verdict, (vTally.get(r.predicted_verdict) || 0) + 1);
      const prev = vMax.get(r.predicted_verdict);
      if (prev == null || r.created_at > prev) vMax.set(r.predicted_verdict, r.created_at);
    }
    const winVerdict = [...vTally.entries()].sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      const ma = vMax.get(a[0]) || "";
      const mb = vMax.get(b[0]) || "";
      return mb < ma ? -1 : (mb > ma ? 1 : 0);
    })[0][0];
    const rTally = new Map();
    const rMax = new Map();
    for (const r of reps) {
      if (r.predicted_verdict !== winVerdict) continue;
      rTally.set(r.predicted_reason, (rTally.get(r.predicted_reason) || 0) + 1);
      const prev = rMax.get(r.predicted_reason);
      if (prev == null || r.created_at > prev) rMax.set(r.predicted_reason, r.created_at);
    }
    const winReason = [...rTally.entries()].sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      const ma = rMax.get(a[0]) || "";
      const mb = rMax.get(b[0]) || "";
      return mb < ma ? -1 : (mb > ma ? 1 : 0);
    })[0][0];
    let perModel = triageByGene.get(gene_symbol);
    if (!perModel) { perModel = {}; triageByGene.set(gene_symbol, perModel); }
    perModel[model] = { verdict: winVerdict, reason: winReason };
  }

  // Pubmed_ncbi rescue lane: if Sonnet's pubmed_ncbi call is more
  // inclusive than its ncbi call (pubmed says yes/contextual, ncbi
  // says no), prefer pubmed for the catalog's Sonnet slot. Justified
  // by mainbench: pubmed_ncbi catches the KLK2/SRC class of FNs that
  // ncbi misses; never overrides ncbi-yes/contextual since pubmed-no
  // doesn't add evidence-of-absence.
  //
  // Pulls all pubmed_ncbi sonnet replicates, computes the same
  // majority-verdict + within-verdict-majority-reason aggregate as
  // the ncbi loop above, then applies the prefer-positive rule.
  const pubmedRows = await env.DB.prepare(
    `SELECT gene_symbol, predicted_verdict, predicted_reason, created_at
       FROM triage_run_public
      WHERE prompt_variant = 'pubmed_ncbi'
        AND model = 'claude-sonnet-4-6'
        AND predicted_verdict IS NOT NULL`
  ).all();
  const pubmedReps = new Map();
  for (const r of pubmedRows.results) {
    let lst = pubmedReps.get(r.gene_symbol);
    if (!lst) { lst = []; pubmedReps.set(r.gene_symbol, lst); }
    lst.push(r);
  }
  for (const [gene_symbol, reps] of pubmedReps) {
    const vTally = new Map();
    const vMax = new Map();
    for (const r of reps) {
      vTally.set(r.predicted_verdict, (vTally.get(r.predicted_verdict) || 0) + 1);
      const prev = vMax.get(r.predicted_verdict);
      if (prev == null || r.created_at > prev) vMax.set(r.predicted_verdict, r.created_at);
    }
    const winVerdict = [...vTally.entries()].sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      const ma = vMax.get(a[0]) || ""; const mb = vMax.get(b[0]) || "";
      return mb < ma ? -1 : (mb > ma ? 1 : 0);
    })[0][0];
    const rTally = new Map();
    const rMax = new Map();
    for (const r of reps) {
      if (r.predicted_verdict !== winVerdict) continue;
      rTally.set(r.predicted_reason, (rTally.get(r.predicted_reason) || 0) + 1);
      const prev = rMax.get(r.predicted_reason);
      if (prev == null || r.created_at > prev) rMax.set(r.predicted_reason, r.created_at);
    }
    const winReason = [...rTally.entries()].sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      const ma = rMax.get(a[0]) || ""; const mb = rMax.get(b[0]) || "";
      return mb < ma ? -1 : (mb > ma ? 1 : 0);
    })[0][0];
    // Apply the rescue rule.
    const perModel = triageByGene.get(gene_symbol);
    if (!perModel) continue;
    const ncbi = perModel["claude-sonnet-4-6"];
    if (!ncbi) continue;
    if (ncbi.verdict === "no" && (winVerdict === "yes" || winVerdict === "contextual")) {
      perModel["claude-sonnet-4-6"] = { verdict: winVerdict, reason: winReason };
    }
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
  const rows = enrichedRows.results.map((u) => {
    covered.add(u.gene_symbol);
    if (u.has_deep_dive) deepSet.add(u.gene_symbol);
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
    if (u.has_deep_dive) row.deep_dive = true;
    if (u.sb_n_sites != null) row.sb = u.sb_n_sites;
    // Slim deep-dive filter projection — only the 21 fields the catalog
    // UI actually filters on. Skips continuous fields (max_paralog_ecd_
    // pct_identity, ortholog identities) and `has_restricted_subdomain`
    // (moved to the Biology card). Parsing failures fall through silently
    // — a malformed record still gets the deep_dive=true marker, just
    // without the filterable rollups.
    if (u.has_deep_dive) {
      const ddf = projectDeepDiveFiltersFromParts(ddfPartsFromRow(u, "sa_ddf_"));
      if (ddf) row.ddf = ddf;
    }
    return row;
  });

  // Append deep-dive-only genes (annotated but not in the universe — rare;
  // e.g. HSPA1A's conditional-surface story). Same json_extract slim
  // projection as the main join above — never pull the full
  // annotation_json (~120 KB × 1.2k rows blows D1's per-query isolate cap).
  const orphanDeep = await env.DB.prepare(
    `SELECT sa1.gene_symbol,
            json_extract(sa1.annotation_json, '$.filters') AS ddf_filters,
            json_extract(sa1.annotation_json, '$.biological_context.subcellular_localization.primary_compartment') AS ddf_primary_compartment,
            json_extract(sa1.annotation_json, '$.accessibility_risks.restricted_subdomain') AS ddf_restricted_subdomain,
            json_extract(sa1.annotation_json, '$.accessibility_risks.secreted_form') AS ddf_secreted_form,
            json_extract(sa1.annotation_json, '$.deterministic_features.surface_bind') AS ddf_surface_bind,
            json_extract(sa1.annotation_json, '$.deterministic_features.homo_oligomerization') AS ddf_homo_oligomerization,
            -- Canonical-topology SCALARS only (see main catalog query).
            json_extract(sa1.annotation_json, '$.deterministic_features.canonical_topology.tm_helix_count') AS ddf_topo_tm_helix_count,
            json_extract(sa1.annotation_json, '$.deterministic_features.canonical_topology.is_gpi_anchored') AS ddf_topo_is_gpi_anchored,
            json_extract(sa1.annotation_json, '$.deterministic_features.canonical_topology.signal_peptide_length') AS ddf_topo_signal_peptide_length,
            gi.uniprot_acc AS uniprot_acc
       FROM surface_annotation sa1
       LEFT JOIN gene_identifier_public gi ON gi.hgnc_symbol = sa1.gene_symbol
      WHERE sa1.schema_version = (
        SELECT MAX(schema_version) FROM surface_annotation sa2
         WHERE sa2.gene_symbol = sa1.gene_symbol
      )
        AND COALESCE(sa1.prompt_corpus_version, '0.0.0') = (
          SELECT MAX(COALESCE(prompt_corpus_version, '0.0.0'))
            FROM surface_annotation sa3
           WHERE sa3.gene_symbol = sa1.gene_symbol
             AND sa3.schema_version = sa1.schema_version
        )`
  ).all();
  for (const r of orphanDeep.results) {
    const sym = r.gene_symbol;
    if (covered.has(sym)) continue;
    deepSet.add(sym);
    const row = { symbol: sym, n_sources: 0, db: 0, deep_dive: true };
    if (r.uniprot_acc) row.uniprot = r.uniprot_acc;
    const t = packTriage(sym);
    if (t) row.tr = t;
    const dd = projectDeepDiveFiltersFromParts(ddfPartsFromRow(r, "ddf_"));
    if (dd) row.ddf = dd;
    rows.push(row);
  }

  // n_papers_selected band-baking — single forward pass over the catalog
  // collects the populated values (deep-dive rows only); cohort
  // percentile cutoffs p10 / p90 are computed once and attached as
  // ddf.n_papers_selected_band (low / moderate / high) on each
  // ddf-bearing row. Bands are mutually exclusive (low at-or-below p10,
  // moderate p10–p90, high at-or-above p90), matching the viewer's
  // filter UI. Cutoffs travel with the response so the viewer can
  // render the tooltip with concrete numbers (e.g. low at-or-below 8
  // papers · high at-or-above 47 papers). When fewer than 3 records
  // carry the value the bands are skipped entirely — percentile
  // estimates aren't meaningful yet, and the viewer falls back to
  // showing only the "any" pill.
  const psValues = [];
  for (const r of rows) {
    const v = r.ddf?.n_papers_selected;
    if (typeof v === "number" && v >= 0) psValues.push(v);
  }
  let psCutoffs = null;
  if (psValues.length >= 3) {
    psValues.sort((a, b) => a - b);
    const at = (q) => {
      // Linear-interpolation percentile (R-7 / NumPy default).
      const idx = (psValues.length - 1) * q;
      const lo = Math.floor(idx);
      const hi = Math.ceil(idx);
      if (lo === hi) return psValues[lo];
      return psValues[lo] + (psValues[hi] - psValues[lo]) * (idx - lo);
    };
    psCutoffs = { p10: Math.round(at(0.1)), p90: Math.round(at(0.9)), n: psValues.length };
    for (const r of rows) {
      const v = r.ddf?.n_papers_selected;
      if (typeof v !== "number") continue;
      r.ddf.n_papers_selected_band =
        v <= psCutoffs.p10 ? "low"
        : v >= psCutoffs.p90 ? "high"
        : "moderate";
    }
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
      //        from deterministic_features.canonical_topology (DeepTMHMM +
      //        UniProt): `ddf.has_tm`, `ddf.tm_count_band`
      //        (none/single/multi), and `ddf.is_gpi_anchored` (present
      //        only on records/topology rows that carry the GPI field).
      row_schema: 7,
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
// grid per the user request 2026-05-15). `headline_variant` is still
// returned for consumers that want to highlight one column.
const BENCH_MATRIX_MODELS = [
  "claude-opus-4-8",
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
const DEFAULT_EXPORT_RUN_ID = "mainbench_canonical_v2";
// The genome-wide Sonnet/NCBI triage sweep over the full protein-coding
// cohort (~19k genes). Used as the run_id for the genome-wide export and
// referenced by the /v1/meta/sizes estimator.
const GENOME_RUN_ID = "genome_full_sonnet_ncbi_v2";
// Reasoning columns appended to the triage export when `with_reasoning=1`.
// Default-off keeps the figure-input exports prose-free (see CLAUDE.md
// "Figure-input TSV conventions" — never ship full reasoning in those);
// opt-in gives the full genome-wide triage corpus with the agent's
// free-text verdict_reasoning for a bulk download.
const REASONING_COLUMNS = ["predicted_key_uncertainty", "verdict_reasoning"];

// Self-describing endpoint catalog for the /v1 index. Kept in one place
// so an agent that lands on the API base discovers the whole surface
// (method + path template + summary) without scraping the docs page.
const V1_ENDPOINTS = [
  { group: "SurfaceBench", method: "GET", path: "/v1/benchmark", summary: "147 ground-truth labels for the current bench_version" },
  { group: "SurfaceBench", method: "GET", path: "/v1/benchmark/{symbol}", summary: "One gene's ground-truth label + rationale" },
  { group: "SurfaceBench", method: "GET", path: "/v1/benchmark/matrix", summary: "Full bench matrix: truth + 5 per-DB flags + verdicts[model][variant]" },
  { group: "SurfaceBench", method: "GET", path: "/v1/benchmark/export.tsv", summary: "Long-format TSV of the bench multi-model sweep" },
  { group: "Genome-wide", method: "GET", path: "/v1/catalog", summary: "Per-gene 5-DB surface-vote matrix + latest triage verdict + deep-dive flag (~19k genes)" },
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
  { group: "Deep dive", method: "GET", path: "/v1/genes/{symbol}", summary: "Full SurfaceomeRecord JSON" },
  { group: "Deep dive", method: "GET", path: "/v1/orthologs/{symbol}", summary: "Mouse + cyno orthologs from the latest Ensembl Compara release" },
  { group: "Utility", method: "GET", path: "/v1/meta/sizes", summary: "Approximate per-endpoint response sizes, computed live from D1" },
  { group: "Utility", method: "GET", path: "/v1", summary: "This index" },
];

// Self-describing API index (HATEOAS-lite). Served at `/v1` and at the
// bare service root so an agent can discover every endpoint + the docs,
// the downloadable skill, llms.txt, the record schema, and the live
// dataset versions in one request. Version lookups are wrapped so a cold
// DB still returns the static catalog.
async function handleV1Index(env) {
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
      record_markdown_template: "https://surfaceome.deliverome.org/data/surfaceome/{symbol}.md",
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
async function handleMetaSizes(env) {
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
    "/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v1": {
      bytes: r0(genome.export_chars + genome.n * EXPORT_NCOLS),
      approx: true,
      note: GENOME_RUN_ID,
    },
    "/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v1&with_reasoning=1": {
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


async function handleTriageExport(env, url) {
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
    `       COALESCE(c.uniprot_surface_flag, 0) AS db_uniprot,`,
    `       COALESCE(c.go_surface_flag, 0)      AS db_go,`,
    `       COALESCE(c.surfy_surface_flag, 0)   AS db_surfy,`,
    `       COALESCE(c.cspa_surface_flag, 0)    AS db_cspa,`,
    `       COALESCE(c.hpa_surface_flag, 0)     AS db_hpa,`,
    `       COALESCE(c.n_sources_surface, 0)    AS n_db_surface,`,
    `       ${[...EXPORT_COLUMNS.slice(1), ...extraCols].map((c) => `t.${c}`).join(", ")}`,
    `  FROM triage_run_public t`,
    `  LEFT JOIN gene_identifier_public gi`,
    `         ON gi.hgnc_symbol = t.gene_symbol`,
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
      WHERE gene_symbol = ? COLLATE NOCASE
      ORDER BY created_at DESC, model, prompt_variant, replicate`
  ).bind(sym).all();
  return json({
    gene_symbol: sym,
    count: rows.results.length,
    runs: rows.results,
  }, { ttl: CACHE_TTL_SHORT });
}

// Per-(gene, model, variant) replicate detail — backs the benchmark
// RationaleDrawer's "majority reason first, then all reps on scroll" view.
// Returns every replicate for the cell (so the drawer can show the
// per-rep spread), plus a computed `majority` block (the binary
// surface-vote majority + the winning-side representative replicate's
// verdict/reason/reasoning). Lazy-loaded by the drawer on open, so the
// /benchmark/matrix payload stays single-rep + small.
async function handleTriageCell(env, symbol, model, variant) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  // model/variant are closed enums — validate against the known sets to
  // avoid an unbounded WHERE and keep the query plan tight.
  if (!BENCH_MATRIX_MODELS.includes(model)) return badRequest("invalid_model");
  if (!BENCH_MATRIX_VARIANTS.includes(variant)) return badRequest("invalid_variant");
  // Scope to the canonical bench run — without this, a gene that also
  // appears in the whole-genome sweep (genome_full_sonnet_ncbi_v1, same
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
  ).bind(DEFAULT_EXPORT_RUN_ID, sym, model, variant).all();
  const reps = rows.results;
  // Binary surface-vote majority over valid-verdict reps (yes/contextual =
  // surface; no = not-surface). Representative = the most common raw
  // verdict on the winning side, with its reason + free-text reasoning.
  const surfaceVote = (v) =>
    (v === "yes" || v === "contextual") ? true : (v === "no" ? false : null);
  const valid = reps.filter((r) => surfaceVote(r.predicted_verdict) !== null);
  let majority = null;
  if (valid.length) {
    const tally = new Map();
    for (const r of valid) {
      const s = surfaceVote(r.predicted_verdict);
      tally.set(s, (tally.get(s) || 0) + 1);
    }
    const ranked = [...tally.entries()].sort((a, b) => b[1] - a[1]);
    const winSide = ranked[0][0];
    const winReps = valid.filter((r) => surfaceVote(r.predicted_verdict) === winSide);
    // Representative raw verdict = most common on the winning side.
    const vTally = new Map();
    for (const r of winReps) {
      vTally.set(r.predicted_verdict, (vTally.get(r.predicted_verdict) || 0) + 1);
    }
    const repVerdict = [...vTally.entries()].sort((a, b) => b[1] - a[1])[0][0];
    const rep = winReps.find((r) => r.predicted_verdict === repVerdict);
    majority = {
      verdict: repVerdict,
      reason: rep?.predicted_reason ?? null,
      reasoning: rep?.verdict_reasoning ?? null,
      confidence: rep?.predicted_confidence ?? null,
      n_reps: valid.length,
      agreement: Math.round((winReps.length / valid.length) * 1000) / 1000,
    };
  }
  return json({
    gene_symbol: sym,
    model,
    prompt_variant: variant,
    majority,
    replicates: reps,
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
  const prefix = url.pathname.startsWith("/surfaceome/") ? "/surfaceome" : "";
  const base = `${url.protocol}//${url.host}${prefix}`;
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
  // Allow lowercase: some HGNC symbols are mixed-case (the Cxorf class,
  // e.g. C11orf24), and gene_symbol is matched COLLATE NOCASE below.
  if (!gene || !/^[A-Za-z0-9-]{1,30}$/.test(gene)) {
    return badRequest("invalid_gene");
  }
  const rows = await env.DB.prepare(
    `SELECT id, submitter_name, comment, approved_at
     FROM feedback_public
     WHERE gene_symbol = ? COLLATE NOCASE
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

    // Per-IP rate limiting on reads (GET), before any handler / D1 work so
    // an over-limit caller is rejected cheaply. POST (feedback submit) has
    // its own Turnstile + KV limiter downstream, so it's excluded here.
    if (request.method === "GET") {
      const limited = await checkRate(env, request, path);
      if (limited) return limited;
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

    if (path === "/v1" || path === "") return handleV1Index(env);
    if (path === "/v1/health") return handleHealth(env);
    if (path === "/v1/genes") return handleGeneList(env);
    if (path === "/v1/catalog") return handleCatalog(env, request);
    if (path === "/v1/benchmark") return handleBenchmarkList(env);
    if (path === "/v1/benchmark/matrix") return handleBenchmarkMatrix(env);
    if (path === "/v1/benchmark/export.tsv") return handleBenchmarkExport(env);
    if (path === "/v1/triage/export.tsv") return handleTriageExport(env, url);
    if (path === "/v1/meta/sizes") return handleMetaSizes(env);
    if (path === "/v1/feedback/moderate") return handleFeedbackModerate(env, url);
    if (path === "/v1/feedback/public") return handleFeedbackPublic(env, url);

    let m;
    if ((m = path.match(/^\/v1\/genes\/([^/]+)$/))) return handleGene(env, m[1]);
    if ((m = path.match(/^\/v1\/orthologs\/([^/]+)$/))) return handleOrthologs(env, m[1]);
    if ((m = path.match(/^\/v1\/benchmark\/([^/]+)$/))) return handleBenchmarkOne(env, m[1]);
    // Per-cell replicate detail (more specific — match before the bare
    // /v1/triage/:symbol route). model = claude-<name>-<n>-<n>; variant
    // = naive|ncbi|web_ncbi|pubmed_ncbi.
    if ((m = path.match(/^\/v1\/triage\/([^/]+)\/([A-Za-z0-9._-]+)\/([a-z_]+)$/))) {
      return handleTriageCell(env, m[1], m[2], m[3]);
    }
    if ((m = path.match(/^\/v1\/triage\/([^/]+)$/))) return handleTriage(env, m[1]);

    return notFound("route_not_found");
  },
};
