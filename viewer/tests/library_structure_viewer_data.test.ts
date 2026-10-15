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
  libraryMembersByAccession,
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
  // The fixture's cohort is `library_designed_orf` -- a proteoform with no UniProt
  // record, so neither "canonical" nor "isoform" is true of it.
  assert.equal(v[0].label, "Designed ORF");
  assert.equal(v[0].residue_offset, 0);
});

test("variants: the label names the proteoform, from the COHORT", () => {
  const labelFor = (over: Record<string, unknown>) =>
    libraryStructureVariants(rec([{ ...topology, ...over }], [structure]))[0].label;

  assert.equal(labelFor({ cohort: "human_canonical", topology_acc: "P11836" }), "Canonical");
  assert.equal(labelFor({ cohort: "human_isoforms", topology_acc: "P11836-2" }), "Isoform 2");
  // Reads the same way as the AFDB isoform tabs beside it, so a reader comparing the two
  // is comparing proteoform to proteoform, with the L1/L2 badge as the only difference.
  assert.equal(labelFor({ cohort: "human_isoforms", topology_acc: "P15941-10" }), "Isoform 10");
  assert.equal(labelFor({ cohort: "cyno_ortholog", topology_acc: "M4ZHZ6" }), "Cyno ortholog");
  assert.equal(labelFor({ cohort: "mouse_ortholog_repick", topology_acc: "P19437" }), "Mouse ortholog");
  assert.equal(labelFor({ cohort: "library_designed_orf" }), "Designed ORF");
});

test("variants: the label does NOT come from candidate_set", () => {
  // This is the whole reason the label moved off `candidate_set`. A
  // `library_reference` member's ordered protein is frequently a UniProt ISOFORM rather
  // than the canonical -- 131 of the 326 L1 tabs that survive the duplicate guard -- so
  // a candidate_set-derived label called those "Ordered" and said nothing about which
  // protein they are. Set the two fields against each other: the cohort must win.
  const v = libraryStructureVariants(
    rec(
      [{ ...topology, candidate_set: "library_reference", cohort: "human_isoforms", topology_acc: "P21439-2" }],
      [structure],
    ),
  );
  assert.equal(v[0].label, "Isoform 2");
  assert.equal(v[0].candidate_set, "library_reference", "candidate_set is still carried");

  // And the converse: an `isoform` candidate_set whose matched record is the canonical.
  const c = libraryStructureVariants(
    rec(
      [{ ...topology, candidate_set: "isoform", cohort: "human_canonical", topology_acc: "Q9NQ90" }],
      [structure],
    ),
  );
  assert.equal(c[0].label, "Canonical");
});

test("variants: an unknown cohort does not get guessed into a proteoform class", () => {
  const v = libraryStructureVariants(
    rec([{ ...topology, cohort: "something_new_2027" }], [structure]),
  );
  assert.equal(v[0].label, "Library form");
  const r = libraryStructureVariants(
    rec([{ ...topology, cohort: "", candidate_set: "expression_rescue" }], [structure]),
  );
  assert.equal(r[0].label, "Rescue arm");
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

// libraryMembersByAccession: which tab shows a protein the library orders. Keyed on the
// sequence-matched topology accession, not on which structure was chosen, so a member
// with no structure (every L2 isoform and ortholog) still marks its tab.

test("members: the canonical is marked when the construct IS the canonical (SLC6A8)", () => {
  const m = libraryMembersByAccession(rec([afdbTopology], [afdbStructure]));
  assert.equal(m.get("P48029")?.[0].candidate_id, "l1-p0031");
  assert.equal(m.get("P48029")?.[0].library, "l1");
});

test("members: an isoform-sequence construct marks the isoform, not the canonical (MUC1)", () => {
  // MUC1's l1-p1264 is P15941-8, folded by us. The 1,255-aa canonical is NOT in the
  // library, and must not be marked just because the member's model is ours.
  const muc1 = { ...topology, candidate_id: "l1-p1264", topology_acc: "P15941-8" };
  const m = libraryMembersByAccession(rec([muc1], [{ ...structure, candidate_id: "l1-p1264" }]));
  assert.ok(m.has("P15941-8"));
  assert.ok(!m.has("P15941"));
});

test("members: no chosen structure is still membership (L2 isoforms and orthologs)", () => {
  const l2 = { ...topology, candidate_id: "l2-p2461", library: "l2", candidate_set: "ortholog", topology_acc: "A0A2K5UMA1" };
  const m = libraryMembersByAccession(rec([l2], []));
  assert.equal(m.get("A0A2K5UMA1")?.[0].library, "l2");
});

test("members: a contained construct marks no existing tab (CACHD1)", () => {
  // Residues 135-1274 of the canonical match no UniProt sequence, so topology_acc is
  // the candidate id; the canonical stays unmarked and the construct gets its own tab.
  const cachd1 = { ...topology, candidate_id: "l1-p0215", topology_acc: "l1-p0215" };
  const m = libraryMembersByAccession(rec([cachd1], []));
  assert.deepEqual([...m.keys()], ["L1-P0215"]);
});

test("members: several members on one gene each mark their own tab (SLC3A2)", () => {
  const rows = [
    ["l1-p1954", "l1", "P08195-2"],
    ["l2-p1433", "l2", "P08195-1"],
    ["l2-p1434", "l2", "P08195-3"],
  ].map(([candidate_id, library, topology_acc]) => ({ ...topology, candidate_id, library, topology_acc }));
  const m = libraryMembersByAccession(rec(rows, []));
  assert.equal(m.size, 3);
  assert.equal(m.get("P08195-1")?.[0].library, "l2");
});
