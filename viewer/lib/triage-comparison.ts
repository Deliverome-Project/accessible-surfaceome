/** Convert the derived `TriageSignal` enum back to the original
 *  triage verdict the agent actually emitted. The signal is a 1:1
 *  rename of `TriageVerdict` (yes | contextual | no), so the
 *  inversion is mechanical. Rendering the verdict instead of the
 *  signal matches what the synthesizer's prose quotes (e.g. SRC's
 *  confidence_reasoning: "Triage called verdict='no', …"). */
export function triageVerdictLabel(signal: string): string {
  if (signal === "likely_accessible") return "Yes";
  if (signal === "possibly_accessible") return "Contextual";
  if (signal === "unlikely") return "No";
  return "Unknown";
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
export function triageVsDeepDive(
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
    // contextual under "unlikely" triage IS a disagreement — the triage
    // missed a state-induced or trafficking-cycling surface that the
    // deep dive found (e.g. TGN46/TGOLN2: triage said `no` /
    // `endomembrane_resident`, the deep dive found CONTEXTUAL surface
    // via dual_localization with documented PM trafficking). Render as
    // `conflict` so the row shows a non-empty pill — "unclear" hides
    // the case entirely and the reader can't tell whether to trust the
    // triage chip or the deep-dive call. The deep dive wins on
    // conflict (it has the per-method evidence), and surfacing the
    // disagreement is the whole point of the pill.
    if (deepVerdict === "contextual") return "conflict";
    return "unclear";
  }
  return "unclear";
}
