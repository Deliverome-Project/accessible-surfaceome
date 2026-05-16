"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type {
  BenchmarkMatrix,
  BenchmarkRow,
  BenchmarkSource,
  BenchmarkVariantResult,
} from "../../lib/surfaceome-types";
import { buildTsv, downloadTextFile, type TsvCell } from "../../lib/tsv";
import { RationaleDrawer, type SelectedCell } from "./RationaleDrawer";
import styles from "./BenchmarkTable.module.css";

const ROW_ESTIMATE_PX = 44;
const ROW_OVERSCAN = 12;

// Resting-grid template: toggle | gene | uniprot | truth | 5 DB dots |
// 3 model NCBI pills. The truth_class column was dropped — `truth_verdict`
// + the per-DB and per-model verdict pills carry the same signal, and
// the prose class label ("secreted negative" etc.) competed visually
// with the verdict pills without adding information.
const GRID_TEMPLATE =
  "12rem 5.5rem 4.5rem " +
  "4.2rem 3rem 4rem 3.6rem 3rem " +
  "6rem 6.5rem 5.6rem";

const DB_KEYS: { key: BenchmarkSource; short: string; long: string }[] = [
  { key: "uniprot", short: "U", long: "UniProt" },
  { key: "go", short: "G", long: "GO" },
  { key: "surfy", short: "S", long: "SURFY" },
  { key: "cspa", short: "C", long: "CSPA" },
  { key: "hpa", short: "H", long: "HPA" },
];

const MODEL_LABELS: { id: string; short: string; long: string }[] = [
  { id: "claude-haiku-4-5",  short: "H", long: "Haiku 4.5" },
  { id: "claude-sonnet-4-6", short: "S", long: "Sonnet 4.6" },
  { id: "claude-opus-4-7",   short: "O", long: "Opus 4.7" },
];

// Display order for the expanded model × variant grid.
const VARIANT_LABELS: { id: string; short: string; long: string }[] = [
  { id: "naive",       short: "naive",       long: "no context"                  },
  { id: "ncbi",        short: "ncbi",        long: "HGNC + UniProt + NCBI summary" },
  { id: "web_ncbi",    short: "web_ncbi",    long: "ncbi + web search"           },
  { id: "pubmed_ncbi", short: "pubmed_ncbi", long: "ncbi + PubMed evidence"      },
];

type TruthFilter = "all" | "yes" | "contextual" | "no" | "disagreements";

function verdictTone(v: string | null | undefined): string {
  if (v === "yes") return styles.verdictYes;
  if (v === "no") return styles.verdictNo;
  if (v === "contextual") return styles.verdictContextual;
  return styles.verdictUnknown;
}

function isCorrect(verdict: string | null, truth: string): boolean {
  if (!verdict) return false;
  if (verdict === truth) return true;
  if (
    (verdict === "yes" || verdict === "contextual") &&
    (truth === "yes" || truth === "contextual")
  ) {
    return true;
  }
  return false;
}

function rowHasAnyDisagreement(r: BenchmarkRow, models: string[]): boolean {
  const verdicts = r.verdicts ?? {};
  for (const m of models) {
    const byVariant = verdicts[m];
    if (!byVariant) continue;
    for (const v of VARIANT_LABELS) {
      const cell = byVariant[v.id];
      if (cell?.verdict && !isCorrect(cell.verdict, r.truth_verdict)) return true;
    }
  }
  return false;
}

interface BenchmarkTableProps {
  matrix: BenchmarkMatrix;
  deepDiveGenes: Set<string>;
  geneNames?: Record<string, string>;
}

export function BenchmarkTable({
  matrix,
  deepDiveGenes,
  geneNames,
}: BenchmarkTableProps) {
  const { rows, models } = matrix;
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<TruthFilter>("all");
  // Row-level expand: shows the full model × variant grid for that gene.
  const [rowExpanded, setRowExpanded] = useState<Set<string>>(new Set());
  // Cell selection: which (gene, model, variant) the right-side
  // rationale drawer is showing. One cell at a time — drawer content
  // swaps as the reader clicks through cells; clicking the same cell
  // twice closes the drawer.
  const [selectedCell, setSelectedCell] = useState<SelectedCell | null>(null);

  function toggleRow(symbol: string) {
    setRowExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  }

  function handleSelectCell(symbol: string, model: string, variant: string) {
    setSelectedCell((prev) =>
      prev && prev.symbol === symbol && prev.model === model && prev.variant === variant
        ? null
        : { symbol, model, variant },
    );
    // Auto-expand the parent row so the selected cell stays visible
    // when the reader closes the drawer or clicks a different cell.
    setRowExpanded((prev) => {
      if (prev.has(symbol)) return prev;
      const next = new Set(prev);
      next.add(symbol);
      return next;
    });
  }

  // ESC closes the drawer. Installed on the table, not the drawer, so
  // we don't depend on drawer focus (the drawer is non-modal).
  useEffect(() => {
    if (!selectedCell) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedCell(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedCell]);

  function handleDownload() {
    const tsv = buildBenchmarkTsv(matrix);
    downloadTextFile("surfacebench.tsv", tsv);
  }

  const counts = useMemo(() => {
    let yes = 0, contextual = 0, no = 0, disagreements = 0;
    for (const r of rows) {
      if (r.truth_verdict === "yes") yes++;
      else if (r.truth_verdict === "contextual") contextual++;
      else if (r.truth_verdict === "no") no++;
      if (rowHasAnyDisagreement(r, models)) disagreements++;
    }
    return { yes, contextual, no, disagreements };
  }, [rows, models]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (q) {
        const hay =
          `${r.gene_symbol} ${r.uniprot_acc} ${r.class} ${r.truth_reason}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (filter === "yes" && r.truth_verdict !== "yes") return false;
      if (filter === "contextual" && r.truth_verdict !== "contextual") return false;
      if (filter === "no" && r.truth_verdict !== "no") return false;
      if (filter === "disagreements" && !rowHasAnyDisagreement(r, models)) {
        return false;
      }
      return true;
    });
  }, [rows, query, filter, models]);

  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_ESTIMATE_PX,
    overscan: ROW_OVERSCAN,
  });
  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();

  const gridStyle: React.CSSProperties = {
    ["--bench-cols" as string]: GRID_TEMPLATE,
  };

  return (
    <div className={styles.wrap} style={gridStyle}>
      <p className={styles.meta}>
        <span>Models: {MODEL_LABELS.map((m) => m.long).join(" · ")}</span>
        <span className={styles.metaDot}>·</span>
        <span>
          Click a gene to compare all 4 prompt variants; click a verdict
          cell to read the agent&apos;s reasoning.
        </span>
      </p>

      <div className={styles.toolbar}>
        <div className={styles.search}>
          <label htmlFor="bench-search" className="sr-only">
            Filter by gene, UniProt, class, or reason
          </label>
          <input
            id="bench-search"
            className={styles.searchInput}
            placeholder="gene · UniProt · class · reason…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            type="search"
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <div className={styles.chipsActions}>
          <div className={styles.chips} role="tablist" aria-label="Truth filters">
            <FilterChip on={filter === "all"} onClick={() => setFilter("all")}>
              All <span className={styles.chipCount}>{rows.length}</span>
            </FilterChip>
            <FilterChip on={filter === "yes"} onClick={() => setFilter("yes")}>
              Yes <span className={styles.chipCount}>{counts.yes}</span>
            </FilterChip>
            <FilterChip
              on={filter === "contextual"}
              onClick={() => setFilter("contextual")}
            >
              Contextual <span className={styles.chipCount}>{counts.contextual}</span>
            </FilterChip>
            <FilterChip on={filter === "no"} onClick={() => setFilter("no")}>
              No <span className={styles.chipCount}>{counts.no}</span>
            </FilterChip>
            <FilterChip
              on={filter === "disagreements"}
              onClick={() => setFilter("disagreements")}
            >
              Disagreements{" "}
              <span className={styles.chipCount}>{counts.disagreements}</span>
            </FilterChip>
          </div>
          <button
            type="button"
            className={styles.downloadBtn}
            onClick={handleDownload}
            title={`Download all ${rows.length} rows as TSV — every (model, variant) cell flattened to its own columns`}
          >
            TSV ↓
          </button>
        </div>
      </div>

      <div className={styles.resultRow}>
        <p className={styles.resultMeta}>
          {filtered.length === rows.length
            ? `${filtered.length} genes`
            : `${filtered.length} of ${rows.length} genes`}
          <span className={styles.metaDot} aria-hidden="true">·</span>
          <span>
            TSV ships verdicts + reason codes + telemetry. Free-text
            reasoning per cell is on{" "}
            <Link href="/api/#benchmark-matrix" className={styles.apiHintLink}>
              <code>GET /v1/benchmark/matrix</code>
            </Link>
            .
          </span>
        </p>
      </div>

      <div
        className={styles.tableScroll}
        ref={scrollRef}
        role="table"
        aria-rowcount={filtered.length + 1}
      >
        <div className={`${styles.headerRow} ${styles.row}`} role="row">
          <div className={styles.headerCell} role="columnheader">Gene</div>
          <div className={`${styles.headerCell} ${styles.headerMono}`} role="columnheader">
            UniProt
          </div>
          <div className={styles.headerCell} role="columnheader">Truth</div>
          {DB_KEYS.map((d) => (
            <div
              key={`hdr-db-${d.key}`}
              className={`${styles.headerCell} ${styles.headerDbCell}`}
              title={d.long}
              role="columnheader"
            >
              {d.long}
            </div>
          ))}
          {MODEL_LABELS.map((m) => (
            <div
              key={`hdr-mdl-${m.id}`}
              className={`${styles.headerCell} ${styles.headerModelCell}`}
              title={`${m.long} · ncbi variant`}
              role="columnheader"
            >
              {m.long}
            </div>
          ))}
        </div>

        <div
          className={styles.body}
          style={
            mounted && filtered.length > 0
              ? { height: totalSize, position: "relative" }
              : undefined
          }
          role="rowgroup"
        >
          {!mounted ? (
            <div className={styles.loadingRow} role="row" aria-hidden="true">
              Loading {filtered.length} rows…
            </div>
          ) : null}
          {mounted && filtered.length > 0
            ? virtualItems.map((item) => {
                const r = filtered[item.index];
                return (
                  <BenchRowView
                    key={r.gene_symbol}
                    row={r}
                    measureRef={virtualizer.measureElement}
                    dataIndex={item.index}
                    virtualStart={item.start}
                    isExpanded={rowExpanded.has(r.gene_symbol)}
                    onToggleRow={toggleRow}
                    selectedCell={selectedCell}
                    onSelectCell={handleSelectCell}
                    hasDeepDive={deepDiveGenes.has(r.gene_symbol)}
                    geneName={geneNames?.[r.gene_symbol]}
                  />
                );
              })
            : null}
          {mounted && filtered.length === 0 ? (
            <div className={styles.empty} role="row">
              No rows match these filters.
            </div>
          ) : null}
        </div>
      </div>

      <RationaleDrawer
        selected={selectedCell}
        matrix={matrix}
        modelLabels={MODEL_LABELS}
        variantLabels={VARIANT_LABELS}
        deepDiveGenes={deepDiveGenes}
        geneNames={geneNames}
        onClose={() => setSelectedCell(null)}
      />
    </div>
  );
}

function FilterChip({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className={`${styles.chip} ${on ? styles.chipOn : ""}`}
      onClick={onClick}
      aria-pressed={on}
    >
      {children}
    </button>
  );
}

function BenchRowView({
  row,
  measureRef,
  dataIndex,
  virtualStart,
  isExpanded,
  onToggleRow,
  selectedCell,
  onSelectCell,
  hasDeepDive,
  geneName,
}: {
  row: BenchmarkRow;
  measureRef?: (el: HTMLDivElement | null) => void;
  dataIndex?: number;
  virtualStart?: number;
  isExpanded: boolean;
  onToggleRow: (symbol: string) => void;
  selectedCell: SelectedCell | null;
  onSelectCell: (symbol: string, model: string, variant: string) => void;
  hasDeepDive: boolean;
  geneName?: string;
}) {
  const style: React.CSSProperties | undefined =
    virtualStart != null
      ? {
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          transform: `translateY(${virtualStart}px)`,
        }
      : undefined;
  const geneCell = (
    <button
      type="button"
      className={styles.symbolButton}
      onClick={() => onToggleRow(row.gene_symbol)}
      aria-expanded={isExpanded}
      aria-label={
        isExpanded
          ? `Collapse ${row.gene_symbol}`
          : `Expand ${row.gene_symbol}`
      }
    >
      <span className={styles.symbolChevron} aria-hidden="true">
        {isExpanded ? "▾" : "▸"}
      </span>
      <span className={styles.symbolStack}>
        <span className={styles.symbolText}>{row.gene_symbol}</span>
        {geneName ? (
          <span className={styles.symbolName} title={geneName}>
            {geneName}
          </span>
        ) : null}
      </span>
    </button>
  );
  return (
    <div
      ref={measureRef}
      data-index={dataIndex}
      role="row"
      className={`${styles.row} ${isExpanded ? styles.rowExpanded : ""}`}
      style={style}
    >
      <div className={`${styles.cell} ${styles.geneCell}`} role="cell">
        {geneCell}
      </div>
      <div className={`${styles.cell} ${styles.uniprotCell}`} role="cell">
        {row.uniprot_acc}
      </div>
      <div className={`${styles.cell} ${styles.truthCell}`} role="cell">
        <span
          className={`${styles.verdictLabel} ${verdictTone(row.truth_verdict)}`}
          title={row.truth_reason.replace(/_/g, " ")}
        >
          {row.truth_verdict}
        </span>
      </div>
      {DB_KEYS.map((d) => {
        const yes = row.db ? Boolean(row.db[d.key]) : false;
        return (
          <div
            key={d.key}
            className={`${styles.cell} ${styles.dbCell} ${yes ? styles.dbCellYes : ""}`}
            role="cell"
            aria-label={`${d.long}: ${yes ? "yes" : "no"}`}
          >
            <span className={styles.dbDot} aria-hidden="true" />
          </div>
        );
      })}
      {MODEL_LABELS.map((m) => {
        // Headline column: NCBI verdict for this model.
        const cell: BenchmarkVariantResult | null | undefined =
          row.verdicts?.[m.id]?.ncbi;
        return (
          <div
            key={`${m.id}-ncbi`}
            className={`${styles.cell} ${styles.modelCell}`}
            role="cell"
          >
            {cell?.verdict ? (
              <span
                className={`${styles.verdictLabel} ${styles.verdictMini} ${verdictTone(cell.verdict)} ${
                  isCorrect(cell.verdict, row.truth_verdict)
                    ? styles.verdictCorrect
                    : styles.verdictWrong
                }`}
                title={
                  cell.reason
                    ? `${m.long} · ncbi → ${cell.verdict} (${cell.reason.replace(/_/g, " ")})`
                    : `${m.long} · ncbi → ${cell.verdict}`
                }
              >
                {cell.verdict}
              </span>
            ) : (
              <span className={styles.dim} title={`${m.long} · ncbi: no run on file`}>
                —
              </span>
            )}
          </div>
        );
      })}
      {isExpanded ? (
        <div className={styles.expandedBlock}>
          {hasDeepDive ? (
            <p className={styles.expandedActions}>
              <Link href={`/${row.gene_symbol}/`} className={styles.deepDiveLink}>
                ↗ Open the {row.gene_symbol} deep-dive page
              </Link>
            </p>
          ) : null}
          <VariantGrid
            row={row}
            selectedCell={selectedCell}
            onSelectCell={onSelectCell}
          />
        </div>
      ) : null}
    </div>
  );
}

/** Expanded model × variant grid. Clicking any verdict cell opens
 *  the side-rationale drawer with that cell's reasoning. */
function VariantGrid({
  row,
  selectedCell,
  onSelectCell,
}: {
  row: BenchmarkRow;
  selectedCell: SelectedCell | null;
  onSelectCell: (symbol: string, model: string, variant: string) => void;
}) {
  return (
    <div className={styles.variantGrid}>
      <div className={styles.variantHeader} />
      {VARIANT_LABELS.map((v) => (
        <div
          key={`vh-${v.id}`}
          className={styles.variantHeader}
          title={v.long}
        >
          {v.long}
        </div>
      ))}
      {MODEL_LABELS.map((m) => (
        <ModelVariantRow
          key={`vrow-${m.id}`}
          row={row}
          model={m}
          selectedCell={selectedCell}
          onSelectCell={onSelectCell}
        />
      ))}
    </div>
  );
}

function ModelVariantRow({
  row,
  model,
  selectedCell,
  onSelectCell,
}: {
  row: BenchmarkRow;
  model: { id: string; short: string; long: string };
  selectedCell: SelectedCell | null;
  onSelectCell: (symbol: string, model: string, variant: string) => void;
}) {
  return (
    <>
      <div className={styles.variantRowLabel}>{model.long}</div>
      {VARIANT_LABELS.map((v) => {
        const cell: BenchmarkVariantResult | null | undefined =
          row.verdicts?.[model.id]?.[v.id];
        const isSelected =
          selectedCell != null &&
          selectedCell.symbol === row.gene_symbol &&
          selectedCell.model === model.id &&
          selectedCell.variant === v.id;
        return (
          <div
            key={`vcell-${model.id}-${v.id}`}
            className={styles.variantCellWrap}
          >
            {cell?.verdict ? (
              <button
                type="button"
                className={`${styles.variantCellBtn} ${
                  isSelected ? styles.variantCellSelected : ""
                } ${verdictTone(cell.verdict)} ${
                  isCorrect(cell.verdict, row.truth_verdict)
                    ? styles.verdictCorrect
                    : styles.verdictWrong
                }`}
                onClick={() => onSelectCell(row.gene_symbol, model.id, v.id)}
                aria-pressed={isSelected}
                title={`${model.long} · ${v.long} → ${cell.verdict}${
                  cell.reason ? ` (${cell.reason.replace(/_/g, " ")})` : ""
                } — click for full reasoning`}
              >
                <span className={`${styles.verdictLabel} ${verdictTone(cell.verdict)}`}>
                  {cell.verdict}
                </span>
              </button>
            ) : (
              <span className={styles.variantCellMissing}>—</span>
            )}
          </div>
        );
      })}
    </>
  );
}

/** Wide TSV download — one row per gene, columns for every cell
 *  (model × variant) in the matrix. */
function buildBenchmarkTsv(matrix: BenchmarkMatrix): string {
  const headers: string[] = [
    "gene_symbol",
    "uniprot_acc",
    "class",
    "truth_verdict",
    "truth_signal",
    "truth_reason",
    "n_db_surface",
  ];
  for (const src of matrix.sources) headers.push(`db_${src}`);
  for (const model of matrix.models) {
    const slug = modelSlug(model);
    for (const variant of matrix.variants) {
      headers.push(
        `${slug}_${variant}_verdict`,
        `${slug}_${variant}_reason`,
        `${slug}_${variant}_correct`,
        `${slug}_${variant}_confidence`,
        `${slug}_${variant}_latency_s`,
        `${slug}_${variant}_cost_usd`,
      );
    }
  }

  const body: TsvCell[][] = matrix.rows.map((r) => {
    const row: TsvCell[] = [
      r.gene_symbol,
      r.uniprot_acc,
      r.class,
      r.truth_verdict,
      r.truth_signal,
      r.truth_reason,
      r.n_db_surface,
    ];
    for (const src of matrix.sources) {
      row.push(r.db ? r.db[src] : "");
    }
    for (const model of matrix.models) {
      const byVariant = r.verdicts?.[model] ?? {};
      for (const variant of matrix.variants) {
        const c: BenchmarkVariantResult | null | undefined = byVariant[variant];
        row.push(
          c?.verdict ?? "",
          c?.reason ?? "",
          c?.correct ?? "",
          c?.confidence ?? "",
          c?.latency_s ?? "",
          c?.cost_usd ?? "",
        );
      }
    }
    return row;
  });
  return buildTsv(headers, body);
}

function modelSlug(modelId: string): string {
  const m = modelId.match(/(opus|sonnet|haiku)/i);
  return m ? m[1].toLowerCase() : modelId.replace(/[^a-z0-9]+/gi, "_");
}
