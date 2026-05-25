import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./SurfaceBindCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

type Compartment =
  | "extracellular"
  | "intracellular"
  | "membrane"
  | "signal"
  | "unknown";

/** Per-residue compartment from the DeepTMHMM topology string.
 *  Returns ``unknown`` when topology data isn't available or the
 *  residue index is out of range. Mirrors the inference rule in
 *  ``GeneHeader.tsx``'s ``surfaceBindAnchors`` mapping — same source
 *  of truth as the 3D label. */
function compartmentAt(topology: string, residue: number): Compartment {
  const idx = residue - 1;
  if (idx < 0 || idx >= topology.length) return "unknown";
  const ch = topology.charAt(idx);
  if (ch === "O") return "extracellular";
  if (ch === "I") return "intracellular";
  if (ch === "M") return "membrane";
  if (ch === "S") return "signal";
  return "unknown";
}

/** Pill tone per compartment. EC = targetable (success / green);
 *  IC = not antibody-accessible (amber); membrane / signal /
 *  unknown = neutral. */
function compartmentTone(c: Compartment): "success" | "amber" | "neutral" {
  if (c === "extracellular") return "success";
  if (c === "intracellular") return "amber";
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

/** Must match ``ANCHOR_PALETTE`` in
 *  ``viewer/components/surfaceome/StructureViewerCard/StructureViewer.tsx``.
 *  Each row's color chip on the table corresponds to the colored
 *  sphere + label at that site's anchor on the 3D structure. */
const ANCHOR_PALETTE = [
  "#C32F62",
  "#E07B3F",
  "#7A4BD8",
  "#0F8A8A",
  "#D62828",
  "#5C3B9B",
  "#B5651D",
  "#1E5BA0",
  "#9A2C7A",
  "#3F8B3F",
] as const;

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

/**
 * Hydrophobicity tone is informational (not better/worse) — high
 * positive or low negative both produce designable surfaces, just
 * for different binder chemistries. Render neutral.
 */

/**
 * SURFACE-Bind per-site card. Renders one row per MaSIF-scored patch
 * (anchor residue, BSA, α/β seed counts, hydrophobicity) — the
 * deterministic targetability layer alongside our LLM-synthesis
 * sections. Hidden entirely when ``has_data=false`` (the absence
 * signal lives on the GeneHeader's "not scored" pill instead).
 */
export function SurfaceBindCard({ rec, n }: Props) {
  const sb = rec.deterministic_features.surface_bind;
  if (!sb.has_data) return null;
  // SURFACE-Bind has the protein but with zero scored sites — render
  // a thin card explaining what that means rather than hiding it
  // (this case is itself informative — the protein went through
  // scoring but no patch cleared the threshold).
  if (sb.sites.length === 0) {
    return (
      <SectionCard
        n={n}
        eyebrow="SURFACE-Bind"
        title="Patch-based targetability"
        meta="Marchand 2026 PNAS · MaSIF surface scoring · deterministic"
      >
        <p className={styles.emptyNote}>
          <strong>Scored by SURFACE-Bind</strong> — present in the
          authoritative ``results_no_TM.csv`` as{" "}
          <strong>{sb.main_class}</strong>
          {sb.sub_class ? (
            <>
              {" "}
              · <strong>{sb.sub_class}</strong>
            </>
          ) : null}{" "}
          — <strong>but no surface patches cleared the MaSIF
          targetability threshold</strong>. The protein went through
          scoring; the surface chemistry didn't yield designable
          binder seeds.{" "}
          <em>
            This is distinct from "not in SURFACE-Bind" (where the
            protein was filtered out at the structural-quality step
            before scoring) — see the header pill for the dataset-
            membership signal.
          </em>
        </p>
      </SectionCard>
    );
  }
  return (
    <SectionCard
      n={n}
      eyebrow="SURFACE-Bind"
      title="Patch-based targetability"
      meta={`Marchand 2026 PNAS · ${sb.n_sites} site${
        sb.n_sites === 1 ? "" : "s"
      } · ${sb.n_seeds_total.toLocaleString()} total binder seeds`}
    >
      <p className={styles.preamble}>
        Each row is one MaSIF-scored surface patch. The numbered,
        colored spheres on the 3D structure above mark each site's
        anchor residue — the swatch in the "Site" column matches the
        sphere color. Anchor = patch center residue (SURFACE-Bind
        doesn't publish the full per-patch residue list, only the
        anchor). BSA tone follows the typical antibody-antigen
        interface band (1,103 ± 244 Å², Ramaraj 2012). Seed counts
        split by binder backbone — α-helical (3-helix bundles,
        minihelix) vs β-strand (β-sheet scaffolds); higher = more
        design options.{" "}
        {sb.main_class ? (
          <>
            SURFACE-Bind classifies this as <strong>{sb.main_class}</strong>
            {sb.sub_class ? (
              <>
                {" "}
                · <strong>{sb.sub_class}</strong>
              </>
            ) : null}
            .
          </>
        ) : null}
      </p>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th
                scope="col"
                className={`label-mono ${styles.head}`}
                title="Colored dot matches the labeled sphere at the same site on the 3D structure above."
              >
                Site
              </th>
              <th scope="col" className={`label-mono ${styles.head}`}>
                Anchor
              </th>
              <th
                scope="col"
                className={`label-mono ${styles.head}`}
                title="Compartment of the anchor residue, derived from DeepTMHMM topology. EC = extracellular (antibody-accessible from outside the cell); IC = intracellular (NOT accessible to systemic antibodies); TM = inside the transmembrane region; SP = signal peptide. SURFACE-Bind scores patch geometry but does NOT filter by which side of the membrane the patch faces — IC patches are real surface features but only accessible from inside the cell."
              >
                Side
              </th>
              <th scope="col" className={`label-mono ${styles.head}`}>
                BSA
              </th>
              <th scope="col" className={`label-mono ${styles.head}`}>
                α-seeds
              </th>
              <th scope="col" className={`label-mono ${styles.head}`}>
                β-seeds
              </th>
              <th scope="col" className={`label-mono ${styles.head}`}>
                Hydrophobicity
              </th>
            </tr>
          </thead>
          <tbody>
            {sb.sites.map((site, i) => {
              const compartment = compartmentAt(
                rec.deterministic_features.canonical_topology
                  .per_residue_topology,
                site.anchor_residue,
              );
              return (
              <tr key={site.site_id}>
                <td className={styles.cellMono}>
                  <span
                    className={styles.swatch}
                    style={{
                      background: ANCHOR_PALETTE[i % ANCHOR_PALETTE.length],
                    }}
                    aria-hidden="true"
                  />
                  {site.site_id + 1}
                </td>
                <td className={styles.cellMono}>R{site.anchor_residue}</td>
                <td className={styles.cell}>
                  <StatusPill
                    tone={compartmentTone(compartment)}
                    size="sm"
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
                <td
                  className={styles.cellMono}
                  title="Eisenberg-style score. Positive = hydrophobic / lipid-facing-style; negative = polar / solvent-exposed-style. Magnitude shapes which binder chemistries pair well — neither better nor worse on its own."
                >
                  {site.hydrophobicity > 0 ? "+" : ""}
                  {site.hydrophobicity.toFixed(1)}
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={styles.footer}>
        <a
          href={`https://surface-bind.inria.fr/protein.html?uniprot=${rec.gene.uniprot_acc}`}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.link}
        >
          SURFACE-Bind entry ↗
        </a>
        {sb.pdbs.length > 0 ? (
          <>
            {" · "}
            {sb.pdbs.length} cross-referenced PDB{sb.pdbs.length === 1 ? "" : "s"}{" "}
            (first few:{" "}
            {sb.pdbs.slice(0, 5).map((p, i) => (
              <span key={p}>
                <a
                  href={`https://www.rcsb.org/structure/${p}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.linkPdb}
                >
                  {p}
                </a>
                {i < Math.min(4, sb.pdbs.length - 1) ? ", " : ""}
              </span>
            ))}
            {sb.pdbs.length > 5 ? ", …" : ""})
          </>
        ) : null}
      </p>
    </SectionCard>
  );
}
