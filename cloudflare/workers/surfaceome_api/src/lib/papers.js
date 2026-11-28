// Shared NCBI paper metadata lookup helpers (used by /v1/genes/:symbol/evidence and /v1/internalization/:symbol).
import { isMissingTable } from "./http.js";

// Max distinct papers we'll look up citation metadata for in one request.
// The busiest records cite ~120 papers; the cap is a cheap guard against a
// pathological record turning one page view into an unbounded fan-out of D1
// queries. Beyond it the extra papers simply render without metadata.
export const PAPER_METADATA_MAX = 400;

// Bound parameters per `IN (...)` lookup. D1 rejects a query carrying more
// than 100 bound params, so the id set is chunked and the chunks are issued
// as one `db.batch()` round trip.
export const PAPER_METADATA_CHUNK = 90;

// Pull every distinct `source_id` out of an evidence ledger's spans. Records
// cite the same paper from many spans, so the Set is what keeps the lookup
// (and the response) proportional to papers rather than to citations.
export function collectSourceIds(evidence) {
  const ids = new Set();
  for (const ev of evidence) {
    for (const sp of ev?.spans ?? []) {
      const sid = sp?.source?.source_id;
      if (typeof sid === "string" && sid) ids.add(sid);
      if (ids.size >= PAPER_METADATA_MAX) return [...ids];
    }
  }
  return [...ids];
}

// Citation metadata for a set of `source_id`s, as a `{ [source_id]: {...} }`
// map. This is the serve-time half of the citation pipeline: the annotator
// bakes only an accession into the record (`SourceRef.title` is a placeholder
// equal to the id), and `paper_metadata` — built by
// scripts/build/build_paper_metadata_table.py from NCBI E-utilities — carries
// the real title / byline / journal / year. Joining here rather than
// rewriting stored records means a metadata refresh ships without
// re-annotating any gene.
//
// Returns {} on any failure or when the table hasn't been created yet: the
// drawer degrades to the bare accession it showed before, which is a worse
// reading experience but never a broken page.
//
// `onError`, when given, is called with the caught error for a REAL failure
// (i.e. one `isMissingTable` doesn't recognize as the persistent/intentional
// "table not provisioned yet" case) — handleGeneEvidence uses it to fold
// this query into its own `degraded` list. Callers that don't need that
// (handleInternalization) simply omit it and keep today's silent-degrade
// behavior unchanged.
export async function fetchPaperMetadata(env, sourceIds, { onError } = {}) {
  if (!sourceIds.length) return {};
  const statements = [];
  for (let i = 0; i < sourceIds.length; i += PAPER_METADATA_CHUNK) {
    const chunk = sourceIds.slice(i, i + PAPER_METADATA_CHUNK);
    const placeholders = chunk.map(() => "?").join(",");
    statements.push(
      env.DB.prepare(
        `SELECT source_id, pmid, pmc_id, doi, title, authors_short,
                authors_json, n_authors, journal, year
           FROM paper_metadata
          WHERE source_id IN (${placeholders})`
      ).bind(...chunk)
    );
  }
  let batches;
  try {
    batches = await env.DB.batch(statements);
  } catch (e) {
    if (onError && !isMissingTable(e)) onError(e);
    return {};
  }
  const papers = {};
  for (const b of batches) {
    for (const row of b?.results ?? []) {
      // `authors_json` is stored as a JSON array string; hand the client the
      // parsed array so it never has to know the storage encoding.
      let authors = null;
      if (row.authors_json) {
        try {
          const parsed = JSON.parse(row.authors_json);
          if (Array.isArray(parsed)) authors = parsed;
        } catch (e) {
          authors = null;
        }
      }
      papers[row.source_id] = {
        source_id: row.source_id,
        pmid: row.pmid ?? null,
        pmc_id: row.pmc_id ?? null,
        doi: row.doi ?? null,
        title: row.title ?? null,
        authors_short: row.authors_short ?? null,
        authors: authors,
        n_authors: row.n_authors ?? null,
        journal: row.journal ?? null,
        year: row.year ?? null,
      };
    }
  }
  return papers;
}

// GET /v1/genes/{SYMBOL}/evidence — the evidence ledger split out of the
// per-gene record (see the strip at the end of handleGene). Reads the SAME
// record_json blob from D1 and returns `{ gene, evidence, papers }`. Same
// symbol validation + 404 posture as handleGene (unknown gene →
// gene_not_annotated), and routed through withEdgeCache (+KV) at the same
// 1-day TTL. The one serve-time enrichment here is `papers` (citation
// metadata by source_id) — the evidence array itself is never rewritten.
