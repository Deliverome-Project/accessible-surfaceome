/** Build API summaries with exactly the same identity/footprint rules as the viewer. */
import {readFileSync, readdirSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {browsingContacts, filterContacts, ligandName, namedLigand} from '../../viewer/lib/contact-sites.ts';
const root = new URL('../../', import.meta.url);
const read = path => readFileSync(new URL(path, root), 'utf8');
const hash = text => createHash('sha256').update(text).digest('hex');
const canonical = value => JSON.stringify(value);
const dir = 'viewer/public/data/contact-sites/';
const manifest = JSON.parse(read(dir+'manifest.json'));
const shards = readdirSync(new URL(dir,root)).filter(x=>/^[0-9a-f]{2}\.json$/.test(x)).sort();
const genes = Object.assign({}, ...shards.map(x=>JSON.parse(read(dir+x))));
const sequences = {};
for (const f of readdirSync(new URL('data/external/structural_intact_extension/uniprot/',root)).filter(x=>x.endsWith('.json'))) {
 for (const r of JSON.parse(read('data/external/structural_intact_extension/uniprot/'+f)).data?.results ?? []) sequences[r.primaryAccession] = r.sequence?.value;
}
const denominator = read('data/analysis/deep_dive_binding_sites/binder_denominator_genes.tsv').trim().split('\n').map(x=>x.split('\t'));
const cols = denominator.shift();
const excluded = denominator.filter(r=>r[cols.indexOf('identifier_status')]!=='unique').map(r=>Object.fromEntries(['hgnc_id','hgnc_symbol','identifier_status','uniprot_acc'].map(k=>[k,r[cols.indexOf(k)]])));
const releaseId = 'contacts-'+hash(shards.map(x=>read(dir+x)).join('')+read('viewer/lib/contact-sites.ts')+read('scripts/audit/export_contact_release.mjs')+canonical(manifest)+canonical(sequences)).slice(0,20);
const identities = new Map(); const output=[];
for (const [acc,gene] of Object.entries(genes).sort()) {
 const sequence=sequences[acc];
 if (gene.sites.length && !sequence) throw Error('Missing reference sequence: '+acc);
 const observations=gene.sites.map(site=>{
  if (!site.positions.length || site.positions.some(p=>!Number.isInteger(p)||p<1||p>sequence.length)) throw Error('Invalid residue: '+acc);
  // Freeze the audited display identity for this release; raw construct/source IDs remain in each observation.
  const name=ligandName(site); const identityKey=namedLigand(site)?name.toLowerCase():`${site.source}:${site.partner}`;
  const ligand_id='lig-'+hash(identityKey).slice(0,24);
  const observation_id='obs-'+hash(canonical([acc,site])).slice(0,32);
  if (!identities.has(ligand_id)) identities.set(ligand_id,{ligand_id,name,aliases:[],source_ids:[],identity_basis:'audited_alias_rules_v1'});
  const identity=identities.get(ligand_id);
  for(const [key,value] of [['aliases',site.partner_label??site.partner],['source_ids',site.source+':'+site.partner]]) if(!identity[key].includes(value)) identity[key].push(value);
  return {...site,ligand_id,observation_id};
 });
 const summarize=ec=>browsingContacts(filterContacts(observations,'',ec,''),true,'').map(({supportingSites,...site})=>({...site,evidence_count:supportingSites.length,evidence_sources:[...new Set(supportingSites.map(s=>s.source))],supportingSites:[]}));
 const all=summarize(false), ec=summarize(true);
 output.push({uniprot_acc:acc,hgnc_id:gene.hgnc_id,symbol:gene.symbol,overview_note:gene.overview_note,overview_label:gene.overview_label,audit_status:observations.length?'mapped':'no_mapped_evidence',reference_sequence_sha256:sequence?hash(sequence):null,reference_sequence_length:sequence?.length??null,all_ligand_count:all.length,all,extracellular:ec,observations});
}
const bundle={release_id:releaseId,manifest:{...manifest,release_id:releaseId,api_schema_version:1,identity_rules:'audited_alias_rules_v1',cohort_rows:denominator.length,excluded_identifiers:excluded,observation_count:output.reduce((n,g)=>n+g.observations.length,0)},ligands:[...identities.values()].sort((a,b)=>a.ligand_id.localeCompare(b.ligand_id)),genes:output};
writeFileSync(process.argv[2]??'/private/tmp/contact-release.json',canonical(bundle));
writeFileSync(new URL(dir+'api-release.json',root),canonical({release_id:releaseId})+'\n');
console.log(JSON.stringify({release_id:releaseId,genes:output.length,observations:bundle.manifest.observation_count,excluded:excluded.length,largest_summary_bytes:Math.max(...output.map(({observations,...g})=>Buffer.byteLength(canonical(g))))}));
