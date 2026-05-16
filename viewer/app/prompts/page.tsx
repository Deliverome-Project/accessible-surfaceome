import path from "node:path";
import { readFileSync, statSync } from "node:fs";
import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Agent prompts — Surfaceome",
  description:
    "The exact system prompts the Haiku triage and Sonnet deep-dive agents " +
    "run with — read straight from the agent source tree at build time.",
};

interface PromptDef {
  id: string;
  label: string;
  /** Path relative to the repo root (one level above ``viewer/``). */
  rel: string;
}

/**
 * Canonical agent prompt paths. The viewer reads them with ``fs`` at
 * build time so the on-page text is always the file the agents
 * actually run with. Starting with just ``triage``; the deep-dive
 * (`surface_annotator/prompts/system.md`) will be added once it
 * stabilizes under the v0.5.0 schema.
 */
const PROMPTS: PromptDef[] = [
  {
    id: "triage",
    label: "Surface accessibility triage",
    rel: "src/accessible_surfaceome/agents/surface_triage/prompts/system.md",
  },
];

interface LoadedPrompt extends PromptDef {
  body: string;
  size_bytes: number;
  source_path: string;
}

function loadPrompt(def: PromptDef): LoadedPrompt | null {
  // ``viewer/`` is one level below the repo root.
  const abs = path.join(process.cwd(), "..", def.rel);
  try {
    const body = readFileSync(abs, "utf-8");
    const stat = statSync(abs);
    return { ...def, body, size_bytes: stat.size, source_path: def.rel };
  } catch {
    return null;
  }
}

export default function PromptsPage() {
  const loaded = PROMPTS.map(loadPrompt).filter((p): p is LoadedPrompt => p != null);

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.hero}>
          <h1 className={`h-display ${styles.heroH1}`}>Agent prompts</h1>
          <p className={`lede ${styles.lede}`}>
            The exact Markdown system prompts the triage and deep-dive
            agents run with — read straight from the agent source tree at
            build time. No paraphrase, no edits. If the prompt on this
            page changed, the next agent run picks it up after{" "}
            <code className={styles.code}>
              uv run accessible-surfaceome agents sync
            </code>
            .
          </p>
        </header>

        {loaded.length === 0 ? (
          <p className={styles.empty}>
            Could not load any prompt files from the repo. Check that the
            viewer is being built from inside <code>viewer/</code> and that
            the agent prompt paths exist.
          </p>
        ) : null}

        {loaded.map((p) => (
          <article key={p.id} id={p.id} className={styles.promptBlock}>
            <header className={styles.promptHeader}>
              <h2 className={`h-section ${styles.promptH2}`}>{p.label}</h2>
              <p className={styles.promptMeta}>
                <code className={styles.code}>{p.source_path}</code>
                <span className={styles.metaSep}> · </span>
                {p.size_bytes.toLocaleString()} bytes
              </p>
            </header>
            <pre className={styles.promptBody}>{p.body}</pre>
          </article>
        ))}
      </section>
    </Shell>
  );
}
