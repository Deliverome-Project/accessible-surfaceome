import type { CellxGeneEnrichment } from "../../../lib/cellxgene-enrichment";
import { CITATIONS, pubmedUrl } from "../../../lib/citations";
import { InfoTip } from "../../InfoTip/InfoTip";
import { SectionCard } from "../SectionCard/SectionCard";
import styles from "./CellxGeneCard.module.css";

interface Props {
  data: CellxGeneEnrichment | null;
  n: number;
}

const BAR_MAX = 6.0;

function pctOfMax(v: number): number {
  const clamped = Math.max(0, Math.min(BAR_MAX, v));
  return (clamped / BAR_MAX) * 100;
}

function fmt(v: number, digits = 2): string {
  return v.toFixed(digits);
}

function fmtN(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${n}`;
}

/**
 * CellxGene tab — per-gene RNA enrichment from CZI's gene-expression
 * (WMG) export. Three blocks, in priority order for reader scanning:
 *
 *   1. Top-N delivery targets ranked by selectivity delta vs lymphoid
 *      baseline (B + CD4T + CD8T) — the "is this gene a candidate
 *      target for cell-type-X delivery?" question
 *   2. Lymphoid baseline reference line — what counts as "background"
 *   3. Top-N cell types overall by mean expression — the catalog view
 *
 * Values are mean log1p(CP10K) among expressing cells, matching the CZI
 * viewer's "Expression" channel. Bars are drawn against a fixed 0-6
 * scale (typical WMG mean ranges 0-7), so a gene's bars are directly
 * comparable across cards.
 */
export function CellxGeneCard({ data }: Props) {
  if (!data) {
    return (
      <SectionCard
        title="CellxGene RNA enrichment"
        lede="No CZI CellxGene expression summary available for this gene yet."
      >
        <p className={styles.empty}>
          Coverage is genome-wide for protein-coding genes; absence here usually
          means the gene wasn't expressed above background in any of the
          ~600 cell types in this Census snapshot.
        </p>
      </SectionCard>
    );
  }

  const targets = data.top_selective_targets ?? [];
  const cellTypes = data.top_cell_types ?? [];
  const lymph = data.lymphoid_baseline;
  const cellxgeneUrl = `https://cellxgene.cziscience.com/gene-expression?gene=${encodeURIComponent(
    data.gene_symbol,
  )}`;

  return (
    <SectionCard
      title="CellxGene RNA enrichment"
      meta={
        <>
          CZI Census {data.census_version} ·{" "}
          <a
            href={cellxgeneUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.viewerLink}
          >
            open in CellxGene viewer
          </a>{" "}
          ·{" "}
          <a
            href={pubmedUrl(CITATIONS.czCellxgene.pmid)}
            target="_blank"
            rel="noopener noreferrer"
          >
            {CITATIONS.czCellxgene.authorYear}
          </a>{" "}
          (CC-BY 4.0)
        </>
      }
      lede={
        <>
          Mean log1p(CP10K) expression among expressing cells, identical
          scale to cellxgene.cziscience.com&apos;s gene-expression viewer.
          Selectivity uses pooled B + CD4 T + CD8 T cells as the lymphoid
          baseline.{" "}
          <InfoTip label="What this scale means">
            CZI Census normalizes raw UMI counts to counts-per-10k, then
            applies log1p. &quot;Mean&quot; here is averaged over cells with
            at least one transcript of the gene, so the value reflects
            how strongly the cells that DO express it transcribe it, not
            what fraction of cells express it. A value of 1 is roughly
            &quot;detected,&quot; 2 is moderate, 4+ is high, 6+ is among
            the most-expressed transcripts in that cell type.
          </InfoTip>
        </>
      }
    >
      {targets.length > 0 && (
        <section className={styles.block}>
          <h3 className={styles.subhead}>
            Top selective targets
            <span className={styles.subheadMeta}>
              ranked by mean expression − lymphoid baseline
            </span>
          </h3>
          <ol className={styles.targetList}>
            {targets.map((t) => (
              <li key={t.target_key} className={styles.targetRow}>
                <div className={styles.targetLabel}>
                  <span className={styles.targetTitle}>{t.label}</span>
                  <span className={styles.targetMeta}>
                    {t.category} · n={fmtN(t.n_expressing)}
                  </span>
                </div>
                <div className={styles.barWrap}>
                  <div
                    className={styles.barFill}
                    style={{ width: `${pctOfMax(t.mean_log1p_cp10k)}%` }}
                    aria-hidden
                  />
                  <span className={styles.barValue}>
                    {fmt(t.mean_log1p_cp10k)}
                  </span>
                </div>
                <div className={styles.delta}>
                  Δ {t.delta_vs_lymphoid > 0 ? "+" : ""}
                  {fmt(t.delta_vs_lymphoid)}
                </div>
              </li>
            ))}
          </ol>
          <p className={styles.baselineLine}>
            Lymphoid baseline ({lymph.cl_ids.length} cell types, n=
            {fmtN(lymph.n_expressing)}):{" "}
            <strong>{fmt(lymph.mean_log1p_cp10k)}</strong>
          </p>
        </section>
      )}

      {cellTypes.length > 0 && (
        <section className={styles.block}>
          <h3 className={styles.subhead}>
            Top cell types overall
            <span className={styles.subheadMeta}>
              ranked by mean expression across all CZI cell types
            </span>
          </h3>
          <ol className={styles.cellList}>
            {cellTypes.map((c) => (
              <li key={c.cl_id} className={styles.cellRow}>
                <div className={styles.cellLabel}>
                  <span className={styles.cellTitle}>{c.cell_type}</span>
                  <span className={styles.cellMeta}>
                    {c.cl_id} · n={fmtN(c.n_expressing)}
                  </span>
                </div>
                <div className={styles.barWrap}>
                  <div
                    className={styles.barFill}
                    style={{ width: `${pctOfMax(c.mean_log1p_cp10k)}%` }}
                    aria-hidden
                  />
                  <span className={styles.barValue}>
                    {fmt(c.mean_log1p_cp10k)}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {targets.length === 0 && cellTypes.length === 0 && (
        <p className={styles.empty}>
          No cell type passed the n≥50 expressing-cell floor for this gene.
        </p>
      )}
    </SectionCard>
  );
}
