import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Reveal } from "../../components/Reveal/Reveal";
import { Shell } from "../../components/Shell/Shell";
import { AccessibilityRisksCard } from "../../components/surfaceome/AccessibilityRisksCard/AccessibilityRisksCard";
import { BiologicalContextCard } from "../../components/surfaceome/BiologicalContextCard/BiologicalContextCard";
import { DataSourcesFooter } from "../../components/surfaceome/DataSourcesFooter/DataSourcesFooter";
import { EvidenceLedgerCard } from "../../components/surfaceome/EvidenceLedgerCard/EvidenceLedgerCard";
import { ExecutiveSummaryCard } from "../../components/surfaceome/ExecutiveSummaryCard/ExecutiveSummaryCard";
import { FiltersCard } from "../../components/surfaceome/FiltersCard/FiltersCard";
import { GeneHeader } from "../../components/surfaceome/GeneHeader/GeneHeader";
import { IsoformsCard } from "../../components/surfaceome/IsoformsCard/IsoformsCard";
import { OrthologsCard } from "../../components/surfaceome/OrthologsCard/OrthologsCard";
import { ParalogsCard } from "../../components/surfaceome/ParalogsCard/ParalogsCard";
import { StructureSummaryCard } from "../../components/surfaceome/StructureSummaryCard/StructureSummaryCard";
import { SurfaceEvidenceCard } from "../../components/surfaceome/SurfaceEvidenceCard/SurfaceEvidenceCard";
import { StructureViewerCard } from "../../components/surfaceome/StructureViewerCard/StructureViewerCard";
import {
  listSurfaceomeGenes,
  loadGeneName,
  loadSurfaceomeRecord,
} from "../../lib/surfaceome";
import { loadStructureViewerData } from "../../lib/structure-viewer";
import styles from "./page.module.css";

interface PageProps {
  params: Promise<{ symbol: string }>;
}

export function generateStaticParams() {
  return listSurfaceomeGenes().map((symbol) => ({ symbol }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { symbol } = await params;
  const rec = loadSurfaceomeRecord(symbol);
  if (!rec) {
    return {
      title: `${symbol} — record not found`,
      robots: { index: false, follow: false },
    };
  }
  return {
    title: `${symbol} — Surfaceome record`,
    description: rec.executive_summary.one_paragraph.slice(0, 160),
  };
}

export default async function GenePage({ params }: PageProps) {
  const { symbol } = await params;
  const rec = loadSurfaceomeRecord(symbol);
  if (!rec) notFound();
  const geneName = loadGeneName(rec.gene.hgnc_symbol);
  const structureData = loadStructureViewerData(rec.gene.uniprot_acc);

  // v1.0.0 section order mirrors the EGFR mockup in
  // docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md.
  // All sections are required by schema, so the array is fixed-length
  // except for StructureViewerCard, which is skipped for soluble
  // proteins (DeepTMHMM has no topology).
  const sections: { kind: string; render: (n: number) => React.ReactNode }[] = [
    { kind: "executive", render: (n) => <ExecutiveSummaryCard rec={rec} n={n} /> },
    { kind: "filters", render: (n) => <FiltersCard rec={rec} n={n} /> },
    { kind: "evidence", render: (n) => <SurfaceEvidenceCard rec={rec} n={n} /> },
    { kind: "biology", render: (n) => <BiologicalContextCard rec={rec} n={n} /> },
    { kind: "isoforms", render: (n) => <IsoformsCard rec={rec} n={n} /> },
    { kind: "paralogs", render: (n) => <ParalogsCard rec={rec} n={n} /> },
    { kind: "orthologs", render: (n) => <OrthologsCard rec={rec} n={n} /> },
    { kind: "risks", render: (n) => <AccessibilityRisksCard rec={rec} n={n} /> },
  ];
  if (structureData) {
    sections.push({
      kind: "structure",
      render: (n) => (
        <StructureViewerCard
          data={structureData}
          geneSymbol={rec.gene.hgnc_symbol}
          n={n}
        />
      ),
    });
  }
  sections.push({
    kind: "structure-summary",
    render: (n) => <StructureSummaryCard rec={rec} n={n} />,
  });
  sections.push({
    kind: "ledger",
    render: (n) => <EvidenceLedgerCard rec={rec} n={n} />,
  });

  return (
    <Shell>
      <article className={`${styles.page} page-width`}>
        <nav className={styles.crumbs} aria-label="Breadcrumb">
          <Link href="/" className={styles.crumbLink}>
            Surfaceome
          </Link>
          <span className={styles.crumbSep} aria-hidden="true">
            /
          </span>
          <span className={styles.crumbHere}>{rec.gene.hgnc_symbol}</span>
          <span className={styles.crumbActions}>
            <a
              className={styles.crumbAction}
              href={`/data/surfaceome/${rec.gene.hgnc_symbol}.json`}
              target="_blank"
              rel="noopener noreferrer"
              title="Canonical record. Everything on this page is rendered from it."
            >
              JSON ↗
            </a>
            <a
              className={styles.crumbAction}
              href={`/data/surfaceome/${rec.gene.hgnc_symbol}.md`}
              target="_blank"
              rel="noopener noreferrer"
              title="Markdown export of the same record + full UniProt canonical sequence + per-residue DeepTMHMM topology for canonical and every alternative isoform."
            >
              Markdown (full) ↗
            </a>
            <a
              className={styles.crumbAction}
              href={`https://alphafold.ebi.ac.uk/entry/${rec.gene.uniprot_acc}`}
              target="_blank"
              rel="noopener noreferrer"
              title="Live AlphaFold DB entry. Current model + sequence are auto-discovered from the AFDB prediction API, so this link auto-tracks AFDB version bumps."
            >
              AFDB ↗
            </a>
          </span>
        </nav>

        <Reveal>
          <GeneHeader rec={rec} geneName={geneName} />
        </Reveal>

        {/* Per-section Reveal wrappers, not a single bulk wrapper.
            A single stagger wrapper around all 12 sections is taller
            than the viewport, so an IntersectionObserver with a
            non-trivial threshold never reaches its trigger and every
            child stays at opacity 0. Per-section Reveals also keep
            the scroll-fade rhythm honest: each card fades in as it
            actually scrolls into view. */}
        {sections.map((s, i) => (
          <Reveal key={s.kind}>{s.render(i + 1)}</Reveal>
        ))}

        <Reveal className={styles.confidence}>
          <p className={`label-mono ${styles.confidenceEyebrow}`}>
            Confidence · {rec.confidence.toFixed(2)}
          </p>
          <p className={styles.confidenceLine}>{rec.confidence_reasoning}</p>
        </Reveal>

        <DataSourcesFooter rec={rec} />
      </article>
    </Shell>
  );
}
