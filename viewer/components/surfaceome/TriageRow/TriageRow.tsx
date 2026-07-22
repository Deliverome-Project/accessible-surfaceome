"use client";

import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { tooltips } from "../../../lib/tooltips";
import {
  triageVerdictLabel,
  triageVsDeepDive,
} from "../../../lib/triage-comparison";
import { InfoTip } from "../../InfoTip/InfoTip";
import { ChipLabelValue } from "../ChipLabelValue/ChipLabelValue";
import { ReasoningDrawer } from "../ReasoningDrawer/ReasoningDrawer";
import type { TriageHeadline } from "../GeneHeader/GeneHeader";
import styles from "./TriageRow.module.css";

interface Props {
  rec: SurfaceomeRecord;
  triageHeadline?: TriageHeadline | null;
}

/** Sonnet first-pass surface verdict, rendered as a compact one-line
 *  strip. Previously lived in the GeneHeader (under the DB-presence
 *  strip); relocated to just above the DataSourcesFooter so the
 *  header is anchored on the deep-dive verdict and the initial-pass
 *  triage sits with the other provenance-flavored content at the
 *  bottom of the page. Tagged with "initial pass · no web search" so
 *  the reader knows this isn't the deep-dive call. When the triage
 *  disagrees with the deep-dive `surface_accessibility`, the row
 *  carries a warn pill that links the eye to the conflict (e.g. for
 *  SRC: triage=Unlikely vs deep-dive=High — the eSrc cancer-specific
 *  surface that the initial triage missed). */
export function TriageRow({ rec, triageHeadline }: Props) {
  const exec = rec.executive_summary;
  // Prefer the latest most-positive triage verdict across all
  // model × variant runs (from /v1/triage/{symbol}) over the
  // record's bundled `triage_signal` — the bundled value is
  // the triage call that *triggered* this deep-dive (a single
  // model × variant × point-in-time snapshot) and can lag
  // behind a later re-triage that flipped the verdict.
  // KLK2 is the smoking gun: bundled signal='unlikely' (the
  // 2026-06-01 sonnet-ncbi call) but the latest+most-positive
  // call (2026-06-23 sonnet-pubmed_ncbi) is 'contextual'.
  const headlineSignal = triageHeadline?.signal ?? rec.triage_signal;
  const headlineReason = triageHeadline?.reason ?? rec.triage_reason ?? null;
  const headlineReasoning =
    triageHeadline?.reasoning ?? rec.triage_reasoning ?? "";
  const headlineConfidence =
    triageHeadline?.confidence ?? rec.triage_confidence ?? null;
  const verdict = triageVsDeepDive(
    headlineSignal,
    exec.surface_accessibility,
    exec.surface_call_reason,
  );
  return (
    <p className={styles.triageRow}>
      <span className={`label-mono ${styles.triageLabel}`}>
        Triage
        <InfoTip wide>{tooltips.triage_signal}</InfoTip>
      </span>
      <span className={styles.triageValue}>
        {triageVerdictLabel(headlineSignal)}
      </span>
      <span className={styles.triageQualifier}>
        <ChipLabelValue label="initial pass" value="no web search" />
      </span>
      {verdict === "conflict" ? (
        <span className={styles.triageConflict}>conflicts with deep dive</span>
      ) : verdict === "agree" ? (
        <span className={styles.triageAgree}>agrees with deep dive</span>
      ) : null}
      {/* The triage agent's own verdict justification, surfaced
       *  in a slide-in drawer. Self-hides when the record
       *  carries no triage_reasoning (older records / genes with
       *  no persisted triage). Distinct from the deep-dive
       *  confidence reasoning in the GeneHeader — this is the
       *  first-pass, no-web-search rationale. */}
      <ReasoningDrawer
        eyebrow={`Triage · ${triageVerdictLabel(headlineSignal)}`}
        title="Why this triage call?"
        ariaLabel="Why the initial triage pass called it this way"
        triggerClassName={styles.triageReasoningTrigger}
        reasoning={headlineReasoning}
        reasonCode={headlineReason}
        meta={(() => {
          // Same provenance the catalog drawer shows inline
          // (Variant + Date), plus Confidence — pass through
          // the existing meta slot so the deep-dive's triage
          // drawer carries the same info at a glance.
          const out: Array<{ label: string; value: string }> = [];
          if (triageHeadline?.promptVariant) {
            out.push({
              label: "Variant",
              value: triageHeadline.promptVariant.replace(/_/g, " "),
            });
          }
          if (triageHeadline?.createdAt) {
            out.push({
              label: "Date",
              value: new Date(triageHeadline.createdAt).toLocaleDateString(
                "en-US",
                { year: "numeric", month: "short", day: "numeric" },
              ),
            });
          }
          if (headlineConfidence) {
            out.push({ label: "Confidence", value: headlineConfidence });
          }
          return out.length > 0 ? out : undefined;
        })()}
        secondary={triageHeadline?.secondary}
      />
    </p>
  );
}
