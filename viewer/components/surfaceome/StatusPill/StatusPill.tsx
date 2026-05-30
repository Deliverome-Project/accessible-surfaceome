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
   *  fleeting native `title=` browser tooltip. `\n` line breaks in the
   *  string are preserved as `<br />`; a blank line (`\n\n`) collapses
   *  to a single break via the popover's `br + br` rule. */
  title?: string;
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
    return (
      <span className={pillClass} title={title} style={style}>
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

  // Render the title string with `\n` → `<br />` so multi-line tooltip
  // bodies keep their line breaks inside the (white-space: normal)
  // popover. The <br/> are direct children of `.popover`, so the
  // InfoTip `br + br { display: none }` rule collapses `\n\n` pairs.
  const lines = title.split("\n");
  return (
    <span className={tip.wrap} data-infotip="">
      <span className={`${pillClass} ${styles.hasTooltip}`} style={style}>
        {children}
      </span>
      <span role="tooltip" className={tip.popover}>
        {lines.map((line, i) => (
          <Fragment key={i}>
            {line}
            {i < lines.length - 1 ? <br /> : null}
          </Fragment>
        ))}
      </span>
    </span>
  );
}
