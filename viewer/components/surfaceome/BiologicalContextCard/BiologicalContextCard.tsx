import type {
  AccessibilityImplication,
  ModulationDirection,
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

/** Small directional glyph for a modulation row's `direction` enum:
 *  ↑ increases surface (green), ↓ decreases (red), ↕ bidirectional (amber),
 *  = no change (muted). Returns null for "unclear" or an absent field (older
 *  records), so those rows show no glyph rather than a misleading one. */
// Rendered "Change" cell for the modulation table — the structured
// `direction` of the surface-accessible pool under the modulating state,
// shown as a glyph + short word. `unclear` (and null / older records that
// lack the field) render an explicit "?" rather than a blank cell, so the
// reader can tell "not determined" apart from "no row".
function directionCell(
  direction: ModulationDirection | undefined,
): React.ReactNode {
  const map: Record<
    string,
    { glyph: string; text: string; color: string; title: string }
  > = {
    increases_surface: {
      glyph: "↑",
      text: "Increase",
      color: "var(--success, #1b5e3f)",
      title: "Increases surface-accessible pool",
    },
    decreases_surface: {
      glyph: "↓",
      text: "Decrease",
      color: "var(--maroon-dark, #922038)",
      title: "Decreases surface-accessible pool",
    },
    bidirectional: {
      glyph: "↕",
      text: "Bidirectional",
      color: "var(--amber-dark, #8a5a16)",
      title: "Both directions documented",
    },
    no_change: {
      glyph: "=",
      text: "Equal",
      color: "var(--ink-faint, #999)",
      title: "No net change in surface accessibility",
    },
  };
  const d = direction ? map[direction] : undefined;
  if (!d) {
    return (
      <span
        title="Direction of change not determined"
        style={{ color: "var(--ink-faint, #999)" }}
      >
        ?
      </span>
    );
  }
  return (
    <span
      aria-label={d.title}
      title={d.title}
      style={{ color: d.color, fontWeight: 600, whiteSpace: "nowrap" }}
    >
      {d.glyph} {d.text}
    </span>
  );
}

export function BiologicalContextCard({ rec, n }: Props) {
  const bc = rec.biological_context;
  const loc = bc.subcellular_localization;
  const es = rec.executive_summary;
  // Co-receptor requirements — surface-expression biology (does the
  // protein need a partner to reach the surface). Lives in
  // ``accessibility_risks`` in the schema but renders here, next to its
  // §01 Biology chip. Moved from the §Risks card.
  const cr = rec.accessibility_risks.co_receptor_requirements;

  return (
    <SectionCard
      n={n}
      eyebrow="Biological context"
      title="Localization & accessibility context"
      meta="Accessibility modulation · subcellular localization · anatomical accessibility"
    >
      {/* Overarching accessibility-context summary — one-sentence
          rationale for WHEN/WHERE the protein is reachable. The headline
          chips (reason / primary compartment / induced-state triggers)
          were removed per UX: each duplicated content already shown below
          — the subcellular-localization "primary" chip and the modulation
          table's trigger column. */}
      {es.accessibility_context_summary ? (
        <div className={styles.contextSummary}>
          <p className={styles.contextRationale}>
            {es.accessibility_context_summary}
          </p>
        </div>
      ) : null}

      <FeatureRationales category="biology" rec={rec} />

      {/* Accessibility modulation — moved to the top (most decision-
          relevant) and rendered as a table: one row per state/lineage
          shift, far easier to scan than the old stacked prose blocks. */}
      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Accessibility modulation</p>
        {bc.accessibility_modulation.length === 0 ? (
          <p className={styles.empty}>No modulation rows recorded.</p>
        ) : (
          <table className={`${styles.table} ${styles.modTable}`}>
            <thead>
              <tr>
                <th scope="col">Context</th>
                <th scope="col">Change</th>
                <th scope="col">Reference</th>
                <th scope="col">Modulating state</th>
                <th scope="col">Implication</th>
                <th scope="col">References</th>
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
                  {/* Structured direction of the surface pool under the
                      modulating state — its own column, "?" when unclear. */}
                  <td>{directionCell(m.direction)}</td>
                  <td>{m.baseline_context}</td>
                  <td>{m.modulating_state}</td>
                  <td>{m.accessibility_implication}</td>
                  <td>
                    {/* The change/effect narrative (the "evidence string")
                     *  lives in the Cites column with its citations rather
                     *  than widening the Shift column. */}
                    {m.change ? (
                      <p className={styles.modChangeCite}>{m.change}</p>
                    ) : null}
                    <EvidenceChipList ids={m.cited_evidence_ids} label="References" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Subcellular localization</p>
        {/* Primary compartment + two labeled secondary axes in one
            consistent stack (was: subdomains as badges but dual_localization
            as a separate full table — same "where else is it" idea, two
            unrelated treatments):
              • surface subdomain — outer-leaflet PM microdomains an antibody
                meets (apical / basolateral / raft / junction).
              • also found in — whole non-primary compartments (endosome,
                lysosome, …); each badge carries its condition + fraction on
                hover and its citation chips inline, so no table data is lost. */}
        <div className={styles.locHead}>
          <StatusPill tone="teal" size="sm">
            <ChipLabelValue label="primary" value={prettyEnum(loc.primary_compartment)} />
          </StatusPill>
        </div>
        {loc.membrane_subdomains.length > 0 ? (
          <div className={styles.locRow}>
            <span className={`label-mono ${styles.locRowLabel}`}>
              surface subdomain
            </span>
            <span className={styles.subdomains}>
              {loc.membrane_subdomains.map((s, i) => (
                <StatusPill key={i} tone="lavender" size="sm">
                  {prettyEnum(s.subdomain)}
                </StatusPill>
              ))}
            </span>
          </div>
        ) : null}
        {loc.dual_localization.length > 0 ? (
          <div className={styles.locRow}>
            <span className={`label-mono ${styles.locRowLabel}`}>
              also found in
            </span>
            <span className={styles.subdomains}>
              {loc.dual_localization.map((d, i) => {
                const pct =
                  d.fraction_estimate != null
                    ? `${(d.fraction_estimate * 100).toFixed(0)}%`
                    : null;
                const hover = [d.condition, pct ? `~${pct} of pool` : null]
                  .filter(Boolean)
                  .join(" · ");
                return (
                  <span key={i} className={styles.locCompartment}>
                    <StatusPill tone="teal" size="sm" title={hover || undefined}>
                      {prettyEnum(d.compartment)}
                      {pct ? ` · ${pct}` : ""}
                    </StatusPill>
                    {d.cited_evidence_ids.length > 0 ? (
                      <EvidenceChipList ids={d.cited_evidence_ids} />
                    ) : null}
                  </span>
                );
              })}
            </span>
          </div>
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
                  label="References"
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
                <th scope="col">References</th>
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
                    <EvidenceChipList ids={a.cited_evidence_ids} label="References" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Co-receptor requirements</p>
        <div className={styles.locHead}>
          <StatusPill
            tone={
              cr.surface_expression_dependency === "required"
                ? "danger"
                : cr.surface_expression_dependency === "modulatory"
                ? "amber"
                : "neutral"
            }
            size="sm"
          >
            <ChipLabelValue
              label="dependency"
              value={prettyEnum(cr.surface_expression_dependency)}
            />
          </StatusPill>
          <StatusPill tone="lavender" size="sm">
            <ChipLabelValue
              label="evidence basis"
              value={prettyEnum(cr.evidence_basis)}
            />
          </StatusPill>
          <EvidenceChipList ids={cr.cited_evidence_ids} label="References" />
        </div>
        {cr.partners.length > 0 ? (
          <p className={styles.locProse}>
            <span className={`label-mono ${styles.muted}`}>Partners</span>{" "}
            {cr.partners.join(", ")}
          </p>
        ) : null}
        {cr.rationale ? <p className={styles.locProse}>{cr.rationale}</p> : null}
      </div>

    </SectionCard>
  );
}
