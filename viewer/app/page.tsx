import { Shell } from "../components/Shell/Shell";
import { NumberedEyebrow } from "../components/NumberedEyebrow/NumberedEyebrow";
import { CatalogTable } from "../components/CatalogTable/CatalogTable";
import { loadCatalog } from "../lib/surfaceome";
import styles from "./page.module.css";

/**
 * Genome-wide index for `surfaceome.deliverome.org`. Pulls the
 * catalog from the public Worker's `/v1/catalog` endpoint at build
 * time (5k+ rows joining candidate_universe_public + triage_run_public
 * + surface_annotation in the `surfaceome_public` D1) and ships them
 * straight into the client table component for filter / sort. Falls
 * back to a committed snapshot when the API is unreachable.
 */
export default async function HomePage() {
  const catalog = await loadCatalog();

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.hero}>
          <NumberedEyebrow n={1}>Surfaceome</NumberedEyebrow>
          <h1 className={`h-display ${styles.heroH1}`}>
            A genome-wide table of <em>cell-surface candidates.</em>
          </h1>
          <p className={`lede ${styles.lede}`}>
            Every protein-coding human gene, scored against five public
            surface-membership databases, with the Haiku triage agent&apos;s
            verdict where it has run and Sonnet deep-dive records where they
            exist. Open accession, evidence-cited, agent-readable.
          </p>
          <ul className={styles.stats} aria-label="Catalog stats">
            <li className={styles.stat}>
              <span className={styles.statN}>{catalog.n_rows.toLocaleString()}</span>
              <span className={`label-mono ${styles.statK}`}>genes</span>
            </li>
            <li className={styles.stat}>
              <span className={styles.statN}>{catalog.n_with_triage.toLocaleString()}</span>
              <span className={`label-mono ${styles.statK}`}>triaged</span>
            </li>
            <li className={styles.stat}>
              <span className={styles.statN}>
                {catalog.n_with_deep_dive.toLocaleString()}
              </span>
              <span className={`label-mono ${styles.statK}`}>deep-dive</span>
            </li>
            <li className={styles.stat}>
              <span className={styles.statN}>5</span>
              <span className={`label-mono ${styles.statK}`}>DB sources</span>
            </li>
          </ul>
        </header>

        <CatalogTable
          rows={catalog.rows}
          generated_at={catalog.generated_at}
          n_rows={catalog.n_rows}
          n_with_triage={catalog.n_with_triage}
          n_with_deep_dive={catalog.n_with_deep_dive}
        />

        <footer className={styles.footnotes}>
          <p>
            <span className="label-mono">DB columns ·</span> U UniProt · G GO ·
            S SURFY · C CSPA · H HPA. Each cell is one source&apos;s vote on
            whether the protein reaches the cell surface; the{" "}
            <code>Sources</code> column is the count of those five (the M1
            universe gate). DeepTMHMM + COMPARTMENTS are tracked upstream as
            auxiliary signals but don&apos;t appear here.
          </p>
          <p>
            <span className="label-mono">Triage ·</span> Haiku-only first pass.
            Verdicts read as <em>yes</em> (constitutively on the surface),{" "}
            <em>contextual</em> (conditional or rare surface), <em>no</em>{" "}
            (no plasma-membrane presence). Sonnet deep-dive records linked from
            the <em>view →</em> column override the triage call when present.
          </p>
          <p>
            <span className="label-mono">API ·</span>{" "}
            <code>GET api.deliverome.org/surfaceome/v1/catalog</code> ships the
            same table as JSON;{" "}
            <code>/v1/genes/&#123;SYMBOL&#125;</code> ships a single
            deep-dive record.
          </p>
          <p className={styles.sourceLine}>
            <span className="label-mono">Source ·</span>{" "}
            {catalog.source === "api" ? (
              <>
                live D1{" "}
                <code>
                  {catalog.universe_version ?? "—"}
                  {catalog.bench_version ? ` · ${catalog.bench_version}` : null}
                </code>
              </>
            ) : (
              <>
                committed snapshot (Worker unreachable —{" "}
                <code>SURFACEOME_API_BASE</code> falls back to local{" "}
                <code>public/data/catalog.json</code>)
              </>
            )}
          </p>
        </footer>
      </section>
    </Shell>
  );
}
