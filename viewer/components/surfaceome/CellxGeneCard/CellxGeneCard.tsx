import type {
  CellxGeneEnrichment,
  EnrichmentClass,
} from "../../../lib/cellxgene-enrichment";
import { CITATIONS, pubmedUrl } from "../../../lib/citations";
import { InfoTip } from "../../InfoTip/InfoTip";
import { SectionCard } from "../SectionCard/SectionCard";
import { CellxGeneChart } from "./CellxGeneChart";
import styles from "./CellxGeneCard.module.css";

interface Props {
  data: CellxGeneEnrichment | null;
  n: number;
}

const ENRICHMENT_LABELS: Record<EnrichmentClass, string> = {
  tissue_enriched: "Tissue enriched",
  group_enriched: "Group enriched",
  tissue_enhanced: "Tissue enhanced",
  low_specificity: "Low specificity",
};

const ENRICHMENT_BLURB: Record<EnrichmentClass, string> = {
  tissue_enriched:
    "≥ 4× higher mRNA in one cell type than in any other cell type. The strongest specificity class.",
  group_enriched:
    "≥ 4× higher average mRNA across 2-5 cell types than in any other cell type. Cell-class-restricted but not strictly single-type.",
  tissue_enhanced:
    "≥ 4× higher mRNA in one cell type than the average of all others. Selective but with non-trivial background.",
  low_specificity:
    "No cell type stands out at ≥ 4× over the rest. Broadly expressed.",
};

function fmtFold(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "";
  if (v >= 100) return `${v.toFixed(0)}×`;
  return `${v.toFixed(1)}×`;
}

/**
 * CellxGene tab — CZI WMG gene-expression enrichment, presented as
 * two interactive HPA-style barplots (common vs rare cell types) +
 * the gene's HPA-style elevation classification.
 *
 * The chart components are client components (Y-axis + sort + hover
 * are reactive); this wrapper stays a server component so the
 * SectionCard chrome + the enrichment chip + the citation tag all
 * render at build time.
 */
export function CellxGeneCard({ data }: Props) {
  if (!data || !data.top_cell_types?.length) {
    return (
      <SectionCard
        title="CellxGene RNA enrichment"
        lede="No CZI CellxGene expression summary available for this gene yet."
      >
        <p className={styles.empty}>
          Coverage is genome-wide for protein-coding genes; absence here usually
          means the gene wasn&apos;t expressed above background (n &lt; 50 cells
          or mean log1p(CP10K) &lt; 1.0) in any of the ~600 cell types in
          this Census snapshot.
        </p>
      </SectionCard>
    );
  }

  const cellxgeneUrl = `https://cellxgene.cziscience.com/gene-expression?gene=${encodeURIComponent(
    data.gene_symbol,
  )}`;
  const enrichmentClass = data.enrichment_class;
  const enrichmentLabel = enrichmentClass
    ? ENRICHMENT_LABELS[enrichmentClass]
    : null;
  const enrichmentBlurb = enrichmentClass
    ? ENRICHMENT_BLURB[enrichmentClass]
    : null;
  const foldChange = data.fold_change;
  const enrichmentClIds = data.enrichment_cl_ids ?? [];

  // Resolve cl_id → display name from the chart's own rows so the chip
  // doesn't need a second lookup.
  const clToName = new Map(
    data.top_cell_types.map((r) => [r.cl_id, r.cell_type]),
  );
  const enrichmentNames = enrichmentClIds
    .map((id) => clToName.get(id) ?? id)
    .slice(0, 3);

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
          Top cell types ranked by mean log1p(CP10K) expression in
          expressing cells — the same scale cellxgene.cziscience.com&apos;s
          gene-expression viewer shows. Switch the Y-axis to %
          expressing for the dot-size channel of the WMG dot plot.{" "}
          <InfoTip label="What these metrics mean">
            <strong>Mean log1p(CP10K)</strong> averages over cells with
            at least one transcript — how strongly the cells that DO
            express it transcribe it. 1 ≈ detected, 2 = moderate, 4+ =
            high, 6+ = among the strongest transcripts in that cell
            type. <strong>% expressing</strong> is{" "}
            <code>n_expressing / n_total</code> in the Census-primary
            cohort. Hover any bar for cell-type details + the top
            tissues that cell type was sampled from. Common cell types
            (≥ 1,000 cells sampled) are plotted above; rare
            high-expressors (&lt; 1,000 cells, mean ≥ 2) get their own
            comparison panel below since small-n means are noisy.
          </InfoTip>
        </>
      }
    >
      {enrichmentClass && (
        <div className={styles.classChip} data-class={enrichmentClass}>
          <span className={styles.classLabel}>
            <span className={styles.classDot} aria-hidden />
            {enrichmentLabel}
            {foldChange != null && Number.isFinite(foldChange) && (
              <span className={styles.classFold}> · {fmtFold(foldChange)}</span>
            )}
          </span>
          {enrichmentNames.length > 0 && (
            <span className={styles.classCells}>
              in {enrichmentNames.join(" · ")}
            </span>
          )}
          {enrichmentBlurb && (
            <InfoTip label="What this classification means" wide>
              <strong>{enrichmentLabel}</strong>. {enrichmentBlurb} Definition
              follows{" "}
              <a
                href="https://www.proteinatlas.org/about/assays+annotation#singlecell_rna"
                target="_blank"
                rel="noopener noreferrer"
              >
                the HPA single-cell elevation taxonomy
              </a>
              , applied to CZI Census mean log1p(CP10K) after expm1 so the 4×
              rule is on the linear CP10K scale.
            </InfoTip>
          )}
        </div>
      )}
      <CellxGeneChart rows={data.top_cell_types} />
    </SectionCard>
  );
}
