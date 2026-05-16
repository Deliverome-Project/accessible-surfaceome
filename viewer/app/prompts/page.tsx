import path from "node:path";
import { readFileSync, statSync } from "node:fs";
import type { Metadata } from "next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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

interface TocItem {
  level: number;
  text: string;
  slug: string;
}

interface LoadedPrompt extends PromptDef {
  body: string;
  size_bytes: number;
  source_path: string;
  toc: TocItem[];
}

/** GitHub-ish slugger: lowercased, non-alphanumerics → `-`, collapsed runs. */
function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function extractToc(body: string): TocItem[] {
  // Match `#` … `######` headings, but skip lines inside fenced code blocks.
  const lines = body.split("\n");
  const out: TocItem[] = [];
  let inCodeBlock = false;
  const seenSlugs = new Map<string, number>();
  for (const line of lines) {
    if (line.startsWith("```")) {
      inCodeBlock = !inCodeBlock;
      continue;
    }
    if (inCodeBlock) continue;
    const m = /^(#{1,6})\s+(.+?)\s*$/.exec(line);
    if (!m) continue;
    const level = m[1].length;
    // Only TOC level 1-3 — anything deeper is detail noise.
    if (level > 3) continue;
    const text = m[2].replace(/`/g, "");
    const base = slugify(text);
    const count = (seenSlugs.get(base) || 0) + 1;
    seenSlugs.set(base, count);
    const slug = count === 1 ? base : `${base}-${count - 1}`;
    out.push({ level, text, slug });
  }
  return out;
}

function loadPrompt(def: PromptDef): LoadedPrompt | null {
  const abs = path.join(process.cwd(), "..", def.rel);
  try {
    const body = readFileSync(abs, "utf-8");
    const stat = statSync(abs);
    return {
      ...def,
      body,
      size_bytes: stat.size,
      source_path: def.rel,
      toc: extractToc(body),
    };
  } catch {
    return null;
  }
}

/** react-markdown component map — adds slug ids to headings so TOC anchors work. */
const markdownComponents = {
  h1: ({ children, ...props }: { children?: React.ReactNode } & React.HTMLAttributes<HTMLHeadingElement>) => {
    const id = slugify(extractText(children));
    return <h1 id={id} className={styles.mdH1} {...props}>{children}</h1>;
  },
  h2: ({ children, ...props }: { children?: React.ReactNode } & React.HTMLAttributes<HTMLHeadingElement>) => {
    const id = slugify(extractText(children));
    return <h2 id={id} className={styles.mdH2} {...props}>{children}</h2>;
  },
  h3: ({ children, ...props }: { children?: React.ReactNode } & React.HTMLAttributes<HTMLHeadingElement>) => {
    const id = slugify(extractText(children));
    return <h3 id={id} className={styles.mdH3} {...props}>{children}</h3>;
  },
};

function extractText(children: React.ReactNode): string {
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(extractText).join("");
  if (children && typeof children === "object" && "props" in children) {
    return extractText((children as { props: { children?: React.ReactNode } }).props.children);
  }
  return "";
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
            build time. No paraphrase, no edits. If a prompt on this page
            changed, the next agent run picks it up after{" "}
            <code className={styles.inlineCode}>
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
                <code className={styles.inlineCode}>{p.source_path}</code>
                <span className={styles.metaSep}> · </span>
                {p.size_bytes.toLocaleString()} bytes
                <span className={styles.metaSep}> · </span>
                {p.body.split("\n").length.toLocaleString()} lines
              </p>
            </header>

            <div className={styles.promptLayout}>
              <div className={styles.promptBody}>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents}
                >
                  {p.body}
                </ReactMarkdown>
              </div>

              {p.toc.length > 1 ? (
                <aside className={styles.toc} aria-label="Table of contents">
                  <p className={styles.tocLabel}>On this page</p>
                  <ol className={styles.tocList}>
                    {p.toc.map((item) => (
                      <li
                        key={item.slug}
                        className={styles.tocItem}
                        data-level={item.level}
                      >
                        <a href={`#${item.slug}`} className={styles.tocLink}>
                          {item.text}
                        </a>
                      </li>
                    ))}
                  </ol>
                </aside>
              ) : null}
            </div>
          </article>
        ))}
      </section>
    </Shell>
  );
}
