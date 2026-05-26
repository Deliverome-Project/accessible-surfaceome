"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import styles from "./ConfidenceReasoningDrawer.module.css";

interface Props {
  /** The synthesizer's user-facing rationale prose. Empty string
   *  hides the trigger entirely (the parent should usually guard
   *  this too — but we double-check here so the component renders
   *  nothing if it's ever passed empty content). */
  reasoning: string;
  /** The confidence value (`high` / `moderate` / `low`) so the
   *  drawer eyebrow can name it explicitly. */
  confidenceLabel: string;
}

/**
 * Slide-in side drawer for the synthesizer's per-gene confidence
 * rationale. Same visual + interaction pattern as the BenchmarkTable
 * `RationaleDrawer`:
 *
 *   * Fixed right-side panel that translateX-slides in on open
 *   * Bottom sheet under 720 px viewport (CSS-only, no JS branch)
 *   * × close button + ESC keyboard handler
 *   * Backdrop click-to-close
 *
 * Trigger is the "reasoning" text rendered inline next to the
 * confidence value in the gene-page header — see the `<button>`
 * below. Trigger styling mirrors the EvidenceLedgerCard `.summary`
 * (accent-colored, cursor: pointer, hover→ink) so it reads as a
 * subtle expand affordance, not a heavy CTA.
 *
 * Client component (we need `useState` + `useEffect` for ESC). The
 * `GeneHeader` parent stays server-rendered and just drops this in.
 */
export function ConfidenceReasoningDrawer({ reasoning, confidenceLabel }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  // Track when the component has mounted on the client so we can
  // safely call `createPortal(..., document.body)`. The portal is
  // load-bearing — see the block below the JSX for the gory details.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // ESC closes the drawer. Mirror of the BenchmarkTable pattern —
  // installed on window so we don't depend on drawer focus.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen]);

  if (!reasoning || !reasoning.trim()) return null;

  // Portal target for the drawer's fixed-position aside + backdrop.
  // This is REQUIRED, not cosmetic: the gene page wraps each section
  // in a `<Reveal>` div that carries `will-change: transform` (and a
  // no-op `transform: translate(0,0)` once the fade settles). Per
  // CSS spec, any ancestor with a non-`none` transform OR a
  // `will-change` that lists `transform`/`perspective`/`filter`
  // establishes a new containing block for `position: fixed`
  // descendants — i.e. `right: 0` no longer means "viewport right",
  // it means "the .reveal ancestor's right edge". The drawer then
  // collapses to ~zero width and renders as a tall vertical sliver
  // pinned inline next to the gene header instead of an offscreen
  // side panel. Portaling to `document.body` skips the .reveal
  // wrapper entirely so the fixed positioning resolves against the
  // viewport again.
  const overlay = (
    <>
      {/* Backdrop — click anywhere off the drawer to close. Lives
       *  below the drawer's z-index so the drawer stays interactive.
       *  Only mounted when the drawer is open so it doesn't intercept
       *  page-wide clicks at rest. */}
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
        aria-label={`Why this confidence is ${confidenceLabel}`}
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
          <p className={`label-mono ${styles.drawerEyebrow}`}>
            Confidence · {confidenceLabel}
          </p>
          <h2 className={styles.drawerTitle}>Why this confidence?</h2>
          <p className={styles.drawerReasoning}>{reasoning}</p>
        </div>
      </aside>
    </>
  );

  return (
    <>
      <button
        type="button"
        className={styles.trigger}
        onClick={() => setIsOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
      >
        reasoning
      </button>

      {mounted ? createPortal(overlay, document.body) : null}
    </>
  );
}
