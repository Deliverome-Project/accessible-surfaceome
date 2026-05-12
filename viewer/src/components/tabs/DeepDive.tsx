import type { SurfaceomeRecord } from "../../lib/types";
import { prettyEnum } from "../../lib/formatPretty";
import { FieldRow } from "../FieldRow";

interface Props {
  rec: SurfaceomeRecord;
  isExpanded: (b: string, f: string) => boolean;
  toggleField: (b: string, f: string) => void;
}

// Concordance pill: small green/red/grey badge depending on the
// ortholog's surface_concordant_with_human flag.
function concordancePill(value: boolean | null | undefined) {
  if (value === true) {
    return <span className="pill" style={{ background: "rgba(120,170,80,0.15)", color: "#5d8a37" }}>concordant</span>;
  }
  if (value === false) {
    return <span className="pill" style={{ background: "rgba(192,80,80,0.15)", color: "#a14545" }}>divergent</span>;
  }
  return <span className="pill" style={{ opacity: 0.6 }}>unknown</span>;
}

export function DeepDiveTab({ rec, isExpanded, toggleField }: Props) {
  const isoforms = rec.isoform_accessibility ?? [];
  const coreceptors = rec.coreceptor_requirements ?? [];
  const orthologs = rec.orthology ?? [];

  // If the whole record predates v0.4.0, there's nothing here.
  if (!isoforms.length && !coreceptors.length && !orthologs.length) {
    return (
      <div className="section-grid">
        <div className="col">
          <div className="card">
            <header><h2><span className="num">04</span>Deep dive</h2></header>
            <div className="empty">
              No isoform / co-receptor / ortholog data on this record.
              This bucket is populated for v0.4.0+ deep-dive records.
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="section-grid">
      <div className="col">
        {isoforms.length > 0 && (
          <div className="card">
            <header>
              <h2><span className="num">01</span>Isoform accessibility</h2>
              <span className="header-meta">{isoforms.length} isoform{isoforms.length === 1 ? "" : "s"}</span>
            </header>
            <p className="field-prose" style={{ opacity: 0.7 }}>
              Per-isoform surface call. One entry per UniProt isoform whose
              call differs from the canonical (or a single entry for the
              canonical when isoforms aren't differential).
            </p>
            {isoforms.map((iso, i) => (
              <FieldRow
                key={iso.isoform_id ?? i}
                k={
                  <span>
                    <span className="mono">{iso.isoform_id}</span>
                    {iso.is_canonical && <span className="tag" style={{ marginLeft: 6 }}>canonical</span>}
                    {iso.differential_from_canonical && <span className="tag" style={{ marginLeft: 6, color: "var(--warn)" }}>differential</span>}
                  </span>
                }
                ids={iso.cited_evidence_ids}
                expanded={isExpanded("deepdive", `iso-${i}`)}
                onToggle={() => toggleField("deepdive", `iso-${i}`)}
              >
                <div className="lh-meta mono">
                  {iso.name ?? "—"}
                  {iso.length_aa != null && ` · ${iso.length_aa} aa`}
                </div>
                <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {iso.surface_status && (
                    <span className={"pill status-" + iso.surface_status}>
                      {prettyEnum(iso.surface_status)}
                    </span>
                  )}
                  {iso.exposure_class && iso.exposure_class !== "unknown" && (
                    <span className="pill">{prettyEnum(iso.exposure_class)}</span>
                  )}
                </div>
                {iso.uniprot_isoform_specific_locations && iso.uniprot_isoform_specific_locations.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <div className="sub">UniProt subcellular locations tagged to this isoform:</div>
                    <div className="tag-list">
                      {iso.uniprot_isoform_specific_locations.map((loc) => (
                        <span key={loc} className="tag">{loc}</span>
                      ))}
                    </div>
                  </div>
                )}
                {iso.rationale && <div className="field-prose" style={{ marginTop: 8 }}>{iso.rationale}</div>}
              </FieldRow>
            ))}
          </div>
        )}

        {coreceptors.length > 0 && (
          <div className="card">
            <header>
              <h2><span className="num">02</span>Co-receptor requirements</h2>
              <span className="header-meta">{coreceptors.length} partner{coreceptors.length === 1 ? "" : "s"}</span>
            </header>
            <p className="field-prose" style={{ opacity: 0.7 }}>
              Partners required for surface delivery or retention (not generic
              constitutive interactors). Examples: CD3 chains require CD247
              (ζ-chain); HLA-I requires TAP1/TAP2 + tapasin + β2-microglobulin.
            </p>
            {coreceptors.map((cr, i) => (
              <FieldRow
                key={i}
                k={
                  <span>
                    <a
                      className="mono"
                      href={cr.partner_uniprot_acc ? `https://www.uniprot.org/uniprotkb/${cr.partner_uniprot_acc}` : `https://www.genenames.org/tools/search/#!/?query=${cr.partner_symbol}`}
                      target="_blank" rel="noopener noreferrer"
                      style={{ borderBottom: "1px dotted" }}
                    >
                      {cr.partner_symbol}
                    </a>
                    {cr.partner_uniprot_acc && (
                      <span className="sub" style={{ marginLeft: 6 }}>{cr.partner_uniprot_acc}</span>
                    )}
                  </span>
                }
                ids={cr.cited_evidence_ids}
                expanded={isExpanded("deepdive", `cr-${i}`)}
                onToggle={() => toggleField("deepdive", `cr-${i}`)}
              >
                <div>
                  <span className="pill">
                    {prettyEnum(cr.requirement_kind_other_label ?? cr.requirement_kind)}
                  </span>
                </div>
                <div className="field-prose" style={{ marginTop: 8 }}>{cr.description}</div>
              </FieldRow>
            ))}
          </div>
        )}

        {orthologs.length > 0 && (
          <div className="card">
            <header>
              <h2><span className="num">03</span>Orthology</h2>
              <span className="header-meta">Mouse + cyno · Ensembl Compara one-to-one + high-confidence</span>
            </header>
            <p className="field-prose" style={{ opacity: 0.7 }}>
              Cross-species surface concordance — supports preclinical-model
              selection and acts as a sanity check on the human call.
            </p>
            {orthologs.map((o, i) => (
              <FieldRow
                key={`${o.species}-${i}`}
                k={
                  <span>
                    <span style={{ textTransform: "capitalize" }}>{o.species}</span>
                    {o.ortholog_gene_symbol && (
                      <span className="mono" style={{ marginLeft: 6, opacity: 0.7 }}>{o.ortholog_gene_symbol}</span>
                    )}
                  </span>
                }
                ids={o.cited_evidence_ids}
                expanded={isExpanded("deepdive", `ortho-${i}`)}
                onToggle={() => toggleField("deepdive", `ortho-${i}`)}
              >
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  {o.percent_identity != null && (
                    <span className="mono">{o.percent_identity.toFixed(2)}% identity</span>
                  )}
                  {o.orthology_type && o.orthology_type !== "unknown" && (
                    <span className="tag">{prettyEnum(o.orthology_type)}</span>
                  )}
                  {concordancePill(o.surface_concordant_with_human)}
                </div>
                {(o.ortholog_uniprot_acc || o.ensembl_gene_id) && (
                  <div style={{ marginTop: 6, display: "flex", gap: 12, flexWrap: "wrap" }} className="sub mono">
                    {o.ortholog_uniprot_acc && (
                      <a href={`https://www.uniprot.org/uniprotkb/${o.ortholog_uniprot_acc}`} target="_blank" rel="noopener noreferrer" style={{ borderBottom: "1px dotted" }}>
                        UniProt: {o.ortholog_uniprot_acc}
                      </a>
                    )}
                    {o.ensembl_gene_id && (
                      <a href={`https://www.ensembl.org/Multi/Search/Results?q=${o.ensembl_gene_id}`} target="_blank" rel="noopener noreferrer" style={{ borderBottom: "1px dotted" }}>
                        Ensembl: {o.ensembl_gene_id}
                      </a>
                    )}
                  </div>
                )}
                {o.notes && <div className="field-prose" style={{ marginTop: 8 }}>{o.notes}</div>}
              </FieldRow>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
