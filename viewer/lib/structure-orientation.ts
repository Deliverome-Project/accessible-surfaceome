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
  transform: OrientationTransform | null,
): string {
  if (!transform) return pdbText;
  const parsed = parsePdbForOrientation(pdbText);
  if (parsed.atoms.length === 0) return pdbText;

  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let minZ = Number.POSITIVE_INFINITY;
  let maxZ = Number.NEGATIVE_INFINITY;
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
  return parsed.lines.join("\n");
}

/**
 * Public API: rotate a PDB string so the membrane plane is horizontal.
 *
 *   - Returns the *oriented* PDB text on success.
 *   - Returns the original PDB text unchanged when topology / atom
 *     counts are too sparse to compute a meaningful transform.
 *
 * Deterministic and side-effect-free; safe to call before
 * ``viewer.addModel(pdbText, "pdb")``.
 *
 * Used only by the legacy PDB-fallback path now. The primary path is
 * ``orientLoadedStructure`` below, which mutates the already-parsed
 * 3dmol atom array — that lets us drive the viewer from BCIF (no
 * client-side text parsing).
 */
export function orientPdbForTopology(pdbText: string, topology: string): string {
  const parsed = parsePdbForOrientation(pdbText);
  const transform = computeOrientationTransform(topology, parsed);
  return applyOrientationTransform(pdbText, transform);
}

/** Atom shape we read from 3dmol's `viewer.selectedAtoms({})`. We
 *  only need x/y/z/atom/resi; AtomSpec has many more fields we ignore. */
interface MutableAtom {
  x?: number;
  y?: number;
  z?: number;
  atom?: string;
  resi?: number;
}

/**
 * In-place orient an already-parsed structure so the membrane plane
 * is horizontal, extracellular side up. Mutates each atom's x/y/z
 * via the same I→O-onto-+Y rotation used by `orientPdbForTopology`,
 * but reads the coords from 3dmol's atom array instead of from raw
 * PDB text — so the viewer can accept BCIF (or any other format
 * 3dmol parses natively) without us needing a JS PDB / mmCIF parser.
 *
 * Returns `true` when a meaningful transform was applied, `false`
 * when topology / atom counts were too sparse and atoms were left
 * unchanged. Callers should call `viewer.render()` after a `true`.
 */
export function orientLoadedStructure(
  atoms: MutableAtom[],
  topology: string,
): boolean {
  if (!topology || atoms.length === 0) return false;
  // Build CA-by-residue map from the already-parsed atom array.
  const caByResidue = new Map<number, Vec3>();
  for (const a of atoms) {
    if (a.atom !== "CA") continue;
    if (
      typeof a.resi !== "number" ||
      a.resi < 1 ||
      typeof a.x !== "number" ||
      typeof a.y !== "number" ||
      typeof a.z !== "number"
    ) {
      continue;
    }
    if (!caByResidue.has(a.resi)) {
      caByResidue.set(a.resi, [a.x, a.y, a.z]);
    }
  }
  if (caByResidue.size === 0) return false;

  // Reuse the existing centroid + rotation math by handing it a
  // ParsedPdb-shaped object (only `atoms` and `caByResidue` are read
  // by computeOrientationTransform — `lines` is unused).
  const parsedShim: ParsedPdb = { lines: [], atoms: [], caByResidue };
  const transform = computeOrientationTransform(topology, parsedShim);
  if (!transform) return false;

  // First pass: apply rotation + flip + meanMY translation. Record
  // tx/tz extremes so we can re-center horizontally in pass two.
  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let minZ = Number.POSITIVE_INFINITY;
  let maxZ = Number.NEGATIVE_INFINITY;
  const transformed: { atom: MutableAtom; t: Vec3 }[] = [];
  for (const atom of atoms) {
    if (
      typeof atom.x !== "number" ||
      typeof atom.y !== "number" ||
      typeof atom.z !== "number"
    ) {
      continue;
    }
    const shifted = vectorSub(
      [atom.x, atom.y, atom.z],
      transform.membraneCenter,
    );
    const rotated = matrixVecMul(transform.rotateToY, shifted);
    let tx = rotated[0];
    let ty = rotated[1];
    let tz = rotated[2];
    if (transform.flipY) {
      ty = -ty;
      tz = -tz;
    }
    ty -= transform.meanMY;
    transformed.push({ atom, t: [tx, ty, tz] });
    if (tx < minX) minX = tx;
    if (tx > maxX) maxX = tx;
    if (tz < minZ) minZ = tz;
    if (tz > maxZ) maxZ = tz;
  }
  const centerX =
    Number.isFinite(minX) && Number.isFinite(maxX) ? (minX + maxX) / 2 : 0;
  const centerZ =
    Number.isFinite(minZ) && Number.isFinite(maxZ) ? (minZ + maxZ) / 2 : 0;
  for (const { atom, t } of transformed) {
    atom.x = t[0] - centerX;
    atom.y = t[1];
    atom.z = t[2] - centerZ;
  }
  return true;
}
