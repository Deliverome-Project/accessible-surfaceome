import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { groupContactSites, filterContacts, contactShard } from '../lib/contact-sites.ts';

const site = (positions, pdb, extra = {}) => ({source:'PDB/PDBe', partner:'P01133', context:'extracellular_explicit', positions, pdb, ...extra});
test('complete-link grouping keeps different footprints and biological identities apart', () => {
  const a=site([1,2,3,4,5,6,7,8],'a');
  const b=site([2,3,4,5,6,7,8,9],'b');
  const c=site([3,4,5,6,7,8,9,10],'c');
  assert.deepEqual(groupContactSites([a,b,c]).map(g=>g.supportingSites.length),[2,1]);
  for(const extra of [{partner:'P01135'},{source:'SAbDab'},{context:'secreted_mature'}]) {
    assert.equal(groupContactSites([a,{...a,...extra}]).length,2);
  }
  assert.equal(groupContactSites([a,b],false).length,2);
  assert.deepEqual(groupContactSites([b,a])[0].positions,a.positions);
});
test('EGFR EGF grouping retains every structural record without synthesizing residues', () => {
  const data=JSON.parse(readFileSync(new URL(`../public/data/contact-sites/${contactShard('P00533')}.json`,import.meta.url)));
  const records=filterContacts(data.P00533.sites,'PDB/PDBe',true,'EGF');
  const groups=groupContactSites(records);
  assert.equal(records.length,10);
  assert.equal(groups.length,3);
  assert.equal(groups.reduce((n,g)=>n+g.supportingSites.length,0),10);
  for(const g of groups) assert.ok(records.some(s=>s.positions===g.positions));
  assert.equal(groupContactSites(records,false).length,10);
});

test('comparison keeps the selected group, caps at three, and rejects overlapping subsets', async () => {
  const { comparisonContacts } = await import('../lib/contact-sites.ts');
  const groups=groupContactSites([
    site([1,2,3,4,5],'a'), site([1,2],'b'), site([10,11,12],'c'),
    site([20,21,22],'d'), site([30,31,32],'e'),
  ],false);
  assert.deepEqual(comparisonContacts(groups,0,true).map(s=>s.pdb),['a','c','d']);
  assert.deepEqual(comparisonContacts(groups,2,false).map(s=>s.pdb),['c']);
  assert.deepEqual(comparisonContacts([],0,true),[]);
});
test('projected outline excludes interior and duplicate points and handles short sites', async () => {
  const { contactHull } = await import('../lib/contact-sites.ts');
  assert.deepEqual(contactHull([[0,0],[2,0],[2,2],[0,2],[1,1],[0,0]]),[[0,0],[2,0],[2,2],[0,2]]);
  assert.deepEqual(contactHull([[1,1]]),[[1,1]]);
  assert.deepEqual(contactHull([[0,0],[1,0],[2,0]]),[[0,0],[2,0]]);
});


test('IUPHAR names expose EGF while TGFA and IMC Fab remain separate groups', () => {
  const data=JSON.parse(readFileSync(new URL(`../public/data/contact-sites/${contactShard('P00533')}.json`,import.meta.url)));
  const sites=data.P00533.sites;
  assert.equal(sites.find(s=>s.partner==='GTOPDB:4918').partner_label,'epiregulin (EREG)');
  assert.equal(sites.find(s=>s.partner==='GTOPDB:4916').partner_label,'EGF');
  assert.equal(sites.find(s=>s.partner==='GTOPDB:5059').partner_label,'TGFα (TGFA)');
  assert.equal(filterContacts(sites,'',true,'EGF').length,20);
  const groups=groupContactSites(filterContacts(sites,'',true,''));
  assert.equal(groups.length,58);
  const imc=groups.find(g=>g.partner==='IMC-11F8 Fab');
  assert.equal(imc.supportingSites.length,8);
  assert.ok(imc.supportingSites.every(s=>s.partner==='IMC-11F8 Fab'));
  const tgfa=groups.filter(g=>g.partner==='GTOPDB:5059'||g.partner==='P01135');
  assert.ok(tgfa.length>0);
  assert.ok(tgfa.every(g=>g.supportingSites.every(s=>s.partner===g.partner)));
});

test('ligand browsing and exact searches show one representative with all observations', async () => {
  const { browsingContacts, ligandOptions, ligandName } = await import('../lib/contact-sites.ts');
  const sites=JSON.parse(readFileSync(new URL(`../public/data/contact-sites/${contactShard('P00533')}.json`,import.meta.url))).P00533.sites;
  const records=filterContacts(sites,'',true,'');
  const overview=browsingContacts(records,true,'');
  const names=overview.map(s=>ligandName(s).toLowerCase());
  assert.equal(new Set(names).size,names.length);
  assert.equal(names.filter(n=>n==='egf').length,1);
  assert.equal(names.filter(n=>n==='cetuximab').length,1);
  assert.equal(names.filter(n=>n==='necitumumab').length,1);
  assert.equal(overview.find(s=>ligandName(s)==='EGF').supportingSites.length,20);
  const egf=browsingContacts(filterContacts(sites,'',true,'EGF'),true,'EGF');
  assert.equal(egf.length,1);
  assert.equal(egf[0].supportingSites.length,20);
  assert.equal(new Set(egf[0].supportingSites.map(s=>s.pdb)).size,10);
  assert.ok(egf[0].supportingSites.some(s=>s.positions===egf[0].positions));
  assert.ok(ligandOptions(records).every(n=>!/^\d+$|^sabdab2_/.test(n)));
  assert.ok(records.filter(s=>s.source==='IEDB').every(s=>s.partner_label && s.partner_label!==s.partner));
  assert.ok(!overview.find(s=>ligandName(s)==='necitumumab').supportingSites.some(s=>s.partner==='P01135'));
});

test('EGFR category totals are ligand counts and retain uncertain roles', async () => {
  const { browsingContacts, contactColor, LIGAND_CATEGORIES } = await import('../lib/contact-sites.ts');
  const sites=JSON.parse(readFileSync(new URL(`../public/data/contact-sites/${contactShard('P00533')}.json`,import.meta.url))).P00533.sites;
  const overview=browsingContacts(filterContacts(sites,'',true,''),true,'');
  const counts=Object.fromEntries(Object.keys(LIGAND_CATEGORIES).map(c=>[c,overview.filter(s=>s.category===c).length]));
  assert.deepEqual(counts,{endogenous_large:4,endogenous_small:0,therapeutic:5,tool:6,receptor_partner:1,unclassified:0});
  assert.equal(Object.values(counts).reduce((a,b)=>a+b,0),16);
  assert.equal(overview.find(s=>s.partner_label==='ERBB2').category,'receptor_partner');
  const egf=sites.filter(s=>s.partner_label==='EGF');
  assert.ok(egf.every(s=>s.category==='endogenous_large' && s.category_reference));
  assert.equal(new Set(egf.map(contactColor)).size,1);
  assert.notEqual(contactColor(egf[0]),contactColor(overview.find(s=>s.partner_label==='Cetuximab')));
});

test('all-ligand rendering retains the full residue union and marks category overlap', async () => {
  const { browsingContacts, contactResidueLayers, SHARED_CONTACT_COLOR } = await import('../lib/contact-sites.ts');
  const sites=JSON.parse(readFileSync(new URL(`../public/data/contact-sites/${contactShard('P00533')}.json`,import.meta.url))).P00533.sites;
  const all=browsingContacts(filterContacts(sites,'',true,''),true,'');
  assert.equal(all.length,16);
  const expected=[...new Set(all.flatMap(s=>s.positions))].sort((a,b)=>a-b);
  const layers=contactResidueLayers(all);
  assert.deepEqual(layers.flatMap(l=>l.positions).sort((a,b)=>a-b),expected);
  assert.ok(layers.some(l=>l.color===SHARED_CONTACT_COLOR));
  const single=browsingContacts(filterContacts(sites,'',true,'EGF'),true,'EGF');
  assert.equal(contactResidueLayers(single).length,1);
  assert.notEqual(contactResidueLayers(single)[0].color,SHARED_CONTACT_COLOR);
  assert.deepEqual(contactResidueLayers(all).flatMap(l=>l.positions).sort((a,b)=>a-b),contactResidueLayers([...all].reverse()).flatMap(l=>l.positions).sort((a,b)=>a-b));
});

test('reviewed EGFR aliases consolidate GC1118 while preserving both source names', async () => {
  const { browsingContacts } = await import('../lib/contact-sites.ts');
  const sites=JSON.parse(readFileSync(new URL(`../public/data/contact-sites/${contactShard('P00533')}.json`,import.meta.url))).P00533.sites;
  const matched=browsingContacts(filterContacts(sites,'',true,'GC1118'),true,'GC1118');
  assert.equal(matched.length,1);
  assert.equal(matched[0].partner_label,'GC1118');
  assert.equal(matched[0].supportingSites.length,5);
  assert.ok(matched[0].supportingSites.some(s=>s.partner_label==='GC1118A'));
  for (const name of ['059-152','DL11']) {
    const group=browsingContacts(filterContacts(sites,'',true,name),true,name)[0];
    assert.equal(group.category,'tool');
    assert.ok(group.category_reason && group.category_reference);
  }
});

test('reviewed six-target cleanup preserves observations and fixes identities', async () => {
  const {browsingContacts} = await import('../lib/contact-sites.ts');
  const gene = acc => JSON.parse(readFileSync(new URL(`../public/data/contact-sites/${contactShard(acc)}.json`,import.meta.url)))[acc];
  for (const [acc,count,records] of [['P04626',29,121],['Q15116',26,85],['P08581',5,52],['P08887',6,21],['Q9NZQ7',15,31],['P35968',4,24]]) {
    const g=gene(acc), sites=browsingContacts(filterContacts(g.sites,'',true,''),true,'');
    assert.equal(g.sites.length,records); assert.equal(sites.length,count);
    for(const s of g.sites.filter(s=>s.source==='Thera-SAbDab')) {assert.equal(s.identity_evidence,'sequence_matched_antibody_arm'); assert.ok(s.identity_matches.length);}
  }
  const her2=gene('P04626');
  assert.ok(her2.sites.some(s=>s.partner_label==='CMJ112' && s.exclude_from_overview));
  assert.ok(her2.sites.some(s=>s.partner==='Herceptin Fab' && s.canonical_partner_label==='Trastuzumab'));
  const pdl1=gene('Q9NZQ7');
  assert.ok(pdl1.sites.some(s=>s.partner==='P33681' && s.category==='therapeutic' && s.canonical_partner_label==='Davoceticept (ALPN-202)'));
  assert.ok(pdl1.sites.some(s=>s.partner==='CCD:6GX' && s.canonical_partner_label==='BMS-202'));
  assert.ok(gene('P08887').sites.some(s=>s.partner==='CYS' && s.exclude_from_overview));
});
