"use client";

import { useMemo, useRef, useState } from "react";
import type { CatalogRow } from "../../lib/surfaceome";
import {
  buildIndex,
  resolveList,
  type ResolvedEntry,
} from "../../lib/compare-match";
import {
  computeCompareStats,
  SONNET_IDX,
  type EnrichRow,
} from "../../lib/compare-stats";
import { DD_BOOL_FIELDS, DD_ENUM_FIELDS } from "../../lib/deep-dive-fields";
import { buildTsv, downloadTextFile, type TsvCell } from "../../lib/tsv";
import { InfoTip } from "../InfoTip/InfoTip";
import styles from "./CompareTool.module.css";

const EXAMPLE_LIST = "EGFR, ERBB2, SRC, CD81, GPR75, P12931, FOObarFAKE";

function fmtPct(x: number): string {
  return `${(x * 100).toFixed(x < 0.01 && x > 0 ? 1 : 0)}%`;
}

function fmtP(p: number): string {
  if (p <= 0) return "0";
  if (p < 1e-4) return p.toExponential(1);
  if (p >= 0.9995) return "1.00";
  return p.toFixed(3);
}

function fmtFold(f: number): string {
  if (!Number.isFinite(f) || f === 0) return "—";
  return `${f.toFixed(f >= 10 ? 0 : 1)}×`;
}

interface CompareToolProps {
  rows: CatalogRow[];
  nRows: number;
  nWithDeepDive: number;
}

export function CompareTool({ rows, nRows, nWithDeepDive }: CompareToolProps) {
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const index = useMemo(() => buildIndex(rows), [rows]);

  const result = useMemo(
    () => (submitted ? resolveList(submitted, index) : null),
    [submitted, index],
  );

  const matchedEntries = useMemo(
    () => (result ? result.entries.filter((e) => e.row) : []),
    [result],
  );
  const notFound = useMemo(
    () => (result ? result.entries.filter((e) => e.matchedBy === "none") : []),
    [result],
  );
  const ambiguous = useMemo(
    () =>
      result ? result.entries.filter((e) => e.matchedBy === "ambiguous") : [],
    [result],
  );

  // Unique genes — two tokens (a symbol and its accession) can resolve to
  // the same row; dedupe so a gene isn't counted twice in the stats.
  const uniqueMatchedRows = useMemo(() => {
    const seen = new Set<string>();
    const out: CatalogRow[] = [];
    for (const e of matchedEntries) {
      const r = e.row;
      if (!r) continue;
      const k = r.uniprot || r.symbol;
      if (seen.has(k)) continue;
      seen.add(k);
      out.push(r);
    }
    return out;
  }, [matchedEntries]);

  const stats = useMemo(
    () => (result ? computeCompareStats(rows, uniqueMatchedRows) : null),
    [result, rows, uniqueMatchedRows],
  );

  function runCompare() {
    setSubmitted(text);
  }

  function loadExample() {
    setText(EXAMPLE_LIST);
    setSubmitted(EXAMPLE_LIST);
  }

  function clearAll() {
    setText("");
    setSubmitted(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const content = String(reader.result ?? "");
      setText(content);
      setSubmitted(content);
    };
    reader.readAsText(file);
  }

  function copyNotFound() {
    const lines = [...notFound, ...ambiguous].map((e) => e.input).join("\n");
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(lines).then(
        () => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1800);
        },
        () => undefined,
      );
    }
  }

  function downloadMatches() {
    if (matchedEntries.length === 0) return;
    downloadTextFile(
      `surfaceome-compare-${uniqueMatchedRows.length}-genes.tsv`,
      buildCompareTsv(matchedEntries),
    );
  }

  const uploadedCount = result ? result.entries.length : 0;
  // Inputs that matched a gene already counted under a different
  // identifier (e.g. a UniProt accession + its gene symbol both pasted).
  // Surfaced so "uploaded" reconciles with "matched genes" + not-found.
  const redundantMatches = matchedEntries.length - uniqueMatchedRows.length;

  return (
    <div className={styles.wrap}>
      {/* ---- Input ------------------------------------------------- */}
      <div className={styles.inputCard}>
        <label htmlFor="compare-input" className={styles.inputLabel}>
          Paste gene symbols or UniProt accessions
          <span className={styles.inputHint}>
            One per line, or separated by commas / spaces / tabs. Old
            (previous) gene symbols are matched too.
          </span>
        </label>
        <textarea
          id="compare-input"
          className={styles.textarea}
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          spellCheck={false}
          placeholder={"EGFR\nERBB2\nCD81\nP12931"}
        />
        <div className={styles.inputActions}>
          <button
            type="button"
            className={styles.primaryBtn}
            onClick={runCompare}
            disabled={text.trim().length === 0}
          >
            Compare
          </button>
          <label className={styles.fileBtn}>
            Upload file
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.txt,.tsv"
              onChange={onFile}
              className={styles.fileInput}
            />
          </label>
          <button type="button" className={styles.ghostBtn} onClick={loadExample}>
            Try an example
          </button>
          {submitted ? (
            <button type="button" className={styles.ghostBtn} onClick={clearAll}>
              Clear
            </button>
          ) : null}
          <span className={styles.universeNote}>
            Compared against {nRows.toLocaleString()} genes. Your list stays
            in your browser.
          </span>
        </div>
      </div>

      {result && stats ? (
        <>
          {/* ---- Summary ------------------------------------------- */}
          <div className={styles.summary}>
            <div className={styles.coverageRow}>
              <Stat label="Uploaded" value={uploadedCount} />
              <Stat label="Matched genes" value={uniqueMatchedRows.length} />
              <Stat
                label="Not found"
                value={notFound.length}
                tone={notFound.length > 0 ? "warn" : undefined}
              />
              {ambiguous.length > 0 ? (
                <Stat label="Ambiguous" value={ambiguous.length} tone="warn" />
              ) : null}
              {redundantMatches > 0 ? (
                <Stat label="Same gene, other ID" value={redundantMatches} />
              ) : null}
              {result.duplicateCount > 0 ? (
                <Stat
                  label="Duplicates collapsed"
                  value={result.duplicateCount}
                />
              ) : null}
            </div>

            {/* Download — the per-protein detail lives in the TSV. */}
            {matchedEntries.length > 0 ? (
              <div className={styles.downloadRow}>
                <span className={styles.downloadMeta}>
                  Per-protein detail (DB votes, triage call, all deep-dive
                  filters) for your {matchedEntries.length} matched
                  {matchedEntries.length === 1 ? " row" : " rows"} →
                </span>
                <button
                  type="button"
                  className={styles.primaryBtn}
                  onClick={downloadMatches}
                >
                  Download matches (TSV) ↓
                </button>
              </div>
            ) : (
              <p className={styles.emptyMatched}>
                None of your inputs matched a gene in the catalog.
              </p>
            )}
          </div>

          {/* ---- Catalog-wide enrichment --------------------------- */}
          {uniqueMatchedRows.length > 0 ? (
            <div className={styles.summary}>
              <p className={`label-mono ${styles.blockHead}`}>
                Enrichment vs the full catalog
                <InfoTip label="About enrichment">
                  For each signal: the share of your matched genes carrying
                  it, vs the share across all {nRows.toLocaleString()} catalog
                  genes, the fold-enrichment, and a one-tailed hypergeometric
                  p-value. Signals are correlated (DB votes co-occur, verdict
                  tracks DB count), so the p-values are descriptive, not
                  multiple-testing-corrected, and only matched genes are
                  tested.
                </InfoTip>
              </p>
              <EnrichTable rows={stats.signals} firstCol="Signal" />

              {stats.catalogGroups.map((g) => (
                <div key={g.key} className={styles.enrichGroup}>
                  <span className={styles.enrichGroupLabel}>{g.label}</span>
                  <EnrichTable rows={g.rows} firstCol="Value" />
                </div>
              ))}
            </div>
          ) : null}

          {/* ---- Deep-dive filter enrichment ----------------------- */}
          {stats.deepDivedListCount > 0 && stats.deepDiveGroups.length > 0 ? (
            <div className={styles.summary}>
              <p className={`label-mono ${styles.blockHead}`}>
                Deep-dive filter enrichment · {stats.deepDivedListCount} of
                your genes deep-dived
                <InfoTip label="About deep-dive filter enrichment">
                  Deep-dive filters exist only on deep-dived genes, a curated
                  non-random subset, so these test your {stats.deepDivedListCount}{" "}
                  deep-dived matches against the{" "}
                  {stats.deepDivedBaselineCount.toLocaleString()} deep-dived
                  catalog genes (not the whole catalog). Underpowered on small
                  lists — read the fold + counts descriptively.
                </InfoTip>
              </p>
              {stats.deepDiveGroups.map((g) => (
                <div key={g.key} className={styles.enrichGroup}>
                  <span className={styles.enrichGroupLabel}>{g.label}</span>
                  <EnrichTable rows={g.rows} firstCol="Value" baseline="deep-dived" />
                </div>
              ))}
            </div>
          ) : null}

          {/* ---- Unresolved ---------------------------------------- */}
          {notFound.length + ambiguous.length > 0 ? (
            <div className={styles.notFoundCard}>
              <div className={styles.notFoundHead}>
                <p className={`label-mono ${styles.blockHead}`}>
                  Unresolved · {notFound.length + ambiguous.length}
                </p>
                <div className={styles.notFoundActions}>
                  <button
                    type="button"
                    className={styles.ghostBtn}
                    onClick={copyNotFound}
                  >
                    {copied ? "Copied" : "Copy"}
                  </button>
                  <button
                    type="button"
                    className={styles.ghostBtn}
                    onClick={() =>
                      downloadTextFile(
                        "compare-not-found.txt",
                        [...notFound, ...ambiguous]
                          .map((e) => e.input)
                          .join("\n") + "\n",
                        "text/plain",
                      )
                    }
                  >
                    Download
                  </button>
                </div>
              </div>
              {ambiguous.length > 0 ? (
                <p className={styles.unresolvedNote}>
                  {ambiguous.length} input
                  {ambiguous.length === 1 ? "" : "s"} matched a synonym shared
                  by multiple genes and weren&rsquo;t auto-resolved — search
                  the catalog by the canonical symbol instead.
                </p>
              ) : null}
              <ul className={styles.tokenList}>
                {notFound.map((e, i) => (
                  <li key={`nf-${i}`} className={styles.token}>
                    {e.input}
                  </li>
                ))}
                {ambiguous.map((e, i) => (
                  <li
                    key={`amb-${i}`}
                    className={`${styles.token} ${styles.tokenAmbiguous}`}
                    title="Synonym maps to multiple genes"
                  >
                    {e.input}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : (
        <p className={styles.placeholder}>
          Paste a list above and hit <strong>Compare</strong> to see which
          source databases, triage calls, and deep-dive filters are enriched
          in your set — and download a per-protein TSV.{" "}
          {nWithDeepDive.toLocaleString()} of the {nRows.toLocaleString()}{" "}
          catalog genes have a deep-dive record.
        </p>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "warn";
}) {
  return (
    <div className={styles.stat}>
      <span
        className={`${styles.statValue} ${tone === "warn" ? styles.statWarn : ""}`}
      >
        {value.toLocaleString()}
      </span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  );
}

function EnrichTable({
  rows,
  firstCol,
  baseline = "catalog",
}: {
  rows: EnrichRow[];
  firstCol: string;
  baseline?: "catalog" | "deep-dived";
}) {
  if (rows.length === 0) return null;
  return (
    <div className={styles.enrichTable}>
      <div className={`${styles.enrichRow} ${styles.enrichHead}`}>
        <span>{firstCol}</span>
        <span className={styles.num}>Your list</span>
        <span className={styles.num}>
          {baseline === "deep-dived" ? "Deep-dived" : "Catalog"}
        </span>
        <span className={styles.num}>Fold</span>
        <span className={styles.num}>p</span>
      </div>
      {rows.map((r) => {
        const listRate = r.listTotal > 0 ? r.listHits / r.listTotal : 0;
        const baselineRate =
          r.baselineTotal > 0 ? r.baselineHits / r.baselineTotal : 0;
        const enriched = r.fold >= 2 && r.pValue < 0.05;
        return (
          <div key={r.label} className={styles.enrichRow}>
            <span className={styles.enrichLabel}>{r.label}</span>
            <span className={styles.num}>
              {fmtPct(listRate)}
              <span className={styles.numSub}>
                {" "}
                {r.listHits}/{r.listTotal}
              </span>
            </span>
            <span className={`${styles.num} ${styles.muted}`}>
              {fmtPct(baselineRate)}
            </span>
            <span className={`${styles.num} ${enriched ? styles.foldHot : ""}`}>
              {fmtFold(r.fold)}
            </span>
            <span className={`${styles.num} ${styles.muted}`}>
              {fmtP(r.pValue)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * TSV of the matched genes — one row per matched input token, with the
 * DB votes, triage call, deep-dive flag, and the 21 DeepDiveFilters
 * (blank when the gene wasn't deep-dived).
 */
function buildCompareTsv(entries: ResolvedEntry[]): string {
  const headers = [
    "input",
    "matched_by",
    "matched_symbol",
    "uniprot_acc",
    "n_sources",
    "db_uniprot",
    "db_go",
    "db_surfy",
    "db_cspa",
    "db_hpa",
    "triage_verdict",
    "triage_reason",
    "deep_dive",
    ...DD_ENUM_FIELDS.map((f) => f.key),
    ...DD_BOOL_FIELDS.map((f) => f.key),
  ];
  const body: TsvCell[][] = entries.map((e) => {
    const r = e.row;
    const triage = r?.triage_by_model[SONNET_IDX];
    const ddf = r?.deep_dive ? r.deep_dive_filters : undefined;
    return [
      e.input,
      e.matchedBy,
      r?.symbol ?? "",
      r?.uniprot ?? "",
      r ? r.n_sources : "",
      r ? r.db.uniprot : "",
      r ? r.db.go : "",
      r ? r.db.surfy : "",
      r ? r.db.cspa : "",
      r ? r.db.hpa : "",
      triage?.verdict ?? "",
      triage?.reason ?? "",
      r ? (r.deep_dive ? 1 : 0) : "",
      ...DD_ENUM_FIELDS.map((f) =>
        ddf ? ((ddf[f.key] as string | undefined) ?? "") : "",
      ),
      ...DD_BOOL_FIELDS.map((f) => {
        if (!ddf) return "";
        const v = ddf[f.key] as boolean | undefined;
        return typeof v === "boolean" ? (v ? 1 : 0) : "";
      }),
    ];
  });
  return buildTsv(headers, body);
}
