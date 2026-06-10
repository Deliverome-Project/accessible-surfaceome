import { scrubAgentJargon } from "../../../lib/textScrub";
import styles from "./EvidenceChip.module.css";

interface EvidenceChipProps {
  evidenceId: string;
  /** Optional short label override. Default is a reader-facing
   *  ``[NN]`` (citation-style) derived from the trailing index of the
   *  internal ``aN_evi_NN`` id — the ``a1`` / ``a2`` planner namespace
   *  is internal plumbing and must not surface in the UI. */
  label?: string;
  /** Optional one-line title for the tooltip (e.g. the agent's claim text). */
  title?: string;
}

/** Render-time label for an evidence id. The data loader renumbers
 *  every ``a[12]_evi_NN`` id into a per-record ``evi_N`` sequence (see
 *  ``lib/evidenceRenumber.ts``); this strips the ``evi_`` prefix so the
 *  chip shows just the bare number — no brackets, no lane prefix.
 *  Falls through to a legacy form (``a1_evi_03`` → ``3``) and finally
 *  to the raw id, so we never erase information if the loader is
 *  bypassed (tests, fixtures, etc.). */
export function defaultEvidenceLabel(evidenceId: string): string {
  const newForm = /^evi_(\d+)$/.exec(evidenceId);
  if (newForm) return newForm[1];
  const legacyForm = /^a[12]_evi_(\d+)$/.exec(evidenceId);
  if (legacyForm) return legacyForm[1];
  return evidenceId;
}

/**
 * EvidenceChip — small monospace pill that opens the global
 * EvidenceDrawer for a single evidence_id.
 *
 * **Pure server component, no `"use client"`.** Click handling is
 * delegated through the page-level :func:`EvidenceClickDelegator`
 * which mounts ONE `document.addEventListener("click", ...)` and
 * walks `closest("[data-evidence-id]")`. That lets a typical
 * gene page render 100+ chips (Surface evidence per-method strips
 * + per-observation rows + linkified inline refs + contradictions)
 * with a single hydration boundary instead of one per chip — the
 * Next.js 16 RSC chunk count drops accordingly and the
 * "/Surface evidence/" tab loads noticeably faster.
 *
 * Communication is still via a CustomEvent on `window` so a chip
 * can live anywhere in the tree without prop-drilling a setter —
 * the drawer component is rendered once at the page level and
 * subscribes. The same chip shape (and styling) gets reused in:
 *
 *   • ExecutiveSummaryCard — top-level cited_evidence_ids
 *   • SurfaceEvidenceCard  — per-method chips + linkified prose refs
 *   • BiologicalContextCard — per-tissue chips
 *   • AccessibilityRisksCard — per-risk-item chips
 *   • EvidenceLedgerCard — the id pill itself is a chip
 *
 * Schema-matched to the v2 SurfaceomeRecord reference design.
 */
export function EvidenceChip({ evidenceId, label, title }: EvidenceChipProps) {
  return (
    <button
      type="button"
      className={styles.chip}
      data-evidence-id={evidenceId}
      title={title ?? `Open evidence ${defaultEvidenceLabel(evidenceId)}`}
    >
      {label ?? defaultEvidenceLabel(evidenceId)}
    </button>
  );
}

/**
 * EvidenceChipList — inline strip of EvidenceChips, with an optional
 * label and a max-display cap. Over the cap, the remaining chips are
 * tucked behind a native `<details>` "+N more" toggle that EXPANDS them
 * inline — every chip stays clickable into the EvidenceDrawer.
 *
 * Previously "+N more" was a plain non-interactive `<span>`, so the
 * overflow evidence (e.g. "+34 more") was visible-but-unreachable. Using
 * `<details>` keeps this a pure server component (no `"use client"` /
 * useState) — the design's whole point is one delegated click listener,
 * not a hydration boundary per chip — while making the overflow openable.
 */
interface EvidenceChipListProps {
  ids: readonly string[];
  label?: string;
  maxVisible?: number;
}

export function EvidenceChipList({ ids, label, maxVisible = 12 }: EvidenceChipListProps) {
  if (!ids.length) return null;
  const head = ids.slice(0, maxVisible);
  const rest = ids.slice(maxVisible);
  return (
    <div className={styles.chipRow}>
      {label ? (
        <span className={`label-mono ${styles.chipRowLabel}`}>{label}</span>
      ) : null}
      <span className={styles.chips}>
        {/* Belt-and-suspenders unique key: the loader already dedupes
         *  ``cited_evidence_ids`` arrays after renumbering, but if any
         *  unrenumbered list slips through (test fixtures, offline
         *  local mode, future regression), `${id}-${i}` keeps React
         *  from throwing on duplicate keys. */}
        {head.map((id, i) => (
          <EvidenceChip key={`${id}-${i}`} evidenceId={id} />
        ))}
        {rest.length > 0 ? (
          <details className={styles.chipOverflowDetails}>
            <summary className={styles.chipOverflow}>+{rest.length} more</summary>
            {/* Revealed on toggle — each remaining id is a real chip that
                opens the EvidenceDrawer, same as the head chips. */}
            {rest.map((id, i) => (
              <EvidenceChip key={`${id}-${i + head.length}`} evidenceId={id} />
            ))}
          </details>
        ) : null}
      </span>
    </div>
  );
}

/**
 * linkifyEvidenceRefs — scan LLM-generated prose and replace inline
 * structured tokens with interactive UI:
 *
 *   1. Evidence IDs ``aN_evi_NN`` → clickable :func:`EvidenceChip`.
 *      Range refs like ``a1_evi_01–05`` (en-dash or hyphen) EXPAND
 *      to one chip per ID in the range — readers see every cited
 *      claim, not just the first.
 *
 *   2. Weight tokens (``high-weight``, ``moderate-weight``,
 *      ``low-weight`` always; bare ``high|moderate|low`` only when
 *      inside the same parenthesis as an evidence ref so we don't
 *      over-badge natural-prose adjectives) → small
 *      :func:`WeightBadge` pill.
 *
 *   3. PMID refs ``PMID:NNNN`` → external `<a>` to pubmed.ncbi.nlm.nih.gov
 *      so the reader can verify the primary source one click away.
 *
 * Returns an array of ``ReactNode``s (alternating string fragments
 * + chip / badge / link components) suitable for direct JSX rendering.
 */

// Token regex — combined alternation so we can walk the prose once
// and dispatch by capture group. The evidence-id prefix is now
// ``evi_`` (per-record renumbered by the loader); legacy
// ``a[12]_evi_`` is kept as a fallback for any prose that escapes
// the loader's rewrite (tests, fixtures, etc.).
//   m[1] = "evi_" or "a1_evi_" / "a2_evi_" prefix (single or range head)
//   m[2] = start number (zero-padded width preserved for output)
//   m[3] = optional range end number (when ``evi_01-05`` style)
//   m[4] = bare PMID number
//   m[5] = PMC article number (PubMed Central full-text link)
//   m[6] = "<weight>-weight" explicit form
//   m[7] = raw evidence-grade enum token (synthesizer prose often opens
//          grade_rationale with the literal enum, e.g.
//          "direct_multi_method — live flow, …") → render as a prettified
//          label so the reader never sees snake_case.
//   m[8] = bare "high" / "moderate" / "low" (context-checked)
const TOKEN_RE =
  /\b(evi_|a[12]_evi_)(\d+)(?:[–\-](\d+))?\b|\bPMID:(\d+)\b|\bPMC(\d+)\b|\b(high-weight|moderate-weight|low-weight)\b|\b(direct_multi_method|direct_single_method|supportive_but_indirect)\b|\b(high|moderate|low)\b/g;

// Normalize compact evidence-ref lists into fully-qualified ids before
// tokenizing. The synthesizer sometimes abbreviates a multi-ref citation
// as "(a1_evi_01, 02, 03)" — only the first ref carries the
// "a1_evi_" prefix and the rest are bare zero-padded numbers. Without
// this, the bare "02" / "03" fall through as plain text (the reported
// IZUMO4 bug). Within each parenthetical, rewrite a bare number that
// follows an evidence ref into "<prefix><NN>" so the main tokenizer
// turns every one into a chip. Only fires inside parens that already
// contain an evidence ref, so prose numbers (e.g. "(see Fig 2)") are
// untouched.
function _expandCompactRefs(text: string): string {
  return text.replace(/\(([^)]*(?:evi_|a[12]_evi_)\d+[^)]*)\)/g, (whole, inner) => {
    let prefix: string | null = null;
    const rewritten = inner.replace(
      /(evi_|a[12]_evi_)(\d+)|(?<=[,;]\s*)(\d+)\b/g,
      (m: string, p: string | undefined, _n: string, bare: string | undefined) => {
        if (p) {
          prefix = p;
          return m;
        }
        // bare number after a comma/semicolon — qualify it with the
        // running prefix (only once we've seen a real ref in this paren).
        if (bare && prefix) return `${prefix}${bare}`;
        return m;
      },
    );
    return `(${rewritten})`;
  });
}

// Prettified labels for the evidence-grade enum tokens (m[6]). Mirrors
// ``ENUM_LABELS`` in lib/enums.ts; kept local so this module stays
// dependency-light. Only the multi-word tokens are matched in TOKEN_RE —
// bare "conflicting" / "weak" are common English words and badging them
// inside free prose would over-fire.
const GRADE_LABELS: Record<string, string> = {
  direct_multi_method: "Direct, multi-method",
  direct_single_method: "Direct, single method",
  supportive_but_indirect: "Supportive but indirect",
};

// Pre-scan helper — mark every character offset that lives inside a
// parenthetical block that contains at least one evidence ref. Used
// to disambiguate bare ``moderate`` (a stance weight when in the
// same parens as ``a1_evi_NN``; otherwise natural-prose adjective).
function _markEvidenceParens(text: string): boolean[] {
  const marks = new Array(text.length).fill(false);
  for (const m of text.matchAll(/\(([^)]*(?:evi_|a[12]_evi_)\d+[^)]*)\)/g)) {
    const start = m.index ?? 0;
    const end = start + m[0].length;
    for (let i = start; i < end; i++) marks[i] = true;
  }
  return marks;
}

export function linkifyEvidenceRefs(text: string): React.ReactNode[] {
  if (!text) return [text];
  // Strip "A1 ledger" / "the merged A1+A2 evidence" / etc. BEFORE
  // expanding compact refs so the chip-pass never sees jargon-rewritten
  // mid-sentences. The scrub is conservative: it only touches phrases
  // that pair A1/A2 with a noun like "ledger" / "evidence" / "biology",
  // never the bare A1/A2 token (which can name real proteins).
  text = scrubAgentJargon(text);
  text = _expandCompactRefs(text);
  const inRefParen = _markEvidenceParens(text);
  const out: React.ReactNode[] = [];
  let lastIdx = 0;
  let key = 0;

  for (const match of text.matchAll(TOKEN_RE)) {
    const idx = match.index ?? 0;
    if (idx > lastIdx) {
      out.push(text.slice(lastIdx, idx));
    }

    if (match[1] !== undefined) {
      // Evidence ID (single or range).
      const prefix = match[1];
      const startStr = match[2];
      const endStr = match[3];
      const pad = startStr.length;
      const startN = parseInt(startStr, 10);
      const endN = endStr ? parseInt(endStr, 10) : startN;
      // Guard against pathological ranges in malformed prose
      // (e.g. ``a1_evi_05–01`` reverse range, or huge spans). Cap
      // at 50 expanded chips; render the literal text if the range
      // is reversed or absurd.
      if (endN >= startN && endN - startN <= 50) {
        for (let n = startN; n <= endN; n++) {
          const id = `${prefix}${String(n).padStart(pad, "0")}`;
          out.push(
            <EvidenceChip key={`evi-${key++}-${id}`} evidenceId={id} />,
          );
          if (n < endN) out.push(" ");
        }
      } else {
        // Malformed range — render the raw matched text as-is.
        out.push(match[0]);
      }
    } else if (match[4] !== undefined) {
      // PMID — outbound link to PubMed.
      const pmid = match[4];
      out.push(
        <a
          key={`pmid-${key++}-${pmid}`}
          href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.pmidLink}
          title={`Open PubMed entry PMID:${pmid} in a new tab`}
        >
          PMID:{pmid}
        </a>,
      );
    } else if (match[5] !== undefined) {
      // PMC article id — outbound link to the open-access full text on
      // PubMed Central. The agent cites primary sources as PMC IDs when
      // the paper is in PMC (vs PMID for the abstract record).
      const pmc = match[5];
      out.push(
        <a
          key={`pmc-${key++}-${pmc}`}
          href={`https://www.ncbi.nlm.nih.gov/pmc/articles/PMC${pmc}/`}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.pmidLink}
          title={`Open PubMed Central article PMC${pmc} in a new tab`}
        >
          PMC{pmc}
        </a>,
      );
    } else if (match[6] !== undefined) {
      // Explicit ``high-weight`` / ``moderate-weight`` / ``low-weight``
      // — always badge, the suffix makes the intent unambiguous.
      const weight = match[6].split("-")[0] as "high" | "moderate" | "low";
      out.push(<WeightBadge key={`w-${key++}`} weight={weight} />);
    } else if (match[7] !== undefined) {
      // Raw evidence-grade enum token — replace the snake_case literal
      // with its prettified label so the reader never sees
      // "direct_multi_method" in the grade_rationale prose.
      out.push(
        <span key={`grade-${key++}`}>{GRADE_LABELS[match[7]] ?? match[7]}</span>,
      );
    } else if (match[8] !== undefined) {
      // Bare ``high`` / ``moderate`` / ``low`` — badge only when
      // inside a parenthesis that contains an evidence ref. Outside
      // that context the same words are natural-prose adjectives
      // (``moderate quality``, ``high coverage``) and we leave them
      // as plain text to avoid false-positive pills.
      if (inRefParen[idx]) {
        const weight = match[8] as "high" | "moderate" | "low";
        out.push(<WeightBadge key={`w-${key++}`} weight={weight} />);
      } else {
        out.push(match[8]);
      }
    }

    lastIdx = idx + match[0].length;
  }
  if (lastIdx < text.length) {
    out.push(text.slice(lastIdx));
  }
  return out.length ? out : [text];
}

/**
 * WeightBadge — small inline pill labeling a structured stance
 * weight (``high`` / ``moderate`` / ``low``). Used by
 * :func:`linkifyEvidenceRefs` to surface the weight token from
 * ``grade_rationale`` parentheticals like
 * ``(a1_evi_06, high-weight)`` as a visual pill instead of leaving
 * it as inline text. Tone matches the stance-weight semantics
 * used elsewhere in the catalog (high = success/green;
 * moderate = warn/amber; low = neutral/muted).
 */
function WeightBadge({ weight }: { weight: "high" | "moderate" | "low" }) {
  const toneClass =
    weight === "high"
      ? styles.weightHigh
      : weight === "moderate"
        ? styles.weightModerate
        : styles.weightLow;
  return (
    <span className={`${styles.weightBadge} ${toneClass}`}>{weight}</span>
  );
}
