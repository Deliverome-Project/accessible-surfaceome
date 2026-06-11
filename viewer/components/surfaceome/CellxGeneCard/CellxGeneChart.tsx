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
  /** All rows for this gene — split into common + rare internally on
   *  each row's `is_rare` flag. */
  rows: CellTypeRow[];
}

type YMetric = "mean" | "pct";
type SortMode = "value" | "type" | "category";

const COMMON_MAX = 25;
const RARE_MAX = 10;
const LABEL_TRUNCATE_AT = 24;

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

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
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
 * One column chart — vertical bars, cell types along the X-axis.
 * Each bar's height encodes the selected metric (mean log1p(CP10K) or
 * % expressing) on a fixed 0..scaleMax axis. Bar fills are colored by
 * the cell type's category (Epithelial / Immune / Neural / …).
 *
 * Why column instead of horizontal row-list: the row-list layout used
 * one line per cell type (~22 px), so ~10 cell types fit in a typical
 * gene-page viewport. The column layout puts each cell type in a
 * ~28 px-wide bar, so ~25 fit in the same horizontal space, with the
 * y-axis grid carrying scale. Reader trades labels-always-visible for
 * more cell types at a glance — every label is still recoverable via
 * the hover popover.
 */
function ColumnChart({
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

  // Y-axis ticks at 25% intervals against the fixed scaleMax. Drawn
  // as background grid lines via the .yGrid pseudo-element rules in
  // CSS — here we emit the labels.
  const tickValues =
    yMetric === "mean"
      ? [0, 1.75, 3.5, 5.25, 7]
      : [0, 0.25, 0.5, 0.75, 1.0];

  return (
    <section className={styles.chartBlock}>
      <h3 className={styles.subhead}>
        {title}
        <span className={styles.subheadMeta}>{subtitle}</span>
      </h3>
      <div className={styles.colChart}>
        <div className={styles.yAxis} aria-hidden>
          {[...tickValues].reverse().map((v) => (
            <span key={v} className={styles.yTick}>
              {yMetric === "mean" ? v.toFixed(1) : fmtPct(v)}
            </span>
          ))}
        </div>
        <ul className={styles.colCanvas}>
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
            return (
              <li key={r.cl_id} className={styles.colBar} tabIndex={0}>
                <div className={styles.colTrack}>
                  <div
                    className={styles.colFill}
                    style={{ height: `${pct}%`, background: color }}
                    aria-hidden
                  />
                </div>
                <span
                  className={styles.colLabel}
                  title={r.cell_type}
                  aria-label={r.cell_type}
                >
                  {truncate(r.cell_type, LABEL_TRUNCATE_AT)}
                </span>
                {/* Hover/focus popover — same content as the previous
                    horizontal layout. Z-indexed above bars; positioned
                    at bar top so it doesn't get cut off when the bar is
                    short. */}
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
      </div>
    </section>
  );
}

/**
 * Per-category summary: one horizontal bar per category that appears
 * in the gene's top_cell_types, showing the average of the active
 * metric across the cell types in that category. Sits ABOVE the
 * detail charts as the "first read" — answers "which broad cell
 * class is this gene strongest in?" before the reader scans 30 bars.
 */
function CategoryAverages({
  rows,
  yMetric,
  scaleMax,
}: {
  rows: Decorated[];
  yMetric: YMetric;
  scaleMax: number;
}) {
  const summary = useMemo(() => {
    const groups = new Map<CellCategory, Decorated[]>();
    for (const r of rows) {
      const arr = groups.get(r.category) ?? [];
      arr.push(r);
      groups.set(r.category, arr);
    }
    const metric = (r: Decorated): number =>
      yMetric === "mean" ? r.mean_log1p_cp10k ?? 0 : r.pct_expressing ?? 0;
    return CATEGORIES.map((c) => {
      const arr = groups.get(c) ?? [];
      if (arr.length === 0) return null;
      const avg =
        arr.reduce((s, r) => s + metric(r), 0) / arr.length;
      return { category: c, n: arr.length, avg };
    })
      .filter((d): d is { category: CellCategory; n: number; avg: number } => !!d)
      .sort((a, b) => b.avg - a.avg);
  }, [rows, yMetric]);

  if (summary.length === 0) return null;

  return (
    <section className={styles.chartBlock}>
      <h3 className={styles.subhead}>
        Per-category average
        <span className={styles.subheadMeta}>
          mean of the active metric across cell types in each category
        </span>
      </h3>
      <ul className={styles.catList}>
        {summary.map((row) => {
          const pct = Math.max(0, Math.min(100, (row.avg / scaleMax) * 100));
          const color = CATEGORY_COLORS[row.category];
          return (
            <li key={row.category} className={styles.catRow}>
              <div className={styles.catLabel}>
                <span
                  className={styles.swatch}
                  style={{ background: color }}
                  aria-hidden
                />
                <span className={styles.catName}>{row.category}</span>
                <span className={styles.catCount}>{row.n}</span>
              </div>
              <div className={styles.catTrack}>
                <div
                  className={styles.catFill}
                  style={{ width: `${pct}%`, background: color }}
                  aria-hidden
                />
                <span className={styles.catValue}>
                  {yMetric === "mean" ? fmtMean(row.avg) : fmtPct(row.avg)}
                </span>
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
  const common = useMemo(
    () => decorated.filter((r) => !r.is_rare),
    [decorated],
  );
  const rare = useMemo(() => decorated.filter((r) => r.is_rare), [decorated]);

  const scaleMax = yMetric === "mean" ? 7 : 1;

  const presentCategories = useMemo(() => {
    const seen = new Set<CellCategory>();
    for (const r of decorated) seen.add(r.category);
    return CATEGORIES.filter((c) => seen.has(c));
  }, [decorated]);

  return (
    <div className={styles.chart}>
      <div
        className={styles.controls}
        role="toolbar"
        aria-label="Chart controls"
      >
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

      <CategoryAverages rows={decorated} yMetric={yMetric} scaleMax={scaleMax} />

      <ColumnChart
        title="Common cell types"
        subtitle="≥ 1,000 cells sampled per cell type — high-confidence rankings"
        rows={common}
        maxRows={COMMON_MAX}
        yMetric={yMetric}
        sortMode={sortMode}
        scaleMax={scaleMax}
      />

      {rare.length > 0 && (
        <ColumnChart
          title="Rare high-expressors"
          subtitle="< 1,000 cells sampled, mean ≥ 2 — comparison only; small-n caveat"
          rows={rare}
          maxRows={RARE_MAX}
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
