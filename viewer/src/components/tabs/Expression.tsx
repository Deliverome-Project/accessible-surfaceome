import type { SurfaceomeRecord } from "../../lib/types";
import { prettyEnum, tissueLabel } from "../../lib/formatPretty";
import { FieldRow } from "../FieldRow";

interface Props {
  rec: SurfaceomeRecord;
  isExpanded: (b: string, f: string) => boolean;
  toggleField: (b: string, f: string) => void;
}

export function ExpressionTab({ rec, isExpanded, toggleField }: Props) {
  // v0.4.0 dropped the `expression` bucket; fall back to ProteinFeatures
  // (Almen / TM count / UniProt keywords / etc.) when the legacy bucket
  // isn't present.
  const ex = rec.expression;
  const pf = rec.protein_features;

  if (!ex && !pf) {
    return (
      <div className="section-grid">
        <div className="col">
          <div className="card">
            <header><h2><span className="num">02</span>Expression</h2></header>
            <div className="empty">No expression data on file for this record.</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="section-grid">
      <div className="col">
        {ex && (
          <div className="card">
            <header><h2><span className="num">02</span>Expression profile <span className="legacy-pill"> · v0.3.2</span></h2></header>
            <FieldRow k="Tumor specificity">
              <span className="tag spec">{prettyEnum(ex.tumor_specificity)}</span>
            </FieldRow>
            <FieldRow k="Tumor indications">
              <div className="tag-list">
                {ex.tumor_indications.map((x) => <span key={x} className="tag">{tissueLabel(x)}</span>)}
              </div>
            </FieldRow>
            <FieldRow k="Top normal tissues">
              <div className="tag-list">
                {ex.normal_tissue_top.map((x) => <span key={x} className="tag">{tissueLabel(x)}</span>)}
              </div>
            </FieldRow>
            <FieldRow k="Concerns">
              <div className="tag-list">
                {ex.normal_tissue_concerns.map((x) => (
                  <span key={x} className="tag" style={{ color: "var(--warn)", borderColor: "rgba(192,120,48,0.35)" }}>
                    {tissueLabel(x)}
                  </span>
                ))}
              </div>
            </FieldRow>
            <hr className="hr" />
            <FieldRow
              k="Summary"
              ids={ex.cited_evidence_ids}
              expanded={isExpanded("expression", "summary")}
              onToggle={() => toggleField("expression", "summary")}
            >
              <div className="field-prose">{ex.summary}</div>
            </FieldRow>
          </div>
        )}

        {pf && (
          <div className="card">
            <header><h2><span className="num">{ex ? "03" : "02"}</span>Protein features</h2></header>
            <p className="field-prose" style={{ opacity: 0.7 }}>
              Pre-loaded from the SURFY snapshot (provenance: <code>{pf.provenance ?? "unknown"}</code>).
            </p>
            {pf.protein_length_aa != null && (
              <FieldRow k="Length"><span className="mono">{pf.protein_length_aa} aa</span></FieldRow>
            )}
            {pf.tm_domain_count != null && (
              <FieldRow k="TM domain count"><span className="mono">{pf.tm_domain_count}</span></FieldRow>
            )}
            {pf.signal_peptide != null && (
              <FieldRow k="Signal peptide"><span className="mono">{pf.signal_peptide ? "yes" : "no"}</span></FieldRow>
            )}
            {pf.topology_string && (
              <FieldRow k="Topology"><span className="mono">{pf.topology_string}</span> <span className="sub">({pf.topology_source ?? "unknown"})</span></FieldRow>
            )}
            {pf.almen_main_class && (
              <FieldRow k="Almen class">
                <span className="tag">{pf.almen_main_class}</span>
                {pf.almen_sub_class && <span className="tag">{pf.almen_sub_class}</span>}
              </FieldRow>
            )}
            {pf.cd_designation && (
              <FieldRow k="CD designation"><span className="tag">{pf.cd_designation}</span></FieldRow>
            )}
            {pf.uniprot_keywords && pf.uniprot_keywords.length > 0 && (
              <FieldRow k="UniProt keywords">
                <div className="tag-list">
                  {pf.uniprot_keywords.map((kw) => <span key={kw} className="tag">{kw}</span>)}
                </div>
              </FieldRow>
            )}
            {pf.pdb_ids && pf.pdb_ids.length > 0 && (
              <FieldRow k="PDB structures">
                <div className="tag-list">
                  {pf.pdb_ids.map((pdb) => (
                    <a key={pdb} className="tag" href={`https://www.rcsb.org/structure/${pdb}`} target="_blank" rel="noopener noreferrer">{pdb}</a>
                  ))}
                </div>
              </FieldRow>
            )}
            {pf.cspa_peptide_count != null && (
              <FieldRow k="CSPA peptides"><span className="mono">{pf.cspa_peptide_count}</span></FieldRow>
            )}
            {pf.hpa_antibody_available != null && (
              <FieldRow k="HPA antibody"><span className="mono">{pf.hpa_antibody_available ? "yes" : "no"}</span></FieldRow>
            )}
            {pf.drugbank_ids && pf.drugbank_ids.length > 0 && (
              <FieldRow k="DrugBank IDs">
                <div className="tag-list">
                  {pf.drugbank_ids.map((id) => <span key={id} className="tag mono">{id}</span>)}
                </div>
              </FieldRow>
            )}
            {pf.surfy_ml_score != null && (
              <FieldRow k="SURFY ML score"><span className="mono">{pf.surfy_ml_score.toFixed(3)}</span></FieldRow>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
