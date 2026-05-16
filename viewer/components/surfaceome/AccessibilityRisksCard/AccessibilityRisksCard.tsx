import type {
  EvidenceStrength,
  Severity,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { CiteCount } from "../CiteCount/CiteCount";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./AccessibilityRisksCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function severityTone(v: Severity | "none") {
  if (v === "high") return "danger" as const;
  if (v === "moderate") return "amber" as const;
  if (v === "low") return "success" as const;
  if (v === "none") return "success" as const;
  return "neutral" as const;
}

function strengthTone(v: EvidenceStrength) {
  if (v === "strong") return "success" as const;
  if (v === "moderate") return "amber" as const;
  return "neutral" as const;
}

function presenceLabel(present: boolean) {
  return present ? "Present" : "Not present";
}

export function AccessibilityRisksCard({ rec, n }: Props) {
  const r = rec.accessibility_risks;
  const ctx = rec.deterministic_features.canonical_topology;
  return (
    <SectionCard
      n={n}
      eyebrow="Accessibility risks"
      title="Accessibility caveats"
      meta="Six subsections · severity + evidence-strength on each · cites point into the evidence ledger"
    >
      <div className={styles.subsection}>
        <div className={styles.subHead}>
          <p className={styles.subTitle}>Shed form</p>
          <StatusPill tone={severityTone(r.shed_form.severity)} size="sm">
            severity · {prettyEnum(r.shed_form.severity)}
          </StatusPill>
          <StatusPill tone={strengthTone(r.shed_form.evidence_strength)} size="sm">
            evidence · {prettyEnum(r.shed_form.evidence_strength)}
          </StatusPill>
          <StatusPill tone={r.shed_form.present ? "danger" : "neutral"} size="sm">
            {presenceLabel(r.shed_form.present)}
          </StatusPill>
          <CiteCount ids={r.shed_form.cited_evidence_ids} label="Shed form" />
        </div>
        {r.shed_form.mechanism ? (
          <p className={styles.prose}>
            <span className={`label-mono ${styles.muted}`}>Mechanism</span>{" "}
            {r.shed_form.mechanism}
            {r.shed_form.sheddase_if_known
              ? ` · sheddase: ${r.shed_form.sheddase_if_known}`
              : ""}
          </p>
        ) : null}
      </div>

      <div className={styles.subsection}>
        <div className={styles.subHead}>
          <p className={styles.subTitle}>Secreted form</p>
          <StatusPill tone={severityTone(r.secreted_form.severity)} size="sm">
            severity · {prettyEnum(r.secreted_form.severity)}
          </StatusPill>
          <StatusPill tone={strengthTone(r.secreted_form.evidence_strength)} size="sm">
            evidence · {prettyEnum(r.secreted_form.evidence_strength)}
          </StatusPill>
          <StatusPill tone={r.secreted_form.present ? "danger" : "neutral"} size="sm">
            {presenceLabel(r.secreted_form.present)}
          </StatusPill>
          <CiteCount ids={r.secreted_form.cited_evidence_ids} label="Secreted form" />
        </div>
        {r.secreted_form.source ? (
          <p className={styles.prose}>
            <span className={`label-mono ${styles.muted}`}>Source</span>{" "}
            {prettyEnum(r.secreted_form.source)}
            {r.secreted_form.ratio_to_membrane != null
              ? ` · ratio-to-membrane: ${r.secreted_form.ratio_to_membrane}`
              : ""}
          </p>
        ) : null}
      </div>

      <div className={styles.subsection}>
        <div className={styles.subHead}>
          <p className={styles.subTitle}>Restricted subdomain</p>
          <StatusPill tone={severityTone(r.restricted_subdomain.severity)} size="sm">
            severity · {prettyEnum(r.restricted_subdomain.severity)}
          </StatusPill>
          <StatusPill
            tone={strengthTone(r.restricted_subdomain.evidence_strength)}
            size="sm"
          >
            evidence · {prettyEnum(r.restricted_subdomain.evidence_strength)}
          </StatusPill>
          <StatusPill tone="lavender" size="sm">
            {prettyEnum(r.restricted_subdomain.domain)}
          </StatusPill>
          <StatusPill
            tone={r.restricted_subdomain.present ? "danger" : "neutral"}
            size="sm"
          >
            {presenceLabel(r.restricted_subdomain.present)}
          </StatusPill>
          <CiteCount
            ids={r.restricted_subdomain.cited_evidence_ids}
            label="Restricted subdomain"
          />
        </div>
        {r.restricted_subdomain.rationale ? (
          <p className={styles.prose}>{r.restricted_subdomain.rationale}</p>
        ) : null}
      </div>

      <div className={styles.subsection}>
        <div className={styles.subHead}>
          <p className={styles.subTitle}>Co-receptor requirements</p>
          <StatusPill
            tone={
              r.co_receptor_requirements.surface_expression_dependency === "required"
                ? "danger"
                : r.co_receptor_requirements.surface_expression_dependency ===
                  "modulatory"
                ? "amber"
                : "neutral"
            }
            size="sm"
          >
            dependency · {prettyEnum(r.co_receptor_requirements.surface_expression_dependency)}
          </StatusPill>
          <StatusPill tone="lavender" size="sm">
            evidence basis · {prettyEnum(r.co_receptor_requirements.evidence_basis)}
          </StatusPill>
          <CiteCount
            ids={r.co_receptor_requirements.cited_evidence_ids}
            label="Co-receptor"
          />
        </div>
        {r.co_receptor_requirements.partners.length > 0 ? (
          <p className={styles.prose}>
            <span className={`label-mono ${styles.muted}`}>Partners</span>{" "}
            {r.co_receptor_requirements.partners.map((p, i) => (
              <span key={i} className={styles.partner}>
                {p}
                {i < r.co_receptor_requirements.partners.length - 1 ? ", " : ""}
              </span>
            ))}
          </p>
        ) : null}
        {r.co_receptor_requirements.rationale ? (
          <p className={styles.prose}>{r.co_receptor_requirements.rationale}</p>
        ) : null}
      </div>

      <div className={styles.subsection}>
        <div className={styles.subHead}>
          <p className={styles.subTitle}>ECD size assessment</p>
          <StatusPill
            tone={
              r.ecd_size_assessment.ecd_accessibility_class === "large"
                ? "success"
                : r.ecd_size_assessment.ecd_accessibility_class === "moderate"
                ? "teal"
                : r.ecd_size_assessment.ecd_accessibility_class === "small"
                ? "amber"
                : "danger"
            }
            size="sm"
          >
            {prettyEnum(r.ecd_size_assessment.ecd_accessibility_class)}
          </StatusPill>
          <span className={styles.muted}>
            (deterministic ECD len: {ctx.ecd_length_residues} aa)
          </span>
          <CiteCount
            ids={r.ecd_size_assessment.cited_evidence_ids}
            label="ECD size"
          />
        </div>
        {r.ecd_size_assessment.rationale ? (
          <p className={styles.prose}>{r.ecd_size_assessment.rationale}</p>
        ) : null}
      </div>

      <div className={styles.subsection}>
        <div className={styles.subHead}>
          <p className={styles.subTitle}>Epitope masking</p>
          {r.epitope_masking.mechanism.length === 0 ? (
            <StatusPill tone="neutral" size="sm">
              mechanism · none documented
            </StatusPill>
          ) : (
            r.epitope_masking.mechanism.map((m) => (
              <StatusPill key={m} tone="lavender" size="sm">
                {prettyEnum(m)}
              </StatusPill>
            ))
          )}
          <StatusPill tone={severityTone(r.epitope_masking.severity)} size="sm">
            severity · {prettyEnum(r.epitope_masking.severity)}
          </StatusPill>
          <StatusPill
            tone={strengthTone(r.epitope_masking.evidence_strength)}
            size="sm"
          >
            evidence · {prettyEnum(r.epitope_masking.evidence_strength)}
          </StatusPill>
          <CiteCount
            ids={r.epitope_masking.cited_evidence_ids}
            label="Epitope masking"
          />
        </div>
        {r.epitope_masking.rationale ? (
          <p className={styles.prose}>{r.epitope_masking.rationale}</p>
        ) : null}
      </div>
    </SectionCard>
  );
}
