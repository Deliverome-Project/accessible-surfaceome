import catalog from "../../lib/search-catalog.json";
import styles from "./SearchCatalog.module.css";

/**
 * SearchCatalog — documents the searches the two plan_trim_select agents
 * run per gene, shown under the "Deep dive · Phase 1" group header on
 * /prompts so a reader can interpret what an agent's prompt works from.
 *
 * The deep dive runs the planner twice with different prompts:
 *   • A1 (surface evidence) — mandates the five method-centric assay
 *     categories: HOW the surface call was made.
 *   • A2 (biological context) — mandates a different floor (IHC flagship,
 *     IF/flow/mass-spec for localization, a normal-tissue tox panel, a
 *     subcellular-localization sweep): WHERE / WHEN it reaches the surface.
 * Both also run the shared literature baselines; both may add planner fill.
 *
 * The data is generated from real code + the two planner prompts by
 * `scripts/build_search_catalog.py` (→ `viewer/lib/search-catalog.json`),
 * so this can't drift from what the agents are actually told to run.
 */

interface CategoryDef {
  id: string;
  label: string;
  finds: string;
  query_preview: string;
}
interface Baseline {
  id: string;
  label: string;
  finds: string;
}
interface TopicPanel {
  label: string;
  finds: string;
}
interface AgentPlan {
  id: string;
  label: string;
  tagline: string;
  always_category_ids: string[];
  skip_category_ids: string[];
  conditional_note: string;
  always_topic: TopicPanel[];
}

const categories = catalog.categories as Record<string, CategoryDef>;
const baselines = catalog.shared_baselines as Baseline[];
const agents = catalog.agents as AgentPlan[];
const planned = catalog.planned_fill as Baseline[];

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

function AgentColumn({ plan }: { plan: AgentPlan }) {
  const skipped = plan.skip_category_ids
    .map((id) => categories[id]?.label)
    .filter(Boolean);
  return (
    <section className={styles.agent}>
      <header className={styles.agentHead}>
        <h4 className={styles.agentTitle}>{plan.label}</h4>
        <p className={styles.agentTagline}>{plan.tagline}</p>
      </header>

      <p className={styles.subhead}>Always-run assays</p>
      <ul className={styles.list}>
        {plan.always_category_ids.map((id) => {
          const c = categories[id];
          return c ? (
            <Row
              key={id}
              label={c.label}
              finds={c.finds}
              query={c.query_preview}
            />
          ) : null;
        })}
      </ul>

      <p className={styles.subhead}>Always-run topic searches</p>
      <ul className={styles.list}>
        {plan.always_topic.map((t) => (
          <Row key={t.label} label={t.label} finds={t.finds} />
        ))}
      </ul>

      <p className={styles.note}>
        {plan.conditional_note}
        {skipped.length ? (
          <>
            {" "}
            <strong>Skips</strong> {skipped.join(" + ")} — that&rsquo;s the
            other pass&rsquo;s job.
          </>
        ) : null}
      </p>
    </section>
  );
}

export function SearchCatalog() {
  const nAlways =
    baselines.length +
    agents.reduce(
      (n, a) => n + a.always_category_ids.length + a.always_topic.length,
      0,
    );
  return (
    <details className={styles.wrap}>
      <summary className={styles.summary}>
        <span className={styles.summaryTitle}>Searches the agents run</span>
        <span className={styles.summaryHint}>
          two passes · {nAlways} always-run searches · {planned.length}{" "}
          planner-chosen — click to expand
        </span>
      </summary>
      <div className={styles.body}>
        <p className={styles.lede}>
          Phase 1 runs the planner <strong>twice</strong> over every gene —
          once as <strong>A1 (surface evidence)</strong>, once as{" "}
          <strong>A2 (biological context)</strong>. Each prompt mandates its
          own floor of searches that always run, regardless of what the
          planner adds. Both passes share the literature baselines below and
          may emit extra planner-chosen queries.
        </p>

        <section className={styles.group}>
          <h4 className={styles.groupTitle}>
            Shared literature baselines — both passes, every gene
          </h4>
          <ul className={styles.list}>
            {baselines.map((b) => (
              <Row key={b.id} label={b.label} finds={b.finds} />
            ))}
          </ul>
        </section>

        <div className={styles.agents}>
          {agents.map((a) => (
            <AgentColumn key={a.id} plan={a} />
          ))}
        </div>

        <section className={styles.group}>
          <h4 className={styles.groupTitle}>
            Planner-chosen fill — added when the gene warrants it
          </h4>
          <p className={styles.groupSub}>
            Not guaranteed per gene — these are the genuinely
            non-deterministic searches the planner composes on top of each
            pass&rsquo;s mandated floor.
          </p>
          <ul className={styles.list}>
            {planned.map((m) => (
              <Row key={m.id} label={m.label} finds={m.finds} />
            ))}
          </ul>
        </section>
      </div>
    </details>
  );
}
