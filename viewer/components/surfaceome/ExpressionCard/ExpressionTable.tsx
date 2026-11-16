"use client";

import type { ExpressionRow, TissueLevel } from "../../../lib/surfaceome-types";
import {
  expressionSourceRank,
  type ExpressionSource,
} from "../../../lib/expression";
import { prettyEnum } from "../../../lib/enums";
import { EvidenceChipList } from "../EvidenceChip/EvidenceChip";
import { StatusPill } from "../StatusPill/StatusPill";
import { SortableHeader } from "../_shared/SortableHeader";
import { SortResetButton } from "../_shared/SortResetButton";
import {
  levelRank,
  useTableSort,
  type SortValue,
} from "../_shared/useTableSort";
import styles from "./ExpressionCard.module.css";

function tissueLevelTone(v: TissueLevel) {
  if (v === "high") return "success" as const;
  if (v === "moderate") return "teal" as const;
  if (v === "low") return "amber" as const;
  if (v === "absent") return "neutral" as const;
  if (v === "mixed") return "lavender" as const;
  return "neutral" as const;
}

/** Tone for the Source column pill — surface is the strongest direct-
 *  surface signal (success/green); bulk reads as caveat (teal); other
 *  is informational (neutral). Lines up with the convention used by
 *  ``tissueLevelTone`` so the row's Level / Source pair is visually
 *  coherent. */
function expressionSourceTone(s: ExpressionSource) {
  if (s === "surface") return "success" as const;
  if (s === "bulk") return "teal" as const;
  return "neutral" as const;
}

type SortKey =
  | "tissue"
  | "cell_type"
  | "level"
  | "source"
  | "cell_states";

type ExpressionRowWithSource = ExpressionRow & { source: ExpressionSource };

interface Props {
  rows: readonly ExpressionRowWithSource[];
}

/**
 * Per-tissue × cell-type × disease expression table — clickable column
 * headers. Default order is the parent ExpressionCard's
 * ``DISEASE_CONTEXT_RANK`` sort (normal → tumor_adjacent → tumor → …);
 * clicking a header cycles none → asc → desc → none so the reader can
 * always restore the default with a third click.
 *
 * The Level column sorts by an explicit ``levelRank`` total order
 * (``high > moderate > low > absent > unknown``) rather than
 * lexicographically — descending sort puts the loudest tissues at the
 * top, which is the obvious "where is this protein expressed?" view.
 */
export function ExpressionTable({ rows }: Props) {
  const { sortKey, sortDir, onSort, reset, ariaSort, sortRows } = useTableSort<SortKey>();

  const comparators: Record<SortKey, (r: ExpressionRowWithSource) => SortValue> = {
    tissue: (r) => r.tissue ?? "",
    cell_type: (r) => r.cell_type ?? "",
    // Sort by explicit Level rank (high → moderate → low → absent →
    // unknown), NOT lexicographic. Documented in ``levelRank``.
    level: (r) => levelRank(r.present),
    // Source: surface > bulk > other so descending sort lands surface
    // rows at the top (the obvious "show me the direct-surface
    // evidence first" view).
    source: (r) => expressionSourceRank(r.source),
    cell_states: (r) => r.cell_states.join(", "),
  };
  const sorted = sortRows(rows, comparators);

  return (
    <div>
      <SortResetButton visible={sortKey !== null} onReset={reset} />
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col" aria-sort={ariaSort("tissue")}>
              <SortableHeader
                k="tissue"
                active={sortKey === "tissue"}
                direction={sortDir}
                onSort={onSort}
              >
                Tissue
              </SortableHeader>
            </th>
            <th scope="col" aria-sort={ariaSort("cell_type")}>
              <SortableHeader
                k="cell_type"
                active={sortKey === "cell_type"}
                direction={sortDir}
                onSort={onSort}
              >
                Cell type
              </SortableHeader>
            </th>
            {/* Disease context is NOT sortable: the table's default order is
                already the DISEASE_CONTEXT_RANK grouping (normal → tumor_adjacent
                → tumor → …) applied by the parent ExpressionCard, so a
                click-to-sort header here would only let the reader scramble that
                intentional grouping. Kept as a plain header like Cites. */}
            <th scope="col">Disease context</th>
            <th scope="col" aria-sort={ariaSort("level")}>
              <SortableHeader
                k="level"
                active={sortKey === "level"}
                direction={sortDir}
                onSort={onSort}
              >
                Level (protein)
              </SortableHeader>
            </th>
            <th scope="col" aria-sort={ariaSort("source")}>
              <SortableHeader
                k="source"
                active={sortKey === "source"}
                direction={sortDir}
                onSort={onSort}
              >
                Source
              </SortableHeader>
            </th>
            <th scope="col" aria-sort={ariaSort("cell_states")}>
              <SortableHeader
                k="cell_states"
                active={sortKey === "cell_states"}
                direction={sortDir}
                onSort={onSort}
              >
                Cell states
              </SortableHeader>
            </th>
            <th scope="col">Cites</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i}>
              <td>{row.tissue || "—"}</td>
              <td>{row.cell_type || "—"}</td>
              <td>
                <span className={styles.mono}>{prettyEnum(row.disease_context)}</span>
                {row.disease_label ? ` (${row.disease_label})` : ""}
              </td>
              <td>
                <StatusPill tone={tissueLevelTone(row.present)} size="sm">
                  {prettyEnum(row.present)}
                </StatusPill>
              </td>
              <td>
                <StatusPill tone={expressionSourceTone(row.source)} size="sm">
                  {row.source}
                </StatusPill>
              </td>
              <td>{row.cell_states.join(", ") || "—"}</td>
              <td>
                <EvidenceChipList ids={row.cited_evidence_ids} label="Cites" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
