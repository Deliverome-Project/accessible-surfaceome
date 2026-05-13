import { Shell } from "../../components/Shell/Shell";
import { BenchmarkTable } from "../../components/BenchmarkTable/BenchmarkTable";
import { listSurfaceomeGenes, loadBenchmarkMatrix } from "../../lib/surfaceome";
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
  title: "147-gene benchmark · Surfaceome",
  description:
    "Per-gene comparison of seven surface-membership databases against three LLM triage variants on the 147-gene triage benchmark.",
};

export default async function BenchmarkPage() {
  const matrix = await loadBenchmarkMatrix();
  const deepDiveGenes = new Set(listSurfaceomeGenes());

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <p className="h-data-eyebrow">
            Triage benchmark · v0.5
          </p>
          <h1 className={`h-data ${styles.title}`}>
            147 genes, seven databases, three models.
          </h1>
          <p className={styles.lede}>
            Each row is one of the 147 curated proteins in our triage
            benchmark, scored against ground truth, the union of seven
            public surface-membership databases, and headline-prompt
            verdicts from Opus 4.7, Sonnet 4.6, and Haiku 4.5. Click a
            row to compare the headline against three alternative
            prompt variants.
          </p>
        </header>

        <BenchmarkTable matrix={matrix} deepDiveGenes={deepDiveGenes} />

        <footer className={styles.footnotes}>
          <p>
            <span className="label-mono">DB columns ·</span> U UniProt · G GO ·
            S SURFY · C CSPA · H HPA · T DeepTMHMM · M COMPARTMENTS. Each
            cell is one source&apos;s vote on whether the protein reaches
            the plasma membrane. Filled dot = surface; empty ring = not
            on the surface in that source.
          </p>
          <p>
            <span className="label-mono">LLM columns ·</span> Headline
            verdict on the <code>{matrix.headline_variant}</code> prompt
            variant. Pills outlined in maroon disagree with truth
            (collapsing <em>yes</em> ≡ <em>contextual</em>, matching the
            D1 <code>correct</code> column). Click <em>+</em> to expand
            the row and compare against{" "}
            {matrix.alt_variants.map((v, i) => (
              <span key={v}>
                <code>{v}</code>
                {i < matrix.alt_variants.length - 1 ? ", " : ""}
              </span>
            ))}
            .
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
