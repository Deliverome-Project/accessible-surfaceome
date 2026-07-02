"use client";

import type { ReactNode } from "react";
import { chipJumpTargets, type ChipJumpTab } from "../../../../lib/chipJumpTargets";
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
 *      ``history.replaceState`` and dispatch a synthetic ``hashchange``
 *      event so ``<SectionTabs>``'s existing listener swaps sections.
 *      ``replaceState`` (not ``pushState``) avoids polluting the back
 *      stack with an entry per chip click.
 *   2. In the next animation frame, look up the destination by id,
 *      scroll it into view, add ``.chip-jump-flash`` for ~1.2 s to draw
 *      the eye, and move focus so a keyboard user's caret follows the
 *      visual jump. The flash class self-suppresses under
 *      ``prefers-reduced-motion: reduce`` (see globals.css).
 *   3. Missing destination is a no-op with a ``console.warn`` in dev.
 *
 * `chipJumpTargets` is imported for the type-narrowing side-effect only —
 * it is not called here; the caller passes the pre-resolved ``targetId``.
 *
 * See docs/superpowers/specs/2026-07-01-clickable-summary-chip-jump-design.md.
 */
export function ChipJumpButton({
  targetId,
  tabId,
  ariaLabel,
  children,
}: ChipJumpButtonProps) {
  // Reference `chipJumpTargets` at runtime so the value import isn't
  // tree-shaken away — its presence anchors the ChipJumpTab type to
  // the same module a caller resolves ids from.
  void chipJumpTargets;

  const onActivate = () => {
    if (typeof window === "undefined") return;
    const desiredHash = `#section-${tabId}`;
    const needsTabSwitch = window.location.hash !== desiredHash;
    if (needsTabSwitch) {
      window.history.replaceState({}, "", desiredHash);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
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
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      el.classList.add("chip-jump-flash");
      window.setTimeout(() => el.classList.remove("chip-jump-flash"), 1300);
      // Move keyboard focus so an assistive-tech reader lands at the
      // destination. `preventScroll` lets the smooth scroll above own
      // the visual motion.
      if (typeof (el as HTMLElement).focus === "function") {
        (el as HTMLElement).focus({ preventScroll: true });
      }
    });
  };

  return (
    <button
      type="button"
      className={styles.jumpTrigger}
      aria-label={ariaLabel}
      data-chip-jump-target={targetId}
      data-chip-jump-tab={tabId}
      onClick={onActivate}
    >
      {children}
    </button>
  );
}
