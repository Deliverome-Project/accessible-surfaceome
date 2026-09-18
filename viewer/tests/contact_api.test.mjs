import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source=readFileSync(new URL('../lib/contact-api.ts',import.meta.url),'utf8').replace("'./contact-sites'",JSON.stringify(new URL('../lib/contact-sites.ts',import.meta.url).href));
const {loadContactGene,loadContactEvidence}=await import('data:text/javascript;base64,'+Buffer.from(stripTypeScriptTypes(source)).toString('base64'));
const original=globalThis.fetch;
const ok=value=>new Response(JSON.stringify(value),{status:200});
test('authoritative empty results never fall back to a snapshot',async()=>{
 let calls=0;globalThis.fetch=async()=>++calls===1?ok({release_id:'r1'}):ok({release_id:'r1',sites:[],audit_status:'no_mapped_evidence'});
 try {const gene=await loadContactGene('P00533',new AbortController().signal);assert.equal(gene.data_origin,'api');assert.equal(gene.sites.length,0);assert.equal(calls,2);} finally {globalThis.fetch=original;}
});
test('service failure is explicitly labeled with fallback release',async()=>{
 globalThis.fetch=async url=>url.includes('api-release')?ok({release_id:'snapshot1'}):url.startsWith('/data/')?ok({P00533:{sites:[],symbol:'EGFR',hgnc_id:'HGNC:3236'}}):new Response('',{status:503});
 try {const gene=await loadContactGene('P00533',new AbortController().signal);assert.equal(gene.data_origin,'snapshot');assert.equal(gene.release_id,'snapshot1');} finally {globalThis.fetch=original;}
});
test('evidence rejects a different release and repeated cursors',async()=>{
 const gene={release_id:'r1',uniprot_acc:'P00533'};
 globalThis.fetch=async()=>ok({release_id:'r2',observations:[],next_cursor:null});
 try {await assert.rejects(()=>loadContactEvidence(gene,'lig',new AbortController().signal),/release mismatch/);
 globalThis.fetch=async()=>ok({release_id:'r1',observations:[],next_cursor:'same'});
 await assert.rejects(()=>loadContactEvidence(gene,'lig',new AbortController().signal),/Repeated/);
 } finally {globalThis.fetch=original;}
});
