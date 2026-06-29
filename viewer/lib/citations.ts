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
  /** Schweke et al. — AF2-based atlas of homo-oligomeric assemblies,
   *  four proteomes, 8,195 predicted homomers including ~3,946 human.
   *  Cited by the StructureViewer's "Homo-oligomer" tab. */
  schwekeHomomer: { authorYear: "Schweke et al. 2024", pmid: "38325366" },
  /** Uhlén et al. 2015 — Human Protein Atlas (HPA) landmark paper. */
  hpa: { authorYear: "Uhlén et al. 2015", pmid: "25613900" },
  /** Bausch-Fluck et al. 2018 — SURFY surfaceome predictor. */
  surfy: { authorYear: "Bausch-Fluck et al. 2018", pmid: "29605868" },
  /** Bausch-Fluck et al. 2015 — Cell Surface Protein Atlas (CSPA). */
  cspa: { authorYear: "Bausch-Fluck et al. 2015", pmid: "25894527" },
  /** Hallgren et al. 2022 — DeepTMHMM topology predictor. */
  deepTmhmm: { authorYear: "Hallgren et al. 2022", pmid: "36323986" },
  /** Howe et al. 2024 — Ensembl 2024 (Compara included). */
  ensemblCompara2024: { authorYear: "Howe et al. 2024", pmid: "38680976" },
  /** Vilella et al. 2009 — EnsemblCompara GeneTrees original paper. */
  ensemblCompara2009: { authorYear: "Vilella et al. 2009", pmid: "19029536" },
} as const;

/**
 * Typical antibody–antigen buried interface area in Å² (Ramaraj et al.
 * 2012, PMID 22246133). Used both as the SURFACE-Bind "antibody-sized
 * patch" cutoff in logic AND in the tooltips that explain that cutoff —
 * so the number stays identical in code and prose.
 */
export const TYPICAL_ANTIBODY_INTERFACE_A2 = 1103;
