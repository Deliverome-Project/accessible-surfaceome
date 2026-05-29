/**
 * Enrichment + distribution stats for the /compare upload tool — all
 * computed client-side over the in-memory catalog.
 *
 * Two kinds of readout:
 *  1. FULL-coverage signals (the 5 DBs, the triage-agent surface call,
 *     and "≥3 DB sources"): every catalog row carries these, so we
 *     report the list rate vs the whole-catalog baseline rate, the
 *     fold-enrichment, and a one-tailed hypergeometric p-value. The
 *     p-values are descriptive, not multiple-testing-corrected — the
 *     signals are correlated (DB votes co-occur) and only matched genes
 *     are tested.
 *  2. PARTIAL-coverage DeepDiveFilters: present only on deep-dived
 *     genes (a curated, non-random subset), so we show value-distribution
 *     counts over the matched-and-deep-dived rows — NOT a p-value.
 */

import type { CatalogRow, DeepDiveFilters } from "./surfaceome";
import {
  DD_BOOL_FIELDS,
  DD_ENUM_FIELDS,
  type DdBoolKey,
  type DdEnumKey,
} from "./deep-dive-fields";

/** Sonnet slot in the catalog `triage_by_model` array (Haiku=0,
 *  Sonnet=1, Opus=2 per the Worker contract). The triage agent is the
 *  only model with full-genome coverage. */
export const SONNET_IDX = 1;

export interface SignalEnrichment {
  key: string;
  label: string;
  listHits: number; // a — matched rows positive for this signal
  listTotal: number; // k — matched rows
  baselineHits: number; // K — catalog rows positive
  baselineTotal: number; // n — catalog rows
  listRate: number; // a / k
  baselineRate: number; // K / n
  fold: number; // listRate / baselineRate
  pValue: number; // one-tailed hypergeometric P(X >= a)
}

type RowPredicate = (r: CatalogRow) => boolean;

const SIGNALS: { key: string; label: string; pred: RowPredicate }[] = [
  { key: "uniprot", label: "UniProt", pred: (r) => Boolean(r.db.uniprot) },
  { key: "go", label: "GO", pred: (r) => Boolean(r.db.go) },
  { key: "surfy", label: "SURFY", pred: (r) => Boolean(r.db.surfy) },
  { key: "cspa", label: "CSPA", pred: (r) => Boolean(r.db.cspa) },
  { key: "hpa", label: "HPA", pred: (r) => Boolean(r.db.hpa) },
  {
    key: "triage_surface",
    label: "Triage call: surface",
    pred: (r) => r.triage_by_model[SONNET_IDX]?.verdict === "yes",
  },
  { key: "n_sources_ge3", label: "≥3 DB sources", pred: (r) => r.n_sources >= 3 },
];

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
    const logp =
      logChoose(lf, K, i) + logChoose(lf, N - K, draws - i) - denom;
    if (Number.isFinite(logp)) sum += Math.exp(logp);
  }
  return Math.min(1, Math.max(0, sum));
}

export function computeEnrichment(
  allRows: CatalogRow[],
  matchedRows: CatalogRow[],
): SignalEnrichment[] {
  const n = allRows.length;
  const k = matchedRows.length;
  const lf = makeLogFact(Math.max(n, 1));
  return SIGNALS.map((s) => {
    let K = 0;
    for (const r of allRows) if (s.pred(r)) K += 1;
    let a = 0;
    for (const r of matchedRows) if (s.pred(r)) a += 1;
    const listRate = k > 0 ? a / k : 0;
    const baselineRate = n > 0 ? K / n : 0;
    const fold = baselineRate > 0 ? listRate / baselineRate : 0;
    const pValue = k > 0 && K > 0 ? hyperTailGE(lf, n, K, k, a) : 1;
    return {
      key: s.key,
      label: s.label,
      listHits: a,
      listTotal: k,
      baselineHits: K,
      baselineTotal: n,
      listRate,
      baselineRate,
      fold,
      pValue,
    };
  });
}

// --- DeepDiveFilters value distribution (descriptive, no p-value) ---------

export interface DdEnumDistribution {
  key: DdEnumKey;
  label: string;
  counts: { value: string; n: number }[];
}

export interface DdBoolDistribution {
  key: DdBoolKey;
  label: string;
  trueN: number;
  falseN: number;
}

export interface DdDistribution {
  /** Matched rows that carry a deep_dive_filters payload. */
  deepDivedCount: number;
  enums: DdEnumDistribution[];
  bools: DdBoolDistribution[];
}

export function computeDdDistribution(
  matchedRows: CatalogRow[],
): DdDistribution {
  const dd = matchedRows
    .map((r) => r.deep_dive_filters)
    .filter((x): x is DeepDiveFilters => Boolean(x));

  const enums: DdEnumDistribution[] = DD_ENUM_FIELDS.map((f) => {
    const counts = new Map<string, number>();
    for (const d of dd) {
      const v = d[f.key] as string | undefined;
      if (v == null) continue;
      counts.set(v, (counts.get(v) ?? 0) + 1);
    }
    // Order by the field's declared value order, then any unexpected
    // values (shouldn't happen) appended after.
    const ordered: { value: string; n: number }[] = [];
    for (const v of f.values) {
      const c = counts.get(v);
      if (c != null) {
        ordered.push({ value: v, n: c });
        counts.delete(v);
      }
    }
    for (const [v, c] of counts) ordered.push({ value: v, n: c });
    return { key: f.key, label: f.label, counts: ordered };
  }).filter((e) => e.counts.length > 0);

  const bools: DdBoolDistribution[] = DD_BOOL_FIELDS.map((f) => {
    let trueN = 0;
    let falseN = 0;
    for (const d of dd) {
      const v = d[f.key] as boolean | undefined;
      if (v === true) trueN += 1;
      else if (v === false) falseN += 1;
    }
    return { key: f.key, label: f.label, trueN, falseN };
  }).filter((b) => b.trueN + b.falseN > 0);

  return { deepDivedCount: dd.length, enums, bools };
}
