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

function stateDependenceTone(v: string) {
  if (v === "low") return "success" as const;
  if (v === "moderate") return "amber" as const;
  if (v === "high") return "danger" as const;
  return "neutral" as const;
}

export function BiologicalContextCard({ rec, n }: Props) {
  const bc = rec.biological_context;
  const loc = bc.subcellular_localization;
  const es = rec.executive_summary;
  // Distinct cell-state triggers across the modulation rows — the
  // "unique contexts" that gate surface accessibility, deduped into chips
  // for the overarching summary.
  const modTriggers = Array.from(
    new Set(
      bc.accessibility_modulation.flatMap((m) =>
        m.cell_state_trigger ? [m.cell_state_trigger] : [],
      ),
    ),
  );

  return (
    <SectionCard
      n={n}
      eyebrow="Biological context"
      title="Localization & accessibility context"
      meta="Accessibility modulation · subcellular localization · anatomical accessibility"
    >
      {/* Overarching accessibility-context summary — the headline chips
          (deduped contexts) + one-sentence rationale for WHEN/WHERE the
          protein is reachable. Mirrored into the §01 signal panel. */}
      <div className={styles.contextSummary}>
        <div className={styles.contextChips}>
          <StatusPill tone="lavender" size="sm">
            <ChipLabelValue
              label="reason"
              value={prettyEnum(es.surface_call_reason)}
            />
          </StatusPill>
          <StatusPill tone={stateDependenceTone(es.state_dependence)} size="sm">
            <ChipLabelValue
              label="state-gated"
              value={prettyEnum(es.state_dependence)}
            />
          </StatusPill>
          <StatusPill tone="teal" size="sm">
            <ChipLabelValue
              label="primary"
              value={prettyEnum(loc.primary_compartment)}
            />
          </StatusPill>
          {modTriggers.map((t) => (
            <StatusPill key={t} tone="amber" size="sm">
              {prettyEnum(t)}
            </StatusPill>
          ))}
        </div>
        {es.accessibility_context_summary ? (
          <p className={styles.contextRationale}>
            {es.accessibility_context_summary}
          </p>
        ) : null}
      </div>

      <FeatureRationales category="biology" rec={rec} />

      {/* Accessibility modulation — moved to the top (most decision-
          relevant) and rendered as a table: one row per state/lineage
          shift, far easier to scan than the old stacked prose blocks. */}
      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Accessibility modulation</p>
        {bc.accessibility_modulation.length === 0 ? (
          <p className={styles.empty}>No modulation rows recorded.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Context</th>
                <th scope="col">Trigger / lineage</th>
                <th scope="col">Shift</th>
                <th scope="col">Implication</th>
                <th scope="col">Cites</th>
              </tr>
            </thead>
            <tbody>
              {bc.accessibility_modulation.map((m, i) => (
                <tr key={i}>
                  <td>
                    <StatusPill tone="lavender" size="sm">
                      {prettyEnum(m.category)}
                    </StatusPill>
                  </td>
                  <td>
                    {m.cell_state_trigger ? (
                      <StatusPill tone="amber" size="sm">
                        {prettyEnum(m.cell_state_trigger)}
                      </StatusPill>
                    ) : null}
                    {m.restricted_lineage ? (
                      <StatusPill tone="teal" size="sm">
                        {prettyEnum(m.restricted_lineage)}
                      </StatusPill>
                    ) : null}
                    {!m.cell_state_trigger && !m.restricted_lineage ? (
                      <span className={styles.muted}>—</span>
                    ) : null}
                  </td>
                  <td>
                    <span className={styles.modShift}>
                      <span className={`label-mono ${styles.muted}`}>baseline</span>{" "}
                      {m.baseline_context}{" "}
                      <span aria-hidden="true">→</span>{" "}
                      <span className={`label-mono ${styles.muted}`}>modulating</span>{" "}
                      {m.modulating_state}
                    </span>
                    {m.change ? (
                      <span className={styles.modChangeInline}>{m.change}</span>
                    ) : null}
                  </td>
                  <td>{m.accessibility_implication}</td>
                  <td>
                    <EvidenceChipList ids={m.cited_evidence_ids} label="Cites" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

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
                  <ChipLabelValue
                    label="restricted subdomain"
                    value={rs.present ? "present" : "none"}
                  />
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

    </SectionCard>
  );
}
