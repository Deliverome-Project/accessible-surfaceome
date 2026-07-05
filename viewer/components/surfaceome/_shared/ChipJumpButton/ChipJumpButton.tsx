"use client";

import type { ReactNode } from "react";
import type { ChipJumpTab } from "../../../../lib/chipJumpTargets";
import styles from "./ChipJumpButton.module.css";

interface ChipJumpButtonProps {
  /** DOM id of the destination element on the target tab. Must match
   *  a value produced by ``viewer/lib/chipJumpTargets``. */
  targetId: string;
  /** SectionTabs section id (the string that follows ``#section-``).
   *  Constrained to the tab set the id map knows about, so a caller
   *  can't wire a chip to a nonexistent tab. */
  tabId: ChipJumpTab;
  /** aria-label describing the jump (e.g. "Jump to rationale: Known ligand").
   *  Read by screen readers; also used as a title tooltip fallback. */
  ariaLabel: string;
  /** The pill (or any chip content) rendered inside the button. */
  children: ReactNode;
}

/**
 * Wraps a chip so it acts as a one-click shortcut to a destination row /
 * block on one of the top-level tabs. Behavior on click / Enter / Space:
 *
 *   1. If the destination tab isn't active, update the URL hash via
 *      ``history.pushState`` and dispatch a synthetic ``hashchange``
 *      event so ``<SectionTabs>``'s existing listener swaps sections.
 *      ``pushState`` (not ``replaceState``) is a deliberate call: the
 *      reader who clicks a chip to jump away should be able to press
 *      the browser back button to return to the §01 Summary metrics
 *      view they were reading. Same pattern as clicking a tab in
 *      ``<SectionTabs>`` (each tab click is back-navigable).
 *   2. In the next animation frame, look up the destination by id,
 *      scroll it into view, add ``.chip-jump-flash`` for ~1.2 s to draw
 *      the eye, and move focus so a keyboard user's caret follows the
 *      visual jump. The flash class self-suppresses under
 *      ``prefers-reduced-motion: reduce`` (see globals.css).
 *   3. Missing destination is a no-op with a ``console.warn`` in dev.
 *
 * See docs/superpowers/specs/2026-07-01-clickable-summary-chip-jump-design.md.
 */
export function ChipJumpButton({
  targetId,
  tabId,
  ariaLabel,
  children,
}: ChipJumpButtonProps) {
  const onActivate = () => {
    if (typeof window === "undefined") return;
    const desiredHash = `#section-${tabId}`;
    const needsTabSwitch = window.location.hash !== desiredHash;
    // ALWAYS push a history entry — even for a jump whose target is on the
    // already-active tab. The browser Back button should return to THIS
    // pre-jump view (the §01 Summary / whatever section the reader was on),
    // never skip past the gene page to the previously-viewed gene. The old
    // code only pushed on a tab switch, so a same-tab jump (e.g. a Summary
    // metric chip pointing at another Summary block) left no back-entry and
    // Back navigated away from the gene entirely. `pushState` adds an entry
    // even when the hash is unchanged.
    window.history.pushState({}, "", desiredHash);
    // Only fire hashchange when the destination tab actually differs, so
    // SectionTabs doesn't churn on a same-tab jump.
    if (needsTabSwitch) {
      window.dispatchEvent(new Event("hashchange"));
    }
    // Wait one frame for SectionTabs to toggle data-active so the
    // destination element is measurable when we scroll to it.
    window.requestAnimationFrame(() => {
      const el = document.getElementById(targetId);
      if (!el) {
        if (process.env.NODE_ENV !== "production") {
          // eslint-disable-next-line no-console
          console.warn(
            `[ChipJumpButton] destination id "${targetId}" not found in the DOM. ` +
              "Chip and destination are out of sync — check viewer/lib/chipJumpTargets.",
          );
        }
        return;
      }
      // Restart the flash cleanly on rapid re-clicks: clear any pending
      // remove-class timer for THIS element before starting a new one.
      // Otherwise a second click's flash gets cut short when the first
      // click's timeout fires mid-animation.
      const prev = (el.dataset.chipJumpFlashTimer ?? "").trim();
      if (prev) {
        window.clearTimeout(Number(prev));
      }
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      el.classList.remove("chip-jump-flash");
      // Force a reflow so re-adding restarts the CSS animation from 0.
      void el.offsetWidth;
      el.classList.add("chip-jump-flash");
      const timer = window.setTimeout(() => {
        el.classList.remove("chip-jump-flash");
        delete el.dataset.chipJumpFlashTimer;
      }, 1300);
      el.dataset.chipJumpFlashTimer = String(timer);
      // Move keyboard focus so an assistive-tech reader lands at the
      // destination. `preventScroll` lets the smooth scroll above own
      // the visual motion.
      if (typeof (el as HTMLElement).focus === "function") {
        (el as HTMLElement).focus({ preventScroll: true });
      }
    });
  };

  // Use a `<span role="button">` (not `<button>`) so the wrapped
  // `<StatusPill>` can host an InfoTip-styled popover (`<span
  // role="tooltip">`) or a hover title-popover with rich content
  // (`<p>`, `<ul>`, etc.) without triggering nested-button / invalid
  // button-content-model DOM recovery. A real `<button>` may only
  // contain phrasing content and no other button — the popover span
  // sometimes contains `<p>` / `<ul>` and the InfoTip trigger itself
  // is a `<button>`, so wrapping in a `<button>` risks the browser
  // auto-closing our button and reparenting the tooltip.
  const onKeyDown = (e: React.KeyboardEvent<HTMLSpanElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onActivate();
    }
  };
  return (
    <span
      role="button"
      tabIndex={0}
      className={styles.jumpTrigger}
      aria-label={ariaLabel}
      data-chip-jump-target={targetId}
      data-chip-jump-tab={tabId}
      onClick={onActivate}
      onKeyDown={onKeyDown}
    >
      {children}
    </span>
  );
}
