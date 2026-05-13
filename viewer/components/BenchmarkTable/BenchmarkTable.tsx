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

const ROW_ESTIMATE_PX = 40;
const ROW_OVERSCAN = 12;

// Grid template: toggle | gene | uniprot | truth | 7 db dots | opus | sonnet
// | haiku | class. Kept narrow so the table reads as a dense matrix rather
// than a layout-heavy editorial block.
const GRID_TEMPLATE =
  "1.6rem 6rem 5rem 4.2rem 1.4rem 1.4rem 1.4rem 1.4rem 1.4rem 1.4rem 1.4rem 4.4rem 4.4rem 4.4rem minmax(10rem, 1fr)";

const DB_KEYS: { key: BenchmarkSource; short: string; long: string }[] = [
  { key: "uniprot", short: "U", long: "UniProt" },
  { key: "go", short: "G", long: "GO" },
  { key: "surfy", short: "S", long: "SURFY" },
  { key: "cspa", short: "C", long: "CSPA" },
  { key: "hpa", short: "H", long: "HPA" },
  { key: "deeptmhmm", short: "T", long: "DeepTMHMM" },
  { key: "compartments", short: "M", long: "COMPARTMENTS" },
];

// Map model ids to short column labels; the long form lives in the
// metadata strip above the table and as the column's title attribute.
const MODEL_LABELS: { id: string; short: string; long: string }[] = [
  { id: "claude-opus-4-7", short: "Opus", long: "Opus 4.7" },
  { id: "claude-sonnet-4-6", short: "Sonnet", long: "Sonnet 4.6" },
  { id: "claude-haiku-4-5", short: "Haiku", long: "Haiku 4.5" },
];

type TruthFilter = "all" | "yes" | "contextual" | "no" | "disagreements";

function verdictTone(v: string | null | undefined): string {
  if (v === "yes") return styles.verdictYes;
  if (v === "no") return styles.verdictNo;
  if (v === "contextual") return styles.verdictContextual;
  return styles.verdictUnknown;
}

function isCorrect(headlineVerdict: string | null, truth: string): boolean {
  // Mirror the D1 `correct` semantics: yes ≡ contextual count as the
  // same predicted class for accuracy purposes.
  if (!headlineVerdict) return false;
  const v = headlineVerdict;
  const t = truth;
  if (v === t) return true;
  if ((v === "yes" || v === "contextual") && (t === "yes" || t === "contextual")) {
    return true;
  }
  return false;
}

interface BenchmarkTableProps {
  matrix: BenchmarkMatrix;
  /** Genes the viewer has a deep-dive record for — used to link gene
   *  symbols to /[symbol]/ pages when one exists. */
  deepDiveGenes: Set<string>;
}

export function BenchmarkTable({ matrix, deepDiveGenes }: BenchmarkTableProps) {
  const { rows, headline_variant, alt_variants, models } = matrix;

  function handleDownload() {
    const tsv = buildBenchmarkTsv(matrix);
    const tag = matrix.bench_version?.slice(0, 8) ?? "snapshot";
    downloadTextFile(`surfaceome-benchmark-${tag}.tsv`, tsv);
  }

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

  const counts = useMemo(() => {
    let yes = 0;
    let contextual = 0;
    let no = 0;
    let disagreements = 0;
    for (const r of rows) {
      if (r.truth_verdict === "yes") yes++;
      else if (r.truth_verdict === "contextual") contextual++;
      else if (r.truth_verdict === "no") no++;
      const anyWrong = models.some((m) => {
        const h = r.headline[m];
        if (!h?.verdict) return false;
        return !isCorrect(h.verdict, r.truth_verdict);
      });
      if (anyWrong) disagreements++;
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
      if (filter === "disagreements") {
        const anyWrong = models.some((m) => {
          const h = r.headline[m];
          if (!h?.verdict) return false;
          return !isCorrect(h.verdict, r.truth_verdict);
        });
        if (!anyWrong) return false;
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

  const headlineShort = headline_variant.replace(/_/g, " ");

  return (
    <div className={styles.wrap} style={gridStyle}>
      <p className={styles.meta}>
        <span>
          BENCH <code>{matrix.bench_version?.slice(0, 8) ?? "—"}</code>
        </span>
        <span className={styles.metaDot}>·</span>
        <span>
          headline <code>{headlineShort}</code>
        </span>
        <span className={styles.metaDot}>·</span>
        <span>models {MODEL_LABELS.map((m) => m.long).join(" · ")}</span>
        <span className={styles.metaDot}>·</span>
        <span>
          alt variants {alt_variants.join(" · ")} (expand row)
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
          title={`Download all ${rows.length} rows as TSV (headline + alt variants for every model)`}
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
        <div className={`${styles.headerRow} ${styles.row}`} role="row">
          <div className={styles.headerCell} aria-hidden="true" />
          <div className={`${styles.headerCell}`} role="columnheader">
            Gene
          </div>
          <div className={`${styles.headerCell} ${styles.headerMono}`} role="columnheader">
            UniProt
          </div>
          <div className={`${styles.headerCell}`} role="columnheader">
            Truth
          </div>
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
          {MODEL_LABELS.map((m) => (
            <div
              key={m.id}
              className={`${styles.headerCell} ${styles.headerModelCell}`}
              title={`${m.long} · ${headlineShort}`}
              role="columnheader"
            >
              {m.short}
            </div>
          ))}
          <div className={styles.headerCell} role="columnheader">
            Class
          </div>
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
                    altVariants={alt_variants}
                    hasDeepDive={deepDiveGenes.has(r.gene_symbol)}
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
  altVariants,
  hasDeepDive,
}: {
  row: BenchmarkRow;
  measureRef?: (el: HTMLDivElement | null) => void;
  dataIndex?: number;
  virtualStart?: number;
  isExpanded: boolean;
  onToggleExpand: (symbol: string) => void;
  altVariants: string[];
  hasDeepDive: boolean;
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
  const geneCell = hasDeepDive ? (
    <Link href={`/${row.gene_symbol}/`} className={styles.symbolLink}>
      {row.gene_symbol}
    </Link>
  ) : (
    <span className={styles.symbolText}>{row.gene_symbol}</span>
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
              ? `Collapse alt variants for ${row.gene_symbol}`
              : `Expand alt variants for ${row.gene_symbol}`
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
      {MODEL_LABELS.map((m) => {
        const h = row.headline[m.id];
        return (
          <div
            key={m.id}
            className={`${styles.cell} ${styles.modelCell}`}
            role="cell"
          >
            {h?.verdict ? (
              <span
                className={`${styles.verdictLabel} ${verdictTone(h.verdict)} ${
                  isCorrect(h.verdict, row.truth_verdict)
                    ? styles.verdictCorrect
                    : styles.verdictWrong
                }`}
                title={
                  h.reason
                    ? `${h.verdict} · ${h.reason.replace(/_/g, " ")}${
                        h.confidence ? ` · ${h.confidence} confidence` : ""
                      }`
                    : h.verdict
                }
              >
                {h.verdict}
              </span>
            ) : (
              <span className={styles.dim}>—</span>
            )}
          </div>
        );
      })}
      <div className={`${styles.cell} ${styles.classCell}`} role="cell">
        <span className={styles.classText} title={row.truth_reason.replace(/_/g, " ")}>
          {row.class.replace(/_/g, " ")}
        </span>
      </div>
      {isExpanded ? (
        <div className={styles.expandedBlock}>
          <AltVariantMatrix row={row} altVariants={altVariants} />
        </div>
      ) : null}
    </div>
  );
}

function AltVariantMatrix({
  row,
  altVariants,
}: {
  row: BenchmarkRow;
  altVariants: string[];
}) {
  return (
    <div className={styles.altGrid}>
      <div className={styles.altHeader}>Model</div>
      {altVariants.map((v) => (
        <div key={v} className={styles.altHeader}>
          {v.replace(/_/g, " ")}
        </div>
      ))}
      {MODEL_LABELS.map((m) => (
        <AltVariantRow
          key={m.id}
          modelLabel={m.long}
          model={m.id}
          row={row}
          altVariants={altVariants}
        />
      ))}
    </div>
  );
}

/**
 * Build a wide TSV from the matrix: one row per gene, with the truth
 * label, every per-DB flag, the headline-variant verdict for each
 * model, and every alt-variant verdict for each model. This matches
 * what the table shows (resting + expanded), so anyone analyzing the
 * download in pandas / R gets the same picture without needing to
 * cross-reference the JSON.
 */
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
  // Per-DB flags in the same order as the table columns.
  for (const src of matrix.sources) headers.push(`db_${src}`);
  // Headline-variant columns per model (verdict / reason / confidence /
  // correct / latency_s).
  for (const model of matrix.models) {
    const m = modelSlug(model);
    headers.push(
      `${m}_headline_verdict`,
      `${m}_headline_reason`,
      `${m}_headline_confidence`,
      `${m}_headline_correct`,
      `${m}_headline_latency_s`,
    );
  }
  // Alt-variant columns: per (model × variant), verdict + correct only
  // (keeps the row narrow — readers wanting full detail can request
  // the long-format dump separately).
  for (const model of matrix.models) {
    const m = modelSlug(model);
    for (const variant of matrix.alt_variants) {
      headers.push(`${m}_${variant}_verdict`, `${m}_${variant}_correct`);
    }
  }

  const rows: TsvCell[][] = matrix.rows.map((r) => {
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
      const h: BenchmarkVariantResult | null | undefined = r.headline[model];
      row.push(
        h?.verdict ?? "",
        h?.reason ?? "",
        h?.confidence ?? "",
        h?.correct ?? "",
        h?.latency_s ?? "",
      );
    }
    for (const model of matrix.models) {
      const byVariant = r.alts[model] ?? {};
      for (const variant of matrix.alt_variants) {
        const v: BenchmarkVariantResult | null | undefined = byVariant[variant];
        row.push(v?.verdict ?? "", v?.correct ?? "");
      }
    }
    return row;
  });
  return buildTsv(headers, rows);
}

function modelSlug(modelId: string): string {
  // claude-opus-4-7 → opus, claude-sonnet-4-6 → sonnet, claude-haiku-4-5 → haiku.
  const m = modelId.match(/(opus|sonnet|haiku)/i);
  return m ? m[1].toLowerCase() : modelId.replace(/[^a-z0-9]+/gi, "_");
}

function AltVariantRow({
  modelLabel,
  model,
  row,
  altVariants,
}: {
  modelLabel: string;
  model: string;
  row: BenchmarkRow;
  altVariants: string[];
}) {
  const byVariant = row.alts[model] ?? {};
  return (
    <>
      <div className={styles.altModelLabel}>{modelLabel}</div>
      {altVariants.map((v) => {
        const r: BenchmarkVariantResult | null = byVariant[v] ?? null;
        if (!r?.verdict) {
          return (
            <div key={v} className={styles.altCell}>
              <span className={styles.dim}>—</span>
            </div>
          );
        }
        const correct = isCorrect(r.verdict, row.truth_verdict);
        return (
          <div key={v} className={styles.altCell}>
            <span
              className={`${styles.altPill} ${verdictTone(r.verdict)} ${
                correct ? styles.verdictCorrect : styles.verdictWrong
              }`}
              title={
                r.reason
                  ? `${r.verdict} · ${r.reason.replace(/_/g, " ")}${
                      r.confidence ? ` · ${r.confidence} confidence` : ""
                    }`
                  : r.verdict
              }
            >
              {r.verdict}
            </span>
          </div>
        );
      })}
    </>
  );
}
