/**
 * Single source for recurring literature citations + the numeric
 * thresholds their prose references. Multiple cards/tooltips cite the
 * same papers (SURFACE-Bind, the typical antibody interface, HPA
 * antigen-design practice); hard-coding the PMID / URL / threshold
 * number in each spot is the drift vector that let the paralog bands
 * diverge. Reference these constants instead so a PMID, link, or
 * threshold can only ever be edited in one place.
 */

/** Canonical PubMed URL for a PMID. */
export const pubmedUrl = (pmid: string): string =>
  `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;

/** Recurring citations, keyed by short slug. `authorYear` is the
 *  reader-facing label; `pmid` is the durable identifier (pair it with
 *  `pubmedUrl` for the clickable link the tooltip-citation rule wants). */
export const CITATIONS = {
  /** SURFACE-Bind / MaSIF patch scoring (Correia lab). */
  surfaceBind: { authorYear: "Balbi et al. 2026", pmid: "41604262" },
  /** Typical antibody–antigen interface geometry. */
  antibodyInterface: { authorYear: "Ramaraj et al. 2012", pmid: "22246133" },
  /** HPA antigen-design single-target vs multitarget identity bands. */
  hpaAntigenDesign: { authorYear: "Edfors / Uhlén 2020", pmid: "33170010" },
} as const;

/**
 * Typical antibody–antigen buried interface area in Å² (Ramaraj et al.
 * 2012, PMID 22246133). Used both as the SURFACE-Bind "antibody-sized
 * patch" cutoff in logic AND in the tooltips that explain that cutoff —
 * so the number stays identical in code and prose.
 */
export const TYPICAL_ANTIBODY_INTERFACE_A2 = 1103;
