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
  /** HPA antigen-design single-target vs multitarget identity bands.
   *  Was previously miscited as Sivertsson et al. 2020 (PMID 33170010,
   *  J. Proteome Res. — "Enhanced Validation of Antibodies Enables the
   *  Discovery of Missing Proteins"). Both are HPA/Uhlén-group antibody-
   *  validation papers with nearly identical titles; Edfors 2018 is the
   *  one that establishes the identity-band framework we're citing. */
  hpaAntigenDesign: { authorYear: "Edfors et al. 2018", pmid: "30297845" },
  /** Schweke et al. — AF2-based atlas of homo-oligomeric assemblies,
   *  four proteomes, 8,195 predicted homomers including ~3,946 human.
   *  Cited by the StructureViewer's "Homo-oligomer" tab. */
  schwekeHomomer: { authorYear: "Schweke et al. 2024", pmid: "38325366" },
  /** DeepTMHMM — deep-learning transmembrane-topology predictor (the
   *  source of `canonical_topology.tm_helix_count`). Preprint-only, so
   *  it has NO PubMed record; cite the durable bioRxiv DOI as the
   *  identifier (this is the tooltip-citation rule's DOI-secondary
   *  escape hatch for a paper with no PMID). Tool version pinned at
   *  `deeptmhmm-1.0.24` in the topology records. */
  deepTMHMM: {
    authorYear: "Hallgren et al. 2022",
    doi: "10.1101/2022.04.08.487609",
  },
} as const;

/** Canonical resolvable URL for a DOI. Used for preprint citations that
 *  have no PMID (DeepTMHMM); the tooltip-citation rule leads with PMID
 *  when one exists and falls back to DOI otherwise. */
export const doiUrl = (doi: string): string => `https://doi.org/${doi}`;

/**
 * Typical antibody–antigen buried interface area in Å² (Ramaraj et al.
 * 2012, PMID 22246133). Used both as the SURFACE-Bind "antibody-sized
 * patch" cutoff in logic AND in the tooltips that explain that cutoff —
 * so the number stays identical in code and prose.
 */
export const TYPICAL_ANTIBODY_INTERFACE_A2 = 1103;
