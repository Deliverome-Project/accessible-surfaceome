import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {handleContactSites} from '../src/contact-sites.js';
const release='contacts-01234567890123456789', ligand='lig-'+ 'a'.repeat(24);
function fixture() {
 const db=new DatabaseSync(':memory:');
 db.exec(readFileSync(new URL('../../../migrations/contact_sites.sql',import.meta.url),'utf8'));
 db.exec('CREATE TABLE gene_identifier_public(hgnc_id TEXT,uniprot_acc TEXT)');
 db.prepare("INSERT INTO contact_release(release_id,manifest_json,state) VALUES(?,?,'validated')").run(release,JSON.stringify({release_id:release}));
 db.prepare('INSERT INTO contact_active_release VALUES(1,?)').run(release);
 db.prepare('INSERT INTO contact_gene VALUES(?,?,?,?,?)').run(release,'P00533','HGNC:3236',JSON.stringify({audit_status:'mapped',all:[{partner:'all'}],extracellular:[{partner:'ec'}]}),'hash');
 db.prepare('INSERT INTO contact_ligand VALUES(?,?,?)').run(release,ligand,'{}');
 db.prepare('INSERT INTO contact_gene_ligand VALUES(?,?,?,?)').run(release,'P00533',ligand,'{}');
 for(let n=0;n<102;n++) db.prepare('INSERT INTO contact_observation VALUES(?,?,?,?,?,?,?,?)').run(release,'obs-'+n.toString(16).padStart(32,'0'),'P00533',ligand,'PDB/PDBe',n===101?'intracellular':'extracellular_explicit',JSON.stringify({n}),'hash');
 db.prepare('INSERT INTO gene_identifier_public VALUES(?,?)').run('HGNC:1','P12345');
 const DB={prepare(sql){return {bind(...args){return {first:async()=>db.prepare(sql).get(...args),all:async()=>({results:db.prepare(sql).all(...args)})}},first:async()=>db.prepare(sql).get()}}};
 const get=async suffix=>{const url=new URL('https://example.test/v1/contact-sites/releases/'+suffix);return handleContactSites(new Request(url),{DB},url.pathname)};
 return {db,get};
}
test('summary scope and current release are explicit; mutable pointer is not cached',async()=>{
 const {get}=fixture();
 const current=await get('current'); assert.equal(current.headers.get('cache-control'),'no-store'); assert.equal((await current.json()).release_id,release);
 assert.equal((await (await get(release+'/proteins/P00533')).json()).sites[0].partner,'ec');
 assert.equal((await (await get(release+'/proteins/P00533?scope=all')).json()).sites[0].partner,'all');
 assert.equal((await get(release+'/proteins/P00533?scope=invalid')).status,400);
});
test('evidence pagination conserves records and excludes intracellular by default',async()=>{
 const {get}=fixture(), path=release+'/proteins/P00533/ligands/'+ligand+'/evidence';
 const first=await (await get(path)).json(); assert.equal(first.observations.length,100);
 const second=await (await get(path+'?cursor='+first.next_cursor)).json(); assert.equal(second.observations.length,1); assert.equal(second.next_cursor,null);
 const all=await (await get(path+'?scope=all&cursor='+first.next_cursor)).json(); assert.equal(all.observations.length,2);
 assert.equal((await get(path+'?cursor=bad')).status,400);
});
test('known unaudited and unknown genes differ; errors remain errors',async()=>{
 const {get}=fixture();assert.equal((await (await get(release+'/proteins/P12345')).json()).audit_status,'not_audited');
 assert.equal((await get(release+'/proteins/P99999')).status,404);
 const bad=await handleContactSites(new Request('https://example.test'),{DB:{prepare(){throw Error('unavailable')}}},'/v1/contact-sites/releases/current');assert.equal(bad.status,503);
});
