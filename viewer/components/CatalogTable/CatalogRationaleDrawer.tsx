"use client";

import Link from "next/link";
import styles from "./CatalogRationaleDrawer.module.css";

/** Shape of a single triage run as returned by the public Worker's
 *  /v1/triage/{symbol} endpoint. Kept in sync with the TriageRun
 *  interface in CatalogTable.tsx. */
export interface CatalogTriageRun {
  created_at: string;
  model: string;
  prompt_variant: string | null;
  predicted_verdict: string;
  predicted_reason: string | null;
  predicted_confidence: string | null;
  verdict_reasoning: string | null;
  latency_s: number | null;
  error: string | null;
}

export type CatalogTriageDetailState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; runs: CatalogTriageRun[] };

/** The headline verdict cached on the catalog row — used as a
 *  synchronous fallback while /v1/triage/{symbol} is in flight. */
export interface CatalogFallbackCell {
  verdict: string | null;
  reason: string | null;
}

interface Props {
  selectedSymbol: string | null;
  /** Cached fetch state for the currently-selected symbol. */
  detail: CatalogTriageDetailState | undefined;
  fallback: CatalogFallbackCell | null;
  geneName: string | null;
  hasDeepDive: boolean;
  onClose: () => void;
}

const SONNET_MODEL_ID = "claude-sonnet-4-6";
const HEADLINE_VARIANT = "ncbi";

/**
 * CatalogRationaleDrawer — right-side non-modal panel that surfaces the
 * Sonnet 4.6 (NCBI-context) reasoning for a single catalog gene. Same
 * pattern as the SurfaceBench RationaleDrawer (focus-trap-free, bottom
 * sheet under 720 px, opacity fade under prefers-reduced-motion); the
 * implementation is independent because the data flow is — the
 * benchmark drawer reads from an in-memory matrix, this one waits on a
 * lazy /v1/triage/{symbol} fetch managed by the parent table.
 */
export function CatalogRationaleDrawer({
  selectedSymbol,
  detail,
  fallback,
  geneName,
  hasDeepDive,
  onClose,
}: Props) {
  const isOpen = selectedSymbol != null;
  const latestSonnet = pickLatestNcbiSonnet(detail);

  // Prefer the live fetch's verdict + reasoning; fall back to the
  // catalog-row's cached NCBI verdict when the fetch hasn't completed
  // (or returned an error).
  const verdict = latestSonnet?.predicted_verdict ?? fallback?.verdict ?? null;
  const reason = latestSonnet?.predicted_reason ?? fallback?.reason ?? null;
  const reasoning = latestSonnet?.verdict_reasoning ?? null;

  return (
    <aside
      className={`${styles.drawer} ${isOpen ? styles.drawerOpen : ""}`}
      role="region"
      aria-label={
        selectedSymbol
          ? `Triage rationale for ${selectedSymbol}`
          : "Rationale panel"
      }
      aria-hidden={!isOpen}
      tabIndex={-1}
    >
      {selectedSymbol ? (
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
            Sonnet 4.6 · NCBI context
          </p>
          <h2 className={styles.drawerTitle}>
            {selectedSymbol}
            {geneName ? (
              <span className={styles.drawerSubtitle}>{geneName}</span>
            ) : null}
          </h2>
          {verdict ? (
            <div className={styles.drawerVerdicts}>
              <span
                className={`${styles.drawerVerdict} ${verdictToneClass(verdict)}`}
              >
                {verdict}
              </span>
            </div>
          ) : null}
          {reason ? (
            <p className={styles.drawerReason}>
              <span className="label-mono">Reason code · </span>
              {reason.replace(/_/g, " ")}
            </p>
          ) : null}
          {detail?.status === "loading" ? (
            <p className={styles.drawerLoading}>
              Loading reasoning for <strong>{selectedSymbol}</strong>…
            </p>
          ) : null}
          {detail?.status === "error" ? (
            <p className={styles.drawerError}>
              Could not load reasoning ({detail.message}). Showing
              cached verdict only.
            </p>
          ) : null}
          {detail?.status === "ready" && reasoning ? (
            <p className={styles.drawerReasoning}>{reasoning}</p>
          ) : null}
          {detail?.status === "ready" && !reasoning ? (
            <p className={styles.drawerReasoningEmpty}>
              (No free-text reasoning recorded for the latest Sonnet
              NCBI run — verdict only.)
            </p>
          ) : null}
          {latestSonnet?.predicted_confidence ||
          latestSonnet?.latency_s != null ? (
            <dl className={styles.drawerMeta}>
              {latestSonnet?.predicted_confidence ? (
                <div className={styles.drawerMetaItem}>
                  <dt className="label-mono">Confidence</dt>
                  <dd>{latestSonnet.predicted_confidence}</dd>
                </div>
              ) : null}
              {latestSonnet?.latency_s != null ? (
                <div className={styles.drawerMetaItem}>
                  <dt className="label-mono">Latency</dt>
                  <dd>{latestSonnet.latency_s.toFixed(1)} s</dd>
                </div>
              ) : null}
            </dl>
          ) : null}
          {hasDeepDive ? (
            <p className={styles.drawerFooter}>
              <Link
                href={`/${selectedSymbol}/`}
                className={styles.drawerDeepDiveLink}
              >
                ↗ Open the {selectedSymbol} deep-dive page
              </Link>
            </p>
          ) : null}
        </div>
      ) : null}
    </aside>
  );
}

function pickLatestNcbiSonnet(
  detail: CatalogTriageDetailState | undefined,
): CatalogTriageRun | null {
  if (!detail || detail.status !== "ready") return null;
  let latest: CatalogTriageRun | null = null;
  for (const r of detail.runs) {
    if (r.model !== SONNET_MODEL_ID) continue;
    if (r.prompt_variant !== HEADLINE_VARIANT) continue;
    if (!latest || latest.created_at < r.created_at) {
      latest = r;
    }
  }
  return latest;
}

function verdictToneClass(v: string | null | undefined): string {
  if (v === "yes") return styles.verdictYes;
  if (v === "no") return styles.verdictNo;
  if (v === "contextual") return styles.verdictContextual;
  return styles.verdictUnknown;
}
