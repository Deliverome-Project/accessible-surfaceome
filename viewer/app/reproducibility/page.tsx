import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Data and code availability — Surfaceome",
  description:
    "Code, data, and figure-reproduction handles for the accessible " +
    "surfaceome project. Repository under MIT; the Zenodo data deposit " +
    "(DOI 10.5281/zenodo.20805384) under CC BY 4.0; per-figure " +
    "reproduction gists archived to Software Heritage.",
};

/**
 * /reproducibility/ — methods-style "Data and code availability"
 * page. Three handles: the live GitHub repository (MIT, includes this
 * viewer), the published Zenodo data deposit (CC BY 4.0; concept DOI
 * 10.5281/zenodo.20805383, version DOI 10.5281/zenodo.20805384), and a
 * per-figure reproduction gist archived to Software Heritage
 * (swh:1:rev:<sha>, recorded in swhid_map.json). The code-release
 * archive DOI is minted at the first tagged GitHub release.
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
            Zenodo data deposit is CC BY 4.0 with a DOI that resolves
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
            <dt className={styles.handleLabel}>License</dt>
            <dd className={styles.handleValue}>MIT</dd>
          </dl>
          <p className={styles.body}>
            At publication the tagged release is deposited on{" "}
            <a
              href="https://zenodo.org/"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.extLink}
            >
              Zenodo
            </a>{" "}
            via the GitHub integration, which mints a DOI for the
            release archive. Zenodo issues a concept DOI that resolves
            to the latest version and a version DOI for each release;
            cite the version DOI to pin to a specific snapshot.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={`h-data-section ${styles.sectionHead}`}>
            Data
          </h2>
          <p className={styles.body}>
            Datasets are deposited on Zenodo under{" "}
            <a
              href="https://creativecommons.org/licenses/by/4.0/"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.extLink}
            >
              CC BY 4.0
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
            <dt className={styles.handleLabel}>Version DOI (this release)</dt>
            <dd className={styles.handleValue}>
              <a
                href="https://doi.org/10.5281/zenodo.20805384"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.extLink}
              >
                10.5281/zenodo.20805384
              </a>
            </dd>
            <dt className={styles.handleLabel}>License</dt>
            <dd className={styles.handleValue}>CC BY 4.0</dd>
          </dl>
          <p className={styles.body}>
            The Zenodo DOI is wired into the figure generator
            (<code>scripts/embed_figure_gist_metadata.py</code>) so every
            figure PDF/PNG carries the dataset citation in its metadata as
            soon as it&apos;s rendered. The published deposit contains:
          </p>
          <ul className={styles.list}>
            <li>
              <code>triage-runs-genome-with-reasoning.tsv</code> — every
              triage agent call across the protein-coding genome (21,950
              rows: the NCBI-context sweep plus a targeted PubMed-context
              re-run), with verdict, reason, confidence, and free-text
              reasoning.
            </li>
            <li>
              <code>triage-benchmark-with-reasoning.tsv</code> — the
              147-protein SurfaceBench (4,851 rows) with truth labels
              joined to every per-model, per-variant triage call.
            </li>
            <li>
              <code>deep_dives_all.tar.gz</code> — the 5,130 per-gene
              deep-dive JSON records, each with its full evidence chain
              and deep-dive classification.
            </li>
          </ul>
          <p className={styles.body}>
            A later version of the deposit will add the manuscript,
            against the same concept DOI.
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
