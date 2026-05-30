import type {
  AccessibilityImplication,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { ChipLabelValue } from "../ChipLabelValue/ChipLabelValue";
import { EvidenceChipList } from "../EvidenceChip/EvidenceChip";
import { FeatureRationales } from "../FeatureChips/FeatureChips";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./BiologicalContextCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function implicationTone(v: AccessibilityImplication) {
  if (v === "favorable") return "success" as const;
  if (v === "restricted") return "danger" as const;
  if (v === "context_dependent") return "amber" as const;
  return "neutral" as const;
}

export function BiologicalContextCard({ rec, n }: Props) {
  const bc = rec.biological_context;
  const loc = bc.subcellular_localization;

  return (
    <SectionCard
      n={n}
      eyebrow="Biological context"
      title="Localization & accessibility context"
      meta="Subcellular localization · anatomical accessibility · accessibility modulation"
    >
      <FeatureRationales category="biology" rec={rec} />

      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Subcellular localization</p>
        <div className={styles.locHead}>
          <StatusPill tone="teal">
            <ChipLabelValue label="primary" value={prettyEnum(loc.primary_compartment)} />
          </StatusPill>
          {loc.membrane_subdomains.length > 0 ? (
            <span className={styles.subdomains}>
              {loc.membrane_subdomains.map((s, i) => (
                <StatusPill key={i} tone="lavender" size="sm">
                  {/* Label these "secondary" so the lavender chips read as
                   *  secondary localizations next to the teal "primary"
                   *  compartment chip, instead of bare unlabeled terms. */}
                  <ChipLabelValue label="secondary" value={prettyEnum(s.subdomain)} />
                </StatusPill>
              ))}
            </span>
          ) : null}
        </div>
        {loc.dual_localization.length > 0 ? (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Compartment</th>
                <th scope="col">Fraction</th>
                <th scope="col">Condition</th>
                <th scope="col">Cites</th>
              </tr>
            </thead>
            <tbody>
              {loc.dual_localization.map((d, i) => (
                <tr key={i}>
                  <td>{prettyEnum(d.compartment)}</td>
                  <td>
                    {d.fraction_estimate != null
                      ? `${(d.fraction_estimate * 100).toFixed(0)}%`
                      : "unknown"}
                  </td>
                  <td>{d.condition ?? "—"}</td>
                  <td>
                    <EvidenceChipList ids={d.cited_evidence_ids} label="Cites" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        {/* exocytosis_evidence was dropped in PR23 round 5 — same
            biology now lives in `accessibility_modulation` rows
            with `category=lysosomal_exocytosis` or `category=
            activation_induced` plus `cell_state_trigger`. */}

        {/* Restricted subdomain — MOVED HERE from §Risks. Describes
         *  WHERE on the cell surface the protein localizes (apical
         *  vs basolateral vs junctional vs broad). That's a
         *  biology-context fact about distribution, not a risk per
         *  se; reading it under Subcellular localization matches
         *  the reader's mental model and keeps the Risks card
         *  focused on shed / secreted / co-receptor / epitope-
         *  masking / ECD-size which truly are accessibility caveats. */}
        {(() => {
          const rs = rec.accessibility_risks.restricted_subdomain;
          return (
            <div className={styles.locRestricted}>
              <p className={`label-mono ${styles.subhead}`}>
                Restricted-subdomain distribution
              </p>
              <div className={styles.locHead}>
                <StatusPill
                  tone={rs.present ? "warn" : "success"}
                  size="sm"
                >
                  {rs.present ? (
                    "Restricted"
                  ) : (
                    <>
                      <span aria-hidden="true">✗</span> No restriction
                    </>
                  )}
                </StatusPill>
                {rs.present ? (
                  <StatusPill tone="lavender" size="sm">
                    {prettyEnum(rs.domain)}
                  </StatusPill>
                ) : null}
                <EvidenceChipList
                  ids={rs.cited_evidence_ids}
                  label="Cites"
                />
              </div>
              {rs.rationale ? (
                <p className={styles.locProse}>{rs.rationale}</p>
              ) : null}
            </div>
          );
        })()}
      </div>

      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Anatomical accessibility</p>
        {bc.anatomical_accessibility.length === 0 ? (
          <p className={styles.empty}>No anatomical-accessibility rows recorded.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Context</th>
                <th scope="col">Orientation</th>
                <th scope="col">Implication</th>
                <th scope="col">Rationale</th>
                <th scope="col">Cites</th>
              </tr>
            </thead>
            <tbody>
              {bc.anatomical_accessibility.map((a, i) => (
                <tr key={i}>
                  <td>{a.context}</td>
                  <td>{prettyEnum(a.orientation)}</td>
                  <td>
                    <StatusPill
                      tone={implicationTone(a.accessibility_implication)}
                      size="sm"
                    >
                      {prettyEnum(a.accessibility_implication)}
                    </StatusPill>
                  </td>
                  <td>{a.rationale}</td>
                  <td>
                    <EvidenceChipList ids={a.cited_evidence_ids} label="Cites" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Accessibility modulation</p>
        {bc.accessibility_modulation.length === 0 ? (
          <p className={styles.empty}>No modulation rows recorded.</p>
        ) : (
          <ul className={styles.modList}>
            {bc.accessibility_modulation.map((m, i) => (
              <li key={i} className={styles.modItem}>
                <div className={styles.modHead}>
                  <StatusPill tone="lavender" size="sm">
                    {prettyEnum(m.category)}
                  </StatusPill>
                  {m.cell_state_trigger ? (
                    <StatusPill tone="amber" size="sm">
                      <ChipLabelValue label="trigger" value={prettyEnum(m.cell_state_trigger)} />
                    </StatusPill>
                  ) : null}
                  {m.restricted_lineage ? (
                    <StatusPill tone="teal" size="sm">
                      <ChipLabelValue label="lineage" value={prettyEnum(m.restricted_lineage)} />
                    </StatusPill>
                  ) : null}
                  <EvidenceChipList ids={m.cited_evidence_ids} label="Cites" />
                </div>
                <p className={styles.modBaseline}>
                  <span className={`label-mono ${styles.muted}`}>baseline</span>{" "}
                  {m.baseline_context}{" "}
                  <span aria-hidden="true">→</span>{" "}
                  <span className={`label-mono ${styles.muted}`}>modulating</span>{" "}
                  {m.modulating_state}
                </p>
                <p className={styles.modChange}>{m.change}</p>
                <p className={styles.modImpl}>
                  <span className={`label-mono ${styles.muted}`}>Implication</span>{" "}
                  {m.accessibility_implication}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </SectionCard>
  );
}
