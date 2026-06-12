"use client";

import { useMemo, useState } from "react";
import type {
  CellInTissue,
  CellTypeRow,
  TissueAggregateRow,
} from "../../../lib/cellxgene-enrichment";
import {
  TISSUE_CATEGORIES,
  type TissueCategory,
  type TissueCategoryId,
  tissueCategoryColorFor,
  tissueCategoryForUberonId,
} from "../../../lib/tissue-categories";
import styles from "./CellxGeneCard.module.css";

interface Props {
  rows: CellTypeRow[];
  tissues?: TissueAggregateRow[];
  cellsByTissue?: Record<string, CellInTissue[]>;
}

type YMetric = "score" | "mean" | "pct";
type SortMode = "value" | "type" | "tissue" | "category";

/* Cell-type bars carry the "mode" signal:
   - Overall Top-20 view: lavender (the same purple used in design
     tokens for Neural / non-tissue-specific reads). Distinct from
     the tissue chart's teal, signals "this is the global view, not
     filtered to anything."
   - Tissue-filtered view: maroon (the primary editorial accent).
     The mode change is visible without having to read the chart
     title — the bar color shifts when you click a tissue. */
const CELL_BAR_COLOR_FILTERED = "var(--maroon-mid, #922038)";
const CELL_BAR_COLOR_OVERALL = "var(--lavender-bright, #8878c8)";
// Tissue bars are now colored per-row by their organ-system category
// (see lib/tissue-categories.ts). SELECTED_TISSUE_COLOR is the override
// for the currently-clicked tissue so it pops against the category
// rainbow.
const SELECTED_TISSUE_COLOR = "var(--maroon-mid, #922038)";

/**
 * Per-metric scale floor. Bars fill against `max(floor, observed)`
 * so moderate-expression genes still produce visible bars without
 * being dwarfed by a 0..7 axis. The user reads the absolute value
 * off the inline label; bar width is for in-gene comparison.
 */
function metricScaleFloor(yMetric: YMetric): number {
  if (yMetric === "mean") return 4.5;
  if (yMetric === "pct") return 1.0;
  return 2.25;
}

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

// Lookup via the reverse `cells_by_tissue` map (v2.1.2+). The build
// emits this so the tissue cross-filter doesn't have to walk each
// cell type's truncated tissues[] array. Returns [] if the gene
// doesn't have any cell types in the requested tissue or the map
// is missing.
function cellsInTissue(
  cellsByTissue: Record<string, CellInTissue[]> | undefined,
  uberonId: string | null,
): CellInTissue[] {
  if (!uberonId || !cellsByTissue) return [];
  return cellsByTissue[uberonId] ?? [];
}

interface SortOption {
  value: SortMode;
  label: string;
  title?: string;
}

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
  sortOptions?: SortOption[];
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
            title="Mean × % expressing — population-mean expression (HPA-nTPM-like). Best one-number metric for delivery-target questions."
          >
            Score (mean × %)
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={yMetric === "mean"}
            data-active={yMetric === "mean"}
            onClick={() => setYMetric("mean")}
            title="Mean log1p(CP10K) among expressing cells"
          >
            Mean
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={yMetric === "pct"}
            data-active={yMetric === "pct"}
            onClick={() => setYMetric("pct")}
            title="Fraction of cells expressing the gene"
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

const Y_AXIS_TITLES: Record<YMetric, string> = {
  mean: "mean log1p(CP10K) in expressing cells",
  pct: "fraction of cells expressing",
  score: "score = mean log1p(CP10K) × % expressing",
};

function YAxis({ scaleMax, yMetric }: { scaleMax: number; yMetric: YMetric }) {
  const ticks = [scaleMax, scaleMax * 0.75, scaleMax * 0.5, scaleMax * 0.25, 0];
  return (
    <div className={styles.yAxisContainer} aria-hidden>
      <div className={styles.yAxisTitle}>{Y_AXIS_TITLES[yMetric]}</div>
      <div className={styles.yAxis}>
        {ticks.map((v) => (
          <span key={v} className={styles.yTick}>
            {fmtValue(v, yMetric)}
          </span>
        ))}
      </div>
    </div>
  );
}

function ColumnBar({
  height,
  color,
  label,
  isTrace,
  isSelected,
  popover,
  hoverTitle,
  onClick,
}: {
  height: number;
  color: string;
  label: string;
  isTrace?: boolean;
  isSelected?: boolean;
  popover: React.ReactNode;
  hoverTitle?: string;
  onClick?: () => void;
}) {
  const fill = isTrace
    ? `color-mix(in srgb, ${color} 35%, transparent)`
    : color;
  // Use a button when the bar is interactive (tissue chart) and a
  // plain div otherwise. <button>-in-<li> is valid; <li>-in-<li> is
  // not, so don't fall back to <li> when there's no onClick.
  const hitContents = (
    <>
      <div className={styles.colTrack}>
        <div
          className={styles.colFill}
          style={{ height: `${height}%`, background: fill }}
          aria-hidden
        />
      </div>
      <span className={styles.colLabel} title={label} aria-label={label}>
        {label}
      </span>
    </>
  );
  // Expose the bar's fill % as a CSS var so the popover can anchor
  // its bottom edge to the fill's top (vs the colBar's top, which
  // is the canvas height — far above the visible fill for low bars).
  const barStyle = {
    ["--bar-height" as string]: `${height}%`,
  } as React.CSSProperties;
  return (
    <li
      className={styles.colBar}
      style={barStyle}
      data-trace={isTrace || undefined}
      data-selected={isSelected || undefined}
    >
      {onClick ? (
        <button
          type="button"
          className={styles.colBarHit}
          onClick={onClick}
          title={hoverTitle}
          aria-pressed={!!isSelected}
        >
          {hitContents}
        </button>
      ) : (
        // No onClick, no tabIndex — cell-type bars aren't selectable;
        // tab-stopping them implied an interaction that doesn't exist.
        <div className={styles.colBarHit} title={hoverTitle}>
          {hitContents}
        </div>
      )}
      <div className={styles.popover} role="tooltip">
        {popover}
      </div>
    </li>
  );
}

function cellPopover(
  r: CellTypeRow,
  value: number,
  swatchColor: string,
): React.ReactNode {
  const meanVal = r.mean_log1p_cp10k ?? 0;
  const pctVal = r.pct_expressing ?? 0;
  const nExpressing = r.n_expressing ?? 0;
  const nTotal = r.n_total ?? nExpressing;
  const tissues = (r.tissues ?? []).slice(0, 3);
  return (
    <>
      <div className={styles.popHeader}>
        <span
          className={styles.swatch}
          style={{ background: swatchColor }}
          aria-hidden
        />
        <strong>{r.cell_type}</strong>
        <span className={styles.popMeta}>{r.cl_id}</span>
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
                  {t.pct_expressing != null ? fmtPct(t.pct_expressing) : ""}{" "}
                  {fmtMean(t.mean_log1p_cp10k)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

function tissuePopover(
  t: TissueAggregateRow,
  swatchColor: string,
  categoryLabel: string,
): React.ReactNode {
  const meanVal = t.mean_log1p_cp10k ?? 0;
  const pctVal = t.pct_expressing ?? 0;
  return (
    <>
      <div className={styles.popHeader}>
        <span
          className={styles.swatch}
          style={{ background: swatchColor }}
          aria-hidden
        />
        <strong>{t.tissue}</strong>
        <span className={styles.popMeta}>
          {t.uberon_id} · {categoryLabel}
        </span>
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
              ({fmtN(t.n_expressing)} / {fmtN(t.n_total)} cells)
            </span>
          </dd>
        </div>
      </dl>
      <p className={styles.popHint}>
        Click to filter cell types to this tissue.
      </p>
    </>
  );
}

/**
 * Top tissues — vertical bars. CLICK a bar to filter the All-cell-types
 * chart below to only show cell types in that tissue, with their
 * tissue-specific stats. Click again (or the "All tissues" reset) to
 * clear.
 */
function TopTissues({
  rows,
  selectedUberonId,
  onSelect,
}: {
  rows: TissueAggregateRow[];
  selectedUberonId: string | null;
  onSelect: (uberonId: string) => void;
}) {
  const [yMetric, setYMetric] = useState<YMetric>("score");
  const [sortMode, setSortMode] = useState<SortMode>("value");

  const sorted = useMemo(() => {
    const arr = [...rows];
    const m = (r: TissueAggregateRow): number => readMetric(r, yMetric);
    if (sortMode === "type") {
      arr.sort((a, b) => a.tissue.localeCompare(b.tissue));
    } else if (sortMode === "category") {
      // Group tissues by their organ-system category. The
      // TISSUE_CATEGORIES list defines a canonical order (CNS first,
      // head/sensory, respiratory, ..., fluids/other last); within
      // each group, rank DESC by the active metric so the strongest
      // tissue per organ system is leftmost. Trace tissues sink to
      // the BOTTOM regardless of category, matching the qualified-
      // first rule on the value-sort.
      const order = new Map(
        TISSUE_CATEGORIES.map((c, i) => [c.id, i] as const),
      );
      const cat = (r: TissueAggregateRow): TissueCategoryId =>
        tissueCategoryForUberonId(r.uberon_id).id;
      arr.sort((a, b) => {
        const ta = a.is_trace ? 1 : 0;
        const tb = b.is_trace ? 1 : 0;
        if (ta !== tb) return ta - tb;
        const oa = order.get(cat(a)) ?? 99;
        const ob = order.get(cat(b)) ?? 99;
        if (oa !== ob) return oa - ob;
        return m(b) - m(a);
      });
    } else {
      arr.sort((a, b) => {
        const ta = a.is_trace ? 1 : 0;
        const tb = b.is_trace ? 1 : 0;
        if (ta !== tb) return ta - tb;
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

  return (
    <section className={styles.chartBlock}>
      <h3 className={styles.subhead}>
        Tissues
        <span className={styles.subheadMeta}>
          every UBERON tissue with detectable signal (n_total ≥ 1k) ·
          {sorted.length} shown · click a bar to filter the
          &ldquo;All cell types&rdquo; chart below
        </span>
      </h3>
      <ChartControls
        yMetric={yMetric}
        setYMetric={setYMetric}
        sortMode={sortMode}
        setSortMode={setSortMode}
        sortOptions={[
          { value: "value", label: "By value" },
          {
            value: "category",
            label: "By category",
            title:
              "Group bars by organ-system category (CNS, respiratory, lymphoid, …); rank DESC within each group",
          },
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
            const isSelected = r.uberon_id === selectedUberonId;
            const category = tissueCategoryForUberonId(r.uberon_id);
            const categoryColor = tissueCategoryColorFor(r.uberon_id);
            // Selected bar reverts to maroon so the click target reads
            // distinctly against the rainbow of category colors.
            const barColor = isSelected
              ? SELECTED_TISSUE_COLOR
              : categoryColor;
            const hoverTitle = r.is_trace
              ? `Trace: only ${r.n_expressing} of ${r.n_total.toLocaleString()} cells expressing (${(r.pct_expressing * 100).toFixed(2)}%). Mean is real but small-n.`
              : `Click to filter to ${r.tissue} cell types`;
            return (
              <ColumnBar
                key={r.uberon_id}
                height={height}
                color={barColor}
                label={r.tissue}
                isTrace={r.is_trace}
                isSelected={isSelected}
                popover={tissuePopover(r, categoryColor, category.label)}
                hoverTitle={hoverTitle}
                onClick={() => onSelect(r.uberon_id)}
              />
            );
          })}
        </ul>
      </div>
      <TissueCategoryLegend rows={sorted} />
    </section>
  );
}

/**
 * Below-chart legend strip listing the tissue organ-system categories
 * present in this gene's tissue rows. Skipped when only one category
 * shows up — at that point the legend is just the chart's caption
 * repeated. Categories appear in canonical (head-to-toe) order, not
 * in alphabetical or by-frequency, so the legend reads the same way
 * across genes.
 */
function TissueCategoryLegend({
  rows,
}: {
  rows: ReadonlyArray<{ uberon_id: string }>;
}) {
  const present = new Set<TissueCategoryId>();
  for (const r of rows) {
    present.add(tissueCategoryForUberonId(r.uberon_id).id);
  }
  if (present.size < 2) return null;
  const items: TissueCategory[] = TISSUE_CATEGORIES.filter((c) =>
    present.has(c.id),
  );
  return (
    <ul className={styles.tissueCatLegend} aria-label="Tissue categories">
      {items.map((c) => (
        <li key={c.id} className={styles.tissueCatLegendItem}>
          <span
            className={styles.tissueCatSwatch}
            style={{ background: `var(${c.colorVar}, ${c.colorFallback})` }}
            aria-hidden
          />
          {c.label}
        </li>
      ))}
    </ul>
  );
}

/**
 * One unified cell-type chart, sitting directly under the Tissues
 * chart. Two modes:
 *
 *  - **No tissue selected**: shows the top 20 cell types globally,
 *    sorted DESC by the active metric. Qualified first, trace
 *    (small-n) appended. Headline: "Top 20 cell types".
 *
 *  - **Tissue selected (via Tissues bar click)**: shows every cell
 *    type whose top-3 tissue list includes the selection, with
 *    stats re-keyed to that tissue's specific mean/pct/n. Headline:
 *    "Cell types in {tissue}". A reset chip in the header returns
 *    to the Top 20 view.
 *
 * Bars are NOT clickable in either mode — cell types are leaves of
 * the hierarchy; there's no concept of "drill into a cell type".
 */
function CellTypeChart({
  rows,
  cellsByTissue,
  selectedUberonId,
  selectedTissueLabel,
  onClearTissue,
}: {
  rows: CellTypeRow[];
  cellsByTissue: Record<string, CellInTissue[]>;
  selectedUberonId: string | null;
  selectedTissueLabel: string | null;
  onClearTissue: () => void;
}) {
  const [yMetric, setYMetric] = useState<YMetric>("score");
  const [sortMode, setSortMode] = useState<SortMode>("value");
  const TOP_N = 20;

  interface ViewRow {
    cl_id: string;
    cell_type: string;
    mean_log1p_cp10k: number;
    pct_expressing: number;
    n_expressing: number;
    n_total: number;
    is_trace: boolean;
    // Original row (when available) for popover detail. In the
    // tissue-filtered case the source is CellInTissue which doesn't
    // carry a `tissues` subarray; popover falls back to single-line
    // info in that case.
    base: CellTypeRow | null;
  }

  // Build view rows:
  //  - Filtered: read from `cellsByTissue[selectedUberonId]` directly.
  //    Cell types not in the global top_cell_types still appear here
  //    (e.g. fibroblast in GPR75's vasculature — pooled mean too low
  //    to make top-50 trace, but vasculature is where its 4
  //    expressing cells live).
  //  - Unfiltered: read from `rows` (top_cell_types), capped at TOP_N
  //    after sorting.
  const viewRows: ViewRow[] = useMemo(() => {
    if (selectedUberonId) {
      const cells = cellsInTissue(cellsByTissue, selectedUberonId);
      // Index the global top_cell_types so a popover can show the
      // cell type's cross-tissue context where available.
      const byCl = new Map(rows.map((r) => [r.cl_id, r]));
      return cells.map((c): ViewRow => ({
        cl_id: c.cl_id,
        cell_type: c.cell_type,
        mean_log1p_cp10k: c.mean_log1p_cp10k,
        pct_expressing: c.pct_expressing,
        n_expressing: c.n_expressing,
        n_total: c.n_total,
        is_trace: !!c.is_trace,
        base: byCl.get(c.cl_id) ?? null,
      }));
    }
    return rows.map((r): ViewRow => ({
      cl_id: r.cl_id,
      cell_type: r.cell_type,
      mean_log1p_cp10k: r.mean_log1p_cp10k,
      pct_expressing: r.pct_expressing,
      n_expressing: r.n_expressing,
      n_total: r.n_total,
      is_trace: !!r.is_trace,
      base: r,
    }));
  }, [rows, selectedUberonId, cellsByTissue]);

  const sorted = useMemo(() => {
    const arr = [...viewRows];
    const m = (r: ViewRow): number => readMetric(r, yMetric);
    const traceTier = (r: ViewRow): number => (r.is_trace ? 1 : 0);
    if (sortMode === "type") {
      arr.sort((a, b) => a.cell_type.localeCompare(b.cell_type));
    } else if (sortMode === "tissue") {
      // Only meaningful in the unfiltered view; sort by dominant
      // tissue (from base row) then by metric DESC.
      arr.sort((a, b) => {
        // "By tissue" sort is only shown in the unfiltered view
        // (no `cellsByTissue` source), where base is always non-null.
        // Safe-guard with optional chaining anyway.
        const ta = a.base?.tissues?.[0]?.tissue ?? "";
        const tb = b.base?.tissues?.[0]?.tissue ?? "";
        if (ta !== tb) return ta.localeCompare(tb);
        return m(b) - m(a);
      });
    } else {
      arr.sort((a, b) => {
        const tt = traceTier(a) - traceTier(b);
        if (tt !== 0) return tt;
        return m(b) - m(a);
      });
    }
    // Only cap the unfiltered view at TOP_N — the filtered view
    // shows every cell type in the tissue (usually < 30).
    return selectedUberonId ? arr : arr.slice(0, TOP_N);
  }, [viewRows, sortMode, yMetric, selectedUberonId]);

  const scaleMax = useMemo(() => {
    const observed = sorted.reduce(
      (mx, r) => Math.max(mx, readMetric(r, yMetric)),
      0,
    );
    return Math.max(metricScaleFloor(yMetric), observed);
  }, [sorted, yMetric]);

  const title = selectedTissueLabel
    ? `Cell types in ${selectedTissueLabel}`
    : `Top ${TOP_N} cell types`;
  const subtitle = selectedTissueLabel
    ? `tissue-specific expression within ${selectedTissueLabel} · ${sorted.length} shown`
    : `highest expression overall · qualified first, trace (small-n) appended`;

  // Sort options depend on view: tissue-filtered view doesn't need
  // a "by tissue" sort (all rows are in the same tissue).
  const sortOptions: SortOption[] = selectedTissueLabel
    ? [
        { value: "value", label: "By value" },
        { value: "type", label: "A → Z" },
      ]
    : [
        { value: "value", label: "By value" },
        { value: "tissue", label: "By tissue" },
        { value: "type", label: "A → Z" },
      ];

  // Bar color signals the mode (purple = global Top-20, maroon =
  // tissue-filtered). Reader sees the mode shift at a glance when
  // they click a tissue, even before reading the title.
  const cellBarColor = selectedTissueLabel
    ? CELL_BAR_COLOR_FILTERED
    : CELL_BAR_COLOR_OVERALL;

  return (
    <section className={styles.chartBlock}>
      <h3 className={styles.subhead}>
        {/* Title + reset button sit on one row so the "back to Top 20"
            action is right next to the chart's current name; the meta
            subtitle drops to the line below. */}
        <span className={styles.titleRow}>
          <span className={styles.titleText}>{title}</span>
          {selectedTissueLabel && (
            <button
              type="button"
              className={styles.resetLink}
              onClick={onClearTissue}
            >
              ← Show top {TOP_N} overall
            </button>
          )}
        </span>
        <span className={styles.subheadMeta}>{subtitle}</span>
      </h3>
      <ChartControls
        yMetric={yMetric}
        setYMetric={setYMetric}
        sortMode={sortMode}
        setSortMode={setSortMode}
        sortOptions={sortOptions}
      />
      {sorted.length === 0 ? (
        <p className={styles.empty}>
          No cell types in {selectedTissueLabel ?? "this view"}.
        </p>
      ) : (
        <div className={styles.colChart}>
          <YAxis scaleMax={scaleMax} yMetric={yMetric} />
          <ul className={styles.colCanvas}>
            {sorted.map((r) => {
              const value = readMetric(r, yMetric);
              const height = Math.max(
                0,
                Math.min(100, (value / scaleMax) * 100),
              );
              const hoverTitle = r.is_trace
                ? `Trace: only ${r.n_expressing} of ${r.n_total.toLocaleString()} cells expressing (${(r.pct_expressing * 100).toFixed(2)}%). Mean is real but small-n.`
                : undefined;
              // For tissue-filtered rows whose cell type isn't in
              // top_cell_types, build a synthetic CellTypeRow from
              // the view-row stats so the popover renders.
              const popoverRow: CellTypeRow = r.base ?? {
                cl_id: r.cl_id,
                cell_type: r.cell_type,
                mean_log1p_cp10k: r.mean_log1p_cp10k,
                pct_expressing: r.pct_expressing,
                n_expressing: r.n_expressing,
                n_total: r.n_total,
                is_rare: r.n_total < 10_000,
                is_trace: r.is_trace,
                tissues: [],
              };
              return (
                <ColumnBar
                  key={r.cl_id}
                  height={height}
                  color={cellBarColor}
                  label={r.cell_type}
                  isTrace={r.is_trace}
                  popover={cellPopover(popoverRow, value, cellBarColor)}
                  hoverTitle={hoverTitle}
                />
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}

export function CellxGeneChart({
  rows,
  tissues = [],
  cellsByTissue = {},
}: Props) {
  const [selectedUberonId, setSelectedUberonId] = useState<string | null>(null);

  const tissueLabel = useMemo(() => {
    if (!selectedUberonId) return null;
    return tissues.find((t) => t.uberon_id === selectedUberonId)?.tissue ?? null;
  }, [selectedUberonId, tissues]);

  const handleSelectTissue = (uberonId: string) => {
    setSelectedUberonId((curr) => (curr === uberonId ? null : uberonId));
  };

  return (
    <div className={styles.chart}>
      {tissues.length > 0 && (
        <TopTissues
          rows={tissues}
          selectedUberonId={selectedUberonId}
          onSelect={handleSelectTissue}
        />
      )}
      {/* One combined cell-type chart directly under Tissues. Shows
          Top 20 overall when no tissue is selected; swaps to
          tissue-filtered when a tissue bar is clicked. The clear
          chip on the chart's subhead returns to the Top 20 view. */}
      <CellTypeChart
        rows={rows}
        cellsByTissue={cellsByTissue}
        selectedUberonId={selectedUberonId}
        selectedTissueLabel={tissueLabel}
        onClearTissue={() => setSelectedUberonId(null)}
      />
    </div>
  );
}
