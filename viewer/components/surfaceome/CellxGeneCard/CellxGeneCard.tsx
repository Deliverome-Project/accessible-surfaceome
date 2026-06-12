import type {
  CellxGeneEnrichment,
  EnrichmentClass,
  TissueAggregateRow,
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

function EnrichmentChip({
  axis,
  klass,
  foldChange,
  entityNames,
}: {
  axis: "cell type" | "tissue";
  klass: EnrichmentClass;
  foldChange: number | null;
  entityNames: string[];
}) {
  return (
    <div className={styles.classChip} data-class={klass}>
      <span className={styles.classAxis}>{axis}</span>
      <span className={styles.classLabel}>
        <span className={styles.classDot} aria-hidden />
        {ENRICHMENT_LABELS[klass]}
        {foldChange != null && Number.isFinite(foldChange) && (
          <span className={styles.classFold}> · {fmtFold(foldChange)}</span>
        )}
      </span>
      {entityNames.length > 0 && (
        <span className={styles.classCells}>
          in {entityNames.join(" · ")}
        </span>
      )}
      <InfoTip label="What this classification means" wide>
        <strong>{ENRICHMENT_LABELS[klass]}</strong> at the {axis} level.{" "}
        {ENRICHMENT_BLURB[klass]} Definition follows{" "}
        <a
          href="https://www.proteinatlas.org/about/assays+annotation#singlecell_rna"
          target="_blank"
          rel="noopener noreferrer"
        >
          the HPA single-cell elevation taxonomy
        </a>
        , applied to CZI Census mean log1p(CP10K) after expm1 so the 4×
        rule is on the linear CP10K scale.{" "}
        {axis === "tissue" && (
          <>
            Reported at the tissue axis because a gene like SLC34A2 has 6+
            co-expressing alveolar cell subtypes, which exceeds HPA&apos;s
            2-5 group cap at the cell-type axis — at the tissue axis (lung)
            the elevation is unambiguous.
          </>
        )}
      </InfoTip>
    </div>
  );
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

  // v2.1 ships cell_type_enrichment + tissue_enrichment as separate
  // objects; v2.0 collapsed them onto the top-level (enrichment_class /
  // enrichment_cl_ids / fold_change). Read v2.1 first, fall back to the
  // v2.0 surface so older D1 rows still render their chip.
  const cellTypeEnr = data.cell_type_enrichment ?? (data.enrichment_class
    ? { class: data.enrichment_class, cl_ids: data.enrichment_cl_ids ?? [], fold_change: data.fold_change ?? null }
    : null);
  const tissueEnr = data.tissue_enrichment ?? null;

  const clToName = new Map(
    data.top_cell_types.map((r) => [r.cl_id, r.cell_type]),
  );

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
          Top cell types and tissues ranked by mean log1p(CP10K)
          expression in expressing cells — the same scale
          cellxgene.cziscience.com&apos;s gene-expression viewer shows.
          Switch the Y-axis to % expressing for the dot-size channel
          of the WMG dot plot.{" "}
          <InfoTip label="What each block shows">
            <strong>Tissues</strong> — every UBERON tissue with
            detectable signal (n_total ≥ 1k), pooled across every
            cell type sampled from that tissue. CLICK a tissue bar
            to filter the cell-type chart below to that tissue.{" "}
            <strong>Top 20 cell types / Cell types in {"{tissue}"}</strong>{" "}
            — one chart that shows the global top-20 by default and
            swaps to the selected tissue&apos;s cell types when a
            tissue is clicked. Stats are re-keyed to the
            tissue&apos;s row inside each cell type&apos;s top-3
            tissue list. A reset chip in the chart subhead returns
            to the Top 20 view.
            <br />
            <br />
            <strong>Y-axis options</strong> — Score (mean × pct,
            population-mean), Mean log1p(CP10K) of expressing cells,
            or % expressing. Each chart has its own toggle.{" "}
            <strong>Mean log1p</strong> values: 1 ≈ detected, 2 =
            moderate, 4+ = high, 6+ = among the strongest.{" "}
            <strong>% expressing</strong> is{" "}
            <code>n_expressing / n_total</code> in the Census-primary
            cohort.
          </InfoTip>
        </>
      }
    >
      {(cellTypeEnr || tissueEnr) && (
        <div className={styles.chipRow}>
          {cellTypeEnr && (
            <EnrichmentChip
              axis="cell type"
              klass={cellTypeEnr.class}
              foldChange={cellTypeEnr.fold_change}
              entityNames={cellTypeEnr.cl_ids
                .map((id) => clToName.get(id) ?? id)
                .slice(0, 3)}
            />
          )}
          {tissueEnr && (
            <EnrichmentChip
              axis="tissue"
              klass={tissueEnr.class}
              foldChange={tissueEnr.fold_change}
              entityNames={tissueEnr.tissue_labels.slice(0, 3)}
            />
          )}
        </div>
      )}
      <CellxGeneChart
        rows={data.top_cell_types}
        tissues={data.top_tissues ?? []}
        cellsByTissue={data.cells_by_tissue ?? {}}
      />
    </SectionCard>
  );
}
