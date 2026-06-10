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

/** Strip JATS-style inline HTML tags (`<i>` / `<b>` / `<sub>` / `<sup>`
 *  / `<em>` / `<strong>`) from a verbatim quote.
 *
 *  When the deep-dive agent quotes from PMC JATS XML it pulls the
 *  raw `<i>GENE</i>` italics markup into the verbatim, which the
 *  drawer would otherwise render literally — `"…expression patterns
 *  of <i>ABC</i> transporter genes…"`. A spot-check of 14 records
 *  found 80 such occurrences, dominating every other "weird text"
 *  pattern we looked at.
 *
 *  Strip the tags rather than render them as React `<em>` / `<strong>`:
 *  the verbatim is there to let the reader cross-check the agent's
 *  source, and the source link sits directly above for italic-aware
 *  rendering. Plain text keeps the implementation safe (no
 *  `dangerouslySetInnerHTML`) and the quote readable.
 */
export function stripInlineHtml(text: string | null | undefined): string {
  if (!text) return "";
  return text
    // Whitelist-style strip: only the JATS-common inline tags we've
    // actually seen leak. Anything else stays as-is so we don't
    // accidentally scrub legitimate angle-bracket text (e.g. ``<5%``).
    .replace(/<\/?(?:i|b|em|strong|sub|sup|italic|bold|subscript|superscript)>/gi, "")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
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
  // The id form is ``evi_NN`` after the loader's renumber pass; legacy
  // ``a[12]_evi_NN`` is kept so fixtures and pre-renumber fields still
  // scrub correctly.
  const tokenAlt = "(?:evi_|a[12]_evi_)\\d+";
  return text
    // Paren-wrapped citation blocks: " (evi_3)" / "(evi_3, evi_7)".
    .replace(
      new RegExp(`\\s*\\((?:${tokenAlt}(?:\\s*[,;]\\s*(?:${tokenAlt}|\\d+))*)\\)`, "g"),
      "",
    )
    // Bare tokens or comma-joined runs of them: "X evi_3." / "X evi_3, evi_7."
    .replace(
      new RegExp(`\\s*${tokenAlt}(?:\\s*[,;]\\s*(?:${tokenAlt}|\\d+))*`, "g"),
      "",
    )
    // Collapse double spaces the removals can leave behind.
    .replace(/[ \t]{2,}/g, " ")
    // Tidy " ." / " ," left after a trailing-token removal.
    .replace(/\s+([.,;:])/g, "$1")
    .trim();
}
