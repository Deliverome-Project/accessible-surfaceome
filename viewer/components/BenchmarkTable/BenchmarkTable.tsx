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
import { prettyEnum } from "../../lib/enums";
import { isQueuedDeepDive } from "../../lib/queued-deep-dives";
import { RationaleDrawer, type SelectedCell } from "./RationaleDrawer";
import styles from "./BenchmarkTable.module.css";

// Sortable column key. Matches the keys we surface in the header row;
// numeric sorts (per-DB / per-model) use n_db_surface and a verdict-rank
// derived from the row. UniProt sort dropped with the column.
type SortKey =
  | "gene_symbol"
  | "truth"
  | "reason"
  | "n_db_surface"
  | "haiku_ncbi"
  | "sonnet_ncbi"
  | "opus_ncbi";

type SortDir = "asc" | "desc";

// Maps verdict strings to a numeric rank for stable sorting. Order is
// yes (3) > contextual (2) > no (1) > unknown / null (0), so DESC puts
// the "yes" rows on top — matches the figure-style narrative.
const VERDICT_RANK: Record<string, number> = {
  yes: 3,
  contextual: 2,
  no: 1,
};
function verdictRank(v: string | null | undefined): number {
  return v ? (VERDICT_RANK[v] ?? 0) : 0;
}

const ROW_ESTIMATE_PX = 44;
const ROW_OVERSCAN = 12;

// Resting-grid template: symbol | truth | # DBs (nBubble) | 5 DB dots |
// 3 model NCBI pills. Mirrors the CatalogTable layout exactly — the
// nBubble count column sits before the per-DB dots, same widths +
// styling as the homepage. .wrap max-width = grid sum + scrollbar.
const GRID_TEMPLATE =
  "12rem 8rem " +
  "12rem " +                          // ground-truth reason (prettyEnum label)
  "3.6rem " +                         // n_db_surface count bubble
  "4.2rem 3rem 4rem 3.6rem 3rem " +   // 5 DB dot columns
  "7.8rem 8.5rem 7.2rem";              // 3 model NCBI pills

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
  { id: "claude-opus-4-8",   short: "O", long: "Opus 4.8" },
];

// Display order for the expanded model × variant grid.
const VARIANT_LABELS: { id: string; short: string; long: string }[] = [
  { id: "naive",       short: "naive",       long: "no context"                  },
  { id: "ncbi",        short: "NCBI",        long: "HGNC + UniProt + NCBI summary" },
  { id: "web_ncbi",    short: "web + NCBI",  long: "NCBI + web search"           },
  { id: "pubmed_ncbi", short: "PubMed + NCBI", long: "NCBI + PubMed evidence"    },
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
  // Row-level expand: a single gene's full model × variant grid is
  // open at a time. Clicking another gene's chevron / verdict cell
  // collapses the previous expansion — keeps the table scannable
  // when the reader is moving through many rows.
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  // Cell selection: which (gene, model, variant) the right-side
  // rationale drawer is showing. One cell at a time — drawer content
  // swaps as the reader clicks through cells; clicking the same cell
  // twice closes the drawer.
  const [selectedCell, setSelectedCell] = useState<SelectedCell | null>(null);
  // Sort state — defaults to gene_symbol ASC so the resting view
  // matches the figure-style alphabetical scan.
  const [sortKey, setSortKey] = useState<SortKey>("gene_symbol");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  function toggleSort(key: SortKey) {
    setSortKey((prev) => {
      if (prev === key) {
        // Same column → flip direction.
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return prev;
      }
      // New column → reset to a sensible default (text ASC, numeric DESC).
      const isNumeric =
        key === "n_db_surface" ||
        key === "haiku_ncbi" ||
        key === "sonnet_ncbi" ||
        key === "opus_ncbi" ||
        key === "truth";
      setSortDir(isNumeric ? "desc" : "asc");
      return key;
    });
  }

  function toggleRow(symbol: string) {
    setExpandedRow((prev) => (prev === symbol ? null : symbol));
  }

  function handleSelectCell(symbol: string, model: string, variant: string) {
    setSelectedCell((prev) =>
      prev && prev.symbol === symbol && prev.model === model && prev.variant === variant
        ? null
        : { symbol, model, variant },
    );
    // Auto-expand the parent row so the selected cell stays visible
    // when the reader closes the drawer or clicks a different cell.
    // Single-row only — collapses whatever else was open.
    setExpandedRow(symbol);
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
    // Download the current filtered + sorted view (matches the
    // CatalogTable pattern — what you see is what gets saved). Clear
    // the search / chips to download the whole 147 rows.
    const tsv = buildBenchmarkTsv(matrix, filtered);
    const isFiltered = filtered.length !== rows.length;
    const suffix = isFiltered ? `-filtered-${filtered.length}` : "";
    downloadTextFile(`surfacebench${suffix}.tsv`, tsv);
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
    const passing = rows.filter((r) => {
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
    // Apply sort on a copy so the source `rows` order is preserved
    // (matters when the user clears the sort by switching to a column
    // and then back, expecting alphabetical default).
    const dir = sortDir === "asc" ? 1 : -1;
    const sorted = [...passing].sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      if (typeof av === "string" && typeof bv === "string") {
        return av.localeCompare(bv) * dir;
      }
      return ((av as number) - (bv as number)) * dir;
    });
    return sorted;
  }, [rows, query, filter, models, sortKey, sortDir]);

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
              title="Rows where at least one LLM (any model × any prompt variant) disagrees with the curated truth verdict. Not LLM-vs-LLM — strictly LLM-vs-truth."
            >
              LLM ≠ truth{" "}
              <span className={styles.chipCount}>{counts.disagreements}</span>
            </FilterChip>
          </div>
          <button
            type="button"
            className={styles.downloadBtn}
            onClick={handleDownload}
            title={
              filtered.length === rows.length
                ? `Download all ${rows.length} bench rows as TSV — every (model, variant) cell flattened to its own columns`
                : `Download ${filtered.length} filtered rows as TSV (of ${rows.length} total)`
            }
          >
            TSV ↓{" "}
            <span className={styles.downloadCount}>
              {filtered.length === rows.length
                ? rows.length
                : `${filtered.length}/${rows.length}`}
            </span>
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
          <SortHeader
            label="Symbol"
            sortKey="gene_symbol"
            activeKey={sortKey}
            dir={sortDir}
            onClick={toggleSort}
          />
          <SortHeader
            label="Truth"
            sortKey="truth"
            activeKey={sortKey}
            dir={sortDir}
            onClick={toggleSort}
            extraClass={styles.headerModelCell}
          />
          <SortHeader
            label="Reason"
            sortKey="reason"
            activeKey={sortKey}
            dir={sortDir}
            onClick={toggleSort}
            title="Curated ground-truth reason — the single TriageReason code (same closed vocabulary the triage agent must choose from) behind the truth verdict."
          />
          <SortHeader
            label="DB votes"
            sortKey="n_db_surface"
            activeKey={sortKey}
            dir={sortDir}
            onClick={toggleSort}
            extraClass={styles.headerDbCell}
            title="Count of the 5 gating DBs that voted yes for this gene. Same column label as the homepage CatalogTable. Click to sort rows by DB consensus."
          />
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
          <SortHeader
            label={MODEL_LABELS[0].long}
            sortKey="haiku_ncbi"
            activeKey={sortKey}
            dir={sortDir}
            onClick={toggleSort}
            extraClass={styles.headerModelCell}
            title={`${MODEL_LABELS[0].long} · NCBI variant`}
          />
          <SortHeader
            label={MODEL_LABELS[1].long}
            sortKey="sonnet_ncbi"
            activeKey={sortKey}
            dir={sortDir}
            onClick={toggleSort}
            extraClass={styles.headerModelCell}
            title={`${MODEL_LABELS[1].long} · NCBI variant`}
          />
          <SortHeader
            label={MODEL_LABELS[2].long}
            sortKey="opus_ncbi"
            activeKey={sortKey}
            dir={sortDir}
            onClick={toggleSort}
            extraClass={styles.headerModelCell}
            title={`${MODEL_LABELS[2].long} · NCBI variant`}
          />
        </div>

        <div
          className={styles.body}
          style={
            mounted && filtered.length > 0
              ? {
                  // `minHeight` (not `height`) so when a single-gene
                  // search match has content taller than the
                  // estimateSize (e.g. a 2-line gene name +
                  // synonyms), the row doesn't get clipped. The
                  // virtualizer's measureElement still drives the
                  // accurate per-row positioning above this.
                  minHeight: totalSize,
                  position: "relative",
                }
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
                    isExpanded={expandedRow === r.gene_symbol}
                    onToggleRow={toggleRow}
                    selectedCell={selectedCell}
                    onSelectCell={handleSelectCell}
                    hasDeepDive={deepDiveGenes.has(r.gene_symbol)}
                    isQueuedDeepDive={isQueuedDeepDive(
                      r.gene_symbol,
                      deepDiveGenes.has(r.gene_symbol),
                    )}
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

      {/* Backdrop overlay — click anywhere off the drawer to close.
       *  ESC also works (handler installed above). Stays under the
       *  drawer's z-index so the drawer itself stays interactive. */}
      <div
        className={`${styles.backdrop} ${selectedCell ? styles.backdropOpen : ""}`}
        aria-hidden="true"
        onClick={() => setSelectedCell(null)}
      />

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

/** Click-to-sort column header. Renders an inline `thBtn` (label + arrow
 *  slot) inside a header cell — same shape as CatalogTable so the two
 *  tables share a sort grammar. The arrow slot is always reserved (a
 *  thin space when inactive) to avoid layout shift on toggle. */
function SortHeader({
  label,
  sortKey,
  activeKey,
  dir,
  onClick,
  extraClass,
  title,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  dir: SortDir;
  onClick: (k: SortKey) => void;
  extraClass?: string;
  title?: string;
}) {
  const active = sortKey === activeKey;
  return (
    <div
      role="columnheader"
      aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}
      className={`${styles.headerCell} ${extraClass ?? ""}`}
    >
      <button
        type="button"
        onClick={() => onClick(sortKey)}
        className={`${styles.thBtn} ${active ? styles.thBtnActive : ""}`}
        title={title ?? `Sort by ${label}`}
      >
        <span>{label}</span>
        <span className={styles.sortIndicator} aria-hidden="true">
          {active ? (dir === "asc" ? "▲" : "▼") : " "}
        </span>
      </button>
    </div>
  );
}

/** Map a benchmark row + sort key onto a primitive that the sort
 *  function can compare. Strings get .localeCompare; numbers go
 *  straight to subtraction. */
function sortValue(r: BenchmarkRow, key: SortKey): string | number {
  switch (key) {
    case "gene_symbol":
      return r.gene_symbol.toUpperCase();
    case "truth":
      return verdictRank(r.truth_verdict);
    case "reason":
      return prettyEnum(r.truth_reason).toUpperCase();
    case "n_db_surface":
      return r.n_db_surface ?? 0;
    case "haiku_ncbi":
      return verdictRank(r.verdicts?.["claude-haiku-4-5"]?.ncbi?.verdict);
    case "sonnet_ncbi":
      return verdictRank(r.verdicts?.["claude-sonnet-4-6"]?.ncbi?.verdict);
    case "opus_ncbi":
      return verdictRank(r.verdicts?.["claude-opus-4-8"]?.ncbi?.verdict);
  }
}

function FilterChip({
  on,
  onClick,
  children,
  title,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <button
      type="button"
      className={`${styles.chip} ${on ? styles.chipOn : ""}`}
      onClick={onClick}
      aria-pressed={on}
      title={title}
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
  isQueuedDeepDive,
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
  isQueuedDeepDive: boolean;
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
      className={`${styles.row} ${isExpanded ? styles.rowExpanded : ""} ${
        isQueuedDeepDive ? styles.rowQueuedDeepDive : ""
      }`}
      style={style}
    >
      <div className={`${styles.cell} ${styles.geneCell}`} role="cell">
        {geneCell}
        {isQueuedDeepDive ? (
          <span
            className={styles.queuedDeepDivePill}
            title="Queued for deep-dive run — agent hasn't been executed yet. See viewer/lib/queued-deep-dives.ts."
          >
            queued
          </span>
        ) : null}
      </div>
      <div className={`${styles.cell} ${styles.truthCell}`} role="cell">
        <span
          className={`${styles.verdictLabel} ${verdictTone(row.truth_verdict)}`}
          title={prettyEnum(row.truth_reason)}
        >
          {row.truth_verdict}
        </span>
      </div>
      {/* Ground-truth reason — the curator's single TriageReason code
       *  (closed vocabulary, same one the triage agent must pick from)
       *  behind the truth verdict. Truncates with an ellipsis; full
       *  label on hover. */}
      <div className={`${styles.cell} ${styles.reasonCell}`} role="cell">
        <span className={styles.reasonText} title={prettyEnum(row.truth_reason)}>
          {prettyEnum(row.truth_reason)}
        </span>
      </div>
      {/* DB consensus count — same nBubble pattern as CatalogTable;
       *  color-coded by data-n so high-consensus genes pop visually. */}
      <div className={`${styles.cell} ${styles.nCell}`} role="cell">
        <span className={styles.nBubble} data-n={row.n_db_surface ?? 0}>
          {row.n_db_surface ?? 0}
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
        // Headline column: NCBI verdict for this model. Clickable —
        // opens the rationale drawer for this (gene, model, ncbi)
        // cell. Same drawer the expanded-row variant grid opens, so
        // a reader doesn't have to expand the row to read the
        // reasoning for the headline NCBI verdict.
        const cell: BenchmarkVariantResult | null | undefined =
          row.verdicts?.[m.id]?.ncbi;
        const isSelected =
          selectedCell != null &&
          selectedCell.symbol === row.gene_symbol &&
          selectedCell.model === m.id &&
          selectedCell.variant === "ncbi";
        return (
          <div
            key={`${m.id}-ncbi`}
            className={`${styles.cell} ${styles.modelCell}`}
            role="cell"
          >
            {cell?.verdict ? (
              <button
                type="button"
                onClick={() => onSelectCell(row.gene_symbol, m.id, "ncbi")}
                aria-pressed={isSelected}
                className={`${styles.modelVerdictBtn} ${
                  isSelected ? styles.modelVerdictBtnSelected : ""
                }`}
                title={
                  cell.reason
                    ? `${m.long} · NCBI → ${cell.verdict} (${cell.reason.replace(/_/g, " ")}) — click for full reasoning`
                    : `${m.long} · NCBI → ${cell.verdict} — click for full reasoning`
                }
              >
                <span
                  className={`${styles.verdictLabel} ${styles.verdictMini} ${verdictTone(cell.verdict)} ${
                    isCorrect(cell.verdict, row.truth_verdict)
                      ? styles.verdictCorrect
                      : styles.verdictWrong
                  }`}
                >
                  {cell.verdict}
                </span>
              </button>
            ) : (
              <span className={styles.dim} title={`${m.long} · NCBI: no run on file`}>
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
function buildBenchmarkTsv(matrix: BenchmarkMatrix, rows?: BenchmarkRow[]): string {
  // Optional `rows` arg lets the caller download a filtered + sorted
  // subset (what they see in the table) instead of the full matrix.
  // The header set + column order is always the same so a script
  // pinning to this TSV's shape doesn't break.
  const sourceRows = rows ?? matrix.rows;
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

  const body: TsvCell[][] = sourceRows.map((r) => {
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
