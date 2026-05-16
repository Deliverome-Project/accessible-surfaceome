"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  orientLoadedStructure,
  orientPdbForTopology,
} from "../../../lib/structure-orientation";
import {
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
}

type LoadStatus = "loading" | "ready" | "error";

interface ViewerInstance {
  clear: () => void;
  resize: () => void;
  render: () => void;
}

/**
 * StructureViewer — the 3Dmol.js-backed canvas. Client-only because
 * 3Dmol expects a DOM + WebGL. The 3Dmol module is dynamically
 * imported on mount so the 524 KB library only lands on per-gene
 * pages (not the catalog index). Auto-loads — no click-to-show
 * gate — so the viewer reads as part of the gene-identity surface
 * rather than a hidden affordance.
 */
export function StructureViewer({ data, geneSymbol }: StructureViewerProps) {
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
      // BCIF (~22% smaller on the wire after gzip) was attempted but
      // 3dmol's BCIF parser dereferences `cats.atom_site.getField(...)`
      // without guarding against partial AFDB BCIF schemas — the
      // current build fails with "Cannot read properties of undefined
      // (reading 'getField')" on AF-* binaries. The `bcif_url` field
      // is still baked into the per-UniProt JSON so a future viewer
      // (or a patched 3dmol) can switch over without re-baking; the
      // post-load `orientLoadedStructure` helper exists to drive that
      // path.

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

      // Rotate the PDB text up front so the membrane plane is
      // horizontal, extracellular side up. (When BCIF lands, swap to
      // `orientLoadedStructure(viewer.selectedAtoms({}), data.topology)`
      // after `viewer.addModel(bcifBuf, "bcif")`.)
      const pdbText = orientPdbForTopology(rawPdb, data.topology);

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

      viewer.zoomTo();
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
            viewer.zoomTo();
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
  }, [data]);

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
