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
import styles from "./BenchmarkTable.module.css";

const ROW_ESTIMATE_PX = 44;
const ROW_OVERSCAN = 12;

// Grid template (top→bottom): toggle | gene | uniprot | truth | 5 DBs |
// 12 model×variant pills (Opus naive/ncbi/web/pubmed → Sonnet ditto →
// Haiku ditto) | class. Each LLM pill is 2.6rem so 12 of them fit in
// ~31rem; the matrix is wide but readable on a laptop with the
// horizontal scroll the .tableScroll wrapper provides.
const LLM_CELL_REM = 2.6;
const GRID_TEMPLATE = [
  "1.6rem",                         // toggle
  "10rem",                          // gene
  "5rem",                           // uniprot
  "4rem",                           // truth pill
  ...Array(5).fill("1.4rem"),       // 5 DB dots
  ...Array(12).fill(`${LLM_CELL_REM}rem`), // 3 models × 4 variants
  "minmax(8rem, 1fr)",              // class
].join(" ");

// Five gating DBs — same set the homepage CatalogTable renders so a
// reader can scan both surfaces with the same mental model.
const DB_KEYS: { key: BenchmarkSource; short: string; long: string }[] = [
  { key: "uniprot", short: "U", long: "UniProt" },
  { key: "go", short: "G", long: "GO" },
  { key: "surfy", short: "S", long: "SURFY" },
  { key: "cspa", short: "C", long: "CSPA" },
  { key: "hpa", short: "H", long: "HPA" },
];

const MODEL_LABELS: { id: string; short: string; long: string }[] = [
  { id: "claude-opus-4-7", short: "Opus", long: "Opus 4.7" },
  { id: "claude-sonnet-4-6", short: "Sonnet", long: "Sonnet 4.6" },
  { id: "claude-haiku-4-5", short: "Haiku", long: "Haiku 4.5" },
];

// One-letter variant abbreviations for the header — long form lives
// in the `title` attribute. Order is fixed at render time so the
// 12-cell grid stays stable across (gene, model) combinations.
const VARIANT_LABELS: { id: string; short: string; long: string }[] = [
  { id: "naive",       short: "n", long: "naive (no context)" },
  { id: "ncbi",        short: "c", long: "ncbi (HGNC + UniProt + NCBI summary)" },
  { id: "web_ncbi",    short: "w", long: "web_ncbi (ncbi + web search)" },
  { id: "pubmed_ncbi", short: "p", long: "pubmed_ncbi (ncbi + PubMed evidence)" },
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
  // Defensive: `r.verdicts` is required by the shipped Worker but may
  // be absent in stub responses (`SURFACEOME_API_BASE=local`) or in
  // a stale edge-cached payload from before the 2026-05-15 shape
  // change. Treat missing data as "no disagreement signal".
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
  /** Genes the viewer has a deep-dive record for — used to link
   *  gene symbols to /[symbol]/ pages when one exists. */
  deepDiveGenes: Set<string>;
  /** symbol → full gene name (HGNC) for the secondary line under
   *  each gene symbol. */
  geneNames?: Record<string, string>;
}

export function BenchmarkTable({
  matrix,
  deepDiveGenes,
  geneNames,
}: BenchmarkTableProps) {
  const { rows, models, headline_variant } = matrix;
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<TruthFilter>("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggleExpand(symbol: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  }

  function handleDownload() {
    const tsv = buildBenchmarkTsv(matrix);
    const tag = matrix.bench_version?.slice(0, 8) ?? "snapshot";
    downloadTextFile(`surfacebench-${tag}.tsv`, tsv);
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
        <span>
          BENCH <code>{matrix.bench_version?.slice(0, 8) ?? "—"}</code>
        </span>
        <span className={styles.metaDot}>·</span>
        <span>
          models {MODEL_LABELS.map((m) => m.long).join(" · ")}
        </span>
        <span className={styles.metaDot}>·</span>
        <span>
          variants {VARIANT_LABELS.map((v) => v.id).join(" · ")}
        </span>
        <span className={styles.metaDot}>·</span>
        <span>headline <code>{headline_variant}</code></span>
        <span className={styles.metaDot}>·</span>
        <span>click <em>+</em> for per-call reasoning</span>
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
      </div>

      <div className={styles.resultRow}>
        <p className={styles.resultMeta}>
          {filtered.length === rows.length
            ? `${filtered.length} genes`
            : `${filtered.length} of ${rows.length} genes`}
        </p>
        <button
          type="button"
          className={styles.downloadBtn}
          onClick={handleDownload}
          title={`Download all ${rows.length} rows as TSV — every (model, variant) cell flattened to its own columns`}
        >
          Download TSV ↓
        </button>
      </div>

      <div
        className={styles.tableScroll}
        ref={scrollRef}
        role="table"
        aria-rowcount={filtered.length + 1}
      >
        {/* Two-row header: top row groups the LLM cells by model
            (spanning 4 variant columns each); bottom row carries the
            actual column labels (gene / uniprot / truth / DB short
            codes / variant short codes / class). */}
        <div className={`${styles.headerRow} ${styles.row} ${styles.modelGroupRow}`} role="row">
          <div className={styles.headerCell} aria-hidden="true" />
          <div className={styles.headerCell} aria-hidden="true" />
          <div className={styles.headerCell} aria-hidden="true" />
          <div className={styles.headerCell} aria-hidden="true" />
          {DB_KEYS.map((d) => (
            <div key={`gap-db-${d.key}`} className={styles.headerCell} aria-hidden="true" />
          ))}
          {MODEL_LABELS.map((m) => (
            <div
              key={`grp-${m.id}`}
              className={`${styles.headerCell} ${styles.modelGroupCell}`}
              role="columnheader"
              title={m.long}
            >
              {m.short}
            </div>
          ))}
          <div className={styles.headerCell} aria-hidden="true" />
        </div>
        <div className={`${styles.headerRow} ${styles.row}`} role="row">
          <div className={styles.headerCell} aria-hidden="true" />
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
              <span aria-hidden="true">{d.short}</span>
              <span className="sr-only">{d.long}</span>
            </div>
          ))}
          {MODEL_LABELS.map((m) =>
            VARIANT_LABELS.map((v) => {
              const isHeadline = v.id === headline_variant;
              return (
                <div
                  key={`hdr-${m.id}-${v.id}`}
                  className={`${styles.headerCell} ${styles.headerVariantCell} ${
                    isHeadline ? styles.headerVariantHeadline : ""
                  }`}
                  title={`${m.long} · ${v.long}`}
                  role="columnheader"
                >
                  {v.short}
                </div>
              );
            })
          )}
          <div className={styles.headerCell} role="columnheader">Class</div>
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
                const isExpanded = expanded.has(r.gene_symbol);
                return (
                  <BenchRowView
                    key={r.gene_symbol}
                    row={r}
                    measureRef={virtualizer.measureElement}
                    dataIndex={item.index}
                    virtualStart={item.start}
                    isExpanded={isExpanded}
                    onToggleExpand={toggleExpand}
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
  onToggleExpand,
  hasDeepDive,
  geneName,
}: {
  row: BenchmarkRow;
  measureRef?: (el: HTMLDivElement | null) => void;
  dataIndex?: number;
  virtualStart?: number;
  isExpanded: boolean;
  onToggleExpand: (symbol: string) => void;
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
  const symbolHead = hasDeepDive ? (
    <Link href={`/${row.gene_symbol}/`} className={styles.symbolLink}>
      {row.gene_symbol}
    </Link>
  ) : (
    <span className={styles.symbolText}>{row.gene_symbol}</span>
  );
  const geneCell = (
    <span className={styles.symbolStack}>
      {symbolHead}
      {geneName ? (
        <span className={styles.symbolName} title={geneName}>
          {geneName}
        </span>
      ) : null}
    </span>
  );
  return (
    <div
      ref={measureRef}
      data-index={dataIndex}
      role="row"
      className={`${styles.row} ${isExpanded ? styles.rowExpanded : ""}`}
      style={style}
    >
      <div className={`${styles.cell} ${styles.toggleCell}`} role="cell">
        <button
          type="button"
          className={styles.toggleBtn}
          onClick={() => onToggleExpand(row.gene_symbol)}
          aria-label={
            isExpanded
              ? `Collapse reasoning for ${row.gene_symbol}`
              : `Expand reasoning for ${row.gene_symbol}`
          }
          aria-expanded={isExpanded}
        >
          {isExpanded ? "−" : "+"}
        </button>
      </div>
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
      {MODEL_LABELS.map((m) =>
        VARIANT_LABELS.map((v) => {
          const cell: BenchmarkVariantResult | null | undefined =
            row.verdicts?.[m.id]?.[v.id];
          return (
            <div
              key={`${m.id}-${v.id}`}
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
                  title={`${m.short} · ${v.id} → ${cell.verdict}${
                    cell.reason ? ` (${cell.reason.replace(/_/g, " ")})` : ""
                  }`}
                >
                  {verdictGlyph(cell.verdict)}
                </span>
              ) : (
                <span className={styles.dim}>·</span>
              )}
            </div>
          );
        })
      )}
      <div className={`${styles.cell} ${styles.classCell}`} role="cell">
        <span className={styles.classText} title={row.truth_reason.replace(/_/g, " ")}>
          {row.class.replace(/_/g, " ")}
        </span>
      </div>
      {isExpanded ? (
        <div className={styles.expandedBlock}>
          <ReasoningGrid row={row} />
        </div>
      ) : null}
    </div>
  );
}

/** Single-character glyph for the per-cell verdict — keeps each of
 *  the 12 LLM cells legible at 2.6rem wide. Hover-tip exposes the
 *  full verdict + reason. */
function verdictGlyph(v: string): string {
  if (v === "yes") return "Y";
  if (v === "no") return "N";
  if (v === "contextual") return "C";
  return "?";
}

/** Row-expand reveal — the full reasoning text for each of the 12
 *  (model × variant) cells. Laid out as 3 model groups, 4 variant
 *  cards per group. Cards without data show a muted "no run on
 *  file". This is the per-call audit surface the user asked for. */
function ReasoningGrid({ row }: { row: BenchmarkRow }) {
  return (
    <div className={styles.reasoningGrid}>
      {MODEL_LABELS.map((m) => (
        <div key={m.id} className={styles.reasoningGroup}>
          <h4 className={styles.reasoningGroupHead}>{m.long}</h4>
          <div className={styles.reasoningCards}>
            {VARIANT_LABELS.map((v) => {
              const cell: BenchmarkVariantResult | null | undefined =
                row.verdicts?.[m.id]?.[v.id];
              return (
                <article
                  key={v.id}
                  className={`${styles.reasoningCard} ${
                    cell?.verdict
                      ? isCorrect(cell.verdict, row.truth_verdict)
                        ? styles.reasoningCardCorrect
                        : styles.reasoningCardWrong
                      : styles.reasoningCardMissing
                  }`}
                >
                  <header className={styles.reasoningCardHead}>
                    <span className={styles.reasoningVariant}>{v.id}</span>
                    {cell?.verdict ? (
                      <span
                        className={`${styles.verdictLabel} ${verdictTone(cell.verdict)}`}
                      >
                        {cell.verdict}
                      </span>
                    ) : (
                      <span className={styles.reasoningMissing}>no run</span>
                    )}
                    {cell?.confidence ? (
                      <span className={styles.reasoningMeta} title="confidence">
                        {cell.confidence}
                      </span>
                    ) : null}
                  </header>
                  {cell?.reasoning ? (
                    <p className={styles.reasoningText}>{cell.reasoning}</p>
                  ) : cell?.verdict && !cell.reasoning ? (
                    <p className={styles.reasoningEmpty}>
                      (no free-text reasoning recorded — verdict only)
                    </p>
                  ) : null}
                  {cell?.reason && cell.reason !== cell.verdict ? (
                    <p className={styles.reasoningReason}>
                      <span className="label-mono">reason ·</span>{" "}
                      {cell.reason.replace(/_/g, " ")}
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Wide TSV download — one row per gene, columns for every cell
 *  (model × variant) in the matrix. Matches the on-page grid so a
 *  reader can pull it down and reproduce the table in pandas. */
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
