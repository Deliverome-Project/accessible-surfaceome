/*
 * Tagged-sites data contracts (browser-safe leaf). Internalization data is
 * owned by agents/internalization (PR #134) and its own viewer card.
 * Mirrors the structure-viewer-types.ts split: interfaces + token-name
 * constants only, no node:fs — safe to import across a "use client" boundary.
 */
import type { Compartment } from "./surface-bind";

export type TaggedSiteProvenance =
  | "literature_retrieved"
  /** The enrichment pass: a second, deeper literature read published BESIDE
   *  `literature_retrieved` rather than over it. Additive because the clip pool
   *  is not monotonic across runs — a paper that degrades to abstract-only
   *  contributes no methods clips, so a rerun legitimately finding less than
   *  its predecessor is the normal case under transient upstream failure. */
  | "literature_enriched"
  | "deterministic_computed"
  | "screen_validated"
  | "validated_literature"; // validation-only; never rendered

export type DeterministicPath = "disorder" | "surface_loop" | "terminal" | "snorkel";
export type TaggedSiteKind = "terminal_n" | "terminal_c" | "internal";
export type Confidence = "high" | "medium" | "low";

export interface EvidenceSource {
  claim?: string;
  citation: string;
  url?: string | null;
  pmid?: string | null;
  doi?: string | null;
}

export interface TaggedSite {
  site_id: string;
  gene_symbol: string;
  uniprot_acc: string;
  provenance: TaggedSiteProvenance;
  /** Only set when provenance === "deterministic_computed". */
  det_path: DeterministicPath | null;
  site_kind: TaggedSiteKind;
  /** Junction: tag sits between insert_after_residue and insert_after_residue+1
   *  (UniProt canonical numbering). Null for a pure N-terminal-before-residue-1 tag. */
  insert_after_residue: number | null;
  residue_before: string | null;
  residue_after: string | null;
  /** Canonical single-token residue for analysis, e.g. "G101": the residue
   *  immediately N-terminal to the junction (tag inserted AFTER it). Matches the
   *  "after N" convention in data/tag_sites/positive_controls.md. Null when there
   *  is no before-residue (e.g. a before-residue-1 N-terminal tag). */
  residue_label?: string | null;
  /** Deterministic-only span of the insertion-tolerant FEATURE the site sits in,
   *  e.g. "S98-K105": the low-pLDDT disorder run (disorder path) or the contiguous
   *  exposed loop (surface_loop path). Null for literature sites and single-residue
   *  features. */
  residue_range?: string | null;
  /** DeepTMHMM per-residue char at the junction (O/I/M/S), or null. */
  topology_state: string | null;
  extracellular: boolean;
  compartment: Compartment;
  tag_type: string;
  tag_length_aa: number | null;
  linker: string | null;
  evidence_type: string | null;
  functional_impact_measured: string | null;
  confidence: Confidence | null;
  /** The argument for this position, as prose. The agent metadata below used
   *  to be concatenated onto the end of this string as
   *  "[validation: ...; position: ...; entailment_verified: True]", which put
   *  raw field names in front of the reader and left nothing renderable. */
  rationale: string | null;
  /** How far the cited study went: did it show the tag on the surface, that
   *  the protein still works, both, or neither. Literature sites only. */
  validation_level?: string | null;
  /** Whether the junction is stated by the paper ("validated"), derived from
   *  topology because the protein has exactly one extracellular terminus
   *  ("topology_derived"), or reasoned from a nearby tag ("inferred"). */
  position_evidence?: string | null;
  source_tier?: string | null;
  /** Where the real tag sits when position_evidence is "inferred" — what makes
   *  an inferred junction checkable rather than asserted. */
  cited_tag_residue?: number | null;
  /** Pipeline gate: the quote was found verbatim in the cited source. */
  entailment_verified?: boolean | null;
  /** The proteoform frame the citation was numbering in, when it was not this
   *  protein's own: "mature" (the paper counts from the signal-peptide
   *  cleavage site), "isoform:P54289-2". Null is the ordinary case — the
   *  position was read in the protein's own frame, or never validated from a
   *  citation. A recovered position is only auditable if the frame travels
   *  with it, so this is what separates "the paper said residue 39" from "the
   *  paper said mature residue 4 and we mapped it". */
  position_frame?: string | null;
  /** Which library MEMBER this site describes (`l1-p1037`), and the sha256 of
   *  the sequence its position is expressed in. A gene is not a unit here: 45
   *  of the 518 internal-site genes have more than one member and 7 of those
   *  disagree about where the tag can go, and 71 of 566 members are not
   *  numbered on the human canonical protein — so a position without its
   *  construct and its sequence is ambiguous between real proteoforms. */
  candidate_id?: string | null;
  library?: string | null;
  numbered_against?: string | null;
  /** Where the junction's extracellular run sits: `inter_tm` is a genuine loop.
   *  Derived from topology, never from `site_kind` — which does not
   *  discriminate at low positions, where topologically identical sites are
   *  labelled `internal` and `terminal_n` interchangeably. */
  loop_run_position?: string | null;
  sources: EvidenceSource[];
  // deterministic-only (null for literature_retrieved / validated_literature):
  plddt: number | null;
  conservation_rank: number | null;
  median_conservation: number | null;
}

/** A published insertion position that is not a surface tag site. */
export interface OtherPosition {
  residue: number;
  kind: "intracellular" | "abrogates_function" | "other";
  supporting_clip_id?: string;
  note?: string;
}

export interface TagSiteSearch {
  /** Which pass: ``literature_v1`` or ``literature_enriched_v1``. */
  run_series: string | null;
  /** The library member this search describes, ``""`` for a gene-level search. */
  candidate_id: string;
  prompt_sha: string | null;
  prompt_version: string | null;
  searched_at: string | null;
  n_papers: number | null;
  n_sites: number | null;
}

export interface TaggedSitesFile {
  has_data: boolean;
  gene_symbol: string;
  uniprot_acc: string;
  sites: TaggedSite[];
  /** Stamped by the literature agent on every result INCLUDING an empty one,
   *  so its presence is the claim "this gene was searched". That is what lets
   *  the card say "Literature-validated (0)" — a searched gene that found
   *  nothing is a finding, and distinct from one nobody has looked at. */
  prompt_sha?: string | null;
  prompt_version?: string | null;
  generated_at?: string | null;
  /** Published insertion positions that are NOT surface tag sites: tolerated
   *  but facing the cytoplasm, or reported to abrogate function. The UNION
   *  across every search of this gene — a function-abrogating insertion does
   *  not stop being a fact because a later pass did not re-cite it. */
  literature_other_positions?: OtherPosition[];
  /** Every search this gene has had, newest first. A gene can carry more than
   *  one: the first literature pass is gene-level (``candidate_id: ""``) and the
   *  enrichment pass records one per library member, which is the only place a
   *  per-member answer is visible. The fields above describe the most recent of
   *  these. Absent on an older Worker. */
  searches?: TagSiteSearch[];
  /** Per-isoform deterministic tag pins (computed on each isoform's OWN AFDB
   *  model), classified vs the canonical prediction. Optional — absent until the
   *  pipeline regeneration populates it. Consumed by the IsoformsCard topology
   *  bars (shared = transfers from canonical; unique = isoform-specific). */
  isoform_pins?: IsoformTagPin[];
  /** Per-ortholog deterministic tag pins (mouse / cyno), computed on each
   *  ortholog's OWN AFDB model and classified vs the human canonical prediction.
   *  Same shape as isoform pins; ``isoform_id`` holds the ortholog UniProt acc and
   *  ``isoform_residue`` is on the ortholog's own residue axis. Rendered on the
   *  ortholog's own structure when its variant tab is active. */
  ortholog_pins?: IsoformTagPin[];
}

/** Overlay design-token NAMES per rendered provenance. Actual color values
 *  live in app/design-tokens.css. validated_literature is intentionally
 *  absent — it is validation-only and never drawn. */
export const PROVENANCE_TOKEN: Record<
  "literature_retrieved" | "deterministic_computed",
  string
> = {
  literature_retrieved: "--tag-site-literature",
  deterministic_computed: "--tag-site-deterministic",
};

/** Concrete hex per rendered provenance for WebGL (3Dmol) spheres, which
 *  cannot consume CSS vars. MUST stay in sync with the --tag-site-* tokens:
 *  literature = --lavender-bright (#8878c8), deterministic = --teal-mid (#3d6b60). */
export const PROVENANCE_HEX: Record<
  "literature_retrieved" | "deterministic_computed",
  string
> = {
  literature_retrieved: "#8878c8",
  deterministic_computed: "#3d6b60",
};

/**
 * Fine-grained overlay CATEGORY — the color axis for the structure-viewer
 * "Tag sites" mode. Splits the coarse provenance into the deterministic lanes
 * (disorder / surface_loop internal loops, ecto N-/C-terminus, C-terminal
 * snorkel) plus literature. Derive it with `tagSiteCategory`; color it with
 * `CATEGORY_HEX` (WebGL) / `CATEGORY_TOKEN` (CSS); label with `CATEGORY_LABEL`.
 */
export type TagSiteCategory =
  | "literature"
  | "surface_loop"
  | "disorder"
  | "terminal_n"
  | "terminal_c"
  | "snorkel"
  | "screen_validated";

/** Resolve a site to its overlay category from provenance + det_path + kind. */
export function tagSiteCategory(
  site: Pick<TaggedSite, "provenance" | "det_path" | "site_kind">,
): TagSiteCategory {
  if (site.provenance === "screen_validated") return "screen_validated";
  if (site.provenance !== "deterministic_computed") return "literature";
  switch (site.det_path) {
    case "disorder":
      return "disorder";
    case "snorkel":
      return "snorkel";
    case "terminal":
      return site.site_kind === "terminal_n" ? "terminal_n" : "terminal_c";
    case "surface_loop":
    default:
      return "surface_loop"; // legacy deterministic rows without a det_path
  }
}

/** WebGL-safe hex per category (3Dmol can't resolve CSS vars). MUST stay in
 *  sync with the --tag-site-* tokens in app/design-tokens.css. */
export const CATEGORY_HEX: Record<TagSiteCategory, string> = {
  literature: "#8878c8", // --lavender-bright
  surface_loop: "#3f7fd0", // blue (ordered exposed loop)
  disorder: "#2f9e44", // green — disordered loop, clearly distinct from the blue surface_loop lane
  terminal_n: "#f4aa28", // --amber-bright
  terminal_c: "#c07830", // --amber-mid
  snorkel: "#922038", // --maroon-mid — fallback / lower-confidence
  screen_validated: "#e5342e", // red — Tedman N-terminal HA control (distinct attention color)
};

export const CATEGORY_TOKEN: Record<TagSiteCategory, string> = {
  literature: "--tag-site-literature",
  surface_loop: "--tag-site-surface-loop",
  disorder: "--tag-site-disorder",
  terminal_n: "--tag-site-terminal-n",
  terminal_c: "--tag-site-terminal-c",
  snorkel: "--tag-site-snorkel",
  screen_validated: "--tag-site-screen-validated",
};

export const CATEGORY_LABEL: Record<TagSiteCategory, string> = {
  literature: "Literature-validated",
  surface_loop: "Surface loop (computed)",
  disorder: "Disordered loop (computed)",
  terminal_n: "Extracellular N-terminus",
  terminal_c: "Extracellular C-terminus",
  snorkel: "C-terminal snorkel",
  screen_validated: "Screen-validated",
};


/** One per-isoform deterministic tag pin (see tag_sites/isoform.py). Placed on
 *  the isoform's OWN residue axis (`left_pct`). */
export interface IsoformTagPin {
  site_id: string;
  isoform_id: string;
  classification: "shared" | "unique" | "control";
  det_path: DeterministicPath | null;
  site_kind: TaggedSiteKind;
  tag_type: string | null;
  isoform_residue: number;
  canonical_residue: number | null;
  left_pct: number; // 0..100 along the isoform's own topology axis
  /** Optional free-text (e.g. isoform surface-expression PME) for the pin tooltip. */
  note?: string | null;
}
