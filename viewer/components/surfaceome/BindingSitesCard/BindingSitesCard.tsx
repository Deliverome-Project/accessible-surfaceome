"use client";

import { CITATIONS } from "../../../lib/citations";
import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { SectionCard } from "../SectionCard/SectionCard";
import { BindingSitesTabs } from "./BindingSitesTabs";
import styles from "./BindingSitesCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

/**
 * SURFACE-Bind per-site card. Renders one row per MaSIF-scored patch
 * (anchor residue, BSA, α/β seed counts, hydrophobicity) — the
 * deterministic targetability layer alongside our LLM-synthesis
 * sections. Hidden entirely when ``has_data=false`` (the absence
 * signal lives on the GeneHeader's "not scored" pill instead).
 *
 * The sortable per-site table + its column info-tooltips live in the
 * ``SurfaceBindTable`` client component (sorting needs client state).
 * This server component owns the prose + section frame and hands the
 * table only the data it needs (the sites array + the topology
 * string) so the full record isn't serialized into the client bundle.
 */
export function BindingSitesCard({ rec, n }: Props) {
  const sb = rec.deterministic_features.surface_bind;
  const bd = rec.deterministic_features.bindome;
  const bindomeSites = bd?.sites ?? null;
  const hasBindome = !!bindomeSites && bindomeSites.length > 0;
  // Bindome alone is enough to render the card: a protein can be absent
  // from SURFACE-Bind entirely and still have designs landing on it.
  if (!sb.has_data && !hasBindome) return null;
  // SURFACE-Bind has the protein but with zero scored sites — render
  // a thin card explaining what that means rather than hiding it
  // (this case is itself informative — the protein went through
  // scoring but no patch cleared the threshold).
  if (sb.sites.length === 0 && !hasBindome) {
    return (
      <SectionCard
        n={n}
        eyebrow="SURFACE-Bind"
        title="Patch-based targetability"
        meta={`Balbi 2026 (PMID ${CITATIONS.surfaceBind.pmid}) · MaSIF surface scoring · deterministic`}
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
      eyebrow="Binding sites"
      title="Where a binder could go"
      meta={[
        sb.has_data
          ? `SURFACE-Bind ${sb.n_sites} site${sb.n_sites === 1 ? "" : "s"}`
          : null,
        hasBindome ? `Bindome ${bindomeSites.length} site${bindomeSites.length === 1 ? "" : "s"}` : null,
        `PMID ${CITATIONS.surfaceBind.pmid}`,
      ]
        .filter(Boolean)
        .join(" · ")}
    >
      <p className={styles.preamble}>
        Each row is one MaSIF-scored surface patch. The numbered
        purple spheres on the 3D structure above mark each site's
        anchor residue (use "Sites focus" mode on the viewer to
        color the spheres by compartment — red EC / green IC).
        Anchor = patch center residue. BSA is the buried surface
        area — the size of the contact footprint a binder would form
        on the patch. Seed counts split by binder backbone — α-helical
        (3-helix bundles, minihelix) vs β-strand (β-sheet scaffolds).
        Click a column header to sort; hover the ⓘ on the scored
        columns for how each value is rated.{" "}
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
      <p className={styles.icDisclaimer}>
        <strong>Why some sites show "IC":</strong> SURFACE-Bind excludes
        transmembrane regions, not necessarily intracellular domains.
        Because the surfaceome-wide scan uses AF2 models of full
        surfaceome proteins, cytoplasmic domains of receptors can still
        contribute predicted binding sites. The IC annotation marks
        these intracellular-facing sites; they may be valid
        protein-binding surfaces but are not extracellularly
        antibody-accessible. For antibody design, filter to EC sites.
      </p>
      <BindingSitesTabs
        surfaceBindSites={sb.sites}
        bindomeSites={bindomeSites}
        topology={
          rec.deterministic_features.canonical_topology.per_residue_topology
        }
      />
      <p className={styles.footer}>
        <a
          href="https://surface-bind.inria.fr/"
          target="_blank"
          rel="noopener noreferrer"
          className={styles.link}
        >
          SURFACE-Bind ↗
        </a>
      </p>
    </SectionCard>
  );
}
