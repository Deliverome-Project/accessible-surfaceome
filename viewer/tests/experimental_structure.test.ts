/*
 * lib/experimental-structure — the PDBe pick and the RCSB load the
 * structure viewer's Experimental tab runs, driven here with a stubbed
 * fetch so every download branch is pinned offline. The cohort-wide
 * live check of the same code is scripts/audit-structures.ts.
 *
 *   npx --yes tsx --test tests/experimental_structure.test.ts
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  dbrefSegments,
  EXP_FULL_ASSEMBLY_MAX_ATOMS,
  fetchExperimentalPdb,
  observedResSeq,
  pickBestStructure,
  pickPdbChain,
  projectedCoverage,
  projectExperimentalChain,
  type PDBeBestStructure,
} from "../lib/experimental-structure";

function hit(over: Partial<PDBeBestStructure>): PDBeBestStructure {
  return {
    pdb_id: "1abc",
    chain_id: "A",
    unp_start: 1,
    unp_end: 100,
    start: 1,
    end: 100,
    experimental_method: "X-ray diffraction",
    resolution: 2.0,
    coverage: 0.5,
    tax_id: 9606,
    ...over,
  };
}

test("pickBestStructure: empty list → null", () => {
  assert.equal(pickBestStructure([]), null);
});

test("pickBestStructure: human rows outrank higher-ranked non-human rows", () => {
  const mouse = hit({ pdb_id: "1mus", tax_id: 10090 });
  const human = hit({ pdb_id: "1hum" });
  assert.equal(pickBestStructure([mouse, human])?.pdb_id, "1hum");
});

test("pickBestStructure: a dirty top yields to a comparable clean structure", () => {
  // GPR75: 9xqn is a fusion (SEQRES span ≠ UniProt span); 9xqc is clean.
  const dirty = hit({ pdb_id: "9xqn", end: 160, coverage: 0.685, resolution: 3.91 });
  const clean = hit({ pdb_id: "9xqc", coverage: 0.663, resolution: 3.0 });
  assert.equal(pickBestStructure([dirty, clean])?.pdb_id, "9xqc");
});

test("pickBestStructure: a dirty top stays when no clean structure is comparable", () => {
  const dirty = hit({ pdb_id: "2drt", end: 160, coverage: 0.9 });
  const lowCov = hit({ pdb_id: "2low", coverage: 0.5 });
  assert.equal(pickBestStructure([dirty, lowCov])?.pdb_id, "2drt");
});

/** A fetch stub that answers by URL and records what was asked for. */
function stubFetch(routes: Record<string, () => Response>) {
  const calls: string[] = [];
  const impl = (async (input: unknown) => {
    const url = String(input);
    calls.push(url);
    for (const [prefix, respond] of Object.entries(routes)) {
      if (url.startsWith(prefix)) return respond();
    }
    return new Response("", { status: 404 });
  }) as typeof fetch;
  return { impl, calls };
}

const CIF = `data_TEST
_struct.title 'a test entry'
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
ATOM 1 N N . GLY A 1 1 ? 0 0 0 1 0 ? 5 GLY A N 1
ATOM 2 N N . GLY B 1 1 ? 0 0 0 1 0 ? 7 GLY O2 N 1
#
`;

const entryJson = (atoms: number) => () =>
  Response.json({
    struct: { title: "From the entry API" },
    rcsb_entry_info: { deposited_atom_count: atoms },
  });

test("fetchExperimentalPdb: a .pdb download is used as-is", async () => {
  const pdb = "ATOM      1  N   GLY A   5       0.000   0.000   0.000  1.00  0.00           N  \n";
  const { impl, calls } = stubFetch({
    "https://files.rcsb.org/download/1ABC.pdb": () => new Response(pdb),
  });
  const r = await fetchExperimentalPdb("1ABC", "A", impl);
  assert.equal(r.rawPdb, pdb);
  assert.equal(r.chainId, "A");
  assert.equal(r.chainOnlyAtomCount, null);
  assert.equal(r.source, "pdb");
  assert.deepEqual(calls, ["https://files.rcsb.org/download/1ABC.pdb"]);
});

test("fetchExperimentalPdb: a .pdb 404 falls back to the full mmCIF, chain remapped", async () => {
  const { impl, calls } = stubFetch({
    "https://data.rcsb.org/rest/v1/core/entry/9V8W": entryJson(4039),
    "https://files.rcsb.org/download/9V8W.cif": () => new Response(CIF),
  });
  const r = await fetchExperimentalPdb("9V8W", "O2", impl);
  assert.ok(calls.includes("https://files.rcsb.org/download/9V8W.cif"));
  assert.equal(r.chainOnlyAtomCount, null);
  assert.equal(r.chainId, "B");
  assert.equal(r.source, "cif");
  assert.equal(pickPdbChain(r.rawPdb, r.chainId), "B");
});

test("fetchExperimentalPdb: an oversized mmCIF-only entry loads one chain from ModelServer", async () => {
  const atoms = EXP_FULL_ASSEMBLY_MAX_ATOMS + 1;
  const { impl, calls } = stubFetch({
    "https://data.rcsb.org/rest/v1/core/entry/8J07": entryJson(atoms),
    "https://models.rcsb.org/v1/8J07/atoms?": () => new Response(CIF),
  });
  const r = await fetchExperimentalPdb("8J07", "O2", impl);
  assert.ok(
    calls.includes(
      "https://models.rcsb.org/v1/8J07/atoms?auth_asym_id=O2&model_nums=1&encoding=cif",
    ),
  );
  assert.ok(!calls.some((u) => u.endsWith(".cif")));
  assert.equal(r.chainOnlyAtomCount, atoms);
  assert.equal(r.source, "cif_chain_only");
});

test("fetchExperimentalPdb: no loadable format throws the RCSB status", async () => {
  const { impl } = stubFetch({});
  await assert.rejects(
    fetchExperimentalPdb("0XXX", "A", impl),
    /RCSB returned 404 for 0XXX/,
  );
});

// ---- projectExperimentalChain: UniProt→author numbering ----------------

/** PDB ATOM lines for chain ``ch``, one CA per author residue number. */
function atomLines(ch: string, resis: number[]): string {
  return resis
    .map(
      (r, i) =>
        `ATOM  ${String(i + 1).padStart(5)}  CA  GLY ${ch}${String(r).padStart(4)}` +
        "       0.000   0.000   0.000  1.00  0.00           C  ",
    )
    .join("\n");
}
const range = (lo: number, hi: number) =>
  Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);

const HIT = {
  pdbId: "2JQK",
  uniprotAcc: "Q9UQN3",
  chainId: "B",
  unpStart: 195,
  unpEnd: 213,
  pdbStart: 1,
  approx: false,
};

test("projection: a file numbered by UniProt needs no lookups", async () => {
  const { impl, calls } = stubFetch({});
  const segs = await projectExperimentalChain(
    HIT, atomLines("B", range(195, 213)), "B", impl,
  );
  assert.deepEqual(segs, [{ unpLo: 195, unpHi: 213, offset: 0 }]);
  assert.deepEqual(calls, []);
});

test("projection: SIFTS author numbers rescue a chain numbered by neither UniProt nor SEQRES", async () => {
  // CHMP2B 2jqk chain B: UniProt 195-213, SEQRES 1-19, author 111-129.
  const { impl } = stubFetch({
    "https://www.ebi.ac.uk/pdbe/api/mappings/2jqk": () =>
      Response.json({
        "2jqk": {
          UniProt: {
            Q9UQN3: {
              mappings: [{
                chain_id: "B",
                unp_start: 195,
                unp_end: 213,
                start: { residue_number: 1, author_residue_number: 111 },
                end: { residue_number: 19, author_residue_number: 129 },
              }],
            },
          },
        },
      }),
  });
  const pdb = atomLines("B", range(116, 129));
  const segs = await projectExperimentalChain(HIT, pdb, "B", impl);
  assert.equal(segs[0].offset, -84);
  assert.equal(projectedCoverage(segs, observedResSeq(pdb, "B")), 14);
});

test("projection: DBREF rescues a chain SIFTS has no author numbers for", async () => {
  // KCNMB4 6v22 chain E: UniProt 1-210 numbered from 2001 in the file.
  const hit = { ...HIT, pdbId: "6V22", uniprotAcc: "Q86W47", chainId: "E", unpStart: 1, unpEnd: 210 };
  const { impl } = stubFetch({});
  const pdb =
    "DBREF  6V22 E 2001  2210  UNP    Q86W47   KCMB4_HUMAN      1    210             \n" +
    atomLines("E", range(2007, 2205));
  const segs = await projectExperimentalChain(hit, pdb, "E", impl);
  assert.deepEqual(segs, [{ unpLo: 1, unpHi: 210, offset: 2000 }]);
  assert.equal(projectedCoverage(segs, observedResSeq(pdb, "E")), 199);
});

test("dbrefSegments ignores other chains and other accessions", () => {
  const pdb =
    "DBREF  6V22 E 2001  2210  UNP    Q86W47   KCMB4_HUMAN      1    210             \n" +
    "DBREF  6V22 A    1  1236  UNP    Q12791   KCMA1_HUMAN      1   1236             \n";
  assert.deepEqual(dbrefSegments(pdb, "E", "Q86W47"), [
    { unpLo: 1, unpHi: 210, offset: 2000 },
  ]);
  assert.deepEqual(dbrefSegments(pdb, "E", "Q12791"), []);
  assert.deepEqual(dbrefSegments(pdb, "B", "Q86W47"), []);
});
