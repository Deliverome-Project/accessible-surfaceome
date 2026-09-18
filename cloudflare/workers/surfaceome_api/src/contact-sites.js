// Version-pinned contact evidence. No query-string cache ambiguity: these small
// reads bypass shared edge/KV caches; ETags still identify exact payloads.
export async function handleContactSites(request, env, path) {
  const headers = {'Content-Type':'application/json; charset=utf-8','Access-Control-Allow-Origin':'*','Cache-Control':'no-store'};
  const reply=(body,status=200,etag)=>new Response(JSON.stringify(body),{status,headers:{...headers,...(etag?{ETag:`"${etag}"`}:{})}});
  try {
    if(path === '/v1/contact-sites/releases/current') {
      const row=await env.DB.prepare("SELECT r.manifest_json FROM contact_release r JOIN contact_active_release a ON a.release_id=r.release_id WHERE a.singleton=1 AND r.state='validated'").first();
      return row?reply(JSON.parse(row.manifest_json)):reply({error:'no_contact_release'},503);
    }
    const match=path.match(/^\/v1\/contact-sites\/releases\/(contacts-[a-f0-9]{20})\/proteins\/([A-Z0-9]{6,10})(?:\/(?:ligands\/(lig-[a-f0-9]{24})\/)?(evidence))?$/);
    if(!match) return reply({error:'route_not_found'},404);
    const [,release,acc,ligand,evidence]=match;
    const url=new URL(request.url), scope=url.searchParams.get('scope')??'extracellular';
    if(!['extracellular','all'].includes(scope)) return reply({error:'invalid_scope'},400);
    if([...url.searchParams.keys()].some(k=>!['scope','cursor'].includes(k))) return reply({error:'unknown_parameter'},400);
    const cursor=url.searchParams.get('cursor')??'';
    if(cursor && (!evidence || !/^obs-[a-f0-9]{32}$/.test(cursor))) return reply({error:'invalid_cursor'},400);
    const valid=await env.DB.prepare("SELECT release_id FROM contact_release WHERE release_id=? AND state='validated'").bind(release).first();
    if(!valid) return reply({error:'release_not_found'},404);
    const gene=await env.DB.prepare('SELECT summary_json,payload_sha256 FROM contact_gene WHERE release_id=? AND uniprot_acc=?').bind(release,acc).first();
    if(!gene) {
      const known=await env.DB.prepare('SELECT hgnc_id FROM gene_identifier_public WHERE uniprot_acc=? LIMIT 1').bind(acc).first();
      return known?reply({release_id:release,uniprot_acc:acc,hgnc_id:known.hgnc_id,audit_status:'not_audited',sites:[]}):reply({error:'protein_not_found'},404);
    }
    if(!evidence) {
      const {all,extracellular,...meta}=JSON.parse(gene.summary_json);
      return reply({...meta,release_id:release,scope,sites:scope==='all'?all:extracellular},200,gene.payload_sha256+'-'+scope);
    }
    if(ligand) {
      const found=await env.DB.prepare('SELECT ligand_id FROM contact_gene_ligand WHERE release_id=? AND uniprot_acc=? AND ligand_id=?').bind(release,acc,ligand).first();
      if(!found) return reply({error:'ligand_not_found'},404);
    }
    const params=[release,acc,...(ligand?[ligand]:[]),cursor];
    const rows=await env.DB.prepare(`SELECT observation_id,observation_json FROM contact_observation WHERE release_id=? AND uniprot_acc=? ${ligand?'AND ligand_id=?':''} AND observation_id>? ${scope==='extracellular'?"AND context LIKE 'extracellular\\_%' ESCAPE '\\'":''} ORDER BY observation_id LIMIT 101`).bind(...params).all();
    const page=rows.results.slice(0,100);
    return reply({release_id:release,uniprot_acc:acc,scope,observations:page.map(r=>JSON.parse(r.observation_json)),next_cursor:rows.results.length>100?page.at(-1).observation_id:null});
  } catch(error) {
    console.error('contact_sites_unavailable',error.message);
    return reply({error:'contact_sites_unavailable'},503);
  }
}
