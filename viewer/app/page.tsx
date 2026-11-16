import { Shell } from "../components/Shell/Shell";
import { CatalogTable } from "../components/CatalogTable/CatalogTable";
import { PaperStrip } from "../components/PaperStrip/PaperStrip";
import { loadCatalog, withDeepDiveFilters } from "../lib/surfaceome";
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
          <PaperStrip />
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
