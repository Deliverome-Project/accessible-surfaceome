// Per-gene record, evidence ledger, Markdown export, orthologs, and tag-sites routes.
import { CACHE_TTL_LONG, CACHE_TTL_SHORT, CORS_HEADERS, SYMBOL_OK, badRequest, cacheControl, checkSymbol, isMissingTable, json, notFound } from "../lib/http.js";
import { attachDeepDiveClassification } from "../lib/catalog_projection.js";
import { collectSourceIds, fetchPaperMetadata } from "../lib/papers.js";
import { TRIAGE_VERDICT_TO_SIGNAL, fetchTriagePrior } from "./triage.js";
import { enrichGeneTopology } from "./gene_topology.js";
import { enrichParalogsAndOrthologs, enrichSchwekeHomomer, enrichSurfaceBindAndBindome } from "./gene_enrichment.js";

export async function handleGene(env, symbol) {
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
  // Every enrichment query below used to swallow its own errors with a bare
  // `.catch(() => null)` — including a genuine D1 hiccup, not just "this
  // gene has no row here". That meant a transient failure silently served
  // (and, via withEdgeCache, PERMANENTLY cached for up to a day) a record
  // with those fields null even though D1 actually had the data — exactly
  // what happened to S100A7A's revision 3 (canonical_topology.protein_length
  // etc. archived null despite the topology_public row existing). `soft()`
  // still degrades a failed query to null (never breaks the endpoint), but
  // now records WHICH query failed in `degraded`, unless the failure is a
  // "no such table" error — that's a persistent, intentional condition (see
  // `isMissingTable`), not a transient one, and stays silent. `degraded` is
  // read at the end of this handler to set DEGRADED_HEADER + force
  // Cache-Control: no-store, so withEdgeCache never caches the response.
  const degraded = [];
  const soft = (p, label) =>
    p.catch((e) => {
      if (isMissingTable(e)) return null;
      degraded.push(label);
      console.warn("enrichment_failed", label, e?.message);
      return null;
    });
  await enrichSchwekeHomomer(env, record, soft);
  const uniprot = record?.gene?.uniprot_acc;
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
      soft(
        env.DB.prepare(
          `SELECT r.topology_version FROM topology_release r
              WHERE EXISTS (
                SELECT 1 FROM topology_public p
                 WHERE p.cohort = 'human_canonical' AND p.topology_version = r.topology_version
              )
              ORDER BY r.loaded_at DESC LIMIT 1`
        ).first(),
        "topology_release_canonical",
      ),
      soft(
        env.DB.prepare(
          `SELECT r.topology_version FROM topology_release r
              WHERE EXISTS (
                SELECT 1 FROM topology_public p
                 WHERE p.cohort = 'human_isoforms' AND p.topology_version = r.topology_version
              )
              ORDER BY r.loaded_at DESC LIMIT 1`
        ).first(),
        "topology_release_isoform",
      ),
      soft(
        env.DB.prepare(
          `SELECT paralog_version FROM compara_paralog_release
              ORDER BY fetched_at DESC LIMIT 1`
        ).first(),
        "compara_paralog_release",
      ),
      soft(
        env.DB.prepare(
          `SELECT ortholog_ecd_version FROM compara_ortholog_ecd_release
              ORDER BY computed_at DESC LIMIT 1`
        ).first(),
        "compara_ortholog_ecd_release",
      ),
    ]);
    const canonicalTopoVersion = topoCanonRow?.topology_version ?? null;
    const isoformTopoVersion = topoIsoRow?.topology_version ?? null;
    const paralogVersion = paralogRelRow?.paralog_version ?? null;
    const orthologEcdVersion = orthoEcdRelRow?.ortholog_ecd_version ?? null;
    await enrichGeneTopology(env, record, sym, uniprot, { canonicalTopoVersion, isoformTopoVersion }, soft, dedupeByKey);
    await enrichParalogsAndOrthologs(env, record, uniprot, { canonicalTopoVersion, paralogVersion, orthologEcdVersion }, soft, dedupeByKey);
    await enrichSurfaceBindAndBindome(env, record, uniprot, soft);
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
  // hasn't covered yet leaves the annotator's call intact). A real
  // (non-missing-table) failure here now also marks the response
  // degraded, same as the `soft()`-wrapped queries above — this is a
  // plain try/catch rather than a promise chain because
  // `fetchTriagePrior` walks a priority list of queries internally,
  // not a single one `soft()` could wrap directly.
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
    if (!isMissingTable(e)) {
      degraded.push("triage_run_public");
      console.warn("enrichment_failed", "triage_run_public", e?.message);
    }
  }
  // Store the shared deep-dive classification on the record so the gene page
  // AND the Zenodo deposit tarball (raw /v1/genes responses) carry the same
  // tier the catalog computes — one authoritative label, no client re-derive.
  // evidence_grade_summary lives in executive_summary, not filters; merge it
  // in so the shared effectiveEvidenceGrade sees the holistic grade.
  if (record?.filters) {
    attachDeepDiveClassification(record, {
      ...record.filters,
      evidence_grade_summary:
        record?.executive_summary?.evidence_grade_summary ?? null,
    });
  }
  // Evidence-ledger split (serve-layer only — the D1 record_json is
  // unchanged): the per-gene record OMITS `evidence` (42–47% of the
  // payload). The quote ledger is served separately at
  // GET /v1/genes/{SYMBOL}/evidence (handleGeneEvidence) so the gene
  // page's initial record load isn't dominated by the evidence array.
  if (record && "evidence" in record) delete record.evidence;
  return json(record, { ttl: CACHE_TTL_LONG, degraded });
}

export async function handleGeneEvidence(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  const row = await env.DB.prepare(
    `SELECT annotation_json
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
  const evidence = Array.isArray(record?.evidence) ? record.evidence : [];
  const degraded = [];
  const papers = await fetchPaperMetadata(env, collectSourceIds(evidence), {
    onError: (e) => {
      degraded.push("paper_metadata");
      console.warn("enrichment_failed", "paper_metadata", e?.message);
    },
  });
  return json({ gene: sym, evidence, papers }, { ttl: CACHE_TTL_LONG, degraded });
}

export async function handleOrthologs(env, symbol) {
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


export async function handleTagSites(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return notFound("gene_not_found");
  // Resilient to deploy order: if tag_site_public isn't provisioned yet (Worker
  // shipped before the sync), return an empty TaggedSitesFile silently. Any
  // OTHER D1 failure (transient timeout / export lock) marks `degraded` so
  // `json()` sets `X-Surfaceome-Degraded` + `Cache-Control: no-store` and
  // `withEdgeCache` never caches a bogus empty `has_data: false` response.
  const degraded = [];
  let rows = [];
  try {
    const res = await env.DB.prepare(
      `SELECT * FROM tag_site_public WHERE gene_symbol = ? COLLATE NOCASE
        ORDER BY provenance, insert_after_residue`
    )
      .bind(sym)
      .all();
    rows = res?.results ?? [];
  } catch (e) {
    if (!isMissingTable(e)) {
      degraded.push("tag_site_public");
      console.warn("enrichment_failed", "tag_site_public", e?.message);
    }
    rows = [];
  }
  const sites = rows.map((r) => ({
    site_id: r.site_id,
    gene_symbol: r.gene_symbol,
    uniprot_acc: r.uniprot_acc,
    provenance: r.provenance,
    det_path: r.det_path ?? null,
    site_kind: r.site_kind,
    insert_after_residue: r.insert_after_residue ?? null,
    residue_before: r.residue_before ?? null,
    residue_after: r.residue_after ?? null,
    residue_label: r.residue_label ?? null,
    residue_range: r.residue_range ?? null,
    topology_state: r.topology_state ?? null,
    extracellular: r.extracellular === 1,
    compartment: r.compartment ?? null,
    tag_type: r.tag_type ?? null,
    tag_length_aa: r.tag_length_aa ?? null,
    linker: r.linker ?? null,
    evidence_type: r.evidence_type ?? null,
    functional_impact_measured: r.functional_impact_measured ?? null,
    confidence: r.confidence ?? null,
    rationale: r.rationale ?? null,
    sources: JSON.parse(r.sources_json || "[]"),
    plddt: r.plddt ?? null,
    conservation_rank: r.conservation_rank ?? null,
    median_conservation: r.median_conservation ?? null,
    // Additive: the agent metadata that used to be concatenated into
    // `rationale` as "[validation: ...; position: ...]". An older viewer
    // ignores unknown fields; a newer one renders them as badges.
    validation_level: r.validation_level ?? null,
    position_evidence: r.position_evidence ?? null,
    source_tier: r.source_tier ?? null,
    cited_tag_residue: r.cited_tag_residue ?? null,
    entailment_verified:
      r.entailment_verified == null ? null : r.entailment_verified === 1,
    // Which proteoform frame the citation numbered in, when it was not the
    // protein's own ("mature", "isoform:P54289-2"). Null is the ordinary case.
    // Additive: an older viewer ignores it, a newer one renders it as a badge —
    // and without it a position recovered from a foreign frame looks identical
    // to one the paper stated directly.
    position_frame: r.position_frame ?? null,
  }));

  // Per-GENE facts, which the per-SITE table cannot carry. Without these a gene
  // the agent searched and found nothing in is indistinguishable from one
  // nobody looked at — it has no site rows either way — and the published
  // intracellular / function-abrogating positions have nowhere to live.
  // LEFT JOIN semantics: absent row => never searched, which is the claim.
  let gene = null;
  try {
    gene = await env.DB.prepare(
      `SELECT prompt_sha, prompt_version, searched_at, n_papers,
              other_positions_json, notes
         FROM tag_site_gene_public WHERE gene_symbol = ? COLLATE NOCASE`
    )
      .bind(sym)
      .first();
  } catch (e) {
    if (!isMissingTable(e)) {
      degraded.push("tag_site_gene_public");
      console.warn("enrichment_failed", "tag_site_gene_public", e?.message);
    }
    gene = null;
  }

  let otherPositions = [];
  if (gene?.other_positions_json) {
    try {
      otherPositions = JSON.parse(gene.other_positions_json) || [];
    } catch {
      otherPositions = [];
    }
  }

  return json(
    {
      // Unchanged meaning for existing consumers: "are there sites to draw".
      has_data: sites.length > 0,
      gene_symbol: rows[0]?.gene_symbol ?? sym,
      uniprot_acc: rows[0]?.uniprot_acc ?? "",
      sites,
      // Presence of prompt_sha is the claim "this gene was searched", which is
      // what lets the viewer say "Literature-validated (0)" instead of nothing.
      prompt_sha: gene?.prompt_sha ?? null,
      prompt_version: gene?.prompt_version ?? null,
      generated_at: gene?.searched_at ?? null,
      n_papers_searched: gene?.n_papers ?? null,
      literature_other_positions: otherPositions,
      literature_notes: gene?.notes ?? null,
    },
    { degraded },
  );
}

// Serve the pre-generated rich Markdown export for a gene from R2.
// Unlike the JSON record (assembled live from D1), the .md bundles
// reanalysis extras NOT in D1 — canonical/isoform/ortholog sequences,
// per-residue DeepTMHMM topology, AlphaFold links — so it's generated
// offline by viewer/scripts/build-markdown-exports.mjs and uploaded to the
// R2 bucket bound as `GENE_MD` (key: `{HGNC_SYMBOL}.md`).
export async function handleGeneMarkdown(env, symbol) {
  if (!SYMBOL_OK.test(symbol)) return notFound("gene_not_found");
  // The binding is optional (absent in a local `wrangler dev` without R2 or
  // an older config) — degrade to 404 rather than throwing on `.get`.
  if (!env.GENE_MD) return notFound("markdown_unavailable");
  // R2 keys are case-sensitive and the generator writes the exact stored
  // HGNC symbol (a minority are mixed-case, e.g. C11orf24). The viewer links
  // with the canonical `hgnc_symbol`, so an exact-case key is correct for the
  // real caller; a hand-typed wrong-case URL 404s (acceptable for a download).
  const obj = await env.GENE_MD.get(`${symbol}.md`);
  if (!obj) return notFound("markdown_not_found");
  return new Response(obj.body, {
    status: 200,
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      "Content-Disposition": `inline; filename="${symbol}.md"`,
      "Cache-Control": cacheControl(CACHE_TTL_SHORT),
      ...CORS_HEADERS,
    },
  });
}

// D1 refuses queries while a database export runs ("Currently processing a
// long-running export"), and transiently when overloaded. Those used to escape
// as uncaught exceptions, so every uncached request failed with a 500 for the
// length of the export (345 such errors across two backups on 2026-10-17/18).
// Answer 503 + Retry-After instead, never cached, so clients and the viewer
// can retry and no error page is stored at the edge.
