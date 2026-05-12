import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Reveal } from "../../components/Reveal/Reveal";
import { Shell } from "../../components/Shell/Shell";
import { GeneHeader } from "../../components/surfaceome/GeneHeader/GeneHeader";
import { SurfaceBiologyCard } from "../../components/surfaceome/SurfaceBiologyCard/SurfaceBiologyCard";
import { DeepDiveCard } from "../../components/surfaceome/DeepDiveCard/DeepDiveCard";
import { ExpressionCard } from "../../components/surfaceome/ExpressionCard/ExpressionCard";
import { LandscapeCard } from "../../components/surfaceome/LandscapeCard/LandscapeCard";
import { RiskFlagsCard } from "../../components/surfaceome/RiskFlagsCard/RiskFlagsCard";
import {
  listSurfaceomeGenes,
  loadGeneName,
  loadSurfaceomeRecord,
  prettyEnum,
} from "../../lib/surfaceome";
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
    description: rec.targetability.tldr,
  };
}

export default async function GenePage({ params }: PageProps) {
  const { symbol } = await params;
  const rec = loadSurfaceomeRecord(symbol);
  if (!rec) notFound();
  const geneName = loadGeneName(rec.gene.hgnc_symbol);

  // Walk visible sections so the section numbers stay sequential even
  // when a record omits a bucket (v0.4.0 records have no `expression`;
  // some genes have no deep-dive entries).
  const sections: { kind: string; render: (n: number) => React.ReactNode }[] = [];
  sections.push({
    kind: "surface",
    render: (n) => <SurfaceBiologyCard rec={rec} n={n} />,
  });
  if (
    (rec.isoform_accessibility?.length ?? 0) +
      (rec.coreceptor_requirements?.length ?? 0) +
      (rec.orthology?.length ?? 0) >
    0
  ) {
    sections.push({
      kind: "deepdive",
      render: (n) => <DeepDiveCard rec={rec} n={n} />,
    });
  }
  if (rec.protein_features || rec.expression) {
    sections.push({
      kind: "expression",
      render: (n) => <ExpressionCard rec={rec} n={n} />,
    });
  }
  if (
    (rec.surface_engagement_validation?.preclinical_evidence?.length ?? 0) +
      (rec.therapeutic_landscape?.patent_disclosures?.length ?? 0) +
      (rec.therapeutic_landscape?.preclinical_evidence?.length ?? 0) >
    0
  ) {
    sections.push({
      kind: "landscape",
      render: (n) => <LandscapeCard rec={rec} n={n} />,
    });
  }
  if (rec.risk_flags.length > 0) {
    sections.push({
      kind: "risks",
      render: (n) => <RiskFlagsCard rec={rec} n={n} />,
    });
  }

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
            >
              JSON ↗
            </a>
          </span>
        </nav>

        <details className={styles.rawDetails}>
          <summary className={styles.rawSummary}>
            Raw deep-dive record
            <span className={styles.rawSummaryHint}>
              · {rec.schema_version} · {rec.evidence_count} evidence
            </span>
          </summary>
          <pre className={styles.rawJson}>{JSON.stringify(rec, null, 2)}</pre>
        </details>

        <Reveal>
          <GeneHeader rec={rec} geneName={geneName} />
        </Reveal>

        <Reveal as="div" stagger stagger_ms={140}>
          {sections.map((s, i) => (
            <div key={s.kind}>{s.render(i + 1)}</div>
          ))}
        </Reveal>

        <Reveal className={styles.confidence}>
          <p className={`label-mono ${styles.confidenceEyebrow}`}>Confidence</p>
          <p className={styles.confidenceLine}>
            <strong>{prettyEnum(rec.confidence)}</strong> — {rec.confidence_reasoning}
          </p>
        </Reveal>
      </article>
    </Shell>
  );
}
