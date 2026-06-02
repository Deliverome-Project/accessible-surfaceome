import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { EvidenceChipList, linkifyEvidenceRefs } from "../EvidenceChip/EvidenceChip";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./ExecutiveSummaryCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function accessibilityTone(v: string) {
  if (v === "high") return "success" as const;
  if (v === "moderate") return "teal" as const;
  if (v === "low") return "amber" as const;
  // `"no"` is the confident negative call — strongest "not surface"
  // signal the schema carries, distinct from `"uncertain"` (no signal
  // either way). Render in danger / red so the reader sees it.
  if (v === "no") return "danger" as const;
  return "neutral" as const;
}

/**
 * Headline-risks display labels. The enum value is the source of
 * truth (matches Pydantic ``HeadlineRisk``); this map lets us render
 * a longer reader-facing phrase without breaking the enum contract.
 * One entry per current enum value — adding a new value without
 * updating this map gracefully falls back to ``prettyEnum(value)``.
 */
const HEADLINE_RISK_LABELS: Record<string, string> = {
  shed_form: "Shed form",
  secreted_form: "Secreted form",
  co_receptor: "Co-receptor required for expression",
  epitope_masked: "Epitope masked",
  isoform_decoy: "Isoform decoy",
};

function headlineRiskLabel(v: string): string {
  return HEADLINE_RISK_LABELS[v] ?? prettyEnum(v);
}

function confidenceTone(v: string) {
  if (v === "high") return "success" as const;
  if (v === "moderate") return "lavender" as const;
  if (v === "low") return "amber" as const;
  return "neutral" as const;
}

function stateTone(v: string) {
  if (v === "low") return "success" as const;
  if (v === "moderate") return "amber" as const;
  if (v === "high") return "danger" as const;
  return "neutral" as const;
}

function gradeTone(v: string) {
  if (v === "direct_multi_method") return "success" as const;
  if (v === "direct_single_method") return "teal" as const;
  if (v === "supportive_but_indirect") return "amber" as const;
  if (v === "conflicting") return "danger" as const;
  return "neutral" as const;
}

export function ExecutiveSummaryCard({ rec, n }: Props) {
  const e = rec.executive_summary;
  return (
    <SectionCard
      n={n}
      eyebrow="Executive summary"
      title="Overview and headline call"
      meta="LLM synthesis · top-line accessibility judgment + headline risks"
    >
      {e.accessibility_context_summary ? (
        <p className="lede">{e.accessibility_context_summary}</p>
      ) : null}

      <p className={styles.paragraph}>{e.one_paragraph}</p>

      <ul className={styles.pillStrip} aria-label="Executive summary pills">
        <li>
          <StatusPill tone={accessibilityTone(e.surface_accessibility)}>
            Accessibility · {prettyEnum(e.surface_accessibility)}
          </StatusPill>
        </li>
        <li>
          <StatusPill tone={gradeTone(e.evidence_grade_summary)}>
            Experimental surface evidence · {prettyEnum(e.evidence_grade_summary)}
          </StatusPill>
        </li>
        <li>
          <StatusPill tone={confidenceTone(e.confidence)}>
            Confidence · {prettyEnum(e.confidence)}
          </StatusPill>
        </li>
        <li>
          <StatusPill tone={stateTone(e.state_dependence)}>
            State dep · {prettyEnum(e.state_dependence)}
          </StatusPill>
        </li>
      </ul>

      {/* Architecture + Family as plain text below the chip strip.
       *  These used to be StatusPills in the strip itself; demoted
       *  here to keep the at-a-glance row focused on accessibility
       *  signals (the architecture / family axes are orthogonal
       *  descriptive metadata that doesn't need a colored chip). */}
      <p className={styles.meta}>
        <span className={`label-mono ${styles.metaLabel}`}>Architecture</span>
        <span className={styles.metaValue}>{prettyEnum(e.subcategory)}</span>
        <span className={`label-mono ${styles.metaLabel}`}>Family (LLM)</span>
        <span className={styles.metaValue}>{prettyEnum(e.llm_family)}</span>
      </p>

      {/* Deterministic registry family tags — curator-assigned, attached
       *  by the orchestrator from the resolved IdentifierBundle (NOT
       *  model output). Shown beside the LLM's Family call so the reader
       *  can cross-check the model's high-level functional call against
       *  HGNC / UniProt ground truth. Each line renders only when the
       *  registry actually classifies the gene (empty list / null is
       *  common and is simply omitted rather than shown blank). */}
      {e.hgnc_gene_groups.length > 0 || e.uniprot_family ? (
        <p className={styles.meta}>
          {e.hgnc_gene_groups.length > 0 ? (
            <>
              <span className={`label-mono ${styles.metaLabel}`}>HGNC group</span>
              <span className={styles.metaValue}>
                {e.hgnc_gene_groups.join(" · ")}
              </span>
            </>
          ) : null}
          {e.uniprot_family ? (
            <>
              <span className={`label-mono ${styles.metaLabel}`}>
                UniProt family
              </span>
              <span className={styles.metaValue}>{e.uniprot_family}</span>
            </>
          ) : null}
        </p>
      ) : null}

      {/* Confidence rationale — collapsible expander beneath the
       *  confidence chip. The synth prompt produces this prose only
       *  when confidence ∈ {moderate, low}; for `high` calls the
       *  field is typically empty, so we hide the expander entirely.
       *  Prose is user-facing per the synth prompt's "writing for the
       *  reader" section (no `A1`/`a1_evi_NN`/`accessibility='X'`
       *  pipeline jargon). */}
      {rec.confidence_reasoning && rec.confidence_reasoning.trim().length > 0 ? (
        <details className={styles.confidenceRationale}>
          <summary>
            Why is confidence {prettyEnum(e.confidence)}? — rationale
          </summary>
          <p className={styles.confidenceRationaleBody}>
            {rec.confidence_reasoning}
          </p>
        </details>
      ) : null}

      {e.headline_risks.length > 0 ? (
        <p className={styles.risks}>
          <span className={`label-mono ${styles.risksLabel}`}>Headline risks</span>
          <span className={styles.risksValue}>
            {e.headline_risks.map(headlineRiskLabel).join(" · ")}
          </span>
        </p>
      ) : (
        <p className={styles.risks}>
          <span className={`label-mono ${styles.risksLabel}`}>Headline risks</span>
          <span className={styles.risksValue}>None flagged.</span>
        </p>
      )}

      {/* Inline citation chips — click any chip to open the global
       *  EvidenceDrawer with that evidence's full claim + verbatim
       *  quote + source links. Mirrors the v2 record's per-block
       *  citations strip. */}
      <EvidenceChipList
        ids={e.cited_evidence_ids}
        label="Cited evidence"
      />
    </SectionCard>
  );
}
