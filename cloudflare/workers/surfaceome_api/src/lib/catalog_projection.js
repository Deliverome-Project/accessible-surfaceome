// Deep-dive filter & surface-method projection shared by /v1/catalog and /v1/genes/:symbol.

import { safeJsonParse } from "./http.js";

// Shared preset predicates — the SAME module the viewer ships
// (viewer/lib/catalog-presets.ts). Importing it here (rather than
// re-implementing the rule) is what keeps the catalog rows, the per-gene
// records, and the Zenodo deposit tarball on ONE authoritative deep-dive
// classification — the drift between the Python mirror and the TS rule is
// exactly what put the figures (2274) out of sync with the viewer (1757).
// esbuild (wrangler's bundler) compiles the .ts and erases its type-only
// `import type { DeepDiveFilters }`, so nothing else is pulled in. Verify the
// bundle resolves this cross-dir path BEFORE deploying:
//   cd cloudflare/workers/surfaceome_api && npx wrangler deploy --dry-run --outdir /tmp/wbundle
import { deepDiveTier, isLowLiteratureSurface } from "../../../../../viewer/lib/catalog-presets";

// Attach the shared classification to a response object from its projected
// ddf: deep_dive_tier ∈ {canonical,likely,low,uncertain,no}, deep_dive_facet
// ∈ {induced,cell_type_restricted,null}, and — when the UniProt surface vote
// is known (catalog rows) — the low_lit_uniprot badge. One helper for the
// catalog rows and the per-gene record so they cannot diverge.
export function attachDeepDiveClassification(target, ddf, uniprotSurfacePositive) {
  if (!ddf) return target;
  const { tier, facet } = deepDiveTier(ddf);
  target.deep_dive_tier = tier;
  target.deep_dive_facet = facet;
  if (uniprotSurfacePositive !== undefined) {
    target.low_lit_uniprot = isLowLiteratureSurface(ddf, !!uniprotSurfacePositive);
  }
  return target;
}

export const DDF_KEYS = [
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
export function ecdBand(pct, hi, mid) {
  if (pct == null) return "none";
  if (pct >= hi) return "high";
  if (pct >= mid) return "moderate";
  return "low";
}

export const ECD_BAND_SOURCES = [
  ["cyno_ortholog_ecd", "cyno_ortholog_ecd_pct_identity", 90, 70],
  ["mouse_ortholog_ecd", "mouse_ortholog_ecd_pct_identity", 90, 70],
  ["max_paralog_ecd", "max_paralog_ecd_pct_identity", 70, 40],
];

// Surface-evidence method categories (catalog "Direct surface method" /
// "Supporting method" facets), derived from the record's
// surface_evidence.methods block. Each methods row is one experiment the
// methods builder judged `direct_surface_accessibility` (an antibody or probe
// reached the protein from outside an intact cell) or
// `supports_surface_localization` (at the membrane, outside not shown); other
// relevance levels are not surface evidence and are dropped. The family and
// subclass vocabularies overlap, so the rules are tried in order and the
// first match wins; anything unmatched is "other". Copied verbatim from
// scripts/build_figure_tsvs.py (Supp Fig 13) and mirrored in
// viewer/lib/deep-dive-fields.ts — tests/test_surface_method_rules_sync.py
// fails if the three drift.
export const SURFACE_METHOD_RULES = [
  ["family", "proximity_labeling", "proximity_labeling"],
  ["subclass", "surface_biotinylation", "surface_biotin_pulldown"],
  ["subclass", "cell_surface_capture", "cell_surface_capture_ms"],
  ["subclass", "N_glycoproteomics", "cell_surface_capture_ms"],
  ["family", "glycoproteomics", "cell_surface_capture_ms"],
  ["subclass", "live_cell_flow", "flow_cytometry"],
  ["subclass", "fixed_cell_flow", "flow_cytometry"],
  ["family", "flow_cytometry", "flow_cytometry"],
  ["subclass", "nonpermeabilized_IF", "immunofluorescence"],
  ["subclass", "permeabilized_IF", "immunofluorescence"],
  ["family", "immunofluorescence", "immunofluorescence"],
  ["subclass", "IHC", "immunohistochemistry"],
  ["subclass", "IHC_membranous", "immunohistochemistry"],
  ["family", "immunohistochemistry", "immunohistochemistry"],
  ["family", "functional_surface_assay", "functional_surface_assay"],
];

// Expression systems that keep the protein at its own expression level, so
// a direct readout there says the native protein is reachable. Overexpressed
// constructs can force surface localization the native protein never shows.
export const NATIVE_EXPRESSION_SYSTEMS = new Set(["endogenous", "mixed", "knock_in_tag"]);

// Surface labeling / capture chemistries only work on intact cells with
// membrane-impermeable reagents, so they count as live-cell unless a row is
// explicitly permeabilized (the methods builder often labels them
// "nonpermeabilized"). Flow and IF need an explicit live_cell label: their
// "nonpermeabilized" rows are usually fixed cells. Functional assays never
// count — find those under the method facet.
export const LIVE_BY_CHEMISTRY = new Set([
  "surface_biotin_pulldown",
  "cell_surface_capture_ms",
  "proximity_labeling",
]);

export function isLiveCellRow(method, permeabilization) {
  if (method === "functional_surface_assay") return false;
  if (permeabilization === "live_cell") return true;
  return LIVE_BY_CHEMISTRY.has(method) && permeabilization !== "permeabilized";
}

export function surfaceMethodCategory(family, subclass) {
  for (const [field, value, method] of SURFACE_METHOD_RULES) {
    if ((field === "family" ? family : subclass) === value) return method;
  }
  return "other";
}

// `packed` is the catalog query's `ddf_surface_methods` column: one
// "family|subclass|relevance|expression_system|permeabilization" token per
// distinct methods row, comma-joined (only direct + supporting rows are
// selected). Returns sorted, de-duplicated method lists (a method that has a
// direct row is never also listed as supporting) plus two flags:
//   * has_native_direct_surface_evidence — any direct row in a native
//     expression system.
//   * has_live_cell_surface_evidence — a direct row on live cells in a
//     native expression system, excluding functional assays (see
//     isLiveCellRow). Overrides the record's baked flag, which keyed on
//     method family and so missed capture MS and counted fixed-cell flow.
export function projectSurfaceMethods(packed) {
  const direct = new Set();
  const supporting = new Set();
  let native = false;
  let liveCell = false;
  for (const tok of (packed || "").split(",")) {
    if (!tok) continue;
    const [family, subclass, relevance, system, permeabilization] = tok.split("|");
    const method = surfaceMethodCategory(family, subclass);
    if (relevance === "direct_surface_accessibility") {
      direct.add(method);
      if (NATIVE_EXPRESSION_SYSTEMS.has(system)) {
        native = true;
        if (isLiveCellRow(method, permeabilization)) liveCell = true;
      }
    } else if (relevance === "supports_surface_localization") {
      supporting.add(method);
    }
  }
  for (const m of direct) supporting.delete(m);
  return {
    surface_method_direct: [...direct].sort(),
    surface_method_supporting: [...supporting].sort(),
    has_native_direct_surface_evidence: native,
    has_live_cell_surface_evidence: liveCell,
  };
}

// Correlated subquery packing a record's direct + supporting methods rows
// into one short string (median ~80 chars) — never the methods objects
// themselves, which carry antibody and expression-observation detail that
// would bloat the catalog query toward D1's isolate-memory cap. `alias` is
// the surface_annotation alias at the call site.
export const surfaceMethodsSql = (alias) => `(SELECT group_concat(DISTINCT
      COALESCE(json_extract(m.value, '$.method_family'), '') || '|' ||
      COALESCE(json_extract(m.value, '$.method_subclass'), '') || '|' ||
      COALESCE(json_extract(m.value, '$.accessibility_relevance'), '') || '|' ||
      COALESCE(json_extract(m.value, '$.expression_system'), '') || '|' ||
      COALESCE(json_extract(m.value, '$.permeabilization'), ''))
    FROM json_each(${alias}.annotation_json, '$.surface_evidence.methods') m
   WHERE json_extract(m.value, '$.accessibility_relevance')
         IN ('direct_surface_accessibility', 'supports_surface_localization'))`;

// Try JSON.parse and return the result, or null on failure / falsy input.
// Also passes through pre-parsed objects — SQLite `json_extract` on an
// object path returns a JSON string, but D1's client-side handling can
// vary, so accepting either shape keeps the caller compact.

export function projectDeepDiveFiltersFromParts(parts) {
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
  // Synthesizer's holistic grade (executive_summary.evidence_grade_summary),
  // sourced outside the top-level `filters` block. The catalog tiers gate on
  // this (viewer effectiveEvidenceGrade) so the deterministic A1-only
  // evidence_grade can't under-call genes with rich A2 context.
  if (typeof parts.evidence_grade_summary === "string") {
    out.evidence_grade_summary = parts.evidence_grade_summary;
    any = true;
  }
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
  // deterministic_features.canonical_topology (DeepTMHMM v1.0.24).
  // SCALAR fields only (json_extracted in handleCatalog); the full
  // per_residue_topology string is never pulled at catalog scale. Keep
  // in sync with the viewer's pickDeepDiveFilters. `has_tm` /
  // `tm_count_band` derive from the TM-helix count.
  const tmc = parts.topo_tm_helix_count;
  if (typeof tmc === "number") {
    out.has_tm = tmc > 0;
    out.tm_count_band = tmc === 0 ? "none" : tmc === 1 ? "single" : "multi";
    any = true;
  }
  // Surface-evidence method facets — sourced from surface_evidence.methods
  // (packed server-side; see projectSurfaceMethods). Emitted for every
  // deep-dive row, empty lists included, so "no direct method" is filterable
  // and distinguishable from a pre-v10 catalog that lacks the keys.
  Object.assign(out, projectSurfaceMethods(parts.surface_methods));
  return any ? out : null;
}

// Build a DDF-parts bag from the `sa_ddf_*` (or `ddf_*`) columns
// emitted by handleCatalog's json_extract queries. `filters` is the
// only value guaranteed to be present when the row has a deep dive;
// the others are null when the annotator didn't populate that block.
export function ddfPartsFromRow(row, prefix) {
  return {
    filters: safeJsonParse(row[`${prefix}filters`]),
    evidence_grade_summary:
      typeof row[`${prefix}evidence_grade_summary`] === "string"
        ? row[`${prefix}evidence_grade_summary`]
        : null,
    primary_compartment:
      typeof row[`${prefix}primary_compartment`] === "string"
        ? row[`${prefix}primary_compartment`]
        : null,
    restricted_subdomain: safeJsonParse(row[`${prefix}restricted_subdomain`]),
    secreted_form: safeJsonParse(row[`${prefix}secreted_form`]),
    surface_bind: safeJsonParse(row[`${prefix}surface_bind`]),
    homo_oligomerization: safeJsonParse(row[`${prefix}homo_oligomerization`]),
    // Canonical-topology scalars only. The catalog query json_extracts the
    // SCALAR paths — NEVER the whole canonical_topology object, which
    // carries per_residue_topology (a ~protein-length string) that would
    // blow D1's per-query isolate memory across ~1.2k catalog rows. See the
    // json_extract paths in handleCatalog.
    topo_tm_helix_count:
      typeof row[`${prefix}topo_tm_helix_count`] === "number"
        ? row[`${prefix}topo_tm_helix_count`]
        : null,
    topo_signal_peptide_length:
      typeof row[`${prefix}topo_signal_peptide_length`] === "number"
        ? row[`${prefix}topo_signal_peptide_length`]
        : null,
    surface_methods:
      typeof row[`${prefix}surface_methods`] === "string"
        ? row[`${prefix}surface_methods`]
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
// Majority verdict across a cell's replicates, then the most common reason
// within the winning verdict. Both tiebreak on the most recent `created_at`,
// so a single-replicate cell returns that replicate.
export function majorityVerdictAndReason(reps) {
  const pick = (rows, field) => {
    const tally = new Map();
    const latest = new Map();
    for (const r of rows) {
      tally.set(r[field], (tally.get(r[field]) || 0) + 1);
      const prev = latest.get(r[field]);
      if (prev == null || r.created_at > prev) latest.set(r[field], r.created_at);
    }
    return [...tally.entries()].sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      const ma = latest.get(a[0]) || "";
      const mb = latest.get(b[0]) || "";
      return mb < ma ? -1 : (mb > ma ? 1 : 0);
    })[0][0];
  };
  const verdict = pick(reps, "predicted_verdict");
  const reason = pick(reps.filter((r) => r.predicted_verdict === verdict), "predicted_reason");
  return { verdict, reason };
}
