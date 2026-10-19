// viewer/lib/tag-sites-overlay.ts
/*
 * Pure overlay derivation shared by the linear TopologyBar pins and the 3D
 * StructureViewer spheres. Browser-safe (no node:fs). Drops the non-rendered
 * validated_literature provenance; resolves each site to a residue and a
 * left-percent along a topology of the given length.
 */
import type { TagSiteCategory, TaggedSite, TaggedSiteProvenance } from "./tag-sites-types";
import { tagSiteCategory } from "./tag-sites-types";

export type RenderedProvenance = "literature_retrieved" | "deterministic_computed" | "screen_validated";

export interface RenderableTagSite {
  siteId: string;
  residue: number;               // 1-indexed, within [1, topologyLength]
  leftPct: number;               // 0..100 along the linear bar
  provenance: RenderedProvenance;
  category: TagSiteCategory;     // fine-grained color axis (lane / terminus / snorkel / literature)
  tagType: string;
  siteKind: TaggedSite["site_kind"];
  // Inclusive residue span (from residue_range, e.g. "H27-K159") to color on
  // the 3D cartoon; null for single-residue / terminal / literature sites.
  spanStart: number | null;
  spanEnd: number | null;
}

const RENDERED: TaggedSiteProvenance[] = ["literature_retrieved", "deterministic_computed", "screen_validated"];

/** Parse a residue_range like "H27-K159" / "89-120" -> [27, 159]; null if absent/malformed. */
function parseSpan(range: string | null | undefined): [number, number] | null {
  if (!range) return null;
  const m = /^[A-Za-z]?(\d+)\s*-\s*[A-Za-z]?(\d+)$/.exec(range.trim());
  if (!m) return null;
  const a = Number(m[1]);
  const b = Number(m[2]);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a < 1 || b < a) return null;
  return [a, b];
}

/** Resolve a site to its display residue: terminal_c -> C-terminus (length);
 *  internal / terminal_n -> insert_after_residue (null -> 1). */
function residueOf(site: TaggedSite, topologyLength: number): number | null {
  if (site.site_kind === "terminal_c") return topologyLength;
  const n = site.insert_after_residue;
  if (n === null || n === 0) return 1;
  return n;
}

export function renderableTagSites(
  sites: readonly TaggedSite[],
  topologyLength: number,
): RenderableTagSite[] {
  if (topologyLength <= 0) return [];
  const out: RenderableTagSite[] = [];
  for (const site of sites) {
    if (!RENDERED.includes(site.provenance)) continue; // drop validated_literature
    // Literature sites are only useful for surface tagging when extracellular;
    // an intracellular published tag (e.g. a cytoplasmic C-terminal fusion) is
    // not a surface-accessible site, so we don't render it.
    // Drop intracellular literature sites, EXCEPT an N-terminal tag: it is placed
    // after signal-peptide cleavage (mature extracellular N-term), so its residue
    // topology may read "signal"/non-extracellular while the tag is surface-displayed.
    if (
      site.provenance === "literature_retrieved" &&
      !site.extracellular &&
      site.site_kind !== "terminal_n"
    )
      continue;
    const residue = residueOf(site, topologyLength);
    if (residue === null || residue < 1 || residue > topologyLength) continue;
    const span = parseSpan(site.residue_range);
    out.push({
      siteId: site.site_id,
      residue,
      leftPct: (residue / topologyLength) * 100,
      provenance: site.provenance as RenderedProvenance,
      category: tagSiteCategory(site),
      tagType: site.tag_type,
      siteKind: site.site_kind,
      spanStart: span ? Math.max(1, span[0]) : null,
      spanEnd: span ? Math.min(topologyLength, span[1]) : null,
    });
  }
  return collapseBySpan(out);
}

/** One anchor ball per span: deterministic candidates that share a residue_range
 *  (e.g. TMEM123's 10 disorder sites across H27-K159) collapse to a single
 *  representative — the residue closest to the span midpoint — so the 3D/linear
 *  overlay shows ONE ball plus the whole-span tint, not a row of balls. Sites
 *  with no span (termini, snorkel, single-residue, literature) pass through. */
function collapseBySpan(rows: RenderableTagSite[]): RenderableTagSite[] {
  const groups = new Map<string, RenderableTagSite[]>();
  const out: RenderableTagSite[] = [];
  for (const r of rows) {
    if (r.spanStart == null || r.spanEnd == null) {
      out.push(r);
      continue;
    }
    const key = `${r.category}:${r.spanStart}-${r.spanEnd}`;
    const g = groups.get(key);
    if (g) g.push(r);
    else groups.set(key, [r]);
  }
  for (const g of groups.values()) {
    const mid = ((g[0].spanStart as number) + (g[0].spanEnd as number)) / 2;
    g.sort((a, b) => Math.abs(a.residue - mid) - Math.abs(b.residue - mid));
    out.push(g[0]); // anchor closest to the span midpoint
  }
  return out;
}
