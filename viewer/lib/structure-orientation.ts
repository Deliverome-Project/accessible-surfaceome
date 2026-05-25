/*
 * Membrane-orientation math for the structure viewer.
 * ------------------------------------------------------------
 * Rotates an AlphaFold PDB so the membrane plane is horizontal,
 * extracellular side up, TM region centered at the origin. Ported
 * verbatim from the deliverome-internal structure-site viewer
 * (cloudflare/surfaceome_structure_site_viewer/deploy_static/
 * index.html, ~lines 3594–3863).
 *
 * Approach: from the per-residue DeepTMHMM topology + CA atom
 * coordinates, compute the centroid of each topology class (M / O /
 * I), then build a rotation matrix that maps the I→O axis onto the
 * +Y axis. Translate so the TM-helix mean Y is zero. Flip Y/Z if
 * needed to put `O` on top. Re-center XZ so the molecule's bounding
 * box is centered horizontally.
 *
 * Browser-safe (no node imports) so the client-side 3Dmol viewer
 * can call it directly.
 */

type Vec3 = [number, number, number];
type Mat3 = [Vec3, Vec3, Vec3];

function vectorAdd(a: Vec3, b: Vec3): Vec3 {
  return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

function vectorSub(a: Vec3, b: Vec3): Vec3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function vectorScale(a: Vec3, s: number): Vec3 {
  return [a[0] * s, a[1] * s, a[2] * s];
}

function vectorDot(a: Vec3, b: Vec3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function vectorCross(a: Vec3, b: Vec3): Vec3 {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function vectorNorm(a: Vec3): number {
  return Math.hypot(a[0], a[1], a[2]);
}

function vectorNormalize(a: Vec3): Vec3 | null {
  const n = vectorNorm(a);
  if (n <= 1e-12) return null;
  return [a[0] / n, a[1] / n, a[2] / n];
}

function centroid(points: Vec3[]): Vec3 | null {
  if (!points.length) return null;
  let acc: Vec3 = [0, 0, 0];
  for (const p of points) acc = vectorAdd(acc, p);
  return vectorScale(acc, 1 / points.length);
}

function matrixVecMul(m: Mat3, v: Vec3): Vec3 {
  return [
    m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
    m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
    m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
  ];
}

function identityMatrix3(): Mat3 {
  return [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1],
  ];
}

function matMul3(a: Mat3, b: Mat3): Mat3 {
  const out: Mat3 = [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0],
  ];
  for (let i = 0; i < 3; i += 1) {
    for (let j = 0; j < 3; j += 1) {
      out[i][j] = a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j];
    }
  }
  return out;
}

/** Rotation matrix sending unit-length `from` onto unit-length `to`. */
function rotationMatrixFromTo(fromVec: Vec3, toVec: Vec3): Mat3 {
  const a = vectorNormalize(fromVec);
  const b = vectorNormalize(toVec);
  if (!a || !b) return identityMatrix3();
  const v = vectorCross(a, b);
  const s = vectorNorm(v);
  const c = vectorDot(a, b);
  if (s <= 1e-8) {
    if (c > 0) return identityMatrix3();
    // 180° rotation around an axis orthogonal to `a`.
    let axis: Vec3 = vectorCross(a, [1, 0, 0]);
    if (vectorNorm(axis) <= 1e-8) {
      axis = vectorCross(a, [0, 0, 1]);
    }
    const u = vectorNormalize(axis);
    if (!u) return identityMatrix3();
    return [
      [2 * u[0] * u[0] - 1, 2 * u[0] * u[1], 2 * u[0] * u[2]],
      [2 * u[1] * u[0], 2 * u[1] * u[1] - 1, 2 * u[1] * u[2]],
      [2 * u[2] * u[0], 2 * u[2] * u[1], 2 * u[2] * u[2] - 1],
    ];
  }
  const vx: Mat3 = [
    [0, -v[2], v[1]],
    [v[2], 0, -v[0]],
    [-v[1], v[0], 0],
  ];
  const vx2 = matMul3(vx, vx);
  const scale = (1 - c) / (s * s);
  const id = identityMatrix3();
  const out: Mat3 = [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0],
  ];
  for (let i = 0; i < 3; i += 1) {
    for (let j = 0; j < 3; j += 1) {
      out[i][j] = id[i][j] + vx[i][j] + vx2[i][j] * scale;
    }
  }
  return out;
}

interface ParsedPdbAtom {
  lineIndex: number;
  x: number;
  y: number;
  z: number;
  resi: number;
  atomName: string;
  tx?: number;
  ty?: number;
  tz?: number;
}

interface ParsedPdb {
  lines: string[];
  atoms: ParsedPdbAtom[];
  caByResidue: Map<number, Vec3>;
}

function parsePdbForOrientation(pdbText: string): ParsedPdb {
  const lines = String(pdbText || "").split(/\r?\n/);
  const atoms: ParsedPdbAtom[] = [];
  const caByResidue = new Map<number, Vec3>();
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!(line.startsWith("ATOM") || line.startsWith("HETATM"))) continue;
    if (line.length < 54) continue;
    const x = Number.parseFloat(line.slice(30, 38));
    const y = Number.parseFloat(line.slice(38, 46));
    const z = Number.parseFloat(line.slice(46, 54));
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    const atomName = line.slice(12, 16).trim();
    const resi = Number.parseInt(line.slice(22, 26).trim(), 10);
    const atom: ParsedPdbAtom = {
      lineIndex: i,
      x,
      y,
      z,
      resi: Number.isInteger(resi) ? resi : 0,
      atomName,
    };
    atoms.push(atom);
    if (atomName === "CA" && atom.resi > 0 && !caByResidue.has(atom.resi)) {
      caByResidue.set(atom.resi, [x, y, z]);
    }
  }
  return { lines, atoms, caByResidue };
}

function collectStateCoords(
  topology: string,
  caByResidue: Map<number, Vec3>,
): { M: Vec3[]; O: Vec3[]; I: Vec3[] } {
  const states: { M: Vec3[]; O: Vec3[]; I: Vec3[] } = { M: [], O: [], I: [] };
  if (!topology) return states;
  for (const [resi, coord] of caByResidue) {
    if (resi < 1 || resi > topology.length) continue;
    const state = topology.charAt(resi - 1);
    if (state === "M" || state === "O" || state === "I") {
      states[state].push(coord);
    }
  }
  return states;
}

interface OrientationTransform {
  membraneCenter: Vec3;
  rotateToY: Mat3;
  flipY: boolean;
  meanMY: number;
}

/**
 * Membrane-slab bounds in the *oriented* coordinate frame (Y is the
 * membrane normal, Y=0 sits at the TM-helix mean). `yMin` / `yMax`
 * come from the M-state CA-atom Y range; `xExtent` / `zExtent` are
 * half-widths that comfortably enclose the protein's XZ footprint
 * so the rendered slab reads as a continuous bilayer rather than a
 * small patch.
 */
export interface MembraneSlab {
  yMin: number;
  yMax: number;
  xExtent: number;
  zExtent: number;
}

export interface OrientationResult {
  pdbText: string;
  membrane: MembraneSlab | null;
}

function computeOrientationTransform(
  topology: string,
  parsed: ParsedPdb,
): OrientationTransform | null {
  if (!topology || parsed.atoms.length === 0 || parsed.caByResidue.size === 0) {
    return null;
  }
  const states = collectStateCoords(topology, parsed.caByResidue);
  // Need a minimum count per class so centroids are statistically
  // meaningful; matches the deliverome-internal threshold.
  if (states.M.length < 6 || states.O.length < 6 || states.I.length < 6) {
    return null;
  }
  const membraneCenter = centroid(states.M);
  const oCenter = centroid(states.O);
  const iCenter = centroid(states.I);
  if (!membraneCenter || !oCenter || !iCenter) return null;
  const oiAxis = vectorSub(oCenter, iCenter);
  if (vectorNorm(oiAxis) <= 1e-8) return null;
  const rotateToY = rotationMatrixFromTo(oiAxis, [0, 1, 0]);
  const transformPoint = (point: Vec3) =>
    matrixVecMul(rotateToY, vectorSub(point, membraneCenter));

  const transformedO = states.O.map(transformPoint);
  const transformedI = states.I.map(transformPoint);
  const meanOY = transformedO.reduce((acc, p) => acc + p[1], 0) / transformedO.length;
  const meanIY = transformedI.reduce((acc, p) => acc + p[1], 0) / transformedI.length;
  const flipY = meanOY < meanIY;

  const transformedM = states.M.map(transformPoint);
  const meanMY = transformedM.reduce((acc, p) => acc + p[1], 0) / transformedM.length;
  return { membraneCenter, rotateToY, flipY, meanMY };
}

function formatPdbCoord(value: number): string {
  const n = Number.isFinite(value) ? value : 0;
  return n.toFixed(3).padStart(8, " ");
}

function applyOrientationTransform(
  pdbText: string,
  topology: string,
  transform: OrientationTransform | null,
): { pdbText: string; membrane: MembraneSlab | null } {
  if (!transform) return { pdbText, membrane: null };
  const parsed = parsePdbForOrientation(pdbText);
  if (parsed.atoms.length === 0) return { pdbText, membrane: null };

  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let minZ = Number.POSITIVE_INFINITY;
  let maxZ = Number.NEGATIVE_INFINITY;
  // Track M-state CA Y bounds in the oriented frame for the
  // membrane-slab thickness. We collect during the same pass that
  // already touches every atom, so this is O(atoms) total.
  let mMinY = Number.POSITIVE_INFINITY;
  let mMaxY = Number.NEGATIVE_INFINITY;
  for (const atom of parsed.atoms) {
    const shifted = vectorSub([atom.x, atom.y, atom.z], transform.membraneCenter);
    const rotated = matrixVecMul(transform.rotateToY, shifted);
    atom.tx = rotated[0];
    atom.ty = rotated[1];
    atom.tz = rotated[2];
    if (transform.flipY) {
      atom.ty = -atom.ty;
      atom.tz = -atom.tz;
    }
    atom.ty -= transform.meanMY;
    if (atom.tx < minX) minX = atom.tx;
    if (atom.tx > maxX) maxX = atom.tx;
    if (atom.tz < minZ) minZ = atom.tz;
    if (atom.tz > maxZ) maxZ = atom.tz;
    if (
      atom.atomName === "CA" &&
      atom.resi > 0 &&
      atom.resi <= topology.length &&
      topology.charAt(atom.resi - 1) === "M"
    ) {
      if (atom.ty < mMinY) mMinY = atom.ty;
      if (atom.ty > mMaxY) mMaxY = atom.ty;
    }
  }

  const centerX =
    Number.isFinite(minX) && Number.isFinite(maxX) ? (minX + maxX) / 2 : 0;
  const centerZ =
    Number.isFinite(minZ) && Number.isFinite(maxZ) ? (minZ + maxZ) / 2 : 0;

  for (const atom of parsed.atoms) {
    if (atom.tx == null || atom.ty == null || atom.tz == null) continue;
    atom.tx -= centerX;
    atom.tz -= centerZ;
    const line = parsed.lines[atom.lineIndex];
    const x = formatPdbCoord(atom.tx);
    const y = formatPdbCoord(atom.ty);
    const z = formatPdbCoord(atom.tz);
    parsed.lines[atom.lineIndex] =
      `${line.slice(0, 30)}${x}${y}${z}${line.length > 54 ? line.slice(54) : ""}`;
  }

  let membrane: MembraneSlab | null = null;
  if (Number.isFinite(mMinY) && Number.isFinite(mMaxY) && mMaxY > mMinY) {
    // Slab XZ extent: take the protein's full XZ bounding-box half-
    // widths (minX/maxX/minZ/maxZ span every atom, not just the M
    // region, so even bulky ECDs / ICDs are enclosed), then pad
    // generously so the slab visibly surrounds the protein on every
    // side rather than terminating flush with the silhouette. The 30 Å
    // pad ≈ two phospholipid head-group rings; the 60 Å floor keeps a
    // single-TM bundle from collapsing to a postage-stamp patch.
    const xHalfWidth = Math.max((maxX - minX) / 2, 0);
    const zHalfWidth = Math.max((maxZ - minZ) / 2, 0);
    membrane = {
      yMin: mMinY,
      yMax: mMaxY,
      xExtent: Math.max(xHalfWidth + 30, 60),
      zExtent: Math.max(zHalfWidth + 30, 60),
    };
  }

  return { pdbText: parsed.lines.join("\n"), membrane };
}

/**
 * Public API: rotate a PDB string so the membrane plane is horizontal.
 *
 *   - On success, returns `{ pdbText, membrane }` — `pdbText` is the
 *     oriented PDB, `membrane` is the slab geometry (Y bounds + XZ
 *     half-widths) for the 3Dmol viewer to draw a translucent
 *     bilayer at the TM-helix plane.
 *   - When topology / atom counts are too sparse to compute a
 *     meaningful transform, returns `{ pdbText: <unchanged>,
 *     membrane: null }` so the caller skips the slab.
 *
 * Deterministic and side-effect-free; safe to call before
 * ``viewer.addModel(pdbText, "pdb")``.
 */
export function orientPdbForTopology(
  pdbText: string,
  topology: string,
): OrientationResult {
  const parsed = parsePdbForOrientation(pdbText);
  const transform = computeOrientationTransform(topology, parsed);
  return applyOrientationTransform(pdbText, topology, transform);
}
