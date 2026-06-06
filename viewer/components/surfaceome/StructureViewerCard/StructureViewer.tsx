"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { CITATIONS, pubmedUrl } from "../../../lib/citations";
import { orientPdbForTopology } from "../../../lib/structure-orientation";
import {
  MEMBRANE_COLOR,
  TOPOLOGY_COLORS,
  alphafoldPdbUrl,
  alphafoldPredictionApiUrl,
} from "../../../lib/structure-viewer-types";
import type {
  AlphafoldPredictionEntry,
  StructureViewerData,
} from "../../../lib/structure-viewer-types";
import { InfoTip } from "../../InfoTip/InfoTip";
import { TopologyLegend } from "../IsoformsCard/TopologyBar";
import { StatusPill } from "../StatusPill/StatusPill";
import { tooltips } from "../../../lib/tooltips";
import styles from "./StructureViewerCard.module.css";

/** Per-residue compartment, derived from the DeepTMHMM topology
 *  string. Annotates each SURFACE-Bind anchor so the viewer can
 *  show whether the site is antibody-accessible (extracellular) or
 *  not (intracellular / TM / signal). */
export type AnchorCompartment =
  | "extracellular"
  | "intracellular"
  | "membrane"
  | "signal"
  | "unknown";

export interface SurfaceBindAnchor {
  siteId: number;
  residue: number;
  compartment: AnchorCompartment;
}

/** A variant the user can switch to via the tab strip above the
 *  canvas. AFDB (isoforms, orthologs), an experimental PDB resolved
 *  at runtime via PDBe + RCSB, or a Schweke et al. 2024 homo-oligomer
 *  AF2 prediction served from a checked-in / Worker-served PDB. */
export type StructureVariant =
  | StructureVariantAfdb
  | StructureVariantExperimental
  | StructureVariantSchwekeHomomer;

interface StructureVariantBase {
  /** Stable key for the React tab list. */
  id: string;
  /** Reader-facing tab label, e.g. "Canonical", "Isoform 2", "Mouse
   *  ortholog", "Experimental". */
  label: string;
  /** Optional secondary text under the label (UniProt acc / PDB id). */
  sublabel?: string;
  /** Per-residue DeepTMHMM topology string (canonical-UniProt-coord). */
  topology: string;
  deeptmhmm_type: StructureViewerData["deeptmhmm_type"];
}

export interface StructureVariantAfdb extends StructureVariantBase {
  source: "afdb";
  /** UniProt accession to fetch from AFDB. Stripped of any isoform
   *  suffix because AFDB models the canonical-acc structure for the
   *  isoform fold too. */
  uniprot_acc: string;
  /** Full UniProt acc including isoform suffix (e.g. "P00533-2"). */
  uniprot_acc_full?: string;
}

/** Schweke et al. 2024 AF2 homo-dimer prediction (Cell 187:999, PMID
 *  38325366). The protein-level call is binary — a protein is a
 *  "candidate complex" when its AF2 dimer interface clears the
 *  logistic-regression dimer_proba threshold — and the structure file
 *  is one of the 8,195 entries in the figshare deposit
 *  ``AF_dimer_models_core.zip`` (DOI 10.6084/m9.figshare.22309177,
 *  share-link only as of 2026-06).
 *
 *  Renderer differs from AFDB / experimental tabs: two chains, distinct
 *  colors (maroon-mid + teal-mid, mirrors the Deliverome palette), no
 *  topology coloring (the homomer view is about the dimer interface,
 *  not which residue is in which compartment). Membrane orientation
 *  via {@link orientPdbForTopology} runs when the model includes TM
 *  residues (multi-pass cases: AQP1, MS4A1/CD20, KCN*, SLC*, GPCRs);
 *  for single-pass ECDs that Schweke's ``nodiso3`` filter clipped to
 *  the soluble domain (CD69, CD28, TFRC, CD3*), orientation is
 *  skipped and the caption flags it as ECD-only. */
export interface StructureVariantSchwekeHomomer extends StructureVariantBase {
  source: "schweke-homomer";
  /** UniProt accession of the homomer subunit. */
  uniprot_acc: string;
  /** Schweke model file URL — typically a static asset path like
   *  ``/data/structures/schweke/{ACC}_V1_{N}.pdb`` checked in under
   *  ``viewer/public/`` (or a future Worker endpoint). */
  pdb_url: string;
  /** AF model number 1-5 — the ``_V1_N`` suffix on the figshare
   *  filename. Display-only. */
  af_model_num: number;
  /** True when Schweke's pipeline trimmed the TM helix as a
   *  disconnected contact cluster (the single-pass ECD-only case).
   *  Drives the "ECD only" caption + skips membrane orientation
   *  because no TM residues are present to align. */
  ecd_only: boolean;
}

export interface StructureVariantExperimental extends StructureVariantBase {
  source: "experimental";
  /** PDBe pick — a `BestStructureCandidate` essentially. The viewer
   *  fetches the PDB file from RCSB at click time and applies the
   *  canonical DeepTMHMM topology coloring with the chain + offset
   *  from this record. */
  pdb_id: string;
  chain_id: string;
  /** PDBe's mapped UniProt residue range covered by this PDB chain. */
  unp_start: number;
  unp_end: number;
  /** PDBe `best_structures` `start`/`end` — these are SEQRES indices
   *  (1-based position within the deposited sequence), NOT author
   *  residue numbers. 3Dmol selects on author resSeq, so they can't be
   *  used as a projection offset directly; the render pipeline derives
   *  the real UniProt→author offset by overlap against the fetched PDB
   *  (see `_bestLinearOffset`). Retained for the clean/dirty span check
   *  and as one offset candidate. */
  pdb_start: number;
  pdb_end: number;
  /** Mapping quality. ``clean`` = the chosen chain maps to UniProt as a
   *  single contiguous segment (span equality), so topology projects via
   *  one linear offset. ``approx`` = the only available structure maps in
   *  multiple discontinuous segments (fusion construct); projection is
   *  piecewise and best-effort, and the caption shows a caveat. */
  mappingMode: "clean" | "approx";
  /** Display-only metadata. */
  experimental_method: string;
  resolution: number | null;
  coverage: number;
}

/** Per-variant AFDB metadata fetched at runtime from
 *  ``alphafold.ebi.ac.uk/api/prediction/{UNIPROT}``. Matches the
 *  subset of fields ``tools/afdb_plddt.py`` reads for the canonical
 *  cohort, but live-fetched here instead of pre-baked. */
interface AfdbVariantMeta {
  latestVersion: number | null;
  // The AlphaFold entry identifier (e.g. ``AF-P00533-F1`` for the
  // canonical, ``AF-P00533-2-F1`` for isoform 2) returned LIVE by the
  // prediction API for the exact accession we asked for. The AFDB
  // entry-page link is built from this so it always lands on the model
  // actually rendered — a bare ``/entry/{acc}`` is NOT a valid AlphaFold
  // entry route (their pages are keyed by entryId, not raw UniProt acc).
  entryId: string | null;
  globalMetricValue: number | null;
  fractionPlddtLow: number;
  fractionPlddtVeryLow: number;
}

/** PDBe `best_structures` API response shape (one entry — the
 *  endpoint returns an object keyed by UniProt acc with an array of
 *  these). We only use a subset of fields; documented for grep-ability. */
interface PDBeBestStructure {
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

/** A contiguous UniProt→PDB-author projection segment. A topology
 *  (UniProt-coord) residue ``u`` in ``[unpLo, unpHi]`` maps to PDB
 *  author resSeq ``u + offset``. Clean structures have a single
 *  segment; fusion constructs have several, each with its own offset. */
interface ProjSegment {
  unpLo: number;
  unpHi: number;
  offset: number;
}

/** Author resSeq values present (ATOM + HETATM) on a chain in the
 *  fetched PDB file — i.e. the residues 3Dmol can actually select.
 *  Used to score candidate projection offsets: the correct offset lands
 *  the most UniProt-mapped residues on real atoms. We can't trust
 *  `best_structures.start` (a SEQRES index) or even PDBe author numbers
 *  (which can diverge from the legacy `.pdb` file RCSB serves, e.g.
 *  EGFR 7syd), so the file itself is the only ground truth. */
function _observedResSeq(pdbText: string, chainId: string): Set<number> {
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
function _overlapCount(
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
function _bestLinearOffset(
  unpLo: number,
  unpHi: number,
  candidates: number[],
  observed: Set<number>,
  fallback: number,
): number {
  let best = fallback;
  let bestScore = _overlapCount(unpLo, unpHi, fallback, observed);
  for (const c of candidates) {
    if (c === fallback) continue;
    const score = _overlapCount(unpLo, unpHi, c, observed);
    if (score > bestScore) {
      best = c;
      bestScore = score;
    }
  }
  return best;
}

/** Build the PDB-author-resSeq → topology(UniProt)-index lookup the
 *  orientation math consumes, inverting the forward ``u → u + offset``
 *  projection used for cartoon coloring. Returns ``null`` for resSeq
 *  outside every segment (unmapped fusion partners, ligands, gaps). */
function _makeResiToTopo(
  segments: ProjSegment[],
): (pdbResi: number) => number | null {
  return (pdbResi: number) => {
    for (const s of segments) {
      const lo = s.unpLo + s.offset;
      const hi = s.unpHi + s.offset;
      if (pdbResi >= lo && pdbResi <= hi) return pdbResi - s.offset;
    }
    return null;
  };
}

/** Raw SIFTS detailed-mapping segment for one chain. ``authorLo`` /
 *  ``authorHi`` are nullable — PDBe omits author numbers for some
 *  entries (GPR75 9xqc returns ``None``/``None``); the offset is then
 *  derived from whichever boundary is present, or from the seqres span. */
interface SiftsRawSegment {
  unpLo: number;
  unpHi: number;
  seqresLo: number;
  authorLo: number | null;
  authorHi: number | null;
}

/** Fetch SIFTS per-segment UniProt↔PDB mappings (``/api/mappings/{pdb}``)
 *  for the chosen chain. Only used on the ``approx`` (fusion) path, where
 *  `best_structures` collapses the discontinuous mapping into one
 *  non-linear span. Returns ``[]`` on any failure so the caller can fall
 *  back to the single-offset projection. */
async function _fetchSiftsSegments(
  pdbId: string,
  uniprotAcc: string,
  chainId: string,
): Promise<SiftsRawSegment[]> {
  try {
    const r = await fetch(
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
function _projSegmentsForDirty(
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
    const offset = _bestLinearOffset(
      s.unpLo, s.unpHi, candidates, observed, authorOffset ?? seqresOffset,
    );
    out.push({ unpLo: s.unpLo, unpHi: s.unpHi, offset });
  }
  return out;
}

/** Subset of the SurfaceomeRecord canonical AFDB struct block.
 *  We only need the fields displayed in the per-variant caption;
 *  declaring just these keeps the prop interface narrow. */
export interface CanonicalStructStats {
  afdb_id: string;
  afdb_version: string;
  ecd_mean_plddt: number;
  ecd_disordered_fraction: number;
  source: string;
}

interface StructureViewerProps {
  data: StructureViewerData;
  geneSymbol: string;
  /** Canonical AFDB stats from
   *  ``rec.deterministic_features.structure``. Drives the caption
   *  on the Canonical variant tab; non-canonical AFDB variants
   *  lazy-fetch their own metadata from AFDB's prediction API
   *  client-side when the user clicks them. */
  canonicalStruct: CanonicalStructStats;
  /** Display name for the gene (e.g. "Epidermal growth factor
   *  receptor"). Shown in the caption when the active variant is
   *  an AlphaFold model — the model has no per-entry title of its
   *  own, so the UniProt protein name stands in. */
  proteinName?: string | null;
  /** SURFACE-Bind anchor-residue overlay. Each entry highlights the
   *  α-carbon of the named residue with a colored sphere + numeric
   *  label (the site index). Pass the array from
   *  ``rec.deterministic_features.surface_bind.sites.map(s =>
   *  ({siteId: s.site_id, residue: s.anchor_residue, compartment:
   *  ...}))``. Empty array = no overlay. SURFACE-Bind only publishes
   *  the patch anchor; nearby contact residues would need binder-PDB
   *  parsing to recover (separate task). */
  surfaceBindAnchors?: SurfaceBindAnchor[];
  /** Optional alternate variants (alt isoforms, mouse / cyno
   *  orthologs). When non-empty, a tab strip renders above the
   *  canvas; clicking a tab swaps the rendered structure to that
   *  variant's AFDB model + topology. Canonical is implied as the
   *  first tab — don't include it in this list. */
  variants?: StructureVariant[];
  /** Optional Schweke et al. 2024 (PMID 38325366) AF2 homo-oligomer
   *  prediction. When non-null, a "Homo-oligomer" tab is rendered
   *  IMMEDIATELY after Canonical and before isoforms / orthologs /
   *  experimental — that ordering matches the biological reading
   *  flow: the canonical fold first, then how two copies of it
   *  assemble, then alternate-isoform / cross-species comparisons. */
  schwekeHomomer?: StructureVariantSchwekeHomomer | null;
}

/** Renderer mode toggle. ``topology`` is the default — full topology
 *  coloring + sphere overlay. ``sites`` washes out the cartoon and
 *  beefs up the spheres so a reader scanning specifically for
 *  SURFACE-Bind sites can see them at a glance against the membrane
 *  + EC/IC labels. */
type ViewMode = "topology" | "sites";

/** Single sphere radius across both modes. Previously sites mode
 *  doubled the radius for emphasis, but the user wanted consistent
 *  ball size so the spatial relationships don't visually shift when
 *  switching modes. 3.2 Å is the compromise — big enough to read
 *  against the cartoon, small enough not to occlude neighbors. */
const SPHERE_RADIUS = 3.2;

/** Collapse a per-residue topology string into per-state [start, end]
 *  ranges (1-indexed, inclusive). Used for variants (isoforms /
 *  orthologs) whose structure-viewer JSON doesn't pre-compute ranges
 *  — they only carry the per-residue string from D1. Canonical uses
 *  the pre-baked ``data.topology_ranges`` because it's the hot path. */
/** Derive the present-states list for the topology legend so it
 *  only shows colors that actually appear on the rendered cartoon.
 *  Mirrors the helper in GeneHeader (previously the only caller). */
function _presentTopologyStates(topology: string): string[] {
  if (!topology) return [];
  const seen = new Set<string>();
  for (const ch of topology) seen.add(ch);
  return ["M", "O", "I", "S", "B"].filter((s) => seen.has(s));
}

/** Derive the per-compartment count map for the sites-mode legend.
 *  Each compartment's chip shows "(N)" so the reader sees both
 *  what's there AND how many of each at a glance. A gene with all-
 *  EC sites still gets a single "(N)" chip; absent compartments
 *  don't render. */
function _presentSitesCompartments(
  anchors: SurfaceBindAnchor[],
): Array<{ compartment: AnchorCompartment; count: number }> {
  const counts = new Map<AnchorCompartment, number>();
  for (const a of anchors) {
    counts.set(a.compartment, (counts.get(a.compartment) ?? 0) + 1);
  }
  return (
    ["extracellular", "intracellular", "membrane", "signal", "unknown"] as const
  )
    .filter((c) => counts.has(c))
    .map((compartment) => ({
      compartment,
      count: counts.get(compartment) ?? 0,
    }));
}

/** Human-readable label for each AnchorCompartment value. Mirrors
 *  the SurfaceBindCard 'Side' column glyphs (EC / IC / TM / SP / ?)
 *  with the longer reader-facing word. */
const COMPARTMENT_LEGEND_LABEL: Record<AnchorCompartment, string> = {
  extracellular: "Extracellular",
  intracellular: "Intracellular",
  membrane: "TM region",
  signal: "Signal peptide",
  unknown: "Unknown",
};

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
function _pickPdbChain(
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

/** Parse the TITLE block out of a PDB file. PDB TITLE records have a
 *  fixed-width header (cols 1-6 = "TITLE ", col 9-10 = continuation
 *  number) and the title text starts at col 11. Multi-line TITLE
 *  blocks concatenate; we join with a single space and collapse runs
 *  of whitespace. Returns ``null`` when no TITLE record is present
 *  (rare for RCSB-served PDBs but defensive). */
function _parsePdbTitle(pdb: string): string | null {
  const lines: string[] = [];
  for (const raw of pdb.split("\n")) {
    if (raw.startsWith("TITLE")) {
      // Cols 11+ carry the text content. .slice(10) strips the
      // record name + continuation number; .trim() handles the
      // PDB's space-padded right edge.
      lines.push(raw.slice(10).trim());
    } else if (lines.length > 0) {
      // TITLE block always contiguous; bail on first non-TITLE.
      break;
    }
  }
  if (lines.length === 0) return null;
  const joined = lines.join(" ").replace(/\s+/g, " ").trim();
  // PDB TITLEs are all caps by convention; sentence-case the result
  // so the caption reads as prose rather than shouting.
  return _sentenceCase(joined);
}

/** Lowercase the title and capitalize sentence starts. Preserves
 *  ALL-CAPS tokens longer than 4 chars (likely acronyms — EGFR,
 *  GRP78) and keeps roman numerals + chemical names in their
 *  original case where reasonably possible. Heuristic — fine for
 *  visual readability, not for indexing. */
function _sentenceCase(s: string): string {
  const lower = s.toLowerCase();
  // Capitalize first letter only — keeping most acronyms in lower
  // case is worse than uniformly lower, since the prose then reads
  // naturally and the reader recognizes gene names from context.
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

/** pLDDT tone bucket. Mirrors the canonical fetcher's
 *  ``ecd_mean_plddt`` interpretation: ≥90 success, ≥70 teal,
 *  ≥50 amber, <50 danger. */
function _plddtTone(p: number): "success" | "teal" | "amber" | "danger" {
  if (p >= 90) return "success";
  if (p >= 70) return "teal";
  if (p >= 50) return "amber";
  return "danger";
}

/** Build the per-variant caption JSX. Separated out of the main
 *  component for legibility — three distinct shapes:
 *  - canonical AFDB: pLDDT + disordered (from prop) + AFDB link
 *  - other AFDB:     same but lazy-fetched + ECD-disordered hidden
 *                    (variant doesn't have ECD-restricted metrics)
 *  - experimental:   PDB title + method/resolution + RCSB link */
function _renderCaption(args: {
  activeVariant: StructureVariant | null;
  canonicalStruct: CanonicalStructStats;
  proteinName?: string | null;
  canonicalUniprot: string;
  afdbMetaByAcc: Record<string, AfdbVariantMeta | "loading" | "error">;
  pdbTitles: Record<string, string>;
}) {
  const {
    activeVariant, canonicalStruct, proteinName, canonicalUniprot,
    afdbMetaByAcc, pdbTitles,
  } = args;

  // ---- Schweke homo-oligomer branch ----
  if (activeVariant?.source === "schweke-homomer") {
    const v = activeVariant;
    const figshareUrl = "https://figshare.com/s/af3c1d5969f7468f2caa";
    return (
      <div className={styles.caption} aria-label="Structure caption">
        <p className={styles.captionTitle}>
          Predicted homo-dimer · two copies of {proteinName ?? canonicalUniprot}
        </p>
        <p className={styles.captionStats}>
          <span className={styles.captionStat}>
            {CITATIONS.schwekeHomomer.authorYear} (PMID{" "}
            <a
              href={pubmedUrl(CITATIONS.schwekeHomomer.pmid)}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.captionLink}
            >
              {CITATIONS.schwekeHomomer.pmid}
            </a>
            )
          </span>
          <span className={styles.captionSep} aria-hidden="true">·</span>
          <span className={styles.captionStat}>
            AF2 dimer · model{" "}
            <strong>{v.uniprot_acc}_V1_{v.af_model_num}</strong>
          </span>
          <span className={styles.captionSep} aria-hidden="true">·</span>
          <span className={styles.captionStat}>candidate complex</span>
          <span className={styles.captionSep} aria-hidden="true">·</span>
          <a
            href={figshareUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.captionLink}
          >
            figshare deposit ↗
          </a>
        </p>
        {v.ecd_only ? (
          <p className={styles.captionCaveat}>
            ECD only — Schweke's <code>nodiso3</code> contact-clustering
            filter dropped the single-pass TM helix as a disconnected
            cluster, so the model shows the soluble extracellular dimer
            interface only (no membrane orientation). For multi-pass
            membrane proteins, all TMs are retained and the homomer
            renders embedded in the bilayer.
          </p>
        ) : null}
      </div>
    );
  }

  // ---- Experimental branch ----
  if (activeVariant?.source === "experimental") {
    const v = activeVariant;
    const title = pdbTitles[v.pdb_id];
    const rcsbUrl = `https://www.rcsb.org/structure/${v.pdb_id.toUpperCase()}`;
    const resLabel =
      typeof v.resolution === "number" && Number.isFinite(v.resolution)
        ? `${v.resolution.toFixed(1)} Å`
        : "—";
    return (
      <div className={styles.caption} aria-label="Structure caption">
        {title ? (
          <p className={styles.captionTitle}>{title}</p>
        ) : null}
        <p className={styles.captionStats}>
          <span className={styles.captionStat}>{v.experimental_method}</span>
          <span className={styles.captionSep} aria-hidden="true">·</span>
          <span className={styles.captionStat}>
            Resolution <strong>{resLabel}</strong>
          </span>
          <span className={styles.captionSep} aria-hidden="true">·</span>
          <span className={styles.captionStat}>
            Chain <strong>{v.chain_id}</strong>
          </span>
          <span className={styles.captionSep} aria-hidden="true">·</span>
          <a
            href={rcsbUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.captionLink}
          >
            RCSB {v.pdb_id.toUpperCase()} ↗
          </a>
          <span className={styles.captionSep} aria-hidden="true">·</span>
          <InfoTip
            wide
            align="end"
            label="How the experimental structure is chosen"
          >
            {tooltips.experimental_best_structure}
          </InfoTip>
        </p>
        {v.mappingMode === "approx" ? (
          <p className={styles.captionCaveat}>
            This chain maps to {proteinName ?? canonicalUniprot} in multiple
            discontinuous segments (a fusion or engineered construct), so the
            topology coloring is projected piecewise and is approximate near
            segment boundaries.
          </p>
        ) : null}
      </div>
    );
  }

  // ---- AFDB branch (canonical OR variant) ----
  const isCanonical = activeVariant === null;
  const acc = isCanonical
    ? canonicalUniprot
    : (activeVariant as StructureVariantAfdb).uniprot_acc;
  const accFull = isCanonical
    ? canonicalUniprot
    : ((activeVariant as StructureVariantAfdb).uniprot_acc_full ?? acc);
  // AlphaFold entry pages are keyed by entryId (``AF-{acc}-F1``), NOT a
  // bare UniProt acc — ``/entry/P00533`` is not a real route. Prefer the
  // LIVE entryId fetched from the prediction API for this exact accession
  // (``AF-P00533-F1`` canonical, ``AF-P00533-2-F1`` for isoform 2). While
  // it's still loading, derive the identical form from the live accession
  // — ``AF-{accFull}-F1`` reproduces the entryId for single-fragment
  // models. We never fall back to the baked ``structure.afdb_id``.
  const liveMetaForUrl = afdbMetaByAcc[accFull];
  const liveEntryId =
    liveMetaForUrl
      && liveMetaForUrl !== "loading"
      && liveMetaForUrl !== "error"
      ? liveMetaForUrl.entryId
      : null;
  const afdbUrl =
    `https://alphafold.ebi.ac.uk/entry/${liveEntryId ?? `AF-${accFull}-F1`}`;

  // Stats: canonical reuses the prop; variants use the live-fetched
  // map (loading / error / data shapes).
  let plddtNode: ReactNode = null;
  let disorderedNode: ReactNode = null;
  let versionLabel = "";
  if (isCanonical) {
    const placeholder = canonicalStruct.source
      .toLowerCase()
      .includes("placeholder");
    const wholeProtein = !placeholder
      && canonicalStruct.source.toLowerCase().includes("whole-protein");
    // Version label: LIVE AFDB latestVersion ONLY (fetched by the effect
    // below, keyed on the canonical acc). The baked `afdb_version` freezes
    // at build time, so a gene whose AFDB model was bumped after its last
    // annotate run would show a stale version (e.g. EGFR P00533 baked "v4"
    // while AFDB serves v6). We do NOT fall back to the baked value at all
    // — if the live fetch is still loading or errored, the version chip is
    // simply omitted rather than risk showing a stale number. Mirrors the
    // variant branch (which has always read `meta.latestVersion` only).
    const canonMeta = afdbMetaByAcc[accFull];
    versionLabel =
      canonMeta && canonMeta !== "loading" && canonMeta !== "error"
        && canonMeta.latestVersion
        ? `v${canonMeta.latestVersion}`
        : "";
    if (placeholder) {
      plddtNode = <StatusPill tone="neutral" size="sm">pending</StatusPill>;
    } else {
      plddtNode = (
        <StatusPill tone={_plddtTone(canonicalStruct.ecd_mean_plddt)} size="sm">
          {wholeProtein ? "Whole" : "ECD"} pLDDT{" "}
          <strong>{canonicalStruct.ecd_mean_plddt.toFixed(1)}</strong>
          {/* InfoTip rendered INSIDE the pill so the ⓘ glyph sits
              next to the value rather than floating as a separate
              chip beside it (matches the inline-badge pattern user
              standardized on). */}
          <InfoTip wide label="About AlphaFold pLDDT">
            {tooltips.afdb_plddt}
          </InfoTip>
        </StatusPill>
      );
    }
    // Disordered % is shown for BOTH ECD-restricted and whole-protein
    // canonical cases — the schema field `ecd_disordered_fraction` is
    // populated in both (with the threshold-based ECD count for
    // proper ECD proteins, and the fetcher's whole-protein global
    // metric for GLOB/soluble-cytoplasmic). Previously hidden for
    // whole-protein to avoid the appearance of comparability with the
    // ECD-restricted number — but the InfoTip below now spells the
    // difference out, and hiding it created an inconsistency with the
    // isoform tabs (which always show whole-protein disordered).
    if (!placeholder) {
      disorderedNode = (
        <span className={styles.captionStat}>
          Disordered{" "}
          <strong>{(canonicalStruct.ecd_disordered_fraction * 100).toFixed(0)}%</strong>
        </span>
      );
    }
  } else {
    // Read with the isoform-suffixed key — the lazy-fetch effect
    // caches per accFull (P00533-2, P00533-3, ...) so each isoform
    // shows its OWN pLDDT, not the canonical's.
    const meta = afdbMetaByAcc[accFull];
    if (meta === "loading" || meta === undefined) {
      plddtNode = <StatusPill tone="neutral" size="sm">loading…</StatusPill>;
    } else if (meta === "error") {
      plddtNode = <StatusPill tone="neutral" size="sm">unavailable</StatusPill>;
    } else {
      versionLabel = meta.latestVersion ? `v${meta.latestVersion}` : "";
      if (typeof meta.globalMetricValue === "number") {
        plddtNode = (
          <StatusPill tone={_plddtTone(meta.globalMetricValue)} size="sm">
            Whole pLDDT{" "}
            <strong>{meta.globalMetricValue.toFixed(1)}</strong>
            <InfoTip wide label="About AlphaFold pLDDT">
              {tooltips.afdb_plddt}
            </InfoTip>
          </StatusPill>
        );
        const lowFrac = meta.fractionPlddtLow + meta.fractionPlddtVeryLow;
        disorderedNode = (
          <span className={styles.captionStat}>
            Disordered{" "}
            <strong>{(lowFrac * 100).toFixed(0)}%</strong>
          </span>
        );
      }
    }
  }

  const label = isCanonical
    ? "AlphaFold model"
    : `AlphaFold model · ${(activeVariant as StructureVariantAfdb).label}`;
  // proteinName / captionTitle was removed from the canonical AFDB
  // branch — the gene symbol is already the page's h1, so repeating
  // the protein descriptor in the structure caption was visual noise.
  // The Experimental tab still gets its PDB title (different shape:
  // the title there describes the specific snapshot, not the protein).
  return (
    <div className={styles.caption} aria-label="Structure caption">
      <p className={styles.captionStats}>
        <span className={styles.captionStat}>{label}</span>
        {plddtNode ? (
          <>
            <span className={styles.captionSep} aria-hidden="true">·</span>
            {/* InfoTip is rendered INSIDE the StatusPill (see the
                plddtNode construction above) so the ⓘ sits next to
                the value rather than as a separate adjacent chip.
                Matches the inline-badge tooltip pattern. */}
            <span className={styles.captionStat}>{plddtNode}</span>
          </>
        ) : null}
        {disorderedNode ? (
          <>
            <span className={styles.captionSep} aria-hidden="true">·</span>
            <span className={styles.captionStat}>
              {disorderedNode}
              <InfoTip wide label="About disordered fraction">
                {tooltips.afdb_disordered}
              </InfoTip>
            </span>
          </>
        ) : null}
        <span className={styles.captionSep} aria-hidden="true">·</span>
        <a
          href={afdbUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.captionLink}
        >
          AFDB {accFull}
          {versionLabel ? ` · ${versionLabel}` : ""} ↗
        </a>
      </p>
    </div>
  );
}

function _computeTopologyRanges(
  topology: string,
): Record<"M" | "O" | "I" | "S" | "B", [number, number][]> {
  const out: Record<string, [number, number][]> = {
    M: [], O: [], I: [], S: [], B: [],
  };
  if (!topology) return out as ReturnType<typeof _computeTopologyRanges>;
  let state = topology.charAt(0);
  let start = 1;
  for (let i = 1; i < topology.length; i += 1) {
    const ch = topology.charAt(i);
    if (ch !== state) {
      if (state in out) out[state].push([start, i]);
      state = ch;
      start = i + 1;
    }
  }
  if (state in out) out[state].push([start, topology.length]);
  return out as ReturnType<typeof _computeTopologyRanges>;
}

/** Compartment glyph rendered as a suffix on the 3D label and in the
 *  table. Short forms keep the label box compact at the typical 3D
 *  zoom level. */
const COMPARTMENT_GLYPH: Record<AnchorCompartment, string> = {
  extracellular: "EC",
  intracellular: "IC",
  membrane: "M",
  signal: "S",
  unknown: "?",
};

/** Single anchor color for "topology" mode — one purple across all
 *  sites. Previously we used a discrete categorical palette so each
 *  site got a distinct color, but in practice the per-sphere number
 *  label + the table's "Site" column are enough to distinguish them
 *  and the categorical palette made the cluster visually noisy.
 *  Purple chosen to contrast both the topology cartoon (pale green /
 *  yellow / gray) and the brand maroon used elsewhere on the page. */
const ANCHOR_COLOR = "#7A4BD8";

/** Per-compartment sphere color for "sites" mode. EC = purple (brand
 *  lavender, the "look here / focus" color); IC = green (safely tucked
 *  away inside the cell); signal peptide = red; TM = gray (inside the
 *  membrane); unknown = mute. The SurfaceBindCard "Side" column uses the
 *  same mapping for visual consistency between the 3D view and the table. */
const COMPARTMENT_COLOR: Record<AnchorCompartment, string> = {
  extracellular: "#8878C8", // lavender-bright (brand purple)
  intracellular: "#16A34A", // green-600
  membrane: "#94A3B8", // slate-400
  signal: "#DD5955", // red (matches topology cartoon)
  unknown: "#6B7280", // gray-500
};

type LoadStatus = "loading" | "ready" | "error" | "nomodel";

interface ViewerInstance {
  clear: () => void;
  resize: () => void;
  render: () => void;
  zoomTo: (sel?: object) => void;
  /** 3Dmol camera-pose snapshot: a number array encoding
   *  position + rotation + zoom. Used to seed `setView` on reset so
   *  the ↺ button returns to the initial pose, not just the initial
   *  zoom (`zoomTo({})` alone re-frames but leaves any accumulated
   *  user rotation in place). */
  getView: () => number[];
  setView: (view: number[]) => void;
  addStyle?: (sel: object, style: object) => void;
  addLabel?: (text: string, options: object) => unknown;
  removeAllLabels?: () => void;
}

/** Slab transparency. 0.34 is heavy enough to read as a clear
 *  membrane band from across the room without obscuring the helices
 *  it's wrapped around. */
const MEMBRANE_OPACITY = 0.34;

/** Chain-A color on the Schweke homo-oligomer tab. Maroon-mid from
 *  the Deliverome design tokens — pairs with the page accent. */
const SCHWEKE_CHAIN_A_COLOR = "#922038";
/** Chain-B color on the Schweke homo-oligomer tab. Teal-mid — the
 *  high-contrast complement to maroon in the brand palette. */
const SCHWEKE_CHAIN_B_COLOR = "#3d6b60";

/**
 * StructureViewer — the 3Dmol.js-backed canvas. Client-only because
 * 3Dmol expects a DOM + WebGL. The 3Dmol module is dynamically
 * imported on mount so the 524 KB library only lands on per-gene
 * pages (not the catalog index). Auto-loads — no click-to-show
 * gate — so the viewer reads as part of the gene-identity surface
 * rather than a hidden affordance.
 */
export function StructureViewer({
  data,
  geneSymbol,
  canonicalStruct,
  proteinName,
  surfaceBindAnchors = [],
  variants = [],
  schwekeHomomer = null,
}: StructureViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<ViewerInstance | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  /** Camera-pose snapshot captured after the first render, refreshed
   *  on container resize. The reset button restores this pose so a
   *  rotation-only manipulation also gets undone — previously the
   *  button called `zoomTo({})` alone, which leaves rotation as-is. */
  const initialViewRef = useRef<number[] | null>(null);
  const [status, setStatus] = useState<LoadStatus>("loading");
  const [errorMsg, setErrorMsg] = useState<string>("");
  // Default to ``topology`` — the topology-colored cartoon is the
  // canonical "what does this protein look like in context" view.
  // ``sites`` is the user-requested "show me SURFACE-Bind sites at a
  // glance" mode; only useful when surfaceBindAnchors has entries.
  const [viewMode, setViewMode] = useState<ViewMode>("topology");
  // Active variant index. ``0`` = canonical (from ``data``); higher
  // indices map into the ``variants`` array. SURFACE-Bind anchors
  // only render on the canonical view — they're keyed to canonical
  // residue numbering, which doesn't align with isoform / ortholog
  // sequences once alternative splicing or species differences
  // shift positions.
  const [variantIdx, setVariantIdx] = useState<number>(0);
  // Per-AFDB-accession availability (canonical + isoform/ortholog
  // variants), probed on mount. `false` ⟹ AFDB has no model for that
  // protein (e.g. megalin/LRP2, beyond AFDB's per-entry size limit) — its
  // tab is grayed and, for the canonical, the viewer defaults to an
  // experimental structure instead. `"loading"` while the probe is in
  // flight; absent key ⟹ not probed (treated as available).
  const [afdbAvail, setAfdbAvail] = useState<
    Record<string, boolean | "loading">
  >({});
  // Set once the reader manually picks a tab (or the auto-default fires)
  // so the auto-default-to-experimental doesn't fight a manual selection.
  const userPickedRef = useRef(false);
  // Stale-render guard counter (see renderViewer): bumped each invocation
  // so a superseded async render can't clobber the current one's status.
  const renderSeqRef = useRef(0);
  // PDBe `best_structures` lookup — fires on mount per gene. When a
  // top experimental candidate is available, an extra "Experimental"
  // variant is appended to the tabs at render time. Three states:
  //   "loading" — request in flight
  //   PDBeBestStructure — top candidate (we use index 0 of the array)
  //   null — no candidate (gene has no PDB / PDBe API error / 404)
  const [pdbeCandidate, setPdbeCandidate] = useState<
    PDBeBestStructure | "loading" | null
  >("loading");
  // PDB TITLE record parsed out of the most-recently-fetched
  // experimental PDB. Keyed on pdb_id so switching between two
  // experimental structures correctly updates the caption.
  const [pdbTitles, setPdbTitles] = useState<Record<string, string>>({});
  // AFDB metadata (pLDDT, disordered fraction, latestVersion) per
  // UniProt acc — populated lazily when the user clicks a
  // non-canonical AFDB variant. Canonical uses `canonicalStruct`
  // (already on the prop) and doesn't go through this map.
  const [afdbMetaByAcc, setAfdbMetaByAcc] = useState<
    Record<string, AfdbVariantMeta | "loading" | "error">
  >({});

  // SURFACE-Bind sphere overlay only makes sense on the canonical
  // AFDB view — anchor residues are canonical-UniProt-keyed and
  // don't translate to isoforms / orthologs / chain-restricted PDBs.
  // If the user clicks an isoform / ortholog / experimental tab
  // while in sites mode, the canvas would just show a gray cartoon
  // with no spheres. Revert to topology mode automatically so the
  // variant view is informative.
  useEffect(() => {
    if (variantIdx !== 0 && viewMode === "sites") {
      setViewMode("topology");
    }
  }, [variantIdx, viewMode]);

  useEffect(() => {
    let cancelled = false;
    async function fetchPDBe() {
      try {
        const r = await fetch(
          `https://www.ebi.ac.uk/pdbe/api/mappings/best_structures/${data.uniprot_acc}`,
          { cache: "force-cache" },
        );
        if (!r.ok) {
          if (!cancelled) setPdbeCandidate(null);
          return;
        }
        const j = (await r.json()) as Record<string, PDBeBestStructure[]>;
        const candidates = j[data.uniprot_acc] ?? [];
        if (candidates.length === 0) {
          if (!cancelled) setPdbeCandidate(null);
          return;
        }
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
        const isClean = (c: PDBeBestStructure) =>
          c.end - c.start === c.unp_end - c.unp_start;
        let chosen = top;
        if (!isClean(top)) {
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
              isClean(c) &&
              c.coverage >= top.coverage - COVERAGE_TOL &&
              (c.resolution == null ||
                top.resolution == null ||
                c.resolution <= top.resolution + RES_TOL),
          );
          if (cleanAlt) chosen = cleanAlt;
        }
        if (!cancelled) setPdbeCandidate(chosen);
      } catch {
        if (!cancelled) setPdbeCandidate(null);
      }
    }
    fetchPDBe();
    return () => { cancelled = true; };
  }, [data.uniprot_acc]);

  // Probe AFDB availability for the canonical + every AFDB variant
  // (isoforms / orthologs) on mount, so tabs whose protein AFDB doesn't
  // model can be grayed up front and the viewer can default to an
  // experimental structure rather than opening on a blank "no model" tab.
  // Prediction-API responses are cached aggressively by AFDB (force-cache).
  useEffect(() => {
    let cancelled = false;
    const accs = Array.from(
      new Set([
        data.uniprot_acc,
        ...variants
          .filter((v): v is StructureVariantAfdb => v.source === "afdb")
          .map((v) => v.uniprot_acc),
      ]),
    );
    setAfdbAvail(Object.fromEntries(accs.map((a) => [a, "loading" as const])));
    (async () => {
      const entries = await Promise.all(
        accs.map(async (acc): Promise<[string, boolean]> => {
          try {
            const r = await fetch(alphafoldPredictionApiUrl(acc), {
              cache: "force-cache",
            });
            return [acc, r.ok];
          } catch {
            // Network hiccup — don't gray it out; the per-tab render
            // will still surface a genuine failure if one occurs.
            return [acc, true];
          }
        }),
      );
      if (!cancelled) setAfdbAvail(Object.fromEntries(entries));
    })();
    return () => {
      cancelled = true;
    };
    // Variant identity is captured by the joined-id key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.uniprot_acc, variants.map((v) => v.id).join(",")]);

  // Effective variants =
  //   Schweke homo-oligomer (if any) +
  //   caller-provided (isoforms / orthologs) +
  //   experimental (when PDBe has a hit).
  // Ordering: Schweke right after Canonical → isoforms / orthologs →
  // experimental last. Mirrors the biological reading flow: how the
  // canonical fold assembles into a complex, then alternate-isoform /
  // cross-species comparisons, then the experimental ground truth.
  const effectiveVariants: StructureVariant[] = useMemo(() => {
    const v: StructureVariant[] = [];
    if (schwekeHomomer) v.push(schwekeHomomer);
    v.push(...variants);
    if (pdbeCandidate && pdbeCandidate !== "loading") {
      v.push({
        source: "experimental",
        id: `exp-${pdbeCandidate.pdb_id}-${pdbeCandidate.chain_id}`,
        label: "Experimental",
        sublabel: `${pdbeCandidate.pdb_id.toUpperCase()} · ${pdbeCandidate.chain_id}`,
        // Reuse canonical topology — DeepTMHMM coords are UniProt-
        // keyed and PDBe gives us the offset to project them onto
        // the PDB chain.
        topology: data.topology,
        deeptmhmm_type: data.deeptmhmm_type,
        pdb_id: pdbeCandidate.pdb_id,
        chain_id: pdbeCandidate.chain_id,
        unp_start: pdbeCandidate.unp_start,
        unp_end: pdbeCandidate.unp_end,
        pdb_start: pdbeCandidate.start,
        pdb_end: pdbeCandidate.end,
        // Span equality ⟹ single contiguous segment ⟹ clean linear
        // projection. The selection cascade already prefers a clean
        // structure when one is comparable, so ``approx`` only sticks
        // when the gene's *only* structure is a fusion construct.
        mappingMode:
          pdbeCandidate.end - pdbeCandidate.start ===
          pdbeCandidate.unp_end - pdbeCandidate.unp_start
            ? "clean"
            : "approx",
        experimental_method: pdbeCandidate.experimental_method,
        resolution: pdbeCandidate.resolution,
        coverage: pdbeCandidate.coverage,
      });
    }
    return v;
  }, [
    variants,
    schwekeHomomer,
    pdbeCandidate,
    data.topology,
    data.deeptmhmm_type,
  ]);

  const isCanonicalActive = variantIdx === 0;
  const activeVariant: StructureVariant | null = isCanonicalActive
    ? null
    : effectiveVariants[variantIdx - 1] ?? null;
  const isExperimentalActive = activeVariant?.source === "experimental";
  const isSchwekeActive = activeVariant?.source === "schweke-homomer";
  // The uniprot_acc / topology / type used by the render pipeline.
  // For experimental view, ``activeUniprot`` is unused (we fetch
  // RCSB by pdb_id instead) — keep canonical for the aria-label.
  const activeUniprot =
    activeVariant && activeVariant.source === "afdb"
      ? activeVariant.uniprot_acc
      : data.uniprot_acc;
  const activeTopology = activeVariant?.topology ?? data.topology;
  const activeDeepTMHMMType =
    activeVariant?.deeptmhmm_type ?? data.deeptmhmm_type;
  // SURFACE-Bind anchor overlay only fires on canonical-AFDB view:
  // (1) anchor residue numbers are canonical-UniProt-keyed, don't
  // translate to isoforms or orthologs; (2) on experimental tabs
  // the chain is restricted + residues may be missing from the
  // crystal, so anchor spheres would mis-render.
  const hasAnchors = surfaceBindAnchors.length > 0 && isCanonicalActive;

  // Canonical-AFDB availability — drives graying its tab.
  const canonAfdbUnavail = afdbAvail[data.uniprot_acc] === false;

  // Default to the Experimental tab when AFDB has no model for the
  // canonical protein but an experimental structure exists, so the viewer
  // opens on a real structure (e.g. megalin's cryo-EM 9CWM) instead of a
  // blank "no model" canonical view. Fires once; a manual tab pick opts out.
  useEffect(() => {
    if (userPickedRef.current) return;
    if (afdbAvail[data.uniprot_acc] !== false) return;
    const expIdx = effectiveVariants.findIndex(
      (v) => v.source === "experimental",
    );
    if (expIdx >= 0) {
      userPickedRef.current = true;
      setVariantIdx(expIdx + 1);
    }
  }, [afdbAvail, effectiveVariants, data.uniprot_acc]);

  // Lazy-fetch AFDB metadata when the user clicks a non-canonical
  // AFDB variant (isoform / ortholog). One fetch per isoform-suffixed
  // acc — AFDB has distinct predictions for canonical (P00533, pLDDT
  // 75.94) AND each isoform (P00533-2 pLDDT 90.38, P00533-3 pLDDT 85.0,
  // P00533-4 pLDDT 90.12 for EGFR), so we MUST key the cache + fetch
  // URL on the isoform-suffixed acc — keying on the base acc would
  // surface the canonical's pLDDT for every isoform tab. The base
  // ``uniprot_acc`` field stays on the variant for the 3D-render
  // pipeline (which still pulls the canonical PDB when an isoform
  // doesn't have its own model file); the AFDB caption metadata is
  // the only place that needs the suffixed acc.
  //
  // CRITICAL: ``afdbMetaByAcc`` is intentionally NOT in the dep array.
  // The effect WRITES to that state ("loading" first, then the result
  // or "error"). If it were a dependency, the "loading" setState would
  // re-trigger the effect, the cleanup would set ``cancelled = true``
  // on the prior closure, and the in-flight fetch's setState would be
  // silently dropped — so the caption would say "loading…" forever.
  // The functional setState reads the latest cache via ``prev``, so
  // stale-closure reads here are harmless: the early-return guard
  // (``acc in afdbMetaByAcc``) is just a fast-path; if it's wrong, the
  // worst case is one extra fetch that's deduped by HTTP cache anyway.
  useEffect(() => {
    // Resolve which AFDB accession needs metadata:
    //   - no variant active  → the canonical UniProt (so the canonical
    //     caption can show the LIVE latestVersion instead of the stale
    //     baked `afdb_version`);
    //   - an AFDB variant tab → that variant's (isoform-suffixed) acc;
    //   - the experimental tab → none (RCSB has no AFDB metadata).
    let accCandidate: string | null;
    if (!activeVariant) {
      accCandidate = data.uniprot_acc;
    } else if (activeVariant.source === "afdb") {
      accCandidate =
        activeVariant.uniprot_acc_full ?? activeVariant.uniprot_acc;
    } else {
      return;
    }
    if (!accCandidate || accCandidate in afdbMetaByAcc) return;
    // const so the narrowed-to-string value is captured by the async
    // closure below (a `let` would widen back to `string | null` there).
    const acc = accCandidate;
    let cancelled = false;
    setAfdbMetaByAcc((prev) => ({ ...prev, [acc]: "loading" }));
    (async () => {
      try {
        const r = await fetch(
          `https://alphafold.ebi.ac.uk/api/prediction/${acc}`,
          { cache: "force-cache" },
        );
        if (!r.ok) throw new Error(`AFDB API ${r.status}`);
        const j = (await r.json()) as Array<{
          uniprotAccession?: string;
          entryId?: string;
          latestVersion?: number;
          globalMetricValue?: number;
          fractionPlddtLow?: number;
          fractionPlddtVeryLow?: number;
        }>;
        // The /api/prediction/{acc} endpoint accepts isoform-suffixed
        // accs AND base accs. For an isoform-suffixed acc the array
        // contains a single matching entry; for a base acc the array
        // can carry canonical PLUS each modelled isoform. Pick the
        // entry whose ``uniprotAccession`` matches what we asked for
        // (defensive: tolerates either response shape).
        const entry = j.find((e) => e.uniprotAccession === acc) ?? j[0];
        if (!entry) throw new Error("empty AFDB response");
        if (cancelled) return;
        setAfdbMetaByAcc((prev) => ({
          ...prev,
          [acc]: {
            latestVersion: entry.latestVersion ?? null,
            entryId: entry.entryId ?? null,
            globalMetricValue: entry.globalMetricValue ?? null,
            fractionPlddtLow: entry.fractionPlddtLow ?? 0,
            fractionPlddtVeryLow: entry.fractionPlddtVeryLow ?? 0,
          },
        }));
      } catch {
        if (cancelled) return;
        setAfdbMetaByAcc((prev) => ({ ...prev, [acc]: "error" }));
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeVariant, data.uniprot_acc]);

  const renderViewer = useCallback(async () => {
    if (!containerRef.current) return;
    // Bump + capture a render token. A renderViewer for one variant can
    // still be mid-fetch when the active variant changes — notably the
    // auto-default canonical → Experimental, which fires AFTER canonical's
    // AFDB 404 is already in flight. Each terminal setStatus below bails if
    // a newer render has started, so the late canonical run can't overwrite
    // the Experimental render's "ready" with "nomodel".
    const renderSeq = ++renderSeqRef.current;
    setStatus("loading");
    setErrorMsg("");
    try {
      // 3dmol ships as CommonJS; depending on bundler the named-export
      // shape can be either ``Mod.createViewer`` or
      // ``Mod.default.createViewer``. Handle both.
      type Mod3D = typeof import("3dmol");
      const Mod = (await import("3dmol")) as Mod3D & { default?: Mod3D };
      const $3Dmol: Mod3D = Mod.default ?? Mod;
      // Branch on which variant flavor is active:
      //   - schweke-homomer  → fetch the AF2 dimer PDB from a static
      //     asset URL (committed under viewer/public/data/structures/
      //     schweke/, or a future Worker endpoint) and short-circuit
      //     the topology-projection / SURFACE-Bind paths below — the
      //     homomer view is its own visualization (chain A / chain B
      //     duotone, optional membrane slab when TMs are in the model).
      //   - experimental    → fetch by PDB id through RCSB; PDBe gives
      //     us the chain + UniProt→author offset to project canonical
      //     DeepTMHMM topology onto the (potentially partial, chain-
      //     restricted) PDB residue numbering.
      //   - AFDB (default)  → fetch by UniProt acc through AFDB DB.
      let rawPdb: string;
      const schwekeVariant = isSchwekeActive
        ? (activeVariant as StructureVariantSchwekeHomomer)
        : null;
      const expVariant = isExperimentalActive
        ? (activeVariant as StructureVariantExperimental)
        : null;
      if (schwekeVariant) {
        const resp = await fetch(schwekeVariant.pdb_url, {
          cache: "force-cache",
        });
        if (!resp.ok) {
          throw new Error(
            `Schweke homomer PDB returned ${resp.status} for ${schwekeVariant.pdb_url}`,
          );
        }
        rawPdb = await resp.text();
      } else if (expVariant) {
        // RCSB returns the PDB file directly. Aggressive caching is
        // fine — PDB entries are immutable per release.
        const rcsbUrl = `https://files.rcsb.org/download/${expVariant.pdb_id}.pdb`;
        const resp = await fetch(rcsbUrl, { cache: "force-cache" });
        if (!resp.ok) {
          throw new Error(
            `RCSB returned ${resp.status} for ${expVariant.pdb_id}`,
          );
        }
        rawPdb = await resp.text();
        // Parse the TITLE record once per PDB and cache so re-renders
        // (mode toggle, etc.) don't re-parse.
        if (!(expVariant.pdb_id in pdbTitles)) {
          const title = _parsePdbTitle(rawPdb);
          if (title) {
            setPdbTitles((prev) => ({ ...prev, [expVariant.pdb_id]: title }));
          }
        }
      } else {
        // URL resolution strategy:
        //   - Canonical view with a baked `data.pdb_url` → use it
        //     directly (the build script wrote a version-correct URL
        //     via the prediction API at build time).
        //   - Anything else (canonical with no baked URL, or any
        //     non-canonical AFDB variant tab) → resolve via the
        //     prediction API first. Previously this fell back to
        //     `alphafoldPdbUrl(acc)`, which used the helper's
        //     `version="v4"` default and ate a 404 before retrying
        //     through the prediction API. The console saw a noisy
        //     `AF-{acc}-F1-model_v4.pdb 404 (Not Found)` on every
        //     gene whose AFDB model had been bumped past v4 (EGFR,
        //     GPR75, …). Prediction-API-first is one extra ~1 KB
        //     cached JSON fetch — cheaper than a 404 + retry, and
        //     silent. The helper's default is now pinned to
        //     LATEST_KNOWN_AFDB_VERSION (v6 as of 2025-08) so even
        //     the "prediction API down + no baked URL" fallback
        //     lands on a current-ish file.
        let pdbUrl: string | null = isCanonicalActive
          ? (data.pdb_url ?? null)
          : null;
        if (!pdbUrl) {
          try {
            const apiResp = await fetch(
              alphafoldPredictionApiUrl(activeUniprot),
            );
            if (apiResp.ok) {
              const entries =
                (await apiResp.json()) as AlphafoldPredictionEntry[];
              pdbUrl = entries[0]?.pdbUrl ?? null;
            }
          } catch {
            // Network / parse error — fall through to the legacy v4
            // URL below as a last resort. The 404 (if any) is the
            // remaining noise; previously it was the FIRST step.
          }
        }
        if (!pdbUrl) pdbUrl = alphafoldPdbUrl(activeUniprot);

        let pdbResp = await fetch(pdbUrl, { cache: "force-cache" });

        // Defensive retry for a STALE baked URL (canonical view with
        // a build-baked v_n URL that's been superseded since the build).
        // The prediction-API-first path above already handles the no-
        // baked-URL cases, so this branch only fires for build-pinned
        // URLs that aged out (observed: O95800 v4→v6 between
        // 2025-08 builds).
        if (pdbResp.status === 404) {
          try {
            const apiResp = await fetch(
              alphafoldPredictionApiUrl(activeUniprot),
            );
            if (apiResp.ok) {
              const entries =
                (await apiResp.json()) as AlphafoldPredictionEntry[];
              if (entries[0]?.pdbUrl && entries[0].pdbUrl !== pdbUrl) {
                pdbUrl = entries[0].pdbUrl;
                pdbResp = await fetch(pdbUrl, { cache: "force-cache" });
              }
            }
          } catch {
            // Fall through to the status check below.
          }
        }
        if (!pdbResp.ok) {
          // A 404 = AlphaFold DB simply has no model for this protein
          // (e.g. megalin/LRP2 and other very large proteins beyond
          // AFDB's per-entry limit). That's not a load FAILURE — surface
          // a soft "no model available" state, not a red error. Non-404s
          // are genuine failures and still throw → the error UI + Retry.
          if (pdbResp.status === 404) {
            if (renderSeq !== renderSeqRef.current) return;
            setErrorMsg("");
            setStatus("nomodel");
            return;
          }
          throw new Error(
            `AlphaFold DB returned ${pdbResp.status} for ${activeUniprot}`,
          );
        }
        rawPdb = await pdbResp.text();
      }

      // Resolve the chain id we'll actually use downstream — PDBe's
      // metadata occasionally disagrees with the deposited PDB
      // (case mismatch, label vs auth asym id). _pickPdbChain falls
      // back to a case-insensitive match, then to the heaviest chain,
      // so the orientation + topology coloring don't silently no-op
      // for entries with mismatched chain ids (GPR75 was the trigger).
      const effectiveChainId = expVariant
        ? _pickPdbChain(rawPdb, expVariant.chain_id) ?? expVariant.chain_id
        : null;

      // Build the UniProt→PDB-author projection for an experimental
      // structure. The topology string is UniProt-keyed; 3Dmol selects
      // on the file's author resSeq; `best_structures.start` is a SEQRES
      // index (and PDBe author numbers can disagree with the legacy .pdb
      // RCSB serves — EGFR 7syd is 1..614 in the file but -23..1186 in
      // PDBe author space). So we validate candidate offsets against the
      // residues ACTUALLY present in the fetched file and keep the best.
      let projSegments: ProjSegment[] = [];
      if (expVariant) {
        const chain = effectiveChainId ?? expVariant.chain_id;
        const observed = _observedResSeq(rawPdb, chain);
        const seqresOffset = expVariant.pdb_start - expVariant.unp_start;
        if (expVariant.mappingMode === "approx") {
          // Approach C — discontinuous fusion mapping. Fetch SIFTS
          // per-segment author numbers and project piecewise, each
          // segment's offset file-validated. Falls through to the
          // single-offset path below if SIFTS is unavailable.
          const raw = await _fetchSiftsSegments(
            expVariant.pdb_id, data.uniprot_acc, expVariant.chain_id,
          );
          if (raw.length > 0) projSegments = _projSegmentsForDirty(raw, observed);
        }
        if (projSegments.length === 0) {
          // Clean single contiguous segment (or dirty w/o usable SIFTS).
          // Candidate offsets: 0 (file numbered by UniProt residue — the
          // modern norm, true for GPR75 9xqc where author == UniProt) vs
          // the legacy SEQRES offset. Ties keep the legacy offset so
          // anything that already rendered can't regress (EGFR 7syd: both
          // are 0, 614 residues). 9xqc: offset 0 covers 266 residues vs
          // the legacy -34's 234, so the bug (off-by-34) is corrected.
          const offset = _bestLinearOffset(
            expVariant.unp_start, expVariant.unp_end,
            [0, seqresOffset], observed, seqresOffset,
          );
          projSegments = [{
            unpLo: expVariant.unp_start,
            unpHi: expVariant.unp_end,
            offset,
          }];
        }
      }

      // Orient both AFDB models and experimental PDBs the same way
      // when possible: rotate so the membrane plane is horizontal and
      // extracellular is up. For experimental PDBs we pass the resolved
      // chain id (so multi-chain assemblies like homotrimers or
      // MHC-peptide complexes don't pollute the centroid math) and the
      // projection map (so the topology lookup translates PDB author
      // numbering → UniProt numbering correctly, piecewise for fusions).
      // orientPdbForTopology returns `membrane: null` when the chain
      // covers no TM residues (ECD-only crystals, soluble fragments),
      // in which case the structure renders unoriented + slab-less —
      // 3Dmol auto-frames the native coords cleanly.
      // Schweke ECD-only: nodiso3 stripped the TM helix as a
      // disconnected contact cluster, so the model carries no M
      // residues to align — orient against an all-M topology would
      // produce a degenerate axis. Pass through unoriented; 3Dmol
      // auto-frames the dimer cleanly and the caption flags it.
      const schwekeSkipOrient = schwekeVariant?.ecd_only === true;
      const { pdbText, membrane } =
        schwekeSkipOrient
          ? { pdbText: rawPdb, membrane: null }
          : expVariant
            ? orientPdbForTopology(rawPdb, activeTopology, {
                chainId: effectiveChainId ?? expVariant.chain_id,
                resiToTopo: _makeResiToTopo(projSegments),
              })
            : orientPdbForTopology(rawPdb, activeTopology);

      const viewer = $3Dmol.createViewer(containerRef.current, {
        backgroundColor: "white",
        antialias: true,
      });
      viewer.addModel(pdbText, "pdb");

      // Mode-specific cartoon styling:
      //   topology mode: paint M/O/I/S/B per DeepTMHMM ranges so the
      //     reader sees the topology coloring + membrane slab.
      //   sites mode: paint the cartoon a single solid gray so the
      //     colored SURFACE-Bind anchor spheres are the dominant
      //     visual cue.
      //
      // CRITICAL: keep cartoon opacity at 1.0 in both modes. Earlier
      // versions used opacity 0.55 in sites mode, which sounded
      // gentler but actually changed the WebGL transparent-render
      // ordering with the membrane slab — the membrane appeared
      // darker / less translucent under the half-transparent cartoon
      // than under a solid one. With both cartoons at opacity 1.0,
      // the membrane slab (MEMBRANE_OPACITY 0.34) renders identically
      // in both modes, matching the user's "make the membrane look
      // the same" requirement.
      if (schwekeVariant) {
        // Homo-oligomer view: drop the topology / sites coloring and
        // paint the two chains in distinct colors so the dimer
        // interface reads at a glance. Maroon-mid (CHAIN_A) + teal-mid
        // (CHAIN_B) — both come from the Deliverome design tokens; the
        // saved screenshots in data/external/schweke_homomer_atlas/ use
        // these exact hex values. SURFACE-Bind anchors / topology /
        // membrane slab are intentionally NOT drawn on this tab: the
        // SB anchor residue numbers are canonical-keyed (don't translate
        // cleanly to the homomer's residue range), topology coloring
        // would compete with chain-distinguishing, and membrane slab is
        // only meaningful when TMs are in the model (multi-pass cases —
        // ``ecd_only=false`` — handled by the orientation block above).
        viewer.setStyle(
          { chain: "A" },
          { cartoon: { color: SCHWEKE_CHAIN_A_COLOR, opacity: 1.0 } },
        );
        viewer.setStyle(
          { chain: "B" },
          { cartoon: { color: SCHWEKE_CHAIN_B_COLOR, opacity: 1.0 } },
        );
      } else if (viewMode === "sites") {
        const baseSel = expVariant && effectiveChainId
          ? { chain: effectiveChainId }
          : {};
        viewer.setStyle(baseSel, {
          cartoon: { color: "#D6D9DE" },
        });
      } else {
        // Default cartoon style for any residue without explicit topology
        // (shouldn't normally happen — DeepTMHMM covers the full sequence).
        // For experimental, restrict the default style to the mapped
        // chain so non-mapped chains (e.g. an antibody Fab co-crystal)
        // stay in default gray. Uses `effectiveChainId` (resolved
        // against the actual PDB) rather than the raw PDBe metadata
        // so mismatches don't silently drop the cartoon entirely.
        const baseSel = expVariant && effectiveChainId
          ? { chain: effectiveChainId }
          : {};
        // Base color for residues without an explicit topology range. A
        // GLOB protein whose topology came back empty (e.g. IZUMO4 —
        // outside the topology-sweep cohort, so NO ranges to overlay at
        // all) would otherwise show bare beta-gray; paint the base
        // GLOB-yellow so it matches every other globular protein. Genes
        // WITH topology overpaint this base via their ranges below, so
        // they're unaffected.
        const baseColor =
          activeDeepTMHMMType === "GLOB"
            ? TOPOLOGY_COLORS.M
            : TOPOLOGY_COLORS.B;
        viewer.setStyle(baseSel, { cartoon: { color: baseColor } });
        // For canonical, use the pre-computed `topology_ranges` from
        // the build-time JSON. For an AFDB variant, compute ranges
        // on the fly. For experimental, project the canonical ranges
        // onto PDB author residue numbers via `projSegments`.
        const ranges = isCanonicalActive
          ? data.topology_ranges
          : _computeTopologyRanges(activeTopology);
        (["M", "O", "I", "S", "B"] as const).forEach((state) => {
          // GLOB (soluble / no membrane topology): DeepTMHMM tags the
          // whole chain "I", so the only non-empty range is I spanning
          // 1..N. Paint it the TM-helix color rather than intracellular-
          // green so the fold doesn't visually assert a compartment it
          // doesn't have; the legend says "Globular" to match.
          const color =
            activeDeepTMHMMType === "GLOB"
              ? TOPOLOGY_COLORS.M
              : TOPOLOGY_COLORS[state];
          (ranges[state] ?? []).forEach(([start, end]) => {
            if (expVariant) {
              // Project each topology range through every projection
              // segment: clip the UniProt range to the segment's window,
              // then shift by the segment's author offset. Clean
              // structures have one segment; fusions (approach C) have
              // several. Residues outside every segment just aren't in
              // the crystal, so they go uncolored. Resolve to the actual
              // PDB-file chain id (not PDBe's metadata) so a casing or
              // label/auth mismatch doesn't silently drop the range.
              projSegments.forEach((seg) => {
                const a = Math.max(start, seg.unpLo);
                const b = Math.min(end, seg.unpHi);
                if (b < a) return;
                const sel: Record<string, unknown> = {
                  resi: `${a + seg.offset}-${b + seg.offset}`,
                };
                if (effectiveChainId) sel.chain = effectiveChainId;
                viewer.setStyle(
                  sel,
                  { cartoon: { color }, line: { color, linewidth: 1.2 } },
                );
              });
            } else {
              viewer.setStyle(
                { resi: `${start}-${end}` },
                { cartoon: { color }, line: { color, linewidth: 1.2 } },
              );
            }
          });
        });
      }

      // SURFACE-Bind anchor overlay — one sphere per scored site at
      // the patch's anchor residue (CA atom). Spheres render ONLY in
      // sites mode (per user feedback: "don't show surface bind
      // sites at all on the topology version"). Colored by
      // compartment so the antibody-accessibility story is the
      // visual cue.
      //
      // SURFACE-Bind only publishes the patch anchor, not the full
      // contact-residue list — to render the actual patch surface
      // we'd need to parse the per-protein binder PDBs and compute
      // contacts (separate task). The sphere is the honest
      // approximation: "the patch is centered here."
      const viewerExt = viewer as ViewerInstance;
      // Suppress SURFACE-Bind anchors on the homo-oligomer tab: the
      // SB anchor residue numbers are canonical-keyed and don't
      // translate cleanly onto a homomer whose residue range may be
      // ECD-only (nodiso3) or a different model than canonical AFDB.
      const shouldRenderAnchors =
        viewMode === "sites" && hasAnchors && !schwekeVariant;
      for (let i = 0; shouldRenderAnchors && i < surfaceBindAnchors.length; i += 1) {
        const { siteId, residue, compartment } = surfaceBindAnchors[i];
        const color = COMPARTMENT_COLOR[compartment];
        const sel = { resi: residue, atom: "CA" };
        // ``addStyle`` (not ``setStyle``) layers on top of the
        // existing cartoon — we want the sphere ON the cartoon, not
        // replacing it. Fallback to ``setStyle`` when older 3Dmol
        // builds don't expose ``addStyle``.
        if (typeof viewerExt.addStyle === "function") {
          viewerExt.addStyle(sel, {
            sphere: { color, radius: SPHERE_RADIUS, opacity: 0.94 },
          });
        } else {
          viewer.setStyle(sel, {
            sphere: { color, radius: SPHERE_RADIUS, opacity: 0.94 },
          });
        }
        // Label: site number + compartment glyph (EC/IC/M/S/?) so the
        // reader sees at-a-glance whether the site is on the
        // antibody-accessible face. ``EC`` = extracellular (good
        // target), ``IC`` = intracellular (not antibody-accessible),
        // ``M`` = inside the membrane (not targetable),
        // ``S`` = signal peptide region. 1-indexed.
        if (typeof viewerExt.addLabel === "function") {
          viewerExt.addLabel(
            `${siteId + 1}·${COMPARTMENT_GLYPH[compartment]}`,
            {
              position: { resi: residue, atom: "CA" },
              backgroundColor: color,
              backgroundOpacity: 0.94,
              fontColor: "white",
              fontSize: 12,
              borderThickness: 0,
              inFront: true,
              // Push the label slightly away from the sphere so they
              // don't fully overlap.
              screenOffset: { x: 16, y: -16 },
            },
          );
        }
      }

      // Frame on atoms BEFORE adding the membrane slab. `zoomTo({})`
      // restricts the fit to selected atoms (empty selection = all
      // atoms), so the slab — which is wider than the protein in XZ —
      // doesn't pull the camera out.
      viewer.zoomTo({});

      // Translucent membrane slab at the TM-helix plane. The
      // orientation transform already pinned the bilayer normal to
      // +Y and centered the TM mean at Y=0, so the slab is just an
      // axis-aligned box spanning [yMin, yMax] in the oriented frame.
      // The slab's XZ extent comes from the TM bundle's own bounding
      // box (not the full protein's) — see structure-orientation.ts
      // for the rationale. Use xCenter / zCenter so the slab tracks
      // the TM helix when the ECD pulls the protein's overall center
      // off the membrane axis.
      //
      // Opacity is the same MEMBRANE_OPACITY in both modes — the
      // earlier sites-mode bump-up made the membrane fight the sphere
      // colors for visual attention. The red EC / green IC sphere
      // colors now carry the spatial orientation cue on their own
      // (no need for the floating "Extracellular ↑" / "Intracellular ↓"
      // text labels that used to sit above and below the slab).
      if (membrane) {
        viewer.addBox({
          corner: {
            x: membrane.xCenter - membrane.xExtent,
            y: membrane.yMin,
            z: membrane.zCenter - membrane.zExtent,
          },
          dimensions: {
            w: membrane.xExtent * 2,
            h: membrane.yMax - membrane.yMin,
            d: membrane.zExtent * 2,
          },
          color: MEMBRANE_COLOR,
          opacity: MEMBRANE_OPACITY,
          wireframe: false,
        });
      }

      // Skip the initial render() if the container is zero-sized
      // (collapsed parent, not-yet-visible tab) — that would burn a
      // frame against an empty WebGL framebuffer and log a stack of
      // GL_INVALID_FRAMEBUFFER_OPERATION warnings. The ResizeObserver
      // below will catch the first non-zero size and call resize() +
      // render() at that point, so the user still sees the model as
      // soon as the container becomes visible.
      const node = containerRef.current;
      const hasSize =
        node != null && node.clientWidth > 0 && node.clientHeight > 0;
      if (hasSize) {
        viewer.render();
      }
      viewerRef.current = viewer as ViewerInstance;

      // Capture the post-initial-render camera pose so the reset
      // button can restore both rotation AND zoom (not just zoom).
      // `zoomTo({})` re-frames on atoms but leaves any user-applied
      // rotation in place; `setView(initialViewRef.current)` is the
      // proper "reset everything" hook. Only meaningful when we
      // actually rendered above; otherwise `getView()` returns the
      // identity pose and we let the ResizeObserver capture it later.
      if (hasSize) {
        try {
          initialViewRef.current = (viewer as ViewerInstance).getView();
        } catch {
          // Older 3Dmol builds may not expose getView; leave initial
          // view null and the reset button will fall back to zoomTo.
        }
      }

      // Re-fit on container resize. Without this the viewer keeps
      // its initial pixel dimensions on layout shifts (responsive
      // viewport, dev-tools open / close, parent flex re-layout)
      // which manifests as "starts too zoomed in" the moment
      // anything else on the page resizes.
      if (
        typeof ResizeObserver !== "undefined" &&
        containerRef.current
      ) {
        // Reuse `node` from the size-gate above (we already null-
        // checked it via containerRef.current at the top of the
        // effect; the outer `if (containerRef.current)` here is just
        // a TS narrowing barrier). We could call `.observe(node!)`
        // but a plain null guard inside the block is clearer.
        if (!node) return;
        const ro = new ResizeObserver((entries) => {
          // Skip zero-size notifications. ResizeObserver fires once on
          // attach with the current bbox; if the container is inside
          // a collapsed parent or hasn't laid out yet, that initial
          // fire reports 0×0. Calling viewer.resize() + render() into
          // a zero-pixel framebuffer logs a wall of GL_INVALID_
          // FRAMEBUFFER_OPERATION warnings ("Framebuffer is
          // incomplete: Attachment has zero size") — visually harmless
          // (the next non-zero fire re-renders cleanly) but extremely
          // noisy in dev tools. Drop those frames here.
          const entry = entries[0];
          if (
            !entry ||
            entry.contentRect.width === 0 ||
            entry.contentRect.height === 0
          ) {
            return;
          }
          try {
            viewer.resize();
            // Match the initial render: fit on atoms only, so the
            // wider membrane slab doesn't pull the camera out on
            // every layout shift.
            viewer.zoomTo({});
            viewer.render();
            // Refresh the stored initial pose for the new viewport
            // size — otherwise resetting after a resize would
            // restore a pose framed for the old dimensions.
            try {
              initialViewRef.current = (viewer as ViewerInstance).getView();
            } catch {
              // ignore (see initial-capture comment above)
            }
          } catch {
            // 3Dmol throws on race against teardown; ignore.
          }
        });
        ro.observe(node);
        resizeObserverRef.current = ro;
      }
      if (renderSeq !== renderSeqRef.current) return;
      setStatus("ready");
    } catch (err) {
      if (renderSeq !== renderSeqRef.current) return;
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      setStatus("error");
    }
    // ``surfaceBindAnchors`` re-triggers the render so changes to
    // SURFACE-Bind data (per-gene) update the overlay. We compare by
    // JSON-stringified value so the effect doesn't re-fire when the
    // parent creates a fresh array reference each render but the
    // content hasn't changed. ``data`` is the canonical structure
    // payload — when it changes the protein has changed. ``viewMode``
    // toggles between topology / sites-focused rendering.
    // ``variantIdx`` switches which AFDB model (canonical / isoform /
    // ortholog) gets fetched + rendered.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, JSON.stringify(surfaceBindAnchors), viewMode, variantIdx]);

  useEffect(() => {
    void renderViewer();
    return () => {
      try {
        resizeObserverRef.current?.disconnect();
      } catch {
        // ignore
      }
      resizeObserverRef.current = null;
      try {
        viewerRef.current?.clear();
      } catch {
        // 3Dmol throws on double-clear; ignore.
      }
      viewerRef.current = null;
    };
  }, [renderViewer]);

  return (
    <div className={styles.viewerShell}>
      {/* Variant tab strip — only rendered when the gene has at least
          one alternative (isoform / ortholog). Canonical is the first
          tab ("Canonical"); subsequent tabs come from the ``variants``
          prop in their original order. Clicking switches which AFDB
          model + per-residue topology is rendered; SURFACE-Bind
          overlay hides on non-canonical tabs (anchor residue numbers
          are canonical-keyed and don't translate cleanly). The strip is
          ALWAYS rendered — a lone "Canonical" tab (when the gene has no
          isoforms / orthologs / experimental, e.g. IZUMO4) keeps the
          affordance consistent across genes. */}
      {(
        <div
          className={styles.variantTabs}
          role="tablist"
          aria-label="Structure variant"
        >
          <button
            type="button"
            role="tab"
            className={`${styles.variantTab} ${canonAfdbUnavail ? styles.variantTabUnavailable : ""}`.trim()}
            data-active={isCanonicalActive}
            onClick={() => {
              userPickedRef.current = true;
              setVariantIdx(0);
            }}
            title={
              canonAfdbUnavail
                ? `No AlphaFold model for canonical ${geneSymbol} (${data.uniprot_acc}) — AlphaFold DB doesn't model this protein.`
                : `AlphaFold model for the canonical ${geneSymbol} (UniProt ${data.uniprot_acc}).`
            }
            aria-selected={isCanonicalActive}
          >
            <span className={styles.variantTabLabel}>Canonical</span>
            <span className={styles.variantTabSub}>{data.uniprot_acc}</span>
          </button>
          {effectiveVariants.map((v, i) => {
            const isActive = variantIdx === i + 1;
            const vUnavail =
              v.source === "afdb" &&
              afdbAvail[(v as StructureVariantAfdb).uniprot_acc] === false;
            return (
              <button
                key={v.id}
                type="button"
                role="tab"
                className={`${styles.variantTab} ${vUnavail ? styles.variantTabUnavailable : ""}`.trim()}
                data-active={isActive}
                onClick={() => {
                  userPickedRef.current = true;
                  setVariantIdx(i + 1);
                }}
                title={
                  vUnavail
                    ? `No AlphaFold model for ${v.label}${v.sublabel ? ` (${v.sublabel})` : ""} — AlphaFold DB doesn't model this protein.`
                    : v.source === "schweke-homomer"
                      ? `Schweke 2024 AF2 homo-oligomer prediction for ${geneSymbol} — predicted dimer of UniProt ${data.uniprot_acc}.`
                      : `AlphaFold model for ${v.label}${v.sublabel ? ` (${v.sublabel})` : ""}.`
                }
                aria-selected={isActive}
              >
                <span className={styles.variantTabLabel}>{v.label}</span>
                {v.sublabel ? (
                  <span className={styles.variantTabSub}>{v.sublabel}</span>
                ) : null}
              </button>
            );
          })}
        </div>
      )}
      <div
        ref={containerRef}
        className={styles.viewerCanvas}
        data-status={status}
        role="img"
        aria-label={`3D structure of ${geneSymbol}, AlphaFold DB ${activeUniprot}`}
      >
        {status === "loading" ? (
          <p className={styles.loadingNote}>Loading AlphaFold…</p>
        ) : null}
        {status === "error" ? (
          <div className={styles.errorBox}>
            <p className={styles.errorMsg}>Could not load structure</p>
            <p className={styles.errorDetail}>{errorMsg}</p>
            <button
              type="button"
              className={styles.errorRetry}
              onClick={renderViewer}
            >
              Retry
            </button>
          </div>
        ) : null}
        {status === "nomodel" ? (
          <div className={styles.nomodelBox}>
            <p className={styles.nomodelMsg}>No AlphaFold model available</p>
            <a
              className={styles.nomodelLink}
              href="https://alphafold.ebi.ac.uk/faq"
              target="_blank"
              rel="noopener noreferrer"
            >
              Why some proteins have no model — AlphaFold DB FAQ&nbsp;↗
            </a>
          </div>
        ) : null}
        {/* Inlaid reset symbol — small icon button in the canvas's
            bottom-right corner. Always rendered (no status gate) so
            it's visible immediately on SSR and stays visible even if
            3dmol takes a moment to mount. The onClick handler restores
            the initial camera pose captured after first render — both
            rotation AND zoom — so a rotation-only manipulation also
            undoes. Falls back to `zoomTo({})` if the initial pose
            wasn't captured (older 3Dmol without getView, or click
            before mount). Try/catch swallows the race-on-teardown
            exception 3Dmol can throw. */}
        <button
          type="button"
          className={styles.resetSymbol}
          onClick={() => {
            try {
              const v = viewerRef.current;
              if (!v) return;
              if (initialViewRef.current) {
                v.setView(initialViewRef.current);
              } else {
                v.zoomTo({});
              }
              v.render();
            } catch {
              // 3Dmol can throw on race against teardown / not-yet-ready
              // — swallow; next render call will settle.
            }
          }}
          title="Reset 3D view (re-center, re-zoom, undo rotation)"
          aria-label="Reset 3D view"
        >
          ↺
        </button>
      </div>
      {/* Controls row — mode toggle + SURFACE-Bind external link.
          Reset is the inlaid ↺ symbol inside the canvas (above), no
          longer in this row. Only rendered when the gene has
          SURFACE-Bind anchors; the link-out is suppressed too so we
          don't promise the reader a SURFACE-Bind entry that has
          nothing to show. */}
      {hasAnchors ? (
        <div className={styles.controls}>
          <div
            className={styles.modeToggle}
            role="group"
            aria-label="3D viewer mode"
          >
            <button
              type="button"
              className={styles.modeButton}
              data-active={viewMode === "topology"}
              onClick={() => setViewMode("topology")}
              title="Color the cartoon by DeepTMHMM topology (extracellular / TM / intracellular). All sites render in one purple color; the number label distinguishes them."
            >
              Topology
            </button>
            <button
              type="button"
              className={styles.modeButton}
              data-active={viewMode === "sites"}
              onClick={() => setViewMode("sites")}
              title="Overlay SURFACE-Bind anchor spheres on the topology-colored cartoon: purple = extracellular (antibody-accessible), green = intracellular (NOT accessible from outside the cell), red = signal peptide, gray = TM / unknown. Cartoon + membrane render identically to Topology mode; this view just adds the sphere overlay."
            >
              SURFACE-Bind sites
            </button>
          </div>
          {/* The previous ↗ deep-link to SURFACE-Bind was removed —
              the §SURFACE-Bind card below already carries the
              "SURFACE-Bind entry ↗" link in its footer; no need to
              duplicate it next to the mode toggle. */}
        </div>
      ) : null}
      {/* Per-variant caption — sits directly below the canvas (above
          the legend) and shows the structure's title + pLDDT /
          resolution + a link out to AFDB or RCSB for the ACTIVE
          variant. For canonical AFDB this is instant (data on prop);
          for non-canonical AFDB variants it lazy-fetches AFDB's
          /api/prediction; for experimental it parses the PDB TITLE
          record once and caches per pdb_id. */}
      {_renderCaption({
        activeVariant,
        canonicalStruct,
        proteinName,
        canonicalUniprot: data.uniprot_acc,
        afdbMetaByAcc,
        pdbTitles,
      })}

      {/* Legend — switches with viewMode. Topology mode shows the
          DeepTMHMM M/O/I/S/B color key; sites mode shows the
          per-compartment EC/IC/TM color key (matching the spheres
          drawn on the cartoon). Moved here from GeneHeader so the
          legend tracks the viewer's internal mode without lifting
          state. */}
      {viewMode === "sites" && hasAnchors ? (
        <>
          <ul
            className={styles.sitesLegend}
            aria-label="SURFACE-Bind site compartment legend"
          >
            {_presentSitesCompartments(surfaceBindAnchors).map(({ compartment, count }) => (
              <li key={compartment} className={styles.sitesLegendItem}>
                <span
                  className={styles.sitesLegendSwatch}
                  style={{ background: COMPARTMENT_COLOR[compartment] }}
                  aria-hidden="true"
                />
                <span className={styles.sitesLegendLabel}>
                  {COMPARTMENT_LEGEND_LABEL[compartment]} ({count})
                </span>
              </li>
            ))}
          </ul>
          {/* SURFACE-Bind citation — PMID + URL from the shared
              `lib/citations` constant, so this caption can't drift from
              the Summary-metrics chip or the §SURFACE-Bind card. */}
          <p className={styles.sitesCitation}>
            {CITATIONS.surfaceBind.authorYear}{" "}
            <a
              href={pubmedUrl(CITATIONS.surfaceBind.pmid)}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.captionLink}
            >
              ↗
            </a>
          </p>
        </>
      ) : (
        <TopologyLegend
          presentStates={_presentTopologyStates(activeTopology)}
          globular={activeDeepTMHMMType === "GLOB"}
        />
      )}
    </div>
  );
}
