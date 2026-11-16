import assert from "node:assert/strict";
import { test } from "node:test";
import {
  afdbFragmentNumber,
  alphafoldFragmentPdbUrl,
  pdbResidueSpan,
  selectAfdbModel,
  stitchAfdbFragments,
  type AfdbEntryLike,
} from "../lib/afdb-model";

const pdbUrl = (entryId: string) =>
  `https://alphafold.ebi.ac.uk/files/${entryId}-model_v6.pdb`;

function entry(
  entryId: string,
  uniprotAccession: string,
  start: number,
  end: number,
  extra: Partial<AfdbEntryLike> = {},
): AfdbEntryLike {
  return {
    entryId,
    uniprotAccession,
    uniprotStart: start,
    uniprotEnd: end,
    pdbUrl: pdbUrl(entryId),
    latestVersion: 6,
    isComplex: false,
    providerId: "GDM",
    ...extra,
  };
}

/** One ATOM line in PDB fixed-column layout. */
function atom(serial: number, resi: number, name = " CA ", res = "ALA"): string {
  return (
    "ATOM  " +
    String(serial).padStart(5, " ") +
    " " +
    name +
    " " +
    res +
    " A" +
    String(resi).padStart(4, " ") +
    "    " +
    "   1.000   2.000   3.000  1.00 90.00           C"
  );
}

test("fragment ordinal is parsed off AFDB's own entry ids only", () => {
  assert.equal(afdbFragmentNumber("AF-P00533-F1", "P00533"), 1);
  assert.equal(afdbFragmentNumber("AF-Q8WZ42-F7", "Q8WZ42"), 7);
  // isoform-suffixed accessions are AFDB entries in their own right
  assert.equal(afdbFragmentNumber("AF-Q07954-2-F1", "Q07954-2"), 1);
  // the isoform entry does NOT belong to the bare accession
  assert.equal(afdbFragmentNumber("AF-Q07954-2-F1", "Q07954"), null);
  // federated third-party model: opaque id, not accession-keyed
  assert.equal(afdbFragmentNumber("AF-0000000015138413", "Q04900"), null);
  assert.equal(afdbFragmentNumber(undefined, "P00533"), null);
});

test("single-fragment entry selects as one fragment with its reported span", () => {
  const sel = selectAfdbModel([entry("AF-P00533-F1", "P00533", 1, 1210)], "P00533");
  assert.ok(sel);
  assert.equal(sel.fragments.length, 1);
  assert.equal(sel.isMultiFragment, false);
  assert.equal(sel.reportedStart, 1);
  assert.equal(sel.reportedEnd, 1210);
  assert.equal(sel.fragments[0].pdbUrl, pdbUrl("AF-P00533-F1"));
});

test("a split entry yields EVERY fragment, in order, not just F1", () => {
  // Shape AFDB uses for an entry past its per-model residue cap: overlapping
  // ~1,400-residue fragments. Deliberately supplied out of order.
  const sel = selectAfdbModel(
    [
      entry("AF-Q6ZZZ9-F3", "Q6ZZZ9", 2401, 3600),
      entry("AF-Q6ZZZ9-F1", "Q6ZZZ9", 1, 1400),
      entry("AF-Q6ZZZ9-F2", "Q6ZZZ9", 1201, 2600),
    ],
    "Q6ZZZ9",
  );
  assert.ok(sel);
  assert.equal(sel.isMultiFragment, true);
  assert.deepEqual(
    sel.fragments.map((f) => f.fragment),
    [1, 2, 3],
  );
  assert.equal(sel.reportedStart, 1);
  assert.equal(sel.reportedEnd, 3600);
  // metadata (pLDDT, version, entry page) comes from fragment 1
  assert.equal(sel.entry.entryId, "AF-Q6ZZZ9-F1");
});

test("an isoform-only response selects NO model (the LRP1 case)", () => {
  // /api/prediction/Q07954 answers 200 with isoform 2 and no canonical model.
  const sel = selectAfdbModel(
    [entry("AF-Q07954-2-F1", "Q07954-2", 1, 292)],
    "Q07954",
  );
  assert.equal(sel, null);
});

test("isoform siblings never leak into a base accession's selection", () => {
  const sel = selectAfdbModel(
    [
      entry("AF-P14209-F1", "P14209", 1, 185),
      entry("AF-P14209-3-F1", "P14209-3", 1, 169),
      entry("AF-P14209-2-F1", "P14209-2", 1, 160),
    ],
    "P14209",
  );
  assert.ok(sel);
  assert.equal(sel.fragments.length, 1);
  assert.equal(sel.fragments[0].entryId, "AF-P14209-F1");
});

test("AFDB's own model wins over a federated third-party one on the same acc", () => {
  // Observed on CD164/CD99: an ATBC ColabFold entry shares the bare acc. It
  // must not be what the caption calls "AlphaFold model", and array position
  // is not a contract — put it first.
  const sel = selectAfdbModel(
    [
      entry("AF-0000000015138413", "Q04900", 1, 197, {
        providerId: "ATBC",
        latestVersion: 1,
      }),
      entry("AF-Q04900-F1", "Q04900", 1, 197),
    ],
    "Q04900",
  );
  assert.ok(sel);
  assert.equal(sel.fragments.length, 1);
  assert.equal(sel.fragments[0].entryId, "AF-Q04900-F1");
});

test("a federated model is still rendered when it is all AFDB has", () => {
  const sel = selectAfdbModel(
    [
      entry("AF-0000000015138413", "Q04900", 1, 197, {
        providerId: "ATBC",
      }),
    ],
    "Q04900",
  );
  assert.ok(sel);
  assert.equal(sel.fragments.length, 1);
  assert.equal(sel.fragments[0].fragment, 1);
});

test("complexes are excluded — the topology coloring expects one chain", () => {
  assert.equal(
    selectAfdbModel(
      [entry("AF-P00533-F1", "P00533", 1, 1210, { isComplex: true })],
      "P00533",
    ),
    null,
  );
});

test("empty / malformed responses select nothing rather than guessing", () => {
  assert.equal(selectAfdbModel([], "P00533"), null);
  assert.equal(selectAfdbModel(null, "P00533"), null);
  assert.equal(selectAfdbModel(undefined, "P00533"), null);
  // an entry with no coordinates is not renderable
  assert.equal(
    selectAfdbModel(
      [{ entryId: "AF-P00533-F1", uniprotAccession: "P00533" }],
      "P00533",
    ),
    null,
  );
});

test("the offline fallback URL can address any fragment, not only F1", () => {
  assert.match(alphafoldFragmentPdbUrl("P00533"), /AF-P00533-F1-model_v6\.pdb$/);
  assert.match(
    alphafoldFragmentPdbUrl("Q8WZ42", 4),
    /AF-Q8WZ42-F4-model_v6\.pdb$/,
  );
  assert.match(
    alphafoldFragmentPdbUrl("Q8WZ42", 2, "v4"),
    /AF-Q8WZ42-F2-model_v4\.pdb$/,
  );
  // nonsense fragment numbers degrade to F1 rather than building a bad URL
  assert.match(alphafoldFragmentPdbUrl("P00533", 0), /-F1-/);
  assert.match(alphafoldFragmentPdbUrl("P00533", Number.NaN), /-F1-/);
});

test("residue span is read from the atoms, which is what the reader sees", () => {
  const pdb = [atom(1, 1), atom(2, 2), atom(3, 1237)].join("\n");
  assert.deepEqual(pdbResidueSpan(pdb), { min: 1, max: 1237 });
  assert.equal(pdbResidueSpan("HEADER something\nEND"), null);
  assert.equal(pdbResidueSpan(""), null);
});

test("fragments numbered from 1 are offset onto the UniProt axis", () => {
  // F2 restarts its own numbering at 1 but covers UniProt 1201+.
  const f1 = [atom(1, 1), atom(2, 2), atom(3, 1400)].join("\n");
  const f2 = [atom(1, 1), atom(2, 200), atom(3, 1400)].join("\n");
  const joined = stitchAfdbFragments([
    { text: f1, start: 1 },
    { text: f2, start: 1201 },
  ]);
  const span = pdbResidueSpan(joined);
  assert.deepEqual(span, { min: 1, max: 2600 });
  // F2's residue 1 lands at UniProt 1201; its 1400 lands at 2600.
  const resis = joined
    .split("\n")
    .filter((l) => l.startsWith("ATOM"))
    .map((l) => Number.parseInt(l.slice(22, 26).trim(), 10));
  assert.ok(resis.includes(1400), "F2 residue 200 → UniProt 1400");
  assert.ok(resis.includes(2600), "F2 residue 1400 → UniProt 2600");
});

test("fragments already in UniProt numbering are passed through untouched", () => {
  const f1 = [atom(1, 1), atom(2, 1400)].join("\n");
  const f2 = [atom(1, 1201), atom(2, 2600)].join("\n");
  const joined = stitchAfdbFragments([
    { text: f1, start: 1 },
    { text: f2, start: 1201 },
  ]);
  assert.deepEqual(pdbResidueSpan(joined), { min: 1, max: 2600 });
});

test("overlapping residues are emitted once, first fragment wins", () => {
  // Both fragments claim UniProt 1300 (AFDB fragments overlap by design):
  // F1 has it at 1300, F2 (local numbering from 1, starting at UniProt 1201)
  // has it at its own residue 100.
  const f1 = [atom(1, 1, " CA ", "MET"), atom(2, 1300, " CA ", "GLY")].join("\n");
  const f2 = [atom(1, 1, " CA ", "SER"), atom(2, 100, " CA ", "TRP"), atom(3, 500, " CA ", "ALA")].join("\n");
  const joined = stitchAfdbFragments([
    { text: f1, start: 1 },
    { text: f2, start: 1201 },
  ]);
  const lines = joined.split("\n").filter((l) => l.startsWith("ATOM"));
  const at1300 = lines.filter(
    (l) => Number.parseInt(l.slice(22, 26).trim(), 10) === 1300,
  );
  assert.equal(at1300.length, 1, "residue 1300 appears exactly once");
  assert.match(at1300[0], /GLY/, "fragment 1's copy is the one kept");
  // and F2's non-overlapping residue still made it
  assert.ok(
    lines.some((l) => Number.parseInt(l.slice(22, 26).trim(), 10) === 1700),
  );
});

test("stitching renumbers atom serials sequentially and closes the file", () => {
  const f1 = [atom(1, 1), atom(2, 2)].join("\n");
  const f2 = [atom(1, 1), atom(2, 2)].join("\n");
  const joined = stitchAfdbFragments([
    { text: f1, start: 1 },
    { text: f2, start: 1201 },
  ]);
  const serials = joined
    .split("\n")
    .filter((l) => l.startsWith("ATOM"))
    .map((l) => Number.parseInt(l.slice(6, 11).trim(), 10));
  assert.deepEqual(serials, [1, 2, 3, 4]);
  assert.ok(joined.includes("\nTER\n"));
  assert.ok(joined.trimEnd().endsWith("END"));
});

test("a single fragment is returned byte-identical — no rewrite risk", () => {
  const f1 = [atom(1, 1), atom(2, 2)].join("\n");
  assert.equal(stitchAfdbFragments([{ text: f1, start: 1 }]), f1);
  assert.equal(stitchAfdbFragments([]), "");
});
