/*
 * Triage-headline parsing (browser-safe).
 * ------------------------------------------------------------
 * Pure logic that turns a ``/v1/triage/{symbol}`` payload into the
 * most-positive Sonnet 4.6 headline call (+ dissenting-variant secondary
 * list). Extracted here — with no ``node:*`` imports — so both the
 * server loader (``lib/surfaceome.ts:loadTriageHeadline``, which adds the
 * fetch/cache wrapper) and the client gene shell can share it. The client
 * shell fetches ``/v1/triage/{symbol}`` in the browser and calls
 * ``parseTriageHeadline`` directly.
 */

import type { TriageSignal } from "./surfaceome-types";

/** Most-positive triage call (yes > contextual > unclear > no) with
 *  latest ``created_at`` as the tiebreak — matches the catalog drawer's
 *  picker. Distinct from a record's bundled ``triage_signal`` (the
 *  specific call that triggered the deep-dive), which can lag a later
 *  re-triage that flipped the verdict. */
export interface TriageHeadlinePayload {
  signal: TriageSignal;
  reason: string | null;
  reasoning: string;
  confidence: string | null;
  /** ISO timestamp of the picked run (newest with the most-positive verdict). */
  createdAt: string | null;
  /** prompt_variant of the picked run (e.g. "pubmed_ncbi"). */
  promptVariant: string | null;
  /** Other variants' latest runs that disagree with the headline, sorted
   *  positive→negative, capped at 3. Empty when all variants agree. */
  secondary: ReadonlyArray<TriageHeadlineSecondaryEntry>;
}

export interface TriageHeadlineSecondaryEntry {
  signal: TriageSignal;
  /** Raw verdict ("yes" | "contextual" | "no" | …) for the verdict-tone
   *  class lookup; mirrors what the catalog drawer renders. */
  verdict: string;
  reason: string | null;
  createdAt: string;
  promptVariant: string | null;
}

/** Shape of the ``/v1/triage/{symbol}`` payload this parser reads. */
export interface TriageRunsPayload {
  runs?: Array<{
    created_at: string;
    model: string;
    prompt_variant: string | null;
    predicted_verdict: string;
    predicted_reason: string | null;
    predicted_confidence: string | null;
    verdict_reasoning: string | null;
  }>;
}

const _VERDICT_RANK: Record<string, number> = {
  yes: 3,
  contextual: 2,
  unclear: 1,
  no: 0,
};

function _verdictToSignal(v: string | null | undefined): TriageSignal {
  if (v === "yes") return "likely_accessible";
  if (v === "contextual") return "possibly_accessible";
  if (v === "no") return "unlikely";
  return "unknown";
}

/**
 * Collapse a triage payload to one row per (Sonnet 4.6 × variant), keep
 * the latest per variant, rank by positivity (then recency), and return
 * the headline plus up to 3 dissenting-variant entries. Returns ``null``
 * when there is no Sonnet 4.6 run.
 */
export function parseTriageHeadline(
  data: TriageRunsPayload,
): TriageHeadlinePayload | null {
  // Collapse to one row per (model × variant), keeping the latest. Scoped
  // to Sonnet 4.6 to match the catalog drawer (the canonical headline
  // model); cross-model runs would noise the deep-dive's triage row.
  const latestByVariant = new Map<
    string,
    NonNullable<TriageRunsPayload["runs"]>[number]
  >();
  for (const r of data.runs ?? []) {
    if (r.model !== "claude-sonnet-4-6") continue;
    const key = r.prompt_variant ?? "";
    const prev = latestByVariant.get(key);
    if (!prev || prev.created_at < r.created_at) {
      latestByVariant.set(key, r);
    }
  }
  const ranked = [...latestByVariant.values()].sort((a, b) => {
    const dr =
      (_VERDICT_RANK[b.predicted_verdict] ?? -1) -
      (_VERDICT_RANK[a.predicted_verdict] ?? -1);
    if (dr !== 0) return dr;
    return a.created_at < b.created_at ? 1 : -1;
  });
  if (ranked.length === 0) return null;
  const headline = ranked[0];
  const secondary: TriageHeadlineSecondaryEntry[] = ranked
    .slice(1)
    .filter((r) => r.predicted_verdict !== headline.predicted_verdict)
    .slice(0, 3)
    .map((r) => ({
      signal: _verdictToSignal(r.predicted_verdict),
      verdict: r.predicted_verdict,
      reason: r.predicted_reason?.trim() || null,
      createdAt: r.created_at,
      promptVariant: r.prompt_variant ?? null,
    }));
  return {
    signal: _verdictToSignal(headline.predicted_verdict),
    reason: headline.predicted_reason?.trim() || null,
    reasoning: headline.verdict_reasoning?.trim() ?? "",
    confidence: headline.predicted_confidence?.trim() || null,
    createdAt: headline.created_at,
    promptVariant: headline.prompt_variant ?? null,
    secondary,
  };
}
