"use client";

import type { ReactNode } from "react";
import styles from "./SortableHeader.module.css";

/**
 * Sortable column header button — used by every column-clickable table
 * in the gene-page (SurfaceBindTable's inline equivalent, the biology /
 * expression tables). The button stays a real ``<button>`` so the column
 * is keyboard-reachable; the indicator (``↕`` inactive, ``▲`` / ``▼``
 * active) lives in a hidden-from-AT span — the parent ``<th
 * aria-sort=>`` is the actual announcement.
 *
 * Visual treatment matches the SurfaceBindTable per-column button:
 * inherits the ``<th>`` font / letter-spacing / color so the unsorted
 * state looks identical to a plain ``<th>`` (no "this is clickable" cue
 * past the cursor — we don't want every header screaming for
 * attention).
 */
interface SortableHeaderProps<K extends string> {
  k: K;
  active: boolean;
  direction: "asc" | "desc";
  onSort: (key: K) => void;
  children: ReactNode;
}

export function SortableHeader<K extends string>({
  k,
  active,
  direction,
  onSort,
  children,
}: SortableHeaderProps<K>) {
  return (
    <button
      type="button"
      className={styles.sortBtn}
      onClick={() => onSort(k)}
      data-active={active ? "true" : "false"}
    >
      {children}
      <span
        aria-hidden="true"
        className={`${styles.sortArrow} ${active ? styles.sortArrowActive : ""}`}
      >
        {active ? (direction === "asc" ? "▲" : "▼") : "↕"}
      </span>
    </button>
  );
}
