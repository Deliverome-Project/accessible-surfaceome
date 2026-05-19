import type { OrthologEntry, SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./FiltersCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

// ---------------------------------------------------------------------------
// Polarity tones — green = positive, amber = mid, red = negative.
//
// Each chip in the filters card carries a "what does it MEAN to a
// target-discovery reader" judgment. For a risk bool, true is bad; for
// a positive bool, true is good. For a graded value (expression_level,
// ortholog identity, evidence_grade), the band determines the tone.
// ---------------------------------------------------------------------------

type Tone = "success" | "warn" | "danger" | "neutral" | "teal" | "lavender" | "amber";

/** Risk boolean — ``true`` = risk present = red. */
function riskBoolPill(label: string, value: boolean) {
  return (
    <StatusPill tone={value ? "danger" : "success"} size="sm">
      <span aria-hidden="true">{value ? "✓" : "✗"}</span> {label}
    </StatusPill>
  );
}

/** Positive boolean — ``true`` = good = green. */
function positiveBoolPill(label: string, value: boolean) {
  return (
    <StatusPill tone={value ? "success" : "neutral"} size="sm">
      <span aria-hidden="true">{value ? "✓" : "✗"}</span> {label}
    </StatusPill>
  );
}

// --- graded-value tone mappers ---------------------------------------

function accessibilityTone(v: string): Tone {
  return v === "high" ? "success" : v === "moderate" ? "warn" : v === "low" ? "danger" : "neutral";
}

function confidenceTone(v: string): Tone {
  return v === "high" ? "success" : v === "moderate" ? "warn" : v === "low" ? "danger" : "neutral";
}

function evidenceGradeTone(v: string): Tone {
  if (v === "direct_multi_method" || v === "direct_single_method") return "success";
  if (v === "supportive_but_indirect") return "warn";
  if (v === "conflicting" || v === "weak") return "danger";
  return "neutral";
}

function ecdAccessibilityTone(v: string): Tone {
  if (v === "large" || v === "moderate") return "success";
  if (v === "small") return "warn";
  if (v === "minimal" || v === "none") return "danger";
  return "neutral";
}

function evidenceDensityTone(v: string): Tone {
  return v === "high" ? "success" : v === "moderate" ? "warn" : v === "low" ? "danger" : "neutral";
}

function expressionLevelTone(v: string): Tone {
  if (v === "high") return "success";
  if (v === "moderate") return "warn";
  if (v === "low" || v === "absent") return "danger";
  return "neutral";
}

function expressionBreadthTone(v: string): Tone {
  if (v === "pan_tissue" || v === "broad") return "success";
  if (v === "restricted") return "warn";
  if (v === "rare") return "danger";
  return "neutral";
}

function surfaceSpecificityTone(v: string): Tone {
  if (v === "surface_dominant") return "success";
  if (v === "mixed") return "warn";
  if (v === "mostly_intracellular") return "danger";
  return "neutral";
}

/**
 * Ortholog ECD identity tone — higher conservation is BETTER (mouse /
 * cyno literature can stand in for human evidence). Thresholds from PR
 * #23 design + ICH S6(R1) biologics-development practice.
 */
function orthologIdentityTone(pct: number | null): Tone {
  if (pct == null) return "neutral";
  if (pct >= 85) return "success";
  if (pct >= 60) return "warn";
  return "danger";
}

/**
 * Paralog max-ECD-identity tone — higher identity is WORSE (more
 * potential antibody cross-reactivity). Inverse polarity from the
 * ortholog scale. Thresholds from Bordeaux et al. 2010 / Edfors et al.
 * 2018 antibody-validation literature.
 */
function paralogIdentityTone(pct: number | null): Tone {
  if (pct == null) return "success"; // no paralogs in the family = no cross-reactivity risk
  if (pct < 50) return "success";
  if (pct < 70) return "warn";
  return "danger";
}

/**
 * Build the ortholog pill label + tone. Handles the ECD-less case
 * (SRC, soluble proteins, GPI-anchored) by falling back to BioMart
 * full-length identity — preserves the chip's signal when the
 * human protein has no ECD to compare. Color polarity comes from
 * :func:`orthologIdentityTone` (higher = better).
 */
function orthologPillLabel(
  ecdPct: number | null,
  entries: OrthologEntry[],
): { text: string; tone: Tone; title?: string } {
  if (ecdPct != null) {
    return { text: `${ecdPct.toFixed(1)}% ECD`, tone: orthologIdentityTone(ecdPct) };
  }
  if (entries.length === 0) {
    return { text: "no Compara ortholog", tone: "neutral" };
  }
  // Ortholog exists, but no ECD to compare — fall back to full-length identity.
  const canonical = entries.find((e) => e.is_canonical) ?? entries[0];
  const fullPct = canonical.full_length_pct_identity_to_human_canonical;
  return {
    text: fullPct != null ? `${fullPct.toFixed(1)}% full-length (no ECD)` : "ortholog · no ECD",
    tone: orthologIdentityTone(fullPct),
    title:
      "Human protein has no ECD to compare (e.g. inner-leaflet, soluble, GPI-anchored). Showing full-length BioMart % identity instead.",
  };
}

// ---------------------------------------------------------------------------


export function FiltersCard({ rec, n }: Props) {
  const f = rec.filters;
  const topo = rec.deterministic_features.canonical_topology;
  const orthos = rec.deterministic_features.orthologs;
  const mousePill = orthologPillLabel(f.mouse_ortholog_ecd_pct_identity, orthos.mouse);
  const cynoPill = orthologPillLabel(f.cyno_ortholog_ecd_pct_identity, orthos.cynomolgus);
  const groups = [
    {
      label: "Accessibility",
      pills: [
        <StatusPill key="acc" tone={accessibilityTone(f.surface_accessibility)} size="sm">
          overall · {prettyEnum(f.surface_accessibility)}
        </StatusPill>,
        <StatusPill key="conf" tone={confidenceTone(f.confidence)} size="sm">
          conf · {prettyEnum(f.confidence)}
        </StatusPill>,
        <StatusPill key="sub" tone="neutral" size="sm">
          {prettyEnum(f.subcategory)}
        </StatusPill>,
        <StatusPill key="grade" tone={evidenceGradeTone(f.evidence_grade)} size="sm">
          {prettyEnum(f.evidence_grade)}
        </StatusPill>,
        <StatusPill key="ecd" tone={ecdAccessibilityTone(f.ecd_accessibility_class)} size="sm">
          ECD · {prettyEnum(f.ecd_accessibility_class)}
        </StatusPill>,
        <StatusPill key="dens" tone={evidenceDensityTone(f.evidence_density)} size="sm">
          evidence · {prettyEnum(f.evidence_density)}
        </StatusPill>,
      ],
    },
    {
      label: "Expression",
      pills: [
        <StatusPill key="level" tone={expressionLevelTone(f.expression_level)} size="sm">
          level · {prettyEnum(f.expression_level)}
        </StatusPill>,
        <StatusPill key="breadth" tone={expressionBreadthTone(f.expression_breadth)} size="sm">
          breadth · {prettyEnum(f.expression_breadth)}
        </StatusPill>,
        <StatusPill key="spec" tone={surfaceSpecificityTone(f.surface_specificity)} size="sm">
          {prettyEnum(f.surface_specificity)}
        </StatusPill>,
      ],
    },
    {
      label: "Risks",
      pills: [
        riskBoolPill("shed form", f.has_shed_form),
        riskBoolPill("secreted form", f.has_secreted_form),
        riskBoolPill("co-receptor for expression", f.requires_coreceptor_for_expression),
        riskBoolPill("epitope masking", f.has_epitope_masking),
        riskBoolPill("restricted subdomain", f.has_restricted_subdomain),
      ],
    },
    {
      label: "Cross-species (deterministic — higher conservation is better)",
      pills: [
        <StatusPill key="m" tone={mousePill.tone} size="sm" title={mousePill.title}>
          mouse · {mousePill.text}
        </StatusPill>,
        <StatusPill key="c" tone={cynoPill.tone} size="sm" title={cynoPill.title}>
          cyno · {cynoPill.text}
        </StatusPill>,
      ],
    },
    {
      label: "Paralogs (deterministic — lower max identity is better)",
      pills: [
        f.max_paralog_ecd_pct_identity == null ? (
          <StatusPill key="p" tone="success" size="sm">
            no Compara paralogs
          </StatusPill>
        ) : (
          <StatusPill
            key="p"
            tone={paralogIdentityTone(f.max_paralog_ecd_pct_identity)}
            size="sm"
          >
            max %ECD identity · {f.max_paralog_ecd_pct_identity.toFixed(1)}%
          </StatusPill>
        ),
      ],
    },
    {
      label: "Topology (deterministic)",
      pills: [
        <StatusPill key="tm" tone="neutral" size="sm">
          {topo.tm_helix_count} TM
        </StatusPill>,
        positiveBoolPill("N-term extracellular", f.n_term_extracellular),
        positiveBoolPill("C-term extracellular", f.c_term_extracellular),
      ],
    },
  ];

  return (
    <SectionCard
      n={n}
      eyebrow="Filters"
      title="Catalog membership and source coverage"
      meta="D1-indexed facets · informational here; the catalog page owns interactive filtering"
    >
      <div className={styles.groups}>
        {groups.map((g) => (
          <div key={g.label} className={styles.group}>
            <p className={`label-mono ${styles.groupLabel}`}>{g.label}</p>
            <ul className={styles.pills}>
              {g.pills.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
