// Ported from prototype's markdown-export.js. Renders a SurfaceomeRecord
// as a single Markdown string with footnote-style references and a sources
// appendix. Phase 1 has empty evidence/sources, so most of the footnote
// machinery is currently a no-op — kept intact so the M3 wire-up is trivial.

import type { SurfaceomeRecord } from "./types";
import { titleCase } from "./formatPretty";

const PRETTY: Record<string, string> = {
  tcr_mimic: "TCR-mimic antibody",
  tcr_t: "TCR-engineered T cells",
  not_recommended: "Not recommended",
  edge_case: "Edge case",
  validated: "Validated",
  pan_tumor: "Pan-tumor",
  not_pm_associated: "Not PM-associated",
  mhc_presented_peptide: "MHC-presented peptide",
  rare_surface: "Rare surface",
  bispecific: "Bispecific",
  high: "High",
  medium: "Medium",
  low: "Low",
  blocking: "Blocking",
  primary: "Primary",
  secondary: "Secondary",
  supports: "Supports",
  refutes: "Refutes",
};
const pretty = (s: string | null | undefined): string =>
  s == null ? "—" : (PRETTY[s] || titleCase(s));

interface Evidence { evidence_id: string; [k: string]: unknown }
type Sources = Record<string, unknown>;

function citeList(
  ids: string[] | undefined,
  evidenceById: Record<string, Evidence>,
  all: Evidence[],
): string {
  if (!ids || !ids.length) return "";
  const refs = ids
    .map((id) => evidenceById[id])
    .filter(Boolean)
    .map((ev) => `[^${all.findIndex((e) => e.evidence_id === ev.evidence_id) + 1}]`);
  return refs.length ? " " + refs.join("") : "";
}

export function recordToMarkdown(
  rec: SurfaceomeRecord,
  evidence: Evidence[] = [],
  _sources: Sources = {},
): string {
  const evidenceById: Record<string, Evidence> = {};
  evidence.forEach((e) => { evidenceById[e.evidence_id] = e; });
  const all = evidence;
  const g = rec.gene;
  const lines: string[] = [];

  lines.push("---");
  lines.push(`hgnc_symbol: ${g.hgnc_symbol}`);
  lines.push(`hgnc_id: ${g.hgnc_id}`);
  lines.push(`uniprot_acc: ${g.uniprot_acc}`);
  lines.push(`ncbi_gene_id: ${g.ncbi_gene_id}`);
  lines.push(`ensembl_gene: ${g.ensembl_gene}`);
  lines.push(`tier: ${rec.targetability.tier}`);
  lines.push(`confidence: ${rec.confidence}`);
  lines.push(`schema_version: ${rec.schema_version}`);
  lines.push(`generated_at: ${new Date().toISOString()}`);
  lines.push("---");
  lines.push("");

  lines.push(`# ${g.hgnc_symbol} — Surfaceome record`);
  lines.push("");
  lines.push(`**Targetability:** ${pretty(rec.targetability.tier)}  `);
  lines.push(`**Confidence:** ${pretty(rec.confidence)}  `);
  lines.push(`**Surface vote:** ${rec.surface_biology.db_comparison.n_sources_voting_surface} / 8 sources  `);
  lines.push(`**Evidence:** ${rec.primary_evidence_count} primary · ${rec.secondary_evidence_count} secondary  `);
  lines.push(`**Risk flags:** ${rec.risk_flags.length}  `);
  lines.push("");
  lines.push("**Identifiers**  ");
  lines.push(`- HGNC: \`${g.hgnc_id}\` — https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${g.hgnc_id}`);
  lines.push(`- UniProt: \`${g.uniprot_acc}\` — https://www.uniprot.org/uniprotkb/${g.uniprot_acc}`);
  lines.push(`- NCBI Gene: \`${g.ncbi_gene_id}\` — https://www.ncbi.nlm.nih.gov/gene/${g.ncbi_gene_id}`);
  lines.push(`- Ensembl: \`${g.ensembl_gene}\` — https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${g.ensembl_gene}`);
  lines.push("");

  lines.push("## Recommendation");
  lines.push("");
  lines.push(rec.targetability.tldr + citeList(rec.targetability.cited_evidence_ids, evidenceById, all));
  lines.push("");
  // v0.3.2 carried `recommended_modalities`; v0.4.0 dropped it.
  if (rec.targetability.recommended_modalities?.length) {
    lines.push("**Recommended modalities**");
    lines.push("");
    rec.targetability.recommended_modalities.forEach((m, i) => {
      const name = m.kind_other_label ? pretty(m.kind_other_label) : pretty(m.kind);
      const flag = m.kind === "not_recommended" ? "Not viable" : i === 0 ? "Primary" : "Alternate";
      lines.push(`${i + 1}. **${name}** _(${flag})_ — ${m.rationale}`);
    });
    lines.push("");
  }

  const sb = rec.surface_biology;
  lines.push("## Surface biology");
  lines.push("");
  lines.push(`- **Surface status:** ${pretty(sb.surface_status)}`);
  lines.push(`- **Topology:** ${pretty(sb.topology)}`);
  lines.push(`- **Anchor type:** ${pretty(sb.anchor_type)}`);
  lines.push(`- **Extracellular domain:** ${sb.extracellular_domain.size_aa ? sb.extracellular_domain.size_aa + " aa" : "Not applicable"}`);
  if (sb.extracellular_domain.notes) lines.push(`  - ${sb.extracellular_domain.notes}`);
  lines.push("");
  lines.push("**Database vote — 8 sources**");
  lines.push("");
  const dbOrder: (keyof typeof sb.db_comparison)[] = [
    "surfy", "cspa", "uniprot_query", "go", "hpa", "deeptmhmm", "compartments", "patent_handle",
  ];
  lines.push("| Source | Vote |");
  lines.push("| --- | --- |");
  dbOrder.forEach((s) => lines.push(`| ${String(s).replace(/_/g, " ")} | ${sb.db_comparison[s] ? "Surface" : "—"} |`));
  lines.push(`| **Total** | **${sb.db_comparison.n_sources_voting_surface} / 8** |`);
  lines.push("");

  // v0.3.2 had an `expression` bucket; v0.4.0 dropped it.
  const ex = rec.expression;
  if (ex) {
    lines.push("## Expression");
    lines.push("");
    lines.push(`- **Tumor specificity:** ${pretty(ex.tumor_specificity)}`);
    lines.push(`- **Tumor indications:** ${ex.tumor_indications.map(titleCase).join(", ") || "—"}`);
    lines.push(`- **Top normal tissues:** ${ex.normal_tissue_top.map(titleCase).join(", ") || "—"}`);
    lines.push(`- **Concerns:** ${ex.normal_tissue_concerns.map(titleCase).join(", ") || "—"}`);
    lines.push("");
    lines.push(ex.summary + citeList(ex.cited_evidence_ids, evidenceById, all));
    lines.push("");
  }

  // v0.4.0: surface_engagement_validation replaces therapeutic_landscape.
  // Legacy records still expose therapeutic_landscape.{patent_disclosures,
  // preclinical_evidence}.
  const sev = rec.surface_engagement_validation?.preclinical_evidence ?? [];
  const tl = rec.therapeutic_landscape;
  const legacyPatents = tl?.patent_disclosures ?? [];
  const legacyPreclinical = tl?.preclinical_evidence ?? [];
  if (sev.length || legacyPatents.length || legacyPreclinical.length) {
    lines.push("## Surface engagement validation");
    lines.push("");
    if (sev.length) {
      sev.forEach((p) => {
        lines.push(`**${p.citation}**  `);
        lines.push(p.finding_summary + citeList(p.cited_evidence_ids, evidenceById, all));
        lines.push("");
      });
    }
    if (legacyPatents.length) {
      lines.push("### Patent disclosures (legacy v0.3.2)");
      lines.push("");
      legacyPatents.forEach((p) => {
        lines.push(`**${p.wo_number} — ${p.title}**  `);
        lines.push(`${p.applicant} · priority ${p.priority_year} · ${pretty(p.modality)}`);
        lines.push("");
        lines.push(p.summary + citeList(p.cited_evidence_ids, evidenceById, all));
        lines.push("");
      });
    }
    if (legacyPreclinical.length) {
      lines.push("### Preclinical evidence (legacy v0.3.2)");
      lines.push("");
      legacyPreclinical.forEach((p) => {
        lines.push(`**${p.citation}**${p.modality ? ` — _${pretty(p.modality)}_` : ""}  `);
        lines.push(p.finding_summary + citeList(p.cited_evidence_ids, evidenceById, all));
        lines.push("");
      });
    }
  }

  lines.push("## Risk flags");
  lines.push("");
  rec.risk_flags.forEach((r, i) => {
    const name = r.kind_other_label || titleCase(r.kind);
    lines.push(`### ${i + 1}. ${name} — _${pretty(r.severity)}_`);
    lines.push("");
    lines.push(r.description + citeList(r.cited_evidence_ids, evidenceById, all));
    lines.push("");
  });

  lines.push("## Confidence");
  lines.push("");
  lines.push(`**${pretty(rec.confidence)}** — ${rec.confidence_reasoning}`);
  lines.push("");

  lines.push("---");
  lines.push(`_Generated from schema ${rec.schema_version} · model ${rec.model_path || "—"} · ${new Date().toISOString()}_`);

  return lines.join("\n");
}
