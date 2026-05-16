import type {
  AccessibilityRelevance,
  EvidenceGrade,
  ExpressionLevel,
  Severity,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { CiteCount } from "../CiteCount/CiteCount";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./SurfaceEvidenceCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function gradeTone(v: EvidenceGrade) {
  if (v === "direct_multi_method") return "success" as const;
  if (v === "direct_single_method") return "teal" as const;
  if (v === "supportive_but_indirect") return "amber" as const;
  if (v === "conflicting") return "danger" as const;
  return "neutral" as const;
}

function relevanceTone(v: AccessibilityRelevance) {
  if (v === "direct_surface_accessibility") return "success" as const;
  if (v === "supports_surface_localization") return "teal" as const;
  if (v === "supports_membrane_association") return "lavender" as const;
  if (v === "expression_only") return "amber" as const;
  return "neutral" as const;
}

function levelTone(v: ExpressionLevel) {
  if (v === "high") return "success" as const;
  if (v === "moderate") return "teal" as const;
  if (v === "low") return "amber" as const;
  if (v === "absent") return "neutral" as const;
  return "neutral" as const;
}

function severityTone(v: Severity | "high" | "moderate" | "low" | "unclear") {
  if (v === "high") return "danger" as const;
  if (v === "moderate") return "amber" as const;
  if (v === "low") return "success" as const;
  return "neutral" as const;
}

export function SurfaceEvidenceCard({ rec, n }: Props) {
  const se = rec.surface_evidence;
  return (
    <SectionCard
      n={n}
      eyebrow="Surface evidence"
      title="Plasma-membrane evidence"
      meta={`Evidence grade · ${prettyEnum(se.evidence_grade)} · ${se.methods.length} method block${
        se.methods.length === 1 ? "" : "s"
      }`}
    >
      <div className={styles.banner}>
        <StatusPill tone={gradeTone(se.evidence_grade)}>
          {prettyEnum(se.evidence_grade)}
        </StatusPill>
        <p className={styles.bannerProse}>{se.grade_rationale}</p>
      </div>

      {se.methods.length === 0 ? (
        <p className={styles.empty}>No method observations recorded.</p>
      ) : (
        <div className={styles.methods}>
          {se.methods.map((m, i) => (
            <div key={i} className={styles.method}>
              <div className={styles.methodHead}>
                <StatusPill tone="teal" size="sm">
                  {prettyEnum(m.method_subclass)}
                </StatusPill>
                <StatusPill tone="neutral" size="sm">
                  {prettyEnum(m.permeabilization)}
                </StatusPill>
                <StatusPill tone="lavender" size="sm">
                  {prettyEnum(m.expression_system)}
                </StatusPill>
                <StatusPill tone={relevanceTone(m.accessibility_relevance)} size="sm">
                  {prettyEnum(m.accessibility_relevance)}
                </StatusPill>
                <CiteCount ids={m.cited_evidence_ids} label="Method" />
              </div>

              {m.antibodies.length > 0 ? (
                <div className={styles.antibodies}>
                  <p className={`label-mono ${styles.subLabel}`}>Antibodies</p>
                  <ul className={styles.abList}>
                    {m.antibodies.map((ab, j) => (
                      <li key={j} className={styles.abItem}>
                        <span className={styles.abName}>{ab.name}</span>
                        <span className={styles.abMeta}>
                          {[ab.clone, ab.vendor, ab.catalog, ab.rrid]
                            .filter((x): x is string => Boolean(x))
                            .join(" · ") || "(reagent details not in source)"}
                        </span>
                        <span className={styles.abPills}>
                          <StatusPill tone="neutral" size="sm">
                            {prettyEnum(ab.monoclonal_or_polyclonal)}
                          </StatusPill>
                          <StatusPill tone="teal" size="sm">
                            {prettyEnum(ab.antibody_epitope_region)}
                          </StatusPill>
                          <StatusPill
                            tone={
                              ab.validation_strength === "strong"
                                ? "success"
                                : ab.validation_strength === "moderate"
                                ? "amber"
                                : "neutral"
                            }
                            size="sm"
                          >
                            {prettyEnum(ab.validation_strength)} validation
                          </StatusPill>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {m.expression_observations.length > 0 ? (
                <div className={styles.obsBlock}>
                  <p className={`label-mono ${styles.subLabel}`}>Observations</p>
                  <table className={styles.obsTable}>
                    <thead>
                      <tr>
                        <th scope="col">Context</th>
                        <th scope="col">Sample</th>
                        <th scope="col">Level</th>
                        <th scope="col">Cites</th>
                      </tr>
                    </thead>
                    <tbody>
                      {m.expression_observations.map((o, k) => (
                        <tr key={k}>
                          <td>{o.context}</td>
                          <td>{prettyEnum(o.sample_type)}</td>
                          <td>
                            <StatusPill tone={levelTone(o.level)} size="sm">
                              {prettyEnum(o.level)}
                            </StatusPill>
                          </td>
                          <td>
                            <CiteCount ids={o.cited_evidence_ids} label="Observation" />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {se.non_surface_expression.length > 0 ? (
        <div className={styles.subsection}>
          <p className={`label-mono ${styles.subhead}`}>
            Non-surface expression (RNA / bulk protein)
          </p>
          <table className={styles.obsTable}>
            <thead>
              <tr>
                <th scope="col">Context</th>
                <th scope="col">Sample</th>
                <th scope="col">Measurement</th>
                <th scope="col">Level</th>
                <th scope="col">Cites</th>
              </tr>
            </thead>
            <tbody>
              {se.non_surface_expression.map((o, i) => (
                <tr key={i}>
                  <td>{o.context}</td>
                  <td>{prettyEnum(o.sample_type)}</td>
                  <td>{prettyEnum(o.measurement_type)}</td>
                  <td>
                    <StatusPill tone={levelTone(o.level)} size="sm">
                      {prettyEnum(o.level)}
                    </StatusPill>
                  </td>
                  <td>
                    <CiteCount ids={o.cited_evidence_ids} label="Expression" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {se.therapeutic_engagement ? (
        <div className={styles.therapeutic}>
          <p className={`label-mono ${styles.subhead}`}>Therapeutic engagement</p>
          <StatusPill tone="maroon" size="md">
            {prettyEnum(se.therapeutic_engagement.highest_stage)}
          </StatusPill>
          <p className={styles.therapeuticProse}>
            {se.therapeutic_engagement.description}
          </p>
          <p className={styles.therapeuticRationale}>
            <span className={`label-mono ${styles.subLabel}`}>
              Surface-form rationale
            </span>
            <span>{se.therapeutic_engagement.surface_form_rationale}</span>
            <CiteCount
              ids={se.therapeutic_engagement.cited_evidence_ids}
              label="Therapeutic"
            />
          </p>
        </div>
      ) : null}

      {se.contradicting_evidence.length > 0 ? (
        <div className={styles.subsection}>
          <p className={`label-mono ${styles.subhead}`}>Contradicting evidence</p>
          <ul className={styles.contradictions}>
            {se.contradicting_evidence.map((c, i) => (
              <li key={i} className={styles.contradiction}>
                <div className={styles.contradictionHead}>
                  <StatusPill
                    tone={severityTone(c.severity_for_surface_accessibility)}
                    size="sm"
                  >
                    {prettyEnum(c.contradiction_type)}
                  </StatusPill>
                  <span className={styles.contradictionSeverity}>
                    severity · {prettyEnum(c.severity_for_surface_accessibility)}
                  </span>
                  <CiteCount ids={c.cited_evidence_ids} label="Contradiction" />
                </div>
                <p className={styles.contradictionClaim}>{c.claim}</p>
                {c.likely_explanation ? (
                  <p className={styles.contradictionExplain}>
                    <span className={`label-mono ${styles.subLabel}`}>
                      Likely explanation
                    </span>{" "}
                    {c.likely_explanation}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </SectionCard>
  );
}
