"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type {
  BenchmarkMatrix,
  BenchmarkVariantResult,
} from "../../lib/surfaceome-types";
import styles from "./BenchmarkTable.module.css";

// Public Worker base (client-side fetch — same origin the SSG loader uses
// server-side). Used to lazy-load per-replicate detail for the open cell.
const API_BASE = "https://api.deliverome.org/surfaceome";

export interface SelectedCell {
  symbol: string;
  model: string;
  variant: string;
}

/** One replicate from /v1/triage/:symbol/:model/:variant. */
interface RepRow {
  replicate: number;
  predicted_verdict: string | null;
  predicted_reason: string | null;
  verdict_reasoning: string | null;
  predicted_confidence: string | null;
  error: string | null;
}
interface CellDetail {
  majority: {
    verdict: string;
    reason: string | null;
    reasoning: string | null;
    confidence: string | null;
    n_reps: number;
    agreement: number;
  } | null;
  replicates: RepRow[];
}

/** Lazy-fetch all replicates for the open (gene, model, variant) cell.
 *  Returns null while loading / on error so the drawer falls back to the
 *  single-rep matrix data it already has. */
function useCellReplicates(sel: SelectedCell | null): CellDetail | null {
  const [detail, setDetail] = useState<CellDetail | null>(null);
  useEffect(() => {
    setDetail(null);
    if (!sel) return;
    let cancelled = false;
    const url = `${API_BASE}/v1/triage/${encodeURIComponent(sel.symbol)}/${encodeURIComponent(sel.model)}/${encodeURIComponent(sel.variant)}`;
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (!cancelled && j) setDetail(j as CellDetail);
      })
      .catch(() => {
        /* network error — drawer keeps the matrix's single-rep view */
      });
    return () => {
      cancelled = true;
    };
  }, [sel?.symbol, sel?.model, sel?.variant]);
  return detail;
}

interface LabelDef {
  id: string;
  short: string;
  long: string;
}

interface RationaleDrawerProps {
  selected: SelectedCell | null;
  matrix: BenchmarkMatrix;
  modelLabels: LabelDef[];
  variantLabels: LabelDef[];
  deepDiveGenes: Set<string>;
  geneNames?: Record<string, string>;
  onClose: () => void;
}

/**
 * RationaleDrawer — right-side non-modal panel that surfaces the
 * full per-(gene, model, variant) reasoning. Persists across cell
 * clicks (replaces content rather than dismissing) so readers can
 * compare verdicts within a row. Closes on ESC or the close button
 * (ESC handler lives in `BenchmarkTable` so it doesn't depend on
 * drawer focus). Below 720 px viewport it becomes a bottom sheet
 * via CSS media query — no JS branching.
 *
 * Content is looked up from `matrix.rows` on every render rather
 * than cached locally, so the drawer keeps working when the virtual
 * row scrolls out of view and unmounts.
 */
export function RationaleDrawer({
  selected,
  matrix,
  modelLabels,
  variantLabels,
  deepDiveGenes,
  geneNames,
  onClose,
}: RationaleDrawerProps) {
  const isOpen = selected != null;
  const data = selected ? lookup(selected, matrix, modelLabels, variantLabels) : null;
  // Lazy-load all replicates for the open cell (per-rep reasons live in
  // a separate Worker call so the matrix payload stays single-rep + small).
  const detail = useCellReplicates(selected);

  return (
    <aside
      className={`${styles.drawer} ${isOpen ? styles.drawerOpen : ""}`}
      role="region"
      aria-label={
        data
          ? `Rationale for ${data.symbol} · ${data.model.long} · ${data.variant.long}`
          : "Rationale panel"
      }
      aria-hidden={!isOpen}
      tabIndex={-1}
    >
      {data ? (
        <div className={styles.drawerCard}>
          <button
            type="button"
            className={styles.drawerCloseBtn}
            onClick={onClose}
            aria-label="Close rationale panel"
          >
            ×
          </button>
          <p className={`label-mono ${styles.drawerEyebrow}`}>
            {data.model.long} · {data.variant.long}
          </p>
          <h2 className={styles.drawerTitle}>
            {data.symbol}
            {geneNames?.[data.symbol] ? (
              <span className={styles.drawerSubtitle}>
                {geneNames[data.symbol]}
              </span>
            ) : null}
          </h2>
          <div className={styles.drawerVerdicts}>
            <span
              className={`${styles.drawerVerdict} ${verdictToneClass(data.cell?.verdict)}`}
              title={`Model verdict: ${data.cell?.verdict ?? "—"}`}
            >
              {data.cell?.verdict ?? "—"}
              <span className={styles.drawerVerdictLabel}> · model</span>
            </span>
            <span
              className={`${styles.drawerVerdict} ${verdictToneClass(data.truth_verdict)}`}
              title="Curated ground-truth verdict"
            >
              {data.truth_verdict}
              <span className={styles.drawerVerdictLabel}> · truth</span>
            </span>
            <span
              className={
                data.correct ? styles.drawerCorrectOK : styles.drawerCorrectBad
              }
            >
              {data.correct === null
                ? "no verdict"
                : data.correct
                  ? "agrees with truth"
                  : "disagrees with truth"}
            </span>
          </div>
          {/* Ground-truth panel — what the human curator said when they
           *  labeled this gene. Surfaces signal + reason + the full
           *  rationale prose so the reader can read the curator's
           *  reasoning side-by-side with the model's. */}
          {(data.truth_reason || data.truth_signal || data.rationale || data.bench_class) ? (
            <div className={styles.drawerTruthBlock}>
              <p className={`label-mono ${styles.drawerTruthEyebrow}`}>
                Ground truth
              </p>
              {data.bench_class ? (
                <p className={styles.drawerTruthLine}>
                  <span className="label-mono">Class · </span>
                  {data.bench_class.replace(/_/g, " ")}
                </p>
              ) : null}
              {data.truth_signal ? (
                <p className={styles.drawerTruthLine}>
                  <span className="label-mono">Signal · </span>
                  {data.truth_signal.replace(/_/g, " ")}
                </p>
              ) : null}
              {data.truth_reason ? (
                <p className={styles.drawerTruthLine}>
                  <span className="label-mono">Reason · </span>
                  {data.truth_reason.replace(/_/g, " ")}
                </p>
              ) : null}
              {data.rationale ? (
                <p className={styles.drawerTruthRationale}>{data.rationale}</p>
              ) : null}
            </div>
          ) : null}
          {/* Majority-vote reason FIRST, then the OTHER replicates below
              (the majority rep itself isn't repeated). Prefer the
              lazy-loaded cell detail's computed majority over the matrix's
              single latest-rep view; fall back to the matrix cell while the
              fetch is in flight. */}
          {(() => {
            const maj = detail?.majority;
            const reason = maj?.reason ?? data.cell?.reason ?? null;
            const reasoning = maj?.reasoning ?? data.cell?.reasoning ?? null;
            // Dedupe replicates by replicate number (defensive — a cell
            // should never carry two rows for the same replicate, but a
            // bad sync once produced collisions). Keep the first seen.
            const seen = new Set<number>();
            const uniqueReps = (detail?.replicates ?? [])
              .slice()
              .sort((a, b) => a.replicate - b.replicate)
              .filter((r) => {
                if (seen.has(r.replicate)) return false;
                seen.add(r.replicate);
                return true;
              });
            // The majority reasoning is already shown above — drop the rep
            // whose reasoning is identical so it isn't displayed twice.
            // Drop only the FIRST match (other reps with coincidentally
            // identical text still show, though that's vanishingly rare for
            // free-text reasoning).
            let majDropped = false;
            const otherReps = uniqueReps.filter((r) => {
              if (
                !majDropped &&
                reasoning != null &&
                r.verdict_reasoning === reasoning
              ) {
                majDropped = true;
                return false;
              }
              return true;
            });
            return (
              <>
                {maj && maj.n_reps > 1 ? (
                  <p className={`label-mono ${styles.drawerReason}`}>
                    Majority verdict · {maj.verdict.replace(/_/g, " ")} ·{" "}
                    {Math.round(maj.agreement * maj.n_reps)}/{maj.n_reps} reps agree
                  </p>
                ) : null}
                {reason ? (
                  <p className={styles.drawerReason}>
                    <span className="label-mono">Model reason code · </span>
                    {reason.replace(/_/g, " ")}
                  </p>
                ) : null}
                {reasoning ? (
                  <p className={styles.drawerReasoning}>{reasoning}</p>
                ) : (
                  <p className={styles.drawerReasoningEmpty}>
                    (No free-text reasoning recorded — verdict only.)
                  </p>
                )}
                {/* Other replicates — the per-rep spread minus the one
                    already shown as the majority. Scroll to reveal.
                    Errored reps (null verdict — the model failed to emit a
                    valid verdict/reason combo even after a retry) are shown
                    as ERRORED and their stale pre-null reasoning is
                    SUPPRESSED, so they don't masquerade as a real vote. The
                    majority's "N/M reps agree" counts only valid reps, so
                    this keeps the two consistent. */}
                {otherReps.length > 0 ? (
                  <details className={styles.drawerReps} open>
                    <summary className="label-mono">
                      {otherReps.length === 1
                        ? "1 other replicate"
                        : `${otherReps.length} other replicates`}
                    </summary>
                    {otherReps.map((rep) => {
                      const errored = rep.predicted_verdict == null;
                      return (
                        <div key={rep.replicate} className={styles.drawerRep}>
                          <p className={`label-mono ${styles.drawerRepHead}`}>
                            Rep {rep.replicate} ·{" "}
                            {errored
                              ? "errored (no valid verdict)"
                              : rep.predicted_verdict!.replace(/_/g, " ")}
                            {!errored && rep.predicted_reason
                              ? ` · ${rep.predicted_reason.replace(/_/g, " ")}`
                              : ""}
                          </p>
                          {errored ? (
                            <p className={styles.drawerReasoningEmpty}>
                              Excluded from the majority — the model didn&apos;t
                              return a schema-valid verdict on this replicate.
                            </p>
                          ) : rep.verdict_reasoning ? (
                            <p className={styles.drawerRepReasoning}>
                              {rep.verdict_reasoning}
                            </p>
                          ) : null}
                        </div>
                      );
                    })}
                  </details>
                ) : null}
              </>
            );
          })()}
          <dl className={styles.drawerMeta}>
            {data.cell?.confidence ? (
              <div className={styles.drawerMetaItem}>
                <dt className="label-mono">Confidence</dt>
                <dd>{data.cell.confidence}</dd>
              </div>
            ) : null}
            {data.cell?.latency_s != null ? (
              <div className={styles.drawerMetaItem}>
                <dt className="label-mono">Latency</dt>
                <dd>{data.cell.latency_s.toFixed(1)} s</dd>
              </div>
            ) : null}
            {data.cell?.cost_usd != null ? (
              <div className={styles.drawerMetaItem}>
                <dt className="label-mono">Cost</dt>
                <dd>${data.cell.cost_usd.toFixed(3)}</dd>
              </div>
            ) : null}
          </dl>
          {deepDiveGenes.has(data.symbol) ? (
            <p className={styles.drawerFooter}>
              <Link
                href={`/${data.symbol}/`}
                className={styles.drawerDeepDiveLink}
              >
                ↗ Open the {data.symbol} deep-dive page
              </Link>
            </p>
          ) : null}
        </div>
      ) : null}
    </aside>
  );
}

interface LookupResult {
  symbol: string;
  model: LabelDef;
  variant: LabelDef;
  cell: BenchmarkVariantResult | null;
  truth_verdict: string;
  truth_signal: string;
  truth_reason: string;
  rationale: string;
  bench_class: string;
  correct: boolean | null;
}

function lookup(
  sel: SelectedCell,
  matrix: BenchmarkMatrix,
  modelLabels: LabelDef[],
  variantLabels: LabelDef[],
): LookupResult | null {
  const row = matrix.rows.find((r) => r.gene_symbol === sel.symbol);
  if (!row) return null;
  const model = modelLabels.find((m) => m.id === sel.model);
  const variant = variantLabels.find((v) => v.id === sel.variant);
  if (!model || !variant) return null;
  const cell = row.verdicts?.[sel.model]?.[sel.variant] ?? null;
  const correct =
    cell?.verdict == null
      ? null
      : isCorrect(cell.verdict, row.truth_verdict);
  // The bench TSV carries the curator's full reasoning per gene in
  // `rationale` (1–3 sentences) plus a short coded `truth_reason`
  // (e.g. "classical_surface_receptor") + `truth_signal` (e.g.
  // "likely_accessible"). Show all three in the drawer so the
  // model's call can be compared against the curated context, not
  // just the bare yes/no/contextual verdict.
  type RowWithExtras = typeof row & {
    truth_signal?: string;
    truth_reason?: string;
    rationale?: string;
    class?: string;
  };
  const r = row as RowWithExtras;
  return {
    symbol: row.gene_symbol,
    model,
    variant,
    cell,
    truth_verdict: row.truth_verdict,
    truth_signal: r.truth_signal ?? "",
    truth_reason: r.truth_reason ?? "",
    rationale: r.rationale ?? "",
    bench_class: r.class ?? "",
    correct,
  };
}

function verdictToneClass(v: string | null | undefined): string {
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
