import { readFileSync } from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import { StudiesExplorer } from "../../components/StudiesExplorer/StudiesExplorer";
import { TierPill } from "../../components/StudiesExplorer/TierPill";
import { deepDiveTier } from "../../lib/catalog-presets";
import { loadCatalog, withDeepDiveFilters } from "../../lib/surfaceome";
import {
  baseAccession,
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
  type TierMap,
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
 * study index and each protein's deep-dive tier are baked in at build time;
 * the per-protein presence shards are fetched in the browser only when a
 * reader opens a study's protein list or compares studies.
 */
export default async function SurfaceProteomicsPage() {
  const index = JSON.parse(
    readFileSync(
      path.join(process.cwd(), "public", "data", "surface-proteomics", "studies.json"),
      "utf8",
    ),
  ) as StudyIndex;

  // Same tier derivation the catalog and gene pages use, keyed by accession.
  const catalog = await loadCatalog();
  const rows = await withDeepDiveFilters(catalog.rows);
  const tiers: TierMap = {};
  for (const r of rows) {
    if (r.deep_dive && r.deep_dive_filters && r.uniprot) {
      tiers[baseAccession(r.uniprot)] = deepDiveTier(r.deep_dive_filters).tier;
    }
  }

  const counted = index.arms.filter(isCounted);
  const countByStatus = (s: ArmStatus) => index.arms.filter((a) => a.status === s).length;

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <p className={`label-mono ${styles.eyebrow}`}>Open data</p>
          <h1 className={`h-data ${styles.title}`}>Surface proteomics data</h1>
          <p className={styles.lede}>
            Which proteins have published experiments actually found on the
            outside of human cells? We collected {index.n_arms} datasets from {index.n_publications} cell-surface
            proteomics papers and matched every reported protein to its UniProt
            accession. <strong>{counted.length} datasets</strong> from{" "}
            {index.n_admitted_publications} papers label proteins on intact cells
            and pass our quality review; together they detect{" "}
            <strong>{index.n_accessions_admitted.toLocaleString("en-US")} proteins</strong>.
            The rest are listed for completeness and clearly marked as not
            counted.
          </p>
          <p className={styles.note}>
            Each protein links to its Surfaceome page where one exists and
            carries our deep-dive tier, so you can see whether it is a Canonical
            or Likely surface protein. Snapshot{" "}
            <code>{index.snapshot}</code>, built {index.generated_at}. Study
            curation is AI-assisted and still under review; report an error to{" "}
            <a href="mailto:surfaceome-viewer@deliverome.org">surfaceome-viewer@deliverome.org</a>.
          </p>
        </header>

        <details className={styles.key}>
          <summary className={styles.keySummary}>
            How to read this page{" "}
            <span className={styles.keyHint}>
              methods, review status, scores and Surfaceome tiers
            </span>
          </summary>
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
                    The share of a study&apos;s proteins that are already well-established
                    surface proteins. A clean intact-cell experiment scores high; one
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

        <StudiesExplorer index={index} tiers={tiers} />
      </section>
    </Shell>
  );
}
