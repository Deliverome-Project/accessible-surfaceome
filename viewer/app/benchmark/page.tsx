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
 * one row per gene: ground-truth verdict, per-DB calls across seven
 * sources, and headline LLM verdicts for opus / sonnet / haiku.
 *
 * Typography intentionally steps down from the rest of the viewer
 * (.h-data / .h-data-eyebrow) so the table dominates the page.
 */
export const metadata = {
  title: "SurfaceBench · 147-gene triage benchmark",
  description:
    "SurfaceBench — per-gene comparison of five surface-membership databases against three LLM triage variants on a 147-gene benchmark.",
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
            147 genes, five databases, three models.
          </h1>
          <p className={styles.lede}>
            <strong>SurfaceBench</strong> is a 147-protein benchmark
            assembled from cases where the five public surface-membership
            databases disagree on surface status. Each protein was
            manually reviewed and classified as surface, contextually
            surface, or non-surface. Sonnet 4.6 and Opus 4.8 — with no
            external tools, working from training-time knowledge plus
            a short NCBI context block — outperform every gold-standard
            database on this set. The table below shows every model ×
            prompt-variant call so you can audit the reasoning per gene.
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
            drive M1 universe membership (same set the homepage catalog
            shows). Each cell is one source&apos;s vote on whether the
            protein reaches the plasma membrane: filled dot = surface,
            empty ring = not on the surface in that source.
          </p>
          <p>
            <span className="label-mono">LLM columns ·</span> Three
            cells per row — one per model on the headline{" "}
            <code>{matrix.headline_variant.toUpperCase()}</code> prompt variant
            (Haiku / Sonnet / Opus). Each is a verdict pill coloured
            by call; pills outlined in maroon disagree with truth
            (collapsing <em>yes</em> ≡ <em>contextual</em> when scoring
            correctness). Hover for the full
            (model → verdict + reason) tooltip. Click <em>+</em> on
            the row to expand the full <strong>3 model × 4 variant</strong>{" "}
            grid (Opus has runs on 2 of 4 variants only); each cell in
            that grid carries its own <em>+</em> to reveal the
            agent&apos;s free-text reasoning for that specific call.
          </p>
        </footer>
      </section>
    </Shell>
  );
}
