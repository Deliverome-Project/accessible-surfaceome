/**
 * Enrichment tests for the /compare upload tool — all computed
 * client-side over the in-memory catalog.
 *
 * Every dimension the catalog filter panel exposes gets a one-tailed
 * hypergeometric enrichment test (fold + p) of the user's matched genes
 * against a baseline:
 *
 *  • BINARY catalog signals (the 5 DBs, "≥3 DB sources") and CATEGORICAL
 *    catalog signals (triage verdict, triage reason) are FULL-coverage —
 *    every catalog row carries them — so the baseline is the whole
 *    catalog.
 *  • DEEP-DIVE filter fields (13 categorical + 8 boolean) exist only on
 *    deep-dived genes, a curated non-random subset, so the baseline is
 *    the deep-dived population (not the whole catalog) and the test asks
 *    "among deep-dived genes, is the list's deep-dived subset enriched
 *    for this value." Underpowered on small lists — read descriptively.
 *
 * p-values are descriptive, not multiple-testing-corrected: the signals
 * are correlated (DB votes co-occur, verdict tracks DB count) and only
 * matched genes are tested.
 */

import type { CatalogRow } from "./surfaceome";
import { prettyEnum } from "./enums";
import { DD_BOOL_FIELDS, DD_ENUM_FIELDS } from "./deep-dive-fields";

/** Sonnet slot in the catalog `triage_by_model` array (Haiku=0,
 *  Sonnet=1, Opus=2) — the only model with full-genome coverage. */
export const SONNET_IDX = 1;

export interface EnrichRow {
  label: string;
  listHits: number; // a — list genes positive for this value
  listTotal: number; // k — list genes in the baseline population
  baselineHits: number; // K — population genes positive
  baselineTotal: number; // n — population size
  fold: number; // (a/k) / (K/n)
  pValue: number; // one-tailed hypergeometric P(X >= a)
}

export interface EnrichGroup {
  key: string;
  label: string;
  rows: EnrichRow[];
}

export interface CompareStats {
  /** Binary catalog-wide signals: 5 DBs + "≥3 DB sources". */
  signals: EnrichRow[];
  /** Categorical catalog-wide enrichment: triage verdict, triage reason. */
  catalogGroups: EnrichGroup[];
  /** Deep-dive-filter enrichment (baseline = deep-dived genes). */
  deepDiveGroups: EnrichGroup[];
  /** Matched genes that carry deep_dive_filters. */
  deepDivedListCount: number;
  /** Catalog genes that carry deep_dive_filters (the DD baseline size). */
  deepDivedBaselineCount: number;
}

// --- hypergeometric tail via log-factorials -------------------------------

function makeLogFact(maxN: number): Float64Array {
  const lf = new Float64Array(maxN + 1);
  let acc = 0;
  for (let i = 1; i <= maxN; i += 1) {
    acc += Math.log(i);
    lf[i] = acc;
  }
  return lf;
}

function logChoose(lf: Float64Array, n: number, k: number): number {
  if (k < 0 || k > n) return -Infinity;
  return lf[n] - lf[k] - lf[n - k];
}

/** P(X >= a) for X ~ Hypergeometric(N population, K successes, draws). */
function hyperTailGE(
  lf: Float64Array,
  N: number,
  K: number,
  draws: number,
  a: number,
): number {
  const denom = logChoose(lf, N, draws);
  if (!Number.isFinite(denom)) return 1;
  const hi = Math.min(K, draws);
  let sum = 0;
  for (let i = Math.max(0, a); i <= hi; i += 1) {
    const logp = logChoose(lf, K, i) + logChoose(lf, N - K, draws - i) - denom;
    if (Number.isFinite(logp)) sum += Math.exp(logp);
  }
  return Math.min(1, Math.max(0, sum));
}

function makeRow(
  label: string,
  a: number,
  k: number,
  K: number,
  n: number,
  lf: Float64Array,
): EnrichRow {
  const fold = n > 0 && k > 0 && K > 0 ? a / k / (K / n) : 0;
  const pValue = k > 0 && K > 0 ? hyperTailGE(lf, n, K, k, a) : 1;
  return { label, listHits: a, listTotal: k, baselineHits: K, baselineTotal: n, fold, pValue };
}

function enrichBinary(
  label: string,
  allRows: CatalogRow[],
  matchedRows: CatalogRow[],
  pred: (r: CatalogRow) => boolean,
  lf: Float64Array,
): EnrichRow {
  let K = 0;
  for (const r of allRows) if (pred(r)) K += 1;
  let a = 0;
  for (const r of matchedRows) if (pred(r)) a += 1;
  return makeRow(label, a, matchedRows.length, K, allRows.length, lf);
}

/**
 * Per-value enrichment for one categorical dimension. `inPop` restricts
 * the baseline population (e.g. deep-dived genes for DD fields); `valueOf`
 * extracts the value (null = excluded). Only values present in the list
 * (a >= 1) are returned, sorted by fold desc then count desc.
 */
function enrichCategory(
  key: string,
  label: string,
  allRows: CatalogRow[],
  matchedRows: CatalogRow[],
  valueOf: (r: CatalogRow) => string | null,
  inPop: (r: CatalogRow) => boolean,
  lf: Float64Array,
  labelOf: (v: string) => string = (v) => v,
): EnrichGroup {
  const pop = allRows.filter(inPop);
  const listPop = matchedRows.filter(inPop);
  const n = pop.length;
  const k = listPop.length;
  const Kmap = new Map<string, number>();
  for (const r of pop) {
    const v = valueOf(r);
    if (v != null) Kmap.set(v, (Kmap.get(v) ?? 0) + 1);
  }
  const amap = new Map<string, number>();
  for (const r of listPop) {
    const v = valueOf(r);
    if (v != null) amap.set(v, (amap.get(v) ?? 0) + 1);
  }
  const rows: EnrichRow[] = [];
  for (const [v, a] of amap) {
    rows.push(makeRow(labelOf(v), a, k, Kmap.get(v) ?? 0, n, lf));
  }
  rows.sort((x, y) => y.fold - x.fold || y.listHits - x.listHits);
  return { key, label, rows };
}

export function computeCompareStats(
  allRows: CatalogRow[],
  matchedRows: CatalogRow[],
): CompareStats {
  const lf = makeLogFact(Math.max(allRows.length, 1));

  const signals: EnrichRow[] = [
    enrichBinary("UniProt", allRows, matchedRows, (r) => Boolean(r.db.uniprot), lf),
    enrichBinary("GO", allRows, matchedRows, (r) => Boolean(r.db.go), lf),
    enrichBinary("SURFY", allRows, matchedRows, (r) => Boolean(r.db.surfy), lf),
    enrichBinary("CSPA", allRows, matchedRows, (r) => Boolean(r.db.cspa), lf),
    enrichBinary("HPA", allRows, matchedRows, (r) => Boolean(r.db.hpa), lf),
    enrichBinary("≥3 DB sources", allRows, matchedRows, (r) => r.n_sources >= 3, lf),
  ];

  const always = () => true;
  const catalogGroups = [
    enrichCategory(
      "triage_verdict",
      "Triage verdict",
      allRows,
      matchedRows,
      (r) => r.triage_by_model[SONNET_IDX]?.verdict ?? null,
      always,
      lf,
    ),
    enrichCategory(
      "triage_reason",
      "Triage reason",
      allRows,
      matchedRows,
      (r) => r.triage_by_model[SONNET_IDX]?.reason ?? null,
      always,
      lf,
      prettyEnum,
    ),
  ].filter((g) => g.rows.length > 0);

  const hasDdf = (r: CatalogRow) => Boolean(r.deep_dive_filters);
  const deepDiveGroups: EnrichGroup[] = [];
  for (const f of DD_ENUM_FIELDS) {
    const g = enrichCategory(
      f.key,
      f.label,
      allRows,
      matchedRows,
      (r) => (r.deep_dive_filters?.[f.key] as string | undefined) ?? null,
      hasDdf,
      lf,
      prettyEnum,
    );
    if (g.rows.length) deepDiveGroups.push(g);
  }
  for (const f of DD_BOOL_FIELDS) {
    const g = enrichCategory(
      f.key,
      f.label,
      allRows,
      matchedRows,
      (r) => {
        const v = r.deep_dive_filters?.[f.key] as boolean | undefined;
        return v == null ? null : v ? "yes" : "no";
      },
      hasDdf,
      lf,
    );
    if (g.rows.length) deepDiveGroups.push(g);
  }

  return {
    signals,
    catalogGroups,
    deepDiveGroups,
    deepDivedListCount: matchedRows.filter(hasDdf).length,
    deepDivedBaselineCount: allRows.filter(hasDdf).length,
  };
}
