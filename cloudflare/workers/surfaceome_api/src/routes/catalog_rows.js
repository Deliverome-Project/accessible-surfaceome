// Row assembly, orphan deep-dive rows, and paper-count band baking for /v1/catalog.
import { attachDeepDiveClassification, ddfPartsFromRow, projectDeepDiveFiltersFromParts, surfaceMethodsSql } from "../lib/catalog_projection.js";

export async function buildCatalogRows(env, { enrichedRows, covered, deepSet, packTriage, libTopoByGene }) {
  // Compact literature-track facet projection for /v1/catalog (row_schema v12).
  // Built from flat scalar columns on surface_internalization (never
  // record_json). Omits unknown/empty/false keys to keep the wire payload
  // slim (~50-90 bytes per graded gene).
  const packInternLitFacets = (u) => {
    if (!u.intern_has_lit) return null;
    const out = {};
    if (u.intern_lit_conf) out.conf = u.intern_lit_conf;
    if (u.intern_lit_basal && u.intern_lit_basal !== "unknown") out.basal = u.intern_lit_basal;
    if (u.intern_lit_native && u.intern_lit_native !== "unknown") out.native = u.intern_lit_native;
    if (u.intern_lit_therapeutic && u.intern_lit_therapeutic !== "unknown") out.therapeutic = u.intern_lit_therapeutic;
    if (u.intern_lit_pathogen && u.intern_lit_pathogen !== "unknown") out.pathogen = u.intern_lit_pathogen;
    if (u.intern_lit_fate && u.intern_lit_fate !== "unknown") out.fate = u.intern_lit_fate;
    if (u.intern_lit_primary) out.primary = true;
    if (u.intern_lit_quant) out.quant = true;
    if (u.intern_lit_fitted) out.fitted = true;
    if (u.intern_lit_binders) {
      try {
        const parsed = JSON.parse(u.intern_lit_binders);
        if (Array.isArray(parsed) && parsed.length) out.binders = parsed;
      } catch { /* ignore malformed */ }
    }
    if (u.intern_lit_mechs) {
      try {
        const parsed = JSON.parse(u.intern_lit_mechs);
        if (Array.isArray(parsed) && parsed.length) out.mechs = parsed;
      } catch { /* ignore malformed */ }
    }
    return Object.keys(out).length ? out : null;
  };

  const rows = enrichedRows.results.map((u) => {
    covered.add(u.gene_symbol);
    if (u.has_deep_dive) deepSet.add(u.gene_symbol);
      // UniProt and CSPA are scored on the SurfaceBench-recalibrated cutoffs,
      // the same rule the paper and every figure use: UniProt expanded to
      // TM>0 / signal-peptide>0 / strict subcellular term, CSPA tightened to
      // high-confidence only. GO, SURFY and HPA are not recalibrated and
      // keep their native flag. db_optimized_cutoff_public is a POSITIVE
      // LIST — absent means 0, never "fall back to native", or the tightened
      // CSPA members it exists to drop come straight back.
    const upOpt = u.uniprot_optimized ? 1 : 0;
    const cspaOpt = u.cspa_optimized ? 1 : 0;
    const goFlag = u.go_surface_flag ? 1 : 0;
    const surfyFlag = u.surfy_surface_flag ? 1 : 0;
    const hpaFlag = u.hpa_surface_flag ? 1 : 0;
    const db =
      (upOpt ? 1 : 0) |
      (goFlag ? 2 : 0) |
      (surfyFlag ? 4 : 0) |
      (cspaOpt ? 8 : 0) |
      (hpaFlag ? 16 : 0);
    const row = {
      symbol: u.gene_symbol,
      // Recomputed, not u.n_sources_surface: that column is the native
      // 5-vote and would contradict the flags beside it.
      n_sources: upOpt + goFlag + surfyFlag + cspaOpt + hpaFlag,
      db,
    };
    if (u.uniprot_acc) row.uniprot = u.uniprot_acc;
    const t = packTriage(u.gene_symbol);
    if (t) row.tr = t;
    if (u.has_deep_dive) row.deep_dive = true;
    if (u.sb_n_sites != null) row.sb = u.sb_n_sites;
    // Internalization sequence-prior grade (SeqGrade: very_high|high|moderate|
    // low|very_low|unknown). Separate standalone pass — a top-level field, NOT
    // inside `ddf`, because it exists for the full internalization cohort
    // independent of deep-dive coverage (viewer filters it as its own category).
    if (u.intern_grade) row.intern = u.intern_grade;
    if (u.intern_has_lit) row.intern_lit = 1;
    // Library members whose exact ordered sequence has a v1 topology (row_schema
    // v11). Independent of `ddf` and of the canonical-topology facets, which
    // describe a different protein for a substantial minority of members.
    const nLibTopo = libTopoByGene.get(u.gene_symbol);
    if (nLibTopo) row.libtopo = nLibTopo;
    // Literature-track overall grade (Grade: high|moderate|low|no|unknown) —
    // distinct from the seq prior above, so the catalog can render a SEPARATE
    // "Internalization (literature)" column + filter. Only present once a gene
    // has had a literature run; older viewers ignore this unknown field.
    if (u.intern_lit_grade) row.intern_lit_grade = u.intern_lit_grade;
    const intl = packInternLitFacets(u);
    if (intl) row.intl = intl;
    // Slim deep-dive filter projection — only the 21 fields the catalog
    // UI actually filters on. Skips continuous fields (max_paralog_ecd_
    // pct_identity, ortholog identities) and `has_restricted_subdomain`
    // (moved to the Biology card). Parsing failures fall through silently
    // — a malformed record still gets the deep_dive=true marker, just
    // without the filterable rollups.
    if (u.has_deep_dive) {
      const ddf = projectDeepDiveFiltersFromParts(ddfPartsFromRow(u, "sa_ddf_"));
      if (ddf) {
        row.ddf = ddf;
        // Low-literature badge gates on the OPTIMIZED UniProt call, not the
        // native flag. The badge's own rationale is that UniProt outperformed
        // the other sources on our positive controls -- and that result is
        // measured under the recalibrated cutoff, which is what every figure
        // and the paper score membership on. Gating on the native flag made
        // the live badge disagree with the published numbers.
        attachDeepDiveClassification(row, ddf, !!u.uniprot_optimized);
      }
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
            json_extract(sa1.annotation_json, '$.executive_summary.evidence_grade_summary') AS ddf_evidence_grade_summary,
            json_extract(sa1.annotation_json, '$.biological_context.subcellular_localization.primary_compartment') AS ddf_primary_compartment,
            json_extract(sa1.annotation_json, '$.accessibility_risks.restricted_subdomain') AS ddf_restricted_subdomain,
            json_extract(sa1.annotation_json, '$.accessibility_risks.secreted_form') AS ddf_secreted_form,
            json_extract(sa1.annotation_json, '$.deterministic_features.surface_bind') AS ddf_surface_bind,
            json_extract(sa1.annotation_json, '$.deterministic_features.homo_oligomerization') AS ddf_homo_oligomerization,
            -- Canonical-topology SCALARS only (see main catalog query).
            json_extract(sa1.annotation_json, '$.deterministic_features.canonical_topology.tm_helix_count') AS ddf_topo_tm_helix_count,
            json_extract(sa1.annotation_json, '$.deterministic_features.canonical_topology.signal_peptide_length') AS ddf_topo_signal_peptide_length,
            ${surfaceMethodsSql("sa1")} AS ddf_surface_methods,
            gi.uniprot_acc AS uniprot_acc,
            si.seq_canonical_grade AS intern_grade,
            si.has_literature AS intern_has_lit,
            si.lit_overall_grade AS intern_lit_grade,
            si.lit_overall_confidence AS intern_lit_conf,
            si.lit_basal_grade AS intern_lit_basal,
            si.lit_native_ligand_grade AS intern_lit_native,
            si.lit_therapeutic_grade AS intern_lit_therapeutic,
            si.lit_pathogen_entry_grade AS intern_lit_pathogen,
            si.lit_predominant_fate AS intern_lit_fate,
            si.lit_has_primary_or_invivo AS intern_lit_primary,
            si.lit_has_quant AS intern_lit_quant,
            si.lit_has_fitted_kinetics AS intern_lit_fitted,
            si.lit_binder_types AS intern_lit_binders,
            si.lit_mechanisms AS intern_lit_mechs
       FROM surface_annotation sa1
       LEFT JOIN gene_identifier_public gi ON gi.hgnc_symbol = sa1.gene_symbol
       LEFT JOIN surface_internalization si ON si.gene_symbol = sa1.gene_symbol
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
    if (r.intern_grade) row.intern = r.intern_grade;
    if (r.intern_has_lit) row.intern_lit = 1;
    if (r.intern_lit_grade) row.intern_lit_grade = r.intern_lit_grade;
    const orphanIntl = packInternLitFacets(r);
    if (orphanIntl) row.intl = orphanIntl;
    // Same v11 field as the main catalog rows; an orphan deep-dive gene can still
    // be a library member, and omitting it here would make `libtopo` depend on
    // which of the two row builders a gene happened to come through.
    const nOrphanLibTopo = libTopoByGene.get(sym);
    if (nOrphanLibTopo) row.libtopo = nOrphanLibTopo;
    const t = packTriage(sym);
    if (t) row.tr = t;
    const dd = projectDeepDiveFiltersFromParts(ddfPartsFromRow(r, "ddf_"));
    if (dd) {
      row.ddf = dd;
      // Orphan deep-dive genes aren't in the candidate universe → no UniProt
      // surface vote, so the low-lit badge is false by construction.
      attachDeepDiveClassification(row, dd, false);
    }
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
  return { rows, psCutoffs };
}
