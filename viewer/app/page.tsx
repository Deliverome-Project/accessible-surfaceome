import Link from "next/link";
import { Reveal } from "../components/Reveal/Reveal";
import { Shell } from "../components/Shell/Shell";
import { NumberedEyebrow } from "../components/NumberedEyebrow/NumberedEyebrow";
import { StatusPill } from "../components/surfaceome/StatusPill/StatusPill";
import { loadAllSurfaceomeRecords, prettyEnum } from "../lib/surfaceome";
import styles from "./page.module.css";

/**
 * Catalogue index for `surfaceome.deliverome.org`. Lists every
 * per-gene record in `public/data/surfaceome/*.json` with its
 * tier, surface_status, and DB vote so a reader can scan
 * candidates at a glance and click into one.
 */
export default function HomePage() {
  const records = loadAllSurfaceomeRecords();

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <Reveal className={styles.hero}>
          <NumberedEyebrow n={1}>Surfaceome</NumberedEyebrow>
          <h1 className={`h-display ${styles.heroH1}`}>
            A working atlas of <em>cell-surface proteins.</em>
          </h1>
          <p className={`lede ${styles.lede}`}>
            Each record is one human gene&apos;s case for — or against — being
            accessible from the outside of a cell. Open accession, evidence
            cited, machine-readable. The first reference records anchor the
            schema; more land as the annotation pipeline ingests them.
          </p>
          <p className={styles.apiLine}>
            <span className="label-mono">API ·</span>{" "}
            <code className={styles.code}>
              GET api.deliverome.org/surfaceome/v1/genes/&#123;SYMBOL&#125;
            </code>
          </p>
        </Reveal>

        <Reveal as="div" stagger stagger_ms={90} className={styles.section}>
          <header className={styles.sectionHead}>
            <NumberedEyebrow n={2}>Records</NumberedEyebrow>
            <h2 className={`h-section ${styles.sectionH2}`}>
              {records.length} gene{records.length === 1 ? "" : "s"} ingested
            </h2>
          </header>

          {records.length === 0 ? (
            <p className={styles.empty}>
              No records ingested yet — drop a{" "}
              <code className={styles.code}>SurfaceomeRecord</code> JSON into{" "}
              <code className={styles.code}>public/data/surfaceome/</code>.
            </p>
          ) : (
            <ul className={styles.list}>
              {records.map((rec) => {
                const g = rec.gene;
                const sub =
                  rec.targetability.recommended_modalities?.[0]?.kind ??
                  rec.triage_signal ??
                  rec.surface_biology.surface_status;
                return (
                  <li key={g.hgnc_symbol} className={styles.row}>
                    <Link href={`/${g.hgnc_symbol}/`} className={styles.rowLink}>
                      <div className={styles.rowSymbolBlock}>
                        <span className={`label-mono ${styles.rowEyebrow}`}>
                          {g.hgnc_id} · {g.uniprot_acc}
                        </span>
                        <span className={styles.rowSymbol}>{g.hgnc_symbol}</span>
                      </div>
                      <p className={styles.rowTldr}>{rec.targetability.tldr}</p>
                      <div className={styles.rowPills}>
                        <StatusPill tone="teal" size="sm">
                          {prettyEnum(rec.surface_biology.surface_status)}
                        </StatusPill>
                        <StatusPill tone="maroon" size="sm">
                          {prettyEnum(rec.targetability.tier)}
                        </StatusPill>
                        <StatusPill tone="lavender" size="sm">
                          {prettyEnum(rec.confidence)}
                        </StatusPill>
                        <span className={styles.rowSub}>
                          {rec.surface_biology.db_comparison.n_sources_voting_surface}/8 ·{" "}
                          {prettyEnum(sub)}
                        </span>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Reveal>
      </section>
    </Shell>
  );
}
