"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
  const hasAnchors = surfaceBindAnchors.length > 0;

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
      // 1) Prefer the build-time-baked pdbUrl. Falls back to the
      //    legacy v4 URL if the build script couldn't enrich this
      //    entry (offline build, AFDB unreachable, etc.).
      let pdbUrl = data.pdb_url ?? alphafoldPdbUrl(data.uniprot_acc);

      // 2) Try the URL with aggressive HTTP caching — AlphaFold PDBs
      //    are immutable per version, so force-cache is safe and
      //    makes repeat visits free.
      let pdbResp = await fetch(pdbUrl, { cache: "force-cache" });

      // 3) On 404 specifically, AFDB has bumped the version since the
      //    last build (observed: O95800 went v4→v6 in 2025-08, with
      //    v1–v5 removed from the file server). Re-query the
      //    prediction API once for the current pdbUrl and retry.
      //    Other errors propagate — no double-latency on hopeless
      //    paths (CORS, 500, timeout).
      if (pdbResp.status === 404) {
        try {
          const apiResp = await fetch(
            alphafoldPredictionApiUrl(data.uniprot_acc),
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
          `AlphaFold DB returned ${pdbResp.status} for ${data.uniprot_acc}`,
        );
      }
      const rawPdb = await pdbResp.text();

      // Rotate the PDB so the membrane plane is horizontal,
      // extracellular side up. Ported from the deliverome-internal
      // structure-site viewer; uses DeepTMHMM's per-residue
      // topology to find the M/O/I centroids, then rotates I→O onto
      // +Y. Falls back to the raw PDB when topology is too sparse
      // (small ECDs / soluble proteins).
      const { pdbText, membrane } = orientPdbForTopology(rawPdb, data.topology);

      const viewer = $3Dmol.createViewer(containerRef.current, {
        backgroundColor: "white",
        antialias: true,
      });
      viewer.addModel(pdbText, "pdb");

      if (viewMode === "topology") {
        // ---- topology mode (default): color cartoon by DeepTMHMM ----
        // Default cartoon style for any residue without explicit topology
        // (shouldn't normally happen — DeepTMHMM covers the full sequence).
        viewer.setStyle({}, { cartoon: { color: TOPOLOGY_COLORS.B } });
        (["M", "O", "I", "S", "B"] as const).forEach((state) => {
          const color = TOPOLOGY_COLORS[state];
          (data.topology_ranges[state] ?? []).forEach(([start, end]) => {
            viewer.setStyle(
              { resi: `${start}-${end}` },
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
      // The slab's XZ extent now comes from the TM bundle's own
      // bounding box (not the full protein's) — see structure-
      // orientation.ts for the rationale. Use the new xCenter /
      // zCenter so the slab tracks the TM helix when the ECD pulls
      // the protein's overall center off the membrane axis.
      // In sites mode the slab is more opaque (a real membrane band)
      // so EC vs IC reads as the dominant spatial cue.
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
          opacity: viewMode === "sites" ? 0.55 : MEMBRANE_OPACITY,
          wireframe: false,
        });

        // Sites mode: render explicit "Extracellular" / "Intracellular"
        // text labels floating above + below the slab so the reader
        // sees the orientation without having to guess from topology
        // coloring (which is muted in this mode).
        if (viewMode === "sites" && typeof viewerExt.addLabel === "function") {
          const slabMid = (membrane.yMin + membrane.yMax) / 2;
          const slabHalf = (membrane.yMax - membrane.yMin) / 2;
          viewerExt.addLabel("Extracellular ↑", {
            position: {
              x: membrane.xCenter,
              y: slabMid + slabHalf + 18,
              z: membrane.zCenter,
            },
            backgroundColor: "#2E7D7D",
            backgroundOpacity: 0.85,
            fontColor: "white",
            fontSize: 13,
            borderThickness: 0,
            inFront: true,
          });
          viewerExt.addLabel("Intracellular ↓", {
            position: {
              x: membrane.xCenter,
              y: slabMid - slabHalf - 18,
              z: membrane.zCenter,
            },
            backgroundColor: "#5C3B9B",
            backgroundOpacity: 0.85,
            fontColor: "white",
            fontSize: 13,
            borderThickness: 0,
            inFront: true,
          });
        }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, JSON.stringify(surfaceBindAnchors), viewMode]);

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
      <div
        ref={containerRef}
        className={styles.viewerCanvas}
        data-status={status}
        role="img"
        aria-label={`3D structure of ${geneSymbol}, AlphaFold DB ${data.uniprot_acc}`}
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
      </div>
      <div className={styles.controls}>
        {/* Mode toggle — only rendered when the gene has SURFACE-Bind
            anchors to focus on; otherwise the "sites" mode would be
            empty and meaningless. Two-button segment so the active
            state reads at a glance. */}
        {hasAnchors ? (
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
              title="Wash out the cartoon and color each SURFACE-Bind site by compartment: green = extracellular (antibody-accessible), amber = intracellular (NOT accessible from outside the cell), gray = TM / unknown. Same sphere size as topology mode so the spatial relationships don't shift."
            >
              Sites focus
            </button>
          </div>
        ) : null}
        {/* Reset view — re-centers and re-zooms the camera. After the
            user has dragged / scrolled the model around, this restores
            the initial framing without a full page reload. */}
        <button
          type="button"
          className={styles.resetButton}
          onClick={() => {
            try {
              viewerRef.current?.zoomTo({});
              viewerRef.current?.render();
            } catch {
              // 3Dmol can throw on race against teardown / re-render
              // (e.g. user clicks Reset right as a mode toggle is
              // re-mounting). Swallow — the next render call will
              // settle the camera.
            }
          }}
          title="Reset the 3D camera to the initial view (re-center and re-zoom)."
        >
          Reset view
        </button>
      </div>
    </div>
  );
}
