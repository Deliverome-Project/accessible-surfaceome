import { Shell } from "../components/Shell/Shell";
import { CatalogTable } from "../components/CatalogTable/CatalogTable";
import { PaperCite } from "../components/PaperCite/PaperCite";
import { loadCatalog, withDeepDiveFilters } from "../lib/surfaceome";
import styles from "./page.module.css";

/**
 * Hero links to the preprint, its code and its data. The HTML copy on
 * the Deliverome site is the primary call to action; the PDF sits
 * beside it, bioRxiv is the version of record. Data is the Zenodo
 * concept DOI (all releases); /reproducibility lists the per-version
 * handles.
 */
const PAPER_HTML_URL = "https://deliverome.org/paper/accessible-surfaceome/";

const PAPER_LINKS: { label: string; ariaLabel: string; href: string }[] = [
  {
    label: "PDF",
    ariaLabel: "Paper PDF",
    href: "https://deliverome.org/paper/accessible-surfaceome/accessible-human-surfaceome.pdf",
  },
  {
    label: "bioRxiv",
    ariaLabel: "Preprint on bioRxiv",
    href: "https://www.biorxiv.org/content/10.64898/2026.10.18.759859v1",
  },
  {
    label: "Code",
    ariaLabel: "Source code on GitHub",
    href: "https://github.com/Deliverome-Project/accessible-surfaceome",
  },
  {
    label: "Data",
    ariaLabel: "Data deposit on Zenodo",
    href: "https://doi.org/10.5281/zenodo.20805383",
  },
];

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
  // Rebuild deep-dive filters from records so a new filter field works
  // without redeploying the Worker (the /v1/catalog `ddf` lags the in-tree
  // taxonomy). Same helper /compare uses.
  const rows = await withDeepDiveFilters(catalog.rows);

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.hero}>
          <h1 className={`h-display ${styles.heroH1}`}>
            A consensus database of the{" "}
            <span className={styles.heroAccent}>
              accessible human surfaceome
            </span>
            .
          </h1>
          <p className={`lede ${styles.lede}`}>
            Five public surfaceome databases disagree more often than
            they agree. This atlas reconciles them: an LLM agent triages
            every protein-coding human gene, and a deep-dive agent
            compiles cited evidence for each strong candidate.
          </p>
          <aside className={styles.paper} aria-labelledby="paper-heading">
            <div className={styles.paperRow}>
              <div className={styles.paperText}>
                <h2 id="paper-heading" className="label-mono">
                  The paper
                </h2>
                <p className={styles.paperCitation}>
                  <cite className={styles.paperTitle}>
                    The accessible human surfaceome
                  </cite>
                  <span className={styles.paperMeta}>
                    Carlson, Hollingsworth &amp; Smallegan · bioRxiv, 2026
                  </span>
                </p>
              </div>
              <div className={styles.paperActions}>
                <a
                  href={PAPER_HTML_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.paperRead}
                  aria-label="Read the paper (opens in a new tab)"
                >
                  Read the paper
                  <span aria-hidden="true">→</span>
                </a>
                <ul className={styles.paperLinks}>
                  {PAPER_LINKS.map((link) => (
                    <li key={link.href}>
                      <a
                        href={link.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={styles.paperLink}
                        aria-label={`${link.ariaLabel} (opens in a new tab)`}
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <PaperCite />
          </aside>
        </header>

        <CatalogTable
          rows={rows}
          generated_at={catalog.generated_at}
          n_rows={catalog.n_rows}
          n_with_triage={catalog.n_with_triage}
          n_with_deep_dive={catalog.n_with_deep_dive}
          universe_version={catalog.universe_version}
        />

        <footer className={styles.footnotes}>
          <p>
            <span className="label-mono">Triage agent ·</span> a single
            Claude call with an NCBI context block, run on every
            protein-coding gene. Verdicts read as <em>yes</em>{" "}
            (constitutively on the surface), <em>contextual</em>{" "}
            (conditional or rare surface), <em>no</em> (no
            plasma-membrane presence). Deep-dive records linked from
            the <em>yes</em> column in the &ldquo;Deep dive&rdquo;
            slot override the triage call when present. The alternative
            models (Haiku 4.5, Opus 4.8) used in the manuscript
            comparison live on{" "}
            <a href="/benchmark/" className={styles.surfaceBenchLink}>
              SurfaceBench
            </a>
            .
          </p>
        </footer>
      </section>
    </Shell>
  );
}
