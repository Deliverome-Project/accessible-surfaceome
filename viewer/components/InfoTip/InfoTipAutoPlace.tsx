"use client";

import { useEffect } from "react";

/**
 * InfoTipAutoPlace — a single document-level listener that nudges any
 * InfoTip popover horizontally so it never spills past the viewport
 * edge. Mounted once in `<Shell>`; the InfoTip itself stays a pure
 * server component (no per-tooltip hydration island — see InfoTip.tsx
 * for why that matters at ~30-60 tips per gene page).
 *
 * Why this exists: the popover is positioned purely in CSS (centered,
 * or left/right via the `align` prop). A JS-free component can't know
 * where its trigger sits relative to the viewport, so a centered
 * popover on a right-column trigger — or a wide one near the left edge
 * — can overflow off-screen. The FiltersCard group tips are the worst
 * case: they render in a `repeat(auto-fit, …)` grid, so the same tip
 * lands in a left column on one viewport and a right column on another.
 * No static CSS rule can fix that.
 *
 * This delegated positioner measures the popover on hover/focus and
 * writes a `--infotip-shift` custom property that every popover variant
 * folds into its `translateX`, clamping it back on-screen with an 8px
 * margin. One capture-phase listener on `document` handles every tip on
 * the page; `closest("[data-infotip]")` is a cheap hit-test.
 */
export function InfoTipAutoPlace() {
  useEffect(() => {
    const MARGIN = 8;

    function place(wrap: Element) {
      const pop = wrap.querySelector<HTMLElement>('[role="tooltip"]');
      if (!pop) return;
      // Reset any prior shift so we measure the CSS-default position.
      pop.style.setProperty("--infotip-shift", "0px");
      const rect = pop.getBoundingClientRect();
      if (rect.width === 0) return; // not laid out (hidden section)
      const vw = document.documentElement.clientWidth;
      let shift = 0;
      if (rect.left < MARGIN) {
        shift = MARGIN - rect.left;
      } else if (rect.right > vw - MARGIN) {
        shift = vw - MARGIN - rect.right;
      }
      if (shift !== 0) {
        pop.style.setProperty("--infotip-shift", `${Math.round(shift)}px`);
      }
    }

    function onActivate(e: Event) {
      const target = e.target as Element | null;
      const wrap = target?.closest?.("[data-infotip]");
      if (wrap) place(wrap);
    }

    // Capture phase so we catch the event before the CSS :hover /
    // :focus-within reveal paints — the popover keeps its layout box
    // while `visibility: hidden`, so measuring here is accurate.
    document.addEventListener("pointerover", onActivate, true);
    document.addEventListener("focusin", onActivate, true);
    return () => {
      document.removeEventListener("pointerover", onActivate, true);
      document.removeEventListener("focusin", onActivate, true);
    };
  }, []);

  return null;
}
