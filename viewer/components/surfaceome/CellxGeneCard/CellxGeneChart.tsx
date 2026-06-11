"use client";

import { useMemo, useState } from "react";
import type { CellTypeRow } from "../../../lib/cellxgene-enrichment";
import {
  CATEGORIES,
  CATEGORY_COLORS,
  categorize,
  type CellCategory,
} from "../../../lib/cellxgene-categories";
import styles from "./CellxGeneCard.module.css";

interface Props {
  rows: CellTypeRow[];
}

type YMetric = "mean" | "pct";
type SortMode = "value" | "type" | "category";

const MAX_ROWS = 25;

function fmtN(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${n}`;
}

function fmtPct(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

function fmtMean(v: number): string {
  return v.toFixed(2);
}

interface Decorated extends CellTypeRow {
  category: CellCategory;
}

export function CellxGeneChart({ rows }: Props) {
  const [yMetric, setYMetric] = useState<YMetric>("mean");
  const [sortMode, setSortMode] = useState<SortMode>("value");

  // Decorate each row with its category once (the rule scan is O(rules)
  // per row, so memo prevents redoing it on every sort/metric flip).
  const decorated = useMemo<Decorated[]>(
    () => rows.map((r) => ({ ...r, category: categorize(r.cell_type) })),
    [rows],
  );

  const sorted = useMemo(() => {
    const arr = [...decorated];
    // Pull the active metric defensively — v1 rows lack pct_expressing,
    // so a missing field reads as 0 rather than NaN-breaking the sort.
    const metric = (r: Decorated): number =>
      yMetric === "mean" ? r.mean_log1p_cp10k ?? 0 : r.pct_expressing ?? 0;
    if (sortMode === "value") {
      arr.sort((a, b) => metric(b) - metric(a));
    } else if (sortMode === "type") {
      arr.sort((a, b) => a.cell_type.localeCompare(b.cell_type));
    } else {
      // category: cluster by category in the canonical CATEGORIES order,
      // then by descending value-on-the-current-metric within each group
      // (so the visual story per category reads top-down by magnitude).
      const order = new Map(CATEGORIES.map((c, i) => [c, i]));
      arr.sort((a, b) => {
        const oa = order.get(a.category) ?? 99;
        const ob = order.get(b.category) ?? 99;
        if (oa !== ob) return oa - ob;
        return metric(b) - metric(a);
      });
    }
    return arr.slice(0, MAX_ROWS);
  }, [decorated, sortMode, yMetric]);

  // Fixed scale per metric so values stay comparable across genes:
  //   * mean log1p(CP10K) tops out around 7 in the CZI data; cap at 7.
  //   * pct_expressing is naturally [0, 1].
  const scaleMax = yMetric === "mean" ? 7 : 1;

  // Which categories actually appear in this gene's rows? Drives the
  // legend so we don't show grey "Other" when there is no Other.
  const presentCategories = useMemo(() => {
    const seen = new Set<CellCategory>();
    for (const r of sorted) seen.add(r.category);
    return CATEGORIES.filter((c) => seen.has(c));
  }, [sorted]);

  return (
    <div className={styles.chart}>
      <div className={styles.controls} role="toolbar" aria-label="Chart controls">
        <div className={styles.controlGroup}>
          <span className={styles.controlLabel}>Y-axis</span>
          <div className={styles.toggle} role="radiogroup" aria-label="Y-axis metric">
            <button
              type="button"
              role="radio"
              aria-checked={yMetric === "mean"}
              data-active={yMetric === "mean"}
              onClick={() => setYMetric("mean")}
            >
              Mean expression
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={yMetric === "pct"}
              data-active={yMetric === "pct"}
              onClick={() => setYMetric("pct")}
            >
              % expressing
            </button>
          </div>
        </div>
        <div className={styles.controlGroup}>
          <span className={styles.controlLabel}>Sort</span>
          <div className={styles.toggle} role="radiogroup" aria-label="Sort order">
            <button
              type="button"
              role="radio"
              aria-checked={sortMode === "value"}
              data-active={sortMode === "value"}
              onClick={() => setSortMode("value")}
            >
              By value
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={sortMode === "category"}
              data-active={sortMode === "category"}
              onClick={() => setSortMode("category")}
            >
              By category
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={sortMode === "type"}
              data-active={sortMode === "type"}
              onClick={() => setSortMode("type")}
            >
              A → Z
            </button>
          </div>
        </div>
      </div>

      <ul className={styles.barList}>
        {sorted.map((r) => {
          // Defensive: while D1 still serves the v1 (schema 1.0) rows,
          // tissues/n_total/pct_expressing are missing. The page must
          // still render — fall back to per-row neutral values until
          // the v2 re-sync completes.
          const meanVal = r.mean_log1p_cp10k ?? 0;
          const pctVal = r.pct_expressing ?? 0;
          const nExpressing = r.n_expressing ?? 0;
          const nTotal = r.n_total ?? nExpressing;
          const tissueList = r.tissues ?? [];
          const value = yMetric === "mean" ? meanVal : pctVal;
          const pct = Math.max(0, Math.min(100, (value / scaleMax) * 100));
          const color = CATEGORY_COLORS[r.category];
          const tissues = tissueList
            .slice(0, 3)
            .map((t) => t.tissue)
            .join(" · ");
          const title =
            `${r.cell_type} (${r.cl_id})\n` +
            `Mean log1p(CP10K) = ${fmtMean(meanVal)}\n` +
            `% expressing = ${fmtPct(pctVal)}` +
            ` (${fmtN(nExpressing)} of ${fmtN(nTotal)} cells)\n` +
            (tissues ? `Tissues: ${tissues}` : "");
          return (
            <li key={r.cl_id} className={styles.barRow} title={title}>
              <div className={styles.barLabel}>
                <span
                  className={styles.swatch}
                  style={{ background: color }}
                  aria-hidden
                />
                <span className={styles.barName}>{r.cell_type}</span>
                {tissues && (
                  <span className={styles.tissues}>{tissues}</span>
                )}
              </div>
              <div className={styles.barTrack}>
                <div
                  className={styles.barFill}
                  style={{ width: `${pct}%`, background: color }}
                  aria-hidden
                />
                <span className={styles.barValue}>
                  {yMetric === "mean" ? fmtMean(value) : fmtPct(value)}
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      {presentCategories.length > 0 && (
        <ul className={styles.legend} aria-label="Category legend">
          {presentCategories.map((c) => (
            <li key={c} className={styles.legendItem}>
              <span
                className={styles.swatch}
                style={{ background: CATEGORY_COLORS[c] }}
                aria-hidden
              />
              <span>{c}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
