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
  /** Forwarded ref so the parent can install a click-outside listener
   *  without the drawer having to own document-level event wiring. */
  drawerRef?: React.RefObject<HTMLElement | null>;
}

const SONNET_MODEL_ID = "claude-sonnet-4-6";

/** Verdict-positivity ordering used to rank Sonnet runs in the
 *  drawer. Higher score = more positive. Anything we don't recognize
 *  ranks below "no" so the picker never silently surfaces an unknown
 *  verdict ahead of a curated one. Mirrors the same yes > contextual
 *  > no ordering the catalog uses elsewhere. */
const VERDICT_RANK: Record<string, number> = {
  yes: 3,
  contextual: 2,
  unclear: 1,
  no: 0,
};
function verdictRank(v: string | null | undefined): number {
  return VERDICT_RANK[v ?? ""] ?? -1;
}

/**
 * CatalogRationaleDrawer — right-side non-modal panel that surfaces the
 * catalog's triage-agent (Sonnet 4.6 with an NCBI-context block, but
 * deliberately labeled "Triage agent" in the UI) reasoning for a
 * single gene. Same pattern as the SurfaceBench RationaleDrawer
 * (focus-trap-free, bottom sheet under 720 px, opacity fade under
 * prefers-reduced-motion); the implementation is independent because
 * the data flow is — the benchmark drawer reads from an in-memory
 * matrix, this one waits on a lazy /v1/triage/{symbol} fetch managed
 * by the parent table.
 */
export function CatalogRationaleDrawer({
  selectedSymbol,
  detail,
  fallback,
  geneName,
  hasDeepDive,
  onClose,
  drawerRef,
}: Props) {
  const isOpen = selectedSymbol != null;
  // Headline = most-positive Sonnet verdict (latest as tiebreaker).
  // Previously this was hard-coded to the "ncbi" variant's latest run,
  // which meant a single later "no" on the ncbi variant could mask
  // multiple "contextual" calls from the pubmed_ncbi / web_ncbi
  // variants — surfacing the most negative call as the headline.
  // KLK2 was the smoking gun: ncbi:2026-06-01="no" hid
  // pubmed_ncbi:2026-06-23="contextual". Picking the most-positive
  // matches what the catalog row shows.
  const { headline, secondary } = pickSonnetHeadlineAndSecondary(detail);
  const verdict =
    headline?.predicted_verdict ?? fallback?.verdict ?? null;
  const reason = headline?.predicted_reason ?? fallback?.reason ?? null;
  const reasoning = headline?.verdict_reasoning ?? null;

  return (
    <aside
      ref={drawerRef}
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
            Triage agent
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
              {headline ? (
                <span className={styles.drawerHeadlineProv}>
                  <span className="label-mono">
                    {(headline.prompt_variant ?? "—").replace(/_/g, " ")}
                  </span>
                  <span className={styles.drawerHeadlineDate}>
                    · {formatDate(headline.created_at)}
                  </span>
                </span>
              ) : null}
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
              (No free-text reasoning recorded for the latest triage
              run — verdict only.)
            </p>
          ) : null}
          {/* Disagreement block: when other Sonnet variants returned a
              different verdict than the headline, list them below the
              positive call so the reader can scroll down for the
              dissenting view. Positive→negative ordering so the eye
              moves through the same hierarchy as the headline. */}
          {secondary.length > 0 ? (
            <div className={styles.drawerSecondary}>
              <p className={`label-mono ${styles.drawerSecondaryLabel}`}>
                Other triage variants disagree
              </p>
              <ul className={styles.drawerSecondaryList}>
                {secondary.map((r, i) => (
                  <li key={i} className={styles.drawerSecondaryItem}>
                    <span
                      className={`${styles.drawerSecondaryVerdict} ${verdictToneClass(r.predicted_verdict)}`}
                    >
                      {r.predicted_verdict}
                    </span>
                    <span className={styles.drawerSecondaryVariant}>
                      {(r.prompt_variant ?? "—").replace(/_/g, " ")}
                    </span>
                    <span className={styles.drawerSecondaryDate}>
                      {formatDate(r.created_at)}
                    </span>
                    {r.predicted_reason ? (
                      <span className={styles.drawerSecondaryReason}>
                        · {r.predicted_reason.replace(/_/g, " ")}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {headline?.predicted_confidence ||
          headline?.latency_s != null ? (
            <dl className={styles.drawerMeta}>
              {headline?.predicted_confidence ? (
                <div className={styles.drawerMetaItem}>
                  <dt className="label-mono">Confidence</dt>
                  <dd>{headline.predicted_confidence}</dd>
                </div>
              ) : null}
              {headline?.latency_s != null ? (
                <div className={styles.drawerMetaItem}>
                  <dt className="label-mono">Latency</dt>
                  <dd>{headline.latency_s.toFixed(1)} s</dd>
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

/** Picks the headline + disagreeing-secondary Sonnet runs from the
 *  /v1/triage/{symbol} response.
 *
 *  Step 1 — collapse each Sonnet `prompt_variant` to its latest run
 *  (so older verdicts on the same variant never speak for that
 *  variant's current opinion).
 *  Step 2 — sort the per-variant latest runs by verdict positivity
 *  (yes > contextual > unclear > no), with latest `created_at` as
 *  tiebreaker.
 *  Step 3 — headline is the first; secondary is every other run
 *  whose verdict differs from the headline (sorted positive→negative,
 *  capped at 3 to keep the panel scannable).
 */
function pickSonnetHeadlineAndSecondary(
  detail: CatalogTriageDetailState | undefined,
): { headline: CatalogTriageRun | null; secondary: CatalogTriageRun[] } {
  if (!detail || detail.status !== "ready") {
    return { headline: null, secondary: [] };
  }
  const latestByVariant = new Map<string, CatalogTriageRun>();
  for (const r of detail.runs) {
    if (r.model !== SONNET_MODEL_ID) continue;
    const key = r.prompt_variant ?? "";
    const prev = latestByVariant.get(key);
    if (!prev || prev.created_at < r.created_at) {
      latestByVariant.set(key, r);
    }
  }
  const ranked = [...latestByVariant.values()].sort((a, b) => {
    const dr = verdictRank(b.predicted_verdict) - verdictRank(a.predicted_verdict);
    if (dr !== 0) return dr;
    return a.created_at < b.created_at ? 1 : -1;
  });
  if (ranked.length === 0) return { headline: null, secondary: [] };
  const headline = ranked[0];
  const secondary = ranked
    .slice(1)
    .filter((r) => r.predicted_verdict !== headline.predicted_verdict)
    .slice(0, 3);
  return { headline, secondary };
}

/** ISO timestamp → "Jun 23, 2026" (always en-US so the catalog reads
 *  the same regardless of locale). Same shape on every variant /
 *  secondary row so a reader can spot a stale 2026-06-01 ncbi vs a
 *  fresh 2026-06-23 pubmed_ncbi at a glance. */
function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function verdictToneClass(v: string | null | undefined): string {
  if (v === "yes") return styles.verdictYes;
  if (v === "no") return styles.verdictNo;
  if (v === "contextual") return styles.verdictContextual;
  return styles.verdictUnknown;
}
