import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Data and code availability — Surfaceome",
  description:
    "Code, data, and figure-reproduction handles for the accessible " +
    "surfaceome project. Repository under MIT; Zenodo deposits under " +
    "CC BY 4.0; per-figure gists archived to Software Heritage.",
};

/**
 * /reproducibility/ — methods-style "Data and code availability"
 * page. Three handles: the live GitHub repository (MIT, includes
 * this viewer), the Zenodo deposit of the full repository at each
 * tagged release (CC BY 4.0 data + code), and per-figure
 * reproduction gists archived to Software Heritage. Actual DOIs and
 * SWHIDs are assigned at publication; the page renders placeholders
 * until then.
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
            licenses with persistent, content-addressed citation
            handles. Code is MIT; Zenodo deposits are CC BY 4.0;
            per-figure gists are archived to Software Heritage so
            citations resolve indefinitely.
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
              <strong>Deep-dive records</strong> — per-gene JSON and
              Markdown for every gene that received a full evidence
              assembly.
            </li>
          </ul>
          <dl className={styles.handleCard}>
            <dt className={styles.handleLabel}>Concept DOI</dt>
            <dd className={styles.handleValue}>
              <span className={styles.handlePending}>
                to be assigned at publication
              </span>
            </dd>
            <dt className={styles.handleLabel}>Version DOI (v1)</dt>
            <dd className={styles.handleValue}>
              <span className={styles.handlePending}>
                to be assigned at publication
              </span>
            </dd>
            <dt className={styles.handleLabel}>License</dt>
            <dd className={styles.handleValue}>CC BY 4.0</dd>
          </dl>
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
            (the PyPA-adopted form of PEP 723), so a reader can
            execute the figure with{" "}
            <code>uv run make_&lt;figure&gt;.py</code> — no
            environment setup, no <code>pip install</code> step.
          </p>
          <p className={styles.body}>
            Each gist is permanently archived via Software Heritage as
            a{" "}
            <a
              href="https://www.softwareheritage.org/2020/07/09/intrinsic-vs-extrinsic-identifiers/"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.extLink}
            >
              SWHID
            </a>{" "}
            of the form <code>swh:1:dir:&lt;sha1&gt;</code> — a
            content-addressed handle that resolves indefinitely from
            the Software Heritage archive and survives gist deletion,
            GitHub outages, or repository renames.
          </p>
          <p className={styles.body}>
            For convenience, every figure file also carries the live
            gist URL in its metadata: PNG outputs embed the URL in the{" "}
            <code>Source</code> tEXt chunk, PDF outputs embed it in
            the <code>Subject</code> info field, so the link travels
            with the file across downstream contexts. Read it with{" "}
            <code>exiftool figure.png | grep Source</code>.
          </p>
        </section>
      </section>
    </Shell>
  );
}
