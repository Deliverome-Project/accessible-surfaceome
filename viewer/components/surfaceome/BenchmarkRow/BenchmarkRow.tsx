import type {
  BenchmarkRow as BenchmarkRowPayload,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { tooltips } from "../../../lib/tooltips";
import { triageVsDeepDive } from "../../../lib/triage-comparison";
import { InfoTip } from "../../InfoTip/InfoTip";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./BenchmarkRow.module.css";

interface Props {
  rec: SurfaceomeRecord;
  benchmarkRow: BenchmarkRowPayload;
}

function benchmarkVerdictLabel(verdict: string): string {
  if (verdict === "yes") return "Yes";
  if (verdict === "contextual") return "Contextual";
  if (verdict === "no") return "No";
  return verdict;
}

function benchmarkVerdictTone(
  verdict: string,
): "success" | "amber" | "danger" | "neutral" {
  if (verdict === "yes") return "success";
  if (verdict === "contextual") return "amber";
  if (verdict === "no") return "danger";
  return "neutral";
}

/** Curated SurfaceBench ground-truth verdict — the strongest reference
 *  point on the page. Rendered only for the ~147 benchmark genes.
 *  Previously lived at the top of the GeneHeader (above the triage
 *  row); relocated to the bottom of the page (above TriageRow, above
 *  DataSourcesFooter) so the header stays anchored on the deep-dive
 *  verdict itself and the reference-point strip content sits with the
 *  other provenance rows at the bottom. */
export function BenchmarkRow({ rec, benchmarkRow }: Props) {
  const exec = rec.executive_summary;
  // Map the benchmark verdict onto the triage-signal scheme so
  // triageVsDeepDive can be reused (yes→likely, contextual→possibly,
  // no→unlikely).
  const benchSignal =
    benchmarkRow.truth_verdict === "yes"
      ? "likely_accessible"
      : benchmarkRow.truth_verdict === "contextual"
        ? "possibly_accessible"
        : benchmarkRow.truth_verdict === "no"
          ? "unlikely"
          : "unknown";
  const benchVerdict = triageVsDeepDive(
    benchSignal,
    exec.surface_accessibility,
    exec.surface_call_reason,
  );
  return (
    <p className={styles.benchmarkRow}>
      <span className={`label-mono ${styles.benchmarkLabel}`}>
        Benchmark
        <InfoTip>{tooltips.benchmark_truth}</InfoTip>
      </span>
      <StatusPill
        tone={benchmarkVerdictTone(benchmarkRow.truth_verdict)}
        size="sm"
      >
        {benchmarkVerdictLabel(benchmarkRow.truth_verdict)}
      </StatusPill>
      {benchVerdict === "conflict" ? (
        <span className={styles.benchmarkConflict}>conflicts with deep dive</span>
      ) : benchVerdict === "agree" ? (
        <span className={styles.benchmarkAgree}>agrees with deep dive</span>
      ) : null}
    </p>
  );
}
