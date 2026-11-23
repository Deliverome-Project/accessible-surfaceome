/*
 * The member's topology with its tag insert flagged on it.
 *
 * The bands and the legend ARE the gene pages' components — `TopologyBar` and
 * `TopologyLegend` from the isoform card, reading the same `TOPOLOGY_COLORS` palette the
 * production strip and the 3D cartoon share — so "intracellular" is the same green here
 * as on surfaceome.deliverome.org, and there is exactly one topology palette in the app.
 * This file adds only what the review page needs on top: the insert flag.
 *
 * Why the insert flag is drawn here rather than through `TopologyBar`'s own `pins`: the
 * gene-page pin is a 3px hairline tinted by provenance, one of many on a bar. A reviewer
 * going through 2,710 members needs the opposite — one mark that cannot be missed. The
 * flag is 6px against 14px bands (so it is the thickest thing on the strip), carries a
 * head and a dark edge, and is labelled with its arm. Changing `TopologyBar`'s pin
 * geometry to get that would change every gene page, so the flag is an overlay instead.
 */
import {
  TopologyBar,
  TopologyLegend,
} from "../surfaceome/IsoformsCard/TopologyBar";
import { armLabel, l1SiteLabel, topologyStatesPresent, type L1Site } from "../../lib/l1-design";
import styles from "./L1Review.module.css";

export interface InsertFlag {
  siteId: string;
  /** 1-indexed residue the cassette goes in after. 0 = before residue 1. */
  insertAfterResidue: number;
  /** Short text ON the flag — two or three characters, because it rides a 6px mark. */
  label: string;
  /** Longer form for the legend line under the strip. */
  legend: string;
  title: string;
  /** Distinct per-arm colour when a member carries multiple arms (a1, a2, a3). */
  color?: string;
}

/** Distinct high-contrast colours for multi-arm picks (a1, a2, a3, …) so each arm
 *  matches across the 2D topology strip, 3D spheres, and Tag site cards. */
export const ARM_COLORS: Record<string, string> = {
  a1: "#B3243B", // crimson
  a2: "#15803D", // deep emerald
  a3: "#B45309", // deep amber
  a4: "#9D174D", // plum
};

export function armColor(siteId: string | null | undefined): string {
  const arm = siteId ? armLabel(siteId) : null;
  return (arm && ARM_COLORS[arm]) || "#B3243B";
}

/**
 * `l1-p1088-a2` → `a2`, and null for every other shape of site id. Defined in
 * `lib/l1-design` — the review panel names a verdict's arm with the same function — and
 * re-exported here, where it was first needed.
 *
 * Multi-arm members name their arms `-aK`, but plenty of single-arm picks do not
 * (`l1-p2089-res1-igk_tag` is a real one): printing the raw id on the flag put a 20
 * character string on a 6px mark and pushed it off the strip. A member without an arm
 * id is labelled by its insert residue instead, which is the number a reviewer is
 * checking anyway.
 */
export { armLabel };

/** The member's current picks as flags, left to right along the sequence. */
export function insertFlags(sites: readonly L1Site[], orderedLength: number | null): InsertFlag[] {
  const primary = sites.filter((s) => s.is_primary !== false && s.insert_after_residue != null && s.insert_after_residue >= 0);
  const multiArm = primary.length > 1;
  return primary
    .map((s) => {
      const r = s.insert_after_residue as number;
      const arm = armLabel(s.site_id);
      const where = l1SiteLabel(s, orderedLength);
      return {
        siteId: s.site_id,
        insertAfterResidue: r,
        label: arm ?? (r === 0 ? "N" : String(r)),
        legend: arm ? `${arm} ${where}` : where,
        title: `${arm ? `${arm} — ` : ""}tag insert ${where} (${s.status})`,
        color: multiArm ? armColor(s.site_id) : undefined,
      };
    })
    .sort((a, b) => a.insertAfterResidue - b.insertAfterResidue);
}

export function L1TopologyStrip({
  topology,
  flags,
  gene,
  variantLabel,
  nAlternatives,
  sp,
  focusSiteId,
  onFlagClick,
  onPickResidue,
  suggestedResidue,
}: {
  /** The arm being looked at: its flag is drawn emphasised. */
  focusSiteId?: string | null;
  /** Clicking a flag focuses that arm on the structure. */
  onFlagClick?: (siteId: string) => void;
  /** Clicking the topology bar itself suggests inserting a tag after that residue. */
  onPickResidue?: (residue: number) => void;
  /** The reviewer's suggested insert residue (typed or clicked), drawn as its own flag. */
  suggestedResidue?: number | null;
  /** Native residues the N-terminus line is about: the native SP, or the stretch an Igk
   *  leader replaces. Drawn as a bracket over the bands, member numbering. */
  sp?: { from: number; to: number; kind: "native_sp" | "replaced"; label: string } | null;
  /** Per-residue DeepTMHMM topology of THIS member's ordered protein. */
  topology: string;
  flags: InsertFlag[];
  gene: string;
  variantLabel: string;
  nAlternatives: number;
}) {
  const n = topology.length;
  if (!n) return null;
  // The cassette goes in BETWEEN residue r and r+1, so the flag belongs on the boundary,
  // not on either residue's centre: r/n of the way along. r = 0 lands it at the far left
  // edge (before residue 1), r = n at the far right.
  // Rounded: the raw division prints 27.500000000000004% into the DOM, which is both
  // noise in the inspector and a sub-micron difference on screen.
  const pct = (r: number) =>
    Math.round(Math.max(0, Math.min(100, (r / n) * 100)) * 1e4) / 1e4;
  return (
    <div className={styles.strip}>
      <div className={styles.stripHead}>
        <span className={styles.stripTitle}>
          Topology &amp; tag insert{flags.length > 1 ? `s (${flags.length} arms)` : ""}
        </span>
        <span className={styles.muted}>
          {n} aa{onPickResidue ? " · click bar to suggest a site" : ""}
        </span>
      </div>
      <div className={styles.stripBody}>
        <TopologyBar
          topology={topology}
          ariaLabel={`${gene} ${variantLabel} topology, ${n} residues`}
          onResidueClick={onPickResidue}
        />
        {sp && sp.to >= sp.from ? (
          <span
            className={sp.kind === "replaced" ? `${styles.spBand} ${styles.spReplaced}` : styles.spBand}
            style={{ left: `${pct(sp.from - 1)}%`, width: `${Math.max(0.6, pct(sp.to) - pct(sp.from - 1))}%` }}
            title={sp.label}
            aria-hidden="true"
          />
        ) : null}
        {flags.map((f) => {
          const x = pct(f.insertAfterResidue);
          // The head is wider than the 6px mark it sits on, so a flag at either end
          // would hang outside the strip. Near the edges it is anchored to that edge
          // instead of centred, which keeps it inside and still reads as this flag's.
          const headShift = x < 6 ? "translateX(-12%)" : x > 94 ? "translateX(-88%)" : "translateX(-50%)";
          const on = focusSiteId === f.siteId;
          const colorStyle = f.color ? { background: f.color, borderColor: f.color } : undefined;
          return (
            <button
              type="button"
              key={f.siteId}
              className={on ? `${styles.insert} ${styles.insertOn}` : styles.insert}
              style={{ left: `${x}%`, ...colorStyle }}
              title={`${f.title} — click to show it on the structure`}
              aria-pressed={on}
              onClick={() => onFlagClick?.(f.siteId)}
            >
              <span className={styles.insertHead} style={{ transform: headShift, ...colorStyle }}>
                {f.label}
              </span>
            </button>
          );
        })}
        {suggestedResidue != null && suggestedResidue >= 0 && suggestedResidue <= n ? (
          <span
            className={`${styles.insert} ${styles.insertSuggested}`}
            style={{ left: `${pct(suggestedResidue)}%` }}
            title={`your suggested site: after residue ${suggestedResidue}`}
          >
            <span className={styles.insertHead}>you</span>
          </span>
        ) : null}
      </div>
      <div className={styles.stripLegend}>
        <TopologyLegend presentStates={topologyStatesPresent(topology)} showMembrane={false} />
        <ul className={styles.legend} aria-label="Tag insert legend">
          {flags.length > 1 ? (
            flags.map((f) => (
              <li key={f.siteId}>
                <span
                  className={styles.insertSwatch}
                  style={f.color ? { background: f.color, borderColor: f.color } : undefined}
                  aria-hidden="true"
                />{" "}
                {f.legend}
              </li>
            ))
          ) : (
            <li>
              <span className={styles.insertSwatch} aria-hidden="true" /> tag insert
              {flags.length ? ` — ${flags[0].legend}` : " — none picked for this member"}
            </li>
          )}
          {sp && sp.to >= sp.from ? (
            <li>
              <span className={sp.kind === "replaced" ? `${styles.spSwatch} ${styles.spReplaced}` : styles.spSwatch} aria-hidden="true" />{" "}
              {sp.kind === "replaced" ? `replaced by the Igκ leader: residues ${sp.from}–${sp.to}` : `native signal peptide: ${sp.from}–${sp.to}`}
            </li>
          ) : null}
          {nAlternatives ? (
            <li className={styles.muted}>
              {nAlternatives} alternative{nAlternatives === 1 ? "" : "s"} not drawn here — see the
              model and the tag-site cards below
            </li>
          ) : null}
        </ul>
      </div>
    </div>
  );
}
