import catalog from "../../lib/search-catalog.json";
import styles from "./SearchCatalog.module.css";

/**
 * SearchCatalog — documents the searches the plan_trim_select agents run
 * per gene, shown under the "Deep dive · Phase 1" group header on /prompts.
 *
 * Two kinds, both surfaced here so a reader can interpret what an agent's
 * prompt is working from:
 *   • DETERMINISTIC sweeps — fixed queries that run for EVERY gene
 *     regardless of what the LLM plans: the NCBI baselines + one query per
 *     assay category.
 *   • LLM-PLANNED — topic queries the planner composes.
 *
 * The data is generated from the actual tool code by
 * `scripts/build_search_catalog.py` (→ `viewer/lib/search-catalog.json`),
 * so this documentation can't drift from what the agents really run.
 */

interface CategoryEntry {
  id: string;
  label: string;
  finds: string;
  deterministic: boolean;
  query_preview: string;
}
interface ModeEntry {
  id: string;
  label: string;
  finds: string;
  deterministic: boolean;
}

const categories = catalog.evidence_retrieval_categories as CategoryEntry[];
const modes = catalog.literature_modes as ModeEntry[];
const detModes = modes.filter((m) => m.deterministic);
const plannedModes = modes.filter((m) => !m.deterministic);

function Row({
  label,
  finds,
  query,
}: {
  label: string;
  finds: string;
  query?: string;
}) {
  return (
    <li className={styles.row}>
      <span className={styles.rowLabel}>{label}</span>
      <span className={styles.rowFinds}>{finds}</span>
      {query ? <code className={styles.rowQuery}>{query}</code> : null}
    </li>
  );
}

export function SearchCatalog() {
  return (
    <details className={styles.wrap}>
      <summary className={styles.summary}>
        <span className={styles.summaryTitle}>
          Searches the agents run
        </span>
        <span className={styles.summaryHint}>
          {categories.length + detModes.length} deterministic ·{" "}
          {plannedModes.length} LLM-planned — click to expand
        </span>
      </summary>
      <div className={styles.body}>
        <p className={styles.lede}>
          Each plan-trim-select agent (A1 surface-evidence, A2
          biology-context) runs a fixed set of <strong>deterministic
          sweeps</strong> for every gene — these always execute, regardless
          of what the prompt below plans — plus the{" "}
          <strong>LLM-planned</strong> topic queries the prompt composes.
          This is the search surface the prompts operate over.
        </p>

        <section className={styles.group}>
          <h4 className={styles.groupTitle}>
            Deterministic sweeps — run for every gene
          </h4>
          <p className={styles.groupSub}>
            NCBI literature baselines, then one query per assay category
            (the <code>evidence_retrieval</code> tool).
          </p>
          <ul className={styles.list}>
            {detModes.map((m) => (
              <Row key={m.id} label={m.label} finds={m.finds} />
            ))}
            {categories.map((c) => (
              <Row
                key={c.id}
                label={c.label}
                finds={c.finds}
                query={c.query_preview}
              />
            ))}
          </ul>
        </section>

        <section className={styles.group}>
          <h4 className={styles.groupTitle}>LLM-planned searches</h4>
          <p className={styles.groupSub}>
            Topic queries the planner chooses based on the gene context.
          </p>
          <ul className={styles.list}>
            {plannedModes.map((m) => (
              <Row key={m.id} label={m.label} finds={m.finds} />
            ))}
          </ul>
        </section>
      </div>
    </details>
  );
}
