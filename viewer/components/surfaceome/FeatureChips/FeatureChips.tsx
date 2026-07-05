import { Fragment } from "react";
import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { chipJumpTargets } from "../../../lib/chipJumpTargets";
import { InfoTip } from "../../InfoTip/InfoTip";
import { ChipJumpButton } from "../_shared/ChipJumpButton/ChipJumpButton";
import { ChipLabelValue } from "../ChipLabelValue/ChipLabelValue";
import { StatusPill } from "../StatusPill/StatusPill";
import { EvidenceChipList, linkifyEvidenceRefs } from "../EvidenceChip/EvidenceChip";
import styles from "./FeatureChips.module.css";

// ---------------------------------------------------------------------------
// Feature chips — the LLM `rec.filters` summary chips, grouped into three
// categories.
//
// Placement (PR #47): the at-a-glance CHIPS render only in the §01 signal
// panel (FiltersCard, under an "LLM-driven" heading). Each category's
// dedicated top-level tab — Biology / Expression / Risks — renders the
// per-chip RATIONALE instead (via <FeatureRationales>), so the at-a-glance
// chip up top and its "why" on the tab are explicitly linked.
//
// Every chip carries a rationale. Four come from the synthesizer's
// LLM-emitted `filters.*_rationale` rollups; two are orchestrator-composed
// for the derived booleans; the remaining five read their rationale out of
// the deep `accessibility_risks` blocks. `buildFeatureChips` is the single
// source of truth binding each chip's value, pill, and rationale together.
// ---------------------------------------------------------------------------

export type FeatureCategory = "biology" | "expression" | "risks";

/** Ordered list of the feature categories. `page.tsx` renders one
 *  top-level tab per entry; FiltersCard renders one signal-panel chip
 *  group per entry, in this order. */
export const FEATURE_CATEGORIES = ["biology", "expression", "risks"] as const;

/** Reader-facing tab label per category. Consumed by `page.tsx` (the
 *  AnchorNav tab strip), the FiltersCard chip-group heading, and the
 *  chip-row aria-label below, so a rename can't drift them apart. */
export const FEATURE_TAB_LABEL: Record<FeatureCategory, string> = {
  biology: "Biology",
  expression: "Expression",
  risks: "Risks",
};

/** One chip: its short label, the pill rendered in the signal panel, and
 *  the rationale prose rendered on the category's tab. `rationale` is null
 *  only for records emitted before the rationale fields existed (genes not
 *  yet re-annotated); the tab renders a muted placeholder in that case. */
export interface FeatureChipModel {
  key: string;
  label: string;
  pill: React.ReactNode;
  rationale: string | null;
  /** Evidence IDs backing the rationale, surfaced as clickable tags on the
   *  tab. Set only for chips whose rationale comes from a deep
   *  `accessibility_risks` block that carries `cited_evidence_ids`
   *  (co-receptor / restricted-subdomain / shed / secreted / epitope). The
   *  LLM-emitted rollup rationales (ligand / specificity / expression
   *  level+breadth) and the orchestrator-derived booleans carry no
   *  structured cites, so this is left unset for them. */
  citedEvidenceIds?: string[];
  /** Provenance / glossary tooltip content. Rendered next to the chip as a
   *  small ⓘ InfoTip so the whole pill remains the click-to-jump target
   *  (the `<ChipJumpButton>` wrapping the pill would otherwise swallow
   *  hover-only tooltips, and mixing hover + click on the same surface is
   *  confusing). Builders that populated this used to pass a `title=` prop
   *  on the `StatusPill` directly; the field split lets us keep the
   *  affordance while separating the two interactions. */
  hoverTooltip?: React.ReactNode;
}

type Tone =
  | "success"
  | "warn"
  | "danger"
  | "neutral"
  | "teal"
  | "lavender"
  | "amber";

/** Normalize a possibly-empty / "None" rationale string to null. */
function nz(s: string | null | undefined): string | null {
  if (s == null) return null;
  const t = s.trim();
  return t === "" || t === "None" ? null : t;
}

/** Risk boolean — ``true`` = risk present = red. Rendered as a
 *  `label · PRESENT/NONE` chip (the shared label·value style) rather
 *  than a ✓/✗ glyph, so the attribute reads as a word. */
function riskBoolPill(label: string, value: boolean) {
  return (
    <StatusPill tone={value ? "danger" : "success"} size="sm">
      <ChipLabelValue label={label} value={value ? "present" : "none"} />
    </StatusPill>
  );
}

function surfaceSpecificityTone(v: string): Tone {
  if (v === "surface_dominant") return "success";
  if (v === "mixed") return "warn";
  if (v === "mostly_intracellular") return "danger";
  return "neutral";
}

/**
 * Co-receptor dependency — "none" means the protein surfaces on its
 * own (best for monovalent-binder programs); "modulatory" means a
 * partner influences but doesn't gate surface presence; "required"
 * means surface presence depends on a partner (worst for monovalent
 * binders, may need bispecific or partner-aware design); "unknown"
 * is the synth's default when the ledger is silent.
 */
function coReceptorDependencyTone(v: string): Tone {
  if (v === "none") return "success";
  if (v === "modulatory") return "warn";
  if (v === "required") return "danger";
  return "neutral";
}

function expressionLevelTone(v: string): Tone {
  if (v === "high") return "success";
  if (v === "moderate") return "warn";
  if (v === "low" || v === "absent") return "danger";
  return "neutral";
}

function expressionBreadthTone(v: string): Tone {
  if (v === "pan_tissue" || v === "broad") return "success";
  if (v === "restricted") return "warn";
  if (v === "rare") return "danger";
  return "neutral";
}

const TT_CORECEPTOR =
  "LLM-driven. Whether the protein needs a partner to reach the surface. " +
  "None = surfaces on its own; modulatory = a partner influences but " +
  "doesn't gate surface presence; required = surface presence depends on " +
  "a partner (a bispecific or partner-aware design may be needed); " +
  "unknown = the agent found no information either way.";

const TT_RESTRICTED_SUBDOMAIN =
  "true = the protein localizes to a restricted membrane microdomain " +
  "(apical / basolateral / tight-junction / ciliary / synaptic / " +
  "lipid-raft), so its surface epitope can be spatially sequestered and " +
  "harder for a systemic binder to reach in vivo. false = no such " +
  "localization restriction flagged.";

const TT_EXPRESSION_LEVEL =
  "How abundantly this protein is expressed at baseline in the tissues " +
  "and cell lines covered by the cited evidence.";

const TT_OE_OBSERVED =
  "Whether prior overexpression studies (HEK293 / HeLa / K562 / U2OS " +
  "transfection, stable or transient) have demonstrated surface " +
  "localization of this protein. Useful precedent when planning an " +
  "overexpression-based validation experiment — you know the " +
  "construct can reach the surface in a heterologous cell line. " +
  "Distinct from the orphan-receptor and low-endogenous flags " +
  "(those describe baseline biology; this one describes prior " +
  "experimental precedent).";

const TT_LOW_ENDOG =
  "Flags proteins where baseline endogenous expression is low or " +
  "absent. These targets typically need overexpression-based studies " +
  "(HEK293 / HeLa / U2OS transfection) to characterize surface " +
  "biology, and antibody / binder validation in endogenous tissues " +
  "is harder because there's little protein to stain or bind in " +
  "untransfected controls.";

// --- per-category chip-model builders --------------------------------

function buildBiologyChips(rec: SurfaceomeRecord): FeatureChipModel[] {
  const f = rec.filters;
  const ar = rec.accessibility_risks;
  return [
    {
      key: "ligand",
      label: "Known ligand",
      rationale: nz(f.has_known_ligand_rationale),
      pill: (
        <StatusPill
          tone={f.has_known_ligand ? "success" : "danger"}
          size="sm"
        >
          <ChipLabelValue
            label="known ligand"
            value={f.has_known_ligand ? "present" : "none"}
          />
        </StatusPill>
      ),
    },
    {
      key: "spec",
      label: "Surface specificity",
      rationale: nz(f.surface_specificity_rationale),
      hoverTooltip:
        "Surface-vs-intracellular split. surface_dominant = surface " +
        "is the primary localization; mixed = ~equal partitioning; " +
        "mostly_intracellular = surface is the minority pool.",
      pill: (
        <StatusPill
          tone={surfaceSpecificityTone(f.surface_specificity)}
          size="sm"
        >
          {/* Sentence-case description + bold UPPERCASE verdict at the
           *  same font size — shared `ChipLabelValue` so every
           *  attribute·value chip reads identically. */}
          <ChipLabelValue
            label="Surface vs intracellular"
            value={prettyEnum(f.surface_specificity)}
          />
        </StatusPill>
      ),
    },
    {
      key: "restricted",
      label: "Restricted membrane subdomain",
      rationale: nz(ar.restricted_subdomain.rationale),
      citedEvidenceIds: ar.restricted_subdomain.cited_evidence_ids,
      hoverTooltip: TT_RESTRICTED_SUBDOMAIN,
      pill: (
        <StatusPill
          tone={f.has_restricted_subdomain ? "danger" : "success"}
          size="sm"
        >
          <ChipLabelValue
            label="restricted membrane subdomain"
            value={f.has_restricted_subdomain ? "present" : "none"}
          />
        </StatusPill>
      ),
    },
    {
      // "partner for expression" (co-receptor dependency) sits LAST in the
      // biology chip row per user request — it reads as a caveat after the
      // protein's own surface properties.
      key: "coreceptor",
      label: "Co-receptor dependency",
      rationale: nz(ar.co_receptor_requirements.rationale),
      citedEvidenceIds: ar.co_receptor_requirements.cited_evidence_ids,
      // Read the dependency from its canonical home in the deep block.
      // `filters.co_receptor_dependency` is only a mirror of it (and is
      // absent on records emitted before that mirror field was added —
      // e.g. the 2026-05-16 demo records — which rendered the chip value
      // as a bare em-dash). The deep-block field is always present.
      hoverTooltip: TT_CORECEPTOR,
      pill: (
        <StatusPill
          tone={coReceptorDependencyTone(
            ar.co_receptor_requirements.surface_expression_dependency,
          )}
          size="sm"
        >
          <ChipLabelValue
            label="partner for expression"
            value={prettyEnum(
              ar.co_receptor_requirements.surface_expression_dependency,
            )}
          />
        </StatusPill>
      ),
    },
  ];
}

function buildExpressionChips(rec: SurfaceomeRecord): FeatureChipModel[] {
  const f = rec.filters;
  return [
    {
      key: "level",
      label: "Expression level",
      rationale: nz(f.expression_level_rationale),
      hoverTooltip: TT_EXPRESSION_LEVEL,
      pill: (
        <StatusPill
          tone={expressionLevelTone(f.expression_level)}
          size="sm"
        >
          <ChipLabelValue label="level" value={prettyEnum(f.expression_level)} />
        </StatusPill>
      ),
    },
    {
      key: "breadth",
      label: "Expression breadth",
      rationale: nz(f.expression_breadth_rationale),
      hoverTooltip:
        "Synthesizer's rollup of cross-tissue expression: pan_tissue (most " +
        "tissues), broad (>half), restricted (a few), rare (one or two).",
      pill: (
        <StatusPill
          tone={expressionBreadthTone(f.expression_breadth)}
          size="sm"
        >
          <ChipLabelValue label="breadth" value={prettyEnum(f.expression_breadth)} />
        </StatusPill>
      ),
    },
    {
      key: "oe_observed",
      label: "Overexpression precedent",
      rationale: nz(f.overexpression_surface_localization_observed_rationale),
      hoverTooltip: TT_OE_OBSERVED,
      pill: (
        <StatusPill
          tone={
            f.overexpression_surface_localization_observed
              ? "success"
              : "neutral"
          }
          size="sm"
        >
          <ChipLabelValue
            label="overexpression precedent"
            value={
              f.overexpression_surface_localization_observed
                ? "present"
                : "none"
            }
          />
        </StatusPill>
      ),
    },
  ];
}

function buildRiskChips(rec: SurfaceomeRecord): FeatureChipModel[] {
  const f = rec.filters;
  const ar = rec.accessibility_risks;
  // shed / secreted carry no free-text `rationale` field — compose a
  // short "why" from their structured deep-block fields (mechanism /
  // source + severity + evidence-strength). This is record-data
  // formatting, not invented prose.
  const shedRationale = nz(
    [
      nz(ar.shed_form.mechanism),
      `severity ${ar.shed_form.severity}, evidence ${ar.shed_form.evidence_strength}`,
    ]
      .filter(Boolean)
      .join(" · "),
  );
  const secretedRationale = nz(
    [
      ar.secreted_form.source ? `source ${prettyEnum(ar.secreted_form.source)}` : null,
      `severity ${ar.secreted_form.severity}, evidence ${ar.secreted_form.evidence_strength}`,
    ]
      .filter(Boolean)
      .join(" · "),
  );
  return [
    {
      key: "shed",
      label: "Shed form",
      rationale: shedRationale,
      citedEvidenceIds: ar.shed_form.cited_evidence_ids,
      pill: riskBoolPill("shed form", f.has_shed_form),
    },
    {
      key: "secreted",
      label: "Secreted form",
      rationale: secretedRationale,
      citedEvidenceIds: ar.secreted_form.cited_evidence_ids,
      pill: riskBoolPill("secreted form", f.has_secreted_form),
    },
    {
      key: "lowendog",
      label: "Low endogenous expression",
      rationale: nz(f.low_endogenous_expression_rationale),
      hoverTooltip: TT_LOW_ENDOG,
      pill: (
        <StatusPill
          tone={f.low_endogenous_expression ? "danger" : "success"}
          size="sm"
        >
          <ChipLabelValue
            label="low endogenous expression"
            value={f.low_endogenous_expression ? "yes" : "no"}
          />
        </StatusPill>
      ),
    },
    {
      key: "epitope",
      label: "Epitope masking",
      rationale: nz(ar.epitope_masking.rationale),
      citedEvidenceIds: ar.epitope_masking.cited_evidence_ids,
      pill: riskBoolPill("epitope masking", f.has_epitope_masking),
    },
  ];
}

const BUILDERS: Record<
  FeatureCategory,
  (rec: SurfaceomeRecord) => FeatureChipModel[]
> = {
  biology: buildBiologyChips,
  expression: buildExpressionChips,
  risks: buildRiskChips,
};

/** Single source of truth: the chip models for one category. Consumed by
 *  FiltersCard (renders `.pill`) and `<FeatureRationales>` (renders
 *  `.rationale`). */
export function buildFeatureChips(
  category: FeatureCategory,
  rec: SurfaceomeRecord,
): FeatureChipModel[] {
  return BUILDERS[category](rec);
}

/**
 * Render a single §01 chip model with the "jump to rationale" wrapper
 * applied when the chip has a rationale to jump to. Consumed by
 * `<FeatureChips>` (for the at-a-glance chip row) AND by `<FiltersCard>`
 * (which inlines the pill mapping directly rather than embedding
 * `<FeatureChips>`). Extracting the wrap decision keeps the two call sites
 * from drifting on which chips become clickable.
 *
 * Two orthogonal decorations:
 * - When `nz(m.rationale)` is non-null, the pill is wrapped in a
 *   `<ChipJumpButton>` so the whole chip surface acts as a jump target.
 * - When `m.hoverTooltip` is set, a small `<InfoTip>` (ⓘ glyph) is
 *   rendered next to the pill so hover / focus reveals the provenance
 *   / glossary tooltip WITHOUT competing with the click-to-jump.
 *
 * Both decorations render as siblings inside a keyed Fragment. The
 * InfoTip sits OUTSIDE the `<ChipJumpButton>` so clicking the ⓘ
 * doesn't trigger a jump, and so its own real `<button>` trigger
 * doesn't nest inside the click surface's `<span role="button">`.
 */
export function renderChipWithJump(
  m: FeatureChipModel,
  category: FeatureCategory,
): React.ReactNode {
  const clickable = nz(m.rationale) !== null;
  const infoTip = m.hoverTooltip ? (
    <InfoTip label={`About ${m.label}`}>{m.hoverTooltip}</InfoTip>
  ) : null;
  const chip = clickable ? (
    <ChipJumpButton
      targetId={chipJumpTargets.featureRationale(category, m.key)}
      tabId={category}
      ariaLabel={`Jump to rationale: ${m.label}`}
    >
      {m.pill}
    </ChipJumpButton>
  ) : (
    m.pill
  );
  return (
    <Fragment key={m.key}>
      {chip}
      {infoTip}
    </Fragment>
  );
}

interface FeatureChipsProps {
  category: FeatureCategory;
  rec: SurfaceomeRecord;
}

/**
 * The at-a-glance chip row for one feature category. Rendered in the §01
 * signal panel (FiltersCard). The `data-feature-chips={category}`
 * attribute is the runtime half of the chip↔tab connection — the matching
 * `data-section-id={category}` lives on the tab section; the new
 * `data-feature-rationales={category}` block on the tab is the rationale
 * counterpart. `viewer/tests/verify_feature_tabs.py` asserts they line up.
 */
export function FeatureChips({ category, rec }: FeatureChipsProps) {
  const models = buildFeatureChips(category, rec);
  return (
    <ul
      className={styles.pills}
      data-feature-chips={category}
      aria-label={`${FEATURE_TAB_LABEL[category]} summary chips`}
    >
      {models.map((m) => (
        <li key={m.key}>{renderChipWithJump(m, category)}</li>
      ))}
    </ul>
  );
}

interface FeatureRationalesProps {
  category: FeatureCategory;
  rec: SurfaceomeRecord;
}

/**
 * The per-chip rationale block for one feature category. Rendered at the
 * top of the category's tab card (where the chip row used to sit). Each
 * entry pairs the chip's pill with its "why" — so the at-a-glance signal
 * up in the §01 panel and the reasoning on the tab are explicitly linked.
 */
export function FeatureRationales({ category, rec }: FeatureRationalesProps) {
  const models = buildFeatureChips(category, rec);
  return (
    <dl
      className={styles.rationales}
      data-feature-rationales={category}
      aria-label={`${FEATURE_TAB_LABEL[category]} signal rationales`}
    >
      {models.map((m) => (
        <div
          key={m.key}
          id={chipJumpTargets.featureRationale(category, m.key)}
          tabIndex={-1}
          className={styles.rationaleRow}
        >
          <dt className={styles.rationaleTerm}>{m.pill}</dt>
          <dd className={styles.rationaleDef}>
            {m.rationale ? (
              <>
                {/* linkifyEvidenceRefs turns any inline `aN_evi_NN` token in
                 *  the prose into a clickable EvidenceChip — covers the
                 *  orchestrator-composed OE rationale, which names its cites
                 *  inline. No-op for rationales without inline IDs. */}
                {linkifyEvidenceRefs(m.rationale)}
                {/* Structured cites for the deep-block chips (co-receptor /
                 *  restricted / shed / secreted / epitope) whose record block
                 *  carries `cited_evidence_ids`. */}
                {m.citedEvidenceIds && m.citedEvidenceIds.length > 0 ? (
                  <span className={styles.rationaleCites}>
                    <EvidenceChipList ids={m.citedEvidenceIds} label="Cites" />
                  </span>
                ) : null}
              </>
            ) : (
              <span className={styles.rationaleMissing}>
                No rationale recorded for this record.
              </span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
