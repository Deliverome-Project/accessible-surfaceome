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
  enriched: "Enriched",
  group_enriched: "Group enriched",
  enhanced: "Enhanced",
  low_specificity: "Low specificity",
  not_detected: "Below detection",
  // Legacy v2.0/v2.1 strings, mapped onto the renamed labels so older
  // D1 rows render the right chip during the schema transition.
  tissue_enriched: "Enriched",
  tissue_enhanced: "Enhanced",
};

const ENRICHMENT_BLURB: Record<EnrichmentClass, string> = {
  enriched:
    "≥ 4× higher mRNA in one entity than the next-ranked. The strongest specificity class.",
  group_enriched:
    "A small group (2-5) of entities all express at ≥ 4× the next-ranked. Class-restricted but not strictly single-entity.",
  enhanced:
    "≥ 4× higher mRNA in one entity than the average of the rest. Selective but with non-trivial background.",
  low_specificity:
    "No entity stands out at ≥ 4× over the rest. Broadly expressed.",
  not_detected:
    "No entity meets the CZI Census noise threshold (≥ 10 expressing cells AND ≥ 1% of cells of that type). Distinct from low specificity — the gene's expression couldn't be measured above background at this Census coverage, not that it's expressed everywhere.",
  // Legacy aliases.
  tissue_enriched:
    "≥ 4× higher mRNA in one entity than the next-ranked. The strongest specificity class.",
  tissue_enhanced:
    "≥ 4× higher mRNA in one entity than the average of the rest. Selective but with non-trivial background.",
};

/** Normalize the legacy `tissue_*` strings onto the renamed ones so the
 *  data-class CSS selector picks the right styling. */
function normalizeClass(c: EnrichmentClass): EnrichmentClass {
  if (c === "tissue_enriched") return "enriched";
  if (c === "tissue_enhanced") return "enhanced";
  return c;
}

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
  axis: "cell class" | "cell type" | "tissue";
  klass: EnrichmentClass;
  foldChange: number | null;
  entityNames: string[];
}) {
  const norm = normalizeClass(klass);
  return (
    <div className={styles.classChip} data-class={norm}>
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
        {axis === "cell class" && (
          <>
            The cell-class axis rolls every leaf Cell Ontology term up to
            one of ~10 broad compartments (Epithelial, Immune, Neural,
            Endothelial, Stromal, Muscle, Reproductive, Stem, Tumor,
            Other) before applying the 4× rule. The leaf-CL axis has
            600+ entities and rarely produces a 4× winner; the broad-
            class axis is what HPA&apos;s rule was sized for.
          </>
        )}
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

  // v2.1.1 prefers the broad-class rollup (cell_class_enrichment) for
  // the chip — HPA's 4× rule works at the broad-class granularity
  // (10 compartments) where it doesn't at the leaf-CL granularity
  // (600+ terms). v2.1 still ships cell_type_enrichment at the leaf
  // level. v2.0 collapsed everything onto the top-level fields. Read
  // newest first, fall back through the chain so older D1 rows still
  // render their chip during the schema transition.
  const cellEnr = data.cell_class_enrichment
    ? {
        class: data.cell_class_enrichment.class,
        // class_labels are already human-readable names for the chip.
        ids: data.cell_class_enrichment.class_labels,
        fold_change: data.cell_class_enrichment.fold_change,
      }
    : data.cell_type_enrichment
    ? {
        class: data.cell_type_enrichment.class,
        ids: data.cell_type_enrichment.cl_ids,
        fold_change: data.cell_type_enrichment.fold_change,
      }
    : data.enrichment_class
    ? {
        class: data.enrichment_class,
        ids: data.enrichment_cl_ids ?? [],
        fold_change: data.fold_change ?? null,
      }
    : null;
  const cellAxisLabel: "cell class" | "cell type" =
    data.cell_class_enrichment ? "cell class" : "cell type";
  const tissueEnr = data.tissue_enrichment ?? null;

  const clToName = new Map(
    data.top_cell_types.map((r) => [r.cl_id, r.cell_type]),
  );

  return (
    <SectionCard
      title="CellxGene RNA enrichment"
      headClassName={styles.fullWidthHead}
      ledeClassName={styles.fullWidthLede}
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
          Where CZI Census detects this gene — every UBERON tissue
          (top), then the top 20 cell types (bottom). Default
          ranking is <strong>Score</strong> (mean log1p(CP10K) × %
          expressing, the population-mean metric most analogous to
          HPA&apos;s nTPM). Click any tissue bar to filter the
          cell-type chart to that tissue; the bar color flips from
          lavender (overall) to maroon (filtered).{" "}
          <InfoTip label="How to read these charts">
            <strong>Tissues</strong> — every UBERON tissue with
            detectable signal (n_total ≥ 1k), pooled across every
            cell type sampled from that tissue. Bars are colored by
            organ-system category (CNS lavender, respiratory teal,
            cardiovascular maroon, lymphoid amber, …) so the reader
            can scan by anatomy. Click a bar to filter the cell-
            type chart below.{" "}
            <strong>Top 20 cell types / Cell types in {"{tissue}"}</strong>{" "}
            — one chart, two modes: global top 20 by score when
            nothing is selected, swapping to the selected
            tissue&apos;s cells (with tissue-specific mean / pct /
            n) when a tissue is clicked. A &ldquo;Show top 20
            overall&rdquo; chip in the subhead returns to the
            unfiltered view.
            <br />
            <br />
            <strong>Y-axis</strong> — each chart has its own toggle.
            {" "}
            <strong>Score</strong> (default) = mean × % expressing,
            answers &ldquo;if I pick a random cell of this type,
            what total signal?&rdquo;{" "}
            <strong>Mean log1p(CP10K)</strong> = average among
            expressing cells (the y-axis on CZI&apos;s WMG dot plot);
            1 ≈ detected, 2 = moderate, 4+ = high, 6+ = among the
            strongest.{" "}
            <strong>% expressing</strong> = <code>n_expressing /
            n_total</code> in the Census-primary cohort (the
            dot-size channel of the WMG dot plot).
            <br />
            <br />
            <strong>Sort</strong> — by value (DESC by active metric),
            by category (group tissues by organ system), by tissue
            (group cell types by their dominant tissue), or A → Z.
            Trace (small-n) bars sink to the bottom under value- or
            category-based sort, render muted, and carry a small-n
            caveat in their hover popover. Hover any bar for full
            label + per-tissue detail.
          </InfoTip>
        </>
      }
    >
      {(cellEnr || tissueEnr) && (
        <div className={styles.chipRow}>
          {cellEnr && (
            <EnrichmentChip
              axis={cellAxisLabel}
              klass={cellEnr.class}
              foldChange={cellEnr.fold_change}
              entityNames={cellEnr.ids
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
