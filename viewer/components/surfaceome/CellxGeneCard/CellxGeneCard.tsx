import type { CellxGeneEnrichment } from "../../../lib/cellxgene-enrichment";
import { CITATIONS, pubmedUrl } from "../../../lib/citations";
import { InfoTip } from "../../InfoTip/InfoTip";
import { SectionCard } from "../SectionCard/SectionCard";
import { CellxGeneChart } from "./CellxGeneChart";
import styles from "./CellxGeneCard.module.css";

interface Props {
  data: CellxGeneEnrichment | null;
  n: number;
}

/**
 * CellxGene tab — CZI gene-expression enrichment, presented as an
 * interactive HPA-style barplot. The chart itself is a client component
 * (Y-axis + sort are reactive); this wrapper stays a server component
 * so the SectionCard chrome + citation tag render with the rest of the
 * page at build time.
 *
 * "Easy to take in at a glance" — categories (Epithelial / Immune /
 * Neural / Endothelial / Stromal / Muscle / Reproductive / Stem /
 * Tumor / Other) get distinct colors from the deliverome palette; the
 * reader can flip the Y-axis between mean log1p(CP10K) and percent
 * expressing, or re-sort by value / category / alphabetical without
 * leaving the page.
 *
 * The previous version had a curated "delivery target" block driven by
 * `tissue_mappings.json`. That mapping is upstream-of-record drift, so
 * the v2 schema dropped it — every reader can now read the same shape
 * regardless of which delivery targets are in vogue.
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
            cohort — fraction of that cell type that detectably
            expresses the gene. Tissues shown under each cell type are
            the top 3 anatomical contexts that cell type was sampled
            from, ranked by expressing-cell count.
          </InfoTip>
        </>
      }
    >
      <CellxGeneChart rows={data.top_cell_types} />
    </SectionCard>
  );
}
