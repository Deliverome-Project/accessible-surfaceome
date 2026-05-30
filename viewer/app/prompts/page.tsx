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
  /** Short description of where this prompt sits in the pipeline. */
  blurb?: string;
}

interface PromptGroup {
  id: string;
  label: string;
  description: string;
  prompts: PromptDef[];
}

/**
 * Canonical agent prompt paths grouped by pipeline phase. The viewer
 * reads each file with ``fs`` at build time so the on-page text is
 * always the file the agents actually run with.
 *
 * Coverage:
 *  - Surface triage — Haiku genome-wide first pass.
 *  - Deep dive Phase 1 — ``plan_trim_select`` literature agent
 *    (per-focus A1/A2 plan-trim-select, plus joint single-agent
 *    plan-trim-select).
 *  - Deep dive Phase 2 — 10 block builders that turn the A1/A2 ledger
 *    into the SurfaceomeRecord sub-blocks.
 *  - Deep dive Phase 3 — synthesizer that assembles the executive
 *    summary, filters, and confidence.
 */
const PROMPT_GROUPS: PromptGroup[] = [
  {
    id: "triage",
    label: "Surface accessibility triage",
    description:
      "Haiku first-pass over the protein-coding genome — produces the " +
      "yes / no / contextual triage verdict that gates which genes get a " +
      "full deep dive.",
    prompts: [
      {
        id: "triage-system",
        label: "Surface accessibility triage",
        rel: "src/accessible_surfaceome/agents/surface_triage/prompts/system.md",
      },
    ],
  },
  {
    id: "deep-dive-phase-1",
    label: "Deep dive · Phase 1 — plan_trim_select (literature agent)",
    description:
      "Three Sonnet / Haiku passes per agent focus: plan the searches, " +
      "trim each paper's candidate clips down to load-bearing ones, then " +
      "select the final EvidenceClaim ledger. The per-focus A1 + A2 " +
      "prompts split into a surface-evidence-methodology run and a " +
      "biology-context run; the joint plan-trim-select prompts run the " +
      "same loop on a unified ledger.",
    prompts: [
      {
        id: "pts-a1-plan",
        label: "A1 (surface evidence) — planner",
        rel: "src/accessible_surfaceome/agents/plan_trim_select/prompts/a1_plan_system.md",
        blurb:
          "Reads the gene context + Deterministic inputs block; emits a " +
          "SearchPlan biased toward methodology-dense query categories " +
          "(flow cytometry, surface biotinylation, mass-spec surfaceome, IHC).",
      },
      {
        id: "pts-a1-trim",
        label: "A1 — per-paper trim",
        rel: "src/accessible_surfaceome/agents/plan_trim_select/prompts/a1_trim_system.md",
        blurb:
          "One Haiku call per paper — keeps the clips that name a surface-" +
          "detection method, antibody, or non-permeabilized assay; drops " +
          "tissue/biology-only clips that the A2 trim handles.",
      },
      {
        id: "pts-a1-select",
        label: "A1 — final selector",
        rel: "src/accessible_surfaceome/agents/plan_trim_select/prompts/a1_select_system.md",
        blurb:
          "Sonnet picks the final A1 clip_ids → EvidenceClaim records with " +
          "verbatim quotes auto-filled from the trimmed pool. Can request " +
          "follow-up searches when the menu has obvious gaps.",
      },
      {
        id: "pts-a2-plan",
        label: "A2 (biological context) — planner",
        rel: "src/accessible_surfaceome/agents/plan_trim_select/prompts/a2_plan_system.md",
        blurb:
          "Mirrors A1 but biases toward tissue / cell-type / " +
          "subcellular-localization / accessibility-modulation queries — " +
          "HPA, Tabula Sapiens, mouse atlases when ortholog ECD identity " +
          "supports the cross-species transfer.",
      },
      {
        id: "pts-a2-trim",
        label: "A2 — per-paper trim",
        rel: "src/accessible_surfaceome/agents/plan_trim_select/prompts/a2_trim_system.md",
        blurb:
          "Keeps clips that name a tissue, cell type, cell state, " +
          "compartment, or stress / activation-induced surface change. " +
          "Drops methodology-only clips.",
      },
      {
        id: "pts-a2-select",
        label: "A2 — final selector",
        rel: "src/accessible_surfaceome/agents/plan_trim_select/prompts/a2_select_system.md",
        blurb:
          "Picks the final A2 clip_ids → EvidenceClaim records that feed " +
          "tissues, cell_types, cell_states, subcellular_localization, " +
          "anatomical_accessibility, and accessibility_modulation builders.",
      },
      {
        id: "pts-joint-plan",
        label: "Joint — planner",
        rel: "src/accessible_surfaceome/agents/plan_trim_select/prompts/plan_system.md",
        blurb:
          "Single-agent variant of the planner — emits one SearchPlan over " +
          "a unified ledger instead of splitting into A1 + A2 passes.",
      },
      {
        id: "pts-joint-trim",
        label: "Joint — per-paper trim",
        rel: "src/accessible_surfaceome/agents/plan_trim_select/prompts/trim_system.md",
      },
      {
        id: "pts-joint-select",
        label: "Joint — final selector",
        rel: "src/accessible_surfaceome/agents/plan_trim_select/prompts/select_system.md",
      },
    ],
  },
  {
    id: "deep-dive-phase-2",
    label: "Deep dive · Phase 2 — block builders (10 Sonnet calls in parallel)",
    description:
      "Each builder consumes a slice of the A1 or A2 EvidenceClaim ledger " +
      "and emits a structured sub-block of the SurfaceomeRecord. All 10 " +
      "run concurrently; their outputs assemble into surface_evidence + " +
      "biological_context.",
    prompts: [
      {
        id: "builder-methods",
        label: "A1 — methods builder",
        rel: "src/accessible_surfaceome/agents/surfaceome_v2/prompts/methods_builder_system.md",
        blurb:
          "EvidenceClaim ledger → list[MethodObservation]. Captures " +
          "antibody / assay / validation strategy / permeabilization status " +
          "for every surface-detection method the literature reports.",
      },
      {
        id: "builder-therapeutic-engagement",
        label: "A1 — therapeutic_engagement builder",
        rel: "src/accessible_surfaceome/agents/surfaceome_v2/prompts/therapeutic_engagement_builder_system.md",
        blurb:
          "Drugs, antibodies, CARs, ADCs, vaccines, PROTACs that imply " +
          "surface accessibility by way of binding.",
      },
      {
        id: "builder-contradictions",
        label: "A1 — contradictions builder",
        rel: "src/accessible_surfaceome/agents/surfaceome_v2/prompts/contradiction_builder_system.md",
        blurb:
          "Papers actively refuting surface localization (intracellular-only " +
          "claims, knockout-without-loss, no-staining controls).",
      },
      {
        id: "builder-evidence-grade",
        label: "A1 — evidence_grade builder",
        rel: "src/accessible_surfaceome/agents/surfaceome_v2/prompts/evidence_grade_builder_system.md",
        blurb:
          "Rolls up across methods + contradictions into the gene-level " +
          "evidence_grade enum (direct_multi_method / direct_single_method / " +
          "supportive_but_indirect / conflicting / weak).",
      },
      {
        id: "builder-tissues",
        label: "A2 — tissues builder",
        rel: "src/accessible_surfaceome/agents/surfaceome_v2/prompts/tissues_builder_system.md",
        blurb:
          "Per-tissue presence + reliability flags from HPA, GTEx, tissue " +
          "atlases, and disease-context tissue staining.",
      },
      {
        id: "builder-cell-types",
        label: "A2 — cell_types builder",
        rel: "src/accessible_surfaceome/agents/surfaceome_v2/prompts/cell_types_builder_system.md",
        blurb:
          "Per-cell-type expression — single-cell atlases, sorted " +
          "populations, immune subsets.",
      },
      {
        id: "builder-cell-states",
        label: "A2 — cell_states builder",
        rel: "src/accessible_surfaceome/agents/surfaceome_v2/prompts/cell_states_builder_system.md",
        blurb:
          "Cell-state modulation: activation, exhaustion, EMT, ER stress, " +
          "hypoxia, senescence, polarization, disease state.",
      },
      {
        id: "builder-subcellular-localization",
        label: "A2 — subcellular_localization builder",
        rel: "src/accessible_surfaceome/agents/surfaceome_v2/prompts/subcellular_localization_builder_system.md",
        blurb:
          "Primary compartment + dual_localization + membrane_subdomains " +
          "(apical / basolateral / lipid raft / tight junction / cilium).",
      },
      {
        id: "builder-anatomical-accessibility",
        label: "A2 — anatomical_accessibility builder",
        rel: "src/accessible_surfaceome/agents/surfaceome_v2/prompts/anatomical_accessibility_builder_system.md",
        blurb:
          "Vascular accessibility, blood-brain barrier, tissue-restricted " +
          "surface, mucosal exposure.",
      },
      {
        id: "builder-accessibility-modulation",
        label: "A2 — accessibility_modulation builder",
        rel: "src/accessible_surfaceome/agents/surfaceome_v2/prompts/accessibility_modulation_builder_system.md",
        blurb:
          "Stress-induced surface fraction, activation-induced upregulation, " +
          "post-translational gates (palmitoylation, ubiquitination), " +
          "recycling / endocytosis kinetics.",
      },
    ],
  },
  {
    id: "deep-dive-phase-3",
    label: "Deep dive · Phase 3 — synthesizer",
    description:
      "Reads the 10 builder outputs + the merged A1+A2 EvidenceClaim ledger " +
      "and emits the executive summary, LLM filters, accessibility risks, " +
      "and confidence with reasoning. The synthesizer doesn't fetch new " +
      "evidence — it only synthesizes from frozen Phase-2 blocks.",
    prompts: [
      {
        id: "synth-system",
        label: "Synthesizer",
        rel: "src/accessible_surfaceome/agents/surfaceome_synthesizer/prompts/system.md",
      },
    ],
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

interface LoadedGroup {
  id: string;
  label: string;
  description: string;
  prompts: LoadedPrompt[];
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

function loadGroup(group: PromptGroup): LoadedGroup {
  return {
    id: group.id,
    label: group.label,
    description: group.description,
    prompts: group.prompts
      .map(loadPrompt)
      .filter((p): p is LoadedPrompt => p != null),
  };
}

/** react-markdown component map — adds slug ids to headings so TOC anchors
 *  work. Each prompt block prefixes its own id namespace so anchors from
 *  multiple prompts on the same page don't collide. */
function makeMarkdownComponents(idPrefix: string) {
  return {
    h1: ({
      children,
      ...props
    }: { children?: React.ReactNode } & React.HTMLAttributes<HTMLHeadingElement>) => {
      const id = `${idPrefix}--${slugify(extractText(children))}`;
      return (
        <h1 id={id} className={styles.mdH1} {...props}>
          {children}
        </h1>
      );
    },
    h2: ({
      children,
      ...props
    }: { children?: React.ReactNode } & React.HTMLAttributes<HTMLHeadingElement>) => {
      const id = `${idPrefix}--${slugify(extractText(children))}`;
      return (
        <h2 id={id} className={styles.mdH2} {...props}>
          {children}
        </h2>
      );
    },
    h3: ({
      children,
      ...props
    }: { children?: React.ReactNode } & React.HTMLAttributes<HTMLHeadingElement>) => {
      const id = `${idPrefix}--${slugify(extractText(children))}`;
      return (
        <h3 id={id} className={styles.mdH3} {...props}>
          {children}
        </h3>
      );
    },
  };
}

function extractText(children: React.ReactNode): string {
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(extractText).join("");
  if (children && typeof children === "object" && "props" in children) {
    return extractText(
      (children as { props: { children?: React.ReactNode } }).props.children
    );
  }
  return "";
}

export default function PromptsPage() {
  const loaded = PROMPT_GROUPS.map(loadGroup).filter((g) => g.prompts.length > 0);
  const totalPrompts = loaded.reduce((n, g) => n + g.prompts.length, 0);
  const totalBytes = loaded.reduce(
    (n, g) => n + g.prompts.reduce((m, p) => m + p.size_bytes, 0),
    0
  );

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.hero}>
          <h1 className={`h-display ${styles.heroH1}`}>Agent prompts</h1>
          <p className={`lede ${styles.lede}`}>
            The exact Markdown system prompts the triage and deep-dive
            agents run with — read straight from the agent source tree at
            build time. No paraphrase, no edits.{" "}
            <strong>{totalPrompts} prompts</strong> totalling{" "}
            <strong>{(totalBytes / 1024).toFixed(1)} KB</strong> of
            instructions. If a prompt on this page changed, the next agent
            run picks it up after{" "}
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

        {/* Top-level index so a reader can jump straight to any prompt
            without scrolling through 20 cards. */}
        {loaded.length > 0 ? (
          <nav className={styles.pageIndex} aria-label="All prompts">
            <p className={styles.tocLabel}>All prompts</p>
            <ol className={styles.pageIndexList}>
              {loaded.map((g) => (
                <li key={g.id} className={styles.pageIndexGroup}>
                  <a href={`#group-${g.id}`} className={styles.pageIndexGroupLink}>
                    {g.label}
                  </a>
                  <ul className={styles.pageIndexPromptList}>
                    {g.prompts.map((p) => (
                      <li key={p.id}>
                        <a href={`#${p.id}`} className={styles.tocLink}>
                          {p.label}
                        </a>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          </nav>
        ) : null}

        {loaded.map((group) => (
          <div key={group.id} id={`group-${group.id}`}>
            <header className={styles.groupHeader}>
              <h2 className={`h-section ${styles.groupH2}`}>{group.label}</h2>
              <p className={styles.groupDescription}>{group.description}</p>
            </header>

            {group.prompts.map((p) => (
              <article key={p.id} id={p.id} className={styles.promptBlock}>
                <header className={styles.promptHeader}>
                  <h3 className={`${styles.promptH2}`}>{p.label}</h3>
                  {p.blurb ? (
                    <p className={styles.promptBlurb}>{p.blurb}</p>
                  ) : null}
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
                      components={makeMarkdownComponents(p.id)}
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
                            <a
                              href={`#${p.id}--${item.slug}`}
                              className={styles.tocLink}
                            >
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
          </div>
        ))}
      </section>
    </Shell>
  );
}
