import type { ReactNode } from "react";
import styles from "./SectionCard.module.css";

interface SectionCardProps {
  /** Section number + short category label. Retained in the props
   *  contract (every card still passes them) but NO LONGER RENDERED: the
   *  numbered "NN — Name" eyebrow line was removed per design feedback —
   *  the AnchorNav tab strip + the section title already identify each
   *  section, so the eyebrow only repeated that. Kept optional so callers
   *  don't all have to drop the props in the same change. */
  n?: number;
  eyebrow?: ReactNode;
  title?: ReactNode;
  meta?: ReactNode;
  lede?: ReactNode;
  children: ReactNode;
}

/**
 * SectionCard — editorial wrapper for a surfaceome record section.
 * Renders an optional .h-section title, a lede line, and a content body.
 * No card chrome (borders / shadows / fills) — the type system carries
 * the structure. (The numbered eyebrow was dropped; see props doc.)
 */
export function SectionCard({
  title,
  meta,
  lede,
  children,
}: SectionCardProps) {
  return (
    <section className={styles.section}>
      <header className={styles.head}>
        {title ? <h2 className={`h-section ${styles.title}`}>{title}</h2> : null}
        {meta ? <p className={styles.meta}>{meta}</p> : null}
        {lede ? <p className={`lede ${styles.lede}`}>{lede}</p> : null}
      </header>
      <div className={styles.body}>{children}</div>
    </section>
  );
}
