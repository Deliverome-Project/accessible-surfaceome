"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { CatalogRow } from "../../lib/surfaceome";
import { buildTsv, downloadTextFile, type TsvCell } from "../../lib/tsv";
import styles from "./CatalogTable.module.css";

// Per-row height estimate fed to @tanstack/react-virtual. Rows with
// a triage verdict are taller (two lines — verdict pill above, reason
// underneath) so we keep the estimate slightly above the no-triage
// height. The virtualizer dynamically re-measures as rows enter the
// viewport, so this only needs to be in the right ballpark for the
// initial scroll-height calc and overscan window.
const ROW_ESTIMATE_PX = 56;
const ROW_OVERSCAN = 12;

// CSS Grid template shared by the header row and every virtualized
// body row. Defining it once here (and once in CSS via the
// ``--catalog-cols`` custom property) is the bulletproof fix for the
// "thead and tbody column widths drift" problem that plagues
// virtualized HTML <table> rows. Both the header and each row are
// `display: grid; grid-template-columns: var(--catalog-cols)`, so the
// columns are GUARANTEED to line up — no proportional-fill rounding,
// no per-row `<table>` re-layout. The Symbol column needs enough room
// to fit the gene's full NCBI descriptive name beneath the symbol
// without truncation (e.g. "G-protein-coupled receptor 75"); 16rem
// covers most cases. Triage was widened way beyond what its content
// uses — `minmax(11rem, 1fr)` is enough for "contextual · cell-state
// induced" + chip + hover hint without leaving the table running off
// the right edge.
const GRID_TEMPLATE =
  "1.75rem 16rem 5.5rem 3rem 1.6rem 1.6rem 1.6rem 1.6rem 1.6rem minmax(11rem, 1fr) 6rem";

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

type SortKey = "symbol" | "uniprot" | "n_sources" | "triage" | "deep_dive";
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
  // Per-row "+" expander: tracks which symbols are open + the
  // lazily-fetched /v1/triage/<symbol> response per symbol. We don't
  // ship the full per-run reasoning in /v1/catalog (too big — 19k
  // genes × ~1 KB reasoning = 20 MB) so the expand triggers a single
  // small fetch and caches the result for the session.
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [triageDetails, setTriageDetails] = useState<
    Record<string, TriageDetailState>
  >({});

  function toggleExpand(symbol: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
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
          Download TSV ↓
        </button>
      </div>

      <div
        className={styles.tableScroll}
        ref={scrollRef}
        role="table"
        aria-rowcount={sorted.length + 1}
      >
        {/* Header row — sticky, identical grid template as every body row */}
        <div className={`${styles.headerRow} ${styles.row}`} role="row">
          {/* Leading toggle column. Empty header cell — every body row
              has a `+` button in this slot to expand triage details. */}
          <div className={styles.headerCell} aria-hidden="true" />
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
                const isExpanded = expanded.has(r.symbol);
                return (
                  <CatalogRowView
                    key={`${r.symbol}-${r.uniprot}`}
                    row={r}
                    measureRef={virtualizer.measureElement}
                    dataIndex={item.index}
                    virtualStart={item.start}
                    isExpanded={isExpanded}
                    onToggleExpand={toggleExpand}
                    detail={isExpanded ? triageDetails[r.symbol] : undefined}
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
    "triage_verdict",
    "triage_reason",
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
    r.triage?.verdict ?? "",
    r.triage?.reason ?? "",
    r.deep_dive ? 1 : 0,
  ]);
  return buildTsv(headers, body);
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
  isExpanded,
  onToggleExpand,
  detail,
}: {
  row: CatalogRow;
  measureRef?: (el: HTMLDivElement | null) => void;
  dataIndex?: number;
  virtualStart?: number;
  isExpanded: boolean;
  onToggleExpand: (symbol: string) => void;
  detail: TriageDetailState | undefined;
}) {
  const symbolHead = row.deep_dive ? (
    <Link href={`/${row.symbol}/`} className={styles.symbolLink}>
      {row.symbol}
    </Link>
  ) : (
    <span className={styles.symbolText}>{row.symbol}</span>
  );
  const symbolCell = (
    <span className={styles.symbolStack}>
      {symbolHead}
      {row.name ? (
        <span className={styles.symbolName} title={row.name}>
          {row.name}
        </span>
      ) : null}
    </span>
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
      className={`${styles.row} ${isExpanded ? styles.rowExpanded : ""}`}
      data-deep-dive={row.deep_dive || undefined}
      style={style}
    >
      <div className={`${styles.cell} ${styles.toggleCell}`} role="cell">
        <button
          type="button"
          className={styles.toggleBtn}
          onClick={() => onToggleExpand(row.symbol)}
          aria-label={
            isExpanded
              ? `Collapse triage details for ${row.symbol}`
              : `Expand triage details for ${row.symbol}`
          }
          aria-expanded={isExpanded}
        >
          {isExpanded ? "−" : "+"}
        </button>
      </div>
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
          <button
            type="button"
            className={`${styles.verdict} ${styles.verdictBtn} ${verdictTone(row.triage.verdict)}`}
            onClick={() => onToggleExpand(row.symbol)}
            aria-expanded={isExpanded}
            aria-label={
              isExpanded
                ? `Collapse triage details for ${row.symbol}`
                : `Open triage details for ${row.symbol}`
            }
          >
            <span className={styles.verdictLabel}>{row.triage.verdict}</span>
            {row.triage.reason ? (
              <span className={styles.verdictReason}>
                {row.triage.reason.replace(/_/g, " ")}
              </span>
            ) : null}
          </button>
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
      {isExpanded ? (
        <div className={styles.expandedBlock}>
          <TriageDetail symbol={row.symbol} fallback={row.triage} detail={detail} />
        </div>
      ) : null}
    </div>
  );
}

function TriageDetail({
  symbol,
  fallback,
  detail,
}: {
  symbol: string;
  fallback: CatalogRow["triage"];
  detail: TriageDetailState | undefined;
}) {
  if (!detail || detail.status === "loading") {
    return (
      <p className={styles.expandedMeta}>
        Loading triage runs for <strong>{symbol}</strong>…
      </p>
    );
  }
  if (detail.status === "error") {
    return (
      <p className={styles.expandedMeta}>
        Could not load triage details ({detail.message}).
        {fallback ? (
          <>
            {" "}Cached verdict: <strong>{fallback.verdict}</strong>
            {fallback.reason ? <> · {fallback.reason.replace(/_/g, " ")}</> : null}
          </>
        ) : null}
      </p>
    );
  }
  // Filter to the canonical genome-wide-sweep run — Sonnet 4.6 with
  // the NCBI prompt variant. The /v1/triage endpoint returns ALL runs
  // including benchmark / eval reruns, replicates, alternate prompts,
  // and (on D1) duplicate uploads from sweep iterations. Take only
  // the SINGLE latest sonnet/ncbi row so the expanded view shows one
  // canonical verdict per gene; "history" can come from a future
  // /history endpoint when it's useful.
  const sweepRuns = detail.runs
    .filter(
      (r) =>
        r.model.toLowerCase().includes("sonnet") && r.prompt_variant === "ncbi",
    )
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  const latestSweep = sweepRuns[0];
  if (!latestSweep) {
    return (
      <p className={styles.expandedMeta}>
        No genome-wide (Sonnet/NCBI) triage run recorded for{" "}
        <strong>{symbol}</strong>.
        {detail.runs.length > 0
          ? ` ${detail.runs.length} other run(s) on file (not shown).`
          : null}
      </p>
    );
  }
  // Render exactly one row — the latest sweep verdict.
  return (
    <ol className={styles.runList}>
      {[latestSweep].map((run, i) => (
        <li key={i} className={styles.runItem}>
          <p className={styles.runMeta}>
            <span className={styles.runBadge} data-verdict={run.predicted_verdict}>
              {run.predicted_verdict}
            </span>
            {run.predicted_reason ? (
              <span>{run.predicted_reason.replace(/_/g, " ")}</span>
            ) : null}
            <span className={styles.runDim}>·</span>
            <span className={styles.runDim}>{run.model}</span>
            {run.prompt_variant ? (
              <>
                <span className={styles.runDim}>·</span>
                <span className={styles.runDim}>{run.prompt_variant}</span>
              </>
            ) : null}
            {run.predicted_confidence ? (
              <>
                <span className={styles.runDim}>·</span>
                <span className={styles.runDim}>
                  conf {run.predicted_confidence}
                </span>
              </>
            ) : null}
            <span className={styles.runDim}>·</span>
            <span className={styles.runDim}>{run.created_at.slice(0, 16)}</span>
          </p>
          {run.verdict_reasoning ? (
            <p className={styles.runReasoning}>{run.verdict_reasoning}</p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
