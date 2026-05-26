"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

interface StructureViewerProps {
  data: StructureViewerData;
  geneSymbol: string;
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
  surfaceBindAnchors = [],
  variants = [],
}: StructureViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<ViewerInstance | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
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

      if (viewMode === "topology") {
        // ---- topology mode (default): color cartoon by DeepTMHMM ----
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
      } else {
        // ---- sites mode: wash out cartoon so the spheres pop ----
        // Pale gray cartoon at low opacity. Spheres get the screen
        // real estate; the cartoon is just contextual silhouette.
        viewer.setStyle({}, {
          cartoon: { color: "#E5E7EB", opacity: 0.55 },
        });
      }

      // SURFACE-Bind anchor overlay — one sphere per scored site at
      // the patch's anchor residue (CA atom). Topology mode uses the
      // per-site categorical palette so individual sites are
      // distinguishable. Sites mode uses one bright red across the
      // board for max contrast against the dimmed cartoon (per user
      // request: "show sites as larger red balls").
      //
      // SURFACE-Bind only publishes the patch anchor, not the full
      // contact-residue list — to render the actual patch surface
      // we'd need to parse the per-protein binder PDBs and compute
      // contacts (separate task). The sphere is the honest
      // approximation: "the patch is centered here."
      const viewerExt = viewer as ViewerInstance;
      for (let i = 0; i < surfaceBindAnchors.length; i += 1) {
        const { siteId, residue, compartment } = surfaceBindAnchors[i];
        // Topology mode: single purple across all sites — the number
        // label distinguishes them. Sites mode: color by compartment
        // (green EC / amber IC / gray TM) so the antibody-
        // accessibility story is the visual cue.
        const color = viewMode === "sites"
          ? COMPARTMENT_COLOR[compartment]
          : ANCHOR_COLOR;
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
            3dmol takes a moment to mount. The onClick handler
            tries/catches the zoomTo call so a click before 3dmol is
            ready is a no-op rather than an exception. */}
        <button
          type="button"
          className={styles.resetSymbol}
          onClick={() => {
            try {
              viewerRef.current?.zoomTo({});
              viewerRef.current?.render();
            } catch {
              // 3Dmol can throw on race against teardown / not-yet-ready
              // — swallow; next render call will settle.
            }
          }}
          title="Reset 3D view (re-center + re-zoom)"
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
              title="Wash out the cartoon and color each SURFACE-Bind site by compartment: red = extracellular (antibody-accessible), green = intracellular (NOT accessible from outside the cell), gray = TM / unknown. Same sphere size as topology mode so the spatial relationships don't shift."
            >
              SURFACE-Bind sites
            </button>
          </div>
          {/* Direct deep-link to the SURFACE-Bind entry page for this
              UniProt — readers who want the full per-protein record
              (binder PDB downloads, full MaSIF score table, etc.)
              jump straight there from the toggle. */}
          <a
            href={`https://surface-bind.inria.fr/protein.html?uniprot=${data.uniprot_acc}`}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.externalLink}
            title="Open the SURFACE-Bind entry for this protein (full binder PDB downloads, per-site MaSIF scores)"
          >
            ↗
          </a>
        </div>
      ) : null}
    </div>
  );
}
