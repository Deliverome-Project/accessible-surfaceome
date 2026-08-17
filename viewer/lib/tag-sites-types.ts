/*
 * Tagged-sites data contracts (browser-safe leaf). Internalization data is
 * owned by agents/internalization (PR #134) and its own viewer card.
 * Mirrors the structure-viewer-types.ts split: interfaces + token-name
 * constants only, no node:fs — safe to import across a "use client" boundary.
 */
import type { Compartment } from "./surface-bind";

export type TaggedSiteProvenance =
  | "literature_retrieved"
  | "deterministic_computed"
  | "validated_literature"; // validation-only; never rendered

export type DeterministicPath = "disorder" | "surface_loop";
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
  rationale: string | null;
  sources: EvidenceSource[];
  // deterministic-only (null for literature_retrieved / validated_literature):
  plddt: number | null;
  conservation_rank: number | null;
  median_conservation: number | null;
}

export interface TaggedSitesFile {
  has_data: boolean;
  gene_symbol: string;
  uniprot_acc: string;
  sites: TaggedSite[];
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
