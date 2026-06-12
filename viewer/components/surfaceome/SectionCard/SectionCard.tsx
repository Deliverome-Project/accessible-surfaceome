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
  /** Extra className appended to the lede paragraph. Used by sections
   *  whose lede needs to break out of the global 75 ch reading-width
   *  cap (e.g. CellxGeneCard — dense intro with InfoTip + the chart
   *  toolbars below). Leave undefined to keep the default cap. */
  ledeClassName?: string;
  /** Extra className appended to the .head element. Needed when
   *  ledeClassName widens the lede — the parent .head also has a
   *  64 ch max-width that caps every child regardless of their own
   *  rules. */
  headClassName?: string;
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
  ledeClassName,
  headClassName,
  children,
}: SectionCardProps) {
  const ledeClasses = ["lede", styles.lede, ledeClassName]
    .filter(Boolean)
    .join(" ");
  const headClasses = [styles.head, headClassName].filter(Boolean).join(" ");
  return (
    <section className={styles.section}>
      <header className={headClasses}>
        {title ? <h2 className={`h-section ${styles.title}`}>{title}</h2> : null}
        {meta ? <p className={styles.meta}>{meta}</p> : null}
        {lede ? <p className={ledeClasses}>{lede}</p> : null}
      </header>
      <div className={styles.body}>{children}</div>
    </section>
  );
}
