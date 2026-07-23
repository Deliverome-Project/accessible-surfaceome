"use client";

import type {
  EvidenceStrength,
  Severity,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/enums";
import { ChipLabelValue } from "../ChipLabelValue/ChipLabelValue";
import { EvidenceChipList, linkifyEvidenceRefs } from "../EvidenceChip/EvidenceChip";
import { FeatureRationales } from "../FeatureChips/FeatureChips";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./AccessibilityRisksCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function severityTone(v: Severity | "none") {
  if (v === "high") return "danger" as const;
  if (v === "moderate") return "amber" as const;
  if (v === "low") return "success" as const;
  if (v === "none") return "success" as const;
  return "neutral" as const;
}

function strengthTone(v: EvidenceStrength) {
  if (v === "strong") return "success" as const;
  if (v === "moderate") return "amber" as const;
  // Weak / inferred evidence reads as a real concern in this card —
  // the risk subsection has data but the data quality is poor.
  // Render in danger (red) rather than neutral (brown); the reader
  // needs to scan for evidence-quality problems quickly.
  if (v === "weak" || v === "inferred") return "danger" as const;
  return "neutral" as const;
}

function presenceLabel(present: boolean) {
  return present ? "Present" : "Not present";
}

/** Colloquial homomer label for a cyclic-symmetry order N. Mirrors the
 *  vocabulary used by the StructureViewer's Schweke tab ("Homo-Dimer" /
 *  "Homo-Trimer" / …) so a reader scanning the risks card for "dimer"
 *  finds it without having to translate "2-mer" mentally. Falls through
 *  to the N-mer form for orders the explicit set doesn't cover (so a
 *  hypothetical 17-mer renders as "17-mer" rather than crashing). */
function stoichiometryLabel(n: number): string {
  const map: Record<number, string> = {
    2: "Dimer",
    3: "Trimer",
    4: "Tetramer",
    5: "Pentamer",
    6: "Hexamer",
    7: "Heptamer",
    8: "Octamer",
    9: "Nonamer",
    10: "Decamer",
    11: "Undecamer",
    12: "Dodecamer",
    13: "Tridecamer",
  };
  return map[n] ?? `${n}-mer`;
}

export function AccessibilityRisksCard({ rec, n }: Props) {
  const r = rec.accessibility_risks;
  const ctx = rec.deterministic_features.canonical_topology;
  return (
    <SectionCard
      n={n}
      eyebrow="Accessibility risks"
      title="Accessibility caveats"
      meta="Four subsections · severity + evidence-strength on each · cites point into the evidence ledger"
    >
      <FeatureRationales category="risks" rec={rec} />

      {/* Epitope masking and the deterministic Schweke homo-oligomer
       *  prediction are paired at the TOP of the card so the reader sees
       *  the two related signals together — the LLM-emitted masking
       *  mechanism + the AF2-derived structural prior on
       *  homo-oligomerization. Everything that follows (Shed / Secreted /
       *  ECD size assessment) is independent risk axes. */}
      <div className={styles.subsection}>
        <div className={styles.subHead}>
          <p className={styles.subTitle}>Epitope masking</p>
          {r.epitope_masking.mechanism.length === 0 ? (
            // No documented masking mechanism is GOOD — render in
            // success/green so it reads as "no risk here" rather
            // than the previous neutral brown which looked like a
            // gap in coverage.
            <StatusPill tone="success" size="sm">
              mechanism · none documented
            </StatusPill>
          ) : (
            r.epitope_masking.mechanism.map((m) => (
              <StatusPill key={m} tone="lavender" size="sm">
                {prettyEnum(m)}
              </StatusPill>
            ))
          )}
          <StatusPill tone={severityTone(r.epitope_masking.severity)} size="sm">
            <ChipLabelValue label="severity" value={prettyEnum(r.epitope_masking.severity)} />
          </StatusPill>
          <StatusPill
            tone={strengthTone(r.epitope_masking.evidence_strength)}
            size="sm"
          >
            <ChipLabelValue label="evidence" value={prettyEnum(r.epitope_masking.evidence_strength)} />
          </StatusPill>
          <EvidenceChipList
            ids={r.epitope_masking.cited_evidence_ids}
            label="Cites"
          />
        </div>
        {r.epitope_masking.rationale ? (
          <p className={styles.prose}>
            {linkifyEvidenceRefs(r.epitope_masking.rationale)}
          </p>
        ) : null}
      </div>

      {/* Deterministic Schweke 2024 (PMID 38325366) AF2 homo-oligomer
       *  prediction — rendered as a sibling chip right under epitope_masking
       *  so the reader sees the deterministic AF2 call paired with the
       *  LLM-emitted masking mechanism. NO severity pill: this is a
       *  deterministic structural prior, not a graded LLM judgment — the
       *  presence + stoichiometry labels carry the signal; a "severity Low"
       *  pill would falsely frame the prediction as a graded assessment.
       *  The schema still carries .severity (used by the Worker's Cat 3
       *  derivation + future analytics); we just don't render it here.
       *  Post-pass populated by the v2 orchestrator from
       *  deterministic_features.homo_oligomerization; older records validate
       *  with the field absent. */}
      {r.homo_oligomerization_prediction ? (
        <div className={styles.subsection}>
          <div className={styles.subHead}>
            <p className={styles.subTitle}>
              Homo-oligomerization (Schweke 2024)
            </p>
            <StatusPill
              tone={
                r.homo_oligomerization_prediction.present
                  ? "danger"
                  : "success"
              }
              size="sm"
            >
              {presenceLabel(r.homo_oligomerization_prediction.present)}
            </StatusPill>
            {r.homo_oligomerization_prediction.present &&
            r.homo_oligomerization_prediction.stoichiometry != null ? (
              // Use the colloquial homomer label ("Dimer" / "Trimer" / ...)
              // as the primary pill text so a reader scanning the risks
              // card for "dimer" sees it immediately. Mirrors the
              // StructureViewer's Schweke tab vocabulary.
              <StatusPill tone="lavender" size="sm">
                {stoichiometryLabel(
                  r.homo_oligomerization_prediction.stoichiometry,
                )}
              </StatusPill>
            ) : null}
            {r.homo_oligomerization_prediction.is_ecd_only ? (
              <StatusPill tone="teal" size="sm">
                ECD-only model
              </StatusPill>
            ) : null}
          </div>
          <p className={styles.prose}>
            {r.homo_oligomerization_prediction.present
              ? r.homo_oligomerization_prediction.stoichiometry != null
                ? `Predicted ${stoichiometryLabel(r.homo_oligomerization_prediction.stoichiometry).toLowerCase()} (homo-${r.homo_oligomerization_prediction.stoichiometry}-mer).`
                : "Predicted homo-oligomer (stoichiometry not reconstructed)."
              : "Not in Schweke's positive refset (treat as a lower bound; known under-call on big multi-pass channels and ligand/covalent dimers)."}{" "}
            {r.homo_oligomerization_prediction.is_ecd_only
              ? "ECD-only model — the soluble ECD is the dimerizing surface, which IS the epitope-accessible region. "
              : ""}
            <span className={`label-mono ${styles.muted}`}>Source</span>{" "}
            <a
              href="https://pubmed.ncbi.nlm.nih.gov/38325366/"
              target="_blank"
              rel="noreferrer"
            >
              Schweke et al. 2024, PMID 38325366
            </a>
          </p>
        </div>
      ) : null}

      <div className={styles.subsection}>
        <div className={styles.subHead}>
          <p className={styles.subTitle}>Shed form</p>
          <StatusPill tone={severityTone(r.shed_form.severity)} size="sm">
            <ChipLabelValue label="severity" value={prettyEnum(r.shed_form.severity)} />
          </StatusPill>
          <StatusPill tone={strengthTone(r.shed_form.evidence_strength)} size="sm">
            <ChipLabelValue label="evidence" value={prettyEnum(r.shed_form.evidence_strength)} />
          </StatusPill>
          <StatusPill tone={r.shed_form.present ? "danger" : "success"} size="sm">
            {presenceLabel(r.shed_form.present)}
          </StatusPill>
          <EvidenceChipList ids={r.shed_form.cited_evidence_ids} label="Cites" />
        </div>
        {r.shed_form.rationale ? (
          <p className={styles.prose}>
            {linkifyEvidenceRefs(r.shed_form.rationale)}
          </p>
        ) : null}
        {r.shed_form.mechanism ? (
          <p className={styles.prose}>
            <span className={`label-mono ${styles.muted}`}>Mechanism</span>{" "}
            {linkifyEvidenceRefs(r.shed_form.mechanism)}
            {r.shed_form.sheddase_if_known
              ? ` · sheddase: ${r.shed_form.sheddase_if_known}`
              : ""}
          </p>
        ) : null}
      </div>

      <div className={styles.subsection}>
        <div className={styles.subHead}>
          <p className={styles.subTitle}>Secreted form</p>
          <StatusPill tone={severityTone(r.secreted_form.severity)} size="sm">
            <ChipLabelValue label="severity" value={prettyEnum(r.secreted_form.severity)} />
          </StatusPill>
          <StatusPill tone={strengthTone(r.secreted_form.evidence_strength)} size="sm">
            <ChipLabelValue label="evidence" value={prettyEnum(r.secreted_form.evidence_strength)} />
          </StatusPill>
          <StatusPill tone={r.secreted_form.present ? "danger" : "success"} size="sm">
            {presenceLabel(r.secreted_form.present)}
          </StatusPill>
          <EvidenceChipList ids={r.secreted_form.cited_evidence_ids} label="Cites" />
        </div>
        {r.secreted_form.rationale ? (
          <p className={styles.prose}>
            {linkifyEvidenceRefs(r.secreted_form.rationale)}
          </p>
        ) : null}
        {r.secreted_form.source ? (
          <p className={styles.prose}>
            <span className={`label-mono ${styles.muted}`}>Source</span>{" "}
            {prettyEnum(r.secreted_form.source)}
            {r.secreted_form.ratio_to_membrane != null
              ? ` · ratio-to-membrane: ${r.secreted_form.ratio_to_membrane}`
              : ""}
          </p>
        ) : null}
      </div>

      {/* Restricted subdomain MOVED to BiologicalContextCard — it
       *  describes WHERE on the cell surface a protein is localized
       *  (apical vs basolateral vs junctional vs broad), which is
       *  biology context, not a risk per se. The Biology card's
       *  subcellular-localization subsection is the natural home. */}

      {/* Co-receptor requirements MOVED to BiologicalContextCard — it's
       *  surface-expression biology (does the protein need a partner to
       *  reach the surface) and its at-a-glance chip lives in the §01
       *  Biology group, so the detail reads best alongside it there. */}

      <div className={styles.subsection}>
        <div className={styles.subHead}>
          <p className={styles.subTitle}>ECD size assessment</p>
          <StatusPill
            tone={
              r.ecd_size_assessment.ecd_accessibility_class === "large"
                ? "success"
                : r.ecd_size_assessment.ecd_accessibility_class === "moderate"
                ? "teal"
                : r.ecd_size_assessment.ecd_accessibility_class === "small"
                ? "amber"
                : "danger"
            }
            size="sm"
          >
            <ChipLabelValue
              label="ECD"
              value={prettyEnum(r.ecd_size_assessment.ecd_accessibility_class)}
            />
          </StatusPill>
          <span className={styles.muted}>
            (deterministic ECD len: {ctx.ecd_length_residues} aa)
          </span>
          <EvidenceChipList
            ids={r.ecd_size_assessment.cited_evidence_ids}
            label="Cites"
          />
        </div>
        {r.ecd_size_assessment.rationale ? (
          <p className={styles.prose}>
            {linkifyEvidenceRefs(r.ecd_size_assessment.rationale)}
          </p>
        ) : null}
      </div>

    </SectionCard>
  );
}
