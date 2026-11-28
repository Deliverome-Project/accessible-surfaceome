// Record history revisions, pinned data releases, and reproducibility replicates.

import { CACHE_TTL_IMMUTABLE, CACHE_TTL_LONG, CACHE_TTL_SHORT, CORS_HEADERS, badRequest, checkSymbol, isMissingTable, json, notFound } from "../lib/http.js";
import { attachDeepDiveClassification } from "../lib/catalog_projection.js";

// --- Record history (spec docs/superpowers/specs/2026-09-27-record-history-design.md) ---
// Archived bodies live write-once in the RECORD_HISTORY R2 bucket, named by
// content hash, so they are cacheable forever. They are read straight from
// R2 rather than through withEdgeCache, which would rebuild the response
// with only Content-Type + Cache-Control and drop ETag / X-Surfaceome-*.

export const RELEASE_VERSION_OK = /^v?(\d+\.\d+\.\d+)$/;
export const REVISION_OK = /^[1-9]\d{0,5}$/;
export const HISTORY_BASE = "https://api.deliverome.org/surfaceome/v1";
export const REVISION_PARTS = {
  record:   { col: "json_hash",     ext: "json", ct: "application/json; charset=utf-8" },
  evidence: { col: "evidence_hash", ext: "json", ct: "application/json; charset=utf-8", missing: "evidence_not_archived" },
  md:       { col: "md_hash",       ext: "md",   ct: "text/markdown; charset=utf-8",   missing: "markdown_not_archived" },
};

// Constant-time byte comparison for the fallback path below (equal-length
// arrays only — callers check .length first).

export function normalizeVersion(v) {
  const m = RELEASE_VERSION_OK.exec(v || "");
  return m ? m[1] : null;
}

// `/v1/releases/v1.0.0...` and `/v1/releases/1.0.0...` must resolve to ONE
// cache key (the bare form) so cut_data_release's purge — which only ever
// targets the bare path — always invalidates the live entry. A v-prefixed
// request redirects (301, no-store) to the canonical bare path rather than
// ever being handled or cached under its own key. Returns null (no
// redirect needed) for an already-bare version or a not-quite-version
// string (the handler's own badRequest("invalid_version") covers that).
export function bareVersionRedirect(rawVer, suffix = "") {
  if (!/^v/i.test(rawVer || "")) return null;
  const bare = rawVer.slice(1);
  if (!RELEASE_VERSION_OK.test(bare)) return null;
  return new Response(null, {
    status: 301,
    headers: {
      Location: `${HISTORY_BASE}/releases/${bare}${suffix}`,
      "Cache-Control": "no-store",
      ...CORS_HEADERS,
    },
  });
}

export async function archivedPart(env, row, part) {
  const p = REVISION_PARTS[part];
  const hash = row[p.col];
  if (!hash) return notFound(p.missing);
  if (!env.RECORD_HISTORY) return json({ error: "history_unavailable" }, { status: 503, ttl: 0 });
  const obj = await env.RECORD_HISTORY.get(`records/sha256/${hash}.${p.ext}`);
  if (!obj) return json({ error: "archive_body_missing" }, { status: 500, ttl: 0 });
  return new Response(obj.body, {
    status: 200,
    headers: {
      "Content-Type": p.ct,
      "Cache-Control": `public, max-age=${CACHE_TTL_IMMUTABLE}, s-maxage=${CACHE_TTL_IMMUTABLE}, immutable`,
      "ETag": `"${hash}"`,
      "X-Surfaceome-Revision": String(row.revision),
      "X-Surfaceome-Content-Hash": hash,
      ...CORS_HEADERS,
    },
  });
}

export async function handleRevisionList(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  const { results } = await env.DB.prepare(
    `SELECT r.gene_symbol, r.hgnc_id, r.revision, r.published_at, r.source,
            r.json_hash, r.evidence_hash, r.md_hash, r.schema_version, r.prompt_corpus_version,
            (SELECT json_group_array(json_object('version', v, 'zenodo_version_doi', doi))
               FROM (
                 SELECT m.version AS v, d.zenodo_version_doi AS doi
                   FROM data_release_member m JOIN data_release d ON d.version = m.version
                  WHERE m.gene_symbol = r.gene_symbol COLLATE NOCASE AND m.revision = r.revision
                  ORDER BY d.cut_at
               )) AS releases
       FROM record_revision r
      WHERE r.gene_symbol = ? COLLATE NOCASE
      ORDER BY r.revision DESC`
  ).bind(sym).all();
  if (!results.length) return notFound("gene_not_annotated");
  const g = results[0];
  const base = `${HISTORY_BASE}/genes/${g.gene_symbol}/revisions`;
  // `results` is ordered newest-first (revision DESC); `changed` is computed
  // by walking oldest-first and diffing each row against the previous
  // (numerically lower) revision of the SAME gene — no extra query, since
  // every row for this gene is already in hand. Revision 1 (a gene's first
  // ARCHIVED version — history no longer contains a seeded/deposited
  // revision 0) is always `["first_archived"]`, since there is no prior
  // revision to diff against and a part-by-part comparison against nothing
  // would be meaningless. It's "first_archived" and not "first_served"
  // deliberately: for a gene that was seeded and then had that seed row
  // renumbered away (drop_seed_revisions.py), its new revision 1 is
  // whatever was first captured into record_revision AFTER that migration
  // — the API had already been serving that gene's record for a while
  // before history (or this migration) existed. Every later revision
  // lists whichever of record/evidence/markdown differ from the previous
  // revision — a NULL-to-value or value-to-NULL transition counts as a
  // change via plain `!==` (NULL !== "somehash").
  const ascending = [...results].sort((a, b) => a.revision - b.revision);
  const changedByRevision = new Map();
  let prev = null;
  for (const r of ascending) {
    let changed;
    if (prev === null) {
      changed = ["first_archived"];
    } else {
      changed = [];
      if (r.json_hash !== prev.json_hash) changed.push("record");
      if (r.evidence_hash !== prev.evidence_hash) changed.push("evidence");
      if (r.md_hash !== prev.md_hash) changed.push("markdown");
    }
    changedByRevision.set(r.revision, changed);
    prev = r;
  }
  return json({
    gene_symbol: g.gene_symbol,
    hgnc_id: g.hgnc_id,
    current_revision: g.revision,
    revisions: results.map((r) => ({
      revision: r.revision,
      published_at: r.published_at,
      source: r.source,
      json_hash: r.json_hash,
      evidence_hash: r.evidence_hash,
      md_hash: r.md_hash,
      schema_version: r.schema_version,
      prompt_corpus_version: r.prompt_corpus_version,
      changed: changedByRevision.get(r.revision),
      releases: r.releases ? JSON.parse(r.releases) : [],
      url: `${base}/${r.revision}`,
      evidence_url: r.evidence_hash ? `${base}/${r.revision}/evidence` : null,
      md_url: r.md_hash ? `${base}/${r.revision}.md` : null,
    })),
  });
}

export async function handleRevisionBody(env, symbol, n, part) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  if (!REVISION_OK.test(n)) return badRequest("invalid_revision");
  const row = await env.DB.prepare(
    `SELECT revision, json_hash, evidence_hash, md_hash FROM record_revision
      WHERE gene_symbol = ? COLLATE NOCASE AND revision = ?`
  ).bind(sym, Number(n)).first();
  if (!row) return notFound("revision_not_found");
  return archivedPart(env, row, part);
}

// A release whose `archive_scope` is 'zenodo_only' predates this system
// (only release 1.0.0, the 2026-08-15 Zenodo deposit, today) — its records
// were never individually archived into `record_revision`/R2, only bundled
// into the Zenodo deposit tarball. NULL/'api' (every release cut under this
// system) has real `data_release_member` rows behind it. See
// docs/superpowers/specs/2026-09-27-record-history-design.md.
export function isZenodoOnly(rel) {
  return rel.archive_scope === "zenodo_only";
}

export const DATA_RELEASE_COLS =
  "version, cut_at, github_tag, zenodo_version_doi, n_genes, notes";

// `data_release.archive_scope` is added by `drop_seed_revisions.py`'s
// idempotent `ALTER TABLE` (or a fresh `apply_record_history_ddl.py`
// apply) — a Worker deploy that reads it can land BEFORE that migration
// has run against public D1, in which case the column doesn't exist yet
// and every `SELECT ... archive_scope ...` below would otherwise 500 on
// every /v1/releases* route. `isMissingTable` already recognizes "no such
// column" as the persistent, deploy-order-dependent case (not a flaky
// one), so on that specific failure this re-queries WITHOUT the column
// and reports every release as `archive_scope: null` (never zenodo-only)
// until the column exists — the same "degrade to absent" posture used
// everywhere else in this file for a not-yet-provisioned table/column.
export async function dataReleaseRows(env, whereSql, params) {
  try {
    const { results } = await env.DB.prepare(
      `SELECT ${DATA_RELEASE_COLS}, archive_scope FROM data_release ${whereSql}`
    ).bind(...params).all();
    return results;
  } catch (e) {
    if (!isMissingTable(e)) throw e;
    const { results } = await env.DB.prepare(
      `SELECT ${DATA_RELEASE_COLS} FROM data_release ${whereSql}`
    ).bind(...params).all();
    return results.map((r) => ({ ...r, archive_scope: null }));
  }
}

export async function dataReleaseRow(env, whereSql, params) {
  const rows = await dataReleaseRows(env, whereSql, params);
  return rows[0] ?? null;
}

// --- Reproducibility replicates (API-only) ---
// Genes re-annotated for the run-to-run reproducibility analysis
// (Supplementary Figure 16), served from public D1 `deep_dive_replicate`.
// These are NOT the published records: surface_annotation stays the only
// source of /v1/genes/{SYMBOL}, nothing in the catalog or viewer reads this
// table, and every response is labelled `reproducibility_replicate: true`
// with a pointer back to the published record. Rows are loaded once from a
// frozen bundle and never rewritten, so the per-gene routes' 1-day TTL needs
// no purge path; the cohort-level index stays on the 1-minute TTL (tiny
// metadata query) so it never needs a purge-map entry.
export const REPLICATE_KINDS = ["published_snapshot", "full_rerun", "fixed_evidence_replay"];
export const REPLICATE_STUDY_OK = /^[a-z0-9_]{1,64}$/;
export const REPLICATE_NOTICE =
  "Reproducibility replicate, not the published record. Kept for the run-to-run " +
  "reproducibility analysis (Supplementary Figure 16); the published record is " +
  "/v1/genes/{symbol}.";
export const REPLICATE_KIND_NOTES = {
  published_snapshot: "The published record exactly as served when the study ran (the comparator); the live record may since have been republished.",
  full_rerun: "The whole pipeline re-run from scratch with the same prompts: literature discovery, abstract triage, paper selection, section builders and synthesizer.",
  fixed_evidence_replay: "Section builders and synthesizer re-run on the published record's own evidence ledger; discovery and selection held fixed.",
};

export function replicateUrl(sym, study, kind) {
  return `${HISTORY_BASE}/genes/${sym}/replicates/${study}/${kind}`;
}

// GET /v1/replicates — every study, its kinds and genes (metadata only; never
// reads annotation_json).
export async function handleReplicateIndex(env) {
  let results;
  try {
    ({ results } = await env.DB.prepare(
      `SELECT study_id, replicate_kind, gene_symbol, hgnc_id, sample_batch,
              run_id, compared_against_run_id
         FROM deep_dive_replicate
        ORDER BY study_id, gene_symbol, replicate_kind`
    ).all());
  } catch (e) {
    if (isMissingTable(e)) return json({ notice: REPLICATE_NOTICE, studies: [] });
    throw e;
  }
  const studies = new Map();
  for (const r of results) {
    let st = studies.get(r.study_id);
    if (!st) {
      st = { study_id: r.study_id, compared_against_run_id: r.compared_against_run_id,
             kinds: {}, genes: new Map() };
      studies.set(r.study_id, st);
    }
    st.kinds[r.replicate_kind] ??= { n: 0, run_id: r.run_id, description: REPLICATE_KIND_NOTES[r.replicate_kind] ?? null };
    st.kinds[r.replicate_kind].n++;
    if (!st.genes.has(r.gene_symbol)) {
      st.genes.set(r.gene_symbol, { gene_symbol: r.gene_symbol, hgnc_id: r.hgnc_id,
        sample_batch: r.sample_batch, url: `${HISTORY_BASE}/genes/${r.gene_symbol}/replicates` });
    }
  }
  return json({
    notice: REPLICATE_NOTICE,
    studies: [...studies.values()].map((st) => ({
      study_id: st.study_id,
      compared_against_run_id: st.compared_against_run_id,
      n_genes: st.genes.size,
      kinds: st.kinds,
      genes: [...st.genes.values()],
    })),
  }, { ttl: CACHE_TTL_SHORT });
}

// GET /v1/genes/{SYMBOL}/replicates — the replicates held for one gene.
export async function handleGeneReplicates(env, symbol) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  let results = [];
  try {
    ({ results } = await env.DB.prepare(
      `SELECT study_id, replicate_kind, gene_symbol, hgnc_id, uniprot_acc, sample_batch,
              run_id, compared_against_run_id, schema_version, prompt_corpus_version,
              record_generated_at
         FROM deep_dive_replicate
        WHERE gene_symbol = ? COLLATE NOCASE
        ORDER BY study_id, replicate_kind`
    ).bind(sym).all());
  } catch (e) {
    if (!isMissingTable(e)) throw e;
  }
  if (!results.length) return notFound("no_replicates");
  const g = results[0];
  return json({
    reproducibility_replicate: true,
    notice: REPLICATE_NOTICE,
    gene_symbol: g.gene_symbol,
    hgnc_id: g.hgnc_id,
    uniprot_acc: g.uniprot_acc,
    published_record_url: `${HISTORY_BASE}/genes/${g.gene_symbol}`,
    replicates: results.map((r) => ({
      study_id: r.study_id,
      replicate_kind: r.replicate_kind,
      description: REPLICATE_KIND_NOTES[r.replicate_kind] ?? null,
      sample_batch: r.sample_batch,
      run_id: r.run_id,
      compared_against_run_id: r.compared_against_run_id,
      schema_version: r.schema_version,
      prompt_corpus_version: r.prompt_corpus_version,
      record_generated_at: r.record_generated_at,
      url: replicateUrl(r.gene_symbol, r.study_id, r.replicate_kind),
    })),
  }, { ttl: CACHE_TTL_LONG });
}

// GET /v1/genes/{SYMBOL}/replicates/{study}/{kind} — one replicate record, in
// full (evidence included), wrapped so it cannot be mistaken for the published
// record. The deep-dive tier is attached with the same shared predicate
// handleGene uses, so a replicate's tier is directly comparable.
export async function handleGeneReplicate(env, symbol, study, kind) {
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  if (!REPLICATE_STUDY_OK.test(study)) return badRequest("invalid_study");
  if (!REPLICATE_KINDS.includes(kind)) return badRequest("invalid_replicate_kind");
  let row = null;
  try {
    row = await env.DB.prepare(
      `SELECT study_id, replicate_kind, gene_symbol, hgnc_id, uniprot_acc, sample_batch,
              run_id, compared_against_run_id, schema_version, prompt_corpus_version,
              record_generated_at, annotation_json
         FROM deep_dive_replicate
        WHERE gene_symbol = ? COLLATE NOCASE AND study_id = ? AND replicate_kind = ?`
    ).bind(sym, study, kind).first();
  } catch (e) {
    if (!isMissingTable(e)) throw e;
  }
  if (!row) return notFound("replicate_not_found");
  let record;
  try {
    record = JSON.parse(row.annotation_json);
  } catch (e) {
    return json({ error: "bad_record_json" }, { status: 500, ttl: 0 });
  }
  const out = {
    reproducibility_replicate: true,
    notice: REPLICATE_NOTICE,
    study_id: row.study_id,
    replicate_kind: row.replicate_kind,
    description: REPLICATE_KIND_NOTES[row.replicate_kind] ?? null,
    gene_symbol: row.gene_symbol,
    hgnc_id: row.hgnc_id,
    uniprot_acc: row.uniprot_acc,
    sample_batch: row.sample_batch,
    run_id: row.run_id,
    compared_against_run_id: row.compared_against_run_id,
    published_record_url: `${HISTORY_BASE}/genes/${row.gene_symbol}`,
  };
  if (record?.filters) {
    attachDeepDiveClassification(out, {
      ...record.filters,
      evidence_grade_summary: record?.executive_summary?.evidence_grade_summary ?? null,
    });
  }
  out.record = record;
  return json(out, { ttl: CACHE_TTL_LONG });
}

export async function handleReleaseList(env) {
  const results = await dataReleaseRows(env, "ORDER BY cut_at DESC", []);
  return json({
    releases: results.map((r) => ({
      version: r.version,
      cut_at: r.cut_at,
      github_tag: r.github_tag,
      zenodo_version_doi: r.zenodo_version_doi,
      n_genes: r.n_genes,
      notes: r.notes,
      api_members: !isZenodoOnly(r),
    })),
  });
}

export async function handleRelease(env, ver) {
  const v = normalizeVersion(ver);
  if (!v) return badRequest("invalid_version");
  const rel = await dataReleaseRow(env, "WHERE version = ?", [v]);
  if (!rel) return notFound("release_not_found");
  // Immutable once its Zenodo version is published; until then a short TTL
  // so --set-doi shows up promptly.
  const hasDoi = Boolean(rel.zenodo_version_doi);
  const ttl = hasDoi ? CACHE_TTL_IMMUTABLE : CACHE_TTL_SHORT;
  const base = {
    version: rel.version,
    cut_at: rel.cut_at,
    github_tag: rel.github_tag,
    zenodo_version_doi: rel.zenodo_version_doi,
    n_genes: rel.n_genes,
    notes: rel.notes,
  };
  if (isZenodoOnly(rel)) {
    return json(
      {
        ...base,
        api_members: false,
        members: [],
        api_note:
          `Release ${rel.version} predates the API's per-gene record history ` +
          "and is archived only in its Zenodo deposit" +
          (rel.zenodo_version_doi ? ` (${rel.zenodo_version_doi})` : "") +
          "; its records are not individually served through these history routes.",
      },
      { ttl, immutable: hasDoi },
    );
  }
  const { results } = await env.DB.prepare(
    `SELECT r.gene_symbol, r.hgnc_id, m.revision, r.json_hash, r.evidence_hash, r.md_hash
       FROM data_release_member m
       JOIN record_revision r ON r.gene_symbol = m.gene_symbol AND r.revision = m.revision
      WHERE m.version = ? ORDER BY r.gene_symbol`
  ).bind(v).all();
  return json({ ...base, api_members: true, members: results }, { ttl, immutable: hasDoi });
}

export async function handleReleaseGene(env, ver, symbol, part) {
  const v = normalizeVersion(ver);
  if (!v) return badRequest("invalid_version");
  const sym = checkSymbol(symbol);
  if (!sym) return badRequest("invalid_symbol");
  const rel = await dataReleaseRow(env, "WHERE version = ?", [v]);
  if (!rel) return notFound("release_not_found");
  if (isZenodoOnly(rel)) {
    return json(
      { error: "release_not_in_api_history", zenodo_version_doi: rel.zenodo_version_doi },
      { status: 404, ttl: 60 },
    );
  }
  const row = await env.DB.prepare(
    `SELECT r.revision, r.json_hash, r.evidence_hash, r.md_hash
       FROM data_release_member m
       JOIN record_revision r ON r.gene_symbol = m.gene_symbol AND r.revision = m.revision
      WHERE m.version = ? AND m.gene_symbol = ? COLLATE NOCASE`
  ).bind(v, sym).first();
  if (!row) return notFound("gene_not_in_release");
  return archivedPart(env, row, part);
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
