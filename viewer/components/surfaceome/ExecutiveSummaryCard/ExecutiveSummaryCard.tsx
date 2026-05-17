import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { EvidenceChipList } from "../EvidenceChip/EvidenceChip";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./ExecutiveSummaryCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function accessibilityTone(v: string) {
  if (v === "high") return "success" as const;
  if (v === "moderate") return "teal" as const;
  if (v === "low") return "amber" as const;
  return "neutral" as const;
}

function confidenceTone(v: string) {
  if (v === "high") return "success" as const;
  if (v === "moderate") return "lavender" as const;
  if (v === "low") return "amber" as const;
  return "neutral" as const;
}

function stateTone(v: string) {
  if (v === "low") return "success" as const;
  if (v === "moderate") return "amber" as const;
  if (v === "high") return "danger" as const;
  return "neutral" as const;
}

function gradeTone(v: string) {
  if (v === "direct_multi_method") return "success" as const;
  if (v === "direct_single_method") return "teal" as const;
  if (v === "supportive_but_indirect") return "amber" as const;
  if (v === "conflicting") return "danger" as const;
  return "neutral" as const;
}

export function ExecutiveSummaryCard({ rec, n }: Props) {
  const e = rec.executive_summary;
  return (
    <SectionCard
      n={n}
      eyebrow="Executive summary"
      title="Overview and headline call"
      meta="LLM synthesis · top-line accessibility judgment + headline risks"
    >
      <p className={styles.paragraph}>{e.one_paragraph}</p>

      <ul className={styles.pillStrip} aria-label="Executive summary pills">
        <li>
          <StatusPill tone={accessibilityTone(e.surface_accessibility)}>
            Accessibility · {prettyEnum(e.surface_accessibility)}
          </StatusPill>
        </li>
        <li>
          <StatusPill tone="teal">{prettyEnum(e.subcategory)}</StatusPill>
        </li>
        <li>
          <StatusPill tone={gradeTone(e.evidence_grade_summary)}>
            {prettyEnum(e.evidence_grade_summary)}
          </StatusPill>
        </li>
        <li>
          <StatusPill tone={confidenceTone(e.confidence)}>
            Confidence · {prettyEnum(e.confidence)}
          </StatusPill>
        </li>
        <li>
          <StatusPill tone={stateTone(e.state_dependence)}>
            State dep · {prettyEnum(e.state_dependence)}
          </StatusPill>
        </li>
      </ul>

      {e.headline_risks.length > 0 ? (
        <p className={styles.risks}>
          <span className={`label-mono ${styles.risksLabel}`}>Headline risks</span>
          <span className={styles.risksValue}>
            {e.headline_risks.map((r) => prettyEnum(r)).join(" · ")}
          </span>
        </p>
      ) : (
        <p className={styles.risks}>
          <span className={`label-mono ${styles.risksLabel}`}>Headline risks</span>
          <span className={styles.risksValue}>None flagged.</span>
        </p>
      )}

      {/* Inline citation chips — click any chip to open the global
       *  EvidenceDrawer with that evidence's full claim + verbatim
       *  quote + source links. Mirrors the v2 sample's per-block
       *  citations strip (data/eval/surfaceome_v2_samples). */}
      <EvidenceChipList
        ids={e.cited_evidence_ids}
        label="Cited evidence"
      />
    </SectionCard>
  );
}
