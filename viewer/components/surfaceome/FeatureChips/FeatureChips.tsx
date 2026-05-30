import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./FeatureChips.module.css";

// ---------------------------------------------------------------------------
// Feature chips — the LLM `rec.filters` summary chips, grouped into three
// categories that each map to a standalone top-level tab on the gene page.
//
// These used to render inside the §01 "Summary metrics" card (FiltersCard)
// under an "LLM-driven" heading. They were promoted out so each category
// is its own tab — Biology / Expression / Risks — sitting above its
// expanded prose+evidence card (BiologicalContextCard / ExpressionCard /
// AccessibilityRisksCard). Keeping the chip builders here, keyed on the
// same `FeatureCategory` the page tabs and the section anchors use, is the
// single source of truth that binds a chip group to its tab.
// ---------------------------------------------------------------------------

export type FeatureCategory = "biology" | "expression" | "risks";

/** Ordered list of the feature categories. `page.tsx` renders one
 *  top-level tab per entry, in this order, between "Surface evidence"
 *  and the evolutionary-context section; each tab's card renders
 *  `<FeatureChips category=… />` for the same category, so the chip↔tab
 *  binding lives in exactly one place. */
export const FEATURE_CATEGORIES = ["biology", "expression", "risks"] as const;

/** Reader-facing tab label per category. Consumed by BOTH `page.tsx`
 *  (the AnchorNav tab strip) and the chip-row aria-label below, so a
 *  rename can't drift the tab and its chips apart. */
export const FEATURE_TAB_LABEL: Record<FeatureCategory, string> = {
  biology: "Biology",
  expression: "Expression",
  risks: "Risks",
};

type Tone =
  | "success"
  | "warn"
  | "danger"
  | "neutral"
  | "teal"
  | "lavender"
  | "amber";

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

// --- per-category chip builders -------------------------------------

function buildBiologyChips(rec: SurfaceomeRecord): React.ReactNode[] {
  const f = rec.filters;
  return [
    <StatusPill
      key="ligand"
      tone={f.has_known_ligand ? "success" : "danger"}
      size="sm"
      title={TT_KNOWN_LIGAND}
    >
      <span aria-hidden="true">{f.has_known_ligand ? "✓" : "✗"}</span>{" "}
      known ligand
    </StatusPill>,
    <StatusPill
      key="spec"
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
    </StatusPill>,
    <StatusPill
      key="coreceptor"
      tone={coReceptorDependencyTone(f.co_receptor_dependency)}
      size="sm"
      title={TT_CORECEPTOR}
    >
      co-receptor · {prettyEnum(f.co_receptor_dependency)}
    </StatusPill>,
    <StatusPill
      key="restricted"
      tone={f.has_restricted_subdomain ? "danger" : "success"}
      size="sm"
      title={TT_RESTRICTED_SUBDOMAIN}
    >
      <span aria-hidden="true">{f.has_restricted_subdomain ? "✓" : "✗"}</span>{" "}
      restricted membrane subdomain
    </StatusPill>,
  ];
}

function buildExpressionChips(rec: SurfaceomeRecord): React.ReactNode[] {
  const f = rec.filters;
  return [
    <StatusPill
      key="level"
      tone={expressionLevelTone(f.expression_level)}
      size="sm"
      title={TT_EXPRESSION_LEVEL}
    >
      level · {prettyEnum(f.expression_level)}
    </StatusPill>,
    <StatusPill
      key="breadth"
      tone={expressionBreadthTone(f.expression_breadth)}
      size="sm"
      title={
        "Synthesizer's rollup of cross-tissue expression: pan_tissue (most " +
        "tissues), broad (>half), restricted (a few), rare (one or two)."
      }
    >
      breadth · {prettyEnum(f.expression_breadth)}
    </StatusPill>,
    // Overexpression-with-surface-readout precedent — derived from
    // method observations. Lets a reader filter for "OE validation has
    // been done on this protein" without joining back to the methods
    // block.
    <StatusPill
      key="oe_observed"
      tone={
        f.overexpression_surface_localization_observed ? "success" : "neutral"
      }
      size="sm"
      title={TT_OE_OBSERVED}
    >
      <span aria-hidden="true">
        {f.overexpression_surface_localization_observed ? "✓" : "✗"}
      </span>{" "}
      Overexpression precedent
    </StatusPill>,
  ];
}

function buildRiskChips(rec: SurfaceomeRecord): React.ReactNode[] {
  const f = rec.filters;
  return [
    riskBoolPill("shed form", f.has_shed_form),
    riskBoolPill("secreted form", f.has_secreted_form),
    // Low endogenous expression — derived from expression_level; grouped
    // here as a risk (low / absent baseline expression makes a harder
    // target / orphan-class candidate). true = risk = red.
    <StatusPill
      key="lowendog"
      tone={f.low_endogenous_expression ? "danger" : "success"}
      size="sm"
      title={TT_LOW_ENDOG}
    >
      <span aria-hidden="true">
        {f.low_endogenous_expression ? "✓" : "✗"}
      </span>{" "}
      low endogenous expression
    </StatusPill>,
    riskBoolPill("epitope masking", f.has_epitope_masking),
  ];
}

const BUILDERS: Record<
  FeatureCategory,
  (rec: SurfaceomeRecord) => React.ReactNode[]
> = {
  biology: buildBiologyChips,
  expression: buildExpressionChips,
  risks: buildRiskChips,
};

interface FeatureChipsProps {
  category: FeatureCategory;
  rec: SurfaceomeRecord;
}

/**
 * Renders the chip row for one feature category at the top of its tab's
 * card. The `data-feature-chips={category}` attribute is the runtime
 * half of the chip↔tab connection — the section that wraps this row
 * carries the matching `data-section-id={category}`, and
 * `viewer/tests/verify_feature_tabs.py` asserts the two line up.
 */
export function FeatureChips({ category, rec }: FeatureChipsProps) {
  const pills = BUILDERS[category](rec).filter((p) => p != null);
  return (
    <ul
      className={styles.pills}
      data-feature-chips={category}
      aria-label={`${FEATURE_TAB_LABEL[category]} summary chips`}
    >
      {pills.map((p, i) => (
        <li key={i}>{p}</li>
      ))}
    </ul>
  );
}
