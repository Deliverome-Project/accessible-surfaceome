import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import {
  classifyExpressionSource,
  expressionSourceRank,
  type ExpressionSource,
} from "../../../lib/expression";
import { FeatureRationales } from "../FeatureChips/FeatureChips";
import { InfoTip } from "../../InfoTip/InfoTip";
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
  // Source-classify + drop RNA-only rows. Each remaining row gets a
  // ``source`` field driving the new Source column. The
  // ``expression_builder`` prompt already prescribes excluding
  // RNA-only sources upstream, but the model doesn't always enforce
  // it — render-time filter closes the gap until the prompt-level
  // enforcement lands.
  const evidenceById = new Map((rec.evidence ?? []).map((e) => [e.evidence_id, e]));
  const classified: (typeof expression[number] & { source: ExpressionSource })[] = [];
  let rnaOnlyDropped = 0;
  for (const row of expression) {
    const source = classifyExpressionSource(row, evidenceById);
    if (source === null) {
      rnaOnlyDropped += 1;
      continue;
    }
    classified.push({ ...row, source });
  }
  // Default row order: enrich for surface evidence. Primary sort is
  // source DESC (surface > bulk > other) so the direct-surface rows
  // lead; within each bucket the original disease-context order is
  // preserved (normal → tumor_adjacent → tumor → …) so the
  // toxicity-baseline reading stays intact. ``Array.prototype.sort``
  // is stable so the secondary disease-context tiebreaker comes from
  // the pre-sort above.
  classified.sort(
    (a, b) => expressionSourceRank(b.source) - expressionSourceRank(a.source),
  );
  // Per-source headcount for the subhead rollup, so a reader sees at
  // a glance how much of each evidence bucket backs the gene.
  const surfaceCount = classified.filter((r) => r.source === "surface").length;
  const bulkCount = classified.filter((r) => r.source === "bulk").length;
  const otherCount = classified.filter((r) => r.source === "other").length;
  return (
    <SectionCard
      n={n}
      eyebrow="Expression"
      title="Expression level & tissue distribution"
      meta="Baseline level · breadth · overexpression precedent · by tissue of origin; disease context + level + evidence sit on each cell of origin"
    >
      <FeatureRationales category="expression" rec={rec} />

      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>
          Expression × cell type × disease context
          {classified.length > 0 ? (
            <span className={styles.sourceRollup}>
              {surfaceCount} surface · {bulkCount} bulk · {otherCount} other
            </span>
          ) : null}
          <InfoTip wide label="About the expression rows">
            Evidence-based literature statements the deep-dive agent
            extracted from primary papers — <strong>not</strong> an
            exhaustive expression atlas. Coverage is bounded by the
            papers in the retrieved corpus; absence of a tissue here
            means &quot;no statement was extracted,&quot; not
            &quot;not expressed.&quot; For atlas-grade tissue
            coverage, cross-reference Human Protein Atlas / GTEx.
            <br />
            <br />
            <strong>Source column.</strong> Each row is bucketed by
            its strongest cited evidence_type:
            <ul style={{ margin: "0.4rem 0 0", paddingLeft: "1.1rem" }}>
              <li>
                <em>surface</em> — at least one direct surface assay
                (flow cytometry / surface biotinylation /
                surface mass-spec).
              </li>
              <li>
                <em>bulk</em> — protein-level methods that don&apos;t
                distinguish surface from intracellular pool (IHC / IF
                / Western blot).
              </li>
              <li>
                <em>other</em> — review assertions, functional
                assays, database annotations, etc.
              </li>
            </ul>
            <strong>RNA-only rows are dropped</strong> (RNA-seq /
            scRNA / RT-qPCR / in-situ hybridization / Northern /
            microarray). RNA doesn&apos;t demonstrate the protein is
            made, let alone surface-accessible.
          </InfoTip>
        </p>
        {classified.length === 0 ? (
          <p className={styles.empty}>
            {expression.length === 0
              ? "No expression rows recorded."
              : `No protein-level expression rows (all ${expression.length} cited rows were RNA-only).`}
          </p>
        ) : (
          <ExpressionTable rows={classified} />
        )}
        {rnaOnlyDropped > 0 && classified.length > 0 ? (
          <p className={styles.empty} style={{ marginTop: "0.5rem" }}>
            {rnaOnlyDropped} RNA-only row{rnaOnlyDropped === 1 ? "" : "s"}{" "}
            hidden — see the <em>About the expression rows</em> tip for
            why.
          </p>
        ) : null}
      </div>
    </SectionCard>
  );
}
