import type { OrthologEntry, SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { tooltips } from "../../../lib/tooltips";
import { InfoTip } from "../../InfoTip/InfoTip";
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

function ecdAccessibilityTone(v: string): Tone {
  if (v === "large" || v === "moderate") return "success";
  if (v === "small") return "warn";
  if (v === "minimal" || v === "none") return "danger";
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
  "(Ramaraj et al. 2012, PMID:22246133, doi:10.1016/j.bbapap.2011.12.007 — average " +
  "conformational epitope = 12 ± 3 residues, 1103 ± 244 Å² buried). " +
  "large ≥ 200 residues (≥10 non-overlapping epitopes possible); " +
  "moderate = 60-199 (multiple epitopes, e.g. tetraspanin EC2 loops); " +
  "small = 30-59 (2-5 candidate epitopes, harder discovery); " +
  "minimal < 30 (1-2 epitopes max, specialized formats needed); " +
  "none = no surface-exposed ECD (GPI / inner-leaflet).";

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

const TT_EXPRESSION_LEVEL =
  "How abundantly this protein is expressed at baseline in the tissues " +
  "and cell lines covered by the cited evidence.";

const TT_LOW_ENDOG =
  "Flags proteins where baseline endogenous expression is low or " +
  "absent. These targets typically need overexpression-based studies " +
  "(HEK293 / HeLa / U2OS transfection) to characterize surface " +
  "biology, and antibody / binder validation in endogenous tissues " +
  "is harder because there's little protein to stain or bind in " +
  "untransfected controls.";

const TT_CORECEPTOR =
  "LLM-driven. Whether the protein needs a partner to reach the surface. " +
  "None = surfaces on its own; modulatory = a partner influences but " +
  "doesn't gate surface presence; required = surface presence depends on " +
  "a partner (a bispecific or partner-aware design may be needed); " +
  "unknown = the agent found no information either way.";

const TT_KNOWN_LIGAND =
  "Has the synthesizer found a documented binding partner / ligand " +
  "for this protein in literature? true = yes (e.g. EGFR ← EGF; " +
  "for kinases like SRC this also captures known substrates / " +
  "interaction partners since the 'ligand' framing is canonical " +
  "for receptors but loose for cytoplasmic kinases). false = " +
  "orphan-class — ligand identity is genuinely unknown (orphan " +
  "GPCRs / NHRs / true orphan kinases). The boolean is the " +
  "catalog filter; the specific ligand identity isn't stored on " +
  "the record — see §Biology for partner / co-receptor evidence.";

const TT_OE_OBSERVED =
  "Whether prior overexpression studies (HEK293 / HeLa / K562 / U2OS " +
  "transfection, stable or transient) have demonstrated surface " +
  "localization of this protein. Useful precedent when planning an " +
  "overexpression-based validation experiment — you know the " +
  "construct can reach the surface in a heterologous cell line. " +
  "Distinct from the orphan-receptor and low-endogenous flags " +
  "(those describe baseline biology; this one describes prior " +
  "experimental precedent).";

const TT_TM_COUNT =
  "Transmembrane helix count from DeepTMHMM (deterministic).";

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

// ---------------------------------------------------------------------------


export function FiltersCard({ rec, n }: Props) {
  const f = rec.filters;
  const topo = rec.deterministic_features.canonical_topology;
  const orthos = rec.deterministic_features.orthologs;
  const isoforms = rec.deterministic_features.isoform_topologies;
  // Total isoforms modeled (canonical + alternate isoform topologies
  // emitted by the DeepTMHMM build) and count of alt isoforms whose
  // per-residue topology string differs from canonical. The second
  // metric is the isoform-decoy heuristic — if alt isoforms expose a
  // different TM/SP arrangement and they express in target tissues,
  // they compete with the canonical for binder occupancy.
  const isoformTotal = 1 + isoforms.length;
  const distinctIsoCount = isoforms.filter(
    (iso) => iso.per_residue_topology !== topo.per_residue_topology,
  ).length;
  const mousePill = orthologPillLabel(f.mouse_ortholog_ecd_pct_identity, orthos.mouse);
  const cynoPill = orthologPillLabel(f.cyno_ortholog_ecd_pct_identity, orthos.cynomolgus);
  // Each group is tagged with `provenance` so the render can partition
  // groups under "LLM-driven" vs "Deterministic" section headings —
  // the same provenance split the GeneHeader vitals used to carry
  // (now removed, since surfacing it twice was redundant). The
  // ordering inside each provenance section follows the original
  // group order so readers' eye doesn't have to re-learn the layout.
  const groups: { label: string; provenance: "llm" | "deterministic"; pills: React.ReactNode[] }[] = [
    // The "Accessibility" umbrella group was retired — the headline
    // accessibility / confidence / state_dependence chips already
    // render in the executive-summary chip strip up top, so showing
    // them twice was noise.
    //
    // The "Evidence" group was retired: the "Experimental surface
    // evidence" vital up top carries `evidence_grade`, and
    // `surface_call_reason` / `evidence_density` live in the catalog
    // filters — duplicating them per-gene here was noise.
    {
      // General descriptive attributes (not risks, not expression
      // levels): ligand / orphan status, surface-vs-intracellular split,
      // co-receptor dependence, restricted-subdomain access. Placed
      // before Expression per user request.
      label: "Attributes",
      provenance: "llm",
      pills: [
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
          {prettyEnum(f.surface_specificity)}
        </StatusPill>,
        <StatusPill
          key="coreceptor"
          tone={coReceptorDependencyTone(f.co_receptor_dependency)}
          size="sm"
          title={TT_CORECEPTOR}
        >
          co-receptor · {prettyEnum(f.co_receptor_dependency)}
        </StatusPill>,
        riskBoolPill("restricted subdomain", f.has_restricted_subdomain),
      ],
    },
    {
      label: "Expression",
      provenance: "llm",
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
        // Overexpression-with-surface-readout precedent — derived
        // from method observations. Lets a reader filter for "OE
        // validation has been done on this protein" without joining
        // back to the methods block. Renders here next to the other
        // expression-evidence pills so the cluster reads as one row.
        <StatusPill
          key="oe_observed"
          tone={f.overexpression_surface_localization_observed ? "success" : "neutral"}
          size="sm"
          title={TT_OE_OBSERVED}
        >
          <span aria-hidden="true">
            {f.overexpression_surface_localization_observed ? "✓" : "✗"}
          </span>{" "}
          Overexpression precedent
        </StatusPill>,
      ],
    },
    {
      label: "Risks",
      provenance: "llm",
      pills: [
        riskBoolPill("shed form", f.has_shed_form),
        riskBoolPill("secreted form", f.has_secreted_form),
        // Low endogenous expression — derived from expression_level;
        // grouped here as a risk (low / absent baseline expression makes
        // a harder target / orphan-class candidate). true = risk = red.
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
      ],
    },
    {
      // Topology was previously the third deterministic group;
      // promoted to first under user request so the structural
      // priors (TM count, isoform variety, ECD class) read BEFORE
      // the homology rollups (Cross-species / Paralogs) that ride
      // on top of them. Order: Topology → Cross-species → Paralogs
      // → Candidate sites.
      label: "Topology",
      provenance: "deterministic",
      pills: [
        <StatusPill key="tm" tone="neutral" size="sm" title={TT_TM_COUNT}>
          {topo.tm_helix_count} TM
        </StatusPill>,
        positiveBoolPill("N-term extracellular", f.n_term_extracellular),
        positiveBoolPill("C-term extracellular", f.c_term_extracellular),
        // Isoform-decoy heuristic — total isoforms modeled + how
        // many of those alt isoforms expose a topology distinct
        // from canonical. If alt isoforms expose a soluble or
        // differently-anchored form AND express in target tissues,
        // they compete with the canonical surface form for binder
        // occupancy. Surfaces the §02 Surface-Bind / §04 Isoforms
        // detail at-a-glance.
        <StatusPill key="iso-count" tone="neutral" size="sm">
          {isoformTotal} isoform{isoformTotal === 1 ? "" : "s"}
        </StatusPill>,
        isoforms.length > 0 ? (
          <StatusPill
            key="iso-distinct"
            tone={distinctIsoCount > 0 ? "amber" : "success"}
            size="sm"
            title={
              "Number of alternate isoforms whose per-residue topology " +
              "differs from canonical. >0 = isoform-decoy risk: an " +
              "alternate isoform exposes a different TM/SP arrangement " +
              "and may compete with the canonical surface form for " +
              "binder occupancy (the §Risks card details the strength)."
            }
          >
            {distinctIsoCount} distinct topology
          </StatusPill>
        ) : null,
        // ECD accessibility class — derived from ECD length, so it
        // belongs alongside the other topology rollups (was in the
        // retired Accessibility group, now moved here so the size /
        // shape / orientation signals all live in one place).
        <StatusPill
          key="ecd"
          tone={ecdAccessibilityTone(f.ecd_accessibility_class)}
          size="sm"
          title={TT_ECD_CLASS}
        >
          ECD · {prettyEnum(f.ecd_accessibility_class)}
        </StatusPill>,
      ],
    },
    {
      label: "Cross-species",
      provenance: "deterministic",
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
      label: "Paralogs",
      provenance: "deterministic",
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
      // Was "SURFACE-Bind"; reader-facing label is now "Candidate
      // sites" — names the metric (per-protein count of MaSIF-scored
      // targetable surface patches) rather than the toolchain. Pill
      // text + tooltips still cite SURFACE-Bind / MaSIF for
      // provenance, and the group label metadata below carries the
      // SURFACE-Bind + Balbi et al links.
      label: "Candidate sites",
      provenance: "deterministic",
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

  // ------------------------------------------------------------
  // Per-group label metadata. Was a single string; now carries:
  //   * ``title`` — tooltip explaining what the group measures + the
  //     cutoffs / source / interpretation. Surfaces the rationale
  //     that previously lived only in the parenthetical (which the
  //     user said wasn't doing enough work).
  //   * ``links`` — outbound links to the underlying data source for
  //     deterministic groups (Ensembl Compara, DeepTMHMM,
  //     SURFACE-Bind). Synth-emitted groups have no external source
  //     to link to.
  // Keyed on the group's short label below so the data stays paired
  // and the JSX render is uncluttered.
  // ------------------------------------------------------------
  const GROUP_META: Record<
    string,
    { title: string; links?: { href: string; label: string }[] }
  > = {
    Accessibility: {
      title:
        "Synthesizer rollups of the accessibility verdict + supporting " +
        "structured signals (surface_accessibility, confidence, " +
        "state_dependence, surface_call_reason, evidence_grade, " +
        "ECD-size class, evidence density). Same fields the catalog " +
        "filters on.",
    },
    // No "Expression" entry — per user feedback the Expression group
    // carries NO category-wide InfoTip. Each Expression chip (level /
    // breadth / specificity / low-endogenous / known-ligand /
    // OE-precedent) already has its own specific tooltip, so a
    // group-level summary tip was redundant. Cross-species / Paralogs /
    // Topology / Candidate-sites keep their group tips because those
    // carry cutoff/threshold provenance not repeated on each chip.
    Risks: {
      title:
        "Things that can complicate antibody / binder access to the " +
        "surface protein. Shed form (proteolytically cleaved soluble " +
        "fragment in circulation that competes for the binder), " +
        "secreted form (free-soluble decoy pool), co-receptor " +
        "dependence (whether surface presentation requires a partner " +
        "protein), epitope masking (steric or PTM-mediated blockage " +
        "of likely binding sites on the surface). Each chip has its " +
        "own tooltip; the §Risks card below shows supporting " +
        "evidence with severity + evidence-strength.",
    },
    "Cross-species": {
      title:
        "Mouse + cynomolgus ortholog %ECD identity to the human " +
        "canonical (or full-length fallback when the human protein " +
        "has no ECD). Cutoffs from ICH S6(R1) biologics-preclinical " +
        "practice: ≥85% = strong pharmacological translation; " +
        "60-85% = use with caution; <60% = species substitution " +
        "unreliable. Source: Ensembl Compara.",
      links: [
        { href: "https://www.ensembl.org/info/genome/compara/index.html", label: "Ensembl Compara" },
      ],
    },
    Paralogs: {
      title:
        "Highest ECD %identity across the gene's Compara paralogs — " +
        "the antibody cross-reactivity risk. Cutoffs from antibody-" +
        "validation literature (Bordeaux 2010 / Edfors 2018): <50% = " +
        "cross-reactivity unlikely; 50-70% = plausible (validate " +
        "against paralog-KO); ≥70% = likely (paralog-discrimination " +
        "required).",
      links: [
        { href: "https://www.ensembl.org/info/genome/compara/index.html", label: "Ensembl Compara" },
      ],
    },
    Topology: {
      title:
        "DeepTMHMM-predicted membrane topology for the canonical " +
        "isoform: TM helix count + which termini face the " +
        "extracellular vs intracellular side + ECD-size accessibility " +
        "class (large / moderate / small / minimal / none — derived " +
        "from ECD residue length per the Ramaraj 2012 antibody-epitope " +
        "thresholds). Drives the subcategory axis (single_pass_T1 / " +
        "multi_pass / GPCR / etc.).",
      links: [
        { href: "https://dtu.biolib.com/DeepTMHMM", label: "DeepTMHMM" },
      ],
    },
    "Candidate sites": {
      title:
        "SURFACE-Bind (Correia lab, Balbi et al. 2026, PMID 41604262, " +
        "PNAS) scores extracellular surface patches for designability " +
        "by de novo protein binders. Each candidate site is a region " +
        "where SURFACE-Bind's MaSIF model identified geometric / " +
        "chemical features compatible with a designable binder. " +
        "Three pill states: 'not in' = the protein was filtered at " +
        "structural QC before scoring (typically inner-leaflet anchors " +
        "or soluble cytoplasmic proteins); 'scored · no patches' = the " +
        "protein was scored but no patches cleared the MaSIF " +
        "targetability threshold; 'N sites · M seeds' = real " +
        "targetability data, where α-seeds = α-helical binder " +
        "candidates and β-seeds = β-strand binder candidates.",
      links: [
        { href: "https://surface-bind.inria.fr/", label: "SURFACE-Bind" },
        {
          // PubMed PMID 41604262 — same source the 3D viewer's
          // sites-mode caption cites. Author + year format
          // mirrored across both surfaces.
          href: "https://pubmed.ncbi.nlm.nih.gov/41604262/",
          label: "Balbi et al · 2026",
        },
      ],
    },
  };

  // Partition into LLM-driven vs Deterministic so the render can
  // emit two section headings with the right groups under each.
  // Order within each provenance bucket = original groups[] order.
  const llmGroups = groups.filter((g) => g.provenance === "llm");
  const detGroups = groups.filter((g) => g.provenance === "deterministic");

  const renderGroup = (g: (typeof groups)[number]) => {
    const meta = GROUP_META[g.label];
    return (
      <div key={g.label} className={styles.group}>
        <p className={`label-mono ${styles.groupLabel}`}>
          <span>{g.label}</span>
          {/* InfoTip with the same prose the native title carried
              before — but readable on click instead of fleeting on
              hover. Spells out the cutoffs + rationale (Cross-species
              %ID bands, Paralog %ECD bands, SURFACE-Bind state
              definitions) so the reader doesn't have to guess what
              moderate / high mean per group. */}
          {meta?.title ? (
            <InfoTip wide label={`About ${g.label}`}>
              {meta.title}
            </InfoTip>
          ) : null}
          {meta?.links?.map((l) => (
            <a
              key={l.href}
              href={l.href}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.groupLink}
              title={`Open ${l.label} in a new tab`}
            >
              {l.label} ↗
            </a>
          ))}
        </p>
        <ul className={styles.pills}>
          {g.pills
            // Drop any nulls before rendering — some groups
            // conditionally include pills (e.g. the topology
            // "N distinct topology" pill only renders when alt
            // isoforms exist). Without this filter an empty <li>
            // renders for each null entry.
            .filter((p) => p != null)
            .map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <SectionCard
      n={n}
      eyebrow="Summary metrics"
      title="At-a-glance signal panel"
      meta="Fields available for catalog-level filtering · rolled up per gene"
    >
      {/* Provenance section heading — synthesizer rollups. Mirror
       *  of the old GeneHeader eyebrow that was removed when the
       *  duplicate Deterministic vital row got cut. */}
      <p className={`label-mono ${styles.provenanceHeading}`}>LLM-driven</p>
      <div className={styles.groups}>{llmGroups.map(renderGroup)}</div>

      {/* Provenance section heading — deterministic-tool readouts.
       *  DeepTMHMM topology, AlphaFold pLDDT (via the SURFACE-Bind
       *  block + isoform cards), Ensembl Compara orthologs +
       *  paralogs, MaSIF / SURFACE-Bind targetability. */}
      <p className={`label-mono ${styles.provenanceHeading}`}>Deterministic</p>
      <div className={styles.groups}>{detGroups.map(renderGroup)}</div>
    </SectionCard>
  );
}
