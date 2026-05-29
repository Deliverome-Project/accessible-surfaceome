"use client";

import { useMemo, useRef, useState } from "react";
import type { CatalogRow } from "../../lib/surfaceome";
import { prettyEnum } from "../../lib/enums";
import {
  buildIndex,
  resolveList,
  type MatchedBy,
  type ResolvedEntry,
} from "../../lib/compare-match";
import {
  computeDdDistribution,
  computeEnrichment,
  SONNET_IDX,
  type SignalEnrichment,
} from "../../lib/compare-stats";
import { DD_BOOL_FIELDS, DD_ENUM_FIELDS } from "../../lib/deep-dive-fields";
import { buildTsv, downloadTextFile, type TsvCell } from "../../lib/tsv";
import { InfoTip } from "../InfoTip/InfoTip";
import { StatusPill } from "../surfaceome/StatusPill/StatusPill";
import styles from "./CompareTool.module.css";

const DB_KEYS: { key: keyof CatalogRow["db"]; long: string }[] = [
  { key: "uniprot", long: "UniProt" },
  { key: "go", long: "GO" },
  { key: "surfy", long: "SURFY" },
  { key: "cspa", long: "CSPA" },
  { key: "hpa", long: "HPA" },
];

const GRID_TEMPLATE =
  "9rem 9rem 3.4rem 1.6rem 1.6rem 1.6rem 1.6rem 1.6rem 6.5rem minmax(7rem, 1fr) 4rem 2rem";

const EXAMPLE_LIST = "EGFR, ERBB2, SRC, CD81, GPR75, P12931, FOObarFAKE";

function verdictTone(
  v: string | null | undefined,
): "success" | "maroon" | "amber" | "neutral" {
  if (v === "yes") return "success";
  if (v === "no") return "maroon";
  if (v === "contextual") return "amber";
  return "neutral";
}

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
  const [expanded, setExpanded] = useState<string | null>(null);
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

  // Unique genes (two tokens — a symbol and its accession — can resolve to
  // the same row; dedupe for the set-level stats so a gene isn't counted
  // twice). The per-input table still shows every token.
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

  const enrichment = useMemo<SignalEnrichment[]>(
    () => (result ? computeEnrichment(rows, uniqueMatchedRows) : []),
    [result, rows, uniqueMatchedRows],
  );

  const ddDist = useMemo(
    () => (result ? computeDdDistribution(uniqueMatchedRows) : null),
    [result, uniqueMatchedRows],
  );

  function runCompare() {
    setSubmitted(text);
    setExpanded(null);
  }

  function loadExample() {
    setText(EXAMPLE_LIST);
    setSubmitted(EXAMPLE_LIST);
    setExpanded(null);
  }

  function clearAll() {
    setText("");
    setSubmitted(null);
    setExpanded(null);
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
      setExpanded(null);
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

  function downloadResults() {
    if (!result) return;
    downloadTextFile(
      `surfaceome-compare-${uniqueMatchedRows.length}-genes.tsv`,
      buildCompareTsv(result.entries),
    );
  }

  const gridStyle: React.CSSProperties = {
    ["--compare-cols" as string]: GRID_TEMPLATE,
  };

  const uploadedCount = result ? result.entries.length : 0;

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

      {result ? (
        <>
          {/* ---- Summary + enrichment ------------------------------ */}
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
              {result.duplicateCount > 0 ? (
                <Stat
                  label="Duplicates collapsed"
                  value={result.duplicateCount}
                />
              ) : null}
            </div>

            {uniqueMatchedRows.length > 0 ? (
              <div className={styles.enrichBlock}>
                <p className={`label-mono ${styles.blockHead}`}>
                  Enrichment vs the full catalog
                  <InfoTip label="About enrichment">
                    For each signal: the share of your matched genes that
                    carry it, vs the share across all {nRows.toLocaleString()}{" "}
                    catalog genes, the fold-enrichment, and a one-tailed
                    hypergeometric p-value. Signals are correlated (DB votes
                    co-occur), so the p-values are descriptive, not
                    multiple-testing-corrected, and only matched genes are
                    tested.
                  </InfoTip>
                </p>
                <div className={styles.enrichTable}>
                  <div className={`${styles.enrichRow} ${styles.enrichHead}`}>
                    <span>Signal</span>
                    <span className={styles.num}>Your list</span>
                    <span className={styles.num}>Catalog</span>
                    <span className={styles.num}>Fold</span>
                    <span className={styles.num}>p</span>
                  </div>
                  {enrichment.map((s) => {
                    const enriched = s.fold >= 2 && s.pValue < 0.05;
                    return (
                      <div key={s.key} className={styles.enrichRow}>
                        <span className={styles.enrichLabel}>{s.label}</span>
                        <span className={styles.num}>
                          {fmtPct(s.listRate)}
                          <span className={styles.numSub}>
                            {" "}
                            {s.listHits}/{s.listTotal}
                          </span>
                        </span>
                        <span className={`${styles.num} ${styles.muted}`}>
                          {fmtPct(s.baselineRate)}
                        </span>
                        <span
                          className={`${styles.num} ${enriched ? styles.foldHot : ""}`}
                        >
                          {fmtFold(s.fold)}
                        </span>
                        <span className={`${styles.num} ${styles.muted}`}>
                          {fmtP(s.pValue)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {ddDist && ddDist.deepDivedCount > 0 ? (
              <div className={styles.enrichBlock}>
                <p className={`label-mono ${styles.blockHead}`}>
                  Deep-dive filters · {ddDist.deepDivedCount} deep-dived
                  {ddDist.deepDivedCount === 1 ? " gene" : " genes"} in your
                  list
                  <InfoTip label="About deep-dive filter counts">
                    Deep-dived genes are a curated, non-random subset, so
                    these are descriptive value counts over your{" "}
                    {ddDist.deepDivedCount} deep-dived matches — not
                    statistical enrichment.
                  </InfoTip>
                </p>
                <div className={styles.ddGrid}>
                  {ddDist.enums.map((f) => (
                    <div key={f.key} className={styles.ddField}>
                      <span className={styles.ddFieldLabel}>{f.label}</span>
                      <span className={styles.ddCounts}>
                        {f.counts.map((c) => (
                          <span key={c.value} className={styles.ddCount}>
                            {prettyEnum(c.value)}
                            <span className={styles.ddCountN}>{c.n}</span>
                          </span>
                        ))}
                      </span>
                    </div>
                  ))}
                  {ddDist.bools.map((f) => (
                    <div key={f.key} className={styles.ddField}>
                      <span className={styles.ddFieldLabel}>{f.label}</span>
                      <span className={styles.ddCounts}>
                        <span className={styles.ddCount}>
                          true<span className={styles.ddCountN}>{f.trueN}</span>
                        </span>
                        <span className={styles.ddCount}>
                          false
                          <span className={styles.ddCountN}>{f.falseN}</span>
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          {/* ---- Results table ------------------------------------- */}
          {matchedEntries.length > 0 ? (
            <div className={styles.resultsCard} style={gridStyle}>
              <div className={styles.resultsTopBar}>
                <p className={styles.resultsMeta}>
                  {matchedEntries.length} matched{" "}
                  {matchedEntries.length === 1 ? "row" : "rows"}
                </p>
                <button
                  type="button"
                  className={styles.downloadBtn}
                  onClick={downloadResults}
                  title="Download all results (matched + not-found) as TSV"
                >
                  TSV ↓
                </button>
              </div>
              <div className={styles.tableScroll} role="table">
                <div className={`${styles.headerRow} ${styles.row}`} role="row">
                  <span className={styles.headerCell}>Input</span>
                  <span className={styles.headerCell}>Matched</span>
                  <span className={`${styles.headerCell} ${styles.center}`}>
                    Votes
                  </span>
                  {DB_KEYS.map((d) => (
                    <span
                      key={d.key}
                      className={`${styles.headerCell} ${styles.center} ${styles.dbHead}`}
                      title={d.long}
                    >
                      {d.long}
                    </span>
                  ))}
                  <span className={`${styles.headerCell} ${styles.center}`}>
                    Triage
                  </span>
                  <span className={styles.headerCell}>Reason</span>
                  <span className={`${styles.headerCell} ${styles.center}`}>
                    Deep dive
                  </span>
                  <span className={styles.headerCell} aria-hidden="true" />
                </div>
                {matchedEntries.map((e, i) => (
                  <CompareRow
                    key={`${e.input}-${i}`}
                    entry={e}
                    expanded={expanded === `${e.input}-${i}`}
                    onToggle={() =>
                      setExpanded((prev) =>
                        prev === `${e.input}-${i}` ? null : `${e.input}-${i}`,
                      )
                    }
                  />
                ))}
              </div>
            </div>
          ) : (
            <p className={styles.emptyMatched}>
              None of your inputs matched a gene in the catalog.
            </p>
          )}

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
          Paste a list above and hit <strong>Compare</strong> to see how each
          protein scores across the five source databases, the triage call,
          and (where available) the deep-dive filters — plus which signals are
          enriched in your set. {nWithDeepDive.toLocaleString()} of the{" "}
          {nRows.toLocaleString()} catalog genes have a deep-dive record.
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

function matchedByBadge(matchedBy: MatchedBy, canonical: string) {
  if (matchedBy === "uniprot") {
    return (
      <StatusPill tone="lavender" size="sm" title={`Matched by UniProt accession → ${canonical}`}>
        via UniProt
      </StatusPill>
    );
  }
  if (matchedBy === "synonym") {
    return (
      <StatusPill tone="amber" size="sm" title={`Matched via an old / previous symbol → ${canonical}`}>
        old symbol
      </StatusPill>
    );
  }
  return null;
}

function CompareRow({
  entry,
  expanded,
  onToggle,
}: {
  entry: ResolvedEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  const row = entry.row;
  if (!row) return null;
  const triage = row.triage_by_model[SONNET_IDX];
  const reason = triage?.reason ? triage.reason.replace(/_/g, " ") : null;
  const ddf = row.deep_dive ? row.deep_dive_filters : undefined;
  const canExpand = Boolean(ddf);
  const badge = matchedByBadge(entry.matchedBy, row.symbol);
  return (
    <>
      <div className={styles.row} role="row">
        <span className={`${styles.cell} ${styles.mono}`}>{entry.input}</span>
        <span className={`${styles.cell} ${styles.matchedCell}`}>
          {row.deep_dive ? (
            <a className={styles.matchedLink} href={`/${row.symbol}/`}>
              {row.symbol}
            </a>
          ) : (
            <span className={styles.mono}>{row.symbol}</span>
          )}
          {badge}
        </span>
        <span className={`${styles.cell} ${styles.center}`}>
          <span className={styles.nBubble} data-n={row.n_sources}>
            {row.n_sources}
          </span>
        </span>
        {DB_KEYS.map((d) => {
          const yes = Boolean(row.db[d.key]);
          return (
            <span
              key={d.key}
              className={`${styles.cell} ${styles.center} ${styles.dbCell} ${yes ? styles.dbCellYes : ""}`}
              aria-label={`${d.long}: ${yes ? "yes" : "no"}`}
            >
              <span className={styles.dbDot} aria-hidden="true" />
            </span>
          );
        })}
        <span className={`${styles.cell} ${styles.center}`}>
          {triage ? (
            <StatusPill tone={verdictTone(triage.verdict)} size="sm">
              {triage.verdict}
            </StatusPill>
          ) : (
            <span className={styles.dim}>—</span>
          )}
        </span>
        <span className={`${styles.cell} ${styles.reasonCell}`}>
          {reason ? (
            <span className={styles.reasonText} title={reason}>
              {reason}
            </span>
          ) : (
            <span className={styles.dim}>—</span>
          )}
        </span>
        <span className={`${styles.cell} ${styles.center}`}>
          {row.deep_dive ? (
            <a
              className={styles.deepLink}
              href={`/${row.symbol}/`}
              title={`Open the deep-dive record for ${row.symbol}`}
            >
              yes
            </a>
          ) : (
            <span className={styles.dim}>—</span>
          )}
        </span>
        <span className={`${styles.cell} ${styles.center}`}>
          {canExpand ? (
            <button
              type="button"
              className={styles.expandBtn}
              onClick={onToggle}
              aria-expanded={expanded}
              aria-label={`${expanded ? "Hide" : "Show"} deep-dive filters for ${row.symbol}`}
            >
              {expanded ? "▾" : "▸"}
            </button>
          ) : null}
        </span>
      </div>
      {expanded && ddf ? (
        <div className={styles.detail} role="row">
          <dl className={styles.detailGrid}>
            {DD_ENUM_FIELDS.map((f) => {
              const v = ddf[f.key] as string | undefined;
              if (v == null) return null;
              return (
                <div key={f.key} className={styles.detailItem}>
                  <dt className={styles.detailLabel}>{f.label}</dt>
                  <dd className={styles.detailValue}>{prettyEnum(v)}</dd>
                </div>
              );
            })}
            {DD_BOOL_FIELDS.map((f) => {
              const v = ddf[f.key] as boolean | undefined;
              if (typeof v !== "boolean") return null;
              return (
                <div key={f.key} className={styles.detailItem}>
                  <dt className={styles.detailLabel}>{f.label}</dt>
                  <dd className={styles.detailValue}>{v ? "yes" : "no"}</dd>
                </div>
              );
            })}
          </dl>
        </div>
      ) : null}
    </>
  );
}

/**
 * TSV of the compare results — one row per input token (matched or not),
 * matching the table columns plus the 21 DeepDiveFilters (blank when the
 * gene wasn't deep-dived).
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
