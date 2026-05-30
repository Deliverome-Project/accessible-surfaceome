import type { SurfaceomeRecord, TissueLevel } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { EvidenceChipList } from "../EvidenceChip/EvidenceChip";
import { FeatureChips } from "../FeatureChips/FeatureChips";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./ExpressionCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function tissueLevelTone(v: TissueLevel) {
  if (v === "high") return "success" as const;
  if (v === "moderate") return "teal" as const;
  if (v === "low") return "amber" as const;
  if (v === "absent") return "neutral" as const;
  if (v === "mixed") return "lavender" as const;
  return "neutral" as const;
}

/**
 * Expression tab — the LLM expression summary chips (level / breadth /
 * overexpression precedent) sitting above the per-tissue expression
 * evidence table that used to live in BiologicalContextCard. Splitting
 * the tissue-level expression rows out of "Biological context" lets the
 * Expression tab map cleanly to its chip category, while the Biology
 * tab keeps localization / anatomical-accessibility / modulation.
 */
export function ExpressionCard({ rec, n }: Props) {
  const bc = rec.biological_context;
  return (
    <SectionCard
      n={n}
      eyebrow="Expression"
      title="Expression level & tissue distribution"
      meta="Baseline level · breadth · overexpression precedent · tissue × disease-context rows"
    >
      <FeatureChips category="expression" rec={rec} />

      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Tissues × disease context</p>
        {bc.tissues.length === 0 ? (
          <p className={styles.empty}>No tissue rows recorded.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Tissue</th>
                <th scope="col">Disease context</th>
                <th scope="col">Level (protein)</th>
                <th scope="col">Cell types</th>
                <th scope="col">Cell states</th>
                <th scope="col">Cites</th>
              </tr>
            </thead>
            <tbody>
              {bc.tissues.map((t, i) => (
                <tr key={i}>
                  <td>{t.tissue}</td>
                  <td>
                    <span className={styles.mono}>{prettyEnum(t.disease_context)}</span>
                  </td>
                  <td>
                    <StatusPill tone={tissueLevelTone(t.present)} size="sm">
                      {prettyEnum(t.present)}
                    </StatusPill>
                  </td>
                  <td>{t.cell_types.join(", ") || "—"}</td>
                  <td>{t.cell_states.join(", ") || "—"}</td>
                  <td>
                    <EvidenceChipList ids={t.cited_evidence_ids} label="Cites" />
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
