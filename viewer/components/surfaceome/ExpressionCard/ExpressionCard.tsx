import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum, tissueLabel } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { FieldRow } from "../FieldRow/FieldRow";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./ExpressionCard.module.css";

interface ExpressionCardProps {
  rec: SurfaceomeRecord;
  n: number;
}

/**
 * ExpressionCard — renders the v0.4.0 protein_features block
 * (SURFY/UniProt snapshot) and the legacy v0.3.2 expression bucket
 * when present. v0.4.0 dropped the expression bucket entirely;
 * legacy records still surface it for back-compat.
 */
export function ExpressionCard({ rec, n }: ExpressionCardProps) {
  const ex = rec.expression;
  const pf = rec.protein_features;

  if (!ex && !pf) return null;

  return (
    <SectionCard
      n={n}
      eyebrow="Expression & features"
      title={
        <>
          What the <em>protein</em> is
        </>
      }
      meta={
        pf?.provenance
          ? `Protein features pre-loaded from ${pf.provenance}`
          : undefined
      }
    >
      {pf ? (
        <div className={styles.subsection}>
          <h3 className={`label-mono ${styles.subhead}`}>Protein features</h3>
          {pf.protein_length_aa != null ? (
            <FieldRow k="Length">
              <span className={styles.mono}>{pf.protein_length_aa} aa</span>
            </FieldRow>
          ) : null}
          {pf.tm_domain_count != null ? (
            <FieldRow k="TM domain count">
              <span className={styles.mono}>{pf.tm_domain_count}</span>
            </FieldRow>
          ) : null}
          {pf.signal_peptide != null ? (
            <FieldRow k="Signal peptide">
              <span className={styles.mono}>{pf.signal_peptide ? "yes" : "no"}</span>
            </FieldRow>
          ) : null}
          {pf.topology_string ? (
            <FieldRow k="Topology">
              <span>
                <span className={styles.mono}>{pf.topology_string}</span>
                <span className={styles.subtle}>
                  {" "}
                  ({pf.topology_source ?? "unknown"})
                </span>
              </span>
            </FieldRow>
          ) : null}
          {pf.almen_main_class ? (
            <FieldRow k="Almen class">
              <div className={styles.row}>
                <span className={styles.tag}>{pf.almen_main_class}</span>
                {pf.almen_sub_class ? (
                  <span className={styles.tag}>{pf.almen_sub_class}</span>
                ) : null}
              </div>
            </FieldRow>
          ) : null}
          {pf.cd_designation ? (
            <FieldRow k="CD designation">
              <StatusPill tone="lavender" size="sm">
                {pf.cd_designation}
              </StatusPill>
            </FieldRow>
          ) : null}
          {pf.uniprot_keywords && pf.uniprot_keywords.length > 0 ? (
            <FieldRow k="UniProt keywords">
              <div className={styles.tagList}>
                {pf.uniprot_keywords.map((kw) => (
                  <span key={kw} className={styles.tag}>
                    {kw}
                  </span>
                ))}
              </div>
            </FieldRow>
          ) : null}
          {pf.pdb_ids && pf.pdb_ids.length > 0 ? (
            <FieldRow k="PDB structures">
              <div className={styles.tagList}>
                {pf.pdb_ids.map((id) => (
                  <a
                    key={id}
                    className={styles.linkTag}
                    href={`https://www.rcsb.org/structure/${id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {id}
                  </a>
                ))}
              </div>
            </FieldRow>
          ) : null}
          {pf.cspa_peptide_count != null ? (
            <FieldRow k="CSPA peptides">
              <span className={styles.mono}>{pf.cspa_peptide_count}</span>
            </FieldRow>
          ) : null}
          {pf.hpa_antibody_available != null ? (
            <FieldRow k="HPA antibody">
              <span className={styles.mono}>
                {pf.hpa_antibody_available ? "yes" : "no"}
              </span>
            </FieldRow>
          ) : null}
          {pf.drugbank_ids && pf.drugbank_ids.length > 0 ? (
            <FieldRow k="DrugBank IDs">
              <div className={styles.tagList}>
                {pf.drugbank_ids.map((id) => (
                  <span key={id} className={`${styles.tag} ${styles.mono}`}>
                    {id}
                  </span>
                ))}
              </div>
            </FieldRow>
          ) : null}
          {pf.surfy_ml_score != null ? (
            <FieldRow k="SURFY ML score">
              <span className={styles.mono}>{pf.surfy_ml_score.toFixed(3)}</span>
            </FieldRow>
          ) : null}
        </div>
      ) : null}

      {ex ? (
        <div className={styles.subsection}>
          <div className={styles.subheadRow}>
            <h3 className={`label-mono ${styles.subhead}`}>Expression profile</h3>
            <StatusPill tone="neutral" size="sm">legacy v0.3.2</StatusPill>
          </div>
          <FieldRow k="Tumor specificity">
            <StatusPill tone="amber" size="sm">
              {prettyEnum(ex.tumor_specificity)}
            </StatusPill>
          </FieldRow>
          <FieldRow k="Tumor indications">
            <div className={styles.tagList}>
              {ex.tumor_indications.map((x) => (
                <span key={x} className={styles.tag}>
                  {tissueLabel(x)}
                </span>
              ))}
            </div>
          </FieldRow>
          <FieldRow k="Top normal tissues">
            <div className={styles.tagList}>
              {ex.normal_tissue_top.map((x) => (
                <span key={x} className={styles.tag}>
                  {tissueLabel(x)}
                </span>
              ))}
            </div>
          </FieldRow>
          {ex.normal_tissue_concerns.length > 0 ? (
            <FieldRow k="Concerns">
              <div className={styles.tagList}>
                {ex.normal_tissue_concerns.map((x) => (
                  <StatusPill key={x} tone="warn" size="sm">
                    {tissueLabel(x)}
                  </StatusPill>
                ))}
              </div>
            </FieldRow>
          ) : null}
          <FieldRow k="Summary" ids={ex.cited_evidence_ids}>
            <p className={styles.prose}>{ex.summary}</p>
          </FieldRow>
        </div>
      ) : null}
    </SectionCard>
  );
}
