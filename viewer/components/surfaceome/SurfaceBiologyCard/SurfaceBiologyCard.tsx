import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { FieldRow } from "../FieldRow/FieldRow";
import { StatusPill } from "../StatusPill/StatusPill";
import { DBVotes } from "../DBVotes/DBVotes";
import styles from "./SurfaceBiologyCard.module.css";

interface SurfaceBiologyCardProps {
  rec: SurfaceomeRecord;
  n: number;
}

function directionTone(d: string) {
  if (d === "supports_surface") return "success" as const;
  if (d === "refutes_surface") return "danger" as const;
  return "neutral" as const;
}

function strengthTone(s: string) {
  if (s === "strong") return "success" as const;
  if (s === "moderate") return "amber" as const;
  return "neutral" as const;
}

export function SurfaceBiologyCard({ rec, n }: SurfaceBiologyCardProps) {
  const sb = rec.surface_biology;
  const induced = sb.induced_presentation ?? [];
  const assays = sb.surface_localization_assays ?? [];

  return (
    <SectionCard
      n={n}
      eyebrow="Surface biology"
      title={<>The <em>extracellular</em> case</>}
      meta={`UniProt · M1 panel · primary assays · schema ${rec.schema_version}`}
    >
      <FieldRow k="Surface status" ids={sb.cited_evidence_ids}>
        <div className={styles.row}>
          <StatusPill tone="teal">{prettyEnum(sb.surface_status)}</StatusPill>
          {rec.triage_signal && rec.triage_signal !== "unknown" ? (
            <StatusPill tone="lavender" size="sm">
              triage: {prettyEnum(rec.triage_signal)}
            </StatusPill>
          ) : null}
        </div>
      </FieldRow>

      <FieldRow k="Topology">
        <span className={styles.mono}>{prettyEnum(sb.topology)}</span>
      </FieldRow>

      <FieldRow k="Anchor type">
        <span className={styles.mono}>{prettyEnum(sb.anchor_type)}</span>
      </FieldRow>

      {sb.exposure_class && sb.exposure_class !== "unknown" ? (
        <FieldRow k="Exposure class">
          <span className={styles.mono}>{prettyEnum(sb.exposure_class)}</span>
        </FieldRow>
      ) : null}

      <FieldRow k="Extracellular domain">
        <span className={styles.mono}>
          {sb.extracellular_domain.size_aa
            ? `${sb.extracellular_domain.size_aa} aa`
            : "Not applicable"}
        </span>
        {sb.extracellular_domain.notes ? (
          <span className={styles.note}>{sb.extracellular_domain.notes}</span>
        ) : null}
      </FieldRow>

      {induced.length > 0 ? (
        <div className={styles.subsection}>
          <h3 className={`label-mono ${styles.subhead}`}>
            Induced / conditional presentation
          </h3>
          <p className={styles.subnote}>
            Contexts under which this otherwise-intracellular protein reaches the
            outer leaflet. Required for{" "}
            <code className={styles.code}>surface_status=&quot;conditional_surface&quot;</code>{" "}
            calls.
          </p>
          {induced.map((ip, i) => (
            <FieldRow
              key={i}
              k={prettyEnum(ip.context_kind_other_label ?? ip.context_kind)}
              ids={ip.cited_evidence_ids}
            >
              <p className={styles.prose}>{ip.description}</p>
            </FieldRow>
          ))}
        </div>
      ) : null}

      {assays.length > 0 ? (
        <div className={styles.subsection}>
          <h3 className={`label-mono ${styles.subhead}`}>Primary surface assays</h3>
          <p className={styles.subnote}>
            Direct experimental observations of surface localization. ≥1 required
            when the surface call is anything other than absent.
          </p>
          {assays.map((a, i) => (
            <FieldRow
              key={i}
              k={
                <span>
                  {prettyEnum(a.assay_type_other_label ?? a.assay_type)}
                  <span className={styles.subtle}> · {a.species}</span>
                </span>
              }
              ariaLabel={a.assay_type_other_label ?? a.assay_type}
              ids={a.cited_evidence_ids}
            >
              <div className={styles.row}>
                <StatusPill tone={directionTone(a.direction)} size="sm">
                  {prettyEnum(a.direction)}
                </StatusPill>
                <StatusPill tone={strengthTone(a.strength)} size="sm">
                  {prettyEnum(a.strength)}
                </StatusPill>
              </div>
              <p className={styles.prose}>
                <span className={styles.subtle}>on </span>
                {a.cell_type_or_line}
              </p>
            </FieldRow>
          ))}
        </div>
      ) : null}

      <div className={styles.subsection}>
        <h3 className={`label-mono ${styles.subhead}`}>
          Database vote · 8 sources
        </h3>
        <DBVotes db={sb.db_comparison} />
      </div>
    </SectionCard>
  );
}
