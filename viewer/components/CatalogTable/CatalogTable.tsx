"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { CatalogRow, TriageCell } from "../../lib/surfaceome";
import { buildTsv, downloadTextFile, type TsvCell } from "../../lib/tsv";
import {
  CatalogRationaleDrawer,
  type CatalogTriageDetailState,
} from "./CatalogRationaleDrawer";
import styles from "./CatalogTable.module.css";

// Per-row height estimate fed to @tanstack/react-virtual. Rows with
// a triage verdict are taller (two lines — verdict pill above, reason
// underneath) so we keep the estimate slightly above the no-triage
// height. The virtualizer dynamically re-measures as rows enter the
// viewport, so this only needs to be in the right ballpark for the
// initial scroll-height calc and overscan window.
const ROW_ESTIMATE_PX = 56;
const ROW_OVERSCAN = 12;

// CSS Grid template — gene | uniprot | sources | 5 DB dots | Sonnet
// verdict (NCBI variant; the catalog's headline model) | deep-dive
// flag. Haiku and Opus calls live on /benchmark so the catalog stays
// a single-model surface. There's no row +/- toggle: clicking the
// gene symbol or the verdict cell opens the right-side rationale
// drawer.
const GRID_TEMPLATE =
  "16rem 5.5rem 3rem 4.5rem 3.2rem 4.5rem 4rem 3.2rem 8rem 5rem";

// Worker base for the on-demand /v1/triage/{symbol} fetch the row
// expander triggers. Falls back to the production deployment when
// `NEXT_PUBLIC_SURFACEOME_API_BASE` isn't set (local dev or static
// export without a build-time override). The `_PUBLIC_` prefix is
// required for Next.js to inline the value into the client bundle.
const TRIAGE_API_BASE =
  process.env.NEXT_PUBLIC_SURFACEOME_API_BASE ?? "https://api.deliverome.org/surfaceome";

interface TriageRun {
  created_at: string;
  model: string;
  prompt_variant: string | null;
  prompt_filename: string | null;
  schema_version: string | null;
  replicate: number | null;
  predicted_verdict: string;
  predicted_reason: string | null;
  predicted_confidence: string | null;
  predicted_key_uncertainty: string | null;
  verdict_reasoning: string | null;
  correct: number | null;
  latency_s: number | null;
  n_web_searches: number | null;
  error: string | null;
}

type TriageDetailState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; runs: TriageRun[] };

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

// Sonnet 4.6 (NCBI variant) is the catalog's headline model — the one
// run on every protein-coding gene with the headline prompt. Haiku
// and Opus calls exist in the Worker response but only render on the
// SurfaceBench benchmark, where the goal is cross-model comparison.
// `idx` is the index in the Worker's `triage_by_model` array (still
// fixed at Haiku=0, Sonnet=1, Opus=2 per Worker contract).
const CATALOG_MODELS: { id: string; idx: number; short: string; long: string }[] = [
  { id: "claude-sonnet-4-6", idx: 1, short: "S", long: "Sonnet 4.6 · ncbi" },
];

type SortKey = "symbol" | "uniprot" | "n_sources" | "triage_sonnet" | "deep_dive";
type SortDir = "asc" | "desc";
// Triage filter was dropped — every gene in the universe has a triage
// verdict (the one gap, SEA, is a resolver-failure outlier), so the
// chip filtered ~all rows in and offered no signal.
type QuickFilter = "all" | "deep_dive" | "n7";

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
  /** universe_version identifier from /v1/catalog — included in the
   *  TSV download filename so a downloaded snapshot is traceable. */
  universe_version?: string;
}

export function CatalogTable({
  rows,
  generated_at,
  n_rows,
  n_with_triage,
  n_with_deep_dive,
  universe_version,
}: CatalogTableProps) {
  const [query, setQuery] = useState("");
  const [quick, setQuick] = useState<QuickFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("deep_dive");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  // Side-rationale drawer: one selected symbol at a time. Clicking the
  // same symbol again toggles the drawer off. The /v1/triage/{symbol}
  // fetch is lazy — kicked off the first time a symbol is selected,
  // cached for the rest of the session (we don't ship the full per-
  // run reasoning in /v1/catalog: 19k genes × ~1 KB reasoning is too
  // big to inline). The drawer reads the cached detail entry and
  // falls back to the catalog row's headline verdict while the fetch
  // is in flight.
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [triageDetails, setTriageDetails] = useState<
    Record<string, TriageDetailState>
  >({});

  function handleSelectSymbol(symbol: string) {
    setSelectedSymbol((prev) => (prev === symbol ? null : symbol));
    if (triageDetails[symbol]) return;
    setTriageDetails((prev) => ({ ...prev, [symbol]: { status: "loading" } }));
    fetch(`${TRIAGE_API_BASE}/v1/triage/${symbol}`, { cache: "force-cache" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = (await res.json()) as { runs: TriageRun[] };
        setTriageDetails((prev) => ({
          ...prev,
          [symbol]: { status: "ready", runs: data.runs ?? [] },
        }));
      })
      .catch((err: Error) => {
        setTriageDetails((prev) => ({
          ...prev,
          [symbol]: { status: "error", message: err.message },
        }));
      });
  }

  // ESC closes the drawer. Installed at the table level so the
  // non-modal drawer doesn't need focus to dismiss.
  useEffect(() => {
    if (!selectedSymbol) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedSymbol(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedSymbol]);

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
        // and every synonym — so a free-text query like "transferrin"
        // can match a gene whose canonical symbol is TF.
        const syn = r.synonyms ? r.synonyms.join(" ") : "";
        const hay =
          `${r.symbol} ${r.uniprot} ${r.name ?? ""} ${syn}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (quick === "deep_dive" && !r.deep_dive) return false;
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
        <div className={styles.chipsActions}>
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
              className={`${styles.chip} ${quick === "n7" ? styles.chipOn : ""}`}
              onClick={() => setQuick("n7")}
              aria-pressed={quick === "n7"}
            >
              5-source consensus
            </button>
          </div>
          <button
            type="button"
            className={styles.downloadBtn}
            onClick={() => {
              const tsv = buildCatalogTsv(rows);
              const tag = universe_version ?? "snapshot";
              downloadTextFile(`surfaceome-catalog-${tag}.tsv`, tsv);
            }}
            title={`Download all ${rows.length.toLocaleString()} catalog rows as TSV`}
          >
            TSV ↓
          </button>
        </div>
      </div>

      <div className={styles.resultRow}>
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
      </div>

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
            label="Accession"
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
              {d.long}
            </div>
          ))}
          {CATALOG_MODELS.map((m) => (
            <div
              key={`mhdr-${m.id}`}
              className={`${styles.headerCell} ${styles.headerCenter}`}
              title={m.long}
              role="columnheader"
            >
              {m.long.replace(" · ncbi", "")}
            </div>
          ))}
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
                const isSelected = selectedSymbol === r.symbol;
                return (
                  <CatalogRowView
                    key={`${r.symbol}-${r.uniprot}`}
                    row={r}
                    measureRef={virtualizer.measureElement}
                    dataIndex={item.index}
                    virtualStart={item.start}
                    isSelected={isSelected}
                    onSelect={handleSelectSymbol}
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

      <CatalogRationaleDrawer
        selectedSymbol={selectedSymbol}
        detail={
          selectedSymbol
            ? (triageDetails[selectedSymbol] as
                | CatalogTriageDetailState
                | undefined)
            : undefined
        }
        fallback={
          selectedSymbol
            ? fallbackFromRows(sorted, selectedSymbol)
            : null
        }
        geneName={
          selectedSymbol ? geneNameFromRows(sorted, selectedSymbol) : null
        }
        hasDeepDive={
          selectedSymbol
            ? Boolean(
                sorted.find((r) => r.symbol === selectedSymbol)?.deep_dive,
              )
            : false
        }
        onClose={() => setSelectedSymbol(null)}
      />
    </div>
  );
}

/** Headline NCBI Sonnet verdict from the catalog row — used as a
 *  synchronous fallback while the drawer's lazy fetch is in flight. */
function fallbackFromRows(
  rows: CatalogRow[],
  symbol: string,
): { verdict: string | null; reason: string | null } | null {
  const row = rows.find((r) => r.symbol === symbol);
  if (!row) return null;
  // idx 1 = Sonnet 4.6 in the Worker's triage_by_model array; see
  // CATALOG_MODELS above for the contract.
  const cell = row.triage_by_model[1];
  return {
    verdict: cell?.verdict ?? null,
    reason: cell?.reason ?? null,
  };
}

function geneNameFromRows(rows: CatalogRow[], symbol: string): string | null {
  const row = rows.find((r) => r.symbol === symbol);
  return row?.name ?? null;
}

/**
 * Build a TSV of the catalog rows — one row per gene, matching the
 * columns shown in the table plus the gene name / synonyms from the
 * NCBI lookup (which the UI uses for search but doesn't render). Bulk
 * download is the full unfiltered dataset; if the reader needs a
 * subset, they can filter in pandas / R after downloading.
 */
function buildCatalogTsv(rows: CatalogRow[]): string {
  const headers = [
    "gene_symbol",
    "uniprot_acc",
    "gene_name",
    "synonyms",
    "n_sources",
    "db_uniprot",
    "db_go",
    "db_surfy",
    "db_cspa",
    "db_hpa",
    "haiku_ncbi_verdict",  "haiku_ncbi_reason",
    "sonnet_ncbi_verdict", "sonnet_ncbi_reason",
    "opus_ncbi_verdict",   "opus_ncbi_reason",
    "has_deep_dive",
  ];
  const body: TsvCell[][] = rows.map((r) => [
    r.symbol,
    r.uniprot,
    r.name ?? "",
    r.synonyms ? r.synonyms.join("|") : "",
    r.n_sources,
    r.db.uniprot,
    r.db.go,
    r.db.surfy,
    r.db.cspa,
    r.db.hpa,
    r.triage_by_model[0]?.verdict ?? "", r.triage_by_model[0]?.reason ?? "",
    r.triage_by_model[1]?.verdict ?? "", r.triage_by_model[1]?.reason ?? "",
    r.triage_by_model[2]?.verdict ?? "", r.triage_by_model[2]?.reason ?? "",
    r.deep_dive ? 1 : 0,
  ]);
  return buildTsv(headers, body);
}

function sortValue(r: CatalogRow, k: SortKey): string | number {
  if (k === "symbol") return r.symbol;
  if (k === "uniprot") return r.uniprot;
  if (k === "n_sources") return r.n_sources;
  if (k === "triage_sonnet") {
    // Sort by the Sonnet/ncbi verdict (slot 1) — the only model with
    // full-genome coverage. yes > contextual > no > none.
    const v = r.triage_by_model[1]?.verdict;
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
  isSelected,
  onSelect,
}: {
  row: CatalogRow;
  measureRef?: (el: HTMLDivElement | null) => void;
  dataIndex?: number;
  virtualStart?: number;
  isSelected: boolean;
  onSelect: (symbol: string) => void;
}) {
  const symbolButton = (
    <button
      type="button"
      className={styles.symbolButton}
      onClick={() => onSelect(row.symbol)}
      aria-pressed={isSelected}
      aria-label={`Open Sonnet reasoning for ${row.symbol}`}
    >
      <span className={styles.symbolStack}>
        <span className={styles.symbolText}>{row.symbol}</span>
        {row.name ? (
          <span className={styles.symbolName} title={row.name}>
            {row.name}
          </span>
        ) : null}
      </span>
    </button>
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
      className={`${styles.row} ${isSelected ? styles.rowSelected : ""}`}
      data-deep-dive={row.deep_dive || undefined}
      style={style}
    >
      <div className={`${styles.cell} ${styles.symbolCell}`} role="cell">
        {symbolButton}
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
      {CATALOG_MODELS.map((m) => {
        const cell = row.triage_by_model[m.idx];
        return (
          <div
            key={`triage-${m.id}`}
            className={`${styles.cell} ${styles.triageCell} ${styles.modelCell}`}
            role="cell"
          >
            {cell ? (
              <button
                type="button"
                className={`${styles.verdictBtn} ${styles.verdictLabel} ${styles.verdictMini} ${verdictTone(cell.verdict)}`}
                onClick={() => onSelect(row.symbol)}
                aria-pressed={isSelected}
                title={
                  cell.reason
                    ? `${m.long}: ${cell.verdict} (${cell.reason.replace(/_/g, " ")}) — click for reasoning`
                    : `${m.long}: ${cell.verdict} — click for reasoning`
                }
              >
                {cell.verdict}
              </button>
            ) : (
              <span className={styles.dim} title={`${m.long}: no run on file`}>—</span>
            )}
          </div>
        );
      })}
      <div className={`${styles.cell} ${styles.deepCell}`} role="cell">
        {row.deep_dive ? (
          <Link
            href={`/${row.symbol}/`}
            className={styles.deepBadge}
            aria-label={`Open the deep-dive record for ${row.symbol}`}
            title={`Open the deep-dive record for ${row.symbol}`}
          >
            yes
          </Link>
        ) : (
          <span className={styles.dim}>—</span>
        )}
      </div>
    </div>
  );
}
