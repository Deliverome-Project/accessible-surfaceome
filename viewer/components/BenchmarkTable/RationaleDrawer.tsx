"use client";

import Link from "next/link";
import type {
  BenchmarkMatrix,
  BenchmarkVariantResult,
} from "../../lib/surfaceome-types";
import styles from "./BenchmarkTable.module.css";

export interface SelectedCell {
  symbol: string;
  model: string;
  variant: string;
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
          {data.cell?.reason ? (
            <p className={styles.drawerReason}>
              <span className="label-mono">Model reason code · </span>
              {data.cell.reason.replace(/_/g, " ")}
            </p>
          ) : null}
          {data.cell?.reasoning ? (
            <p className={styles.drawerReasoning}>{data.cell.reasoning}</p>
          ) : (
            <p className={styles.drawerReasoningEmpty}>
              (No free-text reasoning recorded — verdict only.)
            </p>
          )}
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
