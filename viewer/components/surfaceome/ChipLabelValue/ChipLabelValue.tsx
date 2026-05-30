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
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <>
      <span className={styles.label}>{label}</span>
      <span className={styles.sep} aria-hidden="true">
        {" · "}
      </span>
      <span className={styles.value}>{value}</span>
    </>
  );
}
