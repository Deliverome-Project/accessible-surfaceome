import type {
  CrossReactivityAssessment,
  EvidenceStrength,
  Severity,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { CiteCount } from "../CiteCount/CiteCount";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./ParalogsCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function crossTone(v: CrossReactivityAssessment) {
  if (v === "high") return "danger" as const;
  if (v === "moderate") return "amber" as const;
  if (v === "low") return "success" as const;
  return "neutral" as const;
}

function severityTone(v: Severity) {
  if (v === "high") return "danger" as const;
  if (v === "moderate") return "amber" as const;
  if (v === "low") return "success" as const;
  return "neutral" as const;
}

function strengthTone(v: EvidenceStrength) {
  if (v === "strong") return "success" as const;
  if (v === "moderate") return "amber" as const;
  return "neutral" as const;
}

export function ParalogsCard({ rec, n }: Props) {
  const paralogs = rec.deterministic_features.paralogs;
  const assessments = rec.paralog_assessment;
  const comparaVersion = paralogs[0]?.compara_version ?? "—";

  return (
    <SectionCard
      n={n}
      eyebrow="Paralogs"
      title={
        <>
          The <em>cross-reactivity</em> story
        </>
      }
      meta={`Deterministic table from Ensembl Compara ${comparaVersion} + LLM cross-binding assessment`}
    >
      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>
          Compara paralogs (deterministic)
        </p>
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
      </div>

      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>
          LLM cross-binding assessment
        </p>
        {assessments.length === 0 ? (
          <p className={styles.empty}>
            No LLM cross-binding assessment provided.
          </p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Symbol</th>
                <th scope="col">Cross-reactivity</th>
                <th scope="col">Severity</th>
                <th scope="col">Evidence</th>
                <th scope="col">Rationale</th>
                <th scope="col">Cites</th>
              </tr>
            </thead>
            <tbody>
              {assessments.map((a, i) => (
                <tr key={i}>
                  <td>{a.paralog_symbol}</td>
                  <td>
                    <StatusPill tone={crossTone(a.cross_reactivity_assessment)} size="sm">
                      {prettyEnum(a.cross_reactivity_assessment)}
                    </StatusPill>
                  </td>
                  <td>
                    <StatusPill tone={severityTone(a.severity)} size="sm">
                      {prettyEnum(a.severity)}
                    </StatusPill>
                  </td>
                  <td>
                    <StatusPill tone={strengthTone(a.evidence_strength)} size="sm">
                      {prettyEnum(a.evidence_strength)}
                    </StatusPill>
                  </td>
                  <td>{a.rationale}</td>
                  <td>
                    <CiteCount ids={a.cited_evidence_ids} label="Paralog risk" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </SectionCard>
  );
}
