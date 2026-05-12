import type { CSSProperties, ReactNode } from "react";
import styles from "./StatusPill.module.css";

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
  title?: string;
  style?: CSSProperties;
}

/**
 * StatusPill — single editorial badge used for surface-status,
 * tier, direction, strength, triage, severity, etc. Tones map to
 * design-system color families; no inline hex codes.
 */
export function StatusPill({
  tone = "neutral",
  size = "md",
  children,
  title,
  style,
}: StatusPillProps) {
  return (
    <span
      className={`${styles.pill} ${styles[`tone_${tone}`]} ${styles[`size_${size}`]}`}
      title={title}
      style={style}
    >
      {children}
    </span>
  );
}
