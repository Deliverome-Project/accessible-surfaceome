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
          <p className={styles.heroCtas}>
            <a
              className={styles.heroCta}
              href="https://github.com/Deliverome-Project/accessible-surfaceome"
              target="_blank"
              rel="noopener noreferrer"
            >
              <svg
                className={styles.heroCtaIcon}
                viewBox="0 0 16 16"
                width="16"
                height="16"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"
                />
              </svg>
              View source on GitHub
              <span aria-hidden="true">↗</span>
            </a>
            <a
              className={styles.heroCta}
              href="https://api.deliverome.org/surfaceome/v1/catalog"
              target="_blank"
              rel="noopener noreferrer"
            >
              <span className={`label-mono ${styles.heroCtaLabel}`}>API</span>
              <code>/v1/catalog</code>
              <span aria-hidden="true">↗</span>
            </a>
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
            live D1{" "}
            <code>
              {catalog.universe_version ?? "—"}
              {catalog.bench_version ? ` · ${catalog.bench_version}` : null}
            </code>
          </p>
        </footer>
      </section>
    </Shell>
  );
}
