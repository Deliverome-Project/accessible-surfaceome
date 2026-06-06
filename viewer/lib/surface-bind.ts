/**
 * SURFACE-Bind compartment helpers.
 *
 * SURFACE-Bind scores patch geometry on the AlphaFold model of the
 * *whole* protein and only strips the transmembrane region — it does
 * NOT filter by which side of the membrane a patch faces. So a
 * single-pass receptor (EGFR, etc.) keeps the binder sites scored on
 * its cytoplasmic domain. Those are real surface patches but are not
 * reachable by a systemic antibody, so any count the UI labels
 * "EC sites" must restrict to extracellular-anchored patches.
 *
 * The compartment rule is the DeepTMHMM per-residue topology string:
 * one character per residue (1-indexed), `O` = outside / extracellular,
 * `I` = inside / cytoplasmic, `M` = membrane, `S` = signal peptide.
 * This is the single source of truth shared by the SurfaceBindTable
 * "Side" column and the headline EC-site count, so the two can never
 * drift.
 */

export type Compartment =
  | "extracellular"
  | "intracellular"
  | "membrane"
  | "signal"
  | "unknown";

/** Compartment of a 1-indexed residue from the DeepTMHMM topology
 *  string. Returns "unknown" when topology is absent or the residue
 *  index is out of range — never guessed as extracellular. */
export function compartmentAt(topology: string, residue: number): Compartment {
  const idx = residue - 1;
  if (idx < 0 || idx >= topology.length) return "unknown";
  const ch = topology.charAt(idx);
  if (ch === "O") return "extracellular";
  if (ch === "I") return "intracellular";
  if (ch === "M") return "membrane";
  if (ch === "S") return "signal";
  return "unknown";
}

/** The subset of SURFACE-Bind sites whose anchor residue is
 *  extracellular — the antibody-accessible patches. Generic over the
 *  site shape so callers can pass the full SurfaceBindSite without a
 *  cast. A site with unknown / non-extracellular compartment is
 *  excluded. */
export function ecSites<T extends { anchor_residue: number }>(
  sites: readonly T[],
  topology: string,
): T[] {
  return sites.filter(
    (s) => compartmentAt(topology, s.anchor_residue) === "extracellular",
  );
}
