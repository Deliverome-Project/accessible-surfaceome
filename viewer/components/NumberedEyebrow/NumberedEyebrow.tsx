import type { ReactNode } from "react";
import styles from "./NumberedEyebrow.module.css";

interface NumberedEyebrowProps {
  /** Section number (1-based) — displayed zero-padded ("01 — Mission"). */
  n: number;
  children: ReactNode;
  className?: string;
}

/**
 * NumberedEyebrow — editorial section marker. Reuses the
 * `.label-mono` type primitive from globals.css and a small
 * teal-accented number; no receptor icons (those are a
 * deliverome-org-specific affordance that doesn't belong on a
 * separate sub-product).
 */
export function NumberedEyebrow({
  n,
  children,
  className = "",
}: NumberedEyebrowProps) {
  const num = String(n).padStart(2, "0");
  return (
    <p className={`label-mono ${styles.eyebrow} ${className}`.trim()}>
      <span className={styles.num}>{num}</span>
      <span className={styles.dash} aria-hidden="true">
        —
      </span>
      <span>{children}</span>
    </p>
  );
}
