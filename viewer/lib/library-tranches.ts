/*
 * Which library tranches the viewer shows.
 * ----------------------------------------
 * A tranche is `l1` / `l2` (which candidates we order). It is NOT a DeepTMHMM
 * tool version, so never compare against a bare 1 / 2.
 *
 * L1 is the ordered library. L2 is still being designed, so showing its members
 * would make an in-progress design look final. The default is therefore `l1`
 * only. This is a display switch, nothing more: the Worker and D1 still carry
 * every L2 row, and turning L2 back on is a build-time env change, not a code
 * change:
 *
 *     NEXT_PUBLIC_LIBRARY_TRANCHES=l1,l2
 *
 * Every place a library member reaches the page reads through here:
 * `libraryStructureVariants` (the Ordered/library tabs), `libraryMembersByAccession`
 * (the L1/L2 badges on existing tabs), and IsoformsCard's "In library" pills.
 */

const DEFAULT_TRANCHES = "l1";

function parseTranches(raw: string | undefined): ReadonlySet<string> {
  const list = (raw ?? DEFAULT_TRANCHES)
    .split(",")
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean);
  for (const t of list) {
    if (!/^l\d+$/.test(t)) {
      // A bare "1"/"2" is exactly the tranche/tool-version confusion this module exists
      // to prevent; refuse it loudly at build time rather than silently hiding L1.
      throw new Error(
        `NEXT_PUBLIC_LIBRARY_TRANCHES: "${t}" is not a library tranche; use l1 / l2`,
      );
    }
  }
  return new Set(list.length ? list : [DEFAULT_TRANCHES]);
}

/** Tranches shown on this build. Inlined at build time by Next (static export). */
export const VISIBLE_LIBRARY_TRANCHES: ReadonlySet<string> = parseTranches(
  process.env.NEXT_PUBLIC_LIBRARY_TRANCHES,
);

/** True when a member of this tranche may be shown. A row with no tranche is hidden:
 *  we cannot tell it is not an unfinished design. */
export function isLibraryTrancheVisible(
  tranche: string | null | undefined,
  visible: ReadonlySet<string> = VISIBLE_LIBRARY_TRANCHES,
): boolean {
  return !!tranche && visible.has(tranche.trim().toLowerCase());
}

/** Drop the rows of hidden tranches. Keyed on each row's `library` field. */
export function visibleLibraryRows<T extends { library?: string | null }>(
  rows: readonly T[] | null | undefined,
  visible: ReadonlySet<string> = VISIBLE_LIBRARY_TRANCHES,
): T[] {
  return (rows ?? []).filter((r) => isLibraryTrancheVisible(r.library, visible));
}
