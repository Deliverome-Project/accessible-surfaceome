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
    "SurfaceBench — per-gene comparison of seven surface-membership databases against three LLM triage variants on a 147-gene benchmark.",
};

export default async function BenchmarkPage() {
  const matrix = await loadBenchmarkMatrix();
  const deepDiveGenes = new Set(listSurfaceomeGenes());
  // Build a symbol → full-name map for the benchmark genes so each
  // row can show "ERBB2 / Erb-b2 receptor tyrosine kinase 2" without
  // shipping the entire HGNC lookup to the client. `loadGeneName` is
  // memoized so all 147 calls share one TSV parse.
  const geneNames: Record<string, string> = {};
  for (const row of matrix.rows) {
    const entry = loadGeneName(row.gene_symbol);
    if (entry?.name) geneNames[row.gene_symbol] = entry.name;
  }

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <p className="h-data-eyebrow">
            SurfaceBench · v0.5
          </p>
          <h1 className={`h-data ${styles.title}`}>
            147 genes, seven databases, three models.
          </h1>
          <p className={styles.lede}>
            <strong>SurfaceBench</strong> is the 147-gene triage
            benchmark behind this project. Each row is one curated
            protein, scored against ground truth, the union of seven
            public surface-membership databases, and headline-prompt
            verdicts from Opus 4.7, Sonnet 4.6, and Haiku 4.5. Click a
            row to compare the headline against three alternative
            prompt variants.
          </p>
        </header>

        <BenchmarkTable
          matrix={matrix}
          deepDiveGenes={deepDiveGenes}
          geneNames={geneNames}
        />

        <footer className={styles.footnotes}>
          <p>
            <span className="label-mono">DB columns ·</span> U UniProt · G GO ·
            S SURFY · C CSPA · H HPA · T DeepTMHMM · M COMPARTMENTS. Each
            cell is one source&apos;s vote on whether the protein reaches
            the plasma membrane. Filled dot = surface; empty ring = not
            on the surface in that source.
          </p>
          <p>
            <span className="label-mono">LLM columns ·</span> Twelve
            cells per row — one per (model × prompt variant). Each cell
            is a single-letter glyph (<code>Y</code> / <code>N</code> /{" "}
            <code>C</code>) coloured by verdict; cells outlined in
            maroon disagree with truth (collapsing <em>yes</em> ≡{" "}
            <em>contextual</em>, matching the D1 <code>correct</code>{" "}
            column). The headline variant (<code>{matrix.headline_variant}</code>)
            gets a small accent underline on its column header. Hover
            any cell for the full (model · variant → verdict + reason)
            tooltip; click <em>+</em> on the row to reveal each call&apos;s
            free-text reasoning.
          </p>
          <p>
            <span className="label-mono">API ·</span>{" "}
            <code>
              GET api.deliverome.org/surfaceome/v1/benchmark/matrix
            </code>{" "}
            ships the same table as JSON.
          </p>
          <p className={styles.sourceLine}>
            <span className="label-mono">Source ·</span> live D1{" "}
            <code>
              {matrix.universe_version ?? "—"}
              {matrix.bench_version
                ? ` · ${matrix.bench_version.slice(0, 12)}`
                : null}
            </code>
          </p>
        </footer>
      </section>
    </Shell>
  );
}
