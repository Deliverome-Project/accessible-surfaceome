import { Shell } from "../components/Shell/Shell";
import { NumberedEyebrow } from "../components/NumberedEyebrow/NumberedEyebrow";
import { CatalogTable } from "../components/CatalogTable/CatalogTable";
import { loadCatalog } from "../lib/surfaceome";
import styles from "./page.module.css";

/**
 * Genome-wide index for `surfaceome.deliverome.org`. Reads the
 * pre-built catalog.json at build time (5k+ rows from the
 * candidate-universe TSV unioned with triage verdicts and the
 * deep-dive record set) and ships them straight into the client
 * table component for filter / sort.
 */
export default function HomePage() {
  const catalog = loadCatalog();

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.hero}>
          <NumberedEyebrow n={1}>Surfaceome</NumberedEyebrow>
          <h1 className={`h-display ${styles.heroH1}`}>
            A genome-wide table of <em>cell-surface candidates.</em>
          </h1>
          <p className={`lede ${styles.lede}`}>
            Every human protein with at least one surface signal across seven
            public databases, with the Haiku triage agent&apos;s verdict where it
            has run, and Sonnet deep-dive records where they exist. Open
            accession, evidence-cited, agent-readable.
          </p>
          <ul className={styles.stats} aria-label="Catalog stats">
            <li className={styles.stat}>
              <span className={styles.statN}>{catalog.n_rows.toLocaleString()}</span>
              <span className={`label-mono ${styles.statK}`}>candidates</span>
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
              <span className={styles.statN}>7</span>
              <span className={`label-mono ${styles.statK}`}>sources</span>
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
            S SURFY · C CSPA · H HPA · T DeepTMHMM · M COMPARTMENTS. Each cell is
            a single source&apos;s vote on whether the protein reaches the cell
            surface; the <code>Sources</code> column is the union count.
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
            <code>GET api.deliverome.org/surfaceome/v1/genes/&#123;SYMBOL&#125;</code>{" "}
            ships the same data as JSON.
          </p>
        </footer>
      </section>
    </Shell>
  );
}
