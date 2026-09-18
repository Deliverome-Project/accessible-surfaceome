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
  const records=filterContacts(data.P00533.sites,'',true,'EGF');
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
