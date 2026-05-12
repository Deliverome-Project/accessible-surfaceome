"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { CatalogRow } from "../../lib/surfaceome";
import styles from "./CatalogTable.module.css";

// Per-row height estimate fed to @tanstack/react-virtual. Rows with
// a triage verdict are taller (two lines — verdict pill above, reason
// underneath) so we keep the estimate slightly above the no-triage
// height. The virtualizer dynamically re-measures as rows enter the
// viewport, so this only needs to be in the right ballpark for the
// initial scroll-height calc and overscan window.
const ROW_ESTIMATE_PX = 48;
const ROW_OVERSCAN = 12;

// CSS Grid template shared by the header row and every virtualized
// body row. Defining it once here (and once in CSS via the
// ``--catalog-cols`` custom property) is the bulletproof fix for the
// "thead and tbody column widths drift" problem that plagues
// virtualized HTML <table> rows. Both the header and each row are
// `display: grid; grid-template-columns: var(--catalog-cols)`, so the
// columns are GUARANTEED to line up — no proportional-fill rounding,
// no per-row `<table>` re-layout. The triage column uses `minmax(14rem,1fr)`
// so it absorbs any leftover horizontal space rather than leaving a
// trailing empty gutter on wide viewports.
const GRID_TEMPLATE =
  "7.5rem 5.5rem 3rem 1.6rem 1.6rem 1.6rem 1.6rem 1.6rem minmax(14rem, 1fr) 4.5rem";

// Five gating DBs. DeepTMHMM + COMPARTMENTS were demoted from the
// M1 universe gate upstream (kept in the D1 row for fidelity but
// hidden in the public catalog).
const DB_KEYS: { key: keyof CatalogRow["db"]; short: string; long: string }[] = [
  { key: "uniprot", short: "U", long: "UniProt" },
  { key: "go", short: "G", long: "GO" },
  { key: "surfy", short: "S", long: "SURFY" },
  { key: "cspa", short: "C", long: "CSPA" },
  { key: "hpa", short: "H", long: "HPA" },
];

type SortKey = "symbol" | "uniprot" | "n_sources" | "triage" | "deep_dive";
type SortDir = "asc" | "desc";
type QuickFilter = "all" | "deep_dive" | "triage" | "n7";

function verdictTone(v: string | null | undefined): string {
  if (v === "yes") return styles.verdictYes;
  if (v === "no") return styles.verdictNo;
  if (v === "contextual") return styles.verdictContextual;
  return styles.verdictUnknown;
}

interface CatalogTableProps {
  rows: CatalogRow[];
  /** When sourcing from the snapshot, the timestamp at which it was
   *  built. The API path omits it; the toolbar drops the timestamp
   *  chip when undefined. */
  generated_at?: string;
  n_rows: number;
  n_with_triage: number;
  n_with_deep_dive: number;
}

export function CatalogTable({
  rows,
  generated_at,
  n_rows,
  n_with_triage,
  n_with_deep_dive,
}: CatalogTableProps) {
  const [query, setQuery] = useState("");
  const [quick, setQuick] = useState<QuickFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("deep_dive");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // `mounted` gates the virtualized body so the SSR pass renders an
  // empty body — the header, toolbar, and footnotes still hydrate
  // from server HTML for snappy first paint, and the rows appear on
  // the next client tick. Keeps the static-export HTML tiny.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // The .tableScroll element is the scroll container (overflow-y in
  // CSS), so rows scroll under the sticky header without dragging the
  // whole page around.
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (q) {
        // Search across symbol, UniProt, the NCBI descriptive name,
        // and every synonym — so "transferrin" matches TF and "TGN46"
        // matches TGOLN2 even though neither appears in the canonical
        // symbol.
        const syn = r.synonyms ? r.synonyms.join(" ") : "";
        const hay =
          `${r.symbol} ${r.uniprot} ${r.name ?? ""} ${syn}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (quick === "deep_dive" && !r.deep_dive) return false;
      if (quick === "triage" && !r.triage) return false;
      if (quick === "n7" && r.n_sources < 5) return false;
      return true;
    });
  }, [rows, query, quick]);

  const sorted = useMemo(() => {
    const copy = filtered.slice();
    const dir = sortDir === "asc" ? 1 : -1;
    copy.sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return a.symbol < b.symbol ? -1 : a.symbol > b.symbol ? 1 : 0;
    });
    return copy;
  }, [filtered, sortKey, sortDir]);

  const virtualizer = useVirtualizer({
    count: sorted.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_ESTIMATE_PX,
    overscan: ROW_OVERSCAN,
  });

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();

  function setSort(k: SortKey) {
    if (k === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(k);
      setSortDir(k === "symbol" || k === "uniprot" ? "asc" : "desc");
    }
  }

  const gridStyle: React.CSSProperties = {
    // Exposed as a CSS custom property so the row + header rules in
    // the .module.css can share the same template (referenced via
    // `var(--catalog-cols)`).
    ["--catalog-cols" as string]: GRID_TEMPLATE,
  };

  return (
    <div className={styles.wrap} style={gridStyle}>
      <div className={styles.toolbar}>
        <div className={styles.search}>
          <label htmlFor="catalog-search" className="sr-only">
            Filter by symbol, UniProt, gene name, or synonym
          </label>
          <input
            id="catalog-search"
            className={styles.searchInput}
            placeholder="Filter by symbol, UniProt, name, or synonym…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            type="search"
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <div className={styles.chips} role="tablist" aria-label="Quick filters">
          <button
            type="button"
            className={`${styles.chip} ${quick === "all" ? styles.chipOn : ""}`}
            onClick={() => setQuick("all")}
            aria-pressed={quick === "all"}
          >
            All <span className={styles.chipCount}>{n_rows}</span>
          </button>
          <button
            type="button"
            className={`${styles.chip} ${quick === "deep_dive" ? styles.chipOn : ""}`}
            onClick={() => setQuick("deep_dive")}
            aria-pressed={quick === "deep_dive"}
          >
            Deep-dive <span className={styles.chipCount}>{n_with_deep_dive}</span>
          </button>
          <button
            type="button"
            className={`${styles.chip} ${quick === "triage" ? styles.chipOn : ""}`}
            onClick={() => setQuick("triage")}
            aria-pressed={quick === "triage"}
          >
            Triaged <span className={styles.chipCount}>{n_with_triage}</span>
          </button>
          <button
            type="button"
            className={`${styles.chip} ${quick === "n7" ? styles.chipOn : ""}`}
            onClick={() => setQuick("n7")}
            aria-pressed={quick === "n7"}
          >
            5-source consensus
          </button>
        </div>
      </div>

      <p className={styles.resultMeta}>
        {sorted.length === rows.length
          ? `${sorted.length.toLocaleString()} genes`
          : `${sorted.length.toLocaleString()} of ${rows.length.toLocaleString()} genes`}
        {generated_at ? (
          <>
            <span className={styles.dot} aria-hidden="true">
              ·
            </span>
            <span title={generated_at}>generated {generated_at.slice(0, 10)}</span>
          </>
        ) : null}
      </p>

      <div
        className={styles.tableScroll}
        ref={scrollRef}
        role="table"
        aria-rowcount={sorted.length + 1}
      >
        {/* Header row — sticky, identical grid template as every body row */}
        <div className={`${styles.headerRow} ${styles.row}`} role="row">
          <SortableHeader
            label="Symbol"
            k="symbol"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="left"
          />
          <SortableHeader
            label="UniProt"
            k="uniprot"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="left"
            mono
          />
          <SortableHeader
            label="Sources"
            k="n_sources"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="center"
            title="Count of DB sources voting surface"
          />
          {DB_KEYS.map((d) => (
            <div
              key={d.key}
              className={`${styles.headerCell} ${styles.headerDbCell}`}
              title={d.long}
              role="columnheader"
            >
              <span aria-hidden="true">{d.short}</span>
              <span className="sr-only">{d.long}</span>
            </div>
          ))}
          <SortableHeader
            label="Triage"
            k="triage"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="left"
          />
          <SortableHeader
            label="Deep dive"
            k="deep_dive"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="center"
          />
        </div>

        {/* Body — a single positioned container whose height is the
            virtualizer's totalSize. Each visible row is absolutely
            positioned inside it; the browser reserves the full scroll
            height without us shipping 19k DOM rows. */}
        <div
          className={styles.body}
          style={
            mounted && sorted.length > 0
              ? { height: totalSize, position: "relative" }
              : undefined
          }
          role="rowgroup"
        >
          {!mounted ? (
            <div className={styles.loadingRow} role="row" aria-hidden="true">
              Loading {sorted.length.toLocaleString()} rows…
            </div>
          ) : null}
          {mounted && sorted.length > 0
            ? virtualItems.map((item) => {
                const r = sorted[item.index];
                return (
                  <CatalogRowView
                    key={`${r.symbol}-${r.uniprot}`}
                    row={r}
                    measureRef={virtualizer.measureElement}
                    dataIndex={item.index}
                    virtualStart={item.start}
                  />
                );
              })
            : null}
          {mounted && sorted.length === 0 ? (
            <div className={styles.empty} role="row">
              No rows match these filters.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function sortValue(r: CatalogRow, k: SortKey): string | number {
  if (k === "symbol") return r.symbol;
  if (k === "uniprot") return r.uniprot;
  if (k === "n_sources") return r.n_sources;
  if (k === "triage") {
    // yes > contextual > no > none
    const v = r.triage?.verdict;
    if (v === "yes") return 3;
    if (v === "contextual") return 2;
    if (v === "no") return 1;
    return 0;
  }
  if (k === "deep_dive") return r.deep_dive ? 1 : 0;
  return 0;
}

function SortableHeader({
  label,
  k,
  sortKey,
  sortDir,
  onClick,
  align,
  mono,
  title,
}: {
  label: string;
  k: SortKey;
  sortKey: SortKey;
  sortDir: SortDir;
  onClick: (k: SortKey) => void;
  align: "left" | "center";
  mono?: boolean;
  title?: string;
}) {
  const active = sortKey === k;
  return (
    <div
      role="columnheader"
      className={`${styles.headerCell} ${align === "center" ? styles.headerCenter : ""} ${mono ? styles.headerMono : ""}`}
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        className={`${styles.thBtn} ${active ? styles.thBtnActive : ""}`}
        onClick={() => onClick(k)}
        title={title}
      >
        {label}
        <span className={styles.sortIndicator} aria-hidden="true">
          {active ? (sortDir === "asc" ? "▲" : "▼") : ""}
        </span>
      </button>
    </div>
  );
}

function CatalogRowView({
  row,
  measureRef,
  dataIndex,
  virtualStart,
}: {
  row: CatalogRow;
  measureRef?: (el: HTMLDivElement | null) => void;
  dataIndex?: number;
  virtualStart?: number;
}) {
  const symbolCell = row.deep_dive ? (
    <Link href={`/${row.symbol}/`} className={styles.symbolLink}>
      {row.symbol}
    </Link>
  ) : (
    <span className={styles.symbolText}>{row.symbol}</span>
  );
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
  return (
    <div
      ref={measureRef}
      data-index={dataIndex}
      role="row"
      className={styles.row}
      data-deep-dive={row.deep_dive || undefined}
      style={style}
    >
      <div className={`${styles.cell} ${styles.symbolCell}`} role="cell">
        {symbolCell}
      </div>
      <div className={`${styles.cell} ${styles.uniprotCell}`} role="cell">
        {row.uniprot}
      </div>
      <div className={`${styles.cell} ${styles.nCell}`} role="cell">
        <span className={styles.nBubble} data-n={row.n_sources}>
          {row.n_sources}
        </span>
      </div>
      {DB_KEYS.map((d) => {
        const yes = Boolean(row.db[d.key]);
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
      <div className={`${styles.cell} ${styles.triageCell}`} role="cell">
        {row.triage ? (
          <span className={`${styles.verdict} ${verdictTone(row.triage.verdict)}`}>
            <span className={styles.verdictLabel}>{row.triage.verdict}</span>
            {row.triage.reason ? (
              <span className={styles.verdictReason}>
                {row.triage.reason.replace(/_/g, " ")}
              </span>
            ) : null}
          </span>
        ) : (
          <span className={styles.dim}>—</span>
        )}
      </div>
      <div className={`${styles.cell} ${styles.deepCell}`} role="cell">
        {row.deep_dive ? (
          <Link
            href={`/${row.symbol}/`}
            className={styles.deepBadge}
            aria-label={`View deep-dive record for ${row.symbol}`}
          >
            view →
          </Link>
        ) : (
          <span className={styles.dim}>—</span>
        )}
      </div>
    </div>
  );
}
