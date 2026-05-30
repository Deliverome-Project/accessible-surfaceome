import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { StatusPill } from "../StatusPill/StatusPill";
import { EvidenceChipList } from "../EvidenceChip/EvidenceChip";
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

/** Risk boolean — ``true`` = risk present = red. */
function riskBoolPill(label: string, value: boolean) {
  return (
    <StatusPill tone={value ? "danger" : "success"} size="sm">
      <span aria-hidden="true">{value ? "✓" : "✗"}</span> {label}
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

const TT_KNOWN_LIGAND =
  "Has the synthesizer found a documented binding partner / ligand " +
  "for this protein in literature? true = yes (e.g. EGFR ← EGF; " +
  "for kinases like SRC this also captures known substrates / " +
  "interaction partners since the 'ligand' framing is canonical " +
  "for receptors but loose for cytoplasmic kinases). false = " +
  "orphan-class — ligand identity is genuinely unknown (orphan " +
  "GPCRs / NHRs / true orphan kinases). The boolean is the " +
  "catalog filter; the specific ligand identity isn't stored on " +
  "the record — see the co-receptor evidence below for partners.";

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
          title={TT_KNOWN_LIGAND}
        >
          <span aria-hidden="true">{f.has_known_ligand ? "✓" : "✗"}</span>{" "}
          known ligand
        </StatusPill>
      ),
    },
    {
      key: "spec",
      label: "Surface specificity",
      rationale: nz(f.surface_specificity_rationale),
      pill: (
        <StatusPill
          tone={surfaceSpecificityTone(f.surface_specificity)}
          size="sm"
          title={
            "Surface-vs-intracellular split. surface_dominant = surface " +
            "is the primary localization; mixed = ~equal partitioning; " +
            "mostly_intracellular = surface is the minority pool."
          }
        >
          {f.surface_specificity === "mixed"
            ? "surface vs intracellular mixed"
            : prettyEnum(f.surface_specificity)}
        </StatusPill>
      ),
    },
    {
      key: "coreceptor",
      label: "Co-receptor dependency",
      rationale: nz(ar.co_receptor_requirements.rationale),
      // Read the dependency from its canonical home in the deep block.
      // `filters.co_receptor_dependency` is only a mirror of it (and is
      // absent on records emitted before that mirror field was added —
      // e.g. the 2026-05-16 demo records — which rendered the chip value
      // as a bare em-dash). The deep-block field is always present.
      pill: (
        <StatusPill
          tone={coReceptorDependencyTone(
            ar.co_receptor_requirements.surface_expression_dependency,
          )}
          size="sm"
          title={TT_CORECEPTOR}
        >
          co-receptor ·{" "}
          {prettyEnum(ar.co_receptor_requirements.surface_expression_dependency)}
        </StatusPill>
      ),
    },
    {
      key: "restricted",
      label: "Restricted membrane subdomain",
      rationale: nz(ar.restricted_subdomain.rationale),
      pill: (
        <StatusPill
          tone={f.has_restricted_subdomain ? "danger" : "success"}
          size="sm"
          title={TT_RESTRICTED_SUBDOMAIN}
        >
          <span aria-hidden="true">
            {f.has_restricted_subdomain ? "✓" : "✗"}
          </span>{" "}
          restricted membrane subdomain
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
      pill: (
        <StatusPill
          tone={expressionLevelTone(f.expression_level)}
          size="sm"
          title={TT_EXPRESSION_LEVEL}
        >
          level · {prettyEnum(f.expression_level)}
        </StatusPill>
      ),
    },
    {
      key: "breadth",
      label: "Expression breadth",
      rationale: nz(f.expression_breadth_rationale),
      pill: (
        <StatusPill
          tone={expressionBreadthTone(f.expression_breadth)}
          size="sm"
          title={
            "Synthesizer's rollup of cross-tissue expression: pan_tissue (most " +
            "tissues), broad (>half), restricted (a few), rare (one or two)."
          }
        >
          breadth · {prettyEnum(f.expression_breadth)}
        </StatusPill>
      ),
    },
    {
      key: "oe_observed",
      label: "Overexpression precedent",
      rationale: nz(f.overexpression_surface_localization_observed_rationale),
      pill: (
        <StatusPill
          tone={
            f.overexpression_surface_localization_observed
              ? "success"
              : "neutral"
          }
          size="sm"
          title={TT_OE_OBSERVED}
        >
          <span aria-hidden="true">
            {f.overexpression_surface_localization_observed ? "✓" : "✗"}
          </span>{" "}
          Overexpression precedent
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
      pill: riskBoolPill("shed form", f.has_shed_form),
    },
    {
      key: "secreted",
      label: "Secreted form",
      rationale: secretedRationale,
      pill: riskBoolPill("secreted form", f.has_secreted_form),
    },
    {
      key: "lowendog",
      label: "Low endogenous expression",
      rationale: nz(f.low_endogenous_expression_rationale),
      pill: (
        <StatusPill
          tone={f.low_endogenous_expression ? "danger" : "success"}
          size="sm"
          title={TT_LOW_ENDOG}
        >
          <span aria-hidden="true">
            {f.low_endogenous_expression ? "✓" : "✗"}
          </span>{" "}
          low endogenous expression
        </StatusPill>
      ),
    },
    {
      key: "epitope",
      label: "Epitope masking",
      rationale: nz(ar.epitope_masking.rationale),
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
        <li key={m.key}>{m.pill}</li>
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
        <div key={m.key} className={styles.rationaleRow}>
          <dt className={styles.rationaleTerm}>{m.pill}</dt>
          <dd className={styles.rationaleDef}>
            {m.rationale ?? (
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
