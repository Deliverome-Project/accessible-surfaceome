import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { FieldRow } from "../FieldRow/FieldRow";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./LandscapeCard.module.css";

interface LandscapeCardProps {
  rec: SurfaceomeRecord;
  n: number;
}

export function LandscapeCard({ rec, n }: LandscapeCardProps) {
  const newPreclinical =
    rec.surface_engagement_validation?.preclinical_evidence ?? [];
  const legacyTL = rec.therapeutic_landscape;
  const legacyPatents = legacyTL?.patent_disclosures ?? [];
  const legacyPreclinical = legacyTL?.preclinical_evidence ?? [];

  const total = newPreclinical.length + legacyPatents.length + legacyPreclinical.length;
  if (total === 0) return null;

  return (
    <SectionCard
      n={n}
      eyebrow="Engagement validation"
      title={<>What&apos;s been <em>engaged</em></>}
      meta="Preclinical studies that demonstrate extracellular engagement on live cells."
    >
      {newPreclinical.length > 0 ? (
        <div className={styles.subsection}>
          <h3 className={`label-mono ${styles.subhead}`}>Surface engagement validation</h3>
          {newPreclinical.map((p, i) => (
            <FieldRow
              key={`sev-${i}`}
              k={p.citation}
              ids={p.cited_evidence_ids}
            >
              <p className={styles.prose}>{p.finding_summary}</p>
            </FieldRow>
          ))}
        </div>
      ) : null}

      {legacyPatents.length > 0 ? (
        <div className={styles.subsection}>
          <div className={styles.subheadRow}>
            <h3 className={`label-mono ${styles.subhead}`}>Patent disclosures</h3>
            <StatusPill tone="neutral" size="sm">legacy v0.3.2</StatusPill>
          </div>
          {legacyPatents.map((p, i) => (
            <FieldRow
              key={`pat-${i}`}
              k={p.wo_number}
              ids={p.cited_evidence_ids}
            >
              <p className={styles.title}>{p.title}</p>
              <p className={styles.meta}>
                {p.applicant} · priority {p.priority_year} · {prettyEnum(p.modality)}
              </p>
              <p className={styles.prose}>{p.summary}</p>
            </FieldRow>
          ))}
        </div>
      ) : null}

      {legacyPreclinical.length > 0 ? (
        <div className={styles.subsection}>
          <div className={styles.subheadRow}>
            <h3 className={`label-mono ${styles.subhead}`}>Preclinical evidence</h3>
            <StatusPill tone="neutral" size="sm">legacy v0.3.2</StatusPill>
          </div>
          {legacyPreclinical.map((p, i) => (
            <FieldRow
              key={`leg-pre-${i}`}
              k={p.citation}
              ids={p.cited_evidence_ids}
            >
              {p.modality ? (
                <p className={styles.meta}>{prettyEnum(p.modality)}</p>
              ) : null}
              <p className={styles.prose}>{p.finding_summary}</p>
            </FieldRow>
          ))}
        </div>
      ) : null}
    </SectionCard>
  );
}
