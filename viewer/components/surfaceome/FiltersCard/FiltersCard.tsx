import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./FiltersCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function boolPill(label: string, value: boolean) {
  return (
    <StatusPill tone={value ? "danger" : "neutral"} size="sm">
      <span aria-hidden="true">{value ? "✓" : "✗"}</span> {label}
    </StatusPill>
  );
}

export function FiltersCard({ rec, n }: Props) {
  const f = rec.filters;
  const topo = rec.deterministic_features.canonical_topology;
  const groups = [
    {
      label: "Accessibility",
      pills: [
        <StatusPill key="acc" tone="teal" size="sm">
          overall · {prettyEnum(f.surface_accessibility)}
        </StatusPill>,
        <StatusPill key="conf" tone="lavender" size="sm">
          conf · {prettyEnum(f.confidence)}
        </StatusPill>,
        <StatusPill key="sub" tone="neutral" size="sm">
          {prettyEnum(f.subcategory)}
        </StatusPill>,
        <StatusPill key="grade" tone="amber" size="sm">
          {prettyEnum(f.evidence_grade)}
        </StatusPill>,
        <StatusPill key="ecd" tone="teal" size="sm">
          ECD · {prettyEnum(f.ecd_accessibility_class)}
        </StatusPill>,
        <StatusPill key="dens" tone="neutral" size="sm">
          evidence · {prettyEnum(f.evidence_density)}
        </StatusPill>,
      ],
    },
    {
      label: "Expression",
      pills: [
        <StatusPill key="level" tone="teal" size="sm">
          level · {prettyEnum(f.expression_level)}
        </StatusPill>,
        <StatusPill key="breadth" tone="neutral" size="sm">
          breadth · {prettyEnum(f.expression_breadth)}
        </StatusPill>,
        <StatusPill key="spec" tone="lavender" size="sm">
          {prettyEnum(f.surface_specificity)}
        </StatusPill>,
      ],
    },
    {
      label: "Risks",
      pills: [
        boolPill("shed form", f.has_shed_form),
        boolPill("secreted form", f.has_secreted_form),
        boolPill("co-receptor for expression", f.requires_coreceptor_for_expression),
        boolPill("epitope masking", f.has_epitope_masking),
        boolPill("restricted subdomain", f.has_restricted_subdomain),
      ],
    },
    {
      label: "Cross-species (deterministic)",
      pills: [
        <StatusPill
          key="m"
          tone={f.mouse_ortholog_ecd_pct_identity == null ? "neutral" : "teal"}
          size="sm"
        >
          mouse ·{" "}
          {f.mouse_ortholog_ecd_pct_identity == null
            ? "no Compara ortholog"
            : `${f.mouse_ortholog_ecd_pct_identity.toFixed(1)}%`}
        </StatusPill>,
        <StatusPill
          key="c"
          tone={f.cyno_ortholog_ecd_pct_identity == null ? "neutral" : "teal"}
          size="sm"
        >
          cyno ·{" "}
          {f.cyno_ortholog_ecd_pct_identity == null
            ? "no Compara ortholog"
            : `${f.cyno_ortholog_ecd_pct_identity.toFixed(1)}%`}
        </StatusPill>,
      ],
    },
    {
      label: "Paralogs (deterministic)",
      pills: [
        f.max_paralog_ecd_pct_identity == null ? (
          <StatusPill key="p" tone="neutral" size="sm">
            no Compara paralogs
          </StatusPill>
        ) : (
          <StatusPill key="p" tone="lavender" size="sm">
            max %ECD identity · {f.max_paralog_ecd_pct_identity.toFixed(1)}%
          </StatusPill>
        ),
      ],
    },
    {
      label: "Topology (deterministic)",
      pills: [
        <StatusPill key="tm" tone="neutral" size="sm">
          {topo.tm_helix_count} TM
        </StatusPill>,
        boolPill("N-term extracellular", f.n_term_extracellular),
        boolPill("C-term extracellular", f.c_term_extracellular),
      ],
    },
  ];

  return (
    <SectionCard
      n={n}
      eyebrow="Filters"
      title="Catalog membership and source coverage"
      meta="D1-indexed facets · informational here; the catalog page owns interactive filtering"
    >
      <div className={styles.groups}>
        {groups.map((g) => (
          <div key={g.label} className={styles.group}>
            <p className={`label-mono ${styles.groupLabel}`}>{g.label}</p>
            <ul className={styles.pills}>
              {g.pills.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
