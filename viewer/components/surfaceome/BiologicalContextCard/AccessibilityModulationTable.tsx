"use client";

import type {
  AccessibilityModulationObservation,
  ModulationDirection,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/enums";
import { EvidenceChipList } from "../EvidenceChip/EvidenceChip";
import { StatusPill } from "../StatusPill/StatusPill";
import { SortableHeader } from "../_shared/SortableHeader";
import { SortResetButton } from "../_shared/SortResetButton";
import {
  directionRank,
  useTableSort,
  type SortValue,
} from "../_shared/useTableSort";
import styles from "./BiologicalContextCard.module.css";

/** Small directional glyph for a modulation row's `direction` enum. See
 *  the parent ``BiologicalContextCard`` for the original prose docstring
 *  — duplicated here verbatim so this table can stand alone as a client
 *  component. */
function directionCell(
  direction: ModulationDirection | undefined,
): React.ReactNode {
  const map: Record<
    string,
    { glyph: string; text: string; color: string; title: string }
  > = {
    increases: {
      glyph: "↑",
      text: "Increase",
      color: "var(--success, #1b5e3f)",
      title: "Increases surface-accessible pool",
    },
    decreases: {
      glyph: "↓",
      text: "Decrease",
      color: "var(--maroon-dark, #922038)",
      title: "Decreases surface-accessible pool",
    },
    bidirectional: {
      glyph: "↕",
      text: "Bidirectional",
      color: "var(--amber-dark, #8a5a16)",
      title: "Both directions documented",
    },
    no_change: {
      glyph: "=",
      text: "Equal",
      color: "var(--ink-faint, #999)",
      title: "No net change in surface accessibility",
    },
  };
  const d = direction ? map[direction] : undefined;
  if (!d) {
    return (
      <span
        title="Direction of change not determined"
        style={{ color: "var(--ink-faint, #999)" }}
      >
        ?
      </span>
    );
  }
  return (
    <span
      aria-label={d.title}
      title={d.title}
      style={{ color: d.color, fontWeight: 600, whiteSpace: "nowrap" }}
    >
      {d.glyph} {d.text}
    </span>
  );
}

type SortKey =
  | "category"
  | "direction"
  | "baseline"
  | "modulating"
  | "implication";

interface Props {
  rows: readonly AccessibilityModulationObservation[];
}

/**
 * Per-row accessibility-modulation table — clickable column headers.
 * Default order is the agent-emitted ordering; clicking a header cycles
 * none → asc → desc → none. Enum columns (Context, Implication) sort by
 * ``prettyEnum`` output so the alphabetical order matches displayed
 * text; the Change column sorts by an explicit ``directionRank`` total
 * order (``increases`` is the most actionable signal, so ascending
 * lands it at the top).
 */
export function AccessibilityModulationTable({ rows }: Props) {
  const { sortKey, sortDir, onSort, reset, ariaSort, sortRows } = useTableSort<SortKey>();

  const comparators: Record<SortKey, (r: AccessibilityModulationObservation) => SortValue> = {
    category: (r) => prettyEnum(r.category),
    // Sort the Change column by structured direction rank (NOT by the
    // displayed glyph) — ``increases`` first, ``decreases`` next, then
    // bidirectional / no_change / unclear. Ranks documented in
    // ``directionRank``.
    direction: (r) => directionRank(r.direction),
    baseline: (r) => r.baseline_context ?? "",
    modulating: (r) => r.modulating_state ?? "",
    implication: (r) => r.accessibility_implication ?? "",
  };
  const sorted = sortRows(rows, comparators);

  return (
    <div>
      <SortResetButton visible={sortKey !== null} onReset={reset} />
      <table className={`${styles.table} ${styles.modTable}`}>
        <thead>
          <tr>
            <th scope="col" aria-sort={ariaSort("category")}>
              <SortableHeader
                k="category"
                active={sortKey === "category"}
                direction={sortDir}
                onSort={onSort}
              >
                Context
              </SortableHeader>
            </th>
            <th scope="col" aria-sort={ariaSort("direction")}>
              <SortableHeader
                k="direction"
                active={sortKey === "direction"}
                direction={sortDir}
                onSort={onSort}
              >
                Change
              </SortableHeader>
            </th>
            <th scope="col" aria-sort={ariaSort("baseline")}>
              <SortableHeader
                k="baseline"
                active={sortKey === "baseline"}
                direction={sortDir}
                onSort={onSort}
              >
                Reference
              </SortableHeader>
            </th>
            <th scope="col" aria-sort={ariaSort("modulating")}>
              <SortableHeader
                k="modulating"
                active={sortKey === "modulating"}
                direction={sortDir}
                onSort={onSort}
              >
                Modulating state
              </SortableHeader>
            </th>
            <th scope="col" aria-sort={ariaSort("implication")}>
              <SortableHeader
                k="implication"
                active={sortKey === "implication"}
                direction={sortDir}
                onSort={onSort}
              >
                Implication
              </SortableHeader>
            </th>
            <th scope="col">References</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((m, i) => (
            <tr key={i}>
              <td>
                <StatusPill tone="lavender" size="sm">
                  {prettyEnum(m.category)}
                </StatusPill>
              </td>
              {/* Structured direction of the surface pool under the
                  modulating state — its own column, "?" when unclear. */}
              <td>{directionCell(m.direction)}</td>
              <td>{m.baseline_context}</td>
              <td>{m.modulating_state}</td>
              <td>{m.accessibility_implication}</td>
              <td>
                {/* The change/effect narrative (the "evidence string")
                 *  lives in the Cites column with its citations rather
                 *  than widening the Shift column. */}
                {m.change ? (
                  <p className={styles.modChangeCite}>{m.change}</p>
                ) : null}
                <EvidenceChipList ids={m.cited_evidence_ids} label="References" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
