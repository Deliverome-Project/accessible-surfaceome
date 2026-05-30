"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
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
 *  canvas. Either AFDB-fetchable (isoforms, orthologs) or an
 *  experimental PDB resolved at runtime via PDBe + RCSB. */
export type StructureVariant = StructureVariantAfdb | StructureVariantExperimental;

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
  /** Corresponding PDB residue range. ``offset = pdb_start - unp_start``
   *  translates DeepTMHMM (UniProt-coord) ranges to PDB residue numbers. */
  pdb_start: number;
  pdb_end: number;
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
        </p>
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
  const afdbUrl = `https://alphafold.ebi.ac.uk/entry/${acc}`;

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
    versionLabel = canonicalStruct.afdb_version;
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

/** Per-compartment sphere color for "sites" mode. Per user
 *  preference: EC = red (the "look here / focus" attention color),
 *  IC = green (safely tucked away inside the cell). TM = gray
 *  (inside the membrane); signal / unknown = mute. The SurfaceBindCard
 *  "Side" column uses the same red/green mapping for visual
 *  consistency between the 3D view and the table. */
const COMPARTMENT_COLOR: Record<AnchorCompartment, string> = {
  extracellular: "#DC2626", // red-600
  intracellular: "#16A34A", // green-600
  membrane: "#94A3B8", // slate-400
  signal: "#94A3B8",
  unknown: "#6B7280", // gray-500
};

type LoadStatus = "loading" | "ready" | "error";

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
        // Top-ranked candidate first; PDBe orders by coverage +
        // resolution. Filter to human (tax_id 9606) when present,
        // else accept any candidate (some PDBe rows lack tax_id).
        const human = candidates.find((c) => c.tax_id === 9606);
        const top = human ?? candidates[0] ?? null;
        if (!cancelled) setPdbeCandidate(top);
      } catch {
        if (!cancelled) setPdbeCandidate(null);
      }
    }
    fetchPDBe();
    return () => { cancelled = true; };
  }, [data.uniprot_acc]);

  // Effective variants = caller-provided (isoforms / orthologs) +
  // experimental tab when PDBe has a hit. Experimental always lands
  // after isoforms / orthologs in the tab strip.
  const effectiveVariants: StructureVariant[] = useMemo(() => {
    const v: StructureVariant[] = [...variants];
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
        experimental_method: pdbeCandidate.experimental_method,
        resolution: pdbeCandidate.resolution,
        coverage: pdbeCandidate.coverage,
      });
    }
    return v;
  }, [variants, pdbeCandidate, data.topology, data.deeptmhmm_type]);

  const isCanonicalActive = variantIdx === 0;
  const activeVariant: StructureVariant | null = isCanonicalActive
    ? null
    : effectiveVariants[variantIdx - 1] ?? null;
  const isExperimentalActive = activeVariant?.source === "experimental";
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
    if (!activeVariant || activeVariant.source !== "afdb") return;
    const acc = activeVariant.uniprot_acc_full ?? activeVariant.uniprot_acc;
    if (acc in afdbMetaByAcc) return;
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
  }, [activeVariant]);

  const renderViewer = useCallback(async () => {
    if (!containerRef.current) return;
    setStatus("loading");
    setErrorMsg("");
    try {
      // 3dmol ships as CommonJS; depending on bundler the named-export
      // shape can be either ``Mod.createViewer`` or
      // ``Mod.default.createViewer``. Handle both.
      type Mod3D = typeof import("3dmol");
      const Mod = (await import("3dmol")) as Mod3D & { default?: Mod3D };
      const $3Dmol: Mod3D = Mod.default ?? Mod;
      // Branch on AFDB vs experimental. AFDB fetches by UniProt acc
      // through AFDB DB; experimental fetches by PDB id through RCSB
      // and uses PDBe's chain + offset mapping to project canonical
      // DeepTMHMM topology onto the (potentially partial, chain-
      // restricted) PDB residue numbering.
      let rawPdb: string;
      const expVariant = isExperimentalActive
        ? (activeVariant as StructureVariantExperimental)
        : null;
      if (expVariant) {
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
        // 1) Prefer the build-time-baked pdbUrl. Falls back to the
        //    legacy v4 URL if the build script couldn't enrich this
        //    entry (offline build, AFDB unreachable, etc.).
        // For canonical view, use the build-baked pdbUrl if present
        // (saves an AFDB API hop). For AFDB variants we always go
        // through the AFDB URL helper since we don't bake per-variant
        // URLs.
        let pdbUrl =
          isCanonicalActive
            ? (data.pdb_url ?? alphafoldPdbUrl(activeUniprot))
            : alphafoldPdbUrl(activeUniprot);

        let pdbResp = await fetch(pdbUrl, { cache: "force-cache" });

        // On 404 specifically, AFDB has bumped the version since the
        // last build (observed: O95800 went v4→v6 in 2025-08, with
        // v1–v5 removed from the file server). Re-query the
        // prediction API once for the current pdbUrl and retry.
        if (pdbResp.status === 404) {
          try {
            const apiResp = await fetch(
              alphafoldPredictionApiUrl(activeUniprot),
            );
            if (apiResp.ok) {
              const entries =
                (await apiResp.json()) as AlphafoldPredictionEntry[];
              if (entries[0]?.pdbUrl) {
                pdbUrl = entries[0].pdbUrl;
                pdbResp = await fetch(pdbUrl, { cache: "force-cache" });
              }
            }
          } catch {
            // Fall through to the status check below.
          }
        }
        if (!pdbResp.ok) {
          throw new Error(
            `AlphaFold DB returned ${pdbResp.status} for ${activeUniprot}`,
          );
        }
        rawPdb = await pdbResp.text();
      }

      // For AFDB models we orient the PDB to put the membrane
      // horizontal + extracellular up. Experimental PDBs are not
      // re-oriented: (1) they're chain-restricted and the centroid
      // computation would be skewed by partial coverage; (2) PDB
      // structures often only contain one domain (e.g. an ECD-only
      // crystal), so there's no membrane plane to orient against.
      // 3dmol auto-frames the unoriented coords cleanly.
      const { pdbText, membrane } = expVariant
        ? { pdbText: rawPdb, membrane: null }
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
      if (viewMode === "sites") {
        const baseSel = expVariant ? { chain: expVariant.chain_id } : {};
        viewer.setStyle(baseSel, {
          cartoon: { color: "#D6D9DE" },
        });
      } else {
        // Default cartoon style for any residue without explicit topology
        // (shouldn't normally happen — DeepTMHMM covers the full sequence).
        // For experimental, restrict the default style to the mapped
        // chain so non-mapped chains (e.g. an antibody Fab co-crystal)
        // stay in default gray.
        const baseSel = expVariant ? { chain: expVariant.chain_id } : {};
        viewer.setStyle(baseSel, { cartoon: { color: TOPOLOGY_COLORS.B } });
        // For canonical, use the pre-computed `topology_ranges` from
        // the build-time JSON. For an AFDB variant, compute ranges
        // on the fly. For experimental, project the canonical
        // ranges onto PDB residue numbers via the PDBe offset.
        const ranges = isCanonicalActive
          ? data.topology_ranges
          : _computeTopologyRanges(activeTopology);
        // Experimental projection: pdb_resi = unp_resi - unp_start + pdb_start
        // Drop any portion of a range that falls outside the PDBe-
        // mapped UniProt window (those residues just aren't in the
        // crystal).
        const offset = expVariant
          ? expVariant.pdb_start - expVariant.unp_start
          : 0;
        const unpLo = expVariant?.unp_start ?? -Infinity;
        const unpHi = expVariant?.unp_end ?? Infinity;
        (["M", "O", "I", "S", "B"] as const).forEach((state) => {
          const color = TOPOLOGY_COLORS[state];
          (ranges[state] ?? []).forEach(([start, end]) => {
            // Clip the UniProt range to the PDBe-mapped window.
            const a = Math.max(start, unpLo);
            const b = Math.min(end, unpHi);
            if (b < a) return;
            const pdbA = a + offset;
            const pdbB = b + offset;
            const sel: Record<string, unknown> = { resi: `${pdbA}-${pdbB}` };
            if (expVariant) sel.chain = expVariant.chain_id;
            viewer.setStyle(
              sel,
              { cartoon: { color }, line: { color, linewidth: 1.2 } },
            );
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
      const shouldRenderAnchors = viewMode === "sites" && hasAnchors;
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

      viewer.render();
      viewerRef.current = viewer as ViewerInstance;

      // Capture the post-initial-render camera pose so the reset
      // button can restore both rotation AND zoom (not just zoom).
      // `zoomTo({})` re-frames on atoms but leaves any user-applied
      // rotation in place; `setView(initialViewRef.current)` is the
      // proper "reset everything" hook.
      try {
        initialViewRef.current = (viewer as ViewerInstance).getView();
      } catch {
        // Older 3Dmol builds may not expose getView; leave initial
        // view null and the reset button will fall back to zoomTo.
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
        const node = containerRef.current;
        const ro = new ResizeObserver(() => {
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
      setStatus("ready");
    } catch (err) {
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
          are canonical-keyed and don't translate cleanly). */}
      {effectiveVariants.length > 0 ? (
        <div
          className={styles.variantTabs}
          role="tablist"
          aria-label="Structure variant"
        >
          <button
            type="button"
            role="tab"
            className={styles.variantTab}
            data-active={isCanonicalActive}
            onClick={() => setVariantIdx(0)}
            title={`AlphaFold model for the canonical ${geneSymbol} (UniProt ${data.uniprot_acc}).`}
            aria-selected={isCanonicalActive}
          >
            <span className={styles.variantTabLabel}>Canonical</span>
            <span className={styles.variantTabSub}>{data.uniprot_acc}</span>
          </button>
          {effectiveVariants.map((v, i) => {
            const isActive = variantIdx === i + 1;
            return (
              <button
                key={v.id}
                type="button"
                role="tab"
                className={styles.variantTab}
                data-active={isActive}
                onClick={() => setVariantIdx(i + 1)}
                title={`AlphaFold model for ${v.label}${v.sublabel ? ` (${v.sublabel})` : ""}.`}
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
      ) : null}
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
              title="Overlay SURFACE-Bind anchor spheres on the topology-colored cartoon: red = extracellular (antibody-accessible), green = intracellular (NOT accessible from outside the cell), gray = TM / unknown. Cartoon + membrane render identically to Topology mode; this view just adds the sphere overlay."
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
          {/* SURFACE-Bind citation — Balbi et al 2026, PMID 41604262.
              Same link the Summary metrics SURFACE-Bind chip cites;
              surfaces the source paper right next to the spheres so
              a reader who wants to read the method has a one-click
              path. */}
          <p className={styles.sitesCitation}>
            Balbi et al ·{" "}
            <a
              href="https://pubmed.ncbi.nlm.nih.gov/41604262/"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.captionLink}
            >
              2026 ↗
            </a>
          </p>
        </>
      ) : (
        <TopologyLegend
          presentStates={_presentTopologyStates(activeTopology)}
        />
      )}
    </div>
  );
}
