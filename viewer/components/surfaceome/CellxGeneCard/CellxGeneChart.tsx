"use client";

import { useMemo, useState } from "react";
import type {
  CellTypeRow,
  TissueAggregateRow,
} from "../../../lib/cellxgene-enrichment";
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
  /** Top tissues for the gene, used by sort-by-tissue and by the
   *  optional per-tissue summary block (v2.1+). Empty array if the
   *  record is pre-v2.1. */
  tissues?: TissueAggregateRow[];
}

type YMetric = "mean" | "pct";
type SortMode = "value" | "type" | "category" | "tissue";

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

function dominantTissue(r: Decorated): string {
  return r.tissues?.[0]?.tissue ?? "—";
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
  } else if (sortMode === "category") {
    const order = new Map(CATEGORIES.map((c, i) => [c, i]));
    arr.sort((a, b) => {
      const oa = order.get(a.category) ?? 99;
      const ob = order.get(b.category) ?? 99;
      if (oa !== ob) return oa - ob;
      return metric(b) - metric(a);
    });
  } else {
    // sortMode === "tissue": cluster cell types by their dominant tissue
    // (from each row's top_tissues[0]). Tissues are ranked by the max
    // value-on-the-current-metric within the group, so the strongest
    // tissue cluster reads left-to-right first.
    const tissueRank = new Map<string, number>();
    for (const r of arr) {
      const t = dominantTissue(r);
      const cur = tissueRank.get(t) ?? -Infinity;
      tissueRank.set(t, Math.max(cur, metric(r)));
    }
    arr.sort((a, b) => {
      const ta = dominantTissue(a);
      const tb = dominantTissue(b);
      const ra = tissueRank.get(ta) ?? 0;
      const rb = tissueRank.get(tb) ?? 0;
      if (ra !== rb) return rb - ra;
      if (ta !== tb) return ta.localeCompare(tb);
      return metric(b) - metric(a);
    });
  }
  return arr;
}

/**
 * Cell-type chart — horizontal bars, one row per cell type. Reverted
 * from the column layout because for genes like GPR75 (1-4 cell types
 * after the noise filter) the column chart's fixed 240 px height was
 * wasted whitespace. Horizontal rows are ~24 px each so 5 rows takes
 * ~120 px and 25 rows fit in ~600 px — the layout scales with the
 * data instead of reserving a fixed canvas.
 *
 * Each bar fills horizontally to a percentage of `scaleMax` (7 for
 * mean log1p, 1 for pct), colored by the cell type's category. The
 * row's hover/focus state shows a popover with the full label, %
 * expressing, cell counts, and top tissues.
 */
function CellTypeChart({
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
                <span className={styles.barName} title={r.cell_type}>
                  {truncate(r.cell_type, LABEL_TRUNCATE_AT + 16)}
                </span>
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
              {/* Hover/focus popover — full detail. Positioned BELOW
                  the row by the .barRow .popover CSS so it doesn't
                  overlap the next row on the way down the list. */}
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

  // Hide the per-category block when only 1 (or 0) categories qualify:
  // 1 row is redundant with the Common Cell Types chart below (e.g.
  // GPR75 only has 1 kidney epithelial hit → 1 Epithelial row here).
  if (summary.length <= 1) return null;

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

/**
 * Top tissues block — horizontal bars, one per UBERON term in the
 * gene's `top_tissues` (v2.1+). Sits ABOVE the cell-type charts as
 * the coarsest read: "which organs is this gene in?" before drilling
 * into the cell-type subdivisions below. Same shape / metric as
 * `CategoryAverages` — keeps the visual language consistent.
 *
 * Uses a single neutral fill (teal) rather than per-tissue colors:
 * there are ~150 distinct UBERON terms in CZI, too many to color
 * individually without diluting the cell-type category palette
 * below. The reader uses the bar's TEXT label, not its fill, to
 * identify the tissue.
 */
function TopTissues({
  rows,
  yMetric,
  scaleMax,
}: {
  rows: TissueAggregateRow[];
  yMetric: YMetric;
  scaleMax: number;
}) {
  const sorted = useMemo(() => {
    const metric = (r: TissueAggregateRow): number =>
      yMetric === "mean" ? r.mean_log1p_cp10k ?? 0 : r.pct_expressing ?? 0;
    // Qualified tissues first, then trace, each by metric DESC.
    // Otherwise a high-mean small-n trace tissue (pleura at mean 2.3,
    // n=4) would outrank a moderate-mean qualified one (brain at
    // mean 1.97, n=20k) and the visual story would be wrong.
    return [...rows]
      .sort((a, b) => {
        const ta = a.is_trace ? 1 : 0;
        const tb = b.is_trace ? 1 : 0;
        if (ta !== tb) return ta - tb;
        return metric(b) - metric(a);
      })
      .slice(0, 15);
  }, [rows, yMetric]);

  if (sorted.length === 0) return null;

  const tissueColor = "var(--teal-mid, #3d6b60)";

  return (
    <section className={styles.chartBlock}>
      <h3 className={styles.subhead}>
        Top tissues
        <span className={styles.subheadMeta}>
          pooled across cell types in each UBERON tissue · qualified
          first, then trace (small-n) tissues
        </span>
      </h3>
      <ul className={styles.catList}>
        {sorted.map((row) => {
          const value =
            yMetric === "mean" ? row.mean_log1p_cp10k : row.pct_expressing;
          const pct = Math.max(0, Math.min(100, (value / scaleMax) * 100));
          const isTrace = !!row.is_trace;
          // Mute trace rows so the qualified ones read first. The build
          // sorts qualified-first so all trace rows cluster at the
          // bottom of the list — visual hierarchy reinforces the data.
          const rowColor = isTrace
            ? "color-mix(in srgb, var(--teal-mid, #3d6b60) 35%, transparent)"
            : tissueColor;
          return (
            <li
              key={row.uberon_id}
              className={styles.catRow}
              data-trace={isTrace || undefined}
              title={
                isTrace
                  ? `Trace: only ${row.n_expressing} of ${row.n_total.toLocaleString()} cells expressing (${(row.pct_expressing * 100).toFixed(2)}%). Mean is real but small-n.`
                  : undefined
              }
            >
              <div className={styles.catLabel}>
                <span
                  className={styles.swatch}
                  style={{ background: rowColor }}
                  aria-hidden
                />
                <span className={styles.catName}>{row.tissue}</span>
                {isTrace && (
                  <span className={styles.traceBadge} aria-label="trace expression">
                    trace
                  </span>
                )}
                <span
                  className={styles.catCount}
                  title={`${row.n_expressing.toLocaleString()} of ${row.n_total.toLocaleString()} cells expressing`}
                >
                  {fmtN(row.n_expressing)}
                </span>
              </div>
              <div className={styles.catTrack}>
                <div
                  className={styles.catFill}
                  style={{ width: `${pct}%`, background: rowColor }}
                  aria-hidden
                />
                <span className={styles.catValue}>
                  {yMetric === "mean" ? fmtMean(value) : fmtPct(value)}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function CellxGeneChart({ rows, tissues = [] }: Props) {
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
              aria-checked={sortMode === "tissue"}
              data-active={sortMode === "tissue"}
              onClick={() => setSortMode("tissue")}
            >
              By tissue
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

      {tissues.length > 0 && (
        <TopTissues rows={tissues} yMetric={yMetric} scaleMax={scaleMax} />
      )}

      <CategoryAverages rows={decorated} yMetric={yMetric} scaleMax={scaleMax} />

      <CellTypeChart
        title="Common cell types"
        subtitle="≥ 10,000 cells sampled per cell type — high-confidence rankings"
        rows={common}
        maxRows={COMMON_MAX}
        yMetric={yMetric}
        sortMode={sortMode}
        scaleMax={scaleMax}
      />

      {rare.length > 0 && (
        <CellTypeChart
          title="Rare high-expressors"
          subtitle="< 10,000 cells sampled, mean ≥ 2 — comparison only; small-n caveat"
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
