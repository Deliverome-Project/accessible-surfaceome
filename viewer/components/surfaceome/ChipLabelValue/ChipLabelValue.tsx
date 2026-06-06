import type { ReactNode } from "react";
import styles from "./ChipLabelValue.module.css";

/**
 * Shared "label · VALUE" body for StatusPill chips.
 *
 * The label is a dim, normal-weight description ("what is this?"); the
 * value is the bold, UPPERCASE answer at the SAME font size, so the eye
 * lands on the verdict without a size jump. One component so every
 * attribute·value chip across the feature / biology / risk cards renders
 * identically — no per-chip inline styles to drift.
 *
 * Casing is applied via CSS `text-transform`, so pass the value in its
 * normal form (e.g. `prettyEnum(...)`); it still reads correctly to
 * screen readers and copies out un-shouted.
 */
export function ChipLabelValue({
  label,
  value,
  muted = false,
}: {
  label: string;
  value: ReactNode;
  /** Render the value in the same dim / non-bold / non-uppercase style as
   *  the label, instead of the bold UPPERCASE verdict style. Use for
   *  "no data" values (e.g. validation · none) so the chip doesn't read
   *  as a confident verdict when there's nothing to assert. */
  muted?: boolean;
}) {
  // One wrapper span (not a fragment) so the parent StatusPill's flex
  // `gap` doesn't inject extra space between label / separator / value —
  // the gap is meant for icon↔text on other chips, not for the three
  // pieces of a single label·value. Spacing here is controlled locally by
  // the separator's own margins, kept tight on purpose.
  return (
    <span className={styles.wrap}>
      <span className={styles.label}>{label}</span>
      <span className={styles.sep} aria-hidden="true">
        ·
      </span>
      <span className={muted ? styles.valueMuted : styles.value}>{value}</span>
    </span>
  );
}
