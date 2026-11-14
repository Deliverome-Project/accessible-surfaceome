/*
 * Gene-page structure tabs from the L1 design load: each current member's built pick is
 * shown as its WHOLE tagged refold with the cassette laid out for its own colour, and a
 * tab for a retired L1 design is dropped (TFRC: the retired 81-aa isoform l1-p2520 read
 * as "a tiny fragment").
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs tests/l1_tagged_structure_tab.test.ts
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  currentL1Memberships,
  taggedModelLayout,
  withL1DesignVariants,
  type L1DesignFile,
} from "../lib/l1-design";
import type { StructureVariantLibraryInput } from "../lib/structure-viewer-types";

test("C-terminal tag: native 1..760, cassette 761..811, nothing after", () => {
  const l = taggedModelLayout({
    memberLength: 760, insertAfter: 760, leader: null,
    cassetteFirst: 761, cassetteLast: 811, modelLength: 811,
  });
  assert.deepEqual(l, { segments: [{ unpLo: 1, unpHi: 760, offset: 0 }], cassette: [761, 811], nonNative: [] });
});

test("internal tag: the tail is shifted by the cassette length", () => {
  const l = taggedModelLayout({
    memberLength: 300, insertAfter: 120, leader: null,
    cassetteFirst: 121, cassetteLast: 171, modelLength: 351,
  })!;
  assert.deepEqual(l.segments, [
    { unpLo: 1, unpHi: 120, offset: 0 },
    { unpLo: 121, unpHi: 300, offset: 51 },
  ]);
});

test("Igk swap: the leader remnant is non-native, native resumes after the replaced SP", () => {
  // member SP 1..22 replaced by the Igk leader; mature chain = 2-aa remnant + cassette + 23..200
  const l = taggedModelLayout({
    memberLength: 200, insertAfter: 22, leader: "igk",
    cassetteFirst: 3, cassetteLast: 53, modelLength: 231,
  })!;
  assert.deepEqual(l.segments, [{ unpLo: 23, unpHi: 200, offset: 31 }]);
  assert.deepEqual(l.nonNative, [[1, 2]]);
});

test("snorkel: a TM module between the native chain and the cassette is non-native", () => {
  const l = taggedModelLayout({
    memberLength: 228, insertAfter: 228, leader: null,
    cassetteFirst: 284, cassetteLast: 334, modelLength: 334,
  })!;
  assert.deepEqual(l.segments, [{ unpLo: 1, unpHi: 228, offset: 0 }]);
  assert.deepEqual(l.nonNative, [[229, 283]]);
});

test("numbers that cannot describe one construct give no layout", () => {
  assert.equal(taggedModelLayout({
    memberLength: 50, insertAfter: 10, leader: null, cassetteFirst: 11, cassetteLast: 61, modelLength: 200,
  }), null);
  assert.equal(taggedModelLayout({
    memberLength: 50, insertAfter: null, leader: null, cassetteFirst: 11, cassetteLast: 61, modelLength: 101,
  }), null);
});

const topo = (id: string, n: number) => ({
  candidate_id: id, library: "l1", candidate_set: "library_reference", cohort: "human_canonical",
  topology_acc: "P02786", per_residue_topology: "I".repeat(60) + "M".repeat(20) + "O".repeat(n - 80),
});

const tfrc: L1DesignFile = {
  gene_symbol: "TFRC",
  load: { load_version: "l1d-test", created_at: "2026-11-14T00:00:00Z" },
  members: [{
    member_id: "l1-m2029", design_id: "l1-p2131", gene_symbol: "TFRC", species: "human",
    candidate_set: "library_reference", rung: "C-terminal", ordered_length_aa: 760,
    sites: [{
      site_id: "s1", rung: "C-terminal", site_source: "rung_builder", is_primary: true,
      insert_after_residue: 760, residue_before: null, residue_after: null, leader: null,
      cassette: "spy3-alfa", cassette_aa: 51, rank: null, status: "built", decision: null,
      status_detail: null, confidence: null, rejected_alternative: null, rationale: null,
      tagged_protein_sha256: null, source: { pr: null, pr_state: null, commit: "x", path: "p" },
      decided_by: "d", implemented_by: "i", reason: null,
    } as never],
    structures: [{
      structure_id: "t1", kind: "tagged", site_id: "s1", source: "colabfold_tagged", release: "2026-11-12",
      r2_key: "library-colabfold-tagged/2026-11-12/l1-m2051.cterm.pdb", model_url: null,
      proteoform_match: null, residue_offset: 0, is_chosen: true, mean_plddt: 80,
      cassette_first_model_residue: 761, cassette_last_model_residue: 811, model_length_aa: 811,
      refold_verdict: "pass", note: null,
    }],
  }],
};

const nativeTab = (cid: string, n: number): StructureVariantLibraryInput => ({
  source: "library", id: `library-${cid}`, label: "x", topology: "I".repeat(n), deeptmhmm_type: "TM",
  pdb_url: "u", candidate_id: cid, tranche: "l1", candidate_set: null, model_source: null,
  proteoform_match: null, residue_offset: 0, display_range: [1, n], note: null,
});

test("TFRC: the retired 81-aa design drops, the reference shows its whole tagged refold", () => {
  const tabs = withL1DesignVariants(
    [nativeTab("l1-p2131", 760), nativeTab("l1-p2520", 81), { ...nativeTab("l2-p4210", 763), tranche: "l2" }],
    tfrc,
    [topo("l1-p2131", 760)],
  );
  assert.deepEqual(tabs.map((t) => t.id), ["library-tagged-l1-p2131", "library-l2-p4210"]);
  const t = tabs[0];
  assert.equal(t.display_range, null); // the whole model is drawn
  assert.deepEqual(t.cassette_range, [761, 811]);
  assert.match(t.pdb_url, /library-colabfold-tagged\/2026-11-12\/l1-m2051\.cterm\.pdb$/);
  assert.equal(t.label, "Canonical + tag");
});

test("without the load the tabs are unchanged", () => {
  const before = [nativeTab("l1-p2520", 81)];
  assert.equal(withL1DesignVariants(before, null, []), before);
});

test("library marks drop retired L1 designs only", () => {
  const byAcc = new Map([
    ["F8WBE5", [{ candidate_id: "l1-p2520", library: "l1", candidate_set: "isoform" }]],
    ["P02786", [{ candidate_id: "l1-p2131", library: "l1", candidate_set: "library_reference" }]],
    ["Q62351", [{ candidate_id: "l2-p4210", library: "l2", candidate_set: "ortholog" }]],
  ]);
  assert.deepEqual([...currentL1Memberships(byAcc, tfrc).keys()], ["P02786", "Q62351"]);
});
