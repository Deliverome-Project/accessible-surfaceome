"use client";

import type {
  AccessibilityImplication,
  AnatomicalAccessibilityObservation,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { EvidenceChipList, linkifyEvidenceRefs } from "../EvidenceChip/EvidenceChip";
import { StatusPill } from "../StatusPill/StatusPill";
import { SortableHeader } from "../_shared/SortableHeader";
import { useTableSort, type SortValue } from "../_shared/useTableSort";
import styles from "./BiologicalContextCard.module.css";

function implicationTone(v: AccessibilityImplication) {
  if (v === "favorable") return "success" as const;
  if (v === "restricted") return "danger" as const;
  if (v === "context_dependent") return "amber" as const;
  return "neutral" as const;
}

type SortKey = "context" | "orientation" | "implication" | "rationale";

interface Props {
  rows: readonly AnatomicalAccessibilityObservation[];
}

/**
 * Per-row anatomical accessibility table — clickable column headers.
 * Default order is the agent-emitted ordering; clicking a header cycles
 * none → asc → desc → none so the reader can always restore the default
 * with a third click. Mirrors ``SurfaceBindTable`` (the canonical
 * sortable-table impl) for consistency. Enum columns sort by their
 * ``prettyEnum`` output so alphabetical order matches the displayed
 * text.
 */
export function AnatomicalAccessibilityTable({ rows }: Props) {
  const { sortKey, sortDir, onSort, ariaSort, sortRows } = useTableSort<SortKey>();

  const comparators: Record<SortKey, (r: AnatomicalAccessibilityObservation) => SortValue> = {
    context: (r) => r.context ?? "",
    orientation: (r) => prettyEnum(r.orientation),
    implication: (r) => prettyEnum(r.accessibility_implication),
    rationale: (r) => r.rationale ?? "",
  };
  const sorted = sortRows(rows, comparators);

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col" aria-sort={ariaSort("context")}>
            <SortableHeader
              k="context"
              active={sortKey === "context"}
              direction={sortDir}
              onSort={onSort}
            >
              Context
            </SortableHeader>
          </th>
          <th scope="col" aria-sort={ariaSort("orientation")}>
            <SortableHeader
              k="orientation"
              active={sortKey === "orientation"}
              direction={sortDir}
              onSort={onSort}
            >
              Orientation
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
          <th scope="col" aria-sort={ariaSort("rationale")}>
            <SortableHeader
              k="rationale"
              active={sortKey === "rationale"}
              direction={sortDir}
              onSort={onSort}
            >
              Rationale
            </SortableHeader>
          </th>
          <th scope="col">References</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((a, i) => (
          <tr key={i}>
            <td>{a.context}</td>
            <td>{prettyEnum(a.orientation)}</td>
            <td>
              <StatusPill
                tone={implicationTone(a.accessibility_implication)}
                size="sm"
              >
                {prettyEnum(a.accessibility_implication)}
              </StatusPill>
            </td>
            <td>{linkifyEvidenceRefs(a.rationale)}</td>
            <td>
              <EvidenceChipList ids={a.cited_evidence_ids} label="References" />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
