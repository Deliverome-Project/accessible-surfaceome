"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { SectionTabs } from "../../SectionTabs/SectionTabs";
import { FeedbackModal } from "../../FeedbackModal/FeedbackModal";
import { Reveal } from "../../Reveal/Reveal";
import { Shell } from "../../Shell/Shell";
import { AccessibilityRisksCard } from "../AccessibilityRisksCard/AccessibilityRisksCard";
import { BenchmarkRow } from "../BenchmarkRow/BenchmarkRow";
import { BiologicalContextCard } from "../BiologicalContextCard/BiologicalContextCard";
import { CommunityNotesCard } from "../CommunityNotesCard/CommunityNotesCard";
import { DataSourcesFooter } from "../DataSourcesFooter/DataSourcesFooter";
import { EvidenceClickDelegator } from "../EvidenceClickDelegator/EvidenceClickDelegator";
import { EvidenceDrawer } from "../EvidenceDrawer/EvidenceDrawer";
import { EvidenceLedgerCard } from "../EvidenceLedgerCard/EvidenceLedgerCard";
import { ExpressionCard } from "../ExpressionCard/ExpressionCard";
import { FEATURE_TAB_LABEL } from "../FeatureChips/FeatureChips";
import { FiltersCard } from "../FiltersCard/FiltersCard";
import { GeneHeader } from "../GeneHeader/GeneHeader";
import { GeneJump } from "../GeneJump/GeneJump";
// IsoformsCard now subsumes the old standalone OrthologsCard +
// ParalogsCard — three section tabs collapsed to one ("Isoforms ·
// orthologs · paralogs").
import { IsoformsCard } from "../IsoformsCard/IsoformsCard";
import { SurfaceBindCard } from "../SurfaceBindCard/SurfaceBindCard";
import { SurfaceEvidenceCard } from "../SurfaceEvidenceCard/SurfaceEvidenceCard";
import { TriageRow } from "../TriageRow/TriageRow";
import type { CatalogRow, GeneEntry } from "../../../lib/surfaceome";
import type {
  BenchmarkRow as BenchmarkRowPayload,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import type {
  SchwekeHomomerLoaderRow,
  StructureViewerData,
} from "../../../lib/structure-viewer-types";
import type { TriageHeadlinePayload } from "../../../lib/triage-headline";
import styles from "./GeneDetail.module.css";

interface GeneDetailProps {
  /** The full SurfaceomeRecord — the only hard requirement, fetched by the
   *  client shell from the Worker before this renders. */
  rec: SurfaceomeRecord;
  /** Descriptive protein name + synonyms. On the client shell this comes
   *  from the record's `deterministic_features.surface_bind.protein_name`
   *  (the build-time NCBI/HGNC gene-name TSV is not client-safe), so
   *  `synonyms` is typically empty and the name is null for non-SURFACE-
   *  Bind proteins. */
  geneName: { name: string; synonyms: string[] } | null;
  /** DeepTMHMM topology + AFDB metadata for the canonical UniProt, derived
   *  from the record (`structureViewerDataFromRecord`). Null when the
   *  record carries no accession. */
  structureData: StructureViewerData | null;
  /** Schweke et al. 2024 AF2 homo-oligomer entry, derived from the record's
   *  `deterministic_features.homo_oligomerization`. Null when the protein
   *  isn't a Schweke positive. */
  schwekeHomomer: SchwekeHomomerLoaderRow | null;
  /** 5-DB surface-vote vector. Null on the client shell (the genome-wide
   *  catalog is too large to refetch per gene view), so the inline DB
   *  presence strip is omitted — same graceful path as a resolver-failure
   *  outlier. */
  catalogRow: CatalogRow | null;
  /** Curated SurfaceBench ground-truth row for the ~147 benchmark genes;
   *  null for everything else. */
  benchmarkRow: BenchmarkRowPayload | null;
  /** Latest most-positive triage call (from `/v1/triage/{symbol}`), or null
   *  on a fetch miss — GeneHeader / TriageRow then fall back to
   *  `rec.triage_signal`. */
  triageHeadline: TriageHeadlinePayload | null;
  /** Deep-dive genes for the toolbar's GeneJump typeahead. */
  deepDiveGenes: readonly GeneEntry[];
}

/**
 * GeneDetail — the per-gene deep-dive page composition, extracted from the
 * old server component at `app/[symbol]/page.tsx` into a client component.
 * It renders the same layout the page always rendered; the data (record +
 * derived extras) is now loaded in the browser by the `app/gene` client
 * shell and passed in as props, so the deploy no longer materializes one
 * static file per gene.
 */
export function GeneDetail({
  rec,
  geneName,
  structureData,
  schwekeHomomer,
  catalogRow,
  benchmarkRow,
  triageHeadline,
  deepDiveGenes,
}: GeneDetailProps) {
  // v1.0.0 section order mirrors the EGFR mockup in
  // docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md.
  // The 3D structure viewer + AFDB pLDDT / disordered-fraction stats
  // were promoted to the `<GeneHeader>` sidekick so the reader sees
  // structure confidence next to the model itself. Attribution +
  // license stay in the `<DataSourcesFooter>` at the bottom.
  // Each entry carries a stable `kind` (used as the `section-<kind>`
  // anchor id) and a reader-facing `label` (shown in the AnchorNav
  // strip). The label is short by design — the strip has to fit ~10
  // links horizontally without wrapping on a 1280-wide canvas.
  const sections: {
    kind: string;
    label: string;
    render: (n: number) => ReactNode;
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
    // the tab title out of sync with the chip-row aria-label.
    {
      // Tab label intentionally diverges from `FEATURE_TAB_LABEL.biology`
      // ("Biology") — this §03 tab covers the biology chips AND the
      // accessibility-context block, so the tab reads "Biology &
      // accessibility". The `kind`/`data-section-id` stays "biology" so
      // the anchor + verify_feature_tabs.py runtime check are unaffected.
      kind: "biology",
      label: "Biology & accessibility",
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
    // into one section per user feedback. The combined card has subheads
    // inside so emptiness is still visible but the tab strip is three
    // slots shorter.
    {
      kind: "isoforms",
      label: "Isoforms & homologs",
      render: (n) => <IsoformsCard rec={rec} n={n} />,
    },
    {
      kind: "ledger",
      label: "Evidence",
      render: (n) => <EvidenceLedgerCard rec={rec} n={n} />,
    },
    {
      kind: "community",
      label: "Community notes",
      render: (n) => (
        <CommunityNotesCard gene={rec.gene.hgnc_symbol} uniprotAcc={rec.gene.uniprot_acc} n={n} />
      ),
    },
  ];
  const anchorSections = sections.map((s) => ({ id: s.kind, label: s.label }));

  return (
    <Shell>
      <article className={`${styles.page} page-width`}>
        {/* Warm the AFDB TLS handshake so the StructureViewer's PDB
            fetch starts as fast as possible once 3dmol mounts. React
            19 hoists <link> into <head> automatically. Only rendered
            when this gene actually has a structure to load. */}
        {structureData ? (
          <link
            rel="preconnect"
            href="https://alphafold.ebi.ac.uk"
            crossOrigin="anonymous"
          />
        ) : null}

        {/* Compact toolbar — a small ← icon link is the back-to-catalog
            affordance. The JSON / Markdown / Feedback actions stay on
            the right. */}
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
              data-hint="The complete machine-readable record for this gene (JSON) — the live, canonical data everything on this page is rendered from."
              href={`https://api.deliverome.org/surfaceome/v1/genes/${rec.gene.hgnc_symbol}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              JSON ↗
            </a>
            <a
              className={styles.crumbAction}
              data-hint="Full Markdown export — the complete record plus reanalysis extras not in the JSON: canonical, isoform & cross-species ortholog sequences, per-residue membrane topology (DeepTMHMM), and AlphaFold model download links. Served from R2 via the Worker."
              href={`https://api.deliverome.org/surfaceome/v1/genes/${rec.gene.hgnc_symbol}.md`}
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
            schwekeHomomer={schwekeHomomer}
            catalogRow={catalogRow}
            triageHeadline={triageHeadline}
          />
        </Reveal>

        {/* Tab-style section display. AnchorNav renders inside
            `<SectionTabs>` and drives which section is shown; only
            one section is visible at a time so clicking a tab swaps
            the body in place without scrolling. */}
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
               *  `opacity:0` when its tab was selected. Render the
               *  section directly at full opacity. */}
              {s.render(i + 1)}
            </section>
          ))}
        </SectionTabs>

        {/* Reference-point strips — moved out of the GeneHeader so the
            top of the page stays anchored on the deep-dive Surface
            likelihood hero. Order: Benchmark (curated ground truth,
            when available for the ~147 benchmark genes) above Triage
            (Sonnet first-pass). Both sit just above the
            DataSourcesFooter. */}
        {benchmarkRow ? (
          <BenchmarkRow rec={rec} benchmarkRow={benchmarkRow} />
        ) : null}
        <TriageRow rec={rec} triageHeadline={triageHeadline} />

        <DataSourcesFooter rec={rec} />
      </article>

      {/* Global EvidenceDrawer — listens for the `surfaceome:open-evidence`
       *  CustomEvent dispatched by the page-level <EvidenceClickDelegator>
       *  when any [data-evidence-id] element is clicked. Lets every
       *  <EvidenceChip> stay a pure presentational component (no per-chip
       *  handler) — one drawer for the whole page. */}
      <EvidenceClickDelegator />
      <EvidenceDrawer evidence={rec.evidence} />
      <FeedbackModal />
    </Shell>
  );
}
