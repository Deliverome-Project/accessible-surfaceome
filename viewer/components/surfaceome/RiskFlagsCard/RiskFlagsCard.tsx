import type { SurfaceomeRecord, Severity } from "../../../lib/surfaceome-types";
import { titleCase } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { CiteCount } from "../CiteCount/CiteCount";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./RiskFlagsCard.module.css";

interface RiskFlagsCardProps {
  rec: SurfaceomeRecord;
  n: number;
}

const SEVERITY_TONE: Record<Severity, "danger" | "warn" | "amber" | "neutral"> = {
  blocking: "danger",
  high: "warn",
  medium: "amber",
  low: "neutral",
};

export function RiskFlagsCard({ rec, n }: RiskFlagsCardProps) {
  if (!rec.risk_flags.length) return null;
  return (
    <SectionCard
      n={n}
      eyebrow="Risk flags"
      title={<>What could <em>derail</em> it</>}
      meta={`${rec.risk_flags.length} flag${rec.risk_flags.length === 1 ? "" : "s"}`}
    >
      <ol className={styles.list}>
        {rec.risk_flags.map((r, i) => (
          <li key={i} className={styles.item}>
            <div className={styles.head}>
              <StatusPill tone={SEVERITY_TONE[r.severity]} size="sm">
                {r.severity}
              </StatusPill>
              <h3 className={styles.kind}>
                {r.kind_other_label || titleCase(r.kind)}
              </h3>
              <CiteCount ids={r.cited_evidence_ids} label={r.kind} />
            </div>
            <p className={styles.prose}>{r.description}</p>
          </li>
        ))}
      </ol>
    </SectionCard>
  );
}
