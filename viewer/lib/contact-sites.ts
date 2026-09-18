/** Canonical UniProt numbering; never project these onto isoforms or PDB chains. */
export interface ContactSite {
  source: string;
  partner: string;
  partner_label?: string;
  category?: LigandCategory;
  category_reference?: string;
  pdb: string;
  positions: number[];
  context: string;
  reference: string;
  method: string;
  evidence: string;
  confidence: string;
}
export interface ContactGene { hgnc_id: string; symbol: string; sites: ContactSite[] }
export const LIGAND_CATEGORIES = {
  endogenous_large: { label: "Endogenous · large molecule", color: "#3d6b60" },
  endogenous_small: { label: "Endogenous · small molecule", color: "#b17a26" },
  therapeutic: { label: "Therapeutic", color: "#922038" },
  tool: { label: "Research tool", color: "#75629b" },
  unclassified: { label: "Unclassified", color: "#777777" },
} as const;
export type LigandCategory = keyof typeof LIGAND_CATEGORIES;
export function contactColor(site: ContactSite): string {
  return LIGAND_CATEGORIES[site.category ?? "unclassified"].color;
}
export const CONTACT_COLORS: Record<string, string> = {
  "PDB/PDBe": "#0072b2", "SAbDab": "#cc79a7", "Thera-SAbDab": "#882255",
  "AACDB": "#009e73", "IEDB": "#d55e00", "BioLiP": "#aa7700",
  "GPCRdb": "#332288", "PDBe": "#44aa99", "IUPHAR+PDBe": "#117733",
  "BioGRID+literature": "#666666",
};
export function contactShard(accession: string): string {
  return (Array.from(accession).reduce((sum, char) => sum + char.charCodeAt(0), 0) % 64)
    .toString(16).padStart(2, "0");
}
export function contactContext(context: string): string {
  if (context.startsWith("extracellular_")) return "Extracellular";
  if (context === "secreted_mature") return "Secreted";
  if (context === "membrane_spanning_site") return "Membrane-spanning";
  if (context.startsWith("unknown")) return "Location uncertain";
  return context.replace("non_extracellular:", "Non-extracellular: ").replace(/_/g, " ");
}

export function filterContacts(sites: ContactSite[], source: string, ecOnly: boolean, query: string): ContactSite[] {
  const search = query.trim().toLowerCase();
  const exactName = search && sites.some(site => ligandName(site).toLowerCase() === search);
  return sites.filter(site => (!ecOnly || site.context.startsWith("extracellular_")) &&
    (!source || site.source === source) &&
    (!search || (exactName ? ligandName(site).toLowerCase() === search : `${ligandName(site)} ${site.partner_label ?? ""} ${site.partner}`.toLowerCase().includes(search))));
}

/** Display identity only: preserve source IDs and every original observation. */
export function ligandName(site: ContactSite): string {
  const label = site.partner_label ?? site.partner;
  // IEDB names retain the parenthetical aliases in the evidence records.
  if (/^cetuximab(?:\s|$)/i.test(label)) return "Cetuximab";
  const name = label.replace(/\s*\([^)]*\)\s*$/, "").replace(/\s+(Fab|Fv|VHH)$/i, "").trim();
  // IEDB calls this necitumumab (11F8); AACDB uses IMC-11F8 Fab.
  if (/^(IMC-)?11F8$/i.test(name)) return "necitumumab";
  return name;
}
export function namedLigand(site: ContactSite): boolean {
  if (/^sabdab2_/i.test(ligandName(site))) return false;
  return !/^([A-Z0-9]{6,10}|\d+|CCD:.*|sabdab2_.*)$/.test(site.partner) ||
    Boolean(site.partner_label && site.partner_label !== site.partner);
}
export function ligandOptions(sites: ContactSite[]): string[] {
  const names = new Map<string, string>();
  for (const site of sites.filter(namedLigand)) {
    const name = ligandName(site);
    if (!names.has(name.toLowerCase())) names.set(name.toLowerCase(), name);
  }
  return [...names.values()].sort((a,b) => a.localeCompare(b));
}
export function browsingContacts(sites: ContactSite[], grouped: boolean, query: string): ContactGroup[] {
  if (query.trim()) return groupContactSites(sites, grouped);
  const byLigand = new Map<string, ContactGroup>();
  for (const site of [...sites].filter(namedLigand).sort((a,b) => b.positions.length-a.positions.length)) {
    const name = ligandName(site);
    const key = name.toLowerCase();
    const existing = byLigand.get(key);
    if (existing) existing.supportingSites.push(site);
    else byLigand.set(key, {...site, partner_label: name, supportingSites: [site]});
  }
  return [...byLigand.values()].sort((a,b) => (a.partner_label ?? "").localeCompare(b.partner_label ?? ""));
}

export interface ContactGroup extends ContactSite { supportingSites: ContactSite[] }

/** Conservative complete-link grouping: every pair shares >=70% Jaccard
 * overlap, with identical partner ID, source and compartment. Never merge
 * different ligands or let an intermediate site bridge distinct footprints.
 * The largest observed site is displayed, not a synthetic union of residues.
 */
export function groupContactSites(sites: ContactSite[], enabled = true): ContactGroup[] {
  const groups: ContactGroup[] = [];
  const ordered = enabled ? [...sites].sort((a, b) =>
    b.positions.length - a.positions.length || a.pdb.localeCompare(b.pdb) ||
    a.positions.join(",").localeCompare(b.positions.join(","))) : sites;
  for (const site of ordered) {
    const residues = new Set(site.positions);
    const group = enabled ? groups.find(candidate =>
      candidate.partner === site.partner && candidate.source === site.source &&
      candidate.context === site.context && candidate.supportingSites.every(other => {
        const intersection = other.positions.filter(position => residues.has(position)).length;
        return intersection / (residues.size + other.positions.length - intersection) >= 0.7;
      })) : undefined;
    if (group) group.supportingSites.push(site);
    else groups.push({ ...site, supportingSites: [site] });
  }
  return groups;
}

export interface ContactAtom { x: number; y: number; z: number; resi: number }

/** Select up to three footprints, each sharing <=20% of its smaller residue
 * set with every other selected footprint. This is a display heuristic only:
 * low residue overlap does not establish simultaneous binding. */
export function comparisonContacts(groups: ContactGroup[], selected: number, compare: boolean): ContactGroup[] {
  if (!groups[selected]) return [];
  const result = [groups[selected]];
  if (!compare) return result;
  for (const candidate of groups) {
    if (result.length === 3) break;
    if (result.every(other => {
      const positions = new Set(other.positions);
      const shared = candidate.positions.filter(p => positions.has(p)).length;
      return shared / Math.min(candidate.positions.length, other.positions.length) <= 0.2;
    })) result.push(candidate);
  }
  return result;
}

/** Convex outline of projected C-alpha coordinates; not a molecular surface. */
export function contactHull(points: [number, number][]): [number, number][] {
  const sorted = [...new Map(points.map(p => [p.join(","), p])).values()]
    .sort((a,b) => a[0]-b[0] || a[1]-b[1]);
  if (sorted.length <= 2) return sorted;
  const cross = (a: number[], b: number[], c: number[]) =>
    (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  const half = (rows: [number,number][]) => {
    const hull: [number,number][] = [];
    for(const point of rows) {
      while(hull.length >= 2 && cross(hull[hull.length-2], hull[hull.length-1],point) <= 0) hull.pop();
      hull.push(point);
    }
    return hull.slice(0,-1);
  };
  return [...half(sorted),...half([...sorted].reverse())];
}
