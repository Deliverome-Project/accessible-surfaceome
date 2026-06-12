import type {
  CellxGeneEnrichment,
  EnrichmentClass,
  TissueAggregateRow,
  TopEntityContrib,
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
  enhanced: "Enhanced",
  low_specificity: "Low specificity",
  not_detected: "Below detection",
  // Legacy strings, mapped onto the renamed labels so older D1 rows
  // render correctly during the schema transition. group_enriched
  // collapses to "Enriched" under v2.1.5's τ cutoffs (τ doesn't
  // distinguish single vs. few enriched).
  tissue_enriched: "Enriched",
  tissue_enhanced: "Enhanced",
  group_enriched: "Enriched",
};

const ENRICHMENT_BLURB: Record<EnrichmentClass, string> = {
  enriched:
    "τ ≥ 0.85 — concentrated in one or a few entities relative to the others where the gene is expressed.",
  enhanced:
    "0.5 ≤ τ < 0.85 — selectively elevated in some entities but with non-trivial background expression elsewhere.",
  low_specificity:
    "τ < 0.5 — broadly expressed; no entity dominates the others.",
  not_detected:
    "Either no entity meets the CZI Census noise threshold (≥ 10 expressing cells AND ≥ 1% of cells of that type), OR the top entity's linear pop mean is below the magnitude floor (≈ HPA's nTPM ≥ 1 detection threshold). Distinct from low specificity — the gene isn't strongly expressed anywhere worth flagging, even if τ alone would have fired enriched on a low-magnitude signal.",
  // Legacy aliases collapse to their τ-cutoff equivalents.
  tissue_enriched:
    "τ ≥ 0.85 — concentrated in one or a few entities relative to the others where the gene is expressed.",
  tissue_enhanced:
    "0.5 ≤ τ < 0.85 — selectively elevated in some entities but with non-trivial background expression elsewhere.",
  group_enriched:
    "τ ≥ 0.85 — concentrated in a small group of entities relative to the rest.",
};

/** Normalize the legacy strings onto the renamed ones so the
 *  data-class CSS selector picks the right styling. */
function normalizeClass(c: EnrichmentClass): EnrichmentClass {
  if (c === "tissue_enriched") return "enriched";
  if (c === "tissue_enhanced") return "enhanced";
  if (c === "group_enriched") return "enriched";
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
  tau,
  topContribs,
}: {
  axis: "cell class" | "cell type" | "cell family" | "tissue" | "tissue category" | "tissue organ";
  klass: EnrichmentClass;
  foldChange: number | null;
  entityNames: string[];
  tau?: number | null;
  topContribs?: TopEntityContrib[];
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
        {tau != null && Number.isFinite(tau) && (
          <span className={styles.classFold}> · τ={tau.toFixed(2)}</span>
        )}
      </span>
      {entityNames.length > 0 && (
        <span className={styles.classCells}>
          in {entityNames.join(" · ")}
        </span>
      )}
      <InfoTip label="What this classification means" wide>
        <strong>{ENRICHMENT_LABELS[klass]}</strong> at the {axis} level.{" "}
        {ENRICHMENT_BLURB[klass]}
        {(axis === "cell family" ||
          axis === "tissue organ" ||
          axis === "tissue category" ||
          axis === "cell class") && (
          <>
            {" "}
            Note: this axis groups CZI&apos;s ~600 leaf cell types (or
            ~410 UBERON tissues) into broader rollups (~150 cell
            families / ~150 tissue organs / 13 categories / 10
            compartments), so the entities here are coarser than the
            specific cell types in the chart below. Each rollup&apos;s
            signal is its strongest underlying leaf — that leaf
            appears in parentheses next to each rollup name, and
            matches what you see in the chart.
          </>
        )}
        {" "}<strong>Axis τ</strong> (the number on the chip header — Yanai 2005,
        PMID{" "}
        <a
          href="https://pubmed.ncbi.nlm.nih.gov/15388519/"
          target="_blank"
          rel="noopener noreferrer"
        >
          15388519
        </a>
        ) ∈ [0, 1] is the continuous specificity score over the full
        measured universe (ineligibles floored at 1e-3 ≈ noise) on
        linear population mean (mean × pct, ≈ nTPM). Cutoffs τ ≥ 0.85
        / 0.5 / &lt; 0.5 follow Kryuchkova-Mostacci &amp; Robinson-Rechavi
        2017 (PMID{" "}
        <a
          href="https://pubmed.ncbi.nlm.nih.gov/26891983/"
          target="_blank"
          rel="noopener noreferrer"
        >
          26891983
        </a>
        ) + Lüleci &amp; Yılmaz 2022.
        {topContribs && topContribs.length > 0 && (
          <>
            <br />
            <br />
            <strong>Top {topContribs.length} (within 50% of the peak):</strong>
            <ul style={{ margin: "4px 0 0 16px", paddingLeft: 0 }}>
              {topContribs.map((c) => (
                <li key={c.id}>
                  {c.label}
                  {c.sub_label && (
                    <span style={{ opacity: 0.78 }}> ({c.sub_label})</span>
                  )}
                  {" — pop mean "}
                  {c.pop_mean.toFixed(2)}
                </li>
              ))}
            </ul>
            <span style={{ opacity: 0.78, fontSize: "0.9em", display: "block", marginTop: "6px" }}>
              Only entities within 50% of the peak pop mean appear
              here; the rest of the ~150 axis entries (or ~10/13 for
              the broad-class / tissue-category axes) sit closer to
              the noise floor — they&apos;re what push the axis τ
              high when only one entity stands out.
            </span>
          </>
        )}
      </InfoTip>
    </div>
  );
}

/**
 * CellxGene tab — CZI WMG gene-expression enrichment, presented as
 * two interactive HPA-style barplots (common vs rare cell types) +
 * the gene's τ-cutoff elevation classification (Yanai 2005 τ on
 * linear population mean; cutoffs τ ≥ 0.85 / 0.5 follow
 * Kryuchkova-Mostacci 2017 + Lüleci & Yılmaz 2022).
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

  // v2.1.5 prefers the middle-granularity rollups for the chip — cell
  // FAMILY (~150 terms: B cell, T cell, macrophage, hepatocyte, ...)
  // and tissue ORGAN (~150 terms: brain, prostate gland, eye, ...).
  // These read more biologically specific than the 10/13 broad
  // class/category and more reliable than the 600/410 leaf axes.
  // Falls through to class/category/leaf for older records.
  const cellEnr =
    data.cell_family_enrichment
      ? {
          class: data.cell_family_enrichment.class,
          ids: data.cell_family_enrichment.family_labels ?? [],
          fold_change: data.cell_family_enrichment.fold_change,
          tau: data.cell_family_enrichment.tau ?? null,
          contribs: data.cell_family_enrichment.top_entity_contribs ?? null,
        }
      : data.cell_class_enrichment
      ? {
          class: data.cell_class_enrichment.class,
          ids: data.cell_class_enrichment.class_labels,
          fold_change: data.cell_class_enrichment.fold_change,
          tau: data.cell_class_enrichment.tau ?? null,
          contribs: data.cell_class_enrichment.top_entity_contribs ?? null,
        }
      : data.cell_type_enrichment
      ? {
          class: data.cell_type_enrichment.class,
          ids: data.cell_type_enrichment.cl_ids,
          fold_change: data.cell_type_enrichment.fold_change,
          tau: data.cell_type_enrichment.tau ?? null,
          contribs: data.cell_type_enrichment.top_entity_contribs ?? null,
        }
      : data.enrichment_class
      ? {
          class: data.enrichment_class,
          ids: data.enrichment_cl_ids ?? [],
          fold_change: data.fold_change ?? null,
          tau: null as number | null,
          contribs: null,
        }
      : null;
  const cellAxisLabel: "cell family" | "cell class" | "cell type" =
    data.cell_family_enrichment
      ? "cell family"
      : data.cell_class_enrichment
      ? "cell class"
      : "cell type";
  const tissueOrganEnr = data.tissue_organ_enrichment ?? null;
  const tissueCatEnr = data.tissue_category_enrichment ?? null;
  const tissueEnr = data.tissue_enrichment ?? null;
  const tissueAxisLabel: "tissue organ" | "tissue category" | "tissue" =
    tissueOrganEnr ? "tissue organ" : tissueCatEnr ? "tissue category" : "tissue";

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
          HPA&apos;s nTPM). Bars are colored by organ-system
          category (tissues by their own UBERON walk, cell types by
          their dominant tissue&apos;s category). Click any tissue
          to filter the cell-type chart to that tissue; the
          selected tissue bar turns maroon to mark the click target.
          {" "}
          <InfoTip label="How to read these charts">
            <strong>Tissues</strong> — every UBERON tissue with
            detectable signal (n_total ≥ 1k), pooled across every
            cell type sampled from that tissue. Bars are colored by
            organ-system category from a UBERON ontology walk (CNS
            lavender, head/sensory deep lavender, respiratory teal,
            cardiovascular amber, lymphoid bright amber, digestive
            light teal, hepatobiliary dark amber, urinary deep teal,
            endocrine olive, reproductive lavender-bright,
            skin/adipose warm brown, developmental light amber,
            fluids/other muted) so the reader can scan by anatomy.
            13 anchor tissues — brain, eye, lung, heart, blood,
            liver, intestine, kidney, adrenal gland, testis, ovary,
            skin, embryo — always appear (at low opacity if the gene
            has no signal there) so &ldquo;is this gene in
            liver?&rdquo; is one glance away. Capped at 50 tissues
            per gene; anchors always make the cut. Click a bar to
            filter the cell-type chart.{" "}
            <strong>Top 20 cell types / Cell types in {"{tissue}"}</strong>{" "}
            — one chart, two modes. Bars are colored by each cell
            type&apos;s DOMINANT tissue&apos;s organ-system category
            in the unfiltered Top 20 view (so the reader sees the
            organ-system mix at a glance); in the tissue-filtered
            view every bar gets the selected tissue&apos;s category
            color and stats are re-keyed to the cell type&apos;s
            row inside that tissue. A &ldquo;Show top 20
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
            caveat in their hover popover. No-signal anchor tissues
            render at the bottom of the Tissues chart with reduced
            opacity (not clickable since the gene has zero
            expression there). Hover any bar for full label +
            per-tissue detail; popovers near the viewport edge auto-
            shift inward to stay readable.
          </InfoTip>
        </>
      }
    >
      {(cellEnr || tissueOrganEnr || tissueCatEnr || tissueEnr) && (
        <div className={styles.chipRow}>
          {cellEnr && (
            <EnrichmentChip
              axis={cellAxisLabel}
              klass={cellEnr.class}
              foldChange={cellEnr.fold_change}
              entityNames={cellEnr.ids
                .map((id) => clToName.get(id) ?? id)
                .slice(0, 3)}
              tau={cellEnr.tau}
              topContribs={cellEnr.contribs ?? undefined}
            />
          )}
          {tissueOrganEnr ? (
            <EnrichmentChip
              axis={tissueAxisLabel}
              klass={tissueOrganEnr.class}
              foldChange={tissueOrganEnr.fold_change}
              entityNames={(tissueOrganEnr.organ_labels ?? []).slice(0, 3)}
              tau={tissueOrganEnr.tau}
              topContribs={tissueOrganEnr.top_entity_contribs ?? undefined}
            />
          ) : tissueCatEnr ? (
            <EnrichmentChip
              axis={tissueAxisLabel}
              klass={tissueCatEnr.class}
              foldChange={tissueCatEnr.fold_change}
              entityNames={(tissueCatEnr.category_labels ?? []).slice(0, 3)}
              tau={tissueCatEnr.tau}
              topContribs={tissueCatEnr.top_entity_contribs ?? undefined}
            />
          ) : (
            tissueEnr && (
              <EnrichmentChip
                axis="tissue"
                klass={tissueEnr.class}
                foldChange={tissueEnr.fold_change}
                entityNames={tissueEnr.tissue_labels.slice(0, 3)}
                tau={tissueEnr.tau}
                topContribs={tissueEnr.top_entity_contribs ?? undefined}
              />
            )
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
