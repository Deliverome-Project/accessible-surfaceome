import type { SurfaceomeRecord, TissueLevel } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { EvidenceChipList } from "../EvidenceChip/EvidenceChip";
import { FeatureRationales } from "../FeatureChips/FeatureChips";
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
// Disease-context display order: normal first (the on-target / off-tumor
// toxicity baseline), then the disease reads. Lets the reader see each
// organ's normal-tissue level above its tumor level.
const DISEASE_CONTEXT_RANK: Record<string, number> = {
  normal: 0,
  tumor_adjacent: 1,
  tumor: 2,
  other_disease: 3,
  mixed: 4,
  unknown: 5,
};

export function ExpressionCard({ rec, n }: Props) {
  const bc = rec.biological_context;
  // TRANSITIONAL: pre-migration D1 records predate the ExpressionRow
  // unification and lack `expression`. Fall back to empty so the page
  // renders during the re-sync window. Remove once every served record has
  // been re-annotated and D1 carries `expression`.
  const expression = bc.expression ?? [];
  return (
    <SectionCard
      n={n}
      eyebrow="Expression"
      title="Expression level & tissue distribution"
      meta="Baseline level · breadth · overexpression precedent · by tissue of origin; disease context + level + evidence sit on each cell of origin"
    >
      <FeatureRationales category="expression" rec={rec} />

      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Expression × cell type × disease context</p>
        {expression.length === 0 ? (
          <p className={styles.empty}>No expression rows recorded.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Tissue</th>
                <th scope="col">Cell type</th>
                <th scope="col">Disease context</th>
                <th scope="col">Level (protein)</th>
                <th scope="col">Cell states</th>
                <th scope="col">Cites</th>
              </tr>
            </thead>
            <tbody>
              {expression.map((row, i) => (
                <tr key={i}>
                  <td>{row.tissue || "—"}</td>
                  <td>{row.cell_type || "—"}</td>
                  <td>
                    <span className={styles.mono}>{prettyEnum(row.disease_context)}</span>
                    {row.disease_label ? ` (${row.disease_label})` : ""}
                  </td>
                  <td>
                    <StatusPill tone={tissueLevelTone(row.present)} size="sm">
                      {prettyEnum(row.present)}
                    </StatusPill>
                  </td>
                  <td>{row.cell_states.join(", ") || "—"}</td>
                  <td>
                    <EvidenceChipList ids={row.cited_evidence_ids} label="Cites" />
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
