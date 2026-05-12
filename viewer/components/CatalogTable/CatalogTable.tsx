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

// Single source of truth for column widths shared by:
//   * the <colgroup> in the <thead> (so the header columns size correctly)
//   * the per-row absolutely-positioned <colgroup> (each virtualized row
//     is its own display:table block; without these widths the columns
//     would silently drift away from the header).
// Order MUST match the column order rendered below.
const COL_WIDTHS = [
  "7.5rem", // symbol
  "5.5rem", // uniprot
  "3rem",   // n_sources
  "1.6rem", // db: uniprot
  "1.6rem", // db: go
  "1.6rem", // db: surfy
  "1.6rem", // db: cspa
  "1.6rem", // db: hpa
  "14rem",  // triage
  "4.5rem", // deep dive
] as const;

function Cols() {
  return (
    <colgroup>
      {COL_WIDTHS.map((w, i) => (
        <col key={i} style={{ width: w }} />
      ))}
    </colgroup>
  );
}

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
  // empty tbody — the table header, toolbar, and footnotes still
  // hydrate from server HTML for snappy first paint, and the rows
  // appear on the next client tick. This keeps the static-export
  // HTML tiny (was 22 MB of <tr>; now ~50 KB) and trades a brief
  // empty-table flash for a fast initial paint + interactive load.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // The table is the scroll container (overflow-y: auto in CSS), so
  // rows can scroll under the sticky header without dragging the
  // whole page around. Element-scroll virtualization is more
  // predictable than window-scroll on first paint — no need to
  // measure tbody.offsetTop against window scroll.
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (q) {
        // Search across symbol, UniProt, the NCBI descriptive name, and
        // every synonym — so "transferrin" matches TF and "TGN46" matches
        // TGOLN2 even though neither appears in the canonical symbol.
        const syn = r.synonyms ? r.synonyms.join(" ") : "";
        const hay = `${r.symbol} ${r.uniprot} ${r.name ?? ""} ${syn}`.toLowerCase();
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

  return (
    <div className={styles.wrap}>
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

      <div className={styles.tableScroll} ref={scrollRef}>
        <table className={styles.table}>
          <Cols />
          <thead>
            <tr>
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
                <th
                  key={d.key}
                  className={styles.dbCol}
                  title={d.long}
                  scope="col"
                >
                  <span aria-hidden="true">{d.short}</span>
                  <span className="sr-only">{d.long}</span>
                </th>
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
            </tr>
          </thead>
          <tbody
            style={
              mounted && sorted.length > 0
                ? { height: totalSize, position: "relative", display: "block" }
                : undefined
            }
          >
            {/* SSR / pre-hydration: a single loading row keeps the
                table footprint stable and tells the reader the data
                is on its way. */}
            {!mounted ? (
              <tr aria-hidden="true">
                <td
                  colSpan={5 + DB_KEYS.length}
                  className={styles.loadingRow}
                >
                  Loading {sorted.length.toLocaleString()} rows…
                </td>
              </tr>
            ) : null}
            {/* Post-hydration: only the visible window of rows
                renders. Each row is absolutely positioned inside the
                tbody (height set above to totalSize) so the
                browser's scroll container reserves the right amount
                of room without us having to ship 19k <tr>s. */}
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
              <tr>
                <td colSpan={5 + DB_KEYS.length} className={styles.empty}>
                  No rows match these filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
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
    <th
      scope="col"
      className={`${styles.th} ${align === "center" ? styles.thCenter : ""} ${mono ? styles.thMono : ""}`}
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
    </th>
  );
}

function CatalogRowView({
  row,
  measureRef,
  dataIndex,
  virtualStart,
}: {
  row: CatalogRow;
  measureRef?: (el: HTMLTableRowElement | null) => void;
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
  // When virtualStart is set we position the row absolutely inside
  // the (display:block) tbody. The tbody's height is set to the
  // virtualizer's totalSize so the scrollbar reflects the full row
  // count even though only the visible window is in the DOM.
  const style: React.CSSProperties | undefined =
    virtualStart != null
      ? {
          position: "absolute",
          top: 0,
          left: 0,
          transform: `translateY(${virtualStart}px)`,
          display: "table",
          width: "100%",
          tableLayout: "fixed",
        }
      : undefined;
  return (
    <tr
      ref={measureRef}
      data-index={dataIndex}
      className={styles.row}
      data-deep-dive={row.deep_dive || undefined}
      style={style}
    >
      <td className={styles.symbolCell}>{symbolCell}</td>
      <td className={styles.uniprotCell}>{row.uniprot}</td>
      <td className={styles.nCell}>
        <span className={styles.nBubble} data-n={row.n_sources}>
          {row.n_sources}
        </span>
      </td>
      {DB_KEYS.map((d) => {
        const yes = Boolean(row.db[d.key]);
        return (
          <td
            key={d.key}
            className={`${styles.dbCell} ${yes ? styles.dbCellYes : ""}`}
            aria-label={`${d.long}: ${yes ? "yes" : "no"}`}
          >
            <span className={styles.dbDot} aria-hidden="true" />
          </td>
        );
      })}
      <td className={styles.triageCell}>
        {row.triage ? (
          <span className={`${styles.verdict} ${verdictTone(row.triage.verdict)}`}>
            <span className={styles.verdictLabel}>{row.triage.verdict}</span>
            {row.triage.reason ? (
              <span className={styles.verdictReason}>{row.triage.reason.replace(/_/g, " ")}</span>
            ) : null}
          </span>
        ) : (
          <span className={styles.dim}>—</span>
        )}
      </td>
      <td className={styles.deepCell}>
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
      </td>
    </tr>
  );
}
