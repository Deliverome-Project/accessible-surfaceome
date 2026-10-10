/** `/v1/genes/{sym}/revisions` payload — see the record-history spec. */
export interface RevisionRelease {
  version: string;
  zenodo_version_doi: string | null;
}

/** What changed vs. the previous (numerically lower) revision of this
 *  gene. `"first_archived"` on a gene's first revision — there is no prior
 *  revision to diff against, and a part-by-part comparison against
 *  nothing would be meaningless. Otherwise any of `"record"` /
 *  `"evidence"` / `"markdown"` whose hash differs from the previous
 *  revision (a part appearing or disappearing counts as changed too). */
export type RevisionChange = "first_archived" | "record" | "evidence" | "markdown";

export interface RevisionEntry {
  revision: number;
  published_at: string;
  source: string;
  changed?: RevisionChange[];
  releases: RevisionRelease[];
  url: string;
}

export interface Revisions {
  geneSymbol: string;
  current: RevisionEntry;
  listUrl: string;
}

/** Parse the Worker's `/v1/genes/{sym}/revisions` response into the shape
 *  `<RevisionStrip>` reads, or `null` on any miss (network error, 404
 *  `gene_not_annotated`, or a malformed/empty payload) — the caller then
 *  omits the strip entirely rather than rendering a broken one. */
export function parseRevisions(json: unknown): Revisions | null {
  if (!json || typeof json !== "object") return null;
  const p = json as {
    gene_symbol?: string;
    current_revision?: number;
    revisions?: RevisionEntry[];
  };
  if (!p.gene_symbol || !Array.isArray(p.revisions) || !p.revisions.length) {
    return null;
  }
  const current =
    p.revisions.find((r) => r.revision === p.current_revision) ??
    p.revisions[0];
  return {
    geneSymbol: p.gene_symbol,
    current,
    listUrl: current.url.replace(/\/\d+$/, ""),
  };
}
