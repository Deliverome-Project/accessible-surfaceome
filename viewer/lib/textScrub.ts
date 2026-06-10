/**
 * Defensive scrubbers for synthesizer + builder prose before it
 * reaches the reader. The deep-dive's freeform rationale fields
 * (executive_summary.one_paragraph, surface_evidence.grade_rationale,
 * biological_context.grade_rationale, accessibility_context_summary,
 * various per-block .rationale strings) sometimes leak the agent's
 * internal pipeline namespace into user-facing prose — e.g.
 * "The entire A1 ledger consistently places BAX at intracellular
 *  compartments..." (real example from a deep-dive run).
 *
 * The synthesizer prompt has a Hard Ban list for `confidence_reasoning`
 * (system.md §"Hard ban") but the same rule is NOT enforced on the
 * other prose fields, so the model occasionally writes "the A1 ledger"
 * / "the merged A1+A2 evidence" / etc. Until the prompt-level fix
 * lands AND every record has been re-annotated, the viewer rewrites
 * these phrases at render time so the leak never reaches the reader.
 *
 * Naming policy: when the prose is rewritten, prefer the same
 * substitutions the synthesizer prompt itself prescribes (system.md
 * lines 99-106): `the A1 ledger` → `the evidence`, `A1+A2 evidence`
 * → `the evidence`, etc. Reader sees "the evidence", which is what
 * the agent should have written in the first place.
 */

/** Strip the agent's internal a1/a2 ledger jargon from freeform prose.
 *
 *  Handles (case-insensitive) the phrasings that have been observed
 *  in actual records:
 *    - "the entire A1 ledger" / "the A1 ledger" / "A1 ledger"
 *    - "A1+A2 ledger" / "A1/A2 ledger" / "the merged A1+A2 ledger"
 *    - "A1 evidence" / "the A2 biology" / "A1+A2 evidence"
 *    - "the merged ledger" (synthesizer's pipeline name)
 *
 *  Deliberately does NOT touch:
 *    - Standalone "A1" / "A2" — real protein names (adenosine A1
 *      receptor, GABA-A subunits, etc.) use this token. The
 *      pipeline-jargon phrasings always pair A1/A2 with a noun
 *      ("ledger" / "evidence" / "biology"); scrub on the phrase,
 *      not the token.
 *    - "a1_evi_NN" / "a2_evi_NN" tokens — those become EvidenceChips
 *      via :func:`linkifyEvidenceRefs`; the lowercase + underscore
 *      shape never collides with these patterns.
 */
export function scrubAgentJargon(
  text: string | null | undefined,
): string {
  if (!text) return "";
  return (
    text
      // Compound forms first ("the entire A1+A2 ledger" /
      // "the merged A1+A2 ledger" / "A1+A2 evidence" etc.).
      .replace(
        /\b(?:the\s+(?:entire|merged)\s+)?A[12]\s*[+/]\s*A[12]\s+(?:ledger|evidence|biology|context|axis|claims?)\b/gi,
        "the evidence",
      )
      // "the entire A1 ledger" / "the A1 ledger".
      .replace(
        /\bthe\s+(?:entire\s+)?A[12]\s+(?:ledger|evidence|biology|context|axis)\b/gi,
        "the evidence",
      )
      // Bare "A1 ledger" / "A2 evidence" / "A1 biology" / "A2 axis".
      .replace(
        /\bA[12]\s+(?:ledger|evidence|biology|context|axis|claims?|planner|trim|select)\b/gi,
        "evidence",
      )
      // Possessive: "A1's" / "A2's".
      .replace(/\bA[12]['’]s\s+/g, "the ")
      // Synthesizer pipeline self-references that don't carry A1/A2
      // but mean the same thing.
      .replace(/\bthe\s+merged\s+ledger\b/gi, "the evidence")
      // Collapse double spaces the substitutions can leave behind.
      .replace(/[ \t]{2,}/g, " ")
      // Tidy " ." / " ," / " ;" left after a trailing-word removal.
      .replace(/\s+([.,;:])/g, "$1")
      .trim()
  );
}

/** Strip inline `a[12]_evi_NN` annotation tokens from a string.
 *
 *  Used on the verbatim quote (where these tokens come through as
 *  noise — the colleague flagged them as "weird hashes") and the
 *  agent's claim prose displayed in :class:`EvidenceDrawer`. The
 *  cited-evidence chip strip remains the right surface for "what
 *  backs this claim?" — the drawer body prose itself should read
 *  clean.
 *
 *  Do NOT apply this to fields that flow through
 *  :func:`linkifyEvidenceRefs` — those depend on the tokens being
 *  present so the chip transformer can find them.
 */
export function scrubEvidenceTokens(
  text: string | null | undefined,
): string {
  if (!text) return "";
  return text
    // Paren-wrapped citation blocks: " (a1_evi_03)" /
    // "(a1_evi_03, a2_evi_07)".
    .replace(/\s*\((?:a[12]_evi_\d+(?:\s*[,;]\s*(?:a[12]_evi_\d+|\d+))*)\)/g, "")
    // Bare tokens or comma-joined runs of them:
    // "X a1_evi_03." / "X a1_evi_03, a2_evi_07."
    .replace(/\s*a[12]_evi_\d+(?:\s*[,;]\s*(?:a[12]_evi_\d+|\d+))*/g, "")
    // Collapse double spaces the removals can leave behind.
    .replace(/[ \t]{2,}/g, " ")
    // Tidy " ." / " ," left after a trailing-token removal.
    .replace(/\s+([.,;:])/g, "$1")
    .trim();
}
