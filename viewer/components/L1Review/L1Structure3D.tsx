"use client";

import { useEffect, useRef, useState } from "react";
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
}

type Viewer = {
  addModel: (data: string, fmt: string) => void;
  setStyle: (sel: object, style: object) => void;
  addStyle: (sel: object, style: object) => void;
  addSphere: (spec: object) => void;
  addLabel: (text: string, opts: object) => void;
  removeAllLabels: () => void;
  setClickable: (sel: object, on: boolean, cb: (atom: { resi: number }) => void) => void;
  zoomTo: (sel?: object) => void;
  render: () => void;
  clear: () => void;
  resize: () => void;
};

/**
 * A small 3Dmol view for the L1 review page. Deliberately separate from the gene page's
 * StructureViewer (topology colouring, experimental structures, contact projections):
 * this one only needs a model, a few marked residues and a click-to-pick.
 */
export function L1Structure3D({ pdbUrl, span, marks, cassette, onPick }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const pickRef = useRef(onPick);
  pickRef.current = onPick;
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [loaded, setLoaded] = useState(0);

  // (1) Load the model once per URL. Restyling never refetches or resets the camera.
  useEffect(() => {
    let live = true;
    setState("loading");
    (async () => {
      try {
        type Mod3D = typeof import("3dmol");
        const Mod = (await import("3dmol")) as Mod3D & { default?: Mod3D };
        const $3Dmol = (Mod.default ?? Mod) as unknown as { createViewer: (el: HTMLElement, o: object) => Viewer };
        const res = await fetch(pdbUrl);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const text = await res.text();
        if (!live || !ref.current) return;
        ref.current.innerHTML = "";
        const v = $3Dmol.createViewer(ref.current, { backgroundColor: "white", antialias: true });
        v.addModel(text, "pdb");
        viewerRef.current = v;
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
  }, [pdbUrl]);

  // (2) Style: cartoon, member span, cassette, marked residues. Zoom only on first load.
  const styleKey = JSON.stringify([span, cassette, marks]);
  const zoomedFor = useRef(-1);
  useEffect(() => {
    const v = viewerRef.current;
    if (!v || state !== "ready") return;
    v.removeAllLabels();
    v.setStyle({}, { cartoon: { color: "#D6D9DE", opacity: 1 } });
    if (span) v.setStyle({ resi: `${span[0]}-${span[1]}` }, { cartoon: { color: "#9AA5B1" } });
    if (cassette) v.setStyle({ resi: `${cassette[0]}-${cassette[1]}` }, { cartoon: { color: "#7C5CBF" } });
    for (const m of marks) {
      v.addStyle({ resi: m.resi, atom: "CA" }, { sphere: { color: m.color, radius: m.radius } });
      if (m.label) {
        v.addLabel(m.label, {
          position: { resi: m.resi, atom: "CA" }, fontSize: 11, fontColor: "#1F2933",
          backgroundColor: "#FFFFFF", backgroundOpacity: 0.75, inFront: true,
        } as object);
      }
    }
    // Clickability binds to the styled atoms, so it is re-applied after every restyle.
    v.setClickable({}, true, (atom) => pickRef.current?.(atom.resi));
    if (zoomedFor.current !== loaded) {
      v.zoomTo(span ? { resi: `${span[0]}-${span[1]}` } : {});
      zoomedFor.current = loaded;
    }
    v.render();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [styleKey, state, loaded]);

  return (
    <div className={styles.viewerWrap}>
      <div ref={ref} className={styles.viewer} />
      {state === "loading" && <p className={styles.viewerNote}>Loading model…</p>}
      {state === "error" && <p className={styles.viewerNote}>Could not load {pdbUrl}</p>}
    </div>
  );
}
