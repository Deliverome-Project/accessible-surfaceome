"use client";

/*
 * HomoOligomerViewerCard — standalone (no-record) homo-oligomer card.
 * ------------------------------------------------------------
 * Used by the /homomer-demo/{SYMBOL} routes to render a Schweke 2024
 * (PMID 38325366) AF2 model without needing a full SurfaceomeRecord
 * + StructureViewerData. The production deep-dive card
 * (StructureViewerCard/StructureViewer.tsx) renders the same model on
 * its "Homo-oligomer" tab and pulls topology from the per-gene
 * StructureViewerData JSON; this standalone card optionally accepts
 * topology + per-state ranges as props and applies the same
 * chain-A-by-topology + others-darken-toward-black scheme.
 *
 * Why a separate component: the production card is 2,000+ lines of
 * AFDB / experimental / PDBe orchestration that doesn't fit a
 * standalone demo page. The demo page only needs the 3dmol mount +
 * the chain coloring rules, which is ~100 lines.
 */

import { useEffect, useRef, useState } from "react";
import styles from "./HomoOligomerViewerCard.module.css";

/** DeepTMHMM topology palette — kept in sync with the production
 *  ``viewer/lib/structure-viewer-types.ts`` so the demo and the deep-
 *  dive page render the same hex values. Duplicated here rather than
 *  imported because the types file pulls a chain of server-side
 *  deps; for a 5-key palette, duplication is the cheaper trade. */
const TOPOLOGY_COLORS: Record<string, string> = {
  M: "#FFD579", // TM helix yellow
  O: "#8878C8", // extracellular lavender
  I: "#A9CFA8", // intracellular green
  S: "#DD5955", // signal peptide red
  B: "#C7CED6", // β-strand gray
};

/** See production card's ``SCHWEKE_DARKEST_CHAIN_FRACTION`` — keep in
 *  sync if either is changed. 0.95 leaves a hairline gap between the
 *  darkest chain and pure black so the cartoon's silhouette is still
 *  legible against the canvas. */
const DARKEST_FRACTION = 0.95;

interface HomoOligomerViewerCardProps {
  /** Reader-facing title above the canvas. */
  geneSymbol: string;
  /** UniProt accession (for the subtitle + caption credit line). */
  uniprotAcc: string;
  /** Display-only label of the Schweke model file
   *  (e.g. ``Q96G97_V1_3_c13``). */
  modelLabel: string;
  /** Stoichiometry / cyclic-symmetry order N. Drives the "homo-N-mer"
   *  prose and is used to label expected vs observed chain count. */
  stoichiometry: number;
  /** Public PDB URL (typically
   *  ``/data/structures/schweke/{ACC}_V1_{N}{_cN}.pdb``). */
  pdbUrl: string;
  /** Optional per-residue DeepTMHMM topology string (M/O/I/S/B per
   *  residue, 1-indexed in PDB numbering). When supplied, the
   *  renderer paints each chain with the topology palette darkened by
   *  the chain index; when omitted, all chains render in a single
   *  per-chain shade (TM yellow base) with the same darken gradient. */
  topology?: string | null;
  /** DeepTMHMM type (``TM``, ``SP+TM``, ``SP``, ``BETA``, ``GLOB``).
   *  When ``"GLOB"`` the per-state lookups collapse to the M-yellow
   *  base color so a globular fold doesn't visually assert a
   *  compartment it doesn't have. Optional; defaults to a benign
   *  per-chain fallback when omitted. */
  deeptmhmmType?: "TM" | "SP+TM" | "SP" | "BETA" | "GLOB" | null;
  /** Optional brief description sentence shown under the title. */
  blurb?: string;
}

/** Linearly mix ``hex`` toward black by ``fraction`` ∈ [0,1].
 *  Mirrors ``_darkenHex`` in the production card. */
function darkenHex(hex: string, fraction: number): string {
  const f = Math.max(0, Math.min(1, fraction));
  const cleaned = hex.startsWith("#") ? hex.slice(1) : hex;
  if (cleaned.length !== 6) return hex;
  const r = Number.parseInt(cleaned.slice(0, 2), 16);
  const g = Number.parseInt(cleaned.slice(2, 4), 16);
  const b = Number.parseInt(cleaned.slice(4, 6), 16);
  if (!Number.isFinite(r) || !Number.isFinite(g) || !Number.isFinite(b)) {
    return hex;
  }
  const dr = Math.round(r * (1 - f));
  const dg = Math.round(g * (1 - f));
  const db = Math.round(b * (1 - f));
  const hh = (n: number): string => n.toString(16).padStart(2, "0");
  return `#${hh(dr)}${hh(dg)}${hh(db)}`;
}

/** Extract unique chain IDs from a PDB text (ATOM/HETATM column 22). */
function extractChainIds(pdbText: string): string[] {
  const seen = new Set<string>();
  for (const line of pdbText.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
    if (line.length < 22) continue;
    const ch = line.charAt(21);
    if (ch && ch !== " ") seen.add(ch);
  }
  return Array.from(seen).sort();
}

/** Collapse a per-residue topology string into per-state runs of
 *  [start, end] (1-indexed, inclusive). Same shape as the production
 *  card's ``_computeTopologyRanges`` so the demo matches what readers
 *  see on the live deep-dive page. */
function computeTopologyRanges(topology: string): Record<string, [number, number][]> {
  const out: Record<string, [number, number][]> = {
    M: [], O: [], I: [], S: [], B: [],
  };
  if (!topology) return out;
  let cur = topology.charAt(0);
  let runStart = 1;
  for (let i = 1; i < topology.length; i += 1) {
    const ch = topology.charAt(i);
    if (ch !== cur) {
      if (out[cur]) out[cur].push([runStart, i]);
      cur = ch;
      runStart = i + 1;
    }
  }
  if (out[cur]) out[cur].push([runStart, topology.length]);
  return out;
}

export function HomoOligomerViewerCard({
  geneSymbol,
  uniprotAcc,
  modelLabel,
  stoichiometry,
  pdbUrl,
  topology = null,
  deeptmhmmType = null,
  blurb,
}: HomoOligomerViewerCardProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chainColors, setChainColors] = useState<
    { id: string; color: string }[]
  >([]);

  useEffect(() => {
    let cancelled = false;
    const container = containerRef.current;
    if (!container) return;

    const mount = async () => {
      try {
        setLoading(true);
        setError(null);

        type Mod3D = typeof import("3dmol");
        const Mod = (await import("3dmol")) as Mod3D & { default?: Mod3D };
        const $3Dmol = (Mod.default ?? Mod) as unknown as {
          createViewer: (
            el: HTMLElement,
            opts: { backgroundColor?: string; antialias?: boolean },
          ) => unknown;
        };

        const res = await fetch(pdbUrl);
        if (!res.ok) throw new Error(`fetch ${pdbUrl}: ${res.status}`);
        const pdbText = await res.text();
        if (cancelled) return;

        const chainIds = extractChainIds(pdbText);
        const n = chainIds.length;
        const ranges = topology ? computeTopologyRanges(topology) : null;

        const viewer = $3Dmol.createViewer(container, {
          backgroundColor: "white",
          antialias: true,
        }) as {
          addModel: (data: string, fmt: string) => unknown;
          setStyle: (sel: object, style: object) => void;
          zoomTo: () => void;
          zoom: (factor: number) => void;
          render: () => void;
          resize?: () => void;
        };

        viewerRef.current = viewer;
        viewer.addModel(pdbText, "pdb");

        // Per-chain coloring: chain index 0 = full color, chain N-1 =
        // darkest. Each chain gets its own topology projection.
        const swatches: { id: string; color: string }[] = [];
        chainIds.forEach((chainId, ci) => {
          const darkenFraction = n > 1 ? (ci / (n - 1)) * DARKEST_FRACTION : 0;
          const baseHex =
            ranges && deeptmhmmType !== "GLOB"
              ? TOPOLOGY_COLORS.B
              : TOPOLOGY_COLORS.M;
          const baseColor = darkenHex(baseHex, darkenFraction);
          viewer.setStyle(
            { chain: chainId },
            { cartoon: { color: baseColor, opacity: 1.0 } },
          );
          if (ranges) {
            (["M", "O", "I", "S", "B"] as const).forEach((state) => {
              const stateRanges = ranges[state] ?? [];
              const color = darkenHex(
                deeptmhmmType === "GLOB"
                  ? TOPOLOGY_COLORS.M
                  : TOPOLOGY_COLORS[state] ?? TOPOLOGY_COLORS.B,
                darkenFraction,
              );
              stateRanges.forEach(([start, end]) => {
                viewer.setStyle(
                  { chain: chainId, resi: `${start}-${end}` },
                  { cartoon: { color, opacity: 1.0 } },
                );
              });
            });
          }
          // Swatch for the chain strip below the canvas — uses each
          // chain's TM-yellow (or topology-B fallback) as a single
          // representative color. For genes WITH topology, the
          // rendered cartoon shows multiple colors per chain; the
          // swatch reads as "how dark is this chain overall."
          swatches.push({
            id: chainId,
            color: darkenHex(
              ranges && deeptmhmmType !== "GLOB"
                ? TOPOLOGY_COLORS.M
                : TOPOLOGY_COLORS.M,
              darkenFraction,
            ),
          });
        });

        viewer.zoomTo();
        viewer.zoom(0.92);
        viewer.render();

        if (!cancelled) {
          setChainColors(swatches);
          setLoading(false);
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      }
    };

    mount();

    const ro = new ResizeObserver(() => {
      const v = viewerRef.current as {
        resize?: () => void;
        zoomTo?: () => void;
        render?: () => void;
      } | null;
      if (v?.resize) {
        v.resize();
        v.zoomTo?.();
        v.render?.();
      }
    });
    ro.observe(container);

    return () => {
      cancelled = true;
      ro.disconnect();
    };
  }, [pdbUrl, topology, deeptmhmmType]);

  const stoichLabel =
    stoichiometry === 2
      ? "homo-dimer (c2)"
      : stoichiometry === 3
        ? "homo-trimer (c3)"
        : stoichiometry === 4
          ? "homo-tetramer (c4)"
          : stoichiometry === 5
            ? "homo-pentamer (c5)"
            : stoichiometry === 6
              ? "homo-hexamer (c6)"
              : stoichiometry === 7
                ? "homo-heptamer (c7)"
                : stoichiometry === 8
                  ? "homo-octamer (c8)"
                  : `homo-${stoichiometry}-mer (c${stoichiometry})`;

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>
            {geneSymbol} — predicted {stoichLabel}
          </h2>
          <p className={styles.subtitle}>
            UniProt {uniprotAcc} · {modelLabel}
          </p>
          {blurb ? (
            <p className={styles.subtitle} style={{ marginTop: 4 }}>
              {blurb}
            </p>
          ) : null}
        </div>
        <span className={styles.pill}>Schweke 2024 · candidate complex</span>
      </div>

      <div className={styles.canvasShell}>
        <div ref={containerRef} className={styles.canvas} />
        {loading && <div className={styles.loading}>Loading structure…</div>}
        {error && (
          <div className={styles.loading} style={{ color: "#922038" }}>
            Failed to load: {error}
          </div>
        )}
      </div>

      <div className={styles.chainStrip} aria-label="Chain palette">
        <span style={{ marginRight: 6 }}>
          {chainColors.length} chains · A (full color) →{" "}
          {chainColors[chainColors.length - 1]?.id ?? "?"} (near-black):
        </span>
        {chainColors.map((c) => (
          <span key={c.id}>
            <span
              className={styles.chainSwatch}
              style={{ background: c.color }}
              aria-hidden="true"
            />
            <span className={styles.chainLabel}>{c.id}</span>
          </span>
        ))}
      </div>

      <p className={styles.caption}>
        AlphaFold2 homo-oligomer prediction from{" "}
        <a href="https://pubmed.ncbi.nlm.nih.gov/38325366/">
          Schweke et al., <em>Cell</em> 2024, PMID 38325366
        </a>
        {". "}
        Chain 0 (typically <code>A</code>) renders at the canonical DeepTMHMM
        topology palette; each subsequent chain is linearly darkened toward
        black so all {stoichiometry} subunits stay visually distinct. Model
        extracted from the{" "}
        <a href="https://figshare.com/s/af3c1d5969f7468f2caa">figshare deposit</a>{" "}
        (DOI <code>10.6084/m9.figshare.22309177</code>).
      </p>
    </div>
  );
}
