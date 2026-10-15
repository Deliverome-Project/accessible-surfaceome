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
  libraryConstructByAccession,
  libraryStructureVariants,
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

// ---------------------------------------------------------------------------
// libraryStructureVariants: pairing the two halves the Worker serves.
// ---------------------------------------------------------------------------

const rec = (
  topo: unknown[],
  struct: unknown[],
): Parameters<typeof libraryStructureVariants>[0] =>
  ({
    deterministic_features: {
      library_designed_topology: topo,
      library_designed_structure: struct,
    },
  }) as Parameters<typeof libraryStructureVariants>[0];

test("variants: one tab per member with both halves present and agreeing", () => {
  const v = libraryStructureVariants(rec([topology], [structure]));
  assert.equal(v.length, 1);
  assert.equal(v[0].source, "library");
  assert.equal(v[0].id, "library-l1-p0031");
  assert.equal(v[0].sublabel, "l1-p0031");
  assert.equal(v[0].label, "Ordered");
  assert.equal(v[0].residue_offset, 0);
});

test("variants: labels an isoform and an ortholog member distinctly", () => {
  const iso = libraryStructureVariants(
    rec([{ ...topology, candidate_set: "isoform" }], [structure]),
  );
  const ortho = libraryStructureVariants(
    rec([{ ...topology, candidate_set: "ortholog" }], [structure]),
  );
  assert.equal(iso[0].label, "Ordered isoform");
  assert.equal(ortho[0].label, "Ordered ortholog");
});

test("variants: a member with no CHOSEN structure gets no tab", () => {
  // 26 L1 members are in this state. A tab here would fall back to the gene's
  // canonical model, which is a different protein.
  const v = libraryStructureVariants(
    rec([topology], [{ ...structure, is_chosen: false }]),
  );
  assert.equal(v.length, 0);
});

test("variants: never pairs one member's topology with another's structure", () => {
  const v = libraryStructureVariants(
    rec([topology], [{ ...structure, candidate_id: "l1-p9999" }]),
  );
  assert.equal(v.length, 0);
});

test("variants: skips the mismatched member but keeps the good one", () => {
  const good = { ...topology, candidate_id: "l1-p0042" };
  const goodStruct = { ...structure, candidate_id: "l1-p0042" };
  const v = libraryStructureVariants(
    rec(
      [topology, good],
      [{ ...structure, ordered_length_aa: TOPO.length + 9 }, goodStruct],
    ),
  );
  assert.equal(v.length, 1);
  assert.equal(v[0].candidate_id, "l1-p0042");
});

test("variants: empty when either half is missing", () => {
  assert.deepEqual(libraryStructureVariants(rec([topology], [])), []);
  assert.deepEqual(libraryStructureVariants(rec([], [structure])), []);
});

// ---------------------------------------------------------------------------
// Duplicate tabs, and marking an existing tab as the library construct.
//
// SLC6A8's library construct IS its canonical: l1-p2010's chosen structure is AFDB's
// AF-P48029-F1 and P48029 is the gene's canonical accession. Adding a tab for it loads
// byte-identical coordinates under a second name — the same duplicate-tab class the
// isoform list already guards against. The useful answer is to mark the existing tab.
// ---------------------------------------------------------------------------

const afdbTopology = { ...topology, topology_acc: "P48029" };
const afdbStructure = {
  ...structure,
  source: "alphafold_db",
  r2_key: null,
  model_url: "https://alphafold.ebi.ac.uk/files/AF-P48029-F1-model_v6.pdb",
  proteoform_match: "identical",
};

test("variants: no duplicate tab when the model is already shown under another tab", () => {
  const r = rec([afdbTopology], [afdbStructure]);
  assert.equal(libraryStructureVariants(r, ["P48029"]).length, 0);
  assert.equal(libraryStructureVariants(r, ["p48029"]).length, 0, "case-insensitive");
  // Without the hint it still produces a tab — the guard is the caller's accession list.
  assert.equal(libraryStructureVariants(r).length, 1);
});

test("variants: OUR model always gets a tab, even if the accession is shown", () => {
  // A ColabFold model lives at an R2 key no other tab loads, so it is never a duplicate.
  // MUC1 is this case: canonical P15941 is on screen, the library construct is a 273-aa
  // form we folded.
  const v = libraryStructureVariants(rec([topology], [structure]), ["l1-p0031", "P48029"]);
  assert.equal(v.length, 1);
  assert.equal(v[0].model_source, "colabfold");
});

test("libraryConstructByAccession: maps an AFDB-served member onto its accession", () => {
  const m = libraryConstructByAccession(rec([afdbTopology], [afdbStructure]));
  assert.equal(m.size, 1);
  assert.equal(m.get("P48029")?.candidate_id, "l1-p0031");
  assert.equal(m.get("P48029")?.library, "l1");
});

test("libraryConstructByAccession: excludes our own models", () => {
  // They are never an existing tab, so badging an accession for them would mark the
  // canonical as the library construct when it is precisely not — the MUC1 trap.
  assert.equal(libraryConstructByAccession(rec([topology], [structure])).size, 0);
});

test("libraryConstructByAccession: excludes members whose structure was not chosen", () => {
  const m = libraryConstructByAccession(
    rec([afdbTopology], [{ ...afdbStructure, is_chosen: false }]),
  );
  assert.equal(m.size, 0);
});
