// viewer/lib/tag-sites-overlay.ts
/*
 * Pure overlay derivation shared by the linear TopologyBar pins and the 3D
 * StructureViewer spheres. Browser-safe (no node:fs). Drops the non-rendered
 * validated_literature provenance; resolves each site to a residue and a
 * left-percent along a topology of the given length.
 */
import type { TaggedSite, TaggedSiteProvenance } from "./tag-sites-types";

export type RenderedProvenance = "literature_retrieved" | "deterministic_computed";

export interface RenderableTagSite {
  siteId: string;
  residue: number;               // 1-indexed, within [1, topologyLength]
  leftPct: number;               // 0..100 along the linear bar
  provenance: RenderedProvenance;
  tagType: string;
  siteKind: TaggedSite["site_kind"];
}

const RENDERED: TaggedSiteProvenance[] = ["literature_retrieved", "deterministic_computed"];

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
    const residue = residueOf(site, topologyLength);
    if (residue === null || residue < 1 || residue > topologyLength) continue;
    out.push({
      siteId: site.site_id,
      residue,
      leftPct: (residue / topologyLength) * 100,
      provenance: site.provenance as RenderedProvenance,
      tagType: site.tag_type,
      siteKind: site.site_kind,
    });
  }
  return out;
}
