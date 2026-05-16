import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Reproducibility — Surfaceome",
  description:
    "Every figure, dataset, and analysis script is content-addressed so " +
    "a citation can resolve to a specific snapshot indefinitely — " +
    "Software Heritage SWHIDs for code and figures, Zenodo DOIs for data " +
    "and the manuscript writeup.",
};

/**
 * /reproducibility/ — the project's citation-pinning surface. Three
 * pillars:
 *   1. Per-figure reproduction gists, each registered as a SWHID so
 *      the script + canonical-data URL remain resolvable even if
 *      GitHub deletes the gist.
 *   2. A whole-repo SWHID captured at manuscript submission so the
 *      entire codebase has a single citable handle.
 *   3. A Zenodo deposit of the data artifacts + manuscript writeup,
 *      with a concept DOI that always points to the latest version
 *      and individual version DOIs per upload.
 *
 * Actual SWHIDs and DOIs are assigned at publication; the page
 * currently renders placeholders.
 */
export default function ReproducibilityPage() {
  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <p className="h-data-eyebrow">Reproducibility</p>
          <h1 className={`h-data ${styles.title}`}>
            Citable, content-addressed, and durable.
          </h1>
          <p className={styles.lede}>
            Every figure, dataset, and analysis script in this project is
            content-addressed so that a citation can resolve to a specific
            snapshot indefinitely — independent of GitHub, our domains, or
            the rendering of this site. Below is how that&apos;s wired.
          </p>
        </header>

        <section className={styles.section}>
          <h2 className={`h-data-section ${styles.sectionHead}`}>
            Figures
          </h2>
          <p className={styles.body}>
            Each published figure ships with a public GitHub Gist that
            contains the reproduction script and a short README pointing
            to the canonical data source. Scripts declare their
            dependencies inline using PEP 723 metadata, so a reader can
            execute the figure with{" "}
            <code>uv run make_&lt;figure&gt;.py</code> — no environment
            setup, no <code>pip install</code> step.
          </p>
          <p className={styles.body}>
            Each gist is permanently archived via Software Heritage as a{" "}
            <a
              href="https://www.softwareheritage.org/2020/07/09/intrinsic-vs-extrinsic-identifiers/"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.extLink}
            >
              SWHID
            </a>{" "}
            (Software Heritage Identifier), a content-addressed handle of
            the form{" "}
            <code>swh:1:dir:&lt;sha1&gt;</code>. The SWHID points to a
            byte-exact snapshot of the gist and resolves indefinitely
            from the Software Heritage archive — the citation survives
            gist deletion, GitHub outages, or repository renames.
          </p>
          <p className={styles.body}>
            For convenience, every figure also carries the live gist URL
            inside its file metadata: PNG outputs embed the URL in the{" "}
            <code>Source</code> tEXt chunk and PDF outputs embed it in
            the <code>Subject</code> info field, so the link travels with
            the file when it&apos;s pasted into a Substack draft or
            forwarded over email. Read it with{" "}
            <code>exiftool figure.png | grep Source</code>.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={`h-data-section ${styles.sectionHead}`}>
            Whole-repository snapshot
          </h2>
          <p className={styles.body}>
            The full repository is registered with Software Heritage as a
            single SWHID, captured at the time of manuscript submission.
            This single handle covers every source file — data pipelines,
            agent prompts, viewer code, build scripts, the manuscript
            writeup — in one citable address.
          </p>
          <dl className={styles.handleCard}>
            <dt className={styles.handleLabel}>Live repository</dt>
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
            <dt className={styles.handleLabel}>Whole-repo SWHID</dt>
            <dd className={styles.handleValue}>
              <span className={styles.handlePending}>
                to be assigned at publication
              </span>
            </dd>
          </dl>
        </section>

        <section className={styles.section}>
          <h2 className={`h-data-section ${styles.sectionHead}`}>
            Zenodo deposit (data + writeup)
          </h2>
          <p className={styles.body}>
            At publication, the data artifacts and the manuscript writeup
            are deposited together on{" "}
            <a
              href="https://zenodo.org/"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.extLink}
            >
              Zenodo
            </a>{" "}
            with a DOI. The deposit will include:
          </p>
          <ul className={styles.list}>
            <li>
              <strong>SurfaceBench</strong> — the 147-protein benchmark,
              ground-truth labels, per-model verdicts, and the curation
              rationale.
            </li>
            <li>
              <strong>Triage results</strong> — one row per human
              protein-coding gene with the agent&apos;s verdict, reason,
              and per-call metadata.
            </li>
            <li>
              <strong>Deep-dive records</strong> — per-gene JSON and
              Markdown for every gene that received a full evidence
              assembly.
            </li>
            <li>
              <strong>Manuscript / blog writeup</strong> — the source
              text + figures.
            </li>
          </ul>
          <p className={styles.body}>
            Zenodo issues a <strong>concept DOI</strong> that always
            resolves to the latest version, plus a separate{" "}
            <strong>version DOI</strong> for each individual upload. The
            two are different addresses: cite the version DOI in a paper
            (it pins to a permanent snapshot) and use the concept DOI
            when you want the &ldquo;latest&rdquo; pointer. Updates
            after publication are supported — a new upload creates a new
            version DOI without touching the original.
          </p>
          <dl className={styles.handleCard}>
            <dt className={styles.handleLabel}>Concept DOI (latest)</dt>
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
          </dl>
        </section>
      </section>
    </Shell>
  );
}
