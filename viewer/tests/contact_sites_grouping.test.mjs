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
