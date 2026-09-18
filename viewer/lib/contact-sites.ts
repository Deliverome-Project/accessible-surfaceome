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
