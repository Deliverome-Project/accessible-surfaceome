"use client";

import { useEffect, useRef, useState } from "react";
import {
  L1_CASSETTE_COLOR,
  L1_NONNATIVE_COLOR,
  MEMBRANE_COLOR,
  TOPOLOGY_COLORS,
} from "../../lib/structure-viewer-types";
import { orientPdbForTopology, type MembraneSlab } from "../../lib/structure-orientation";
import {
  L1_MEMBRANE_HALF_THICKNESS,
  l1ModelStateRuns,
  l1ModelToMember,
  topologyStatesPresent,
  type L1ModelMap,
} from "../../lib/l1-design";
import styles from "./L1Review.module.css";

/** One residue to mark, in MODEL numbering. */
export interface L1Mark {
  resi: number;
  color: string;
  /** Sphere radius; picks are drawn larger than contacts. */
  radius: number;
  label?: string;
}

interface Props {
  pdbUrl: string;
  /** Model residues the member covers; the rest is drawn faint. */
  span: [number, number] | null;
  marks: L1Mark[];
  /** Tagged models: the cassette span, drawn in its own colour. */
  cassette: [number, number] | null;
  /** Called with the MODEL residue number the reader clicked. */
  onPick?: (modelResidue: number) => void;
  /** Maps a MODEL residue number to this member's residue number for hover tooltips. */
  modelToMemberResi?: (modelResidue: number) => number | null;
  /** Key text for the model residues that are not the member's own (an Igk leader
   *  construct's residues, a snorkel module). */
  nonNativeLabel?: string;
  /** Model residue to bring to the centre of the view (a focused arm), animated. */
  focusResi?: number | null;
  /** DeepTMHMM v1 per-residue topology of the member's ordered protein (matched by
   *  design id, length and sequence hash), or null when there is none. */
  topology?: string | null;
  /** How this model's residues map onto that topology; null draws no shading. */
  map?: L1ModelMap | null;
  /** Residues in the model file, so the key lists "not in the member" only when some are. */
  modelLength?: number | null;
  /** Shorter canvas for the gene page's card. */
  compact?: boolean;
  /** Called when the user clicks the ↺ reset-view button (e.g. to clear a focused arm). */
  onReset?: () => void;
}

type Viewer = {
  addModel: (data: string, fmt: string) => void;
  setStyle: (sel: object, style: object) => void;
  addStyle: (sel: object, style: object) => void;
  addSphere: (spec: object) => void;
  addBox: (spec: object) => void;
  addLabel: (text: string, opts: object) => void;
  removeAllLabels: () => void;
  setClickable: (sel: object, on: boolean, cb: (atom: { resi: number }) => void) => void;
  setHoverable?: (
    sel: object,
    on: boolean,
    hoverCb: (atom: { resi: number; resn?: string }) => void,
    unhoverCb: () => void,
  ) => void;
  zoomTo: (sel?: object) => void;
  center: (sel?: object, animationDuration?: number) => void;
  getView?: () => number[];
  setView?: (view: number[]) => void;
  render: () => void;
  clear: () => void;
  resize: () => void;
};

/** The membrane drawn on the gene page has the same colour and opacity. */
const MEMBRANE_OPACITY = 0.34;
const OUTSIDE_COLOR = "#ECEEF1";
/** Side colours on L1 models. Extracellular is a neutral slate gray (Becca, 2026-11-22:
 *  "the ec is gray so the orange stand out more"): the orange cassette sits on the
 *  extracellular side, so the side it touches carries no hue of its own. Darker than the
 *  translucent membrane slab and the pale "not in the member" gray, so the three grays
 *  stay apart; TM yellow, cytoplasmic green and signal-peptide red are the site palette.
 *  Only these L1 views use it; the gene page's Structure card and the 2D strips keep
 *  TOPOLOGY_COLORS. */
const L1_SIDE_COLORS: Record<string, string> = { ...TOPOLOGY_COLORS, O: "#7B8290" };
const L1_SIDE_LABELS: Record<string, string> = {
  M: "TM helix",
  O: "Extracellular",
  I: "Cytoplasmic",
  S: "Signal peptide",
  B: "β strand",
};
/** The legend swatch for the slab, drawn as the slab renders (translucent on white). */
const MEMBRANE_SWATCH = "rgba(160, 164, 171, 0.34)";
/** Smallest half-width of the drawn bilayer. The orientation sizes the slab to the TM
 *  bundle (+12 Å), which for a single helix is a 50 Å tile that reads as a box rather
 *  than a membrane; 45 Å each way keeps it a sheet without dwarfing a multipass bundle. */
const MIN_SLAB_HALF_WIDTH = 45;

const SIDE_LABEL: Record<string, string> = {
  O: "extracellular",
  I: "cytoplasmic",
  M: "membrane",
  S: "signal peptide",
};

/**
 * Orient the model so the membrane is horizontal (extracellular up) and return where the
 * bilayer sits. The plane comes from the model itself: its normal is the axis between
 * the member's extracellular and cytoplasmic Cα centroids, its midplane the mean height
 * of the TM-helix Cαs, and the drawn slab is ±15 Å around that midplane. A member with a
 * very short cytoplasmic tail fails the default 6-residue minimum, so it is retried at 1.
 */
function orient(text: string, topology: string | null | undefined, map: L1ModelMap | null | undefined) {
  if (!topology || !map || !topology.includes("M")) return { pdbText: text, membrane: null as MembraneSlab | null };
  const resiToTopo = l1ModelToMember(map);
  const first = orientPdbForTopology(text, topology, { resiToTopo });
  if (first.membrane) return first;
  return orientPdbForTopology(text, topology, { resiToTopo, minSideResidues: 1 });
}

/**
 * A small 3Dmol view for L1 members (review page and the gene page's L1 design card).
 * Deliberately separate from the gene page's StructureViewer: this one draws one model,
 * the member's membrane and side shading, a few marked residues and a click-to-pick.
 */
export function L1Structure3D({ pdbUrl, span, marks, cassette, onPick, modelToMemberResi, topology, map, modelLength, compact, nonNativeLabel, focusResi, onReset }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const initialViewRef = useRef<number[] | null>(null);
  const pickRef = useRef(onPick);
  pickRef.current = onPick;
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [loaded, setLoaded] = useState(0);
  const [membrane, setMembrane] = useState<MembraneSlab | null>(null);
  const [hoverAtom, setHoverAtom] = useState<{ resi: number; resn?: string } | null>(null);
  const shaded = !!(topology && map);
  // Orientation depends on the topology and map, so a change in either reloads the model.
  const orientKey = shaded ? JSON.stringify([topology, map?.segments]) : "";

  // (1) Load + orient the model once per URL/topology. Restyling never refetches.
  useEffect(() => {
    let live = true;
    setState("loading");
    setMembrane(null);
    setHoverAtom(null);
    initialViewRef.current = null;
    (async () => {
      try {
        type Mod3D = typeof import("3dmol");
        const Mod = (await import("3dmol")) as Mod3D & { default?: Mod3D };
        const $3Dmol = (Mod.default ?? Mod) as unknown as { createViewer: (el: HTMLElement, o: object) => Viewer };
        const res = await fetch(pdbUrl);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const raw = await res.text();
        if (!live || !ref.current) return;
        const { pdbText, membrane: slab } = orient(raw, topology, map);
        ref.current.innerHTML = "";
        const v = $3Dmol.createViewer(ref.current, { backgroundColor: "white", antialias: true });
        v.addModel(pdbText, "pdb");
        viewerRef.current = v;
        setMembrane(slab);
        setState("ready");
        setLoaded((n) => n + 1);
      } catch {
        if (live) setState("error");
      }
    })();
    return () => {
      live = false;
      viewerRef.current?.clear();
      viewerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pdbUrl, orientKey]);

  // (3) A focused arm (clicked flag or tag-site card) is brought to the centre, so the
  // sphere is found without hunting for it on a 1,600-residue model.
  useEffect(() => {
    const v = viewerRef.current;
    if (!v || state !== "ready" || focusResi == null) return;
    try {
      v.center({ resi: focusResi, atom: "CA" }, 400);
    } catch {
      /* residue not in this model: leave the view as it is */
    }
  }, [focusResi, state, loaded]);

  // (2) Style: side shading (or plain span), cassette, marked residues. Zoom only on first
  // load, then add the membrane so the wider slab never pulls the camera out.
  const styleKey = JSON.stringify([span, cassette, marks, map?.nonNative]);
  const zoomedFor = useRef(-1);
  useEffect(() => {
    const v = viewerRef.current;
    if (!v || state !== "ready") return;
    v.removeAllLabels();
    if (shaded && topology && map) {
      v.setStyle({}, { cartoon: { color: OUTSIDE_COLOR, opacity: 1 } });
      for (const r of l1ModelStateRuns(topology, map)) {
        const color = L1_SIDE_COLORS[r.state];
        if (color) v.setStyle({ resi: `${r.lo}-${r.hi}` }, { cartoon: { color } });
      }
      for (const [lo, hi] of map.nonNative) v.setStyle({ resi: `${lo}-${hi}` }, { cartoon: { color: L1_NONNATIVE_COLOR } });
    } else {
      v.setStyle({}, { cartoon: { color: "#D6D9DE", opacity: 1 } });
      if (span) v.setStyle({ resi: `${span[0]}-${span[1]}` }, { cartoon: { color: "#9AA5B1" } });
    }
    if (cassette) v.setStyle({ resi: `${cassette[0]}-${cassette[1]}` }, { cartoon: { color: L1_CASSETTE_COLOR } });
    for (const m of marks) {
      v.addStyle({ resi: m.resi, atom: "CA" }, { sphere: { color: m.color, radius: m.radius } });
      if (m.label) {
        v.addLabel(m.label, {
          position: { resi: m.resi, atom: "CA" }, fontSize: 11, fontColor: "#1F2933",
          backgroundColor: "#FFFFFF", backgroundOpacity: 0.75, inFront: true,
        } as object);
      }
    }
    // Clickability and hover bind to the styled atoms, so both are re-applied after every restyle.
    v.setClickable({}, true, (atom) => pickRef.current?.(atom.resi));
    v.setHoverable?.(
      {},
      true,
      (atom) => setHoverAtom({ resi: atom.resi, resn: atom.resn }),
      () => setHoverAtom(null),
    );
    const firstZoom = zoomedFor.current !== loaded;
    if (firstZoom) {
      v.zoomTo(span ? { resi: `${span[0]}-${span[1]}` } : {});
      zoomedFor.current = loaded;
      if (membrane) {
        const h = L1_MEMBRANE_HALF_THICKNESS;
        const hx = Math.max(membrane.xExtent, MIN_SLAB_HALF_WIDTH);
        const hz = Math.max(membrane.zExtent, MIN_SLAB_HALF_WIDTH);
        v.addBox({
          corner: { x: membrane.xCenter - hx, y: -h, z: membrane.zCenter - hz },
          dimensions: { w: hx * 2, h: 2 * h, d: hz * 2 },
          color: MEMBRANE_COLOR,
          opacity: MEMBRANE_OPACITY,
          wireframe: false,
        });
      }
    }
    v.render();
    if (firstZoom) {
      try {
        initialViewRef.current = v.getView?.() ?? null;
      } catch {
        initialViewRef.current = null;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [styleKey, state, loaded, membrane, shaded]);

  const handleReset = () => {
    const v = viewerRef.current;
    if (!v) return;
    if (initialViewRef.current && v.setView) {
      v.setView(initialViewRef.current);
    } else {
      v.zoomTo(span ? { resi: `${span[0]}-${span[1]}` } : {});
    }
    v.render();
    onReset?.();
  };

  const outside =
    !!map?.nonNative.length || !!(span && (span[0] > 1 || (modelLength != null && modelLength > span[1])));
  const side = map?.cassetteSide ? SIDE_LABEL[map.cassetteSide] ?? null : null;
  const hoverLabel = (() => {
    if (!hoverAtom) return null;
    if (cassette && hoverAtom.resi >= cassette[0] && hoverAtom.resi <= cassette[1]) {
      return `tag cassette (model ${hoverAtom.resi})`;
    }
    const memRes = modelToMemberResi ? modelToMemberResi(hoverAtom.resi) : null;
    if (memRes != null && memRes >= 1) {
      const st = topology && memRes <= topology.length ? SIDE_LABEL[topology[memRes - 1]] : null;
      const prefix = hoverAtom.resn ? `${hoverAtom.resn} ${memRes}` : `residue ${memRes}`;
      return `${prefix}${st ? ` · ${st}` : ""}${onPick ? " — click to suggest" : ""}`;
    }
    if (!onPick) return `model ${hoverAtom.resi} — switch to Native to click-pick`;
    return `model ${hoverAtom.resi} (not in member sequence)`;
  })();
  return (
    <div className={styles.viewerWrap}>
      <div className={styles.viewerStage}>
        <div ref={ref} className={compact ? `${styles.viewer} ${styles.viewerCompact}` : styles.viewer} />
        {state === "loading" && <p className={styles.viewerNote} role="status" aria-live="polite">Loading model…</p>}
        {state === "error" && <p className={styles.viewerNote} role="alert">Could not load {pdbUrl}</p>}
        {state === "ready" && hoverLabel ? (
          <span className={styles.viewerHover} aria-live="polite">{hoverLabel}</span>
        ) : null}
        {state === "ready" && !hoverLabel && onPick ? (
          <span className={styles.viewerHint}>Click a residue to suggest a site</span>
        ) : null}
        {state === "ready" && (
          <button
            type="button"
            className={styles.resetSymbol}
            onClick={handleReset}
            title="Reset view"
            aria-label="Reset structure view"
          >
            ↺
          </button>
        )}
      </div>
      {state === "ready" ? (
        <div className={styles.sideLegend} aria-label="Membrane and side shading">
          {shaded && topology ? (
            <>
              <ul className={styles.sideExtra}>
                {topologyStatesPresent(topology).map((st) => (
                  <li key={st}><i style={{ background: L1_SIDE_COLORS[st] }} /> {L1_SIDE_LABELS[st] ?? st}</li>
                ))}
                {membrane ? <li><i style={{ background: MEMBRANE_SWATCH }} /> membrane (estimated)</li> : null}
                {cassette ? (
                  <li><i style={{ background: L1_CASSETTE_COLOR }} /> tag cassette{side ? ` (inserted on the ${side} side)` : ""}</li>
                ) : null}
                {map?.nonNative.length ? (
                  <li title="Model residues before the tag that are not part of this member's protein">
                    <i style={{ background: L1_NONNATIVE_COLOR }} /> {nonNativeLabel ?? "added residues (not this protein's own)"}
                    {` (model ${map.nonNative.map(([a, b]) => (a === b ? `${a}` : `${a}–${b}`)).join(", ")})`}
                  </li>
                ) : null}
                {outside ? <li><i style={{ background: OUTSIDE_COLOR }} /> not in the member</li> : null}
              </ul>
              {map?.unlistedSiteInsertAfter != null ? (
                <p className={styles.sideWarn}>
                  This refold carries the tag after residue {map.unlistedSiteInsertAfter}, a site that is not among
                  this member&rsquo;s current picks: it was folded for an earlier pick.
                </p>
              ) : null}
              <p className={styles.sideNote}>
                Shading: DeepTMHMM v1 topology of this member&rsquo;s ordered protein, matched by sequence
                {map?.cassette ? ", mapped around the cassette" : ""}.{" "}
                {membrane
                  ? "Membrane: estimated from this model (normal through the extracellular and cytoplasmic centroids, ±15 Å around the TM-helix midplane), extracellular up."
                  : "No membrane drawn: the model has too few TM, extracellular or cytoplasmic residues to place one."}
              </p>
            </>
          ) : (
            <p className={styles.sideNote}>
              No side shading or membrane: no DeepTMHMM v1 topology matches this member&rsquo;s sequence yet
              {topology ? ", or this model's residues could not be mapped onto it" : ""}.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
