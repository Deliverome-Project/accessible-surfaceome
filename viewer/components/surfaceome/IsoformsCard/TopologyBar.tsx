import { MEMBRANE_COLOR, TOPOLOGY_COLORS } from "../../../lib/structure-viewer-types";
import styles from "./TopologyBar.module.css";

interface Props {
  /** Per-residue DeepTMHMM topology string (1 char per residue). */
  topology: string;
  /** A11y label — e.g. "GPR75 canonical isoform topology". */
  ariaLabel?: string;
  /** Length of the longest topology in the table (typically the canonical).
   *  When set, this bar's WIDTH is scaled to ``topology.length /
   *  maxResidues`` and left-aligned, so a shorter variant (truncated isoform,
   *  fragment ortholog) renders as a proportionally shorter bar that lines up
   *  with the canonical's N-terminus — rather than every bar stretching to the
   *  full column width. Omit for a standalone full-width bar (legacy callers). */
  maxResidues?: number;
}

interface Run {
  state: string;
  length: number;
  start: number;
  end: number;
}

/** Collapse the per-residue topology string into runs of constant state. */
function runs(topology: string): Run[] {
  const out: Run[] = [];
  if (!topology) return out;
  let cur = topology[0];
  let runStart = 1;
  let runLen = 1;
  for (let i = 1; i < topology.length; i += 1) {
    if (topology[i] === cur) {
      runLen += 1;
    } else {
      out.push({ state: cur, length: runLen, start: runStart, end: runStart + runLen - 1 });
      cur = topology[i];
      runStart = i + 1;
      runLen = 1;
    }
  }
  out.push({ state: cur, length: runLen, start: runStart, end: runStart + runLen - 1 });
  return out;
}

const STATE_LABELS: Record<string, string> = {
  M: "TM helix",
  O: "Extracellular",
  I: "Intracellular",
  S: "Signal peptide",
  B: "β-strand",
};

/**
 * Horizontal topology strip, ported from the PR23 GPR75 preview HTML
 * (`docs/plans/2026-05-13-deep-dive-redesign-preview-GPR75.html`).
 * Each segment's flex-basis is the residue count of that run, so
 * the bar is residue-proportional within the row. Colors use the
 * shared `TOPOLOGY_COLORS` palette so the strip and the 3D card
 * agree on what M / O / I / S look like.
 */
export function TopologyBar({ topology, ariaLabel, maxResidues }: Props) {
  const segments = runs(topology);
  if (segments.length === 0) return null;
  // Scale this bar's width to its length relative to the longest topology in
  // the table so variant bars are length-proportional + left-aligned to the
  // canonical frame. Clamped to 100% defensively (a variant longer than the
  // supplied max gets full width rather than overflowing the cell).
  const widthPct =
    maxResidues && maxResidues > 0
      ? `${Math.min(100, (topology.length / maxResidues) * 100)}%`
      : "100%";
  return (
    <div
      className={styles.bar}
      role="img"
      aria-label={ariaLabel ?? "Per-residue topology bar"}
      style={{ width: widthPct }}
    >
      {segments.map((seg, i) => (
        <div
          key={i}
          className={styles.seg}
          style={{
            flexGrow: seg.length,
            background: TOPOLOGY_COLORS[seg.state] ?? "transparent",
          }}
          title={`${STATE_LABELS[seg.state] ?? seg.state} · residues ${seg.start}–${seg.end} (${seg.length} aa)`}
        />
      ))}
    </div>
  );
}

interface LegendProps {
  /** Restrict the legend to the states actually present in any of the topologies. */
  presentStates?: string[];
  /** When true, append a "Membrane" swatch matching the translucent
   *  slab the 3D viewer draws around the TM region. Defaults to true
   *  for compatibility with the structure-viewer call site; pass
   *  ``false`` when reusing this legend for a topology bar that has
   *  no rendered slab (e.g. the isoform strip). */
  showMembrane?: boolean;
  /** True when the protein is globular / soluble (DeepTMHMM label
   *  ``GLOB``): there is no membrane slab to annotate, so the
   *  "Membrane" swatch is suppressed even if a stray ``M`` state
   *  slips into ``presentStates``. */
  globular?: boolean;
}

export function TopologyLegend({
  presentStates,
  showMembrane = true,
  globular = false,
}: LegendProps) {
  // GLOB / soluble proteins (e.g. SRC's myristoyl-anchored cytoplasmic
  // kinase fold, IZUMO4 outside the topology-sweep cohort): the
  // StructureViewer paints every residue with ``TOPOLOGY_COLORS.M``
  // (TM-yellow) rather than the intracellular-green that a literal
  // "IIIII…I" topology would imply — see the comment at
  // ``StructureViewer.tsx`` next to the GLOB color branch. The legend
  // has to match, so render a single ``Globular`` swatch instead of
  // walking through per-state labels (which would advertise "Intracellular"
  // for a sequence the viewer is actually colouring TM-yellow). This
  // implements the intent of commit ac52920ac (the comment "the legend
  // says 'Globular' to match" was added but the legend update was
  // never landed; the swatch then drifted relative to the cartoon for
  // every globular gene until reported as a regression).
  if (globular) {
    return (
      <ul className={styles.legend} aria-label="Topology color legend">
        <li className={styles.legendItem}>
          <span
            className={styles.legendSwatch}
            style={{ background: TOPOLOGY_COLORS.M ?? "transparent" }}
            aria-hidden="true"
          />
          <span className={styles.legendLabel}>Globular</span>
        </li>
      </ul>
    );
  }
  const states = presentStates ?? ["M", "O", "I", "S", "B"];
  // Only show "Membrane" when the M state is actually present and the
  // protein isn't globular — matches the StructureViewer's "no slab on
  // soluble proteins" rule exactly, so the legend can never advertise a
  // slab the viewer didn't draw.
  const includeMembrane = showMembrane && states.includes("M");
  return (
    <ul className={styles.legend} aria-label="Topology color legend">
      {states.map((s) => (
        <li key={s} className={styles.legendItem}>
          <span
            className={styles.legendSwatch}
            style={{ background: TOPOLOGY_COLORS[s] ?? "transparent" }}
            aria-hidden="true"
          />
          <span className={styles.legendLabel}>{STATE_LABELS[s] ?? s}</span>
        </li>
      ))}
      {includeMembrane ? (
        <li key="membrane" className={styles.legendItem}>
          <span
            className={styles.legendSwatch}
            style={{ background: MEMBRANE_COLOR }}
            aria-hidden="true"
          />
          <span className={styles.legendLabel}>Membrane</span>
        </li>
      ) : null}
    </ul>
  );
}
