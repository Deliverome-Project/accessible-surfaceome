"use client";

import { useCallback, useMemo, useState } from "react";

/**
 * Generic sort state for a column-clickable table. Pattern mirrors
 * ``SurfaceBindTable`` (the canonical sortable-table implementation in
 * this app): columns are keyed by a string ``SortKey``; clicking a
 * column header cycles ``none → ascending → descending → none`` (so the
 * default agent-emitted order can always be restored with one more
 * click); ``aria-sort`` on the ``<th>`` reflects the current state for
 * screen readers.
 *
 * Returns:
 *   - ``sortKey`` / ``sortDir`` — current sort state (``sortKey === null``
 *     when no column has been clicked, so the default rendering order is
 *     preserved).
 *   - ``onSort(key)`` — click handler for the header button.
 *   - ``ariaSort(key)`` — value to pass into ``aria-sort=`` on a ``<th>``.
 *   - ``sortRows(rows, comparators)`` — apply the current sort to a
 *     ``readonly`` row array using the caller-supplied per-column
 *     comparators. Returns a NEW array (the original is left untouched
 *     — callers can rely on stable identity when ``sortKey === null``).
 *     Stable sort because ``Array.prototype.sort`` is stable in every JS
 *     runtime we target.
 */
export type SortDir = "asc" | "desc";

export interface UseTableSort<K extends string> {
  sortKey: K | null;
  sortDir: SortDir;
  onSort: (key: K) => void;
  /** Drop any active column sort and restore the default agent-emitted
   *  order. The third-click cycle on a header does the same thing, but
   *  that path requires the reader to remember which column they last
   *  clicked — this is the discoverable affordance, surfaced as a
   *  ``Reset sort`` chip above the table when ``sortKey !== null``. */
  reset: () => void;
  ariaSort: (key: K) => "ascending" | "descending" | "none";
  sortRows: <R>(
    rows: readonly R[],
    comparators: Record<K, (row: R) => SortValue>,
  ) => readonly R[];
}

/** Comparable value returned by a per-column comparator. Numbers compare
 *  numerically (use for explicit ranks — e.g. ``high > moderate > low``);
 *  strings compare with ``localeCompare`` (use for display strings —
 *  e.g. ``prettyEnum`` output, so the alphabetical order the user sees
 *  matches the order applied). */
export type SortValue = number | string;

export function useTableSort<K extends string>(): UseTableSort<K> {
  const [sortKey, setSortKey] = useState<K | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const onSort = useCallback(
    (key: K) => {
      if (sortKey !== key) {
        setSortKey(key);
        setSortDir("asc");
        return;
      }
      if (sortDir === "asc") {
        setSortDir("desc");
        return;
      }
      // Third click on the same column — clear the sort and restore the
      // default agent-emitted order. (Asc → desc → off → asc cycle.)
      setSortKey(null);
      setSortDir("asc");
    },
    [sortKey, sortDir],
  );

  const reset = useCallback(() => {
    setSortKey(null);
    setSortDir("asc");
  }, []);

  const ariaSort = useCallback(
    (key: K): "ascending" | "descending" | "none" => {
      if (sortKey !== key) return "none";
      return sortDir === "asc" ? "ascending" : "descending";
    },
    [sortKey, sortDir],
  );

  const sortRows = useCallback(
    <R,>(
      rows: readonly R[],
      comparators: Record<K, (row: R) => SortValue>,
    ): readonly R[] => {
      if (!sortKey) return rows;
      const cmp = comparators[sortKey];
      const dir = sortDir === "asc" ? 1 : -1;
      return [...rows].sort((a, b) => {
        const av = cmp(a);
        const bv = cmp(b);
        if (typeof av === "number" && typeof bv === "number") {
          return (av - bv) * dir;
        }
        return String(av).localeCompare(String(bv)) * dir;
      });
    },
    [sortKey, sortDir],
  );

  return useMemo<UseTableSort<K>>(
    () => ({ sortKey, sortDir, onSort, reset, ariaSort, sortRows }),
    [sortKey, sortDir, onSort, reset, ariaSort, sortRows],
  );
}

/** Rank for ``TissueLevel`` / ``Severity`` columns. Higher score = more
 *  "interesting" (high > moderate > low > absent > unknown), so a
 *  descending sort puts the high-intensity rows at the top — usually
 *  what a reader scanning for "where is this protein loud?" wants. */
export function levelRank(v: string | null | undefined): number {
  const map: Record<string, number> = {
    high: 4,
    moderate: 3,
    low: 2,
    mixed: 2,
    absent: 1,
    none: 1,
    unknown: 0,
    unclear: 0,
  };
  return v ? (map[v] ?? -1) : -1;
}

/** Rank for ``ModulationDirection`` — a deliberate total order so the
 *  "Change" column can be sorted: ``increases`` (most actionable —
 *  oncogenic upregulation, immune activation) first, then ``decreases``,
 *  then ``bidirectional`` / ``no_change``, then ``unclear`` /
 *  undefined. Ascending puts ``increases`` at the top. */
export function directionRank(v: string | null | undefined): number {
  const map: Record<string, number> = {
    increases: 0,
    decreases: 1,
    bidirectional: 2,
    no_change: 3,
    unclear: 4,
  };
  return v ? (map[v] ?? 5) : 5;
}
