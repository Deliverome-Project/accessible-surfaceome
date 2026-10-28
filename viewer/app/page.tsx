import { Shell } from "../components/Shell/Shell";
import { CatalogTable } from "../components/CatalogTable/CatalogTable";
import { loadCatalog, withDeepDiveFilters } from "../lib/surfaceome";
import styles from "./page.module.css";

/**
 * Hero links to the preprint, its code and its data. The HTML and PDF
 * are the copies hosted on the Deliverome site; bioRxiv and the DOI
 * are the version of record. Data is the Zenodo concept DOI (all
 * releases); /reproducibility lists the per-version handles.
 */
const PAPER_LINKS: {
  label: string;
  ariaLabel: string;
  href: string;
  primary?: boolean;
}[] = [
  {
    label: "Read the paper",
    ariaLabel: "Read the paper on the Deliverome site",
    href: "https://deliverome.org/paper/accessible-surfaceome/",
    primary: true,
  },
  {
    label: "PDF",
    ariaLabel: "Download the paper as a PDF",
    href: "https://deliverome.org/paper/accessible-surfaceome/accessible-human-surfaceome.pdf",
  },
  {
    label: "bioRxiv",
    ariaLabel: "The preprint on bioRxiv",
    href: "https://www.biorxiv.org/content/10.64898/2026.10.18.759859v1",
  },
  {
    label: "DOI 10.64898/2026.10.18.759859",
    ariaLabel: "Preprint DOI 10.64898/2026.10.18.759859",
    href: "https://doi.org/10.64898/2026.10.18.759859",
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
            Roughly 10–20% of human proteins reach the cell surface, yet
            over 65% of approved drugs target these molecules —
            accessibility on the extracellular face of the plasma
            membrane lets a drug act without crossing into the cell.
            Five public databases (UniProt, GO Cellular Component, the
            Human Protein Atlas, the Cell Surface Protein Atlas, and
            SURFY) each catalog the surfaceome, but with different
            definitions and methods, so their calls disagree more often
            than they agree.
          </p>
          <p className={`lede ${styles.lede}`}>
            This atlas reconciles them. An LLM triage agent scores
            every protein-coding human gene against the union of the
            five sources; a deep-dive agent then assembles the evidence
            behind each strong candidate — surface-localization
            methods, antibody validation, isoform topology,
            accessibility caveats — into per-gene records. Open
            accession, evidence-cited, agent-readable.
          </p>
          <aside className={styles.paper} aria-labelledby="paper-heading">
            <h2 id="paper-heading" className={`label-mono ${styles.paperLabel}`}>
              The paper
            </h2>
            <p className={styles.paperCitation}>
              <cite className={styles.paperTitle}>
                The accessible human surfaceome
              </cite>{" "}
              · Carlson, Hollingsworth &amp; Smallegan · bioRxiv, 2026
            </p>
            <ul className={styles.paperLinks}>
              {PAPER_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={link.primary ? styles.paperLinkPrimary : styles.paperLink}
                    aria-label={`${link.ariaLabel} (opens in a new tab)`}
                  >
                    {link.label}
                    <span aria-hidden="true">↗</span>
                  </a>
                </li>
              ))}
            </ul>
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
