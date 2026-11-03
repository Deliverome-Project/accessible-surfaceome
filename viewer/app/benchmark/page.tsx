import { Shell } from "../../components/Shell/Shell";
import { BenchmarkTable } from "../../components/BenchmarkTable/BenchmarkTable";
import {
  listSurfaceomeGenes,
  loadBenchmarkMatrix,
  loadGeneName,
} from "../../lib/surfaceome";
import styles from "./page.module.css";

/**
 * 147-gene triage benchmark page. Joins three D1 tables server-side
 * (benchmark_version + candidate_universe_public + triage_run_public)
 * via the public Worker's /v1/benchmark/matrix endpoint, then renders
 * one row per gene: ground-truth verdict, per-DB calls across the five
 * gating sources, and one headline LLM verdict per Claude model (the
 * model columns are data-driven from the payload's `models` list).
 *
 * Typography intentionally steps down from the rest of the viewer
 * (.h-data / .h-data-eyebrow) so the table dominates the page.
 */
export const metadata = {
  title: "SurfaceBench · 147-gene triage benchmark",
  description:
    "SurfaceBench — per-gene comparison of five surface-membership databases against eight Claude models and five triage prompt variants on a 147-gene benchmark.",
};

export default async function BenchmarkPage() {
  const matrix = await loadBenchmarkMatrix();
  const deepDiveGenes = new Set(await listSurfaceomeGenes());
  // Build a symbol → full-name map for the benchmark genes so each
  // row can show "ERBB2 / Erb-b2 receptor tyrosine kinase 2" without
  // shipping the entire HGNC lookup to the client. `loadGeneName` is
  // memoized so all 147 calls share one TSV parse.
  const geneNames: Record<string, string> = {};
  const geneSynonyms: Record<string, string[]> = {};
  for (const row of matrix.rows) {
    const entry = loadGeneName(row.gene_symbol);
    if (entry?.name) geneNames[row.gene_symbol] = entry.name;
    if (entry?.synonyms?.length) geneSynonyms[row.gene_symbol] = entry.synonyms;
  }

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>
            147 genes, five databases, eight models.
          </h1>
          <p className={styles.lede}>
            <strong>SurfaceBench</strong> is a 147-protein benchmark
            assembled from cases where the five public surface-membership
            databases disagree on surface status. Each protein was
            manually reviewed and classified as surface, contextually
            surface, or non-surface. Sonnet 4.6 and Opus 4.8 — with no
            external tools, working from training-time knowledge plus
            a short NCBI context block — outperform every gold-standard
            database on this set. Sonnet 4.6 on that NCBI prompt is the
            production triage configuration (marked ★ in the table). The
            table below shows every model × prompt-variant call so you can
            audit the reasoning per gene.
          </p>
        </header>

        <BenchmarkTable
          matrix={matrix}
          deepDiveGenes={deepDiveGenes}
          geneNames={geneNames}
          geneSynonyms={geneSynonyms}
        />

        <footer className={styles.footnotes}>
          <p>
            <span className="label-mono">Reason ·</span> the curator&apos;s
            single ground-truth reason behind each verdict, drawn from the
            same closed <code>TriageReason</code> vocabulary the triage
            agent must pick from — so each model&apos;s reason is directly
            comparable to the truth reason. Hover a truncated label for the
            full text.
          </p>
          <p>
            <span className="label-mono">DB columns ·</span> UniProt · GO ·
            SURFY · CSPA · HPA — the five gating databases that
            drive candidate-universe membership (same set the homepage catalog
            shows). Each cell is one source&apos;s vote on whether the
            protein reaches the plasma membrane: filled dot = surface,
            empty ring = not on the surface in that source.
          </p>
          <p>
            <span className="label-mono">LLM columns ·</span> One
            compact cell per model on the headline{" "}
            <code>{matrix.headline_variant.toUpperCase()}</code> prompt variant,
            ordered Haiku 4.5 · Haiku 5.5 · Sonnet 4.6 · Sonnet 5 · Sonnet
            5.5 · Opus 4.8 · Opus 5 · Opus 5.5. Every model ran each prompt
            three times, and each cell shows the majority verdict across
            those replicates (refused replicates excluded) — the per-cell
            numbers the paper reports. Each is a verdict pill colored
            by call (<em>ctx</em> = contextual); pills outlined in maroon
            disagree with truth (collapsing <em>yes</em> ≡{" "}
            <em>contextual</em> when scoring correctness). The tinted
            Sonnet 4.6 ★ column is the production configuration. Hover for
            the full (model → verdict + reason) tooltip; click a pill to
            read the agent&apos;s reasoning.
          </p>
          <p>
            <span className="label-mono">Prompt variants ·</span> Click a
            gene to expand the full model × variant grid. Not every model ran
            every variant: Haiku 4.5 and Sonnet 4.6 ran all four of{" "}
            <em>no context</em>, <em>NCBI</em>, <em>NCBI + web search</em>{" "}
            and <em>NCBI + PubMed</em>; Opus 4.8, Haiku 5.5 and Sonnet 5.5 ran{" "}
            <em>no context</em> and <em>NCBI</em>; Sonnet 5 and Opus 5 ran{" "}
            <em>NCBI</em> only; and Opus 5.5 ran <em>NCBI</em> plus{" "}
            <em>NCBI · low effort</em> — the same prompt at low reasoning
            effort. Cells with no run on file show a dash.
          </p>
          <p>
            <span className="label-mono">Refused ·</span> A small number
            of calls were declined by the model&apos;s safety classifier and
            returned no verdict. A refused replicate is left out of its
            cell&apos;s majority; a cell whose replicates all refused shows as{" "}
            <em>refused</em> (<em>ref</em>{" "}
            in the headline columns, with a dashed outline) — distinct from a
            dash (no run on file) and from <em>errored</em> (a run that
            returned no valid verdict) — and are not counted as agreeing or
            disagreeing with truth.
          </p>
        </footer>
      </section>
    </Shell>
  );
}
