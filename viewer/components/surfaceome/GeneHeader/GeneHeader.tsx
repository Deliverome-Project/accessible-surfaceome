import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./GeneHeader.module.css";

interface GeneHeaderProps {
  rec: SurfaceomeRecord;
}

/**
 * GeneHeader — display-scale gene symbol, lede, identifier links,
 * and four vitals. Designed as the page-opening editorial block so
 * the reader gets a one-glance picture of the record before any
 * section card.
 */
export function GeneHeader({ rec }: GeneHeaderProps) {
  const g = rec.gene;
  const ids = [
    {
      label: "HGNC",
      value: g.hgnc_id,
      href: `https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${g.hgnc_id}`,
    },
    {
      label: "UniProt",
      value: g.uniprot_acc,
      href: `https://www.uniprot.org/uniprotkb/${g.uniprot_acc}`,
    },
    {
      label: "NCBI Gene",
      value: String(g.ncbi_gene_id),
      href: `https://www.ncbi.nlm.nih.gov/gene/${g.ncbi_gene_id}`,
    },
    {
      label: "Ensembl",
      value: g.ensembl_gene,
      href: `https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${g.ensembl_gene}`,
    },
  ];
  const blocking = rec.risk_flags.filter((r) => r.severity === "blocking").length;
  const highRisks = rec.risk_flags.filter((r) => r.severity === "high").length;
  const sub =
    rec.targetability.recommended_modalities?.[0]?.kind ??
    rec.triage_signal ??
    rec.surface_biology.surface_status;

  return (
    <header className={styles.header}>
      <p className={`label-mono ${styles.eyebrow}`}>
        Surfaceome record · {rec.schema_version}
      </p>
      <h1 className={`h-display ${styles.symbol}`}>{g.hgnc_symbol}</h1>
      <p className={`lede ${styles.tldr}`}>{rec.targetability.tldr}</p>

      <ul className={styles.ids} aria-label="External identifiers">
        {ids.map((id) => (
          <li key={id.label} className={styles.idItem}>
            <a
              className={styles.idLink}
              href={id.href}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span className={`label-mono ${styles.idLabel}`}>{id.label}</span>
              <span className={styles.idValue}>{id.value}</span>
            </a>
          </li>
        ))}
      </ul>

      <dl className={styles.vitals}>
        <div className={styles.vital}>
          <dt className={`label-mono ${styles.vitalK}`}>Surface status</dt>
          <dd className={styles.vitalV}>
            <StatusPill tone="teal">
              {prettyEnum(rec.surface_biology.surface_status)}
            </StatusPill>
            <span className={styles.vitalSub}>
              {rec.surface_biology.db_comparison.n_sources_voting_surface}/8 sources
            </span>
          </dd>
        </div>

        <div className={styles.vital}>
          <dt className={`label-mono ${styles.vitalK}`}>Targetability</dt>
          <dd className={styles.vitalV}>
            <StatusPill tone="maroon">{prettyEnum(rec.targetability.tier)}</StatusPill>
            <span className={styles.vitalSub}>{prettyEnum(sub)}</span>
          </dd>
        </div>

        <div className={styles.vital}>
          <dt className={`label-mono ${styles.vitalK}`}>Confidence</dt>
          <dd className={styles.vitalV}>
            <StatusPill tone="lavender">{prettyEnum(rec.confidence)}</StatusPill>
            <span className={styles.vitalSub}>
              {rec.primary_evidence_count} primary · {rec.secondary_evidence_count} secondary
            </span>
          </dd>
        </div>

        <div className={styles.vital}>
          <dt className={`label-mono ${styles.vitalK}`}>Risk flags</dt>
          <dd className={styles.vitalV}>
            <span className={styles.vitalCount}>{rec.risk_flags.length}</span>
            <span className={styles.vitalSub}>
              {blocking ? `${blocking} blocking` : null}
              {blocking && highRisks ? " · " : null}
              {highRisks ? `${highRisks} high` : null}
              {!blocking && !highRisks ? "—" : null}
            </span>
          </dd>
        </div>
      </dl>
    </header>
  );
}
