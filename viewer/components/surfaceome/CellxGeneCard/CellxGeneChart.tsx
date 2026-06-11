"use client";

import { useMemo, useState } from "react";
import type {
  CellTypeRow,
  TissueRow,
  TissueAggregateRow,
} from "../../../lib/cellxgene-enrichment";
import styles from "./CellxGeneCard.module.css";

interface Props {
  rows: CellTypeRow[];
  tissues?: TissueAggregateRow[];
}

type YMetric = "score" | "mean" | "pct";
type SortMode = "value" | "type" | "tissue";

const CELL_BAR_COLOR = "var(--maroon-mid, #922038)";
const TISSUE_BAR_COLOR = "var(--teal-mid, #3d6b60)";
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
function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/**
 * For a cell type, look up the row in its `tissues[]` array whose
 * uberon_id matches. Returns undefined if the cell type doesn't have
 * that tissue in its top-3 tissue subarray (the build truncates the
 * per-cell-type tissue list at 3). When the user filters by tissue,
 * we use this to surface the tissue-specific stats; rows whose
 * truncated tissue list misses the selection get filtered out.
 */
function tissueOf(r: CellTypeRow, uberonId: string): TissueRow | undefined {
  return (r.tissues ?? []).find((t) => t.uberon_id === uberonId);
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
        {truncate(label, 24)}
        {isTrace && (
          <span className={styles.traceBadge} aria-label="trace expression">
            trace
          </span>
        )}
      </span>
    </>
  );
  return (
    <li
      className={styles.colBar}
      data-trace={isTrace || undefined}
      data-selected={isSelected || undefined}
    >
      {onClick ? (
        <button
          type="button"
          className={styles.colBarHit}
          onClick={onClick}
          tabIndex={0}
          title={hoverTitle}
          aria-pressed={!!isSelected}
        >
          {hitContents}
        </button>
      ) : (
        <div
          className={styles.colBarHit}
          tabIndex={0}
          title={hoverTitle}
        >
          {hitContents}
        </div>
      )}
      <div className={styles.popover} role="tooltip">
        {popover}
      </div>
    </li>
  );
}

function cellPopover(r: CellTypeRow, value: number): React.ReactNode {
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
          style={{ background: CELL_BAR_COLOR }}
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

function tissuePopover(t: TissueAggregateRow): React.ReactNode {
  const meanVal = t.mean_log1p_cp10k ?? 0;
  const pctVal = t.pct_expressing ?? 0;
  return (
    <>
      <div className={styles.popHeader}>
        <span
          className={styles.swatch}
          style={{ background: TISSUE_BAR_COLOR }}
          aria-hidden
        />
        <strong>{t.tissue}</strong>
        <span className={styles.popMeta}>{t.uberon_id}</span>
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
            const barColor = isSelected
              ? SELECTED_TISSUE_COLOR
              : TISSUE_BAR_COLOR;
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
                popover={tissuePopover(r)}
                hoverTitle={hoverTitle}
                onClick={() => onSelect(r.uberon_id)}
              />
            );
          })}
        </ul>
      </div>
    </section>
  );
}

/**
 * Top-N cell types chart. Always sorted by the active metric DESC and
 * truncated at N (default 20). Trace cell types are INCLUDED (so
 * low-expression genes like GPR75 still get a real top-20 view) but
 * qualified cells rank first, then trace. Trace bars carry the muted
 * styling + badge so the reader sees the small-n caveat.
 */
function TopCellTypes({ rows, n = 20 }: { rows: CellTypeRow[]; n?: number }) {
  const [yMetric, setYMetric] = useState<YMetric>("score");

  const sorted = useMemo(() => {
    const m = (r: CellTypeRow): number => readMetric(r, yMetric);
    const traceTier = (r: CellTypeRow): number => (r.is_trace ? 1 : 0);
    return [...rows]
      .sort((a, b) => {
        const tt = traceTier(a) - traceTier(b);
        if (tt !== 0) return tt;
        return m(b) - m(a);
      })
      .slice(0, n);
  }, [rows, yMetric, n]);

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
        Top {n} cell types
        <span className={styles.subheadMeta}>
          highest expression overall · qualified first, trace
          (small-n) cells appended · ranked by the active metric
        </span>
      </h3>
      <ChartControls yMetric={yMetric} setYMetric={setYMetric} />
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
            return (
              <ColumnBar
                key={r.cl_id}
                height={height}
                color={CELL_BAR_COLOR}
                label={r.cell_type}
                isTrace={r.is_trace}
                popover={cellPopover(r, value)}
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
 * Full cell-type chart. When a tissue is selected (via the Top
 * tissues chart), filters cell types to those that include the
 * tissue in their top-3 tissue list and reads stats from that
 * tissue's row inside each cell type. Otherwise renders all cell
 * types with their pooled (across-tissue) stats.
 */
function CellTypeChart({
  rows,
  selectedUberonId,
  selectedTissueLabel,
  onClearTissue,
}: {
  rows: CellTypeRow[];
  selectedUberonId: string | null;
  selectedTissueLabel: string | null;
  onClearTissue: () => void;
}) {
  const [yMetric, setYMetric] = useState<YMetric>("score");
  const [sortMode, setSortMode] = useState<SortMode>("value");

  /**
   * Build a derived "view row" for each cell type. When a tissue is
   * selected, the view row's mean/pct come from the cell type's
   * tissue-specific stats (looked up in r.tissues[]); when no tissue
   * is selected, they come from the cell type's pooled-across-tissues
   * stats. is_trace is also recomputed from the active stats so the
   * filter-by-tissue view doesn't carry "trace" badges based on
   * cross-tissue n.
   */
  interface ViewRow {
    cl_id: string;
    cell_type: string;
    mean_log1p_cp10k: number;
    pct_expressing: number;
    n_expressing: number;
    n_total: number;
    is_trace: boolean;
    // keep the original for popover detail
    base: CellTypeRow;
  }

  const viewRows: ViewRow[] = useMemo(() => {
    return rows
      .map((r): ViewRow | null => {
        if (selectedUberonId) {
          const t = tissueOf(r, selectedUberonId);
          if (!t) return null;
          return {
            cl_id: r.cl_id,
            cell_type: r.cell_type,
            mean_log1p_cp10k: t.mean_log1p_cp10k,
            pct_expressing: t.pct_expressing,
            n_expressing: t.n_expressing,
            n_total: t.n_total,
            is_trace: t.n_expressing < 10 || t.pct_expressing < 0.01,
            base: r,
          };
        }
        return {
          cl_id: r.cl_id,
          cell_type: r.cell_type,
          mean_log1p_cp10k: r.mean_log1p_cp10k,
          pct_expressing: r.pct_expressing,
          n_expressing: r.n_expressing,
          n_total: r.n_total,
          is_trace: !!r.is_trace,
          base: r,
        };
      })
      .filter((r): r is ViewRow => r !== null);
  }, [rows, selectedUberonId]);

  const sorted = useMemo(() => {
    const arr = [...viewRows];
    const m = (r: ViewRow): number => readMetric(r, yMetric);
    const traceTier = (r: ViewRow): number => (r.is_trace ? 1 : 0);
    if (sortMode === "type") {
      arr.sort((a, b) => a.cell_type.localeCompare(b.cell_type));
    } else if (sortMode === "tissue") {
      // Sort by dominant tissue (from base row) then by metric DESC.
      arr.sort((a, b) => {
        const ta = a.base.tissues?.[0]?.tissue ?? "";
        const tb = b.base.tissues?.[0]?.tissue ?? "";
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
    return arr;
  }, [viewRows, sortMode, yMetric]);

  const scaleMax = useMemo(() => {
    const observed = sorted.reduce(
      (mx, r) => Math.max(mx, readMetric(r, yMetric)),
      0,
    );
    return Math.max(metricScaleFloor(yMetric), observed);
  }, [sorted, yMetric]);

  const title = selectedTissueLabel
    ? `Cell types in ${selectedTissueLabel}`
    : "All cell types";
  const subtitle = selectedTissueLabel
    ? `tissue-specific expression within ${selectedTissueLabel}`
    : "every cell type with detectable expression · qualified first, then trace";

  return (
    <section className={styles.chartBlock}>
      <h3 className={styles.subhead}>
        {title}
        <span className={styles.subheadMeta}>{subtitle}</span>
        {selectedTissueLabel && (
          <button
            type="button"
            className={styles.resetLink}
            onClick={onClearTissue}
          >
            Show all tissues
          </button>
        )}
      </h3>
      <ChartControls
        yMetric={yMetric}
        setYMetric={setYMetric}
        sortMode={sortMode}
        setSortMode={setSortMode}
        sortOptions={[
          { value: "value", label: "By value" },
          { value: "tissue", label: "By tissue" },
          { value: "type", label: "A → Z" },
        ]}
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
              return (
                <ColumnBar
                  key={r.cl_id}
                  height={height}
                  color={CELL_BAR_COLOR}
                  label={r.cell_type}
                  isTrace={r.is_trace}
                  popover={cellPopover(r.base, value)}
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

export function CellxGeneChart({ rows, tissues = [] }: Props) {
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
      <TopCellTypes rows={rows} />
      <CellTypeChart
        rows={rows}
        selectedUberonId={selectedUberonId}
        selectedTissueLabel={tissueLabel}
        onClearTissue={() => setSelectedUberonId(null)}
      />
    </div>
  );
}
