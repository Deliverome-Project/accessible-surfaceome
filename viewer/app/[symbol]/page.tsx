import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Reveal } from "../../components/Reveal/Reveal";
import { Shell } from "../../components/Shell/Shell";
import { AccessibilityRisksCard } from "../../components/surfaceome/AccessibilityRisksCard/AccessibilityRisksCard";
import { BiologicalContextCard } from "../../components/surfaceome/BiologicalContextCard/BiologicalContextCard";
import { DatabasePresenceCard } from "../../components/surfaceome/DatabasePresenceCard/DatabasePresenceCard";
import { DataSourcesFooter } from "../../components/surfaceome/DataSourcesFooter/DataSourcesFooter";
import { EvidenceDrawer } from "../../components/surfaceome/EvidenceDrawer/EvidenceDrawer";
import { EvidenceLedgerCard } from "../../components/surfaceome/EvidenceLedgerCard/EvidenceLedgerCard";
import { ExecutiveSummaryCard } from "../../components/surfaceome/ExecutiveSummaryCard/ExecutiveSummaryCard";
import { FiltersCard } from "../../components/surfaceome/FiltersCard/FiltersCard";
import { GeneHeader } from "../../components/surfaceome/GeneHeader/GeneHeader";
import { IsoformsCard } from "../../components/surfaceome/IsoformsCard/IsoformsCard";
import { OrthologsCard } from "../../components/surfaceome/OrthologsCard/OrthologsCard";
import { ParalogsCard } from "../../components/surfaceome/ParalogsCard/ParalogsCard";
import { SurfaceEvidenceCard } from "../../components/surfaceome/SurfaceEvidenceCard/SurfaceEvidenceCard";
import {
  listSurfaceomeGenes,
  loadCatalogRow,
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
  // 5-DB presence vector (UniProt / GO / SURFY / CSPA / HPA) from the
  // candidate-universe build — the same vote pattern shown as dots on
  // the catalog (/) and SurfaceBench (/benchmark) rows. Catalog load
  // is memoized so this is O(1) once the first gene page has been
  // rendered in the build. `null` for resolver-failure outliers; the
  // card is omitted in that case rather than rendered with a stub.
  const catalogRow = await loadCatalogRow(rec.gene.hgnc_symbol);

  // v1.0.0 section order mirrors the EGFR mockup in
  // docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md.
  // The 3D structure viewer + AFDB pLDDT / disordered-fraction stats
  // were promoted to the `<GeneHeader>` sidekick so the reader sees
  // structure confidence next to the model itself. Attribution +
  // license stay in the `<DataSourcesFooter>` at the bottom. The
  // standalone StructureSummaryCard was removed (it duplicated both
  // the stats now in the header and the attribution now in the
  // footer).
  const sections: { kind: string; render: (n: number) => React.ReactNode }[] = [
    { kind: "executive", render: (n) => <ExecutiveSummaryCard rec={rec} n={n} /> },
    ...(catalogRow
      ? [
          {
            kind: "db-presence",
            render: (n: number) => (
              <DatabasePresenceCard row={catalogRow} n={n} />
            ),
          },
        ]
      : []),
    { kind: "filters", render: (n) => <FiltersCard rec={rec} n={n} /> },
    { kind: "evidence", render: (n) => <SurfaceEvidenceCard rec={rec} n={n} /> },
    { kind: "biology", render: (n) => <BiologicalContextCard rec={rec} n={n} /> },
    { kind: "isoforms", render: (n) => <IsoformsCard rec={rec} n={n} /> },
    { kind: "paralogs", render: (n) => <ParalogsCard rec={rec} n={n} /> },
    { kind: "orthologs", render: (n) => <OrthologsCard rec={rec} n={n} /> },
    { kind: "risks", render: (n) => <AccessibilityRisksCard rec={rec} n={n} /> },
    { kind: "ledger", render: (n) => <EvidenceLedgerCard rec={rec} n={n} /> },
  ];

  return (
    <Shell>
      <article className={`${styles.page} page-width`}>
        {/* Warm the AFDB TLS handshake so the StructureViewer's PDB
            fetch starts as fast as possible once 3dmol mounts. React
            19 hoists <link> into <head> automatically; no need for a
            separate generateMetadata hop. Only rendered when this
            gene actually has a structure to load. */}
        {structureData ? (
          <link
            rel="preconnect"
            href="https://alphafold.ebi.ac.uk"
            crossOrigin="anonymous"
          />
        ) : null}

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
              data-hint="Canonical record. Everything on this page is rendered from it."
              href={`/data/surfaceome/${rec.gene.hgnc_symbol}.json`}
              target="_blank"
              rel="noopener noreferrer"
            >
              JSON ↗
            </a>
            <a
              className={styles.crumbAction}
              data-hint="Markdown export of the same record + the full UniProt canonical sequence + per-residue DeepTMHMM topology for canonical and every alternative isoform + a link to the live AlphaFold DB entry."
              href={`/data/surfaceome/${rec.gene.hgnc_symbol}.md`}
              target="_blank"
              rel="noopener noreferrer"
            >
              Markdown (full) ↗
            </a>
          </span>
        </nav>

        <Reveal>
          <GeneHeader rec={rec} geneName={geneName} structureData={structureData} />
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
            Confidence ·{" "}
            {typeof rec.confidence === "number"
              ? rec.confidence.toFixed(2)
              : String(rec.confidence ?? "—")}
          </p>
          <p className={styles.confidenceLine}>{rec.confidence_reasoning}</p>
        </Reveal>

        <DataSourcesFooter rec={rec} />
      </article>

      {/* Global EvidenceDrawer — listens for the `surfaceome:open-evidence`
       *  CustomEvent dispatched by any <EvidenceChip> in the tree
       *  (executive-summary cited_evidence_ids, per-method chips,
       *  per-tissue chips, the EvidenceLedger items themselves). Renders
       *  one drawer for the whole page so it persists across section
       *  scrolls and chip clicks. */}
      <EvidenceDrawer evidence={rec.evidence} />
    </Shell>
  );
}
