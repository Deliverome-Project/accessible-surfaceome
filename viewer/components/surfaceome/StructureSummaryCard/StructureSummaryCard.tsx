import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./StructureSummaryCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function plddtTone(plddt: number) {
  if (plddt >= 90) return "success" as const;
  if (plddt >= 70) return "teal" as const;
  if (plddt >= 50) return "amber" as const;
  return "danger" as const;
}

export function StructureSummaryCard({ rec, n }: Props) {
  const s = rec.deterministic_features.structure;
  return (
    <SectionCard
      n={n}
      eyebrow="Structure summary"
      title="Predicted structure (AlphaFold + DeepTMHMM)"
      meta={`AlphaFold DB ${s.afdb_version} · ECD-region stats`}
    >
      <dl className={styles.stats}>
        <div className={styles.stat}>
          <dt className={`label-mono ${styles.k}`}>AFDB ID</dt>
          <dd className={styles.v}>
            <a
              className={styles.link}
              href={`https://alphafold.ebi.ac.uk/entry/${rec.gene.uniprot_acc}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span className={styles.mono}>{s.afdb_id}</span>
            </a>
          </dd>
        </div>
        <div className={styles.stat}>
          <dt className={`label-mono ${styles.k}`}>ECD mean pLDDT</dt>
          <dd className={styles.v}>
            <StatusPill tone={plddtTone(s.ecd_mean_plddt)} size="md">
              {s.ecd_mean_plddt.toFixed(1)}
            </StatusPill>
          </dd>
        </div>
        <div className={styles.stat}>
          <dt className={`label-mono ${styles.k}`}>ECD disordered fraction</dt>
          <dd className={styles.v}>{(s.ecd_disordered_fraction * 100).toFixed(1)}%</dd>
        </div>
        {/* ecd_solvent_accessible_fraction was considered + dropped
            in PR23 round 9 — would have required a new SASA dep
            (FreeSASA / mkdssp); the two pLDDT-based metrics carry
            the structure-quality signal without it. Real epitope-
            accessibility scoring is deferred to v1.x. */}
      </dl>

      <p className={styles.attribution}>
        Structure data from{" "}
        <a
          className={styles.attributionLink}
          href={`https://alphafold.ebi.ac.uk/entry/${rec.gene.uniprot_acc}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {s.source}
        </a>{" "}
        · {s.attribution} · licensed{" "}
        <a
          className={styles.attributionLink}
          href="https://creativecommons.org/licenses/by/4.0/"
          target="_blank"
          rel="noopener noreferrer"
        >
          {s.license}
        </a>
        {s.citations.length > 0 ? (
          <>
            {" "}
            · cite{" "}
            {s.citations.map((c, i) => (
              <span key={i} className={styles.mono}>
                {c}
                {i < s.citations.length - 1 ? "; " : ""}
              </span>
            ))}
          </>
        ) : null}
      </p>
    </SectionCard>
  );
}
