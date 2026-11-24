/*
 * Rigid-body Cα superposition (Kabsch / Horn quaternion method) for overlaying
 * a member's native model onto its oriented tagged refold in 3Dmol.js.
 *
 * Paired strictly through each model's member-residue segments (`l1ResidueSegments`),
 * so inserted tag cassettes, Igκ leader remnants, snorkel modules, and outside
 * residues are excluded automatically. When native AlphaFold pLDDT B-factors are
 * present, the fit prefers confident residues (pLDDT >= 70) so disordered tails
 * do not tilt the structured core.
 *
 * Browser-safe (zero external / node dependencies).
 */
import { modelToMember, type TaggedModelLayout } from "./l1-design";

export type Vec3 = [number, number, number];
export type Mat3 = [Vec3, Vec3, Vec3];

export interface RigidTransform {
  rotation: Mat3;
  mobileCentroid: Vec3;
  targetCentroid: Vec3;
  rmsd: number;
}

export interface SuperposeResult {
  pdbText: string;
  /** Cα RMSD (Å) over the aligned residues used to compute the rigid transform. */
  rmsd: number;
  /** Number of Cα pairs used in the rigid-body fit. */
  alignedCount: number;
  /** Total matched native Cα pairs between mobile and target models. */
  totalMatchedCount: number;
  /** True when the fit was restricted to confident (pLDDT >= 70) native residues. */
  confidentOnly: boolean;
}

interface ParsedCa {
  coord: Vec3;
  bfactor: number;
}

function parseCaByResidue(pdbText: string): Map<number, ParsedCa> {
  const lines = String(pdbText || "").split(/\r?\n/);
  const map = new Map<number, ParsedCa>();
  let primaryChain: string | null = null;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.startsWith("ATOM")) continue;
    if (line.length < 54) continue;
    const atomName = line.slice(12, 16).trim();
    if (atomName !== "CA") continue;
    const chain = line.slice(21, 22);
    if (primaryChain == null) primaryChain = chain;
    else if (chain !== primaryChain) continue;
    const resi = Number.parseInt(line.slice(22, 26).trim(), 10);
    if (!Number.isInteger(resi) || map.has(resi)) continue;
    const x = Number.parseFloat(line.slice(30, 38));
    const y = Number.parseFloat(line.slice(38, 46));
    const z = Number.parseFloat(line.slice(46, 54));
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    const rawB = line.length >= 66 ? Number.parseFloat(line.slice(60, 66)) : Number.NaN;
    map.set(resi, { coord: [x, y, z], bfactor: Number.isFinite(rawB) ? rawB : 0 });
  }
  return map;
}

function centroid(points: readonly Vec3[]): Vec3 {
  let sx = 0;
  let sy = 0;
  let sz = 0;
  for (let i = 0; i < points.length; i += 1) {
    sx += points[i][0];
    sy += points[i][1];
    sz += points[i][2];
  }
  const inv = 1 / points.length;
  return [sx * inv, sy * inv, sz * inv];
}

function mat3VecMul(m: Mat3, v: Vec3): Vec3 {
  return [
    m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
    m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
    m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
  ];
}

/**
 * Largest eigenvector of a real symmetric 4×4 matrix via cyclic Jacobi rotations.
 * Unconditionally convergent for all symmetric 4×4 matrices (including repeated
 * eigenvalues, 180° rotations, and degenerate/planar point clouds).
 */
function largestEigenvector4(sym: number[][]): [number, number, number, number] {
  const a = sym.map((row) => [...row]);
  const v = [
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
  ];
  const maxSweeps = 50;
  for (let sweep = 0; sweep < maxSweeps; sweep += 1) {
    let maxOff = 0;
    for (let p = 0; p < 4; p += 1) {
      for (let q = p + 1; q < 4; q += 1) {
        const apq = a[p][q];
        const absApq = Math.abs(apq);
        if (absApq > maxOff) maxOff = absApq;
        if (absApq < 1e-15) continue;
        const app = a[p][p];
        const aqq = a[q][q];
        const tau = (aqq - app) / (2 * apq);
        const t = tau >= 0
          ? 1 / (tau + Math.sqrt(1 + tau * tau))
          : -1 / (-tau + Math.sqrt(1 + tau * tau));
        const c = 1 / Math.sqrt(1 + t * t);
        const s = t * c;
        const h = t * apq;
        a[p][p] = app - h;
        a[q][q] = aqq + h;
        a[p][q] = 0;
        a[q][p] = 0;
        for (let r = 0; r < 4; r += 1) {
          if (r !== p && r !== q) {
            const arp = a[r][p];
            const arq = a[r][q];
            a[r][p] = c * arp - s * arq;
            a[p][r] = a[r][p];
            a[r][q] = s * arp + c * arq;
            a[q][r] = a[r][q];
          }
          const vrp = v[r][p];
          const vrq = v[r][q];
          v[r][p] = c * vrp - s * vrq;
          v[r][q] = s * vrp + c * vrq;
        }
      }
    }
    if (maxOff < 1e-13) break;
  }
  let best = 0;
  for (let i = 1; i < 4; i += 1) {
    if (a[i][i] > a[best][best]) best = i;
  }
  const q: [number, number, number, number] = [v[0][best], v[1][best], v[2][best], v[3][best]];
  const norm = Math.hypot(q[0], q[1], q[2], q[3]);
  if (norm <= 1e-15) return [1, 0, 0, 0];
  return [q[0] / norm, q[1] / norm, q[2] / norm, q[3] / norm];
}

function quaternionToMat3([w, x, y, z]: [number, number, number, number]): Mat3 {
  const xx = x * x;
  const yy = y * y;
  const zz = z * z;
  const xy = x * y;
  const xz = x * z;
  const yz = y * z;
  const wx = w * x;
  const wy = w * y;
  const wz = w * z;
  return [
    [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)],
    [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)],
    [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)],
  ];
}

/**
 * Compute the optimal proper rigid transformation (R ∈ SO(3), det(R) = +1) mapping
 * `mobile` onto `target` via Horn's closed-form unit-quaternion method (1987).
 * Returns null if fewer than 3 paired points are provided.
 */
export function kabschAlign(mobile: readonly Vec3[], target: readonly Vec3[]): RigidTransform | null {
  const n = mobile.length;
  if (n < 3 || n !== target.length) return null;
  const cP = centroid(mobile);
  const cQ = centroid(target);

  // Cross-covariance S = Σ (p_i - cP)(q_i - cQ)^T
  let sxx = 0, sxy = 0, sxz = 0;
  let syx = 0, syy = 0, syz = 0;
  let szx = 0, szy = 0, szz = 0;
  for (let i = 0; i < n; i += 1) {
    const px = mobile[i][0] - cP[0];
    const py = mobile[i][1] - cP[1];
    const pz = mobile[i][2] - cP[2];
    const qx = target[i][0] - cQ[0];
    const qy = target[i][1] - cQ[1];
    const qz = target[i][2] - cQ[2];
    sxx += px * qx; sxy += px * qy; sxz += px * qz;
    syx += py * qx; syy += py * qy; syz += py * qz;
    szx += pz * qx; szy += pz * qy; szz += pz * qz;
  }

  // Horn's 4×4 symmetric Davenport-K matrix N whose principal eigenvector is the
  // unit quaternion maximizing Σ q_i^T R(q) p_i over proper rotations R ∈ SO(3).
  const N = [
    [sxx + syy + szz, syz - szy, szx - sxz, sxy - syx],
    [syz - szy, sxx - syy - szz, sxy + syx, sxz + szx],
    [szx - sxz, sxy + syx, -sxx + syy - szz, syz + szy],
    [sxy - syx, sxz + szx, syz + szy, -sxx - syy + szz],
  ];
  const quat = largestEigenvector4(N);
  const rotation = quaternionToMat3(quat);

  let sumSq = 0;
  for (let i = 0; i < n; i += 1) {
    const p: Vec3 = [mobile[i][0] - cP[0], mobile[i][1] - cP[1], mobile[i][2] - cP[2]];
    const rp = mat3VecMul(rotation, p);
    const dx = rp[0] + cQ[0] - target[i][0];
    const dy = rp[1] + cQ[1] - target[i][1];
    const dz = rp[2] + cQ[2] - target[i][2];
    sumSq += dx * dx + dy * dy + dz * dz;
  }
  return {
    rotation,
    mobileCentroid: cP,
    targetCentroid: cQ,
    rmsd: Math.sqrt(sumSq / n),
  };
}

function formatPdbCoord(value: number): string {
  const n = Number.isFinite(value) ? value : 0;
  return n.toFixed(3).padStart(8, " ");
}

function transformPdbCoords(pdbText: string, tf: RigidTransform): string {
  const lines = String(pdbText || "").split(/\r?\n/);
  const { rotation: R, mobileCentroid: cP, targetCentroid: cQ } = tf;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!(line.startsWith("ATOM") || line.startsWith("HETATM"))) continue;
    if (line.length < 54) continue;
    const x = Number.parseFloat(line.slice(30, 38));
    const y = Number.parseFloat(line.slice(38, 46));
    const z = Number.parseFloat(line.slice(46, 54));
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    const rp = mat3VecMul(R, [x - cP[0], y - cP[1], z - cP[2]]);
    const nx = formatPdbCoord(rp[0] + cQ[0]);
    const ny = formatPdbCoord(rp[1] + cQ[1]);
    const nz = formatPdbCoord(rp[2] + cQ[2]);
    lines[i] = `${line.slice(0, 30)}${nx}${ny}${nz}${line.slice(54)}`;
  }
  return lines.join("\n");
}

const MIN_CONFIDENT_PAIRS = 10;

/**
 * Superpose `mobilePdbText` (e.g. a member's native structure) onto `targetPdbText`
 * (e.g. the member's oriented tagged refold) using matched member Cα residues.
 *
 * Prefers confident mobile residues (pLDDT >= 70, or >= 0.70 when stored on a 0–1
 * scale) when at least 10 confident pairs are present; otherwise uses all matched
 * Cα pairs. Returns null when fewer than 3 Cα residues can be paired.
 */
export function superposePdb(
  mobilePdbText: string,
  targetPdbText: string,
  mobileSegments: TaggedModelLayout["segments"],
  targetSegments: TaggedModelLayout["segments"],
): SuperposeResult | null {
  const mobileCa = parseCaByResidue(mobilePdbText);
  const targetCa = parseCaByResidue(targetPdbText);
  if (mobileCa.size < 3 || targetCa.size < 3) return null;

  const targetByMember = new Map<number, Vec3>();
  for (const [resi, entry] of targetCa) {
    const mem = modelToMember(resi, targetSegments);
    if (mem != null && !targetByMember.has(mem)) targetByMember.set(mem, entry.coord);
  }

  const pairs: { mobile: Vec3; target: Vec3; mobileB: number }[] = [];
  let maxB = 0;
  for (const [resi, entry] of mobileCa) {
    const mem = modelToMember(resi, mobileSegments);
    if (mem == null) continue;
    const tCoord = targetByMember.get(mem);
    if (!tCoord) continue;
    if (entry.bfactor > maxB) maxB = entry.bfactor;
    pairs.push({ mobile: entry.coord, target: tCoord, mobileB: entry.bfactor });
  }
  if (pairs.length < 3) return null;

  const bThreshold = maxB > 0 ? (maxB <= 1.05 ? 0.7 : 70) : Number.POSITIVE_INFINITY;
  const confident = pairs.filter((p) => p.mobileB >= bThreshold);
  const confidentOnly = confident.length >= MIN_CONFIDENT_PAIRS;
  const chosen = confidentOnly ? confident : pairs;

  const tf = kabschAlign(
    chosen.map((p) => p.mobile),
    chosen.map((p) => p.target),
  );
  if (!tf) return null;

  return {
    pdbText: transformPdbCoords(mobilePdbText, tf),
    rmsd: tf.rmsd,
    alignedCount: chosen.length,
    totalMatchedCount: pairs.length,
    confidentOnly,
  };
}
