import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { SectionCard } from "../SectionCard/SectionCard";
import styles from "./ParalogsCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

/**
 * Paralogs §4 — deterministic Compara table only.
 *
 * PR23 round 10 dropped the LLM cross-reactivity verdict block:
 * per-antibody cross-reactivity behavior is captured in
 * `AntibodyRef.cross_reactivity_notes` (§1), and the gene-family
 * prior is captured by the deterministic
 * `filters.max_paralog_ecd_pct_identity` rollup. Catalog readers
 * filter on raw %ECD identity rather than an LLM call.
 */
export function ParalogsCard({ rec, n }: Props) {
  const paralogs = rec.deterministic_features.paralogs;
  const comparaVersion = paralogs[0]?.compara_version ?? "—";

  return (
    <SectionCard
      n={n}
      eyebrow="Paralogs"
      title="Paralogs (Ensembl Compara)"
      meta={`Deterministic · Ensembl Compara ${comparaVersion} · within-species paralogs`}
      lede="Compara within-species paralog %ECD identities. Per-antibody cross-reactivity behavior is captured per-clone under §1 Surface Evidence (AntibodyRef.cross_reactivity_notes). The LLM cross-reactivity verdict was deferred to v1.x."
    >
      {paralogs.length === 0 ? (
        <p className={styles.empty}>No paralogs in Compara.</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Symbol</th>
              <th scope="col">UniProt</th>
              <th scope="col">ECD %id</th>
              <th scope="col">Family</th>
            </tr>
          </thead>
          <tbody>
            {paralogs.map((p, i) => (
              <tr key={i}>
                <td>{p.paralog_symbol}</td>
                <td>
                  <a
                    className={styles.link}
                    href={`https://www.uniprot.org/uniprotkb/${p.paralog_uniprot_acc}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <span className={styles.mono}>{p.paralog_uniprot_acc}</span>
                  </a>
                </td>
                <td>{p.ecd_pct_identity.toFixed(1)}%</td>
                <td>
                  <span className={styles.mono}>{p.family_id}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SectionCard>
  );
}
