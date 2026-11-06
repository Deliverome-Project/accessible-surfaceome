import { readFileSync } from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import { StudiesExplorer } from "../../components/StudiesExplorer/StudiesExplorer";
import { TierPill } from "../../components/StudiesExplorer/TierPill";
import {
  DOWNLOADS,
  isCounted,
  METHOD_CLASS_LABEL,
  OVERLAP_SCREEN,
  STATUS_HELP,
  STATUS_LABEL,
  TIER_HELP,
  TIER_ORDER,
  type ArmStatus,
  type MethodClass,
  type StudyIndex,
} from "../../lib/surface-proteomics";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Surface proteomics data — Surfaceome",
  description:
    "Published human cell-surface proteomics studies, with method, cell type, " +
    "review status and the proteins each detected. Compare and intersect the " +
    "protein lists of two or more studies.",
};

const METHOD_HELP: Record<MethodClass, string> = {
  intact_cell:
    "Proteins are tagged on living, unbroken cells (biotinylation, glycan capture, proximity labeling), so a tag can only reach what faces outward. This is the only method family we count as evidence that a protein is reachable from outside the cell.",
  fractionation:
    "Cells are broken open and membranes are purified. This shows that a protein is membrane-associated, including on internal membranes, not that it is exposed on the outer surface.",
};

const sentence = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

const STATUS_ORDER: ArmStatus[] = ["core", "provisional", "held", "below_screen", "comparator"];

/**
 * /surface-proteomics/ — the S3E8 study compendium, linked from
 * deliverome.org's Open Data menu rather than the viewer's own nav. The
 * study index is baked in at build time;
 * the per-protein presence shards are fetched in the browser only when a
 * reader opens a study's protein list or compares studies.
 */
export default function SurfaceProteomicsPage() {
  const index = JSON.parse(
    readFileSync(
      path.join(process.cwd(), "public", "data", "surface-proteomics", "studies.json"),
      "utf8",
    ),
  ) as StudyIndex;

  const counted = index.arms.filter(isCounted);
  const countByStatus = (s: ArmStatus) => index.arms.filter((a) => a.status === s).length;

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>Surface proteomics data</h1>
          <p className={styles.lede}>
            Which proteins have published experiments actually found on the
            outside of human cells? We collected {index.n_arms} datasets from {index.n_publications} cell-surface
            proteomics papers and matched every reported protein to its UniProt
            accession. <strong>{counted.length} datasets</strong> from{" "}
            {index.n_admitted_publications} papers pass our quality review (see &ldquo;How to read this page&rdquo;)
            and count as surface evidence; together they detect{" "}
            <strong>{index.n_accessions_admitted.toLocaleString("en-US")} proteins</strong>.
            The other {index.n_arms - counted.length} are listed for completeness
            and marked as not counted.
          </p>
          <p className={styles.scope}>
            The compendium covers whole-surface measurements: labeling of exposed proteins on intact cells, and membrane fractionation. It does not include targeted membrane enrichment of chosen proteins, such as proximity labeling around a single bait, antibody or affinity pulldowns, or lists restricted to a target panel.
          </p>
          <p className={styles.downloads}>
            <strong>Download:</strong>{" "}
            <a href={DOWNLOADS.matrix} download>
              every protein × dataset (TSV, {index.n_accessions.toLocaleString("en-US")} rows)
            </a>{" "}
            ·{" "}
            <a href={DOWNLOADS.datasets} download>
              dataset details (TSV, {index.n_arms} rows)
            </a>
          </p>
        </header>

        <details className={styles.key}>
          <summary className={styles.keySummary}>
            How to read this page{" "}
            <span className={styles.keyHint}>
              what counts as surface evidence, methods, scores and Surfaceome tiers
            </span>
          </summary>
          <section className={styles.review} aria-labelledby="quality-review">
          <h2 id="quality-review" className={styles.reviewTitle}>
            What our quality review checks
          </h2>
          <p className={styles.reviewLede}>
            A dataset counts as surface evidence only if it passes all four checks, judged
            from each paper&apos;s methods section and supplementary tables. The reading is
            AI-assisted and still under review; report an error to{" "}
            <a href="mailto:surfaceome-viewer@deliverome.org">surfaceome-viewer@deliverome.org</a>.
          </p>
          <ol className={styles.checks}>
            <li>
              <strong>Human cells or tissue.</strong> Non-human proteins and samples are
              excluded before anything else.
            </li>
            <li>
              <strong>Labeled on intact, living cells.</strong> The tag (biotin, glycan
              capture, proximity label) went on before the cells were broken open, so it
              could only reach proteins facing outward. Membrane fractionation and labels
              that reach inside the cell fail this check.{" "}
              <span className={styles.fails}>{countByStatus("comparator")} datasets → Comparator</span>
            </li>
            <li>
              <strong>Mostly surface proteins, not background.</strong> At least{" "}
              {Math.round(OVERLAP_SCREEN * 100)}% of the dataset&apos;s proteins must be
              established surface proteins, meaning Canonical or Likely in our Surfaceome. A
              list below that is dominated by intracellular contamination. (A random set of
              human proteins scores about 15%.) When the authors pre-filtered their list to
              annotated surface proteins, the bar is raised to match.{" "}
              <span className={styles.fails}>
                {countByStatus("below_screen")} datasets → High background
              </span>
            </li>
            <li>
              <strong>Readable per protein.</strong> The published table has to say which
              proteins were detected. Tables where every value is imputed, or where the
              baseline sample can&apos;t be identified, fail.{" "}
              <span className={styles.fails}>{countByStatus("held")} datasets → Held</span>
            </li>
          </ol>
          <p className={styles.reviewLede}>
            Datasets that pass are <strong>Core</strong> ({countByStatus("core")}), or{" "}
            <strong>Provisional</strong> ({countByStatus("provisional")}) when they pass with a
            caveat, such as sitting within two points of the {Math.round(OVERLAP_SCREEN * 100)}%
            bar. Both count.
          </p>
        </section>
          <p className={styles.snapshot}>
            Data snapshot <code>{index.snapshot}</code>, built {index.generated_at}.
          </p>
          <div className={styles.keyGrid}>
            <section>
              <h2 className={styles.keyHead}>Method</h2>
              <dl className={styles.defs}>
                {(Object.keys(METHOD_HELP) as MethodClass[])
                  .filter((m) => index.arms.some((a) => a.method_class === m))
                  .map((m) => (
                  <div key={m}>
                    <dt>
                      <span className={`${styles.swatch} ${styles[`sw_${m}`]}`} aria-hidden="true" />
                      {METHOD_CLASS_LABEL[m]}
                    </dt>
                    <dd>{METHOD_HELP[m]}</dd>
                  </div>
                ))}
              </dl>
            </section>
            <section>
              <h2 className={styles.keyHead}>Review status</h2>
              <dl className={styles.defs}>
                {STATUS_ORDER.map((s) => (
                  <div key={s}>
                    <dt>
                      {STATUS_LABEL[s]}{" "}
                      <span className={s === "core" || s === "provisional" ? styles.yes : styles.no}>
                        {s === "core" || s === "provisional" ? "counted" : "not counted"}
                      </span>{" "}
                      <span className={styles.n}>{countByStatus(s)} datasets</span>
                    </dt>
                    <dd>{sentence(STATUS_HELP[s].replace(/^[^:]+:\s*/, ""))}</dd>
                  </div>
                ))}
              </dl>
            </section>
            <section>
              <h2 className={styles.keyHead}>Scores</h2>
              <dl className={styles.defs}>
                <div>
                  <dt>Surface overlap</dt>
                  <dd>
                    The share of a study&apos;s proteins that are Canonical or Likely in our
                    Surfaceome. A clean intact-cell experiment scores high; one
                    swamped by intracellular contamination scores low. Intact-cell datasets
                    need at least {Math.round(OVERLAP_SCREEN * 100)}% (the tick on each
                    bar) to be counted.
                  </dd>
                </div>
                <div>
                  <dt>Counted datasets</dt>
                  <dd>
                    For a protein, how many of the {counted.length} counted datasets detected
                    it. Many independent detections on intact cells is strong evidence
                    that the protein is surface-exposed in at least some cell types.
                  </dd>
                </div>
              </dl>
            </section>
            <section>
              <h2 className={styles.keyHead}>Surfaceome tier</h2>
              <dl className={styles.defs}>
                {TIER_ORDER.map((t) => (
                  <div key={t}>
                    <dt>
                      <TierPill tier={t} withTitle={false} />
                    </dt>
                    <dd>{TIER_HELP[t]}</dd>
                  </div>
                ))}
              </dl>
            </section>
          </div>
        </details>

        <StudiesExplorer index={index} />
      </section>
    </Shell>
  );
}
