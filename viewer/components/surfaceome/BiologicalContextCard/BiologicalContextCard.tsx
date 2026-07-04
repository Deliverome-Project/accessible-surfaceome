import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { chipJumpTargets } from "../../../lib/chipJumpTargets";
import { ChipLabelValue } from "../ChipLabelValue/ChipLabelValue";
import { EvidenceChipList, linkifyEvidenceRefs } from "../EvidenceChip/EvidenceChip";
import { FeatureRationales } from "../FeatureChips/FeatureChips";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import { AccessibilityModulationTable } from "./AccessibilityModulationTable";
import { AnatomicalAccessibilityTable } from "./AnatomicalAccessibilityTable";
import styles from "./BiologicalContextCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
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
      {/* Localization at-a-glance — primary compartment + the non-primary
          compartments the protein is ALSO found in (endosome / lysosome / …).
          Surfaced in the accessibility-context header, not only in the
          Subcellular localization subsection lower down. */}
      <div className={styles.contextBadges}>
        <StatusPill tone="teal" size="sm">
          <ChipLabelValue
            label="primary"
            value={prettyEnum(loc.primary_compartment)}
          />
        </StatusPill>
        {loc.dual_localization.map((d, i) => (
          <StatusPill key={`dl-${i}`} tone="lavender" size="sm">
            <ChipLabelValue label="also in" value={prettyEnum(d.compartment)} />
          </StatusPill>
        ))}
      </div>

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

      {/* Biological-context grade rationale — synth's reasoning for the
          rich/moderate/sparse rollup of expression × cell types × tissues ×
          modulation evidence. Lives at bc.grade_rationale + bc.grade_cited_evidence_ids.
          Was hidden pre-2.50.x; surfaced here so the reader can see why the
          A2 evidence picture was graded as it was. */}
      {bc.grade_rationale ? (
        <div className={styles.contextSummary}>
          <p className={`label-mono ${styles.muted}`}>
            Biology evidence — {prettyEnum(bc.biological_context_grade)}
          </p>
          <p className={styles.contextRationale}>
            {linkifyEvidenceRefs(bc.grade_rationale)}
          </p>
        </div>
      ) : null}

      <FeatureRationales category="biology" rec={rec} />

      {/* Accessibility modulation moved to the bottom of the Biology section
          (was at top): rows are dense per-state/lineage detail that reads
          better AFTER the static "where is the protein?" picture
          (subcellular + anatomical + co-receptor) is in the reader's head.
          The headline modulation signal (oncogenic / immune / stress trigger)
          is already shown in the at-a-glance chip in the section header. */}
      <div
        id={chipJumpTargets.primaryCompartment}
        tabIndex={-1}
        className={styles.subsection}
      >
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
        {loc.rationale ? (
          <p className={styles.locProse}>
            {linkifyEvidenceRefs(loc.rationale)}
          </p>
        ) : null}
        {loc.membrane_subdomains.length > 0 ? (
          <div className={styles.locRow}>
            <span className={`label-mono ${styles.locRowLabel}`}>
              surface subdomain
            </span>
            <span className={styles.subdomains}>
              {loc.membrane_subdomains.map((s, i) => (
                <StatusPill
                  key={i}
                  tone="lavender"
                  size="sm"
                  title={s.rationale || undefined}
                >
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
                const hover = [
                  d.rationale,
                  d.condition,
                  pct ? `~${pct} of pool` : null,
                ]
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
                <p className={styles.locProse}>
                  {linkifyEvidenceRefs(rs.rationale)}
                </p>
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
          <AnatomicalAccessibilityTable rows={bc.anatomical_accessibility} />
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
        {cr.rationale ? (
          <p className={styles.locProse}>
            {linkifyEvidenceRefs(cr.rationale)}
          </p>
        ) : null}
      </div>

      {/* Accessibility modulation — moved to the BOTTOM of the Biology
          section. Per-row state/lineage shifts (oncogenic upregulation,
          immune activation, stress release) are dense table data that
          reads better after the reader has the static "where is the
          protein?" picture (subcellular + anatomical + co-receptor) in
          their head. The headline modulation chip in the section header
          covers the at-a-glance trigger bucket. */}
      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Accessibility modulation</p>
        {bc.accessibility_modulation.length === 0 ? (
          <p className={styles.empty}>No modulation rows recorded.</p>
        ) : (
          <AccessibilityModulationTable rows={bc.accessibility_modulation} />
        )}
      </div>

    </SectionCard>
  );
}
