import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { SectionTabs } from "../../components/SectionTabs/SectionTabs";
import { FeedbackModal } from "../../components/FeedbackModal/FeedbackModal";
import { Reveal } from "../../components/Reveal/Reveal";
import { Shell } from "../../components/Shell/Shell";
import { AccessibilityRisksCard } from "../../components/surfaceome/AccessibilityRisksCard/AccessibilityRisksCard";
import { BiologicalContextCard } from "../../components/surfaceome/BiologicalContextCard/BiologicalContextCard";
import { CommunityNotesCard } from "../../components/surfaceome/CommunityNotesCard/CommunityNotesCard";
import { DataSourcesFooter } from "../../components/surfaceome/DataSourcesFooter/DataSourcesFooter";
import { EvidenceClickDelegator } from "../../components/surfaceome/EvidenceClickDelegator/EvidenceClickDelegator";
import { EvidenceDrawer } from "../../components/surfaceome/EvidenceDrawer/EvidenceDrawer";
import { EvidenceLedgerCard } from "../../components/surfaceome/EvidenceLedgerCard/EvidenceLedgerCard";
import { ExpressionCard } from "../../components/surfaceome/ExpressionCard/ExpressionCard";
import { FEATURE_TAB_LABEL } from "../../components/surfaceome/FeatureChips/FeatureChips";
import { FiltersCard } from "../../components/surfaceome/FiltersCard/FiltersCard";
import { GeneHeader } from "../../components/surfaceome/GeneHeader/GeneHeader";
import { GeneJump } from "../../components/surfaceome/GeneJump/GeneJump";
// IsoformsCard now subsumes the old standalone OrthologsCard +
// ParalogsCard — three section tabs collapsed to one ("Isoforms ·
// orthologs · paralogs").
import { IsoformsCard } from "../../components/surfaceome/IsoformsCard/IsoformsCard";
import { SurfaceBindCard } from "../../components/surfaceome/SurfaceBindCard/SurfaceBindCard";
import { SurfaceEvidenceCard } from "../../components/surfaceome/SurfaceEvidenceCard/SurfaceEvidenceCard";
import {
  listSurfaceomeGenes,
  loadCatalogRow,
  loadGeneName,
  loadSurfaceomeRecord,
} from "../../lib/surfaceome";
import {
  loadStructureViewerData,
  structureViewerDataFromRecord,
} from "../../lib/structure-viewer";
import styles from "./page.module.css";

interface PageProps {
  params: Promise<{ symbol: string }>;
}

export async function generateStaticParams() {
  const genes = await listSurfaceomeGenes();
  // `output: export` requires a dynamic route to enumerate at least one
  // param at build time. In the offline stub build (SURFACEOME_API_BASE=
  // local) the Worker-backed gene list is empty, so emit a single sentinel
  // route to keep the exporter happy; GenePage renders its not-found
  // boundary for it. Production builds hit the live Worker, get a non-empty
  // list, and never take this branch.
  if (genes.length === 0) return [{ symbol: "__offline_stub__" }];
  return genes.map((symbol) => ({ symbol }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { symbol } = await params;
  const rec = await loadSurfaceomeRecord(symbol);
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
  const rec = await loadSurfaceomeRecord(symbol);
  if (!rec) notFound();
  // Descriptive protein name: prefer the D1 record's name
  // (surface_bind.protein_name — the UniProt name), which is only
  // populated for SURFACE-Bind proteins, falling back to the local NCBI
  // name map for the rest. Synonyms always come from the local map (the
  // record carries no synonym list).
  const localName = loadGeneName(rec.gene.hgnc_symbol);
  const d1ProteinName = rec.deterministic_features.surface_bind.protein_name;
  const geneName = d1ProteinName
    ? { name: d1ProteinName, synonyms: localName?.synonyms ?? [] }
    : localName;
  // Structure-viewer data: prefer the committed static file when present
  // — it bakes the AFDB model version + URL resolved at build time (now
  // v6 for EGFR etc.), so the canonical view loads the latest model
  // directly instead of relying on a render-time prediction-API call
  // that falls back to a stale v4 URL on any hiccup. Genes outside the
  // static topology-sweep cohort (CD81, HSPA5) fall back to deriving
  // from the deep-dive record's DeepTMHMM topology (which comes from D1);
  // there `pdb_url` is null so the client resolves the latest via the
  // AFDB prediction API.
  const structureData =
    loadStructureViewerData(rec.gene.uniprot_acc) ??
    structureViewerDataFromRecord(
      rec.gene.uniprot_acc,
      rec.deterministic_features.canonical_topology,
    );
  // 5-DB presence vector (UniProt / GO / SURFY / CSPA / HPA) from the
  // candidate-universe build — the same vote pattern shown as dots on
  // the catalog (/) and SurfaceBench (/benchmark) rows. Catalog load
  // is memoized so this is O(1) once the first gene page has been
  // rendered in the build. `null` for resolver-failure outliers; the
  // card is omitted in that case rather than rendered with a stub.
  const catalogRow = await loadCatalogRow(rec.gene.hgnc_symbol);

  // Deep-dive gene symbols for the toolbar's <GeneJump> typeahead — the
  // SAME set generateStaticParams emits, so every suggestion resolves to a
  // real statically-generated page (a non-deep-dive symbol would 404 under
  // output: export). Memoized in listSurfaceomeGenes, so this is one Worker
  // call per build, not per page.
  const deepDiveGenes = await listSurfaceomeGenes();

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
    // Biology / Expression / Risks each map 1:1 to an LLM feature-chip
    // category. The tab `label`s pull from the SAME `FEATURE_TAB_LABEL`
    // map the cards' <FeatureChips> rows use, so a rename can't drift
    // the tab title out of sync with the chip-row aria-label (the
    // compile-time half of the tab↔chip "connection"; the runtime half
    // is asserted by viewer/tests/verify_feature_tabs.py via the
    // data-section-id / data-feature-chips attributes).
    {
      kind: "biology",
      label: FEATURE_TAB_LABEL.biology,
      render: (n) => <BiologicalContextCard rec={rec} n={n} />,
    },
    {
      kind: "expression",
      label: FEATURE_TAB_LABEL.expression,
      render: (n) => <ExpressionCard rec={rec} n={n} />,
    },
    // Risks promoted above the evolutionary-context group per user
    // feedback — accessibility risks are higher-priority reading than
    // the isoform / ortholog / paralog comparison that follows it.
    {
      kind: "risks",
      label: FEATURE_TAB_LABEL.risks,
      render: (n) => <AccessibilityRisksCard rec={rec} n={n} />,
    },
    // SURFACE-Bind section only when the protein has at least one
    // scored patch. Two empty cases are filtered out so the AnchorNav
    // strip never offers a tab that opens a sites-less section:
    //   * not in SURFACE-Bind's table (`has_data=false`), and
    //   * scored but no patch cleared the MaSIF threshold
    //     (`n_sites=0`, e.g. CLDN18).
    // Both absence signals are still surfaced — as the "not in" /
    // "scored · no patches" pill states in the §01 "Candidate sites"
    // group — so dropping the section here loses no information.
    ...(rec.deterministic_features.surface_bind.has_data &&
    rec.deterministic_features.surface_bind.n_sites > 0
      ? [
          {
            kind: "surface-bind",
            label: "SURFACE-Bind",
            render: (n: number) => <SurfaceBindCard rec={rec} n={n} />,
          },
        ]
      : []),
    // Evolutionary context — isoforms + orthologs + paralogs combined
    // into one section per user feedback. The previous three-tab split
    // each had its own AnchorNav entry so empty subsections stayed
    // visible to readers; the combined card has subheads inside so
    // emptiness is still visible (e.g. "No paralogs in Compara." renders
    // under its own subhead) but the tab strip is three slots shorter.
    {
      kind: "isoforms",
      label: "Isoforms · orthologs · paralogs",
      render: (n) => <IsoformsCard rec={rec} n={n} />,
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
          {/* Jump to another gene's deep dive without going back to the
              catalog table. Suggestions are the deep-dive set only. */}
          <GeneJump genes={deepDiveGenes} current={rec.gene.hgnc_symbol} />
          <span className={styles.crumbActions}>
            <a
              className={styles.crumbAction}
              data-hint="Canonical record, served live from the public Worker (D1). Everything on this page is rendered from it."
              href={`https://api.deliverome.org/surfaceome/v1/genes/${rec.gene.hgnc_symbol}`}
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
          <GeneHeader
            rec={rec}
            geneName={geneName}
            structureData={structureData}
            catalogRow={catalogRow}
          />
        </Reveal>

        {/* Confidence + reasoning moved INTO the GeneHeader's
         *  Confidence vital cell (drawer right below the value)
         *  — the second below-the-fold copy here was redundant. */}

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
              {/* No <Reveal> wrapper here. Inactive tab panels are
               *  `display:none` (see SectionTabs), and an
               *  IntersectionObserver never fires for a display:none
               *  element — so a Reveal-wrapped panel stayed stranded at
               *  `opacity:0` when its tab was selected (the content was
               *  in the DOM but invisible: "evidence/ledger not
               *  rendering / impossibly slow to view"). Tab panels are
               *  swapped, not scrolled into view, so the scroll-fade was
               *  the wrong primitive — render the section directly at
               *  full opacity. The GeneHeader above keeps its <Reveal>:
               *  it's always in-flow + above the fold, so its observer
               *  fires on mount. */}
              {s.render(i + 1)}
            </section>
          ))}
        </SectionTabs>

        <DataSourcesFooter rec={rec} />
      </article>

      {/* Global EvidenceDrawer — listens for the `surfaceome:open-evidence`
       *  CustomEvent. Dispatched by the page-level
       *  <EvidenceClickDelegator> when any [data-evidence-id]
       *  element gets clicked anywhere in the document. Lets every
       *  <EvidenceChip> stay a pure server component (no `"use
       *  client"`, no per-chip handler) — the page renders 100+
       *  chips with a single hydration boundary. Renders one drawer
       *  for the whole page so it persists across section scrolls
       *  and chip clicks. */}
      <EvidenceClickDelegator />
      <EvidenceDrawer evidence={rec.evidence} />
      <FeedbackModal />
    </Shell>
  );
}
