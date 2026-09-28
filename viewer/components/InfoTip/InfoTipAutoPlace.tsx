"use client";

import { useEffect } from "react";

/**
 * InfoTipAutoPlace — a single document-level listener that keeps every
 * InfoTip popover fully on-screen and legible. Mounted once in
 * `<Shell>`; the InfoTip itself stays a pure server component (no
 * per-tooltip hydration island — see InfoTip.tsx for why that matters
 * at ~30-60 tips per gene page).
 *
 * It handles two failure modes a JS-free popover can't:
 *
 * 1. **Viewport-edge overflow.** The popover is positioned purely in
 *    CSS (centered, or left/right via the `align` prop), so a centered
 *    popover on a right-column trigger — or a wide one near the left
 *    edge — can spill off-screen. The FiltersCard group tips are the
 *    worst case: they render in a `repeat(auto-fit, …)` grid, so the
 *    same tip lands in a left column on one viewport and a right column
 *    on another. For these the positioner writes a `--infotip-shift`
 *    custom property that every popover variant folds into its
 *    `translateX`, clamping it back on-screen with an 8px margin.
 *
 * 2. **Clipping by a scroll container.** A popover inside an
 *    `overflow: auto/hidden` ancestor (the catalog table's
 *    `.tableScroll`, whose column headers carry InfoTips) is clipped to
 *    that box. With a filtered-down table — searching one gene leaves a
 *    ~100px-tall scroll box — the popover was cut off after two lines
 *    and scrolled inside the table instead of overlaying the page. It
 *    was also squeezed to its `min-width`, because an absolutely
 *    positioned popover shrink-wraps to its narrow column cell. For
 *    these the positioner lifts the popover to `position: fixed` at the
 *    trigger's viewport coordinates, which escapes the clip and sizes
 *    it against the viewport instead of the cell.
 *
 * One capture-phase listener on `document` handles every tip on the
 * page; `closest("[data-infotip]")` is a cheap hit-test.
 */

const MARGIN = 8;
/** Matches the CSS `top: calc(100% + 0.45rem)` trigger→popover gap, so
 *  the `.wrap::after` hover bridge still spans it in fixed mode. */
const GAP_REM = 0.45;

/** True when an ancestor between `el` and the document root clips its
 *  overflow — i.e. an absolutely positioned popover would be cut off. */
function hasClippingAncestor(el: Element): boolean {
  for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) {
    const cs = getComputedStyle(n);
    if (cs.overflowX !== "visible" || cs.overflowY !== "visible") return true;
  }
  return false;
}

function resetInline(pop: HTMLElement) {
  pop.style.removeProperty("position");
  pop.style.removeProperty("top");
  pop.style.removeProperty("left");
  pop.style.removeProperty("right");
  pop.style.removeProperty("transform");
  pop.style.removeProperty("max-height");
  pop.style.setProperty("--infotip-shift", "0px");
}

/** Place a popover with `position: fixed` just below its trigger,
 *  honouring the InfoTip `align` variant and clamping to the viewport. */
function placeFixed(wrap: Element, pop: HTMLElement) {
  const trigger = wrap.querySelector("button") ?? wrap;
  const t = trigger.getBoundingClientRect();
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const gap =
    GAP_REM * parseFloat(getComputedStyle(document.documentElement).fontSize);

  pop.style.position = "fixed";
  pop.style.right = "auto";
  pop.style.transform = "none";
  pop.style.left = "0px";
  pop.style.top = "0px";
  // Measure at the viewport origin, where the popover lays out against
  // its own max-width rather than the column cell it lives in.
  const { width } = pop.getBoundingClientRect();

  const align = pop.dataset.align;
  let left =
    align === "end"
      ? t.right - width
      : align === "start"
        ? t.left
        : t.left + t.width / 2 - width / 2;
  left = Math.max(MARGIN, Math.min(left, vw - MARGIN - width));
  const top = t.bottom + gap;

  pop.style.left = `${Math.round(left)}px`;
  pop.style.top = `${Math.round(top)}px`;
  // Scroll internally rather than run off the bottom of the viewport.
  pop.style.maxHeight = `${Math.max(120, Math.round(vh - top - MARGIN))}px`;

  // A transformed ancestor (e.g. a `.reveal` section mid-animation)
  // becomes the containing block for `position: fixed`, offsetting the
  // popover. Correct by the measured delta so it lands where intended.
  const r = pop.getBoundingClientRect();
  const dx = Math.round(left - r.left);
  const dy = Math.round(top - r.top);
  if (dx !== 0) pop.style.left = `${Math.round(left) + dx}px`;
  if (dy !== 0) pop.style.top = `${Math.round(top) + dy}px`;
}

function place(wrap: Element) {
  const pop = wrap.querySelector<HTMLElement>('[role="tooltip"]');
  if (!pop) return;
  // Reset any prior placement so we measure the CSS-default position.
  resetInline(pop);
  const rect = pop.getBoundingClientRect();
  if (rect.width === 0) return; // not laid out (hidden section)

  if (hasClippingAncestor(wrap)) {
    placeFixed(wrap, pop);
    return;
  }

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

export function InfoTipAutoPlace() {
  useEffect(() => {
    let active: Element | null = null;

    function onActivate(e: Event) {
      const target = e.target as Element | null;
      const wrap = target?.closest?.("[data-infotip]");
      if (!wrap) return;
      active = wrap;
      place(wrap);
    }

    // A fixed-position popover doesn't move with its trigger, so re-place
    // the open one when anything scrolls (page or the table's own scroll
    // box) or the viewport resizes.
    function onReflow() {
      if (!active) return;
      if (!active.matches(":hover, :focus-within")) {
        active = null;
        return;
      }
      place(active);
    }

    // Capture phase so we catch the event before the CSS :hover /
    // :focus-within reveal paints — the popover keeps its layout box
    // while `visibility: hidden`, so measuring here is accurate.
    document.addEventListener("pointerover", onActivate, true);
    document.addEventListener("focusin", onActivate, true);
    document.addEventListener("scroll", onReflow, true);
    window.addEventListener("resize", onReflow);
    return () => {
      document.removeEventListener("pointerover", onActivate, true);
      document.removeEventListener("focusin", onActivate, true);
      document.removeEventListener("scroll", onReflow, true);
      window.removeEventListener("resize", onReflow);
    };
  }, []);

  return null;
}
