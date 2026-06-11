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
  rows: CellTypeRow[];
  tissues?: TissueAggregateRow[];
}

type YMetric = "score" | "mean" | "pct";
type SortMode = "value" | "type" | "category" | "tissue";

/**
 * Per-metric scale floor. Bars fill against `max(floor, observed)`
 * so:
 *  - For genes whose top expression is moderate, the bar still
 *    shows visible fill (no 0..7 axis dwarfing a 1.97 brain hit).
 *  - For genes whose top expression exceeds the floor, the scale
 *    expands so the bar isn't pinned at 100%.
 *
 * Defaults: 4.5 for mean log1p(CP10K) (a "moderate-to-high"
 * boundary), 1.0 for pct (full saturation, can't exceed 1), and
 * 4.5 × 0.5 = 2.25 for score (a moderate mean × half-population
 * boundary). The user can read the absolute number off the bar's
 * inline value; the bar width is for visual comparison within the
 * gene.
 */
function metricScaleFloor(yMetric: YMetric): number {
  if (yMetric === "mean") return 4.5;
  if (yMetric === "pct") return 1.0;
  return 2.25; // score = mean × pct
}

/**
 * Read the active metric off a row.
 *  - mean: mean log1p(CP10K) among expressing cells (the WMG viewer's scale)
 *  - pct: fraction of cells expressing (n_expressing / n_total)
 *  - score: mean × pct, the population-mean expression — an
 *    HPA-nTPM-style metric that combines both channels into one
 *    number. Best single metric for delivery-target questions
 *    ("if I pick cells of this type, what total signal do I get?").
 */
function readMetric(
  m: { mean_log1p_cp10k?: number; pct_expressing?: number },
  yMetric: YMetric,
): number {
  const mean = m.mean_log1p_cp10k ?? 0;
  const pct = m.pct_expressing ?? 0;
  if (yMetric === "mean") return mean;
  if (yMetric === "pct") return pct;
  return mean * pct;
}

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

function fmtValue(v: number, yMetric: YMetric): string {
  return yMetric === "pct" ? fmtPct(v) : fmtMean(v);
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

/**
 * Per-chart toolbar. Each chart owns its own yMetric + sortMode
 * state, so the reader can answer "what's the top score?" and "what's
 * the top % expressing?" simultaneously across the Tissues / Common
 * cell types / Per-category blocks without one toggle dragging all
 * three. `sortOptions` is parameterized because tissue charts don't
 * have a "by category" mode and category-average charts don't take
 * any sort mode at all.
 */
function ChartControls({
  yMetric,
  setYMetric,
  sortMode,
  setSortMode,
  sortOptions,
}: {
  yMetric: YMetric;
  setYMetric: (m: YMetric) => void;
  sortMode?: SortMode;
  setSortMode?: (s: SortMode) => void;
  sortOptions?: { value: SortMode; label: string; title?: string }[];
}) {
  return (
    <div
      className={styles.controls}
      role="toolbar"
      aria-label="Chart controls"
    >
      <div className={styles.controlGroup}>
        <span className={styles.controlLabel}>Y-axis</span>
        <div
          className={styles.toggle}
          role="radiogroup"
          aria-label="Y-axis metric"
        >
          <button
            type="button"
            role="radio"
            aria-checked={yMetric === "score"}
            data-active={yMetric === "score"}
            onClick={() => setYMetric("score")}
            title="Mean × % expressing — population-mean expression (HPA-nTPM-like). Best one-number metric: 'if I pick cells of this type, what total signal do I get?'"
          >
            Score (mean × %)
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={yMetric === "mean"}
            data-active={yMetric === "mean"}
            onClick={() => setYMetric("mean")}
            title="Mean log1p(CP10K) among expressing cells — how strongly the cells that DO express it transcribe it"
          >
            Mean
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={yMetric === "pct"}
            data-active={yMetric === "pct"}
            onClick={() => setYMetric("pct")}
            title="Fraction of cells expressing the gene — n_expressing / n_total"
          >
            % expressing
          </button>
        </div>
      </div>
      {sortOptions && setSortMode && sortMode && (
        <div className={styles.controlGroup}>
          <span className={styles.controlLabel}>Sort</span>
          <div
            className={styles.toggle}
            role="radiogroup"
            aria-label="Sort order"
          >
            {sortOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                role="radio"
                aria-checked={sortMode === opt.value}
                data-active={sortMode === opt.value}
                onClick={() => setSortMode(opt.value)}
                title={opt.title}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * One vertical column bar in a chart. Height = pct of scale max.
 * Color = caller-provided (categories for cell types, neutral teal
 * for tissues). Trace bars render with reduced opacity. Label
 * rotated -45° beneath the bar; full label + hover detail in the
 * popover.
 */
function ColumnBar({
  height,
  color,
  label,
  isTrace,
  popover,
  hoverTitle,
}: {
  /** 0..100 percentage of chart scale. */
  height: number;
  color: string;
  label: string;
  isTrace?: boolean;
  popover: React.ReactNode;
  hoverTitle?: string;
}) {
  const fill = isTrace
    ? `color-mix(in srgb, ${color} 35%, transparent)`
    : color;
  return (
    <li
      className={styles.colBar}
      tabIndex={0}
      data-trace={isTrace || undefined}
      title={hoverTitle}
    >
      <div className={styles.colTrack}>
        <div
          className={styles.colFill}
          style={{ height: `${height}%`, background: fill }}
          aria-hidden
        />
      </div>
      <span className={styles.colLabel} title={label} aria-label={label}>
        {truncate(label, 24)}
        {isTrace && (
          <span className={styles.traceBadge} aria-label="trace expression">
            trace
          </span>
        )}
      </span>
      <div className={styles.popover} role="tooltip">
        {popover}
      </div>
    </li>
  );
}

/**
 * Y-axis ticks scaled to the chart's actual max value.
 */
function YAxis({ scaleMax, yMetric }: { scaleMax: number; yMetric: YMetric }) {
  const ticks = [scaleMax, scaleMax * 0.75, scaleMax * 0.5, scaleMax * 0.25, 0];
  return (
    <div className={styles.yAxis} aria-hidden>
      {ticks.map((v) => (
        <span key={v} className={styles.yTick}>
          {fmtValue(v, yMetric)}
        </span>
      ))}
    </div>
  );
}

/**
 * Cell-type column chart. Vertical bars colored by category, labels
 * rotated below. Reader's own yMetric + sortMode controls in the
 * header. Qualified bars first, trace at the end.
 */
function CellTypeChart({
  title,
  subtitle,
  rows,
}: {
  title: string;
  subtitle: string;
  rows: Decorated[];
}) {
  const [yMetric, setYMetric] = useState<YMetric>("score");
  const [sortMode, setSortMode] = useState<SortMode>("value");

  const sorted = useMemo(() => {
    const arr = [...rows];
    const m = (r: Decorated): number => readMetric(r, yMetric);
    const traceTier = (r: Decorated): number => (r.is_trace ? 1 : 0);
    if (sortMode === "value") {
      arr.sort((a, b) => {
        const tt = traceTier(a) - traceTier(b);
        if (tt !== 0) return tt;
        return m(b) - m(a);
      });
    } else if (sortMode === "type") {
      arr.sort((a, b) => a.cell_type.localeCompare(b.cell_type));
    } else if (sortMode === "category") {
      const order = new Map(CATEGORIES.map((c, i) => [c, i]));
      arr.sort((a, b) => {
        const oa = order.get(a.category) ?? 99;
        const ob = order.get(b.category) ?? 99;
        if (oa !== ob) return oa - ob;
        return m(b) - m(a);
      });
    } else {
      const tissueRank = new Map<string, number>();
      for (const r of arr) {
        const t = dominantTissue(r);
        const cur = tissueRank.get(t) ?? -Infinity;
        tissueRank.set(t, Math.max(cur, m(r)));
      }
      arr.sort((a, b) => {
        const ta = dominantTissue(a);
        const tb = dominantTissue(b);
        const ra = tissueRank.get(ta) ?? 0;
        const rb = tissueRank.get(tb) ?? 0;
        if (ra !== rb) return rb - ra;
        if (ta !== tb) return ta.localeCompare(tb);
        return m(b) - m(a);
      });
    }
    return arr;
  }, [rows, sortMode, yMetric]);

  const scaleMax = useMemo(() => {
    const observed = sorted.reduce(
      (mx, r) => Math.max(mx, readMetric(r, yMetric)),
      0,
    );
    return Math.max(metricScaleFloor(yMetric), observed);
  }, [sorted, yMetric]);

  if (sorted.length === 0) {
    return (
      <section className={styles.chartBlock}>
        <h3 className={styles.subhead}>
          {title}
          <span className={styles.subheadMeta}>{subtitle}</span>
        </h3>
        <p className={styles.empty}>No qualifying cell types.</p>
      </section>
    );
  }

  return (
    <section className={styles.chartBlock}>
      <h3 className={styles.subhead}>
        {title}
        <span className={styles.subheadMeta}>{subtitle}</span>
      </h3>
      <ChartControls
        yMetric={yMetric}
        setYMetric={setYMetric}
        sortMode={sortMode}
        setSortMode={setSortMode}
        sortOptions={[
          { value: "value", label: "By value" },
          { value: "category", label: "By category" },
          { value: "tissue", label: "By tissue" },
          { value: "type", label: "A → Z" },
        ]}
      />
      <div className={styles.colChart}>
        <YAxis scaleMax={scaleMax} yMetric={yMetric} />
        <ul className={styles.colCanvas}>
          {sorted.map((r) => {
            const meanVal = r.mean_log1p_cp10k ?? 0;
            const pctVal = r.pct_expressing ?? 0;
            const nExpressing = r.n_expressing ?? 0;
            const nTotal = r.n_total ?? nExpressing;
            const value = readMetric(r, yMetric);
            const height = Math.max(
              0,
              Math.min(100, (value / scaleMax) * 100),
            );
            const baseColor = CATEGORY_COLORS[r.category];
            const tissues = (r.tissues ?? []).slice(0, 3);
            const popover = (
              <>
                <div className={styles.popHeader}>
                  <span
                    className={styles.swatch}
                    style={{ background: baseColor }}
                    aria-hidden
                  />
                  <strong>{r.cell_type}</strong>
                  <span className={styles.popMeta}>{r.cl_id}</span>
                  <span className={styles.popCategory}>{r.category}</span>
                </div>
                <dl className={styles.popStats}>
                  <div>
                    <dt>Score</dt>
                    <dd>{fmtMean(meanVal * pctVal)}</dd>
                  </div>
                  <div>
                    <dt>Mean log1p</dt>
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
                {tissues.length > 0 && (
                  <div className={styles.popTissues}>
                    <span className={styles.popTissuesLabel}>Tissues</span>
                    <ul>
                      {tissues.map((t) => (
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
              </>
            );
            const hoverTitle = r.is_trace
              ? `Trace: only ${nExpressing} of ${nTotal.toLocaleString()} cells expressing (${(pctVal * 100).toFixed(2)}%). Mean is real but small-n.`
              : undefined;
            return (
              <ColumnBar
                key={r.cl_id}
                height={height}
                color={baseColor}
                label={r.cell_type}
                isTrace={r.is_trace}
                popover={popover}
                hoverTitle={hoverTitle}
              />
            );
          })}
        </ul>
      </div>
    </section>
  );
}

/**
 * Top tissues column chart. Same shape as CellTypeChart but rows are
 * UBERON terms with a single neutral fill (teal) — there are too many
 * tissue terms to color individually without diluting the cell-class
 * palette below.
 */
function TopTissues({ rows }: { rows: TissueAggregateRow[] }) {
  const [yMetric, setYMetric] = useState<YMetric>("score");
  const [sortMode, setSortMode] = useState<SortMode>("value");

  const sorted = useMemo(() => {
    const arr = [...rows];
    const m = (r: TissueAggregateRow): number => readMetric(r, yMetric);
    const traceTier = (r: TissueAggregateRow): number => (r.is_trace ? 1 : 0);
    if (sortMode === "type") {
      arr.sort((a, b) => a.tissue.localeCompare(b.tissue));
    } else {
      arr.sort((a, b) => {
        const tt = traceTier(a) - traceTier(b);
        if (tt !== 0) return tt;
        return m(b) - m(a);
      });
    }
    return arr;
  }, [rows, sortMode, yMetric]);

  const scaleMax = useMemo(() => {
    const observed = sorted.reduce(
      (mx, r) => Math.max(mx, readMetric(r, yMetric)),
      0,
    );
    return Math.max(metricScaleFloor(yMetric), observed);
  }, [sorted, yMetric]);

  if (sorted.length === 0) return null;

  const tissueColor = "var(--teal-mid, #3d6b60)";

  return (
    <section className={styles.chartBlock}>
      <h3 className={styles.subhead}>
        Top tissues
        <span className={styles.subheadMeta}>
          pooled across cell types in each UBERON tissue · qualified
          first, then trace (small-n)
        </span>
      </h3>
      <ChartControls
        yMetric={yMetric}
        setYMetric={setYMetric}
        sortMode={sortMode}
        setSortMode={setSortMode}
        sortOptions={[
          { value: "value", label: "By value" },
          { value: "type", label: "A → Z" },
        ]}
      />
      <div className={styles.colChart}>
        <YAxis scaleMax={scaleMax} yMetric={yMetric} />
        <ul className={styles.colCanvas}>
          {sorted.map((r) => {
            const value = readMetric(r, yMetric);
            const height = Math.max(
              0,
              Math.min(100, (value / scaleMax) * 100),
            );
            const meanVal = r.mean_log1p_cp10k ?? 0;
            const pctVal = r.pct_expressing ?? 0;
            const popover = (
              <>
                <div className={styles.popHeader}>
                  <span
                    className={styles.swatch}
                    style={{ background: tissueColor }}
                    aria-hidden
                  />
                  <strong>{r.tissue}</strong>
                  <span className={styles.popMeta}>{r.uberon_id}</span>
                </div>
                <dl className={styles.popStats}>
                  <div>
                    <dt>Score</dt>
                    <dd>{fmtMean(meanVal * pctVal)}</dd>
                  </div>
                  <div>
                    <dt>Mean log1p</dt>
                    <dd>{fmtMean(meanVal)}</dd>
                  </div>
                  <div>
                    <dt>% expressing</dt>
                    <dd>
                      {fmtPct(pctVal)}
                      <span className={styles.popHint}>
                        {" "}
                        ({fmtN(r.n_expressing)} / {fmtN(r.n_total)} cells)
                      </span>
                    </dd>
                  </div>
                </dl>
              </>
            );
            const hoverTitle = r.is_trace
              ? `Trace: only ${r.n_expressing} of ${r.n_total.toLocaleString()} cells expressing (${(pctVal * 100).toFixed(2)}%). Mean is real but small-n.`
              : undefined;
            return (
              <ColumnBar
                key={r.uberon_id}
                height={height}
                color={tissueColor}
                label={r.tissue}
                isTrace={r.is_trace}
                popover={popover}
                hoverTitle={hoverTitle}
              />
            );
          })}
        </ul>
      </div>
    </section>
  );
}

/**
 * Per-category summary. One horizontal bar per category present in
 * the gene's top_cell_types. Reader-visible as the "first read" of
 * which broad cell class the gene is strongest in. Vertical-column
 * layout would be overkill for ≤10 short rows; keeping horizontal.
 */
function CategoryAverages({ rows }: { rows: Decorated[] }) {
  const [yMetric, setYMetric] = useState<YMetric>("score");

  const summary = useMemo(() => {
    const groups = new Map<CellCategory, Decorated[]>();
    for (const r of rows) {
      const arr = groups.get(r.category) ?? [];
      arr.push(r);
      groups.set(r.category, arr);
    }
    const m = (r: Decorated): number => readMetric(r, yMetric);
    return CATEGORIES.map((c) => {
      const arr = groups.get(c) ?? [];
      if (arr.length === 0) return null;
      const avg = arr.reduce((s, r) => s + m(r), 0) / arr.length;
      return { category: c, n: arr.length, avg };
    })
      .filter(
        (d): d is { category: CellCategory; n: number; avg: number } => !!d,
      )
      .sort((a, b) => b.avg - a.avg);
  }, [rows, yMetric]);

  const scaleMax = useMemo(() => {
    const observed = summary.reduce((mx, r) => Math.max(mx, r.avg), 0);
    return Math.max(metricScaleFloor(yMetric), observed);
  }, [summary, yMetric]);

  if (summary.length <= 1) return null;

  return (
    <section className={styles.chartBlock}>
      <h3 className={styles.subhead}>
        Per-category average
        <span className={styles.subheadMeta}>
          mean of the active metric across cell types in each category
        </span>
      </h3>
      <ChartControls yMetric={yMetric} setYMetric={setYMetric} />
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
                  {fmtValue(row.avg, yMetric)}
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
  const decorated = useMemo(() => decorate(rows), [rows]);

  const presentCategories = useMemo(() => {
    const seen = new Set<CellCategory>();
    for (const r of decorated) seen.add(r.category);
    return CATEGORIES.filter((c) => seen.has(c));
  }, [decorated]);

  return (
    <div className={styles.chart}>
      {tissues.length > 0 && <TopTissues rows={tissues} />}
      <CategoryAverages rows={decorated} />
      <CellTypeChart
        title="Cell types"
        subtitle="every cell type with detectable expression · qualified first, then trace"
        rows={decorated}
      />
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
