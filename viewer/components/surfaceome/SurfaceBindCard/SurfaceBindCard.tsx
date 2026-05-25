import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./SurfaceBindCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
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
          In SURFACE-Bind ({sb.main_class}
          {sb.sub_class ? ` · ${sb.sub_class}` : ""}), but no surface
          patches cleared the MaSIF targetability threshold. The
          protein was scored; the surface chemistry didn't yield
          designable binder seeds.
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
        Each row is one MaSIF-scored surface patch. Anchor = patch
        center residue. BSA tone follows the typical antibody-antigen
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
              <th scope="col" className={`label-mono ${styles.head}`}>
                Site
              </th>
              <th scope="col" className={`label-mono ${styles.head}`}>
                Anchor
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
            {sb.sites.map((site) => (
              <tr key={site.site_id}>
                <td className={styles.cellMono}>{site.site_id}</td>
                <td className={styles.cellMono}>R{site.anchor_residue}</td>
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
            ))}
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
