/** Canonical UniProt numbering; never project these onto isoforms or PDB chains. */
export interface ContactSite {
  ligand_identity_key?: string;
  identity_basis?: string;
  identity_display_label?: string;
  processing_status?: string;
  exclude_from_overview?: boolean;
  exclude_from_ec_overview?: boolean;
  identity_evidence?: string;
  identity_note?: string;
  ligand_id?: string;
  observation_id?: string;
  evidence_count?: number;
  evidence_sources?: string[];
  supportingSites?: ContactSite[];
  source: string;
  partner: string;
  partner_label?: string;
  canonical_partner_label?: string;
  category_reason?: string;
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
export interface ContactGene { overview_note?: string; overview_label?: string; hgnc_id: string; symbol: string; sites: ContactSite[]; uniprot_acc?: string; release_id?: string; data_origin?: "api" | "snapshot"; all_ligand_count?: number; audit_status?: "mapped" | "no_mapped_evidence" | "not_audited" }
export const LIGAND_CATEGORIES = {
  endogenous_large: { label: "Endogenous · large molecule", color: "#3d6b60" },
  endogenous_small: { label: "Endogenous · small molecule", color: "#b17a26" },
  therapeutic: { label: "Therapeutic", color: "#922038" },
  tool: { label: "Research tool", color: "#75629b" },
  receptor_partner: { label: "Receptor partner", color: "#426d92" },
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
  if (context === "removed_processing_segment") return "Processed domain / precursor; surface eligibility unresolved";
  if (context.startsWith("extracellular_")) return "Extracellular";
  if (context === "secreted_mature") return "Secreted";
  if (context === "membrane_spanning_site") return "Membrane-spanning";
  if (context.startsWith("unknown")) return "Location uncertain";
  return context.replace("non_extracellular:", "Non-extracellular: ").replace(/_/g, " ");
}

export function filterContacts(sites: ContactSite[], source: string, ecOnly: boolean, query: string): ContactSite[] {
  const search = query.trim().toLowerCase();
  const exactName = search && sites.some(site => ligandName(site).toLowerCase() === search);
  return sites.filter(site => (!ecOnly || (site.context.startsWith("extracellular_") && !site.exclude_from_ec_overview)) &&
    (!source || site.source === source) &&
    (!search || (exactName ? ligandName(site).toLowerCase() === search : `${ligandName(site)} ${site.partner_label ?? ""} ${site.partner}`.toLowerCase().includes(search))));
}

/** Display identity only: preserve source IDs and every original observation. */
export function ligandName(site: ContactSite): string {
  if (site.identity_display_label) return site.identity_display_label;
  // Reviewed names retain construct qualifiers; stripping these can merge variants.
  if (site.canonical_partner_label?.trim()) return site.canonical_partner_label.trim();
  const label = site.partner_label ?? site.partner;
  // Short display aliases do not determine identity; the exported key does.
  if (/^cetuximab(?:\s|$)/i.test(label)) return "Cetuximab";
  const name = label.replace(/\s*\([^)]*\)\s*$/, "").replace(/\s+(Fab|Fv|VHH)$/i, "").trim();
  if (/^(IMC-)?11F8$/i.test(name)) return "necitumumab";
  return name;
}
export function namedLigand(site: ContactSite): boolean {
  if (site.exclude_from_overview) return false;
  if (site.canonical_partner_label?.trim()) return true;
  if (/^sabdab2_/i.test(ligandName(site))) return false;
  return !/^([A-Z0-9]{6,10}|\d+|CCD:.*|sabdab2_.*)$/.test(site.partner) ||
    Boolean(site.partner_label && site.partner_label !== site.partner);
}
export function ligandOptions(sites: ContactSite[]): string[] {
  return browsingContacts(sites, true, "").map(ligandName);
}

/** Anchor site navigation along canonical numbering without letting a single
 * distant contact dominate the location of a discontinuous footprint. */
function contactSitePosition(site: ContactSite): number {
  const positions = [...site.positions].sort((a, b) => a - b);
  if (!positions.length) return Number.POSITIVE_INFINITY;
  const middle = Math.floor(positions.length / 2);
  return positions.length % 2 ? positions[middle] : (positions[middle - 1] + positions[middle]) / 2;
}

export function browsingContacts(sites: ContactSite[], _grouped: boolean, query: string): ContactGroup[] {
  const byLigand = new Map<string, ContactGroup>();
  for (const site of [...sites].filter(site => query.trim() || namedLigand(site)).sort((a,b) => b.positions.length-a.positions.length)) {
    const name = ligandName(site);
    const key = site.ligand_identity_key ?? site.ligand_id ?? name.toLowerCase();
    const existing = byLigand.get(key);
    if (existing) existing.supportingSites.push(site);
    else byLigand.set(key, {...site, partner_label: name, supportingSites: site.supportingSites ?? [site]});
  }
  // Within each category, visit the most overlapping footprint next. This is
  // navigation only: no antibody identities or contact observations are merged.
  const result: ContactGroup[] = [];
  for (const category of Object.keys(LIGAND_CATEGORIES)) {
    const remaining = [...byLigand.values()]
      .filter(site => (site.category ?? "unclassified") === category)
      .sort((a, b) => contactSitePosition(a) - contactSitePosition(b) || ligandName(a).localeCompare(ligandName(b)));
    if (!remaining.length) continue;
    result.push(remaining.shift()!);
    while (remaining.length) {
      const previous = result[result.length - 1];
      const residues = new Set(previous.positions);
      const overlap = (site: ContactSite) => {
        const shared = site.positions.filter(position => residues.has(position)).length;
        const union = residues.size + site.positions.length - shared;
        return union ? shared / union : 0;
      };
      remaining.sort((a, b) => overlap(b) - overlap(a) ||
        Math.abs(contactSitePosition(a) - contactSitePosition(previous)) - Math.abs(contactSitePosition(b) - contactSitePosition(previous)) ||
        contactSitePosition(a) - contactSitePosition(b) || ligandName(a).localeCompare(ligandName(b)));
      result.push(remaining.shift()!);
    }
  }
  return result;
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
      candidate.ligand_identity_key === site.ligand_identity_key &&
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

/** Resolve overlap explicitly instead of letting the last ligand overwrite earlier colors. */
export const SHARED_CONTACT_COLOR = "#536879";
export function contactResidueLayers(sites: ContactSite[]): {color: string; positions: number[]}[] {
  const categories = new Map<number, Set<string>>();
  for (const site of sites) for (const position of site.positions) {
    const colors = categories.get(position) ?? new Set<string>();
    colors.add(contactColor(site)); categories.set(position, colors);
  }
  const layers = new Map<string, number[]>();
  for (const [position, colors] of categories) {
    const color = colors.size > 1 ? SHARED_CONTACT_COLOR : [...colors][0];
    const positions = layers.get(color) ?? [];
    positions.push(position); layers.set(color, positions);
  }
  return [...layers].map(([color, positions]) => ({color, positions}));
}
