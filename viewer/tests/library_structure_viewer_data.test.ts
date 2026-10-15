/*
 * `structureViewerDataFromLibraryMember` must refuse to build a half-answer.
 *
 * Every failure mode here would render as a plausible structure under a plausible
 * overlay, so none of them is catchable by looking at the page. Colouring a library
 * member's model with another proteoform's topology offsets the overlay; renumbering a
 * model without its matching topology does the same in reverse. The builder therefore
 * returns null unless both halves describe the same member and agree on length, and the
 * caller falls back to the canonical path, which is explicitly about the canonical
 * protein.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  STRUCTURES_BASE,
  structureViewerDataFromLibraryMember,
} from "../lib/structure-viewer-types";

const TOPO = "SSSSSSSSMMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOIIIIIIIIII"; // 50 residues

const topology = {
  candidate_id: "l1-p0031",
  library: "l1",
  candidate_set: "library_reference",
  per_residue_topology: TOPO,
  tm_helix_count: 1,
  signal_peptide_length: 8,
  cohort: "library_designed_orf",
  tool: "deeptmhmm_v1",
  topology_version: "topo_2026_10_14_l1_designed",
  topology_acc: "l1-p0031",
};

const structure = {
  candidate_id: "l1-p0031",
  source: "colabfold",
  r2_key: "library-colabfold/colabfold-2026-10-14/l1-p0031.pdb",
  model_url: null as string | null,
  proteoform_match: "ours_by_construction",
  residue_offset: 0,
  ordered_length_aa: TOPO.length,
  display_first_model_residue: 1,
  display_last_model_residue: TOPO.length,
  is_chosen: true,
  note: null as string | null,
};

test("library member: builds from the R2 key when we folded the ordered sequence", () => {
  const d = structureViewerDataFromLibraryMember(topology, structure);
  assert.ok(d);
  assert.equal(d.pdb_url, `${STRUCTURES_BASE}/${structure.r2_key}`);
  assert.equal(d.topology, TOPO);
  assert.equal(d.library_candidate_id, "l1-p0031");
  assert.equal(d.library_tranche, "l1");
  assert.equal(d.source_tool, "deeptmhmm_v1");
});

test("library member: carries the offset and display range for a contained member", () => {
  const d = structureViewerDataFromLibraryMember(topology, {
    ...structure,
    source: "alphafold_db",
    r2_key: null,
    model_url: "https://alphafold.ebi.ac.uk/files/AF-P34969-F1-model_v6.pdb",
    proteoform_match: "contained",
    residue_offset: 101,
    display_first_model_residue: 102,
    display_last_model_residue: 101 + TOPO.length,
  });
  assert.ok(d);
  assert.equal(d.library_residue_offset, 101);
  assert.deepEqual(d.library_display_range, [102, 101 + TOPO.length]);
});

test("library member: refuses when the two halves are about different members", () => {
  const d = structureViewerDataFromLibraryMember(topology, {
    ...structure,
    candidate_id: "l1-p9999",
  });
  assert.equal(d, null);
});

test("library member: refuses when topology length disagrees with the ordered length", () => {
  // One of the two is then about a different protein, and which one is unknowable here.
  const d = structureViewerDataFromLibraryMember(topology, {
    ...structure,
    ordered_length_aa: TOPO.length + 7,
  });
  assert.equal(d, null);
});

test("library member: refuses an alternate structure that was not chosen", () => {
  const d = structureViewerDataFromLibraryMember(topology, {
    ...structure,
    is_chosen: false,
  });
  assert.equal(d, null);
});

test("library member: refuses when there is no topology string", () => {
  const d = structureViewerDataFromLibraryMember(
    { ...topology, per_residue_topology: "" },
    structure,
  );
  assert.equal(d, null);
});

test("library member: refuses when neither an R2 key nor a model URL is available", () => {
  const d = structureViewerDataFromLibraryMember(topology, {
    ...structure,
    r2_key: null,
    model_url: null,
  });
  assert.equal(d, null);
});
