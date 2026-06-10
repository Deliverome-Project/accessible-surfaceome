"use client";

import styles from "./SortResetButton.module.css";

/**
 * "Reset sort" affordance for sortable tables — rendered above a table
 * when ``useTableSort`` has a non-null ``sortKey``. The third-click cycle
 * on a column header already restores the default order, but that path
 * isn't discoverable: once the reader has poked two or three columns,
 * the "which one was active?" question is real. This button is the
 * out-of-band escape hatch.
 *
 * Sized as a chip-style text button (not a primary action) so it doesn't
 * compete with the table itself. Hidden via ``display:none`` when no
 * sort is active rather than unmounted so the table header doesn't shift
 * vertically as the user cycles between sorted and unsorted states.
 */
interface SortResetButtonProps {
  visible: boolean;
  onReset: () => void;
}

export function SortResetButton({ visible, onReset }: SortResetButtonProps) {
  return (
    <div className={styles.row} data-visible={visible ? "true" : "false"}>
      <button type="button" className={styles.btn} onClick={onReset}>
        <span aria-hidden="true" className={styles.glyph}>
          ↺
        </span>
        Reset sort
      </button>
    </div>
  );
}
