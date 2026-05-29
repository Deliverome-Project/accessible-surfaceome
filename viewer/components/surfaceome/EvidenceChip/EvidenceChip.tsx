"use client";

import styles from "./EvidenceChip.module.css";

interface EvidenceChipProps {
  evidenceId: string;
  /** Optional short label override (default: the evidence_id itself, e.g. "a1_evi_03"). */
  label?: string;
  /** Optional one-line title for the tooltip (e.g. the agent's claim text). */
  title?: string;
}

/**
 * EvidenceChip — small monospace pill that opens the global
 * EvidenceDrawer for a single evidence_id.
 *
 * Communication is via a CustomEvent on `window` (not React context)
 * so a chip can live anywhere in the tree without prop-drilling a
 * setter — the drawer component is rendered once at the page level
 * and subscribes. The same chip shape (and styling) gets reused in:
 *
 *   • ExecutiveSummaryCard — top-level cited_evidence_ids
 *   • SurfaceEvidenceCard  — per-method chips
 *   • BiologicalContextCard — per-tissue chips
 *   • AccessibilityRisksCard — per-risk-item chips
 *   • EvidenceLedgerCard — the id pill itself is a chip
 *
 * Schema-matched to the v2 reference design (data/eval/surfaceome_v2_samples).
 */
export function EvidenceChip({ evidenceId, label, title }: EvidenceChipProps) {
  return (
    <button
      type="button"
      className={styles.chip}
      onClick={() => {
        window.dispatchEvent(
          new CustomEvent("surfaceome:open-evidence", {
            detail: { evidenceId },
          }),
        );
      }}
      title={title ?? `Open evidence ${evidenceId}`}
    >
      {label ?? evidenceId}
    </button>
  );
}

/**
 * EvidenceChipList — inline strip of EvidenceChips, with optional
 * label and a max-display cap (the v2 sample shows up to 12 chips
 * per block; over that, render an "+N more" overflow button that
 * expands the list inline).
 */
interface EvidenceChipListProps {
  ids: readonly string[];
  label?: string;
  maxVisible?: number;
}

export function EvidenceChipList({ ids, label, maxVisible = 12 }: EvidenceChipListProps) {
  if (!ids.length) return null;
  const head = ids.slice(0, maxVisible);
  const overflow = ids.length - head.length;
  return (
    <div className={styles.chipRow}>
      {label ? (
        <span className={`label-mono ${styles.chipRowLabel}`}>{label}</span>
      ) : null}
      <span className={styles.chips}>
        {head.map((id) => (
          <EvidenceChip key={id} evidenceId={id} />
        ))}
        {overflow > 0 ? (
          <span className={styles.chipOverflow} title={ids.slice(maxVisible).join(", ")}>
            +{overflow} more
          </span>
        ) : null}
      </span>
    </div>
  );
}

/**
 * linkifyEvidenceRefs — find ``aN_evi_NN`` patterns in prose text and
 * wrap each one in a clickable :func:`EvidenceChip`. Returns an array
 * of ``ReactNode``s (alternating string fragments + chip components)
 * suitable for direct JSX rendering.
 *
 * The LLM-generated prose fields (``grade_rationale``,
 * ``surface_form_rationale``, contradiction explanations, etc.) often
 * cite evidence inline as ``(a1_evi_06, high-weight)`` or
 * ``(a1_evi_09, a1_evi_15, moderate)``. Without linkification those
 * IDs are dead text — the reader has to mentally cross-reference the
 * Evidence ledger §. With it, each ID opens the global EvidenceDrawer
 * on click (same affordance as the chip strips below method rows).
 *
 * Pattern matched: ``\ba[12]_evi_\d+\b`` — case-sensitive, word-
 * bounded so it doesn't trigger on substrings like ``A1_EVI_03``
 * inside other tokens. Range refs like ``a1_evi_01–05`` (en-dash) are
 * NOT expanded — only the first ID gets linkified; the ``–05`` half
 * stays as text. Acceptable since the range form is rare and the
 * reader can click the first chip + scan the drawer for siblings.
 */
const EVIDENCE_REF_RE = /\b(a[12]_evi_\d+)\b/g;

export function linkifyEvidenceRefs(text: string): React.ReactNode[] {
  if (!text) return [text];
  const out: React.ReactNode[] = [];
  let lastIdx = 0;
  let chipKey = 0;
  for (const match of text.matchAll(EVIDENCE_REF_RE)) {
    const idx = match.index ?? 0;
    if (idx > lastIdx) {
      out.push(text.slice(lastIdx, idx));
    }
    const id = match[1];
    out.push(<EvidenceChip key={`evi-ref-${chipKey++}-${id}`} evidenceId={id} />);
    lastIdx = idx + id.length;
  }
  if (lastIdx < text.length) {
    out.push(text.slice(lastIdx));
  }
  return out.length ? out : [text];
}
