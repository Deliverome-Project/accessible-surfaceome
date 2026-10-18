import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Data and code availability — Surfaceome",
  description:
    "Code, data, and figure-reproduction handles for the accessible " +
    "surfaceome project. Code under MIT (concept DOI " +
    "10.5281/zenodo.22116981); the Zenodo data deposit (concept DOI " +
    "10.5281/zenodo.20805383) under CC0 1.0; per-figure reproduction " +
    "gists archived to Software Heritage.",
};

/**
 * /reproducibility/ — methods-style "Data and code availability"
 * page. Three handles: the GitHub repository (MIT, includes this
 * viewer; Zenodo code concept DOI 10.5281/zenodo.22116981, one version
 * DOI per tagged GitHub release), the Zenodo data deposit (CC0 1.0;
 * concept DOI 10.5281/zenodo.20805383, one version DOI per numbered data
 * release — listed on Zenodo and by the API's /v1/releases), and a
 * per-figure reproduction gist archived to Software Heritage
 * (swh:1:rev:<sha>, recorded in swhid_map.json). The deposit-contents
 * list mirrors data release 1.3.0. The manuscript is NOT part of the
 * data deposit — it gets its own Zenodo record under the bioRxiv DOI.
 */
export default function ReproducibilityPage() {
  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>
            Data and code availability
          </h1>
          <p className={styles.lede}>
            All code, data, and figures are distributed under open
            licenses with persistent citation handles. Code is MIT; the
            Zenodo data deposit is CC0 1.0 with a DOI that resolves
            indefinitely; each figure ships a standalone reproduction
            gist archived to Software Heritage as a content-addressed
            SWHID.
          </p>
        </header>

        <section className={styles.section}>
          <h2 className={`h-data-section ${styles.sectionHead}`}>
            Code
          </h2>
          <p className={styles.body}>
            The full project — data pipelines, agent prompts, build
            scripts, and the source for this site — lives in one
            repository under the MIT License.
          </p>
          <dl className={styles.handleCard}>
            <dt className={styles.handleLabel}>Repository</dt>
            <dd className={styles.handleValue}>
              <a
                href="https://github.com/Deliverome-Project/accessible-surfaceome"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.extLink}
              >
                github.com/Deliverome-Project/accessible-surfaceome
              </a>
            </dd>
            <dt className={styles.handleLabel}>Concept DOI (all versions)</dt>
            <dd className={styles.handleValue}>
              <a
                href="https://doi.org/10.5281/zenodo.22116981"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.extLink}
              >
                10.5281/zenodo.22116981
              </a>
            </dd>
            <dt className={styles.handleLabel}>License</dt>
            <dd className={styles.handleValue}>MIT</dd>
          </dl>
          <p className={styles.body}>
            Each tagged GitHub release is archived on{" "}
            <a
              href="https://zenodo.org/"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.extLink}
            >
              Zenodo
            </a>{" "}
            through the GitHub integration. The concept DOI above
            resolves to the latest release, and each release also has
            its own version DOI, listed on its Zenodo record. Cite the
            concept DOI for the software in general, or a version DOI
            to pin a specific snapshot.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={`h-data-section ${styles.sectionHead}`}>
            Data
          </h2>
          <p className={styles.body}>
            Datasets are deposited on Zenodo under{" "}
            <a
              href="https://creativecommons.org/publicdomain/zero/1.0/"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.extLink}
            >
              CC0 1.0
            </a>
            . The deposit includes:
          </p>
          <ul className={styles.list}>
            <li>
              <strong>SurfaceBench</strong> — the curated 147-protein
              benchmark with ground-truth labels, per-model verdicts,
              and the curation rationale.
            </li>
            <li>
              <strong>Triage results</strong> — one row per human
              protein-coding gene with the agent&apos;s verdict,
              reason, and per-call metadata.
            </li>
            <li>
              <strong>Deep-dive records</strong> — a per-gene JSON for
              every gene that received a full evidence assembly, each
              carrying its evidence chain and its deep-dive tier.
            </li>
          </ul>
          <dl className={styles.handleCard}>
            <dt className={styles.handleLabel}>Concept DOI (all versions)</dt>
            <dd className={styles.handleValue}>
              <a
                href="https://doi.org/10.5281/zenodo.20805383"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.extLink}
              >
                10.5281/zenodo.20805383
              </a>
            </dd>
            <dt className={styles.handleLabel}>License</dt>
            <dd className={styles.handleValue}>CC0 1.0</dd>
          </dl>
          <p className={styles.body}>
            Cite the concept DOI, which always resolves to the latest
            release. Each numbered data release also has its own version
            DOI, listed on the Zenodo record and by the API at{" "}
            <a
              href="https://api.deliverome.org/surfaceome/v1/releases"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.extLink}
            >
              <code>/v1/releases</code>
            </a>
            ; cite a version DOI to pin an exact snapshot.
          </p>
          <p className={styles.body}>
            The Zenodo DOI is wired into the figure generator
            (<code>scripts/figures/embed_figure_gist_metadata.py</code>) so every
            figure PDF/PNG carries the dataset citation in its metadata as
            soon as it&apos;s rendered. Release 1.3.0 of the deposit
            contains:
          </p>
          <ul className={styles.list}>
            <li>
              <code>triage-runs-genome-with-reasoning.tsv</code> — every
              triage agent call across the protein-coding genome (33,728
              rows: the 19,324-gene NCBI-context pass plus 14,404 rows
              from the PubMed-context rescue pass, each labelled by a{" "}
              <code>triage_pass</code> column), with verdict, reason,
              confidence, and free-text reasoning.
            </li>
            <li>
              <code>triage-benchmark-with-reasoning.tsv</code> — the
              147-protein SurfaceBench (7,938 rows: 147 genes × 18
              model-variant cells × 3 replicates) with truth labels
              joined to every triage call.
            </li>
            <li>
              <code>deep-dive-preset-membership.tsv</code> — catalog
              preset membership for every deep-dived gene (5,332 rows),
              computed with the predicates documented on the{" "}
              <a href="/api/#presets" className={styles.extLink}>
                API page
              </a>
              .
            </li>
            <li>
              <code>deep_dives_1.3.0.tar.gz</code> — the 5,332 per-gene
              deep dives: for each gene the record JSON, its evidence
              ledger and its Markdown brief, plus a{" "}
              <code>manifest.tsv</code>.
            </li>
            <li>
              <code>deep-dive-reproducibility-replicates-v1.tar.gz</code>{" "}
              — the run-to-run reproducibility replicates behind
              Supplementary Figure 16 (not published records).
            </li>
            <li>
              <code>figure-source-data_1.3.0.tar.gz</code> — the source
              table behind every data figure in the manuscript, the four
              canonical figure-input tables (including{" "}
              <code>db_optimized_cutoffs.tsv</code>), and a{" "}
              <code>manifest.tsv</code> giving each file&apos;s figure,
              sha256, reproduction gist and SWHID.
            </li>
          </ul>
          <p className={styles.body}>
            Between releases, the API keeps a write-once history of
            every gene: each distinct state it served is archived as a
            numbered revision at{" "}
            <code>/v1/genes/{"{SYMBOL}"}/revisions</code>, and the
            numbered data releases, with their Zenodo version DOIs, are
            listed at <code>/v1/releases</code>. See the{" "}
            <a href="/api/#history" className={styles.extLink}>
              API page
            </a>{" "}
            for details.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={`h-data-section ${styles.sectionHead}`}>
            Per-figure reproduction
          </h2>
          <p className={styles.body}>
            Each published figure ships with a public GitHub Gist
            containing a standalone reproduction script and a short
            README pointing to the canonical data source. Scripts
            declare their dependencies inline using{" "}
            <a
              href="https://packaging.python.org/en/latest/specifications/inline-script-metadata/"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.extLink}
            >
              inline script metadata
            </a>{" "}
            so a reader can execute the figure with{" "}
            <code>uv run make_&lt;figure&gt;.py</code> — no
            environment setup, no <code>pip install</code> step.
          </p>
          <p className={styles.body}>
            Each gist is archived to{" "}
            <a
              href="https://www.softwareheritage.org/"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.extLink}
            >
              Software Heritage
            </a>{" "}
            (via Save Code Now) and cited as a content-addressed{" "}
            <code>swh:1:rev:&lt;sha&gt;</code> of the gist&apos;s HEAD
            commit — recorded per figure in the repository&apos;s{" "}
            <code>swhid_map.json</code>. The revision pins the exact
            script + data snapshot a figure was rendered against and
            resolves from the SWH archive even if the gist is later
            deleted. The underlying dataset&apos;s durable handle is the
            Zenodo DOI above.
          </p>
          <p className={styles.body}>
            For convenience, every figure file also carries citation
            handles in its metadata: PNG outputs embed the gist URL in
            the <code>Source</code> tEXt chunk and the dataset Zenodo
            DOI in <code>Subject</code>; PDF outputs use the analogous{" "}
            <code>Subject</code> + <code>Keywords</code> fields. The
            handles travel with the file across downstream contexts —
            slide decks, blog posts, supplementary uploads. Read with{" "}
            <code>exiftool figure.png</code>.
          </p>
        </section>
      </section>
    </Shell>
  );
}
