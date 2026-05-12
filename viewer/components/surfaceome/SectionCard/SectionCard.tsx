import type { ReactNode } from "react";
import { NumberedEyebrow } from "../../NumberedEyebrow/NumberedEyebrow";
import styles from "./SectionCard.module.css";

interface SectionCardProps {
  n: number;
  eyebrow: ReactNode;
  title?: ReactNode;
  meta?: ReactNode;
  lede?: ReactNode;
  children: ReactNode;
}

/**
 * SectionCard — editorial wrapper for a surfaceome record section.
 * Pairs a NumberedEyebrow with an optional .h-section title, a lede
 * line, and a content body. The rhythm comes from the section's
 * padding plus the eyebrow; no card chrome (borders / shadows /
 * fills) — the type system carries the structure.
 */
export function SectionCard({
  n,
  eyebrow,
  title,
  meta,
  lede,
  children,
}: SectionCardProps) {
  return (
    <section className={styles.section}>
      <header className={styles.head}>
        <NumberedEyebrow n={n}>{eyebrow}</NumberedEyebrow>
        {title ? <h2 className={`h-section ${styles.title}`}>{title}</h2> : null}
        {meta ? <p className={styles.meta}>{meta}</p> : null}
        {lede ? <p className={`lede ${styles.lede}`}>{lede}</p> : null}
      </header>
      <div className={styles.body}>{children}</div>
    </section>
  );
}
