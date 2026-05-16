import { Shell } from "../components/Shell/Shell";
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
        </header>

        <CatalogTable
          rows={catalog.rows}
          generated_at={catalog.generated_at}
          n_rows={catalog.n_rows}
          n_with_triage={catalog.n_with_triage}
          n_with_deep_dive={catalog.n_with_deep_dive}
          universe_version={catalog.universe_version}
        />

        <footer className={styles.footnotes}>
          <p>
            <span className="label-mono">DB columns ·</span> UniProt · GO ·
            SURFY · CSPA · HPA. Each cell is one source&apos;s vote on
            whether the protein reaches the cell surface; the{" "}
            <code>Sources</code> column is the count of those five (the M1
            universe gate). DeepTMHMM + COMPARTMENTS are tracked upstream as
            auxiliary signals but don&apos;t appear here.
          </p>
          <p>
            <span className="label-mono">Triage agent ·</span> a single
            Claude call with an NCBI context block, run on every
            protein-coding gene. Verdicts read as <em>yes</em>{" "}
            (constitutively on the surface), <em>contextual</em>{" "}
            (conditional or rare surface), <em>no</em> (no
            plasma-membrane presence). Deep-dive records linked from
            the <em>yes</em> column in the &ldquo;Deep dive&rdquo;
            slot override the triage call when present. The alternative
            models (Haiku 4.5, Opus 4.7) used in the manuscript
            comparison live on{" "}
            <a href="/benchmark/" className={styles.surfaceBenchLink}>
              SurfaceBench
            </a>
            .
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
            <code>{catalog.universe_version ?? "—"}</code>
          </p>
        </footer>
      </section>
    </Shell>
  );
}
