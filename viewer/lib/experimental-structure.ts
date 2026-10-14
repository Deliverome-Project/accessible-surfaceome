/**
 * Experimental-structure selection and loading for the structure viewer.
 *
 * Lives outside `StructureViewer.tsx` so the cohort audit
 * (`scripts/audit-structures.ts`) runs exactly the code the viewer runs:
 * the PDBe `best_structures` pick, the RCSB download with its mmCIF
 * fallback, the chain resolution and the UniProt→author projection. An
 * audit that re-implemented any of these would drift from the viewer and
 * stop catching the failures it exists to catch (9V8W shipped a 404
 * because nothing exercised the RCSB path across the cohort).
 */
import { mmcifToPdb } from "./mmcif-to-pdb";

/** PDBe `best_structures` API response shape (one entry — the
 *  endpoint returns an object keyed by UniProt acc with an array of
 *  these). We only use a subset of fields; documented for grep-ability. */
export interface PDBeBestStructure {
  pdb_id: string;
  chain_id: string;
  unp_start: number;
  unp_end: number;
  start: number;
  end: number;
  experimental_method: string;
  resolution: number | null;
  coverage: number;
  tax_id?: number;
}

/** The viewer's experimental-structure pick from a PDBe
 *  `best_structures` list, or ``null`` when the list is empty. */
export function pickBestStructure(
  candidates: PDBeBestStructure[],
): PDBeBestStructure | null {
  if (candidates.length === 0) return null;
  // PDBe already ranks by coverage → resolution. Prefer the human
  // (same-species) rows when any exist; otherwise rank over
  // everything (some rows lack tax_id).
  const human = candidates.filter((c) => c.tax_id === 9606);
  const ranked = human.length > 0 ? human : candidates;
  const top = ranked[0];
  // "clean" = the chain maps to UniProt as a single contiguous
  // segment (SEQRES span == UniProt span), so the topology
  // projects through one linear offset. A "dirty" top is usually
  // a fusion construct (e.g. GPR75 9xqn packs BRIL + the receptor
  // into one chain across 7 discontinuous segments), which
  // mis-colors under a single offset.
  if (isCleanStructure(top)) return top;
  // Skip down to a comparable clean structure when one exists:
  // similar coverage (within tolerance — don't trade away much
  // of the resolved sequence) and not much worse resolution
  // (better resolution is never penalized). GPR75 is the
  // trigger: top 9xqn is a dirty fusion (cov 0.685, 3.91 Å);
  // 9xqc is clean (cov 0.663, 3.0 Å) — a 0.02 coverage cost for
  // a clean, higher-resolution map. When no comparable clean
  // structure exists we keep the dirty top and project it
  // piecewise (approach C) with a caption caveat.
  const COVERAGE_TOL = 0.1;
  const RES_TOL = 2.0;
  const cleanAlt = ranked.find(
    (c) =>
      isCleanStructure(c) &&
      c.coverage >= top.coverage - COVERAGE_TOL &&
      (c.resolution == null ||
        top.resolution == null ||
        c.resolution <= top.resolution + RES_TOL),
  );
  return cleanAlt ?? top;
}

/** Span equality ⟹ the chain maps to UniProt as one contiguous segment. */
export function isCleanStructure(c: PDBeBestStructure): boolean {
  return c.end - c.start === c.unp_end - c.unp_start;
}

/** Above this many deposited atoms an mmCIF-only experimental entry is
 *  loaded as its mapped chain alone (RCSB ModelServer) rather than the
 *  whole assembly. 99,999 is also the legacy PDB format's serial limit,
 *  so this only ever trims entries RCSB couldn't serve as .pdb anyway;
 *  past it the full mmCIF runs from ~8 MB to hundreds of MB. */
export const EXP_FULL_ASSEMBLY_MAX_ATOMS = 99_999;

/** Title + deposited atom count from the RCSB entry API. ``null`` on any
 *  failure, in which case the caller loads the full mmCIF. */
export async function fetchRcsbEntrySummary(
  pdbId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ title: string | null; atomCount: number | null } | null> {
  try {
    const r = await fetchImpl(
      `https://data.rcsb.org/rest/v1/core/entry/${pdbId.toUpperCase()}`,
      { cache: "force-cache" },
    );
    if (!r.ok) return null;
    const j = (await r.json()) as {
      struct?: { title?: string };
      rcsb_entry_info?: { deposited_atom_count?: number };
    };
    return {
      title: j.struct?.title ?? null,
      atomCount: j.rcsb_entry_info?.deposited_atom_count ?? null,
    };
  } catch {
    return null;
  }
}

/** An experimental structure as PDB-format text, ready for the viewer. */
export interface ExperimentalPdb {
  rawPdb: string;
  /** The PDBe chain id as it appears in ``rawPdb`` — identity except when
   *  an mmCIF-only entry's multi-character chain ids were remapped. */
  chainId: string;
  /** Deposited atom count when the entry was too large to load whole and
   *  only ``chainId`` was fetched; ``null`` for a full-assembly load. */
  chainOnlyAtomCount: number | null;
  /** Which RCSB download loaded: the legacy .pdb, the full mmCIF, or
   *  the mapped chain's mmCIF from the ModelServer. */
  source: "pdb" | "cif" | "cif_chain_only";
}

/** Download an experimental structure from RCSB as PDB text. Throws
 *  ``Error("RCSB returned {status} for {id}")`` when no format loads. */
export async function fetchExperimentalPdb(
  pdbId: string,
  chainId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ExperimentalPdb> {
  // RCSB returns the PDB file directly. Aggressive caching is
  // fine — PDB entries are immutable per release.
  const rcsbBase = `https://files.rcsb.org/download/${pdbId}`;
  const resp = await fetchImpl(`${rcsbBase}.pdb`, { cache: "force-cache" });
  if (resp.ok) {
    return {
      rawPdb: await resp.text(),
      chainId,
      chainOnlyAtomCount: null,
      source: "pdb",
    };
  }
  // Entries that don't fit the legacy format (a 5-character
  // ligand code, multi-character chain ids, >99,999 atoms) have
  // no .pdb at all — 9V8W 404s on its A1D9S ligand. The mmCIF
  // always exists; convert it to the PDB text the rest of the
  // pipeline reads. A whole-assembly mmCIF can run to hundreds
  // of MB (8J07, a microtubule doublet, is 353 MB), so above
  // EXP_FULL_ASSEMBLY_MAX_ATOMS fetch only the mapped chain from
  // the RCSB ModelServer instead.
  const entry = await fetchRcsbEntrySummary(pdbId, fetchImpl);
  const chainOnly =
    entry?.atomCount != null && entry.atomCount > EXP_FULL_ASSEMBLY_MAX_ATOMS;
  const cifUrl = chainOnly
    ? `https://models.rcsb.org/v1/${pdbId}/atoms?` +
      `auth_asym_id=${encodeURIComponent(chainId)}` +
      "&model_nums=1&encoding=cif"
    : `${rcsbBase}.cif`;
  const cifResp = await fetchImpl(cifUrl, { cache: "force-cache" });
  if (!cifResp.ok) {
    throw new Error(`RCSB returned ${cifResp.status} for ${pdbId}`);
  }
  const converted = mmcifToPdb(await cifResp.text(), {
    preferredChainId: chainId,
    title: entry?.title,
  });
  return {
    rawPdb: converted.pdb,
    chainId: converted.chainMap[chainId] ?? chainId,
    chainOnlyAtomCount: chainOnly ? (entry.atomCount as number) : null,
    source: chainOnly ? "cif_chain_only" : "cif",
  };
}

/**
 * Pick the effective chain ID to use for an experimental PDB. PDBe's
 * `best_structures` endpoint returns a chain ID that should match the
 * deposited PDB's auth_asym_id, but in practice the two disagree
 * occasionally:
 *
 *   - Case mismatch (PDBe "A" vs PDB "a") — uncommon but happens for
 *     a few recently-deposited entries.
 *   - PDBe gives the label_asym_id while the RCSB PDB file uses
 *     auth_asym_id — different conventions for the same chain.
 *   - GPR75 (UniProt O95800) was the trigger case: the PDBe metadata's
 *     chain didn't appear in the served PDB file, so every chain-
 *     restricted `setStyle` call below silently no-op'd and the model
 *     rendered in 3Dmol's default gray with no topology coloring.
 *
 * Strategy: extract the set of chains actually present in the PDB
 * (one entry per ATOM/HETATM `column 22` letter), then:
 *
 *   1. Exact match → use as-is.
 *   2. Case-insensitive match → use the PDB's actual casing.
 *   3. Otherwise → use the chain with the most atoms (the canonical
 *      protein chain in the overwhelming majority of cases). This is
 *      defensive and not strictly correct for hetero-complexes where
 *      the canonical chain isn't the biggest, but it beats the silent
 *      no-op the previous code path produced.
 *
 * Returns `null` when the PDB has no ATOM/HETATM lines at all
 * (corrupt download); the caller should treat that as a render-skip
 * failure.
 */
export function pickPdbChain(
  pdbText: string,
  preferredChainId: string,
): string | null {
  const counts = new Map<string, number>();
  for (const line of pdbText.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
    if (line.length < 22) continue;
    const c = line.slice(21, 22);
    if (!c.trim()) continue;
    counts.set(c, (counts.get(c) ?? 0) + 1);
  }
  if (counts.size === 0) return null;
  if (counts.has(preferredChainId)) return preferredChainId;
  // Case-insensitive fallback — PDBe occasionally lowercases what
  // the PDB file capitalizes (or vice versa).
  const target = preferredChainId.toLowerCase();
  for (const c of counts.keys()) {
    if (c.toLowerCase() === target) return c;
  }
  // Last resort: heaviest chain. Logged as a console.warn so the
  // mismatch surfaces in dev tools — readers shouldn't see anything
  // unusual since the topology coloring still works.
  let best: string | null = null;
  let bestCount = -1;
  for (const [c, n] of counts) {
    if (n > bestCount) {
      best = c;
      bestCount = n;
    }
  }
  if (typeof console !== "undefined" && best) {
    console.warn(
      `[StructureViewer] PDBe chain "${preferredChainId}" not found in ` +
        `PDB file (chains present: ${[...counts.keys()].join(", ")}); ` +
        `falling back to heaviest chain "${best}".`,
    );
  }
  return best;
}

/** Author resSeq values present (ATOM + HETATM) on a chain in the
 *  fetched PDB file — i.e. the residues 3Dmol can actually select.
 *  Used to score candidate projection offsets: the correct offset lands
 *  the most UniProt-mapped residues on real atoms. We can't trust
 *  `best_structures.start` (a SEQRES index) or even PDBe author numbers
 *  (which can diverge from the legacy `.pdb` file RCSB serves, e.g.
 *  EGFR 7syd), so the file itself is the only ground truth. */
export function observedResSeq(pdbText: string, chainId: string): Set<number> {
  const out = new Set<number>();
  for (const line of pdbText.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
    if (line.length < 26) continue;
    if (line.slice(21, 22) !== chainId) continue;
    const resi = Number.parseInt(line.slice(22, 26).trim(), 10);
    if (Number.isInteger(resi)) out.add(resi);
  }
  return out;
}

/** Count residues of UniProt window ``[unpLo, unpHi]`` that, shifted by
 *  ``offset``, land on an observed author resSeq. */
export function overlapCount(
  unpLo: number,
  unpHi: number,
  offset: number,
  observed: Set<number>,
): number {
  let n = 0;
  for (let u = unpLo; u <= unpHi; u += 1) {
    if (observed.has(u + offset)) n += 1;
  }
  return n;
}

/** Pick the UniProt→author offset that lands the most of
 *  ``[unpLo, unpHi]`` on real atoms. ``candidates`` are principled
 *  guesses: ``0`` (file numbered by UniProt residue — the modern norm,
 *  true for GPR75 9xqc), the SEQRES-based legacy offset, and (for
 *  fusions) the SIFTS author offset. Ties keep ``fallback`` so a
 *  structure that already rendered with the legacy offset can never
 *  regress — a different offset is only adopted when it strictly covers
 *  more residues, which means it genuinely aligns better to the file. */
export function bestLinearOffset(
  unpLo: number,
  unpHi: number,
  candidates: number[],
  observed: Set<number>,
  fallback: number,
): number {
  let best = fallback;
  let bestScore = overlapCount(unpLo, unpHi, fallback, observed);
  for (const c of candidates) {
    if (c === fallback) continue;
    const score = overlapCount(unpLo, unpHi, c, observed);
    if (score > bestScore) {
      best = c;
      bestScore = score;
    }
  }
  return best;
}

/** A contiguous UniProt→PDB-author projection segment. A topology
 *  (UniProt-coord) residue ``u`` in ``[unpLo, unpHi]`` maps to PDB
 *  author resSeq ``u + offset``. Clean structures have a single
 *  segment; fusion constructs have several, each with its own offset. */
export interface ProjSegment {
  unpLo: number;
  unpHi: number;
  offset: number;
}

/** Raw SIFTS detailed-mapping segment for one chain. ``authorLo`` /
 *  ``authorHi`` are nullable — PDBe omits author numbers for some
 *  entries (GPR75 9xqc returns ``None``/``None``); the offset is then
 *  derived from whichever boundary is present, or from the seqres span. */
export interface SiftsRawSegment {
  unpLo: number;
  unpHi: number;
  seqresLo: number;
  authorLo: number | null;
  authorHi: number | null;
}

/** Fetch SIFTS per-segment UniProt↔PDB mappings (``/api/mappings/{pdb}``)
 *  for the chosen chain. Used on the ``approx`` (fusion) path, where
 *  `best_structures` collapses the discontinuous mapping into one
 *  non-linear span, and when the single-offset guess lands nothing.
 *  Returns ``[]`` on any failure so the caller can fall back to the
 *  single-offset projection. */
export async function fetchSiftsSegments(
  pdbId: string,
  uniprotAcc: string,
  chainId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<SiftsRawSegment[]> {
  try {
    const r = await fetchImpl(
      `https://www.ebi.ac.uk/pdbe/api/mappings/${pdbId.toLowerCase()}`,
      { cache: "force-cache" },
    );
    if (!r.ok) return [];
    const j = (await r.json()) as Record<
      string,
      { UniProt?: Record<string, { mappings?: Array<Record<string, unknown>> }> }
    >;
    const unpBlock = j[pdbId.toLowerCase()]?.UniProt ?? {};
    const block = unpBlock[uniprotAcc] ?? Object.values(unpBlock)[0];
    const mappings = block?.mappings ?? [];
    const segs: SiftsRawSegment[] = [];
    for (const m of mappings) {
      if (m.chain_id !== chainId && m.struct_asym_id !== chainId) continue;
      const unpLo = m.unp_start as number;
      const unpHi = m.unp_end as number;
      if (typeof unpLo !== "number" || typeof unpHi !== "number") continue;
      const start = m.start as Record<string, number | null> | undefined;
      const end = m.end as Record<string, number | null> | undefined;
      segs.push({
        unpLo,
        unpHi,
        seqresLo: (start?.residue_number as number) ?? unpLo,
        authorLo: (start?.author_residue_number as number | null) ?? null,
        authorHi: (end?.author_residue_number as number | null) ?? null,
      });
    }
    return segs;
  } catch {
    return [];
  }
}

/** Convert raw SIFTS segments into projection segments (approach C). For
 *  each segment, derive the UniProt→author offset from whichever author
 *  boundary PDBe provides (both give the same offset for a linear
 *  segment; if one is null use the other), then keep whichever of
 *  {author offset, seqres offset} lands more of the segment on real
 *  atoms. Self-correcting: validating against the file means a wrong
 *  author number simply loses to the seqres candidate. */
export function projSegmentsFromSifts(
  raw: SiftsRawSegment[],
  observed: Set<number>,
): ProjSegment[] {
  const out: ProjSegment[] = [];
  for (const s of raw) {
    const seqresOffset = s.seqresLo - s.unpLo;
    const candidates: number[] = [];
    let authorOffset: number | null = null;
    if (s.authorLo != null) authorOffset = s.authorLo - s.unpLo;
    else if (s.authorHi != null) authorOffset = s.authorHi - s.unpHi;
    if (authorOffset != null) candidates.push(authorOffset);
    candidates.push(seqresOffset);
    const offset = bestLinearOffset(
      s.unpLo, s.unpHi, candidates, observed, authorOffset ?? seqresOffset,
    );
    out.push({ unpLo: s.unpLo, unpHi: s.unpHi, offset });
  }
  return out;
}

/** Residues of ``segments`` that land on an observed author resSeq —
 *  how much of the chain the topology colouring will actually paint. */
export function projectedCoverage(
  segments: ProjSegment[],
  observed: Set<number>,
): number {
  return segments.reduce(
    (n, s) => n + overlapCount(s.unpLo, s.unpHi, s.offset, observed),
    0,
  );
}

/** The UniProt→PDB-author projection for an experimental chain. The
 *  topology string is UniProt-keyed; 3Dmol selects on the file's author
 *  resSeq; `best_structures.start` is a SEQRES index (and PDBe author
 *  numbers can disagree with the legacy .pdb RCSB serves — EGFR 7syd is
 *  1..614 in the file but -23..1186 in PDBe author space). So candidate
 *  offsets are validated against ``observed``, the residues actually in
 *  the fetched file, and the best kept. */
export async function projectExperimentalChain(
  hit: {
    pdbId: string;
    uniprotAcc: string;
    /** PDBe chain id (what SIFTS is keyed on). */
    chainId: string;
    unpStart: number;
    unpEnd: number;
    /** `best_structures.start` — a SEQRES index. */
    pdbStart: number;
    /** Fusion construct: project piecewise from SIFTS. */
    approx: boolean;
  },
  pdbText: string,
  fileChainId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ProjSegment[]> {
  const observed = observedResSeq(pdbText, fileChainId);
  const sifts = () =>
    fetchSiftsSegments(hit.pdbId, hit.uniprotAcc, hit.chainId, fetchImpl).then(
      (raw) => projSegmentsFromSifts(raw, observed),
    );
  if (hit.approx) {
    // Approach C — discontinuous fusion mapping. Project piecewise from
    // SIFTS per-segment author numbers, each segment's offset file-
    // validated. Falls through to the single-offset path if SIFTS is
    // unavailable.
    const segs = await sifts();
    if (segs.length > 0) return segs;
  }
  // Clean single contiguous segment (or dirty w/o usable SIFTS).
  // Candidate offsets: 0 (file numbered by UniProt residue — the
  // modern norm, true for GPR75 9xqc where author == UniProt) vs
  // the legacy SEQRES offset. Ties keep the legacy offset so
  // anything that already rendered can't regress (EGFR 7syd: both
  // are 0, 614 residues). 9xqc: offset 0 covers 266 residues vs
  // the legacy -34's 234, so the bug (off-by-34) is corrected.
  const seqresOffset = hit.pdbStart - hit.unpStart;
  const offset = bestLinearOffset(
    hit.unpStart, hit.unpEnd, [0, seqresOffset], observed, seqresOffset,
  );
  const single = [{ unpLo: hit.unpStart, unpHi: hit.unpEnd, offset }];
  if (hit.approx || projectedCoverage(single, observed) > 0) return single;
  // Neither guess lands a single residue: the file numbers the chain by
  // neither UniProt nor SEQRES (CHMP2B 2jqk chain B is a 19-residue
  // peptide numbered 111-129 for UniProt 195-213). SIFTS carries the
  // author numbers, so take its projection when it does better.
  const segs = await sifts();
  if (projectedCoverage(segs, observed) > 0) return segs;
  // SIFTS has no author numbers either (KCNMB4 6v22 chain E is numbered
  // from 2001, M6PR 1juq chain E's 13-residue peptide from 301). The
  // file's own DBREF records state author ↔ UniProt numbering directly.
  const dbref = dbrefSegments(pdbText, fileChainId, hit.uniprotAcc);
  return projectedCoverage(dbref, observed) > 0 ? dbref : single;
}

/** Projection segments from a PDB file's DBREF records for one chain
 *  and UniProt accession: author residues ``[seqBegin, seqEnd]`` map to
 *  UniProt ``[dbBegin, dbEnd]``. Reads the one-line ``DBREF`` form only:
 *  the ``DBREF1``/``DBREF2`` pair is for accessions longer than 8
 *  characters, and no cohort gene with a structure has one. Converted
 *  mmCIF text carries no DBREF, so this returns ``[]`` for it. */
export function dbrefSegments(
  pdbText: string,
  chainId: string,
  uniprotAcc: string,
): ProjSegment[] {
  const out: ProjSegment[] = [];
  const int = (s: string) => Number.parseInt(s.trim(), 10);
  const push = (seqBegin: number, dbBegin: number, dbEnd: number) => {
    if ([seqBegin, dbBegin, dbEnd].every(Number.isInteger)) {
      out.push({ unpLo: dbBegin, unpHi: dbEnd, offset: seqBegin - dbBegin });
    }
  };
  for (const line of pdbText.split(/\r?\n/)) {
    if (!line.startsWith("DBREF ") || line.slice(12, 13) !== chainId) continue;
    if (line.slice(26, 32).trim() !== "UNP") continue;
    if (line.slice(33, 41).trim() !== uniprotAcc) continue;
    push(int(line.slice(14, 18)), int(line.slice(55, 60)), int(line.slice(62, 67)));
  }
  return out;
}
