import {contactShard} from './contact-sites';
import type {ContactGene, ContactSite} from './contact-sites';

const API = process.env.NEXT_PUBLIC_CONTACT_API_BASE ?? 'https://api.deliverome.org/surfaceome';
async function request(path: string, signal: AbortSignal) {
  const response = await fetch(`${API}${path}`, {signal});
  if (!response.ok) throw new Error(`Contact API: ${response.status}`);
  return response.json();
}
export async function loadContactGene(accession: string, signal: AbortSignal): Promise<ContactGene> {
  try {
    const release = await request('/v1/contact-sites/releases/current', signal);
    const gene = await request(`/v1/contact-sites/releases/${release.release_id}/proteins/${accession}`, signal);
    if (gene.release_id !== release.release_id || !Array.isArray(gene.sites)) throw new Error('Invalid contact response');
    return {...gene, data_origin:'api'};
  } catch (error) {
    if (signal.aborted) throw error;
    const [response, metadata] = await Promise.all([
      fetch(`/data/contact-sites/${contactShard(accession)}.json`, {signal}),
      fetch('/data/contact-sites/api-release.json', {signal}),
    ]);
    if (!response.ok || !metadata.ok) throw error;
    const snapshot = await response.json(), release = await metadata.json();
    const gene = snapshot[accession];
    if (!gene) return {hgnc_id:'',symbol:'',sites:[],audit_status:'not_audited',data_origin:'snapshot',release_id:release.release_id};
    return {...gene,uniprot_acc:accession,data_origin:'snapshot',release_id:release.release_id,audit_status:gene.sites.length?'mapped':'no_mapped_evidence'};
  }
}
export async function loadContactEvidence(gene: ContactGene, ligandId: string, signal: AbortSignal): Promise<ContactSite[]> {
  const records: ContactSite[]=[];
  let cursor: string | null=null;
  const seen=new Set<string>();
  do {
    const page: {release_id:string; observations:ContactSite[]; next_cursor:string|null} = await request(
      `/v1/contact-sites/releases/${gene.release_id}/proteins/${gene.uniprot_acc}/ligands/${ligandId}/evidence${cursor?`?cursor=${cursor}`:''}`,signal);
    if (page.release_id !== gene.release_id) throw new Error('Contact evidence release mismatch');
    records.push(...page.observations);
    cursor=page.next_cursor;
    if(cursor) { if(seen.has(cursor)) throw new Error('Repeated evidence cursor'); seen.add(cursor); }
  } while(cursor);
  return records;
}
