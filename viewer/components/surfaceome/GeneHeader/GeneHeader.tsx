import type { ReactNode } from "react";
import type { CatalogRow } from "../../../lib/surfaceome";
import type {
  AccessibilityModulationObservation,
  BenchmarkRow,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import type { SchwekeHomomerLoaderRow } from "../../../lib/structure-viewer";
import type { StructureViewerData } from "../../../lib/structure-viewer-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { tooltips } from "../../../lib/tooltips";
import { ReasoningDrawer } from "../ReasoningDrawer/ReasoningDrawer";
import { DatabasePresenceStrip } from "../DatabasePresenceCard/DatabasePresenceStrip";
import { linkifyEvidenceRefs } from "../EvidenceChip/EvidenceChip";
import { FeedbackButton } from "../../FeedbackButton/FeedbackButton";
import { InfoTip } from "../../InfoTip/InfoTip";
import { ChipLabelValue } from "../ChipLabelValue/ChipLabelValue";
import { StatusPill } from "../StatusPill/StatusPill";
import { StructureViewer } from "../StructureViewerCard/StructureViewer";
import styles from "./GeneHeader.module.css";

/** Convert an isoform UniProt id like "P00533-2" into a reader-friendly
 *  tab label ("Isoform 2"). Falls back to the raw id when the suffix
 *  doesn't match the expected pattern. */
function _isoformLabel(isoformId: string): string {
  const m = /-(\d+)$/.exec(isoformId);
  return m ? `Isoform ${m[1]}` : isoformId;
}

/** Best-effort DeepTMHMM type inference from a per-residue topology
 *  string. The StructureViewerData type expects "TM" / "SP+TM" /
 *  "SP" / "BETA" / "GLOB"; the IsoformTopology Pydantic class
 *  doesn't carry the rolled-up type, so we approximate from the
 *  per-residue string. The result drives the GLOB-vs-TM caption only
 *  — no functional behavior depends on it. */
function _inferDeepTMHMMType(
  topology: string,
): import("../../../lib/structure-viewer-types").DeepTMHMMType {
  const hasS = topology.includes("S");
  const hasM = topology.includes("M");
  const hasB = topology.includes("B");
  if (hasB) return "BETA";
  if (hasS && hasM) return "SP+TM";
  if (hasM) return "TM";
  if (hasS) return "SP";
  return "GLOB";
}

/** Coerce an OrthologEntry's stored ``deeptmhmm_label`` into the viewer's
 *  DeepTMHMMType. Orthologs DO carry the rolled-up label from D1 (unlike
 *  isoforms), so prefer it; fall back to inferring from the per-residue
 *  string if the label is missing or unrecognized. */
function _coerceDeepTMHMMType(
  label: string | null | undefined,
  topology: string,
): import("../../../lib/structure-viewer-types").DeepTMHMMType {
  const known = ["TM", "SP+TM", "SP", "BETA", "GLOB"] as const;
  if (label && (known as readonly string[]).includes(label)) {
    return label as (typeof known)[number];
  }
  return _inferDeepTMHMMType(topology);
}

interface GeneHeaderProps {
  rec: SurfaceomeRecord;
  /** Descriptive gene name + synonyms from NCBI gene_info. The record
   *  itself doesn't carry the field; the page loads it server-side via
   *  ``loadGeneName(symbol)`` and passes it down. ``null`` when no
   *  entry exists for the symbol. */
  geneName?: { name: string; synonyms: string[] } | null;
  /** DeepTMHMM topology data for the canonical UniProt. Loaded
   *  server-side via ``loadStructureViewerData(uniprot_acc)``;
   *  ``null`` when no JSON exists for the UniProt — header
   *  collapses back to single-column. Membrane-anchored cytoplasmic
   *  proteins (DeepTMHMM type GLOB, e.g. SRC, myristoyl-anchored)
   *  CAN still have a JSON when emitted via the build script's
   *  ``--include-globular`` flag; the viewer paints them uniformly
   *  intracellular and the caption is adjusted to describe the
   *  membrane-anchoring rather than a transmembrane orientation. */
  structureData?: StructureViewerData | null;
  /** Schweke et al. 2024 (PMID 38325366) AF2 homo-oligomer entry, when
   *  this gene is in the manifest. Forwarded as the ``schwekeHomomer``
   *  prop on <StructureViewer>, where it surfaces as a "Homo-oligomer"
   *  tab IMMEDIATELY after Canonical. Null for genes outside the
   *  8,195-homomer reference set or whose PDB asset hasn't been
   *  ingested yet. */
  schwekeHomomer?: SchwekeHomomerLoaderRow | null;
  /** 5-DB surface-vote vector from the candidate-universe build.
   *  When present, a slim ``<DatabasePresenceStrip>`` renders inline
   *  above the executive summary so the reader sees DB consensus
   *  without scrolling. ``null`` for resolver-failure outliers — the
   *  strip is omitted in that case (same fall-back as the old
   *  section-card placement). */
  catalogRow?: CatalogRow | null;
  /** Curated SurfaceBench ground-truth row — present only for the ~147
   *  benchmark genes. When set, a "Benchmark" row renders ABOVE the
   *  triage row showing the hand-curated truth verdict (the strongest
   *  reference point on the page). ``null`` for the ~19k non-benchmark
   *  genes, where the row is omitted. */
  benchmarkRow?: BenchmarkRow | null;
}

function tierCounts(rec: SurfaceomeRecord) {
  let primary = 0;
  let secondary = 0;
  let tertiary = 0;
  for (const e of rec.evidence) {
    if (e.evidence_tier === "primary") primary += 1;
    else if (e.evidence_tier === "secondary") secondary += 1;
    else if (e.evidence_tier === "tertiary") tertiary += 1;
  }
  return { primary, secondary, tertiary, total: rec.evidence.length };
}

// All four vitals share one traffic-light scale: green (high / direct
// evidence) → yellow (moderate) → red (low / negative), plus gray for
// unknown / no-signal. See `.h-vital-display.tone-*` in globals.css.
// No teal, lavender, or light-green — the 2×2 grid scans like a heatmap.
function accessibilityTone(value: string) {
  if (value === "high") return "success" as const; // green
  if (value === "moderate") return "amber" as const; // yellow
  // `"low"` and `"no"` (confident negative) both read red — the reader
  // scans red for "not a good surface target".
  if (value === "low") return "danger" as const; // red
  if (value === "no") return "danger" as const; // red
  return "neutral" as const; // unknown / uncertain → gray
}

function gradeTone(value: string) {
  // Direct evidence (single- or multi-method) → green; supportive /
  // conflicting → yellow; nothing graded → gray.
  if (value === "direct_multi_method") return "success" as const; // green
  if (value === "direct_single_method") return "success" as const; // green
  if (value === "supportive_but_indirect") return "amber" as const; // yellow
  // `"conflicting"` is contradictory evidence, not a confident
  // negative — yellow (caution / mixed), not red.
  if (value === "conflicting") return "amber" as const; // yellow
  return "neutral" as const; // gray
}

/** Convert the derived `TriageSignal` enum back to the original
 *  triage verdict the agent actually emitted. The signal is a 1:1
 *  rename of `TriageVerdict` (yes | contextual | no), so the
 *  inversion is mechanical. Rendering the verdict instead of the
 *  signal matches what the synthesizer's prose quotes (e.g. SRC's
 *  confidence_reasoning: "Triage called verdict='no', …"). */
function triageVerdictLabel(signal: string): string {
  if (signal === "likely_accessible") return "Yes";
  if (signal === "possibly_accessible") return "Contextual";
  if (signal === "unlikely") return "No";
  return "Unknown";
}

/** Display label for a SurfaceBench ground-truth verdict. The matrix
 *  stores the raw curated verdict ("yes" | "contextual" | "no"); render
 *  it title-cased to match the triage row's verdict labels. */
function benchmarkVerdictLabel(verdict: string): string {
  if (verdict === "yes") return "Yes";
  if (verdict === "contextual") return "Contextual";
  if (verdict === "no") return "No";
  return prettyEnum(verdict);
}

/** Tone for the benchmark verdict value — green = surface (yes), amber =
 *  contextual / state-dependent, red = not surface (no), gray otherwise.
 *  Same traffic-light scale as the rest of the header. */
function benchmarkVerdictTone(
  verdict: string,
): "success" | "amber" | "danger" | "neutral" {
  if (verdict === "yes") return "success";
  if (verdict === "contextual") return "amber";
  if (verdict === "no") return "danger";
  return "neutral";
}

/** Closed-enum buckets for ``executive_summary.surface_call_reason``, mirrored
 * from ``src/accessible_surfaceome/tools/_shared/models.py`` (``_YES_REASONS``
 * / ``_CONTEXTUAL_REASONS`` / ``_NO_REASONS``). The reason field is what
 * actually determines the deep-dive's yes/contextual/no bucket — looking at
 * ``surface_accessibility`` alone misclassifies the entire CONTEXTUAL bucket
 * (which renders as ``surface_accessibility = "low"`` plus a CONTEXTUAL
 * reason like ``cell_state_induced``). ``other`` appears in every bucket in
 * the schema, so we deliberately leave it out here and let the fallback by
 * accessibility magnitude decide. */
const DEEP_DIVE_YES_REASONS: ReadonlySet<string> = new Set([
  "classical_surface_receptor",
  "gpi_anchored",
  "multipass_with_exposed_loops",
  "extracellular_face_protein",
  "stable_complex_partner",
]);
const DEEP_DIVE_CONTEXTUAL_REASONS: ReadonlySet<string> = new Set([
  "cell_state_induced",
  "tissue_restricted_surface",
  "lysosomal_exocytosis",
  "dual_localization",
  "stable_surface_attachment",
]);
const DEEP_DIVE_NO_REASONS: ReadonlySet<string> = new Set([
  "cytoplasmic",
  "nuclear",
  "mitochondrial_internal",
  "endomembrane_resident",
  "nuclear_envelope",
  "inner_leaflet_anchored",
  "secreted_only",
  "pmhc_only_intracellular",
]);

/** Collapse the deep-dive's ``(surface_accessibility, surface_call_reason)``
 * to a yes / contextual / no bucket matching the bench-truth taxonomy. The
 * call_reason is the primary signal (it directly names the bucket); we only
 * fall back to accessibility magnitude when the reason is absent or out-of-
 * vocabulary (``"other"`` or a future schema addition). */
function collapseDeepDive(
  accessibility: string,
  callReason: string | null | undefined,
): "yes" | "contextual" | "no" | "unclear" {
  if (callReason) {
    if (DEEP_DIVE_CONTEXTUAL_REASONS.has(callReason)) return "contextual";
    if (DEEP_DIVE_YES_REASONS.has(callReason)) return "yes";
    if (DEEP_DIVE_NO_REASONS.has(callReason)) return "no";
  }
  if (accessibility === "high" || accessibility === "moderate") return "yes";
  if (accessibility === "low" || accessibility === "no") return "no";
  return "unclear";
}

/** Compare a positive-side signal (Sonnet triage prior or curated bench
 * truth, both expressed in triage-signal vocabulary) against the deep-dive
 * verdict.
 *
 * Returns one of:
 * - `"agree"` — both sides land in the same yes / contextual / no bucket.
 *   ``possibly_accessible`` (≈ contextual) is also a soft agree with
 *   ``yes`` (a surface that's reachable across more states than the triage
 *   estimated isn't a conflict — just a stronger result).
 * - `"conflict"` — strong disagreement: positive vs no, or negative vs yes.
 *   Tighter than the old naive-binary check: a deep-dive verdict of
 *   ``low + cell_state_induced`` no longer trips ``conflict`` against a
 *   ``possibly_accessible`` triage / ``contextual`` bench truth.
 * - `"unclear"` — one or both sides emit ``unknown`` / ``uncertain``, or the
 *   axes are too far apart to call (e.g. ``unlikely`` triage vs deep-dive
 *   ``contextual``: the triage missed a state-induced surface, which is
 *   informative but not a hard "the deep dive said the opposite" pill).
 *
 * The deep dive wins on conflict (it has the per-method evidence); the
 * triage row just flags the disagreement for transparency. */
function triageVsDeepDive(
  triage: string,
  accessibility: string,
  callReason: string | null | undefined,
): "agree" | "conflict" | "unclear" {
  const triageStrongPositive = triage === "likely_accessible";
  const triageSoftPositive = triage === "possibly_accessible";
  const triageNegative = triage === "unlikely";
  const deepVerdict = collapseDeepDive(accessibility, callReason);

  if (triageStrongPositive) {
    if (deepVerdict === "yes") return "agree";
    if (deepVerdict === "no") return "conflict";
    return "unclear"; // contextual under "yes"-leaning triage — softer than expected, not a hard conflict
  }
  if (triageSoftPositive) {
    if (deepVerdict === "yes" || deepVerdict === "contextual") return "agree";
    if (deepVerdict === "no") return "conflict";
    return "unclear";
  }
  if (triageNegative) {
    if (deepVerdict === "no") return "agree";
    if (deepVerdict === "yes") return "conflict";
    return "unclear"; // contextual under "unlikely" triage — triage missed a state-induced surface
  }
  return "unclear";
}

function stateDependenceTone(value: string) {
  // Toned by literal value so the whole 2×2 reads as one consistent
  // heatmap: low→red, moderate→yellow, high→green, like every other
  // vital. NOTE: this is the favorability INVERSE for state-dependence —
  // a *low* state-dependence call is actually the safest, always-on
  // target, yet it tints red here to keep the value→color mapping
  // uniform across the grid. If a future reviewer wants this toned by
  // favorability instead (low=green/constitutive, high=red/state-gated),
  // flip the two non-amber branches.
  if (value === "low") return "danger" as const; // red
  if (value === "moderate") return "amber" as const; // yellow
  if (value === "high") return "success" as const; // green
  return "neutral" as const; // unclear → gray
}

function confidenceTone(value: string) {
  // high→green, moderate→amber, low→red — same red→green ramp as the
  // other vitals (was green / lavender / amber).
  if (value === "high") return "success" as const;
  if (value === "moderate") return "amber" as const;
  if (value === "low") return "danger" as const;
  return "neutral" as const;
}

/** Structured body for the State-dependence "Reasoning" drawer. The
 *  state-dependence call has no single prose field (unlike confidence /
 *  grade); its rationale lives in the per-observation
 *  `biological_context.accessibility_modulation` entries. Render each as
 *  a compact block — the modulation category (+ cell-state trigger when
 *  present), the `change` (what happens), and the
 *  `accessibility_implication` (the so-what for surface access). The
 *  drawer footer carries the union of cited evidence, so per-block chips
 *  are omitted here to keep the narrative readable. */
function stateModulationBody(
  observations: readonly AccessibilityModulationObservation[],
): ReactNode {
  return (
    <div className={styles.stateModList}>
      {observations.map((m, i) => {
        const category =
          m.category === "other" && m.category_other_label
            ? m.category_other_label
            : prettyEnum(m.category);
        const trigger = m.cell_state_trigger
          ? ` · ${prettyEnum(m.cell_state_trigger)}`
          : "";
        return (
          <div key={i} className={styles.stateModItem}>
            <p className={`label-mono ${styles.stateModCategory}`}>
              {category}
              {trigger}
            </p>
            <p className={styles.stateModChange}>{m.change}</p>
            <p className={styles.stateModImplication}>
              {m.accessibility_implication}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function plddtTone(plddt: number) {
  if (plddt >= 90) return "success" as const;
  if (plddt >= 70) return "teal" as const;
  if (plddt >= 50) return "amber" as const;
  return "danger" as const;
}

/** Map a vital tone enum to the `.h-vital-display` tone modifier class.
 *  The four tones form a traffic-light scale plus gray: success (green),
 *  amber (yellow), danger (red), neutral (gray, for unknown / unclear).
 *  Every tone gets a class — `neutral` tints muted-gray rather than
 *  falling back to ink, so an "Unknown" vital still reads as gray. */
function vitalToneClass(
  tone: "success" | "amber" | "danger" | "neutral",
): string {
  return `tone-${tone}`;
}

/**
 * GeneHeader — display-scale gene symbol, executive lede, identifier
 * links, and four vitals. Driven entirely by `executive_summary` +
 * derived counts from the evidence ledger; no v0.x targetability /
 * surface_biology fields.
 */
export function GeneHeader({
  rec,
  geneName,
  structureData,
  schwekeHomomer,
  catalogRow,
  benchmarkRow,
}: GeneHeaderProps) {
  const g = rec.gene;
  const exec = rec.executive_summary;
  const counts = tierCounts(rec);
  const struct = rec.deterministic_features.structure;
  // The fetcher signals what kind of pLDDT the number is via the
  // ``source`` string (see :func:`tools.afdb_plddt.fetch_afdb_plddt`).
  //   * "placeholder" — fetcher hasn't run, the 0.0 isn't a measurement.
  //   * "whole-protein" — protein has no extracellular residues (GLOB
  //     proteins like SRC); the fetcher reused the global metric so the
  //     schema field stays populated. Honest display: label "Whole pLDDT"
  //     so the reader doesn't think it's ECD-restricted, and omit the
  //     disordered fraction (the global frac-low + frac-very-low isn't
  //     comparable to the ECD-restricted threshold-based number on
  //     proper ECD proteins).
  //   * "ECD-restricted" — real ECD-restricted pLDDT computed from the
  //     CIF; label "ECD pLDDT" as the schema field intends.
  const structSource = struct.source.toLowerCase();
  const structPlaceholder = structSource.includes("placeholder");
  const structWholeProtein =
    !structPlaceholder && structSource.includes("whole-protein");
  const plddtLabel = structWholeProtein ? "Whole pLDDT" : "ECD pLDDT";
  // Four canonical external IDs only — SURFACE-Bind was dropped from
  // this row (it's already linked from the 3D viewer's ↗ control next
  // to the mode toggle, no need to surface it twice).
  const ids = [
    {
      label: "HGNC",
      value: g.hgnc_id,
      href: `https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${g.hgnc_id}`,
    },
    {
      label: "UniProt",
      value: g.uniprot_acc,
      href: `https://www.uniprot.org/uniprotkb/${g.uniprot_acc}`,
    },
    {
      label: "NCBI Gene",
      value: String(g.ncbi_gene_id),
      href: `https://www.ncbi.nlm.nih.gov/gene/${g.ncbi_gene_id}`,
    },
    {
      label: "Ensembl",
      value: g.ensembl_gene,
      href: `https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${g.ensembl_gene}`,
    },
  ];

  return (
    <header className={styles.header}>
      <div className={styles.headerGrid}>
        <div className={styles.headerText}>
          {/* Gene symbol + the descriptive name inline (small italics)
              on the same baseline, with previous synonyms on a small
              line below. */}
          <h1 className={`h-gene ${styles.symbol}`}>
            {g.hgnc_symbol}
            {geneName?.name ? (
              <span className={styles.geneFullName}>{geneName.name}</span>
            ) : null}
            {geneName?.synonyms && geneName.synonyms.length > 0 ? (
              <span className={styles.synonyms}>
                Synonyms: {geneName.synonyms.slice(0, 3).join(", ")}
              </span>
            ) : null}
          </h1>

          {/* IDs row — small, immediately under the descriptive gene
              name. Was previously placed below the exec lede + headline
              risks; promoted here per user feedback so the external
              identifiers are visually attached to the gene-name strip. */}
          {/* IDs row + Submit-feedback CTA. The button sits inline at
              the end of the identifier strip so the call-to-action is
              visually attached to the IDs rather than floating
              elsewhere on the page; on narrow viewports the flex wrap
              puts it on its own line under the IDs. */}
          <div className={styles.idsRow}>
            <ul className={styles.ids} aria-label="External identifiers">
              {ids.map((id) => (
                <li key={id.label} className={styles.idItem}>
                  <a
                    className={styles.idLink}
                    href={id.href}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <span className={`label-mono ${styles.idLabel}`}>{id.label}</span>
                    <span className={styles.idValue}>{id.value}</span>
                  </a>
                </li>
              ))}
            </ul>
            <FeedbackButton
              gene={g.hgnc_symbol}
              uniprotAcc={g.uniprot_acc}
              variant="standalone"
            />
          </div>

          {/* DB-membership strip — was a full §section card; promoted
              to an inline strip immediately above the exec summary
              per user feedback. ``null`` for resolver-failure
              outliers, where we just omit the strip. */}
          {catalogRow ? <DatabasePresenceStrip row={catalogRow} /> : null}

          {/* Benchmark row — only for the ~147 SurfaceBench genes. The
              hand-curated ground-truth verdict is the strongest reference
              point on the page, so it sits ABOVE the model's first-pass
              triage. Reuses the triage-row layout for visual consistency;
              the value is toned on the same traffic-light scale. */}
          {benchmarkRow
            ? (() => {
                // Same agree/conflict comparison the triage row makes, but
                // against the curated ground-truth verdict instead of the
                // model's triage prior. Map the benchmark verdict onto the
                // triage-signal scheme so triageVsDeepDive can be reused
                // (yes→likely, contextual→possibly, no→unlikely).
                const benchSignal =
                  benchmarkRow.truth_verdict === "yes"
                    ? "likely_accessible"
                    : benchmarkRow.truth_verdict === "contextual"
                      ? "possibly_accessible"
                      : benchmarkRow.truth_verdict === "no"
                        ? "unlikely"
                        : "unknown";
                const benchVerdict = triageVsDeepDive(
                  benchSignal,
                  exec.surface_accessibility,
                  exec.surface_call_reason,
                );
                return (
                  <p className={styles.triageRow}>
                    <span className={`label-mono ${styles.triageLabel}`}>
                      Benchmark
                      <InfoTip>{tooltips.benchmark_truth}</InfoTip>
                    </span>
                    <StatusPill
                      tone={benchmarkVerdictTone(benchmarkRow.truth_verdict)}
                      size="sm"
                    >
                      {benchmarkVerdictLabel(benchmarkRow.truth_verdict)}
                    </StatusPill>
                    {benchVerdict === "conflict" ? (
                      <span className={styles.triageConflict}>
                        conflicts with deep dive
                      </span>
                    ) : benchVerdict === "agree" ? (
                      <span className={styles.triageAgree}>
                        agrees with deep dive
                      </span>
                    ) : null}
                  </p>
                );
              })()
            : null}

          {/* Triage row — Sonnet first-pass surface verdict, sitting
              under the DB-presence strip for transparency. Tagged with
              "initial pass · no web search" so the reader knows this
              isn't the deep-dive call. When the triage disagrees with
              the deep-dive `surface_accessibility`, the row carries a
              warn pill that links the eye to the conflict (e.g. for
              SRC: triage=Unlikely vs deep-dive=High — the eSrc
              cancer-specific surface that the initial triage missed). */}
          {(() => {
            const verdict = triageVsDeepDive(
              rec.triage_signal,
              exec.surface_accessibility,
              exec.surface_call_reason,
            );
            return (
              <p className={styles.triageRow}>
                <span className={`label-mono ${styles.triageLabel}`}>
                  Triage
                  <InfoTip wide>{tooltips.triage_signal}</InfoTip>
                </span>
                <span className={styles.triageValue}>
                  {triageVerdictLabel(rec.triage_signal)}
                </span>
                <span className={styles.triageQualifier}>
                  <ChipLabelValue label="initial pass" value="no web search" />
                </span>
                {verdict === "conflict" ? (
                  <span className={styles.triageConflict}>
                    conflicts with deep dive
                  </span>
                ) : verdict === "agree" ? (
                  <span className={styles.triageAgree}>
                    agrees with deep dive
                  </span>
                ) : null}
                {/* The triage agent's own verdict justification, surfaced
                 *  in a slide-in drawer. Self-hides when the record
                 *  carries no triage_reasoning (older records / genes with
                 *  no persisted triage). Distinct from the deep-dive
                 *  confidence reasoning below — this is the first-pass,
                 *  no-web-search rationale. */}
                <ReasoningDrawer
                  eyebrow={`Triage · ${triageVerdictLabel(rec.triage_signal)}`}
                  title="Why this triage call?"
                  ariaLabel="Why the initial triage pass called it this way"
                  triggerClassName={styles.triageReasoningTrigger}
                  reasoning={rec.triage_reasoning ?? ""}
                />
              </p>
            );
          })()}

          {/* Executive summary one-paragraph. Headline risks + cited
              evidence chips were dropped from the header per user
              feedback — both are still visible:
                * headline_risks → the §Risks card (they're not a
                  state-dependence signal, so they no longer sit under
                  that vital)
                * cited_evidence_ids → the §Evidence ledger + each
                  per-row EvidenceChipList */}
          <p className={styles.execLede}>
            {linkifyEvidenceRefs(exec.one_paragraph)}
          </p>

          {/* At-a-glance 2×2 vitals grid. Each value is the deep-dive
              agent's synthesis (Accessibility / Experimental surface
              evidence / Confidence / State dependence). Architecture +
              Family sit inside the Accessibility cell as pill chips
              (each with its own InfoTip); Confidence, Surface evidence,
              and State dependence each carry a "Reasoning" drawer chip.
              The LLM-vs-Deterministic split now lives in §01 Summary
              metrics; deterministic tool data (topology, pLDDT,
              SURFACE-Bind, conservation) is no longer duplicated
              here. */}
          <dl className={styles.vitals}>
            {(() => {
              const accessTone = accessibilityTone(exec.surface_accessibility);
              const gradeT = gradeTone(exec.evidence_grade_summary);
              const confT = confidenceTone(exec.confidence);
              const stateT = stateDependenceTone(exec.state_dependence);
              return (
                <>
                  <div className={styles.vital}>
                    <dt className={`label-mono ${styles.vitalK}`}>
                      Accessibility
                      <InfoTip>{tooltips.surface_accessibility}</InfoTip>
                    </dt>
                    <dd className={styles.vitalV}>
                      <p className={`h-vital-display ${vitalToneClass(accessTone)}`}>
                        {prettyEnum(exec.surface_accessibility)}
                      </p>
                      {/* Architecture + Family — two pill chips beneath
                       *  the accessibility value. Sentence-cased,
                       *  brown ``--ink-soft`` color (NOT the
                       *  accessibility tone — these are neutral
                       *  metadata about the protein, not signals about
                       *  its accessibility). The deep-dive agent picks
                       *  the values; ``InfoTip`` per chip carries the
                       *  provenance + enum-value glossary. */}
                      <div className={styles.archFamilyInline}>
                        <span className={styles.archFamilyChip}>
                          <span className={styles.archFamilyChipKey}>
                            Architecture
                          </span>
                          <span className={styles.archFamilyChipValue}>
                            {prettyEnum(exec.subcategory)}
                          </span>
                          <InfoTip>{tooltips.architecture_chip}</InfoTip>
                        </span>
                        <span className={styles.archFamilyChip}>
                          <span className={styles.archFamilyChipKey}>
                            Family
                          </span>
                          <span className={styles.archFamilyChipValue}>
                            {prettyEnum(exec.llm_family)}
                          </span>
                          <InfoTip>{tooltips.family_chip}</InfoTip>
                        </span>
                        {/* Deterministic registry families (HGNC gene
                         *  group + UniProt SIMILARITY family) moved to
                         *  the §01 Summary-metrics "Deterministic"
                         *  block — see FiltersCard. They're registry
                         *  ground truth, not model output, so they read
                         *  better beside the other deterministic-tool
                         *  readouts than next to the LLM Family chip. */}
                      </div>
                    </dd>
                  </div>

                  <div className={styles.vital}>
                    <dt className={`label-mono ${styles.vitalK}`}>
                      Experimental surface evidence
                      <InfoTip>{tooltips.experimental_surface_evidence}</InfoTip>
                    </dt>
                    <dd className={styles.vitalV}>
                      <p className={`h-vital-display ${vitalToneClass(gradeT)}`}>
                        {prettyEnum(exec.evidence_grade_summary)}
                      </p>
                      <span className={styles.vitalSub}>
                        {counts.total} entries
                      </span>
                      {/* "Reasoning" chip — opens a slide-in drawer with
                       *  the synthesizer's grade_rationale prose. Source
                       *  field is ``surface_evidence.grade_rationale``,
                       *  which the §02 banner also renders; the chip is
                       *  the vital-grid surface so the reader can read the
                       *  reasoning without scrolling to the section. */}
                      <ReasoningDrawer
                        eyebrow={`Surface evidence · ${prettyEnum(
                          exec.evidence_grade_summary,
                        )}`}
                        title="Why this grade?"
                        ariaLabel={`Why this evidence grade is ${prettyEnum(
                          exec.evidence_grade_summary,
                        )}`}
                        reasoning={rec.surface_evidence.grade_rationale ?? ""}
                        // Union of every method block's cited evidence — the
                        // grade rationale aggregates across all methods, so
                        // the chip strip should too. Dedup preserves order.
                        citedEvidenceIds={Array.from(
                          new Set(
                            rec.surface_evidence.methods.flatMap(
                              (m) => m.cited_evidence_ids,
                            ),
                          ),
                        )}
                      />
                    </dd>
                  </div>

                  <div className={styles.vital}>
                    <dt className={`label-mono ${styles.vitalK}`}>
                      Confidence
                      <InfoTip>{tooltips.confidence}</InfoTip>
                    </dt>
                    <dd className={styles.vitalV}>
                      <p className={`h-vital-display ${vitalToneClass(confT)}`}>
                        {prettyEnum(exec.confidence)}
                      </p>
                      <span className={styles.vitalSub}>
                        {counts.primary} primary · {counts.secondary} secondary
                      </span>
                      {/* "Reasoning" — slide-in side drawer below the
                       *  confidence value. Self-hides when reasoning is
                       *  empty so the trigger never appears for
                       *  high-confidence calls. */}
                      <ReasoningDrawer
                        eyebrow={`Confidence · ${prettyEnum(exec.confidence)}`}
                        title="Why this confidence?"
                        ariaLabel={`Why this confidence is ${prettyEnum(
                          exec.confidence,
                        )}`}
                        reasoning={rec.confidence_reasoning ?? ""}
                        // Lede's cited_evidence_ids cover the overall
                        // surface call which the confidence rationale
                        // justifies; pass them through so the reader
                        // can drill into the source quotes from inside
                        // the drawer.
                        citedEvidenceIds={exec.cited_evidence_ids}
                      />
                    </dd>
                  </div>

                  <div className={styles.vital}>
                    <dt className={`label-mono ${styles.vitalK}`}>
                      State dependence
                      <InfoTip>{tooltips.state_dependence}</InfoTip>
                    </dt>
                    <dd className={styles.vitalV}>
                      <p className={`h-vital-display ${vitalToneClass(stateT)}`}>
                        {prettyEnum(exec.state_dependence)}
                      </p>
                      {/* "Reasoning" chip — the state-dependence call has
                       *  no single prose field; its rationale lives in the
                       *  per-observation accessibility_modulation entries
                       *  (the "Normal → Disease" surface-access story).
                       *  Guarded on length so always-on surface proteins
                       *  (no modulation observations) show just the value
                       *  with no chip. The old "N headline risks" subtitle
                       *  was removed — headline risks aren't a
                       *  state-dependence signal; they live in the §Risks
                       *  card. */}
                      {rec.biological_context.accessibility_modulation.length >
                      0 ? (
                        <ReasoningDrawer
                          eyebrow={`State dependence · ${prettyEnum(
                            exec.state_dependence,
                          )}`}
                          title="What modulates surface access?"
                          ariaLabel="How surface access changes with cell state"
                          citedEvidenceIds={Array.from(
                            new Set(
                              rec.biological_context.accessibility_modulation.flatMap(
                                (m) => m.cited_evidence_ids,
                              ),
                            ),
                          )}
                        >
                          {stateModulationBody(
                            rec.biological_context.accessibility_modulation,
                          )}
                        </ReasoningDrawer>
                      ) : null}
                    </dd>
                  </div>
                </>
              );
            })()}
          </dl>

          {/* Deterministic-tools row was here. Removed per user
              request — deterministic data (topology, pLDDT,
              SURFACE-Bind, conservation) now lives only in §01
              Summary metrics grouped under a "Deterministic"
              section header. Surfacing it twice was redundant. */}
        </div>

        {structureData ? (
          <aside className={styles.structureSlot} aria-label="3D structure">
            <StructureViewer
              data={structureData}
              geneSymbol={g.hgnc_symbol}
              // Schweke et al. 2024 (PMID 38325366) AF2 homo-oligomer
              // model when this gene is in the manifest. Renders as a
              // "Homo-oligomer" tab right after Canonical and before
              // isoforms / orthologs. Assemble the full variant here
              // (rather than in the loader) so the canonical topology
              // and DeepTMHMM type — already in hand via structureData
              // — don't have to be re-derived.
              schwekeHomomer={
                schwekeHomomer
                  ? (() => {
                      // Label/sublabel depend on the assembly:
                      //   c2 dimer ECD-only  → "ECD Dimer · Schweke 2024"
                      //   c2 dimer (full)    → "Dimer · Schweke 2024"
                      //   c3..c13            → "{N}-Mer (c{N}) · Schweke 2024"
                      const n = schwekeHomomer.stoichiometry;
                      const sub =
                        n === 2
                          ? schwekeHomomer.ecd_only
                            ? "ECD Dimer · Schweke 2024"
                            : "Dimer · Schweke 2024"
                          : `${n}-Mer (c${n}) · Schweke 2024`;
                      return {
                        source: "schweke-homomer" as const,
                        id: `schweke-${schwekeHomomer.uniprot_acc}-V1-${schwekeHomomer.af_model_num}-c${n}`,
                        label: "Homo-oligomer",
                        sublabel: sub,
                        uniprot_acc: schwekeHomomer.uniprot_acc,
                        pdb_url: schwekeHomomer.pdb_url,
                        af_model_num: schwekeHomomer.af_model_num,
                        ecd_only: schwekeHomomer.ecd_only,
                        stoichiometry: n,
                        topology: structureData.topology,
                        deeptmhmm_type: structureData.deeptmhmm_type,
                      };
                    })()
                  : null
              }
              // Canonical AFDB stats — the new caption inside the
              // viewer renders these for the canonical tab (and
              // lazy-fetches metadata for other AFDB variants when
              // the user switches tabs).
              canonicalStruct={{
                afdb_id: struct.afdb_id,
                afdb_version: struct.afdb_version,
                ecd_mean_plddt: struct.ecd_mean_plddt,
                ecd_disordered_fraction: struct.ecd_disordered_fraction,
                source: struct.source,
              }}
              // UniProt protein name (NCBI gene_info `name`) — shown
              // in italic above the AFDB stats for the canonical
              // tab, like the structure title shown for experimental.
              proteinName={geneName?.name ?? null}
              // Pass SURFACE-Bind anchor residues so each scored
              // patch gets a sphere + label on the 3D structure.
              // Empty array when the protein isn't in SURFACE-Bind
              // OR is in but no patches cleared scoring; the viewer
              // simply skips the overlay loop in that case.
              // Compartment per anchor is derived from the
              // DeepTMHMM ``per_residue_topology`` character at
              // the anchor residue (1-indexed): O=extracellular,
              // I=intracellular, M=membrane, S=signal, else
              // unknown. Lets the viewer's "Sites focus" mode
              // label each sphere with EC/IC at a glance so the
              // reader knows which sites are antibody-accessible.
              surfaceBindAnchors={rec.deterministic_features.surface_bind.sites.map(
                (s) => {
                  const topo = structureData.topology;
                  const idx = s.anchor_residue - 1;
                  const ch =
                    idx >= 0 && idx < topo.length ? topo.charAt(idx) : "?";
                  const compartment =
                    ch === "O"
                      ? ("extracellular" as const)
                      : ch === "I"
                        ? ("intracellular" as const)
                        : ch === "M"
                          ? ("membrane" as const)
                          : ch === "S"
                            ? ("signal" as const)
                            : ("unknown" as const);
                  return {
                    siteId: s.site_id,
                    residue: s.anchor_residue,
                    compartment,
                  };
                },
              )}
              // Variant tabs above the 3D canvas: alt isoforms
              // (sourced from `rec.deterministic_features.isoform_topologies`)
              // and 1:1 orthologs (mouse + cynomolgus). Each variant
              // carries its own per-residue topology so the topology
              // coloring + membrane slab work without extra fetches.
              //
              // Isoforms: the .3line UniProt acc has a `-N` suffix
              // (e.g. "P00533-2"). AFDB models the canonical
              // accession but applies the isoform-specific
              // sequence/topology, so the URL path strips the
              // suffix back to the bare canonical.
              //
              // Orthologs: the per-residue topology + DeepTMHMM label
              // are now backfilled onto each `OrthologEntry` (sourced
              // from `topology_public` cohorts mouse_ortholog /
              // cyno_ortholog), so the canonical mouse + cyno orthologs
              // get their own AFDB tab — fetched by the ortholog's own
              // UniProt acc, colored by the ortholog's own topology.
              // Only the canonical ortholog per species is shown (alt
              // ortholog isoforms aren't structurally interesting here),
              // and only when it actually carries a topology string.
              variants={[
                // Cap the 3D tab strip at the first 3 isoforms.
                // isoform_topologies is in UniProt isoform-number order
                // (Isoform 2, 3, 4, …) — major isoforms first — so the
                // slice keeps the MAJOR ones rather than picking by
                // topology divergence. A gene with many isoforms would
                // otherwise overflow the tab strip (and add dead 404 tabs
                // for isoforms AFDB doesn't model). The §Isoforms table
                // below still lists EVERY isoform; this cap is 3D-only.
                // Defensive filter: some annotated records (e.g. TACSTD2)
                // carry the canonical accession itself inside
                // `isoform_topologies`. The 3D viewer already renders the
                // canonical as its own dedicated tab above this list, so
                // including it again here surfaces a duplicate "Isoform"
                // tab pointing at the same AFDB model. Same upstream bug
                // as in IsoformsCard; same fix.
                ...rec.deterministic_features.isoform_topologies
                  .filter((iso) => iso.isoform_id !== rec.gene.uniprot_acc)
                  .slice(0, 3)
                  .map((iso) => ({
                    source: "afdb" as const,
                    id: `iso-${iso.isoform_id}`,
                    label: _isoformLabel(iso.isoform_id),
                    sublabel: iso.isoform_id,
                    uniprot_acc: iso.uniprot_acc,
                    uniprot_acc_full: iso.isoform_id,
                    topology: iso.per_residue_topology,
                    // IsoformTopology doesn't carry `deeptmhmm_type`
                    // (TM / SP+TM / etc.) — synthesize a best-effort
                    // value from the topology string so the GLOB
                    // caption etc. still render sensibly on variant
                    // switch.
                    deeptmhmm_type: _inferDeepTMHMMType(
                      iso.per_residue_topology,
                    ),
                  })),
                ...(
                  [
                    ["mouse", "Mouse ortholog"],
                    ["cynomolgus", "Cyno ortholog"],
                  ] as const
                ).flatMap(([species, label]) =>
                  rec.deterministic_features.orthologs[species]
                    .filter(
                      (o) => o.is_canonical && !!o.per_residue_topology,
                    )
                    .map((o) => {
                      const topo = o.per_residue_topology as string;
                      return {
                        source: "afdb" as const,
                        id: `ortholog-${species}-${o.ortholog_uniprot_acc}`,
                        label,
                        sublabel: o.ortholog_uniprot_acc,
                        uniprot_acc: o.ortholog_uniprot_acc,
                        uniprot_acc_full: o.ortholog_uniprot_acc,
                        topology: topo,
                        deeptmhmm_type: _coerceDeepTMHMMType(
                          o.deeptmhmm_label,
                          topo,
                        ),
                      };
                    }),
                ),
              ]}
            />
            {/* Legend moved INSIDE <StructureViewer> so it can
                switch between the M/O/I/S/B topology key and the
                EC/IC/TM sites key based on the viewer's internal
                viewMode state. */}
            {/* AFDB stats moved INSIDE <StructureViewer> as part of
                the new per-variant caption. The caption renders the
                pLDDT pill + disordered fraction + AFDB entry link
                for the active variant (canonical reuses
                rec.deterministic_features.structure; isoforms /
                orthologs lazy-fetch AFDB metadata at click time;
                experimental shows resolution + method + RCSB link
                instead). */}
            {/* SURFACE-Bind summary <dl> was removed — it duplicated the
                §SURFACE-Bind card (which carries the same site count,
                seed total, and surface-bind.inria.fr link in a richer
                presentation) AND the Summary metrics SURFACE-Bind chip
                (which gives the catalog-filter view). One source of
                truth: the SurfaceBindCard section below. */}
            {/* Old DeepTMHMM-orientation caption removed — the new
                StructureViewer caption already names the model + the
                per-variant pLDDT / disordered stats; the orientation
                hint is implicit in the membrane slab shown above. */}
          </aside>
        ) : null}
      </div>

    </header>
  );
}
