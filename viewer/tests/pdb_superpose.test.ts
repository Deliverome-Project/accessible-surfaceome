/*
 * Rigid-body Cα superposition (Kabsch / Horn quaternion method) for the L1
 * review viewer's optional native-structure overlay.
 *
 *   npx --yes tsx --test tests/pdb_superpose.test.ts
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { kabschAlign, superposePdb, type Mat3, type Vec3 } from "../lib/pdb-superpose";
import { l1ResidueSegments, type L1Site } from "../lib/l1-design";

function det3(m: Mat3): number {
  return (
    m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) -
    m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
    m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
  );
}

function applyMat(m: Mat3, v: Vec3, t: Vec3 = [0, 0, 0]): Vec3 {
  return [
    m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2] + t[0],
    m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2] + t[1],
    m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2] + t[2],
  ];
}

function axisAngleMat(axis: Vec3, angleRad: number): Mat3 {
  const n = Math.hypot(axis[0], axis[1], axis[2]);
  const [x, y, z] = [axis[0] / n, axis[1] / n, axis[2] / n];
  const c = Math.cos(angleRad);
  const s = Math.sin(angleRad);
  const k = 1 - c;
  return [
    [c + x * x * k, x * y * k - z * s, x * z * k + y * s],
    [y * x * k + z * s, c + y * y * k, y * z * k - x * s],
    [z * x * k - y * s, z * y * k + x * s, c + z * z * k],
  ];
}

function pdbLine(serial: number, atom: string, resi: number, [x, y, z]: Vec3, bfactor = 90, record = "ATOM"): string {
  return (
    `${record.padEnd(6)}${String(serial).padStart(5)}  ${atom.padEnd(3)} ALA A${String(resi).padStart(4)}    ` +
    `${x.toFixed(3).padStart(8)}${y.toFixed(3).padStart(8)}${z.toFixed(3).padStart(8)}  1.00${bfactor.toFixed(2).padStart(6)}           C`
  );
}

function parseCaCoords(pdbText: string): Map<number, Vec3> {
  const out = new Map<number, Vec3>();
  for (const line of pdbText.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") || line.slice(12, 16).trim() !== "CA") continue;
    const resi = Number.parseInt(line.slice(22, 26).trim(), 10);
    out.set(resi, [
      Number.parseFloat(line.slice(30, 38)),
      Number.parseFloat(line.slice(38, 46)),
      Number.parseFloat(line.slice(46, 54)),
    ]);
  }
  return out;
}

const HELIX_PTS: Vec3[] = Array.from({ length: 16 }, (_, i) => [
  3.5 * Math.cos(i * 1.1) + 0.2 * i,
  1.5 * i,
  3.5 * Math.sin(i * 1.1) - 0.1 * i,
]);

test("kabschAlign recovers identity, pure translation, arbitrary 3D rotation, and 180-degree rotation", () => {
  const cases: { name: string; R: Mat3; t: Vec3 }[] = [
    { name: "identity + translation", R: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], t: [12.5, -7.25, 33.1] },
    { name: "arbitrary 3D rotation", R: axisAngleMat([1, -2, 3], 1.234), t: [-4.5, 19.2, 8.7] },
    { name: "180-degree rotation", R: axisAngleMat([0, 1, 1], Math.PI), t: [5.0, 2.0, -9.0] },
  ];
  for (const c of cases) {
    const target = HELIX_PTS.map((p) => applyMat(c.R, p, c.t));
    const tf = kabschAlign(HELIX_PTS, target);
    assert.ok(tf, c.name);
    assert.ok(tf.rmsd < 1e-6, `${c.name}: rmsd=${tf.rmsd}`);
    assert.ok(Math.abs(det3(tf.rotation) - 1) < 1e-6, `${c.name}: det(R)=${det3(tf.rotation)}`);
  }
});

test("kabschAlign never produces an improper reflection on a mirrored point cloud", () => {
  const chiral: Vec3[] = [
    [0, 0, 0],
    [4, 0, 0],
    [0, 5, 0],
    [0, 0, 6],
    [2, 3, 1],
  ];
  const mirrored: Vec3[] = chiral.map(([x, y, z]) => [-x, y, z]);
  const tf = kabschAlign(chiral, mirrored);
  assert.ok(tf);
  assert.ok(Math.abs(det3(tf.rotation) - 1) < 1e-6, "must remain proper rotation SO(3)");
  assert.ok(tf.rmsd > 0.5, "chiral reflection cannot achieve zero proper-rotation RMSD");
});

test("superposePdb aligns across an internal cassette insertion and native residue offset", () => {
  // Member length 16; insert 51-aa cassette after residue 8; native has residue_offset = 2.
  const memberLen = 16;
  const cassetteLen = 51;
  const R = axisAngleMat([2, 1, -1], 0.95);
  const T: Vec3 = [14.2, -6.8, 21.4];

  const nativeLines: string[] = [];
  for (let r = 1; r <= memberLen; r += 1) {
    nativeLines.push(pdbLine(r, "CA", r + 2, HELIX_PTS[r - 1], 92));
  }
  // Extra HETATM atom should be rigidly transformed alongside ATOM records.
  nativeLines.push(pdbLine(99, "ZN", 500, [1, 2, 3], 90, "HETATM"));

  const taggedLines: string[] = [];
  let serial = 1;
  for (let r = 1; r <= 8; r += 1) {
    taggedLines.push(pdbLine(serial++, "CA", r, applyMat(R, HELIX_PTS[r - 1], T), 90));
  }
  // 51-aa cassette placed far away — must NOT pollute the native Cα pairing.
  for (let c = 1; c <= cassetteLen; c += 1) {
    taggedLines.push(pdbLine(serial++, "CA", 8 + c, [150 + c, 150, 150], 60));
  }
  for (let r = 9; r <= memberLen; r += 1) {
    taggedLines.push(pdbLine(serial++, "CA", r + cassetteLen, applyMat(R, HELIX_PTS[r - 1], T), 90));
  }

  const site = {
    site_id: "l1-p1249-a4",
    insert_after_residue: 8,
    leader: null,
    is_primary: true,
    status: "built",
  } as L1Site;
  const member = { ordered_length_aa: memberLen, sites: [site] };
  const nativeSegs = l1ResidueSegments(member, {
    kind: "native",
    site_id: null,
    residue_offset: 2,
    cassette_first_model_residue: null,
    cassette_last_model_residue: null,
    model_length_aa: memberLen + 2,
  })!;
  const taggedSegs = l1ResidueSegments(member, {
    kind: "tagged",
    site_id: "l1-p1249-a4",
    residue_offset: 0,
    cassette_first_model_residue: 9,
    cassette_last_model_residue: 8 + cassetteLen,
    model_length_aa: memberLen + cassetteLen,
  })!;

  const res = superposePdb(nativeLines.join("\n"), taggedLines.join("\n"), nativeSegs, taggedSegs);
  assert.ok(res);
  assert.equal(res.alignedCount, memberLen);
  assert.equal(res.totalMatchedCount, memberLen);
  assert.equal(res.confidentOnly, true);
  assert.ok(res.rmsd < 0.01, `expected near-zero RMSD, got ${res.rmsd}`);

  const alignedCa = parseCaCoords(res.pdbText);
  const expectedFirst = applyMat(R, HELIX_PTS[0], T);
  const gotFirst = alignedCa.get(3)!; // member res 1 = native res 3
  assert.ok(
    Math.hypot(gotFirst[0] - expectedFirst[0], gotFirst[1] - expectedFirst[1], gotFirst[2] - expectedFirst[2]) < 0.01,
  );
});

test("superposePdb prefers confident (pLDDT >= 70) core residues over floppy disordered tails", () => {
  const R = axisAngleMat([0, 0, 1], 0.7);
  const T: Vec3 = [5, -3, 2];
  // 12 confident core residues (pLDDT 92) + 4 disordered tail residues (pLDDT 38) displaced by 30 Å in target.
  const nativeLines: string[] = [];
  const taggedLines: string[] = [];
  for (let i = 0; i < 16; i += 1) {
    const isCore = i < 12;
    nativeLines.push(pdbLine(i + 1, "CA", i + 1, HELIX_PTS[i], isCore ? 92 : 38));
    const moved = applyMat(R, HELIX_PTS[i], T);
    const targetCoord: Vec3 = isCore ? moved : [moved[0] + 30, moved[1] - 25, moved[2] + 18];
    taggedLines.push(pdbLine(i + 1, "CA", i + 1, targetCoord, isCore ? 92 : 38));
  }
  const segs = [{ unpLo: 1, unpHi: 16, offset: 0 }];
  const res = superposePdb(nativeLines.join("\n"), taggedLines.join("\n"), segs, segs);
  assert.ok(res);
  assert.equal(res.confidentOnly, true);
  assert.equal(res.alignedCount, 12);
  assert.equal(res.totalMatchedCount, 16);
  assert.ok(res.rmsd < 0.01, `core RMSD should not be dragged by disordered tail, got ${res.rmsd}`);
});

test("superposePdb returns null when fewer than 3 Cα residues match", () => {
  const pdb = [pdbLine(1, "CA", 1, [0, 0, 0]), pdbLine(2, "CA", 2, [3, 0, 0])].join("\n");
  const segs = [{ unpLo: 1, unpHi: 2, offset: 0 }];
  assert.equal(superposePdb(pdb, pdb, segs, segs), null);
});
