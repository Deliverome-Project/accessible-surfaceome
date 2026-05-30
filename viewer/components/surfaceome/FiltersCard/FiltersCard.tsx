import {
  CITATIONS,
  pubmedUrl,
  TYPICAL_ANTIBODY_INTERFACE_A2,
} from "../../../lib/citations";
import { ecSites } from "../../../lib/surface-bind";
import { ChipLabelValue } from "../ChipLabelValue/ChipLabelValue";
import type { OrthologEntry, SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { cellStateTriggerDesc } from "../../../lib/enums";
import { tooltips } from "../../../lib/tooltips";
import { InfoTip } from "../../InfoTip/InfoTip";
import {
  buildFeatureChips,
  FEATURE_CATEGORIES,
  FEATURE_TAB_LABEL,
} from "../FeatureChips/FeatureChips";
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

/** Positive boolean — ``true`` = good = green. Rendered as a
 *  `label · YES/NO` chip (shared label·value style) instead of a ✓/✗
 *  glyph. */
function positiveBoolPill(label: string, value: boolean) {
  return (
    <StatusPill tone={value ? "success" : "neutral"} size="sm">
      <ChipLabelValue label={label} value={value ? "yes" : "no"} />
    </StatusPill>
  );
}

// --- UniProt SIMILARITY family parser --------------------------------
//
// UniProt's curated family classification is a period-separated path
// where each segment is suffixed with its rank word, e.g. EGFR:
//   "protein kinase superfamily. Tyr protein kinase family. EGF receptor subfamily"
// → superfamily "protein kinase" / family "Tyr protein kinase" /
//   subfamily "EGF receptor". Depth is variable: single-level strings
// ("claudin family") yield one entry. We split on ". ", classify each
// segment by its trailing rank word, and strip that word so the chip
// shows the rank as its key and the bare name as its value.

type UniprotFamilyLevel = "superfamily" | "family" | "subfamily";

function parseUniprotFamily(
  raw: string,
): { level: UniprotFamilyLevel; name: string }[] {
  return raw
    .split(/\.\s+/)
    .map((seg) => seg.trim())
    .filter(Boolean)
    .map((seg) => {
      // Order matters: "superfamily" / "subfamily" both end in "family",
      // so test the more specific suffixes first.
      if (/\s*superfamily$/i.test(seg)) {
        const name = seg.replace(/\s*superfamily$/i, "").trim();
        return { level: "superfamily" as const, name: name || seg };
      }
      if (/\s*subfamily$/i.test(seg)) {
        const name = seg.replace(/\s*subfamily$/i, "").trim();
        return { level: "subfamily" as const, name: name || seg };
      }
      if (/\s*family$/i.test(seg)) {
        const name = seg.replace(/\s*family$/i, "").trim();
        return { level: "family" as const, name: name || seg };
      }
      // Defensive fallback: a segment with no recognized rank word keeps
      // its full text under the generic "family" rank. Every UniProt
      // SIMILARITY segment we've observed ends in one of the three words,
      // so this only guards against future/odd formatting.
      return { level: "family" as const, name: seg };
    });
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

// expressionLevelTone / expressionBreadthTone / surfaceSpecificityTone /
// coReceptorDependencyTone moved to FeatureChips.tsx with the chips that
// use them.

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
 * ortholog scale. Bands mirror the §07 "Paralog (specificity)" tier
 * (HPA antigen-design practice, PMID 33170010): >80% multitarget likely
 * (red), 60-80% caution (amber), <60% lower risk (green).
 */
function paralogIdentityTone(pct: number | null): Tone {
  if (pct == null) return "success"; // no paralogs in the family = no cross-reactivity risk
  if (pct > 80) return "danger";
  if (pct >= 60) return "warn";
  return "success";
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

// ECD-size class tooltip now lives in `lib/tooltips` as
// `catalog_ecd_class` — shared with the catalog so the Ramaraj footprint
// citation + the large/moderate/small/minimal bands stay identical.
// Ortholog + paralog tooltip bodies now live in `lib/tooltips`
// (`ortholog_species_relevance` / `paralog_specificity`) — the SAME
// nodes the §07 Isoforms card renders, so the cutoff bands + citations
// can't drift between the two surfaces. Reference `tooltips.*` below.

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

// TT_EXPRESSION_LEVEL / TT_LOW_ENDOG / TT_CORECEPTOR / TT_KNOWN_LIGAND /
// TT_OE_OBSERVED moved to FeatureChips.tsx along with the Biology /
// Expression / Risks chips they annotate.

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

const TT_UNIPROT_FAMILY =
  "UniProt's curated family classification, parsed from the Swiss-Prot " +
  "SIMILARITY annotation into its superfamily / family / subfamily " +
  "levels. Deterministic registry ground truth resolved from the " +
  "identifier bundle — NOT model output. Cross-check it against the " +
  "model's high-level Family call in the executive summary.";

const TT_HGNC_GROUP =
  "HGNC's curator-assigned gene group(s) for this gene — a gene can " +
  "belong to several. Deterministic registry ground truth resolved " +
  "from the identifier bundle — NOT model output. Cross-check it " +
  "against the model's high-level Family call in the executive summary.";

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
  // Deterministic registry families — curator-assigned classification
  // resolved from the identifier bundle (NOT model output). The UniProt
  // SIMILARITY string is split into superfamily / family / subfamily
  // subchips; HGNC gene groups are a flat list (no rank levels). The two
  // lists are concatenated into ONE "Family & gene group" bucket under the
  // §01 "Deterministic" heading (so the pills wrap in a single column
  // rather than claiming two), letting the reader cross-check the model's
  // high-level Family call (executive summary) against registry ground
  // truth. Empty list / null is common — the bucket is simply omitted when
  // both lists are empty rather than shown blank.
  const es = rec.executive_summary;
  // Deduped cell-state triggers — the "unique contexts" that gate surface
  // accessibility, echoed from §03 into the panel as chips.
  const modTriggers = Array.from(
    new Set(
      rec.biological_context.accessibility_modulation.flatMap((m) =>
        m.cell_state_trigger ? [m.cell_state_trigger] : [],
      ),
    ),
  );
  const uniprotFamilyPills: React.ReactNode[] = es.uniprot_family
    ? parseUniprotFamily(es.uniprot_family).map((seg, i) => (
        <StatusPill
          key={`uf-${i}`}
          tone="neutral"
          size="sm"
          title={TT_UNIPROT_FAMILY}
        >
          {/* Rank word ("superfamily"/"family"/"subfamily") stays at the
              base pill size and reads as the label; the family NAME renders
              1.5pt smaller (`.familyName`) so it sits one register quieter. */}
          {seg.level} · <span className={styles.familyName}>{seg.name}</span>
        </StatusPill>
      ))
    : [];
  // Guard with `?? []` (mirrors the `uniprot_family` ternary above): the
  // committed schema types `hgnc_gene_groups` as a non-optional string[],
  // but a served record can still omit it — a stale Worker/`.next` fetch
  // cache predating this field, a partially-synced public D1 mirror, or a
  // future schema move into `deterministic_features`. Without the guard a
  // missing field turns into a whole-page 500 (`.map` of undefined); with
  // it the section just drops the HGNC pills and the page still renders.
  const hgncFamilyPills: React.ReactNode[] = (es.hgnc_gene_groups ?? []).map(
    (group, i) => (
      <StatusPill key={`hg-${i}`} tone="neutral" size="sm" title={TT_HGNC_GROUP}>
        {/* HGNC gene groups carry no rank word, so the whole label is the
            name — render it at the same 1.5pt-smaller size as the UniProt
            family names so the merged bucket reads consistently. */}
        <span className={styles.familyName}>{group}</span>
      </StatusPill>
    ),
  );
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
    //
    // The LLM "Biology" / "Expression" / "Risks" chip groups live here
    // (PR #47) as the single at-a-glance home for the model's rollup
    // chips. PR #38 had promoted them out to three standalone tabs; per
    // user feedback the chips belong in the §01 signal panel, and each
    // tab now renders the per-chip RATIONALE (<FeatureRationales>)
    // instead. The chip builders are the shared source of truth in
    // components/surfaceome/FeatureChips/FeatureChips.tsx, so a panel
    // chip and its tab rationale can't drift.
    // Accessibility context — the §03 summary echoed into the
    // at-a-glance panel: the deep-dive's surface-call reason, state-
    // gating, primary compartment, and deduped modulation triggers. The
    // one-sentence rationale rides the group InfoTip (GROUP_META below).
    {
      label: "Accessibility context",
      provenance: "llm" as const,
      pills: [
        <StatusPill key="reason" tone="lavender" size="sm">
          <ChipLabelValue
            label="reason"
            value={prettyEnum(es.surface_call_reason)}
          />
        </StatusPill>,
        <StatusPill
          key="state"
          tone={stateDependenceTone(es.state_dependence)}
          size="sm"
        >
          <ChipLabelValue
            label="state-gated"
            value={prettyEnum(es.state_dependence)}
          />
        </StatusPill>,
        <StatusPill key="primary" tone="teal" size="sm">
          <ChipLabelValue
            label="primary"
            value={prettyEnum(
              rec.biological_context.subcellular_localization
                .primary_compartment,
            )}
          />
        </StatusPill>,
        ...modTriggers.map((t) => (
          <StatusPill
            key={`trig-${t}`}
            tone="amber"
            size="sm"
            title={cellStateTriggerDesc(t)}
          >
            <ChipLabelValue label="trigger" value={prettyEnum(t)} />
          </StatusPill>
        )),
      ],
    },
    ...FEATURE_CATEGORIES.map((cat) => ({
      label: FEATURE_TAB_LABEL[cat],
      provenance: "llm" as const,
      pills: buildFeatureChips(cat, rec).map((m) => m.pill),
    })),
    //
    // Registry families lead the deterministic block — protein
    // classification is identity-level context that frames the
    // structural priors (topology) and homology rollups that follow.
    // UniProt SIMILARITY levels (superfamily/family/subfamily) and HGNC
    // gene groups share ONE bucket so the two registry-classification
    // readouts read as a single column and the pills wrap together
    // instead of claiming two grid columns. Omitted entirely when
    // neither registry classifies the gene (both lists empty).
    ...(uniprotFamilyPills.length > 0 || hgncFamilyPills.length > 0
      ? [
          {
            label: "Family & gene group",
            provenance: "deterministic" as const,
            pills: [...uniprotFamilyPills, ...hgncFamilyPills],
          },
        ]
      : []),
    {
      // Topology was previously the third deterministic group;
      // promoted to first under user request so the structural
      // priors (TM count, isoform variety, ECD class) read BEFORE
      // the homology rollups (Paralogs / Cross-species) that ride
      // on top of them. Order: Topology → Paralogs → Cross-species
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
        <StatusPill
          key="isoforms"
          tone={distinctIsoCount > 0 ? "amber" : "neutral"}
          size="sm"
          title={
            isoforms.length > 0
              ? "Total isoform topology models (canonical + alternates), " +
                "with the count of alternates whose per-residue topology " +
                "differs from canonical. >0 distinct = isoform-decoy risk: " +
                "an alternate exposes a different TM/SP arrangement and may " +
                "compete with the canonical surface form for binder " +
                "occupancy (the §Risks card details the strength)."
              : undefined
          }
        >
          {isoformTotal} isoform{isoformTotal === 1 ? "" : "s"}
          {isoforms.length > 0
            ? ` · ${distinctIsoCount} distinct topology`
            : ""}
        </StatusPill>,
        // ECD accessibility class — derived from ECD length, so it
        // belongs alongside the other topology rollups (was in the
        // retired Accessibility group, now moved here so the size /
        // shape / orientation signals all live in one place).
        <StatusPill
          key="ecd"
          tone={ecdAccessibilityTone(f.ecd_accessibility_class)}
          size="sm"
          title={tooltips.catalog_ecd_class}
        >
          ECD · {prettyEnum(f.ecd_accessibility_class)}
        </StatusPill>,
      ],
    },
    {
      label: "Paralogs",
      provenance: "deterministic",
      pills: (() => {
        const paralogs = rec.deterministic_features.paralogs;
        if (paralogs.length === 0) {
          return [
            <StatusPill
              key="p-none"
              tone="success"
              size="sm"
              title={
                <>
                  {tooltips.paralog_specificity}
                  <br />
                  <br />
                  No paralogs in Compara — no within-family cross-reactivity
                  risk.
                </>
              }
            >
              no Compara paralogs
            </StatusPill>,
          ];
        }
        // Per-paralog specificity tier on ECD %identity (or full-length
        // when the protein has no ECD — ECD-less kinases / soluble
        // proteins still get a homology-based tier). Same §07 "Paralog
        // (specificity)" bands (HPA antigen-design practice, PMID
        // 33170010): >80% multitarget likely, 60-80% caution.
        const nMultitarget = paralogs.filter((p) => {
          const v = p.ecd_pct_identity ?? p.full_length_pct_identity;
          return v != null && v > 80;
        }).length;
        const nCaution = paralogs.filter((p) => {
          const v = p.ecd_pct_identity ?? p.full_length_pct_identity;
          return v != null && v >= 60 && v <= 80;
        }).length;
        const out: React.ReactNode[] = [];
        if (f.max_paralog_ecd_pct_identity != null) {
          out.push(
            <StatusPill
              key="p-max"
              tone={paralogIdentityTone(f.max_paralog_ecd_pct_identity)}
              size="sm"
              title={tooltips.paralog_specificity}
            >
              <ChipLabelValue
                label="max %ECD identity"
                value={`${f.max_paralog_ecd_pct_identity.toFixed(1)}%`}
              />
            </StatusPill>,
          );
        }
        out.push(
          <StatusPill
            key="p-multitarget"
            tone={nMultitarget > 0 ? "danger" : "success"}
            size="sm"
            title={tooltips.paralog_specificity}
          >
            {nMultitarget} multitarget likely
          </StatusPill>,
        );
        // Only surface the "caution" tier when it's non-empty — a
        // "0 caution" chip is noise next to the max-%ECD + multitarget
        // pills.
        if (nCaution > 0) {
          out.push(
            <StatusPill
              key="p-caution"
              tone="amber"
              size="sm"
              title={tooltips.paralog_specificity}
            >
              {nCaution} caution
            </StatusPill>,
          );
        }
        return out;
      })(),
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
          // Stack the shared general-rationale tooltip in front of it so
          // both are visible on hover.
          title={
            mousePill.title ? (
              <>
                {tooltips.ortholog_species_relevance}
                <br />
                <br />
                {mousePill.title}
              </>
            ) : (
              tooltips.ortholog_species_relevance
            )
          }
        >
          <ChipLabelValue label="mouse" value={mousePill.text} />
        </StatusPill>,
        <StatusPill
          key="c"
          tone={cynoPill.tone}
          size="sm"
          title={
            cynoPill.title ? (
              <>
                {tooltips.ortholog_species_relevance}
                <br />
                <br />
                {cynoPill.title}
              </>
            ) : (
              tooltips.ortholog_species_relevance
            )
          }
        >
          <ChipLabelValue label="cyno" value={cynoPill.text} />
        </StatusPill>,
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
        // SURFACE-Bind scores patches on the whole-protein AF2 model and
        // only strips the TM region, so cytoplasmic patches survive (e.g.
        // EGFR's kinase domain). Restrict the count to extracellular-
        // anchored sites — the antibody-accessible ones — so the "EC
        // sites" label is honest. The shared helper keeps this in lockstep
        // with the §SURFACE-Bind table's per-site "Side" column.
        const ec = ecSites(
          sb.sites,
          rec.deterministic_features.canonical_topology.per_residue_topology,
        );
        const ecCount = ec.length;
        // Count EC sites whose buried area reaches the typical
        // antibody-antigen footprint — patches genuinely antibody-sized.
        // The threshold is the shared Ramaraj 2012 constant so code +
        // tooltip prose can't disagree on the number.
        const nAtTypical = ec.filter(
          (s) => s.area_a2 >= TYPICAL_ANTIBODY_INTERFACE_A2,
        ).length;
        if (!sb.has_data) {
          return [
            <StatusPill
              key="sb-not-in"
              tone="neutral"
              size="sm"
              title="Not in SURFACE-Bind's dataset — filtered at structural-quality screening, so targetability wasn't assessed."
            >
              not in SURFACE-Bind
            </StatusPill>,
          ];
        }
        if (sb.n_sites === 0) {
          return [
            <StatusPill
              key="sb-scored-empty"
              tone="danger"
              size="sm"
              title="Scored by SURFACE-Bind, but no surface patches cleared the MaSIF targetability threshold."
            >
              <ChipLabelValue label="scored" value="no patches" />
            </StatusPill>,
          ];
        }
        if (ecCount === 0) {
          return [
            <StatusPill
              key="sb-no-ec"
              tone="danger"
              size="sm"
              title={`Scored ${sb.n_sites} surface patch${
                sb.n_sites === 1 ? "" : "es"
              }, but every anchor sits on an intracellular / membrane face — none are extracellular, so none are reachable by a systemic antibody.`}
            >
              0 EC sites
            </StatusPill>,
          ];
        }
        return [
          <StatusPill
            key="sb-sites"
            tone="success"
            size="sm"
            title={`Extracellular surface patches SURFACE-Bind's MaSIF model scored as designable binder sites${
              ecCount < sb.n_sites
                ? ` (${sb.n_sites} scored in total; ${
                    sb.n_sites - ecCount
                  } anchor on intracellular / membrane faces and are excluded)`
                : ""
            }.`}
          >
            {ecCount} EC site{ecCount === 1 ? "" : "s"}
          </StatusPill>,
          <StatusPill
            key="sb-typical"
            tone={nAtTypical > 0 ? "success" : "amber"}
            size="sm"
            title="EC sites whose buried area reaches the typical antibody-antigen interface (≥1,103 Å², Ramaraj et al. 2012, PMID:22246133) — patches large enough to seat an antibody footprint."
          >
            {nAtTypical} ≥ typical interface
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
    { title: React.ReactNode; links?: { href: string; label: string }[] }
  > = {
    // One-sentence accessibility-context rationale on the group InfoTip —
    // only when the synthesizer authored it (older records render the
    // chips with no tooltip until re-annotated).
    ...(es.accessibility_context_summary
      ? {
          "Accessibility context": {
            title: es.accessibility_context_summary,
          },
        }
      : {}),
    "Family & gene group": {
      title:
        "Registry classification from two deterministic sources: " +
        "UniProt's Swiss-Prot SIMILARITY line (split into superfamily / " +
        "family / subfamily levels) and HGNC's curator-assigned gene " +
        "group membership (a gene can belong to several). Both resolved " +
        "from the identifier bundle, not model output — compare against " +
        "the LLM's Family call above.",
      // Only link the registries that actually contributed pills to this
      // gene: a gene with no UniProt SIMILARITY line shouldn't dangle a
      // UniProt link, and vice-versa for HGNC.
      links: [
        ...(uniprotFamilyPills.length > 0
          ? [
              {
                href: `https://www.uniprot.org/uniprotkb/${rec.gene.uniprot_acc}/entry#family_and_domains`,
                label: "UniProt",
              },
            ]
          : []),
        ...(hgncFamilyPills.length > 0
          ? [
              {
                href: "https://www.genenames.org/data/genegroup/",
                label: "HGNC gene groups",
              },
            ]
          : []),
      ],
    },
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
    // No "Risks" entry — the overarching group InfoTip was dropped per
    // user feedback; each risk chip carries its own tooltip and the
    // §Risks card below covers the supporting evidence.
    // Shared with the §07 "Ortholog (species relevance)" InfoTip via
    // `lib/tooltips` so the bands + framing can't drift. Compara is the
    // data source.
    "Cross-species": {
      title: tooltips.ortholog_species_relevance,
      links: [
        { href: "https://www.ensembl.org/info/genome/compara/index.html", label: "Ensembl Compara" },
      ],
    },
    // Shared with the §07 "Paralog (specificity)" InfoTip via
    // `lib/tooltips` (HPA PMID 33170010 link is inline in that node);
    // Compara is the data source.
    Paralogs: {
      title: tooltips.paralog_specificity,
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
      // PMIDs + the typical-interface number come from `lib/citations`
      // so they can't drift from the SURFACE-Bind chip, the 3D viewer
      // caption, or the site-size logic above.
      title:
        `SURFACE-Bind (Correia lab, ${CITATIONS.surfaceBind.authorYear}, ` +
        `PMID ${CITATIONS.surfaceBind.pmid}, PNAS) scores extracellular ` +
        "surface patches for designability by de novo protein binders. " +
        "Each EC site is a patch where its MaSIF model found geometry / " +
        "chemistry compatible with a designable binder; '≥ typical " +
        "interface' counts the patches whose buried area reaches the " +
        `~${TYPICAL_ANTIBODY_INTERFACE_A2.toLocaleString()} Å² typical ` +
        `antibody-antigen footprint (${CITATIONS.antibodyInterface.authorYear}, ` +
        `PMID ${CITATIONS.antibodyInterface.pmid}).`,
      links: [
        { href: "https://surface-bind.inria.fr/", label: "SURFACE-Bind" },
        {
          // Same source the 3D viewer's sites-mode caption cites.
          href: pubmedUrl(CITATIONS.surfaceBind.pmid),
          label: `${CITATIONS.surfaceBind.authorYear}`,
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
      {/* Provenance section heading — synthesizer rollups. Only rendered
       *  if any LLM-provenance group survives; today the Biology /
       *  Expression / Risks chip groups have moved to their own tabs, so
       *  llmGroups is empty and this heading is suppressed (leaving
       *  "Deterministic" as the first heading — its :first-child rule
       *  drops the top border). The guard keeps the card correct if an
       *  LLM-provenance group is ever added back. */}
      {llmGroups.length > 0 ? (
        <>
          <p className={`label-mono ${styles.provenanceHeading}`}>LLM-driven</p>
          <div className={styles.groups}>{llmGroups.map(renderGroup)}</div>
        </>
      ) : null}

      {/* Provenance section heading — deterministic-tool readouts.
       *  DeepTMHMM topology, AlphaFold pLDDT (via the SURFACE-Bind
       *  block + isoform cards), Ensembl Compara orthologs +
       *  paralogs, MaSIF / SURFACE-Bind targetability. */}
      <p className={`label-mono ${styles.provenanceHeading}`}>Deterministic</p>
      <div className={styles.groups}>{detGroups.map(renderGroup)}</div>
    </SectionCard>
  );
}
