import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { FieldRow } from "../FieldRow/FieldRow";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./DeepDiveCard.module.css";

interface DeepDiveCardProps {
  rec: SurfaceomeRecord;
  n: number;
}

function concordancePill(value: boolean | null | undefined) {
  if (value === true) return <StatusPill tone="success" size="sm">concordant</StatusPill>;
  if (value === false) return <StatusPill tone="danger" size="sm">divergent</StatusPill>;
  return <StatusPill tone="neutral" size="sm">unknown</StatusPill>;
}

export function DeepDiveCard({ rec, n }: DeepDiveCardProps) {
  const isoforms = rec.isoform_accessibility ?? [];
  const coreceptors = rec.coreceptor_requirements ?? [];
  const orthologs = rec.orthology ?? [];

  if (!isoforms.length && !coreceptors.length && !orthologs.length) return null;

  return (
    <SectionCard
      n={n}
      eyebrow="Deep dive"
      title={<>Isoforms, partners, <em>orthologs</em></>}
      meta="Cross-species concordance · co-receptor dependencies · per-isoform calls"
    >
      {isoforms.length > 0 ? (
        <div className={styles.subsection}>
          <h3 className={`label-mono ${styles.subhead}`}>Isoform accessibility</h3>
          <p className={styles.subnote}>
            Per-isoform surface call. One entry per UniProt isoform whose call
            differs from the canonical (or a single entry for the canonical when
            isoforms aren&apos;t differential).
          </p>
          {isoforms.map((iso, i) => (
            <FieldRow
              key={iso.isoform_id ?? i}
              k={
                <span className={styles.isoKey}>
                  <span className={styles.mono}>{iso.isoform_id}</span>
                  {iso.is_canonical ? (
                    <StatusPill tone="teal" size="sm">canonical</StatusPill>
                  ) : null}
                  {iso.differential_from_canonical ? (
                    <StatusPill tone="warn" size="sm">differential</StatusPill>
                  ) : null}
                </span>
              }
              ariaLabel={iso.isoform_id}
              ids={iso.cited_evidence_ids}
            >
              <p className={styles.meta}>
                {iso.name ?? "—"}
                {iso.length_aa != null ? ` · ${iso.length_aa} aa` : null}
              </p>
              <div className={styles.row}>
                {iso.surface_status ? (
                  <StatusPill tone="teal" size="sm">
                    {prettyEnum(iso.surface_status)}
                  </StatusPill>
                ) : null}
                {iso.exposure_class && iso.exposure_class !== "unknown" ? (
                  <StatusPill tone="lavender" size="sm">
                    {prettyEnum(iso.exposure_class)}
                  </StatusPill>
                ) : null}
              </div>
              {iso.uniprot_isoform_specific_locations &&
              iso.uniprot_isoform_specific_locations.length > 0 ? (
                <div>
                  <p className={`label-mono ${styles.tagListLabel}`}>
                    UniProt isoform-specific locations
                  </p>
                  <div className={styles.tagList}>
                    {iso.uniprot_isoform_specific_locations.map((loc) => (
                      <span key={loc} className={styles.tag}>
                        {loc}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {iso.rationale ? (
                <p className={styles.prose}>{iso.rationale}</p>
              ) : null}
            </FieldRow>
          ))}
        </div>
      ) : null}

      {coreceptors.length > 0 ? (
        <div className={styles.subsection}>
          <h3 className={`label-mono ${styles.subhead}`}>Co-receptor requirements</h3>
          <p className={styles.subnote}>
            Partners required for surface delivery or retention (not generic
            constitutive interactors). E.g. CD3 chains require CD247; HLA-I
            requires TAP1/TAP2 + tapasin + β2-microglobulin.
          </p>
          {coreceptors.map((cr, i) => (
            <FieldRow
              key={i}
              k={
                <span className={styles.isoKey}>
                  <a
                    className={styles.partnerLink}
                    href={
                      cr.partner_uniprot_acc
                        ? `https://www.uniprot.org/uniprotkb/${cr.partner_uniprot_acc}`
                        : `https://www.genenames.org/tools/search/#!/?query=${cr.partner_symbol}`
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {cr.partner_symbol}
                  </a>
                  {cr.partner_uniprot_acc ? (
                    <span className={styles.subtle}>{cr.partner_uniprot_acc}</span>
                  ) : null}
                </span>
              }
              ariaLabel={cr.partner_symbol}
              ids={cr.cited_evidence_ids}
            >
              <div>
                <StatusPill tone="lavender" size="sm">
                  {prettyEnum(cr.requirement_kind_other_label ?? cr.requirement_kind)}
                </StatusPill>
              </div>
              <p className={styles.prose}>{cr.description}</p>
            </FieldRow>
          ))}
        </div>
      ) : null}

      {orthologs.length > 0 ? (
        <div className={styles.subsection}>
          <h3 className={`label-mono ${styles.subhead}`}>Orthology</h3>
          <p className={styles.subnote}>
            Cross-species surface concordance via Ensembl Compara one-to-one,
            high-confidence pairs. Supports preclinical-model selection.
          </p>
          {orthologs.map((o, i) => (
            <FieldRow
              key={`${o.species}-${i}`}
              k={
                <span className={styles.isoKey}>
                  <span className={styles.species}>{o.species}</span>
                  {o.ortholog_gene_symbol ? (
                    <span className={`${styles.mono} ${styles.subtle}`}>
                      {o.ortholog_gene_symbol}
                    </span>
                  ) : null}
                </span>
              }
              ariaLabel={`${o.species} ortholog`}
              ids={o.cited_evidence_ids}
            >
              <div className={styles.row}>
                {o.percent_identity != null ? (
                  <span className={styles.mono}>
                    {o.percent_identity.toFixed(2)}% identity
                  </span>
                ) : null}
                {o.orthology_type && o.orthology_type !== "unknown" ? (
                  <span className={styles.tag}>{prettyEnum(o.orthology_type)}</span>
                ) : null}
                {concordancePill(o.surface_concordant_with_human)}
              </div>
              {(o.ortholog_uniprot_acc || o.ensembl_gene_id) ? (
                <div className={`${styles.row} ${styles.subtle}`}>
                  {o.ortholog_uniprot_acc ? (
                    <a
                      className={styles.xref}
                      href={`https://www.uniprot.org/uniprotkb/${o.ortholog_uniprot_acc}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      UniProt: {o.ortholog_uniprot_acc}
                    </a>
                  ) : null}
                  {o.ensembl_gene_id ? (
                    <a
                      className={styles.xref}
                      href={`https://www.ensembl.org/Multi/Search/Results?q=${o.ensembl_gene_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Ensembl: {o.ensembl_gene_id}
                    </a>
                  ) : null}
                </div>
              ) : null}
              {o.notes ? <p className={styles.prose}>{o.notes}</p> : null}
            </FieldRow>
          ))}
        </div>
      ) : null}
    </SectionCard>
  );
}
