import { Fragment } from "react";
import type { CSSProperties, ReactNode } from "react";
import styles from "./StatusPill.module.css";
// Reuse the InfoTip popover styling directly so a chip's tooltip is
// pixel-identical to every other tooltip on the page (the `ⓘ` field
// popovers, the group-label tips, etc.). Importing the same CSS module
// means the `.wrap:hover .popover` reveal selector + hover-bridge +
// the document-level auto-placer (`data-infotip`) all apply unchanged —
// no duplicated, drift-prone copy of the popover rules.
import tip from "../../InfoTip/InfoTip.module.css";

type Tone =
  | "neutral"
  | "maroon"
  | "teal"
  | "amber"
  | "lavender"
  | "success"
  | "warn"
  | "danger";

interface StatusPillProps {
  tone?: Tone;
  size?: "sm" | "md";
  children: ReactNode;
  /** Tooltip body. When set, the pill renders the shared styled
   *  popover (matching `<InfoTip>`) on hover/focus rather than the
   *  fleeting native `title=` browser tooltip. A `string` keeps its
   *  `\n` line breaks (rendered as `<br />`; a blank line `\n\n`
   *  collapses via the popover's `br + br` rule). A `ReactNode` (e.g. a
   *  shared entry from `lib/tooltips`) is rendered as-is, so a chip can
   *  reuse the exact same tooltip body as the rest of the page instead
   *  of a drift-prone string copy. */
  title?: ReactNode;
  /** Opt back into the OS-native `title=` tooltip instead of the
   *  styled popover. Use ONLY for pills nested inside an
   *  `overflow: auto/hidden` ancestor (e.g. a horizontally-scrollable
   *  table), where the absolutely-positioned CSS popover would be
   *  clipped by the scroll container. The native tooltip is
   *  OS-rendered so it escapes the clip. */
  nativeTooltip?: boolean;
  style?: CSSProperties;
}

/**
 * StatusPill — single editorial badge used for surface-status,
 * tier, direction, strength, triage, severity, etc. Tones map to
 * design-system color families; no inline hex codes.
 *
 * When given a `title`, the pill itself becomes the hover/focus
 * trigger for a styled popover that reuses the InfoTip CSS — so chip
 * tooltips read like the rest of the page's tooltips instead of the
 * OS-native `title=` bubble (delayed, unstyled, not theme-aware).
 */
export function StatusPill({
  tone = "neutral",
  size = "md",
  children,
  title,
  nativeTooltip = false,
  style,
}: StatusPillProps) {
  const pillClass = `${styles.pill} ${styles[`tone_${tone}`]} ${styles[`size_${size}`]}`;

  // Inside an overflow-clipping container the styled popover would be
  // cut off, so fall back to the OS-native tooltip (which escapes the
  // clip) when the caller opts in.
  if (nativeTooltip) {
    // The OS-native `title=` attribute only accepts a string; a
    // ReactNode body can't render in it, so drop it in that (rare) case.
    return (
      <span
        className={pillClass}
        title={typeof title === "string" ? title : undefined}
        style={style}
      >
        {children}
      </span>
    );
  }

  const pill = (
    <span className={pillClass} style={style}>
      {children}
    </span>
  );

  if (!title) return pill;

  // A string title is rendered with `\n` → `<br />` so multi-line bodies
  // keep their breaks inside the (white-space: normal) popover; the <br/>
  // are direct children of `.popover`, so the InfoTip `br + br
  // { display: none }` rule collapses `\n\n` pairs. A ReactNode title
  // (e.g. a shared `lib/tooltips` entry) is rendered as-is.
  const body =
    typeof title === "string" ? (
      title.split("\n").map((line, i, arr) => (
        <Fragment key={i}>
          {line}
          {i < arr.length - 1 ? <br /> : null}
        </Fragment>
      ))
    ) : (
      title
    );
  return (
    <span className={tip.wrap} data-infotip="">
      <span className={`${pillClass} ${styles.hasTooltip}`} style={style}>
        {children}
      </span>
      <span role="tooltip" className={tip.popover}>
        {body}
      </span>
    </span>
  );
}
