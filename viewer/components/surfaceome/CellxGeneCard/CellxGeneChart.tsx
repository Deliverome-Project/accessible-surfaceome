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
  /** All rows for this gene — the chart will split into common + rare
   *  internally based on each row's `is_rare` flag. */
  rows: CellTypeRow[];
}

type YMetric = "mean" | "pct";
type SortMode = "value" | "type" | "category";

const COMMON_MAX_ROWS = 20;
const RARE_MAX_ROWS = 10;

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

function decorate(rows: CellTypeRow[]): Decorated[] {
  return rows.map((r) => ({ ...r, category: categorize(r.cell_type) }));
}

function sortRows(
  rows: Decorated[],
  sortMode: SortMode,
  yMetric: YMetric,
): Decorated[] {
  const arr = [...rows];
  const metric = (r: Decorated): number =>
    yMetric === "mean" ? r.mean_log1p_cp10k ?? 0 : r.pct_expressing ?? 0;
  if (sortMode === "value") {
    arr.sort((a, b) => metric(b) - metric(a));
  } else if (sortMode === "type") {
    arr.sort((a, b) => a.cell_type.localeCompare(b.cell_type));
  } else {
    const order = new Map(CATEGORIES.map((c, i) => [c, i]));
    arr.sort((a, b) => {
      const oa = order.get(a.category) ?? 99;
      const ob = order.get(b.category) ?? 99;
      if (oa !== ob) return oa - ob;
      return metric(b) - metric(a);
    });
  }
  return arr;
}

/**
 * One CellxGene chart — toolbar + bar list + legend. Renders the rows
 * the caller passed in (common or rare), unaware of which bucket it
 * is. The outer `CellxGeneChart` component splits the buckets and
 * renders two of these side by side (or stacked on mobile).
 */
function BarChart({
  title,
  subtitle,
  rows,
  maxRows,
  yMetric,
  sortMode,
  scaleMax,
}: {
  title: string;
  subtitle: string;
  rows: Decorated[];
  maxRows: number;
  yMetric: YMetric;
  sortMode: SortMode;
  scaleMax: number;
}) {
  const sorted = useMemo(
    () => sortRows(rows, sortMode, yMetric).slice(0, maxRows),
    [rows, sortMode, yMetric, maxRows],
  );

  if (sorted.length === 0) {
    return (
      <section className={styles.chartBlock}>
        <h3 className={styles.subhead}>
          {title}
          <span className={styles.subheadMeta}>{subtitle}</span>
        </h3>
        <p className={styles.empty}>No qualifying cell types in this bucket.</p>
      </section>
    );
  }

  return (
    <section className={styles.chartBlock}>
      <h3 className={styles.subhead}>
        {title}
        <span className={styles.subheadMeta}>{subtitle}</span>
      </h3>
      <ul className={styles.barList}>
        {sorted.map((r) => {
          const meanVal = r.mean_log1p_cp10k ?? 0;
          const pctVal = r.pct_expressing ?? 0;
          const nExpressing = r.n_expressing ?? 0;
          const nTotal = r.n_total ?? nExpressing;
          const tissueList = r.tissues ?? [];
          const value = yMetric === "mean" ? meanVal : pctVal;
          const pct = Math.max(0, Math.min(100, (value / scaleMax) * 100));
          const color = CATEGORY_COLORS[r.category];
          const topTissues = tissueList.slice(0, 3);
          const tissuesInline = topTissues.map((t) => t.tissue).join(" · ");
          return (
            <li key={r.cl_id} className={styles.barRow} tabIndex={0}>
              <div className={styles.barLabel}>
                <span
                  className={styles.swatch}
                  style={{ background: color }}
                  aria-hidden
                />
                <span className={styles.barName}>{r.cell_type}</span>
                {tissuesInline && (
                  <span className={styles.tissues}>{tissuesInline}</span>
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
              {/* CSS-only hover/focus popover. Sits above its row at the
                  same horizontal position. No JS state so it survives
                  re-sorts without re-mounting. */}
              <div className={styles.popover} role="tooltip">
                <div className={styles.popHeader}>
                  <span
                    className={styles.swatch}
                    style={{ background: color }}
                    aria-hidden
                  />
                  <strong>{r.cell_type}</strong>
                  <span className={styles.popMeta}>{r.cl_id}</span>
                  <span className={styles.popCategory}>{r.category}</span>
                </div>
                <dl className={styles.popStats}>
                  <div>
                    <dt>Mean log1p(CP10K)</dt>
                    <dd>{fmtMean(meanVal)}</dd>
                  </div>
                  <div>
                    <dt>% expressing</dt>
                    <dd>
                      {fmtPct(pctVal)}
                      <span className={styles.popHint}>
                        {" "}
                        ({fmtN(nExpressing)} / {fmtN(nTotal)} cells)
                      </span>
                    </dd>
                  </div>
                </dl>
                {topTissues.length > 0 && (
                  <div className={styles.popTissues}>
                    <span className={styles.popTissuesLabel}>Tissues</span>
                    <ul>
                      {topTissues.map((t) => (
                        <li key={t.uberon_id}>
                          {t.tissue}
                          <span className={styles.popHint}>
                            {" "}
                            {t.pct_expressing != null
                              ? fmtPct(t.pct_expressing)
                              : ""}{" "}
                            {fmtMean(t.mean_log1p_cp10k)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function CellxGeneChart({ rows }: Props) {
  const [yMetric, setYMetric] = useState<YMetric>("mean");
  const [sortMode, setSortMode] = useState<SortMode>("value");

  const decorated = useMemo(() => decorate(rows), [rows]);
  const common = useMemo(() => decorated.filter((r) => !r.is_rare), [decorated]);
  const rare = useMemo(() => decorated.filter((r) => r.is_rare), [decorated]);

  const scaleMax = yMetric === "mean" ? 7 : 1;

  // Build the legend from EVERY decorated row (both buckets) so it's
  // consistent regardless of which bucket the reader is looking at.
  const presentCategories = useMemo(() => {
    const seen = new Set<CellCategory>();
    for (const r of decorated) seen.add(r.category);
    return CATEGORIES.filter((c) => seen.has(c));
  }, [decorated]);

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

      <BarChart
        title="Common cell types"
        subtitle="≥ 1,000 cells sampled per cell type — high-confidence rankings"
        rows={common}
        maxRows={COMMON_MAX_ROWS}
        yMetric={yMetric}
        sortMode={sortMode}
        scaleMax={scaleMax}
      />

      {rare.length > 0 && (
        <BarChart
          title="Rare high-expressors"
          subtitle="< 1,000 cells sampled, mean ≥ 2 — comparison only; small-n caveat"
          rows={rare}
          maxRows={RARE_MAX_ROWS}
          yMetric={yMetric}
          sortMode={sortMode}
          scaleMax={scaleMax}
        />
      )}

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
