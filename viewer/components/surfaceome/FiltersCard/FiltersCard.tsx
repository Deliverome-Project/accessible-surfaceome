import type { OrthologEntry, SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./FiltersCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

// ---------------------------------------------------------------------------
// Polarity tones — green = positive, amber = mid, red = negative.
//
// Each chip in the filters card carries a "what does it MEAN to a
// target-discovery reader" judgment. For a risk bool, true is bad; for
// a positive bool, true is good. For a graded value (expression_level,
// ortholog identity, evidence_grade), the band determines the tone.
// ---------------------------------------------------------------------------

type Tone = "success" | "warn" | "danger" | "neutral" | "teal" | "lavender" | "amber";

/** Risk boolean — ``true`` = risk present = red. */
function riskBoolPill(label: string, value: boolean) {
  return (
    <StatusPill tone={value ? "danger" : "success"} size="sm">
      <span aria-hidden="true">{value ? "✓" : "✗"}</span> {label}
    </StatusPill>
  );
}

/** Positive boolean — ``true`` = good = green. */
function positiveBoolPill(label: string, value: boolean) {
  return (
    <StatusPill tone={value ? "success" : "neutral"} size="sm">
      <span aria-hidden="true">{value ? "✓" : "✗"}</span> {label}
    </StatusPill>
  );
}

// --- graded-value tone mappers ---------------------------------------

function accessibilityTone(v: string): Tone {
  return v === "high" ? "success" : v === "moderate" ? "warn" : v === "low" ? "danger" : "neutral";
}

function confidenceTone(v: string): Tone {
  return v === "high" ? "success" : v === "moderate" ? "warn" : v === "low" ? "danger" : "neutral";
}

function evidenceGradeTone(v: string): Tone {
  if (v === "direct_multi_method" || v === "direct_single_method") return "success";
  if (v === "supportive_but_indirect") return "warn";
  if (v === "conflicting" || v === "weak") return "danger";
  return "neutral";
}

function ecdAccessibilityTone(v: string): Tone {
  if (v === "large" || v === "moderate") return "success";
  if (v === "small") return "warn";
  if (v === "minimal" || v === "none") return "danger";
  return "neutral";
}

function evidenceDensityTone(v: string): Tone {
  return v === "high" ? "success" : v === "moderate" ? "warn" : v === "low" ? "danger" : "neutral";
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

function surfaceSpecificityTone(v: string): Tone {
  if (v === "surface_dominant") return "success";
  if (v === "mixed") return "warn";
  if (v === "mostly_intracellular") return "danger";
  return "neutral";
}

/**
 * State dependence — low is best (constitutive surface presence),
 * high is worst (only-in-cancer / only-on-activation / only-in-stress
 * conditionality). Mirror of executive_summary.state_dependence.
 */
function stateDependenceTone(v: string): Tone {
  if (v === "low") return "success";
  if (v === "moderate") return "warn";
  if (v === "high") return "danger";
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

/**
 * Surface_call_reason — synth-derived reason, 19 values. We color by
 * verdict-bucket: YES-bucket (canonical surface receptors etc) = success,
 * CONTEXTUAL-bucket (state-gated mechanisms) = lavender, NO-bucket
 * (cytoplasmic / nuclear / inner-leaflet etc) = danger when paired
 * with a low / no accessibility call.
 */
const YES_BUCKET_REASONS = new Set([
  "classical_surface_receptor",
  "gpi_anchored",
  "multipass_with_exposed_loops",
  "extracellular_face_protein",
  "stable_complex_partner",
]);
const CONTEXTUAL_BUCKET_REASONS = new Set([
  "cell_state_induced",
  "tissue_restricted_surface",
  "lysosomal_exocytosis",
  "dual_localization",
  "stable_surface_attachment",
]);
const NO_BUCKET_REASONS = new Set([
  "cytoplasmic",
  "nuclear",
  "mitochondrial_internal",
  "endomembrane_resident",
  "nuclear_envelope",
  "inner_leaflet_anchored",
  "secreted_only",
  "pmhc_only_intracellular",
]);
function surfaceCallReasonTone(v: string): Tone {
  if (YES_BUCKET_REASONS.has(v)) return "success";
  if (CONTEXTUAL_BUCKET_REASONS.has(v)) return "lavender";
  if (NO_BUCKET_REASONS.has(v)) return "danger";
  return "neutral"; // 'other' or unrecognized
}

/**
 * Ortholog ECD identity tone — higher conservation is BETTER (mouse /
 * cyno literature can stand in for human evidence). Thresholds from PR
 * #23 design + ICH S6(R1) biologics-development practice.
 */
function orthologIdentityTone(pct: number | null): Tone {
  if (pct == null) return "neutral";
  if (pct >= 85) return "success";
  if (pct >= 60) return "warn";
  return "danger";
}

/**
 * Paralog max-ECD-identity tone — higher identity is WORSE (more
 * potential antibody cross-reactivity). Inverse polarity from the
 * ortholog scale. Thresholds from Bordeaux et al. 2010 / Edfors et al.
 * 2018 antibody-validation literature.
 */
function paralogIdentityTone(pct: number | null): Tone {
  if (pct == null) return "success"; // no paralogs in the family = no cross-reactivity risk
  if (pct < 50) return "success";
  if (pct < 70) return "warn";
  return "danger";
}

/**
 * Build the ortholog pill label + tone. Handles the ECD-less case
 * (SRC, soluble proteins, GPI-anchored) by falling back to BioMart
 * full-length identity — preserves the chip's signal when the
 * human protein has no ECD to compare. Color polarity comes from
 * :func:`orthologIdentityTone` (higher = better).
 */
function orthologPillLabel(
  ecdPct: number | null,
  entries: OrthologEntry[],
): { text: string; tone: Tone; title?: string } {
  if (ecdPct != null) {
    return { text: `${ecdPct.toFixed(1)}% ECD`, tone: orthologIdentityTone(ecdPct) };
  }
  if (entries.length === 0) {
    return { text: "no Compara ortholog", tone: "neutral" };
  }
  // Ortholog exists, but no ECD to compare — fall back to full-length identity.
  const canonical = entries.find((e) => e.is_canonical) ?? entries[0];
  const fullPct = canonical.full_length_pct_identity_to_human_canonical;
  return {
    text: fullPct != null ? `${fullPct.toFixed(1)}% full-length (no ECD)` : "ortholog · no ECD",
    tone: orthologIdentityTone(fullPct),
    title:
      "Human protein has no ECD to compare (e.g. inner-leaflet, soluble, GPI-anchored). Showing full-length BioMart % identity instead.",
  };
}

// ---------------------------------------------------------------------------
// Tooltip rationale — surfaced via the StatusPill `title` prop on
// every chip whose tone / class is bounded by a numeric or
// literature-derived threshold. Sourced from the synthesizer prompt's
// own threshold rationale; keeping the strings here lets the viewer
// stay readable without re-deriving the rationale per render.
//
// When the underlying threshold changes (in either the Pydantic
// schema or the synthesizer prompt), update the string here AND the
// upstream source so the chip's tooltip stays honest.
// ---------------------------------------------------------------------------

const TT_ECD_CLASS =
  "ECD-size bands derived from antibody-antigen interface measurements " +
  "(Ramaraj et al. 2012, doi:10.1016/j.bbapap.2012.07.005 — average " +
  "conformational epitope = 12 ± 3 residues, 1103 ± 244 Å² buried). " +
  "large ≥ 200 residues (≥10 non-overlapping epitopes possible); " +
  "moderate = 60-199 (multiple epitopes, e.g. tetraspanin EC2 loops); " +
  "small = 30-59 (2-5 candidate epitopes, harder discovery); " +
  "minimal < 30 (1-2 epitopes max, specialized formats needed); " +
  "none = no surface-exposed ECD (GPI / inner-leaflet).";

const TT_EVIDENCE_DENSITY =
  "Bucketed evidence row count: high ≥ 30 supporting rows, " +
  "moderate ≥ 10, low < 10. Derived in the orchestrator from " +
  "the merged A1+A2 ledger; deterministic, not LLM-judged.";

const TT_ORTHOLOG_ID =
  "ECD % identity to the human canonical, restricted to " +
  "extracellular residues. Cutoffs from ICH S6(R1) biologics-" +
  "preclinical-development practice: ≥85% = strong pharmacological " +
  "translation (mouse / cyno can stand in for human evidence); " +
  "60-85% = use with caution; < 60% = species substitution unreliable.";

const TT_PARALOG_ID =
  "Highest ECD % identity across the gene's Compara paralogs — " +
  "antibody cross-reactivity risk. Cutoffs from antibody-validation " +
  "literature (Bordeaux et al. 2010 / Edfors et al. 2018): < 50% = " +
  "cross-reactivity unlikely; 50-70% = plausible (validate against " +
  "paralog-KO); ≥ 70% = likely (paralog-discrimination required).";

const TT_ACCESSIBILITY =
  "Synthesizer's headline call: high (clear surface presence across " +
  "multiple methods), moderate (one or two methods, or contested), " +
  "low (weak / state-dependent / mostly intracellular), uncertain " +
  "(insufficient evidence either way), no (confidently NOT at the " +
  "surface — distinct from uncertain).";

const TT_CONFIDENCE =
  "Synthesizer's confidence in its accessibility call. Required to " +
  "carry a non-empty `confidence_reasoning` (≤600 chars) whenever " +
  "this is moderate or low.";

const TT_EVIDENCE_GRADE =
  "A1 evidence-grade rollup, reflecting experimental-method " +
  "coverage: direct_multi_method (≥2 categories with " +
  "live-cell / non-perm methods); direct_single_method (one " +
  "category); supportive_but_indirect (fractionation / " +
  "glycoproteomics, no direct surface staining); conflicting / weak.";

const TT_EXPRESSION_LEVEL =
  "Synthesizer's rollup of endogenous expression. Drives the derived " +
  "`low_endogenous_expression` filter (fires when level ∈ {low, " +
  "absent}); affects whether overexpression-only evidence has to " +
  "carry the surface call.";

const TT_LOW_ENDOG =
  "Derived filter: true iff expression_level ∈ {low, absent}. " +
  "Single source of truth for the orphan-class catalog filter — " +
  "the orchestrator computes this from expression_level so the " +
  "two signals can't drift.";

const TT_KNOWN_LIGAND =
  "Orphan-receptor status. true (default) = validated endogenous " +
  "ligand documented in literature. false = orphan-class gene where " +
  "ligand identity is unknown (orphan GPCRs / NHRs / kinases). " +
  "Tractability signal for the catalog.";

const TT_TM_COUNT =
  "Transmembrane helix count from DeepTMHMM (deterministic). " +
  "Drives `subcategory` choice: 0 (soluble / inner-leaflet), 1 " +
  "(single-pass T1 or T2), 7 (GPCR), other counts (multi-pass / " +
  "transporters / ion channels).";

const TT_STATE_DEP =
  "Synthesizer's call: low (constitutive surface presence), moderate " +
  "(modestly state-gated — e.g. activation-dependent), high (only-in-" +
  "cancer / only-on-stress / only-on-activation surface presence — SRC " +
  "via cancer-state autophagolysosomal exocytosis is the canonical " +
  "case), unclear. Conditionality flag that rides alongside " +
  "surface_accessibility — a `high` accessibility call with " +
  "`high` state_dependence means the targetable state exists but " +
  "is state-gated.";

const TT_CO_RECEPTOR =
  "Co-receptor dependence of surface expression: none (protein " +
  "surfaces on its own), modulatory (partner influences but doesn't " +
  "gate surface presence), required (surface presence depends on a " +
  "partner — bispecific / partner-aware design may be needed), " +
  "unknown (ledger silent on partner interactions).";

const TT_CALL_REASON =
  "Synthesizer's reason for the surface call, re-derived from A1+A2 " +
  "evidence (NOT inherited from the triage's first-pass call). 19 " +
  "values across YES-bucket (canonical surface mechanisms), " +
  "CONTEXTUAL-bucket (state-gated mechanisms — `lysosomal_exocytosis` " +
  "etc), and NO-bucket (cytoplasmic / nuclear / inner-leaflet etc). " +
  "SRC: synth-derived `lysosomal_exocytosis` overrides the triage's " +
  "`inner_leaflet_anchored` baseline-state label.";

// ---------------------------------------------------------------------------


export function FiltersCard({ rec, n }: Props) {
  const f = rec.filters;
  const topo = rec.deterministic_features.canonical_topology;
  const orthos = rec.deterministic_features.orthologs;
  const mousePill = orthologPillLabel(f.mouse_ortholog_ecd_pct_identity, orthos.mouse);
  const cynoPill = orthologPillLabel(f.cyno_ortholog_ecd_pct_identity, orthos.cynomolgus);
  const groups = [
    {
      label: "Accessibility",
      pills: [
        <StatusPill
          key="acc"
          tone={accessibilityTone(f.surface_accessibility)}
          size="sm"
          title={TT_ACCESSIBILITY}
        >
          overall · {prettyEnum(f.surface_accessibility)}
        </StatusPill>,
        <StatusPill
          key="conf"
          tone={confidenceTone(f.confidence)}
          size="sm"
          title={TT_CONFIDENCE}
        >
          conf · {prettyEnum(f.confidence)}
        </StatusPill>,
        <StatusPill
          key="state_dep"
          tone={stateDependenceTone(f.state_dependence)}
          size="sm"
          title={TT_STATE_DEP}
        >
          state dep · {prettyEnum(f.state_dependence)}
        </StatusPill>,
        <StatusPill
          key="reason"
          tone={surfaceCallReasonTone(f.surface_call_reason)}
          size="sm"
          title={TT_CALL_REASON}
        >
          reason · {prettyEnum(f.surface_call_reason)}
        </StatusPill>,
        <StatusPill
          key="coreceptor"
          tone={coReceptorDependencyTone(f.co_receptor_dependency)}
          size="sm"
          title={TT_CO_RECEPTOR}
        >
          co-receptor · {prettyEnum(f.co_receptor_dependency)}
        </StatusPill>,
        <StatusPill
          key="sub"
          tone="neutral"
          size="sm"
          title={
            "Architecture (how the protein sits in the membrane): " +
            "single_pass_T1/T2, multi_pass, GPCR (7TM), GPI_anchored, " +
            "tetraspanin, other. Orthogonal to the `family` axis below."
          }
        >
          arch · {prettyEnum(f.subcategory)}
        </StatusPill>,
        <StatusPill
          key="fam"
          tone="lavender"
          size="sm"
          title={
            "Functional family per SURFACE-Bind (Marchand 2026 PNAS, " +
            "doi:10.1073/pnas.2506269123). receptor = GPCRs/RTKs/cytokine " +
            "receptors; enzyme = surface peptidases / ectonucleotidases / " +
            "kinases-by-identity; transporter = SLCs / ABC / channels / " +
            "aquaporins; miscellaneous = adhesion / junction / tetraspanin " +
            "/ scaffold / chaperone / structural."
          }
        >
          family · {prettyEnum(f.protein_family)}
        </StatusPill>,
        <StatusPill
          key="grade"
          tone={evidenceGradeTone(f.evidence_grade)}
          size="sm"
          title={TT_EVIDENCE_GRADE}
        >
          {prettyEnum(f.evidence_grade)}
        </StatusPill>,
        <StatusPill
          key="ecd"
          tone={ecdAccessibilityTone(f.ecd_accessibility_class)}
          size="sm"
          title={TT_ECD_CLASS}
        >
          ECD · {prettyEnum(f.ecd_accessibility_class)}
        </StatusPill>,
        <StatusPill
          key="dens"
          tone={evidenceDensityTone(f.evidence_density)}
          size="sm"
          title={TT_EVIDENCE_DENSITY}
        >
          evidence · {prettyEnum(f.evidence_density)}
        </StatusPill>,
      ],
    },
    {
      label: "Expression",
      pills: [
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
          {prettyEnum(f.surface_specificity)}
        </StatusPill>,
        // Derived from `expression_level`; appears here so the
        // catalog filter the orphan-class story uses is visible
        // next to the source it's computed from.
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
        // Orphan-receptor status — replaces the dropped
        // `HeadlineRisk.ligand_unknown` value.
        <StatusPill
          key="ligand"
          tone={f.has_known_ligand ? "success" : "danger"}
          size="sm"
          title={TT_KNOWN_LIGAND}
        >
          <span aria-hidden="true">
            {f.has_known_ligand ? "✓" : "✗"}
          </span>{" "}
          known ligand
        </StatusPill>,
      ],
    },
    {
      label: "Risks",
      pills: [
        riskBoolPill("shed form", f.has_shed_form),
        riskBoolPill("secreted form", f.has_secreted_form),
        riskBoolPill("co-receptor required for expression", f.requires_coreceptor_for_expression),
        riskBoolPill("epitope masking", f.has_epitope_masking),
        riskBoolPill("restricted subdomain", f.has_restricted_subdomain),
      ],
    },
    {
      label: "Cross-species (deterministic — higher conservation is better)",
      pills: [
        <StatusPill
          key="m"
          tone={mousePill.tone}
          size="sm"
          // `mousePill.title` is the per-row note ("no Compara
          // ortholog", "fell back to full-length identity, etc.").
          // Stack the general-rationale tooltip behind it via a
          // newline so both are visible on hover.
          title={mousePill.title ? `${TT_ORTHOLOG_ID}\n\n${mousePill.title}` : TT_ORTHOLOG_ID}
        >
          mouse · {mousePill.text}
        </StatusPill>,
        <StatusPill
          key="c"
          tone={cynoPill.tone}
          size="sm"
          title={cynoPill.title ? `${TT_ORTHOLOG_ID}\n\n${cynoPill.title}` : TT_ORTHOLOG_ID}
        >
          cyno · {cynoPill.text}
        </StatusPill>,
      ],
    },
    {
      label: "Paralogs (deterministic — lower max identity is better)",
      pills: [
        f.max_paralog_ecd_pct_identity == null ? (
          <StatusPill
            key="p"
            tone="success"
            size="sm"
            title={`${TT_PARALOG_ID}\n\nNo paralogs in Compara — no within-family cross-reactivity risk.`}
          >
            no Compara paralogs
          </StatusPill>
        ) : (
          <StatusPill
            key="p"
            tone={paralogIdentityTone(f.max_paralog_ecd_pct_identity)}
            size="sm"
            title={TT_PARALOG_ID}
          >
            max %ECD identity · {f.max_paralog_ecd_pct_identity.toFixed(1)}%
          </StatusPill>
        ),
      ],
    },
    {
      label: "Topology (deterministic)",
      pills: [
        <StatusPill key="tm" tone="neutral" size="sm" title={TT_TM_COUNT}>
          {topo.tm_helix_count} TM
        </StatusPill>,
        positiveBoolPill("N-term extracellular", f.n_term_extracellular),
        positiveBoolPill("C-term extracellular", f.c_term_extracellular),
      ],
    },
    {
      label: "SURFACE-Bind (deterministic — Marchand 2026 PNAS)",
      // Three distinct states, each rendered explicitly so the reader
      // can tell them apart at a glance:
      //   1. not_in: SURFACE-Bind dropped the protein at structural QC
      //   2. scored_empty: in the table, but no patches cleared scoring
      //   3. scored_with_sites: real targetability data
      pills: (() => {
        const sb = rec.deterministic_features.surface_bind;
        if (!sb.has_data) {
          return [
            <StatusPill
              key="sb-not-in"
              tone="neutral"
              size="sm"
              title={
                "NOT in SURFACE-Bind's dataset. SURFACE-Bind filtered " +
                "this protein out during structural-quality screening — " +
                "typically inner-leaflet anchors, soluble cytoplasmic " +
                "proteins, or poorly-modeled targets. Distinct from " +
                "'scored · no patches' (where the protein WAS scored)."
              }
            >
              not in SURFACE-Bind
            </StatusPill>,
          ];
        }
        if (sb.n_sites === 0) {
          return [
            <StatusPill
              key="sb-scored-empty"
              tone="amber"
              size="sm"
              title={
                "Scored by SURFACE-Bind but no surface patches cleared " +
                "the MaSIF targetability threshold. The protein is in " +
                "SURFACE-Bind's authoritative table; the surface " +
                "chemistry just didn't yield designable binder seeds. " +
                "Distinct from 'not in SURFACE-Bind' (where the " +
                "protein was filtered out before scoring)."
              }
            >
              scored · no patches
            </StatusPill>,
          ];
        }
        return [
          <StatusPill
            key="sb-sites"
            tone="success"
            size="sm"
            title={
              "Number of MaSIF-scored targetable surface patches. " +
              "Each site is a region where SURFACE-Bind's patch scoring " +
              "identified geometric / chemical features compatible with " +
              "a de novo binder. Higher = more design flexibility."
            }
          >
            {sb.n_sites} sites
          </StatusPill>,
          <StatusPill
            key="sb-alpha"
            tone="teal"
            size="sm"
            title={
              "Total α-helical binder candidate seeds aligned across all " +
              "sites — SURFACE-Bind's continuous-fragment library docked " +
              "to the surface patches and ranked by MaSIF score."
            }
          >
            {sb.n_seeds_alpha.toLocaleString()} α-seeds
          </StatusPill>,
          <StatusPill
            key="sb-beta"
            tone="teal"
            size="sm"
            title={
              "Total β-strand binder candidate seeds aligned across all " +
              "sites. β-strand binders are typically the harder design " +
              "target; high counts here mean the surface has β-favorable " +
              "patches."
            }
          >
            {sb.n_seeds_beta.toLocaleString()} β-seeds
          </StatusPill>,
        ];
      })(),
    },
  ];

  return (
    <SectionCard
      n={n}
      eyebrow="Summary metrics"
      title="At-a-glance signal panel"
      meta="D1-indexed facets · same fields the catalog filters on, rolled up per gene"
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
