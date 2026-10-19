/*
 * mmcifToPdb — the fallback the structure viewer uses for experimental
 * entries RCSB publishes only as mmCIF (9V8W: its A1D9S ligand code is
 * too long for the PDB residue-name column, so the .pdb download 404s).
 * The expected ATOM line below is byte-for-byte what RCSB's own .pdb
 * would carry; a full-file comparison against 7SYD and 9XQC matched on
 * every ATOM/HETATM record when this was written.
 *
 *   npx --yes tsx --test tests/mmcif_to_pdb.test.ts
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { mmcifToPdb } from "../lib/mmcif-to-pdb";

const HEADER = `data_TEST
_struct.entry_id                     TEST
_struct.title                        'membrane protein with a long ligand code'
#
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_alt_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_entity_id
_atom_site.label_seq_id
_atom_site.pdbx_PDB_ins_code
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.occupancy
_atom_site.B_iso_or_equiv
_atom_site.pdbx_formal_charge
_atom_site.auth_seq_id
_atom_site.auth_comp_id
_atom_site.auth_asym_id
_atom_site.auth_atom_id
_atom_site.pdbx_PDB_model_num
`;

function atoms(pdb: string): string[] {
  return pdb.split("\n").filter((l) => /^(ATOM|HETATM)/.test(l));
}

test("ATOM records land in the legacy PDB columns", () => {
  const cif =
    HEADER +
    "ATOM   1    N  N   . ASP   A 1 60  ? 88.475  113.139 112.391 1.00 36.73 ? 60  ASP   A N   1 \n" +
    "ATOM   2    C  CA  . ASP   A 1 60  ? 88.646  114.129 111.336 1.00 36.73 ? 60  ASP   A CA  1 \n" +
    "#\n";
  const lines = atoms(mmcifToPdb(cif).pdb);
  assert.equal(
    lines[0],
    "ATOM      1  N   ASP A  60      88.475 113.139 112.391  1.00 36.73           N  ",
  );
  assert.equal(lines[1].slice(12, 16), " CA ");
});

test("a 5-character ligand code is truncated to the 3-column field", () => {
  const cif =
    HEADER +
    "HETATM 9 C C1 . A1D9S B 2 . ? 1.000 2.000 3.000 1.00 20.00 ? 801 A1D9S A C1 1 \n" +
    "#\n";
  const [line] = atoms(mmcifToPdb(cif).pdb);
  assert.equal(line.slice(0, 6), "HETATM");
  assert.equal(line.slice(17, 20), "A1D");
  assert.equal(line.slice(21, 22), "A");
  assert.equal(line.length, 80);
});

test("quoted atom names keep their prime", () => {
  const cif =
    HEADER +
    `HETATM 3 C "C1'" . NAG C 3 . ? 1.000 2.000 3.000 1.00 20.00 ? 901 NAG A "C1'" 1 \n` +
    "#\n";
  const [line] = atoms(mmcifToPdb(cif).pdb);
  assert.equal(line.slice(12, 16), " C1'");
});

test("multi-character chains are remapped, preferred chain first, and reported", () => {
  const cif =
    HEADER +
    "ATOM 1 N N . GLY A 1 1 ? 0 0 0 1 0 ? 1 GLY A N 1 \n" +
    "ATOM 2 N N . GLY B 1 1 ? 0 0 0 1 0 ? 1 GLY AAA N 1 \n" +
    "ATOM 3 N N . GLY C 1 1 ? 0 0 0 1 0 ? 1 GLY O2 N 1 \n" +
    "#\n";
  const { pdb, chainMap } = mmcifToPdb(cif, { preferredChainId: "O2" });
  assert.equal(chainMap.A, "A");
  // O2 is the chain the caller selects on, so it takes the first free id.
  assert.equal(chainMap.O2, "B");
  assert.equal(chainMap.AAA, "C");
  assert.deepEqual(
    atoms(pdb).map((l) => l[21]),
    ["A", "C", "B"],
  );
});

test("only the first model is emitted", () => {
  const cif =
    HEADER +
    "ATOM 1 N N . GLY A 1 1 ? 0 0 0 1 0 ? 1 GLY A N 1 \n" +
    "ATOM 2 N N . GLY A 1 1 ? 0 0 0 1 0 ? 1 GLY A N 2 \n" +
    "#\n";
  assert.equal(atoms(mmcifToPdb(cif).pdb).length, 1);
});

test("TITLE comes from _struct.title, or the caller when the file has none", () => {
  const body = "ATOM 1 N N . GLY A 1 1 ? 0 0 0 1 0 ? 1 GLY A N 1 \n#\n";
  assert.match(
    mmcifToPdb(HEADER + body).pdb,
    /^TITLE {5}membrane protein with a long ligand code\n/,
  );
  const sliced = HEADER.replace(/_struct\.title.*\n/, "") + body;
  assert.match(
    mmcifToPdb(sliced, { title: "From the entry API" }).pdb,
    /^TITLE {5}From the entry API\n/,
  );
});
