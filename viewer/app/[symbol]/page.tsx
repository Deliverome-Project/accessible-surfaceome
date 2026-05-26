import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { SectionTabs } from "../../components/SectionTabs/SectionTabs";
import { FeedbackButton } from "../../components/FeedbackButton/FeedbackButton";
import { FeedbackModal } from "../../components/FeedbackModal/FeedbackModal";
import { Reveal } from "../../components/Reveal/Reveal";
import { Shell } from "../../components/Shell/Shell";
import { AccessibilityRisksCard } from "../../components/surfaceome/AccessibilityRisksCard/AccessibilityRisksCard";
import { BiologicalContextCard } from "../../components/surfaceome/BiologicalContextCard/BiologicalContextCard";
import { CommunityNotesCard } from "../../components/surfaceome/CommunityNotesCard/CommunityNotesCard";
import { DataSourcesFooter } from "../../components/surfaceome/DataSourcesFooter/DataSourcesFooter";
import { EvidenceDrawer } from "../../components/surfaceome/EvidenceDrawer/EvidenceDrawer";
import { EvidenceLedgerCard } from "../../components/surfaceome/EvidenceLedgerCard/EvidenceLedgerCard";
import { FiltersCard } from "../../components/surfaceome/FiltersCard/FiltersCard";
import { GeneHeader } from "../../components/surfaceome/GeneHeader/GeneHeader";
import { IsoformsCard } from "../../components/surfaceome/IsoformsCard/IsoformsCard";
import { OrthologsCard } from "../../components/surfaceome/OrthologsCard/OrthologsCard";
import { ParalogsCard } from "../../components/surfaceome/ParalogsCard/ParalogsCard";
import { SurfaceBindCard } from "../../components/surfaceome/SurfaceBindCard/SurfaceBindCard";
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
  // Each entry carries a stable `kind` (used as the `section-<kind>`
  // anchor id) and a reader-facing `label` (shown in the AnchorNav
  // strip). The label is short by design — the strip has to fit ~10
  // links horizontally without wrapping on a 1280-wide canvas.
  const sections: {
    kind: string;
    label: string;
    render: (n: number) => React.ReactNode;
  }[] = [
    // DB-membership was its own §section; promoted to an inline
    // strip in `<GeneHeader>` per user feedback. The section entry
    // is gone; nothing to surface in AnchorNav for it.
    {
      kind: "metrics",
      label: "Summary metrics",
      render: (n) => <FiltersCard rec={rec} n={n} />,
    },
    {
      kind: "evidence",
      label: "Surface evidence",
      render: (n) => <SurfaceEvidenceCard rec={rec} n={n} />,
    },
    {
      kind: "biology",
      label: "Biology",
      render: (n) => <BiologicalContextCard rec={rec} n={n} />,
    },
    {
      kind: "isoforms",
      label: "Isoforms",
      render: (n) => <IsoformsCard rec={rec} n={n} />,
    },
    {
      kind: "paralogs",
      label: "Paralogs",
      render: (n) => <ParalogsCard rec={rec} n={n} />,
    },
    {
      kind: "orthologs",
      label: "Orthologs",
      render: (n) => <OrthologsCard rec={rec} n={n} />,
    },
    // SurfaceBindCard renders ``null`` when the protein isn't in
    // SURFACE-Bind's authoritative table. Filter the section out
    // entirely in the absent case so the AnchorNav link doesn't
    // jump to an empty anchor — the absence is already signaled
    // by the "not scored" pill in the GeneHeader.
    ...(rec.deterministic_features.surface_bind.has_data
      ? [
          {
            kind: "surface-bind",
            label: "SURFACE-Bind",
            render: (n: number) => <SurfaceBindCard rec={rec} n={n} />,
          },
        ]
      : []),
    {
      kind: "risks",
      label: "Risks",
      render: (n) => <AccessibilityRisksCard rec={rec} n={n} />,
    },
    {
      kind: "ledger",
      label: "Evidence ledger",
      render: (n) => <EvidenceLedgerCard rec={rec} n={n} />,
    },
    {
      kind: "community",
      label: "Community notes",
      render: (n) => (
        <CommunityNotesCard gene={rec.gene.hgnc_symbol} n={n} />
      ),
    },
  ];
  const anchorSections = sections.map((s) => ({ id: s.kind, label: s.label }));

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

        {/* Compact toolbar — drop the "Surfaceome / EGFR" breadcrumb
            text (the gene symbol is already the page's h1 below); a
            small ← icon link is the back-to-catalog affordance. The
            JSON / Markdown / Feedback actions stay on the right.
            Pulls the gene-symbol h1 ~30 px closer to the top of the
            page. */}
        <nav className={styles.crumbs} aria-label="Page actions">
          <Link
            href="/"
            className={styles.crumbBack}
            title="Back to surfaceome catalog"
            aria-label="Back to surfaceome catalog"
          >
            ←
          </Link>
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
            <FeedbackButton gene={rec.gene.hgnc_symbol} uniprotAcc={rec.gene.uniprot_acc} />
          </span>
        </nav>

        <Reveal>
          <GeneHeader
            rec={rec}
            geneName={geneName}
            structureData={structureData}
            catalogRow={catalogRow}
          />
        </Reveal>

        {/* Tab-style section display. AnchorNav renders inside
            `<SectionTabs>` and drives which section is shown; only
            one section is visible at a time so clicking a tab swaps
            the body in place without scrolling. All sections are
            pre-rendered server-side and the CSS hides the inactive
            ones (no client re-render on tab change). */}
        <SectionTabs sections={anchorSections}>
          {sections.map((s, i) => (
            <section
              key={s.kind}
              id={`section-${s.kind}`}
              data-section-id={s.kind}
            >
              <Reveal>{s.render(i + 1)}</Reveal>
            </section>
          ))}
        </SectionTabs>

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
      <FeedbackModal />
    </Shell>
  );
}
