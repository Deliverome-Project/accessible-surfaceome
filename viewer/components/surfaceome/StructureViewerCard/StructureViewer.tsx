"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

type LoadStatus = "idle" | "loading" | "ready" | "error";

interface ViewerInstance {
  clear: () => void;
  resize: () => void;
  render: () => void;
}

/**
 * StructureViewer — the 3Dmol.js-backed canvas. Client-only because
 * 3Dmol expects a DOM + WebGL. The 3Dmol module is dynamically
 * imported on the first "Show 3D structure" click so the 524 KB
 * library never lands in the initial bundle.
 */
export function StructureViewer({ data, geneSymbol }: StructureViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<ViewerInstance | null>(null);
  const [status, setStatus] = useState<LoadStatus>("idle");
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
      // 1) Ask the AFDB API for the current latest pdbUrl. AFDB
      //    occasionally bumps a UniProt to a new model version and
      //    removes older versions from the file server, so a hard-
      //    coded ``v4`` URL can 404 (observed for O95800 in 2025-08
      //    when the model was promoted to v6). Fall back to the
      //    legacy v4 URL if the API is unreachable.
      let pdbUrl = alphafoldPdbUrl(data.uniprot_acc);
      try {
        const apiResp = await fetch(alphafoldPredictionApiUrl(data.uniprot_acc));
        if (apiResp.ok) {
          const entries = (await apiResp.json()) as AlphafoldPredictionEntry[];
          if (entries[0]?.pdbUrl) {
            pdbUrl = entries[0].pdbUrl;
          }
        }
      } catch {
        // Network blip → use the legacy URL; its 404 (if any) will
        // surface in the next fetch with a clearer error.
      }
      const pdbResp = await fetch(pdbUrl);
      if (!pdbResp.ok) {
        throw new Error(
          `AlphaFold DB returned ${pdbResp.status} for ${data.uniprot_acc}`,
        );
      }
      const pdbText = await pdbResp.text();

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
      setStatus("ready");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      setStatus("error");
    }
  }, [data]);

  useEffect(() => {
    return () => {
      try {
        viewerRef.current?.clear();
      } catch {
        // 3Dmol throws on double-clear; ignore.
      }
      viewerRef.current = null;
    };
  }, []);

  return (
    <div className={styles.viewerShell}>
      <div
        ref={containerRef}
        className={styles.viewerCanvas}
        data-status={status}
        role="img"
        aria-label={`3D structure of ${geneSymbol}, AlphaFold DB ${data.uniprot_acc}`}
      >
        {status === "idle" ? (
          <button
            type="button"
            className={styles.loadButton}
            onClick={renderViewer}
          >
            Show 3D structure
            <span className={styles.loadButtonHint}>
              ~600 KB · loads 3Dmol.js + AFDB structure
            </span>
          </button>
        ) : null}
        {status === "loading" ? (
          <p className={styles.loadingNote}>Loading AlphaFold structure…</p>
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
