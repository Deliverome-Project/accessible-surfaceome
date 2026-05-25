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

interface StructureViewerProps {
  data: StructureViewerData;
  geneSymbol: string;
  /** SURFACE-Bind anchor-residue overlay. Each entry highlights the
   *  α-carbon of the named residue with a colored sphere + numeric
   *  label (the site index). Pass the array from
   *  ``rec.deterministic_features.surface_bind.sites.map(s =>
   *  ({siteId: s.site_id, residue: s.anchor_residue}))``. Empty
   *  array = no overlay. SURFACE-Bind only publishes the patch
   *  anchor; nearby contact residues would need binder-PDB
   *  parsing to recover (separate task). */
  surfaceBindAnchors?: { siteId: number; residue: number }[];
}

/** Per-site sphere palette — discrete categorical, picked so the
 *  spheres pop against the topology palette (which uses pale green /
 *  yellow / gray) and the maroon brand accent. Cycles when there
 *  are more sites than entries (rare; max site count in our cohort
 *  is ~12). */
const ANCHOR_PALETTE = [
  "#C32F62", // maroon (brand)
  "#E07B3F", // orange
  "#7A4BD8", // violet
  "#0F8A8A", // teal
  "#D62828", // crimson
  "#5C3B9B", // deep purple
  "#B5651D", // ochre
  "#1E5BA0", // ocean blue
  "#9A2C7A", // magenta
  "#3F8B3F", // forest green
] as const;

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

      // Default cartoon style for any residue without explicit topology
      // (shouldn't normally happen — DeepTMHMM covers the full sequence).
      viewer.setStyle({}, { cartoon: { color: TOPOLOGY_COLORS.B } });

      // Color each topology range.
      (["M", "O", "I", "S", "B"] as const).forEach((state) => {
        const color = TOPOLOGY_COLORS[state];
        (data.topology_ranges[state] ?? []).forEach(([start, end]) => {
          viewer.setStyle(
            { resi: `${start}-${end}` },
            { cartoon: { color }, line: { color, linewidth: 1.2 } },
          );
        });
      });

      // SURFACE-Bind anchor overlay — one sphere per scored site at
      // the patch's anchor residue (CA atom). Discrete categorical
      // palette so individual sites are distinguishable; numeric
      // label (1-indexed for human readability) sits next to each
      // sphere so the reader can match site rows in the
      // SurfaceBindCard table to positions on the 3D structure.
      //
      // SURFACE-Bind only publishes the patch anchor, not the full
      // contact-residue list — to render the actual patch surface
      // we'd need to parse the per-protein binder PDBs and compute
      // contacts (separate task). The sphere is the honest
      // approximation: "the patch is centered here."
      const viewerExt = viewer as ViewerInstance;
      for (let i = 0; i < surfaceBindAnchors.length; i += 1) {
        const { siteId, residue } = surfaceBindAnchors[i];
        const color = ANCHOR_PALETTE[i % ANCHOR_PALETTE.length];
        const sel = { resi: residue, atom: "CA" };
        // ``addStyle`` (not ``setStyle``) layers on top of the
        // existing topology cartoon — we want the sphere ON the
        // cartoon, not replacing it. Fallback to ``setStyle`` when
        // older 3Dmol builds don't expose ``addStyle``.
        if (typeof viewerExt.addStyle === "function") {
          viewerExt.addStyle(sel, {
            sphere: { color, radius: 2.6, opacity: 0.92 },
          });
        } else {
          viewer.setStyle(sel, {
            sphere: { color, radius: 2.6, opacity: 0.92 },
          });
        }
        // Numeric label at the same residue, 1-indexed because the
        // table reader counts from 1 even though the schema is
        // 0-indexed. Background color matches the sphere so the
        // pairing is obvious; white text reads on any of our hues.
        if (typeof viewerExt.addLabel === "function") {
          viewerExt.addLabel(`${siteId + 1}`, {
            position: { resi: residue, atom: "CA" },
            backgroundColor: color,
            backgroundOpacity: 0.92,
            fontColor: "white",
            fontSize: 12,
            borderThickness: 0,
            inFront: true,
            // Push the label slightly away from the sphere so they
            // don't fully overlap.
            screenOffset: { x: 14, y: -14 },
          });
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
      // Opacity stays low so the protein cartoon reads as the primary
      // figure; the slab is spatial context, not the subject.
      if (membrane) {
        viewer.addBox({
          corner: {
            x: -membrane.xExtent,
            y: membrane.yMin,
            z: -membrane.zExtent,
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
    // payload — when it changes the protein has changed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, JSON.stringify(surfaceBindAnchors)]);

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
    </div>
  );
}
