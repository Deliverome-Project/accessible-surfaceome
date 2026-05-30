"use client";

import { type ReactNode, useMemo, useState } from "react";
import { type Compartment, compartmentAt } from "../../../lib/surface-bind";
import type { SurfaceBindSite } from "../../../lib/surfaceome-types";
import { InfoTip } from "../../InfoTip/InfoTip";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./SurfaceBindCard.module.css";

// `compartmentAt` + the `Compartment` type are imported from
// ``lib/surface-bind`` — the same helper the FiltersCard "EC sites"
// count uses, so the table's per-site "Side" column and the headline
// count can never disagree.

/** Pill tone per compartment — mirrors ``COMPARTMENT_COLOR`` in
 *  ``viewer/components/surfaceome/StructureViewerCard/StructureViewer.tsx``
 *  so the 3D sphere color and the table pill match per site.
 *  Per user preference: EC = red ("look here / focus"), IC = green
 *  (safely tucked away inside the cell); membrane / signal /
 *  unknown = neutral. */
function compartmentTone(c: Compartment): "danger" | "success" | "neutral" {
  if (c === "extracellular") return "danger";
  if (c === "intracellular") return "success";
  return "neutral";
}

/** Short label for the column. EC = extracellular (antibody-
 *  accessible); IC = intracellular (not accessible from outside);
 *  TM = inside the membrane; SP = signal peptide; ? = no topology. */
function compartmentGlyph(c: Compartment): string {
  if (c === "extracellular") return "EC";
  if (c === "intracellular") return "IC";
  if (c === "membrane") return "TM";
  if (c === "signal") return "SP";
  return "?";
}

/** Sort rank for the Side column — EC first (most antibody-relevant),
 *  then membrane / signal, intracellular, unknown last. */
function compartmentRank(c: Compartment): number {
  if (c === "extracellular") return 0;
  if (c === "membrane") return 1;
  if (c === "signal") return 2;
  if (c === "intracellular") return 3;
  return 4;
}

/**
 * Per-site targetability tone — three buckets based on the size of
 * the patch's β-seed pool (or α-seed pool for α-favored surfaces).
 * Cutoffs are practitioner heuristics: ≥1,000 seeds = comfortable
 * design margin, ≥100 = workable, <100 = thin / specialized.
 */
function seedCountTone(n: number): "success" | "teal" | "amber" | "neutral" {
  if (n >= 1000) return "success";
  if (n >= 100) return "teal";
  if (n >= 1) return "amber";
  return "neutral";
}

/**
 * BSA tone — compared to the average antibody-antigen interface
 * (1,103 ± 244 Å², Ramaraj 2012). Patches in the "fat" end of that
 * distribution score success; below the lower bound score amber.
 */
function bsaTone(area: number): "success" | "teal" | "amber" {
  if (area >= 1500) return "success";
  if (area >= 850) return "teal";
  return "amber";
}

type SortKey = "site" | "anchor" | "side" | "bsa" | "alpha" | "beta" | "hydro";
type SortDir = "asc" | "desc";

interface Props {
  sites: readonly SurfaceBindSite[];
  /** DeepTMHMM per-residue topology string — used to derive each
   *  anchor's compartment (the Side column). */
  topology: string;
}

/**
 * SurfaceBindTable — the sortable per-site MaSIF table. Client
 * component because column sorting needs local state; it renders
 * inside the (server) ``SurfaceBindCard`` frame. The score-rating
 * legends that used to live in the card's preamble now live in the
 * BSA / α-seed / β-seed column header info-tooltips, so the prose
 * stays about *what* each column is and the tooltip explains *how
 * it's rated*.
 */
export function SurfaceBindTable({ sites, topology }: Props) {
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const rows = useMemo(() => {
    const decorated = sites.map((site) => ({
      site,
      compartment: compartmentAt(topology, site.anchor_residue),
    }));
    if (!sortKey) {
      // Default order: extracellular-first (most antibody-relevant),
      // then largest BSA within each compartment.
      return [...decorated].sort(
        (a, b) =>
          compartmentRank(a.compartment) - compartmentRank(b.compartment) ||
          b.site.area_a2 - a.site.area_a2,
      );
    }
    const dir = sortDir === "asc" ? 1 : -1;
    const value = (r: (typeof decorated)[number]): number => {
      switch (sortKey) {
        case "site":
          return r.site.site_id;
        case "anchor":
          return r.site.anchor_residue;
        case "side":
          return compartmentRank(r.compartment);
        case "bsa":
          return r.site.area_a2;
        case "alpha":
          return r.site.n_seeds_alpha;
        case "beta":
          return r.site.n_seeds_beta;
        case "hydro":
          return r.site.hydrophobicity;
      }
    };
    return [...decorated].sort((a, b) => (value(a) - value(b)) * dir);
  }, [sites, topology, sortKey, sortDir]);

  function onSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function ariaSort(key: SortKey): "ascending" | "descending" | "none" {
    if (sortKey !== key) return "none";
    return sortDir === "asc" ? "ascending" : "descending";
  }

  function SortButton({ k, children }: { k: SortKey; children: ReactNode }) {
    const active = sortKey === k;
    return (
      <button type="button" className={styles.sortBtn} onClick={() => onSort(k)}>
        {children}
        <span
          aria-hidden="true"
          className={`${styles.sortArrow} ${active ? styles.sortArrowActive : ""}`}
        >
          {active ? (sortDir === "asc" ? "▲" : "▼") : "↕"}
        </span>
      </button>
    );
  }

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th
              scope="col"
              aria-sort={ariaSort("site")}
              className={`label-mono ${styles.head}`}
              title="Site number matches the labeled sphere at the same site on the 3D structure above."
            >
              <SortButton k="site">Site</SortButton>
            </th>
            <th
              scope="col"
              aria-sort={ariaSort("anchor")}
              className={`label-mono ${styles.head}`}
            >
              <SortButton k="anchor">Anchor</SortButton>
            </th>
            <th
              scope="col"
              aria-sort={ariaSort("side")}
              className={`label-mono ${styles.head}`}
              title="Compartment of the anchor residue, derived from DeepTMHMM topology. EC = extracellular (antibody-accessible from outside the cell); IC = intracellular (NOT accessible to systemic antibodies); TM = inside the transmembrane region; SP = signal peptide. SURFACE-Bind scores patch geometry but does NOT filter by which side of the membrane the patch faces — IC patches are real surface features but only accessible from inside the cell."
            >
              <SortButton k="side">Side</SortButton>
            </th>
            <th
              scope="col"
              aria-sort={ariaSort("bsa")}
              className={`label-mono ${styles.head}`}
            >
              <SortButton k="bsa">BSA</SortButton>
              <InfoTip label="About BSA" align="end">
                Predicted buried surface area for the site. Larger values
                indicate a broader putative protein–protein interaction
                surface and may provide more contact area for binder design.
                Treat as a geometry-based proxy for interface size, not as a
                binding-affinity prediction. Tone compares it to the typical
                antibody–antigen interface (1,103 ± 244 Å²,{" "}
                <a
                  href="https://pubmed.ncbi.nlm.nih.gov/22246133/"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Ramaraj 2012
                </a>
                ): <strong>≥1,500 Å²</strong> green (comfortably larger),{" "}
                <strong>≥850</strong> teal (within range), <strong>&lt;850</strong>{" "}
                amber (smaller than a typical interface — harder).
              </InfoTip>
            </th>
            <th
              scope="col"
              aria-sort={ariaSort("alpha")}
              className={`label-mono ${styles.head}`}
            >
              <SortButton k="alpha">α-seeds</SortButton>
              <InfoTip label="About α-seeds" align="end">
                Number of compatible α-helical seed fragments identified for
                this site (3-helix bundles, minihelix). Higher counts suggest
                more MaSIF-seed matches from helical motifs and may offer more
                starting geometries for helix-based miniprotein or peptide
                binder design. Tone: <strong>≥1,000</strong> green,{" "}
                <strong>≥100</strong> teal, <strong>≥1</strong> amber,{" "}
                <strong>0</strong> neutral.
              </InfoTip>
            </th>
            <th
              scope="col"
              aria-sort={ariaSort("beta")}
              className={`label-mono ${styles.head}`}
            >
              <SortButton k="beta">β-seeds</SortButton>
              <InfoTip label="About β-seeds" align="end">
                Number of compatible β-strand / β-sheet seed fragments
                identified for this site. Higher counts suggest more β-motif
                starting points for binder design. Compare within a target or
                family rather than as an absolute targetability score, since
                seed counts depend on the underlying seed library. Tone:{" "}
                <strong>≥1,000</strong> green, <strong>≥100</strong> teal,{" "}
                <strong>≥1</strong> amber, <strong>0</strong> neutral.
              </InfoTip>
            </th>
            <th
              scope="col"
              aria-sort={ariaSort("hydro")}
              className={`label-mono ${styles.head}`}
            >
              <SortButton k="hydro">Hydrophobicity</SortButton>
              <InfoTip label="About hydrophobicity" align="end">
                Average hydrophobic character of the predicted site
                (Eisenberg-style; positive = hydrophobic / lipid-facing,
                negative = polar / solvent-exposed). More hydrophobic patches
                are common in protein–protein interfaces and may favor
                shape-complementary binding, but highly hydrophobic exposed
                sites can raise developability or nonspecific-binding
                concerns. Interpret alongside BSA, seed counts, glycosylation,
                topology, and biological context.
              </InfoTip>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ site, compartment }) => (
            <tr key={site.site_id}>
              <td className={styles.cellMono}>{site.site_id + 1}</td>
              <td className={styles.cellMono}>R{site.anchor_residue}</td>
              <td className={styles.cell}>
                <StatusPill
                  tone={compartmentTone(compartment)}
                  size="sm"
                  // Native tooltip: this pill lives inside the
                  // horizontally-scrollable `.tableWrap` (overflow:auto),
                  // which would clip the styled CSS popover. The OS
                  // tooltip escapes the clip.
                  nativeTooltip
                  title={
                    compartment === "intracellular"
                      ? "Intracellular — this site is on the cytoplasmic face. NOT accessible to systemic antibodies; only relevant for intracellular binder strategies (cell-penetrating, intrabodies)."
                      : compartment === "extracellular"
                        ? "Extracellular — antibody-accessible from outside the cell."
                        : compartment === "membrane"
                          ? "Within the transmembrane region — not accessible."
                          : compartment === "signal"
                            ? "Signal peptide region — cleaved during maturation."
                            : "Compartment unknown — no topology data for this residue."
                  }
                >
                  {compartmentGlyph(compartment)}
                </StatusPill>
              </td>
              <td className={styles.cell}>
                <StatusPill tone={bsaTone(site.area_a2)} size="sm">
                  {site.area_a2.toFixed(0)} Å²
                </StatusPill>
              </td>
              <td className={styles.cell}>
                <StatusPill tone={seedCountTone(site.n_seeds_alpha)} size="sm">
                  {site.n_seeds_alpha.toLocaleString()}
                </StatusPill>
              </td>
              <td className={styles.cell}>
                <StatusPill tone={seedCountTone(site.n_seeds_beta)} size="sm">
                  {site.n_seeds_beta.toLocaleString()}
                </StatusPill>
              </td>
              <td className={styles.cellMono}>
                {site.hydrophobicity > 0 ? "+" : ""}
                {site.hydrophobicity.toFixed(1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
