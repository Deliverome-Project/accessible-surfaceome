import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { FeatureRationales } from "../FeatureChips/FeatureChips";
import { SectionCard } from "../SectionCard/SectionCard";
import { ExpressionTable } from "./ExpressionTable";
import styles from "./ExpressionCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
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
  // Stable-sort by DISEASE_CONTEXT_RANK so normal-tissue rows lead the
  // table (the on-target / off-tumor baseline reads first), followed by
  // tumor_adjacent → tumor → other_disease → mixed → unknown. Agent-
  // emitted order is preserved within each disease_context bucket, so a
  // gene's own "important first" ordering still shows through.
  const expression = [...(bc.expression ?? [])].sort(
    (a, b) =>
      (DISEASE_CONTEXT_RANK[a.disease_context] ?? 99) -
      (DISEASE_CONTEXT_RANK[b.disease_context] ?? 99),
  );
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
          <ExpressionTable rows={expression} />
        )}
      </div>
    </SectionCard>
  );
}
