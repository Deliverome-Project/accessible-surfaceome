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

/** The deep-dive field used as the headline "verdict" (shown separately
 *  from the other filter fields, mirroring the triage verdict). */
const DEEP_DIVE_VERDICT_KEY = "surface_accessibility";

/** Sentence-case a label: capitalize the first character only. */
function sentenceCase(s: string): string {
  return s.length > 0 ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

/** Enum value → sentence-cased human label (prettyEnum lowercases). */
const prettyCase = (v: string): string => sentenceCase(prettyEnum(v));

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
  /** The deep-dive headline call (surface_accessibility), surfaced on its
   *  own — like the triage verdict — rather than buried in the filter
   *  fields. Null when no matched gene is deep-dived. */
  deepDiveVerdict: EnrichGroup | null;
  /** Multi-valued deep-dive filter enrichment (baseline = deep-dived genes). */
  deepDiveEnumGroups: EnrichGroup[];
  /** Boolean deep-dive flags, one "= yes" row per field (baseline =
   *  deep-dived genes). The complementary "no" is redundant so it's
   *  dropped; collapsed into one table rather than 8 single-row groups. */
  deepDiveBoolFlags: EnrichRow[];
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

/** P(X <= a) — the depletion (lower) tail. */
function hyperTailLE(
  lf: Float64Array,
  N: number,
  K: number,
  draws: number,
  a: number,
): number {
  const denom = logChoose(lf, N, draws);
  if (!Number.isFinite(denom)) return 1;
  const lo = Math.max(0, draws - (N - K));
  let sum = 0;
  for (let i = lo; i <= a; i += 1) {
    const logp = logChoose(lf, K, i) + logChoose(lf, N - K, draws - i) - denom;
    if (Number.isFinite(logp)) sum += Math.exp(logp);
  }
  return Math.min(1, Math.max(0, sum));
}

/**
 * One enrichment row. `a` may be 0 — a value present in the baseline but
 * absent from the list is *depleted* (fold < 1, fold = 0 when a = 0),
 * which is as informative as enrichment, so those rows are kept. The
 * p-value is the one-tailed hypergeometric tail in the direction of the
 * observed deviation: the enrichment tail P(X >= a) when a is at or above
 * the expected count, else the depletion tail P(X <= a).
 */
function makeRow(
  label: string,
  a: number,
  k: number,
  K: number,
  n: number,
  lf: Float64Array,
): EnrichRow {
  // Category declared in the taxonomy but absent from the baseline
  // (K = 0) — nothing to compare against, so fold / p are NaN and render
  // as "—". Still shown (with 0/k) so the full category list is visible.
  if (K === 0) {
    return { label, listHits: a, listTotal: k, baselineHits: 0, baselineTotal: n, fold: NaN, pValue: NaN };
  }
  const fold = n > 0 && k > 0 ? a / k / (K / n) : 0;
  let pValue = 1;
  if (k > 0 && n > 0) {
    const expected = (k * K) / n;
    pValue =
      a >= expected ? hyperTailGE(lf, n, K, k, a) : hyperTailLE(lf, n, K, k, a);
  }
  return { label, listHits: a, listTotal: k, baselineHits: K, baselineTotal: n, fold, pValue };
}

function enrichBinary(
  label: string,
  pop: CatalogRow[],
  listPop: CatalogRow[],
  pred: (r: CatalogRow) => boolean,
  lf: Float64Array,
): EnrichRow {
  let K = 0;
  for (const r of pop) if (pred(r)) K += 1;
  let a = 0;
  for (const r of listPop) if (pred(r)) a += 1;
  return makeRow(label, a, listPop.length, K, pop.length, lf);
}

/**
 * Per-value enrichment for one categorical dimension. `inPop` restricts
 * the baseline population (e.g. deep-dived genes for DD fields); `valueOf`
 * extracts the value (null = excluded). EVERY value present in the
 * baseline population is returned — including values absent from the list
 * (a = 0), which are depleted (fold 0) and just as informative as
 * enriched ones. Sorted by fold desc then count desc (so the default
 * view leads with enrichment and trails into depletion).
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
  allValues?: readonly string[],
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
  // Universe of rows: the declared taxonomy (`allValues`) unioned with any
  // value seen in the data, so EVERY category shows — including ones absent
  // from both the list and the baseline (a = 0, K = 0, rendered "—"). When
  // no taxonomy is supplied, fall back to the values present in the
  // baseline (still surfaces depleted list values).
  const universe =
    allValues && allValues.length
      ? Array.from(new Set<string>([...allValues, ...Kmap.keys()]))
      : Array.from(Kmap.keys());
  const rows = universe.map((v) =>
    makeRow(labelOf(v), amap.get(v) ?? 0, k, Kmap.get(v) ?? 0, n, lf),
  );
  // Sort by fold desc, treating NaN (no-baseline) folds as lowest so they
  // trail the comparable rows; tie-break on list count then label.
  rows.sort((x, y) => {
    const xf = Number.isFinite(x.fold) ? x.fold : -Infinity;
    const yf = Number.isFinite(y.fold) ? y.fold : -Infinity;
    if (yf !== xf) return yf - xf;
    if (y.listHits !== x.listHits) return y.listHits - x.listHits;
    return x.label < y.label ? -1 : x.label > y.label ? 1 : 0;
  });
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
      sentenceCase,
      ["yes", "contextual", "no"],
    ),
    enrichCategory(
      "triage_reason",
      "Triage reason",
      allRows,
      matchedRows,
      (r) => r.triage_by_model[SONNET_IDX]?.reason ?? null,
      always,
      lf,
      prettyCase,
    ),
  ].filter((g) => g.rows.length > 0);

  const hasDdf = (r: CatalogRow) => Boolean(r.deep_dive_filters);
  const ddPop = allRows.filter(hasDdf);
  const ddListPop = matchedRows.filter(hasDdf);

  // Multi-valued enum fields — one sub-table each, showing the FULL
  // declared taxonomy (`f.values`) so every category appears even with no
  // list/baseline match. The headline call (surface_accessibility) is
  // pulled out as `deepDiveVerdict` (shown on its own, like triage
  // verdict); the rest go in the collapsible group list. Drop fields with
  // no baseline data at all.
  let deepDiveVerdict: EnrichGroup | null = null;
  const deepDiveEnumGroups: EnrichGroup[] = [];
  for (const f of DD_ENUM_FIELDS) {
    const isVerdict = f.key === DEEP_DIVE_VERDICT_KEY;
    const g = enrichCategory(
      f.key,
      isVerdict ? "Deep-dive verdict" : f.label,
      allRows,
      matchedRows,
      (r) => (r.deep_dive_filters?.[f.key] as string | undefined) ?? null,
      hasDdf,
      lf,
      prettyCase,
      f.values,
    );
    if (!g.rows.some((row) => row.baselineHits > 0)) continue;
    if (isVerdict) deepDiveVerdict = g;
    else deepDiveEnumGroups.push(g);
  }

  // Boolean flags — one "= yes" row per field (the complementary "no" is
  // redundant). All fields shown, including those no deep-dived gene is
  // positive for (rendered as a no-match "—" row).
  const deepDiveBoolFlags: EnrichRow[] = DD_BOOL_FIELDS.map((f) =>
    enrichBinary(
      f.label,
      ddPop,
      ddListPop,
      (r) => r.deep_dive_filters?.[f.key] === true,
      lf,
    ),
  );
  deepDiveBoolFlags.sort((a, b) => {
    const af = Number.isFinite(a.fold) ? a.fold : -Infinity;
    const bf = Number.isFinite(b.fold) ? b.fold : -Infinity;
    return bf - af || b.listHits - a.listHits;
  });

  return {
    signals,
    catalogGroups,
    deepDiveVerdict,
    deepDiveEnumGroups,
    deepDiveBoolFlags,
    deepDivedListCount: ddListPop.length,
    deepDivedBaselineCount: ddPop.length,
  };
}
