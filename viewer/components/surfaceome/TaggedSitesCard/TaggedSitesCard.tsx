"use client";

import { SectionCard } from "../SectionCard/SectionCard";
import type {
  EvidenceSource,
  TaggedSite,
  TaggedSitesFile,
} from "../../../lib/tag-sites-types";
import {
  CATEGORY_HEX,
  CATEGORY_LABEL,
  tagSiteCategory,
} from "../../../lib/tag-sites-types";
import styles from "./TaggedSitesCard.module.css";

const KIND_LABEL: Record<TaggedSite["site_kind"], string> = {
  terminal_n: "N-terminus",
  terminal_c: "C-terminus",
  internal: "Internal loop",
};

/** Display token for the junction: prefer the canonical residue_label
 *  ("G101"), else derive a readable fallback from site_kind. */
function residueDisplay(s: TaggedSite): string {
  if (s.residue_label) return s.residue_label;
  if (s.site_kind === "terminal_c") return "C-term";
  if (s.site_kind === "terminal_n") return "N-term";
  if (s.insert_after_residue != null) return `after ${s.insert_after_residue}`;
  return "—";
}

/** Resolve an evidence source to an external href: explicit url, else a
 *  PubMed link from the PMID, else a doi.org link. Null if unlinkable. */
function sourceHref(src: EvidenceSource): string | null {
  if (src.url) return src.url;
  if (src.pmid) return `https://pubmed.ncbi.nlm.nih.gov/${src.pmid}/`;
  if (src.doi) return `https://doi.org/${src.doi}`;
  return null;
}

function Sources({ sources }: { sources: EvidenceSource[] }) {
  if (!sources.length) return <span className={styles.muted}>—</span>;
  return (
    <span className={styles.sources}>
      {sources.map((src, i) => {
        const href = sourceHref(src);
        const label =
          src.citation ||
          (src.pmid ? `PMID ${src.pmid}` : src.doi ? `DOI ${src.doi}` : "source");
        return href ? (
          <a key={i} href={href} target="_blank" rel="noopener noreferrer">
            {label}
          </a>
        ) : (
          <span key={i}>{label}</span>
        );
      })}
    </span>
  );
}

/** Literature-validated tag sites: residue + placement + tag + evidence +
 *  linked sources, with a muted detail line (rationale carries the folded
 *  validation_level / position / source_tier / entailment tags). */
function LiteratureTable({ sites }: { sites: TaggedSite[] }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.head}>Residue</th>
            <th className={styles.head}>Placement</th>
            <th className={styles.head}>Compartment</th>
            <th className={styles.head}>Tag</th>
            <th className={styles.head}>Evidence</th>
            <th className={styles.head}>Conf.</th>
            <th className={styles.head}>Sources</th>
          </tr>
        </thead>
        <tbody>
          {sites.map((s) => (
            <tr key={s.site_id}>
              <td className={styles.residue}>{residueDisplay(s)}</td>
              <td>{KIND_LABEL[s.site_kind]}</td>
              <td>{s.compartment ?? s.topology_state ?? "—"}</td>
              <td>{s.tag_type || "—"}</td>
              <td className={styles.evidence}>
                {s.evidence_type || "—"}
                {s.functional_impact_measured ? (
                  <span className={styles.detail}>{s.functional_impact_measured}</span>
                ) : null}
              </td>
              <td>{s.confidence ?? "—"}</td>
              <td>
                <Sources sources={s.sources} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Deterministic candidate sites: computed insertion points with the
 *  path (disorder / surface_loop), residue range, and structural scores. */
function DeterministicTable({ sites }: { sites: TaggedSite[] }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.head}>Residue</th>
            <th className={styles.head}>Range</th>
            <th className={styles.head}>Placement</th>
            <th className={styles.head}>Compartment</th>
            <th className={styles.head}>Path</th>
            <th className={styles.head}>pLDDT</th>
            <th className={styles.head}>Conf.</th>
          </tr>
        </thead>
        <tbody>
          {sites.map((s) => (
            <tr key={s.site_id}>
              <td className={styles.residue}>{residueDisplay(s)}</td>
              <td className={styles.muted}>{s.residue_range ?? "—"}</td>
              <td>{KIND_LABEL[s.site_kind]}</td>
              <td>{s.compartment ?? s.topology_state ?? "—"}</td>
              <td>{s.det_path ?? "—"}</td>
              <td>{s.plddt != null ? s.plddt.toFixed(1) : "—"}</td>
              <td>{s.confidence ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export interface TaggedSitesCardProps {
  taggedSites: TaggedSitesFile | null;
  n?: number;
}

/**
 * §Tag sites — a dedicated section (its own tab, distinct from
 * Internalization) listing engineered epitope/tag insertion points for the
 * protein. Two provenances, matching the structure-viewer overlay legend:
 *   • literature_retrieved — tags published + validated in the literature
 *     (hybrid lit-search + web_search agent), with linked sources;
 *   • deterministic_computed — computed candidate insertion points from the
 *     disorder / surface-loop pipeline (pLDDT + RSA/DSSP, feature-veto).
 * `validated_literature` provenance is validation-only and never rendered
 * (mirrors `renderableTagSites`).
 */
export function TaggedSitesCard({ taggedSites, n }: TaggedSitesCardProps) {
  const sites = taggedSites?.sites ?? [];
  const lit = sites.filter((s) => s.provenance === "literature_retrieved");
  const det = sites.filter((s) => s.provenance === "deterministic_computed");
  const legendCategories = Array.from(
    new Set([...lit, ...det].map((s) => tagSiteCategory(s))),
  );

  if (!taggedSites?.has_data || lit.length + det.length === 0) {
    return (
      <SectionCard n={n} title="Tag sites">
        <p className={styles.empty}>No tag-site suggestions for this protein yet.</p>
      </SectionCard>
    );
  }

  return (
    <SectionCard
      n={n}
      title="Tag sites"
      lede="Engineered epitope/tag insertion points — literature-validated tags and computed candidate positions. Highlighted on the structure viewer above."
    >
      <p className={styles.legend}>
        {legendCategories.map((c) => (
          <span key={c} className={styles.legendItem}>
            <span
              className={styles.dot}
              style={{ background: CATEGORY_HEX[c] }}
              aria-hidden="true"
            />
            {CATEGORY_LABEL[c]}
          </span>
        ))}
      </p>

      {lit.length > 0 ? (
        <>
          <h3 className={styles.subhead}>Literature-validated ({lit.length})</h3>
          <LiteratureTable sites={lit} />
        </>
      ) : null}

      {det.length > 0 ? (
        <>
          <h3 className={styles.subhead}>Computed candidates ({det.length})</h3>
          <DeterministicTable sites={det} />
        </>
      ) : null}
    </SectionCard>
  );
}
