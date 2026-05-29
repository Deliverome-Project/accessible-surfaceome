import type { ReactNode } from "react";
import styles from "./InfoTip.module.css";

interface InfoTipProps {
  /** Tooltip body. Plain text or small inline JSX (e.g. an `<a>` for
   *  a doi link). Renders inside an aria-described popover. */
  children: ReactNode;
  /** Glyph shown to the reader. Defaults to a small `ⓘ`. */
  glyph?: string;
  /** Aria-label for the trigger button. Defaults to "About this field". */
  label?: string;
  /** Additional class names for the trigger (e.g. for inline alignment
   *  inside a label-mono row). */
  triggerClassName?: string;
  /** Use a wider popover (max-width ~44rem vs the default ~28em) for
   *  long-prose tooltips that would otherwise wrap into a tall narrow
   *  column. */
  wide?: boolean;
}

/**
 * InfoTip — small provenance popover. **Pure server component, no
 * `"use client"`.**
 *
 * Behavior is CSS-only:
 * - Hover on the trigger (mouse) → popover shows.
 * - Focus on the trigger (keyboard Tab) → popover shows via
 *   `:focus-within` on the wrapper.
 * - Mouseleave / blur → popover hides.
 *
 * Why no JS: a typical gene page renders ~60 InfoTips (one per
 * vital cell + one per filter chip + per-method tooltips). Each
 * was a `"use client"` boundary with useState/useRef/useLayoutEffect
 * + click/hover/keyboard handlers + auto-flip viewport detection.
 * Collectively that's 60 hydration islands of overhead. Converting
 * to CSS-only drops it to zero — the popover is always in the DOM
 * (hidden via `visibility: hidden`) and the browser reveals it
 * natively on `:hover` / `:focus-within`.
 *
 * Trade-offs from the JS version:
 * - Lost: viewport-edge auto-flip (popover may extend off-screen
 *   for triggers near page edges). Acceptable; the popover has
 *   `max-width: 90vw` so it never exceeds the viewport width.
 * - Lost: click-to-pin (popover closes when hover/focus leaves;
 *   touch users get a brief tap-and-hold view, same as native
 *   `title="..."` behavior).
 * - Lost: explicit ESC handler (not needed — moving focus dismisses).
 * - Kept: keyboard accessibility via real `<button>` trigger
 *   (Tab reaches it, focus shows tooltip).
 * - Kept: `role="tooltip"` so screen readers identify the popover
 *   content as a tooltip.
 *
 * The popover is rendered as a `<span role="tooltip">` inside the
 * wrapper. It's always in the DOM (necessary for CSS sibling
 * selectors to fire on hover/focus); visibility is toggled via
 * `visibility: hidden` → `visible` so it's still in the a11y tree
 * when shown.
 */
export function InfoTip({
  children,
  glyph = "ⓘ",
  label = "About this field",
  triggerClassName,
  wide = false,
}: InfoTipProps) {
  return (
    <span className={styles.wrap}>
      <button
        type="button"
        className={`${styles.trigger} ${triggerClassName ?? ""}`.trim()}
        aria-label={label}
      >
        <span aria-hidden="true">{glyph}</span>
      </button>
      <span
        role="tooltip"
        className={`${styles.popover} ${wide ? styles.popoverWide : ""}`
          .replace(/\s+/g, " ")
          .trim()}
      >
        {children}
      </span>
    </span>
  );
}
