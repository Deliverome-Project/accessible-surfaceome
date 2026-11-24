/*
 * Membrane + side shading on L1 models: the model -> member map, the projected state
 * runs, the cassette's side, the sequence-matched topology, and the short-tail fallback
 * in the orientation.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs tests/l1_membrane_shading.test.ts
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  l1MemberTopology,
  l1ModelMap,
  l1ModelStateRuns,
  l1ModelToMember,
  type L1Site,
} from "../lib/l1-design";
import { orientPdbForTopology, superposePdbOntoTarget } from "../lib/structure-orientation";

const site = (over: Partial<L1Site>): L1Site =>
  ({ site_id: "s1", insert_after_residue: 10, leader: null, is_primary: true, status: "built", ...over }) as L1Site;
const model = (over: Record<string, unknown>) =>
  ({ kind: "native", site_id: null, residue_offset: 0, cassette_first_model_residue: null,
    cassette_last_model_residue: null, model_length_aa: null, ...over }) as Parameters<typeof l1ModelMap>[1];

// 20-residue type I member: 5 O, 10 M... keep it simple: OOOOO MMMMMMMMMM IIIII
const TOPO = "OOOOOMMMMMMMMMMIIIII";

test("native model: one shift, runs land in model numbering", () => {
  const map = l1ModelMap({ ordered_length_aa: 20, sites: [] }, model({ residue_offset: 3 }), TOPO)!;
  assert.deepEqual(map.segments, [{ unpLo: 1, unpHi: 20, offset: 3 }]);
  assert.deepEqual(l1ModelStateRuns(TOPO, map), [
    { state: "O", lo: 4, hi: 8 }, { state: "M", lo: 9, hi: 18 }, { state: "I", lo: 19, hi: 23 },
  ]);
  assert.equal(l1ModelToMember(map)(4), 1);
  assert.equal(l1ModelToMember(map)(2), null);
});

test("internal tag: topology splits around the cassette and the cassette takes the insert side", () => {
  // insert after residue 3 (extracellular); 51-aa cassette at model 4..54; tail 55..71
  const m = { ordered_length_aa: 20, sites: [site({ insert_after_residue: 3 })] };
  const map = l1ModelMap(m, model({ kind: "tagged", site_id: "s1", cassette_first_model_residue: 4,
    cassette_last_model_residue: 54, model_length_aa: 71 }), TOPO)!;
  assert.deepEqual(map.cassette, [4, 54]);
  assert.equal(map.cassetteSide, "O");
  const runs = l1ModelStateRuns(TOPO, map);
  assert.deepEqual(runs[0], { state: "O", lo: 1, hi: 3 });
  assert.deepEqual(runs[1], { state: "O", lo: 55, hi: 56 });
  assert.ok(runs.every((r) => r.hi < 4 || r.lo > 54), "nothing painted over the cassette");
});

test("C-terminal tag sits on the side of the last residue", () => {
  const m = { ordered_length_aa: 20, sites: [site({ insert_after_residue: 20 })] };
  const map = l1ModelMap(m, model({ kind: "tagged", site_id: "s1", cassette_first_model_residue: 21,
    cassette_last_model_residue: 71, model_length_aa: 71 }), TOPO)!;
  assert.equal(map.cassetteSide, "I");
});

test("a map that cannot describe the construct draws no shading", () => {
  assert.equal(l1ModelMap({ ordered_length_aa: 21, sites: [] }, model({}), TOPO), null);
  assert.equal(l1ModelMap({ ordered_length_aa: 20, sites: [] }, model({ kind: "tagged", site_id: "nope" }), TOPO), null);
});

test("topology is matched by sequence, not only design id", () => {
  const row = { candidate_id: "l1-p1", per_residue_topology: TOPO, ordered_length_aa: "20", sequence_sha256: "aaa", tool: "deeptmhmm_v1" };
  assert.ok(l1MemberTopology([row], { design_id: "l1-p1", ordered_length_aa: 20, sequence_sha256: "aaa" }));
  assert.equal(l1MemberTopology([row], { design_id: "l1-p1", ordered_length_aa: 20, sequence_sha256: "bbb" }), null);
  assert.equal(l1MemberTopology([{ ...row, tool: "deeptmhmm_v2" }], { design_id: "l1-p1", ordered_length_aa: 20 }), null);
});

function helixPdb(): string {
  // O residues at y = +20.., M along y from +12 to -12, I (two residues) at y = -16.
  const lines: string[] = [];
  const add = (resi: number, y: number, x = 0) =>
    lines.push(`ATOM  ${String(resi).padStart(5)}  CA  ALA A${String(resi).padStart(4)}    ${x.toFixed(3).padStart(8)}${y.toFixed(3).padStart(8)}${(0).toFixed(3).padStart(8)}  1.00 90.00           C`);
  let r = 1;
  for (let i = 0; i < 8; i += 1) add(r++, 20 + i, i);
  for (let i = 0; i < 16; i += 1) add(r++, 12 - i * 1.6);
  for (let i = 0; i < 2; i += 1) add(r++, -16 - i, i);
  return lines.join("\n");
}

test("short cytoplasmic tail: default orientation gives no membrane, the retry at 1 does", () => {
  const topo = "O".repeat(8) + "M".repeat(16) + "I".repeat(2);
  assert.equal(orientPdbForTopology(helixPdb(), topo).membrane, null);
  const res = orientPdbForTopology(helixPdb(), topo, { minSideResidues: 1 });
  assert.ok(res.membrane, "membrane placed");
});

test("a refold of an earlier pick maps from its own cassette position and says so", () => {
  const m = { ordered_length_aa: 20, sites: [site({ site_id: "current", insert_after_residue: 2 })] };
  const map = l1ModelMap(m, model({ kind: "tagged", site_id: "older", cassette_first_model_residue: 4,
    cassette_last_model_residue: 54, model_length_aa: 71 }), TOPO)!;
  assert.equal(map.unlistedSiteInsertAfter, 3);
  assert.equal(map.cassetteSide, "O");
  // numbers that do not add up to the member (room for a leader) are refused, not guessed
  assert.equal(l1ModelMap(m, model({ kind: "tagged", site_id: "older", cassette_first_model_residue: 6,
    cassette_last_model_residue: 56, model_length_aa: 73 }), TOPO), null);
});

test("superposePdbOntoTarget recovers an exact 3D rotation + translation with near-zero RMSD", () => {
  const mkPdb = (coords: [number, number, number][], startResi = 1) =>
    coords
      .map(
        ([x, y, z], i) =>
          `ATOM  ${String(i + 1).padStart(5)}  CA  ALA A${String(startResi + i).padStart(4)}    ${x.toFixed(3).padStart(8)}${y.toFixed(3).padStart(8)}${z.toFixed(3).padStart(8)}  1.00 90.00           C`,
      )
      .join("\n");
  const targetCoords: [number, number, number][] = [
    [0, 0, 0],
    [3.8, 0.2, 0.5],
    [7.1, 2.4, -1.2],
    [6.5, 6.0, 0.9],
    [2.9, 7.2, 3.4],
    [-0.5, 5.1, 4.8],
  ];
  // Apply an arbitrary proper 3D rotation (90° around Z then 45° around X) + translation to create the mobile PDB
  const s = Math.SQRT1_2;
  const mobileCoords: [number, number, number][] = targetCoords.map(([x, y, z]) => {
    const x1 = -y, y1 = x, z1 = z;
    return [x1 + 14.2, s * y1 - s * z1 - 8.7, s * y1 + s * z1 + 22.5];
  });
  const targetPdb = mkPdb(targetCoords, 10);
  const mobilePdb = mkPdb(mobileCoords, 1);
  const pairs: [number, number][] = targetCoords.map((_, i) => [1 + i, 10 + i]);
  const res = superposePdbOntoTarget(mobilePdb, targetPdb, pairs);
  assert.ok(res, "superposition succeeds");
  assert.equal(res.nAligned, 6);
  assert.ok(res.rmsd < 1e-3, `expected near-zero RMSD, got ${res.rmsd}`);
  // Verify aligned coordinates match target PDB coordinates
  const lines = res.pdbText.split("\n");
  for (let i = 0; i < targetCoords.length; i += 1) {
    const x = parseFloat(lines[i].slice(30, 38));
    const y = parseFloat(lines[i].slice(38, 46));
    const z = parseFloat(lines[i].slice(46, 54));
    assert.ok(Math.hypot(x - targetCoords[i][0], y - targetCoords[i][1], z - targetCoords[i][2]) < 1e-2);
  }
});
