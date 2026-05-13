import type {
  GapImpact,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { CiteCount } from "../CiteCount/CiteCount";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./KnowledgeGapsCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function impactTone(v: GapImpact) {
  if (v === "high") return "danger" as const;
  if (v === "moderate") return "amber" as const;
  return "neutral" as const;
}

export function KnowledgeGapsCard({ rec, n }: Props) {
  const gaps = rec.knowledge_gaps;
  return (
    <SectionCard
      n={n}
      eyebrow="Knowledge gaps"
      title={
        <>
          What we <em>couldn&apos;t</em> determine
        </>
      }
      meta="Questions the agent tried and couldn't answer. High-impact gaps cap top-line confidence."
    >
      {gaps.length === 0 ? (
        <p className={styles.empty}>All questions addressed.</p>
      ) : (
        <ul className={styles.list}>
          {gaps.map((g, i) => (
            <li key={i} className={styles.item}>
              <p className={styles.question}>{g.question}</p>
              <div className={styles.head}>
                <StatusPill tone={impactTone(g.impact_on_confidence)} size="sm">
                  impact · {prettyEnum(g.impact_on_confidence)}
                </StatusPill>
                <StatusPill tone="neutral" size="sm">
                  {prettyEnum(g.why_unresolved)}
                </StatusPill>
                <CiteCount ids={g.cited_evidence_ids} label="Knowledge gap" />
              </div>
              {g.detail ? <p className={styles.detail}>{g.detail}</p> : null}
              {g.suggested_resolution ? (
                <p className={styles.resolution}>
                  <span className={`label-mono ${styles.muted}`}>Suggested next step</span>
                  {g.suggested_resolution}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
