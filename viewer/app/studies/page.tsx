import { readFileSync } from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import { StudiesExplorer } from "../../components/StudiesExplorer/StudiesExplorer";
import type { StudyIndex } from "../../lib/surface-proteomics";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Surface proteomics studies — Surfaceome",
  description:
    "Published human cell-surface proteomics studies, with method, cell type, " +
    "review status and the proteins each detected. Compare the protein lists " +
    "of two or more studies.",
};

/**
 * /studies/ — the S3E8 study compendium. The study index is baked in at
 * build time (it is small); the per-protein presence shards are fetched in
 * the browser only when a reader opens a study's protein list or compares
 * studies.
 */
export default function StudiesPage() {
  const index = JSON.parse(
    readFileSync(
      path.join(process.cwd(), "public", "data", "surface-proteomics", "studies.json"),
      "utf8",
    ),
  ) as StudyIndex;

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>Surface proteomics studies</h1>
          <p className={styles.lede}>
            {index.n_arms} study arms from {index.n_publications} published human
            cell-surface proteomics papers, with the proteins each one reported.{" "}
            {index.n_admitted_arms} arms from {index.n_admitted_publications} papers
            label proteins on intact cells and pass our review; together they
            detect {index.n_accessions_admitted.toLocaleString("en-US")} proteins.
            The other arms are listed and labelled but not counted. Held arms
            publish tables that can&apos;t support a per-protein call. Below-screen
            arms overlap known surface proteins too little. Comparators, such as
            membrane fractionation and lysate glycoproteomes, show membrane
            association rather than extracellular access.
          </p>
          <p className={styles.note}>
            Select one study to see its proteins, or two or more to compare their
            overlap. Proteins are matched by current UniProt accession. Snapshot{" "}
            <code>{index.snapshot}</code>, built {index.generated_at}. Study
            curation is AI-assisted and still under review; report an error to{" "}
            <a href="mailto:surfaceome-viewer@deliverome.org">
              surfaceome-viewer@deliverome.org
            </a>
            .
          </p>
        </header>
        <StudiesExplorer index={index} />
      </section>
    </Shell>
  );
}
