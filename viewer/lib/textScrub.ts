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

/** Strip JATS-style HTML tags from a verbatim quote.
 *
 *  When the deep-dive agent quotes from PMC JATS XML it pulls the
 *  raw markup into the verbatim, which the drawer would otherwise
 *  render literally:
 *    - inline italics — `"…expression patterns of <i>ABC</i> transporter…"`
 *    - structured-abstract section headings — `"<h4>Background</h4>Severe
 *      Omicron cases…<h4>Results</h4>We identify CD63…"` (PMID 41818370,
 *      the bug the user flagged on CD63's EVI drawer; affects 42 records
 *      in the cohort).
 *
 *  Strip the inline tags rather than render them as React `<em>` /
 *  `<strong>`: the verbatim is there to let the reader cross-check the
 *  agent's source, and the source link sits directly above for italic-
 *  aware rendering. Plain text keeps the implementation safe (no
 *  `dangerouslySetInnerHTML`) and the quote readable.
 *
 *  Headings are transformed `<h[1-6]>X</h[1-6]>` → ` X: ` so the section
 *  label survives as an inline marker — "Background: …injury. Results: …"
 *  reads cleanly, where a bare strip would collide the label into the
 *  next sentence ("BackgroundSevere Omicron…").
 *
 *  Conservative on what gets stripped: only tags whose first char inside
 *  `<` is a letter. `<5%` (math, not a tag) passes through untouched.
 */
export function stripInlineHtml(text: string | null | undefined): string {
  if (!text) return "";
  return text
    // 1. Structured-abstract section headings — turn into inline labels
    //    so "Background"/"Methods"/"Results"/"Conclusions" survive as
    //    readable separators instead of evaporating into a wall of text.
    .replace(
      /<h([1-6])[^>]*>\s*([^<]+?)\s*<\/h\1>/gi,
      " $2: ",
    )
    // 2. JATS inline + block tags we've seen leak. Whitelist keeps us
    //    safe from over-scrubbing legitimate angle-bracket text.
    .replace(
      /<\/?(?:i|b|em|strong|sub|sup|italic|bold|subscript|superscript|sec|p|title|list|list-item|xref|ext-link|break)(?:\s+[^>]*)?\/?>/gi,
      "",
    )
    // 3. Normalize Unicode whitespace + hyphen variants so quotes render
    //    cleanly and are search/copy-paste friendly. Conservative
    //    whitelist — only the chars that visually equal an ASCII
    //    counterpart get converted:
    //      • U+00A0  NO-BREAK SPACE      → ` ` (regular space)
    //      • U+2009  THIN SPACE          → ` `
    //      • U+2010  HYPHEN              → `-`
    //      • U+2011  NON-BREAKING HYPHEN → `-`
    //      • U+2212  MINUS SIGN          → `-`
    //    Deliberately LEAVES legitimate typography untouched:
    //    en-dash (U+2013), em-dash (U+2014), curly quotes (U+2018/9),
    //    Greek letters (α/β/κ/μ), ±, ×, °, →, ′, ≥. Those convey
    //    distinct semantic meaning in scientific prose.
    .replace(/[  ]/g, " ")
    .replace(/[‐‑−]/g, "-")
    // 4. Tidy whitespace inside inline parenthetical citations — PMC
    //    sources frequently emit `(Author et al., 2020 )` with a stray
    //    trailing space before the close paren (and occasionally a
    //    leading one). Cosmetic but distracting at quote-density.
    .replace(/\(\s+/g, "(")
    .replace(/\s+\)/g, ")")
    .replace(/[ \t]{2,}/g, " ")
    // Tidy up `injury. Results:` cases — the heading transform leaves a
    // space before the punctuation when a sentence terminated right
    // before the heading and the heading inserted its leading space.
    .replace(/\s+([.,;:])/g, "$1")
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
