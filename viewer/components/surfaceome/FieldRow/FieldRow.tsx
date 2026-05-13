import type { ReactNode } from "react";
import { CiteCount } from "../CiteCount/CiteCount";
import styles from "./FieldRow.module.css";

interface FieldRowProps {
  /**
   * Label for the left column. Accepts a ReactNode so callers can
   * inject decorations (`<>UniProt <span className="tag">canonical</span></>`).
   * Pass a plain string when possible — `CiteCount` uses it for the
   * citation `aria-label`.
   */
  k: ReactNode;
  ariaLabel?: string;
  ids?: string[];
  children: ReactNode;
}

export function FieldRow({ k, ariaLabel, ids, children }: FieldRowProps) {
  const citeLabel = typeof k === "string" ? k : ariaLabel;
  return (
    <div className={styles.row}>
      <div className={styles.k}>{k}</div>
      <div className={styles.v}>
        <div className={styles.body}>{children}</div>
        {ids && ids.length > 0 ? <CiteCount ids={ids} label={citeLabel} /> : null}
      </div>
    </div>
  );
}
