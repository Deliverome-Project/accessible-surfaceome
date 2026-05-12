import type { SurfaceomeRecord } from "../lib/types";
import { prettyEnum, tissueLabel } from "../lib/formatPretty";

export function GeneHeader({ rec }: { rec: SurfaceomeRecord }) {
  const g = rec.gene;
  const ids = [
    { label: "HGNC", value: g.hgnc_id, href: `https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${g.hgnc_id}` },
    { label: "UniProt", value: g.uniprot_acc, href: `https://www.uniprot.org/uniprotkb/${g.uniprot_acc}` },
    { label: "NCBI Gene", value: String(g.ncbi_gene_id), href: `https://www.ncbi.nlm.nih.gov/gene/${g.ncbi_gene_id}` },
    { label: "Ensembl", value: g.ensembl_gene, href: `https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${g.ensembl_gene}` },
  ];
  const tier = rec.targetability.tier;
  const blocking = rec.risk_flags.filter((r) => r.severity === "blocking").length;
  const highRisks = rec.risk_flags.filter((r) => r.severity === "high").length;
  // v0.4.0 dropped the `expression` bucket; fall back to "—" tumor counts.
  const indications = rec.expression?.tumor_indications ?? [];
  // v0.4.0 dropped targetability.recommended_modalities; fall back to triage_signal
  // or surface_status as the secondary signal under the tier badge.
  const tierSub =
    rec.targetability.recommended_modalities?.[0]?.kind
    ?? rec.triage_signal
    ?? rec.surface_biology.surface_status
    ?? "—";
  return (
    <header className="gene-header">
      <div className="gene-id-block">
        <h1 className="symbol">{g.hgnc_symbol}</h1>
        <div className="alias">{g.hgnc_symbol === "KAAG1" ? "also known as RU2 · RU2AS · DCDC2 antisense ORF" : g.hgnc_symbol}</div>
        <div className="id-grid">
          {ids.map((id) => (
            <a key={id.label} className="id-cell" href={id.href} target="_blank" rel="noopener noreferrer">
              <span className="label">{id.label}</span>
              <span className="value">{id.value}</span>
            </a>
          ))}
        </div>
      </div>
      <div className="verdict">
        <p className="tldr">{rec.targetability.tldr}</p>
        <div className="vitals">
          <div className={"vital vital-status status-" + rec.surface_biology.surface_status}>
            <span className="k">Surface status</span>
            <span className="v">{prettyEnum(rec.surface_biology.surface_status)}</span>
            <span className="sub">{rec.surface_biology.db_comparison.n_sources_voting_surface}/8 sources</span>
          </div>
          <div className={"vital vital-tier tier-" + tier}>
            <span className="k">Targetability</span>
            <span className="v">{prettyEnum(tier)}</span>
            <span className="sub">{prettyEnum(tierSub)}</span>
          </div>
          <div className="vital">
            <span className="k">Confidence</span>
            <span className={"v conf-" + rec.confidence}>{prettyEnum(rec.confidence)}</span>
            <span className="sub">{rec.primary_evidence_count} primary · {rec.secondary_evidence_count} secondary</span>
          </div>
          <div className="vital">
            <span className="k">Risk flags</span>
            <span className="v count">{rec.risk_flags.length}</span>
            <span className="sub">
              {blocking ? `${blocking} blocking · ` : ""}
              {highRisks ? `${highRisks} high` : (blocking ? "" : "—")}
            </span>
          </div>
          <div className="vital">
            <span className="k">Indication</span>
            <span className="v count">
              {indications.length}
              <span className="total"> tumors</span>
            </span>
            <span className="sub">
              {indications.length
                ? `${tissueLabel(indications[0])}${indications.length > 1 ? `, +${indications.length - 1}` : ""}`
                : "—"}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
