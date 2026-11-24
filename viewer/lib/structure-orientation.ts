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
  chain: string;
  tx?: number;
  ty?: number;
  tz?: number;
}

interface ParsedPdb {
  lines: string[];
  atoms: ParsedPdbAtom[];
  caByResidue: Map<number, Vec3>;
}

/**
 * Parse a PDB file into a list of atoms + a residue-keyed CA map.
 *
 * When `chainFilter` is given, only atoms on that chain contribute
 * to `caByResidue` (the data the orientation math uses). All atoms
 * are still collected into `atoms` so the transform applies to the
 * full model — we only want to AVOID multi-chain centroid pollution
 * in experimental PDBs (homotrimers, MHC-peptide complexes, etc.),
 * not hide other chains from the viewer.
 */
function parsePdbForOrientation(
  pdbText: string,
  chainFilter?: string,
): ParsedPdb {
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
    // PDB column 22 (1-indexed) = chain identifier. JS slice(21, 22).
    const chain = line.slice(21, 22);
    const atom: ParsedPdbAtom = {
      lineIndex: i,
      x,
      y,
      z,
      resi: Number.isInteger(resi) ? resi : 0,
      atomName,
      chain,
    };
    atoms.push(atom);
    const inFilter = chainFilter == null || chain === chainFilter;
    if (atomName === "CA" && atom.resi > 0 && inFilter && !caByResidue.has(atom.resi)) {
      caByResidue.set(atom.resi, [x, y, z]);
    }
  }
  return { lines, atoms, caByResidue };
}

/**
 * Bucket CA atoms by topology state (M / O / I).
 *
 * The PDB's residue numbering need not match the topology's. For
 * AlphaFold models numbering IS UniProt-residue and `residueOffset`
 * is 0; for experimental PDBs (where the chain often starts at a
 * non-1 residue number, sometimes negative for engineered tags),
 * the caller passes `residueOffset = pdb_start - unp_start` and we
 * subtract it before indexing the topology string.
 */
function collectStateCoords(
  topology: string,
  caByResidue: Map<number, Vec3>,
  residueOffset = 0,
  resiToTopo?: (pdbResi: number) => number | null,
): { M: Vec3[]; O: Vec3[]; I: Vec3[] } {
  const states: { M: Vec3[]; O: Vec3[]; I: Vec3[] } = { M: [], O: [], I: [] };
  if (!topology) return states;
  for (const [resi, coord] of caByResidue) {
    // `resiToTopo` (when supplied) maps a PDB author resSeq → topology
    // (UniProt) index, handling non-linear / multi-segment numbering.
    // Without it we fall back to the single linear shift. NB: keep the
    // explicit `== null` guard — a `null` return would coerce to 0 and
    // sneak past the `< 1` bound otherwise.
    const topoResi = resiToTopo ? resiToTopo(resi) : resi - residueOffset;
    if (topoResi == null || topoResi < 1 || topoResi > topology.length) continue;
    const state = topology.charAt(topoResi - 1);
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
  /** XZ centroid offset from the protein's own XZ-centered frame.
   *  The TM bundle isn't always at the same X/Z as the protein's
   *  overall bounding-box center (e.g. an ECD that hangs off to
   *  one side shifts the bbox center but not the TM helix). The
   *  3Dmol viewer must add this offset when placing the slab. */
  xCenter: number;
  zCenter: number;
}

export interface OrientationResult {
  pdbText: string;
  membrane: MembraneSlab | null;
}

function computeOrientationTransform(
  topology: string,
  parsed: ParsedPdb,
  residueOffset = 0,
  resiToTopo?: (pdbResi: number) => number | null,
  minSideResidues = 6,
): OrientationTransform | null {
  if (!topology || parsed.atoms.length === 0 || parsed.caByResidue.size === 0) {
    return null;
  }
  const states = collectStateCoords(
    topology, parsed.caByResidue, residueOffset, resiToTopo,
  );
  // Need a minimum count per class so centroids are statistically
  // meaningful; matches the deliverome-internal threshold.
  if (states.M.length < 6 || states.O.length < minSideResidues || states.I.length < minSideResidues) {
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
  chainFilter?: string,
  residueOffset = 0,
  resiToTopo?: (pdbResi: number) => number | null,
): { pdbText: string; membrane: MembraneSlab | null } {
  if (!transform) return { pdbText, membrane: null };
  // Don't pass chainFilter here — we want the transform to apply to
  // ALL atoms (other chains stay positioned relative to the canonical
  // one in the rotated frame). Chain-aware filtering only happens
  // below when picking M-state CAs for slab Y bounds.
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
  // Also track the X/Z bounds of M-state CA atoms — this gives the
  // TM bundle's actual cross-section, which the slab should match.
  // The previous full-protein bounding box made the slab dwarf the
  // membrane on proteins with large ECDs (EGFR is the worst case:
  // 620-residue ECD + 270-residue ICD vs a single 23-residue TM
  // helix produced a 200×200 Å slab around a single helix).
  let mMinX = Number.POSITIVE_INFINITY;
  let mMaxX = Number.NEGATIVE_INFINITY;
  let mMinZ = Number.POSITIVE_INFINITY;
  let mMaxZ = Number.NEGATIVE_INFINITY;
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
    // Slab Y/X/Z bounds: pick only CAs that (a) are on the canonical
    // chain (when chainFilter is given), AND (b) map to an `M` in the
    // topology. `resiToTopo` handles non-linear numbering; otherwise
    // the single linear shift (PDB-coord → UniProt-coord) applies.
    const topoResi = resiToTopo ? resiToTopo(atom.resi) : atom.resi - residueOffset;
    if (
      atom.atomName === "CA" &&
      atom.resi > 0 &&
      topoResi != null &&
      topoResi >= 1 &&
      topoResi <= topology.length &&
      topology.charAt(topoResi - 1) === "M" &&
      (chainFilter == null || atom.chain === chainFilter)
    ) {
      if (atom.ty < mMinY) mMinY = atom.ty;
      if (atom.ty > mMaxY) mMaxY = atom.ty;
      if (atom.tx < mMinX) mMinX = atom.tx;
      if (atom.tx > mMaxX) mMaxX = atom.tx;
      if (atom.tz < mMinZ) mMinZ = atom.tz;
      if (atom.tz > mMaxZ) mMaxZ = atom.tz;
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
    // Slab XZ extent: take the TM-helix-bundle's own XZ bounding-box
    // half-widths (NOT the full protein's — that made the slab dwarf
    // the membrane for big-ECD single-pass receptors like EGFR), then
    // pad ~12 Å (≈ one phospholipid head-group ring) so the slab
    // visibly surrounds the TM region without spilling into the ECD.
    // The 25 Å floor keeps a single-helix TM from collapsing to a
    // visually-indistinguishable patch. Re-center against the new
    // post-shift coordinates (the XZ recentering above moves the
    // protein's bbox center to origin, and the TM bundle inherits
    // the same shift).
    const mHalfX = Number.isFinite(mMaxX) && Number.isFinite(mMinX)
      ? Math.max((mMaxX - mMinX) / 2, 0) : 0;
    const mHalfZ = Number.isFinite(mMaxZ) && Number.isFinite(mMinZ)
      ? Math.max((mMaxZ - mMinZ) / 2, 0) : 0;
    const mCenterX = Number.isFinite(mMaxX) && Number.isFinite(mMinX)
      ? (mMinX + mMaxX) / 2 - centerX : 0;
    const mCenterZ = Number.isFinite(mMaxZ) && Number.isFinite(mMinZ)
      ? (mMinZ + mMaxZ) / 2 - centerZ : 0;
    membrane = {
      yMin: mMinY,
      yMax: mMaxY,
      xExtent: Math.max(mHalfX + 12, 25),
      zExtent: Math.max(mHalfZ + 12, 25),
      xCenter: mCenterX,
      zCenter: mCenterZ,
    };
  }

  return { pdbText: parsed.lines.join("\n"), membrane };
}

/**
 * Options for {@link orientPdbForTopology} — needed for experimental
 * PDBs (where the relevant chain isn't always "A" and the residue
 * numbering rarely matches the canonical UniProt sequence). AFDB
 * models can omit both: their PDBs are single-chain (A) and number
 * residues by UniProt position.
 */
export interface OrientPdbOptions {
  /** PDB chain ID to use for centroid math + slab Y bounds. When set,
   *  CAs on other chains don't pollute the M/O/I centroids or the
   *  membrane slab thickness — important for multi-chain experimental
   *  structures (homotrimers, MHC-peptide complexes, partner
   *  co-crystals). Other chains still get the same orientation
   *  transform applied so they stay positioned correctly relative to
   *  the canonical chain in the rendered model. Default: include all
   *  chains. */
  chainId?: string;
  /** Residue-number offset to translate PDB residue → topology
   *  (UniProt) residue: `topologyResi = pdbResi - residueOffset`.
   *  Default 0 (AFDB convention). Ignored when `resiToTopo` is set. */
  residueOffset?: number;
  /** Non-linear PDB-author-resSeq → topology(UniProt)-index map. When
   *  provided it overrides `residueOffset` for every per-residue lookup
   *  (centroid bucketing + membrane-slab bounds). Needed for
   *  experimental PDBs whose author numbering isn't a single linear
   *  shift of the UniProt sequence — multi-segment fusion constructs,
   *  or files renumbered away from both UniProt and SIFTS author space.
   *  Return `null` for resSeq values that don't map onto the topology
   *  (unmapped fusion partners, ligands, gaps). */
  resiToTopo?: (pdbResi: number) => number | null;
  /** Fewest extracellular (O) and intracellular (I) CAs each side needs before the
   *  O→I axis is trusted. Default 6, the deliverome-internal threshold the gene page
   *  keeps. The L1 views lower it to 1 on a retry so a single-pass member with a
   *  2–5-residue cytoplasmic tail still gets a membrane instead of none; the TM-helix
   *  count stays at 6 either way. */
  minSideResidues?: number;
}

/**
 * Public API: rotate a PDB string so the membrane plane is horizontal.
 *
 *   - On success, returns `{ pdbText, membrane }` — `pdbText` is the
 *     oriented PDB, `membrane` is the slab geometry (Y bounds + XZ
 *     half-widths) for the 3Dmol viewer to draw a translucent
 *     bilayer at the TM-helix plane.
 *   - When topology / atom counts are too sparse to compute a
 *     meaningful transform (no TM coverage in the chain, &lt;6
 *     residues of any M/O/I class), returns `{ pdbText: <unchanged>,
 *     membrane: null }` so the caller skips the slab AND the
 *     orientation transform (the structure renders in its native
 *     pose).
 *
 * Deterministic and side-effect-free; safe to call before
 * ``viewer.addModel(pdbText, "pdb")``.
 */
export function orientPdbForTopology(
  pdbText: string,
  topology: string,
  options?: OrientPdbOptions,
): OrientationResult {
  const chainFilter = options?.chainId;
  const residueOffset = options?.residueOffset ?? 0;
  const resiToTopo = options?.resiToTopo;
  const parsed = parsePdbForOrientation(pdbText, chainFilter);
  const transform = computeOrientationTransform(
    topology, parsed, residueOffset, resiToTopo, options?.minSideResidues ?? 6,
  );
  return applyOrientationTransform(
    pdbText, topology, transform, chainFilter, residueOffset, resiToTopo,
  );
}

export interface SuperposeResult {
  pdbText: string;
  rmsd: number;
  nAligned: number;
}

/**
 * Largest-eigenvalue unit eigenvector of a 4×4 real symmetric matrix via
 * cyclic Jacobi rotations (converges to < 1e-13 in < 10 sweeps).
 */
function largestEigenvector4(sym: number[][]): [number, number, number, number] {
  const a = sym.map((r) => [...r]);
  const v = [
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
  ];
  for (let sweep = 0; sweep < 25; sweep += 1) {
    let maxOff = 0;
    for (let p = 0; p < 4; p += 1) {
      for (let q = p + 1; q < 4; q += 1) {
        const apq = a[p][q];
        if (Math.abs(apq) > maxOff) maxOff = Math.abs(apq);
        if (Math.abs(apq) < 1e-13) continue;
        const tau = (a[q][q] - a[p][p]) / (2 * apq);
        const t = tau >= 0 ? 1 / (tau + Math.hypot(1, tau)) : -1 / (-tau + Math.hypot(1, tau));
        const c = 1 / Math.hypot(1, t);
        const s = t * c;
        const app = a[p][p];
        const aqq = a[q][q];
        a[p][p] = app - t * apq;
        a[q][q] = aqq + t * apq;
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
  const n = Math.hypot(q[0], q[1], q[2], q[3]) || 1;
  return [q[0] / n, q[1] / n, q[2] / n, q[3] / n];
}

/**
 * Superpose `mobilePdb` onto `targetPdb` using Horn's quaternion Kabsch
 * alignment over the matched `[mobileResi, targetResi]` Cα pairs.
 * Guarantees a proper rotation (det R = +1, no reflections).
 */
export function superposePdbOntoTarget(
  mobilePdb: string,
  targetPdb: string,
  pairs: readonly [number, number][],
): SuperposeResult | null {
  const mobile = parsePdbForOrientation(mobilePdb);
  const target = parsePdbForOrientation(targetPdb);
  const P: Vec3[] = [];
  const Q: Vec3[] = [];
  for (const [mRes, tRes] of pairs) {
    const p = mobile.caByResidue.get(mRes);
    const q = target.caByResidue.get(tRes);
    if (p && q) {
      P.push(p);
      Q.push(q);
    }
  }
  if (P.length < 3) return null;
  const pMean = centroid(P)!;
  const qMean = centroid(Q)!;
  let sxx = 0, sxy = 0, sxz = 0;
  let syx = 0, syy = 0, syz = 0;
  let szx = 0, szy = 0, szz = 0;
  for (let i = 0; i < P.length; i += 1) {
    const px = P[i][0] - pMean[0];
    const py = P[i][1] - pMean[1];
    const pz = P[i][2] - pMean[2];
    const qx = Q[i][0] - qMean[0];
    const qy = Q[i][1] - qMean[1];
    const qz = Q[i][2] - qMean[2];
    sxx += px * qx; sxy += px * qy; sxz += px * qz;
    syx += py * qx; syy += py * qy; syz += py * qz;
    szx += pz * qx; szy += pz * qy; szz += pz * qz;
  }
  const N = [
    [sxx + syy + szz, syz - szy, szx - sxz, sxy - syx],
    [syz - szy, sxx - syy - szz, sxy + syx, szx + sxz],
    [szx - sxz, sxy + syx, -sxx + syy - szz, syz + szy],
    [sxy - syx, szx + sxz, syz + szy, -sxx - syy + szz],
  ];
  const [w, x, y, z] = largestEigenvector4(N);
  const R: Mat3 = [
    [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
    [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
    [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
  ];
  let sqErr = 0;
  for (let i = 0; i < P.length; i += 1) {
    const rot = matrixVecMul(R, vectorSub(P[i], pMean));
    const aligned = vectorAdd(rot, qMean);
    const d = vectorSub(aligned, Q[i]);
    sqErr += vectorDot(d, d);
  }
  const rmsd = Math.sqrt(sqErr / P.length);
  for (const atom of mobile.atoms) {
    const rot = matrixVecMul(R, vectorSub([atom.x, atom.y, atom.z], pMean));
    const aligned = vectorAdd(rot, qMean);
    const line = mobile.lines[atom.lineIndex];
    mobile.lines[atom.lineIndex] =
      `${line.slice(0, 30)}${formatPdbCoord(aligned[0])}${formatPdbCoord(aligned[1])}${formatPdbCoord(aligned[2])}${line.length > 54 ? line.slice(54) : ""}`;
  }
  return { pdbText: mobile.lines.join("\n"), rmsd, nAligned: P.length };
}

/**
 * Return the N- and C-terminal Cα residue numbers (first and last `ATOM` Cα
 * records on the first chain) for labelling a PDB model's termini.
 */
export function pdbTerminiResidues(pdbText: string): { n: number; c: number; chain: string } | null {
  let chain: string | null = null;
  let first: number | null = null;
  let last: number | null = null;
  for (const line of String(pdbText || "").split(/\r?\n/)) {
    if (!line.startsWith("ATOM")) continue;
    if (line.length < 26) continue;
    if (line.slice(12, 16).trim() !== "CA") continue;
    const ch = line.slice(21, 22);
    if (chain === null) chain = ch;
    else if (ch !== chain) continue;
    const resi = Number.parseInt(line.slice(22, 26).trim(), 10);
    if (!Number.isInteger(resi)) continue;
    if (first === null) first = resi;
    last = resi;
  }
  return first !== null && last !== null ? { n: first, c: last, chain: (chain ?? "").trim() } : null;
}
