/** Canonical UniProt numbering; never project these onto isoforms or PDB chains. */
export interface ContactSite {
  source: string;
  partner: string;
  partner_label?: string;
  pdb: string;
  positions: number[];
  context: string;
  reference: string;
  method: string;
  evidence: string;
  confidence: string;
}
export interface ContactGene { hgnc_id: string; symbol: string; sites: ContactSite[] }
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
  return sites.filter(site => (!ecOnly || site.context.startsWith("extracellular_")) &&
    (!source || site.source === source) &&
    (!search || `${site.partner_label ?? ""} ${site.partner}`.toLowerCase().includes(search)));
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
