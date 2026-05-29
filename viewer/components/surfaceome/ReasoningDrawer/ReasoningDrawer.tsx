"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import {
  EvidenceChipList,
  linkifyEvidenceRefs,
} from "../EvidenceChip/EvidenceChip";
import styles from "./ReasoningDrawer.module.css";

interface Props {
  /** Eyebrow line in the drawer header, e.g. "Confidence · Moderate". */
  eyebrow: string;
  /** Drawer title, e.g. "Why this confidence?". */
  title: string;
  /** Accessible region label for the slide-in aside. */
  ariaLabel: string;
  /** Trigger chip text. Defaults to "Reasoning" — sentence case, brown
   *  ``--ink-soft`` per the design's "click for reasoning" register. */
  triggerLabel?: string;
  /** Extra class appended to the trigger button. Lets a caller adjust
   *  contextual layout — e.g. the Triage row is baseline-aligned and
   *  zeroes the chip's default top margin. The base chip styling always
   *  applies; this only adds to it. */
  triggerClassName?: string;
  /** Evidence-claim IDs rendered as a chip strip at the bottom of the
   *  drawer. Each chip dispatches the page-level
   *  ``surfaceome:open-evidence`` event so the reader can drill into the
   *  source quote without leaving the panel. Empty / omitted hides the
   *  strip (e.g. the Triage drawer, whose reasoning predates the
   *  evidence ledger). */
  citedEvidenceIds?: readonly string[];
  /** Prose-body convenience. When provided, rendered as a styled
   *  paragraph. An empty / whitespace-only string self-hides the whole
   *  component (returns null) so callers can pass a maybe-empty field
   *  without guarding. Mutually exclusive with ``children``. */
  reasoning?: string;
  /** Structured body — an alternative to ``reasoning`` for drawers whose
   *  content isn't a single prose string (e.g. the state-dependence
   *  modulation list). When using ``children`` the CALLER guards
   *  emptiness (don't render the component when there's nothing to
   *  show). */
  children?: ReactNode;
}

/**
 * Generic slide-in reasoning drawer. One component backs every
 * "Reasoning ›" chip in the gene header (Confidence, Experimental
 * surface evidence, State dependence, Triage) so the trigger styling,
 * portal/stacking behavior, ESC + backdrop close, and cited-evidence
 * strip stay identical across all four. These were previously per-vital
 * forks (`ConfidenceReasoningDrawer`, `EvidenceGradeReasoningDrawer`)
 * that drifted — the trigger color + casing had to be fixed in two
 * places at once. One component, no drift.
 *
 * Same interaction pattern as the BenchmarkTable `RationaleDrawer`:
 * fixed right-side panel that translateX-slides in; bottom sheet under
 * 720px (CSS-only); × close + ESC + backdrop click-to-close.
 *
 * Portaled to `document.body` because the gene page wraps sections in a
 * `<Reveal>` whose `will-change`/`transform` would otherwise establish a
 * containing block for `position: fixed` and collapse the drawer to a
 * vertical sliver pinned inline. The portal hops it out so the fixed
 * positioning resolves against the viewport.
 */
export function ReasoningDrawer({
  eyebrow,
  title,
  ariaLabel,
  triggerLabel = "Reasoning",
  triggerClassName,
  citedEvidenceIds,
  reasoning,
  children,
}: Props) {
  const [isOpen, setIsOpen] = useState(false);
  // Track client mount so `createPortal(..., document.body)` is safe.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // ESC closes the drawer. Installed on window (not the drawer) so it
  // works regardless of focus.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen]);

  // Signal open/closed state on `document.body` so the global
  // EvidenceDrawer can detect "reasoning drawer is open" and shift
  // its own right-edge anchor leftward — side-by-side instead of
  // behind. Cleared on unmount so a stale value doesn't leak.
  useEffect(() => {
    if (typeof document === "undefined") return;
    if (isOpen) {
      document.body.dataset.reasoningDrawerOpen = "true";
    } else {
      delete document.body.dataset.reasoningDrawerOpen;
    }
    return () => {
      delete document.body.dataset.reasoningDrawerOpen;
    };
  }, [isOpen]);

  // Prose mode: an empty / blank reasoning string self-hides the whole
  // trigger. Structured (children) mode leaves the emptiness guard to
  // the caller.
  const proseMode = reasoning !== undefined;
  const hasProse = typeof reasoning === "string" && reasoning.trim().length > 0;
  if (proseMode && !hasProse) return null;

  // Prose body: run the reasoning through `linkifyEvidenceRefs` so
  // inline IDs like `a1_evi_13` become clickable EvidenceChips that
  // open the global EvidenceDrawer on click. The chips render inline
  // in the prose, not just at the bottom — readers can drill into the
  // specific evidence each sentence cites without scanning the
  // bottom strip.
  const body =
    children ??
    (reasoning ? (
      <p className={styles.drawerReasoning}>{linkifyEvidenceRefs(reasoning)}</p>
    ) : null);

  const overlay = (
    <>
      {isOpen ? (
        <div
          className={styles.backdrop}
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      ) : null}

      <aside
        className={`${styles.drawer} ${isOpen ? styles.drawerOpen : ""}`}
        role="region"
        aria-label={ariaLabel}
        aria-hidden={!isOpen}
        tabIndex={-1}
      >
        <div className={styles.drawerCard}>
          <button
            type="button"
            className={styles.drawerCloseBtn}
            onClick={() => setIsOpen(false)}
            aria-label="Close reasoning panel"
          >
            ×
          </button>
          <p className={`label-mono ${styles.drawerEyebrow}`}>{eyebrow}</p>
          <h2 className={styles.drawerTitle}>{title}</h2>
          {body}
          {citedEvidenceIds && citedEvidenceIds.length > 0 ? (
            <div className={styles.drawerEvidence}>
              <p className={`label-mono ${styles.drawerEvidenceLabel}`}>
                Cited evidence
              </p>
              <EvidenceChipList ids={citedEvidenceIds} />
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );

  return (
    <>
      <button
        type="button"
        className={`${styles.trigger}${triggerClassName ? ` ${triggerClassName}` : ""}`}
        onClick={() => setIsOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
      >
        {triggerLabel}
      </button>

      {mounted ? createPortal(overlay, document.body) : null}
    </>
  );
}
